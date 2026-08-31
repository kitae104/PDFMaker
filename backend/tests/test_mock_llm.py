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
