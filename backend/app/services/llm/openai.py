import json
import logging
import re
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.jobs import GenerationOptions
from app.schemas.pipeline import (
    ChapterAnalysis,
    KeyMomentAnalysis,
    LessonChapter,
    LessonContent,
    SceneWindowSummary,
    SceneWindowSummaryList,
    TranscriptData,
    TranscriptSegment,
)
from app.services.llm.base import LLMProvider
from app.services.llm.mock import MockLLMProvider, segments_between
from app.services.transcript_parser import correct_common_transcript_terms
from app.services.video import format_timestamp

logger = logging.getLogger(__name__)

LESSON_CHUNK_THRESHOLD = 12
LESSON_CHUNK_SIZE = 8


class OpenAILLMProvider(LLMProvider):
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the OpenAI LLM provider.")
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.base_url = str(settings.openai_base_url).rstrip("/")
        self.fallback = MockLLMProvider()

    def analyze_transcript(self, transcript: TranscriptData) -> dict:
        return {"language": transcript.language, "segment_count": len(transcript.segments), "duration": transcript.duration}

    def generate_chapters(self, transcript: TranscriptData) -> ChapterAnalysis:
        schema = {
            "chapters": [
                {"title": "string", "start": 0, "end": 60, "summary": "string", "importance": 8}
            ]
        }
        prompt = (
            "아래 timestamp transcript를 3-7개의 학습 chapter로 나누세요. "
            "중복 자막을 그대로 복사하지 말고, 자연스러운 한국어 문장으로 요약하세요.\n\n"
            f"JSON shape:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Transcript:\n{format_segments(transcript.segments, max_chars=14000)}"
        )
        try:
            data = self._chat_json(CHAPTER_SYSTEM_PROMPT, prompt, max_tokens=2200)
            return ChapterAnalysis.model_validate(data)
        except Exception:
            logger.exception("OpenAI chapter generation failed; falling back to mock output")
            return self.fallback.generate_chapters(transcript)

    def select_key_moments(self, transcript: TranscriptData, chapters: ChapterAnalysis) -> KeyMomentAnalysis:
        schema = {
            "keyMoments": [
                {"timestamp": 12.3, "title": "string", "reason": "string", "importance": 8, "captureRecommended": True}
            ]
        }
        chapter_data = [chapter.model_dump() for chapter in chapters.chapters]
        prompt = (
            "각 chapter에서 이미지로 남길 가치가 큰 장면을 고르세요. "
            "reason은 transcript를 그대로 붙이지 말고 선택 이유를 한 문장으로 쓰세요.\n\n"
            f"Chapters:\n{json.dumps(chapter_data, ensure_ascii=False)}\n\n"
            f"JSON shape:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Transcript:\n{format_segments(transcript.segments, max_chars=12000)}"
        )
        try:
            data = self._chat_json(KEY_MOMENT_SYSTEM_PROMPT, prompt, max_tokens=2200)
            return KeyMomentAnalysis.model_validate(data)
        except Exception:
            logger.exception("OpenAI key moment generation failed; falling back to mock output")
            return self.fallback.select_key_moments(transcript, chapters)

    def generate_lesson_content(
        self,
        transcript: TranscriptData,
        chapters: ChapterAnalysis,
        moments: KeyMomentAnalysis,
        options: GenerationOptions,
    ) -> LessonContent:
        windows = [
            {
                "id": str(index),
                "title": chapter.title,
                "summary": chapter.summary,
                "start": chapter.start,
                "end": chapter.end,
                "segments": segments_between(transcript, chapter.start, chapter.end),
            }
            for index, chapter in enumerate(chapters.chapters, start=1)
        ]
        return self.generate_lesson_from_scene_windows("AI Generated Lecture Notes", transcript, windows, options)

    def generate_lesson_from_scene_windows(
        self,
        title: str,
        transcript: TranscriptData,
        windows: list[dict],
        options: GenerationOptions,
    ) -> LessonContent:
        if len(windows) > LESSON_CHUNK_THRESHOLD:
            return self._generate_lesson_from_windows_in_batches(title, transcript, windows, options)

        scene_inputs = [window_for_prompt(window, max_chars=1300) for window in windows]
        schema = {
            "title": "string",
            "overview": "string",
            "learning_objectives": ["string"],
            "chapters": [
                {
                    "title": "1. string",
                    "learning_objectives": ["string"],
                    "explanation": "string",
                    "beginner_explanation": "string",
                    "key_points": ["string"],
                    "terms": [{"term": "string", "definition": "string"}],
                    "timestamp": "00:00",
                    "summary": "string",
                }
            ],
            "final_summary": ["string"],
            "review_questions": ["string"],
        }
        prompt = (
            "선택된 장면 구간을 바탕으로 한국어 강의 노트를 만드세요. "
            "입력된 Scenes 배열의 각 항목마다 chapters 항목을 정확히 1개씩 같은 순서로 생성하세요. "
            "예를 들어 Scenes가 12개이면 chapters도 반드시 12개여야 합니다. "
            "겹쳐 추출된 자동 자막, 잘못 끊긴 어절, 어색한 조사와 반복을 자연스럽게 고치세요. "
            "원문에 없는 사실은 추가하지 말고, 보충 설명이 필요하면 '보충 설명:'으로 시작하세요.\n\n"
            f"문서 제목: {title}\n"
            f"난이도: {options.difficulty}\n"
            f"자료 유형: {options.material_type}\n"
            f"분량: {options.pdf_length}\n\n"
            f"JSON shape:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Scenes:\n{json.dumps(scene_inputs, ensure_ascii=False)}"
        )
        try:
            data = self._chat_json(LESSON_SYSTEM_PROMPT, prompt, max_tokens=max(5200, min(12000, len(windows) * 750)))
            lesson = clean_lesson_content(LessonContent.model_validate(data))
            if len(lesson.chapters) != len(windows):
                chapters = self._repair_lesson_chapter_batch(lesson.chapters, title, windows, options, 1)
                return LessonContent.model_validate(
                    {
                        **lesson.model_dump(),
                        "chapters": [chapter.model_dump() for chapter in chapters],
                    }
                )
            return lesson
        except Exception:
            logger.exception("OpenAI lesson generation failed; falling back to mock output")
            return self.fallback.generate_lesson_from_scene_windows(title, transcript, windows, options)

    def _generate_lesson_from_windows_in_batches(
        self,
        title: str,
        transcript: TranscriptData,
        windows: list[dict],
        options: GenerationOptions,
    ) -> LessonContent:
        fallback = self.fallback.generate_lesson_from_scene_windows(title, transcript, windows, options)
        metadata = self._generate_lesson_metadata(title, transcript, windows, options, fallback)
        chapters: list[LessonChapter] = []
        for start_index in range(0, len(windows), LESSON_CHUNK_SIZE):
            batch = windows[start_index : start_index + LESSON_CHUNK_SIZE]
            chapters.extend(self._generate_lesson_chapter_batch(title, batch, options, start_index + 1))

        return clean_lesson_content(
            LessonContent(
                title=metadata["title"],
                overview=metadata["overview"],
                learning_objectives=metadata["learning_objectives"],
                chapters=chapters,
                final_summary=metadata["final_summary"],
                review_questions=metadata["review_questions"],
            )
        )

    def _generate_lesson_metadata(
        self,
        title: str,
        transcript: TranscriptData,
        windows: list[dict],
        options: GenerationOptions,
        fallback: LessonContent,
    ) -> dict:
        schema = {
            "title": "string",
            "overview": "string",
            "learning_objectives": ["string"],
            "final_summary": ["string"],
            "review_questions": ["string"],
        }
        scene_outline = [
            {
                "scene_number": index,
                "title": str(window.get("title") or ""),
                "start": float(window.get("start") or 0),
                "end": float(window.get("end") or 0),
                "summary": str(window.get("summary") or ""),
            }
            for index, window in enumerate(windows, start=1)
        ]
        prompt = (
            "선택된 전체 장면 흐름을 바탕으로 한국어 강의 노트의 문서 메타 정보를 만드세요. "
            "chapters는 여기서 생성하지 않습니다. 모든 장면을 훑은 뒤 전체 개요, 학습 목표, 마지막 정리, 복습 질문만 작성하세요. "
            "원문에 없는 사실은 추가하지 마세요.\n\n"
            f"문서 제목: {title}\n"
            f"난이도: {options.difficulty}\n"
            f"자료 유형: {options.material_type}\n"
            f"분량: {options.pdf_length}\n\n"
            f"JSON shape:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Transcript sample:\n{format_segments(transcript.segments, max_chars=6000)}\n\n"
            f"Scene outline:\n{json.dumps(scene_outline, ensure_ascii=False)}"
        )
        try:
            data = self._chat_json(LESSON_SYSTEM_PROMPT, prompt, max_tokens=1800)
            return {
                "title": str(data.get("title") or fallback.title),
                "overview": str(data.get("overview") or fallback.overview),
                "learning_objectives": string_list(data.get("learning_objectives"), fallback.learning_objectives),
                "final_summary": string_list(data.get("final_summary"), fallback.final_summary),
                "review_questions": string_list(data.get("review_questions"), fallback.review_questions),
            }
        except Exception:
            logger.exception("OpenAI lesson metadata generation failed; using fallback metadata")
            return {
                "title": fallback.title,
                "overview": fallback.overview,
                "learning_objectives": fallback.learning_objectives,
                "final_summary": fallback.final_summary,
                "review_questions": fallback.review_questions,
            }

    def _generate_lesson_chapter_batch(
        self,
        title: str,
        windows: list[dict],
        options: GenerationOptions,
        start_number: int,
    ) -> list[LessonChapter]:
        scene_inputs = [
            {
                **window_for_prompt(window, max_chars=1700),
                "scene_number": start_number + offset,
            }
            for offset, window in enumerate(windows)
        ]
        schema = {
            "chapters": [
                {
                    "title": "13. string",
                    "learning_objectives": ["string"],
                    "explanation": "string",
                    "beginner_explanation": "string",
                    "key_points": ["string"],
                    "terms": [{"term": "string", "definition": "string"}],
                    "timestamp": "00:00",
                    "summary": "string",
                }
            ]
        }
        expected_count = len(windows)
        end_number = start_number + expected_count - 1
        prompt = (
            "선택된 장면 구간 각각에 대해 한국어 강의 노트 chapter를 생성하세요. "
            "입력 Scenes 배열의 각 항목마다 chapters 항목을 정확히 1개씩 같은 순서로 생성하세요. "
            f"이번 배치는 전체 문서 중 장면 {start_number}부터 {end_number}까지입니다. "
            "각 chapter.title은 반드시 해당 scene_number로 시작하세요. "
            "내용 정리, 핵심 포인트, 주요 용어는 해당 장면의 transcript와 current_summary에 근거해야 하며, "
            "뒤쪽 장면이라고 해서 짧게 쓰거나 일반적인 문장으로 대체하지 마세요. "
            "terms는 실제 장면 내용에 등장하거나 명확히 설명되는 개념만 고르세요. "
            "겹쳐 추출된 자동 자막, 잘못 끊긴 어절, 어색한 조사와 반복을 자연스럽게 고치세요. "
            "원문에 없는 사실은 추가하지 말고, 보충 설명이 필요하면 '보충 설명:'으로 시작하세요.\n\n"
            f"문서 제목: {title}\n"
            f"난이도: {options.difficulty}\n"
            f"자료 유형: {options.material_type}\n"
            f"분량: {options.pdf_length}\n\n"
            f"JSON shape:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Scenes:\n{json.dumps(scene_inputs, ensure_ascii=False)}"
        )
        try:
            data = self._chat_json(LESSON_SYSTEM_PROMPT, prompt, max_tokens=max(4200, min(10000, expected_count * 1050)))
            chapters = [LessonChapter.model_validate(item) for item in data.get("chapters", [])]
            return self._repair_lesson_chapter_batch(chapters, title, windows, options, start_number)
        except Exception:
            logger.exception("OpenAI lesson chapter batch generation failed; retrying scenes %s-%s individually", start_number, end_number)
            return [
                self._generate_lesson_chapter_for_window(title, window, options, start_number + offset)
                for offset, window in enumerate(windows)
            ]

    def _repair_lesson_chapter_batch(
        self,
        chapters: list[LessonChapter],
        title: str,
        windows: list[dict],
        options: GenerationOptions,
        start_number: int,
    ) -> list[LessonChapter]:
        if len(chapters) == len(windows):
            return normalize_chapter_numbers(chapters, start_number)

        logger.warning("OpenAI lesson chapter batch count mismatch: expected %s, got %s", len(windows), len(chapters))
        repaired = chapters[: len(windows)]
        if len(repaired) < len(windows):
            for offset in range(len(repaired), len(windows)):
                repaired.append(self._generate_lesson_chapter_for_window(title, windows[offset], options, start_number + offset))
        return normalize_chapter_numbers(repaired, start_number)

    def _generate_lesson_chapter_for_window(
        self,
        title: str,
        window: dict,
        options: GenerationOptions,
        scene_number: int,
    ) -> LessonChapter:
        scene_input = {**window_for_prompt(window, max_chars=2200), "scene_number": scene_number}
        schema = {
            "chapter": {
                "title": f"{scene_number}. string",
                "learning_objectives": ["string"],
                "explanation": "string",
                "beginner_explanation": "string",
                "key_points": ["string"],
                "terms": [{"term": "string", "definition": "string"}],
                "timestamp": "00:00",
                "summary": "string",
            }
        }
        prompt = (
            "다음 단일 장면을 한국어 강의 노트 chapter로 작성하세요. "
            f"chapter.title은 반드시 '{scene_number}. '로 시작하세요. "
            "내용 정리, 핵심 포인트, 주요 용어는 이 장면의 transcript와 current_summary에 근거해야 합니다. "
            "terms는 실제 장면 내용에 등장하거나 명확히 설명되는 개념만 고르세요. "
            "원문에 없는 사실은 추가하지 말고, 보충 설명이 필요하면 '보충 설명:'으로 시작하세요.\n\n"
            f"문서 제목: {title}\n"
            f"난이도: {options.difficulty}\n"
            f"자료 유형: {options.material_type}\n"
            f"분량: {options.pdf_length}\n\n"
            f"JSON shape:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Scene:\n{json.dumps(scene_input, ensure_ascii=False)}"
        )
        try:
            data = self._chat_json(LESSON_SYSTEM_PROMPT, prompt, max_tokens=2200)
            return normalize_chapter_numbers([LessonChapter.model_validate(data.get("chapter", data))], scene_number)[0]
        except Exception:
            logger.exception("OpenAI single scene lesson generation failed; using fallback for scene %s", scene_number)
            fallback = self.fallback.generate_lesson_from_scene_windows(title, TranscriptData(segments=[], duration=0), [window], options)
            return normalize_chapter_numbers(fallback.chapters, scene_number)[0]

    def summarize_scene_windows(self, windows: list[dict]) -> SceneWindowSummaryList:
        if not windows:
            return SceneWindowSummaryList(scenes=[])
        scene_inputs = [window_for_prompt(window, max_chars=1000) for window in windows]
        schema = {
            "scenes": [
                {
                    "id": "same id from input",
                    "title": "short natural title",
                    "summary": "one or two complete Korean sentences",
                }
            ]
        }
        prompt = (
            "장면 선택 메뉴에 표시할 요약을 생성하세요. 각 scene의 transcript는 자동 자막이라 중복과 끊긴 말이 섞일 수 있습니다. "
            "스크립트를 그대로 복사하지 말고 의미를 보존해 자연스러운 한국어 문장으로 재작성하세요. "
            "잘못 인식된 단어는 문맥상 분명할 때만 고치고, 불확실한 내용은 단정하지 마세요. "
            "각 summary는 1-2문장, title은 8단어 이하로 작성하세요.\n\n"
            f"JSON shape:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Scenes:\n{json.dumps(scene_inputs, ensure_ascii=False)}"
        )
        try:
            data = self._chat_json(SCENE_SYSTEM_PROMPT, prompt, max_tokens=max(1000, len(windows) * 180))
            parsed = SceneWindowSummaryList.model_validate(data)
            return clean_scene_summaries(fill_missing_scene_summaries(windows, parsed))
        except Exception:
            logger.exception("OpenAI scene summary generation failed; falling back to local summaries")
            return self.fallback.summarize_scene_windows(windows)

    def summarize(self, transcript: TranscriptData) -> str:
        prompt = (
            "아래 transcript의 전체 내용을 한국어로 3문장 이내로 요약하세요. "
            "반복 자막은 통합하고, 원문에 없는 사실은 추가하지 마세요.\n\n"
            f"Transcript:\n{format_segments(transcript.segments, max_chars=10000)}"
        )
        try:
            data = self._chat_json(SUMMARY_SYSTEM_PROMPT, prompt, max_tokens=700)
            summary = str(data.get("summary") or "").strip()
            if summary:
                return summary
        except Exception:
            logger.exception("OpenAI transcript summary failed; falling back to mock output")
        return self.fallback.summarize(transcript)

    def _chat_json(self, system: str, user: str, max_tokens: int) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": max_tokens,
        }
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        return parse_json_object(content)


