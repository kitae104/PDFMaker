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

## View Results

When the job completes, open the result page to inspect:

- HTML Preview
- Transcript
- Chapters
- Key Moments
- Selected Frames

Use **Download PDF** to save the generated lecture notes.

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
