function ProgressBar({ progress, status, currentStep }) {
  const percentage = Math.round(progress * 100);

  const statusColors = {
    pending: '#6b7280',
    downloading: '#3b82f6',
    transcribing: '#8b5cf6',
    analyzing: '#f59e0b',
    selecting: '#10b981',
    cutting: '#ef4444',
    clip_metadata: '#a855f7',
    subtitling: '#ec4899',
    uploading: '#06b6d4',
    completed: '#22c55e',
    failed: '#dc2626',
  };

  const color = statusColors[status] || '#6b7280';

  return (
    <div className="progress-container">
      <div className="progress-header">
        <span className="status-badge" style={{ backgroundColor: color }}>
          {status.toUpperCase()}
        </span>
        <span className="percentage">{percentage}%</span>
      </div>

      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${percentage}%`, backgroundColor: color }}
        />
      </div>

      {currentStep && (
        <p className="current-step">{currentStep}</p>
      )}
    </div>
  );
}

export default ProgressBar;
