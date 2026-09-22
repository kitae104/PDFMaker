"""OpenAI 호환 HTTP 계층 테스트. 실제 네트워크 없이 httpx.MockTransport로 응답을 고정한다."""

import json
import ssl

import certifi
import httpx
import pytest

from app.schemas.jobs import GenerationOptions
from app.schemas.pipeline import TranscriptData, TranscriptSegment
from app.services.llm import openai as openai_module
from app.services.llm.gemini import GeminiLLMProvider
from app.services.llm.mock import MockLLMProvider
from app.services.llm.openai import (
    LLMResponseFormatError,
    LLMResponseTruncatedError,
    OpenAILLMProvider,
    build_http_client,
    classify_llm_error,
)


def chat_response(content: str | None, finish_reason: str = "stop", status: int = 200, headers: dict | None = None) -> httpx.Response:
    body = {"choices": [{"index": 0, "finish_reason": finish_reason, "message": {"role": "assistant", "content": content}}]}
    return httpx.Response(status, json=body, headers=headers or {})


@pytest.fixture
def transport(monkeypatch):
    """handler 목록을 차례로 소비하는 MockTransport를 build_http_client에 주입한다."""
    state: dict = {"handlers": [], "requests": [], "sleeps": [], "timeouts": []}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        step = state["handlers"].pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    def fake_client(timeout=None):
        state["timeouts"].append(timeout)
        return httpx.Client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(openai_module, "build_http_client", fake_client)
    monkeypatch.setattr(openai_module, "_sleep", lambda seconds: state["sleeps"].append(seconds))
    monkeypatch.setattr(openai_module.settings, "llm_max_retries", 3)
    return state


def make_provider(**kwargs) -> OpenAILLMProvider:
    return OpenAILLMProvider(api_key="test-key", model="test-model", base_url="https://llm.invalid/v1", **kwargs)


def test_chat_json_retries_429_with_retry_after_then_succeeds(transport):
    transport["handlers"] = [
        httpx.Response(429, headers={"Retry-After": "7"}, json={"error": "rate"}),
        httpx.Response(503, json={"error": "busy"}),
        chat_response('{"summary": "요약입니다"}'),
    ]

    data = make_provider()._chat_json("sys", "user", max_tokens=100)

    assert data == {"summary": "요약입니다"}
    assert len(transport["requests"]) == 3
    assert transport["sleeps"] == [7.0, 2.0]  # Retry-After 존중, 이후 지수 백오프(2**1)


def test_chat_json_retries_timeout_only_once_even_with_higher_max_retries(transport, monkeypatch):
    # W3: timeout·네트워크 오류는 llm_max_retries와 무관하게 최대 1회만 재시도한다 (이전 기대값: 1+2=3회 요청).
    monkeypatch.setattr(openai_module.settings, "llm_max_retries", 2)
    transport["handlers"] = [httpx.ReadTimeout("slow")] * 3

    with pytest.raises(httpx.ReadTimeout) as info:
        make_provider()._chat_json("sys", "user", max_tokens=100)

    assert len(transport["requests"]) == 2
    assert transport["sleeps"] == [1.0]
    assert classify_llm_error(info.value) == "응답 시간 초과"


def test_chat_json_does_not_retry_auth_error(transport):
    transport["handlers"] = [httpx.Response(401, json={"error": "bad key"})]

    with pytest.raises(httpx.HTTPStatusError) as info:
        make_provider()._chat_json("sys", "user", max_tokens=100)

    assert len(transport["requests"]) == 1
    assert classify_llm_error(info.value) == "인증 실패(401·403)"


def test_chat_json_does_not_retry_ssl_failure(transport):
    error = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in chain")
    transport["handlers"] = [error, chat_response("{}")]

    with pytest.raises(httpx.ConnectError) as info:
        make_provider()._chat_json("sys", "user", max_tokens=100)

    assert len(transport["requests"]) == 1
    assert classify_llm_error(info.value) == "SSL 인증서 검증 실패"


