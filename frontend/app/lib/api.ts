export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
  const formData = new FormData();
  formData.append('image', imageBlob, 'input.png');

  const response = await fetch(`${API_BASE}/api/v1/generate`, {
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
  let attempts = 0;

  while (attempts < MAX_POLLING_ATTEMPTS) {
    try {
      const response = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`);
      
      if (!response.ok) {
        // Log non-200 but keep trying for a bit, maybe it's a temporary blip
        console.warn(`Attempt ${attempts}: API responded with ${response.status}`);
      } else {
        const job: JobResponse = await response.json();
        if (onUpdate) onUpdate(job.status);

        if (job.status === 'completed') return jobId;
        if (job.status === 'failed') throw new Error(job.error || 'The neural engine encountered an internal error.');
      }
    } catch (err) {
      // If it's our own 'failed' error, rethrow it
      if (err instanceof Error && err.message.includes('neural engine')) throw err;
      
      // Otherwise, it might be a network error, log and continue polling
      console.error('Polling error:', err);
    }

    attempts++;
    await new Promise(r => setTimeout(r, POLLING_INTERVAL));
  }

  throw new Error('Synthesis timed out. The worker might be overloaded.');
}

export function getResultUrl(jobId: string) {
  return `${API_BASE}/api/v1/jobs/${jobId}/result`;
}
