# AI Video Lecture Note Generator

Turn videos into structured learning materials. The current workflow extracts scene-change images, summarizes transcript windows between scenes, lets the user choose the images to include, generates an editable lecture document, and downloads a PDF from the edited content.

## Quick Start

```bash
cp .env.example .env
```

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

For a hosted frontend, set `VITE_API_BASE_URL` to the deployed backend API URL, for example `https://your-backend.example.com/api`. When deploying this repository to Vercel, the included `vercel.json` builds the Vite app from `frontend/`.

## Mock Mode

The default `.env.example` uses:

```env
LLM_PROVIDER=mock
STT_PROVIDER=mock
VISION_PROVIDER=mock
```

This lets the full pipeline run without external API keys. If FFmpeg is not installed, mock mode still creates placeholder educational frames so the preview and PDF flow can be tested end to end.

YouTube URL input is also wired for local testing. It validates the URL, reads public oEmbed metadata when available, builds the scene review step, and then creates an editable document draft before PDF download.

## LLM Provider Selection

Use OpenAI:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

Use Gemini through its OpenAI-compatible endpoint:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.7-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
```

If `LLM_PROVIDER` is `openai`/`gemini` without its API key, or has an unknown value, the backend refuses to start with a clear error. `mock` (and the not-yet-implemented `ollama`) run without keys, and every job then shows a warning that real AI was not used. LLM call failures that fall back to rule-based content, and video uploads processed by the mock STT, are also reported as job warnings on the results screen.

The `.env` file is always read from the repository root, and relative `STORAGE_PATH` / sqlite `DATABASE_URL` paths are resolved against `backend/`, so the working directory does not matter.

Other settings:

```env
LLM_TIMEOUT_SECONDS=120            # per request
LLM_MAX_RETRIES=3                  # 429/5xx/timeout retries with backoff (Retry-After respected)
LLM_USE_SYSTEM_TRUST_STORE=true    # use the OS certificate store (corporate SSL proxies)
LLM_CA_BUNDLE=                     # optional CA bundle path, overrides the trust store
GEMINI_REASONING_EFFORT=           # optional, sent only when set
TRANSCRIPT_CORRECTION_PROFILE=auto # auto | automotive | none
```

Check the connection with `GET /api/health` (effective provider/model/STT) and `GET /api/health/llm` (one minimal LLM call; returns a classified error such as SSL, 429, timeout, auth or missing model).

YouTube jobs need real captions. If captions cannot be fetched (no captions, or the server IP is blocked by YouTube), the job fails with a message asking you to upload an SRT/VTT file through the transcript input instead.

## Optional FFmpeg

Install FFmpeg and ensure `ffmpeg` and `ffprobe` are on PATH to enable real metadata, audio extraction, and frame capture.

## Docker

```bash
docker compose up --build
```

The backend image installs FFmpeg. PostgreSQL is included, while local development can use SQLite.
