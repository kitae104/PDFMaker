import { create } from 'zustand';
import type { Job } from '../types';

interface JobState {
  activeJob: Job | null;
  recentJobs: Job[];
  setActiveJob: (job: Job | null) => void;
  setRecentJobs: (jobs: Job[]) => void;
}

export const useJobStore = create<JobState>((set) => ({
  activeJob: null,
  recentJobs: [],
  setActiveJob: (job) => set({ activeJob: job }),
  setRecentJobs: (jobs) => set({ recentJobs: jobs })
}));