def test_finish_reason_length_is_truncation_error(transport):
    transport["handlers"] = [chat_response('{"summary": "잘린', finish_reason="length")]

    with pytest.raises(LLMResponseTruncatedError) as info:
        make_provider()._chat_json("sys", "user", max_tokens=100)

    assert classify_llm_error(info.value) == "응답 잘림"


def test_empty_content_is_format_error(transport):
    transport["handlers"] = [chat_response(None)]

    with pytest.raises(LLMResponseFormatError) as info:
        make_provider()._chat_json("sys", "user", max_tokens=100)

    assert classify_llm_error(info.value) == "응답 형식 오류"


@pytest.mark.parametrize(
    ("exc", "label"),
    [
        (httpx.HTTPStatusError("x", request=httpx.Request("POST", "https://x"), response=httpx.Response(429)), "요청 한도 초과(429)"),
        (httpx.HTTPStatusError("x", request=httpx.Request("POST", "https://x"), response=httpx.Response(404)), "모델 없음(404)"),
        (httpx.HTTPStatusError("x", request=httpx.Request("POST", "https://x"), response=httpx.Response(500)), "기타"),
        (httpx.ConnectError("connection refused"), "네트워크 오류"),
        (json.JSONDecodeError("bad", "{", 0), "응답 형식 오류"),
        (ssl.SSLCertVerificationError("verify failed"), "SSL 인증서 검증 실패"),
        (RuntimeError("?"), "기타"),
    ],
)
def test_classify_llm_error(exc, label):
    assert classify_llm_error(exc) == label


def test_ssl_error_is_detected_through_exception_chain():
    try:
        try:
            raise ssl.SSLCertVerificationError("verify failed")
        except ssl.SSLError as inner:
            raise httpx.ConnectError("connect failed") from inner
    except httpx.ConnectError as outer:
        assert classify_llm_error(outer) == "SSL 인증서 검증 실패"


def test_payload_includes_reasoning_effort_only_when_configured(transport):
    transport["handlers"] = [chat_response('{"ok": true}'), chat_response('{"ok": true}')]

    make_provider()._chat_json("sys", "user", max_tokens=50)
    make_provider(reasoning_effort="low")._chat_json("sys", "user", max_tokens=50)

    first, second = (json.loads(request.content) for request in transport["requests"])
    assert "reasoning_effort" not in first
    assert second["reasoning_effort"] == "low"
    assert second["max_tokens"] == 50
    assert second["response_format"] == {"type": "json_object"}


def test_gemini_provider_passes_reasoning_effort_setting(monkeypatch):
    monkeypatch.setattr("app.services.llm.gemini.settings.gemini_api_key", "test-gemini-key")
    monkeypatch.setattr("app.services.llm.gemini.settings.gemini_reasoning_effort", "none")
    assert GeminiLLMProvider().reasoning_effort == "none"

    monkeypatch.setattr("app.services.llm.gemini.settings.gemini_reasoning_effort", None)
    assert GeminiLLMProvider().reasoning_effort is None


def test_ping_sends_one_small_request_without_retry(transport):
    transport["handlers"] = [httpx.Response(429, json={"error": "rate"}), chat_response('{"ok": true}')]

    with pytest.raises(httpx.HTTPStatusError):
        make_provider().ping()
    assert len(transport["requests"]) == 1
    assert transport["timeouts"][0] <= openai_module.PING_TIMEOUT_SECONDS

    make_provider().ping()
    payload = json.loads(transport["requests"][1].content)
    assert payload["max_tokens"] == openai_module.PING_MAX_TOKENS


def test_build_http_client_prefers_ca_bundle(monkeypatch):
    captured = {}
    real_create = ssl.create_default_context

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real_create(*args, **kwargs)

    monkeypatch.setattr(openai_module.settings, "llm_ca_bundle", certifi.where())
    monkeypatch.setattr(openai_module.ssl, "create_default_context", spy)
    with build_http_client(5) as client:
        assert isinstance(client, httpx.Client)
    assert captured.get("cafile") == certifi.where()


