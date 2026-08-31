import { useEffect, useMemo, useState } from 'react';
import { CheckSquare, Download, FilePenLine, Film, Image as ImageIcon, Loader2, Square } from 'lucide-react';
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
  updateSceneSelection
} from '../api/client';
import { ProgressSteps } from '../components/ProgressSteps';
import type { Chapter, Job, LessonChapter, LessonContent, ReviewSegment, Transcript } from '../types';
import { formatTimestamp } from '../utils/format';

type Tab = 'review' | 'editor' | 'preview' | 'transcript';
type TopListField = 'learning_objectives' | 'final_summary' | 'review_questions';
type ChapterListField = 'learning_objectives' | 'key_points';

const readyStatuses = ['REVIEW_READY', 'DOCUMENT_READY', 'COMPLETED'];

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

  const selectedIds = useMemo(() => reviewSegments.filter((segment) => segment.selected).map((segment) => segment.id), [reviewSegments]);
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
      const blob = await generateEditedPdf(jobId, content);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'lecture-notes.pdf';
      link.click();
      URL.revokeObjectURL(url);
      setJob(await getJob(jobId));
    } catch {
      setErrorMessage('수정본 PDF를 생성하지 못했습니다.');
    } finally {
      setIsDownloadingPdf(false);
    }
  }

  function updateContent<K extends keyof LessonContent>(field: K, value: LessonContent[K]) {
    setContent((current) => current ? { ...current, [field]: value } : current);
  }

  function updateTopList(field: TopListField, index: number, value: string) {
    setContent((current) => {
      if (!current) return current;
      const next = [...current[field]];
      next[index] = value;
      return { ...current, [field]: next };
    });
  }

  function addTopListItem(field: TopListField) {
    setContent((current) => current ? { ...current, [field]: [...current[field], ''] } : current);
  }

  function removeTopListItem(field: TopListField, index: number) {
    setContent((current) => current ? { ...current, [field]: current[field].filter((_, itemIndex) => itemIndex !== index) } : current);
  }

  function updateChapter(index: number, patch: Partial<LessonChapter>) {
    setContent((current) => {
      if (!current) return current;
      return { ...current, chapters: current.chapters.map((chapter, chapterIndex) => chapterIndex === index ? { ...chapter, ...patch } : chapter) };
    });
  }

  function updateChapterList(chapterIndex: number, field: ChapterListField, itemIndex: number, value: string) {
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
    setContent((current) => {
      if (!current) return current;
      return {
        ...current,
        chapters: current.chapters.map((chapter, index) => index === chapterIndex ? { ...chapter, [field]: [...chapter[field], ''] } : chapter)
      };
    });
  }

  function removeChapterListItem(chapterIndex: number, field: ChapterListField, itemIndex: number) {
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
    return <main className="min-h-screen bg-slate-50 p-8 text-slate-600">결과를 불러오는 중입니다.</main>;
  }

  return (
    <main className="min-h-screen bg-slate-50 text-ink">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-4">
          <Link to="/" className="font-bold text-indigo-700">AI Video Lecture Note Generator</Link>
          <button
            type="button"
            onClick={downloadEditedPdf}
            disabled={!content || isDownloadingPdf}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-bold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {isDownloadingPdf ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            수정본 PDF 다운로드
          </button>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-5 py-8">
        <div className="mb-6 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex h-20 w-32 items-center justify-center rounded-lg bg-indigo-50 text-indigo-700">
              <Film className="h-8 w-8" />
            </div>
            <div>
              <h1 className="text-3xl font-black text-slate-950">{job.project_title}</h1>
              <p className="mt-1 text-slate-500">{reviewSegments.length || chapters.length || 0}개 장면 / {selectedIds.length}개 선택됨</p>
            </div>
          </div>
        </div>

        {!readyForReview ? <ProgressSteps job={job} /> : null}
        {errorMessage ? <p className="mb-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{errorMessage}</p> : null}

        {readyForReview ? (
          <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-wrap gap-1 border-b border-slate-200 p-2">
              {(['review', 'editor', 'preview', 'transcript'] as Tab[]).map((item) => (
                <button key={item} onClick={() => setTab(item)} className={`rounded-md px-4 py-2 text-sm font-bold ${tab === item ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>
                  {item === 'review' ? '장면 선택' : item === 'editor' ? '문서 편집' : item === 'preview' ? '미리보기' : 'Transcript'}
                </button>
              ))}
            </div>

            <div className="p-5">
              {tab === 'review' ? (
                <div>
                  <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h2 className="text-xl font-bold text-slate-950">화면 변경 기준 장면</h2>
                      <p className="mt-1 text-sm text-slate-500">각 이미지는 다음 이미지로 바뀌기 전까지의 스크립트 요약과 연결됩니다.</p>
                    </div>
                    <button
                      type="button"
                      onClick={createDraft}
                      disabled={!selectedIds.length || isGeneratingDraft}
                      className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-bold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                    >
                      {isGeneratingDraft ? <Loader2 className="h-4 w-4 animate-spin" /> : <FilePenLine className="h-4 w-4" />}
                      선택 내용으로 문서 초안 생성
                    </button>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    {reviewSegments.map((segment, index) => (
                      <article key={segment.id} className={`rounded-lg border p-4 ${segment.selected ? 'border-indigo-200 bg-indigo-50/40' : 'border-slate-200 bg-white'}`}>
                        <button type="button" onClick={() => toggleSegment(segment.id)} className="mb-3 inline-flex items-center gap-2 text-sm font-bold text-slate-800">
                          {segment.selected ? <CheckSquare className="h-5 w-5 text-indigo-600" /> : <Square className="h-5 w-5 text-slate-400" />}
                          {index + 1}. {formatTimestamp(segment.start)} - {formatTimestamp(segment.end)}
                        </button>
                        {segment.frame ? (
                          <img src={mediaUrl(segment.frame.url)} alt={segment.title} className="aspect-video w-full rounded-md border border-slate-200 object-cover" />
                        ) : (
                          <div className="flex aspect-video w-full items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-slate-400">
                            <ImageIcon className="h-8 w-8" />
                          </div>
                        )}
                        <h3 className="mt-3 text-base font-bold text-slate-950">{segment.title}</h3>
                        <p className="mt-2 text-sm leading-relaxed text-slate-600">{segment.summary}</p>
                      </article>
                    ))}
                  </div>
                </div>
              ) : null}

              {tab === 'editor' ? (
                content ? (
                  <div className="grid gap-5">
                    <EditorField label="문서 제목" value={content.title} onChange={(value) => updateContent('title', value)} />
                    <EditorTextarea label="전체 영상 개요" value={content.overview} onChange={(value) => updateContent('overview', value)} />
                    <StringListEditor title="학습 목표" items={content.learning_objectives} onChange={(index, value) => updateTopList('learning_objectives', index, value)} onAdd={() => addTopListItem('learning_objectives')} onRemove={(index) => removeTopListItem('learning_objectives', index)} />

                    <div className="grid gap-4">
                      {content.chapters.map((chapter, chapterIndex) => (
                        <section key={`${chapter.title}-${chapterIndex}`} className="rounded-lg border border-slate-200 p-4">
                          <div className="mb-4 flex items-center justify-between gap-3">
                            <h2 className="text-lg font-bold text-slate-950">장면 {chapterIndex + 1}</h2>
                            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">{chapter.timestamp}</span>
                          </div>
                          <EditorField label="제목" value={chapter.title} onChange={(value) => updateChapter(chapterIndex, { title: value })} />
                          <StringListEditor title="학습 목표" items={chapter.learning_objectives} onChange={(index, value) => updateChapterList(chapterIndex, 'learning_objectives', index, value)} onAdd={() => addChapterListItem(chapterIndex, 'learning_objectives')} onRemove={(index) => removeChapterListItem(chapterIndex, 'learning_objectives', index)} />
                          <EditorTextarea label="개념 설명" value={chapter.explanation} onChange={(value) => updateChapter(chapterIndex, { explanation: value })} />
                          <EditorTextarea label="쉽게 이해하기" value={chapter.beginner_explanation} onChange={(value) => updateChapter(chapterIndex, { beginner_explanation: value })} />
                          <StringListEditor title="핵심 포인트" items={chapter.key_points} onChange={(index, value) => updateChapterList(chapterIndex, 'key_points', index, value)} onAdd={() => addChapterListItem(chapterIndex, 'key_points')} onRemove={(index) => removeChapterListItem(chapterIndex, 'key_points', index)} />
                          <TermEditor chapter={chapter} onChange={(terms) => updateChapter(chapterIndex, { terms })} />
                          <EditorTextarea label="한 줄 정리" value={chapter.summary} onChange={(value) => updateChapter(chapterIndex, { summary: value })} />
                        </section>
                      ))}
                    </div>

                    <StringListEditor title="마지막 정리" items={content.final_summary} onChange={(index, value) => updateTopList('final_summary', index, value)} onAdd={() => addTopListItem('final_summary')} onRemove={(index) => removeTopListItem('final_summary', index)} />
                    <StringListEditor title="복습 질문" items={content.review_questions} onChange={(index, value) => updateTopList('review_questions', index, value)} onAdd={() => addTopListItem('review_questions')} onRemove={(index) => removeTopListItem('review_questions', index)} />
                    <div className="flex justify-end">
                      <button type="button" onClick={downloadEditedPdf} disabled={isDownloadingPdf} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-3 font-bold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300">
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
                  <iframe title="Document Preview" src={apiUrl(`/jobs/${jobId}/preview`)} className="h-[760px] w-full rounded-lg border border-slate-200 bg-white" />
                ) : (
                  <EmptyEditor onCreate={createDraft} disabled={!selectedIds.length || isGeneratingDraft} loading={isGeneratingDraft} />
                )
              ) : null}

              {tab === 'transcript' ? (
                <div className="grid gap-3">
                  {transcript?.segments.map((segment) => (
                    <div key={`${segment.start}-${segment.end}`} className="rounded-lg bg-slate-50 p-3">
                      <span className="font-bold text-indigo-700">{formatTimestamp(segment.start)}</span>
                      <p className="mt-1 text-slate-700">{segment.text}</p>
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
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
      <FilePenLine className="mx-auto h-10 w-10 text-indigo-600" />
      <p className="mt-3 font-bold text-slate-900">선택된 장면으로 문서 초안을 만들 수 있습니다.</p>
      <button type="button" onClick={onCreate} disabled={disabled} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-bold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300">
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FilePenLine className="h-4 w-4" />}
        문서 초안 생성
      </button>
    </div>
  );
}

function EditorField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-sm font-bold text-slate-700">{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 outline-none focus:border-indigo-500" />
    </label>
  );
}

function EditorTextarea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="mt-4 block">
      <span className="text-sm font-bold text-slate-700">{label}</span>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} className="mt-2 min-h-28 w-full rounded-lg border border-slate-200 px-3 py-2 leading-relaxed outline-none focus:border-indigo-500" />
    </label>
  );
}

function StringListEditor({
  title,
  items,
  onChange,
  onAdd,
  onRemove
}: {
  title: string;
  items: string[];
  onChange: (index: number, value: string) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}) {
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h3 className="text-sm font-bold text-slate-700">{title}</h3>
        <button type="button" onClick={onAdd} className="rounded-md bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700 hover:bg-slate-200">추가</button>
      </div>
      <div className="grid gap-2">
        {items.map((item, index) => (
          <div key={`${title}-${index}`} className="grid gap-2 sm:grid-cols-[1fr_auto]">
            <input value={item} onChange={(event) => onChange(index, event.target.value)} className="rounded-lg border border-slate-200 px-3 py-2 outline-none focus:border-indigo-500" />
            <button type="button" onClick={() => onRemove(index)} className="rounded-md px-3 py-2 text-sm font-bold text-rose-600 hover:bg-rose-50">삭제</button>
          </div>
        ))}
      </div>
    </div>
  );
}

function TermEditor({ chapter, onChange }: { chapter: LessonChapter; onChange: (terms: LessonChapter['terms']) => void }) {
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h3 className="text-sm font-bold text-slate-700">주요 용어</h3>
        <button type="button" onClick={() => onChange([...chapter.terms, { term: '', definition: '' }])} className="rounded-md bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700 hover:bg-slate-200">추가</button>
      </div>
      <div className="grid gap-2">
        {chapter.terms.map((term, index) => (
          <div key={`${term.term}-${index}`} className="grid gap-2 lg:grid-cols-[0.35fr_1fr_auto]">
            <input
              value={term.term}
              onChange={(event) => onChange(chapter.terms.map((item, itemIndex) => itemIndex === index ? { ...item, term: event.target.value } : item))}
              className="rounded-lg border border-slate-200 px-3 py-2 outline-none focus:border-indigo-500"
              placeholder="용어"
            />
            <input
              value={term.definition}
              onChange={(event) => onChange(chapter.terms.map((item, itemIndex) => itemIndex === index ? { ...item, definition: event.target.value } : item))}
              className="rounded-lg border border-slate-200 px-3 py-2 outline-none focus:border-indigo-500"
              placeholder="설명"
            />
            <button type="button" onClick={() => onChange(chapter.terms.filter((_, itemIndex) => itemIndex !== index))} className="rounded-md px-3 py-2 text-sm font-bold text-rose-600 hover:bg-rose-50">삭제</button>
          </div>
        ))}
      </div>
    </div>
  );
}
