from pathlib import Path
import re
import logging
from html import escape

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.schemas.pipeline import LessonContent

logger = logging.getLogger(__name__)


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

    def generate_pdf(
        self,
        html_path: Path,
        pdf_path: Path,
        content: LessonContent | None = None,
        frames: list[dict] | None = None,
        project: dict | None = None,
    ) -> Path:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            pdf_html_path = self._prepare_html_for_pdf(html_path)
        except Exception as exc:
            logger.exception("Failed to prepare HTML for PDF; using original HTML path: %s", exc)
            pdf_html_path = html_path
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page()
                page.goto(pdf_html_path.resolve().as_uri(), wait_until="networkidle")
                page.pdf(path=str(pdf_path), format="A4", print_background=True)
                browser.close()
            return pdf_path
        except Exception as exc:
            logger.exception("Playwright PDF generation failed; using ReportLab fallback: %s", exc)
            return self._fallback_pdf(pdf_html_path, pdf_path, content=content, frames=frames or [], project=project or {})

    def _fallback_pdf(
        self,
        html_path: Path,
        pdf_path: Path,
        content: LessonContent | None = None,
        frames: list[dict] | None = None,
        project: dict | None = None,
    ) -> Path:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import Image, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

            font_name, bold_font_name = self._register_pdf_fonts()
            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                rightMargin=18 * mm,
                leftMargin=18 * mm,
                topMargin=18 * mm,
                bottomMargin=18 * mm,
            )
            styles = self._fallback_styles(font_name, bold_font_name)
            story = []

            if content is None:
                story.extend(self._fallback_story_from_html(html_path, styles))
            else:
                frame_rows = frames or []
                project_data = project or {}
                story.append(Paragraph(self._p(content.title), styles["title"]))
                if project_data.get("title"):
                    story.append(Paragraph(self._p(f"영상 제목: {project_data['title']}"), styles["body"]))
                story.append(Paragraph(self._p("자료 생성: AI Video Lecture Note Generator"), styles["body"]))
                story.append(Spacer(1, 10 * mm))
                story.append(Paragraph("영상 개요", styles["h2"]))
                story.append(Paragraph(self._p(content.overview), styles["callout"]))
                story.append(Paragraph("학습 목표", styles["h3"]))
                story.append(self._list_flowable(content.learning_objectives, styles))
                story.append(PageBreak())

                for index, chapter in enumerate(content.chapters):
                    if index > 0:
                        story.append(PageBreak())
                    story.append(Paragraph(self._p(chapter.title), styles["h2"]))
                    story.append(Spacer(1, 3 * mm))
                    story.append(Paragraph(self._p(f"Source: {chapter.timestamp}"), styles["badge"]))
                    story.append(Spacer(1, 4 * mm))
                    frame_path = self._frame_path(frame_rows[index]) if index < len(frame_rows) else None
                    if frame_path and frame_path.exists():
                        story.extend(self._image_flowable(frame_path, doc.width))
                    story.append(Paragraph("학습 목표", styles["h3"]))
                    story.append(self._list_flowable(chapter.learning_objectives, styles))
                    story.append(Paragraph("개념 설명", styles["h3"]))
                    story.append(Paragraph(self._p(chapter.explanation), styles["body"]))
                    story.append(Paragraph("쉽게 이해하기", styles["h3"]))
                    story.append(Paragraph(self._p(chapter.beginner_explanation), styles["callout"]))
                    story.append(Paragraph("핵심 포인트", styles["h3"]))
                    story.append(self._list_flowable(chapter.key_points, styles))
                    if chapter.terms:
                        story.append(Paragraph("주요 용어", styles["h3"]))
                        rows = [[Paragraph("용어", styles["table_header"]), Paragraph("설명", styles["table_header"])]]
                        rows.extend(
                            [
                                Paragraph(self._p(item.get("term", "")), styles["table_cell"]),
                                Paragraph(self._p(item.get("definition", "")), styles["table_cell"]),
                            ]
                            for item in chapter.terms
                        )
                        table = Table(rows, colWidths=[doc.width * 0.28, doc.width * 0.72], hAlign="LEFT")
                        table.setStyle(
                            TableStyle(
                                [
                                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eff6ff")),
                                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dbeafe")),
                                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                                ]
                            )
                        )
                        story.append(table)
                    story.append(Paragraph("한 줄 정리", styles["h3"]))
                    story.append(Paragraph(self._p(chapter.summary), styles["body"]))
                    story.append(Spacer(1, 8 * mm))

                story.append(Paragraph("마지막 정리", styles["h2"]))
                story.append(self._list_flowable(content.final_summary, styles))
                story.append(Paragraph("복습 질문", styles["h3"]))
                story.append(self._list_flowable(content.review_questions, styles))

            doc.build(story)
            return pdf_path
        except Exception as exc:
            logger.exception("ReportLab PDF fallback failed; writing minimal PDF: %s", exc)
            pdf_path.write_bytes(
                b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
                b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n"
                b"trailer<</Root 1 0 R>>\n%%EOF"
            )
            return pdf_path

    def _prepare_html_for_pdf(self, html_path: Path) -> Path:
        html = html_path.read_text(encoding="utf-8")
        font_css = self._pdf_font_face_css()
        if font_css:
            html = html.replace("<style>", f"<style>\n{font_css}\n", 1)

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

    def _pdf_font_face_css(self) -> str:
        regular, bold = self._find_korean_fonts()
        if not regular:
            return ""
        family = "PDFMakerKR"
        css = [
            f'@font-face {{ font-family: "{family}"; src: url("{regular.resolve().as_uri()}") format("truetype"); font-weight: 400; }}',
        ]
        if bold:
            css.append(f'@font-face {{ font-family: "{family}"; src: url("{bold.resolve().as_uri()}") format("truetype"); font-weight: 700; }}')
        css.append(f'body {{ font-family: "{family}", "Noto Sans KR", "Malgun Gothic", sans-serif; }}')
        return "\n".join(css)

    def _find_korean_fonts(self) -> tuple[Path | None, Path | None]:
        regular_candidates = [
            Path("C:/Windows/Fonts/malgun.ttf"),
            Path("C:/Windows/Fonts/NanumGothic.ttf"),
            Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        ]
        bold_candidates = [
            Path("C:/Windows/Fonts/malgunbd.ttf"),
            Path("C:/Windows/Fonts/NanumGothicBold.ttf"),
            Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        ]
        regular = next((path for path in regular_candidates if path.exists()), None)
        bold = next((path for path in bold_candidates if path.exists()), None)
        return regular, bold

    def _register_pdf_fonts(self) -> tuple[str, str]:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase.ttfonts import TTFont

        font_name = "PDFMakerKR"
        bold_font_name = "PDFMakerKR-Bold"
        regular, bold = self._find_korean_fonts()
        if regular:
            try:
                if font_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(font_name, str(regular)))
                if bold and bold_font_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(bold_font_name, str(bold)))
                elif not bold:
                    bold_font_name = font_name
                return font_name, bold_font_name
            except Exception as exc:
                logger.warning("Failed to register Korean TTF/TTC font %s: %s", regular, exc)

        cid_font = "HYGothic-Medium"
        if cid_font not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(UnicodeCIDFont(cid_font))
        return cid_font, cid_font

    def _fallback_styles(self, font_name: str, bold_font_name: str) -> dict[str, object]:
        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle

        return {
            "title": ParagraphStyle("TitleKR", fontName=bold_font_name, fontSize=24, leading=31, textColor=colors.HexColor("#16245a"), spaceAfter=14),
            "h2": ParagraphStyle("H2KR", fontName=bold_font_name, fontSize=17, leading=24, textColor=colors.HexColor("#1e3a8a"), spaceBefore=8, spaceAfter=10),
            "h3": ParagraphStyle("H3KR", fontName=bold_font_name, fontSize=12, leading=17, textColor=colors.HexColor("#1d4ed8"), spaceBefore=10, spaceAfter=5),
            "body": ParagraphStyle("BodyKR", fontName=font_name, fontSize=10, leading=15, textColor=colors.HexColor("#172033"), spaceAfter=6),
            "callout": ParagraphStyle("CalloutKR", fontName=font_name, fontSize=10, leading=15, textColor=colors.HexColor("#172033"), backColor=colors.HexColor("#eff6ff"), borderColor=colors.HexColor("#bfdbfe"), borderWidth=0.5, borderPadding=8, spaceAfter=8),
            "badge": ParagraphStyle("BadgeKR", fontName=bold_font_name, fontSize=8, leading=11, textColor=colors.HexColor("#1d4ed8"), backColor=colors.HexColor("#dbeafe"), borderPadding=4, spaceAfter=8),
            "table_header": ParagraphStyle("TableHeaderKR", fontName=bold_font_name, fontSize=9, leading=13, textColor=colors.HexColor("#1e3a8a")),
            "table_cell": ParagraphStyle("TableCellKR", fontName=font_name, fontSize=9, leading=13, textColor=colors.HexColor("#172033")),
        }

    def _list_flowable(self, items: list[str], styles: dict[str, object]):
        from reportlab.platypus import ListFlowable, ListItem, Paragraph

        safe_items = items or ["내용 없음"]
        return ListFlowable(
            [ListItem(Paragraph(self._p(item), styles["body"]), leftIndent=12) for item in safe_items],
            bulletType="bullet",
            leftIndent=16,
        )

    def _image_flowable(self, path: Path, max_width: float) -> list:
        from reportlab.platypus import Image, Spacer
        from PIL import Image as PILImage

        with PILImage.open(path) as image:
            width, height = image.size
        target_width = max_width
        target_height = target_width * height / max(width, 1)
        return [Image(str(path), width=target_width, height=target_height), Spacer(1, 8)]

    def _frame_path(self, frame: dict) -> Path | None:
        value = frame.get("path") or frame.get("url")
        if not value:
            return None
        if str(value).startswith("/storage/"):
            return settings.storage_path / str(value).removeprefix("/storage/")
        return Path(str(value))

    def _fallback_story_from_html(self, html_path: Path, styles: dict[str, object]) -> list:
        from reportlab.platypus import Paragraph, Spacer

        text = html_path.read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r"<(script|style).*?</\1>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        stripped = re.sub(r"\s+", " ", text).strip()
        return [Paragraph(self._p(stripped[:4000] or "PDF content"), styles["body"]), Spacer(1, 8)]

    def _p(self, text: str) -> str:
        return escape(re.sub(r"\s+", " ", text or "").strip())