def test_ssl_verify_uses_truststore_or_default(monkeypatch):
    monkeypatch.setattr(openai_module.settings, "llm_ca_bundle", None)
    monkeypatch.setattr(openai_module.settings, "llm_use_system_trust_store", False)
    assert openai_module._ssl_verify() is True

    monkeypatch.setattr(openai_module.settings, "llm_use_system_trust_store", True)
    verify = openai_module._ssl_verify()
    # truststore 설치 시 SSLContext, 미설치 시 certifi 기본값(True)으로 안전하게 동작한다.
    assert verify is True or isinstance(verify, ssl.SSLContext)


# ---- 폴백 경고 기록 ----


def make_windows(count: int, text: str = "장면 설명입니다.") -> list[dict]:
    return [
        {
            "id": str(index + 1),
            "title": f"{index + 1}번 장면",
            "summary": f"{index + 1}번 장면 요약",
            "start": float(index * 10),
            "end": float(index * 10 + 10),
            "segments": [TranscriptSegment(start=float(index * 10), end=float(index * 10 + 5), text=f"{index + 1}번 {text}")],
        }
        for index in range(count)
    ]


class FailingProvider(OpenAILLMProvider):
    """_chat_json이 지정한 예외를 던지는 provider (네트워크 없음)."""

    def __init__(self, exc: Exception, fail_when=lambda user: True):
        self.fallback = MockLLMProvider()
        self.exc = exc
        self.fail_when = fail_when

    def _chat_json(self, system: str, user: str, max_tokens: int) -> dict:
        if self.fail_when(user):
            raise self.exc
        scene = json.loads(user.split("Scene:\n", 1)[1])
        number = scene["scene_number"]
        return {"chapter": {"title": f"{number}. 개별 장면", "explanation": "설명"}}


def test_whole_lesson_failure_records_single_korean_warning():
    provider = FailingProvider(httpx.ReadTimeout("slow"))
    windows = make_windows(3)

    result = provider.generate_lesson_from_scene_windows("문서", TranscriptData(segments=[], duration=30), windows, GenerationOptions())

    assert len(result.chapters) == 3
    warnings = provider.drain_fallback_warnings()
    assert warnings == ["강의 본문 생성이 실패해 규칙 기반 대체 내용을 사용했습니다 (원인: 응답 시간 초과)"]
    assert provider.drain_fallback_warnings() == []


def test_scene_failures_are_grouped_into_ranges():
    # 배치 요청은 실패, 개별 재요청은 장면 3-10만 실패 → "장면 3-10" 한 줄로 묶인다.
    failing_scenes = set(range(3, 11))

    def fail_when(user: str) -> bool:
        if "Scene:\n" not in user:
            return True
        return json.loads(user.split("Scene:\n", 1)[1])["scene_number"] in failing_scenes

    provider = FailingProvider(httpx.ReadTimeout("slow"), fail_when)
    windows = make_windows(13)  # LESSON_CHUNK_THRESHOLD(12) 초과 → 배치 경로

    result = provider.generate_lesson_from_scene_windows("문서", TranscriptData(segments=[], duration=130), windows, GenerationOptions())

    assert len(result.chapters) == 13
    assert result.chapters[0].title == "1. 개별 장면"
    warnings = provider.drain_fallback_warnings()
    assert "장면 3-10의 강의 본문 생성이 실패해 규칙 기반 대체 내용을 사용했습니다 (원인: 응답 시간 초과)" in warnings
    assert any(message.startswith("강의 본문 생성 중 개요") for message in warnings)
    assert all("본문 생성" in message for message in warnings)


def test_scene_summary_failure_warning_and_mock_has_no_warnings():
    provider = FailingProvider(httpx.HTTPStatusError("x", request=httpx.Request("POST", "https://x"), response=httpx.Response(429)))
    provider.summarize_scene_windows(make_windows(2))
    provider.summarize_scene_windows(make_windows(2))  # 같은 문구는 중복 기록하지 않는다

    assert provider.drain_fallback_warnings() == ["장면 요약 생성이 실패해 규칙 기반 요약을 사용했습니다 (원인: 요청 한도 초과(429))"]
    assert MockLLMProvider().drain_fallback_warnings() == []


