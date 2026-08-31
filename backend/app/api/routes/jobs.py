import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppError
from app.models.entities import Chapter, Frame, GeneratedDocument, Job, KeyMoment, Transcript
from app.schemas.jobs import GenerationOptions, JobResponse, YouTubeJobCreate
from app.services.job_service import JobService
from app.services.storage import StorageService
from app.services.youtube import analyze_youtube_url

router = APIRouter(prefix="/jobs", tags=["jobs"])


def to_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id,
        project_id=job.project_id,
        project_title=job.project.title,
        source_type=job.project.source_type,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.post("", response_model=JobResponse)
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    material_type: str = Form("Detailed Lecture"),
    difficulty: str = Form("대학생 수준"),
    pdf_length: str = Form("Auto"),
    db: Session = Depends(get_db),
) -> JobResponse:
    storage = StorageService()
    staging = storage.root / "uploads"
    staging.mkdir(parents=True, exist_ok=True)
    source = await storage.save_upload(file, staging)
    options = GenerationOptions(material_type=material_type, difficulty=difficulty, pdf_length=pdf_length)
    service = JobService(db)
    job = service.create_video_job(source, Path(source).stem, options)
    job_dir = storage.job_dir(job.id)
    final_source = storage.copy_into(source, job_dir / "source" / source.name)
    source.unlink(missing_ok=True)
    job.project.source_path = str(final_source)
    db.commit()
    background_tasks.add_task(service.run_job, job.id)
    db.refresh(job)
    return to_response(job)


@router.post("/youtube", response_model=JobResponse)
def create_youtube_job(
    payload: YouTubeJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobResponse:
    if not payload.has_rights:
        raise AppError("분석에 필요한 권한 확인 체크가 필요합니다.", 400)
    try:
        metadata = analyze_youtube_url(payload.url)
    except ValueError:
        raise AppError("올바른 YouTube URL이 아닙니다.", 400)
    options = GenerationOptions(
        material_type=payload.material_type,
        difficulty=payload.difficulty,
        pdf_length=payload.pdf_length,
    )
    service = JobService(db)
    job = service.create_youtube_job(metadata["sourceUrl"], metadata["title"], options)
    background_tasks.add_task(service.run_job, job.id)
    db.refresh(job)
    return to_response(job)


@router.post("/transcript", response_model=JobResponse)
async def create_transcript_job(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    transcript_text: str | None = Form(None),
    title: str = Form("Transcript Lecture Notes"),
    material_type: str = Form("Detailed Lecture"),
    difficulty: str = Form("대학생 수준"),
    pdf_length: str = Form("Auto"),
    db: Session = Depends(get_db),
) -> JobResponse:
    storage = StorageService()
    staging = storage.root / "uploads"
    staging.mkdir(parents=True, exist_ok=True)
    if file:
        source = await storage.save_upload(file, staging)
    elif transcript_text and transcript_text.strip():
        source = staging / "transcript-input.txt"
        source.write_text(transcript_text.strip(), encoding="utf-8")
    else:
        raise AppError("Transcript 파일을 업로드하거나 텍스트를 입력해주세요.", 400)

    options = GenerationOptions(material_type=material_type, difficulty=difficulty, pdf_length=pdf_length)
    service = JobService(db)
    job = service.create_transcript_job(source, title or Path(source).stem, options)
    job_dir = storage.job_dir(job.id)
    final_source = storage.copy_into(source, job_dir / "source" / source.name)
    source.unlink(missing_ok=True)
    job.project.source_path = str(final_source)
    db.commit()
    background_tasks.add_task(service.run_job, job.id)
    db.refresh(job)
    return to_response(job)


@router.get("", response_model=list[JobResponse])
def list_jobs(db: Session = Depends(get_db)) -> list[JobResponse]:
    return [to_response(job) for job in JobService(db).list_jobs()]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobResponse:
    job = db.get(Job, job_id)
    if not job:
        raise AppError("작업을 찾을 수 없습니다.", 404)
    return to_response(job)


@router.get("/{job_id}/transcript")
def get_transcript(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = require_job(db, job_id)
    transcript = db.query(Transcript).filter(Transcript.project_id == job.project_id).first()
    if not transcript:
        raise AppError("Transcript가 아직 생성되지 않았습니다.", 404)
    return json.loads(Path(transcript.content_path).read_text(encoding="utf-8"))


@router.get("/{job_id}/chapters")
def get_chapters(job_id: str, db: Session = Depends(get_db)) -> list[dict]:
    job = require_job(db, job_id)
    rows = db.query(Chapter).filter(Chapter.project_id == job.project_id).order_by(Chapter.order).all()
    return [
        {"id": row.id, "title": row.title, "start": row.start_time, "end": row.end_time, "summary": row.summary, "importance": row.importance}
        for row in rows
    ]


@router.get("/{job_id}/moments")
def get_moments(job_id: str, db: Session = Depends(get_db)) -> list[dict]:
    job = require_job(db, job_id)
    rows = db.query(KeyMoment).join(Chapter).filter(Chapter.project_id == job.project_id).all()
    return [
        {"id": row.id, "title": row.title, "timestamp": row.timestamp, "reason": row.reason, "importance": row.importance, "selected": row.selected}
        for row in rows
    ]


@router.get("/{job_id}/frames")
def get_frames(job_id: str, db: Session = Depends(get_db)) -> list[dict]:
    job = require_job(db, job_id)
    storage = StorageService()
    rows = db.query(Frame).join(KeyMoment).join(Chapter).filter(Chapter.project_id == job.project_id).all()
    return [
        {
            "id": row.id,
            "timestamp": row.timestamp,
            "selected": row.selected,
            "score": row.score,
            "url": f"/storage/{storage.relative(Path(row.path))}",
        }
        for row in rows
    ]


@router.get("/{job_id}/preview", response_class=HTMLResponse)
def get_preview(job_id: str, db: Session = Depends(get_db)) -> FileResponse:
    job = require_job(db, job_id)
    document = db.query(GeneratedDocument).filter(GeneratedDocument.project_id == job.project_id).first()
    if not document:
        raise AppError("HTML 미리보기가 아직 생성되지 않았습니다.", 404)
    return FileResponse(document.html_path, media_type="text/html")


@router.get("/{job_id}/pdf")
def get_pdf(job_id: str, db: Session = Depends(get_db)) -> FileResponse:
    job = require_job(db, job_id)
    document = db.query(GeneratedDocument).filter(GeneratedDocument.project_id == job.project_id).first()
    if not document:
        raise AppError("PDF가 아직 생성되지 않았습니다.", 404)
    return FileResponse(document.pdf_path, media_type="application/pdf", filename="lecture-notes.pdf")


def require_job(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise AppError("작업을 찾을 수 없습니다.", 404)
    return job
