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

## Troubleshooting

- If FFmpeg is missing, install it and add it to PATH for real video processing.
- If PDF generation fails with Playwright, install browser binaries with `python -m playwright install chromium`.
- If upload fails, check file extension and `MAX_UPLOAD_SIZE_MB`.
