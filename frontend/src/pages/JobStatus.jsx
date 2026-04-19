import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import ProgressBar from '../components/ProgressBar';
import StepsList from '../components/StepsList';
import ClipsList from '../components/ClipsList';
import { getJob, getJobResults, API_URL } from '../lib/api';

function JobStatus() {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  // SSE streaming state
  const [sseConnected, setSseConnected] = useState(false);
  const [stepProgress, setStepProgress] = useState(0);
  const [stepMessage, setStepMessage] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [stepRemaining, setStepRemaining] = useState(0);
  const [totalRemaining, setTotalRemaining] = useState(0);
  const [stepDurations, setStepDurations] = useState({});

  const eventSourceRef = useRef(null);
  const fallbackIntervalRef = useRef(null);

  // Initial job load
  useEffect(() => {
    loadJob();
    return () => {
      // Cleanup on unmount
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (fallbackIntervalRef.current) {
        clearInterval(fallbackIntervalRef.current);
      }
    };
  }, [id]);

  // Setup SSE or fallback to polling
  useEffect(() => {
    if (!job) return;

    // If job is in terminal state, no need for streaming
    if (['completed', 'failed', 'cancelled'].includes(job.status)) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (fallbackIntervalRef.current) {
        clearInterval(fallbackIntervalRef.current);
        fallbackIntervalRef.current = null;
      }

      // Load results if completed
      if (job.status === 'completed' && !results) {
        loadResults();
      }
      return;
    }

    // Try to connect to SSE
    connectSSE();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [job?.status, id]);

  const connectSSE = () => {
    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    try {
      const sseUrl = `${API_URL}/jobs/${id}/stream`;
      const eventSource = new EventSource(sseUrl);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        setSseConnected(true);
        // Clear polling fallback if SSE connects
        if (fallbackIntervalRef.current) {
          clearInterval(fallbackIntervalRef.current);
          fallbackIntervalRef.current = null;
        }
      };

      eventSource.addEventListener('progress', (event) => {
        try {
          const data = JSON.parse(event.data);

          // Update job state
          setJob(prev => ({
            ...prev,
            status: data.status,
            progress: data.progress,
            current_step: data.current_step,
            error: data.error,
          }));

          // Update SSE-specific state
          setStepProgress(data.step_progress || 0);
          setStepMessage(data.step_message);
          setElapsed(data.elapsed || 0);
          setStepRemaining(data.step_remaining || 0);
          setTotalRemaining(data.total_remaining || 0);
          setStepDurations(data.step_durations || {});

          // Handle completion
          if (data.status === 'completed') {
            loadResults();
          }
        } catch (e) {
          console.error('Error parsing SSE data:', e);
        }
      });

      eventSource.addEventListener('error', (event) => {
        try {
          const data = JSON.parse(event.data);
          setError(data.error);
        } catch (e) {
          // Connection error, not a data error
        }
      });

      eventSource.onerror = () => {
        setSseConnected(false);
        eventSource.close();
        eventSourceRef.current = null;

        // Fallback to polling if SSE fails
        if (!fallbackIntervalRef.current) {
          fallbackIntervalRef.current = setInterval(loadJob, 2000);
        }
      };
    } catch (e) {
      console.error('SSE connection failed:', e);
      // Fallback to polling
      if (!fallbackIntervalRef.current) {
        fallbackIntervalRef.current = setInterval(loadJob, 2000);
      }
    }
  };

  const loadJob = async () => {
    try {
      const jobData = await getJob(id);
      setJob(jobData);
      setLoading(false);

      // Update step durations from job data if available
      if (jobData.step_durations) {
        setStepDurations(jobData.step_durations);
      }

      if (jobData.status === 'completed' && !results) {
        loadResults();
      }
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const loadResults = async () => {
    try {
      const resultsData = await getJobResults(id);
      setResults(resultsData);
    } catch (err) {
      console.error('Error loading results:', err);
    }
  };

  if (loading) {
    return (
      <div className="job-status">
        <div className="loading-spinner">Loading job...</div>
      </div>
    );
  }

  if (error && !job) {
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

  const isProcessing = job && !['completed', 'failed', 'cancelled'].includes(job.status);

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
          stepProgress={stepProgress}
          stepMessage={stepMessage}
          elapsed={elapsed}
          stepRemaining={stepRemaining}
          totalRemaining={totalRemaining}
          stepDurations={stepDurations}
        />

        {/* Connection status indicator */}
        {isProcessing && (
          <div className={`connection-status ${sseConnected ? 'connected' : 'polling'}`}>
            {sseConnected ? 'Live updates' : 'Polling updates'}
          </div>
        )}
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
