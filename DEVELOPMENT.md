# Development

## Backend Commands

```bash
cd backend
pip install -r requirements.txt
pytest
uvicorn app.main:app --reload
```

## Frontend Commands

```bash
cd frontend
npm install
npm run build
npm run dev
```

## Notes

- Keep prompts in `backend/app/prompts`.
- Never log API keys or raw secrets.
- Use `storage/jobs/{job_id}` for all generated artifacts.
- FFmpeg commands must use subprocess argument arrays, not shell strings.
