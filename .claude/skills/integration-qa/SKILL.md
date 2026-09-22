---
name: integration-qa
description: "PDFMaker 통합 QA 검증 절차. 백엔드 Pydantic 스키마 ↔ 프론트 types ↔ api/client.ts 경계면 교차 비교, JobStatus 전이 정합성, pytest·npm build 실행, 생성 PDF 점검, QA 리포트 작성 시 반드시 사용. '검증해줘', 'QA', '테스트 돌려줘', '연동 확인', '깨진 데 없는지 확인', '배포 전 점검' 요청에도 사용. 단순 코드 스타일 리뷰(code-review)에는 쓰지 않는다."
---

# Integration QA

"존재 확인"이 아니라 "양쪽이 서로 맞는가"를 확인한다. 각각은 맞는데 연결부가 어긋나는 결함이 이 프로젝트에서 가장 비싸다 — 예: 스키마 필드 이름 변경 후 axios 제네릭이 그대로라 빌드는 통과하고 화면만 비는 경우.

## 검사 범위 정하기

- `_workspace/02_*_changes.md`가 있으면: 1단계 전체 + 변경 기록에 언급된 경계면만 2단계 + 문서/LLM 변경 시 3단계.
- 변경 기록이 없으면(기준선 점검, "전체 QA 해줘"): **모든 단계, 모든 경계면**을 검사한다.

## 1단계: 자동 검사 (항상)

저장소 루트에서 실행한다(각 명령이 다른 디렉터리에서 시작하지 않도록 서브셸 사용):

```bash
backend/.venv/Scripts/python .claude/skills/integration-qa/scripts/check_contracts.py
(cd backend && .venv/Scripts/python -m pytest -q)
(cd frontend && npm run build)      # frontend/dist가 갱신된다(gitignore 대상)
```

`check_contracts.py`가 보는 것:
- `JobStatus` enum ↔ TS 유니온, `statusLabel` 누락
- 같은 이름의 Pydantic 모델 ↔ TS interface 필드(`JobResponse`는 TS `Job`에 대응)
- `@router.*` 라우트 ↔ `client.ts` 호출 (없는 라우트 호출 = FAIL, 호출되지 않는 라우트 = WARN)

WARN은 판단이 필요하다. 2026-09-22 기준 `POST /jobs/{id}/review-segments/regenerate`는 프론트에서 호출되지 않는다 — 기존 상태이므로 새 WARN과 구분해서 보고한다. 스크립트는 `api.<verb><T>('literal')` 형태와 `apiUrl('...')`만 인식한다. 다른 형태의 호출이 있으면 `unchecked api calls` WARN이 뜨며, 그 호출은 손으로 확인한다.

## 2단계: 수동 교차 비교 (변경 범위에 따라)

스크립트가 못 보는 경계면. 변경 기록(`_workspace/02_*_changes.md`)에 언급된 영역만 골라서 **생산자와 소비자를 같이 열어** 비교한다.

| 경계면 | 생산자 | 소비자 | 확인할 것 |
|---|---|---|---|
| dict 반환 라우트 | `jobs.py`의 `/transcript`, `/chapters`, `/moments`, `/frames`, `/review-segments`, `job_service._*_dict`, `build_review_segments` | `types`의 `Chapter`, `KeyMoment`, `Frame`, `ReviewSegment` | 키 이름, null 가능성, 중첩(`frame: {...} | null`) |
| 상태 전이 | `job_service.py`의 모든 `status =` / `_status(...)` | `ProgressSteps.steps` 순서, HomePage의 이동 조건, ResultsPage `readyStatuses`·폴링 중단 조건 | 프론트가 기다리는 상태에 실제로 도달하는가. **동기 라우트(document-draft, pdf)에서 `_status()`로 중간 상태를 커밋한 뒤 예외가 나면 안정 상태(READY 계열 또는 FAILED)로 돌아가는 경로가 있는가** — 없으면 작업이 GENERATING_*에 영구히 멈추고 프론트가 무한 폴링한다 |
| 문서 콘텐츠 | LLM provider가 만드는 `LessonContent` (mock 포함) | `lecture.html.j2`, `document.py` 폴백, ResultsPage 편집기 | 새/삭제 필드가 세 소비자 모두에 반영됐는가 |
| 파일 URL | `_frame_dict`의 `/storage/...` | `mediaUrl()`, `document._frame_path` | 경로 접두사 일치, 배포 환경 호스트 |
| YouTube 분석 | `services/youtube.py`가 만드는 dict (`/youtube/analyze`) | `types`의 `YouTubeMetadata` (camelCase) | 키 이름, null 가능 필드 |
| 요청 본문 | `schemas/jobs.py`의 `*Create`, `SceneSelectionRequest`, Form 필드 | `client.ts`의 body/FormData 키 | `moment_ids`, `has_rights`, `material_type` 등 이름 일치 |

## 3단계: 산출물 확인 (문서/LLM 변경 시)

```bash
backend/.venv/Scripts/python .claude/skills/pdf-document/scripts/render_sample.py --out _workspace/pdf/qa
backend/.venv/Scripts/python .claude/skills/pdf-document/scripts/render_sample.py --out _workspace/pdf/qa --fallback
backend/.venv/Scripts/python .claude/skills/pdf-document/scripts/inspect_pdf.py _workspace/pdf/qa/sample.pdf
backend/.venv/Scripts/python .claude/skills/pdf-document/scripts/inspect_pdf.py _workspace/pdf/qa/sample_fallback.pdf --fallback
```
- `render_sample.py`가 출력하는 `Renderer:` 줄을 확인한다. 기본 실행인데 `reportlab-fallback`이면 Playwright 출력은 미검증이다.
- `--fallback`을 주면 폴백의 알려진 목차 부재가 `KNOWN`으로 표시된다(pdf-document 스킬 참고). 그 외 FAIL은 모두 실제 결함이다.

## 판정 규칙

- 도구가 없어 못 돌린 검사(node_modules 없음, Playwright 미설치 등)는 **미검증**이다. PASS로 적지 않는다.
- 빌드 통과는 타입 일치의 증거가 아니다. 제네릭 캐스팅 경계는 2단계로 확인한다.
- 직접 수정은 명백한 한 줄 결함(오타, 누락된 라벨)만. 나머지는 담당 에이전트에게 돌려보낸다.

## 항목 세는 법

리포트의 PASS/FAIL/WARN/미검증 개수는 다음 단위로 센다: `check_contracts` 출력 한 줄 = 1항목, pytest = 1항목, npm build = 1항목, 교차 비교 표의 경계면 한 줄 = 1항목, `inspect_pdf` 실행 한 번 = 1항목(KNOWN만 있으면 PASS).

## 리포트 형식 (`_workspace/03_qa_report.md`)

```markdown
# QA Report — {날짜}
## 요약
PASS n / FAIL n / WARN n / 미검증 n — 판정: 통과 | 수정 필요
## 자동 검사
- check_contracts: (출력 붙여넣기)
- pytest: N passed, M failed (실패 테스트 이름)
- npm run build: 성공 | 실패 (첫 에러)
## 교차 비교
| 경계면 | 결과 | 근거 (파일:라인) |
## FAIL 항목
### F1. {제목}
- 담당: pipeline-engineer | llm-content-engineer | document-designer | frontend-engineer (경계면이면 양쪽)
- 위치: path:line ↔ path:line
- 증상 / 수정 제안
## WARN 항목
### W1. {제목} — 위치, 판단 근거, 기존/신규 여부
## 미검증 항목과 이유
```
