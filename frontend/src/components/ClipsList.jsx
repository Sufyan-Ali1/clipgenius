import { useState } from 'react';
import { getClipDownloadUrl } from '../lib/api';

function ClipsList({ clips, jobId }) {
  const [copiedId, setCopiedId] = useState(null);

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const copyToClipboard = async (text, clipNumber, type) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(`${clipNumber}-${type}`);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
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

            {clip.description && (
              <div className="clip-description">
                <div className="description-header">
                  <span className="label">Caption:</span>
                  <button
                    className={`copy-btn ${copiedId === `${clip.clip_number}-desc` ? 'copied' : ''}`}
                    onClick={() => copyToClipboard(clip.description, clip.clip_number, 'desc')}
                  >
                    {copiedId === `${clip.clip_number}-desc` ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <p className="description-text">{clip.description}</p>
              </div>
            )}

            {clip.hashtags && clip.hashtags.length > 0 && (
              <div className="clip-hashtags">
                <div className="hashtags-header">
                  <span className="label">Hashtags:</span>
                  <button
                    className={`copy-btn ${copiedId === `${clip.clip_number}-tags` ? 'copied' : ''}`}
                    onClick={() => copyToClipboard(clip.hashtags.join(' '), clip.clip_number, 'tags')}
                  >
                    {copiedId === `${clip.clip_number}-tags` ? 'Copied!' : 'Copy All'}
                  </button>
                </div>
                <div className="hashtags-list">
                  {clip.hashtags.map((tag, idx) => (
                    <span key={idx} className="hashtag">{tag}</span>
                  ))}
                </div>
              </div>
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
