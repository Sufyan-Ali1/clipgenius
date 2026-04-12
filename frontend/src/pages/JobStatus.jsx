import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import ProgressBar from '../components/ProgressBar';
import StepsList from '../components/StepsList';
import ClipsList from '../components/ClipsList';
import { getJob, getJobResults } from '../lib/api';

function JobStatus() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadJob();

    const interval = setInterval(() => {
      if (job?.status !== 'completed' && job?.status !== 'failed') {
        loadJob();
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [id, job?.status]);

  const loadJob = async () => {
    try {
      const jobData = await getJob(id);
      setJob(jobData);
      setLoading(false);

      if (jobData.status === 'completed') {
        const resultsData = await getJobResults(id);
        setResults(resultsData);
      }
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="job-status">
        <div className="loading-spinner">Loading job...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="job-status">
        <div className="error-card">
          <h2>Error</h2>
          <p>{error}</p>
          <Link to="/" className="back-btn">Back to Home</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="job-status">
      <header className="job-header">
        <Link to="/" className="back-link">Back</Link>
        <h1>Job Status</h1>
        <span className="job-id">{id}</span>
      </header>

      <section className="progress-section">
        <ProgressBar
          progress={job.progress}
          status={job.status}
          currentStep={job.current_step}
        />
        <StepsList
          currentStatus={job.status}
          addSubtitles={job.add_subtitles}
        />
      </section>

      {job.status === 'failed' && job.error && (
        <section className="error-section">
          <h3>Error Details</h3>
          <p className="error-message">{job.error}</p>
        </section>
      )}

      {job.status === 'completed' && results && (
        <section className="results-section">
          <ClipsList
            clips={results.clips}
            jobId={id}
          />

          <div className="summary">
            <p>Total Duration: {Math.round(results.total_duration)}s</p>
            {results.output_directory && (
              <p>Output: {results.output_directory}</p>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

export default JobStatus;
