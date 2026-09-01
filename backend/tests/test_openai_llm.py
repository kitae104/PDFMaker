from app.schemas.jobs import GenerationOptions
from app.schemas.pipeline import LessonChapter, LessonContent, TranscriptData, TranscriptSegment
from app.services.llm.mock import MockLLMProvider
from app.services.llm.openai import OpenAILLMProvider, ensure_lesson_covers_windows


def make_content(chapter_count: int) -> LessonContent:
    return LessonContent(
        title="테스트 문서",
        overview="개요",
        learning_objectives=["목표"],
        chapters=[
            LessonChapter(
                title=f"{index + 1}. 원본 장면",
                learning_objectives=["학습 목표"],
                explanation="설명",
                beginner_explanation="쉬운 설명",
                key_points=["핵심"],
                terms=[{"term": "용어", "definition": "정의"}],
                timestamp="00:00",
                summary="요약",
            )
            for index in range(chapter_count)
        ],
        final_summary=["정리"],
        review_questions=["질문"],
    )


def make_transcript(window_count: int) -> TranscriptData:
    return TranscriptData(
        language="ko",
        duration=float(window_count * 10),
        segments=[
            TranscriptSegment(start=float(index * 10), end=float(index * 10 + 5), text=f"{index + 1}번 장면 설명입니다.")
            for index in range(window_count)
        ],
    )


def make_windows(count: int) -> list[dict]:
    return [
        {
            "id": str(index + 1),
            "title": f"{index + 1}번 장면",
            "summary": f"{index + 1}번 장면 요약",
            "start": float(index * 10),
            "end": float(index * 10 + 10),
            "segments": [TranscriptSegment(start=float(index * 10), end=float(index * 10 + 5), text=f"{index + 1}번 장면 설명입니다.")],
        }
        for index in range(count)
    ]


def test_ensure_lesson_covers_windows_fills_missing_chapters():
    windows = make_windows(12)
    result = ensure_lesson_covers_windows(make_content(3), "테스트 문서", make_transcript(12), windows, GenerationOptions())

    assert len(result.chapters) == 12
    assert result.chapters[0].title == "1. 원본 장면"
    assert result.chapters[3].title.startswith("4. 4번 장면")


def test_ensure_lesson_covers_windows_trims_extra_chapters():
    windows = make_windows(3)
    result = ensure_lesson_covers_windows(make_content(5), "테스트 문서", make_transcript(3), windows, GenerationOptions())

    assert len(result.chapters) == 3


def test_long_lesson_generation_uses_openai_batches_for_late_scenes():
    provider = FakeOpenAIProvider()
    result = provider.generate_lesson_from_scene_windows("긴 강의", make_transcript(20), make_windows(20), GenerationOptions())

    assert len(result.chapters) == 20
    assert result.chapters[0].title == "1. OpenAI 장면 1"
    assert result.chapters[12].title == "13. OpenAI 장면 13"
    assert result.chapters[-1].title == "20. OpenAI 장면 20"
    assert result.chapters[-1].terms == [{"term": "장면20", "definition": "OpenAI batch에서 고른 용어"}]


def test_long_lesson_generation_retries_missing_batch_scenes_individually():
    provider = PartialBatchOpenAIProvider()
    result = provider.generate_lesson_from_scene_windows("긴 강의", make_transcript(16), make_windows(16), GenerationOptions())

    assert len(result.chapters) == 16
    assert result.chapters[7].title == "8. OpenAI 개별 장면 8"
    assert result.chapters[15].title == "16. OpenAI 개별 장면 16"
    assert result.chapters[15].terms == [{"term": "개별16", "definition": "개별 재요청에서 고른 용어"}]


def test_short_lesson_generation_retries_missing_scenes_individually():
    provider = PartialBatchOpenAIProvider()
    result = provider.generate_lesson_from_scene_windows("짧은 강의", make_transcript(12), make_windows(12), GenerationOptions())

    assert len(result.chapters) == 12
    assert result.chapters[11].title == "12. OpenAI 개별 장면 12"
    assert result.chapters[11].terms == [{"term": "개별12", "definition": "개별 재요청에서 고른 용어"}]


class FakeOpenAIProvider(OpenAILLMProvider):
    def __init__(self):
        self.fallback = MockLLMProvider()

    def _chat_json(self, system: str, user: str, max_tokens: int) -> dict:
        if "문서 메타 정보" in user:
            return {
                "title": "긴 강의",
                "overview": "전체 장면을 끝까지 반영한 개요",
                "learning_objectives": ["전체 흐름 이해"],
                "final_summary": ["끝부분까지 정리"],
                "review_questions": ["마지막 장면의 핵심은 무엇인가요?"],
            }

        scenes = user.split("Scenes:\n", 1)[1]
        import json

        chapters = [self._chapter(scene, index) for index, scene in enumerate(json.loads(scenes), start=1)]
        if '"overview": "string"' in user:
            return {
                "title": "짧은 강의",
                "overview": "전체 장면을 반영한 개요",
                "learning_objectives": ["전체 흐름 이해"],
                "chapters": chapters,
                "final_summary": ["끝부분까지 정리"],
                "review_questions": ["마지막 장면의 핵심은 무엇인가요?"],
            }
        return {"chapters": chapters}

    def _chapter(self, scene: dict, fallback_number: int) -> dict:
        scene_number = scene.get("scene_number") or fallback_number
        return {
            "title": f"{scene_number}. OpenAI 장면 {scene_number}",
            "learning_objectives": [f"장면 {scene_number} 이해"],
            "explanation": f"장면 {scene_number}의 내용을 OpenAI batch 방식으로 정리했습니다.",
            "beginner_explanation": f"장면 {scene_number}을 쉽게 풀어 설명했습니다.",
            "key_points": [f"장면 {scene_number} 핵심"],
            "terms": [{"term": f"장면{scene_number}", "definition": "OpenAI batch에서 고른 용어"}],
            "timestamp": scene["timestamp"],
            "summary": f"장면 {scene_number} 요약",
        }


class PartialBatchOpenAIProvider(FakeOpenAIProvider):
    def _chat_json(self, system: str, user: str, max_tokens: int) -> dict:
        if "Scene:\n" in user:
            import json

            scene = json.loads(user.split("Scene:\n", 1)[1])
            scene_number = scene["scene_number"]
            return {
                "chapter": {
                    "title": f"{scene_number}. OpenAI 개별 장면 {scene_number}",
                    "learning_objectives": [f"개별 장면 {scene_number} 이해"],
                    "explanation": f"장면 {scene_number}을 개별 재요청으로 정리했습니다.",
                    "beginner_explanation": f"장면 {scene_number}을 쉽게 설명했습니다.",
                    "key_points": [f"개별 장면 {scene_number} 핵심"],
                    "terms": [{"term": f"개별{scene_number}", "definition": "개별 재요청에서 고른 용어"}],
                    "timestamp": scene["timestamp"],
                    "summary": f"개별 장면 {scene_number} 요약",
                }
            }

        data = super()._chat_json(system, user, max_tokens)
        if "chapters" in data:
            data["chapters"] = data["chapters"][:-1]
        return data
