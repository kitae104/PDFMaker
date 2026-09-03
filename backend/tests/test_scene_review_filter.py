from PIL import Image

from app.schemas.pipeline import SceneWindowSummary, TranscriptSegment
from app.services.job_service import is_mostly_dark_frame, remove_trailing_non_learning_windows


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


def test_remove_trailing_non_learning_windows_drops_channel_closing():
    windows = [
        make_window(1, 0, 940, "도장의 기본 재료와 정상적인 도장 과정을 설명합니다."),
        make_window(2, 940, 972, "다음 영상 예고 및 마무리 인사"),
        make_window(3, 972, 973, "채널 클로징"),
    ]
    summaries = {
        "2": SceneWindowSummary(id="2", title="다음 영상 예고 및 마무리 인사", summary="다음 편 안내와 마무리 클로징 인사입니다."),
        "3": SceneWindowSummary(id="3", title="채널 클로징", summary="자동차 도장의 정석 채널의 마무리 클로징 인사입니다."),
    }

    result = remove_trailing_non_learning_windows(windows, summaries, duration=973)

    assert [window["id"] for window in result] == ["1"]


def test_remove_trailing_non_learning_windows_drops_short_dark_tail(tmp_path):
    dark_frame = tmp_path / "dark.jpg"
    Image.new("RGB", (320, 180), (0, 0, 0)).save(dark_frame)
    windows = [
        make_window(1, 0, 940, "도장 정상성의 핵심 개념을 설명합니다."),
        {
            **make_window(2, 940, 948, "자막 없음"),
            "frame_path": str(dark_frame),
        },
    ]

    result = remove_trailing_non_learning_windows(windows, {}, duration=948)

    assert [window["id"] for window in result] == ["1"]
    assert is_mostly_dark_frame(dark_frame)


def test_remove_trailing_non_learning_windows_keeps_dark_learning_tail(tmp_path):
    dark_frame = tmp_path / "dark-slide.jpg"
    Image.new("RGB", (320, 180), (0, 0, 0)).save(dark_frame)
    windows = [
        make_window(1, 0, 940, "도장 정상성의 핵심 개념을 설명합니다."),
        {
            **make_window(2, 940, 948, "마지막 핵심 개념을 요약하고 학습 내용을 정리합니다."),
            "frame_path": str(dark_frame),
        },
    ]

    result = remove_trailing_non_learning_windows(windows, {}, duration=948)

    assert [window["id"] for window in result] == ["1", "2"]