SCENE_SYSTEM_PROMPT = (
    "You rewrite noisy auto-caption snippets into concise, coherent Korean scene summaries. "
    "Return JSON only."
)
CHAPTER_SYSTEM_PROMPT = "You create timestamped Korean chapter analysis from transcript text. Return JSON only."
KEY_MOMENT_SYSTEM_PROMPT = "You select educational key moments from transcript chapters. Return JSON only."
LESSON_SYSTEM_PROMPT = "You create Korean lecture notes grounded in the supplied transcript windows. Return JSON only."
SUMMARY_SYSTEM_PROMPT = "You summarize Korean transcript text faithfully. Return JSON only with a summary field."


def window_for_prompt(window: dict, max_chars: int) -> dict:
    segments = window.get("segments", [])
    return {
        "id": str(window.get("id") or ""),
        "title": str(window.get("title") or ""),
        "start": float(window.get("start") or 0),
        "end": float(window.get("end") or 0),
        "timestamp": format_timestamp(float(window.get("start") or 0)),
        "current_summary": str(window.get("summary") or ""),
        "transcript": format_segments(segments, max_chars=max_chars),
    }


def format_segments(segments: list[TranscriptSegment], max_chars: int) -> str:
    lines = []
    size = 0
    for segment in segments:
        text = re.sub(r"\s+", " ", segment.text).strip()
        if not text:
            continue
        line = f"[{format_timestamp(segment.start)}-{format_timestamp(segment.end)}] {text}"
        if size + len(line) > max_chars:
            break
        lines.append(line)
        size += len(line)
    return "\n".join(lines)


