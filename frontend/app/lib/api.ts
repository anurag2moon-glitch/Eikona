import { db, ref, get } from './firebase';

let cachedApiBase: string | null = null;
let lastFetchTime = 0;
const CACHE_TTL = 30000; // 30 seconds

async function getDynamicApiBase(): Promise<string> {
  const now = Date.now();
  if (cachedApiBase && (now - lastFetchTime < CACHE_TTL)) {
    return cachedApiBase;
  }

  try {
    const dbRef = ref(db, 'server_config/api_url');
    const snapshot = await get(dbRef);
    if (snapshot.exists()) {
      cachedApiBase = snapshot.val();
      lastFetchTime = now;
      return cachedApiBase!;
    }
  } catch (error) {
    console.warn('Failed to fetch API base from Firebase, falling back to env/default:', error);
  }

  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
}

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed';

export interface JobResponse {
  job_id: string;
  status: JobStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
  result_url?: string;
}

/**
 * Submits an image to the API
 */
export async function submitJob(imageBlob: Blob): Promise<string> {
  const apiBase = await getDynamicApiBase();
  const formData = new FormData();
  formData.append('image', imageBlob, 'input.png');

  const response = await fetch(`${apiBase}/api/v1/generate`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to submit job');
  }

  const { job_id } = await response.json();
  return job_id;
}

const POLLING_INTERVAL = 1000;
const MAX_POLLING_ATTEMPTS = 120; // 2 minutes max

/**
 * Polls for job completion with a safety timeout
 */
export async function pollJob(jobId: string, onUpdate?: (status: JobStatus) => void): Promise<string> {
  const apiBase = await getDynamicApiBase();
  let attempts = 0;

  while (attempts < MAX_POLLING_ATTEMPTS) {
    try {
      const response = await fetch(`${apiBase}/api/v1/jobs/${jobId}`);
      
      if (!response.ok) {
        console.warn(`Attempt ${attempts}: API responded with ${response.status}`);
      } else {
        const job: JobResponse = await response.json();
        if (onUpdate) onUpdate(job.status);

        if (job.status === 'completed') return jobId;
        if (job.status === 'failed') throw new Error(job.error || 'The neural engine encountered an internal error.');
      }
    } catch (err) {
      if (err instanceof Error && err.message.includes('neural engine')) throw err;
      console.error('Polling error:', err);
    }

    attempts++;
    await new Promise(r => setTimeout(r, POLLING_INTERVAL));
  }

  throw new Error('Synthesis timed out. The worker might be overloaded.');
}

export async function getResultUrl(jobId: string) {
  const apiBase = await getDynamicApiBase();
  // Add a timestamp to bust browser cache so the user doesn't have to clear cookies/incognito
  return `${apiBase}/api/v1/jobs/${jobId}/result?t=${Date.now()}`;
}
