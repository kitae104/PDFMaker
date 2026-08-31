import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.entities import Chapter, Frame, GeneratedDocument, Job, JobStatus, KeyMoment, Project, SourceType, Transcript
from app.schemas.jobs import GenerationOptions
from app.schemas.pipeline import ChapterAnalysis, KeyMomentAnalysis, LessonContent, TranscriptData, TranscriptSegment
from app.services.document import DocumentGenerator
from app.services.llm.providers import get_llm_provider
from app.services.storage import StorageService
from app.services.transcript_parser import normalize_transcript_segments, parse_transcript_file
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
    JobStatus.REVIEW_READY: 76,
    JobStatus.DOCUMENT_READY: 92,
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

    def get_review_segments(self, job_id: str) -> list[dict]:
        job = self.db.get(Job, job_id)
        if not job:
            return []
        return build_review_segments(self.db, self.storage, job)

    def update_scene_selection(self, job_id: str, moment_ids: list[str]) -> list[dict]:
        job = self.db.get(Job, job_id)
        if not job:
            return []
        allowed = set(moment_ids)
        rows = self.db.query(KeyMoment).join(Chapter).filter(Chapter.project_id == job.project_id).all()
        for row in rows:
            row.selected = row.id in allowed
        self.db.commit()
        return build_review_segments(self.db, self.storage, job)

    def generate_document_draft(self, job_id: str, moment_ids: list[str] | None = None) -> LessonContent:
        if moment_ids is not None:
            self.update_scene_selection(job_id, moment_ids)
        runner = JobRunner(self.db)
        return runner.generate_document_draft(job_id)

    def regenerate_scene_summaries(self, job_id: str) -> list[dict]:
        job = self.db.get(Job, job_id)
        if not job:
            return []
        runner = JobRunner(self.db)
        runner.regenerate_scene_summaries(job)
        return build_review_segments(self.db, self.storage, job)

    def render_pdf_from_content(self, job_id: str, content: LessonContent) -> Path:
        runner = JobRunner(self.db)
        return runner.render_pdf_from_content(job_id, content)


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

            self._status(job, JobStatus.SELECTING_KEY_MOMENTS)
            self._status(job, JobStatus.CAPTURING_FRAMES)
            self._create_scene_review(project.id, source_path, job_dir, transcript, metadata)

            job.status = JobStatus.REVIEW_READY
            job.progress = STATUS_PROGRESS[JobStatus.REVIEW_READY]
            job.completed_at = datetime.utcnow()
            self.db.commit()
            logger.info("[JOB %s] review ready", job.id)
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

    def _create_scene_review(self, project_id: str, source_path: Path, job_dir: Path, transcript: TranscriptData, metadata: dict) -> None:
        self._delete_existing_review(project_id)
        duration = float(metadata.get("duration") or transcript.duration or 0)
        scenes = self.video.detect_scene_changes(source_path, job_dir / "frames", duration)
        if not scenes:
            cover = job_dir / "frames" / "scene_0000.jpg"
            self.video.capture_frame(source_path, 0, cover, "Opening scene")
            scenes = [(0.0, cover)]
        scenes = sorted(scenes, key=lambda item: item[0])
        windows = scene_windows_from_detected_scenes(scenes, transcript)
        summaries = self.llm.summarize_scene_windows(windows)
        summary_by_id = {scene.id: scene for scene in summaries.scenes}
        for window in windows:
            index = int(window["id"])
            timestamp = float(window["timestamp"])
            frame_path = Path(window["frame_path"])
            scene_summary = summary_by_id.get(str(index))
            title = scene_summary.title if scene_summary else window["title"]
            summary = scene_summary.summary if scene_summary else window["summary"]
            chapter = Chapter(
                project_id=project_id,
                title=title,
                start_time=float(window["start"]),
                end_time=float(window["end"]),
                summary=summary,
                importance=8,
                order=index,
            )
            self.db.add(chapter)
            self.db.flush()
            moment = KeyMoment(
                chapter_id=chapter.id,
                timestamp=timestamp,
                title=title,
                reason=summary,
                importance=8,
                selected=True,
            )
            self.db.add(moment)
            self.db.flush()
            self.db.add(Frame(key_moment_id=moment.id, timestamp=timestamp, path=str(frame_path), score=1.0, selected=True))
        self.db.commit()

    def regenerate_scene_summaries(self, job: Job) -> None:
        transcript = load_transcript(self.db, job)
        rows = self.db.query(KeyMoment).join(Chapter).filter(Chapter.project_id == job.project_id).order_by(KeyMoment.timestamp).all()
        windows = []
        for moment in rows:
            start = moment.chapter.start_time
            end = moment.chapter.end_time
            segments = transcript_segments_between(transcript, start, end)
            windows.append(
                {
                    "id": moment.id,
                    "title": moment.title,
                    "summary": summarize_segments(segments),
                    "start": start,
                    "end": end,
                    "timestamp": moment.timestamp,
                    "segments": segments,
                }
            )
        summaries = self.llm.summarize_scene_windows(windows)
        summary_by_id = {scene.id: scene for scene in summaries.scenes}
        for moment in rows:
            scene_summary = summary_by_id.get(moment.id)
            if not scene_summary:
                continue
            moment.title = scene_summary.title
            moment.reason = scene_summary.summary
            moment.chapter.title = scene_summary.title
            moment.chapter.summary = scene_summary.summary
        self.db.commit()

    def _delete_existing_review(self, project_id: str) -> None:
        moments = self.db.query(KeyMoment).join(Chapter).filter(Chapter.project_id == project_id).all()
        for moment in moments:
            for frame in moment.frames:
                self.db.delete(frame)
            self.db.delete(moment)
        for chapter in self.db.query(Chapter).filter(Chapter.project_id == project_id).all():
            self.db.delete(chapter)
        self.db.commit()

    def generate_document_draft(self, job_id: str) -> LessonContent:
        job = self.db.get(Job, job_id)
        if not job:
            raise RuntimeError("Missing job")
        project = self.db.get(Project, job.project_id)
        transcript = load_transcript(self.db, job)
        windows = build_selected_windows(self.db, job, transcript)
        options = GenerationOptions.model_validate_json(job.options_json)
        self._status(job, JobStatus.GENERATING_CONTENT)
        lesson = self.llm.generate_lesson_from_scene_windows(project.title if project else "Lecture Notes", transcript, windows, options)
        job_dir = self.storage.job_dir(job.id)
        content_path = job_dir / "html" / "editable_document.json"
        content_path.parent.mkdir(parents=True, exist_ok=True)
        content_path.write_text(lesson.model_dump_json(indent=2), encoding="utf-8")
        self._status(job, JobStatus.GENERATING_HTML)
        self._render_document(job, lesson)
        job.status = JobStatus.DOCUMENT_READY
        job.progress = STATUS_PROGRESS[JobStatus.DOCUMENT_READY]
        self.db.commit()
        return lesson

    def render_pdf_from_content(self, job_id: str, content: LessonContent) -> Path:
        job = self.db.get(Job, job_id)
        if not job:
            raise RuntimeError("Missing job")
        job_dir = self.storage.job_dir(job.id)
        content_path = job_dir / "html" / "editable_document.json"
        content_path.parent.mkdir(parents=True, exist_ok=True)
        content_path.write_text(content.model_dump_json(indent=2), encoding="utf-8")
        self._status(job, JobStatus.GENERATING_HTML)
        html_path, pdf_path = self._render_document(job, content)
        self._status(job, JobStatus.GENERATING_PDF)
        self.document.generate_pdf(html_path, pdf_path)
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.completed_at = datetime.utcnow()
        self.db.commit()
        return pdf_path

    def _render_document(self, job: Job, lesson: LessonContent) -> tuple[Path, Path]:
        project = self.db.get(Project, job.project_id)
        job_dir = self.storage.job_dir(job.id)
        html_path = job_dir / "html" / "lecture.html"
        pdf_path = job_dir / "pdf" / "lecture.pdf"
        frames = selected_frame_dicts(self.db, self.storage, job)
        self.document.render_html(
            html_path,
            lesson,
            project={
                "title": project.title if project else lesson.title,
                "source_type": project.source_type.value if project else "",
                "source_url": project.source_url if project else None,
                "duration": None,
                "channel": None,
                "thumbnail": None,
            },
            chapters=[self._chapter_dict(row) for row in self.db.query(Chapter).filter(Chapter.project_id == job.project_id).order_by(Chapter.order).all()],
            moments=[self._moment_dict(row) for row in self.db.query(KeyMoment).join(Chapter).filter(Chapter.project_id == job.project_id).all()],
            frames=frames,
        )
        document = self.db.query(GeneratedDocument).filter(GeneratedDocument.project_id == job.project_id).first()
        if document:
            document.html_path = str(html_path)
            document.pdf_path = str(pdf_path)
        else:
            self.db.add(GeneratedDocument(project_id=job.project_id, type="pdf", html_path=str(html_path), pdf_path=str(pdf_path)))
        self.db.commit()
        return html_path, pdf_path

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