def test_warnings_never_leak_key_or_url():
    provider = FailingProvider(httpx.ConnectError("https://secret.invalid/v1?key=sk-test-123 refused"))
    provider.summarize_scene_windows(make_windows(1))

    (message,) = provider.drain_fallback_warnings()
    assert "sk-test" not in message and "secret.invalid" not in message
    assert message.endswith("(원인: 네트워크 오류)")


# ---- 도메인 치환 적용 범위 ----


class EchoLessonProvider(OpenAILLMProvider):
    def __init__(self):
        self.fallback = MockLLMProvider()

    def _chat_json(self, system: str, user: str, max_tokens: int) -> dict:
        return {
            "title": "한류 강의",
            "overview": "한류 콘텐츠의 확산",
            "learning_objectives": ["한류를 이해한다"],
            "chapters": [{"title": "1. 한류의 시작", "explanation": "한류가 퍼졌습니다.", "terms": [{"용어": "한류", "설명": "한국 대중문화 열풍"}]}],
            "final_summary": ["정리"],
            "review_questions": ["질문"],
        }


def test_domain_corrections_skipped_for_non_automotive_lesson(monkeypatch):
    monkeypatch.setattr("app.services.transcript_parser.settings.transcript_correction_profile", "auto")
    windows = make_windows(1, text="한류 드라마와 음악이 세계로 퍼지고 있습니다.")

    result = EchoLessonProvider().generate_lesson_from_scene_windows("문서", TranscriptData(segments=[], duration=10), windows, GenerationOptions())

    assert result.title == "한류 강의"
    assert result.chapters[0].explanation == "한류가 퍼졌습니다."
    assert result.chapters[0].terms == [{"term": "한류", "definition": "한국 대중문화 열풍"}]


def test_domain_corrections_applied_for_automotive_lesson(monkeypatch):
    monkeypatch.setattr("app.services.transcript_parser.settings.transcript_correction_profile", "auto")
    windows = make_windows(1, text="자동차 도료에는 한류와 첨가제가 들어갑니다.")

    result = EchoLessonProvider().generate_lesson_from_scene_windows("문서", TranscriptData(segments=[], duration=10), windows, GenerationOptions())

    assert result.chapters[0].terms == [{"term": "안료", "definition": "한국 대중문화 열풍"}]


def test_network_error_retry_is_limited_but_5xx_keeps_max_retries(transport):
    transport["handlers"] = [
        httpx.Response(503, json={"error": "busy"}),
        httpx.ConnectError("reset"),
        httpx.Response(502, json={"error": "busy"}),
        httpx.Response(500, json={"error": "busy"}),
    ]

    with pytest.raises(httpx.HTTPStatusError):
        make_provider()._chat_json("sys", "user", max_tokens=100)

    # 1+3회: 5xx는 llm_max_retries(3)를 그대로 쓰고, 그 사이 네트워크 오류 1회도 재시도됐다.
    assert len(transport["requests"]) == 4


def test_network_error_second_time_is_not_retried(transport):
    transport["handlers"] = [httpx.ConnectError("reset"), httpx.ConnectError("reset")]

    with pytest.raises(httpx.ConnectError):
        make_provider()._chat_json("sys", "user", max_tokens=100)

    assert len(transport["requests"]) == 2


BREAKER_WARNING_PREFIX = "AI 연결 문제로 이후 장면은 대체 내용으로 생성했습니다"


