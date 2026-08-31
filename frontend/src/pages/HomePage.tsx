import { type ReactNode, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Download,
  FileText,
  Film,
  Link as LinkIcon,
  Search,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  Wand2
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { analyzeYouTube, apiUrl, createTranscriptJob, createVideoJob, createYouTubeJob, getHealth, listJobs } from '../api/client';
import { ProgressSteps } from '../components/ProgressSteps';
import { useJobStore } from '../stores/jobs';
import { statusLabel } from '../utils/format';
import type { Job, YouTubeMetadata } from '../types';

type InputMode = 'youtube' | 'video' | 'transcript';

const DEFAULT_GENERATION_OPTIONS = {
  materialType: '강의 교재',
  difficulty: '대학생 수준',
  pdfLength: '자동'
};

export function HomePage() {
  const [mode, setMode] = useState<InputMode>('youtube');
  const [health, setHealth] = useState<string>('확인 중');
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
    getHealth().then((data) => setHealth(`${data.database} 연결됨`)).catch(() => setHealth('서버 연결 필요'));
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
                { file: transcriptFile, text: transcriptText, title: transcriptFile?.name.replace(/\.[^/.]+$/, '') || '스크립트 기반 강의자료' },
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
      setYoutubeMessage('영상 주소를 확인하지 못했습니다. 주소와 권한 체크 상태를 다시 확인해주세요.');
    } finally {
      setIsAnalyzingYoutube(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f2f0e9] text-ink">
      <section className="relative overflow-hidden bg-[#101712] text-white">
        <div className="absolute inset-0 bg-[url('/hero-lecture-workflow.png')] bg-cover bg-center opacity-80" />
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(13,20,15,0.94)_0%,rgba(13,20,15,0.78)_43%,rgba(13,20,15,0.28)_100%)]" />
        <div className="relative mx-auto grid min-h-[760px] max-w-7xl gap-10 px-5 py-8 lg:grid-cols-[0.92fr_1.08fr] lg:px-8 lg:py-10">
          <div className="flex flex-col justify-between">
            <nav className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-white/15 bg-white/10 shadow-2xl backdrop-blur">
                  <Wand2 className="h-5 w-5 text-amber-200" />
                </div>
                <div>
                  <p className="text-sm font-black tracking-normal text-white">강의자료 메이커</p>
                  <p className="text-xs font-semibold text-white/55">영상에서 PDF까지</p>
                </div>
              </div>
              <span className="rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-xs font-bold text-emerald-100 backdrop-blur">
                {health}
              </span>
            </nav>

            <div className="max-w-2xl pb-10 pt-16 lg:pb-20">
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/30 bg-emerald-300/10 px-4 py-2 text-sm font-bold text-emerald-100 shadow-2xl backdrop-blur">
                <Sparkles className="h-4 w-4" />
                장면, 요약, 편집본을 한 번에
              </span>
              <h1 className="mt-7 break-keep text-4xl font-black leading-[1.12] tracking-normal text-white sm:text-6xl xl:text-7xl">
                영상을 교재로 바꿉니다
              </h1>
              <p className="mt-6 max-w-xl break-keep text-lg font-medium leading-8 text-stone-100/85">
                유튜브, 영상 파일, 스크립트를 넣으면 화면 전환 장면을 추출하고 자연스러운 한국어 요약과 편집 가능한 PDF 초안을 만듭니다.
              </p>
              <div className="mt-8 grid gap-3 sm:grid-cols-3">
                <Metric label="장면 검토" value="자동 추출" />
                <Metric label="문장 보정" value="요약 정리" />
                <Metric label="출력 형식" value="PDF" />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-center lg:justify-end">
            <div className="w-full max-w-[620px] rounded-lg border border-white/18 bg-white/92 p-4 text-slate-950 shadow-[0_30px_90px_rgba(0,0,0,0.45)] backdrop-blur-xl sm:p-5">
              <div className="rounded-lg border border-stone-200 bg-[#fbfaf6] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)] sm:p-5">
                <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-black text-emerald-700">새 강의자료 만들기</p>
                    <h2 className="mt-1 text-2xl font-black tracking-normal text-slate-950">자료 입력</h2>
                  </div>
                  <span className="rounded-full bg-amber-100 px-3 py-1.5 text-xs font-black text-amber-800">기본값 적용</span>
                </div>

                <div className="grid grid-cols-3 gap-2 rounded-lg border border-stone-200 bg-stone-100 p-1">
                  <ModeButton active={mode === 'youtube'} label="주소" icon={<LinkIcon />} onClick={() => setMode('youtube')} />
                  <ModeButton active={mode === 'video'} label="파일" icon={<Film />} onClick={() => setMode('video')} />
                  <ModeButton active={mode === 'transcript'} label="대본" icon={<FileText />} onClick={() => setMode('transcript')} />
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
                    <VideoPanel file={file} isDragging={isDragging} onFileChange={setFile} onDraggingChange={setIsDragging} />
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

                <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                  <p className="flex items-center gap-2 text-sm font-black text-emerald-900">
                    <ShieldCheck className="h-4 w-4" />
                    생성 설정
                  </p>
                  <p className="mt-2 text-sm leading-6 text-emerald-950/80">
                    강의 교재, 대학생 수준, 자동 분량으로 생성합니다. 핵심 장면, 용어 정리, 마지막 요약, 시간 표시, 출처, 학습 목표, 복습 질문을 포함합니다.
                  </p>
                </div>

                <button
                  onClick={startJob}
                  disabled={!canStart}
                  className="mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#145947] px-5 py-3 font-black text-white shadow-[0_16px_35px_rgba(20,89,71,0.28)] transition hover:-translate-y-0.5 hover:bg-[#0f4639] disabled:cursor-not-allowed disabled:bg-stone-300 disabled:text-stone-500 disabled:shadow-none"
                >
                  <Wand2 className="h-5 w-5" />
                  {isUploading ? '작업 생성 중' : '강의자료 생성 시작'}
                  {!isUploading ? <ArrowRight className="h-5 w-5" /> : null}
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-5 py-10 lg:grid-cols-[0.95fr_1.05fr] lg:px-8">
        {activeJob ? <ProgressSteps job={activeJob} /> : <WorkflowPreview />}
        <RecentJobs jobs={recentJobs} onOpen={(jobId) => navigate(`/results/${jobId}`)} />
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/12 bg-white/10 px-4 py-3 shadow-2xl backdrop-blur">
      <p className="text-xs font-bold text-stone-200/70">{label}</p>
      <p className="mt-1 text-lg font-black text-white">{value}</p>
    </div>
  );
}

