/**
 * Supervisord API Client
 * 
 * Uses cockpit.http() to call supervisord XML-RPC API
 * cockpit.http() runs server-side (not in browser), avoiding CORS issues
 */

import cockpit from 'cockpit';
import { SUPERVISORD_CONFIG, FEATURES } from '../config';

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

  const credentials = btoa(`${SUPERVISORD_CONFIG.username}:${SUPERVISORD_CONFIG.password}`);

  try {
    const http = cockpit.http({
      address: SUPERVISORD_CONFIG.address,
      port: SUPERVISORD_CONFIG.port
    });

    const response = await http.post('/RPC2', xmlRequest, {
      'Content-Type': 'text/xml',
      'Authorization': `Basic ${credentials}`
    });

    return parseXMLRPCResponse(response);
  } catch (err) {
    const msg = err.message || err.problem || String(err);
    throw new Error(`Failed to connect to supervisord: ${msg}`);
  }
}

/**
 * Parse XML-RPC response into program objects
 * @param {string} xmlResponse - Raw XML-RPC response text
 * @returns {Array} Parsed program array
 */
function parseXMLRPCResponse(xmlResponse) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(xmlResponse, 'text/xml');

  // Check for XML-RPC faults
  const fault = doc.querySelector('fault');
  if (fault) {
    const faultString = fault.querySelector('member value string')?.textContent || 'Unknown fault';
    throw new Error(`Supervisord error: ${faultString}`);
  }

  // Response: methodResponse > params > param > value > array > data > value[]
  const dataElement = doc.querySelector('methodResponse > params > param > value > array > data');
  if (!dataElement) {
    return [];
  }

  const values = dataElement.querySelectorAll(':scope > value');

  return Array.from(values).map(value => {
    const struct = parseStruct(value);
    return {
      name: struct.name || 'unknown',
      group: struct.group || struct.name || 'unknown',
      statename: struct.statename || 'UNKNOWN',
      state: struct.state || 0,
      pid: struct.pid > 0 ? struct.pid : null,
      uptime: calculateUptime(struct.now, struct.start, struct.stop, struct.statename),
      description: struct.description || '',
      spawnerr: struct.spawnerr || '',
      stdout_logfile: struct.stdout_logfile || '',
      stderr_logfile: struct.stderr_logfile || ''
    };
  });
}

/**
 * Parse XML-RPC struct element to JavaScript object
 */
function parseStruct(valueNode) {
  const structNode = valueNode.querySelector('struct');
  if (!structNode) return {};

  const members = structNode.querySelectorAll(':scope > member');
  const obj = {};

  members.forEach(member => {
    const name = member.querySelector('name')?.textContent;
    const value = member.querySelector('value');
    if (name && value) {
      obj[name] = parseValue(value);
    }
  });

  return obj;
}

/**
 * Parse XML-RPC value (int, string, boolean, etc.)
 */
function parseValue(valueNode) {
  const int = valueNode.querySelector('int, i4, i8');
  const str = valueNode.querySelector('string');
  const bool = valueNode.querySelector('boolean');
  const dbl = valueNode.querySelector('double');

  if (int) return parseInt(int.textContent, 10);
  if (dbl) return parseFloat(dbl.textContent);
  if (str) return str.textContent;
  if (bool) return bool.textContent === '1';

  const text = valueNode.textContent?.trim();
  if (/^-?\d+$/.test(text)) return parseInt(text, 10);
  return text || '';
}

/**
 * Calculate human-readable uptime
 */
