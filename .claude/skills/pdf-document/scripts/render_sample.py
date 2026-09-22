"""Render a sample lecture note through DocumentGenerator (HTML + PDF) without running the pipeline.

Usage (from repo root):
    backend/.venv/Scripts/python .claude/skills/pdf-document/scripts/render_sample.py [--out _workspace/pdf] [--content draft.json] [--fallback]

--content  LessonContent JSON file. Defaults to a built-in Korean sample.
--fallback Force the ReportLab fallback path instead of Playwright.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.schemas.pipeline import LessonContent  # noqa: E402
from app.services.document import DocumentGenerator  # noqa: E402

SAMPLE_TITLES = ["BMS 개요", "셀 밸런싱", "열 관리"]
SAMPLE = {
    "title": "샘플 강의: 전기차 배터리 관리 시스템",
    "overview": "배터리 관리 시스템(BMS)의 역할과 셀 밸런싱 원리를 다룬다.",
    "learning_objectives": ["BMS의 주요 기능을 설명한다.", "셀 밸런싱이 필요한 이유를 이해한다."],
    "chapters": [
        {
            "title": f"{i}. {title}",
            "learning_objectives": [f"{title}의 핵심을 설명한다."],
            "explanation": f"{title}에 대한 개념 설명입니다. <b>강조</b>와 줄바꿈을 포함합니다.\n두 번째 줄입니다.",
            "beginner_explanation": "물탱크 여러 개의 수위를 똑같이 맞추는 일에 비유할 수 있습니다.",
            "key_points": ["핵심 포인트 A", "핵심 포인트 B"],
            "terms": [{"term": "SOC", "definition": "배터리 충전 상태(State of Charge)"}],
            "timestamp": f"0{i}:00",
            "summary": f"{title} 한 줄 정리.",
        }
        for i, title in enumerate(SAMPLE_TITLES, start=1)
    ],
    "final_summary": ["BMS는 안전과 수명을 지킨다.", "밸런싱은 셀 간 편차를 줄인다."],
    "review_questions": ["패시브 밸런싱과 액티브 밸런싱의 차이는?"],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "_workspace" / "pdf"))
    parser.add_argument("--content")
    parser.add_argument("--fallback", action="store_true")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data = json.loads(Path(args.content).read_text(encoding="utf-8")) if args.content else SAMPLE
    content = LessonContent.model_validate(data)

    # Frames live under STORAGE_PATH and are referenced as /storage/... exactly like real jobs,
    # so the /storage -> file:// rewrite and _frame_path() are exercised.
    frame_dir = Path(settings.storage_path) / "_harness_sample"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i, _ in enumerate(content.chapters):
        img = frame_dir / f"sample_frame_{i}.jpg"
        Image.new("RGB", (1280, 720), (30 + i * 40, 80, 120)).save(img)
        frames.append({"id": f"f{i}", "url": f"/storage/_harness_sample/{img.name}", "selected": True, "timestamp": i * 60})

    gen = DocumentGenerator()
    project = {"title": content.title}
    name = "sample_fallback" if args.fallback else "sample"
    html = gen.render_html(out / f"{name}.html", content, project, [], [], frames)
    pdf_path = out / f"{name}.pdf"

    used = {"renderer": "playwright"}
    real_fallback = gen._fallback_pdf

    def tracking_fallback(*a, **kw):
        used["renderer"] = "reportlab-fallback"
        return real_fallback(*a, **kw)

    gen._fallback_pdf = tracking_fallback
    if args.fallback:
        gen._fallback_pdf(gen._prepare_html_for_pdf(html), pdf_path, content=content, frames=frames, project=project)
    else:
        gen.generate_pdf(html, pdf_path, content=content, frames=frames, project=project)
    print(f"HTML:     {html}")
    print(f"PDF:      {pdf_path}")
    print(f"Renderer: {used['renderer']}")
    if not args.fallback and used["renderer"] != "playwright":
        print("WARNING: Playwright failed and the ReportLab fallback was used; Playwright output is unverified.")

if __name__ == "__main__":
    main()
