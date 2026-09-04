from app.schemas.pipeline import TranscriptData, TranscriptSegment
from app.services.llm.mock import MockLLMProvider


def test_mock_llm_outputs_structured_data():
    transcript = TranscriptData(segments=[TranscriptSegment(start=0, end=10, text="hello")], duration=300)
    provider = MockLLMProvider()
    chapters = provider.generate_chapters(transcript)
    moments = provider.select_key_moments(transcript, chapters)
    assert len(chapters.chapters) == 3
    assert len(moments.keyMoments) >= 3
    assert moments.keyMoments[0].importance >= 7


def test_mock_scene_summary_uses_learning_title_not_opening_hook():
    transcript = TranscriptData(
        segments=[
            TranscriptSegment(
                start=0,
                end=18,
                text="여러분, 페인트 한 통을 사서 차에 뿌리면 자동으로 색깔이 입혀진다고 생각하셨겠죠? 하지만 자동차 도료에는 화학 공학 기술이 담겨 있습니다.",
            )
        ],
        duration=18,
    )
    provider = MockLLMProvider()
    result = provider.summarize_scene_windows(
        [
            {
                "id": "1",
                "title": "페인트 한 통을 사서 차에 뿌리면 자동으로 색깔이",
                "summary": "",
                "segments": transcript.segments,
            }
        ]
    )

    assert result.scenes[0].title == "자동차 도료 개요: 화학 공학 기술의 집약체"
    assert not result.scenes[0].summary.startswith("여러분")
