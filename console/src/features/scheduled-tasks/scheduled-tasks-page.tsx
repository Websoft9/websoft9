import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControlLabel,
    IconButton,
    InputAdornment,
    MenuItem,
    Paper,
    Stack,
    Switch,
    Tab,
    Tabs,
    SvgIcon,
    TextField,
    Tooltip,
    Typography,
} from "@mui/material";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAppColorMode } from "../../app/providers/color-mode";
import { PageDescriptionHeader } from "../../shared/design-system/page-description-header";
import {
    SurfaceFeedbackToast,
    SurfaceStateCard,
} from "../../shared/design-system/standard-surfaces";
import { getSurfacePalette } from "../../shared/design-system/surface-theme";
import "./scheduled-tasks-page.css";

type ScheduledTask = {
    task_id: string;
    name: string;
    target: "container" | "host";
    profile_id: string | null;
    schedule: string;
    timezone: string;
    command: string;
    execution_mode: "command" | "path" | "upload";
    script_path: string | null;
    script_name: string | null;
    timeout_seconds: number;
    retry_count: number;
    enabled: boolean;
    last_run_at: string | null;
    last_status: "never" | "running" | "success" | "failed" | "skipped";
    sync_status: "synced" | "failed" | "unreachable";
    execution_path: string;
    syncing?: boolean;
    next_run_at: string | null;
    created_at: string;
    updated_at: string;
};

type TaskForm = Pick<
    ScheduledTask,
    | "name"
    | "target"
    | "profile_id"
    | "schedule"
    | "command"
    | "execution_mode"
    | "script_path"
    | "timeout_seconds"
    | "retry_count"
    | "enabled"
>;
type ScheduleMode =
    | "hourly"
    | "daily"
    | "weekly"
    | "monthly"
    | "intervalMinutes"
    | "intervalHours"
    | "custom";
type TimeoutUnit = "seconds" | "minutes" | "hours";
type StatusFilter = "all" | ScheduledTask["last_status"];
type EnabledFilter = "all" | "enabled" | "disabled";

type SavedHostProfile = {
    profile_id: string;
    name: string;
    host: string;
    username: string;
};

type ScheduledTaskRun = {
    run_id: string;
    task_id: string;
    started_at: string;
    finished_at: string | null;
    status: ScheduledTask["last_status"];
    exit_code: number | null;
    trigger: "cron" | "manual";
    log_path: string;
};

type ScheduledTasksResponse = {
    tasks: ScheduledTask[];
};

type HostAccessProfileResponse = {
    saved_profiles: SavedHostProfile[];
};

type HostCapability = {
    capability_status: "ready" | "unavailable";
    timezone: string;
    message: string;
};

const defaultTaskForm: TaskForm = {
    name: "",
    target: "container",
    profile_id: null,
    schedule: "30 2 * * *",
    command: "",
    execution_mode: "command",
    script_path: null,
    timeout_seconds: 30,
    retry_count: 3,
    enabled: true,
};

const taskQueryKey = ["scheduled-tasks"] as const;

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
    const response = await fetch(input, {
        credentials: "include",
        headers: {
            Accept: "application/json",
            ...(init?.body ? { "Content-Type": "application/json" } : {}),
            ...init?.headers,
        },
        ...init,
    });
    const payload = (await response.json().catch(() => null)) as
        { details?: string; message?: string } | T | null;
    if (!response.ok) {
        const detail =
            payload && typeof payload === "object" && "details" in payload
                ? (payload.details ?? payload.message)
                : null;
        throw new Error(detail ?? `HTTP ${response.status}`);
    }
    return payload as T;
}

function formatDateTime(value: string | null, formatter: Intl.DateTimeFormat) {
    return value ? formatter.format(new Date(value)) : "—";
}

function statusTone(
    status: ScheduledTask["last_status"],
): "default" | "success" | "warning" | "error" | "info" {
    if (status === "success") return "success";
    if (status === "failed") return "error";
    if (status === "running") return "info";
    if (status === "skipped") return "warning";
    return "default";
}

function TaskStatusIcon({ status }: { status: ScheduledTask["last_status"] }) {
    const path = status === "success"
        ? "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm-1.2 14.2L6.6 12l1.4-1.4 2.8 2.8 5.2-5.2 1.4 1.4-6.6 6.6Z"
        : status === "failed"
            ? "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm3.1 11.7-1.4 1.4-1.7-1.7-1.7 1.7-1.4-1.4 1.7-1.7-1.7-1.7 1.4-1.4 1.7 1.7 1.7-1.7 1.4 1.4-1.7 1.7 1.7 1.7Z"
            : status === "running"
                ? "M12 2a10 10 0 1 0 10 10h-2a8 8 0 1 1-8-8V2Z"
                : status === "skipped"
                    ? "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm-5 9h6V7l5 5-5 5v-4H7v-2Z"
                    : "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 5v5.6l3.8 2.3-1 1.7-4.8-2.9V7h2Z";
    const color = status === "success" ? "success.main" : status === "failed" ? "error.main" : status === "running" ? "info.main" : status === "skipped" ? "warning.main" : "text.disabled";
    return <SvgIcon sx={{ fontSize: 20, color }}><path d={path} /></SvgIcon>;
}

function TaskSyncStatusIcon({ status }: { status: "failed" | "unreachable" }) {
    const path = status === "unreachable"
        ? "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm-1 4h2v7h-2V6Zm0 9h2v2h-2v-2Z"
        : "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 5v6l4 2.4-1 1.7-5-3V7h2Z";
    return <SvgIcon sx={{ fontSize: 20, color: "error.main" }}><path d={path} /></SvgIcon>;
}

function isIntegerInRange(value: string, minimum: number, maximum: number) {
    return (
        /^\d+$/.test(value) && Number(value) >= minimum && Number(value) <= maximum
    );
}

function RunIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="m8 5 11 7-11 7V5Z" />
        </SvgIcon>
    );
}

function RefreshIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M17.65 6.35A7.95 7.95 0 0 0 12 4a8 8 0 1 0 7.75 10h-2.08A6 6 0 1 1 12 6c1.3 0 2.5.42 3.47 1.13L13 10h7V3l-2.35 3.35Z" />
        </SvgIcon>
    );
}

function LogIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M5 4h14v16H5V4Zm2 3v2h10V7H7Zm0 4v2h10v-2H7Zm0 4v2h7v-2H7Z" />
        </SvgIcon>
    );
}

function EditIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="m4 17.25V20h2.75L17.81 8.94l-2.75-2.75L4 17.25ZM19.96 6.79a1 1 0 0 0 0-1.41l-1.34-1.34a1 1 0 0 0-1.41 0l-1.05 1.05 2.75 2.75 1.05-1.05Z" />
        </SvgIcon>
    );
}

function DeleteIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M6 7h12v13H6V7Zm2 2v9h8V9H8Zm2-5h4l1 1h4v2H5V5h4l1-1Z" />
        </SvgIcon>
    );
}

function CloseIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M18.3 5.71 12 12l6.3 6.29-1.42 1.42L10.59 13.4 4.29 19.7l-1.41-1.42L9.17 12 2.88 5.71 4.29 4.29l6.3 6.3 6.29-6.3 1.42 1.42Z" />
        </SvgIcon>
    );
}

function UploadIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z" /></SvgIcon>;
}

