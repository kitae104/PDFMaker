import re
from html import unescape
from urllib.parse import parse_qs, urlparse
from pathlib import Path

import httpx

from app.core.exceptions import AppError
from app.schemas.pipeline import TranscriptData
from app.services.transcript_parser import parse_vtt

YOUTUBE_TRANSCRIPT_UNAVAILABLE_MESSAGE = (
    "YouTube 자막을 가져오지 못했습니다. 서버 IP가 YouTube에 차단됐거나 자막이 없는 영상일 수 있습니다. "
    "자막 파일(SRT/VTT)을 내려받아 '자막' 입력으로 올려 주세요."
)


class YouTubeTranscriptUnavailableError(AppError):
    def __init__(self, message: str = YOUTUBE_TRANSCRIPT_UNAVAILABLE_MESSAGE):
        super().__init__(message, 422)


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


def fetch_youtube_transcript(url: str) -> TranscriptData:
    """Fetch a real caption transcript or raise YouTubeTranscriptUnavailableError."""
    try:
        info = extract_youtube_info(url)
        caption = pick_caption(info)
        if not caption:
            raise YouTubeTranscriptUnavailableError()
        response = httpx.get(caption["url"], timeout=12)
        response.raise_for_status()
        text = clean_vtt(response.text)
        transcript = parse_vtt(text)
    except YouTubeTranscriptUnavailableError:
        raise
    except Exception as exc:
        raise YouTubeTranscriptUnavailableError() from exc
    if not transcript.segments:
        raise YouTubeTranscriptUnavailableError()
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


PREFERRED_CAPTION_LANGS = ["ko", "ko-KR", "en", "en-US", "en-GB"]


def pick_caption(info: dict) -> dict | None:
    """Choose a VTT caption track.

    Manual subtitles win. For automatic captions only the original-language track is used
    ("<lang>-orig" or the video's own language); YouTube machine translations are skipped.
    Non-VTT tracks are never chosen because the parser only understands VTT.
    """
    original_lang = str(info.get("language") or "").strip()
    manual = info.get("subtitles") or {}
    manual_order = unique_list([*PREFERRED_CAPTION_LANGS, original_lang, *manual.keys()])
    for lang in manual_order:
        if lang == "live_chat":
            continue
        chosen = choose_vtt(manual.get(lang) or [])
        if chosen:
            return {**chosen, "language": lang}

    automatic = info.get("automatic_captions") or {}
    orig_keys = [key for key in automatic if key.endswith("-orig")]
    auto_order = unique_list([*orig_keys, original_lang])
    for lang in auto_order:
        if not lang:
            continue
        chosen = choose_vtt(automatic.get(lang) or [], allow_translated=False)
        if chosen:
            return {**chosen, "language": lang.removesuffix("-orig")}
    return None


def unique_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def is_translated_caption(entry: dict) -> bool:
    return "tlang=" in str(entry.get("url") or "")


def choose_vtt(entries: list[dict], allow_translated: bool = True) -> dict | None:
    for entry in entries:
        if entry.get("ext") != "vtt" or not entry.get("url"):
            continue
        if not allow_translated and is_translated_caption(entry):
            continue
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
