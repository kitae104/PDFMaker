---
name: frontend-ui
description: "PDFMaker React 프론트엔드 작업 규약. HomePage(입력: 영상 업로드/YouTube URL/자막), ResultsPage(진행 상태·장면 검토·문서 편집·PDF 다운로드), ProgressSteps, api/client.ts, types/index.ts, Zustand store, Tailwind 스타일 수정 시 반드시 사용. '화면 수정', 'UI 개선', '버튼 추가', '편집기 기능', '랜딩 페이지 디자인' 요청에도 사용. 백엔드 API 자체를 만드는 작업(backend-pipeline)에는 쓰지 않는다."
---

# Frontend UI

## 구조

| 파일 | 역할 |
|---|---|
| `src/api/client.ts` | axios 인스턴스(`VITE_API_BASE_URL` 또는 `/api`)와 엔드포인트별 함수. **모든 API 호출은 여기를 거친다** |
| `src/types/index.ts` | 백엔드 응답 타입. `backend/app/schemas/*.py`와 1:1로 맞춰야 한다 |
| `src/main.tsx` | 라우트: `/`, `/results/:jobId` |
| `src/pages/HomePage.tsx` | 입력 3종 + 생성 옵션 → Job 생성 → `GET /jobs/{id}` 폴링 → REVIEW_READY/DOCUMENT_READY/COMPLETED에서 `/results/:jobId`로 이동 |
| `src/pages/ResultsPage.tsx` | 장면 검토·선택 → document-draft 생성/편집(자체 interval 폴링 포함) → PDF 다운로드 |
| `src/components/ProgressSteps.tsx` | `steps: JobStatus[]` 순서로 진행 표시 |
| `src/utils/format.ts` | `statusLabel` 등 한국어 표기 |
| `src/stores/jobs.ts` | Zustand 전역 상태 |

## API 계약 맞추기

1. 응답 타입을 추측하지 않는다. `backend/app/schemas/jobs.py`, `schemas/pipeline.py`, 그리고 dict를 반환하는 라우트는 `backend/app/api/routes/jobs.py`와 `job_service.py`의 `_*_dict` / `build_review_segments`를 직접 읽는다.
2. 백엔드 필드명은 snake_case가 기본이다. 예외적으로 camelCase인 곳(`YouTubeMetadata`, `KeyMomentData.captureRecommended`)은 백엔드 그대로 따른다. 프론트에서 이름을 바꾸지 않는다.
3. `api.get<T>()`의 제네릭은 런타임 검증이 아니다. 타입을 바꾸면 실제 응답 예시(pytest 결과나 `/docs` 스키마)와 대조한다.
4. 새 JobStatus가 생기면 `types` 유니온, `ProgressSteps.steps`, `statusLabel`을 함께 수정한다.
5. 필요한 엔드포인트가 없으면 백엔드를 직접 만들지 말고 변경 기록에 "백엔드 요청"으로 남긴다 — 계약은 pipeline-engineer가 소유한다.

## UX 원칙

- UI 문구는 한국어. 에러는 `job.error_message`를 그대로 보여 주되 기술 스택 트레이스는 노출하지 않는다.
- 긴 작업은 폴링으로 진행률(`progress`)을 보여 준다. 폴링은 COMPLETED/FAILED/REVIEW_READY/DOCUMENT_READY 등 사용자 입력 대기 상태에서 멈춘다.
- 편집기에서 사용자가 입력한 HTML은 백엔드 `rich_text` sanitizer를 거쳐 PDF에 들어간다. 프론트에서 `dangerouslySetInnerHTML`을 새로 쓸 때는 신뢰할 수 있는 내용인지 먼저 확인한다.
- 이미지 URL은 `mediaUrl()`로 감싼다(배포 환경에서 API 호스트가 다를 수 있다).
- 모바일 폭에서도 장면 카드와 편집기가 가로 스크롤 없이 보여야 한다.

## 검증

```bash
cd frontend && npm run build     # tsc -b + vite build. 반드시 통과
```
node_modules가 없으면 `npm ci`를 먼저 실행한다. 화면 동작 확인이 필요하면 `run` 스킬 또는 `run.ps1`로 앱을 띄워 브라우저로 확인한다.

## 산출물 (`_workspace/02_frontend-engineer_changes.md`)
변경 파일 / 호출하는 API와 사용하는 타입 / 백엔드 요청(있다면) / 빌드 결과 / 미검증 항목
