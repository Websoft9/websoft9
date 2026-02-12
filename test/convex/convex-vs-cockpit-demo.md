# Convex 替代 cockpit.js 技术方案

## 架构对比

### Before (cockpit.js)
```
Dashboard (Browser)
    ↓ WebSocket
cockpit-ws
    ↓ D-Bus
cockpit-bridge
    ↓ exec/file/dbus
Host System
```

### After (Convex)
```
Dashboard (Browser)
    ↓ WebSocket (Convex Subscriptions)
Convex Backend (Container)
    ↓ Node.js child_process / fs
Host System (via docker.sock + nsenter)
```

---

## 实现示例

### 1. 执行命令并实时推送输出

**Convex Schema**:
```typescript
// convex/schema.ts
import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  commandTasks: defineTable({
    command: v.string(),
    args: v.array(v.string()),
    status: v.union(v.literal("running"), v.literal("completed"), v.literal("failed")),
    output: v.string(),
    exitCode: v.optional(v.number()),
    createdAt: v.number(),
    updatedAt: v.number(),
  }).index("by_status", ["status"]),
});
```

**Backend - 执行命令**:
```typescript
// convex/system.ts
import { action } from "./_generated/server";
import { v } from "convex/values";
import { spawn } from "child_process";
import { internal } from "./_generated/api";

export const executeCommand = action({
  args: {
    command: v.string(),
    args: v.array(v.string()),
  },
  handler: async (ctx, { command, args }) => {
    // 创建任务记录
    const taskId = await ctx.runMutation(internal.system.createTask, {
      command,
      args,
    });

    // 异步执行命令
    const proc = spawn(command, args);
    let output = "";

    proc.stdout.on("data", async (data) => {
      output += data.toString();
      // 实时更新输出到数据库（触发前端 subscription）
      await ctx.runMutation(internal.system.appendOutput, {
        taskId,
        chunk: data.toString(),
      });
    });

    proc.stderr.on("data", async (data) => {
      output += data.toString();
      await ctx.runMutation(internal.system.appendOutput, {
        taskId,
        chunk: data.toString(),
      });
    });

    proc.on("close", async (code) => {
      await ctx.runMutation(internal.system.completeTask, {
        taskId,
        exitCode: code ?? 0,
      });
    });

    return { taskId };
  },
});

// Internal mutations
export const createTask = internalMutation({
  args: { command: v.string(), args: v.array(v.string()) },
  handler: async (ctx, { command, args }) => {
    return await ctx.db.insert("commandTasks", {
      command,
      args,
      status: "running",
      output: "",
      createdAt: Date.now(),
      updatedAt: Date.now(),
    });
  },
});

export const appendOutput = internalMutation({
  args: { taskId: v.id("commandTasks"), chunk: v.string() },
  handler: async (ctx, { taskId, chunk }) => {
    const task = await ctx.db.get(taskId);
    if (!task) return;
    
    await ctx.db.patch(taskId, {
      output: task.output + chunk,
      updatedAt: Date.now(),
    });
  },
});

export const completeTask = internalMutation({
  args: { taskId: v.id("commandTasks"), exitCode: v.number() },
  handler: async (ctx, { taskId, exitCode }) => {
    await ctx.db.patch(taskId, {
      status: exitCode === 0 ? "completed" : "failed",
      exitCode,
      updatedAt: Date.now(),
    });
  },
});
```

**Frontend - 实时订阅输出**:
```typescript
// Dashboard React Component
import { useQuery, useMutation } from "convex/react";
import { api } from "../convex/_generated/api";

export function CommandExecutor() {
  const executeCommand = useMutation(api.system.executeCommand);
  const [taskId, setTaskId] = useState<Id<"commandTasks"> | null>(null);
  
  // 实时订阅任务状态（替代 cockpit.js 的 WebSocket）
  const task = useQuery(api.system.getTask, taskId ? { taskId } : "skip");

  const runDockerCompose = async () => {
    const result = await executeCommand({
      command: "docker",
      args: ["compose", "up", "-d"],
    });
    setTaskId(result.taskId);
  };

  return (
    <div>
      <button onClick={runDockerCompose}>Deploy App</button>
      
      {task && (
        <div>
          <pre>{task.output}</pre>
          <div>Status: {task.status}</div>
          {task.exitCode !== undefined && <div>Exit Code: {task.exitCode}</div>}
        </div>
      )}
    </div>
  );
}
```

**Query - 订阅任务状态**:
```typescript
// convex/system.ts
export const getTask = query({
  args: { taskId: v.id("commandTasks") },
  handler: async (ctx, { taskId }) => {
    return await ctx.db.get(taskId);
  },
});
```

---

### 2. 文件操作