function calculateUptime(now, start, stop, statename) {
  if (statename !== 'RUNNING' || !start || start === 0) return null;

  const uptime = (stop > 0 ? stop : now) - start;
  if (uptime < 0) return null;

  const days = Math.floor(uptime / 86400);
  const hours = Math.floor((uptime % 86400) / 3600);
  const minutes = Math.floor((uptime % 3600) / 60);
  const seconds = uptime % 60;

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

/**
 * Fetch resource usage (CPU%, Memory) for given PIDs
 * Uses cockpit.spawn to run ps inside the container
 * @param {number[]} pids - Array of PIDs to query
 * @returns {Promise<Object>} Map of pid -> { cpu, memory }
 */
export async function fetchProcessResources(pids) {
  if (!pids || pids.length === 0) return {};

  try {
    const output = await cockpit.spawn(
      ['ps', '-o', 'pid,pcpu,rss', '--no-headers', '-p', pids.join(',')],
      { err: 'ignore' }
    );

    const resources = {};
    const lines = output.trim().split('\n');
    for (const line of lines) {
      const parts = line.trim().split(/\s+/);
      if (parts.length >= 3) {
        const pid = parseInt(parts[0], 10);
        const cpu = parseFloat(parts[1]);
        const rssKB = parseInt(parts[2], 10);
        resources[pid] = {
          cpu: cpu,
          memory: formatMemory(rssKB),
          rssKB: rssKB
        };
      }
    }
    return resources;
  } catch {
    // ps may fail if processes exited between calls
    return {};
  }
}

/**
 * Format RSS (in KB) to human-readable string
 */
function formatMemory(rssKB) {
  if (rssKB >= 1048576) {
    return `${(rssKB / 1048576).toFixed(1)} GB`;
  } else if (rssKB >= 1024) {
    return `${(rssKB / 1024).toFixed(1)} MB`;
  }
  return `${rssKB} KB`;
}

/**
 * Fetch listening ports for given PIDs
 * Strategy: 
 *   1. Parse /proc/<pid>/cmdline for --port, --bind, -p flags
 *   2. Use ss -tlnp to match PIDs directly where available
 *   3. For well-known services, apply default ports as fallback
 * @param {number[]} pids - Array of PIDs to query
 * @returns {Promise<Object>} Map of pid -> ports string array
 */
export async function fetchProcessPorts(pids) {
  if (!pids || pids.length === 0) return {};

  const portsByPid = {};

  const defaultPorts = {
    'nginx': ['80'],
    'sshd': ['22'],
    'dbus-daemon': [],
    'gitea': ['3000'],
    'cron': [],
  };

  try {
    // 1. ss -tlnpH for PID-based matching
    const ssPorts = {};
    try {
      const ssOutput = await cockpit.spawn(['ss', '-tlnpH'], { err: 'ignore' });
      for (const line of ssOutput.trim().split('\n')) {
        if (!line.includes('LISTEN')) continue;
        const pidMatch = line.match(/pid=(\d+)/);
        if (!pidMatch) continue;
        // ss format: "LISTEN 0 128 0.0.0.0:22 0.0.0.0:*"
        // Local address:port is the 4th whitespace-separated field
        const fields = line.trim().split(/\s+/);
        // fields: [LISTEN, recv-q, send-q, local_addr:port, peer_addr:port, ...]
        const localField = fields[3] || '';
        const lastColon = localField.lastIndexOf(':');
        if (lastColon >= 0) {
          const port = localField.substring(lastColon + 1);
          if (/^\d+$/.test(port)) {
            const pid = parseInt(pidMatch[1], 10);
            if (!ssPorts[pid]) ssPorts[pid] = [];
            if (!ssPorts[pid].includes(port)) ssPorts[pid].push(port);
          }
        }
      }
    } catch { /* ignore */ }

    // 2. For each PID: cmdline parsing + ss + defaults
    for (const pid of pids) {
      const ports = [];

      if (ssPorts[pid]) {
        ports.push(...ssPorts[pid]);
      }

      try {
        const cmdline = await cockpit.spawn(
          ['sh', '-c', `cat /proc/${pid}/cmdline | tr '\\0' ' '`],
          { err: 'ignore' }
        );
        const args = cmdline.trim().split(/\s+/).filter(Boolean);
        const cmdName = (args[0] || '').split('/').pop();

        for (let i = 0; i < args.length; i++) {
          const arg = args[i];
          // --port=8080 or --port 8080
          const portEq = arg.match(/^--port=(\d+)$/);
          if (portEq) {
            if (!ports.includes(portEq[1])) ports.push(portEq[1]);
            continue;
          }
          if (arg === '--port' && args[i + 1] && /^\d+$/.test(args[i + 1])) {
            if (!ports.includes(args[i + 1])) ports.push(args[i + 1]);
            continue;
          }
          // -p 8080
          if (arg === '-p' && args[i + 1] && /^\d+$/.test(args[i + 1])) {
            if (!ports.includes(args[i + 1])) ports.push(args[i + 1]);
            continue;
          }
          // --bind :9000 or --bind=:9000
          if (arg.startsWith('--bind')) {
            const bindVal = arg.includes('=') ? arg.split('=')[1] : args[i + 1];
            if (bindVal) {
              const bm = bindVal.match(/:(\d+)/);
              if (bm && !ports.includes(bm[1])) ports.push(bm[1]);
            }
            continue;
          }
        }

        // Fallback to well-known defaults
        if (ports.length === 0 && defaultPorts[cmdName]) {
          ports.push(...defaultPorts[cmdName]);
        }
      } catch { /* process may have exited */ }

      if (ports.length > 0) {
        portsByPid[pid] = ports;
      }
    }

    return portsByPid;
  } catch {
    return {};
  }
}

/**
 * Control service operations (start, stop, restart)
 * Uses supervisor XML-RPC methods
 * @param {string} serviceName - Service/program name
 * @param {string} action - 'start' | 'stop' | 'restart'
 * @returns {Promise<{success: boolean, message: string}>}
 */
export async function controlService(serviceName, action) {
  const credentials = btoa(`${SUPERVISORD_CONFIG.username}:${SUPERVISORD_CONFIG.password}`);

  if (FEATURES.ENABLE_DEBUG_LOGS) {
    console.log(`[controlService] Starting: ${action} ${serviceName}`);
  }

  try {
    const http = cockpit.http({
      address: SUPERVISORD_CONFIG.address,
      port: SUPERVISORD_CONFIG.port
    });

    let methodName;

    switch (action) {
      case 'start':
        methodName = 'supervisor.startProcess';
        break;
      case 'stop':
        methodName = 'supervisor.stopProcess';
        break;
      case 'restart':
        // Supervisor XML-RPC doesn't have reliable restartProcess, use stop then start
        await callSupervisorMethod(http, credentials, 'supervisor.stopProcess', serviceName);
        await callSupervisorMethod(http, credentials, 'supervisor.startProcess', serviceName);
        if (FEATURES.ENABLE_DEBUG_LOGS) {
          console.log(`[controlService] Restart completed for ${serviceName}`);
        }
        return { success: true, message: `Service ${serviceName} restarted successfully` };
      default:
        throw new Error(`Unknown action: ${action}`);
    }

    await callSupervisorMethod(http, credentials, methodName, serviceName);
    if (FEATURES.ENABLE_DEBUG_LOGS) {
      console.log(`[controlService] ${action} completed for ${serviceName}`);
    }
    return { 
      success: true, 
      message: `Service ${serviceName} ${action}${action.endsWith('e') ? 'd' : 'ed'} successfully` 
    };

  } catch (err) {
    const msg = err.message || err.problem || String(err);
    console.error(`[controlService] ERROR (${action} ${serviceName}):`, msg, err);
    return { 
      success: false, 
      message: `Failed to ${action} service: ${msg}` 
    };
  }
}

/**
 * Helper to call a supervisor XML-RPC method
 */
async function callSupervisorMethod(http, credentials, methodName, serviceName) {
  const xmlRequest = `<?xml version="1.0"?>
<methodCall>
  <methodName>${methodName}</methodName>
  <params>
    <param><value><string>${serviceName}</string></value></param>
    <param><value><boolean>1</boolean></value></param>
  </params>
</methodCall>`;

  if (FEATURES.ENABLE_DEBUG_LOGS) {
    console.log(`[controlService] Calling ${methodName}(${serviceName})...`);
    console.log(`[controlService] XML Request:`, xmlRequest);
  }

  const response = await http.post('/RPC2', xmlRequest, {
    'Content-Type': 'text/xml',
    'Authorization': `Basic ${credentials}`
  });

  if (FEATURES.ENABLE_DEBUG_LOGS) {
    console.log(`[controlService] Response received:`, response);
  }

  // Check for XML-RPC fault
  const parser = new DOMParser();
  const doc = parser.parseFromString(response, 'text/xml');
  const fault = doc.querySelector('fault');
  if (fault) {
    const faultString = fault.querySelector('member value string')?.textContent || 'Unknown fault';
    if (FEATURES.ENABLE_DEBUG_LOGS) {
      console.error(`[controlService] XML-RPC Fault:`, faultString);
    }
    throw new Error(faultString);
  }

  if (FEATURES.ENABLE_DEBUG_LOGS) {
    console.log(`[controlService] ${methodName}(${serviceName}) completed successfully`);
  }
}

/**
 * Export for testing
 */
export { formatMemory };

export const _internal = {
  parseXMLRPCResponse,
  parseStruct,
  parseValue,
  calculateUptime,
  formatMemory
};
