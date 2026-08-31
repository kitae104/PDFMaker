import { useEffect, useState } from 'react';
import { Download, Film, ListChecks } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { apiUrl, getChapters, getFrames, getJob, getMoments, getTranscript, mediaUrl } from '../api/client';
import { ProgressSteps } from '../components/ProgressSteps';
import type { Chapter, Frame, Job, KeyMoment, Transcript } from '../types';
import { formatTimestamp } from '../utils/format';

type Tab = 'preview' | 'transcript' | 'chapters' | 'moments';

export function ResultsPage() {
  const { jobId } = useParams();
  const [job, setJob] = useState<Job | null>(null);
  const [tab, setTab] = useState<Tab>('preview');
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [moments, setMoments] = useState<KeyMoment[]>([]);
  const [frames, setFrames] = useState<Frame[]>([]);

  useEffect(() => {
    if (!jobId) return;
    const load = async () => {
      const nextJob = await getJob(jobId);
      setJob(nextJob);
      if (nextJob.status === 'COMPLETED') {
        const [nextTranscript, nextChapters, nextMoments, nextFrames] = await Promise.all([
          getTranscript(jobId),
          getChapters(jobId),
          getMoments(jobId),
          getFrames(jobId)
        ]);
        setTranscript(nextTranscript);
        setChapters(nextChapters);
        setMoments(nextMoments);
        setFrames(nextFrames);
      }
    };
    load();
    const timer = window.setInterval(load, 2500);
    return () => window.clearInterval(timer);
  }, [jobId]);

  if (!job || !jobId) {
    return <main className="min-h-screen bg-slate-50 p-8 text-slate-600">결과를 불러오는 중입니다.</main>;
  }

  const completed = job.status === 'COMPLETED';

  return (
    <main className="min-h-screen bg-slate-50 text-ink">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-4">
          <Link to="/" className="font-bold text-indigo-700">AI Video Lecture Note Generator</Link>
          {completed ? (
            <a href={apiUrl(`/jobs/${jobId}/pdf`)} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-bold text-white hover:bg-indigo-700">
              <Download className="h-4 w-4" /> PDF 다운로드
            </a>
          ) : null}
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
              <p className="mt-1 text-slate-500">{chapters.length || 0} Chapters / {moments.length || 0} Key Moments</p>
            </div>
          </div>
        </div>

        {!completed ? <ProgressSteps job={job} /> : null}

        {completed ? (
          <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="flex gap-1 border-b border-slate-200 p-2">
              {(['preview', 'transcript', 'chapters', 'moments'] as Tab[]).map((item) => (
                <button key={item} onClick={() => setTab(item)} className={`rounded-md px-4 py-2 text-sm font-bold ${tab === item ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>
                  {item === 'preview' ? 'Preview' : item === 'transcript' ? 'Transcript' : item === 'chapters' ? 'Chapters' : 'Key Moments'}
                </button>
              ))}
            </div>

            <div className="p-5">
              {tab === 'preview' ? (
                <iframe title="PDF Preview" src={apiUrl(`/jobs/${jobId}/preview`)} className="h-[760px] w-full rounded-lg border border-slate-200 bg-white" />
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
              {tab === 'chapters' ? (
                <div className="grid gap-4">
                  {chapters.map((chapter) => (
                    <article key={chapter.id} className="rounded-lg border border-slate-100 p-4">
                      <h2 className="text-xl font-bold text-slate-950">{chapter.title}</h2>
                      <p className="mt-1 text-sm font-semibold text-indigo-700">{formatTimestamp(chapter.start)} - {formatTimestamp(chapter.end)} / 중요도 {chapter.importance}</p>
                      <p className="mt-2 text-slate-600">{chapter.summary}</p>
                    </article>
                  ))}
                </div>
              ) : null}
              {tab === 'moments' ? (
                <div className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
                  <div className="grid gap-3">
                    {moments.map((moment) => (
                      <div key={moment.id} className="rounded-lg border border-slate-100 p-4">
                        <div className="flex items-center gap-2">
                          <ListChecks className="h-4 w-4 text-indigo-600" />
                          <strong>{formatTimestamp(moment.timestamp)} {moment.title}</strong>
                        </div>
                        <p className="mt-2 text-sm text-slate-600">{moment.reason}</p>
                      </div>
                    ))}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {frames.filter((frame) => frame.selected).map((frame) => (
                      <img key={frame.id} src={mediaUrl(frame.url)} alt="Selected key frame" className="rounded-lg border border-slate-200" />
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>
    </main>
  );
}
