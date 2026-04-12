const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function createJob(inputSource, options = {}) {
  const res = await fetch(`${API_URL}/api/v1/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      input_source: inputSource,
      ...options,
    }),
  });

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to create job');
  }

  return res.json();
}

export async function getJob(jobId) {
  const res = await fetch(`${API_URL}/api/v1/jobs/${jobId}`);

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to get job');
  }

  return res.json();
}

export async function getJobResults(jobId) {
  const res = await fetch(`${API_URL}/api/v1/jobs/${jobId}/results`);

  if (!res.ok) {
    if (res.status === 404) {
      return null;
    }
    const error = await res.json();
    throw new Error(error.detail || 'Failed to get results');
  }

  return res.json();
}

export async function listJobs() {
  const res = await fetch(`${API_URL}/api/v1/jobs`);

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to list jobs');
  }

  return res.json();
}

export function getClipDownloadUrl(jobId, clipNumber) {
  return `${API_URL}/api/v1/jobs/${jobId}/clips/${clipNumber}/download`;
}
