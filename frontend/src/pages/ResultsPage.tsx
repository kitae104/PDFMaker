import { type ClipboardEvent, type ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import { Bold, Car, CheckCircle2, CheckSquare, Download, FilePenLine, Film, Gauge, Image as ImageIcon, Italic, List, ListOrdered, Loader2, Square, Underline, Wrench } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import {
  apiUrl,
  generateDocumentDraft,
  generateEditedPdf,
  getChapters,
  getDocumentDraft,
  getJob,
  getReviewSegments,
  getTranscript,
  mediaUrl,
  updateDocumentDraft,
  updateSceneSelection
} from '../api/client';
import { ProgressSteps } from '../components/ProgressSteps';
import type { Chapter, Job, LessonChapter, LessonContent, ReviewSegment, Transcript } from '../types';
import { formatTimestamp } from '../utils/format';

type Tab = 'review' | 'editor' | 'preview' | 'transcript';
type TopListField = 'learning_objectives' | 'final_summary' | 'review_questions';
type ChapterListField = 'learning_objectives' | 'key_points';
type SurfaceTone = 'light' | 'dark';

const readyStatuses = ['REVIEW_READY', 'DOCUMENT_READY', 'COMPLETED'];

const tabItems: { id: Tab; label: string }[] = [
  { id: 'review', label: '장면 선택' },
  { id: 'editor', label: '문서 편집' },
  { id: 'preview', label: '미리보기' },
  { id: 'transcript', label: '스크립트' }
];

export function ResultsPage() {
  const { jobId } = useParams();
  const [job, setJob] = useState<Job | null>(null);
  const [tab, setTab] = useState<Tab>('review');
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [reviewSegments, setReviewSegments] = useState<ReviewSegment[]>([]);
  const [content, setContent] = useState<LessonContent | null>(null);
  const [isGeneratingDraft, setIsGeneratingDraft] = useState(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const [previewVersion, setPreviewVersion] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    let timer: number | undefined;

    const load = async () => {
      const nextJob = await getJob(jobId);
      if (cancelled) return;
      setJob(nextJob);

      if (readyStatuses.includes(nextJob.status)) {
        const [segments, nextTranscript, nextChapters] = await Promise.all([
          getReviewSegments(jobId),
          getTranscript(jobId),
          getChapters(jobId)
        ]);
        if (cancelled) return;
        setReviewSegments(segments);
        setTranscript(nextTranscript);
        setChapters(nextChapters);
      }

      if (nextJob.status === 'DOCUMENT_READY' || nextJob.status === 'COMPLETED') {
        try {
          const draft = await getDocumentDraft(jobId);
          if (!cancelled) {
            setContent(draft);
            setTab((current) => current === 'review' ? 'editor' : current);
          }
        } catch {
          undefined;
        }
      }

      if ((readyStatuses.includes(nextJob.status) || nextJob.status === 'FAILED') && timer) {
        window.clearInterval(timer);
      }
    };

    load().catch(() => setErrorMessage('결과 데이터를 불러오지 못했습니다.'));
    timer = window.setInterval(() => {
      load().catch(() => undefined);
    }, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [jobId]);

  const selectedReviewSegments = useMemo(() => reviewSegments.filter((segment) => segment.selected), [reviewSegments]);
  const selectedIds = useMemo(() => selectedReviewSegments.map((segment) => segment.id), [selectedReviewSegments]);
  const selectedChapterBySegmentId = useMemo(() => {
    const mapping = new Map<string, LessonChapter>();
    if (!content) return mapping;
    if (selectedReviewSegments.length !== content.chapters.length) return mapping;
    selectedReviewSegments.forEach((segment, index) => {
      const chapter = content.chapters[index];
      if (chapter) mapping.set(segment.id, chapter);
    });
    return mapping;
  }, [content, selectedReviewSegments]);
  const readyForReview = job ? readyStatuses.includes(job.status) : false;

  async function toggleSegment(segmentId: string) {
    if (!jobId) return;
    const nextIds = reviewSegments
      .filter((segment) => segment.id === segmentId ? !segment.selected : segment.selected)
      .map((segment) => segment.id);
    setReviewSegments((current) => current.map((segment) => ({ ...segment, selected: nextIds.includes(segment.id) })));
    try {
      const nextSegments = await updateSceneSelection(jobId, nextIds);
      setReviewSegments(nextSegments);
    } catch {
      setErrorMessage('장면 선택을 저장하지 못했습니다.');
    }
  }

  async function createDraft() {
    if (!jobId || !selectedIds.length) return;
    setIsGeneratingDraft(true);
    setErrorMessage('');
    try {
      const draft = await generateDocumentDraft(jobId, selectedIds);
      const nextJob = await getJob(jobId);
      setContent(draft);
      setJob(nextJob);
      setPreviewVersion((version) => version + 1);
      setTab('editor');
    } catch {
      setErrorMessage('문서 초안을 생성하지 못했습니다.');
    } finally {
      setIsGeneratingDraft(false);
    }
  }

  async function downloadEditedPdf() {
    if (!jobId || !content) return;
    setIsDownloadingPdf(true);
    setErrorMessage('');
    try {
      const saved = await saveDocumentEdits({ silent: true });
      const blob = await generateEditedPdf(jobId, saved ?? content);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'lecture-notes.pdf';
      link.click();
      URL.revokeObjectURL(url);
      setJob(await getJob(jobId));
      setPreviewVersion((version) => version + 1);
    } catch {
      setErrorMessage('수정본 PDF를 생성하지 못했습니다.');
    } finally {
      setIsDownloadingPdf(false);
    }
  }

  async function saveDocumentEdits(options: { silent?: boolean } = {}) {
    if (!jobId || !content) return null;
    setIsSavingDraft(true);
    setErrorMessage('');
    if (!options.silent) setSaveMessage('');
    try {
      const saved = await updateDocumentDraft(jobId, content);
      setContent(saved);
      setPreviewVersion((version) => version + 1);
      if (!options.silent) setSaveMessage('수정 내용이 저장되었습니다.');
      return saved;
    } catch {
      setErrorMessage('수정 내용을 저장하지 못했습니다.');
      return null;
    } finally {
      setIsSavingDraft(false);
    }
  }

  function updateContent<K extends keyof LessonContent>(field: K, value: LessonContent[K]) {
    setSaveMessage('');
    setContent((current) => current ? { ...current, [field]: value } : current);
  }

  function updateTopList(field: TopListField, index: number, value: string) {
    setContent((current) => {
      setSaveMessage('');
      if (!current) return current;
      const next = [...current[field]];
      next[index] = value;
      return { ...current, [field]: next };
    });
  }

  function addTopListItem(field: TopListField) {
    setSaveMessage('');
    setContent((current) => current ? { ...current, [field]: [...current[field], ''] } : current);
  }

  function removeTopListItem(field: TopListField, index: number) {
    setSaveMessage('');
    setContent((current) => current ? { ...current, [field]: current[field].filter((_, itemIndex) => itemIndex !== index) } : current);
  }

  function updateChapter(index: number, patch: Partial<LessonChapter>) {
    setSaveMessage('');
    setContent((current) => {
      if (!current) return current;
      return { ...current, chapters: current.chapters.map((chapter, chapterIndex) => chapterIndex === index ? { ...chapter, ...patch } : chapter) };
    });
  }

  function updateChapterList(chapterIndex: number, field: ChapterListField, itemIndex: number, value: string) {
    setSaveMessage('');
    setContent((current) => {
      if (!current) return current;
      const chapters = current.chapters.map((chapter, index) => {
        if (index !== chapterIndex) return chapter;
        const next = [...chapter[field]];
        next[itemIndex] = value;
        return { ...chapter, [field]: next };
      });
      return { ...current, chapters };
    });
  }

  function addChapterListItem(chapterIndex: number, field: ChapterListField) {
    setSaveMessage('');
    setContent((current) => {
      if (!current) return current;
      return {
        ...current,
        chapters: current.chapters.map((chapter, index) => index === chapterIndex ? { ...chapter, [field]: [...chapter[field], ''] } : chapter)
      };
    });
  }

  function removeChapterListItem(chapterIndex: number, field: ChapterListField, itemIndex: number) {
    setSaveMessage('');
    setContent((current) => {
      if (!current) return current;
      return {
        ...current,
        chapters: current.chapters.map((chapter, index) =>
          index === chapterIndex ? { ...chapter, [field]: chapter[field].filter((_, listIndex) => listIndex !== itemIndex) } : chapter
        )
      };
    });
  }

  if (!job || !jobId) {
    return <main className="app-carbon min-h-screen p-8 text-zinc-300">결과를 불러오는 중입니다.</main>;
  }

  return (
    <main className="app-carbon min-h-screen text-[#f8faf2]">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-[#07090a]/82 shadow-[0_14px_34px_rgba(0,0,0,0.34)] backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4">
          <Link to="/" className="flex items-center gap-2 font-black text-white">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-lime-300/25 bg-lime-300/10 text-lime-200">
              <Car className="h-5 w-5" />
            </span>
            AUTO PDF LAB
          </Link>
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={() => saveDocumentEdits()}
              disabled={!content || isSavingDraft}
              className="pit-button inline-flex min-h-10 items-center gap-2 rounded-lg px-4 py-2 text-sm font-black transition disabled:cursor-not-allowed disabled:opacity-55"
            >
              {isSavingDraft ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
              수정 완료
            </button>
            <button
              type="button"
              onClick={downloadEditedPdf}
              disabled={!content || isDownloadingPdf || isSavingDraft}
              className="drive-button inline-flex min-h-10 items-center gap-2 rounded-lg px-4 py-2 text-sm font-black transition"
            >
              {isDownloadingPdf ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              수정본 PDF 다운로드
            </button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl px-5 py-8">
        <div className="glass-panel speed-line mb-6 rounded-lg p-5">
          <div className="flex flex-wrap items-center gap-4">
            <div className="gauge-ring flex h-24 w-24 items-center justify-center rounded-full shadow-[0_18px_36px_rgba(0,0,0,0.34)]">
              <div className="flex h-[76px] w-[76px] items-center justify-center rounded-full bg-[#111719] text-lime-200">
                <Gauge className="h-9 w-9" />
              </div>
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-black text-lime-200">편집 작업대</p>
              <h1 className="mt-1 break-keep text-3xl font-black text-white">{job.project_title}</h1>
              <p className="mt-2 text-zinc-300">{reviewSegments.length || chapters.length || 0}개 장면 / {selectedIds.length}개 선택됨</p>
            </div>
            <div className="metal-card rounded-lg px-4 py-3">
              <p className="text-xs font-black text-cyan-100/70">STATUS</p>
              <p className="mt-1 text-lg font-black text-white">{job.progress}%</p>
            </div>
          </div>
        </div>

        {!readyForReview ? <ProgressSteps job={job} /> : null}
        {errorMessage ? <p className="mb-4 rounded-lg border border-red-300/25 bg-red-400/10 p-3 text-sm text-red-100">{errorMessage}</p> : null}
        {saveMessage ? <p className="mb-4 rounded-lg border border-lime-300/25 bg-lime-300/10 p-3 text-sm font-bold text-lime-100">{saveMessage}</p> : null}

        {readyForReview ? (
          <div className="glass-panel flex h-[calc(100vh-19rem)] min-h-[560px] flex-col overflow-hidden rounded-lg">
            <div className="shrink-0 border-b border-white/10 bg-[#07090a]/44 p-2 backdrop-blur-xl">
              <div className="flex flex-wrap gap-2">
              {tabItems.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setTab(item.id)}
                  className={`min-h-10 rounded-md px-4 py-2 text-sm font-black transition ${
                    tab === item.id ? 'drive-button' : 'pit-button bg-white/[0.04] text-zinc-200'
                  }`}
                >
                  {item.label}
                </button>
              ))}
              </div>
            </div>

            <div className="tab-scroll min-h-0 flex-1 overflow-y-auto p-5">
              {tab === 'review' ? (
                <div>
                  <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h2 className="text-xl font-black text-white">화면 변경 기준 장면</h2>
                      <p className="mt-1 text-sm text-zinc-300">각 이미지는 다음 이미지로 바뀌기 전까지의 스크립트 요약과 연결됩니다.</p>
                    </div>
                    <button
                      type="button"
                      onClick={createDraft}
                      disabled={!selectedIds.length || isGeneratingDraft}
                      className="drive-button inline-flex min-h-10 items-center gap-2 rounded-lg px-4 py-2 text-sm font-black transition"
                    >
                      {isGeneratingDraft ? <Loader2 className="h-4 w-4 animate-spin" /> : <FilePenLine className="h-4 w-4" />}
                      선택 내용으로 문서 초안 생성
                    </button>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    {reviewSegments.map((segment, index) => {
                      const chapter = selectedChapterBySegmentId.get(segment.id);
                      const displayTitle = chapter?.title ?? segment.title;
                      const displaySummary = stripRichText(chapter?.summary ?? segment.summary);
                      return (
                        <article
                          key={segment.id}
                          className={`rounded-lg border p-4 shadow-[0_16px_34px_rgba(0,0,0,0.22)] transition hover:-translate-y-0.5 ${
                            segment.selected ? 'border-lime-300/45 bg-lime-300/[0.08]' : 'border-white/12 bg-white/[0.045]'
                          }`}
                        >
                          <button type="button" onClick={() => toggleSegment(segment.id)} className="mb-3 inline-flex items-center gap-2 text-sm font-black text-zinc-100">
                            {segment.selected ? <CheckSquare className="h-5 w-5 text-lime-200" /> : <Square className="h-5 w-5 text-zinc-500" />}
                            {index + 1}. {formatTimestamp(segment.start)} - {formatTimestamp(segment.end)}
                          </button>
                          {segment.frame ? (
                            <img src={mediaUrl(segment.frame.url)} alt={displayTitle} className="aspect-video w-full rounded-md border border-white/10 object-cover shadow-[0_14px_28px_rgba(0,0,0,0.32)]" />
                          ) : (
                            <div className="flex aspect-video w-full items-center justify-center rounded-md border border-white/10 bg-white/[0.04] text-zinc-500">
                              <ImageIcon className="h-8 w-8" />
                            </div>
                          )}
                          <h3 className="mt-3 text-base font-black text-white">{displayTitle}</h3>
                          <p className="mt-2 text-sm leading-relaxed text-zinc-300">{displaySummary}</p>
                        </article>
                      );
                    })}
                  </div>
                </div>
              ) : null}

              {tab === 'editor' ? (
                content ? (
                  <div className="grid gap-5">
                    <EditorField tone="dark" label="문서 제목" value={content.title} onChange={(value) => updateContent('title', value)} />
                    <EditorTextarea tone="dark" label="전체 영상 개요" value={content.overview} onChange={(value) => updateContent('overview', value)} />
                    <StringListEditor tone="dark" title="학습 목표" items={content.learning_objectives} onChange={(index, value) => updateTopList('learning_objectives', index, value)} onAdd={() => addTopListItem('learning_objectives')} onRemove={(index) => removeTopListItem('learning_objectives', index)} />

                    <div className="grid gap-4">
                      {content.chapters.map((chapter, chapterIndex) => {
                        const chapterFrame = selectedReviewSegments.length === content.chapters.length ? selectedReviewSegments[chapterIndex]?.frame : null;
                        return (
                        <section key={`${chapter.title}-${chapterIndex}`} className="light-card rounded-lg p-4">
                          <div className="mb-4 grid gap-4 sm:grid-cols-[176px_1fr_auto] sm:items-center">
                            {chapterFrame ? (
                              <img
                                src={mediaUrl(chapterFrame.url)}
                                alt={`장면 ${chapterIndex + 1} 캡처`}
                                className="aspect-video w-full max-w-56 rounded-md border border-black/10 object-cover shadow-[0_12px_24px_rgba(0,0,0,0.2)] sm:w-44"
                              />
                            ) : (
                              <div className="flex aspect-video w-full max-w-56 items-center justify-center rounded-md border border-black/10 bg-[#dfe5dc] text-[#6e9e00] shadow-[inset_0_1px_0_rgba(255,255,255,0.8)] sm:w-44">
                                <ImageIcon className="h-6 w-6" />
                              </div>
                            )}
                            <div className="min-w-0">
                              <h2 className="flex items-center gap-2 text-lg font-black text-[#101416]">
                                <Wrench className="h-5 w-5 shrink-0 text-[#6e9e00]" />
                                장면 {chapterIndex + 1}
                              </h2>
                              <p className="mt-1 line-clamp-2 break-keep text-sm font-bold text-zinc-600">{chapter.title}</p>
                            </div>
                            <span className="w-fit rounded-full bg-[#101416] px-3 py-1 text-xs font-black text-lime-200">{chapter.timestamp}</span>
                          </div>
                          <EditorField label="제목" value={chapter.title} onChange={(value) => updateChapter(chapterIndex, { title: value })} />
                          <StringListEditor title="학습 목표" items={chapter.learning_objectives} onChange={(index, value) => updateChapterList(chapterIndex, 'learning_objectives', index, value)} onAdd={() => addChapterListItem(chapterIndex, 'learning_objectives')} onRemove={(index) => removeChapterListItem(chapterIndex, 'learning_objectives', index)} />
                          <RichTextEditor label="개념 설명" value={chapter.explanation} onChange={(value) => updateChapter(chapterIndex, { explanation: value })} />
                          <RichTextEditor label="쉽게 이해하기" value={chapter.beginner_explanation} onChange={(value) => updateChapter(chapterIndex, { beginner_explanation: value })} />
                          <StringListEditor title="핵심 포인트" items={chapter.key_points} onChange={(index, value) => updateChapterList(chapterIndex, 'key_points', index, value)} onAdd={() => addChapterListItem(chapterIndex, 'key_points')} onRemove={(index) => removeChapterListItem(chapterIndex, 'key_points', index)} />
                          <TermEditor chapter={chapter} onChange={(terms) => updateChapter(chapterIndex, { terms })} />
                          <RichTextEditor label="한 줄 정리" value={chapter.summary} onChange={(value) => updateChapter(chapterIndex, { summary: value })} />
                        </section>
                        );
                      })}
                    </div>

                    <StringListEditor tone="dark" title="마지막 정리" items={content.final_summary} onChange={(index, value) => updateTopList('final_summary', index, value)} onAdd={() => addTopListItem('final_summary')} onRemove={(index) => removeTopListItem('final_summary', index)} />
                    <StringListEditor tone="dark" title="복습 질문" items={content.review_questions} onChange={(index, value) => updateTopList('review_questions', index, value)} onAdd={() => addTopListItem('review_questions')} onRemove={(index) => removeTopListItem('review_questions', index)} />
                    <div className="flex flex-wrap justify-end gap-2">
                      <button type="button" onClick={() => saveDocumentEdits()} disabled={isSavingDraft} className="pit-button inline-flex min-h-11 items-center gap-2 rounded-lg px-5 py-3 font-black transition disabled:cursor-not-allowed disabled:opacity-55">
                        {isSavingDraft ? <Loader2 className="h-5 w-5 animate-spin" /> : <CheckCircle2 className="h-5 w-5" />}
                        수정 완료
                      </button>
                      <button type="button" onClick={downloadEditedPdf} disabled={isDownloadingPdf || isSavingDraft} className="drive-button inline-flex min-h-11 items-center gap-2 rounded-lg px-5 py-3 font-black transition">
                        {isDownloadingPdf ? <Loader2 className="h-5 w-5 animate-spin" /> : <Download className="h-5 w-5" />}
                        수정본 PDF 다운로드
                      </button>
                    </div>
                  </div>
                ) : (
                  <EmptyEditor onCreate={createDraft} disabled={!selectedIds.length || isGeneratingDraft} loading={isGeneratingDraft} />
                )
              ) : null}

              {tab === 'preview' ? (
                content ? (
                  <iframe title="문서 미리보기" src={apiUrl(`/jobs/${jobId}/preview?v=${previewVersion}`)} className="h-full min-h-[480px] w-full rounded-lg border border-white/10 bg-white shadow-[0_18px_44px_rgba(0,0,0,0.3)]" />
                ) : (
                  <EmptyEditor onCreate={createDraft} disabled={!selectedIds.length || isGeneratingDraft} loading={isGeneratingDraft} />
                )
              ) : null}

              {tab === 'transcript' ? (
                <div className="grid gap-3">
                  {transcript?.segments.map((segment) => (
                    <div key={`${segment.start}-${segment.end}`} className="metal-card rounded-lg p-3">
                      <span className="font-black text-lime-200">{formatTimestamp(segment.start)}</span>
                      <p className="mt-1 text-zinc-200">{segment.text}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>
    </main>
  );
}

function EmptyEditor({ onCreate, disabled, loading }: { onCreate: () => void; disabled: boolean; loading: boolean }) {
  return (
    <div className="rounded-lg border border-dashed border-lime-300/30 bg-lime-300/[0.06] p-8 text-center">
      <FilePenLine className="mx-auto h-10 w-10 text-lime-200" />
      <p className="mt-3 font-black text-white">선택된 장면으로 문서 초안을 만들 수 있습니다.</p>
      <button type="button" onClick={onCreate} disabled={disabled} className="drive-button mt-4 inline-flex min-h-10 items-center gap-2 rounded-lg px-4 py-2 text-sm font-black transition">
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FilePenLine className="h-4 w-4" />}
        문서 초안 생성
      </button>
    </div>
  );
}

function EditorField({ label, value, onChange, tone = 'light' }: { label: string; value: string; onChange: (value: string) => void; tone?: SurfaceTone }) {
  return (
    <label className="block">
      <span className={`text-sm font-black ${tone === 'dark' ? 'text-lime-100' : 'text-zinc-700'}`}>{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} className="race-field mt-2 w-full rounded-lg px-3 py-2 text-[#101416] outline-none transition" />
    </label>
  );
}

function EditorTextarea({ label, value, onChange, tone = 'light' }: { label: string; value: string; onChange: (value: string) => void; tone?: SurfaceTone }) {
  return (
    <label className="mt-4 block">
      <span className={`text-sm font-black ${tone === 'dark' ? 'text-lime-100' : 'text-zinc-700'}`}>{label}</span>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} className="race-field mt-2 min-h-28 w-full rounded-lg px-3 py-2 leading-relaxed text-[#101416] outline-none transition" />
    </label>
  );
}

function RichTextEditor({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const editorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (editorRef.current && editorRef.current.innerHTML !== value) {
      editorRef.current.innerHTML = value || '';
    }
  }, [value]);

  function runCommand(command: string) {
    editorRef.current?.focus();
    document.execCommand(command);
    onChange(editorRef.current?.innerHTML || '');
  }

  function handlePaste(event: ClipboardEvent<HTMLDivElement>) {
    event.preventDefault();
    const text = event.clipboardData.getData('text/plain');
    document.execCommand('insertText', false, text);
    onChange(editorRef.current?.innerHTML || '');
  }

  return (
    <div className="mt-4">
      <span className="text-sm font-black text-zinc-700">{label}</span>
      <div className="mt-2 overflow-hidden rounded-lg border border-black/10 bg-[#edf2e8] shadow-[0_10px_24px_rgba(14,18,20,0.09),inset_0_1px_0_rgba(255,255,255,0.8)]">
        <div className="flex flex-wrap gap-1 border-b border-black/10 bg-[#101416] p-2">
          <EditorToolButton label="굵게" icon={<Bold />} onClick={() => runCommand('bold')} />
          <EditorToolButton label="기울임" icon={<Italic />} onClick={() => runCommand('italic')} />
          <EditorToolButton label="밑줄" icon={<Underline />} onClick={() => runCommand('underline')} />
          <EditorToolButton label="글머리 목록" icon={<List />} onClick={() => runCommand('insertUnorderedList')} />
          <EditorToolButton label="번호 목록" icon={<ListOrdered />} onClick={() => runCommand('insertOrderedList')} />
        </div>
        <div
          ref={editorRef}
          role="textbox"
          aria-label={label}
          contentEditable
          suppressContentEditableWarning
          onInput={(event) => onChange(event.currentTarget.innerHTML)}
          onBlur={(event) => onChange(event.currentTarget.innerHTML)}
          onPaste={handlePaste}
          className="min-h-36 w-full bg-[#f8faf2] px-3 py-3 leading-relaxed text-[#101416] outline-none [&_ol]:ml-5 [&_ol]:list-decimal [&_p]:mb-2 [&_ul]:ml-5 [&_ul]:list-disc"
        />
      </div>
    </div>
  );
}

function EditorToolButton({ label, icon, onClick }: { label: string; icon: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      title={label}
      aria-label={label}
      className="pit-button flex h-9 w-9 items-center justify-center rounded-md p-0 text-lime-100 transition [&>svg]:h-4 [&>svg]:w-4"
    >
      {icon}
    </button>
  );
}

function StringListEditor({
  title,
  items,
  onChange,
  onAdd,
  onRemove,
  tone = 'light'
}: {
  title: string;
  items: string[];
  onChange: (index: number, value: string) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
  tone?: SurfaceTone;
}) {
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h3 className={`text-sm font-black ${tone === 'dark' ? 'text-lime-100' : 'text-zinc-700'}`}>{title}</h3>
        <button type="button" onClick={onAdd} className="rounded-md bg-[#101416] px-3 py-1.5 text-xs font-black text-lime-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.14)] transition hover:bg-[#20282b]">추가</button>
      </div>
      <div className="grid gap-2">
        {items.map((item, index) => (
          <div key={`${title}-${index}`} className="grid gap-2 sm:grid-cols-[1fr_auto]">
            <input value={item} onChange={(event) => onChange(index, event.target.value)} className="race-field rounded-lg px-3 py-2 text-[#101416] outline-none transition" />
            <button type="button" onClick={() => onRemove(index)} className="rounded-md px-3 py-2 text-sm font-black text-red-600 transition hover:bg-red-50">삭제</button>
          </div>
        ))}
      </div>
    </div>
  );
}

function stripRichText(value: string) {
  return value
    .replace(/<\s*br\s*\/?\s*>/gi, ' ')
    .replace(/<\/(p|div|li)>/gi, ' ')
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function TermEditor({ chapter, onChange }: { chapter: LessonChapter; onChange: (terms: LessonChapter['terms']) => void }) {
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h3 className="text-sm font-black text-zinc-700">주요 용어</h3>
        <button type="button" onClick={() => onChange([...chapter.terms, { term: '', definition: '' }])} className="rounded-md bg-[#101416] px-3 py-1.5 text-xs font-black text-lime-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.14)] transition hover:bg-[#20282b]">추가</button>
      </div>
      <div className="grid gap-2">
        {chapter.terms.map((term, index) => (
          <div key={`${term.term}-${index}`} className="grid gap-2 lg:grid-cols-[0.35fr_1fr_auto]">
            <input
              value={term.term}
              onChange={(event) => onChange(chapter.terms.map((item, itemIndex) => itemIndex === index ? { ...item, term: event.target.value } : item))}
              className="race-field rounded-lg px-3 py-2 text-[#101416] outline-none transition"
              placeholder="용어"
            />
            <input
              value={term.definition}
              onChange={(event) => onChange(chapter.terms.map((item, itemIndex) => itemIndex === index ? { ...item, definition: event.target.value } : item))}
              className="race-field rounded-lg px-3 py-2 text-[#101416] outline-none transition"
              placeholder="설명"
            />
            <button type="button" onClick={() => onChange(chapter.terms.filter((_, itemIndex) => itemIndex !== index))} className="rounded-md px-3 py-2 text-sm font-black text-red-600 transition hover:bg-red-50">삭제</button>
          </div>
        ))}
      </div>
    </div>
  );
}
