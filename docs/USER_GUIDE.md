# User Guide

## Run The Program

1. Copy `.env.example` to `.env`.
2. Start the backend with `uvicorn app.main:app --reload`.
3. Start the frontend with `npm run dev`.
4. Open `http://localhost:5173`.

## Upload A Video

Choose **Video Upload**, drop an MP4/MOV/MKV/WEBM file, select lesson options, and start generation. The progress panel shows each pipeline step.

## Upload A Transcript

Choose **Transcript**, upload a `.txt`, `.srt`, or `.vtt` file, or paste transcript text directly. Timestamped transcript files keep their timestamps; plain text is converted into timed segments for the lesson pipeline.

## Review Scenes

When the first stage is ready, open the result page to inspect scene-change cards. Each card contains a captured image and the transcript summary up to the next scene. Scenes are selected by default.

Use **선택 내용으로 문서 초안 생성** to build an editable lesson document from the selected scenes.

## Edit And Download

The editor includes the generated overview, learning goals, table-of-contents-backed scene sections, concept explanations, key points, terms, one-line summaries, final summary, and review questions.

Use **수정본 PDF 다운로드** to render the current edited content into the final PDF.

## YouTube URL

The YouTube tab validates the URL, checks public metadata, and can create lecture notes through the mock-safe pipeline. For full transcript-accurate analysis, upload an MP4 or transcript when the platform or content rights limit direct media access.

## AI Providers

Server secrets stay in `.env`. Use mock mode for local testing:

```env
LLM_PROVIDER=mock
STT_PROVIDER=mock
```

Use OpenAI for generated chapter summaries and lesson content:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

Use Gemini through the OpenAI-compatible Gemini endpoint:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.7-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
```

## Troubleshooting

- If FFmpeg is missing, install it and add it to PATH for real video processing.
- If PDF generation fails with Playwright, install browser binaries with `python -m playwright install chromium`.
- If upload fails, check file extension and `MAX_UPLOAD_SIZE_MB`.
