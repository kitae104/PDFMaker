import { type ReactNode, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  Car,
  CheckCircle2,
  Download,
  FileText,
  Film,
  Gauge,
  Link as LinkIcon,
  Search,
  ShieldCheck,
  UploadCloud,
  Wand2,
  Wrench
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { analyzeYouTube, apiUrl, createTranscriptJob, createVideoJob, createYouTubeJob, getHealth, listJobs } from '../api/client';
import { ProgressSteps } from '../components/ProgressSteps';
import { useJobStore } from '../stores/jobs';
import { statusLabel } from '../utils/format';
import type { Job, YouTubeMetadata } from '../types';

type InputMode = 'youtube' | 'video' | 'transcript';

const DEFAULT_GENERATION_OPTIONS = {
  materialType: '자동차 학과 강의 교재',
  difficulty: '대학생 수준',
  pdfLength: '자동'
};

export function HomePage() {
  const [mode, setMode] = useState<InputMode>('youtube');
  const [health, setHealth] = useState<string>('점검 중');
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
                { file: transcriptFile, text: transcriptText, title: transcriptFile?.name.replace(/\.[^/.]+$/, '') || '자동차 강의 스크립트' },
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
    <main className="app-carbon min-h-screen text-[#f8faf2]">
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('/hero-lecture-workflow.png')] bg-cover bg-center opacity-40" />
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(7,9,10,0.98)_0%,rgba(7,9,10,0.82)_46%,rgba(7,9,10,0.38)_100%)]" />
        <div className="absolute inset-x-0 bottom-0 h-40 bg-[linear-gradient(180deg,transparent,rgba(7,9,10,0.98))]" />

        <div className="relative mx-auto grid min-h-[760px] max-w-7xl gap-8 px-5 py-6 lg:grid-cols-[0.88fr_1.12fr] lg:px-8 lg:py-8">
          <div className="flex flex-col justify-between">
            <nav className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-lime-300/25 bg-white/10 shadow-[0_18px_35px_rgba(0,0,0,0.35),inset_0_1px_0_rgba(255,255,255,0.16)] backdrop-blur">
                  <Car className="h-6 w-6 text-lime-200" />
                </div>
                <div>
                  <p className="text-sm font-black tracking-normal text-white">AUTO PDF LAB</p>
                  <p className="text-xs font-bold text-white/55">영상 분석에서 교재 출고까지</p>
                </div>
              </div>
              <span className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1.5 text-xs font-black text-cyan-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.12)] backdrop-blur">
                {health}
              </span>
            </nav>

            <div className="max-w-2xl pb-8 pt-14 lg:pb-16">
              <span className="inline-flex items-center gap-2 rounded-full border border-lime-300/25 bg-lime-300/10 px-4 py-2 text-sm font-black text-lime-100 shadow-[0_14px_30px_rgba(0,0,0,0.28)] backdrop-blur">
                <Gauge className="h-4 w-4" />
                자동차 학과용 강의자료 튜닝룸
              </span>
              <h1 className="mt-7 break-keep text-4xl font-black leading-[1.06] tracking-normal text-white sm:text-6xl xl:text-7xl">
                영상을 PDF 교재로<br className="hidden sm:block" /> 정밀하게 튜닝합니다
              </h1>
              <p className="mt-6 max-w-xl break-keep text-lg font-medium leading-8 text-zinc-200/86">
                정비 실습, 구조 해설, 주행 원리 영상을 넣으면 핵심 장면을 추출하고 편집 가능한 강의 PDF 초안으로 정리합니다.
              </p>
              <div className="mt-8 grid gap-3 sm:grid-cols-3">
                <Metric icon={<Film />} label="INPUT" value="영상/대본" />
                <Metric icon={<Wrench />} label="TUNE" value="장면 편집" />
                <Metric icon={<FileText />} label="OUTPUT" value="PDF 출고" />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-center lg:justify-end">
            <div className="glass-panel speed-line w-full max-w-[640px] rounded-lg p-3 sm:p-4">
              <div className="ivory-panel rounded-lg p-4 sm:p-5">
                <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-black text-[#517500]">🏁 새 교재 제작</p>
                    <h2 className="mt-1 text-2xl font-black tracking-normal text-[#101416]">소스 입력</h2>
                  </div>
                  <span className="rounded-full border border-[#c7db48] bg-[#edff9f] px-3 py-1.5 text-xs font-black text-[#425700] shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
                    자동차 교재 기본값
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 rounded-lg border border-black/10 bg-[#dfe5dc] p-1 shadow-[inset_0_2px_5px_rgba(7,9,10,0.08)]">
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

                <div className="mt-5 rounded-lg border border-[#cde85a] bg-[#f4ffd0] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.85),0_12px_24px_rgba(115,151,18,0.12)]">
                  <p className="flex items-center gap-2 text-sm font-black text-[#243300]">
                    <ShieldCheck className="h-4 w-4" />
                    생성 설정
                  </p>
                  <p className="mt-2 text-sm leading-6 text-[#243300]/80">
                    자동차 학과 강의 교재, 대학생 수준, 자동 분량으로 생성합니다. 핵심 장면, 용어 정리, 시간 표시, 출처, 학습 목표, 복습 질문을 포함합니다.
                  </p>
                </div>

                <button
                  onClick={startJob}
                  disabled={!canStart}
                  className="drive-button mt-5 flex min-h-12 w-full items-center justify-center gap-2 rounded-lg px-5 py-3 font-black transition"
                >
                  <Wand2 className="h-5 w-5" />
                  {isUploading ? '작업 생성 중' : '교재 생성 엔진 시동'}
                  {!isUploading ? <ArrowRight className="h-5 w-5" /> : null}
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-6 px-5 pb-12 pt-4 lg:grid-cols-[0.95fr_1.05fr] lg:px-8">
        {activeJob ? <ProgressSteps job={activeJob} /> : <WorkflowPreview />}
        <RecentJobs jobs={recentJobs} onOpen={(jobId) => navigate(`/results/${jobId}`)} />
      </section>
    </main>
  );
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="metal-card rounded-lg px-4 py-3">
      <p className="flex items-center gap-2 text-xs font-black text-cyan-100/70">
        <span className="[&>svg]:h-4 [&>svg]:w-4">{icon}</span>
        {label}
      </p>
      <p className="mt-2 text-lg font-black text-white">{value}</p>
    </div>
  );
}

