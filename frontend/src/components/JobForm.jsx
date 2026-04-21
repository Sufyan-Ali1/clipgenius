import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { createJob, startUploadJob } from '../lib/api';

function JobForm() {
  const [clipMode, setClipMode] = useState('ai'); // 'ai' or 'manual'
  const [inputMode, setInputMode] = useState('youtube'); // 'youtube' or 'upload'
  const [url, setUrl] = useState('');
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [addSubtitles, setAddSubtitles] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [manualClips, setManualClips] = useState([{ start: '', end: '' }]);
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFile = (selectedFile) => {
    const allowedExtensions = ['.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v'];
    const ext = '.' + selectedFile.name.split('.').pop().toLowerCase();

    if (!allowedExtensions.includes(ext)) {
      setError(`Invalid file type. Allowed: ${allowedExtensions.join(', ')}`);
      return;
    }

    if (selectedFile.size > 500 * 1024 * 1024) {
      setError('File too large. Maximum size is 500MB');
      return;
    }

    setFile(selectedFile);
    setError('');
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const isValidTimestamp = (ts) => {
    if (!ts) return false;
    return /^(\d{1,2}:)?\d{1,2}:\d{2}$/.test(ts.trim());
  };

  const parseTimestamp = (ts) => {
    const parts = ts.trim().split(':').map(Number);
    if (parts.length === 2) {
      return parts[0] * 60 + parts[1];
    } else if (parts.length === 3) {
      return parts[0] * 3600 + parts[1] * 60 + parts[2];
    }
    return 0;
  };

  const validateManualClips = () => {
    for (let i = 0; i < manualClips.length; i++) {
      const clip = manualClips[i];
      if (!isValidTimestamp(clip.start)) {
        return `Clip ${i + 1}: Invalid start time (use MM:SS)`;
      }
      if (!isValidTimestamp(clip.end)) {
        return `Clip ${i + 1}: Invalid end time (use MM:SS)`;
      }
      if (parseTimestamp(clip.end) <= parseTimestamp(clip.start)) {
        return `Clip ${i + 1}: End must be after start`;
      }
    }
    return null;
  };

  const handleClipChange = (index, field, value) => {
    const updated = [...manualClips];
    updated[index][field] = value;
    setManualClips(updated);
  };

  const addClipRow = () => {
    setManualClips([...manualClips, { start: '', end: '' }]);
  };

  const removeClipRow = (index) => {
    if (manualClips.length > 1) {
      setManualClips(manualClips.filter((_, i) => i !== index));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (clipMode === 'manual') {
        const validationError = validateManualClips();
        if (validationError) {
          throw new Error(validationError);
        }
      }

      let result;
      const options = {
        add_subtitles: addSubtitles,
        manual_clips: clipMode === 'manual' ? manualClips : null,
      };

      if (inputMode === 'upload') {
        if (!file) {
          throw new Error('Please select a video file');
        }
        result = await startUploadJob(file, options);
        navigate(`/jobs/${result.job_id}`, { state: { fileToUpload: file } });
        return;
      } else {
        if (!url) {
          throw new Error('Please enter a YouTube URL');
        }
        result = await createJob(url, options);
      }

      navigate(`/jobs/${result.job_id}`);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024 * 1024) {
      return (bytes / 1024).toFixed(1) + ' KB';
    }
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <form onSubmit={handleSubmit} className="job-form-dashboard">
      {/* Section 1: Mode Toggle */}
      <div className="mode-toggle">
        <button
          type="button"
          className={`mode-toggle-btn ${clipMode === 'ai' ? 'active' : ''}`}
          onClick={() => !loading && setClipMode('ai')}
          disabled={loading}
        >
          AI Mode
        </button>
        <button
          type="button"
          className={`mode-toggle-btn ${clipMode === 'manual' ? 'active' : ''}`}
          onClick={() => !loading && setClipMode('manual')}
          disabled={loading}
        >
          Manual Mode
        </button>
      </div>

      {/* Section 2: Video Source */}
      <div className="source-section">
        <div className="source-cards">
          <div
            className={`source-card ${inputMode === 'youtube' ? 'active' : ''}`}
            onClick={() => !loading && setInputMode('youtube')}
          >
            <div className="source-card-icon">
              <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
              </svg>
            </div>
            <span className="source-card-title">YouTube URL</span>
            <span className="source-card-desc">Paste a video link</span>
          </div>

          <div
            className={`source-card ${inputMode === 'upload' ? 'active' : ''}`}
            onClick={() => !loading && setInputMode('upload')}
          >
            <div className="source-card-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
            </div>
            <span className="source-card-title">Upload File</span>
            <span className="source-card-desc">Drag & drop or browse</span>
          </div>
        </div>

        {/* Input Area */}
        <div className="input-area">
          {inputMode === 'youtube' ? (
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://youtube.com/watch?v=..."
              disabled={loading}
              className="url-input"
            />
          ) : (
            <div
              className={`upload-zone ${dragActive ? 'drag-active' : ''} ${file ? 'has-file' : ''}`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => !file && fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".mp4,.mov,.avi,.webm,.mkv,.m4v"
                onChange={handleFileInput}
                disabled={loading}
                style={{ display: 'none' }}
              />
              {file ? (
                <div className="file-selected">
                  <svg className="file-selected-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                  </svg>
                  <div className="file-selected-info">
                    <span className="file-selected-name">{file.name}</span>
                    <span className="file-selected-size">{formatFileSize(file.size)}</span>
                  </div>
                  {!loading && (
                    <button
                      type="button"
                      className="file-remove"
                      onClick={(e) => { e.stopPropagation(); setFile(null); }}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                      </svg>
                    </button>
                  )}
                </div>
              ) : (
                <div className="upload-placeholder">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/>
                    <line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                  <span>Drop video file or click to browse</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Section 3: Manual Timestamps (Conditional) */}
      {clipMode === 'manual' && (
        <div className="timestamps-section">
          <div className="timestamps-header">
            <span className="timestamps-label">Timestamps</span>
            <span className="timestamps-hint">Format: MM:SS or HH:MM:SS</span>
          </div>
          <div className="timestamps-list">
            {manualClips.map((clip, index) => (
              <div key={index} className="timestamp-row">
                <span className="timestamp-num">{index + 1}</span>
                <input
                  type="text"
                  value={clip.start}
                  onChange={(e) => handleClipChange(index, 'start', e.target.value)}
                  placeholder="0:00"
                  className="timestamp-field"
                  disabled={loading}
                />
                <span className="timestamp-sep">to</span>
                <input
                  type="text"
                  value={clip.end}
                  onChange={(e) => handleClipChange(index, 'end', e.target.value)}
                  placeholder="1:30"
                  className="timestamp-field"
                  disabled={loading}
                />
                {manualClips.length > 1 && (
                  <button
                    type="button"
                    className="timestamp-remove"
                    onClick={() => removeClipRow(index)}
                    disabled={loading}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <line x1="18" y1="6" x2="6" y2="18"/>
                      <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                  </button>
                )}
              </div>
            ))}
          </div>
          <button
            type="button"
            className="add-timestamp-btn"
            onClick={addClipRow}
            disabled={loading}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19"/>
              <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            Add Another Clip
          </button>
        </div>
      )}

      {/* Section 4: Footer */}
      <div className="form-footer">
        <label className="subtitle-toggle">
          <input
            type="checkbox"
            checked={addSubtitles}
            onChange={(e) => setAddSubtitles(e.target.checked)}
            disabled={loading}
          />
          <span className="toggle-track">
            <span className="toggle-thumb"></span>
          </span>
          <span className="toggle-label">Add Subtitles</span>
        </label>

        <button
          type="submit"
          className="create-btn"
          disabled={loading || (inputMode === 'upload' ? !file : !url)}
        >
          {loading ? (
            <>
              <span className="btn-spinner"></span>
              Processing...
            </>
          ) : (
            <>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
              Create Clips
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="form-error">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          {error}
        </div>
      )}
    </form>
  );
}

export default JobForm;
