import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, Download, FileText, Film, Link as LinkIcon, Search, UploadCloud, Wand2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { analyzeYouTube, apiUrl, createTranscriptJob, createVideoJob, createYouTubeJob, getHealth, listJobs } from '../api/client';
import { ProgressSteps } from '../components/ProgressSteps';
import { useJobStore } from '../stores/jobs';
import { statusLabel } from '../utils/format';
import type { YouTubeMetadata } from '../types';

type InputMode = 'youtube' | 'video' | 'transcript';

const DEFAULT_GENERATION_OPTIONS = {
  materialType: 'Detailed Lecture',
  difficulty: '대학생 수준',
  pdfLength: 'Auto'
};

export function HomePage() {
  const [mode, setMode] = useState<InputMode>('youtube');
  const [health, setHealth] = useState<string>('checking');
  const [file, setFile] = useState<File | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState('https://youtu.be/JKj7eTi0Axo?si=AJrOgnxr5x_fSOlP');
  const [youtubeHasRights, setYoutubeHasRights] = useState(true);
  const [youtubeMetadata, setYoutubeMetadata] = useState<YouTubeMetadata | null>(null);
  const [youtubeMessage, setYoutubeMessage] = useState<string>('');
  const [isAnalyzingYoutube, setIsAnalyzingYoutube] = useState(false);
  const [transcriptText, setTranscriptText] = useState('');
  const [transcriptFile, setTranscriptFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const { activeJob, recentJobs, setActiveJob, setRecentJobs } = useJobStore();
  const navigate = useNavigate();

  useEffect(() => {
    getHealth().then((data) => setHealth(`${data.app_name} / ${data.database}`)).catch(() => setHealth('backend offline'));
    listJobs().then(setRecentJobs).catch(() => undefined);
  }, [setRecentJobs]);

  useEffect(() => {
    if (!activeJob || ['REVIEW_READY', 'DOCUMENT_READY', 'COMPLETED', 'FAILED'].includes(activeJob.status)) return;
    const id = window.setInterval(async () => {
      const jobs = await listJobs();
      setRecentJobs(jobs);
      const current = jobs.find((job) => job.id === activeJob.id);
      if (current) {
        setActiveJob(current);
        if (['REVIEW_READY', 'DOCUMENT_READY', 'COMPLETED'].includes(current.status)) navigate(`/results/${current.id}`);
      }
    }, 1800);
    return () => window.clearInterval(id);
  }, [activeJob, navigate, setActiveJob, setRecentJobs]);

  const canStart = useMemo(() => {
    if (isUploading) return false;
    if (mode === 'video') return Boolean(file);
    if (mode === 'youtube') return Boolean(youtubeUrl.trim()) && youtubeHasRights;
    if (mode === 'transcript') return Boolean(transcriptFile || transcriptText.trim());
    return false;
  }, [file, isUploading, mode, transcriptFile, transcriptText, youtubeHasRights, youtubeUrl]);

  async function startJob() {
    setIsUploading(true);
    try {
      const job =
        mode === 'youtube'
          ? await createYouTubeJob(youtubeUrl, { ...DEFAULT_GENERATION_OPTIONS, hasRights: youtubeHasRights })
          : mode === 'transcript'
            ? await createTranscriptJob(
                { file: transcriptFile, text: transcriptText, title: transcriptFile?.name.replace(/\.[^/.]+$/, '') || 'Transcript Lecture Notes' },
                DEFAULT_GENERATION_OPTIONS
              )
          : file
            ? await createVideoJob(file, DEFAULT_GENERATION_OPTIONS)
            : null;
      if (!job) return;
      setActiveJob(job);
    } finally {
      setIsUploading(false);
    }
  }

  async function confirmYouTube() {
    setYoutubeMessage('');
    setIsAnalyzingYoutube(true);
    try {
      const metadata = await analyzeYouTube(youtubeUrl, youtubeHasRights);
      setYoutubeMetadata(metadata);
    } catch {
      setYoutubeMetadata(null);
      setYoutubeMessage('YouTube URL을 확인하지 못했습니다. 주소와 권한 체크를 확인해주세요.');
    } finally {
      setIsAnalyzingYoutube(false);
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-sky-50 via-white to-indigo-50 text-ink">
      <section className="mx-auto grid max-w-6xl gap-8 px-5 py-10 lg:grid-cols-[1.05fr_0.95fr] lg:py-14">
        <div className="flex flex-col justify-center">
          <span className="mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-indigo-100 bg-white px-4 py-2 text-sm font-semibold text-indigo-700 shadow-sm">
            <Wand2 className="h-4 w-4" /> AI education workflow
          </span>
          <h1 className="max-w-3xl text-4xl font-black leading-tight tracking-normal text-slate-950 sm:text-6xl">
            AI Video Lecture Note Generator
          </h1>
          <p className="mt-5 max-w-2xl text-xl font-semibold text-slate-700">Turn videos into structured learning materials.</p>
          <p className="mt-4 max-w-2xl text-lg text-slate-600">
            영상 하나로 핵심 내용, 중요한 화면, 설명, PDF를 자동 생성합니다.
          </p>
          <div className="mt-6 rounded-lg border border-blue-100 bg-white/80 p-4 text-sm text-slate-600 shadow-sm">
            업로드하거나 분석하는 콘텐츠를 사용할 적절한 권한이 있는지 확인해주세요. 생성된 자료를 공개 또는 배포하는 경우 원본 콘텐츠의 저작권 및 플랫폼 이용조건을 확인해야 합니다.
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-xl shadow-indigo-100/60">
          <div className="mb-5 flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-indigo-700">영상 입력 방법</p>
              <h2 className="text-2xl font-bold text-slate-950">Generate lecture notes</h2>
            </div>
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">{health}</span>
          </div>

          <div className="grid grid-cols-3 gap-2 rounded-lg bg-slate-100 p-1">
            <ModeButton active={mode === 'youtube'} label="YouTube URL" icon={<LinkIcon />} onClick={() => setMode('youtube')} />
            <ModeButton active={mode === 'video'} label="Video Upload" icon={<Film />} onClick={() => setMode('video')} />
            <ModeButton active={mode === 'transcript'} label="Transcript" icon={<FileText />} onClick={() => setMode('transcript')} />
          </div>

          <div className="mt-5">
            {mode === 'youtube' ? (
              <YouTubePanel
                url={youtubeUrl}
                hasRights={youtubeHasRights}
                metadata={youtubeMetadata}
                message={youtubeMessage}
                isAnalyzing={isAnalyzingYoutube}
                onUrlChange={(nextUrl) => {
                  setYoutubeUrl(nextUrl);
                  setYoutubeMetadata(null);
                }}
                onRightsChange={setYoutubeHasRights}
                onAnalyze={confirmYouTube}
              />
            ) : null}
            {mode === 'video' ? (
              <div>
                <div
                  className={`flex min-h-48 flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition ${
                    isDragging ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200 bg-slate-50'
                  }`}
                  onDragOver={(event) => {
                    event.preventDefault();
                    setIsDragging(true);
                  }}
                  onDragLeave={() => setIsDragging(false)}
                  onDrop={(event) => {
                    event.preventDefault();
                    setIsDragging(false);
                    setFile(event.dataTransfer.files?.[0] ?? null);
                  }}
                >
                  <UploadCloud className="mb-3 h-9 w-9 text-indigo-600" />
                  <p className="font-semibold text-slate-900">Drag & Drop</p>
                  <p className="mb-4 text-sm text-slate-500">mp4, mov, mkv, webm</p>
                  <label className="inline-flex cursor-pointer items-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-indigo-700">
                    파일 선택
                    <input className="hidden" type="file" accept=".mp4,.mov,.mkv,.webm" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
                  </label>
                  {file ? <p className="mt-3 text-sm font-medium text-indigo-700">{file.name}</p> : null}
                </div>
              </div>
            ) : null}
            {mode === 'transcript' ? (
              <TranscriptPanel
                text={transcriptText}
                file={transcriptFile}
                onTextChange={setTranscriptText}
                onFileChange={setTranscriptFile}
              />
            ) : null}
          </div>

          <div className="mt-5 rounded-lg border border-emerald-100 bg-emerald-50 p-4">
            <p className="flex items-center gap-2 text-sm font-bold text-emerald-800">
              <CheckCircle2 className="h-4 w-4" /> 기본 생성 설정 적용
            </p>
            <p className="mt-2 text-sm leading-relaxed text-emerald-900">
              유튜브 내용에 대한 강의 교재, 대학생 수준, 내용에 따른 자동 길이로 생성합니다. 핵심 장면, 용어 정리, 마지막 요약, Timestamp, 출처, 학습 목표, 복습 문제는 자동 포함됩니다.
            </p>
          </div>

          <button
            onClick={startJob}
            disabled={!canStart}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-5 py-3 font-bold text-white shadow-lg shadow-indigo-200 hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
          >
            <Wand2 className="h-5 w-5" /> {isUploading ? '작업 생성 중' : '강의자료 생성 시작'}
          </button>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-5 pb-12 lg:grid-cols-[1fr_1fr]">
        {activeJob ? <ProgressSteps job={activeJob} /> : null}
        <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 text-xl font-bold text-slate-950">최근 작업</h2>
          <div className="grid gap-3">
            {recentJobs.length ? recentJobs.map((job) => (
              <article key={job.id} className="rounded-lg border border-slate-100 p-4 hover:border-indigo-200 hover:bg-indigo-50">
                <div className="flex items-center justify-between gap-3">
                  <strong className="text-slate-900">{job.project_title}</strong>
                  <span className="text-sm font-semibold text-indigo-700">{statusLabel(job.status)}</span>
                </div>
                <div className="mt-2 h-1.5 rounded-full bg-slate-100"><div className="h-full rounded-full bg-indigo-600" style={{ width: `${job.progress}%` }} /></div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => navigate(`/results/${job.id}`)}
                    className="rounded-md bg-white px-3 py-2 text-sm font-bold text-indigo-700 shadow-sm ring-1 ring-indigo-100 hover:bg-indigo-50"
                  >
                    결과 보기
                  </button>
                  {job.status === 'COMPLETED' ? (
                    <a
                      href={apiUrl(`/jobs/${job.id}/pdf`)}
                      className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-3 py-2 text-sm font-bold text-white shadow-sm hover:bg-indigo-700"
                    >
                      <Download className="h-4 w-4" /> PDF 다운로드
                    </a>
                  ) : null}
                </div>
              </article>
            )) : <p className="text-sm text-slate-500">아직 생성한 자료가 없습니다.</p>}
          </div>
        </div>
      </section>
    </main>
  );
}

function ModeButton({ active, label, icon, onClick }: { active: boolean; label: string; icon: ReactNode; onClick: () => void }) {
  return (
    <button onClick={onClick} className={`flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-bold ${active ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-500 hover:text-slate-900'}`}>
      <span className="[&>svg]:h-4 [&>svg]:w-4">{icon}</span>
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

function YouTubePanel({
  url,
  hasRights,
  metadata,
  message,
  isAnalyzing,
  onUrlChange,
  onRightsChange,
  onAnalyze
}: {
  url: string;
  hasRights: boolean;
  metadata: YouTubeMetadata | null;
  message: string;
  isAnalyzing: boolean;
  onUrlChange: (value: string) => void;
  onRightsChange: (value: boolean) => void;
  onAnalyze: () => void;
}) {
  return (
    <div className="rounded-lg border border-indigo-100 bg-indigo-50 p-4">
      <label className="text-sm font-semibold text-slate-700">YouTube URL</label>
      <div className="mt-2 flex gap-2">
        <input
          value={url}
          onChange={(event) => onUrlChange(event.target.value)}
          className="min-w-0 flex-1 rounded-lg border border-indigo-100 px-3 py-2 outline-none focus:border-indigo-500"
          placeholder="https://www.youtube.com/watch?v=..."
        />
        <button
          type="button"
          onClick={onAnalyze}
          disabled={!url.trim() || !hasRights || isAnalyzing}
          className="inline-flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-bold text-indigo-700 shadow-sm ring-1 ring-indigo-100 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:text-slate-400"
        >
          <Search className="h-4 w-4" /> {isAnalyzing ? '확인 중' : '영상 확인'}
        </button>
      </div>
      <label className="mt-3 flex items-start gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={hasRights}
          onChange={(event) => onRightsChange(event.target.checked)}
          className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600"
        />
        본 영상의 분석 및 자료 생성에 필요한 권한을 가지고 있습니다.
      </label>
      {message ? (
        <p className="mt-3 flex items-center gap-2 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">
          <AlertCircle className="h-4 w-4" /> {message}
        </p>
      ) : null}
      {metadata ? (
        <div className="mt-4 grid gap-4 rounded-lg bg-white p-3 shadow-sm sm:grid-cols-[132px_1fr]">
          <img src={metadata.thumbnail} alt={metadata.title} className="aspect-video w-full rounded-md object-cover" />
          <div>
            <p className="flex items-center gap-2 text-sm font-bold text-emerald-700"><CheckCircle2 className="h-4 w-4" /> 영상 확인 완료</p>
            <h3 className="mt-1 font-bold text-slate-950">{metadata.title}</h3>
            <p className="mt-1 text-sm text-slate-500">{metadata.channel}</p>
            <p className="mt-2 text-xs leading-relaxed text-slate-500">{metadata.policyNote}</p>
          </div>
        </div>
      ) : (
        <p className="mt-3 text-sm text-indigo-900">
          기본값은 유튜브 내용에 대한 강의 교재, 대학생 수준, PDF 길이 Auto입니다. 영상 확인 없이도 권한 체크와 URL이 있으면 Mock 기반 생성 흐름을 시작할 수 있습니다.
        </p>
      )}
    </div>
  );
}

function TranscriptPanel({
  text,
  file,
  onTextChange,
  onFileChange
}: {
  text: string;
  file: File | null;
  onTextChange: (value: string) => void;
  onFileChange: (file: File | null) => void;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <label className="text-sm font-semibold text-slate-700">Transcript Upload</label>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <label className="inline-flex cursor-pointer items-center rounded-lg bg-white px-4 py-2 text-sm font-bold text-indigo-700 shadow-sm ring-1 ring-slate-200 hover:bg-indigo-50">
          파일 선택
          <input className="hidden" type="file" accept=".txt,.srt,.vtt" onChange={(event) => onFileChange(event.target.files?.[0] ?? null)} />
        </label>
        {file ? <span className="text-sm font-semibold text-indigo-700">{file.name}</span> : <span className="text-sm text-slate-500">txt, srt, vtt 지원</span>}
      </div>
      <textarea
        value={text}
        onChange={(event) => onTextChange(event.target.value)}
        className="mt-3 min-h-36 w-full rounded-lg border border-slate-200 px-3 py-2 outline-none focus:border-indigo-500"
        placeholder="Transcript를 직접 붙여넣어도 됩니다."
      />
      <p className="mt-3 text-sm text-slate-500">Timestamp가 있는 SRT/VTT는 시간을 유지하고, 일반 텍스트는 자동으로 시간 구간을 만들어 강의자료로 변환합니다.</p>
    </div>
  );
}