function ModeButton({ active, label, icon, onClick }: { active: boolean; label: string; icon: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex min-h-11 items-center justify-center gap-1.5 rounded-md px-2 py-2 text-xs font-black transition sm:gap-2 sm:px-3 sm:text-sm ${
        active ? 'bg-[#101416] text-lime-200 shadow-[0_10px_18px_rgba(0,0,0,0.24),inset_0_1px_0_rgba(255,255,255,0.14)]' : 'text-zinc-600 hover:bg-white/70 hover:text-[#101416]'
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
    <div className="light-card rounded-lg p-4">
      <label className="text-sm font-black text-zinc-700">유튜브 영상 주소</label>
      <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_auto]">
        <input
          value={url}
          onChange={(event) => onUrlChange(event.target.value)}
          className="race-field min-h-11 min-w-0 rounded-lg px-3 py-2 text-[#101416] outline-none transition"
          placeholder="https://www.youtube.com/watch?v=..."
        />
        <button
          type="button"
          onClick={onAnalyze}
          disabled={!url.trim() || !hasRights || isAnalyzing}
          className="pit-button inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-black transition disabled:cursor-not-allowed disabled:opacity-55"
        >
          <Search className="h-4 w-4" />
          {isAnalyzing ? '확인 중' : '영상 확인'}
        </button>
      </div>
      <label className="mt-3 flex items-start gap-2 text-sm leading-6 text-zinc-700">
        <input
          type="checkbox"
          checked={hasRights}
          onChange={(event) => onRightsChange(event.target.checked)}
          className="mt-1 h-4 w-4 rounded border-zinc-300 accent-[#8ed11b]"
        />
        이 영상을 분석하고 강의자료를 만들 권한이 있습니다.
      </label>
      {message ? (
        <p className="mt-3 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {message}
        </p>
      ) : null}
      {metadata ? (
        <div className="mt-4 grid gap-4 rounded-lg border border-black/10 bg-[#f5f7ef] p-3 shadow-[0_12px_24px_rgba(0,0,0,0.1)] sm:grid-cols-[132px_1fr]">
          <img src={metadata.thumbnail} alt={metadata.title} className="aspect-video w-full rounded-md object-cover shadow-[0_12px_22px_rgba(0,0,0,0.2)]" />
          <div>
            <p className="flex items-center gap-2 text-sm font-black text-[#517500]">
              <CheckCircle2 className="h-4 w-4" />
              영상 확인 완료
            </p>
            <h3 className="mt-1 font-black leading-snug text-[#101416]">{metadata.title}</h3>
            <p className="mt-1 text-sm text-zinc-500">{metadata.channel}</p>
            <p className="mt-2 text-xs leading-5 text-zinc-500">{metadata.policyNote}</p>
          </div>
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-zinc-500">
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
        isDragging ? 'border-lime-400 bg-lime-50 shadow-[0_18px_36px_rgba(120,178,13,0.18)]' : 'light-card border-zinc-200'
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
      <UploadCloud className="mb-3 h-10 w-10 text-[#6e9e00]" />
      <p className="font-black text-[#101416]">영상 파일을 정비 베이에 올려주세요</p>
      <p className="mb-4 text-sm text-zinc-500">mp4, mov, mkv, webm 형식을 지원합니다.</p>
      <label className="pit-button inline-flex min-h-10 cursor-pointer items-center rounded-lg px-4 py-2 text-sm font-black transition">
        파일 선택
        <input className="hidden" type="file" accept=".mp4,.mov,.mkv,.webm" onChange={(event) => onFileChange(event.target.files?.[0] ?? null)} />
      </label>
      {file ? <p className="mt-3 max-w-full break-words text-sm font-black text-[#517500]">{file.name}</p> : null}
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
    <div className="light-card rounded-lg p-4">
      <label className="text-sm font-black text-zinc-700">스크립트 파일</label>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <label className="pit-button inline-flex min-h-10 cursor-pointer items-center rounded-lg px-4 py-2 text-sm font-black transition">
          파일 선택
          <input className="hidden" type="file" accept=".txt,.srt,.vtt" onChange={(event) => onFileChange(event.target.files?.[0] ?? null)} />
        </label>
        {file ? <span className="max-w-full break-words text-sm font-black text-[#517500]">{file.name}</span> : <span className="text-sm text-zinc-500">txt, srt, vtt 지원</span>}
      </div>
      <textarea
        value={text}
        onChange={(event) => onTextChange(event.target.value)}
        className="race-field mt-3 min-h-40 w-full rounded-lg px-3 py-2 leading-6 text-[#101416] outline-none transition"
        placeholder="스크립트를 직접 붙여넣어도 됩니다."
      />
      <p className="mt-3 text-sm leading-6 text-zinc-500">시간 정보가 있는 SRT/VTT는 시간을 유지하고, 일반 텍스트는 자동으로 구간을 나눕니다.</p>
    </div>
  );
}

function WorkflowPreview() {
  const items = [
    ['01', '장면 스캔', '화면 전환을 기준으로 핵심 이미지를 고릅니다.', <Gauge className="h-5 w-5" />],
    ['02', '내용 튜닝', '겹친 자막과 어색한 표현을 자연스럽게 다듬습니다.', <Wrench className="h-5 w-5" />],
    ['03', 'PDF 출고', '선택한 장면으로 편집 가능한 PDF 초안을 만듭니다.', <FileText className="h-5 w-5" />]
  ] as const;
  return (
    <div className="glass-panel rounded-lg p-5">
      <p className="text-sm font-black text-lime-200">작업 흐름</p>
      <h2 className="mt-1 text-xl font-black text-white">영상에서 교재까지</h2>
      <div className="mt-5 grid gap-3">
        {items.map(([step, title, body, icon]) => (
          <div key={step} className="metal-card grid grid-cols-[52px_1fr] gap-3 rounded-lg p-4">
            <span className="gauge-ring flex h-12 w-12 items-center justify-center rounded-full text-sm font-black text-white shadow-[0_12px_24px_rgba(0,0,0,0.32)]">{step}</span>
            <div>
              <p className="flex items-center gap-2 font-black text-white">
                <span className="text-lime-200">{icon}</span>
                {title}
              </p>
              <p className="mt-1 text-sm leading-6 text-zinc-300">{body}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RecentJobs({ jobs, onOpen }: { jobs: Job[]; onOpen: (jobId: string) => void }) {
  const visibleJobs = jobs.slice(0, 3);
  return (
    <div className="glass-panel rounded-lg p-5">
      <h2 className="mb-4 text-xl font-black text-white">최근 작업</h2>
      <div className="grid gap-3">
        {visibleJobs.length ? visibleJobs.map((job) => (
          <article key={job.id} className="metal-card rounded-lg p-4 transition hover:-translate-y-0.5 hover:border-lime-300/35">
            <div className="flex items-center justify-between gap-3">
              <strong className="min-w-0 break-words text-white">{job.project_title}</strong>
              <span className="shrink-0 rounded-full bg-lime-300/10 px-2.5 py-1 text-xs font-black text-lime-200">{statusLabel(job.status)}</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-[linear-gradient(90deg,#ff3d3d,#ffb020,#b8ff2c,#4fe7ff)] transition-all" style={{ width: `${job.progress}%` }} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => onOpen(job.id)}
                className="pit-button rounded-md px-3 py-2 text-sm font-black transition"
              >
                결과 보기
              </button>
              {job.status === 'COMPLETED' ? (
                <a
                  href={apiUrl(`/jobs/${job.id}/pdf`)}
                  className="drive-button inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-black transition"
                >
                  <Download className="h-4 w-4" />
                  PDF 다운로드
                </a>
              ) : null}
            </div>
          </article>
        )) : <p className="text-sm text-zinc-300">아직 생성한 자료가 없습니다.</p>}
      </div>
    </div>
  );
}
