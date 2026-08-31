from pydantic import BaseModel, Field


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


class LessonChapter(BaseModel):
    title: str
    learning_objectives: list[str]
    explanation: str
    beginner_explanation: str
    key_points: list[str]
    terms: list[dict[str, str]]
    timestamp: str
    summary: str


class LessonContent(BaseModel):
    title: str
    overview: str
    learning_objectives: list[str]
    chapters: list[LessonChapter]
    final_summary: list[str]
    review_questions: list[str]
