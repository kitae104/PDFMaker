import re
from html import unescape
from urllib.parse import parse_qs, urlparse
from pathlib import Path

import httpx

from app.schemas.pipeline import TranscriptData
from app.services.transcript_parser import parse_vtt


def extract_youtube_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/").split("/")[0]
    elif host.endswith("youtube.com"):
        candidate = parse_qs(parsed.query).get("v", [""])[0]
    else:
        return None
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate or ""):
        return candidate
    return None


def analyze_youtube_url(url: str) -> dict:
    video_id = extract_youtube_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL")

    fallback = {
        "videoId": video_id,
        "title": f"YouTube Video {video_id}",
        "channel": "Unknown",
        "duration": None,
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        "captionsAvailable": None,
        "sourceUrl": normalize_watch_url(video_id),
        "policyNote": "원본 영상 다운로드 없이 메타데이터와 사용자가 확인한 권한을 바탕으로 자료 생성 흐름을 시작합니다.",
    }
    try:
        info = extract_youtube_info(normalize_watch_url(video_id))
        fallback["title"] = info.get("title") or fallback["title"]
        fallback["channel"] = info.get("channel") or info.get("uploader") or fallback["channel"]
        fallback["duration"] = info.get("duration") or fallback["duration"]
        fallback["thumbnail"] = info.get("thumbnail") or fallback["thumbnail"]
        fallback["captionsAvailable"] = bool(info.get("subtitles") or info.get("automatic_captions"))
        return fallback
    except Exception:
        pass

    try:
        response = httpx.get(
            "https://www.youtube.com/oembed",
            params={"url": normalize_watch_url(video_id), "format": "json"},
            timeout=6,
        )
        response.raise_for_status()
        data = response.json()
        fallback["title"] = data.get("title") or fallback["title"]
        fallback["channel"] = data.get("author_name") or fallback["channel"]
        fallback["thumbnail"] = data.get("thumbnail_url") or fallback["thumbnail"]
    except Exception:
        pass
    return fallback


def normalize_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def extract_youtube_info(url: str) -> dict:
    from yt_dlp import YoutubeDL

    with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}) as ydl:
        return ydl.extract_info(url, download=False)


def fetch_youtube_transcript(url: str) -> TranscriptData | None:
    info = extract_youtube_info(url)
    caption = pick_caption(info)
    if not caption:
        return None
    response = httpx.get(caption["url"], timeout=12)
    response.raise_for_status()
    text = clean_vtt(response.text)
    transcript = parse_vtt(text)
    if not transcript.segments:
        return None
    language = caption.get("language") or caption.get("name") or "auto"
    transcript.language = str(language)[:16]
    return transcript


def download_youtube_video(url: str, output_dir: Path) -> Path | None:
    from yt_dlp import YoutubeDL

    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output_dir / "youtube-source.%(ext)s")
    options = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "outtmpl": outtmpl,
        "format": "bestvideo[height<=480][ext=mp4]/best[height<=480][ext=mp4]/best[height<=480]/best",
    }
    ffmpeg_location = find_playwright_ffmpeg()
    if ffmpeg_location:
        options["ffmpeg_location"] = str(ffmpeg_location)
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded = Path(ydl.prepare_filename(info))
            if downloaded.exists() and downloaded.stat().st_size > 0:
                return downloaded
    except Exception:
        pass
    candidates = sorted(output_dir.glob("youtube-source.*"), key=lambda path: path.stat().st_size if path.exists() else 0, reverse=True)
    return candidates[0] if candidates else None


def pick_caption(info: dict) -> dict | None:
    caption_sets = [info.get("subtitles") or {}, info.get("automatic_captions") or {}]
    preferred_langs = ["ko", "ko-KR", "en", "en-US"]
    for captions in caption_sets:
        for lang in preferred_langs:
            chosen = choose_vtt(captions.get(lang) or [])
            if chosen:
                return {**chosen, "language": lang}
        for lang, entries in captions.items():
            chosen = choose_vtt(entries or [])
            if chosen:
                return {**chosen, "language": lang}
    return None


def choose_vtt(entries: list[dict]) -> dict | None:
    for entry in entries:
        if entry.get("ext") == "vtt" and entry.get("url"):
            return entry
    for entry in entries:
        if entry.get("url"):
            return entry
    return None


def clean_vtt(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    return text


def find_playwright_ffmpeg() -> Path | None:
    try:
        import imageio_ffmpeg

        return Path(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    candidate = Path.home() / "AppData" / "Local" / "ms-playwright" / "ffmpeg-1010" / "ffmpeg-win64.exe"
    return candidate if candidate.exists() else None