def parse_json_object(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("OpenAI response was not a JSON object")
    return value


def fill_missing_scene_summaries(windows: list[dict], parsed: SceneWindowSummaryList) -> SceneWindowSummaryList:
    by_id = {scene.id: scene for scene in parsed.scenes}
    scenes: list[SceneWindowSummary] = []
    fallback = MockLLMProvider().summarize_scene_windows(windows)
    fallback_by_id = {scene.id: scene for scene in fallback.scenes}
    for index, window in enumerate(windows, start=1):
        scene_id = str(window.get("id") or index)
        scene = by_id.get(scene_id) or fallback_by_id.get(scene_id)
        if scene is None:
            scene = SceneWindowSummary(id=scene_id, title=f"Scene {index}", summary="이 구간에는 추출 가능한 스크립트가 많지 않습니다.")
        try:
            scenes.append(SceneWindowSummary.model_validate(scene))
        except ValidationError:
            scenes.append(SceneWindowSummary(id=scene_id, title=f"Scene {index}", summary="이 구간에는 추출 가능한 스크립트가 많지 않습니다."))
    return SceneWindowSummaryList(scenes=scenes)


def clean_scene_summaries(summary_list: SceneWindowSummaryList) -> SceneWindowSummaryList:
    return SceneWindowSummaryList(
        scenes=[
            SceneWindowSummary(
                id=scene.id,
                title=correct_common_transcript_terms(scene.title),
                summary=correct_common_transcript_terms(scene.summary),
            )
            for scene in summary_list.scenes
        ]
    )


def clean_lesson_content(content: LessonContent) -> LessonContent:
    data = content.model_dump()
    data["title"] = correct_common_transcript_terms(data["title"])
    data["overview"] = correct_common_transcript_terms(data["overview"])
    data["learning_objectives"] = [correct_common_transcript_terms(item) for item in data["learning_objectives"]]
    data["final_summary"] = [correct_common_transcript_terms(item) for item in data["final_summary"]]
    data["review_questions"] = [correct_common_transcript_terms(item) for item in data["review_questions"]]
    for chapter in data["chapters"]:
        for key in ["title", "explanation", "beginner_explanation", "timestamp", "summary"]:
            chapter[key] = correct_common_transcript_terms(chapter[key])
        chapter["learning_objectives"] = [correct_common_transcript_terms(item) for item in chapter["learning_objectives"]]
        chapter["key_points"] = [correct_common_transcript_terms(item) for item in chapter["key_points"]]
        chapter["terms"] = [
            {term_key: correct_common_transcript_terms(term_value) for term_key, term_value in term.items()}
            for term in chapter["terms"]
        ]
    return LessonContent.model_validate(data)


def string_list(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    items = [str(item).strip() for item in value if str(item).strip()]
    return items or fallback


def normalize_chapter_numbers(chapters: list[LessonChapter], start_number: int) -> list[LessonChapter]:
    normalized: list[LessonChapter] = []
    for offset, chapter in enumerate(chapters):
        scene_number = start_number + offset
        title_without_number = re.sub(r"^\s*\d+\s*[.)]\s*", "", chapter.title).strip()
        normalized.append(chapter.model_copy(update={"title": f"{scene_number}. {title_without_number or chapter.title}"}))
    return normalized


def ensure_lesson_covers_windows(
    content: LessonContent,
    title: str,
    transcript: TranscriptData,
    windows: list[dict],
    options: GenerationOptions,
) -> LessonContent:
    if len(content.chapters) == len(windows):
        return content

    logger.warning("OpenAI lesson chapter count mismatch: expected %s, got %s", len(windows), len(content.chapters))
    fallback = MockLLMProvider().generate_lesson_from_scene_windows(title, transcript, windows, options)
    chapters = content.chapters[: len(windows)]
    if len(chapters) < len(windows):
        chapters.extend(fallback.chapters[len(chapters):])

    return LessonContent.model_validate(
        {
            **content.model_dump(),
            "chapters": [chapter.model_dump() for chapter in chapters],
        }
    )