def load_transcript(db: Session, job: Job) -> TranscriptData:
    transcript_row = db.query(Transcript).filter(Transcript.project_id == job.project_id).first()
    if not transcript_row:
        raise RuntimeError("Missing transcript")
    transcript = TranscriptData.model_validate_json(Path(transcript_row.content_path).read_text(encoding="utf-8"))
    transcript.segments = normalize_transcript_segments(transcript.segments)
    transcript.duration = transcript.segments[-1].end if transcript.segments else transcript.duration
    return transcript


def transcript_segments_between(transcript: TranscriptData, start: float, end: float) -> list[TranscriptSegment]:
    return [segment for segment in transcript.segments if segment.end >= start and segment.start < end and segment.text.strip()]


def summarize_segments(segments: list[TranscriptSegment], limit: int = 360) -> str:
    text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
    if not text:
        return "이 구간에는 추출 가능한 스크립트가 많지 않습니다."
    return text[:limit].rstrip()


def scene_title(segments: list[TranscriptSegment], index: int) -> str:
    for segment in segments:
        words = segment.text.strip().split()
        if words:
            return " ".join(words[:8])[:80]
    return f"Scene {index}"


def scene_windows_from_detected_scenes(scenes: list[tuple[float, Path]], transcript: TranscriptData) -> list[dict]:
    windows = []
    for index, (timestamp, frame_path) in enumerate(scenes, start=1):
        start = 0.0 if index == 1 else timestamp
        end = scenes[index][0] if index < len(scenes) else transcript.duration
        segments = transcript_segments_between(transcript, start, end)
        windows.append(
            {
                "id": str(index),
                "title": scene_title(segments, index),
                "summary": summarize_segments(segments),
                "start": start,
                "end": end,
                "timestamp": timestamp,
                "frame_path": str(frame_path),
                "segments": segments,
            }
        )
    return windows


