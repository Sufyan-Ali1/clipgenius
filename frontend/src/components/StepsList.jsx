import { useEffect, useState } from 'react';

// Estimated durations per step (in seconds)
const STEP_ESTIMATES = {
  downloading: 45,
  transcribing: 90,
  analyzing: 45,
  selecting: 10,
  cutting: 60,
  subtitling: 30,
};

// Step descriptions shown during processing
const STEP_DESCRIPTIONS = {
  downloading: 'Fetching video from source...',
  transcribing: 'Converting speech to text...',
  analyzing: 'Finding viral-worthy moments...',
  selecting: 'Choosing the best clips...',
  cutting: 'Extracting video segments...',
  subtitling: 'Burning captions into video...',
};

function formatTime(seconds) {
  if (seconds === null || seconds === undefined || seconds < 0) return '--:--';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function StepsList({
  currentStatus,
  addSubtitles,
  stepProgress = 0,
  stepMessage = null,
  elapsed = 0,
  stepRemaining = 0,
  totalRemaining = 0,
  stepDurations = {},
}) {
  // Local elapsed timer for smoother updates
  const [localElapsed, setLocalElapsed] = useState(elapsed);

  useEffect(() => {
    setLocalElapsed(elapsed);
  }, [elapsed, currentStatus]);

  // Increment local elapsed every second when step is active
  useEffect(() => {
    if (currentStatus && !['completed', 'failed', 'cancelled', 'pending'].includes(currentStatus)) {
      const interval = setInterval(() => {
        setLocalElapsed(prev => prev + 1);
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [currentStatus]);

  // Define all pipeline steps in order
  const allSteps = [
    { key: 'downloading', label: 'Download Video' },
    { key: 'transcribing', label: 'Transcribe Audio' },
    { key: 'analyzing', label: 'Analyze Content' },
    { key: 'selecting', label: 'Select Clips' },
    { key: 'cutting', label: 'Cut Clips' },
    { key: 'subtitling', label: 'Add Subtitles', showIf: addSubtitles === true },
  ];

  // Filter steps
  const steps = allSteps.filter(step => step.showIf === undefined || step.showIf === true);

  // Step order for determining status
  const stepOrder = steps.map(s => s.key);

  // Get step status (completed, current, pending, failed)
  const getStepStatus = (stepKey) => {
    if (currentStatus === 'completed') {
      return 'completed';
    }
    if (currentStatus === 'failed') {
      const currentIndex = stepOrder.indexOf(currentStatus);
      const stepIndex = stepOrder.indexOf(stepKey);
      if (stepIndex < currentIndex || currentIndex === -1) {
        return 'completed';
      }
      return stepIndex === currentIndex ? 'failed' : 'pending';
    }

    const currentIndex = stepOrder.indexOf(currentStatus);
    const stepIndex = stepOrder.indexOf(stepKey);

    if (currentIndex === -1) {
      return 'pending';
    }

    if (stepIndex < currentIndex) {
      return 'completed';
    } else if (stepIndex === currentIndex) {
      return 'current';
    } else {
      return 'pending';
    }
  };

  // Get time info for a step
  const getStepTimeInfo = (stepKey, status) => {
    if (status === 'completed') {
      const duration = stepDurations[stepKey];
      if (duration !== undefined) {
        return { text: `Done in ${formatTime(duration)}`, type: 'completed' };
      }
      return { text: 'Completed', type: 'completed' };
    }

    if (status === 'current') {
      const estimate = STEP_ESTIMATES[stepKey] || 60;
      const remaining = Math.max(0, estimate - localElapsed);
      return {
        text: `${formatTime(localElapsed)} elapsed`,
        remaining: `~${formatTime(remaining)} remaining`,
        type: 'current'
      };
    }

    if (status === 'pending') {
      const estimate = STEP_ESTIMATES[stepKey];
      if (estimate) {
        return { text: `~${formatTime(estimate)} estimated`, type: 'pending' };
      }
    }

    return { text: '', type: status };
  };

  return (
    <div className="steps-timeline">
      {/* Total remaining time header */}
      {totalRemaining > 0 && currentStatus !== 'completed' && currentStatus !== 'failed' && (
        <div className="steps-header">
          <span className="steps-remaining">~{formatTime(totalRemaining)} remaining</span>
        </div>
      )}

      <div className="steps-vertical">
        {steps.map((step, index) => {
          const status = getStepStatus(step.key);
          const timeInfo = getStepTimeInfo(step.key, status);
          const isCurrent = status === 'current';
          const description = isCurrent ? (stepMessage || STEP_DESCRIPTIONS[step.key]) : STEP_DESCRIPTIONS[step.key];

          return (
            <div key={step.key} className={`step-row step-${status}`}>
              {/* Connector line */}
              <div className="step-line-container">
                <div className={`step-line ${index === 0 ? 'step-line-first' : ''} ${index === steps.length - 1 ? 'step-line-last' : ''}`}>
                  <div className={`step-line-fill step-line-fill-${status}`}></div>
                </div>
              </div>

              {/* Step indicator */}
              <div className={`step-indicator-vertical ${isCurrent ? 'step-indicator-pulse' : ''}`}>
                {status === 'completed' ? (
                  <svg className="step-icon-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                ) : status === 'current' ? (
                  <div className="step-spinner-ring"></div>
                ) : status === 'failed' ? (
                  <svg className="step-icon-x" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                ) : (
                  <span className="step-number-vertical">{index + 1}</span>
                )}
              </div>

              {/* Step content */}
              <div className="step-content-vertical">
                <div className="step-header-row">
                  <span className="step-title">{step.label}</span>
                  <span className={`step-time step-time-${timeInfo.type}`}>
                    {timeInfo.text}
                  </span>
                </div>

                {/* Progress bar for current step */}
                {isCurrent && (
                  <div className="step-progress-container">
                    <div className="step-progress-bar">
                      <div
                        className="step-progress-fill"
                        style={{ width: `${Math.min(100, stepProgress * 100)}%` }}
                      ></div>
                    </div>
                    {timeInfo.remaining && (
                      <span className="step-time-remaining">{timeInfo.remaining}</span>
                    )}
                  </div>
                )}

                {/* Description */}
                {(isCurrent || status === 'pending') && (
                  <p className="step-description">
                    {isCurrent ? description : ''}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default StepsList;
