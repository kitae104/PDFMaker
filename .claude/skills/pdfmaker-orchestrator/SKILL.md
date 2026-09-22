---
name: pdfmaker-orchestrator
description: "PDFMaker(영상/YouTube/자막 → 한국어 강의 노트 PDF) 개발 작업을 전문 에이전트(pipeline/llm-content/document/frontend/qa)에게 나눠 맡기고 통합 검증까지 조율하는 오케스트레이터. 기능 추가, 버그 수정, 파이프라인·요약 품질·PDF 레이아웃·화면 개선, 새 LLM/STT/Vision provider 추가, Phase 로드맵(자막 탐색, Vision 프레임 랭킹, PPT·퀴즈 내보내기) 구현처럼 여러 영역에 걸치거나 검증이 필요한 요청에 반드시 사용. 후속 작업: 'QA 다시', '지난 작업 수정', '이전 결과 기반으로 보완', '프론트만 다시', 'PDF 부분만 다시', '재실행', '업데이트', '결과 개선' 요청에도 사용. 코드 설명·단순 질문·한 줄 수정은 직접 처리한다."
---

# PDFMaker Orchestrator

## 실행 모드: 서브 에이전트 (생성 → 검증 루프)

에이전트는 `Agent` 도구로 호출하고, 산출물은 `_workspace/` 파일로 주고받는다. 에이전트끼리 대화할 필요 없이 "변경 기록 → QA 리포트 → 수정" 흐름이면 충분하기 때문이다. 세션에 `TeamCreate`/`SendMessage` 도구가 있고 백엔드·프론트가 같은 API 계약을 동시에 설계해야 하는 큰 작업이면, Phase 2를 에이전트 팀으로 바꿔도 된다(팀원 구성은 아래 표와 동일).

## 에이전트 구성

| 에이전트 | subagent_type | 담당 영역 | 스킬 | 산출물 |
|---|---|---|---|---|
| pipeline-engineer | `pipeline-engineer` | routes, job_service, video, youtube, models, schemas | backend-pipeline | `_workspace/02_pipeline-engineer_changes.md` |
| llm-content-engineer | `llm-content-engineer` | services/llm, 프롬프트, 콘텐츠 품질 | llm-content | `_workspace/02_llm-content-engineer_changes.md` |
| document-designer | `document-designer` | lecture.html.j2, document.py, PDF | pdf-document | `_workspace/02_document-designer_changes.md`, `_workspace/pdf/` |
| frontend-engineer | `frontend-engineer` | frontend/src 전체 | frontend-ui | `_workspace/02_frontend-engineer_changes.md` |
| qa-inspector | `qa-inspector` | 경계면 교차 검증, 테스트 실행 | integration-qa | `_workspace/03_qa_report.md` |

모든 호출에 `model: "opus"`를 지정한다. 커스텀 타입이 세션에 로드되지 않았다면(`.claude/agents/`는 세션 시작 시 로드된다) `subagent_type: "general-purpose"`로 호출하고 프롬프트 첫 줄에 "`.claude/agents/{name}.md`를 읽고 그 역할로 작업하라"를 넣는다.

## Phase 0: 컨텍스트 확인

1. `_workspace/` 존재 여부를 확인한다.
   - **없음** → 초기 실행. Phase 1로.
   - **있음 + 사용자가 이전 작업의 일부 수정/보완 요청** → 부분 재실행. `01_plan.md`, 관련 `02_*`, `03_qa_report.md`를 읽고, 해당 에이전트만 재호출한 뒤 Phase 3(QA)을 다시 돈다.
   - **있음 + 새 작업** → 기존 폴더를 `_workspace_{YYYYMMDD_HHMMSS}/`로 옮기고 초기 실행.
2. `git status`로 작업 트리를 확인한다. 사용자의 커밋되지 않은 변경이 있으면 에이전트가 덮어쓰지 않도록 계획에 해당 파일을 적는다.

## Phase 1: 계획 (오케스트레이터 직접)

1. 요청을 분석해 **필요한 에이전트만** 고른다. 규모 기준:
   - 한 영역, 작은 수정 → 담당 에이전트 1명 + QA
   - API 계약이 바뀜 → pipeline-engineer + frontend-engineer + QA
   - `LessonContent` 필드가 바뀜 → llm-content + pipeline + document + frontend + QA
2. 관련 코드를 직접 훑어보고 `_workspace/01_plan.md`를 쓴다:
   ```markdown
   # 요청
   # 목표 / 완료 기준 (검증 가능한 문장으로)
   # 에이전트별 작업
   ## pipeline-engineer: 작업, 건드릴 파일
   ...
   # 계약 변경 (있다면): 엔드포인트/스키마 이전 → 이후
   # 순서와 병렬 여부
   # 건드리면 안 되는 파일
   ```
3. 계약 변경이 있으면 **계약을 계획 단계에서 확정**한다. 백엔드와 프론트가 각자 추측하면 경계면 불일치가 생긴다.
4. 요구가 모호해 구현 방향이 크게 갈리면 이 단계에서 사용자에게 묻는다.

## Phase 2: 구현

병렬 규칙: 에이전트들이 **서로 다른 파일만** 수정할 때만 한 메시지에서 동시 호출(`run_in_background: true`)한다. `job_service.py`, `schemas/pipeline.py`처럼 여러 에이전트가 건드리는 파일이 있으면 소유자를 정하고 순차 실행한다.

일반적인 순서:
1. 계약 생산자 먼저: pipeline-engineer (스키마/라우트), llm-content-engineer (provider 출력)
2. 소비자: document-designer, frontend-engineer — 1의 `02_*_changes.md`를 입력으로 준다
3. 서로 독립이면 1·2를 병렬로

호출 프롬프트에 반드시 포함할 것:
- `_workspace/01_plan.md` 경로와 해당 에이전트 섹션
- 먼저 읽을 스킬 이름
- 선행 에이전트의 `02_*_changes.md` 경로 (소비자인 경우)
- 산출물 경로
- 부분 재실행이면: QA 리포트의 해당 FAIL 항목 ID와 "지적된 부분만 수정"

예시:
```
Agent(
  description: "Backend: add quiz export endpoint",
  subagent_type: "pipeline-engineer",
  model: "opus",
  prompt: "backend-pipeline 스킬을 읽고 따르라. 계획: _workspace/01_plan.md 의 'pipeline-engineer' 섹션.
           완료 후 _workspace/02_pipeline-engineer_changes.md 를 스킬의 형식대로 작성하라."
)
```

## Phase 3: 검증

각 구현 에이전트가 끝나면 qa-inspector를 호출한다. 입력: 모든 `_workspace/02_*_changes.md`. 출력: `_workspace/03_qa_report.md`. 여러 에이전트가 순차로 작업한 큰 작업이면 계약 생산자 완료 직후 한 번 중간 QA를 돌려 불일치가 소비자에게 전파되기 전에 잡는다.

## Phase 4: 수정 루프 (최대 2회)

1. QA 리포트의 FAIL을 담당 에이전트별로 묶어 재호출한다(프롬프트에 FAIL ID와 리포트 경로).
2. 다시 Phase 3.
3. 2회 후에도 FAIL이 남으면 멈추고 남은 FAIL을 사용자에게 그대로 보고한다. 억지로 통과시키지 않는다.

## Phase 5: 보고

1. 오케스트레이터가 직접 최종 확인: `git diff --stat`, 계획의 완료 기준 충족 여부.
2. 사용자에게 보고: 무엇을 바꿨는지, QA 결과(PASS/FAIL/미검증), 사용자가 직접 확인할 것(예: 실제 API 키로 생성 품질, 브라우저 화면).
3. 커밋은 사용자가 요청할 때만 한다.
4. `_workspace/`는 지우지 않는다(다음 부분 재실행의 입력). git에는 올라가지 않는다(.gitignore).
5. 피드백을 묻는다: "결과나 에이전트 구성에서 바꾸고 싶은 점이 있나요?" 피드백은 해당 스킬/에이전트에 반영하고 CLAUDE.md 변경 이력에 기록한다.

## 데이터 흐름

```
사용자 요청
   ↓
[오케스트레이터] → _workspace/01_plan.md
   ↓
[pipeline] [llm-content]  →  02_*_changes.md   (계약 생산자)
   ↓ (changes 파일을 입력으로)
[document] [frontend]     →  02_*_changes.md   (소비자)
   ↓
[qa-inspector] → 03_qa_report.md
   ↓ FAIL 있으면 담당자 재호출 (≤2회)
[오케스트레이터] → 사용자 보고
```

## 에러 핸들링

| 상황 | 대응 |
|---|---|
| 에이전트가 산출물 파일 없이 종료 | 반환 메시지를 확인하고 1회 재호출. 재실패 시 해당 영역 미완료로 보고 |
| 두 에이전트가 같은 파일을 수정해 충돌 | 뒤에 실행된 에이전트의 변경을 기준으로 `git diff`를 확인, 앞 에이전트의 의도가 사라졌으면 해당 에이전트 재호출 |
| 테스트 환경 부재(FFmpeg, Playwright, node_modules) | 미검증으로 표시하고 계속. 사용자 보고에 명시 |
| QA와 구현 에이전트 판단이 상충 | 둘 다 보고서에 남기고 오케스트레이터가 코드를 직접 읽어 판정 |
| 수정 루프 2회 초과 | 중단하고 사용자에게 남은 문제와 선택지 제시 |

## 테스트 시나리오

### 정상 흐름 — "PDF에 퀴즈(복습 질문 정답) 섹션 추가"
1. Phase 0: `_workspace/` 없음 → 초기 실행
2. Phase 1: `LessonContent`에 `review_answers` 추가 → llm-content, pipeline, document, frontend, qa 선택. 계약을 plan에 확정
3. Phase 2: llm-content(mock/openai 출력) → pipeline(스키마) 순차 → document·frontend 병렬
4. Phase 3: QA — check_contracts에서 `LessonContent` 필드 일치, PDF inspect에 새 섹션 확인
5. Phase 5: 변경 요약 + 미검증(실제 Gemini 출력) 보고

### 에러 흐름 — 경계면 불일치
1. frontend-engineer가 `review_answers`를 `reviewAnswers`로 타입에 추가
2. QA: check_contracts가 `LessonContent ↔ LessonContent`에서 FAIL (TS expects `reviewAnswers`)
3. Phase 4: frontend-engineer만 재호출 (FAIL ID 전달) → QA 재실행 → PASS
4. 보고에 "1회 수정 루프 발생"을 기록

### 부분 재실행 — "PDF 부분만 다시, 이미지가 너무 커"
1. Phase 0: `_workspace/` 있음 + 부분 수정 → document-designer만 재호출(기존 `02_document-designer_changes.md`와 사용자 피드백 전달)
2. QA는 3단계(PDF 점검)와 pytest만 실행
