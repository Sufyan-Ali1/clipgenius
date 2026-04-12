import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createJob } from '../lib/api';

function JobForm() {
  const [url, setUrl] = useState('');
  const [addSubtitles, setAddSubtitles] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await createJob(url, { add_subtitles: addSubtitles });
      navigate(`/jobs/${result.job_id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="job-form">
      <div className="input-group">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Paste YouTube URL here..."
          disabled={loading}
          required
        />
        <button type="submit" disabled={loading || !url}>
          {loading ? 'Creating...' : 'Create Clips'}
        </button>
      </div>

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

      {error && <p className="error">{error}</p>}
    </form>
  );
}

export default JobForm;
