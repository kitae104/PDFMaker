---
name: pdf-document
description: "PDFMaker 강의 노트 HTML/PDF 렌더링 규약. lecture.html.j2 템플릿, DocumentGenerator(document.py), Playwright PDF와 ReportLab 폴백, 목차·번호, 이미지 배치, 페이지 나눔, 여백, 한글 폰트 깨짐 작업 시 반드시 사용. 'PDF 모양 이상', '목차 번호', '이미지가 안 나와', '글자 깨짐', 'PDF 디자인 수정' 요청에도 사용. 이 프로젝트가 PDF를 '만드는 코드'를 고치는 스킬이다 — 이미 있는 PDF 파일을 병합·분할·추출하는 일반 PDF 작업이나 생성 텍스트 내용 자체의 품질(llm-content)에는 쓰지 않는다."
---

# PDF Document

`LessonContent` → Jinja2 HTML → PDF. 렌더링 경로가 두 개이고, 둘 다 실제 사용자에게 도달할 수 있다.

## 렌더링 경로

```
render_html(lecture.html.j2)  →  lecture.html
generate_pdf():
  _prepare_html_for_pdf()  한글 @font-face 주입, /storage/ 이미지 src → file:// URI  →  lecture.pdf.html
  ├─ Playwright chromium page.pdf(A4)      ← 주 경로
  └─ 예외 시 _fallback_pdf() (ReportLab)    ← 브라우저 미설치·클라우드 환경에서 실제로 쓰임
```

- 템플릿만 고치면 ReportLab 폴백에는 반영되지 않는다. 폴백은 `LessonContent`를 직접 읽어 story를 조립한다(`_fallback_styles`, `rich_text_reportlab`). 섹션을 추가·삭제·재배치하면 **양쪽 모두** 수정한다.
- 필터: `toc_title`(목차에서 `"N. "` 접두사 제거 — 챕터 제목은 `"N. 제목"` 형식), `rich_text`(허용 태그만 남기는 sanitizer). 사용자가 편집한 내용은 HTML일 수 있으므로 `| safe`를 새로 쓰지 말고 `rich_text`를 거친다.
- 챕터별 이미지: `frames | selectattr("selected")`의 index와 챕터 index를 짝짓는다. 선택 프레임 수 ≠ 챕터 수이면 뒤쪽 챕터 이미지가 빠지거나 밀린다 — 이미지 관련 변경 시 이 매핑을 확인한다.
- **알려진 차이 (2026-09-22 기준):** ReportLab 폴백에는 목차 섹션이 없다. 폴백 PDF는 `inspect_pdf.py ... --fallback`으로 검사하면 이 항목이 `KNOWN`으로 표시된다. 이 차이를 고치면 `inspect_pdf.py`의 `KNOWN_FALLBACK_GAPS`에서 `목차`를 빼고 이 문단도 지운다.
- 한글 폰트: `_find_korean_fonts()`가 OS별 경로를 탐색하고, 못 찾으면 ReportLab은 CID 폰트(HYGothic)로 대체한다. 새 폰트 경로는 이 함수에 추가한다.

## 작업 절차

1. 변경 전 기준 PDF 생성 (비교용)
   ```bash
   backend/.venv/Scripts/python .claude/skills/pdf-document/scripts/render_sample.py --out _workspace/pdf/before
   backend/.venv/Scripts/python .claude/skills/pdf-document/scripts/render_sample.py --out _workspace/pdf/before --fallback
   ```
2. 템플릿/`document.py` 수정
3. 변경 후 두 경로 모두 재생성 (`--out _workspace/pdf/after`)
4. 점검
   ```bash
   backend/.venv/Scripts/python .claude/skills/pdf-document/scripts/inspect_pdf.py _workspace/pdf/after/sample.pdf
   backend/.venv/Scripts/python .claude/skills/pdf-document/scripts/inspect_pdf.py _workspace/pdf/after/sample_fallback.pdf --fallback
   ```
   `render_sample.py`는 `Renderer:` 줄로 실제 사용된 경로를 알려 준다. 샘플 프레임은 실제 작업처럼 `STORAGE_PATH/_harness_sample/`에 저장되고 `/storage/...` URL로 참조되므로, 이미지 경로 변환도 함께 검증된다.
   검사 항목: 페이지 수, 페이지별 이미지 수, 한글 추출 가능 여부(폰트 누락 탐지), 중복 번호(`1. 1.`), 필수 섹션 존재.
5. 레이아웃 변경이면 PDF 페이지를 Read 도구로 열어 눈으로 확인한다. 텍스트 검사로는 여백·겹침·잘림을 못 잡는다.
6. 실제 사용자 초안으로 재현해야 하면 `--content <LessonContent.json>`을 준다(`GET /api/jobs/{id}/document-draft` 응답 저장본).
7. `cd backend && .venv/Scripts/python -m pytest tests/test_document.py -q`

## 디자인 기준

- A4, 인쇄 배경 포함. 제목만 페이지 끝에 남고 본문이 다음 페이지로 넘어가는 고아 제목을 피한다(`break-after: avoid`).
- "쉽게 이해하기" callout 뒤 여백은 최근 커밋에서 의도적으로 추가됐다 — 유지한다.
- 이미지는 본문 폭에 맞추고 종횡비를 유지한다.
- 색상은 기존 네이비/블루 계열(`#16245a`, `#1e3a8a`, `#1d4ed8`)을 유지해 두 경로의 인상을 맞춘다.

## 산출물 (`_workspace/02_document-designer_changes.md`)
변경 파일 / 두 경로 반영 여부 / inspect_pdf 결과(before·after) / 확인한 PDF 경로 / pytest 결과 / 미검증 항목(예: Playwright 미설치)
