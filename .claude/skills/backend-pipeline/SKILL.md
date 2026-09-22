---
name: backend-pipeline
description: "PDFMaker FastAPI 백엔드 파이프라인 작업 규약. Job 생성·실행, JobStatus 상태 전이, API 라우트(/api/jobs/*), SQLAlchemy 모델, Pydantic 스키마, storage/jobs 경로, FFmpeg 장면 추출, YouTube/자막 입력, pytest 작성 시 반드시 사용. 백엔드 API·파이프라인 버그 수정이나 새 엔드포인트 추가 요청에도 사용. LLM 프롬프트 품질(llm-content)이나 PDF 레이아웃(pdf-document) 작업에는 쓰지 않는다."
---

# Backend Pipeline

영상/YouTube/자막 → 장면 검토 → 문서 초안 → PDF 로 이어지는 FastAPI 파이프라인을 안전하게 변경하는 방법.

## 코드 지도

| 영역 | 파일 | 비고 |
|---|---|---|
| 라우트 | `app/api/routes/jobs.py`, `youtube.py`, `health.py` | prefix는 `settings.api_prefix`(`/api`) |
| 오케스트레이션 | `app/services/job_service.py` | `JobService`(외부용 facade) → `PipelineRunner.run()`(백그라운드 실행) |
| 영상 | `app/services/video.py` | ffprobe 메타데이터, 오디오 추출, 장면 감지, 프레임 캡처 |
| 입력 | `youtube.py`, `transcript_parser.py` | yt-dlp, oEmbed, SRT/VTT/텍스트 파싱 |
| 저장 | `app/services/storage.py` | 모든 산출물은 `storage/jobs/{job_id}/` |
| 모델/스키마 | `app/models/entities.py`, `app/schemas/jobs.py`, `schemas/pipeline.py` | |

## JobStatus 상태 머신

```
QUEUED → ANALYZING_INPUT → EXTRACTING_AUDIO → TRANSCRIBING → ANALYZING_TRANSCRIPT
      → GENERATING_CHAPTERS → SELECTING_KEY_MOMENTS → CAPTURING_FRAMES → REVIEW_READY   (PipelineRunner.run)
REVIEW_READY  --POST document-draft-->  DOCUMENT_READY
DOCUMENT_READY --POST pdf-->            COMPLETED
어느 단계든 예외 → FAILED (error_message = user_safe_error(exc))
```

- 상태를 바꿀 때는 `PipelineRunner._status()`를 사용한다. `STATUS_PROGRESS` 맵으로 progress를 갱신하고 즉시 커밋한다.
- 새 상태를 추가하면 **다섯 곳을 함께** 바꾼다: `entities.JobStatus`, `job_service.STATUS_PROGRESS`, `frontend/src/types/index.ts`의 `JobStatus`, `ProgressSteps.tsx`의 `steps`, `utils/format.ts`의 `statusLabel`. 하나라도 빠지면 프론트 진행 표시가 멈춘 것처럼 보인다.
- `error_message`에는 `user_safe_error()`를 거친 문자열만 넣는다 — 원본 예외에 경로나 키가 섞일 수 있다.

## 변경 규칙

1. **스키마 우선.** 응답 형태를 바꾸면 `schemas/*.py`부터 바꾸고 `response_model`을 지정한다. 스키마 없이 dict를 반환하는 라우트(`/transcript`, `/chapters`, `/review-segments` 등)를 고칠 때는 반환 키를 변경 기록에 그대로 적는다 — 프론트 타입과 대조할 유일한 근거다.
2. **FFmpeg는 인자 배열.** `subprocess.run([ffmpeg, "-i", str(path), ...])`. 셸 문자열은 파일명 인젝션 위험이 있다. 실행 파일은 `imageio-ffmpeg` 또는 PATH에서 찾는 기존 헬퍼를 재사용한다.
3. **FFmpeg 없는 환경을 깨지 않는다.** 기존 코드는 FFmpeg 부재 시 placeholder 프레임을 만든다. 새 영상 처리도 같은 폴백을 갖춘다.
4. **파일 경로.** `StorageService`로 job 디렉터리를 얻는다. DB에는 절대 경로가 저장되지만 API 응답에는 `/storage/{storage.relative(path)}` URL만 내보낸다(`GET /frames` 참고). `_frame_dict`의 `path`/`uri`는 PDF 렌더링용 내부 값이므로 라우트 응답으로 그대로 반환하지 않는다.
5. **비밀값.** `.env`를 읽지 않는다. 설정은 `app.core.config.settings`로만 접근하고 키를 로그에 남기지 않는다.
6. **긴 작업은 BackgroundTasks.** 라우트는 Job을 만들고 즉시 `JobResponse`를 반환한다. 프론트는 `GET /jobs/{id}` 폴링으로 상태를 본다.

## 테스트

```bash
cd backend && .venv/Scripts/python -m pytest -q        # Windows venv
```
- 새 로직마다 `tests/test_*.py`에 단위 테스트를 추가한다. 순수 함수(`scene_windows_from_detected_scenes`, `remove_trailing_non_learning_windows` 등)는 직접 테스트하고, 라우트는 `httpx`/`TestClient` + mock provider로 테스트한다.
- 외부 네트워크(YouTube, LLM API)에 의존하는 테스트는 쓰지 않는다. monkeypatch로 대체한다.

## 산출물 기록 형식 (`_workspace/02_pipeline-engineer_changes.md`)

```markdown
## 변경 파일
- path — 한 줄 설명
## API/스키마 변경
- 엔드포인트 | 이전 shape | 이후 shape   (없으면 "없음")
## JobStatus 변경
## 테스트
- 추가/수정 테스트, pytest 결과 요약 (N passed / M failed)
## 미검증 항목
```
