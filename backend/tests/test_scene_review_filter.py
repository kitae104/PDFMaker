from app.schemas.pipeline import SceneWindowSummary, TranscriptSegment
from app.services.job_service import remove_trailing_non_learning_windows


def make_window(index: int, start: float, end: float, text: str) -> dict:
    return {
        "id": str(index),
        "title": f"{index}번 장면",
        "summary": text,
        "start": start,
        "end": end,
        "segments": [TranscriptSegment(start=start, end=end, text=text)],
    }


def test_remove_trailing_non_learning_windows_drops_outro_only():
    windows = [
        make_window(1, 0, 60, "핵심 개념을 설명합니다."),
        make_window(2, 60, 120, "실습 과정을 정리합니다."),
        make_window(3, 120, 180, "다음 강의에서는 추가 예제를 소개하겠습니다. 시청해 주셔서 감사합니다."),
    ]
    summaries = {
        "3": SceneWindowSummary(id="3", title="다음 내용 소개", summary="다음 시간 안내와 마무리 인사입니다.")
    }

    result = remove_trailing_non_learning_windows(windows, summaries, duration=180)

    assert [window["id"] for window in result] == ["1", "2"]


def test_remove_trailing_non_learning_windows_keeps_final_learning_summary():
    windows = [
        make_window(1, 0, 60, "핵심 개념을 설명합니다."),
        make_window(2, 60, 120, "오늘 배운 개념을 학습 관점에서 마지막으로 정리합니다."),
    ]

    result = remove_trailing_non_learning_windows(windows, {}, duration=120)

    assert [window["id"] for window in result] == ["1", "2"]
