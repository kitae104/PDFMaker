"""Inspect a generated lecture PDF for common regressions.

Usage: backend/.venv/Scripts/python .claude/skills/pdf-document/scripts/inspect_pdf.py <file.pdf> [--fallback] [--text]

--fallback  The PDF came from the ReportLab fallback, which has no table of contents yet;
            report that heading as KNOWN instead of FAIL.

Checks
- page count, image count per page
- Korean text actually extractable (catches missing-font / tofu output)
- duplicated numbering such as "1. 1." or "1) 1." (table-of-contents regression)
- required section headings present
Exit code 1 if any FAIL.
"""
import re
import sys
from pathlib import Path

from pypdf import PdfReader

REQUIRED = ["목차", "마지막 정리"]
KNOWN_FALLBACK_GAPS = {"목차"}
DUP_NUM = re.compile(r"(?m)^\s*(\d+)\s*[.)]\s*\1\s*[.)]")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    reader = PdfReader(str(Path(next(a for a in sys.argv[1:] if not a.startswith("--")))))
    texts, images = [], []
    for page in reader.pages:
        texts.append(page.extract_text() or "")
        try:
            images.append(len(page.images))
        except Exception:
            images.append(-1)
    full = "\n".join(texts)
    hangul = len(re.findall(r"[가-힣]", full))
    # Chromium PDFs with embedded Korean fonts extract spaces as NUL; treat both as whitespace.
    full = full.replace("\x00", " ")
    compact = re.sub(r"\s+", "", full)
    dups = sorted(set(DUP_NUM.findall(full)))

    results = [
        ("pages", "PASS" if reader.pages else "FAIL", str(len(reader.pages))),
        ("images/page", "INFO", str(images)),
        ("hangul chars", "PASS" if hangul > 20 else "FAIL", str(hangul)),
        ("duplicate numbering", "FAIL" if dups else "PASS", ", ".join(dups) or "-"),
    ]
    fallback = "--fallback" in sys.argv
    for h in REQUIRED:
        if re.sub(r"\s+", "", h) in compact:
            status = "PASS"
        else:
            status = "KNOWN" if fallback and h in KNOWN_FALLBACK_GAPS else "FAIL"
        results.append((f"heading '{h}'", status, "known fallback gap" if status == "KNOWN" else ""))

    for name, status, detail in results:
        print(f"[{status:5}] {name:24} {detail}")
    if "--text" in sys.argv:
        print("\n----- extracted text -----\n" + full)
    return 1 if any(s == "FAIL" for _, s, _ in results) else 0


if __name__ == "__main__":
    sys.exit(main())
