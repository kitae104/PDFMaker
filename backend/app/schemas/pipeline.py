from typing import Any

from pydantic import BaseModel, Field, field_validator

TERM_KEY_ALIASES = ("term", "name", "word", "keyword", "용어")
DEFINITION_KEY_ALIASES = ("definition", "description", "meaning", "explanation", "desc", "정의", "설명")
TERM_TEXT_SEPARATORS = (":", "：", " - ", " – ", " — ")


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(text for text in (_to_text(item) for item in value) if text)
    return str(value).strip()


def normalize_string_list(value: Any) -> list[str]:
    """None 항목 제거, 비문자열은 str 변환, 단일 문자열은 1개짜리 리스트로."""
    if value is None:
        return []
    if isinstance(value, (str, int, float)):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return value  # 검증기에서 타입 오류로 처리되도록 그대로 둔다
    return [text for text in (_to_text(item) for item in value) if text]


def _pick(mapping: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    lowered = {str(key).strip().lower(): item for key, item in mapping.items()}
    for alias in aliases:
        if alias in lowered and lowered[alias] not in (None, ""):
            return lowered[alias]
    return None


def _split_term_text(text: str) -> tuple[str, str]:
    for separator in TERM_TEXT_SEPARATORS:
        if separator in text:
            term, definition = text.split(separator, 1)
            return term.strip(), definition.strip()
    return text.strip(), ""


def _normalize_term_item(item: Any) -> list[dict[str, str]]:
    if item is None:
        return []
    if isinstance(item, dict):
        term = _pick(item, TERM_KEY_ALIASES)
        definition = _pick(item, DEFINITION_KEY_ALIASES)
        known_keys = set(TERM_KEY_ALIASES) | set(DEFINITION_KEY_ALIASES)
        if not any(str(key).strip().lower() in known_keys for key in item):
            # {"용어A": "정의A", ...} 형태의 매핑으로 간주
            return [{"term": _to_text(key), "definition": _to_text(value)} for key, value in item.items()]
        return [{"term": _to_text(term), "definition": _to_text(definition)}]
    if isinstance(item, (list, tuple)):
        parts = list(item) + ["", ""]
        return [{"term": _to_text(parts[0]), "definition": _to_text(parts[1])}]
    term, definition = _split_term_text(_to_text(item))
    return [{"term": term, "definition": definition}]


def normalize_terms(value: Any) -> list[dict[str, str]]:
    """LLM이 내는 다양한 terms 모양을 정확히 {term, definition} 딕셔너리 리스트로 맞춘다."""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    normalized: list[dict[str, str]] = []
    for item in items:
        for entry in _normalize_term_item(item):
            # 편집기에서 정의만 입력한 행도 데이터 유실이 없도록 보존한다. 둘 다 비었을 때만 버린다.
            if entry["term"] or entry["definition"]:
                normalized.append(entry)
    return normalized


class TranscriptSegment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str


class TranscriptData(BaseModel):
    language: str = "ko"
    duration: float = 0.0
    segments: list[TranscriptSegment]


class ChapterData(BaseModel):
    title: str
    start: float
    end: float
    summary: str
    importance: int = Field(ge=1, le=10)


class ChapterAnalysis(BaseModel):
    chapters: list[ChapterData]


class KeyMomentData(BaseModel):
    timestamp: float
    title: str
    reason: str
    importance: int = Field(ge=1, le=10)
    captureRecommended: bool = True


class KeyMomentAnalysis(BaseModel):
    keyMoments: list[KeyMomentData]


class SceneWindowSummary(BaseModel):
    id: str
    title: str
    summary: str


class SceneWindowSummaryList(BaseModel):
    scenes: list[SceneWindowSummary]


class LessonChapter(BaseModel):
    title: str
    learning_objectives: list[str] = Field(default_factory=list)
    explanation: str
    beginner_explanation: str = ""
    key_points: list[str] = Field(default_factory=list)
    terms: list[dict[str, str]] = Field(default_factory=list)
    timestamp: str = ""
    summary: str = ""

    @field_validator("learning_objectives", "key_points", mode="before")
    @classmethod
    def _clean_string_lists(cls, value: Any) -> Any:
        return normalize_string_list(value)

    @field_validator("terms", mode="before")
    @classmethod
    def _clean_terms(cls, value: Any) -> Any:
        return normalize_terms(value)

    @field_validator("beginner_explanation", "timestamp", "summary", mode="before")
    @classmethod
    def _clean_optional_text(cls, value: Any) -> Any:
        return "" if value is None else value


class LessonContent(BaseModel):
    title: str
    overview: str
    learning_objectives: list[str]
    chapters: list[LessonChapter]
    final_summary: list[str]
    review_questions: list[str]

    @field_validator("learning_objectives", "final_summary", "review_questions", mode="before")
    @classmethod
    def _clean_string_lists(cls, value: Any) -> Any:
        return normalize_string_list(value)
