import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def make_id() -> str:
    return uuid4().hex


class SourceType(str, enum.Enum):
    VIDEO = "video"
    YOUTUBE = "youtube"
    TRANSCRIPT = "transcript"


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    ANALYZING_INPUT = "ANALYZING_INPUT"
    EXTRACTING_AUDIO = "EXTRACTING_AUDIO"
    TRANSCRIBING = "TRANSCRIBING"
    ANALYZING_TRANSCRIPT = "ANALYZING_TRANSCRIPT"
    GENERATING_CHAPTERS = "GENERATING_CHAPTERS"
    SELECTING_KEY_MOMENTS = "SELECTING_KEY_MOMENTS"
    CAPTURING_FRAMES = "CAPTURING_FRAMES"
    GENERATING_CONTENT = "GENERATING_CONTENT"
    GENERATING_HTML = "GENERATING_HTML"
    GENERATING_PDF = "GENERATING_PDF"
    REVIEW_READY = "REVIEW_READY"
    DOCUMENT_READY = "DOCUMENT_READY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_id)
    title: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    jobs: Mapped[list["Job"]] = relationship(back_populates="project")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    options_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    project: Mapped[Project] = relationship(back_populates="jobs")


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    language: Mapped[str] = mapped_column(String(16), default="ko")
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    content_path: Mapped[str] = mapped_column(Text)


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String(255))
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text)
    importance: Mapped[int] = mapped_column(Integer)
    order: Mapped[int] = mapped_column(Integer)

    moments: Mapped[list["KeyMoment"]] = relationship(back_populates="chapter")


class KeyMoment(Base):
    __tablename__ = "key_moments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_id)
    chapter_id: Mapped[str] = mapped_column(ForeignKey("chapters.id"))
    timestamp: Mapped[float] = mapped_column(Float)
    title: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text)
    importance: Mapped[int] = mapped_column(Integer)
    selected: Mapped[bool] = mapped_column(Boolean, default=True)

    chapter: Mapped[Chapter] = relationship(back_populates="moments")
    frames: Mapped[list["Frame"]] = relationship(back_populates="key_moment")


class Frame(Base):
    __tablename__ = "frames"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_id)
    key_moment_id: Mapped[str] = mapped_column(ForeignKey("key_moments.id"))
    timestamp: Mapped[float] = mapped_column(Float)
    path: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)

    key_moment: Mapped[KeyMoment] = relationship(back_populates="frames")


class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=make_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    type: Mapped[str] = mapped_column(String(32), default="pdf")
    html_path: Mapped[str] = mapped_column(Text)
    pdf_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
