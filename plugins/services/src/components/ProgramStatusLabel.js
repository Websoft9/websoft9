import React from 'react';
import { Label } from '@patternfly/react-core';

/**
 * Status configuration for supervisord states
 * Maps statename to PatternFly Label color and display icon
 */
const STATUS_CONFIG = {
  RUNNING: { color: 'green', icon: '●', text: 'Running' },
  STOPPED: { color: 'grey', icon: '○', text: 'Stopped' },
  FATAL: { color: 'red', icon: '⚠', text: 'Fatal' },
  EXITED: { color: 'red', icon: '⚠', text: 'Exited' },
  STARTING: { color: 'orange', icon: '⟳', text: 'Starting' },
  STOPPING: { color: 'orange', icon: '⟳', text: 'Stopping' },
  BACKOFF: { color: 'orange', icon: '⟳', text: 'Backoff' },
  UNKNOWN: { color: 'grey', icon: '?', text: 'Unknown' }
};

/**
 * ProgramStatusLabel Component
 * Displays a colored PatternFly Label based on supervisord process state
 * 
 * @param {Object} props
 * @param {string} props.statename - Supervisord statename (RUNNING, STOPPED, etc.)
 */
function ProgramStatusLabel({ statename }) {
  const config = STATUS_CONFIG[statename] || STATUS_CONFIG.UNKNOWN;
  
  return (
    <Label 
      color={config.color} 
      aria-label={`Status: ${config.text}`}
    >
      <span className="status-icon" aria-hidden="true">{config.icon}</span>
      {config.text}
    </Label>
  );
}

export default ProgramStatusLabel;
