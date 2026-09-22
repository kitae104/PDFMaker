"""Regression tests for deployment hardening: settings resolution, startup validation,
job warnings, YouTube caption failures, transcript correction profile and F1 status recovery."""

import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import config
from app.core.database import Base, get_db
from app.core.exceptions import AppError, register_exception_handlers
from app.models.entities import Job, JobStatus
from app.schemas.jobs import GenerationOptions
from app.services import job_service
from app.services.document import DocumentGenerator
from app.services.llm import providers
from app.services.llm.mock import MockLLMProvider
from app.services.storage import StorageService
from app.services.transcript_parser import (
    correct_common_transcript_terms,
    normalize_transcript_segments,
    parse_srt,
    should_apply_domain_corrections,
)
from app.services.video import VideoService
from app.services.youtube import YOUTUBE_TRANSCRIPT_UNAVAILABLE_MESSAGE, YouTubeTranscriptUnavailableError, pick_caption
from app.schemas.pipeline import TranscriptSegment

BACKEND_DIR = Path(__file__).resolve().parents[1]

TRANSCRIPT_SRT = "\n\n".join(
    [
        "1\n00:00:00,000 --> 00:00:20,000\n오늘은 데이터 구조의 기본 개념을 설명합니다.",
        "2\n00:00:25,000 --> 00:00:50,000\n스택은 나중에 넣은 값을 먼저 꺼내는 구조입니다.",
        "3\n00:00:55,000 --> 00:01:20,000\n큐는 먼저 넣은 값을 먼저 꺼내는 구조입니다.",
    ]
)


