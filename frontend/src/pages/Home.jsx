import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import JobForm from '../components/JobForm';
import { listJobs } from '../lib/api';

function Home() {
  const [recentJobs, setRecentJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRecentJobs();
  }, []);

  const loadRecentJobs = async () => {
    try {
      const jobs = await listJobs();
      setRecentJobs(jobs.slice(0, 5));
    } catch (err) {
      console.error('Failed to load jobs:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      pending: '#6b7280',
      downloading: '#3b82f6',
      transcribing: '#8b5cf6',
      analyzing: '#f59e0b',
      selecting: '#10b981',
      cutting: '#ef4444',
      subtitling: '#ec4899',
      uploading: '#06b6d4',
      completed: '#22c55e',
      failed: '#dc2626',
    };
    return colors[status] || '#6b7280';
  };

  return (
    <div className="home">
      <header className="hero-section">
        <h1>Video Clips Generator</h1>
        <p>Extract viral-worthy clips from YouTube videos using AI</p>
      </header>

      <section className="form-section">
        <JobForm />
      </section>

      <section className="recent-section">
        <h2>Recent Jobs</h2>
        {loading ? (
          <p className="loading">Loading...</p>
        ) : recentJobs.length === 0 ? (
          <p className="empty">No jobs yet. Submit a YouTube URL to get started!</p>
        ) : (
          <ul className="jobs-list">
            {recentJobs.map((job) => (
              <li key={job.job_id}>
                <Link to={`/jobs/${job.job_id}`}>
                  <span className="job-id">{job.job_id.slice(0, 8)}...</span>
                  <span
                    className="job-status"
                    style={{ backgroundColor: getStatusColor(job.status) }}
                  >
                    {job.status}
                  </span>
                  <span className="job-progress">{Math.round(job.progress * 100)}%</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export default Home;
