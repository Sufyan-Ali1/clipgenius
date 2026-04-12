import { getClipDownloadUrl } from '../lib/api';

function ClipsList({ clips, jobId }) {
  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="clips-list">
      <div className="clips-header">
        <h3>Generated Clips ({clips.length})</h3>
      </div>

      <div className="clips-grid">
        {clips.map((clip) => (
          <div key={clip.clip_number} className="clip-card">
            <div className="clip-number">Clip #{clip.clip_number}</div>

            <div className="clip-info">
              <div className="info-row">
                <span className="label">Duration:</span>
                <span>{formatDuration(clip.duration)}</span>
              </div>
              <div className="info-row">
                <span className="label">Time:</span>
                <span>{formatDuration(clip.start_seconds)} - {formatDuration(clip.end_seconds)}</span>
              </div>
              {clip.score && (
                <div className="info-row">
                  <span className="label">Score:</span>
                  <span className="score">{clip.score}/10</span>
                </div>
              )}
            </div>

            {clip.hook && (
              <p className="clip-hook">"{clip.hook}"</p>
            )}

            <div className="clip-filename">{clip.filename}</div>

            <a
              href={getClipDownloadUrl(jobId, clip.clip_number)}
              download={clip.filename}
              className="download-btn"
            >
              Download Clip
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ClipsList;
