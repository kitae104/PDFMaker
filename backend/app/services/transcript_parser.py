import re
from collections.abc import Iterable
from pathlib import Path

from app.core.config import settings
from app.schemas.pipeline import TranscriptData, TranscriptSegment


COMMON_TRANSCRIPT_CORRECTIONS = {
    "알료": "안료",
    "한류": "안료",
    "청가제": "첨가제",
    "구착력": "부착력",
    "강택": "광택",
    "포면": "표면",
    "우래탄": "우레탄",
    "배학": "배합",
    "베인드": "페인트",
    "산하철": "산화철",
    "이산화 티탐": "이산화 티타늄",
}

# Automotive painting vocabulary. COMMON_TRANSCRIPT_CORRECTIONS are only safe for this domain
# (e.g. "한류" -> "안료" would corrupt a K-culture transcript).
AUTOMOTIVE_PAINT_KEYWORDS = (
    "도료",
    "도장",
    "페인트",
    "안료",
    "클리어코트",
    "클리어 코트",
    "프라이머",
    "우레탄",
    "자동차",
    "도막",
    "경화제",
    "첨가제",
    "부착력",
    "광택",
    "산화철",
    "티타늄",
    "판금",
    "차체",
)
DOMAIN_KEYWORD_MIN_DISTINCT = 2


def should_apply_domain_corrections(texts: Iterable[str]) -> bool:
    profile = (settings.transcript_correction_profile or "auto").strip().lower()
    if profile == "none":
        return False
    if profile == "automotive":
        return True
    # "auto": keywords are counted after tentative correction so common mis-hearings
    # ("알료", "베인드") still count as evidence for the domain.
    combined = " ".join(str(text or "") for text in texts)
    corrected = correct_common_transcript_terms(combined, enabled=True)
    found = {keyword for keyword in AUTOMOTIVE_PAINT_KEYWORDS if keyword in corrected}
    return len(found) >= DOMAIN_KEYWORD_MIN_DISTINCT


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
    segments = normalize_transcript_segments(segments)
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
    segments = normalize_transcript_segments(segments)
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


def normalize_transcript_segments(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    cleaned: list[TranscriptSegment] = []
    current_start: float | None = None
    current_end = 0.0
    current_tokens: list[str] = []

    def flush() -> None:
        nonlocal current_start, current_end, current_tokens
        if current_start is not None and current_tokens:
            cleaned.append(TranscriptSegment(start=current_start, end=current_end, text=" ".join(current_tokens)))
        current_start = None
        current_end = 0.0
        current_tokens = []

    apply_corrections = should_apply_domain_corrections(segment.text for segment in segments)
    for segment in sorted(segments, key=lambda item: (item.start, item.end)):
        text = normalize_text(segment.text, apply_corrections)
        if not text:
            continue
        tokens = text.split()
        if not tokens:
            continue
        gap = segment.start - current_end if current_start is not None else 0
        if current_start is None or gap > 2.0 or should_start_new_segment(current_start, current_end, current_tokens):
            flush()
            current_start = segment.start
            current_end = segment.end
            current_tokens = tokens
            continue
        addition = unique_suffix(current_tokens, tokens)
        if addition:
            current_tokens.extend(addition)
        current_end = max(current_end, segment.end)

    flush()
    return cleaned


def normalize_text(text: str, apply_corrections: bool = True) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    return correct_common_transcript_terms(text, enabled=apply_corrections)


def correct_common_transcript_terms(text: str, enabled: bool = True) -> str:
    if not enabled:
        return text
    for source, target in COMMON_TRANSCRIPT_CORRECTIONS.items():
        text = text.replace(source, target)
    return text


def should_start_new_segment(start: float, end: float, tokens: list[str]) -> bool:
    if end - start < 18:
        return False
    if tokens and re.search(r"[.!?。？！]$", tokens[-1]):
        return True
    return end - start >= 28


def unique_suffix(existing_tokens: list[str], next_tokens: list[str]) -> list[str]:
    max_overlap = min(len(existing_tokens), len(next_tokens), 30)
    for size in range(max_overlap, 0, -1):
        if existing_tokens[-size:] == next_tokens[:size]:
            return next_tokens[size:]
    normalized_existing = " ".join(existing_tokens[-80:])
    normalized_next = " ".join(next_tokens)
    if normalized_next and normalized_next in normalized_existing:
        return []
    return next_tokens
