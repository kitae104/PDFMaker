import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.entities import Chapter, Frame, GeneratedDocument, Job, JobStatus, KeyMoment, Project, SourceType, Transcript
from app.schemas.jobs import GenerationOptions
from app.schemas.pipeline import ChapterAnalysis, KeyMomentAnalysis, TranscriptData, TranscriptSegment
from app.services.document import DocumentGenerator
from app.services.llm.providers import get_llm_provider
from app.services.storage import StorageService
from app.services.transcript_parser import parse_transcript_file
from app.services.transcription.providers import get_transcription_provider
from app.services.video import VideoService
from app.services.vision.providers import get_vision_provider
from app.services.youtube import analyze_youtube_url, download_youtube_video, fetch_youtube_transcript

logger = logging.getLogger(__name__)


STATUS_PROGRESS = {
    JobStatus.ANALYZING_INPUT: 8,
    JobStatus.EXTRACTING_AUDIO: 18,
    JobStatus.TRANSCRIBING: 32,
    JobStatus.ANALYZING_TRANSCRIPT: 42,
    JobStatus.GENERATING_CHAPTERS: 52,
    JobStatus.SELECTING_KEY_MOMENTS: 62,
    JobStatus.CAPTURING_FRAMES: 72,
    JobStatus.GENERATING_CONTENT: 82,
    JobStatus.GENERATING_HTML: 90,
    JobStatus.GENERATING_PDF: 96,
    JobStatus.COMPLETED: 100,
}


class JobService:
    def __init__(self, db: Session):
        self.db = db
        self.storage = StorageService()

    def list_jobs(self) -> list[Job]:
        return self.db.query(Job).order_by(Job.created_at.desc()).limit(20).all()

    def create_video_job(self, source_path: Path, title: str, options: GenerationOptions) -> Job:
        project = Project(title=title, source_type=SourceType.VIDEO, source_path=str(source_path))
        self.db.add(project)
        self.db.flush()
        job = Job(project_id=project.id, options_json=options.model_dump_json())
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def create_youtube_job(self, url: str, title: str, options: GenerationOptions) -> Job:
        project = Project(title=title, source_type=SourceType.YOUTUBE, source_url=url)
        self.db.add(project)
        self.db.flush()
        job = Job(project_id=project.id, options_json=options.model_dump_json())
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def create_transcript_job(self, source_path: Path, title: str, options: GenerationOptions) -> Job:
        project = Project(title=title, source_type=SourceType.TRANSCRIPT, source_path=str(source_path))
        self.db.add(project)
        self.db.flush()
        job = Job(project_id=project.id, options_json=options.model_dump_json())
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def run_job(self, job_id: str) -> None:
        with SessionLocal() as db:
            runner = JobRunner(db)
            runner.run(job_id)