export function ScheduledTasksPage() {
    const { t, i18n } = useTranslation("shell");
    const { colorMode } = useAppColorMode();
    const darkMode = colorMode === "dark";
    const palette = getSurfacePalette(darkMode);
    const queryClient = useQueryClient();
    const formatter = new Intl.DateTimeFormat(i18n.resolvedLanguage, {
        dateStyle: "medium",
        timeStyle: "short",
    });
    const [editorTask, setEditorTask] = useState<
        ScheduledTask | null | undefined
    >(undefined);
    const [form, setForm] = useState<TaskForm>(defaultTaskForm);
    const [uploadFile, setUploadFile] = useState<File | null>(null);
    const [scheduleMode, setScheduleMode] = useState<ScheduleMode>("daily");
    const [scheduleMinute, setScheduleMinute] = useState("30");
    const [scheduleHour, setScheduleHour] = useState("2");
    const [scheduleDay, setScheduleDay] = useState("1");
    const [scheduleWeekday, setScheduleWeekday] = useState("0");
    const [timeoutUnit, setTimeoutUnit] = useState<TimeoutUnit>("seconds");
    const [searchValue, setSearchValue] = useState("");
    const [activeTarget, setActiveTarget] = useState<ScheduledTask["target"]>("container");
    const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
    const [enabledFilter, setEnabledFilter] = useState<EnabledFilter>("all");
    const [saving, setSaving] = useState(false);
    const [pendingTaskId, setPendingTaskId] = useState<string | null>(null);
    const [refreshingTaskIds, setRefreshingTaskIds] = useState<Set<string>>(() => new Set());
    const [logTask, setLogTask] = useState<ScheduledTask | null>(null);
    const [taskRuns, setTaskRuns] = useState<ScheduledTaskRun[]>([]);
    const [selectedRun, setSelectedRun] = useState<ScheduledTaskRun | null>(null);
    const [logBefore, setLogBefore] = useState<number | null>(null);
    const [logContent, setLogContent] = useState("");
    const [logLoading, setLogLoading] = useState(false);
    const [deleteTask, setDeleteTask] = useState<ScheduledTask | null>(null);
    const [feedback, setFeedback] = useState<{
        severity: "success" | "error" | "info";
        message: string;
    } | null>(null);
    const [scheduleError, setScheduleError] = useState<string | null>(null);
    const supportsEventSource = typeof window !== "undefined" && typeof EventSource !== "undefined";
    const pageShellRef = useRef<HTMLDivElement | null>(null);
    const scheduleInputRef = useRef<HTMLInputElement | null>(null);
    const [editorScope, setEditorScope] = useState<{
        top: number;
        left: number;
        width: number;
        height: number;
    } | null>(null);

    const tasksQuery = useQuery<ScheduledTasksResponse, Error>({
        queryKey: taskQueryKey,
        queryFn: () => requestJson("/api/scheduled-tasks"),
        refetchOnWindowFocus: false,
    });
    const hostProfilesQuery = useQuery<HostAccessProfileResponse, Error>({
        queryKey: ["host-access-profiles"],
        queryFn: () => requestJson("/api/host-access/profile"),
        refetchOnWindowFocus: false,
    });
    const hostCapabilityQuery = useQuery<HostCapability, Error>({
        queryKey: ["scheduled-task-host-capability", form.profile_id],
        queryFn: () =>
            requestJson(
                `/api/scheduled-tasks/hosts/${encodeURIComponent(form.profile_id ?? "")}/capability`,
                { method: "POST" },
            ),
        enabled:
            editorTask !== undefined &&
            form.target === "host" &&
            Boolean(form.profile_id),
        staleTime: 300_000,
        retry: false,
    });

    const tasks = tasksQuery.data?.tasks ?? [];
    const savedHostProfiles = hostProfilesQuery.data?.saved_profiles ?? [];
    const filteredTasks = tasks.filter((task) => {
        const query = searchValue.trim().toLowerCase();
        const searchableValues = [
            task.name,
            task.command,
            task.script_path ?? "",
            task.script_name ?? "",
            task.schedule,
            task.target,
            task.execution_mode,
            executionLocationLabel(task),
            hostIdentityLabel(task) ?? "",
            t(`scheduledTasks.executionModes.${task.execution_mode}`),
            scheduleLabel(task.schedule),
        ];
        return (!query || searchableValues.some((value) => value.toLowerCase().includes(query)))
            && task.target === activeTarget
            && (statusFilter === "all" || task.last_status === statusFilter)
            && (enabledFilter === "all" || task.enabled === (enabledFilter === "enabled"));
    });
    const taskCounts: Record<ScheduledTask["target"], number> = {
        container: tasks.filter((task) => task.target === "container").length,
        host: tasks.filter((task) => task.target === "host").length,
    };
    const runningTaskIds = tasks
        .filter((task) => task.last_status === "running")
        .map((task) => task.task_id)
        .join(",");
    const executionReady =
        form.execution_mode === "command"
            ? Boolean(form.command.trim())
            : Boolean(form.script_path?.trim());

    useEffect(() => {
        if (!supportsEventSource || !tasksQuery.data) {
            return;
        }
        const eventSource = new EventSource("/api/scheduled-tasks/stream", { withCredentials: true });
        const handleSnapshot = (event: Event) => {
            try {
                const payload = JSON.parse((event as MessageEvent<string>).data) as ScheduledTasksResponse;
                if (payload.tasks) {
                    queryClient.setQueryData(taskQueryKey, payload);
                }
            } catch {
                // Keep the last local snapshot when a stream event is malformed.
            }
        };
        eventSource.addEventListener("snapshot", handleSnapshot);
        return () => {
            eventSource.removeEventListener("snapshot", handleSnapshot);
            eventSource.close();
        };
    }, [Boolean(tasksQuery.data), queryClient, supportsEventSource]);
    const editorSelectMenuProps = {
        disablePortal: true,
        slotProps: {
            paper: {
                sx: {
                    borderRadius: 0,
                    mt: 0.5,
                    zIndex: 1501,
                    backgroundColor: palette.panelBg,
                    color: palette.text,
                },
            },
        },
    };

    useEffect(() => {
        if (!runningTaskIds) {
            return undefined;
        }

        let disposed = false;
        const refreshRunningTasks = async () => {
            const updates = await Promise.all(
                runningTaskIds.split(",").map(async (taskId) => {
                    try {
                        return await requestJson<ScheduledTask>(
                            `/api/scheduled-tasks/${taskId}/refresh-status`,
                            { method: "POST" },
                        );
                    } catch {
                        return null;
                    }
                }),
            );
            if (disposed) {
                return;
            }
            const updatesById = new Map(
                updates
                    .filter((task): task is ScheduledTask => task !== null)
                    .map((task) => [task.task_id, task]),
            );
            queryClient.setQueryData<ScheduledTasksResponse>(
                taskQueryKey,
                (current) =>
                    current
                        ? {
                            ...current,
                            tasks: current.tasks.map(
                                (task) => updatesById.get(task.task_id) ?? task,
                            ),
                        }
                        : current,
            );
        };

        void refreshRunningTasks();
        const timer = window.setInterval(() => void refreshRunningTasks(), 1_500);
        return () => {
            disposed = true;
            window.clearInterval(timer);
        };
    }, [queryClient, runningTaskIds]);

    useLayoutEffect(() => {
        const shell = pageShellRef.current;
        const main = shell?.closest("main");
        if (!shell || !(main instanceof HTMLElement)) return;
        const update = () => {
            const rect = main.getBoundingClientRect();
            setEditorScope({
                top: rect.top,
                left: rect.left,
                width: rect.width,
                height: rect.height,
            });
        };
        update();
        const observer = new ResizeObserver(update);
        observer.observe(main);
        window.addEventListener("resize", update);
        return () => {
            observer.disconnect();
            window.removeEventListener("resize", update);
        };
    }, []);

    function applyVisualSchedule(
        mode = scheduleMode,
        values = {
            minute: scheduleMinute,
            hour: scheduleHour,
            day: scheduleDay,
            weekday: scheduleWeekday,
        },
    ) {
        if (mode === "custom") return;
        const schedule =
            mode === "hourly"
                ? `${values.minute} * * * *`
                : mode === "daily"
                    ? `${values.minute} ${values.hour} * * *`
                    : mode === "weekly"
                        ? `${values.minute} ${values.hour} * * ${values.weekday}`
                        : mode === "monthly"
                            ? `${values.minute} ${values.hour} ${values.day} * *`
                            : mode === "intervalMinutes"
                                ? `*/${Math.min(59, Math.max(1, Number(values.minute)))} * * * *`
                                : `0 */${Math.min(23, Math.max(1, Number(values.hour)))} * * *`;
        setForm((current) => ({ ...current, schedule }));
    }

    function setVisualScheduleMode(mode: ScheduleMode) {
        setScheduleError(null);
        if (mode !== "custom") {
            const values = {
                minute: /^\d+$/.test(scheduleMinute) ? scheduleMinute : "0",
                hour: /^\d+$/.test(scheduleHour) ? scheduleHour : "0",
                day: /^\d+$/.test(scheduleDay) ? scheduleDay : "1",
                weekday: /^\d+$/.test(scheduleWeekday) ? scheduleWeekday : "0",
            };
            setScheduleMinute(values.minute);
            setScheduleHour(values.hour);
            setScheduleDay(values.day);
            setScheduleWeekday(values.weekday);
            setScheduleMode(mode);
            applyVisualSchedule(mode, values);
            return;
        }
        setScheduleMode(mode);
        applyVisualSchedule(mode);
    }

    function localizedTaskError(error: unknown) {
        const message = error instanceof Error ? error.message : "";
        if (/Schedule must be a (five-field|valid five-field) cron expression/i.test(message)) {
            return t("scheduledTasks.validation.invalidSchedule");
        }
        if (/A task name is required/i.test(message)) return t("scheduledTasks.errors.nameRequired");
        if (/A command is required/i.test(message)) return t("scheduledTasks.errors.commandRequired");
        if (/Script path must be an absolute path/i.test(message)) return t("scheduledTasks.errors.scriptPathInvalid");
        if (/Uploaded script content is invalid|Upload a script before selecting|Upload the script again/i.test(message)) return t("scheduledTasks.errors.scriptRequired");
        if (/Task input exceeds/i.test(message)) return t("scheduledTasks.errors.inputTooLong");
        if (/Timeout must be/i.test(message)) return t("scheduledTasks.errors.timeoutInvalid");
        if (/Retry count must be/i.test(message)) return t("scheduledTasks.errors.retryInvalid");
        if (/A saved SSH host profile is required|SSH host tasks require/i.test(message)) return t("scheduledTasks.errors.hostRequired");
        if (/Platform tasks cannot use/i.test(message)) return t("scheduledTasks.errors.platformHostMismatch");
        if (/A task with this name already exists/i.test(message)) return t("scheduledTasks.errors.nameExists");
        if (/Host is unavailable|SSH host|Scheduled Task Host Unavailable|inspect the SSH host/i.test(message)) return t("scheduledTasks.errors.hostUnavailable");
        if (/synchroniz|runner|remote task|crontab|task block/i.test(message)) return t("scheduledTasks.errors.syncFailed");
        if (/Scheduled Task Not Found/i.test(message)) return t("scheduledTasks.errors.notFound");
        return t("scheduledTasks.feedback.failed");
    }

    function hostCapabilityErrorMessage(error: Error) {
        const message = error.message;
        if (/Authentication failed|SSH Authentication Failed/i.test(message)) {
            return t("scheduledTasks.hostCapability.authenticationFailed");
        }
        if (/Timed out|timeout/i.test(message)) {
            return t("scheduledTasks.hostCapability.connectionTimedOut");
        }
        if (/Unable to connect|No route to host|Connection refused|Network is unreachable/i.test(message)) {
            return t("scheduledTasks.hostCapability.connectionFailed");
        }
        return t("scheduledTasks.hostCapability.checkFailed");
    }

    function openCreateDialog() {
        setForm({
            ...defaultTaskForm,
            command: t("scheduledTasks.fields.commandExample"),
        });
        setTimeoutUnit("seconds");
        setUploadFile(null);
        setScheduleMode("daily");
        setScheduleMinute("30");
        setScheduleHour("2");
        setScheduleDay("1");
        setScheduleWeekday("0");
        setEditorTask(null);
    }

    function openEditDialog(task: ScheduledTask) {
        setForm({
            name: task.name,
            target: task.target,
            profile_id: task.profile_id,
            schedule: task.schedule,
            command: task.command,
            execution_mode: task.execution_mode ?? "command",
            script_path: task.script_path,
            timeout_seconds: task.timeout_seconds ?? 0,
            retry_count: task.retry_count ?? 0,
            enabled: task.enabled,
        });
        setUploadFile(null);
        setTimeoutUnit("seconds");
        const parts = task.schedule.split(" ");
        const isHourly =
            parts.length === 5 &&
            isIntegerInRange(parts[0], 0, 59) &&
            parts[1] === "*" &&
            parts[2] === "*" &&
            parts[3] === "*" &&
            parts[4] === "*";
        const isDaily =
            parts.length === 5 &&
            isIntegerInRange(parts[0], 0, 59) &&
            isIntegerInRange(parts[1], 0, 23) &&
            parts[2] === "*" &&
            parts[3] === "*" &&
            parts[4] === "*";
        const isWeekly =
            parts.length === 5 &&
            isIntegerInRange(parts[0], 0, 59) &&
            isIntegerInRange(parts[1], 0, 23) &&
            parts[2] === "*" &&
            parts[3] === "*" &&
            isIntegerInRange(parts[4], 0, 6);
        const isMonthly =
            parts.length === 5 &&
            isIntegerInRange(parts[0], 0, 59) &&
            isIntegerInRange(parts[1], 0, 23) &&
            isIntegerInRange(parts[2], 1, 31) &&
            parts[3] === "*" &&
            parts[4] === "*";
        const intervalMinuteMatch = /^\*\/(\d+)$/.exec(parts[0]);
        const isIntervalMinutes =
            parts.length === 5 &&
            intervalMinuteMatch !== null &&
            Number(intervalMinuteMatch[1]) >= 1 &&
            Number(intervalMinuteMatch[1]) <= 59 &&
            parts.slice(1).every((part) => part === "*");
        const intervalHourMatch = /^\*\/(\d+)$/.exec(parts[1]);
        const isIntervalHours =
            parts.length === 5 &&
            parts[0] === "0" &&
            intervalHourMatch !== null &&
            Number(intervalHourMatch[1]) >= 1 &&
            Number(intervalHourMatch[1]) <= 23 &&
            parts.slice(2).every((part) => part === "*");
        const visualMode: ScheduleMode | null = isHourly
            ? "hourly"
            : isDaily
                ? "daily"
                : isWeekly
                    ? "weekly"
                    : isMonthly
                        ? "monthly"
                        : isIntervalMinutes
                            ? "intervalMinutes"
                            : isIntervalHours
                                ? "intervalHours"
                                : null;
        setScheduleMode(visualMode ?? "custom");
        if (visualMode) {
            setScheduleMinute(
                isIntervalMinutes ? intervalMinuteMatch![1] : parts[0],
            );
            setScheduleHour(
                isIntervalHours ? intervalHourMatch![1] : parts[1] === "*" ? "0" : parts[1],
            );
            setScheduleDay(parts[2] === "*" ? "1" : parts[2]);
            setScheduleWeekday(parts[4] === "*" ? "0" : parts[4]);
        }
        setEditorTask(task);
    }

    async function refreshTasks() {
        await queryClient.invalidateQueries({ queryKey: taskQueryKey });
    }

    async function syncTasks() {
        await requestJson("/api/scheduled-tasks/sync", { method: "POST" });
        await refreshTasks();
    }

    async function saveTask() {
        setSaving(true);
        setScheduleError(null);
        try {
            const scriptContent = uploadFile ? await uploadFile.text() : undefined;
            const payload = {
                ...(form.target === "host" ? form : { ...form, profile_id: null }),
                ...(uploadFile
                    ? { script_name: uploadFile.name, script_content: scriptContent }
                    : {}),
            };
            if (editorTask) {
                await requestJson(`/api/scheduled-tasks/${editorTask.task_id}`, {
                    method: "PUT",
                    body: JSON.stringify(payload),
                });
            } else {
                await requestJson("/api/scheduled-tasks", {
                    method: "POST",
                    body: JSON.stringify(payload),
                });
            }
            await refreshTasks();
            setEditorTask(undefined);
            setFeedback({
                severity: "success",
                message: t(
                    editorTask
                        ? "scheduledTasks.feedback.updated"
                        : "scheduledTasks.feedback.created",
                ),
            });
        } catch (error) {
            const message = error instanceof Error ? error.message : "";
            if (/Schedule must be a (five-field|valid five-field) cron expression/i.test(message)) {
                setScheduleMode("custom");
                setScheduleError(t("scheduledTasks.validation.invalidSchedule"));
                requestAnimationFrame(() => scheduleInputRef.current?.focus());
            }
            setFeedback({
                severity: "error",
                message: localizedTaskError(error),
            });
        } finally {
            setSaving(false);
        }
    }

    function executionLocationLabel(task: ScheduledTask) {
        return task.execution_path || "—";
    }

    function hostIdentityLabel(task: ScheduledTask) {
        if (task.target !== "host") {
            return null;
        }
        const profile = savedHostProfiles.find(
            (item) => item.profile_id === task.profile_id,
        );
        if (!profile) {
            return t("scheduledTasks.hostUnavailable");
        }
        return profile.username
            ? `${profile.username}@${profile.host}`
            : profile.host;
    }

    function scheduleLabel(schedule: string) {
        const parts = schedule.trim().split(/\s+/);
        if (parts.length !== 5) return schedule;
        const [minute, hour, day, month, weekday] = parts;
        const minuteInterval = /^\*\/(\d+)$/.exec(minute);
        const hourInterval = /^\*\/(\d+)$/.exec(hour);
        if (minuteInterval && hour === "*" && day === "*" && month === "*" && weekday === "*") {
            return t("scheduledTasks.scheduleSummary.everyMinutes", { count: minuteInterval[1] });
        }
        if (minute === "0" && hourInterval && day === "*" && month === "*" && weekday === "*") {
            return t("scheduledTasks.scheduleSummary.everyHours", { count: hourInterval[1] });
        }
        if (/^\d+$/.test(minute) && hour === "*" && day === "*" && month === "*" && weekday === "*") {
            return t("scheduledTasks.scheduleSummary.hourlyAt", { minute: minute.padStart(2, "0") });
        }
        if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && day === "*" && month === "*" && weekday === "*") {
            return t("scheduledTasks.scheduleSummary.dailyAt", { time: `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}` });
        }
        if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && day === "*" && month === "*" && /^\d+$/.test(weekday)) {
            return t("scheduledTasks.scheduleSummary.weeklyAt", { weekday: t(`scheduledTasks.weekdays.${weekday}`), time: `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}` });
        }
        if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && /^\d+$/.test(day) && month === "*" && weekday === "*") {
            return t("scheduledTasks.scheduleSummary.monthlyAt", { day, time: `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}` });
        }
        return t("scheduledTasks.scheduleSummary.custom");
    }

    async function updateTask(
        task: ScheduledTask,
        action: "toggle" | "run" | "refresh",
    ) {
        setPendingTaskId(task.task_id);
        if (action === "refresh") {
            setRefreshingTaskIds((current) => new Set(current).add(task.task_id));
        }
        try {
            if (action === "toggle") {
                const updatedTask = await requestJson<ScheduledTask>(`/api/scheduled-tasks/${task.task_id}/toggle`, {
                    method: "POST",
                    body: JSON.stringify({ enabled: !task.enabled }),
                });
                queryClient.setQueryData<ScheduledTasksResponse>(
                    taskQueryKey,
                    (current) =>
                        current
                            ? {
                                ...current,
                                tasks: current.tasks.map((item) =>
                                    item.task_id === updatedTask.task_id ? updatedTask : item,
                                ),
                            }
                            : current,
                );
            } else if (action === "run") {
                await requestJson(`/api/scheduled-tasks/${task.task_id}/run`, {
                    method: "POST",
                });
                queryClient.setQueryData<ScheduledTasksResponse>(
                    taskQueryKey,
                    (current) =>
                        current
                            ? {
                                ...current,
                                tasks: current.tasks.map((item) =>
                                    item.task_id === task.task_id
                                        ? { ...item, last_status: "running" }
                                        : item,
                                ),
                            }
                            : current,
                );
                setFeedback({
                    severity: "info",
                    message: t("scheduledTasks.feedback.started"),
                });
            } else {
                const refreshedTask = await requestJson<ScheduledTask>(
                    `/api/scheduled-tasks/${task.task_id}/refresh-status`,
                    { method: "POST" },
                );
                queryClient.setQueryData<ScheduledTasksResponse>(
                    taskQueryKey,
                    (current) =>
                        current
                            ? {
                                ...current,
                                tasks: current.tasks.map((item) =>
                                    item.task_id === refreshedTask.task_id
                                        ? refreshedTask
                                        : item,
                                ),
                            }
                            : current,
                );
            }
        } catch (error) {
            setFeedback({
                severity: "error",
                message: localizedTaskError(error),
            });
        } finally {
            setPendingTaskId(null);
            if (action === "refresh") {
                setRefreshingTaskIds((current) => {
                    const next = new Set(current);
                    next.delete(task.task_id);
                    return next;
                });
            }
        }
    }

    async function openLog(task: ScheduledTask) {
        setLogTask(task);
        setTaskRuns([]);
        setSelectedRun(null);
        setLogContent("");
        setLogLoading(true);
        try {
            const response = await requestJson<{ runs: ScheduledTaskRun[] }>(
                `/api/scheduled-tasks/${task.task_id}/runs`,
            );
            setTaskRuns(response.runs);
        } catch (error) {
            setFeedback({
                severity: "error",
                message: localizedTaskError(error),
            });
        } finally {
            setLogLoading(false);
        }
    }

    async function openRunLog(task: ScheduledTask, run: ScheduledTaskRun, before?: number) {
        setSelectedRun(run);
        if (before === undefined) {
            setLogContent("");
            setLogBefore(null);
        }
        setLogLoading(true);
        try {
            const query = before === undefined ? "" : `?before=${before}`;
            const response = await requestJson<{ content: string; next_before: number | null }>(
                `/api/scheduled-tasks/${task.task_id}/runs/${run.run_id}/log${query}`,
            );
            setLogContent((current) => before === undefined ? response.content : `${response.content}${current ? `\n${current}` : ""}`);
            setLogBefore(response.next_before);
        } catch (error) {
            setFeedback({ severity: "error", message: localizedTaskError(error) });
        } finally {
            setLogLoading(false);
        }
    }

    function downloadRunLog(task: ScheduledTask, run: ScheduledTaskRun) {
        const link = document.createElement("a");
        link.href = `/api/scheduled-tasks/${task.task_id}/runs/${run.run_id}/log/download`;
        link.download = "";
        document.body.appendChild(link);
        link.click();
        link.remove();
    }

    async function confirmDelete() {
        if (!deleteTask) return;
        setPendingTaskId(deleteTask.task_id);
        try {
            await requestJson(`/api/scheduled-tasks/${deleteTask.task_id}`, {
                method: "DELETE",
            });
            await refreshTasks();
            setDeleteTask(null);
            setFeedback({
                severity: "success",
                message: t("scheduledTasks.feedback.deleted"),
            });
        } catch (error) {
            setFeedback({
                severity: "error",
                message: localizedTaskError(error),
            });
        } finally {
            setPendingTaskId(null);
        }
    }

    return (
        <Box
            className="scheduled-tasks-page-shell"
            ref={pageShellRef}
            sx={{
                minHeight: "calc(100vh - 120px)",
                position: "relative",
                mx: { xs: -1, md: -3 },
                my: { xs: -1.25, md: -2.25 },
                px: { xs: 2, md: 3 },
                py: { xs: 1.25, md: 1.5 },
                backgroundColor: palette.pageBg,
                color: palette.text,
                overflowY: "auto",
            }}
        >
            <PageDescriptionHeader
                title={t("scheduledTasks.title")}
                description={t("scheduledTasks.description")}
                descriptionColor={palette.subtleText}
            />

            {!hostProfilesQuery.isLoading && savedHostProfiles.length === 0 ? (
                <Alert severity="info" sx={{ mb: 2 }}>
                    {t("scheduledTasks.hostEmpty")}
                </Alert>
            ) : null}

            {tasksQuery.isLoading ? (
                <SurfaceStateCard
                    loading
                    detail={t("scheduledTasks.loading")}
                    darkMode={darkMode}
                />
            ) : null}
            {tasksQuery.error ? (
                <Alert
                    severity="error"
                    action={
                        <Button
                            color="inherit"
                            size="small"
                            onClick={() => void tasksQuery.refetch()}
                        >
                            {t("scheduledTasks.actions.retry")}
                        </Button>
                    }
                >
                    {tasksQuery.error.message}
                </Alert>
            ) : null}
            {!tasksQuery.isLoading && !tasksQuery.error ? (
                <Box className="scheduled-tasks-list-frame" sx={{ mb: 1.5 }}>
                    <Box className="scheduled-tasks-list-content">
                        <Box className="scheduled-tasks-toolbar">
                            <Tabs
                                className="scheduled-tasks-tabs"
                                value={activeTarget}
                                onChange={(_event, value) => setActiveTarget(value as ScheduledTask["target"])}
                                sx={{
                                    minHeight: 34,
                                    flexShrink: 0,
                                    backgroundColor: palette.panelBg,
                                    border: `1px solid ${palette.border}`,
                                    borderRadius: "6px",
                                    overflow: "hidden",
                                    "& .MuiTabs-indicator": { display: "none" },
                                }}
                            >
                                <Tab
                                    value="container"
                                    label={`${t("scheduledTasks.platform")} (${taskCounts.container})`}
                                    sx={{
                                        minHeight: 34,
                                        px: 1.5,
                                        fontSize: 13,
                                        fontWeight: 600,
                                        textTransform: "none",
                                        borderRadius: "5px",
                                        "&.Mui-selected": { backgroundColor: palette.accentSoft, color: palette.accent },
                                    }}
                                />
                                <Tab
                                    value="host"
                                    label={`${t("scheduledTasks.host")} (${taskCounts.host})`}
                                    sx={{
                                        minHeight: 34,
                                        px: 1.5,
                                        fontSize: 13,
                                        fontWeight: 600,
                                        textTransform: "none",
                                        borderRadius: "5px",
                                        "&.Mui-selected": { backgroundColor: palette.accentSoft, color: palette.accent },
                                    }}
                                />
                            </Tabs>
                            <Stack
                                className="scheduled-tasks-toolbar-actions"
                                direction="row"
                                spacing={1}
                                sx={{ flexWrap: "wrap", justifyContent: "flex-end", minWidth: 0 }}
                            >
                                <TextField
                                    className="scheduled-tasks-toolbar-search"
                                    onChange={(event) => setSearchValue(event.target.value)}
                                    placeholder={t("scheduledTasks.filters.searchPlaceholder")}
                                    size="small"
                                    value={searchValue}
                                />
                                <TextField
                                    className="scheduled-tasks-toolbar-filter"
                                    select
                                    size="small"
                                    value={statusFilter}
                                    onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                                    slotProps={{ select: { MenuProps: { slotProps: { paper: { sx: { borderRadius: 0, mt: 0.5, "& .MuiMenuItem-root": { fontSize: 14, fontWeight: 500 } } } } } } }}
                                >
                                    <MenuItem value="all">{t("scheduledTasks.filters.allStatuses")}</MenuItem>
                                    {(["never", "running", "success", "failed", "skipped"] as StatusFilter[]).filter((status) => status !== "all").map((status) => <MenuItem key={status} value={status}>{t(`scheduledTasks.status.${status}`)}</MenuItem>)}
                                </TextField>
                                <TextField
                                    className="scheduled-tasks-toolbar-filter scheduled-tasks-toolbar-filter--enabled"
                                    select
                                    size="small"
                                    value={enabledFilter}
                                    onChange={(event) => setEnabledFilter(event.target.value as EnabledFilter)}
                                    slotProps={{ select: { MenuProps: { slotProps: { paper: { sx: { borderRadius: 0, mt: 0.5, "& .MuiMenuItem-root": { fontSize: 14, fontWeight: 500 } } } } } } }}
                                >
                                    <MenuItem value="all">{t("scheduledTasks.filters.allEnabled")}</MenuItem>
                                    <MenuItem value="enabled">{t("scheduledTasks.filters.enabled")}</MenuItem>
                                    <MenuItem value="disabled">{t("scheduledTasks.filters.disabled")}</MenuItem>
                                </TextField>
                                <Button
                                    className="scheduled-tasks-toolbar-create"
                                    onClick={openCreateDialog}
                                    size="small"
                                    variant="contained"
                                >
                                    {t("scheduledTasks.actions.create")}
                                </Button>
                                <Tooltip title={t("scheduledTasks.actions.refreshList")}>
                                    <span>
                                        <IconButton
                                            className="scheduled-tasks-toolbar-refresh"
                                            disabled={tasksQuery.isFetching}
                                            onClick={() => void syncTasks()}
                                            size="small"
                                        >
                                            {tasksQuery.isFetching ? (
                                                <CircularProgress size={16} />
                                            ) : (
                                                <RefreshIcon />
                                            )}
                                        </IconButton>
                                    </span>
                                </Tooltip>
                            </Stack>
                        </Box>
                        <Paper
                            className="scheduled-tasks-panel"
                            elevation={0}
                            sx={{
                                display: { xs: "none", md: "block" },
                                backgroundColor: palette.panelBg,
                            }}
                        >
                            <Box
                                className="scheduled-tasks-table"
                                component="table"
                                sx={{ width: "100%", minWidth: 1080, borderCollapse: "collapse" }}
                            >
                                <thead>
                                    <tr>
                                        <th>{t("scheduledTasks.columns.name")}</th>
                                        <th>{t("scheduledTasks.columns.executionMode")}</th>
                                        <th>{t("scheduledTasks.columns.executionLocation")}</th>
                                        <th>{t("scheduledTasks.columns.schedule")}</th>
                                        <th>{t("scheduledTasks.columns.lastRun")}</th>
                                        <th>{t("scheduledTasks.columns.enabled")}</th>
                                        <th className="scheduled-tasks-actions-column">
                                            {t("scheduledTasks.columns.actions")}
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {tasksQuery.isFetching ? (
                                        <tr>
                                            <td colSpan={7}>
                                                <Box
                                                    sx={{
                                                        minHeight: 160,
                                                        display: "flex",
                                                        alignItems: "center",
                                                        justifyContent: "center",
                                                        gap: 1.25,
                                                        color: palette.subtleText,
                                                    }}
                                                >
                                                    <CircularProgress size={20} />
                                                    <Typography
                                                        sx={{ fontSize: 14, color: palette.subtleText }}
                                                    >
                                                        {t("scheduledTasks.loading")}
                                                    </Typography>
                                                </Box>
                                            </td>
                                        </tr>
                                    ) : tasks.length === 0 ? (
                                        <tr>
                                            <td colSpan={7}>
                                                <Box
                                                    sx={{
                                                        minHeight: 160,
                                                        display: "flex",
                                                        alignItems: "center",
                                                        justifyContent: "center",
                                                        textAlign: "center",
                                                    }}
                                                >
                                                    <Box>
                                                        <Typography sx={{ fontSize: 16, fontWeight: 700 }}>
                                                            {t("scheduledTasks.empty.title")}
                                                        </Typography>
                                                        <Typography
                                                            sx={{
                                                                mt: 0.5,
                                                                fontSize: 13,
                                                                color: palette.subtleText,
                                                            }}
                                                        >
                                                            {t("scheduledTasks.empty.description")}
                                                        </Typography>
                                                    </Box>
                                                </Box>
                                            </td>
                                        </tr>
                                    ) : filteredTasks.length === 0 ? (
                                        <tr>
                                            <td colSpan={7}>
                                                <Box
                                                    sx={{
                                                        minHeight: 160,
                                                        display: "flex",
                                                        alignItems: "center",
                                                        justifyContent: "center",
                                                    }}
                                                >
                                                    <Typography sx={{ fontSize: 16, fontWeight: 700 }}>
                                                        {t("scheduledTasks.empty.noResults")}
                                                    </Typography>
                                                </Box>
                                            </td>
                                        </tr>
                                    ) : (
                                        filteredTasks.map((task) => (
                                            <tr className="scheduled-tasks-table-row" key={task.task_id}>
                                                <td>
                                                    <Typography sx={{ fontSize: 14, fontWeight: 600 }}>
                                                        {task.name}
                                                    </Typography>
                                                    {hostIdentityLabel(task) ? (
                                                        <Typography sx={{ mt: 0.25, fontSize: 12, color: palette.subtleText }}>
                                                            {hostIdentityLabel(task)}
                                                        </Typography>
                                                    ) : null}
                                                </td>
                                                <td>
                                                    <Tooltip title={task.execution_mode === "command" ? task.command : task.script_path ?? task.script_name ?? ""}>
                                                        <Typography
                                                            sx={{
                                                                maxWidth: 235,
                                                                overflow: "hidden",
                                                                textOverflow: "ellipsis",
                                                                whiteSpace: "nowrap",
                                                                fontSize: 13,
                                                            }}
                                                        >
                                                            {t(`scheduledTasks.executionModes.${task.execution_mode}`)}
                                                        </Typography>
                                                    </Tooltip>
                                                </td>
                                                <td>
                                                    <Tooltip title={task.execution_path || ""}>
                                                        <Typography
                                                            sx={{
                                                                maxWidth: 280,
                                                                overflow: "hidden",
                                                                textOverflow: "ellipsis",
                                                                whiteSpace: "nowrap",
                                                                fontFamily: "monospace",
                                                                fontSize: 12,
                                                            }}
                                                        >
                                                            {executionLocationLabel(task)}
                                                        </Typography>
                                                    </Tooltip>
                                                </td>
                                                <td>
                                                    <Tooltip title={task.schedule}><Typography sx={{ fontSize: 13 }}>{scheduleLabel(task.schedule)}</Typography></Tooltip>
                                                </td>
                                                <td>
                                                    {task.syncing || refreshingTaskIds.has(task.task_id) ? (
                                                        <Stack direction="row" spacing={0.75} sx={{ alignItems: "center", whiteSpace: "nowrap" }}>
                                                            <CircularProgress size={18} />
                                                            <Typography sx={{ fontSize: 12, color: "primary.main" }}>{t("scheduledTasks.syncStatus.taskSyncing")}</Typography>
                                                        </Stack>
                                                    ) : task.sync_status === "unreachable" ? (
                                                        <Stack direction="row" spacing={0.75} sx={{ alignItems: "center", whiteSpace: "nowrap" }}>
                                                            <Tooltip title={t("scheduledTasks.hostUnavailable")}><Box sx={{ display: "flex" }}><TaskSyncStatusIcon status="unreachable" /></Box></Tooltip>
                                                            <Typography sx={{ fontSize: 12, color: "error.main" }}>{t("scheduledTasks.hostUnavailable")}</Typography>
                                                        </Stack>
                                                    ) : task.sync_status === "failed" ? (
                                                        <Stack direction="row" spacing={0.75} sx={{ alignItems: "center", whiteSpace: "nowrap" }}>
                                                            <Tooltip title={t("scheduledTasks.syncFailed")}><Box sx={{ display: "flex" }}><TaskSyncStatusIcon status="failed" /></Box></Tooltip>
                                                            <Typography sx={{ fontSize: 12, color: "error.main" }}>{t("scheduledTasks.syncFailed")}</Typography>
                                                        </Stack>
                                                    ) : task.last_run_at ? (
                                                        <Stack direction="row" spacing={0.75} sx={{ alignItems: "center", whiteSpace: "nowrap" }}>
                                                            <Tooltip title={t(`scheduledTasks.status.${task.last_status}`)}><Box sx={{ display: "flex" }}><TaskStatusIcon status={task.last_status} /></Box></Tooltip>
                                                            <Typography sx={{ fontSize: 12, color: palette.subtleText }}>
                                                                {formatDateTime(task.last_run_at, formatter)}
                                                            </Typography>
                                                        </Stack>
                                                    ) : (
                                                        <Stack direction="row" spacing={0.75} sx={{ alignItems: "center", whiteSpace: "nowrap" }}>
                                                            <Tooltip title={t("scheduledTasks.status.never")}><Box sx={{ display: "flex" }}><TaskStatusIcon status="never" /></Box></Tooltip>
                                                            <Typography sx={{ fontSize: 12, color: palette.subtleText }}>{t("scheduledTasks.status.never")}</Typography>
                                                        </Stack>
                                                    )}
                                                </td>
                                                <td>
                                                    <Switch
                                                        checked={task.enabled}
                                                        disabled={pendingTaskId === task.task_id}
                                                        onChange={() => void updateTask(task, "toggle")}
                                                        size="small"
                                                        slotProps={{
                                                            input: {
                                                                "aria-label": t("scheduledTasks.actions.toggle", {
                                                                    name: task.name,
                                                                }),
                                                            },
                                                        }}
                                                    />
                                                </td>
                                                <td className="scheduled-tasks-actions-column">
                                                    <Stack
                                                        className="scheduled-tasks-row-actions"
                                                        direction="row"
                                                        spacing={0.25}
                                                    >
                                                        <Tooltip title={t("scheduledTasks.actions.run")}>
                                                            <span>
                                                                <IconButton
                                                                    disabled={
                                                                        pendingTaskId === task.task_id ||
                                                                        task.last_status === "running"
                                                                    }
                                                                    onClick={() => void updateTask(task, "run")}
                                                                    size="small"
                                                                >
                                                                    <RunIcon />
                                                                </IconButton>
                                                            </span>
                                                        </Tooltip>
                                                        <Tooltip title={t("scheduledTasks.actions.refresh")}>
                                                            <span>
                                                                <IconButton
                                                                    disabled={pendingTaskId === task.task_id}
                                                                    onClick={() => void updateTask(task, "refresh")}
                                                                    size="small"
                                                                >
                                                                    {pendingTaskId === task.task_id ? <CircularProgress size={16} /> : <RefreshIcon />}
                                                                </IconButton>
                                                            </span>
                                                        </Tooltip>
                                                        <Tooltip title={t("scheduledTasks.actions.logs")}>
                                                            <IconButton
                                                                onClick={() => void openLog(task)}
                                                                size="small"
                                                            >
                                                                <LogIcon />
                                                            </IconButton>
                                                        </Tooltip>
                                                        <Tooltip title={t("scheduledTasks.actions.edit")}>
                                                            <IconButton
                                                                onClick={() => openEditDialog(task)}
                                                                size="small"
                                                            >
                                                                <EditIcon />
                                                            </IconButton>
                                                        </Tooltip>
                                                        <Tooltip title={t("scheduledTasks.actions.delete")}>
                                                            <IconButton
                                                                className="scheduled-tasks-row-action-danger"
                                                                color="error"
                                                                onClick={() => setDeleteTask(task)}
                                                                size="small"
                                                            >
                                                                <DeleteIcon />
                                                            </IconButton>
                                                        </Tooltip>
                                                    </Stack>
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                </tbody>
                            </Box>
                        </Paper>
                    </Box>
                </Box>
            ) : null}
            {!tasksQuery.isLoading &&
                !tasksQuery.error &&
                !tasksQuery.isFetching &&
                filteredTasks.length > 0 ? (
                <Stack spacing={2} sx={{ display: { xs: "flex", md: "none" } }}>
                    {filteredTasks.map((task) => (
                        <Paper
                            key={task.task_id}
                            elevation={0}
                            sx={{
                                p: 1.5,
                                border: `1px solid ${palette.border}`,
                                borderRadius: "2px",
                                backgroundColor: palette.panelBg,
                            }}
                        >
                            <Stack spacing={1.25}>
                                <Stack
                                    direction="row"
                                    sx={{
                                        justifyContent: "space-between",
                                        alignItems: "flex-start",
                                        gap: 1,
                                    }}
                                >
                                    <Box sx={{ minWidth: 0 }}>
                                        <Typography sx={{ fontSize: 14, fontWeight: 600 }}>
                                            {task.name}
                                        </Typography>
                                        {hostIdentityLabel(task) ? (
                                            <Typography sx={{ mt: 0.25, fontSize: 12, color: palette.subtleText }}>
                                                {hostIdentityLabel(task)}
                                            </Typography>
                                        ) : null}
                                    </Box>
                                    <Switch
                                        checked={task.enabled}
                                        disabled={pendingTaskId === task.task_id}
                                        onChange={() => void updateTask(task, "toggle")}
                                        size="small"
                                        slotProps={{
                                            input: {
                                                "aria-label": t("scheduledTasks.actions.toggle", {
                                                    name: task.name,
                                                }),
                                            },
                                        }}
                                    />
                                </Stack>
                                <Box>
                                    <Tooltip title={task.schedule}><Typography sx={{ fontSize: 13 }}>{scheduleLabel(task.schedule)}</Typography></Tooltip>
                                </Box>
                                <Typography
                                    sx={{
                                        overflow: "hidden",
                                        textOverflow: "ellipsis",
                                        whiteSpace: "nowrap",
                                        fontFamily: "monospace",
                                        fontSize: 12,
                                    }}
                                >
                                    {t(`scheduledTasks.executionModes.${task.execution_mode}`)} · {task.execution_mode === "command" ? task.command : task.script_path ?? task.script_name}
                                </Typography>
                                <Typography sx={{ fontSize: 12, color: palette.subtleText, fontFamily: "monospace" }}>
                                    {t("scheduledTasks.columns.executionLocation")}: {executionLocationLabel(task)}
                                </Typography>
                                <Stack
                                    direction="row"
                                    sx={{
                                        justifyContent: "space-between",
                                        alignItems: "center",
                                        gap: 1,
                                    }}
                                >
                                    <Stack spacing={0.3}>
                                        <Chip
                                            label={t(`scheduledTasks.status.${task.last_status}`)}
                                            color={statusTone(task.last_status)}
                                            size="small"
                                        />
                                        {task.last_run_at ? (
                                            <Typography
                                                sx={{ fontSize: 12, color: palette.subtleText }}
                                            >
                                                {formatDateTime(task.last_run_at, formatter)}
                                            </Typography>
                                        ) : null}
                                        {task.sync_status === "unreachable" ? (
                                            <Typography sx={{ fontSize: 12, color: "error.main" }}>
                                                {t("scheduledTasks.hostUnavailable")}
                                            </Typography>
                                        ) : null}
                                    </Stack>
                                    <Stack direction="row" spacing={0.25}>
                                        <Tooltip title={t("scheduledTasks.actions.run")}>
                                            <span>
                                                <IconButton
                                                    disabled={
                                                        pendingTaskId === task.task_id ||
                                                        task.last_status === "running"
                                                    }
                                                    onClick={() => void updateTask(task, "run")}
                                                    size="small"
                                                >
                                                    <RunIcon />
                                                </IconButton>
                                            </span>
                                        </Tooltip>
                                        <Tooltip title={t("scheduledTasks.actions.refresh")}>
                                            <IconButton
                                                disabled={pendingTaskId === task.task_id}
                                                onClick={() => void updateTask(task, "refresh")}
                                                size="small"
                                            >
                                                <RefreshIcon />
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title={t("scheduledTasks.actions.logs")}>
                                            <IconButton
                                                onClick={() => void openLog(task)}
                                                size="small"
                                            >
                                                <LogIcon />
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title={t("scheduledTasks.actions.edit")}>
                                            <IconButton
                                                onClick={() => openEditDialog(task)}
                                                size="small"
                                            >
                                                <EditIcon />
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title={t("scheduledTasks.actions.delete")}>
                                            <IconButton
                                                color="error"
                                                onClick={() => setDeleteTask(task)}
                                                size="small"
                                            >
                                                <DeleteIcon />
                                            </IconButton>
                                        </Tooltip>
                                    </Stack>
                                </Stack>
                            </Stack>
                        </Paper>
                    ))}
                </Stack>
            ) : null}
            {!tasksQuery.isLoading &&
                !tasksQuery.error &&
                (tasksQuery.isFetching || filteredTasks.length === 0) ? (
                <Paper
                    elevation={0}
                    sx={{
                        display: { xs: "block", md: "none" },
                        p: 2,
                        minHeight: 160,
                        border: `1px solid ${palette.border}`,
                        borderRadius: 0,
                        backgroundColor: palette.panelBg,
                    }}
                >
                    <Stack
                        sx={{
                            minHeight: 120,
                            justifyContent: "center",
                            alignItems: "center",
                            textAlign: "center",
                        }}
                    >
                        {tasksQuery.isFetching ? (
                            <CircularProgress size={22} />
                        ) : (
                            <>
                                <Typography sx={{ fontSize: 16, fontWeight: 700 }}>
                                    {tasks.length === 0
                                        ? t("scheduledTasks.empty.title")
                                        : t("scheduledTasks.empty.noResults")}
                                </Typography>
                                {tasks.length === 0 ? (
                                    <Typography
                                        sx={{ mt: 0.5, fontSize: 13, color: palette.subtleText }}
                                    >
                                        {t("scheduledTasks.empty.description")}
                                    </Typography>
                                ) : null}
                            </>
                        )}
                    </Stack>
                </Paper>
            ) : null}

            {editorTask !== undefined && editorScope ? (
                <Box
                    sx={{
                        position: "fixed",
                        top: editorScope.top,
                        left: editorScope.left,
                        width: editorScope.width,
                        height: editorScope.height,
                        zIndex: 1400,
                    }}
                >
                    <Box
                        onClick={() => !saving && setEditorTask(undefined)}
                        sx={{
                            position: "absolute",
                            inset: 0,
                            backgroundColor: "rgba(15, 23, 42, 0.18)",
                        }}
                    />
                    <Box
                        role="dialog"
                        aria-modal="true"
                        sx={{
                            position: "relative",
                            display: "flex",
                            flexDirection: "column",
                            width: {
                                xs: "calc(100% - 24px)",
                                md: "min(960px, calc(100% - 24px))",
                            },
                            maxHeight: "calc(100% - 24px)",
                            mx: "auto",
                            my: 1,
                            backgroundColor: palette.panelBg,
                            border: `1px solid ${palette.border}`,
                            borderRadius: "2px",
                            boxShadow: "0 16px 40px rgba(15, 23, 42, 0.16)",
                            overflow: "visible",
                        }}
                    >
                        <Box
                            className="scheduled-tasks-editor-header"
                            sx={{ borderBottom: `1px solid ${palette.border}` }}
                        >
                            <Box className="scheduled-tasks-editor-hero scheduled-tasks-editor-hero--plain">
                                <Box sx={{ minWidth: 0 }}>
                                    <Typography
                                        className="scheduled-tasks-editor-title"
                                        sx={{ fontSize: 20, fontWeight: 600 }}
                                    >
                                        {t(
                                            editorTask
                                                ? "scheduledTasks.editor.editTitle"
                                                : "scheduledTasks.editor.createTitle",
                                        )}
                                    </Typography>
                                </Box>
                                <IconButton
                                    aria-label={t("scheduledTasks.actions.cancel")}
                                    className="scheduled-tasks-editor-close"
                                    disabled={saving}
                                    onClick={() => setEditorTask(undefined)}
                                    size="small"
                                >
                                    <CloseIcon />
                                </IconButton>
                            </Box>
                        </Box>
                        <Box
                            className="scheduled-tasks-editor-content"
                            sx={{ overflowY: "auto", flex: 1, minHeight: 0 }}
                        >
                            <Stack className="scheduled-tasks-editor-form" spacing={1.5}>
                                <Box>
                                    <Typography sx={{ mb: 0.75, fontSize: 13 }}>
                                        {t("scheduledTasks.fields.name")}
                                    </Typography>
                                    <TextField
                                        autoFocus
                                        fullWidth
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                name: event.target.value,
                                            }))
                                        }
                                        placeholder={t("scheduledTasks.fields.name")}
                                        required
                                        size="small"
                                        value={form.name}
                                        sx={{ "& .MuiOutlinedInput-root": { borderRadius: 0 } }}
                                    />
                                </Box>
                                <Box>
                                    <Typography sx={{ mb: 0.75, fontSize: 13, fontWeight: 600 }}>
                                        {t("scheduledTasks.fields.target")}
                                    </Typography>
                                    <TextField
                                        fullWidth
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                target: event.target.value as TaskForm["target"],
                                                profile_id:
                                                    event.target.value === "host"
                                                        ? current.profile_id
                                                        : null,
                                            }))
                                        }
                                        select
                                        size="small"
                                        value={form.target}
                                        slotProps={{ select: { MenuProps: editorSelectMenuProps } }}
                                        sx={{ "& .MuiOutlinedInput-root": { borderRadius: 0 } }}
                                    >
                                        <MenuItem value="container">
                                            {t("scheduledTasks.platform")}
                                        </MenuItem>
                                        <MenuItem value="host">{t("scheduledTasks.host")}</MenuItem>
                                    </TextField>
                                </Box>
                                {form.target === "host" ? (
                                    <Box>
                                        <Typography
                                            sx={{ mb: 0.75, fontSize: 13, fontWeight: 600 }}
                                        >
                                            {t("scheduledTasks.fields.host")}
                                        </Typography>
                                        <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
                                            <TextField
                                                onChange={(event) =>
                                                    setForm((current) => ({
                                                        ...current,
                                                        profile_id: event.target.value || null,
                                                    }))
                                                }
                                                required
                                                select
                                                size="small"
                                                value={form.profile_id ?? ""}
                                                slotProps={{
                                                    select: { MenuProps: editorSelectMenuProps },
                                                }}
                                                sx={{ flex: { md: "0 0 calc(50% - 4px)" }, "& .MuiOutlinedInput-root": { borderRadius: 0 } }}
                                            >
                                                {savedHostProfiles.map((profile) => (
                                                    <MenuItem
                                                        key={profile.profile_id}
                                                        value={profile.profile_id}
                                                    >
                                                        {profile.name || profile.host} ({profile.username}@
                                                        {profile.host})
                                                    </MenuItem>
                                                ))}
                                            </TextField>
                                            {hostCapabilityQuery.isLoading ? (
                                                <Typography sx={{ flex: 1, alignSelf: "center", fontSize: 13, color: palette.subtleText }}>
                                                    {t("scheduledTasks.hostChecking")}
                                                </Typography>
                                            ) : null}
                                            {hostCapabilityQuery.data ? (
                                                <Alert severity={hostCapabilityQuery.data.capability_status === "ready" ? "success" : "error"} sx={{ flex: 1, py: 0, alignItems: "center" }}>
                                                    {hostCapabilityQuery.data.capability_status === "ready"
                                                        ? t("scheduledTasks.hostCapability.ready")
                                                        : t("scheduledTasks.hostCapability.unavailable")}
                                                </Alert>
                                            ) : null}
                                            {hostCapabilityQuery.error ? (
                                                <Alert severity="error" sx={{ flex: 1, py: 0, alignItems: "center" }}>
                                                    {hostCapabilityErrorMessage(hostCapabilityQuery.error)}
                                                </Alert>
                                            ) : null}
                                        </Stack>
                                    </Box>
                                ) : null}
                                <Box>
                                    <Typography sx={{ mb: 0.75, fontSize: 13, fontWeight: 600 }}>
                                        {t("scheduledTasks.fields.schedule")}
                                    </Typography>
                                    <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                                        <TextField
                                            select
                                            size="small"
                                            value={scheduleMode}
                                            onChange={(event) =>
                                                setVisualScheduleMode(
                                                    event.target.value as ScheduleMode,
                                                )
                                            }
                                            slotProps={{
                                                select: { MenuProps: editorSelectMenuProps },
                                            }}
                                            sx={{
                                                minWidth: 220,
                                                "& .MuiOutlinedInput-root": { borderRadius: 0 },
                                            }}
                                        >
                                            {(
                                                [
                                                    "hourly",
                                                    "daily",
                                                    "weekly",
                                                    "monthly",
                                                    "intervalMinutes",
                                                    "intervalHours",
                                                    "custom",
                                                ] as ScheduleMode[]
                                            ).map((mode) => (
                                                <MenuItem key={mode} value={mode}>
                                                    {t(`scheduledTasks.scheduleModes.${mode}`)}
                                                </MenuItem>
                                            ))}
                                        </TextField>
                                        {scheduleMode !== "custom" ? (
                                            <Stack
                                                direction="row"
                                                spacing={0}
                                                sx={{ flex: 1, flexWrap: "wrap", columnGap: 1, rowGap: 1 }}
                                            >
                                                {scheduleMode !== "intervalHours" ? (
                                                    <TextField
                                                        size="small"
                                                        type="number"
                                                        value={scheduleMinute}
                                                        onChange={(event) => {
                                                            const minute = String(Math.min(59, Math.max(
                                                                scheduleMode === "intervalMinutes" ? 1 : 0,
                                                                Math.trunc(Number(event.target.value) || 0),
                                                            )));
                                                            setScheduleMinute(minute);
                                                            applyVisualSchedule(scheduleMode, {
                                                                minute,
                                                                hour: scheduleHour,
                                                                day: scheduleDay,
                                                                weekday: scheduleWeekday,
                                                            });
                                                        }}
                                                        slotProps={{
                                                            input: { endAdornment: <InputAdornment position="end">{t("scheduledTasks.scheduleControls.minute")}</InputAdornment> },
                                                            htmlInput: { min: scheduleMode === "intervalMinutes" ? 1 : 0, max: 59, step: 1 },
                                                        }}
                                                        sx={{
                                                            minWidth: 120,
                                                            flex: "1 1 120px",
                                                            order: 3,
                                                            "& .MuiOutlinedInput-root": { borderRadius: 0 },
                                                        }}
                                                    />
                                                ) : null}
                                                {scheduleMode !== "hourly" &&
                                                    scheduleMode !== "intervalMinutes" ? (
                                                    <TextField
                                                        size="small"
                                                        type="number"
                                                        value={scheduleHour}
                                                        onChange={(event) => {
                                                            const hour = String(Math.min(23, Math.max(
                                                                scheduleMode === "intervalHours" ? 1 : 0,
                                                                Math.trunc(Number(event.target.value) || 0),
                                                            )));
                                                            setScheduleHour(hour);
                                                            applyVisualSchedule(scheduleMode, {
                                                                minute: scheduleMinute,
                                                                hour,
                                                                day: scheduleDay,
                                                                weekday: scheduleWeekday,
                                                            });
                                                        }}
                                                        slotProps={{
                                                            input: { endAdornment: <InputAdornment position="end">{t("scheduledTasks.scheduleControls.hour")}</InputAdornment> },
                                                            htmlInput: { min: scheduleMode === "intervalHours" ? 1 : 0, max: 23, step: 1 },
                                                        }}
                                                        sx={{
                                                            minWidth: 120,
                                                            flex: "1 1 120px",
                                                            order: 2,
                                                            "& .MuiOutlinedInput-root": { borderRadius: 0 },
                                                        }}
                                                    />
                                                ) : null}
                                                {scheduleMode === "weekly" ? (
                                                    <TextField
                                                        select
                                                        size="small"
                                                        value={scheduleWeekday}
                                                        onChange={(event) => {
                                                            const weekday = event.target.value;
                                                            setScheduleWeekday(weekday);
                                                            applyVisualSchedule(scheduleMode, {
                                                                minute: scheduleMinute,
                                                                hour: scheduleHour,
                                                                day: scheduleDay,
                                                                weekday,
                                                            });
                                                        }}
                                                        slotProps={{
                                                            select: { MenuProps: editorSelectMenuProps },
                                                        }}
                                                        sx={{
                                                            width: 120,
                                                            order: 1,
                                                            "& .MuiOutlinedInput-root": { borderRadius: 0 },
                                                        }}
                                                    >
                                                        {Array.from({ length: 7 }, (_, value) => (
                                                            <MenuItem key={value} value={String(value)}>
                                                                {t(`scheduledTasks.weekdays.${value}`)}
                                                            </MenuItem>
                                                        ))}
                                                    </TextField>
                                                ) : null}
                                                {scheduleMode === "monthly" ? (
                                                    <TextField
                                                        size="small"
                                                        type="number"
                                                        value={scheduleDay}
                                                        onChange={(event) => {
                                                            const day = String(Math.min(31, Math.max(
                                                                1,
                                                                Math.trunc(Number(event.target.value) || 1),
                                                            )));
                                                            setScheduleDay(day);
                                                            applyVisualSchedule(scheduleMode, {
                                                                minute: scheduleMinute,
                                                                hour: scheduleHour,
                                                                day,
                                                                weekday: scheduleWeekday,
                                                            });
                                                        }}
                                                        slotProps={{
                                                            input: { endAdornment: <InputAdornment position="end">{t("scheduledTasks.scheduleControls.day")}</InputAdornment> },
                                                            htmlInput: { min: 1, max: 31, step: 1 },
                                                        }}
                                                        sx={{
                                                            minWidth: 120,
                                                            flex: "1 1 120px",
                                                            order: 1,
                                                            "& .MuiOutlinedInput-root": { borderRadius: 0 },
                                                        }}
                                                    />
                                                ) : null}
                                            </Stack>
                                        ) : (
                                            <TextField
                                                error={Boolean(scheduleError)}
                                                fullWidth
                                                helperText={scheduleError}
                                                inputRef={scheduleInputRef}
                                                onChange={(event) => {
                                                    setScheduleError(null);
                                                    setForm((current) => ({
                                                        ...current,
                                                        schedule: event.target.value,
                                                    }));
                                                }
                                                }
                                                placeholder="0 0 * * *"
                                                size="small"
                                                value={form.schedule}
                                                sx={{ "& .MuiOutlinedInput-root": { borderRadius: 0 } }}
                                            />
                                        )}
                                    </Stack>
                                </Box>
                                <Box>
                                    <Typography sx={{ mb: 0.75, fontSize: 13, fontWeight: 600 }}>
                                        {t("scheduledTasks.fields.executionMode")}
                                    </Typography>
                                    <TextField
                                        fullWidth
                                        select
                                        size="small"
                                        value={form.execution_mode}
                                        onChange={(event) =>
                                            setForm((current) => ({
                                                ...current,
                                                execution_mode: event.target
                                                    .value as TaskForm["execution_mode"],
                                            }))
                                        }
                                        slotProps={{ select: { MenuProps: editorSelectMenuProps } }}
                                        sx={{ "& .MuiOutlinedInput-root": { borderRadius: 0 } }}
                                    >
                                        {(["command", "path"] as const).map((mode) => (
                                            <MenuItem key={mode} value={mode}>
                                                {t(`scheduledTasks.executionModes.${mode}`)}
                                            </MenuItem>
                                        ))}
                                        {form.execution_mode === "upload" ? (
                                            <MenuItem value="upload">
                                                {t("scheduledTasks.executionModes.upload")}
                                            </MenuItem>
                                        ) : null}
                                    </TextField>
                                </Box>
                                {form.execution_mode === "command" ||
                                    form.execution_mode === "upload" ? (
                                    <Box>
                                        <Stack
                                            direction="row"
                                            sx={{
                                                alignItems: "center",
                                                justifyContent: "space-between",
                                                mb: 0.75,
                                            }}
                                        >
                                            <Typography sx={{ fontSize: 13 }}>
                                                {t("scheduledTasks.fields.command")}
                                            </Typography>
                                            <Tooltip title={t("scheduledTasks.fields.scriptUpload")}>
                                                <IconButton component="label" size="small">
                                                    <input
                                                        hidden
                                                        accept="text/x-shellscript,text/plain,.sh"
                                                        type="file"
                                                        onChange={(event) => {
                                                            const file = event.target.files?.[0];
                                                            if (!file) return;
                                                            if (form.execution_mode === "upload") {
                                                                setUploadFile(file);
                                                                return;
                                                            }
                                                            if (file)
                                                                void file
                                                                    .text()
                                                                    .then((content) =>
                                                                        setForm((current) => ({
                                                                            ...current,
                                                                            command: content,
                                                                        })),
                                                                    );
                                                        }}
                                                    />
                                                    <UploadIcon />
                                                </IconButton>
                                            </Tooltip>
                                        </Stack>
                                        {form.execution_mode === "command" ? (
                                            <TextField
                                                fullWidth
                                                multiline
                                                minRows={4}
                                                onChange={(event) =>
                                                    setForm((current) => ({
                                                        ...current,
                                                        command: event.target.value,
                                                    }))
                                                }
                                                placeholder={t("scheduledTasks.fields.commandExample")}
                                                required
                                                size="small"
                                                value={form.command}
                                                sx={{
                                                    "& .MuiOutlinedInput-root": { borderRadius: 0 },
                                                    "& textarea": { resize: "vertical" },
                                                }}
                                            />
                                        ) : (
                                            <Typography sx={{ fontSize: 13, color: palette.subtleText }}>
                                                {t("scheduledTasks.fields.uploadLegacyHint", {
                                                    name: uploadFile?.name ?? editorTask?.script_name ?? "-",
                                                })}
                                            </Typography>
                                        )}
                                    </Box>
                                ) : null}
                                {form.execution_mode === "path" ? (
                                    <Box>
                                        <Typography
                                            sx={{ mb: 0.75, fontSize: 13 }}
                                        >
                                            {t("scheduledTasks.fields.scriptPath")}
                                        </Typography>
                                        <TextField
                                            fullWidth
                                            onChange={(event) =>
                                                setForm((current) => ({
                                                    ...current,
                                                    script_path: event.target.value,
                                                }))
                                            }
                                            placeholder="/opt/scripts/task.sh"
                                            size="small"
                                            value={form.script_path ?? ""}
                                            sx={{ "& .MuiOutlinedInput-root": { borderRadius: 0 } }}
                                        />
                                    </Box>
                                ) : null}
                                <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
                                    <Box sx={{ flex: 1 }}>
                                        <Typography
                                            sx={{ mb: 0.75, fontSize: 13 }}
                                        >
                                            {t("scheduledTasks.fields.timeout")}
                                        </Typography>
                                        <Stack direction="row" spacing={0}>
                                            <TextField
                                                fullWidth
                                                slotProps={{
                                                    htmlInput: { min: 0, max: 86400, step: 1 },
                                                }}
                                                onChange={(event) => {
                                                    const multiplier =
                                                        timeoutUnit === "hours"
                                                            ? 3600
                                                            : timeoutUnit === "minutes"
                                                                ? 60
                                                                : 1;
                                                    setForm((current) => ({
                                                        ...current,
                                                        timeout_seconds: Math.min(
                                                            86400,
                                                            Math.max(
                                                                0,
                                                                Math.trunc(Number(event.target.value) || 0) *
                                                                multiplier,
                                                            ),
                                                        ),
                                                    }));
                                                }}
                                                size="small"
                                                type="number"
                                                value={Math.trunc(
                                                    form.timeout_seconds /
                                                    (timeoutUnit === "hours"
                                                        ? 3600
                                                        : timeoutUnit === "minutes"
                                                            ? 60
                                                            : 1),
                                                )}
                                                sx={{
                                                    "& .MuiOutlinedInput-root": {
                                                        borderRadius: "2px 0 0 2px",
                                                        height: 38,
                                                    },
                                                }}
                                            />
                                            <TextField
                                                select
                                                size="small"
                                                value={timeoutUnit}
                                                onChange={(event) => {
                                                    const unit = event.target.value as TimeoutUnit;
                                                    setTimeoutUnit(unit);
                                                }}
                                                slotProps={{
                                                    select: { MenuProps: editorSelectMenuProps },
                                                }}
                                                sx={{
                                                    width: 132,
                                                    flexShrink: 0,
                                                    "& .MuiOutlinedInput-root": {
                                                        borderRadius: "0 2px 2px 0",
                                                        height: 38,
                                                    },
                                                }}
                                            >
                                                <MenuItem value="seconds">
                                                    {t("scheduledTasks.scheduleControls.seconds")}
                                                </MenuItem>
                                                <MenuItem value="minutes">
                                                    {t("scheduledTasks.scheduleControls.minutes")}
                                                </MenuItem>
                                                <MenuItem value="hours">
                                                    {t("scheduledTasks.scheduleControls.hours")}
                                                </MenuItem>
                                            </TextField>
                                        </Stack>
                                    </Box>
                                    <Box sx={{ flex: 1 }}>
                                        <Typography
                                            sx={{ mb: 0.75, fontSize: 13 }}
                                        >
                                            {t("scheduledTasks.fields.retryCount")}
                                        </Typography>
                                        <TextField
                                            fullWidth
                                            slotProps={{ htmlInput: { min: 0, max: 10, step: 1 } }}
                                            onChange={(event) =>
                                                setForm((current) => ({
                                                    ...current,
                                                    retry_count: Math.min(
                                                        10,
                                                        Math.max(
                                                            0,
                                                            Math.trunc(Number(event.target.value) || 0),
                                                        ),
                                                    ),
                                                }))
                                            }
                                            size="small"
                                            type="number"
                                            value={form.retry_count}
                                            sx={{ "& .MuiOutlinedInput-root": { borderRadius: 0 } }}
                                            helperText={t("scheduledTasks.fields.retryCountHint")}
                                        />
                                    </Box>
                                </Stack>
                                <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                                    <Typography sx={{ fontSize: 13 }}>
                                        {t("scheduledTasks.fields.enabled")}
                                    </Typography>
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={form.enabled}
                                                onChange={(event) =>
                                                    setForm((current) => ({
                                                        ...current,
                                                        enabled: event.target.checked,
                                                    }))
                                                }
                                            />
                                        }
                                        label={t("scheduledTasks.fields.enabledNow")}
                                    />
                                </Stack>
                            </Stack>
                        </Box>
                        <Box
                            className="scheduled-tasks-editor-actions"
                            sx={{
                                display: "flex",
                                justifyContent: "flex-end",
                                gap: 1,
                                borderTop: `1px solid ${palette.border}`,
                            }}
                        >
                            <Button
                                disabled={saving}
                                onClick={() => setEditorTask(undefined)}
                            >
                                {t("scheduledTasks.actions.cancel")}
                            </Button>
                            <Button
                                disabled={
                                    saving ||
                                    !form.name.trim() ||
                                    !executionReady ||
                                    (form.target === "host" &&
                                        !form.profile_id)
                                }
                                onClick={() => void saveTask()}
                                variant="contained"
                                sx={{ borderRadius: 0 }}
                            >
                                {saving ? (
                                    <CircularProgress color="inherit" size={18} />
                                ) : (
                                    t("scheduledTasks.actions.save")
                                )}
                            </Button>
                        </Box>
                    </Box>
                </Box>
            ) : null}

            {logTask && editorScope ? (
                <Box className="scheduled-tasks-scoped-overlay" sx={editorScope}>
                    <Box className="scheduled-tasks-scoped-backdrop" onClick={() => setLogTask(null)} />
                    <Box className="scheduled-tasks-scoped-dialog scheduled-tasks-log-dialog" role="dialog" aria-modal="true">
                        <DialogTitle className="scheduled-tasks-scoped-title">
                            <Typography sx={{ fontSize: 16, fontWeight: 700 }}>
                                {selectedRun ? t("scheduledTasks.runLogTitle", { name: logTask.name }) : t("scheduledTasks.runHistoryTitle", { name: logTask.name })}
                            </Typography>
                            <IconButton aria-label={t("scheduledTasks.actions.close")} onClick={() => setLogTask(null)} size="small">
                                <CloseIcon />
                            </IconButton>
                        </DialogTitle>
                        <DialogContent className="scheduled-tasks-log-content" dividers>
                            {selectedRun ? (
                                <Box component="pre" className="scheduled-tasks-log-panel">
                                    {logLoading ? t("scheduledTasks.loading") : logContent || t("scheduledTasks.logEmpty")}
                                </Box>
                            ) : logLoading ? (
                                <Box sx={{ flex: 1, minHeight: 0, display: "flex", alignItems: "center", justifyContent: "center", gap: 1, color: palette.subtleText }}>
                                    <CircularProgress size={20} />
                                    <Typography sx={{ fontSize: 14 }}>{t("scheduledTasks.loading")}</Typography>
                                </Box>
                            ) : (
                                <Stack spacing={0.75} sx={{ width: "100%", overflow: "auto" }}>
                                    {taskRuns.map((run) => (
                                        <Button key={run.run_id} onClick={() => void openRunLog(logTask, run)} sx={{ justifyContent: "space-between", border: "1px solid", borderColor: "divider", borderRadius: 0, color: "text.primary", textTransform: "none" }}>
                                            <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}><Chip label={t(`scheduledTasks.status.${run.status}`)} color={statusTone(run.status)} size="small" /><Typography sx={{ fontSize: 12 }}>{formatDateTime(run.started_at, formatter)}</Typography></Stack>
                                            <Typography sx={{ fontSize: 12 }}>{t(`scheduledTasks.triggers.${run.trigger}`)} · {t("scheduledTasks.exitCode", { code: run.exit_code ?? "—" })}</Typography>
                                        </Button>
                                    ))}
                                    {!logLoading && !taskRuns.length ? <Typography>{t("scheduledTasks.runEmpty")}</Typography> : null}
                                </Stack>
                            )}
                        </DialogContent>
                        <DialogActions className="scheduled-tasks-scoped-actions">
                            {selectedRun && logBefore !== null ? <Button onClick={() => void openRunLog(logTask, selectedRun, logBefore)}>{t("scheduledTasks.actions.loadEarlier")}</Button> : null}
                            {selectedRun ? <Button onClick={() => downloadRunLog(logTask, selectedRun)}>{t("scheduledTasks.actions.download")}</Button> : null}
                            {selectedRun ? <Button onClick={() => { setSelectedRun(null); setLogContent(""); }}>{t("scheduledTasks.actions.back")}</Button> : <Button onClick={() => void openLog(logTask)}>{t("scheduledTasks.actions.refreshRuns")}</Button>}
                            <Button onClick={() => setLogTask(null)}>{t("scheduledTasks.actions.close")}</Button>
                        </DialogActions>
                    </Box>
                </Box>
            ) : null}

            {deleteTask && editorScope ? (
                <Box className="scheduled-tasks-scoped-overlay" sx={editorScope}>
                    <Box className="scheduled-tasks-scoped-backdrop" onClick={() => setDeleteTask(null)} />
                    <Box className="scheduled-tasks-scoped-dialog scheduled-tasks-delete-dialog" role="dialog" aria-modal="true">
                        <DialogTitle className="scheduled-tasks-scoped-title">
                            <Typography sx={{ fontSize: 16, fontWeight: 700 }}>
                                {t("scheduledTasks.delete.title")}
                            </Typography>
                            <IconButton aria-label={t("scheduledTasks.actions.close")} onClick={() => setDeleteTask(null)} size="small">
                                <CloseIcon />
                            </IconButton>
                        </DialogTitle>
                        <DialogContent dividers>
                            <Typography>
                                {t("scheduledTasks.delete.description", { name: deleteTask.name })}
                            </Typography>
                            {deleteTask.target === "host" && deleteTask.sync_status === "unreachable" ? (
                                <Alert severity="warning" sx={{ mt: 2 }}>
                                    {t("scheduledTasks.delete.unreachableHostWarning")}
                                </Alert>
                            ) : null}
                        </DialogContent>
                        <DialogActions className="scheduled-tasks-scoped-actions">
                            <Button onClick={() => setDeleteTask(null)}>{t("scheduledTasks.actions.cancel")}</Button>
                            <Button color="error" disabled={pendingTaskId === deleteTask.task_id} onClick={() => void confirmDelete()} variant="contained">
                                {t("scheduledTasks.actions.delete")}
                            </Button>
                        </DialogActions>
                    </Box>
                </Box>
            ) : null}

            <SurfaceFeedbackToast
                open={Boolean(feedback)}
                severity={feedback?.severity ?? "info"}
                message={feedback?.message ?? ""}
                onClose={() => setFeedback(null)}
            />
        </Box>
    );
}
