# Architecture

The application is split into a React/Vite frontend and a FastAPI backend.

## Backend

- API routes create and inspect long-running jobs.
- SQLAlchemy stores projects, jobs, transcripts, chapters, moments, frames, and generated documents.
- StorageService isolates all job files under `storage/jobs/{job_id}`.
- VideoService wraps FFmpeg/ffprobe with argument-array subprocess calls.
- Transcription, LLM, and Vision providers use interfaces with mock implementations by default.
- DocumentGenerator renders Jinja2 HTML first, then converts it to PDF with Playwright when available, falling back to a local PDF writer for development resilience.

## Pipeline

```text
video upload
-> metadata
-> audio extraction
-> transcript
-> chapter analysis
-> key moments
-> frame capture
-> lesson content
-> HTML
-> PDF
```

## Extension Points

- Add OpenAI/Gemini/Ollama providers behind `LLMProvider`.
- Add Whisper/OpenAI STT behind `TranscriptionProvider`.
- Add model-based frame ranking behind `VisionProvider`.
- Add output types through `DocumentGenerator`.
