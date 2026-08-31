from pathlib import Path

import pytest

from app.core.exceptions import AppError
from app.services.video import VideoService, format_timestamp


def test_format_timestamp():
    assert format_timestamp(438) == "07:18"


def test_validate_video_rejects_extension(tmp_path: Path):
    path = tmp_path / "bad.exe"
    path.write_text("x")
    with pytest.raises(AppError):
        VideoService().validate_video(path)
