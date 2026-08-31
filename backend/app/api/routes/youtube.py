from fastapi import APIRouter
from pydantic import BaseModel

from app.core.exceptions import AppError
from app.services.youtube import analyze_youtube_url, extract_youtube_id

router = APIRouter(prefix="/youtube", tags=["youtube"])


class YouTubeAnalyzeRequest(BaseModel):
    url: str
    has_rights: bool = False


@router.post("/analyze")
def analyze_youtube(request: YouTubeAnalyzeRequest) -> dict:
    if not request.has_rights:
        raise AppError("분석에 필요한 권한 확인 체크가 필요합니다.", 400)
    try:
        metadata = analyze_youtube_url(request.url)
    except ValueError:
        raise AppError("올바른 YouTube URL이 아닙니다.", 400)
    return metadata
