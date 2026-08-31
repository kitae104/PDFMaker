from pathlib import Path

from app.services.vision.base import VisionProvider


class MockVisionProvider(VisionProvider):
    def select_best_frame(self, frame_paths: list[Path]) -> Path:
        if not frame_paths:
            raise ValueError("No frames to select")
        return frame_paths[len(frame_paths) // 2]
