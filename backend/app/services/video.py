import json
import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.core.exceptions import AppError


class VideoService:
    allowed_extensions = {".mp4", ".mov", ".mkv", ".webm"}

    def validate_video(self, path: Path) -> None:
        if path.suffix.lower() not in self.allowed_extensions:
            raise AppError("지원하지 않는 영상 파일입니다.", 400)
        if not path.exists() or path.stat().st_size == 0:
            raise AppError("영상 파일이 비어 있거나 손상되었습니다.", 400)

    def has_ffmpeg(self) -> bool:
        return self.ffmpeg_path() is not None

    def has_ffprobe(self) -> bool:
        return shutil.which("ffprobe") is not None

    def ffmpeg_path(self) -> str | None:
        if path := shutil.which("ffmpeg"):
            return path
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
        playwright_ffmpeg = Path.home() / "AppData" / "Local" / "ms-playwright" / "ffmpeg-1010" / "ffmpeg-win64.exe"
        if playwright_ffmpeg.exists():
            return str(playwright_ffmpeg)
        return None

    def get_metadata(self, path: Path) -> dict:
        self.validate_video(path)
        if not self.has_ffprobe():
            return {"duration": 600.0, "title": path.stem, "format": path.suffix.lower(), "ffmpeg": False}
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name:stream=codec_type,width,height",
            "-of",
            "json",
            str(path),
        ]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            data = json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise AppError("영상 메타데이터를 읽는 중 문제가 발생했습니다.", 400) from exc
        duration = float(data.get("format", {}).get("duration") or 0)
        video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        return {
            "duration": duration,
            "title": path.stem,
            "format": data.get("format", {}).get("format_name", path.suffix.lower()),
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "ffmpeg": True,
        }

    def get_duration(self, path: Path) -> float:
        return float(self.get_metadata(path).get("duration") or 0)

    def extract_audio(self, input_path: Path, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg = self.ffmpeg_path()
        if not ffmpeg:
            output_path.write_bytes(b"")
            return output_path
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            str(output_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            raise AppError("영상의 음성을 분석하는 중 문제가 발생했습니다.", 400) from exc
        return output_path

    def capture_frame(self, input_path: Path, timestamp: float, output_path: Path, label: str = "") -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg = self.ffmpeg_path()
        if ffmpeg:
            cmd = [
                ffmpeg,
                "-y",
                "-ss",
                str(max(timestamp, 0)),
                "-i",
                str(input_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(output_path),
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                if output_path.exists() and output_path.stat().st_size > 0:
                    return output_path
            except subprocess.CalledProcessError:
                pass
        self._create_placeholder_frame(output_path, timestamp, label)
        return output_path

    def capture_frames(self, input_path: Path, timestamp: float, output_dir: Path, offsets: list[float], label: str) -> list[Path]:
        paths = []
        for index, offset in enumerate(offsets, start=1):
            capture_time = max(timestamp + offset, 0)
            path = output_dir / f"frame_{int(timestamp):04d}_{index:02d}.jpg"
            paths.append(self.capture_frame(input_path, capture_time, path, label))
        return paths

    def detect_scene_changes(
        self,
        input_path: Path,
        output_dir: Path,
        duration: float,
        threshold: float = 0.35,
        max_scenes: int = 12,
    ) -> list[tuple[float, Path]]:
        output_dir.mkdir(parents=True, exist_ok=True)
        ffmpeg = self.ffmpeg_path()
        if ffmpeg and input_path.exists() and input_path.stat().st_size > 1024:
            pattern = output_dir / "scene_%04d.jpg"
            max_events = max(max_scenes * 12, 96)
            cmd = [
                ffmpeg,
                "-y",
                "-i",
                str(input_path),
                "-vf",
                f"select='gt(scene,{threshold})',scale=1280:-1,showinfo",
                "-frames:v",
                str(max_events),
                "-vsync",
                "vfr",
                str(pattern),
            ]
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                timestamps = [float(value) for value in re.findall(r"pts_time:([0-9.]+)", result.stderr)]
                files = sorted(output_dir.glob("scene_*.jpg"))
                scenes = [(timestamps[index] if index < len(timestamps) else 0.0, file) for index, file in enumerate(files)]
                if scenes:
                    filtered = filter_scene_spacing(scenes, duration, max_scenes)
                    return filtered[:max_scenes]
            except subprocess.CalledProcessError:
                pass

        return self.sample_frames(input_path, output_dir, duration, max_scenes)

    def sample_frames(self, input_path: Path, output_dir: Path, duration: float, count: int) -> list[tuple[float, Path]]:
        effective_duration = max(duration or 0, 300)
        step = effective_duration / max(count, 1)
        scenes = []
        for index in range(count):
            timestamp = round(index * step, 2)
            path = output_dir / f"scene_{index + 1:04d}.jpg"
            self.capture_frame(input_path, timestamp, path, f"Scene {index + 1}")
            scenes.append((timestamp, path))
        return scenes

    def _create_placeholder_frame(self, output_path: Path, timestamp: float, label: str) -> None:
        image = Image.new("RGB", (1280, 720), color=(239, 246, 255))
        draw = ImageDraw.Draw(image)
        title_font = ImageFont.load_default()
        text = label or "Key learning moment"
        draw.rounded_rectangle((70, 70, 1210, 650), radius=28, fill=(255, 255, 255), outline=(147, 197, 253), width=4)
        draw.text((120, 150), "AI Generated Key Frame", fill=(30, 64, 175), font=title_font)
        draw.text((120, 250), text[:90], fill=(15, 23, 42), font=title_font)
        draw.text((120, 330), f"Source timestamp: {format_timestamp(timestamp)}", fill=(71, 85, 105), font=title_font)
        draw.text((120, 430), "Install FFmpeg to capture real video frames.", fill=(100, 116, 139), font=title_font)
        image.save(output_path, quality=90)


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    minutes, sec = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


def filter_scene_spacing(scenes: list[tuple[float, Path]], duration: float, max_scenes: int) -> list[tuple[float, Path]]:
    if not scenes:
        return []
    if max_scenes <= 1:
        return [scenes[0]]
    effective_duration = max(duration or 0, scenes[-1][0], 1)
    min_gap = max(8.0, min(30.0, effective_duration / max_scenes * 0.45))
    filtered: list[tuple[float, Path]] = []
    for timestamp, path in scenes:
        if not filtered or timestamp - filtered[-1][0] >= min_gap:
            filtered.append((timestamp, path))
        if len(filtered) >= max_scenes:
            break
    if len(filtered) >= min(4, max_scenes):
        return filtered
    step = max(len(scenes) / max_scenes, 1)
    return [scenes[min(round(index * step), len(scenes) - 1)] for index in range(min(max_scenes, len(scenes)))]
