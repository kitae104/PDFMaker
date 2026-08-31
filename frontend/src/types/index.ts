export type JobStatus =
  | 'QUEUED'
  | 'ANALYZING_INPUT'
  | 'EXTRACTING_AUDIO'
  | 'TRANSCRIBING'
  | 'ANALYZING_TRANSCRIPT'
  | 'GENERATING_CHAPTERS'
  | 'SELECTING_KEY_MOMENTS'
  | 'CAPTURING_FRAMES'
  | 'REVIEW_READY'
  | 'GENERATING_CONTENT'
  | 'GENERATING_HTML'
  | 'DOCUMENT_READY'
  | 'GENERATING_PDF'
  | 'COMPLETED'
  | 'FAILED';

export interface HealthResponse {
  status: string;
  app_name: string;
  database: string;
}

export interface YouTubeMetadata {
  videoId: string;
  title: string;
  channel: string;
  duration: number | null;
  thumbnail: string;
  captionsAvailable: boolean | null;
  sourceUrl: string;
  policyNote: string;
}

export interface Job {
  id: string;
  project_id: string;
  project_title: string;
  source_type: 'video' | 'youtube' | 'transcript';
  status: JobStatus;
  progress: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface Transcript {
  language: string;
  duration: number;
  segments: TranscriptSegment[];
}

export interface Chapter {
  id: string;
  title: string;
  start: number;
  end: number;
  summary: string;
  importance: number;
}

export interface KeyMoment {
  id: string;
  title: string;
  timestamp: number;
  reason: string;
  importance: number;
  selected: boolean;
}

export interface Frame {
  id: string;
  timestamp: number;
  selected: boolean;
  score: number;
  url: string;
}

export interface ReviewSegment {
  id: string;
  title: string;
  summary: string;
  start: number;
  end: number;
  selected: boolean;
  frame: {
    id: string;
    url: string;
    timestamp: number;
  } | null;
}

export interface LessonTerm {
  term: string;
  definition: string;
}

export interface LessonChapter {
  title: string;
  learning_objectives: string[];
  explanation: string;
  beginner_explanation: string;
  key_points: string[];
  terms: LessonTerm[];
  timestamp: string;
  summary: string;
}

export interface LessonContent {
  title: string;
  overview: string;
  learning_objectives: string[];
  chapters: LessonChapter[];
  final_summary: string[];
  review_questions: string[];
}
