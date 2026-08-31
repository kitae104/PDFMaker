import axios from 'axios';
import type { Chapter, Frame, HealthResponse, Job, KeyMoment, Transcript, YouTubeMetadata } from '../types';

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '');
const backendBaseUrl = configuredApiBaseUrl?.replace(/\/api$/, '');

export const apiBaseUrl = configuredApiBaseUrl || '/api';

export function apiUrl(path: string) {
  return `${apiBaseUrl}${path.startsWith('/') ? path : `/${path}`}`;
}

export function mediaUrl(path: string) {
  if (/^(https?:|data:|blob:)/.test(path)) return path;
  if (backendBaseUrl && path.startsWith('/storage')) return `${backendBaseUrl}${path}`;
  return path;
}

export const api = axios.create({
  baseURL: apiBaseUrl
});

export async function getHealth() {
  const { data } = await api.get<HealthResponse>('/health');
  return data;
}

export async function listJobs() {
  const { data } = await api.get<Job[]>('/jobs');
  return data;
}

export async function createVideoJob(file: File, options: { materialType: string; difficulty: string; pdfLength: string }) {
  const form = new FormData();
  form.append('file', file);
  form.append('material_type', options.materialType);
  form.append('difficulty', options.difficulty);
  form.append('pdf_length', options.pdfLength);
  const { data } = await api.post<Job>('/jobs', form, { headers: { 'Content-Type': 'multipart/form-data' } });
  return data;
}

export async function analyzeYouTube(url: string, hasRights: boolean) {
  const { data } = await api.post<YouTubeMetadata>('/youtube/analyze', { url, has_rights: hasRights });
  return data;
}

export async function createYouTubeJob(url: string, options: { materialType: string; difficulty: string; pdfLength: string; hasRights: boolean }) {
  const { data } = await api.post<Job>('/jobs/youtube', {
    url,
    has_rights: options.hasRights,
    material_type: options.materialType,
    difficulty: options.difficulty,
    pdf_length: options.pdfLength
  });
  return data;
}

export async function createTranscriptJob(input: { file: File | null; text: string; title: string }, options: { materialType: string; difficulty: string; pdfLength: string }) {
  const form = new FormData();
  if (input.file) form.append('file', input.file);
  if (input.text.trim()) form.append('transcript_text', input.text.trim());
  form.append('title', input.title || 'Transcript Lecture Notes');
  form.append('material_type', options.materialType);
  form.append('difficulty', options.difficulty);
  form.append('pdf_length', options.pdfLength);
  const { data } = await api.post<Job>('/jobs/transcript', form, { headers: { 'Content-Type': 'multipart/form-data' } });
  return data;
}

export async function getJob(jobId: string) {
  const { data } = await api.get<Job>(`/jobs/${jobId}`);
  return data;
}

export async function getTranscript(jobId: string) {
  const { data } = await api.get<Transcript>(`/jobs/${jobId}/transcript`);
  return data;
}

export async function getChapters(jobId: string) {
  const { data } = await api.get<Chapter[]>(`/jobs/${jobId}/chapters`);
  return data;
}

export async function getMoments(jobId: string) {
  const { data } = await api.get<KeyMoment[]>(`/jobs/${jobId}/moments`);
  return data;
}

export async function getFrames(jobId: string) {
  const { data } = await api.get<Frame[]>(`/jobs/${jobId}/frames`);
  return data;
}
