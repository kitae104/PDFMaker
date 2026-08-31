from abc import ABC, abstractmethod
from pathlib import Path


class VisionProvider(ABC):
    @abstractmethod
    def select_best_frame(self, frame_paths: list[Path]) -> Path:
        raise NotImplementedError
