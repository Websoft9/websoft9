import React, { useState, useEffect, useCallback } from 'react';
import {
  Page,
  PageSection,
  Card,
  CardBody,
  Button,
  Spinner,
  Alert,
  AlertActionCloseButton,
  EmptyState,
  EmptyStateBody,
  Flex,
  FlexItem,
  Title
} from '@patternfly/react-core';
import { SyncIcon, CheckCircleIcon, ExclamationCircleIcon, PauseCircleIcon, CubesIcon } from '@patternfly/react-icons';
import ServiceTable from './components/ServiceTable';
import { fetchSupervisordStatus, fetchProcessResources, fetchProcessPorts, formatMemory } from './utils/api';
import { UI_TIMINGS } from './config';
import './App.css';

/**
 * Main App Component for Services Plugin
 * Displays supervisord programs with real-time status monitoring
 */
function App() {
  // State management
  const [programs, setPrograms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  /**
   * Load programs from supervisord XML-RPC API
   * @param {boolean} isManual - True if triggered by manual refresh button
   */
  const loadPrograms = useCallback(async (isManual = false) => {
    try {
      // Show appropriate loading state
      if (isManual) {
        setRefreshing(true);
      } else if (programs.length === 0) {
        setLoading(true);
      }
      
      setError(null);
      const data = await fetchSupervisordStatus();

      // Fetch resource usage for running processes
      const runningPids = data.filter(p => p.pid).map(p => p.pid);
      const [resources, ports] = await Promise.all([
        fetchProcessResources(runningPids),
        fetchProcessPorts(runningPids)
      ]);

      // Merge resource data into programs
      const enriched = data.map(p => {
        const base = { ...p, cpu: null, memory: null, rssKB: 0, ports: [] };
        if (p.pid) {
          if (resources[p.pid]) {
            base.cpu = resources[p.pid].cpu;
            base.memory = resources[p.pid].memory;
            base.rssKB = resources[p.pid].rssKB;
          }
          if (ports[p.pid]) {
            base.ports = ports[p.pid];
          }
        }
        return base;
      });
      setPrograms(enriched);
    } catch (err) {
      console.error('Failed to fetch supervisord status:', err);
      setError(err.message || 'Failed to connect to supervisord');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [programs.length]);

  /**
   * Handle manual refresh button click
   */
  const handleRefresh = () => {
    loadPrograms(true);
  };

  /**
   * Dismiss error alert
   */
  const dismissError = () => {
    setError(null);
  };

  // Initial load and auto-refresh setup
  useEffect(() => {
    loadPrograms();
    
    // Set up auto-refresh interval
    const interval = setInterval(() => {
      loadPrograms();
    }, UI_TIMINGS.AUTO_REFRESH_INTERVAL);
    
    // Cleanup on unmount
    return () => clearInterval(interval);
  }, [loadPrograms]);

  // ========== Summary Stats ==========
  const totalCount = programs.length;
  const runningCount = programs.filter(p => p.statename === 'RUNNING').length;
  const stoppedCount = programs.filter(p => p.statename === 'STOPPED').length;
  const errorCount = programs.filter(p => ['FATAL', 'EXITED', 'BACKOFF'].includes(p.statename)).length;
  const totalCpu = programs.reduce((sum, p) => sum + (p.cpu || 0), 0);
  const totalRssKB = programs.reduce((sum, p) => sum + (p.rssKB || 0), 0);

  // ========== Render States ==========

  // Initial loading state (full page spinner)
  if (loading && programs.length === 0 && !error) {
    return (
      <Page className="pf-m-no-sidebar">
        <PageSection isFilled>
          <EmptyState titleText="Loading services..." headingLevel="h4">
            <Spinner size="xl" />
            <EmptyStateBody>
              Connecting to supervisord...
            </EmptyStateBody>
          </EmptyState>
        </PageSection>
      </Page>
    );
  }

  return (
    <Page className="pf-m-no-sidebar">
      {/* Header Section */}
      <PageSection variant="light">
        <Card>
          <CardBody>
            <Flex 
              justifyContent={{ default: 'justifyContentSpaceBetween' }} 
              alignItems={{ default: 'alignItemsCenter' }}
            >
              <FlexItem>
                <Title headingLevel="h1" size="xl">
                  Supervisord Services
                </Title>
              </FlexItem>
              <FlexItem>
                <Button 
                  variant="secondary" 
                  icon={<SyncIcon />}
                  onClick={handleRefresh}
                  isLoading={refreshing}
                  isDisabled={refreshing}
                  aria-label="Refresh services list"
                >
                  Refresh
                </Button>
              </FlexItem>
            </Flex>
          </CardBody>
        </Card>

        {/* Summary Stats */}
        {programs.length > 0 && (
          <Flex className="services-stats" spaceItems={{ default: 'spaceItemsLg' }} style={{ marginTop: 'var(--pf-t--global--spacer--md)' }}>
            <FlexItem>
              <Card isCompact isPlain>
                <CardBody>
                  <Flex alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsSm' }}>
                    <CubesIcon color="var(--pf-t--global--icon--color--regular)" />
                    <span><strong>{totalCount}</strong> Total</span>
                  </Flex>
                </CardBody>
              </Card>
            </FlexItem>
            <FlexItem>
              <Card isCompact isPlain>
                <CardBody>
                  <Flex alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsSm' }}>
                    <CheckCircleIcon color="var(--pf-t--global--icon--color--status--success--default)" />
                    <span><strong>{runningCount}</strong> Running</span>
                  </Flex>
                </CardBody>
              </Card>
            </FlexItem>
            {stoppedCount > 0 && (
              <FlexItem>
                <Card isCompact isPlain>
                  <CardBody>
                    <Flex alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsSm' }}>
                      <PauseCircleIcon color="var(--pf-t--global--icon--color--status--info--default)" />
                      <span><strong>{stoppedCount}</strong> Stopped</span>
                    </Flex>
                  </CardBody>
                </Card>
              </FlexItem>
            )}
            {errorCount > 0 && (
              <FlexItem>
                <Card isCompact isPlain>
                  <CardBody>
                    <Flex alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsSm' }}>
                      <ExclamationCircleIcon color="var(--pf-t--global--icon--color--status--danger--default)" />
                      <span><strong>{errorCount}</strong> Error</span>
                    </Flex>
                  </CardBody>
                </Card>
              </FlexItem>
            )}
            <FlexItem>
              <Card isCompact isPlain>
                <CardBody>
                  CPU: <strong>{totalCpu.toFixed(1)}%</strong>
                </CardBody>
              </Card>
            </FlexItem>
            <FlexItem>
              <Card isCompact isPlain>
                <CardBody>
                  Memory: <strong>{formatMemory(totalRssKB)}</strong>
                </CardBody>
              </Card>
            </FlexItem>
          </Flex>
        )}
      </PageSection>

      {/* Content Section */}
      <PageSection>
        {/* Error Alert */}
        {error && (
          <Alert 
            variant="danger" 
            title="Failed to load services"
            className="services-alert"
            isInline
            actionClose={
              <AlertActionCloseButton onClose={dismissError} />
            }
          >
            {error}
          </Alert>
        )}

        {/* Empty State - No programs configured */}
        {!error && programs.length === 0 && (
          <Card>
            <CardBody>
              <EmptyState titleText="No Programs Configured" headingLevel="h4">
                <EmptyStateBody>
                  Supervisord has no programs to manage.
                  <br />
                  Add program sections to supervisord.conf to get started.
                </EmptyStateBody>
              </EmptyState>
            </CardBody>
          </Card>
        )}

        {/* Programs Table */}
        {!error && programs.length > 0 && (
          <Card>
            <CardBody>
              <ServiceTable programs={programs} onRefresh={() => loadPrograms()} />
            </CardBody>
          </Card>
        )}
      </PageSection>
    </Page>
  );
}

export default App;
