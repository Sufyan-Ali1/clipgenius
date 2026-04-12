function StepsList({ currentStatus, addSubtitles }) {
  // Define all pipeline steps in order
  const allSteps = [
    { key: 'downloading', label: 'Downloading video', icon: '1' },
    { key: 'transcribing', label: 'Transcribing audio', icon: '2' },
    { key: 'analyzing', label: 'Analyzing content', icon: '3' },
    { key: 'selecting', label: 'Selecting clips', icon: '4' },
    { key: 'cutting', label: 'Cutting clips', icon: '5' },
    { key: 'subtitling', label: 'Adding subtitles', icon: '6', showIf: addSubtitles === true },
  ];

  // Filter steps - only show if showIf is undefined (always show) or true
  const steps = allSteps.filter(step => step.showIf === undefined || step.showIf === true);

  // Re-number steps after filtering
  steps.forEach((step, index) => {
    step.icon = String(index + 1);
  });

  // Step order for determining status
  const stepOrder = steps.map(s => s.key);

  // Get step status (completed, current, pending)
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
      return 'failed';
    }

    const currentIndex = stepOrder.indexOf(currentStatus);
    const stepIndex = stepOrder.indexOf(stepKey);

    if (currentIndex === -1) {
      // Status is pending or not in our list
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

  return (
    <div className="steps-list">
      {steps.map((step, index) => {
        const status = getStepStatus(step.key);
        return (
          <div key={step.key} className={`step-item step-${status}`}>
            <div className="step-indicator">
              {status === 'completed' ? (
                <span className="step-check">&#10003;</span>
              ) : status === 'current' ? (
                <span className="step-spinner"></span>
              ) : (
                <span className="step-number">{step.icon}</span>
              )}
            </div>
            <div className="step-content">
              <span className="step-label">{step.label}</span>
            </div>
            {index < steps.length - 1 && <div className="step-connector"></div>}
          </div>
        );
      })}
    </div>
  );
}

export default StepsList;
