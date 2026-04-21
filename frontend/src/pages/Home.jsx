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
      const response = await listJobs();
      // Handle both array and object response formats
      const jobs = Array.isArray(response) ? response : (response.jobs || []);
      setRecentJobs(Array.isArray(jobs) ? jobs.slice(0, 6) : []);
    } catch (err) {
      console.error('Failed to load jobs:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      pending: '#6b7280',
      uploading_video: '#8b5cf6',
      downloading: '#3b82f6',
      transcribing: '#8b5cf6',
      analyzing: '#f59e0b',
      selecting: '#10b981',
      cutting: '#ec4899',
      subtitling: '#06b6d4',
      uploading: '#06b6d4',
      completed: '#22c55e',
      failed: '#dc2626',
    };
    return colors[status] || '#6b7280';
  };

  const formatSource = (source) => {
    if (!source) return 'Unknown';
    if (source.includes('youtube.com') || source.includes('youtu.be')) {
      return 'YouTube Video';
    }
    const filename = source.split(/[/\\]/).pop();
    return filename.length > 25 ? filename.slice(0, 22) + '...' : filename;
  };

  return (
    <div className="home">
      {/* Hero Section */}
      <section className="hero">
        <div className="hero-glow"></div>
        <h1 className="hero-title">
          Turn Videos into <span className="gradient-text">Viral Clips</span>
        </h1>
        <p className="hero-subtitle">
          AI-powered tool that extracts the most engaging moments from your videos
          for TikTok, YouTube Shorts, and Instagram Reels
        </p>
        <div className="hero-stats">
          <div className="stat-item">
            <span className="stat-number">10x</span>
            <span className="stat-label">Faster than manual</span>
          </div>
          <div className="stat-item">
            <span className="stat-number">AI</span>
            <span className="stat-label">Viral detection</span>
          </div>
          <div className="stat-item">
            <span className="stat-number">60-100s</span>
            <span className="stat-label">Optimal length</span>
          </div>
        </div>
      </section>

      {/* Form Section */}
      <section className="form-section">
        <h2 className="section-title">Get Started</h2>
        <div className="form-card">
          <JobForm />
        </div>
      </section>

      {/* How It Works */}
      <section className="how-it-works">
        <h2 className="section-title">How It Works</h2>
        <div className="steps-row">
          <div className="hiw-step">
            <div className="hiw-step-icon">1</div>
            <h3>Upload Video</h3>
            <p>Paste a YouTube URL or upload your video file directly</p>
          </div>
          <div className="hiw-step-arrow">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </div>
          <div className="hiw-step">
            <div className="hiw-step-icon">2</div>
            <h3>AI Analysis</h3>
            <p>Our AI finds the most viral-worthy moments automatically</p>
          </div>
          <div className="hiw-step-arrow">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </div>
          <div className="hiw-step">
            <div className="hiw-step-icon">3</div>
            <h3>Get Clips</h3>
            <p>Download ready-to-post clips with captions and hashtags</p>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="features">
        <h2 className="section-title">Powerful Features</h2>
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2a4 4 0 0 1 4 4v1a3 3 0 0 1 3 3v1a2 2 0 0 1-2 2h-1v5a4 4 0 0 1-8 0v-5H7a2 2 0 0 1-2-2v-1a3 3 0 0 1 3-3V6a4 4 0 0 1 4-4z" />
                <circle cx="9" cy="10" r="1" fill="currentColor" />
                <circle cx="15" cy="10" r="1" fill="currentColor" />
              </svg>
            </div>
            <h3>AI-Powered</h3>
            <p>LLM analyzes your content to identify the most engaging and viral-worthy moments</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <path d="M14 2v6h6" />
                <path d="M16 13H8M16 17H8M10 9H8" />
              </svg>
            </div>
            <h3>Auto Subtitles</h3>
            <p>Whisper transcription with professional burned-in captions for accessibility</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="5" y="2" width="14" height="20" rx="2" />
                <line x1="12" y1="18" x2="12" y2="18.01" strokeWidth="3" strokeLinecap="round" />
              </svg>
            </div>
            <h3>Vertical Mode</h3>
            <p>9:16 format perfectly optimized for TikTok, Shorts, and Reels</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <path d="M14 2v6h6" />
                <path d="M12 18v-6M9 15l3 3 3-3" />
              </svg>
            </div>
            <h3>Manual Mode</h3>
            <p>Specify exact timestamps when you know precisely which moments you want</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" />
              </svg>
            </div>
            <h3>Cloud Sync</h3>
            <p>Auto-upload finished clips directly to your Google Drive folder</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
            </div>
            <h3>Fast Processing</h3>
            <p>GPU acceleration and parallel processing for quick turnaround times</p>
          </div>
        </div>
      </section>

      {/* Recent Jobs */}
      <section className="recent-jobs">
        <div className="section-header">
          <h2 className="section-title">Recent Jobs</h2>
        </div>
        {loading ? (
          <div className="jobs-loading">
            <div className="loading-spinner-small"></div>
            <span>Loading recent jobs...</span>
          </div>
        ) : recentJobs.length === 0 ? (
          <div className="jobs-empty">
            <div className="empty-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <path d="M12 8v8M8 12h8" />
              </svg>
            </div>
            <p>No jobs yet. Submit a video above to get started!</p>
          </div>
        ) : (
          <div className="jobs-grid">
            {recentJobs.map((job) => (
              <Link to={`/jobs/${job.job_id}`} key={job.job_id} className="job-card">
                <div className="job-card-header">
                  <span className="job-card-id">{job.job_id.slice(0, 8)}</span>
                  <span
                    className="job-card-status"
                    style={{ backgroundColor: getStatusColor(job.status) }}
                  >
                    {job.status.replace('_', ' ')}
                  </span>
                </div>
                <div className="job-card-progress">
                  <div
                    className="job-card-progress-fill"
                    style={{ width: `${Math.round(job.progress * 100)}%` }}
                  ></div>
                </div>
                <div className="job-card-meta">
                  <span className="job-card-source">{formatSource(job.input_source)}</span>
                  <span className="job-card-percent">{Math.round(job.progress * 100)}%</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default Home;
