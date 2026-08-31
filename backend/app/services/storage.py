import re
import shutil
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import AppError


SAFE_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".txt", ".srt", ".vtt"}


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name or "upload.bin"


class StorageService:
    def __init__(self, root: Path | None = None):
        self.root = (root or settings.storage_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        safe_job_id = re.sub(r"[^a-fA-F0-9]", "", job_id)
        if safe_job_id != job_id:
            raise AppError("잘못된 작업 ID입니다.", 400)
        path = (self.root / "jobs" / safe_job_id).resolve()
        if not path.is_relative_to(self.root):
            raise AppError("잘못된 저장 경로입니다.", 400)
        path.mkdir(parents=True, exist_ok=True)
        for child in ["source", "audio", "transcript", "frames", "html", "pdf"]:
            (path / child).mkdir(exist_ok=True)
        return path

    def relative(self, path: Path) -> str:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            raise AppError("저장소 외부 파일에는 접근할 수 없습니다.", 400)
        return str(resolved.relative_to(self.root)).replace("\\", "/")

    async def save_upload(self, upload: UploadFile, destination_dir: Path) -> Path:
        filename = sanitize_filename(upload.filename or "upload.bin")
        suffix = Path(filename).suffix.lower()
        if suffix not in SAFE_EXTENSIONS:
            raise AppError("지원하지 않는 파일 형식입니다.", 400)
        destination = (destination_dir / filename).resolve()
        if not destination.is_relative_to(destination_dir.resolve()):
            raise AppError("잘못된 파일 이름입니다.", 400)

        max_bytes = settings.max_upload_size_mb * 1024 * 1024
        written = 0
        with destination.open("wb") as out:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    destination.unlink(missing_ok=True)
                    raise AppError("업로드 파일이 허용 크기를 초과했습니다.", 413)
                out.write(chunk)
        await upload.close()
        return destination

    def copy_into(self, source: Path, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination
