---
name: llm-content
description: "PDFMaker LLM 콘텐츠 생성 규약. LLMProvider 인터페이스(mock/openai/gemini), 장면 요약·챕터·강의 본문(LessonContent) 생성, 시스템 프롬프트 수정, JSON 파싱·폴백, 한국어 강의 노트 품질(자막 근거, 쉬운 설명, 보충 설명 표기) 작업 시 반드시 사용. '요약 품질 개선', '프롬프트 수정', '새 LLM 추가', 'Gemini 모델 변경' 요청에도 사용. PDF 레이아웃·폰트 문제에는 쓰지 않는다."
---

# LLM Content

## 실제 구조 (먼저 확인할 것)

| 파일 | 역할 |
|---|---|
| `app/services/llm/base.py` | `LLMProvider` ABC — 모든 provider가 구현할 메서드 목록 |
| `mock.py` | 키 없이 동작하는 결정적 출력. 테스트·로컬·폴백의 기반 |
| `openai.py` | OpenAI 호환 Chat API 구현. **실제 시스템 프롬프트 상수는 이 파일 하단(`*_SYSTEM_PROMPT`)과 각 메서드의 user prompt 조립부에 있다** |
| `gemini.py` | `OpenAILLMProvider`를 상속, Gemini의 OpenAI 호환 엔드포인트 사용 |
| `providers.py` | `get_llm_provider()` — 키가 없으면 mock으로 폴백 |
| `app/prompts/*.txt` | 현재 **코드에서 로드되지 않는다**. 여기만 고치면 동작이 바뀌지 않는다 |

프롬프트를 바꿀 때: 동작을 바꾸려면 `openai.py`의 상수/조립부를 수정한다. DEVELOPMENT.md의 "프롬프트는 prompts/에" 원칙으로 옮기려면 로더를 추가하는 별도 작업으로 계획하고 사용자에게 알린다 — 조용히 한쪽만 바꾸면 두 곳이 어긋난다.

## 인터페이스 변경 순서

1. `base.py`에 추상 메서드 추가
2. `mock.py` 구현 (결정적, 한국어, 스키마 준수)
3. `openai.py` 구현 → gemini는 상속으로 자동 적용되는지 확인
4. 호출부(`job_service.py`) 연결
5. 테스트: `tests/test_mock_llm.py`, `tests/test_openai_llm.py`(HTTP를 monkeypatch한 고정 JSON 응답)

## 출력 스키마 (`schemas/pipeline.py`)

`LessonContent{title, overview, learning_objectives[], chapters[LessonChapter], final_summary[], review_questions[]}`
`LessonChapter{title, learning_objectives[], explanation, beginner_explanation, key_points[], terms[{term, definition}], timestamp, summary}`

필드를 추가/변경하면 영향 범위: `lecture.html.j2`, `document.py`의 reportlab 폴백, `frontend/src/types/index.ts`, `ResultsPage.tsx` 편집기. 변경 기록에 반드시 적는다.

## 콘텐츠 품질 기준

- **근거성:** 자막에 없는 내용은 본문에 넣지 않는다. 필요한 보충은 `보충 설명`으로 명시한다.
- **챕터 제목:** 형식은 `"{장면번호}. {제목}"`이다(mock과 openai의 정규화 단계가 이 형식을 강제한다). 본문 제목에는 번호가 그대로 보이고, 목차 `<ol>`에서는 `toc_title` 필터가 번호를 떼어 낸다. 번호 형식을 바꾸면(`1)`, `제1장` 등) 목차에 번호가 두 번 찍힌다 — 최근 수정된 중복 번호 버그가 이것이었다.
- **beginner_explanation:** 전문 용어 없이 비유 중심으로 2~4문장.
- **terms:** 자막에 실제 등장한 용어만.
- **분량:** 장면 수에 비례. 긴 영상은 기존 배치 경로(`_generate_lesson_from_windows_in_batches`)를 사용해 토큰 한도를 피한다.
- **JSON 강건성:** `_chat_json` 파싱 실패, 필드 누락, 빈 배열에 대해 mock 폴백 또는 기본값 채움이 동작해야 한다.

## 금지

- 테스트에서 실제 API 호출 (비용, 키 노출)
- 모델명·키 하드코딩 — `settings.*_model`, `settings.*_api_key` 사용

## 산출물 (`_workspace/02_llm-content-engineer_changes.md`)
변경 파일 / 프롬프트 diff 요약 / 스키마 영향 / mock 출력 샘플(JSON 일부) / pytest 결과 / 미검증 항목