**Backend**:
```typescript
// convex/files.ts
import { action } from "./_generated/server";
import { v } from "convex/values";
import { promises as fs } from "fs";

export const readFile = action({
  args: { path: v.string() },
  handler: async (ctx, { path }) => {
    const content = await fs.readFile(path, "utf-8");
    return { content };
  },
});

export const writeFile = action({
  args: { path: v.string(), content: v.string() },
  handler: async (ctx, { path, content }) => {
    await fs.writeFile(path, content, "utf-8");
    return { success: true };
  },
});

export const listDirectory = action({
  args: { path: v.string() },
  handler: async (ctx, { path }) => {
    const entries = await fs.readdir(path, { withFileTypes: true });
    return entries.map(entry => ({
      name: entry.name,
      isDirectory: entry.isDirectory(),
    }));
  },
});
```

**Frontend**:
```typescript
export function FileEditor() {
  const readFile = useMutation(api.files.readFile);
  const writeFile = useMutation(api.files.writeFile);
  const [content, setContent] = useState("");

  const loadFile = async () => {
    const result = await readFile({ path: "/data/compose/app/docker-compose.yml" });
    setContent(result.content);
  };

  const saveFile = async () => {
    await writeFile({ 
      path: "/data/compose/app/docker-compose.yml",
      content 
    });
  };

  return (
    <div>
      <button onClick={loadFile}>Load</button>
      <textarea value={content} onChange={(e) => setContent(e.target.value)} />
      <button onClick={saveFile}>Save</button>
    </div>
  );
}
```

---

### 3. systemd 服务管理

**Backend**:
```typescript
// convex/systemd.ts
import { action } from "./_generated/server";
import { v } from "convex/values";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

export const restartService = action({
  args: { serviceName: v.string() },
  handler: async (ctx, { serviceName }) => {
    // 如果在容器内，需使用 nsenter
    const { stdout, stderr } = await execAsync(
      `/usr/local/bin/host-exec systemctl restart ${serviceName}`
    );
    return { output: stdout, error: stderr };
  },
});

export const getServiceStatus = action({
  args: { serviceName: v.string() },
  handler: async (ctx, { serviceName }) => {
    const { stdout } = await execAsync(
      `/usr/local/bin/host-exec systemctl status ${serviceName}`
    );
    return { status: stdout };
  },
});
```

---

### 4. 实时监控指标

**Backend - Scheduler 定期采集**:
```typescript
// convex/monitoring.ts
import { query, internalMutation } from "./_generated/server";
import { v } from "convex/values";

// Cron job: 每 5 秒采集一次指标
export const collectMetrics = internalMutation({
  handler: async (ctx) => {
    const cpuUsage = await getCpuUsage();
    const memUsage = await getMemUsage();
    
    await ctx.db.insert("metrics", {
      timestamp: Date.now(),
      cpu: cpuUsage,
      memory: memUsage,
    });
  },
});

// Frontend 订阅最新指标
export const latestMetrics = query({
  handler: async (ctx) => {
    const metrics = await ctx.db
      .query("metrics")
      .order("desc")
      .take(1);
    return metrics[0];
  },
});
```

**Frontend - 实时图表**:
```typescript
export function MetricsDashboard() {
  const metrics = useQuery(api.monitoring.latestMetrics);
  
  // metrics 每 5 秒自动更新（Convex 自动推送）
  return (
    <div>
      <div>CPU: {metrics?.cpu}%</div>
      <div>Memory: {metrics?.memory}%</div>
    </div>
  );
}
```

---

## 关键优势

### Convex vs cockpit.js

| 特性 | cockpit.js | Convex |
|------|------------|--------|
| **实时推送** | WebSocket | WebSocket (原生) |
| **命令执行** | cockpit-bridge | Node.js child_process |
| **文件操作** | cockpit.file() | Node.js fs |
| **认证** | PAM/SSH | Convex Auth (现代) |
| **数据持久化** | ❌ | ✅ (内置数据库) |
| **类型安全** | ❌ | ✅ (TypeScript) |
| **错误处理** | 手动 | 自动重试 |
| **离线支持** | ❌ | ✅ (Optimistic updates) |

---

## 部署要求

### docker-compose.yml
```yaml
services:
  websoft9:
    image: websoft9:latest
    privileged: true  # 如需 nsenter
    pid: host         # 如需 nsenter
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/host:ro
    environment:
      - CONVEX_DEPLOYMENT_URL=http://localhost:3210
```

### host-exec 脚本（如需宿主机访问）
```bash
#!/bin/bash
# /usr/local/bin/host-exec
nsenter --target 1 --mount --uts --ipc --net --pid -- "$@"
```

---

## 总结

**Convex 完全可以替代 cockpit.js**，并提供更多优势：
- ✅ 原生 TypeScript 支持
- ✅ 内置数据库和认证
- ✅ 更好的错误处理
- ✅ 现代化 DX（热重载、类型检查）
- ✅ 统一的后端架构（无需 Cockpit 依赖）

**唯一需要注意的**：
- 如需深度宿主机访问 → 使用 `privileged: true` + nsenter
- 如只需容器管理 → docker.sock 足够
