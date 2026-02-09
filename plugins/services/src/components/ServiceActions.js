import React from 'react';
import { Button, Spinner } from '@patternfly/react-core';
import { PlayIcon, StopIcon, RedoIcon } from '@patternfly/react-icons';
import { PROTECTED_SERVICES } from '../config';
import './ServiceActions.css';

/**
 * ServiceActions Component
 * Renders action buttons for service control (start/stop/restart)
 * 
 * @param {Object} props
 * @param {Object} props.program - Program object with statename
 * @param {Function} props.onAction - Callback (action, serviceName)
 * @param {string|null} props.loadingService - Name of service currently being operated on
 */
function ServiceActions({ program, onAction, loadingService }) {
  // If this is a protected service, show nothing
  if (PROTECTED_SERVICES.includes(program.name)) {
    return <span className="service-actions-placeholder">-</span>;
  }

  const isRunning = program.statename === 'RUNNING';
  const isStopped = ['STOPPED', 'EXITED', 'FATAL'].includes(program.statename);
  const isLoading = loadingService === program.name;

  return (
    <div className="service-actions-container">
      {isLoading ? (
        <Spinner size="md" />
      ) : (
        <>
          <Button
            variant="plain"
            icon={<PlayIcon />}
            isDisabled={isRunning}
            onClick={() => onAction('start', program.name)}
            aria-label={`Start ${program.name}`}
            title="Start"
            className="service-actions-button"
          />
          <Button
            variant="plain"
            icon={<StopIcon />}
            isDisabled={isStopped}
            onClick={() => onAction('stop', program.name)}
            aria-label={`Stop ${program.name}`}
            title="Stop"
            className="service-actions-button"
          />
          <Button
            variant="plain"
            icon={<RedoIcon />}
            isDisabled={isStopped}
            onClick={() => onAction('restart', program.name)}
            aria-label={`Restart ${program.name}`}
            title="Restart"
            className="service-actions-button"
          />
        </>
      )}
    </div>
  );
}

export default ServiceActions;
