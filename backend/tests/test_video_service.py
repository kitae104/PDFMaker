from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.services.video import VideoService, filter_scene_spacing, format_timestamp, scene_count_for_duration, scene_detection_gap


def test_format_timestamp():
    assert format_timestamp(438) == "07:18"


def test_validate_video_rejects_extension(tmp_path: Path):
    path = tmp_path / "bad.exe"
    path.write_text("x")
    with pytest.raises(AppError):
        VideoService().validate_video(path)


def test_scene_count_extends_after_five_minutes():
    assert scene_count_for_duration(300) == 12
    assert scene_count_for_duration(301) == 13
    assert scene_count_for_duration(600) == 24


def test_scene_detection_gap_keeps_scanning_manageable():
    assert scene_detection_gap(300, 12) == 12.5
    assert scene_detection_gap(600, 24) == 12.5


def test_filter_scene_spacing_samples_across_full_video(tmp_path: Path):
    scenes = [(float(index * 10), tmp_path / f"scene_{index:04d}.jpg") for index in range(60)]

    result = filter_scene_spacing(scenes, duration=600, max_scenes=24)

    assert len(result) == 24
    assert result[0][0] == 0
    assert result[-1][0] == 590
    assert any(timestamp >= 500 for timestamp, _ in result)