def build_review_segments(db: Session, storage: StorageService, job: Job) -> list[dict]:
    rows = db.query(KeyMoment).join(Chapter).filter(Chapter.project_id == job.project_id).order_by(KeyMoment.timestamp).all()
    result = []
    for moment in rows:
        frame = next((item for item in moment.frames if item.selected), moment.frames[0] if moment.frames else None)
        result.append(
            {
                "id": moment.id,
                "title": moment.title,
                "summary": moment.reason,
                "start": moment.chapter.start_time,
                "end": moment.chapter.end_time,
                "selected": moment.selected,
                "frame": None
                if not frame
                else {
                    "id": frame.id,
                    "url": f"/storage/{storage.relative(Path(frame.path))}",
                    "timestamp": frame.timestamp,
                },
            }
        )
    return result


def build_selected_windows(db: Session, job: Job, transcript: TranscriptData) -> list[dict]:
    moments = db.query(KeyMoment).join(Chapter).filter(Chapter.project_id == job.project_id, KeyMoment.selected.is_(True)).order_by(KeyMoment.timestamp).all()
    if not moments:
        moments = db.query(KeyMoment).join(Chapter).filter(Chapter.project_id == job.project_id).order_by(KeyMoment.timestamp).all()
    windows = []
    for index, moment in enumerate(moments):
        start = 0.0 if index == 0 else moment.timestamp
        end = moments[index + 1].timestamp if index + 1 < len(moments) else transcript.duration
        segments = transcript_segments_between(transcript, start, end)
        windows.append({"id": moment.id, "title": moment.title, "summary": moment.reason, "start": start, "end": end, "segments": segments})
    return windows


def selected_frame_dicts(db: Session, storage: StorageService, job: Job) -> list[dict]:
    moments = db.query(KeyMoment).join(Chapter).filter(Chapter.project_id == job.project_id, KeyMoment.selected.is_(True)).order_by(KeyMoment.timestamp).all()
    frames = []
    for moment in moments:
        frame = next((item for item in moment.frames if item.selected), moment.frames[0] if moment.frames else None)
        if frame:
            frames.append({"path": frame.path, "timestamp": frame.timestamp, "selected": True, "url": f"/storage/{storage.relative(Path(frame.path))}"})
    return frames
