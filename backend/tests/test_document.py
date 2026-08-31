from app.schemas.pipeline import LessonContent
from app.services.document import DocumentGenerator


def test_pdf_generation_fallback(tmp_path):
    generator = DocumentGenerator()
    html = tmp_path / "lecture.html"
    html.write_text("<html><body><h1>Lecture</h1></body></html>", encoding="utf-8")
    pdf = generator.generate_pdf(html, tmp_path / "lecture.pdf")
    assert pdf.exists()
    assert pdf.stat().st_size > 0
