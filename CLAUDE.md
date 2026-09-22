# PDFMaker

영상/YouTube/자막 → 장면 검토 → 편집 가능한 한국어 강의 노트 → PDF. FastAPI(`backend/`) + React/Vite(`frontend/`). 개발 규칙은 `DEVELOPMENT.md`, 구조는 `ARCHITECTURE.md`를 따른다.

- 백엔드 테스트: `cd backend && .venv/Scripts/python -m pytest -q`
- 프론트 빌드(타입 검사 포함): `cd frontend && npm run build`
- `.env`에는 실제 API 키가 있다. 읽거나 출력하지 않는다.

## 하네스: PDFMaker 개발

**목표:** 백엔드 파이프라인·LLM 콘텐츠·PDF 렌더링·프론트엔드 변경을 전문 에이전트에게 나눠 맡기고, 경계면 교차 검증까지 거쳐 완료한다.

**트리거:** 여러 영역에 걸치거나 검증이 필요한 PDFMaker 개발 요청(기능 추가, 버그 수정, 품질·레이아웃·UI 개선, 후속 수정·재실행) 시 `pdfmaker-orchestrator` 스킬을 사용하라. 단순 질문·코드 설명·한 줄 수정은 직접 응답 가능.

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-09-22 | 초기 구성 (에이전트 5, 스킬 6) | 전체 | - |
| 2026-09-22 | QA 스크립트 오탐 수정, 기준선 점검 모드·동기 라우트 에러 경로 검사·YouTube 경계면 추가, render_sample이 /storage 경로·실제 렌더러 표시 | integration-qa, pdf-document, qa-inspector | 첫 QA 시험 실행 피드백 |
