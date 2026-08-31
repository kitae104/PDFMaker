export function formatTimestamp(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

export function statusLabel(status: string) {
  const labels: Record<string, string> = {
    QUEUED: '대기 중',
    ANALYZING_INPUT: '영상 정보 확인',
    EXTRACTING_AUDIO: '음성 추출',
    TRANSCRIBING: '스크립트 생성',
    ANALYZING_TRANSCRIPT: 'AI 내용 분석',
    GENERATING_CHAPTERS: '단원 구성',
    SELECTING_KEY_MOMENTS: '중요 장면 선정',
    CAPTURING_FRAMES: '화면 캡처',
    REVIEW_READY: '장면 검토 준비',
    GENERATING_CONTENT: '강의자료 작성',
    GENERATING_HTML: '미리보기 생성',
    DOCUMENT_READY: '편집 초안 준비',
    GENERATING_PDF: 'PDF 생성',
    COMPLETED: '완료',
    FAILED: '실패'
  };
  return labels[status] ?? status;
}
