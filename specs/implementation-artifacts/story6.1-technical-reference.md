# Story 6.1: Technical Implementation Reference

**Parent Story**: [story6.1-service-list-status.md](story6.1-service-list-status.md)

This document provides detailed technical implementation guidance for developers.

## Table of Contents
1. [Supervisord Configuration](#supervisord-configuration)
2. [API Implementation](#api-implementation)
3. [Component Code](#component-code)
4. [XML-RPC Reference](#xml-rpc-reference)

---

## Supervisord Configuration

### Enable XML-RPC Server

Add to `/data/dev/websoft9/docker/cockpit/supervisord.conf`:

```ini
[inet_http_server]
port=127.0.0.1:9001
username=admin
password=%(ENV_ADMIN_PASSWORD)s

[supervisorctl]
serverurl=http://127.0.0.1:9001
username=admin
password=%(ENV_ADMIN_PASSWORD)s

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface
```

**Security Notes:**
- Listen only on localhost (127.0.0.1)
- Authentication required using ENV_ADMIN_PASSWORD
- No external access possible

---

## API Implementation

### File: `plugins/services/src/utils/api.js`

```javascript
const SUPERVISORD_URL = 'http://127.0.0.1:9001/RPC2';

// Get credentials from cockpit config or use defaults
// Note: In production, consider using cockpit.file() to read from a config file
// or implement proper credential management
const SUPERVISOR_USER = 'admin';
const SUPERVISOR_PASS = window.ADMIN_PASSWORD || 'admin'; // Set via index.html or config

/**
 * Fetch all supervisord program status
 * @returns {Promise<Array>} Array of program info objects
 */
export async function fetchSupervisordStatus() {
  const xmlRequest = `<?xml version="1.0"?>
<methodCall>
  <methodName>supervisor.getAllProcessInfo</methodName>
  <params></params>
</methodCall>`;

  const credentials = btoa(`${SUPERVISOR_USER}:${SUPERVISOR_PASS}`);
  
  const response = await fetch(SUPERVISORD_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'text/xml',
      'Authorization': `Basic ${credentials}`
    },
    body: xmlRequest
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const xmlText = await response.text();
  return parseXMLRPCResponse(xmlText);
}

/**
 * Parse XML-RPC response into program objects
 * @param {string} xmlResponse - Raw XML-RPC response
 * @returns {Array} Parsed program array
 */
function parseXMLRPCResponse(xmlResponse) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(xmlResponse, 'text/xml');
  
  // Check for XML-RPC faults
  const fault = doc.querySelector('fault');
  if (fault) {
    const faultString = doc.querySelector('fault member name:contains("faultString") ~ value string')?.textContent;
    throw new Error(`Supervisord error: ${faultString || 'Unknown fault'}`);
  }
  
  // Get all process structs from response array
  const values = doc.querySelectorAll('methodResponse > params > param > value > array > data > value');
  
  return Array.from(values).map(value => {
    const struct = parseStruct(value);
    return {
      name: struct.name,
      group: struct.group,
      statename: struct.statename,
      state: struct.state,
      pid: struct.pid > 0 ? struct.pid : null,
      uptime: calculateUptime(struct.now, struct.start, struct.stop),
      description: struct.description,
      spawnerr: struct.spawnerr
    };
  });
}

/**
 * Parse XML-RPC struct element to JavaScript object
 */
function parseStruct(valueNode) {
  const members = valueNode.querySelectorAll('struct > member');
  const obj = {};
  
  members.forEach(member => {
    const name = member.querySelector('name').textContent;
    const value = member.querySelector('value');
    obj[name] = parseValue(value);
  });
  
  return obj;
}

/**
 * Parse XML-RPC value (int, string, etc.)
 */
function parseValue(valueNode) {
  const int = valueNode.querySelector('int, i4');
  const string = valueNode.querySelector('string');
  const boolean = valueNode.querySelector('boolean');
  
  if (int) return parseInt(int.textContent);
  if (string) return string.textContent;
  if (boolean) return boolean.textContent === '1';
  
  return valueNode.textContent.trim();
}

/**
 * Calculate human-readable uptime from timestamps
 */
function calculateUptime(now, start, stop) {
  if (!start || start === 0) return null;
  
  const uptime = (stop > 0 ? stop : now) - start;
  const days = Math.floor(uptime / 86400);
  const hours = Math.floor((uptime % 86400) / 3600);
  const minutes = Math.floor((uptime % 3600) / 60);
  const seconds = uptime % 60;
  
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}
```

---

## Component Code

### File: `plugins/services/src/components/ServiceTable.js`

```javascript
import React from 'react';
import { Table, Thead, Tr, Th, Tbody, Td } from '@patternfly/react-table';
import ProgramStatusLabel from './ProgramStatusLabel';

function ServiceTable({ programs }) {
  if (!programs || programs.length === 0) {
    return null;
  }

  return (
    <Table variant="compact" aria-label="Supervisord programs table">
      <Thead>
        <Tr>
          <Th>Program Name</Th>
          <Th>Status</Th>
          <Th>PID</Th>
          <Th>Uptime</Th>
        </Tr>
      </Thead>
      <Tbody>
        {programs.map(program => (
          <Tr key={`${program.group}:${program.name}`}>
            <Td dataLabel="Program">{program.name}</Td>
            <Td dataLabel="Status">
              <ProgramStatusLabel statename={program.statename} />
            </Td>
            <Td dataLabel="PID">{program.pid || '-'}</Td>
            <Td dataLabel="Uptime">{program.uptime || '-'}</Td>
          </Tr>
        ))}
      </Tbody>
    </Table>
  );
}

export default ServiceTable;
```

### File: `plugins/services/src/components/ProgramStatusLabel.js`

```javascript
import React from 'react';
import { Label } from '@patternfly/react-core';

const STATUS_CONFIG = {
  RUNNING: { color: 'green', icon: '●' },
  STOPPED: { color: 'grey', icon: '○' },
  FATAL: { color: 'red', icon: '⚠' },
  EXITED: { color: 'red', icon: '⚠' },
  STARTING: { color: 'orange', icon: '⟳' },
  STOPPING: { color: 'orange', icon: '⟳' },
  BACKOFF: { color: 'orange', icon: '⟳' },
  UNKNOWN: { color: 'grey', icon: '?' }
};

function ProgramStatusLabel({ statename }) {
  const config = STATUS_CONFIG[statename] || STATUS_CONFIG.UNKNOWN;
  
  return (
    <Label color={config.color} aria-label={`Status: ${statename}`}>
      <span aria-hidden="true">{config.icon}</span> {statename}
    </Label>
  );
}

export default ProgramStatusLabel;
```

### File: `plugins/services/src/App.js`

```javascript
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
  EmptyStateIcon,
  EmptyStateBody,
  Title,
  Flex,
  FlexItem
} from '@patternfly/react-core';
import { SyncIcon, ListIcon } from '@patternfly/react-icons';
import ServiceTable from './components/ServiceTable';
import { fetchSupervisordStatus } from './utils/api';
import './App.css';

const REFRESH_INTERVAL = 5000; // 5 seconds

function App() {
  const [programs, setPrograms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const loadPrograms = useCallback(async (isManual = false) => {
    try {
      if (isManual) setRefreshing(true);
      else if (programs.length === 0) setLoading(true);
      
      setError(null);
      const data = await fetchSupervisordStatus();
      setPrograms(data);
    } catch (err) {
      console.error('Failed to fetch supervisord status:', err);
      setError(err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [programs.length]);

  useEffect(() => {
    loadPrograms();
    const interval = setInterval(() => loadPrograms(), REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [loadPrograms]);

  // Initial loading state
  if (loading && programs.length === 0) {
    return (
      <Page>
        <PageSection>
          <EmptyState>
            <EmptyStateIcon variant="container" component={Spinner} />
            <Title size="lg" headingLevel="h4">Loading services...</Title>
          </EmptyState>
        </PageSection>
      </Page>
    );
  }

  return (
    <Page>
      {/* Header Section */}
      <PageSection variant="light">
        <Card>
          <CardBody>
            <Flex justifyContent={{ default: 'justifyContentSpaceBetween' }} alignItems={{ default: 'alignItemsCenter' }}>
              <FlexItem>
                <Title headingLevel="h1" size="xl">Supervisord Services</Title>
              </FlexItem>
              <FlexItem>
                <Button 
                  variant="secondary" 
                  icon={<SyncIcon />}
                  onClick={() => loadPrograms(true)}
                  isLoading={refreshing}
                  isDisabled={refreshing}
                >
                  Refresh
                </Button>
              </FlexItem>
            </Flex>
          </CardBody>
        </Card>
      </PageSection>

      {/* Content Section */}
      <PageSection>
        {/* Error Alert */}
        {error && (
          <Alert 
            variant="danger" 
            title="Failed to load services" 
            isInline
            actionClose={<AlertActionCloseButton onClose={() => setError(null)} />}
          >
            {error}
          </Alert>
        )}

        {/* Empty State */}
        {!error && programs.length === 0 && (
          <EmptyState>
            <EmptyStateIcon icon={ListIcon} />
            <Title size="lg" headingLevel="h4">No Programs Configured</Title>
            <EmptyStateBody>
              Supervisord has no programs to manage
            </EmptyStateBody>
          </EmptyState>
        )}

        {/* Programs Table */}
        {!error && programs.length > 0 && (
          <Card>
            <CardBody>
              <ServiceTable programs={programs} />
            </CardBody>
          </Card>
        )}
      </PageSection>
    </Page>
  );
}

export default App;
```

---

## XML-RPC Reference

### Supervisord XML-RPC Documentation
- **Official Docs**: http://supervisord.org/api.html
- **Endpoint**: `http://127.0.0.1:9001/RPC2`
- **Protocol**: XML-RPC over HTTP
- **Authentication**: HTTP Basic Auth

### API Method: `supervisor.getAllProcessInfo()`

**Request:**
```xml
<?xml version="1.0"?>
<methodCall>
  <methodName>supervisor.getAllProcessInfo</methodName>
  <params></params>
</methodCall>
```

**Response Structure:**
```xml
<methodResponse>
  <params>
    <param>
      <value>
        <array>
          <data>
            <value>
              <struct>
                <member>
                  <name>name</name>
                  <value><string>apphub</string></value>
                </member>
                <member>
                  <name>group</name>
                  <value><string>apphub</string></value>
                </member>
                <member>
                  <name>statename</name>
                  <value><string>RUNNING</string></value>
                </member>
                <member>
                  <name>state</name>
                  <value><int>20</int></value>
                </member>
                <member>
                  <name>pid</name>
                  <value><int>1234</int></value>
                </member>
                <member>
                  <name>start</name>
                  <value><int>1707472000</int></value>
                </member>
                <member>
                  <name>stop</name>
                  <value><int>0</int></value>
                </member>
                <member>
                  <name>now</name>
                  <value><int>1707480123</int></value>
                </member>
                <member>
                  <name>description</name>
                  <value><string>pid 1234, uptime 2:15:23</string></value>
                </member>
                <member>
                  <name>spawnerr</name>
                  <value><string></string></value>
                </member>
                <member>
                  <name>exitstatus</name>
                  <value><int>0</int></value>
                </member>
              </struct>
            </value>
            <!-- More program entries... -->
          </data>
        </array>
      </value>
    </param>
  </params>
</methodResponse>
```

### State Codes & Names

| Code | Name | Meaning | Color |
|------|------|---------|-------|
| 0 | STOPPED | Not running | Grey |
| 10 | STARTING | Starting up | Orange |
| 20 | RUNNING | Running normally | Green |
| 30 | BACKOFF | Crashed, retrying | Orange |
| 40 | STOPPING | Shutting down | Orange |
| 100 | EXITED | Exited normally | Red |
| 200 | FATAL | Failed to start | Red |
| 1000 | UNKNOWN | Unknown state | Grey |

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Program name |
| `group` | string | Program group |
| `statename` | string | Human-readable state (use for display) |
| `state` | int | Numeric state code |
| `pid` | int | Process ID (0 if not running) |
| `start` | int | Unix timestamp when started |
| `stop` | int | Unix timestamp when stopped (0 if running) |
| `now` | int | Current server timestamp |
| `description` | string | Human-readable status message |
| `spawnerr` | string | Error message if spawn failed |
| `exitstatus` | int | Exit code of last termination |

### Testing XML-RPC Manually

**Using curl:**
```bash
curl -u admin:your_password \
  -H "Content-Type: text/xml" \
  -d '<?xml version="1.0"?>
<methodCall>
  <methodName>supervisor.getAllProcessInfo</methodName>
  <params></params>
</methodCall>' \
  http://127.0.0.1:9001/RPC2
```

**Using Python:**
```python
import xmlrpc.client

server = xmlrpc.client.ServerProxy(
    'http://admin:your_password@127.0.0.1:9001/RPC2'
)
programs = server.supervisor.getAllProcessInfo()
print(programs)
```

---

## Alternative Implementation: Backend Proxy

If XML parsing in frontend becomes problematic,create a simple proxy in apphub:

### File: `apphub/src/routers/supervisord.py`

```python
from fastapi import APIRouter, HTTPException
import xmlrpc.client

router = APIRouter(prefix="/api/supervisord", tags=["supervisord"])

@router.get("/status")
async def get_supervisord_status():
    """Get all supervisord program status"""
    try:
        server = xmlrpc.client.ServerProxy(
            'http://admin:PASSWORD@127.0.0.1:9001/RPC2'
        )
        programs = server.supervisor.getAllProcessInfo()
        return programs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

Then frontend becomes simpler:
```javascript
export async function fetchSupervisordStatus() {
  const response = await fetch('/api/supervisord/status');
  if (!response.ok) throw new Error('Failed to fetch status');
  return response.json();
}
```

**Decision**: Use direct XML-RPC for v1 to keep plugin independent. Can refactor later if needed.

---

## Notes for Developers

1. **Error Handling**: Always handle XML-RPC faults gracefully
2. **Authentication**: Use environment variables for credentials
3. **Performance**: 5-second auto-refresh is reasonable for typical usage
4. **Accessibility**: Include proper ARIA labels for screen readers
5. **Testing**: Test with various program states (RUNNING, STOPPED, FATAL, etc.)
6. **Future**: Story 6.2 will add control actions using these methods:
   - `supervisor.startProcess(name, wait=True)`
   - `supervisor.stopProcess(name, wait=True)`
   - `supervisor.restartProcess(name)` (not available, use stop + start)