function ModeButton({ active, label, icon, onClick }: { active: boolean; label: string; icon: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex min-h-11 items-center justify-center gap-1.5 rounded-md px-2 py-2 text-xs font-black transition sm:gap-2 sm:px-3 sm:text-sm ${
        active ? 'bg-white text-[#145947] shadow-sm' : 'text-slate-500 hover:bg-white/60 hover:text-slate-900'
      }`}
    >
      <span className="[&>svg]:h-4 [&>svg]:w-4">{icon}</span>
      <span>{label}</span>
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
    <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
      <label className="text-sm font-black text-slate-700">유튜브 영상 주소</label>
      <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_auto]">
        <input
          value={url}
          onChange={(event) => onUrlChange(event.target.value)}
          className="min-h-11 min-w-0 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 outline-none transition focus:border-emerald-600 focus:bg-white"
          placeholder="https://www.youtube.com/watch?v=..."
        />
        <button
          type="button"
          onClick={onAnalyze}
          disabled={!url.trim() || !hasRights || isAnalyzing}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-slate-950 px-4 py-2 text-sm font-black text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-stone-200 disabled:text-stone-500"
        >
          <Search className="h-4 w-4" />
          {isAnalyzing ? '확인 중' : '영상 확인'}
        </button>
      </div>
      <label className="mt-3 flex items-start gap-2 text-sm leading-6 text-slate-700">
        <input
          type="checkbox"
          checked={hasRights}
          onChange={(event) => onRightsChange(event.target.checked)}
          className="mt-1 h-4 w-4 rounded border-stone-300 text-emerald-700"
        />
        이 영상을 분석하고 강의자료를 만들 권한이 있습니다.
      </label>
      {message ? (
        <p className="mt-3 flex items-center gap-2 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {message}
        </p>
      ) : null}
      {metadata ? (
        <div className="mt-4 grid gap-4 rounded-lg border border-stone-100 bg-[#fbfaf6] p-3 sm:grid-cols-[132px_1fr]">
          <img src={metadata.thumbnail} alt={metadata.title} className="aspect-video w-full rounded-md object-cover shadow-md" />
          <div>
            <p className="flex items-center gap-2 text-sm font-black text-emerald-700">
              <CheckCircle2 className="h-4 w-4" />
              영상 확인 완료
            </p>
            <h3 className="mt-1 font-black leading-snug text-slate-950">{metadata.title}</h3>
            <p className="mt-1 text-sm text-slate-500">{metadata.channel}</p>
            <p className="mt-2 text-xs leading-5 text-slate-500">{metadata.policyNote}</p>
          </div>
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-slate-500">
          주소와 권한 확인만으로 시작할 수 있습니다. 공개 자막이 있으면 자막 기반으로, 제한이 있으면 로컬 검증 흐름으로 진행합니다.
        </p>
      )}
    </div>
  );
}

function VideoPanel({
  file,
  isDragging,
  onFileChange,
  onDraggingChange
}: {
  file: File | null;
  isDragging: boolean;
  onFileChange: (file: File | null) => void;
  onDraggingChange: (dragging: boolean) => void;
}) {
  return (
    <div
      className={`flex min-h-56 flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition ${
        isDragging ? 'border-emerald-600 bg-emerald-50' : 'border-stone-200 bg-white'
      }`}
      onDragOver={(event) => {
        event.preventDefault();
        onDraggingChange(true);
      }}
      onDragLeave={() => onDraggingChange(false)}
      onDrop={(event) => {
        event.preventDefault();
        onDraggingChange(false);
        onFileChange(event.dataTransfer.files?.[0] ?? null);
      }}
    >
      <UploadCloud className="mb-3 h-10 w-10 text-[#145947]" />
      <p className="font-black text-slate-900">영상 파일을 끌어오세요</p>
      <p className="mb-4 text-sm text-slate-500">mp4, mov, mkv, webm 형식을 지원합니다.</p>
      <label className="inline-flex min-h-10 cursor-pointer items-center rounded-lg bg-slate-950 px-4 py-2 text-sm font-black text-white shadow-sm transition hover:bg-slate-800">
        파일 선택
        <input className="hidden" type="file" accept=".mp4,.mov,.mkv,.webm" onChange={(event) => onFileChange(event.target.files?.[0] ?? null)} />
      </label>
      {file ? <p className="mt-3 max-w-full break-words text-sm font-bold text-emerald-700">{file.name}</p> : null}
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
    <div className="rounded-lg border border-stone-200 bg-white p-4 shadow-sm">
      <label className="text-sm font-black text-slate-700">스크립트 파일</label>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <label className="inline-flex min-h-10 cursor-pointer items-center rounded-lg bg-slate-950 px-4 py-2 text-sm font-black text-white shadow-sm transition hover:bg-slate-800">
          파일 선택
          <input className="hidden" type="file" accept=".txt,.srt,.vtt" onChange={(event) => onFileChange(event.target.files?.[0] ?? null)} />
        </label>
        {file ? <span className="max-w-full break-words text-sm font-bold text-emerald-700">{file.name}</span> : <span className="text-sm text-slate-500">txt, srt, vtt 지원</span>}
      </div>
      <textarea
        value={text}
        onChange={(event) => onTextChange(event.target.value)}
        className="mt-3 min-h-40 w-full rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 leading-6 outline-none transition focus:border-emerald-600 focus:bg-white"
        placeholder="스크립트를 직접 붙여넣어도 됩니다."
      />
      <p className="mt-3 text-sm leading-6 text-slate-500">시간 정보가 있는 SRT/VTT는 시간을 유지하고, 일반 텍스트는 자동으로 구간을 나눕니다.</p>
    </div>
  );
}

function WorkflowPreview() {
  const items = [
    ['1', '장면 추출', '화면 전환을 기준으로 핵심 이미지를 고릅니다.'],
    ['2', '문장 정리', '겹친 자막과 어색한 표현을 자연스럽게 다듬습니다.'],
    ['3', '교재 생성', '선택한 장면으로 편집 가능한 PDF 초안을 만듭니다.']
  ];
  return (
    <div className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-black text-emerald-700">작업 흐름</p>
      <h2 className="mt-1 text-xl font-black text-slate-950">영상에서 교재까지</h2>
      <div className="mt-5 grid gap-3">
        {items.map(([step, title, body]) => (
          <div key={step} className="grid grid-cols-[44px_1fr] gap-3 rounded-lg border border-stone-100 bg-[#fbfaf6] p-4">
            <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#145947] text-sm font-black text-white">{step}</span>
            <div>
              <p className="font-black text-slate-900">{title}</p>
              <p className="mt-1 text-sm leading-6 text-slate-500">{body}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RecentJobs({ jobs, onOpen }: { jobs: Job[]; onOpen: (jobId: string) => void }) {
  return (
    <div className="rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
      <h2 className="mb-4 text-xl font-black text-slate-950">최근 작업</h2>
      <div className="grid gap-3">
        {jobs.length ? jobs.map((job) => (
          <article key={job.id} className="rounded-lg border border-stone-100 bg-[#fbfaf6] p-4 transition hover:border-emerald-200 hover:bg-emerald-50/40">
            <div className="flex items-center justify-between gap-3">
              <strong className="min-w-0 break-words text-slate-900">{job.project_title}</strong>
              <span className="shrink-0 text-sm font-black text-emerald-700">{statusLabel(job.status)}</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-stone-200">
              <div className="h-full rounded-full bg-[#145947] transition-all" style={{ width: `${job.progress}%` }} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => onOpen(job.id)}
                className="rounded-md bg-white px-3 py-2 text-sm font-black text-[#145947] shadow-sm ring-1 ring-emerald-100 transition hover:bg-emerald-50"
              >
                결과 보기
              </button>
              {job.status === 'COMPLETED' ? (
                <a
                  href={apiUrl(`/jobs/${job.id}/pdf`)}
                  className="inline-flex items-center gap-2 rounded-md bg-[#145947] px-3 py-2 text-sm font-black text-white shadow-sm transition hover:bg-[#0f4639]"
                >
                  <Download className="h-4 w-4" />
                  PDF 다운로드
                </a>
              ) : null}
            </div>
          </article>
        )) : <p className="text-sm text-slate-500">아직 생성한 자료가 없습니다.</p>}
      </div>
    </div>
  );
}
