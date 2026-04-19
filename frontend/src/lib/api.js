export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

export function uploadVideo(file, options = {}, onProgress = null) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);

    // Add optional parameters
    if (options.num_clips) formData.append('num_clips', options.num_clips);
    if (options.min_duration) formData.append('min_duration', options.min_duration);
    if (options.max_duration) formData.append('max_duration', options.max_duration);
    if (options.add_subtitles !== undefined) formData.append('add_subtitles', options.add_subtitles);
    if (options.vertical_mode !== undefined) formData.append('vertical_mode', options.vertical_mode);
    if (options.video_quality) formData.append('video_quality', options.video_quality);

    const xhr = new XMLHttpRequest();

    // Track upload progress
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        const progress = event.loaded / event.total;
        onProgress(progress);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response = JSON.parse(xhr.responseText);
          resolve(response);
        } catch (e) {
          reject(new Error('Invalid response from server'));
        }
      } else {
        try {
          const error = JSON.parse(xhr.responseText);
          reject(new Error(error.detail || 'Failed to upload video'));
        } catch (e) {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      }
    };

    xhr.onerror = () => {
      reject(new Error('Network error during upload'));
    };

    xhr.open('POST', `${API_URL}/api/v1/jobs/upload`);
    xhr.send(formData);
  });
}

// Start an upload job - returns job_id immediately so we can redirect to status page
export async function startUploadJob(file, options = {}) {
  const formData = new FormData();
  formData.append('filename', file.name);
  formData.append('filesize', file.size);

  // Add optional parameters
  if (options.num_clips) formData.append('num_clips', options.num_clips);
  if (options.min_duration) formData.append('min_duration', options.min_duration);
  if (options.max_duration) formData.append('max_duration', options.max_duration);
  if (options.add_subtitles !== undefined) formData.append('add_subtitles', options.add_subtitles);
  if (options.vertical_mode !== undefined) formData.append('vertical_mode', options.vertical_mode);
  if (options.video_quality) formData.append('video_quality', options.video_quality);

  const res = await fetch(`${API_URL}/api/v1/jobs/upload/start`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Failed to start upload job');
  }

  return res.json();
}

// Upload file to an existing job with progress tracking
export function uploadJobFile(jobId, file, onProgress = null) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        const progress = event.loaded / event.total;
        onProgress(progress);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response = JSON.parse(xhr.responseText);
          resolve(response);
        } catch (e) {
          reject(new Error('Invalid response from server'));
        }
      } else {
        try {
          const error = JSON.parse(xhr.responseText);
          reject(new Error(error.detail || 'Failed to upload file'));
        } catch (e) {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      }
    };

    xhr.onerror = () => {
      reject(new Error('Network error during upload'));
    };

    xhr.open('POST', `${API_URL}/api/v1/jobs/${jobId}/file`);
    xhr.send(formData);
  });
}
