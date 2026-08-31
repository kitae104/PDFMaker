import re
from pathlib import Path

from app.schemas.pipeline import TranscriptData, TranscriptSegment


def parse_transcript_file(path: Path) -> TranscriptData:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".srt":
        return parse_srt(text)
    if suffix == ".vtt":
        return parse_vtt(text)
    return parse_plain_text(text)


def parse_plain_text(text: str) -> TranscriptData:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    segments = []
    for index, line in enumerate(lines or [text.strip() or "Transcript content"]):
        start = index * 8.0
        segments.append(TranscriptSegment(start=start, end=start + 8.0, text=line))
    return TranscriptData(language="ko", duration=segments[-1].end if segments else 0, segments=segments)


def parse_srt(text: str) -> TranscriptData:
    blocks = re.split(r"\n\s*\n", text.strip())
    segments: list[TranscriptSegment] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        time_line = next((line for line in lines if "-->" in line), "")
        if not time_line:
            continue
        start_s, end_s = [part.strip() for part in time_line.split("-->", 1)]
        body = " ".join(line for line in lines if line != time_line and not line.isdigit())
        if not body:
            continue
        segments.append(TranscriptSegment(start=parse_timestamp(start_s), end=parse_timestamp(end_s), text=body))
    return TranscriptData(language="ko", duration=segments[-1].end if segments else 0, segments=segments)


def parse_vtt(text: str) -> TranscriptData:
    cleaned = "\n".join(line for line in text.splitlines() if not line.startswith("WEBVTT"))
    return parse_srt(cleaned)


def parse_timestamp(value: str) -> float:
    value = value.strip().split()[0].replace(",", ".")
    parts = value.split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return hours * 3600 + minutes * 60 + seconds
