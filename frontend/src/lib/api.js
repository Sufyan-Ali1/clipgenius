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

export async function uploadVideo(file, options = {}, onProgress = null) {
  const formData = new FormData();
  formData.append('file', file);

  // Add optional parameters
  if (options.num_clips) formData.append('num_clips', options.num_clips);
  if (options.min_duration) formData.append('min_duration', options.min_duration);
  if (options.max_duration) formData.append('max_duration', options.max_duration);
  if (options.add_subtitles !== undefined) formData.append('add_subtitles', options.add_subtitles);
  if (options.vertical_mode !== undefined) formData.append('vertical_mode', options.vertical_mode);
  if (options.video_quality) formData.append('video_quality', options.video_quality);

  const res = await fetch(`${API_URL}/api/v1/jobs/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to upload video');
  }

  return res.json();
}