# ---------------------------------------------------------------- fixtures


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "storage_path", tmp_path / "storage")
    monkeypatch.setattr(config.settings, "llm_provider", "mock")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    monkeypatch.setattr(job_service, "SessionLocal", session_factory)
    session = session_factory()

    def fake_scenes(self, source_path, output_dir, duration, *args, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        scenes = []
        for index, timestamp in enumerate([0.0, 25.0, 55.0]):
            path = output_dir / f"scene_{index:04d}.jpg"
            Image.new("RGB", (64, 36), (200, 200, 200)).save(path)
            scenes.append((timestamp, path))
        return scenes

    monkeypatch.setattr(VideoService, "detect_scene_changes", fake_scenes)
    try:
        yield session, session_factory
    finally:
        session.close()
        engine.dispose()


def make_client(session_factory) -> TestClient:
    from app.api.routes import health, jobs

    app = FastAPI()
    app.include_router(health.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    register_exception_handlers(app)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app, raise_server_exceptions=False)


def create_ready_transcript_job(db, tmp_path) -> Job:
    source = tmp_path / "lecture.srt"
    source.write_text(TRANSCRIPT_SRT, encoding="utf-8")
    service = job_service.JobService(db)
    job = service.create_transcript_job(source, "자료구조", GenerationOptions())
    job_service.JobRunner(db).run(job.id)
    db.refresh(job)
    assert job.status == JobStatus.REVIEW_READY, job.error_message
    return job


# ---------------------------------------------------------------- settings


def test_relative_sqlite_url_is_resolved_against_backend_dir():
    url = config.resolve_sqlite_url("sqlite:///./storage/app.db")
    assert url == f"sqlite:///{(BACKEND_DIR / 'storage' / 'app.db').resolve().as_posix()}"
    assert config.resolve_sqlite_url("sqlite://") == "sqlite://"
    assert config.resolve_sqlite_url("sqlite:///:memory:") == "sqlite:///:memory:"
    assert config.resolve_sqlite_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    absolute = (BACKEND_DIR / "x.db").resolve().as_posix()
    assert config.resolve_sqlite_url(f"sqlite:///{absolute}") == f"sqlite:///{absolute}"


def test_settings_paths_are_backend_relative_and_env_file_absolute():
    assert config.BACKEND_DIR == BACKEND_DIR
    assert config.ROOT_DIR == BACKEND_DIR.parent
    env_file = Path(config.Settings.model_config["env_file"])
    assert env_file.is_absolute()
    assert env_file == BACKEND_DIR.parent / ".env"
    settings = config.Settings(_env_file=None, storage_path="./storage", database_url="sqlite:///./storage/app.db")
    assert settings.storage_path == (BACKEND_DIR / "storage").resolve()
    assert settings.database_url.endswith((BACKEND_DIR / "storage" / "app.db").resolve().as_posix())


def test_settings_resolution_does_not_depend_on_cwd(tmp_path):
    # Values are compared inside the child process; nothing from .env is printed.
    script = (
        "import hashlib; from app.core.config import settings;"
        "print(hashlib.sha256((str(settings.storage_path)+'|'+settings.database_url+'|'+settings.llm_provider).encode()).hexdigest())"
    )
    env = {"PYTHONPATH": str(BACKEND_DIR)}
    import os

    env = {**os.environ, **env}
    outputs = []
    for cwd in [BACKEND_DIR, BACKEND_DIR.parent, tmp_path]:
        result = subprocess.run([sys.executable, "-c", script], cwd=cwd, env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, "settings import failed"
        outputs.append(result.stdout.strip())
    assert len(set(outputs)) == 1


# ---------------------------------------------------------------- startup validation


@pytest.mark.parametrize(
    ("provider", "openai_key", "gemini_key"),
    [("bogus", None, None), ("openai", None, "g"), ("gemini", "o", None), ("gemini", None, "")],
)
def test_validate_llm_settings_rejects_unusable_config(monkeypatch, provider, openai_key, gemini_key):
    monkeypatch.setattr(providers.settings, "llm_provider", provider)
    monkeypatch.setattr(providers.settings, "openai_api_key", openai_key)
    monkeypatch.setattr(providers.settings, "gemini_api_key", gemini_key)
    with pytest.raises(providers.LLMConfigurationError):
        providers.validate_llm_settings()


@pytest.mark.parametrize("provider", ["mock", "ollama", "MOCK"])
def test_validate_llm_settings_allows_keyless_providers(monkeypatch, provider):
    monkeypatch.setattr(providers.settings, "llm_provider", provider)
    monkeypatch.setattr(providers.settings, "openai_api_key", None)
    monkeypatch.setattr(providers.settings, "gemini_api_key", None)
    providers.validate_llm_settings()
    assert providers.effective_llm_provider_name() == "mock"
    assert providers.effective_llm_model() is None


def test_effective_provider_reports_gemini_model(monkeypatch):
    monkeypatch.setattr(providers.settings, "llm_provider", "gemini")
    monkeypatch.setattr(providers.settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(providers.settings, "gemini_model", "gemini-test")
    providers.validate_llm_settings()
    assert providers.effective_llm_provider_name() == "gemini"
    assert providers.effective_llm_model() == "gemini-test"


def test_create_app_fails_on_invalid_llm_provider(monkeypatch):
    monkeypatch.setattr(config.settings, "llm_provider", "mock")
    from app import main

    monkeypatch.setattr(config.settings, "llm_provider", "bogus")
    with pytest.raises(providers.LLMConfigurationError):
        main.create_app()


# ---------------------------------------------------------------- health


def test_health_reports_effective_providers(db_session):
    _, factory = db_session
    client = make_client(factory)
    data = client.get("/api/health").json()
    assert data["llm_provider"] == "mock"
    assert data["llm_model"] is None
    assert data["stt_provider"] == "mock"
    llm = client.get("/api/health/llm").json()
    assert llm == {"ok": True, "provider": "mock", "model": None, "latency_ms": None, "error": None}


def test_health_llm_classifies_failure_without_leaking_details(db_session, monkeypatch):
    _, factory = db_session
    monkeypatch.setattr(providers.settings, "llm_provider", "gemini")
    monkeypatch.setattr(providers.settings, "gemini_api_key", "secret-test-key")
    monkeypatch.setattr(providers.settings, "gemini_model", "gemini-test")

    def failing_ping(self):
        raise httpx.ReadTimeout("timed out calling https://internal.example/v1?key=secret-test-key")

    from app.services.llm.openai import OpenAILLMProvider

    monkeypatch.setattr(OpenAILLMProvider, "ping", failing_ping)
    response = make_client(factory).get("/api/health/llm")
    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is False
    assert body["provider"] == "gemini"
    assert body["model"] == "gemini-test"
    assert body["error"] == "응답 시간 초과"
    assert isinstance(body["latency_ms"], int)
    assert "secret" not in response.text and "internal.example" not in response.text


# ---------------------------------------------------------------- YouTube


def test_pick_caption_prefers_original_auto_caption_over_translation():
    info = {
        "language": "en",
        "automatic_captions": {
            "ko": [{"ext": "vtt", "url": "https://x/timedtext?lang=en&tlang=ko"}],
            "en-orig": [{"ext": "json3", "url": "https://x/j"}, {"ext": "vtt", "url": "https://x/timedtext?lang=en"}],
            "en": [{"ext": "vtt", "url": "https://x/timedtext?lang=en&kind=asr"}],
        },
    }
    chosen = pick_caption(info)
    assert chosen["url"] == "https://x/timedtext?lang=en"
    assert chosen["language"] == "en"


def test_pick_caption_uses_original_language_auto_caption_without_orig_key():
    info = {
        "language": "ko",
        "automatic_captions": {
            "en": [{"ext": "vtt", "url": "https://x/t?lang=ko&tlang=en"}],
            "ko": [{"ext": "vtt", "url": "https://x/t?lang=ko"}],
        },
    }
    assert pick_caption(info)["url"] == "https://x/t?lang=ko"


def test_pick_caption_rejects_machine_translations_and_non_vtt():
    only_translated = {"language": "en", "automatic_captions": {"ko": [{"ext": "vtt", "url": "https://x/t?tlang=ko"}]}}
    assert pick_caption(only_translated) is None
    non_vtt = {"subtitles": {"ko": [{"ext": "srv3", "url": "https://x/s"}]}, "automatic_captions": {}}
    assert pick_caption(non_vtt) is None


def test_pick_caption_prefers_manual_korean_subtitles():
    info = {
        "language": "en",
        "subtitles": {"en": [{"ext": "vtt", "url": "https://x/en"}], "ko": [{"ext": "vtt", "url": "https://x/ko"}]},
        "automatic_captions": {"en-orig": [{"ext": "vtt", "url": "https://x/auto"}]},
    }
    chosen = pick_caption(info)
    assert chosen["url"] == "https://x/ko"
    assert chosen["language"] == "ko"


def test_fetch_youtube_transcript_raises_when_no_caption(monkeypatch):
    from app.services import youtube

    monkeypatch.setattr(youtube, "extract_youtube_info", lambda url: {"subtitles": {}, "automatic_captions": {}})
    with pytest.raises(YouTubeTranscriptUnavailableError):
        youtube.fetch_youtube_transcript("https://www.youtube.com/watch?v=JKj7eTi0Axo")

    def blocked(url):
        raise RuntimeError("Sign in to confirm you're not a bot")

    monkeypatch.setattr(youtube, "extract_youtube_info", blocked)
    with pytest.raises(YouTubeTranscriptUnavailableError):
        youtube.fetch_youtube_transcript("https://www.youtube.com/watch?v=JKj7eTi0Axo")


def test_youtube_job_fails_with_clear_message_when_captions_unavailable(db_session, monkeypatch):
    db, _ = db_session
    monkeypatch.setattr(job_service, "analyze_youtube_url", lambda url: {"duration": 120, "channel": "c"})

    def no_captions(url):
        raise YouTubeTranscriptUnavailableError()

    def must_not_download(*args, **kwargs):
        raise AssertionError("download should not run without captions")

    monkeypatch.setattr(job_service, "fetch_youtube_transcript", no_captions)
    monkeypatch.setattr(job_service, "download_youtube_video", must_not_download)
    service = job_service.JobService(db)
    job = service.create_youtube_job("https://www.youtube.com/watch?v=JKj7eTi0Axo", "영상", GenerationOptions())
    job_service.JobRunner(db).run(job.id)
    db.refresh(job)
    assert job.status == JobStatus.FAILED
    assert job.error_message == YOUTUBE_TRANSCRIPT_UNAVAILABLE_MESSAGE
    assert not (StorageService().job_dir(job.id) / "transcript" / "transcript.json").exists()


# ---------------------------------------------------------------- transcript correction profile


def test_domain_corrections_skip_non_automotive_text(monkeypatch):
    monkeypatch.setattr(config.settings, "transcript_correction_profile", "auto")
    texts = ["한류 열풍이 이어지고", "포면 가공 공정을 소개합니다"]
    assert should_apply_domain_corrections(texts) is False
    segments = normalize_transcript_segments([TranscriptSegment(start=0, end=2, text="한류 열풍, 포면 가공")])
    assert segments[0].text == "한류 열풍, 포면 가공"


def test_domain_corrections_apply_to_automotive_text(monkeypatch):
    monkeypatch.setattr(config.settings, "transcript_correction_profile", "auto")
    assert should_apply_domain_corrections(["자동차 도장에서 알료와 우래탄을 배학합니다"]) is True
    data = parse_srt("1\n00:00:01,000 --> 00:00:03,000\n자동차 도장용 알료와 청가제\n")
    assert data.segments[0].text == "자동차 도장용 안료와 첨가제"


def test_domain_correction_profiles(monkeypatch):
    monkeypatch.setattr(config.settings, "transcript_correction_profile", "none")
    assert should_apply_domain_corrections(["자동차 도장 페인트 안료"]) is False
    monkeypatch.setattr(config.settings, "transcript_correction_profile", "automotive")
    assert should_apply_domain_corrections(["한류"]) is True
    assert correct_common_transcript_terms("한류", enabled=False) == "한류"
    assert correct_common_transcript_terms("한류", enabled=True) == "안료"


# ---------------------------------------------------------------- warnings


def test_storage_warnings_dedupe_and_replace(tmp_path):
    storage = StorageService(tmp_path)
    job_id = "b" * 32
    assert storage.read_warnings(job_id) == []
    storage.add_warnings(job_id, ["A", "A", "장면 1의 강의 본문 생성이 실패"])
    assert storage.read_warnings(job_id) == ["A", "장면 1의 강의 본문 생성이 실패"]
    storage.add_warnings(job_id, ["장면 2의 강의 본문 생성이 실패"], replace_containing="본문 생성")
    assert storage.read_warnings(job_id) == ["A", "장면 2의 강의 본문 생성이 실패"]
    assert storage.read_warnings("../etc") == []


def test_mock_llm_warning_is_exposed_on_job_response(db_session, tmp_path):
    db, factory = db_session
    job = create_ready_transcript_job(db, tmp_path)
    client = make_client(factory)
    body = client.get(f"/api/jobs/{job.id}").json()
    assert body["warnings"] == [job_service.MOCK_LLM_WARNING]
    listed = client.get("/api/jobs").json()
    assert listed[0]["warnings"] == [job_service.MOCK_LLM_WARNING]
    # A second draft does not duplicate the mock warning.
    job_service.JobService(db).generate_document_draft(job.id)
    job_service.JobService(db).generate_document_draft(job.id)
    assert StorageService().read_warnings(job.id) == [job_service.MOCK_LLM_WARNING]


def test_lesson_fallback_warnings_are_replaced_by_new_draft(db_session, tmp_path, monkeypatch):
    db, _ = db_session
    job = create_ready_transcript_job(db, tmp_path)
    calls = {"n": 0}

    class FlakyProvider(MockLLMProvider):
        def generate_lesson_from_scene_windows(self, *args, **kwargs):
            calls["n"] += 1
            self._record_fallback_warning(f"장면 {calls['n']}의 강의 본문 생성이 실패해 규칙 기반 대체 내용을 사용했습니다 (원인: 응답 시간 초과)")
            return super().generate_lesson_from_scene_windows(*args, **kwargs)

    monkeypatch.setattr(job_service, "get_llm_provider", lambda: FlakyProvider())
    job_service.JobService(db).generate_document_draft(job.id)
    job_service.JobService(db).generate_document_draft(job.id)
    warnings = StorageService().read_warnings(job.id)
    assert [item for item in warnings if "본문 생성" in item] == [
        "장면 2의 강의 본문 생성이 실패해 규칙 기반 대체 내용을 사용했습니다 (원인: 응답 시간 초과)"
    ]
    assert job_service.MOCK_LLM_WARNING in warnings


def test_video_job_with_mock_stt_records_warning(db_session, tmp_path, monkeypatch):
    db, _ = db_session
    monkeypatch.setattr(VideoService, "get_metadata", lambda self, path: {"duration": 90})

    def fake_audio(self, input_path, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"")
        return output_path

    monkeypatch.setattr(VideoService, "extract_audio", fake_audio)
    source = tmp_path / "lecture.mp4"
    source.write_bytes(b"fake")
    service = job_service.JobService(db)
    job = service.create_video_job(source, "lecture", GenerationOptions())
    job_service.JobRunner(db).run(job.id)
    db.refresh(job)
    assert job.status == JobStatus.REVIEW_READY
    warnings = StorageService().read_warnings(job.id)
    assert job_service.MOCK_STT_VIDEO_WARNING in warnings
    assert job_service.MOCK_LLM_WARNING in warnings


# ---------------------------------------------------------------- F1: status recovery


def test_document_draft_failure_restores_review_ready(db_session, tmp_path, monkeypatch):
    db, factory = db_session
    job = create_ready_transcript_job(db, tmp_path)

    def broken_render(self, *args, **kwargs):
        raise OSError("disk full at C:/secret/path")

    monkeypatch.setattr(DocumentGenerator, "render_html", broken_render)
    with pytest.raises(AppError):
        job_service.JobService(db).generate_document_draft(job.id)
    check = factory()
    stored = check.get(Job, job.id)
    assert stored.status == JobStatus.REVIEW_READY
    assert stored.progress == job_service.STATUS_PROGRESS[JobStatus.REVIEW_READY]
    assert stored.error_message and "secret" not in stored.error_message
    check.close()

    response = make_client(factory).post(f"/api/jobs/{job.id}/document-draft")
    assert response.status_code == 500
    assert "secret" not in response.text
    assert make_client(factory).get(f"/api/jobs/{job.id}").json()["status"] == "REVIEW_READY"


def test_document_draft_success_clears_previous_error(db_session, tmp_path, monkeypatch):
    db, factory = db_session
    job = create_ready_transcript_job(db, tmp_path)
    original = DocumentGenerator.render_html

    def broken_render(self, *args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(DocumentGenerator, "render_html", broken_render)
    with pytest.raises(AppError):
        job_service.JobService(db).generate_document_draft(job.id)
    monkeypatch.setattr(DocumentGenerator, "render_html", original)
    job_service.JobService(db).generate_document_draft(job.id)
    check = factory()
    stored = check.get(Job, job.id)
    assert stored.status == JobStatus.DOCUMENT_READY
    assert stored.error_message is None
    check.close()


def test_pdf_failure_restores_document_ready(db_session, tmp_path, monkeypatch):
    db, factory = db_session
    job = create_ready_transcript_job(db, tmp_path)
    lesson = job_service.JobService(db).generate_document_draft(job.id)

    def broken_pdf(self, *args, **kwargs):
        raise RuntimeError("playwright browser missing")

    monkeypatch.setattr(DocumentGenerator, "generate_pdf", broken_pdf)
    with pytest.raises(AppError):
        job_service.JobService(db).render_pdf_from_content(job.id, lesson)
    check = factory()
    stored = check.get(Job, job.id)
    assert stored.status == JobStatus.DOCUMENT_READY
    assert stored.progress == job_service.STATUS_PROGRESS[JobStatus.DOCUMENT_READY]
    assert stored.error_message
    check.close()

    response = make_client(factory).post(f"/api/jobs/{job.id}/pdf", json=json.loads(lesson.model_dump_json()))
    assert response.status_code == 500
    assert make_client(factory).get(f"/api/jobs/{job.id}").json()["status"] == "DOCUMENT_READY"


def _break_lesson_generation(monkeypatch):
    def broken_lesson(self, *args, **kwargs):
        raise RuntimeError("llm exploded at C:/secret/path")

    monkeypatch.setattr(MockLLMProvider, "generate_lesson_from_scene_windows", broken_lesson)


def _draft_path(job: Job) -> Path:
    return StorageService().job_dir(job.id) / "html" / "editable_document.json"


@pytest.mark.parametrize("prior_status", [JobStatus.DOCUMENT_READY, JobStatus.COMPLETED])
def test_draft_regeneration_failure_keeps_existing_draft_visible(db_session, tmp_path, monkeypatch, prior_status):
    """W4: regenerating over an existing draft must fall back to DOCUMENT_READY, otherwise the
    ResultsPage stops loading the draft after a refresh."""
    db, factory = db_session
    job = create_ready_transcript_job(db, tmp_path)
    job_service.JobService(db).generate_document_draft(job.id)
    draft_before = _draft_path(job).read_text(encoding="utf-8")
    db.refresh(job)
    job.status = prior_status
    job.progress = 100 if prior_status == JobStatus.COMPLETED else job_service.STATUS_PROGRESS[prior_status]
    db.commit()

    _break_lesson_generation(monkeypatch)
    with pytest.raises(AppError):
        job_service.JobService(db).generate_document_draft(job.id)
    check = factory()
    stored = check.get(Job, job.id)
    assert stored.status == JobStatus.DOCUMENT_READY
    assert stored.progress == job_service.STATUS_PROGRESS[JobStatus.DOCUMENT_READY]
    assert stored.error_message and "secret" not in stored.error_message
    check.close()
    assert _draft_path(job).read_text(encoding="utf-8") == draft_before

    client = make_client(factory)
    response = client.post(f"/api/jobs/{job.id}/document-draft")
    assert response.status_code == 500
    assert "secret" not in response.text
    assert client.get(f"/api/jobs/{job.id}").json()["status"] == "DOCUMENT_READY"
    assert client.get(f"/api/jobs/{job.id}/document-draft").status_code == 200


def test_draft_regeneration_failure_without_draft_file_restores_review_ready(db_session, tmp_path, monkeypatch):
    db, factory = db_session
    job = create_ready_transcript_job(db, tmp_path)
    job_service.JobService(db).generate_document_draft(job.id)
    _draft_path(job).unlink()

    _break_lesson_generation(monkeypatch)
    with pytest.raises(AppError):
        job_service.JobService(db).generate_document_draft(job.id)
    check = factory()
    stored = check.get(Job, job.id)
    assert stored.status == JobStatus.REVIEW_READY
    assert stored.progress == job_service.STATUS_PROGRESS[JobStatus.REVIEW_READY]
    check.close()
