from pathlib import Path
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.schemas.pipeline import LessonContent


class DocumentGenerator:
    def __init__(self, template_dir: Path | None = None):
        root = template_dir or Path(__file__).resolve().parents[1] / "templates"
        self.env = Environment(loader=FileSystemLoader(root), autoescape=select_autoescape(["html", "xml"]))

    def render_html(
        self,
        output_path: Path,
        content: LessonContent,
        project: dict,
        chapters: list[dict],
        moments: list[dict],
        frames: list[dict],
    ) -> Path:
        template = self.env.get_template("lecture.html.j2")
        html = template.render(
            app_name=settings.app_name,
            content=content,
            project=project,
            chapters=chapters,
            moments=moments,
            frames=frames,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        return output_path

    def generate_pdf(self, html_path: Path, pdf_path: Path) -> Path:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from playwright.sync_api import sync_playwright

            pdf_html_path = self._prepare_html_for_pdf(html_path)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page()
                page.goto(pdf_html_path.resolve().as_uri(), wait_until="networkidle")
                page.pdf(path=str(pdf_path), format="A4", print_background=True)
                browser.close()
            return pdf_path
        except Exception:
            return self._fallback_pdf(html_path, pdf_path)

    def _fallback_pdf(self, html_path: Path, pdf_path: Path) -> Path:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas

            text = html_path.read_text(encoding="utf-8", errors="ignore")
            stripped = " ".join(text.replace("<", " <").split())
            c = canvas.Canvas(str(pdf_path), pagesize=A4)
            width, height = A4
            c.setFont("Helvetica-Bold", 16)
            c.drawString(48, height - 64, "AI Generated Lecture Notes")
            c.setFont("Helvetica", 10)
            y = height - 96
            for chunk in [stripped[i : i + 95] for i in range(0, min(len(stripped), 3500), 95)]:
                if y < 56:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    y = height - 56
                c.drawString(48, y, chunk)
                y -= 14
            c.save()
            return pdf_path
        except Exception:
            pdf_path.write_bytes(
                b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
                b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n"
                b"trailer<</Root 1 0 R>>\n%%EOF"
            )
            return pdf_path

    def _prepare_html_for_pdf(self, html_path: Path) -> Path:
        html = html_path.read_text(encoding="utf-8")

        def replace_storage_src(match: re.Match[str]) -> str:
            quote = match.group("quote")
            src = match.group("src")
            file_uri = self._src_to_file_uri(src)
            return f"src={quote}{file_uri}{quote}"

        html = re.sub(r"src=(?P<quote>['\"])(?P<src>(?:/storage/|[A-Za-z]:\\)[^'\"]+)(?P=quote)", replace_storage_src, html)
        pdf_html_path = html_path.with_name("lecture.pdf.html")
        pdf_html_path.write_text(html, encoding="utf-8")
        return pdf_html_path

    def _src_to_file_uri(self, src: str) -> str:
        if src.startswith("/storage/"):
            relative = src.removeprefix("/storage/").replace("/", "\\")
            return (settings.storage_path / relative).resolve().as_uri()
        return Path(src).resolve().as_uri()
