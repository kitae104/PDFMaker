from datetime import datetime

from pydantic import BaseModel

from app.models.entities import JobStatus, SourceType


class GenerationOptions(BaseModel):
    material_type: str = "Detailed Lecture"
    difficulty: str = "대학생 수준"
    pdf_length: str = "Auto"
    extract_key_frames: bool = True
    include_terms: bool = True
    include_final_summary: bool = True
    show_timestamps: bool = True
    show_source: bool = True
    include_learning_goals: bool = True
    include_review_questions: bool = True


class YouTubeJobCreate(BaseModel):
    url: str
    has_rights: bool = False
    material_type: str = "Detailed Lecture"
    difficulty: str = "대학생 수준"
    pdf_length: str = "Auto"


class SceneSelectionRequest(BaseModel):
    moment_ids: list[str]


class JobResponse(BaseModel):
    id: str
    project_id: str
    project_title: str
    source_type: SourceType
    status: JobStatus
    progress: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class HealthResponse(BaseModel):
    status: str
    app_name: str
    database: str
