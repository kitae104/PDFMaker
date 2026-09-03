from PIL import Image as PILImage
from pypdf import PdfReader
from urllib.parse import unquote, urlparse

from app.schemas.pipeline import LessonChapter, LessonContent
from app.services.document import DocumentGenerator


def test_pdf_generation_fallback(tmp_path):
    generator = DocumentGenerator()
    html = tmp_path / "lecture.html"
    html.write_text("<html><body><h1>Lecture</h1></body></html>", encoding="utf-8")
    pdf = generator.generate_pdf(html, tmp_path / "lecture.pdf")
    assert pdf.exists()
    assert pdf.stat().st_size > 0


def test_reportlab_fallback_preserves_korean_text_and_images(tmp_path):
    generator = DocumentGenerator()
    html = tmp_path / "lecture.html"
    html.write_text("<html><body><h1>한글 제목</h1></body></html>", encoding="utf-8")
    frame = tmp_path / "frame.jpg"
    PILImage.new("RGB", (320, 180), (20, 89, 71)).save(frame)
    content = LessonContent(
        title="한글 제목",
        overview="한글 개요입니다.",
        learning_objectives=["한글 목표를 이해한다."],
        chapters=[
            LessonChapter(
                title="1. 첫 번째 장면",
                learning_objectives=["장면 내용을 설명한다."],
                explanation="한글 설명이 깨지지 않아야 합니다.",
                beginner_explanation="쉽게 이해할 수 있는 한글 설명입니다.",
                key_points=["핵심 포인트"],
                terms=[{"term": "용어", "definition": "한글 정의"}],
                timestamp="00:00",
                summary="한 줄 정리",
            )
        ],
        final_summary=["마지막 정리"],
        review_questions=["복습 질문"],
    )

    pdf = generator._fallback_pdf(html, tmp_path / "fallback.pdf", content=content, frames=[{"path": str(frame)}])

    assert pdf.exists()
    reader = PdfReader(str(pdf))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "한글 제목" in text
    assert pdf_has_image(reader)


def test_reportlab_fallback_starts_each_chapter_on_new_page(tmp_path):
    generator = DocumentGenerator()
    html = tmp_path / "lecture.html"
    html.write_text("<html><body><h1>한글 제목</h1></body></html>", encoding="utf-8")
    content = LessonContent(
        title="한글 제목",
        overview="한글 개요입니다.",
        learning_objectives=["한글 목표를 이해한다."],
        chapters=[
            LessonChapter(
                title=f"{index}. 장면",
                learning_objectives=["장면 내용을 설명한다."],
                explanation="한글 설명이 깨지지 않아야 합니다.",
                beginner_explanation="쉽게 이해할 수 있는 한글 설명입니다.",
                key_points=["핵심 포인트"],
                terms=[],
                timestamp="00:00",
                summary="한 줄 정리",
            )
            for index in range(1, 3)
        ],
        final_summary=["마지막 정리"],
        review_questions=["복습 질문"],
    )

    pdf = generator._fallback_pdf(html, tmp_path / "paged.pdf", content=content)

    assert len(PdfReader(str(pdf)).pages) >= 3


def test_storage_image_src_converts_to_platform_path(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    frame = storage / "jobs" / "abc123" / "frames" / "scene.jpg"
    frame.parent.mkdir(parents=True)
    frame.write_bytes(b"image")
    monkeypatch.setattr("app.services.document.settings.storage_path", storage)

    uri = DocumentGenerator()._src_to_file_uri("/storage/jobs/abc123/frames/scene.jpg")

    parsed = urlparse(uri)
    assert parsed.scheme == "file"
    assert "%5C" not in uri
    assert unquote(parsed.path).replace("\\", "/").endswith("/storage/jobs/abc123/frames/scene.jpg")


def pdf_has_image(reader: PdfReader) -> bool:
    for page in reader.pages:
        resources = page.get("/Resources") or {}
        xobjects = resources.get("/XObject") or {}
        for value in xobjects.values():
            obj = value.get_object()
            if obj.get("/Subtype") == "/Image":
                return True
    return False