class JobRunner:
    def __init__(self, db: Session):
        self.db = db
        self.storage = StorageService()
        self.video = VideoService()
        self.stt = get_transcription_provider()
        self.llm = get_llm_provider()
        self.vision = get_vision_provider()
        self.document = DocumentGenerator()

    def run(self, job_id: str) -> None:
        job = self.db.get(Job, job_id)
        if not job:
            return
        try:
            job.started_at = datetime.utcnow()
            self._status(job, JobStatus.ANALYZING_INPUT)
            project = self.db.get(Project, job.project_id)
            if not project:
                raise RuntimeError("Missing project source")
            job_dir = self.storage.job_dir(job.id)
            source_path: Path | None = None
            if project.source_type == SourceType.VIDEO:
                if not project.source_path:
                    raise RuntimeError("Missing video file")
                source_path = Path(project.source_path)
                metadata = self.video.get_metadata(source_path)
                self._status(job, JobStatus.EXTRACTING_AUDIO)
                audio_path = self.video.extract_audio(source_path, job_dir / "audio" / "audio.wav")
                self._status(job, JobStatus.TRANSCRIBING)
                transcript = self.stt.transcribe(audio_path, float(metadata.get("duration") or 0))
            elif project.source_type == SourceType.YOUTUBE:
                metadata = analyze_youtube_url(project.source_url or "")
                self._status(job, JobStatus.TRANSCRIBING)
                transcript = fetch_youtube_transcript(project.source_url or "") or self._youtube_transcript(project.title, project.source_url or "", metadata)
                source_path = download_youtube_video(project.source_url or "", job_dir / "source")
                if source_path is None:
                    source_path = job_dir / "source" / "youtube-placeholder.mp4"
                    source_path.write_bytes(b"youtube placeholder")
            elif project.source_type == SourceType.TRANSCRIPT:
                if not project.source_path:
                    raise RuntimeError("Missing transcript source")
                metadata = {"duration": None, "channel": None, "thumbnail": None}
                self._status(job, JobStatus.TRANSCRIBING)
                transcript = parse_transcript_file(Path(project.source_path))
                source_path = job_dir / "source" / "transcript-placeholder.mp4"
                source_path.write_bytes(b"transcript placeholder")
            else:
                raise RuntimeError("Unsupported source type")
            transcript_path = job_dir / "transcript" / "transcript.json"
            transcript_path.write_text(transcript.model_dump_json(indent=2), encoding="utf-8")
            self.db.add(Transcript(project_id=project.id, language=transcript.language, duration=transcript.duration, content_path=str(transcript_path)))

            self._status(job, JobStatus.ANALYZING_TRANSCRIPT)
            self.llm.analyze_transcript(transcript)

            self._status(job, JobStatus.GENERATING_CHAPTERS)
            chapters = self.llm.generate_chapters(transcript)
            chapter_rows = self._save_chapters(project.id, chapters)

            self._status(job, JobStatus.SELECTING_KEY_MOMENTS)
            moments = self.llm.select_key_moments(transcript, chapters)
            moment_rows = self._save_moments(chapter_rows, moments)

            self._status(job, JobStatus.CAPTURING_FRAMES)
            frame_rows = self._capture_frames(source_path, job_dir, moment_rows)

            self._status(job, JobStatus.GENERATING_CONTENT)
            options = GenerationOptions.model_validate_json(job.options_json)
            lesson = self.llm.generate_lesson_content(transcript, chapters, moments, options)

            self._status(job, JobStatus.GENERATING_HTML)
            html_path = job_dir / "html" / "lecture.html"
            pdf_path = job_dir / "pdf" / "lecture.pdf"
            self.document.render_html(
                html_path,
                lesson,
                project={
                    "title": project.title,
                    "source_type": project.source_type.value,
                    "source_url": project.source_url,
                    "duration": metadata.get("duration"),
                    "channel": metadata.get("channel"),
                    "thumbnail": metadata.get("thumbnail"),
                },
                chapters=[self._chapter_dict(row) for row in chapter_rows],
                moments=[self._moment_dict(row) for row in moment_rows],
                frames=[self._frame_dict(row) for row in frame_rows],
            )

            self._status(job, JobStatus.GENERATING_PDF)
            self.document.generate_pdf(html_path, pdf_path)
            self.db.add(GeneratedDocument(project_id=project.id, type="pdf", html_path=str(html_path), pdf_path=str(pdf_path)))

            job.status = JobStatus.COMPLETED
            job.progress = 100
            job.completed_at = datetime.utcnow()
            self.db.commit()
            logger.info("[JOB %s] completed", job.id)
        except Exception as exc:
            logger.exception("[JOB %s] failed", job_id)
            job.status = JobStatus.FAILED
            job.progress = max(job.progress, 1)
            job.error_message = user_safe_error(exc)
            job.completed_at = datetime.utcnow()
            self.db.commit()

    def _status(self, job: Job, status: JobStatus) -> None:
        job.status = status
        job.progress = STATUS_PROGRESS.get(status, job.progress)
        self.db.commit()
        logger.info("[JOB %s] %s", job.id, status.value)

    def _youtube_transcript(self, title: str, url: str, metadata: dict) -> TranscriptData:
        channel = metadata.get("channel") or "Unknown channel"
        segments = [
            TranscriptSegment(start=0, end=45, text=f"이 자료는 YouTube 영상 '{title}'의 학습 노트 생성을 위해 준비되었습니다."),
            TranscriptSegment(start=45, end=110, text=f"영상 출처는 {channel} 채널이며 URL은 {url} 입니다."),
            TranscriptSegment(start=110, end=190, text="현재 로컬 MVP는 플랫폼 정책을 고려하여 원본 영상을 자동 다운로드하지 않고 메타데이터와 Mock 분석 흐름을 사용합니다."),
            TranscriptSegment(start=190, end=260, text="실제 강의 내용 기반 자료가 필요하면 같은 화면에서 원본 MP4 또는 Transcript 파일을 함께 업로드할 수 있습니다."),
            TranscriptSegment(start=260, end=320, text="Mock Provider는 Chapter, Key Moment, HTML 미리보기, PDF 생성 흐름을 검증하기 위한 예시 콘텐츠를 생성합니다."),
        ]
        return TranscriptData(language="ko", duration=320, segments=segments)

    def _save_chapters(self, project_id: str, analysis: ChapterAnalysis) -> list[Chapter]:
        rows = []
        for index, chapter in enumerate(analysis.chapters, start=1):
            row = Chapter(
                project_id=project_id,
                title=chapter.title,
                start_time=chapter.start,
                end_time=chapter.end,
                summary=chapter.summary,
                importance=chapter.importance,
                order=index,
            )
            self.db.add(row)
            rows.append(row)
        self.db.commit()
        return rows

    def _save_moments(self, chapters: list[Chapter], analysis: KeyMomentAnalysis) -> list[KeyMoment]:
        rows = []
        for index, moment in enumerate(analysis.keyMoments):
            chapter = chapters[min(index, len(chapters) - 1)]
            row = KeyMoment(
                chapter_id=chapter.id,
                timestamp=moment.timestamp,
                title=moment.title,
                reason=moment.reason,
                importance=moment.importance,
                selected=moment.captureRecommended and moment.importance >= settings.key_moment_threshold,
            )
            self.db.add(row)
            rows.append(row)
        self.db.commit()
        return rows

    def _capture_frames(self, source_path: Path, job_dir: Path, moments: list[KeyMoment]) -> list[Frame]:
        rows = []
        offsets = capture_offsets(settings.frame_capture_offset, settings.frame_capture_count)
        for moment in moments:
            if not moment.selected:
                continue
            paths = self.video.capture_frames(source_path, moment.timestamp, job_dir / "frames", offsets, moment.title)
            best = self.vision.select_best_frame(paths)
            for path in paths:
                row = Frame(
                    key_moment_id=moment.id,
                    timestamp=moment.timestamp,
                    path=str(path),
                    score=1.0 if path == best else 0.5,
                    selected=path == best,
                )
                self.db.add(row)
                rows.append(row)
        self.db.commit()
        return rows

    def _chapter_dict(self, row: Chapter) -> dict:
        return {"title": row.title, "start": row.start_time, "end": row.end_time, "summary": row.summary, "importance": row.importance}

    def _moment_dict(self, row: KeyMoment) -> dict:
        return {"title": row.title, "timestamp": row.timestamp, "reason": row.reason, "importance": row.importance, "selected": row.selected}

    def _frame_dict(self, row: Frame) -> dict:
        return {
            "path": row.path,
            "timestamp": row.timestamp,
            "selected": row.selected,
            "url": f"/storage/{self.storage.relative(Path(row.path))}",
            "uri": Path(row.path).resolve().as_uri(),
        }


def capture_offsets(offset: int, count: int) -> list[float]:
    if count <= 1:
        return [0]
    start = -abs(offset)
    end = abs(offset)
    step = (end - start) / (count - 1)
    return [round(start + index * step, 2) for index in range(count)]


def user_safe_error(exc: Exception) -> str:
    message = str(exc)
    if "ffmpeg" in message.lower():
        return "영상 처리 도구를 실행하는 중 문제가 발생했습니다. FFmpeg 설치 상태를 확인해주세요."
    return "강의자료를 생성하는 중 문제가 발생했습니다. 입력 파일을 확인하거나 Mock Provider 설정으로 다시 시도해주세요."
