from app.services.vision.base import VisionProvider
from app.services.vision.mock import MockVisionProvider


def get_vision_provider() -> VisionProvider:
    return MockVisionProvider()
