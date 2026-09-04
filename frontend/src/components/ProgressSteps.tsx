import { CheckCircle2, Circle, Gauge, Loader2, XCircle } from 'lucide-react';
import type { Job, JobStatus } from '../types';
import { statusLabel } from '../utils/format';

const steps: JobStatus[] = [
  'ANALYZING_INPUT',
  'EXTRACTING_AUDIO',
  'TRANSCRIBING',
  'ANALYZING_TRANSCRIPT',
  'SELECTING_KEY_MOMENTS',
  'CAPTURING_FRAMES',
  'REVIEW_READY',
  'GENERATING_CONTENT',
  'GENERATING_HTML',
  'DOCUMENT_READY',
  'GENERATING_PDF'
];

export function ProgressSteps({ job }: { job: Job }) {
  const currentIndex = steps.indexOf(job.status);
  const progressDegrees = Math.round((job.progress / 100) * 260);

  return (
    <div className="glass-panel rounded-lg p-5">
      <div className="mb-5 grid gap-4 sm:grid-cols-[auto_1fr_auto] sm:items-center">
        <div
          className="flex h-24 w-24 items-center justify-center rounded-full p-2 shadow-[0_18px_36px_rgba(0,0,0,0.34),inset_0_1px_0_rgba(255,255,255,0.15)]"
          style={{
            background: `conic-gradient(from 230deg, #ff3d3d 0deg, #ffb020 ${Math.max(progressDegrees * 0.35, 18)}deg, #b8ff2c ${progressDegrees}deg, rgba(255,255,255,0.12) ${progressDegrees}deg 360deg)`
          }}
        >
          <div className="flex h-full w-full flex-col items-center justify-center rounded-full bg-[#111719] text-center">
            <Gauge className="h-5 w-5 text-lime-200" />
            <strong className="mt-1 text-2xl font-black text-white">{job.progress}%</strong>
          </div>
        </div>
        <div>
          <p className="text-sm font-black text-lime-200">{statusLabel(job.status)}</p>
          <h3 className="mt-1 break-keep text-xl font-black text-white">{job.project_title}</h3>
          <p className="mt-2 text-sm text-zinc-300">분석 엔진이 장면, 자막, PDF 초안을 순서대로 점검하고 있습니다.</p>
        </div>
        <span className="inline-flex w-fit items-center rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1.5 text-xs font-black text-cyan-100">
          DRIVE MODE
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/10 shadow-[inset_0_1px_3px_rgba(0,0,0,0.35)]">
        <div className="h-full rounded-full bg-[linear-gradient(90deg,#ff3d3d,#ffb020,#b8ff2c,#4fe7ff)] transition-all" style={{ width: `${job.progress}%` }} />
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {steps.map((step, index) => {
          const done = job.status === 'COMPLETED' || index < currentIndex || step === 'REVIEW_READY' && ['GENERATING_CONTENT', 'GENERATING_HTML', 'DOCUMENT_READY', 'GENERATING_PDF'].includes(job.status);
          const active = step === job.status;
          return (
            <div
              key={step}
              className={`flex min-h-11 items-center gap-2 rounded-lg border px-3 py-2 text-sm transition ${
                active
                  ? 'border-lime-300/45 bg-lime-300/10 text-white shadow-[0_12px_22px_rgba(129,196,12,0.1)]'
                  : done
                    ? 'border-cyan-300/20 bg-cyan-300/[0.07] text-zinc-200'
                    : 'border-white/10 bg-white/[0.03] text-zinc-400'
              }`}
            >
              {job.status === 'FAILED' && active ? (
                <XCircle className="h-4 w-4 text-red-300" />
              ) : done ? (
                <CheckCircle2 className="h-4 w-4 text-lime-200" />
              ) : active ? (
                <Loader2 className="h-4 w-4 animate-spin text-lime-200" />
              ) : (
                <Circle className="h-4 w-4 text-zinc-500" />
              )}
              <span>{statusLabel(step)}</span>
            </div>
          );
        })}
      </div>
      {job.error_message ? <p className="mt-4 rounded-lg border border-red-300/25 bg-red-400/10 p-3 text-sm text-red-100">{job.error_message}</p> : null}
    </div>
  );
}