@pytest.mark.parametrize(
    "failure, reason",
    [
        (httpx.ReadTimeout("slow"), "응답 시간 초과"),
        (httpx.Response(401, json={"error": "auth"}), "인증 실패(401·403)"),
        (httpx.Response(404, json={"error": "model"}), "모델 없음(404)"),
        (httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"), "SSL 인증서 검증 실패"),
    ],
)
def test_circuit_breaker_opens_after_two_connection_failures(transport, failure, reason):
    per_call = 2 if isinstance(failure, httpx.ReadTimeout) else 1  # timeout은 1회 재시도
    transport["handlers"] = [failure] * (per_call * 2)
    provider = make_provider()

    for _ in range(2):
        with pytest.raises(Exception):
            provider._chat_json("sys", "user", max_tokens=100)
    requests_before = len(transport["requests"])

    with pytest.raises(openai_module.LLMCircuitOpenError) as info:
        provider._chat_json("sys", "user", max_tokens=100)

    assert len(transport["requests"]) == requests_before  # 네트워크 호출 없음
    assert classify_llm_error(info.value) == reason
    warnings = provider.drain_fallback_warnings()
    assert warnings == [f"{BREAKER_WARNING_PREFIX} (원인: {reason})"]


def test_circuit_breaker_counter_resets_on_success(transport):
    transport["handlers"] = [
        httpx.Response(401, json={"error": "auth"}),
        chat_response('{"ok": true}'),
        httpx.Response(401, json={"error": "auth"}),
        chat_response('{"ok": true}'),
    ]
    provider = make_provider()

    with pytest.raises(httpx.HTTPStatusError):
        provider._chat_json("sys", "user", max_tokens=100)
    assert provider._chat_json("sys", "user", max_tokens=100) == {"ok": True}
    with pytest.raises(httpx.HTTPStatusError):
        provider._chat_json("sys", "user", max_tokens=100)
    assert provider._chat_json("sys", "user", max_tokens=100) == {"ok": True}

    assert len(transport["requests"]) == 4
    assert provider.drain_fallback_warnings() == []


def test_non_connection_failure_does_not_trip_breaker(transport, monkeypatch):
    monkeypatch.setattr(openai_module.settings, "llm_max_retries", 0)
    transport["handlers"] = [
        httpx.Response(401, json={"error": "auth"}),
        httpx.Response(500, json={"error": "boom"}),
        httpx.Response(401, json={"error": "auth"}),
        chat_response('{"ok": true}'),
    ]
    provider = make_provider()

    for _ in range(3):
        with pytest.raises(httpx.HTTPStatusError):
            provider._chat_json("sys", "user", max_tokens=100)
    assert provider._chat_json("sys", "user", max_tokens=100) == {"ok": True}


def test_breaker_is_per_instance_and_ping_bypasses_it(transport):
    transport["handlers"] = [httpx.Response(401, json={"error": "auth"})] * 2 + [chat_response('{"ok": true}')] * 2
    tripped = make_provider()
    for _ in range(2):
        with pytest.raises(httpx.HTTPStatusError):
            tripped._chat_json("sys", "user", max_tokens=100)

    tripped.ping()  # 연결 점검은 브레이커와 무관하게 실제로 한 번 보낸다
    assert make_provider()._chat_json("sys", "user", max_tokens=100) == {"ok": True}
    assert len(transport["requests"]) == 4


def test_breaker_bounds_batched_lesson_generation(transport):
    """장면 12개 초과 배치 경로에서 연결이 계속 끊겨도 요청 수가 2회 호출분으로 끝나고 전 장면이 폴백된다."""
    transport["handlers"] = [httpx.ReadTimeout("slow")] * 4
    provider = make_provider()
    windows = [
        {
            "start": index * 10.0,
            "end": index * 10.0 + 10,
            "timestamp": f"00:{index:02d}",
            "summary": f"장면 {index + 1} 요약",
            "segments": [TranscriptSegment(start=index * 10.0, end=index * 10.0 + 5, text=f"장면 {index + 1} 자막 내용입니다.")],
        }
        for index in range(14)
    ]
    transcript = TranscriptData(segments=[TranscriptSegment(start=0, end=5, text="자막")], duration=140)

    lesson = provider.generate_lesson_from_scene_windows("제목", transcript, windows, GenerationOptions())

    assert len(transport["requests"]) == 4  # 호출 2회 × (1 + 재시도 1)
    assert len(lesson.chapters) == 14
    warnings = provider.drain_fallback_warnings()
    assert f"{BREAKER_WARNING_PREFIX} (원인: 응답 시간 초과)" in warnings
    assert sum(BREAKER_WARNING_PREFIX in item for item in warnings) == 1
