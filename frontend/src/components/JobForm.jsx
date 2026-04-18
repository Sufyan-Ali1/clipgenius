import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { createJob, uploadVideo } from '../lib/api';

function JobForm() {
  const [inputMode, setInputMode] = useState('youtube'); // 'youtube' or 'upload'
  const [url, setUrl] = useState('');
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [addSubtitles, setAddSubtitles] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
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
    const allowedTypes = ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm', 'video/x-matroska'];
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    setUploadProgress(0);

    try {
      let result;

      if (inputMode === 'upload') {
        if (!file) {
          throw new Error('Please select a video file');
        }
        result = await uploadVideo(file, { add_subtitles: addSubtitles });
      } else {
        if (!url) {
          throw new Error('Please enter a YouTube URL');
        }
        result = await createJob(url, { add_subtitles: addSubtitles });
      }

      navigate(`/jobs/${result.job_id}`);
    } catch (err) {
      setError(err.message);
    } finally {
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
    <form onSubmit={handleSubmit} className="job-form">
      {/* Input Mode Tabs */}
      <div className="input-mode-tabs">
        <button
          type="button"
          className={`tab ${inputMode === 'youtube' ? 'active' : ''}`}
          onClick={() => setInputMode('youtube')}
          disabled={loading}
        >
          YouTube URL
        </button>
        <button
          type="button"
          className={`tab ${inputMode === 'upload' ? 'active' : ''}`}
          onClick={() => setInputMode('upload')}
          disabled={loading}
        >
          Upload Video
        </button>
      </div>

      {/* Upload Mode */}
      {inputMode === 'upload' && (
        <div
          className={`upload-area ${dragActive ? 'drag-active' : ''} ${file ? 'has-file' : ''}`}
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
            <div className="file-info">
              <div className="file-icon">🎬</div>
              <div className="file-details">
                <span className="file-name">{file.name}</span>
                <span className="file-size">{formatFileSize(file.size)}</span>
              </div>
              <button
                type="button"
                className="remove-file"
                onClick={(e) => { e.stopPropagation(); setFile(null); }}
                disabled={loading}
              >
                ×
              </button>
            </div>
          ) : (
            <div className="upload-prompt">
              <div className="upload-icon">📁</div>
              <p>Drag & drop your video here</p>
              <p className="upload-hint">or click to browse</p>
              <p className="upload-formats">MP4, MOV, MKV, AVI, WebM (max 500MB)</p>
            </div>
          )}
        </div>
      )}

      {/* YouTube Mode */}
      {inputMode === 'youtube' && (
        <div className="youtube-input">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Paste YouTube URL here..."
            disabled={loading}
          />
        </div>
      )}

      {/* Options */}
      <div className="options-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={addSubtitles}
            onChange={(e) => setAddSubtitles(e.target.checked)}
            disabled={loading}
          />
          <span>Add Subtitles</span>
        </label>
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        className="submit-btn"
        disabled={loading || (inputMode === 'upload' ? !file : !url)}
      >
        {loading ? (
          inputMode === 'upload' ? 'Uploading...' : 'Creating...'
        ) : (
          'Create Clips'
        )}
      </button>

      {error && <p className="error">{error}</p>}
    </form>
  );
}

export default JobForm;
