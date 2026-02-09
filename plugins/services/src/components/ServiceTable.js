import React, { useState, useCallback } from 'react';
import {
  Table,
  Thead,
  Tr,
  Th,
  Tbody,
  Td
} from '@patternfly/react-table';
import {
  Button,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  Spinner,
  CodeBlock,
  CodeBlockCode,
  Flex,
  FlexItem,
  Alert,
  AlertGroup,
  AlertActionCloseButton
} from '@patternfly/react-core';
import { ExclamationTriangleIcon } from '@patternfly/react-icons';
import cockpit from 'cockpit';
import ProgramStatusLabel from './ProgramStatusLabel';
import ServiceActions from './ServiceActions';
import { controlService } from '../utils/api';
import { UI_TIMINGS, FEATURES } from '../config';

/**
 * ServiceTable Component
 * Displays supervisord programs in a PatternFly table with control actions
 * 
 * @param {Object} props
 * @param {Array} props.programs - Array of program objects from supervisord
 * @param {Function} props.onRefresh - Callback to refresh data after operations
 */
function ServiceTable({ programs, onRefresh }) {
  const [logModal, setLogModal] = useState({ isOpen: false, title: '', content: '', loading: false });
  const [confirmModal, setConfirmModal] = useState({ isOpen: false, action: '', serviceName: '' });
  const [loadingService, setLoadingService] = useState(null);
  const [alerts, setAlerts] = useState([]);

  const openLog = useCallback(async (name, logFile) => {
    setLogModal({ isOpen: true, title: `${name} — ${logFile.split('/').pop()}`, content: '', loading: true });
    try {
      const output = await cockpit.spawn(['tail', '-n', '200', logFile], { err: 'out' });
      setLogModal(prev => ({ ...prev, content: output || '(empty log file)', loading: false }));
    } catch (err) {
      setLogModal(prev => ({ ...prev, content: `Failed to read log: ${err.message || err}`, loading: false }));
    }
  }, []);

  const closeLog = useCallback(() => {
    setLogModal({ isOpen: false, title: '', content: '', loading: false });
  }, []);

  // Alert/Toast management
  const addAlert = useCallback((variant, message) => {
    const id = Date.now();
    setAlerts(prev => [...prev, { id, variant, message }]);
    // Auto-dismiss after configured duration
    setTimeout(() => {
      setAlerts(prev => prev.filter(a => a.id !== id));
    }, UI_TIMINGS.TOAST_DURATION);
  }, []);

  const dismissAlert = useCallback((id) => {
    setAlerts(prev => prev.filter(a => a.id !== id));
  }, []);

  // Action execution
  const executeAction = useCallback(async (action, serviceName) => {
    if (FEATURES.ENABLE_DEBUG_LOGS) {
      console.log(`[ServiceTable] executeAction called: ${action} ${serviceName}`);
    }
    setLoadingService(serviceName);
    setConfirmModal({ isOpen: false, action: '', serviceName: '' });

    try {
      if (FEATURES.ENABLE_DEBUG_LOGS) {
        console.log(`[ServiceTable] Calling controlService...`);
      }
      const result = await controlService(serviceName, action);
      if (FEATURES.ENABLE_DEBUG_LOGS) {
        console.log(`[ServiceTable] controlService result:`, result);
      }
      
      if (result.success) {
        addAlert('success', result.message);
        // Refresh table after a brief delay to allow service state to update
        setTimeout(() => {
          if (onRefresh) onRefresh();
        }, UI_TIMINGS.REFRESH_DELAY);
      } else {
        addAlert('danger', result.message);
      }
    } catch (err) {
      if (FEATURES.ENABLE_DEBUG_LOGS) {
        console.error(`[ServiceTable] executeAction error:`, err);
      }
      addAlert('danger', `Operation failed: ${err.message || err}`);
    } finally {
      setLoadingService(null);
    }
  }, [onRefresh, addAlert]);

  // Action handlers
  const handleAction = useCallback((action, serviceName) => {
    // Show confirmation dialog for destructive actions
    if (action === 'stop' || action === 'restart') {
      setConfirmModal({ isOpen: true, action, serviceName });
    } else {
      // Execute start immediately
      executeAction(action, serviceName);
    }
  }, [executeAction]);

  const cancelAction = useCallback(() => {
    setConfirmModal({ isOpen: false, action: '', serviceName: '' });
  }, []);

  if (!programs || programs.length === 0) {
    return null;
  }

  // Column definitions
  const columns = ['Program', 'Status', 'PID', 'Ports', 'CPU', 'Memory', 'Uptime', 'Logs', 'Actions'];

  return (
    <>
      <Table 
        variant="compact" 
        aria-label="Supervisord programs table"
        isStickyHeader
      >
        <Thead>
          <Tr>
            {columns.map((col, index) => (
              <Th key={index}>{col}</Th>
            ))}
          </Tr>
        </Thead>
        <Tbody>
          {programs.map((program) => (
            <Tr key={`${program.group}:${program.name}`}>
              <Td dataLabel="Program">
                <strong>{program.name}</strong>
              </Td>
              <Td dataLabel="Status">
                <ProgramStatusLabel statename={program.statename} />
              </Td>
              <Td dataLabel="PID">
                {program.pid || '-'}
              </Td>
              <Td dataLabel="Ports">
                {program.ports && program.ports.length > 0 ? program.ports.join(', ') : '-'}
              </Td>
              <Td dataLabel="CPU">
                {program.cpu != null ? `${program.cpu}%` : '-'}
              </Td>
              <Td dataLabel="Memory">
                {program.memory || '-'}
              </Td>
              <Td dataLabel="Uptime">
                {program.uptime || '-'}
              </Td>
              <Td dataLabel="Logs">
                <Flex spaceItems={{ default: 'spaceItemsSm' }}>
                  {program.stdout_logfile && (
                    <FlexItem>
                      <Button
                        variant="link"
                        isInline
                        onClick={() => openLog(program.name, program.stdout_logfile)}
                      >
                        stdout
                      </Button>
                    </FlexItem>
                  )}
                  {program.stderr_logfile && (
                    <FlexItem>
                      <Button
                        variant="link"
                        isInline
                        onClick={() => openLog(program.name, program.stderr_logfile)}
                      >
                        stderr
                      </Button>
                    </FlexItem>
                  )}
                  {!program.stdout_logfile && !program.stderr_logfile && '-'}
                </Flex>
              </Td>
              <Td dataLabel="Actions">
                <ServiceActions 
                  program={program}
                  onAction={handleAction}
                  loadingService={loadingService}
                />
              </Td>
            </Tr>
          ))}
        </Tbody>
      </Table>

      {/* Alert/Toast Notifications */}
      <AlertGroup isToast isLiveRegion>
        {alerts.map(alert => (
          <Alert
            key={alert.id}
            variant={alert.variant}
            title={alert.message}
            actionClose={
              <AlertActionCloseButton onClose={() => dismissAlert(alert.id)} />
            }
          />
        ))}
      </AlertGroup>

      {/* Confirmation Dialog */}
      <Modal
        isOpen={confirmModal.isOpen}
        onClose={cancelAction}
        variant="small"
        titleIconVariant={ExclamationTriangleIcon}
        title={`${confirmModal.action.charAt(0).toUpperCase() + confirmModal.action.slice(1)} Service?`}
        aria-label="Confirm action"
      >
        <ModalBody>
          Are you sure you want to {confirmModal.action} <strong>{confirmModal.serviceName}</strong>?
          {confirmModal.action === 'restart' && (
            <p style={{ marginTop: '8px', color: 'var(--pf-v5-global--warning-color--100)' }}>
              This may cause brief downtime.
            </p>
          )}
        </ModalBody>
        <ModalFooter>
          <Button
            variant={confirmModal.action === 'stop' ? 'danger' : 'primary'}
            onClick={() => executeAction(confirmModal.action, confirmModal.serviceName)}
          >
            {confirmModal.action.charAt(0).toUpperCase() + confirmModal.action.slice(1)}
          </Button>
          <Button variant="link" onClick={cancelAction}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>

      {/* Log Viewer Modal */}
      <Modal
        isOpen={logModal.isOpen}
        onClose={closeLog}
        aria-label="Log viewer"
        variant="large"
      >
        <ModalHeader title={logModal.title} />
        <ModalBody>
          {logModal.loading ? (
            <Spinner size="lg" />
          ) : (
            <CodeBlock>
              <CodeBlockCode style={{ maxHeight: '60vh', overflow: 'auto', whiteSpace: 'pre' }}>
                {logModal.content}
              </CodeBlockCode>
            </CodeBlock>
          )}
        </ModalBody>
        <ModalFooter>
          <Button variant="secondary" onClick={closeLog}>Close</Button>
        </ModalFooter>
      </Modal>
    </>
  );
}

export default ServiceTable;
