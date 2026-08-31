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
    TRANSCRIBING: 'Transcript 생성',
    ANALYZING_TRANSCRIPT: 'AI 내용 분석',
    GENERATING_CHAPTERS: 'Chapter 생성',
    SELECTING_KEY_MOMENTS: '중요 장면 선정',
    CAPTURING_FRAMES: '화면 캡처',
    GENERATING_CONTENT: '강의자료 작성',
    GENERATING_HTML: 'HTML 생성',
    GENERATING_PDF: 'PDF 생성',
    COMPLETED: '완료',
    FAILED: '실패'
  };
  return labels[status] ?? status;
}
