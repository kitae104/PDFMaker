# Implementation Plan

## Architecture

- FastAPI backend with service-layer pipeline and provider interfaces.
- React + TypeScript + Vite frontend with upload, progress, and results pages.
- SQLAlchemy database with SQLite fallback and PostgreSQL-compatible models.
- Filesystem storage rooted at `STORAGE_PATH`.
- Jinja2 HTML generation before PDF rendering.

## Directory Structure

```text
backend/app/api
backend/app/core
backend/app/models
backend/app/schemas
backend/app/services
backend/app/prompts
backend/app/templates
frontend/src/api
frontend/src/components
frontend/src/pages
frontend/src/stores
frontend/src/types
docs
storage
```

## Implementation Steps

1. Backend app, config, database, health endpoint.
2. Frontend app shell and backend health check.
3. Video upload and job creation.
4. FFmpeg metadata/audio/frame services with mock-safe fallback.
5. Mock STT and transcript persistence.
6. LLM provider interface with mock chapter/moment/content generation.
7. HTML and PDF generation.
8. Results UI with preview, transcript, chapters, moments, and PDF download.
9. Tests and documentation.

## API Design

- `GET /api/health`
- `POST /api/jobs`
- `POST /api/jobs/youtube`
- `POST /api/jobs/transcript`
- `GET /api/jobs`
- `GET /api/jobs/{id}`
- `GET /api/jobs/{id}/transcript`
- `GET /api/jobs/{id}/chapters`
- `GET /api/jobs/{id}/moments`
- `GET /api/jobs/{id}/frames`
- `GET /api/jobs/{id}/preview`
- `GET /api/jobs/{id}/pdf`
- `POST /api/youtube/analyze`

## Database Design

- Project: input/source metadata.
- Job: status, progress, error, timestamps.
- Transcript: timestamp JSON path.
- Chapter: LLM chapter records.
- KeyMoment: chapter-linked timestamps.
- Frame: captured image files.
- GeneratedDocument: HTML and PDF artifacts.
