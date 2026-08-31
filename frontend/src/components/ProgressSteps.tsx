import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react';
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
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-indigo-700">{statusLabel(job.status)}</p>
          <h3 className="text-lg font-bold text-slate-950">{job.project_title}</h3>
        </div>
        <div className="text-right text-sm text-slate-500">
          <strong className="text-2xl text-indigo-700">{job.progress}%</strong>
        </div>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-indigo-600 transition-all" style={{ width: `${job.progress}%` }} />
      </div>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {steps.map((step, index) => {
          const done = job.status === 'COMPLETED' || index < currentIndex || step === 'REVIEW_READY' && ['GENERATING_CONTENT', 'GENERATING_HTML', 'DOCUMENT_READY', 'GENERATING_PDF'].includes(job.status);
          const active = step === job.status;
          return (
            <div key={step} className="flex items-center gap-2 text-sm text-slate-700">
              {job.status === 'FAILED' && active ? (
                <XCircle className="h-4 w-4 text-rose-500" />
              ) : done ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              ) : active ? (
                <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
              ) : (
                <Circle className="h-4 w-4 text-slate-300" />
              )}
              <span>{statusLabel(step)}</span>
            </div>
          );
        })}
      </div>
      {job.error_message ? <p className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{job.error_message}</p> : null}
    </div>
  );
}
