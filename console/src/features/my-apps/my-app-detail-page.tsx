import {
    Alert,
    Box,
    Button,
    Checkbox,
    CircularProgress,
    IconButton,
    Step,
    StepContent,
    StepLabel,
    Stepper,
    Switch,
    Typography,
} from '@mui/material'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAppColorMode } from '../../app/providers/color-mode'
import { SurfaceDialog, SurfaceFeedbackToast } from '../../shared/design-system/standard-surfaces'
import { getSurfacePalette } from '../../shared/design-system/surface-theme'
import { LegacyMyAppLogo } from './my-app-media'
import { canOpenMyAppsDetailOverlay, clearMyAppsDetailOverlayIntent, consumePendingComposeReturn, hasMyAppsDetailOverlayIntent, markPendingComposeReturn, rememberMyAppsDetailRoute } from './my-app-detail-overlay-intent'
import { VolumeFileManagerDialog } from './volume-file-manager-dialog'
import { type MyAppDetail, useMyAppDetail } from './use-my-app-detail'
import { MyAppAccessPanel } from './my-app-access-panel'
import { useMyAppPhpInfo } from './use-my-app-php-info'
import './my-app-detail-page.css'

// =====================
// Types
// =====================
type DetailTabKey = 'overview' | 'access' | 'container' | 'volumes' | 'php' | 'database' | 'monitor' | 'compose' | 'uninstall'
type LifecycleActionKey = 'start' | 'stop' | 'restart' | 'redeploy' | 'uninstall'
type ActionFeedback = {
    severity: 'success' | 'error' | 'info'
    message: string
}
type RedeployLogEntry = {
    timestamp?: string
    type?: string
    status?: string
    message?: string
    details?: string
    data?: unknown
}
type DatabaseRow = {
    type: string
    host: string
    account: string
    password: string
    toolApps: Array<{ label: string; appKey: string }>
}
type BackupSnapshot = {
    id: string
    short_id?: string
    time: string
    summary?: {
        total_bytes_processed?: number
    }
}
type VolumeBackupRow = {
    id: string
    fullId: string
    time: string
    size: string
}
type PhpMigrationFeedback = {
    message: string
    details?: string
}

type MyAppsDetailLocationState = {
    backgroundScrollTop?: number
}

type ContentScopeRect = {
    top: number
    left: number
    width: number
    height: number
}

function getDetailDialogPalette(darkMode: boolean) {
    const palette = getSurfacePalette(darkMode)

    return {
        panel: palette.dialogBg,
        panelSoft: palette.panelSoft,
        panelMuted: palette.panelMuted,
        text: palette.text,
        subtleText: palette.subtleText,
        border: palette.borderStrong,
        divider: palette.divider,
        accent: palette.accent,
        accentSoft: palette.accentSoft,
        warning: palette.warning,
        warningSoft: palette.warningSoft,
        danger: palette.danger,
        overlay: palette.overlay,
    }
}

// =====================
// Action button icon helpers (dripicons CSS classes, same as old plugin)
// =====================
function BtnIcon({ className, spinning }: { className: string; spinning?: boolean }) {
    if (spinning) return <span style={{ width: 14, height: 14, display: 'inline-block', border: '2px solid currentColor', borderRightColor: 'transparent', borderRadius: '50%', animation: 'spin 0.75s linear infinite', verticalAlign: 'middle', opacity: 0.75 }} />
    return <i className={`${className} noti-icon`} />
}

// Password visibility icons (SVG, used in database tab)
function IconEye() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zm0 12.5a5 5 0 1 1 0-10 5 5 0 0 1 0 10zm0-8a3 3 0 1 0 0 6 3 3 0 0 0 0-6z" /></svg>
}
function IconEyeOff() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 7a5 5 0 0 1 5 5c0 .64-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46A11.8 11.8 0 0 0 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65a3 3 0 0 0 3 3c.22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53a5 5 0 0 1-5-5c0-.79.2-1.53.53-2.2zm4.31-.78 3.15 3.15.02-.16a3 3 0 0 0-3-3l-.17.01z" /></svg>
}
function IconCopy() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v12h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z" /></svg>
}
function IconRefresh() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="none"><path d="M20 12A8 8 0 1 1 17.66 6.34" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /><path d="M20 4v6h-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
}
function IconAdd() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="none"><path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
}


// =====================
// Status helpers
// =====================
function getStatusLabel(status: number) {
    if (status === 1) return 'Active'
    if (status === 3) return 'Installing'
    if (status === 4) return 'Error'
    return 'Inactive'
}

function getStatusColor(status: number) {
    if (status === 1) return 'var(--myapps-detail-success-text)'
    if (status === 4) return 'var(--myapps-detail-danger-text)'
    return 'var(--myapps-detail-warning-strong)'
}

// =====================
// Data helpers
// =====================
const dbConfig: Record<string, { account: string; toolApps: Array<{ label: string; appKey: string }> }> = {
    mariadb: { account: 'root', toolApps: [{ label: 'phpMyAdmin', appKey: 'phpmyadmin' }, { label: 'CloudBeaver', appKey: 'cloudbeaver' }] },
    mysql: { account: 'root', toolApps: [{ label: 'phpMyAdmin', appKey: 'phpmyadmin' }, { label: 'CloudBeaver', appKey: 'cloudbeaver' }] },
    postgresql: { account: 'postgres', toolApps: [{ label: 'pgAdmin', appKey: 'pgadmin' }, { label: 'CloudBeaver', appKey: 'cloudbeaver' }] },
    mongodb: { account: 'root', toolApps: [{ label: 'MongoCompass', appKey: 'mongocompass' }] },
    oracle: { account: 'system', toolApps: [{ label: 'CloudBeaver', appKey: 'cloudbeaver' }] },
    sqlserver: { account: 'sa', toolApps: [{ label: 'CloudBeaver', appKey: 'cloudbeaver' }] },
    redis: { account: '-', toolApps: [{ label: 'RedisInsight', appKey: 'redisinsight' }] },
}

function hasAccessTab(data: MyAppDetail | undefined) {
    if (!data) return false
    if (data.app_dist === 'compose') return true
    const env = data.env
    if (!env) return false
    return Boolean(
        env.W9_URL?.trim()
        || Object.entries(env).some(([key, value]) => (key.startsWith('W9_LOGIN') || key.endsWith('PORT_SET')) && value?.trim()),
    )
}

function getDetailTabs(data: MyAppDetail): DetailTabKey[] {
    const tabs: DetailTabKey[] = ['overview', 'container', 'compose', 'uninstall']
    if (hasAccessTab(data)) tabs.splice(1, 0, 'access')
    if ((data.volumes ?? []).length > 0) tabs.splice(3, 0, 'volumes')
    if (data.is_php_app) tabs.splice(4, 0, 'php')
    if (data.is_monitor_app) tabs.splice(6, 0, 'monitor')
    return tabs
}

const knownDetailPortLabelKeys: Record<string, string> = {
    W9_HTTP_PORT_SET: 'appStorePage.install.httpPortLabel',
    W9_HTTPS_PORT_SET: 'appStorePage.install.httpsPortLabel',
    W9_DB_PORT_SET: 'appStorePage.install.databasePortLabel',
}

const detailPortTokenLabels = {
    en: {
        API: 'API',
        APP: 'Application',
        DB: 'Database',
        HTTP: 'HTTP',
        HTTPS: 'HTTPS',
        PORT: 'Port',
    },
    zh: {
        API: 'API',
        APP: '应用',
        DB: '数据库',
        HTTP: 'HTTP',
        HTTPS: 'HTTPS',
        PORT: '端口',
    },
} as const

function humanizeDetailPortToken(token: string) {
    return token
        .toLowerCase()
        .replace(/(^|\s)(\w)/g, (value) => value.toUpperCase())
}

function formatDetailSettingName(value: string, locale: string) {
    const localeKey = locale.toLowerCase().startsWith('zh') ? 'zh' : 'en'
    const tokenLabels = detailPortTokenLabels[localeKey]

    return value
        .split('_')
        .filter(Boolean)
        .map((token) => tokenLabels[token.toUpperCase() as keyof typeof tokenLabels] ?? humanizeDetailPortToken(token))
        .join(' ')
}

function getDetailPortLabel(key: string, t: (key: string, options?: Record<string, unknown>) => string, locale: string) {
    const knownLabelKey = knownDetailPortLabelKeys[key]
    if (knownLabelKey) {
        return t(knownLabelKey)
    }

    const normalizedKey = key.replace(/^W9_/, '').replace(/_SET$/, '')
    if (!normalizedKey) {
        return key
    }

    if (normalizedKey.endsWith('_PORT')) {
        const portName = normalizedKey.slice(0, -'_PORT'.length)
        return t('appStorePage.install.dynamicPortLabel', {
            name: formatDetailSettingName(portName, locale),
        })
    }

    return t('appStorePage.install.dynamicSettingLabel', {
        name: formatDetailSettingName(normalizedKey, locale),
    })
}

// PORT_SET env key -> translated label key or raw env key fallback
function getPortEntries(env: Record<string, string> | undefined): Array<[string, string, string]> {
    if (!env) return []
    return Object.entries(env)
        .filter(([key]) => key.endsWith('PORT_SET'))
        .map(([key, value]) => [key, knownDetailPortLabelKeys[key] ?? key, String(value || '-')])
}

// Container state → color badge
function ContainerStateBadge({ state }: { state: string }) {
    const lower = state.toLowerCase()
    let bg = '#6c757d'
    let color = '#fff'
    if (lower === 'running') { bg = '#0acf97' }
    else if (lower === 'exited' || lower === 'stopped' || lower === 'dead') { bg = '#fa5c7c' }
    else if (lower === 'paused') { bg = '#ffbc00'; color = '#313a46' }
    else if (lower === 'created') { bg = '#6c757d' }
    return (
        <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: '12px',
            backgroundColor: bg,
            color,
            fontSize: '12px',
            fontWeight: 600,
            lineHeight: '18px',
        }}>{state}</span>
    )
}

function formatCreationDate(value: number | null | undefined, locale: string) {
    if (!value) return '-'
    const normalized = value > 10_000_000_000 ? value : value * 1_000
    try {
        return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(normalized))
    } catch {
        return '-'
    }
}

function getContainerStateSummary(containers: Array<Record<string, unknown>> | undefined) {
    if (!containers || containers.length === 0) return '-'
    const counts = containers.reduce<Record<string, number>>((acc, c) => {
        const state = typeof c.State === 'string' ? c.State : typeof c.state === 'string' ? c.state : 'unknown'
        acc[state] = (acc[state] ?? 0) + 1
        return acc
    }, {})
    return Object.entries(counts)
        .sort(([a], [b]) => (a === 'running' ? -1 : b === 'running' ? 1 : a.localeCompare(b)))
        .map(([state, n]) => `${state}(${n})`)
        .join('-')
}

function getContainerName(c: Record<string, unknown>) {
    const names = Array.isArray(c.Names) ? c.Names : []
    return (typeof names[0] === 'string' ? names[0] : '').replace(/^\//, '') || '-'
}

function getContainerState(c: Record<string, unknown>) {
    return typeof c.State === 'string' ? c.State : typeof c.state === 'string' ? c.state : 'unknown'
}

function getContainerStatus(c: Record<string, unknown>) {
    return typeof c.Status === 'string' ? c.Status : '-'
}

function canProbePhpRuntime(containers: Array<Record<string, unknown>> | undefined, appId: string | undefined) {
    if (!containers || containers.length === 0 || !appId) return true

    const primaryContainers = containers.filter((container) => getContainerName(container) === appId)
    if (primaryContainers.length === 0) return true

    return primaryContainers.some((container) => getContainerState(container).toLowerCase() === 'running')
}

function getContainerImage(c: Record<string, unknown>) {
    return typeof c.Image === 'string' ? c.Image : '-'
}

function getContainerId(c: Record<string, unknown>) {
    return typeof c.Id === 'string' ? c.Id : typeof c.id === 'string' ? c.id : ''
}

function getContainerCreatedAt(c: Record<string, unknown>, locale: string) {
    const created = typeof c.Created === 'number' ? c.Created : null
    return created ? formatCreationDate(created, locale) : '-'
}

function getContainerIpAddress(c: Record<string, unknown>) {
    const ns = c.NetworkSettings
    if (!ns || typeof ns !== 'object') return '-'
    const networks = (ns as { Networks?: Record<string, { IPAddress?: string }> }).Networks
    const ip = networks?.websoft9?.IPAddress
    if (typeof ip === 'string' && ip.trim()) return ip
    return Object.values(networks ?? {}).find((n) => typeof n?.IPAddress === 'string' && n.IPAddress.trim())?.IPAddress || '-'
}

function getPublishedPorts(c: Record<string, unknown>) {
    const ports = Array.isArray(c.Ports) ? c.Ports : []
    return ports
        .filter((p): p is { IP?: unknown; PublicPort?: unknown; PrivatePort?: unknown } => Boolean(p && typeof p === 'object'))
        .filter((p) => typeof p.IP === 'string' && /^(\d{1,3}\.){3}\d{1,3}$/.test(p.IP))
        .sort((a, b) => Number(a.PublicPort ?? 0) - Number(b.PublicPort ?? 0))
        .map((p) => `${String(p.PublicPort ?? '')}:${String(p.PrivatePort ?? '')}`)
        .filter(Boolean)
        .join(', ') || '-'
}

function getVolumeLabel(v: Record<string, unknown>) {
    return String(v.Name ?? v.name ?? v.Mountpoint ?? '-')
}

function getVolumeId(v: Record<string, unknown>) {
    return String(v.Name ?? v.name ?? '')
}

function getVolumeCreatedAt(v: Record<string, unknown>, locale: string) {
    const createdAt = typeof v.CreatedAt === 'string' ? v.CreatedAt : ''
    if (!createdAt) return '-'
    const parsed = Date.parse(createdAt)
    if (Number.isNaN(parsed)) return createdAt
    try {
        return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(parsed))
    } catch {
        return createdAt
    }
}

function getDatabaseRows(data: MyAppDetail): DatabaseRow[] {
    const expose = data.env?.W9_DB_EXPOSE
    if (!expose) return []
    return expose.split(',').map((s) => s.trim()).filter(Boolean).map((dbType) => ({
        type: dbType,
        host: `${data.app_id}-${dbType}`,
        account: dbConfig[dbType]?.account || '-',
        password: data.env?.W9_POWER_PASSWORD || '-',
        toolApps: dbConfig[dbType]?.toolApps || [],
    }))
}

function getComposeRepositoryTarget(data: MyAppDetail) {
    const git = data.gitConfig ?? {}
    for (const key of ['URL', 'RepositoryURL'] as const) {
        const value = git[key]
        if (typeof value !== 'string' || !value.trim()) continue

        try {
            const parsed = new URL(value)
            const normalizedPath = parsed.pathname.replace(/\.git$/i, '')
            if (normalizedPath.startsWith('/w9git/')) {
                return normalizedPath
            }
        } catch {
            const normalizedPath = value.trim().replace(/\.git$/i, '')
            if (normalizedPath.startsWith('/w9git/')) {
                return normalizedPath
            }
        }
    }

    return `/w9git/websoft9/${data.app_id}`
}

function formatBackupSize(bytes: number) {
    if (!bytes) return '0 B'
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let value = bytes
    let unitIndex = 0
    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024
        unitIndex += 1
    }
    return `${Number(value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 2))} ${units[unitIndex]}`
}

function formatBackupTime(value: string, locale: string) {
    const parsed = Date.parse(value)
    if (Number.isNaN(parsed)) return value
    try {
        return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(parsed))
    } catch {
        return value
    }
}

function formatBackupRows(snapshots: BackupSnapshot[], locale: string): VolumeBackupRow[] {
    return [...snapshots]
        .sort((a, b) => Date.parse(b.time) - Date.parse(a.time))
        .map((snapshot) => ({
            id: snapshot.short_id || snapshot.id.slice(0, 8),
            fullId: snapshot.id,
            time: formatBackupTime(snapshot.time, locale),
            size: formatBackupSize(snapshot.summary?.total_bytes_processed || 0),
        }))
}

// =====================
// API helpers
// =====================
async function parseJsonError(response: Response, fallback: string) {
    try {
        const body = (await response.json()) as { details?: string; message?: string }
        return body.details || body.message || fallback
    } catch {
        return fallback
    }
}

async function copyTextWithFallback(value: string) {
    if (navigator.clipboard?.writeText) {
        try {
            await navigator.clipboard.writeText(value)
            return
        } catch {
            // Fall through to the execCommand path for browsers without clipboard permission.
        }
    }

    const textarea = document.createElement('textarea')
    textarea.value = value
    textarea.setAttribute('readonly', 'true')
    textarea.style.position = 'absolute'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.select()

    const copied = document.execCommand('copy')
    document.body.removeChild(textarea)

    if (!copied) {
        throw new Error('Copy failed')
    }
}

function openProductPath(path: string, navigate: (to: string) => void, rememberedRoute?: string, openInNewWindow = false) {
    const normalizedPath = path.trim()
    rememberMyAppsDetailRoute(rememberedRoute ?? (typeof window === 'undefined' ? null : `${window.location.pathname}${window.location.search}`))

    let targetPath = normalizedPath

    if (normalizedPath.startsWith('/w9deployment/')) {
        targetPath = `/containers?target=${encodeURIComponent(normalizedPath)}`
    } else if (normalizedPath.startsWith('/w9git/')) {
        targetPath = `/repository?target=${encodeURIComponent(normalizedPath)}`
    } else if (normalizedPath.startsWith('/w9proxy/')) {
        targetPath = `/gateway?target=${encodeURIComponent(normalizedPath)}`
    }

    if (openInNewWindow) {
        window.open(targetPath, '_blank', 'noopener,noreferrer')
        return
    }

    if (normalizedPath.startsWith('/w9deployment/')) {
        navigate(targetPath)
        return
    }

    if (normalizedPath.startsWith('/w9git/')) {
        navigate(targetPath)
        return
    }

    if (normalizedPath.startsWith('/w9proxy/')) {
        navigate(targetPath)
        return
    }

    window.location.assign(targetPath)
}

function openAppStoreTool(appKey: string, navigate: (to: string, options?: { state?: unknown }) => void) {
    rememberMyAppsDetailRoute(typeof window === 'undefined' ? null : `${window.location.pathname}${window.location.search}`)
    navigate('/appstore', { state: { openAppKey: appKey } })
}

async function runLifecycleRequest(url: string, method: 'POST' | 'DELETE') {
    const response = await fetch(url, {
        method,
        credentials: 'include',
        headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
        throw new Error(await parseJsonError(response, `Lifecycle action failed: ${response.status}`))
    }
}

async function fetchBackupSnapshots(appId: string) {
    const response = await fetch(`/api/backup/snapshots?app_id=${encodeURIComponent(appId)}`, {
        credentials: 'include',
        headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
        throw new Error(await parseJsonError(response, `Backup list failed: ${response.status}`))
    }
    return (await response.json()) as BackupSnapshot[]
}

async function createAppBackup(appId: string) {
    const response = await fetch(`/api/backup/${encodeURIComponent(appId)}`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
        throw new Error(await parseJsonError(response, `Create backup failed: ${response.status}`))
    }
}

async function submitPhpMigrationRequest(appId: string, targetVersion: string, remarks: string) {
    const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/php/migration-request`, {
        method: 'POST',
        credentials: 'include',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ target_version: targetVersion, remarks }),
    })

    if (!response.ok) {
        throw new Error(await parseJsonError(response, `PHP migration request failed: ${response.status}`))
    }

    return (await response.json()) as PhpMigrationFeedback
}

async function deleteAppBackup(snapshotId: string) {
    const response = await fetch(`/api/backup/snapshots/${encodeURIComponent(snapshotId)}`, {
        method: 'DELETE',
        credentials: 'include',
        headers: { Accept: 'application/json' },
    })
    if (!response.ok && response.status !== 204) {
        throw new Error(await parseJsonError(response, `Delete backup failed: ${response.status}`))
    }
}

async function restoreAppBackup(appId: string, snapshotId: string) {
    const response = await fetch(`/api/backup/restore/${encodeURIComponent(appId)}/${encodeURIComponent(snapshotId)}`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
        throw new Error(await parseJsonError(response, `Restore backup failed: ${response.status}`))
    }
}

async function runRedeployRequest(
    appId: string,
    pullImage: boolean,
    onLog: (entry: RedeployLogEntry) => void,
) {
    const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/redeploy?pullImage=${String(pullImage)}`, {
        method: 'PUT',
        credentials: 'include',
        headers: { Accept: 'text/plain' },
    })
    if (!response.ok || !response.body) {
        throw new Error(await parseJsonError(response, `Redeploy failed: ${response.status}`))
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalStatus: 'success' | 'failed' | null = null

    while (true) {
        const { done, value } = await reader.read()
        buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
            if (!line.trim()) continue
            const entry = JSON.parse(line) as RedeployLogEntry
            onLog(entry)
            if (entry.status === 'success') finalStatus = 'success'
            if (entry.status === 'failed' || entry.type === 'error') finalStatus = 'failed'
        }

        if (done) break
    }

    if (buffer.trim()) {
        const entry = JSON.parse(buffer) as RedeployLogEntry
        onLog(entry)
        if (entry.status === 'success') finalStatus = 'success'
        if (entry.status === 'failed' || entry.type === 'error') finalStatus = 'failed'
    }

    if (finalStatus !== 'success') throw new Error('Redeploy did not complete successfully.')
}

// =====================
// Main component
// =====================
export function MyAppDetailPage() {
    const { t, i18n } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const { appId } = useParams()
    const location = useLocation()
    const navigate = useNavigate()
    const [searchParams, setSearchParams] = useSearchParams()
    const queryClient = useQueryClient()
    const locationState = (location.state ?? null) as MyAppsDetailLocationState | null
    const initialTab = searchParams.get('tab')
    const [selectedTab, setSelectedTab] = useState<DetailTabKey>(() => {
        if (initialTab && ['overview', 'access', 'container', 'volumes', 'php', 'database', 'monitor', 'compose', 'uninstall'].includes(initialTab)) {
            return initialTab as DetailTabKey
        }

        return 'overview'
    })
    const [actionInProgress, setActionInProgress] = useState<LifecycleActionKey | null>(null)
    const [feedback, setFeedback] = useState<ActionFeedback | null>(null)
    const [redeployDialogOpen, setRedeployDialogOpen] = useState(false)
    const [redeployPullImage, setRedeployPullImage] = useState(false)
    const [redeployLogs, setRedeployLogs] = useState<RedeployLogEntry[]>([])
    const [uninstallDialogOpen, setUninstallDialogOpen] = useState(false)
    const [purgeData, setPurgeData] = useState(false)
    const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({})
    const [volumeBackups, setVolumeBackups] = useState<VolumeBackupRow[]>([])
    const [volumeBackupLoading, setVolumeBackupLoading] = useState(false)
    const [volumeBackupError, setVolumeBackupError] = useState<string | null>(null)
    const [createBackupDialogOpen, setCreateBackupDialogOpen] = useState(false)
    const [deleteBackupTarget, setDeleteBackupTarget] = useState<VolumeBackupRow | null>(null)
    const [restoreBackupTarget, setRestoreBackupTarget] = useState<VolumeBackupRow | null>(null)
    const [deleteBackupConfirmed, setDeleteBackupConfirmed] = useState(false)
    const [restoreBackupConfirmed, setRestoreBackupConfirmed] = useState(false)
    const [volumeBackupAction, setVolumeBackupAction] = useState<'create' | 'delete' | 'restore' | null>(null)
    const [composeStep, setComposeStep] = useState(0)
    const [showPhpMigrationForm, setShowPhpMigrationForm] = useState(false)
    const [phpTargetVersion, setPhpTargetVersion] = useState('')
    const [phpMigrationRemarks, setPhpMigrationRemarks] = useState('')
    const [phpMigrationSubmitting, setPhpMigrationSubmitting] = useState(false)
    const [contentScopeRect, setContentScopeRect] = useState<ContentScopeRect | null>(null)
    const [activeVolumeFileManager, setActiveVolumeFileManager] = useState<{ volumeId: string; label: string } | null>(null)

    useEffect(() => {
        const openedFromIntent = hasMyAppsDetailOverlayIntent(appId)

        if (canOpenMyAppsDetailOverlay(appId, location.pathname)) {
            return () => {
                if (openedFromIntent) {
                    clearMyAppsDetailOverlayIntent(appId)
                }
            }
        }

        if (/^\/myapps\/[^/]+/.test(location.pathname)) {
            navigate('/myapps', { replace: true })
        }

        return () => {
            if (openedFromIntent) {
                clearMyAppsDetailOverlayIntent(appId)
            }
        }
    }, [appId, location.pathname, navigate])

    const { data, error, isLoading, refetch } = useMyAppDetail(appId)
    const canLoadPhpRuntime = canProbePhpRuntime(data?.containers, data?.app_id)
    const phpInfoQuery = useMyAppPhpInfo(data?.app_id, Boolean(data?.is_php_app && selectedTab === 'php' && canLoadPhpRuntime))
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const isDarkMode = colorMode === 'dark'
    const surfacePalette = getSurfacePalette(isDarkMode)
    const dialogPalette = getDetailDialogPalette(isDarkMode)
    const contentScopeContainer = typeof document === 'undefined' ? null : document.querySelector('#app-shell-main')
    const detailSurfaceVars = useMemo(() => ({
        '--myapps-detail-shell-bg': surfacePalette.dialogBg,
        '--myapps-detail-surface': surfacePalette.panelBg,
        '--myapps-detail-surface-soft': surfacePalette.panelSoft,
        '--myapps-detail-surface-muted': surfacePalette.panelMuted,
        '--myapps-detail-border': surfacePalette.border,
        '--myapps-detail-border-strong': surfacePalette.borderStrong,
        '--myapps-detail-text': surfacePalette.text,
        '--myapps-detail-text-strong': surfacePalette.text,
        '--myapps-detail-muted': surfacePalette.subtleText,
        '--myapps-detail-subtle': surfacePalette.placeholderText,
        '--myapps-detail-accent': '#1767d1',
        '--myapps-detail-accent-hover': '#1767d1',
        '--myapps-detail-accent-soft': isDarkMode ? 'rgba(23, 103, 209, 0.2)' : 'rgba(23, 103, 209, 0.1)',
        '--myapps-detail-accent-disabled': isDarkMode ? 'rgba(23, 103, 209, 0.2)' : '#dce9f8',
        '--myapps-detail-accent-contrast': '#ffffff',
        '--myapps-detail-danger': surfacePalette.danger,
        '--myapps-detail-warning': surfacePalette.warningSoft,
        '--myapps-detail-warning-text': surfacePalette.warning,
        '--myapps-detail-action-bg': surfacePalette.actionBg,
        '--myapps-detail-action-hover': surfacePalette.actionHover,
        '--myapps-detail-action-border': surfacePalette.border,
        '--myapps-detail-action-border-strong': surfacePalette.borderStrong,
        '--myapps-detail-action-text': surfacePalette.subtleText,
        '--myapps-detail-action-text-hover': surfacePalette.text,
        '--myapps-detail-action-disabled-bg': surfacePalette.panelSoft,
        '--myapps-detail-action-disabled-text': surfacePalette.placeholderText,
        '--myapps-detail-nav-hover-bg': surfacePalette.actionBg,
        '--myapps-detail-nav-active-bg': '#1767d1',
        '--myapps-detail-nav-active-text': '#ffffff',
        '--myapps-detail-success-soft': isDarkMode ? 'rgba(52, 211, 153, 0.16)' : 'rgba(16, 185, 129, 0.12)',
        '--myapps-detail-success-text': isDarkMode ? '#86efac' : '#047857',
        '--myapps-detail-warning-soft': isDarkMode ? 'rgba(251, 191, 36, 0.16)' : 'rgba(245, 158, 11, 0.12)',
        '--myapps-detail-warning-strong': isDarkMode ? '#fcd34d' : '#b45309',
        '--myapps-detail-danger-soft': isDarkMode ? 'rgba(248, 113, 113, 0.16)' : 'rgba(239, 68, 68, 0.12)',
        '--myapps-detail-danger-text': isDarkMode ? '#fca5a5' : '#b91c1c',
    }) as CSSProperties, [surfacePalette])
    const primaryToolbarButtonStyle = useMemo(() => ({
        minWidth: 36,
        width: 36,
        height: 36,
        padding: '5px',
        borderRadius: 4,
        border: 'none',
        backgroundColor: '#1767d1',
        color: '#ffffff',
        boxShadow: 'none',
    }) as CSSProperties, [])
    const disabledPrimaryToolbarButtonStyle = useMemo(() => ({
        ...primaryToolbarButtonStyle,
        backgroundColor: isDarkMode ? 'rgba(23,103,209,0.2)' : '#dce9f8',
        color: 'rgba(255,255,255,0.72)',
    }) as CSSProperties, [primaryToolbarButtonStyle, isDarkMode])
    const closeToolbarButtonStyle = useMemo(() => ({
        width: 40,
        height: 40,
        padding: 0,
        borderRadius: 999,
        border: 'none',
        backgroundColor: 'transparent',
        color: surfacePalette.subtleText,
        boxShadow: 'none',
    }) as CSSProperties, [surfacePalette.subtleText])
    const contentScopedDialogPlacementSx = useMemo(() => ({
        '& .MuiDialog-container': {
            alignItems: 'flex-start',
            justifyContent: 'center',
            pt: { xs: 3, md: 3 },
            pb: { xs: 1.5, md: 2.5 },
        },
    }), [])
    const dialogCancelButtonSx = useMemo(() => ({
        minWidth: 68,
        borderRadius: 0,
        boxShadow: 'none',
        border: `1px solid ${dialogPalette.border}`,
        backgroundColor: surfacePalette.actionBg,
        color: dialogPalette.subtleText,
        '&:hover': {
            backgroundColor: surfacePalette.actionHover,
            color: dialogPalette.text,
            boxShadow: 'none',
        },
    }), [dialogPalette.border, dialogPalette.subtleText, dialogPalette.text, surfacePalette.actionBg, surfacePalette.actionHover])
    const dialogPrimaryButtonSx = useMemo(() => ({
        minWidth: 68,
        borderRadius: 0,
        boxShadow: 'none',
        '&:hover': {
            boxShadow: 'none',
        },
    }), [])
    const dialogAccentButtonSx = useMemo(() => ({
        ...dialogPrimaryButtonSx,
        backgroundColor: dialogPalette.accent,
        color: '#ffffff',
        '&:hover': {
            backgroundColor: isDarkMode ? '#2b7be0' : '#1d4ed8',
            boxShadow: 'none',
        },
    }), [dialogPalette.accent, dialogPrimaryButtonSx, isDarkMode])
    const dialogWarningButtonSx = useMemo(() => ({
        ...dialogPrimaryButtonSx,
        backgroundColor: '#ffbc00',
        border: '1px solid #ffbc00',
        color: '#313a46',
        '&:hover': {
            backgroundColor: '#e0a700',
            border: '1px solid #e0a700',
            boxShadow: 'none',
        },
    }), [dialogPrimaryButtonSx])

    const detailTabs = useMemo(() => (data ? getDetailTabs(data) : ['overview' as const]), [data])
    const portEntries = useMemo(() => getPortEntries(data?.env), [data?.env])
    const databaseRows = useMemo(() => (data ? getDatabaseRows(data) : []), [data])
    const containerStateSummary = useMemo(() => getContainerStateSummary(data?.containers), [data?.containers])
    const sortedVolumes = useMemo(() => {
        const volumes = [...(data?.volumes ?? [])]
        return volumes.sort((a, b) => getVolumeLabel(a).localeCompare(getVolumeLabel(b)))
    }, [data?.volumes])
    const composeSteps = useMemo(() => ([
        {
            label: t('myAppsDetailPage.tabs.compose.steps.modify.label'),
            description: t('myAppsDetailPage.tabs.compose.steps.modify.description'),
            action: t('myAppsDetailPage.tabs.compose.steps.modify.action'),
        },
        {
            label: t('myAppsDetailPage.tabs.compose.steps.redeploy.label'),
            description: t('myAppsDetailPage.tabs.compose.steps.redeploy.description'),
            action: t('myAppsDetailPage.tabs.compose.steps.redeploy.action'),
        },
    ]), [t])

    useEffect(() => {
        if (!detailTabs.includes(selectedTab)) {
            if (selectedTab === 'database' && detailTabs.includes('volumes') && databaseRows.length > 0) {
                setSelectedTab('volumes')
                return
            }

            setSelectedTab(detailTabs[0] ?? 'overview')
        }
    }, [databaseRows.length, detailTabs, selectedTab])

    useEffect(() => {
        if (!(contentScopeContainer instanceof HTMLElement)) {
            return
        }

        const restoreScrollTop = typeof locationState?.backgroundScrollTop === 'number' ? locationState.backgroundScrollTop : contentScopeContainer.scrollTop

        contentScopeContainer.scrollTop = restoreScrollTop

        const updateScopeRect = () => {
            const rect = contentScopeContainer.getBoundingClientRect()
            setContentScopeRect({
                top: rect.top,
                left: rect.left,
                width: rect.width,
                height: rect.height,
            })
        }

        updateScopeRect()

        window.addEventListener('resize', updateScopeRect)
        return () => {
            window.removeEventListener('resize', updateScopeRect)
        }
    }, [contentScopeContainer, locationState?.backgroundScrollTop])

    useEffect(() => {
        if (!(contentScopeContainer instanceof HTMLElement)) {
            return
        }

        const lockedScrollTop = typeof locationState?.backgroundScrollTop === 'number' ? locationState.backgroundScrollTop : contentScopeContainer.scrollTop
        const previousOverflowY = contentScopeContainer.style.overflowY
        const previousOverscrollBehavior = contentScopeContainer.style.overscrollBehavior

        contentScopeContainer.scrollTop = lockedScrollTop
        contentScopeContainer.style.overflowY = 'hidden'
        contentScopeContainer.style.overscrollBehavior = 'contain'

        return () => {
            contentScopeContainer.style.overflowY = previousOverflowY
            contentScopeContainer.style.overscrollBehavior = previousOverscrollBehavior
            contentScopeContainer.scrollTop = lockedScrollTop
        }
    }, [contentScopeContainer, locationState?.backgroundScrollTop])

    useEffect(() => {
        if (!/^\/myapps\/[^/]+/.test(location.pathname)) {
            return
        }

        const urlTab = searchParams.get('tab')
        if (urlTab === selectedTab) {
            return
        }

        const nextParams = new URLSearchParams(searchParams)
        nextParams.set('tab', selectedTab)
        setSearchParams(nextParams, { replace: true })
    }, [location.pathname, searchParams, selectedTab, setSearchParams])

    useEffect(() => {
        if (selectedTab !== 'compose') {
            setComposeStep(0)
            return
        }

        if (consumePendingComposeReturn(appId)) {
            setComposeStep(1)
            return
        }

        setComposeStep(0)
    }, [appId, selectedTab])

    useEffect(() => {
        if (!appId) {
            return
        }

        rememberMyAppsDetailRoute(`/myapps/${encodeURIComponent(appId)}?tab=${encodeURIComponent(selectedTab)}`)
    }, [appId, selectedTab])

    useEffect(() => {
        if (!deleteBackupTarget) {
            setDeleteBackupConfirmed(false)
        }
    }, [deleteBackupTarget])

    useEffect(() => {
        if (!restoreBackupTarget) {
            setRestoreBackupConfirmed(false)
        }
    }, [restoreBackupTarget])

    useEffect(() => {
        if (!data?.app_id || selectedTab !== 'volumes') return

        let cancelled = false
        setVolumeBackupLoading(true)
        setVolumeBackupError(null)

        void fetchBackupSnapshots(data.app_id)
            .then((snapshots) => {
                if (cancelled) return
                setVolumeBackups(formatBackupRows(snapshots, locale))
            })
            .catch((err) => {
                if (cancelled) return
                setVolumeBackups([])
                setVolumeBackupError(err instanceof Error ? err.message : t('myAppsDetailPage.tabs.volumes.backups.loadFailed'))
            })
            .finally(() => {
                if (!cancelled) setVolumeBackupLoading(false)
            })

        return () => {
            cancelled = true
        }
    }, [data?.app_id, locale, selectedTab, t])

    async function refreshAfterAction() {
        await Promise.all([
            queryClient.invalidateQueries({ queryKey: ['my-apps'] }),
            queryClient.invalidateQueries({ queryKey: ['my-app-detail', appId] }),
        ])
        setTimeout(() => {
            void queryClient.invalidateQueries({ queryKey: ['my-apps'] })
            void queryClient.invalidateQueries({ queryKey: ['my-app-detail', appId] })
        }, 1500)
    }

    const isComposeApp = data?.app_dist === 'compose'

    async function handleSimpleAction(actionKey: 'start' | 'stop' | 'restart') {
        if (!data) return
        const apiBase = isComposeApp ? '/api/compose-apps' : '/api/apps'
        const actionMap = {
            start: { method: 'POST' as const, url: `${apiBase}/${encodeURIComponent(data.app_id)}/start`, msg: t('myAppsDetailPage.feedback.startSuccess', { appId: data.app_id }) },
            stop: { method: 'POST' as const, url: `${apiBase}/${encodeURIComponent(data.app_id)}/stop`, msg: t('myAppsDetailPage.feedback.stopSuccess', { appId: data.app_id }) },
            restart: { method: 'POST' as const, url: `${apiBase}/${encodeURIComponent(data.app_id)}/restart`, msg: t('myAppsDetailPage.feedback.restartSuccess', { appId: data.app_id }) },
        }
        const cfg = actionMap[actionKey]
        setActionInProgress(actionKey)
        try {
            await runLifecycleRequest(cfg.url, cfg.method)
            await refreshAfterAction()
            setFeedback({ severity: 'success', message: cfg.msg })
        } catch (err) {
            setFeedback({ severity: 'error', message: err instanceof Error ? err.message : t('myAppsDetailPage.feedback.genericError') })
        } finally {
            setActionInProgress(null)
        }
    }

    async function handleRedeploy() {
        if (!data) return
        setActionInProgress('redeploy')
        setRedeployLogs([])
        try {
            if (isComposeApp) {
                // Compose apps use a simple POST (no streaming)
                await runLifecycleRequest(
                    `/api/compose-apps/${encodeURIComponent(data.app_id)}/redeploy`,
                    'POST',
                )
            } else {
                await runRedeployRequest(data.app_id, redeployPullImage, (entry) => setRedeployLogs((prev) => [...prev, entry]))
            }
            await refreshAfterAction()
            setFeedback({ severity: 'success', message: t('myAppsDetailPage.feedback.redeploySuccess', { appId: data.app_id }) })
        } catch (err) {
            setFeedback({ severity: 'error', message: err instanceof Error ? err.message : t('myAppsDetailPage.feedback.genericError') })
        } finally {
            setActionInProgress(null)
        }
    }

    async function handleUninstall() {
        if (!data) return
        setActionInProgress('uninstall')
        try {
            if (isComposeApp) {
                await runLifecycleRequest(`/api/compose-apps/${encodeURIComponent(data.app_id)}`, 'DELETE')
            } else {
                await runLifecycleRequest(`/api/apps/${encodeURIComponent(data.app_id)}/uninstall?purge_data=${String(purgeData)}`, 'DELETE')
            }
            await queryClient.invalidateQueries({ queryKey: ['my-apps'] })
            setFeedback({ severity: 'success', message: t('myAppsDetailPage.feedback.uninstallSuccess', { appId: data.app_id }) })
            navigate('/myapps')
        } catch (err) {
            setFeedback({ severity: 'error', message: err instanceof Error ? err.message : t('myAppsDetailPage.feedback.genericError') })
        } finally {
            setActionInProgress(null)
            setUninstallDialogOpen(false)
        }
    }

    async function refreshVolumeBackups() {
        if (!data?.app_id) return
        setVolumeBackupLoading(true)
        setVolumeBackupError(null)
        try {
            const snapshots = await fetchBackupSnapshots(data.app_id)
            setVolumeBackups(formatBackupRows(snapshots, locale))
        } catch (err) {
            setVolumeBackups([])
            setVolumeBackupError(err instanceof Error ? err.message : t('myAppsDetailPage.tabs.volumes.backups.loadFailed'))
        } finally {
            setVolumeBackupLoading(false)
        }
    }

    async function handleCreateBackup() {
        if (!data?.app_id) return
        setVolumeBackupAction('create')
        try {
            await createAppBackup(data.app_id)
            await refreshVolumeBackups()
            setCreateBackupDialogOpen(false)
            setFeedback({ severity: 'success', message: t('myAppsDetailPage.tabs.volumes.backups.createSuccess') })
        } catch (err) {
            setFeedback({ severity: 'error', message: err instanceof Error ? err.message : t('myAppsDetailPage.tabs.volumes.backups.createFailed') })
        } finally {
            setVolumeBackupAction(null)
        }
    }

    async function handleDeleteBackup() {
        if (!deleteBackupTarget) return
        setVolumeBackupAction('delete')
        try {
            await deleteAppBackup(deleteBackupTarget.fullId)
            await refreshVolumeBackups()
            setDeleteBackupTarget(null)
            setFeedback({ severity: 'success', message: t('myAppsDetailPage.tabs.volumes.backups.deleteSuccess') })
        } catch (err) {
            setFeedback({ severity: 'error', message: err instanceof Error ? err.message : t('myAppsDetailPage.tabs.volumes.backups.deleteFailed') })
        } finally {
            setVolumeBackupAction(null)
        }
    }

    async function handleRestoreBackup() {
        if (!data?.app_id || !restoreBackupTarget) return
        setVolumeBackupAction('restore')
        try {
            await restoreAppBackup(data.app_id, restoreBackupTarget.fullId)
            await refreshVolumeBackups()
            await refreshAfterAction()
            setRestoreBackupTarget(null)
            setFeedback({ severity: 'success', message: t('myAppsDetailPage.tabs.volumes.backups.restoreSuccess') })
        } catch (err) {
            setFeedback({ severity: 'error', message: err instanceof Error ? err.message : t('myAppsDetailPage.tabs.volumes.backups.restoreFailed') })
        } finally {
            setVolumeBackupAction(null)
        }
    }

    function handleComposeAction(stepIndex: number) {
        if (!data) return

        if (stepIndex === 0) {
            const composeRoute = `/myapps/${encodeURIComponent(data.app_id)}?tab=compose`
            markPendingComposeReturn(data.app_id)
            rememberMyAppsDetailRoute(composeRoute)
            openProductPath(getComposeRepositoryTarget(data), navigate, composeRoute, true)
            setComposeStep(1)
            return
        }

        setComposeStep(1)
        setRedeployLogs([])
        setRedeployDialogOpen(true)
    }

    async function handlePhpMigrationRequest() {
        if (!data?.app_id) return

        if (!phpTargetVersion.trim()) {
            setFeedback({ severity: 'error', message: t('myAppsDetailPage.tabs.php.validation.version') })
            return
        }

        if (!phpMigrationRemarks.trim()) {
            setFeedback({ severity: 'error', message: t('myAppsDetailPage.tabs.php.validation.remarks') })
            return
        }

        setPhpMigrationSubmitting(true)
        try {
            const result = await submitPhpMigrationRequest(data.app_id, phpTargetVersion.trim(), phpMigrationRemarks.trim())
            setFeedback({ severity: 'success', message: result.details || result.message || t('myAppsDetailPage.tabs.php.migration.submitSuccess') })
            setShowPhpMigrationForm(false)
            setPhpTargetVersion('')
            setPhpMigrationRemarks('')
        } catch (err) {
            setFeedback({ severity: 'error', message: err instanceof Error ? err.message : t('myAppsDetailPage.feedback.genericError') })
        } finally {
            setPhpMigrationSubmitting(false)
        }
    }

    const containerStates = (data?.containers ?? [])
        .map((container) => (typeof container.State === 'string' ? container.State : typeof container.state === 'string' ? container.state : 'unknown'))

    // Keep disable semantics consistent with legacy plugin appdetail.js
    const disableStartByState = containerStates.some((state) => ['running', 'restarting', 'paused', 'created'].includes(state))
    const disableStopByState = containerStates.length === 0 || containerStates.every((state) => state === 'exited')

    const isStartDisabled = !data || actionInProgress !== null || disableStartByState
    const isStopDisabled = !data || actionInProgress !== null || disableStopByState
    const isRestartDisabled = !data || actionInProgress !== null
    const isRedeployDisabled = !data || actionInProgress !== null

    const tabLabels: Record<DetailTabKey, string> = {
        overview: t('myAppsDetailPage.tabs.overview.label'),
        access: t('myAppsDetailPage.tabs.access.label'),
        container: t('myAppsDetailPage.tabs.container.label'),
        volumes: t('myAppsDetailPage.tabs.volumes.label'),
        php: t('myAppsDetailPage.tabs.php.label'),
        database: t('myAppsDetailPage.tabs.database.label'),
        monitor: t('myAppsDetailPage.tabs.monitor.label'),
        compose: t('myAppsDetailPage.tabs.compose.label'),
        uninstall: isComposeApp ? t('myAppsDetailPage.tabs.uninstall.removeLabel') : t('myAppsDetailPage.tabs.uninstall.label'),
    }

    const tabTitles: Record<DetailTabKey, string> = {
        overview: t('myAppsDetailPage.tabs.overview.title'),
        access: t('myAppsDetailPage.tabs.access.title'),
        container: t('myAppsDetailPage.tabs.container.title'),
        volumes: t('myAppsDetailPage.tabs.volumes.title'),
        php: t('myAppsDetailPage.tabs.php.title'),
        database: t('myAppsDetailPage.tabs.database.title'),
        monitor: t('myAppsDetailPage.tabs.monitor.title'),
        compose: t('myAppsDetailPage.tabs.compose.title'),
        uninstall: t('myAppsDetailPage.tabs.uninstall.title'),
    }

    const overviewEntries = useMemo(
        () => data
            ? isComposeApp
                ? [
                    { label: t('myAppsDetailPage.summary.appId'), value: data.app_id },
                    { label: t('myAppsDetailPage.summary.createdAt'), value: formatCreationDate(data.creationDate, locale) },
                ]
                : [
                    { label: t('myAppsDetailPage.summary.appId'), value: data.app_id },
                    { label: t('myAppsDetailPage.summary.appName'), value: data.app_name || '-' },
                    { label: t('myAppsDetailPage.summary.appVersion'), value: data.app_version || '-' },
                    ...portEntries.map(([key, labelKey, value]) => ({
                        label: labelKey === key ? getDetailPortLabel(key, t, locale) : t(labelKey),
                        value,
                    })),
                    { label: t('myAppsDetailPage.summary.createdAt'), value: formatCreationDate(data.creationDate, locale) },
                ]
            : [],
        [data, isComposeApp, locale, portEntries, t],
    )
    return (
        <>
            <div
                className={`myapps-detail-overlay${isDarkMode ? ' is-dark' : ''}`}
                style={
                    {
                        ...detailSurfaceVars,
                        ...(contentScopeRect
                            ? {
                                position: 'fixed',
                                top: contentScopeRect.top,
                                left: contentScopeRect.left,
                                width: contentScopeRect.width,
                                height: contentScopeRect.height,
                                zIndex: 1400,
                            }
                            : {}),
                    }
                }
            >
                <div className="myapps-detail-shell">

                    {/* ── Header (Modal.Header equivalent) ── */}
                    <div className="myapps-detail-header">
                        <div className="myapps-detail-header-row">
                            {/* App icon (appstore-item-content-icon col-same-height) */}
                            <div className="appstore-item-content-icon">
                                <LegacyMyAppLogo
                                    appId={data?.app_id || appId}
                                    appName={data?.app_name}
                                    logoUrl={data?.logo_url}
                                    locale={locale}
                                    size={80}
                                    marginY={0}
                                />
                            </div>

                            {/* App title + status */}
                            <div className="myapps-detail-meta">
                                <h4 className="appstore-item-content-title myapps-detail-title">
                                    {data?.app_id || appId}
                                </h4>
                                <h5 className="myapps-detail-status" style={{ color: getStatusColor(data?.status ?? 2) }}>
                                    {getStatusLabel(data?.status ?? 2)}
                                    {' : '}
                                    <span className="myapps-detail-status-meta">{containerStateSummary}</span>
                                </h5>
                            </div>

                            {/* Action buttons */}
                            <div className="myapps-detail-actions">
                                {/* Start */}
                                <Button
                                    className="myapps-detail-toolbar-button"
                                    disabled={isStartDisabled}
                                    onClick={() => void handleSimpleAction('start')}
                                    style={isStartDisabled ? disabledPrimaryToolbarButtonStyle : primaryToolbarButtonStyle}
                                    title={t('myAppsDetailPage.actions.start')}
                                    variant="contained"
                                >
                                    <BtnIcon className="dripicons-media-play" spinning={actionInProgress === 'start'} />
                                </Button>
                                {/* Stop */}
                                <Button
                                    className="myapps-detail-toolbar-button"
                                    disabled={isStopDisabled}
                                    onClick={() => void handleSimpleAction('stop')}
                                    style={isStopDisabled ? disabledPrimaryToolbarButtonStyle : primaryToolbarButtonStyle}
                                    title={t('myAppsDetailPage.actions.stop')}
                                    variant="contained"
                                >
                                    <BtnIcon className="dripicons-power" spinning={actionInProgress === 'stop'} />
                                </Button>
                                {/* Restart */}
                                <Button
                                    className="myapps-detail-toolbar-button"
                                    disabled={isRestartDisabled}
                                    onClick={() => void handleSimpleAction('restart')}
                                    style={isRestartDisabled ? disabledPrimaryToolbarButtonStyle : primaryToolbarButtonStyle}
                                    title={t('myAppsDetailPage.actions.restart')}
                                    variant="contained"
                                >
                                    <BtnIcon className="dripicons-clockwise" spinning={actionInProgress === 'restart'} />
                                </Button>
                                {/* Redeploy */}
                                <Button
                                    className="myapps-detail-toolbar-button"
                                    disabled={isRedeployDisabled}
                                    onClick={() => { setRedeployLogs([]); setRedeployDialogOpen(true) }}
                                    style={isRedeployDisabled ? disabledPrimaryToolbarButtonStyle : primaryToolbarButtonStyle}
                                    title={t('myAppsDetailPage.actions.redeploy')}
                                    variant="contained"
                                >
                                    <BtnIcon className="dripicons-cutlery" spinning={actionInProgress === 'redeploy'} />
                                </Button>
                                {/* Close */}
                                <IconButton
                                    className="myapps-detail-toolbar-close"
                                    onClick={() => navigate('/myapps')}
                                    style={closeToolbarButtonStyle}
                                    title="Close"
                                >
                                    <svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor">
                                        <path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                                    </svg>
                                </IconButton>
                            </div>
                        </div>
                    </div>

                    {/* ── Loading state ── */}
                    {isLoading ? (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, padding: '64px 24px' }}>
                            <CircularProgress size={28} />
                            <span style={{ color: '#6c757d', fontSize: '14px' }}>{t('myAppsDetailPage.states.loading')}</span>
                        </div>
                    ) : null}

                    {/* ── Error state ── */}
                    {!isLoading && error ? (
                        <div style={{ padding: 24 }}>
                            <Alert
                                action={<Button color="inherit" size="small" onClick={() => void refetch()}>{t('myAppsDetailPage.states.retry')}</Button>}
                                severity="warning"
                                variant="outlined"
                            >
                                <strong>{t('myAppsDetailPage.states.errorTitle')}</strong>
                                <br />
                                {t('myAppsDetailPage.states.errorDetail', { statusCode: error.statusCode ?? 'unknown' })}
                            </Alert>
                        </div>
                    ) : null}

                    {/* ── Body (Modal.Body row equivalent) ── */}
                    {!isLoading && !error && data ? (
                        <div className="myapps-detail-body">
                            {data.error ? (
                                <Alert severity="error" variant="outlined" style={{ marginBottom: 16 }}>
                                    {data.error}
                                </Alert>
                            ) : null}

                            {/* 2-column layout: nav (col-sm-2) + content (col-sm-10) */}
                            <div className="myapps-detail-layout">
                                {/* Left: Nav pills */}
                                <div className="myapps-detail-nav-col">
                                    <div className="nav flex-column nav-pills">
                                        {detailTabs.map((tabKey) => (
                                            <button
                                                key={tabKey}
                                                className={`nav-link${selectedTab === tabKey ? ' active' : ''}`}
                                                onClick={() => setSelectedTab(tabKey)}
                                            >
                                                {tabLabels[tabKey]}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {/* Right: Tab content */}
                                <div className="myapps-detail-content-col">
                                    {/* Panel title */}
                                    {!['overview', 'access', 'container', 'database', 'compose', 'volumes', 'uninstall', 'php'].includes(selectedTab) ? (
                                        <div className="myapps-panel-header">
                                            <h5 className="myapps-panel-title">{selectedTab === 'volumes' ? tabLabels.volumes : tabTitles[selectedTab]}</h5>
                                        </div>
                                    ) : null}

                                    {/* ── Overview ── */}
                                    {selectedTab === 'overview' ? (
                                        <div className="myapps-access-section myapps-overview-section">
                                            <div className="myapps-access-section-head">
                                                <div className="myapps-section-label-bar">
                                                    <span className="myapps-section-label-indicator" />
                                                    <span className="myapps-section-label-text">{tabLabels.overview}</span>
                                                </div>
                                            </div>
                                            <div className="myapps-php-card-body">
                                                <div className="myapps-overview-runtime-block">
                                                    {overviewEntries.map((entry, index) => (
                                                        <div className="myapps-overview-runtime-row" key={`overview-row-${index}`}>
                                                            <span className="myapps-overview-runtime-label">{entry.label}</span>
                                                            <span className="myapps-overview-runtime-value">{entry.value}</span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>
                                    ) : null}

                                    {/* ── Access ── */}
                                    {selectedTab === 'access' ? (
                                        <MyAppAccessPanel
                                            appId={data.app_id}
                                            env={data.env}
                                            isComposeApp={isComposeApp}
                                            onUpdated={refreshAfterAction}
                                            scopeRect={contentScopeRect}
                                            isDarkMode={isDarkMode}
                                        />
                                    ) : null}

                                    {/* ── Container ── */}
                                    {selectedTab === 'container' ? (
                                        <div className="myapps-access-section myapps-container-section">
                                            <div className="myapps-access-section-head">
                                                <div className="myapps-section-label-bar">
                                                    <span className="myapps-section-label-indicator" />
                                                    <span className="myapps-section-label-text">{t('myAppsDetailPage.tabs.container.title')}</span>
                                                </div>
                                                <button
                                                    className="myapps-icon-action-btn myapps-icon-action-btn-plain"
                                                    onClick={() => openProductPath(`/w9deployment/#!/${data.endpointId ?? 1}/docker/stacks/${data.app_id}?type=2&regular=false&external=true&orphaned=false`, navigate, undefined, true)}
                                                    title={t('myAppsDetailPage.tabs.container.more')}
                                                    type="button"
                                                >
                                                    <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                                                        <path d="M12 7a1.75 1.75 0 1 1 0-3.5A1.75 1.75 0 0 1 12 7Zm0 6.75a1.75 1.75 0 1 1 0-3.5 1.75 1.75 0 0 1 0 3.5Zm0 6.75a1.75 1.75 0 1 1 0-3.5 1.75 1.75 0 0 1 0 3.5Z" />
                                                    </svg>
                                                </button>
                                            </div>
                                            {(data.containers ?? []).length > 0 ? (
                                                <div className="myapps-php-card-body myapps-container-card-body">
                                                    <div className="myapps-php-runtime-card myapps-container-runtime-card">
                                                        <div className="myapps-table-wrap">
                                                            <table className="myapps-detail-table" role="table">
                                                                <thead>
                                                                    <tr>
                                                                        <th>{t('myAppsDetailPage.tabs.container.columns.name')}</th>
                                                                        <th>{t('myAppsDetailPage.tabs.container.columns.state')}</th>
                                                                        <th>{t('myAppsDetailPage.tabs.container.columns.status')}</th>
                                                                        <th className="myapps-cell-center">{t('myAppsDetailPage.tabs.container.columns.actions')}</th>
                                                                        <th>{t('myAppsDetailPage.tabs.container.columns.image')}</th>
                                                                        <th>{t('myAppsDetailPage.tabs.container.columns.created')}</th>
                                                                        <th>{t('myAppsDetailPage.tabs.container.columns.ipAddress')}</th>
                                                                        <th>{t('myAppsDetailPage.tabs.container.columns.ports')}</th>
                                                                    </tr>
                                                                </thead>
                                                                <tbody>
                                                                    {(data.containers ?? []).map((c, i) => {
                                                                        const containerId = getContainerId(c)
                                                                        const endpointId = data.endpointId ?? 1
                                                                        const state = getContainerState(c)
                                                                        const image = getContainerImage(c)
                                                                        return (
                                                                            <tr key={`${getContainerName(c)}-${i}`}>
                                                                                <td>{getContainerName(c)}</td>
                                                                                <td><ContainerStateBadge state={state} /></td>
                                                                                <td>{getContainerStatus(c)}</td>
                                                                                <td className="myapps-cell-center">
                                                                                    <div className="myapps-table-actions-inline">
                                                                                        <a href={containerId ? `/containers?target=${encodeURIComponent(`/w9deployment/#!/${endpointId}/docker/containers/${containerId}/logs`)}` : '#'} className="myapps-table-action-link" onClick={(event) => {
                                                                                            if (!containerId) return
                                                                                            event.preventDefault()
                                                                                            window.open(`/containers?target=${encodeURIComponent(`/w9deployment/#!/${endpointId}/docker/containers/${containerId}/logs`)}`, '_blank')
                                                                                        }}>
                                                                                            <i className="dripicons-document-remove noti-icon" />
                                                                                        </a>
                                                                                        {state === 'running' ? (
                                                                                            <a href={containerId ? `/containers?target=${encodeURIComponent(`/w9deployment/#!/${endpointId}/docker/containers/${containerId}/stats`)}` : '#'} className="myapps-table-action-link" onClick={(event) => {
                                                                                                if (!containerId) return
                                                                                                event.preventDefault()
                                                                                                window.open(`/containers?target=${encodeURIComponent(`/w9deployment/#!/${endpointId}/docker/containers/${containerId}/stats`)}`, '_blank')
                                                                                            }}>
                                                                                                <i className="dripicons-graph-bar noti-icon" />
                                                                                            </a>
                                                                                        ) : null}
                                                                                        {state === 'running' ? (
                                                                                            <a href={containerId ? `/containers?target=${encodeURIComponent(`/w9deployment/#!/${endpointId}/docker/containers/${containerId}/exec`)}` : '#'} className="myapps-table-action-link" onClick={(event) => {
                                                                                                if (!containerId) return
                                                                                                event.preventDefault()
                                                                                                window.open(`/containers?target=${encodeURIComponent(`/w9deployment/#!/${endpointId}/docker/containers/${containerId}/exec`)}`, '_blank')
                                                                                            }}>
                                                                                                <i className="dripicons-code noti-icon" />
                                                                                            </a>
                                                                                        ) : null}
                                                                                    </div>
                                                                                </td>
                                                                                <td title={image}>{image.length > 20 ? `${image.slice(0, 20)}...` : image}</td>
                                                                                <td>{getContainerCreatedAt(c, locale)}</td>
                                                                                <td>{getContainerIpAddress(c)}</td>
                                                                                <td>{getPublishedPorts(c)}</td>
                                                                            </tr>
                                                                        )
                                                                    })}
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                    </div>
                                                </div>
                                            ) : (
                                                <div className="myapps-php-card-body myapps-container-card-body">
                                                    <div className="myapps-php-runtime-card myapps-container-runtime-card myapps-detail-section-card-empty" style={{ padding: 16 }}>
                                                        <Alert severity="info" variant="outlined">{t('myAppsDetailPage.tabs.container.empty')}</Alert>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ) : null}

                                    {/* ── Volumes ── */}
                                    {selectedTab === 'volumes' ? (
                                        (sortedVolumes.length > 0 || databaseRows.length > 0) ? (
                                            <>
                                                {sortedVolumes.length > 0 ? (
                                                    <div className="myapps-access-section myapps-volume-card">
                                                        <div className="myapps-access-section-head">
                                                            <div className="myapps-section-label-bar">
                                                                <span className="myapps-section-label-indicator" />
                                                                <span className="myapps-section-label-text">{t('myAppsDetailPage.tabs.volumes.title')}</span>
                                                            </div>
                                                        </div>
                                                        <div className="myapps-php-card-body">
                                                            <div className="myapps-php-runtime-card myapps-volume-runtime-card">
                                                                <div className="myapps-table-wrap">
                                                                    <table className="myapps-detail-table" role="table">
                                                                        <thead>
                                                                            <tr>
                                                                                <th>{t('myAppsDetailPage.tabs.volumes.columns.name')}</th>
                                                                                <th>{t('myAppsDetailPage.tabs.volumes.columns.driver')}</th>
                                                                                <th>{t('myAppsDetailPage.tabs.volumes.columns.mountpoint')}</th>
                                                                                <th>{t('myAppsDetailPage.tabs.volumes.columns.created')}</th>
                                                                                <th className="myapps-cell-center">{t('myAppsDetailPage.tabs.volumes.columns.action')}</th>
                                                                            </tr>
                                                                        </thead>
                                                                        <tbody>
                                                                            {sortedVolumes.map((v, i) => {
                                                                                const volumeLabel = getVolumeLabel(v)
                                                                                const volumeId = getVolumeId(v)
                                                                                return (
                                                                                    <tr key={`${volumeLabel}-${i}`}>
                                                                                        <td>{volumeLabel}</td>
                                                                                        <td>{String(v.Driver ?? '-')}</td>
                                                                                        <td>{String(v.Mountpoint ?? '-')}</td>
                                                                                        <td>{getVolumeCreatedAt(v, locale)}</td>
                                                                                        <td className="myapps-cell-center">
                                                                                            <button
                                                                                                className="myapps-inline-link"
                                                                                                disabled={!volumeId}
                                                                                                onClick={() => setActiveVolumeFileManager({ volumeId, label: volumeLabel })}
                                                                                            >
                                                                                                {t('myAppsDetailPage.tabs.volumes.fileManager.entry')}
                                                                                            </button>
                                                                                        </td>
                                                                                    </tr>
                                                                                )
                                                                            })}
                                                                        </tbody>
                                                                    </table>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                ) : null}

                                                <div className="myapps-access-section myapps-volume-card">
                                                    <div className="myapps-access-section-head">
                                                        <div className="myapps-section-label-bar">
                                                            <span className="myapps-section-label-indicator" />
                                                            <span className="myapps-section-label-text">{t('myAppsDetailPage.tabs.volumes.backups.title')}</span>
                                                        </div>
                                                        <div className="myapps-card-header-actions">
                                                            <button
                                                                className="myapps-inline-icon-action myapps-inline-icon-action-neutral myapps-inline-icon-action-compact"
                                                                onClick={() => setCreateBackupDialogOpen(true)}
                                                                title={t('myAppsDetailPage.tabs.volumes.backups.create')}
                                                                aria-label={t('myAppsDetailPage.tabs.volumes.backups.create')}
                                                                disabled={volumeBackupAction === 'create' || volumeBackupLoading}
                                                            >
                                                                <IconAdd />
                                                            </button>
                                                            <button
                                                                className="myapps-inline-icon-action myapps-inline-icon-action-neutral myapps-inline-icon-action-compact"
                                                                onClick={() => void refreshVolumeBackups()}
                                                                title={volumeBackupLoading ? t('myAppsDetailPage.tabs.volumes.backups.refreshing') : t('myAppsDetailPage.tabs.volumes.backups.refresh')}
                                                                aria-label={volumeBackupLoading ? t('myAppsDetailPage.tabs.volumes.backups.refreshing') : t('myAppsDetailPage.tabs.volumes.backups.refresh')}
                                                                disabled={volumeBackupLoading}
                                                            >
                                                                <IconRefresh />
                                                            </button>
                                                        </div>
                                                    </div>
                                                    <div className="myapps-php-card-body">
                                                        <div className="myapps-php-runtime-card myapps-volume-runtime-card">
                                                            <div className="myapps-backup-table-shell">
                                                                <div className="myapps-table-wrap myapps-table-wrap-overlay">
                                                                    <table className="myapps-detail-table myapps-backup-detail-table" role="table">
                                                                        <thead>
                                                                            <tr>
                                                                                <th>{t('myAppsDetailPage.tabs.volumes.backups.columns.id')}</th>
                                                                                <th>{t('myAppsDetailPage.tabs.volumes.backups.columns.created')}</th>
                                                                                <th>{t('myAppsDetailPage.tabs.volumes.backups.columns.size')}</th>
                                                                                <th>{t('myAppsDetailPage.tabs.volumes.backups.columns.action')}</th>
                                                                            </tr>
                                                                        </thead>
                                                                        <tbody>
                                                                            {volumeBackupLoading && volumeBackups.length === 0 ? (
                                                                                <tr>
                                                                                    <td colSpan={4} className="myapps-empty-cell">
                                                                                        <div className="myapps-table-inline-loading" aria-live="polite">
                                                                                            <CircularProgress size={18} />
                                                                                            <span>{t('myAppsDetailPage.tabs.volumes.backups.refreshing')}</span>
                                                                                        </div>
                                                                                    </td>
                                                                                </tr>
                                                                            ) : volumeBackups.length === 0 ? (
                                                                                <tr>
                                                                                    <td colSpan={4} className="myapps-empty-cell">{volumeBackupError || t('myAppsDetailPage.tabs.volumes.backups.empty')}</td>
                                                                                </tr>
                                                                            ) : (
                                                                                volumeBackups.map((backup) => (
                                                                                    <tr key={backup.fullId}>
                                                                                        <td>{backup.id}</td>
                                                                                        <td>{backup.time}</td>
                                                                                        <td>{backup.size}</td>
                                                                                        <td>
                                                                                            <div className="myapps-table-actions-text">
                                                                                                <button className="myapps-inline-link" onClick={() => setRestoreBackupTarget(backup)}>{t('myAppsDetailPage.tabs.volumes.backups.restore')}</button>
                                                                                                <button className="myapps-inline-link myapps-inline-link-danger" onClick={() => setDeleteBackupTarget(backup)}>{t('myAppsDetailPage.tabs.volumes.backups.delete')}</button>
                                                                                            </div>
                                                                                        </td>
                                                                                    </tr>
                                                                                ))
                                                                            )}
                                                                        </tbody>
                                                                    </table>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>

                                                {databaseRows.length > 0 ? (
                                                    <div className="myapps-access-section myapps-volume-card">
                                                        <div className="myapps-access-section-head">
                                                            <div className="myapps-section-label-bar">
                                                                <span className="myapps-section-label-indicator" />
                                                                <span className="myapps-section-label-text">{t('myAppsDetailPage.tabs.database.title')}</span>
                                                            </div>
                                                        </div>
                                                        <div className="myapps-php-card-body">
                                                            <div className="myapps-php-runtime-card myapps-volume-runtime-card">
                                                                <div className="myapps-database-card-body myapps-volume-database-card-body">
                                                                    <table className="myapps-database-table" role="table">
                                                                        <thead>
                                                                            <tr>
                                                                                <th>{t('myAppsDetailPage.tabs.database.columns.type')}</th>
                                                                                <th>{t('myAppsDetailPage.tabs.database.columns.host')}</th>
                                                                                <th>{t('myAppsDetailPage.tabs.database.columns.account')}</th>
                                                                                <th>{t('myAppsDetailPage.tabs.database.columns.password')}</th>
                                                                                <th>{t('myAppsDetailPage.tabs.database.columns.tool')}</th>
                                                                            </tr>
                                                                        </thead>
                                                                        <tbody>
                                                                            {databaseRows.map((row) => (
                                                                                <tr key={`${row.type}-${row.host}`}>
                                                                                    <td>{row.type}</td>
                                                                                    <td>{row.host}</td>
                                                                                    <td>{row.account}</td>
                                                                                    <td>
                                                                                        <div className="myapps-database-password-cell">
                                                                                            <span className="myapps-database-password-text">
                                                                                                {showPasswords[row.type] ? row.password : '•'.repeat(Math.min(row.password.length, 16))}
                                                                                            </span>
                                                                                            <button
                                                                                                className="myapps-database-icon-btn"
                                                                                                title={showPasswords[row.type] ? t('myAppsDetailPage.tabs.database.hidePassword') : t('myAppsDetailPage.tabs.database.showPassword')}
                                                                                                onClick={() => setShowPasswords((prev) => ({ ...prev, [row.type]: !prev[row.type] }))}
                                                                                            >
                                                                                                {showPasswords[row.type] ? <IconEyeOff /> : <IconEye />}
                                                                                            </button>
                                                                                            <button
                                                                                                className="myapps-database-icon-btn"
                                                                                                title={t('myAppsDetailPage.tabs.database.copy')}
                                                                                                onClick={async () => {
                                                                                                    try {
                                                                                                        await copyTextWithFallback(row.password)
                                                                                                        setFeedback({ severity: 'success', message: t('myAppsDetailPage.tabs.database.copied') })
                                                                                                    } catch {
                                                                                                        setFeedback({ severity: 'error', message: t('myAppsDetailPage.tabs.database.copyFailed') })
                                                                                                    }
                                                                                                }}
                                                                                            >
                                                                                                <IconCopy />
                                                                                            </button>
                                                                                        </div>
                                                                                    </td>
                                                                                    <td>
                                                                                        {row.toolApps.length > 0 ? (
                                                                                            <div className="myapps-table-actions-text">
                                                                                                {row.toolApps.map((tool) => (
                                                                                                    <button
                                                                                                        key={`${row.type}-${tool.appKey}`}
                                                                                                        className="myapps-inline-link"
                                                                                                        onClick={() => openAppStoreTool(tool.appKey, navigate)}
                                                                                                    >
                                                                                                        {tool.label}
                                                                                                    </button>
                                                                                                ))}
                                                                                            </div>
                                                                                        ) : '-'}
                                                                                    </td>
                                                                                </tr>
                                                                            ))}
                                                                        </tbody>
                                                                    </table>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                ) : null}
                                            </>
                                        ) : (
                                            <div className="myapps-access-section myapps-volume-card">
                                                <div className="myapps-access-section-head">
                                                    <div className="myapps-section-label-bar">
                                                        <span className="myapps-section-label-indicator" />
                                                        <span className="myapps-section-label-text">{tabLabels.volumes}</span>
                                                    </div>
                                                </div>
                                                <div className="myapps-php-card-body">
                                                    <div className="myapps-php-runtime-card myapps-volume-runtime-card myapps-detail-section-card-empty" style={{ padding: 16 }}>
                                                        <Alert severity="info" variant="outlined">{t('myAppsDetailPage.tabs.volumes.empty')}</Alert>
                                                    </div>
                                                </div>
                                            </div>
                                        )
                                    ) : null}

                                    {/* ── PHP ── */}
                                    {selectedTab === 'php' ? (
                                        <div className="myapps-php-layout">
                                            <div className="myapps-access-section">
                                                <div className="myapps-access-section-head">
                                                    <div className="myapps-section-label-bar">
                                                        <span className="myapps-section-label-indicator" />
                                                        <span className="myapps-section-label-text">{t('myAppsDetailPage.tabs.php.runtimeTitle')}</span>
                                                    </div>
                                                </div>
                                                <div className="myapps-php-card-body">
                                                    {phpInfoQuery.isLoading ? (
                                                        <div className="myapps-access-loading">
                                                            <CircularProgress size={18} />
                                                            <span>{t('myAppsDetailPage.tabs.php.loading')}</span>
                                                        </div>
                                                    ) : null}
                                                    {!canLoadPhpRuntime ? (
                                                        <Alert severity="info" variant="outlined">
                                                            {t('myAppsDetailPage.tabs.php.unavailable')}
                                                        </Alert>
                                                    ) : null}
                                                    {phpInfoQuery.error ? (
                                                        <Alert severity={phpInfoQuery.error.statusCode === 400 ? 'info' : 'warning'} variant="outlined">
                                                            {phpInfoQuery.error.statusCode === 400
                                                                ? t('myAppsDetailPage.tabs.php.unavailable')
                                                                : t('myAppsDetailPage.tabs.php.error', { statusCode: phpInfoQuery.error.statusCode ?? 'unknown' })}
                                                        </Alert>
                                                    ) : null}
                                                    {phpInfoQuery.data ? (
                                                        <div className="myapps-php-runtime-grid">
                                                            <div className="myapps-php-runtime-card myapps-php-runtime-card-inline">
                                                                <div className="myapps-php-runtime-card-line">
                                                                    <span className="myapps-php-runtime-card-label">{t('myAppsDetailPage.tabs.php.currentVersionLabel')}</span>
                                                                    <span className="myapps-php-runtime-card-value">{phpInfoQuery.data.version}</span>
                                                                </div>
                                                                {Object.entries(phpInfoQuery.data.modules).length > 0 ? (
                                                                    <div className="myapps-php-runtime-card-value myapps-php-runtime-card-value-block myapps-php-module-groups">
                                                                        {Object.entries(phpInfoQuery.data.modules).map(([group, modules], index, array) => (
                                                                            <div className="myapps-php-module-group" key={group}>
                                                                                <strong className="myapps-php-module-title">{group}</strong>
                                                                                <div className="myapps-php-module-list">{modules.length > 0 ? modules.join(', ') : '-'}</div>
                                                                                {index < array.length - 1 ? <div className="myapps-php-module-divider" /> : null}
                                                                            </div>
                                                                        ))}
                                                                    </div>
                                                                ) : null}
                                                            </div>
                                                        </div>
                                                    ) : null}
                                                </div>
                                            </div>

                                            <div className="myapps-access-section">
                                                <div className="myapps-access-section-head">
                                                    <div className="myapps-section-label-bar">
                                                        <span className="myapps-section-label-indicator" />
                                                        <div className="myapps-section-label-stack">
                                                            <span className="myapps-section-label-text">{t('myAppsDetailPage.tabs.php.migrationTitle')}</span>
                                                            <p className="myapps-section-label-desc">{t('myAppsDetailPage.tabs.php.migration.note')}</p>
                                                        </div>
                                                    </div>
                                                    <button className={`myapps-card-header-btn${showPhpMigrationForm ? ' myapps-card-header-btn-secondary' : ''}`} onClick={() => {
                                                        setShowPhpMigrationForm((prev) => !prev)
                                                        if (showPhpMigrationForm) {
                                                            setPhpTargetVersion('')
                                                            setPhpMigrationRemarks('')
                                                        }
                                                    }}>
                                                        {showPhpMigrationForm ? t('myAppsDetailPage.tabs.php.migration.cancel') : t('myAppsDetailPage.tabs.php.migration.request')}
                                                    </button>
                                                </div>
                                                {showPhpMigrationForm ? (
                                                    <div className="myapps-php-card-body">
                                                        <div className="myapps-php-request-box">
                                                            <div className="myapps-php-request-row">
                                                                <label className="myapps-php-request-label">
                                                                    <span>{t('myAppsDetailPage.tabs.php.migration.targetVersion')}</span>
                                                                    <span className="myapps-php-request-required">*</span>
                                                                </label>
                                                                <select className={`myapps-php-request-select${phpTargetVersion ? '' : ' is-placeholder'}`} value={phpTargetVersion} onChange={(event) => setPhpTargetVersion(event.target.value)}>
                                                                    <option value="">{t('myAppsDetailPage.tabs.php.migration.selectVersion')}</option>
                                                                    <option value="7.4">PHP 7.4</option>
                                                                    <option value="8.0">PHP 8.0</option>
                                                                    <option value="8.1">PHP 8.1</option>
                                                                    <option value="8.2">PHP 8.2</option>
                                                                    <option value="8.3">PHP 8.3</option>
                                                                    <option value="other">{t('myAppsDetailPage.tabs.php.migration.otherVersion')}</option>
                                                                </select>
                                                            </div>
                                                            <div className="myapps-php-request-row myapps-php-request-row-top">
                                                                <label className="myapps-php-request-label">
                                                                    <span>{t('myAppsDetailPage.tabs.php.migration.remarks')}</span>
                                                                    <span className="myapps-php-request-required">*</span>
                                                                </label>
                                                                <div className="myapps-php-request-field myapps-php-request-field-remarks">
                                                                    <div className="myapps-php-request-note">{t('myAppsDetailPage.tabs.php.migration.remarksNote')}</div>
                                                                    <div className="myapps-php-request-example">{t('myAppsDetailPage.tabs.php.migration.remarksExample')}</div>
                                                                    <textarea className="myapps-php-request-textarea myapps-php-request-textarea-embedded" rows={4} value={phpMigrationRemarks} onChange={(event) => setPhpMigrationRemarks(event.target.value)} placeholder={t('myAppsDetailPage.tabs.php.migration.remarksPlaceholder')} />
                                                                </div>
                                                            </div>
                                                            <div className="myapps-php-request-actions">
                                                                <button className="myapps-card-header-btn" disabled={phpMigrationSubmitting} onClick={() => void handlePhpMigrationRequest()}>
                                                                    {phpMigrationSubmitting ? t('myAppsDetailPage.actions.running') : t('myAppsDetailPage.tabs.php.migration.submit')}
                                                                </button>
                                                            </div>
                                                        </div>
                                                    </div>
                                                ) : null}
                                            </div>
                                        </div>
                                    ) : null}

                                    {/* ── Database ── */}
                                    {/* ── Monitor ── */}
                                    {selectedTab === 'monitor' ? (
                                        <div style={{ maxWidth: 640 }}>
                                            <Alert severity="info" variant="outlined" style={{ marginBottom: 12 }}>
                                                {t('myAppsDetailPage.tabs.monitor.placeholder')}
                                            </Alert>
                                            <button
                                                className="myapps-action-btn"
                                                style={{ padding: '6px 14px', fontSize: 14 }}
                                                onClick={() => navigate('/gateway')}
                                            >
                                                {t('myAppsDetailPage.tabs.monitor.openGateway')}
                                            </button>
                                        </div>
                                    ) : null}

                                    {/* ── Compose ── */}
                                    {selectedTab === 'compose' ? (
                                        <div className="myapps-access-section myapps-compose-section">
                                            <div className="myapps-access-section-head">
                                                <div className="myapps-section-label-bar">
                                                    <span className="myapps-section-label-indicator" />
                                                    <div className="myapps-section-label-stack">
                                                        <span className="myapps-section-label-text">{t('myAppsDetailPage.tabs.compose.title')}</span>
                                                        <p className="myapps-section-label-desc">{t('myAppsDetailPage.tabs.compose.description')}</p>
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="myapps-php-card-body">
                                                <div className="myapps-php-runtime-card myapps-compose-runtime-card">
                                                    <div className="myapps-compose-card-body">
                                                        <Box sx={{ maxWidth: 520 }}>
                                                            <Stepper activeStep={composeStep} orientation="vertical">
                                                                {composeSteps.map((step, index) => (
                                                                    <Step key={step.label}>
                                                                        <StepLabel>{step.label}</StepLabel>
                                                                        <StepContent>
                                                                            <Typography>{step.description}</Typography>
                                                                            <Box sx={{ mb: 2, mt: 1 }}>
                                                                                <button className="myapps-card-header-btn" onClick={() => handleComposeAction(index)}>
                                                                                    {step.action}
                                                                                </button>
                                                                                <button className="myapps-compose-back-btn" disabled={index === 0} onClick={() => setComposeStep((prev) => Math.max(prev - 1, 0))}>
                                                                                    {t('myAppsDetailPage.tabs.compose.back')}
                                                                                </button>
                                                                            </Box>
                                                                        </StepContent>
                                                                    </Step>
                                                                ))}
                                                            </Stepper>
                                                        </Box>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    ) : null}

                                    {/* ── Uninstall ── */}
                                    {selectedTab === 'uninstall' ? (
                                        <div className="myapps-access-section myapps-uninstall-section">
                                            <div className="myapps-access-section-head">
                                                <div className="myapps-section-label-bar">
                                                    <span className="myapps-section-label-indicator" />
                                                    <span className="myapps-section-label-text">
                                                        {isComposeApp
                                                            ? t('myAppsDetailPage.tabs.uninstall.removeTitle')
                                                            : t('myAppsDetailPage.tabs.uninstall.title')}
                                                    </span>
                                                </div>
                                            </div>
                                            <div className="myapps-php-card-body">
                                                <div className="myapps-php-runtime-card myapps-uninstall-runtime-card">
                                                    <div className="myapps-uninstall-layout">
                                                        <div className="myapps-uninstall-copy">
                                                            <p className="myapps-uninstall-desc">
                                                                {isComposeApp
                                                                    ? t('myAppsDetailPage.tabs.uninstall.removePlaceholder')
                                                                    : t('myAppsDetailPage.tabs.uninstall.placeholder')}
                                                            </p>
                                                        </div>
                                                        <div className="myapps-uninstall-actions">
                                                            <button
                                                                className="myapps-uninstall-btn"
                                                                disabled={actionInProgress !== null}
                                                                onClick={() => setUninstallDialogOpen(true)}
                                                            >
                                                                {isComposeApp
                                                                    ? t('myAppsDetailPage.actions.remove')
                                                                    : t('myAppsDetailPage.actions.uninstall')}
                                                            </button>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        </div>
                    ) : null}
                </div>
            </div>

            {/* ── Redeploy dialog ── */}
            <SurfaceDialog
                open={redeployDialogOpen}
                onClose={() => setRedeployDialogOpen(false)}
                maxWidth="md"
                scope="content"
                scopeRect={contentScopeRect}
                contentStrategy="viewport-fixed"
                darkMode={isDarkMode}
                sx={[
                    contentScopedDialogPlacementSx,
                    {
                        zIndex: 1505,
                        '& .MuiBackdrop-root': { backgroundColor: dialogPalette.overlay },
                    },
                ]}
                paperSx={{
                    width: { xs: 'min(100%, 780px)', md: 'min(780px, calc(100% - 20px))' },
                    maxWidth: '780px',
                    borderRadius: 0,
                    backgroundColor: dialogPalette.panel,
                    color: dialogPalette.text,
                    border: `1px solid ${dialogPalette.border}`,
                    boxShadow: isDarkMode ? '0 24px 64px rgba(2, 6, 23, 0.56)' : '0 16px 40px rgba(15, 23, 42, 0.16)',
                }}
            >
                <Box sx={{ px: 2.25, py: 1.5, borderBottom: `1px solid ${dialogPalette.divider}`, backgroundColor: dialogPalette.panel }}>
                    <Typography sx={{ fontSize: 16, fontWeight: 700, color: dialogPalette.text }}>
                        {t('myAppsDetailPage.dialogs.redeployTitle')}
                    </Typography>
                </Box>
                <Box sx={{ px: 2.25, py: 2, borderBottom: `1px solid ${dialogPalette.divider}`, backgroundColor: dialogPalette.panel }}>
                    <Typography sx={{ m: 0, fontSize: 14, lineHeight: 1.7, color: dialogPalette.subtleText }}>{t('myAppsDetailPage.dialogs.redeployBody')}</Typography>
                    <Box sx={{ mt: 1.5, display: 'inline-flex', alignItems: 'center', gap: 0.75, color: dialogPalette.text }}>
                        <Typography sx={{ fontSize: 14, color: dialogPalette.text }}>{t('myAppsDetailPage.dialogs.redeployPullImage')}</Typography>
                        <Switch checked={redeployPullImage} onChange={(e) => setRedeployPullImage(e.target.checked)} color="primary" />
                    </Box>
                    {redeployLogs.length > 0 ? (
                        <div style={{ maxHeight: 220, overflowY: 'auto', backgroundColor: dialogPalette.panelMuted, color: dialogPalette.text, padding: 10, marginTop: 10, fontFamily: 'monospace', borderRadius: 6, border: `1px solid ${dialogPalette.border}` }}>
                            {redeployLogs.map((entry, i) => (
                                <div key={i} style={{ color: entry.type === 'error' ? dialogPalette.danger : dialogPalette.text, whiteSpace: 'pre-wrap', lineHeight: 1.5, fontSize: '0.9em' }}>
                                    {entry.timestamp ? `[${new Date(entry.timestamp).toLocaleTimeString()}] ` : ''}
                                    {entry.message ?? (typeof entry.data === 'string' ? entry.data : JSON.stringify(entry.data ?? entry.status ?? ''))}
                                </div>
                            ))}
                        </div>
                    ) : null}
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.25, py: 1.25, backgroundColor: dialogPalette.panel }}>
                    <Button onClick={() => setRedeployDialogOpen(false)} sx={dialogCancelButtonSx}>{t('myAppsDetailPage.dialogs.cancel')}</Button>
                    <Button
                        disabled={actionInProgress !== null}
                        onClick={() => void handleRedeploy()}
                        variant="contained"
                        sx={dialogAccentButtonSx}
                    >
                        {actionInProgress === 'redeploy' ? t('myAppsDetailPage.actions.running') : t('myAppsDetailPage.actions.redeploy')}
                    </Button>
                </Box>
            </SurfaceDialog>

            {/* ── Uninstall dialog ── */}
            <SurfaceDialog
                open={uninstallDialogOpen}
                onClose={() => setUninstallDialogOpen(false)}
                maxWidth="sm"
                scope="content"
                scopeRect={contentScopeRect}
                contentStrategy="viewport-fixed"
                darkMode={isDarkMode}
                sx={[
                    contentScopedDialogPlacementSx,
                    {
                        zIndex: 1506,
                        '& .MuiBackdrop-root': { backgroundColor: dialogPalette.overlay },
                    },
                ]}
                paperSx={{
                    width: { xs: 'min(100%, 560px)', md: 'min(560px, calc(100% - 20px))' },
                    maxWidth: '560px',
                    borderRadius: 0,
                    backgroundColor: dialogPalette.panel,
                    color: dialogPalette.text,
                    border: `1px solid ${dialogPalette.border}`,
                    boxShadow: isDarkMode ? '0 24px 64px rgba(2, 6, 23, 0.56)' : '0 16px 40px rgba(15, 23, 42, 0.16)',
                }}
            >
                <Box sx={{ px: 2.25, py: 1.5, borderBottom: `1px solid ${dialogPalette.divider}`, backgroundColor: dialogPalette.panel }}>
                    <Typography sx={{ fontSize: 16, fontWeight: 700, color: dialogPalette.text }}>
                        {isComposeApp ? t('myAppsDetailPage.dialogs.removeTitle') : t('myAppsDetailPage.dialogs.uninstallTitle')}
                    </Typography>
                </Box>
                <Box sx={{ px: 2.25, py: 2, borderBottom: `1px solid ${dialogPalette.divider}`, backgroundColor: dialogPalette.panel }}>
                    <Typography sx={{ m: 0, fontSize: 14, lineHeight: 1.7, color: dialogPalette.subtleText }}>
                        {isComposeApp
                            ? t('myAppsDetailPage.dialogs.removeBody', { appId: data?.app_id ?? appId ?? '-' })
                            : t('myAppsDetailPage.dialogs.uninstallBody', { appId: data?.app_id ?? appId ?? '-' })}
                    </Typography>
                    {!isComposeApp ? (
                        <Box sx={{ mt: 1.5, display: 'inline-flex', alignItems: 'center', gap: 0.75, color: dialogPalette.text }}>
                            <Typography sx={{ fontSize: 14, color: dialogPalette.text }}>{t('myAppsDetailPage.dialogs.uninstallPurge')}</Typography>
                            <Switch checked={purgeData} onChange={(e) => setPurgeData(e.target.checked)} color="warning" />
                        </Box>
                    ) : null}
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.25, py: 1.25, backgroundColor: dialogPalette.panel }}>
                    <Button onClick={() => setUninstallDialogOpen(false)} sx={dialogCancelButtonSx}>{t('myAppsDetailPage.dialogs.cancel')}</Button>
                    <Button
                        sx={dialogWarningButtonSx}
                        disabled={actionInProgress !== null}
                        onClick={() => void handleUninstall()}
                        variant="contained"
                    >
                        {actionInProgress === 'uninstall'
                            ? t('myAppsDetailPage.actions.running')
                            : isComposeApp
                                ? t('myAppsDetailPage.actions.remove')
                                : t('myAppsDetailPage.actions.uninstall')}
                    </Button>
                </Box>
            </SurfaceDialog>

            <SurfaceDialog
                open={createBackupDialogOpen}
                onClose={() => setCreateBackupDialogOpen(false)}
                maxWidth="md"
                scope="content"
                scopeRect={contentScopeRect}
                contentStrategy="viewport-fixed"
                darkMode={isDarkMode}
                sx={[contentScopedDialogPlacementSx, { zIndex: 1505, '& .MuiBackdrop-root': { backgroundColor: dialogPalette.overlay } }]}
                paperSx={{
                    width: { xs: 'min(100%, 780px)', md: 'min(780px, calc(100% - 20px))' },
                    maxWidth: '780px',
                    borderRadius: 0,
                    backgroundColor: dialogPalette.panel,
                    color: dialogPalette.text,
                    border: `1px solid ${dialogPalette.border}`,
                }}
            >
                <Box sx={{ px: 2.25, py: 1.5, borderBottom: `1px solid ${dialogPalette.divider}`, backgroundColor: dialogPalette.panelSoft }}>
                    <Typography sx={{ fontSize: 16, fontWeight: 700, color: dialogPalette.text }}>{t('myAppsDetailPage.tabs.volumes.backups.create')}</Typography>
                </Box>
                <Box sx={{ px: 2.25, py: 2, borderBottom: `1px solid ${dialogPalette.divider}` }}>
                    <Typography sx={{ m: 0, mb: 1.5, fontSize: 14, lineHeight: 1.7, color: dialogPalette.subtleText }}>{t('myAppsDetailPage.tabs.volumes.backups.createBody')}</Typography>
                    <Box sx={{ mb: 1.5, px: 1.5, py: 1.25, border: `1px solid ${dialogPalette.divider}`, backgroundColor: dialogPalette.panelSoft }}>
                        <Typography sx={{ fontSize: 13, fontWeight: 700, color: dialogPalette.text, mb: 0.75 }}>{t('myAppsDetailPage.tabs.volumes.backups.tipsTitle')}</Typography>
                        <Box component="ul" sx={{ m: 0, pl: 2.25, color: dialogPalette.subtleText, fontSize: 13, lineHeight: 1.7 }}>
                            <li>{t('myAppsDetailPage.tabs.volumes.backups.createTips.allVolumes')}</li>
                            <li>{t('myAppsDetailPage.tabs.volumes.backups.createTips.duration')}</li>
                            <li>{t('myAppsDetailPage.tabs.volumes.backups.createTips.accessible')}</li>
                        </Box>
                    </Box>
                    <div className="myapps-table-wrap">
                        <table className="myapps-detail-table" role="table">
                            <thead>
                                <tr>
                                    <th>{t('myAppsDetailPage.tabs.volumes.columns.name')}</th>
                                    <th>{t('myAppsDetailPage.tabs.volumes.columns.mountpoint')}</th>
                                    <th>{t('myAppsDetailPage.tabs.volumes.columns.driver')}</th>
                                </tr>
                            </thead>
                            <tbody>
                                {sortedVolumes.map((v, i) => (
                                    <tr key={`${getVolumeLabel(v)}-dialog-${i}`}>
                                        <td>{getVolumeLabel(v)}</td>
                                        <td>{String(v.Mountpoint ?? '-')}</td>
                                        <td>{String(v.Driver ?? '-')}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.25, py: 1.25 }}>
                    <Button onClick={() => setCreateBackupDialogOpen(false)} sx={dialogCancelButtonSx}>{t('myAppsDetailPage.dialogs.close')}</Button>
                    <Button variant="contained" sx={dialogAccentButtonSx} onClick={() => void handleCreateBackup()} disabled={volumeBackupAction === 'create'}>
                        {volumeBackupAction === 'create' ? t('myAppsDetailPage.actions.running') : t('myAppsDetailPage.tabs.volumes.backups.create')}
                    </Button>
                </Box>
            </SurfaceDialog>

            <SurfaceDialog
                open={Boolean(deleteBackupTarget)}
                onClose={() => setDeleteBackupTarget(null)}
                maxWidth="sm"
                scope="content"
                scopeRect={contentScopeRect}
                contentStrategy="viewport-fixed"
                darkMode={isDarkMode}
                sx={[contentScopedDialogPlacementSx, { zIndex: 1506, '& .MuiBackdrop-root': { backgroundColor: dialogPalette.overlay } }]}
                paperSx={{
                    width: { xs: 'min(100%, 560px)', md: 'min(560px, calc(100% - 20px))' },
                    maxWidth: '560px',
                    borderRadius: 0,
                    backgroundColor: dialogPalette.panel,
                    color: dialogPalette.text,
                    border: `1px solid ${dialogPalette.border}`,
                }}
            >
                <Box sx={{ px: 2.25, py: 1.5, borderBottom: `1px solid ${dialogPalette.divider}`, backgroundColor: dialogPalette.panelSoft }}>
                    <Typography sx={{ fontSize: 16, fontWeight: 700, color: dialogPalette.text }}>{t('myAppsDetailPage.tabs.volumes.backups.deleteTitle')}</Typography>
                </Box>
                <Box sx={{ px: 2.25, py: 2, borderBottom: `1px solid ${dialogPalette.divider}` }}>
                    <Typography sx={{ m: 0, fontSize: 14, lineHeight: 1.7, color: dialogPalette.subtleText }}>{t('myAppsDetailPage.tabs.volumes.backups.deleteBody')}</Typography>
                    {deleteBackupTarget ? (
                        <Box sx={{ mt: 1.5, display: 'grid', gap: 0.75, fontSize: 13, color: dialogPalette.subtleText }}>
                            <Typography sx={{ fontSize: 13, color: dialogPalette.subtleText }}>{t('myAppsDetailPage.tabs.volumes.backups.columns.id')}: {deleteBackupTarget.id}</Typography>
                            <Typography sx={{ fontSize: 13, color: dialogPalette.subtleText }}>{t('myAppsDetailPage.tabs.volumes.backups.columns.created')}: {deleteBackupTarget.time}</Typography>
                            <Typography sx={{ fontSize: 13, color: dialogPalette.subtleText }}>{t('myAppsDetailPage.tabs.volumes.backups.columns.size')}: {deleteBackupTarget.size}</Typography>
                        </Box>
                    ) : null}
                    <Box sx={{ mt: 1.75, display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                        <Checkbox checked={deleteBackupConfirmed} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setDeleteBackupConfirmed(event.target.checked)} sx={{ p: 0.25, color: dialogPalette.subtleText }} />
                        <Typography sx={{ fontSize: 13, lineHeight: 1.7, color: dialogPalette.subtleText }}>{t('myAppsDetailPage.tabs.volumes.backups.deleteConfirm')}</Typography>
                    </Box>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.25, py: 1.25 }}>
                    <Button onClick={() => setDeleteBackupTarget(null)} sx={dialogCancelButtonSx}>{t('myAppsDetailPage.dialogs.cancel')}</Button>
                    <Button variant="contained" sx={dialogWarningButtonSx} onClick={() => void handleDeleteBackup()} disabled={volumeBackupAction === 'delete' || !deleteBackupConfirmed}>
                        {volumeBackupAction === 'delete' ? t('myAppsDetailPage.actions.running') : t('myAppsDetailPage.tabs.volumes.backups.delete')}
                    </Button>
                </Box>
            </SurfaceDialog>

            <SurfaceDialog
                open={Boolean(restoreBackupTarget)}
                onClose={() => setRestoreBackupTarget(null)}
                maxWidth="sm"
                scope="content"
                scopeRect={contentScopeRect}
                contentStrategy="viewport-fixed"
                darkMode={isDarkMode}
                sx={[contentScopedDialogPlacementSx, { zIndex: 1506, '& .MuiBackdrop-root': { backgroundColor: dialogPalette.overlay } }]}
                paperSx={{
                    width: { xs: 'min(100%, 560px)', md: 'min(560px, calc(100% - 20px))' },
                    maxWidth: '560px',
                    borderRadius: 0,
                    backgroundColor: dialogPalette.panel,
                    color: dialogPalette.text,
                    border: `1px solid ${dialogPalette.border}`,
                }}
            >
                <Box sx={{ px: 2.25, py: 1.5, borderBottom: `1px solid ${dialogPalette.divider}`, backgroundColor: dialogPalette.panelSoft }}>
                    <Typography sx={{ fontSize: 16, fontWeight: 700, color: dialogPalette.text }}>{t('myAppsDetailPage.tabs.volumes.backups.restoreTitle')}</Typography>
                </Box>
                <Box sx={{ px: 2.25, py: 2, borderBottom: `1px solid ${dialogPalette.divider}` }}>
                    <Typography sx={{ m: 0, fontSize: 14, lineHeight: 1.7, color: dialogPalette.subtleText }}>{t('myAppsDetailPage.tabs.volumes.backups.restoreBody')}</Typography>
                    {restoreBackupTarget ? (
                        <Box sx={{ mt: 1.5, display: 'grid', gap: 0.75, fontSize: 13, color: dialogPalette.subtleText }}>
                            <Typography sx={{ fontSize: 13, color: dialogPalette.subtleText }}>{t('myAppsDetailPage.tabs.volumes.backups.columns.id')}: {restoreBackupTarget.id}</Typography>
                            <Typography sx={{ fontSize: 13, color: dialogPalette.subtleText }}>{t('myAppsDetailPage.tabs.volumes.backups.columns.created')}: {restoreBackupTarget.time}</Typography>
                            <Typography sx={{ fontSize: 13, color: dialogPalette.subtleText }}>{t('myAppsDetailPage.tabs.volumes.backups.columns.size')}: {restoreBackupTarget.size}</Typography>
                        </Box>
                    ) : null}
                    <Box sx={{ mt: 1.5, px: 1.5, py: 1.25, border: `1px solid ${dialogPalette.divider}`, backgroundColor: dialogPalette.panelSoft }}>
                        <Typography sx={{ fontSize: 13, fontWeight: 700, color: dialogPalette.warning, mb: 0.75 }}>{t('myAppsDetailPage.tabs.volumes.backups.tipsTitle')}</Typography>
                        <Box component="ul" sx={{ m: 0, pl: 2.25, color: dialogPalette.subtleText, fontSize: 13, lineHeight: 1.7 }}>
                            <li>{t('myAppsDetailPage.tabs.volumes.backups.restoreTips.stopAndStart')}</li>
                            <li>{t('myAppsDetailPage.tabs.volumes.backups.restoreTips.replaceData')}</li>
                            <li>{t('myAppsDetailPage.tabs.volumes.backups.restoreTips.duration')}</li>
                            <li>{t('myAppsDetailPage.tabs.volumes.backups.restoreTips.unavailable')}</li>
                            <li>{t('myAppsDetailPage.tabs.volumes.backups.restoreTips.risk')}</li>
                            <li>{t('myAppsDetailPage.tabs.volumes.backups.restoreTips.failure')}</li>
                        </Box>
                    </Box>
                    <Box sx={{ mt: 1.75, display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                        <Checkbox checked={restoreBackupConfirmed} onChange={(event: React.ChangeEvent<HTMLInputElement>) => setRestoreBackupConfirmed(event.target.checked)} sx={{ p: 0.25, color: dialogPalette.subtleText }} />
                        <Typography sx={{ fontSize: 13, lineHeight: 1.7, color: dialogPalette.subtleText }}>{t('myAppsDetailPage.tabs.volumes.backups.restoreConfirm')}</Typography>
                    </Box>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.25, py: 1.25 }}>
                    <Button onClick={() => setRestoreBackupTarget(null)} sx={dialogCancelButtonSx}>{t('myAppsDetailPage.dialogs.cancel')}</Button>
                    <Button variant="contained" sx={dialogWarningButtonSx} onClick={() => void handleRestoreBackup()} disabled={volumeBackupAction === 'restore' || !restoreBackupConfirmed}>
                        {volumeBackupAction === 'restore' ? t('myAppsDetailPage.actions.running') : t('myAppsDetailPage.tabs.volumes.backups.restore')}
                    </Button>
                </Box>
            </SurfaceDialog>

            <VolumeFileManagerDialog
                open={activeVolumeFileManager !== null}
                volumeId={activeVolumeFileManager?.volumeId ?? ''}
                volumeLabel={activeVolumeFileManager?.label ?? ''}
                darkMode={isDarkMode}
                scopeRect={contentScopeRect}
                onClose={() => setActiveVolumeFileManager(null)}
            />

            {/* ── Feedback toast ── */}
            <SurfaceFeedbackToast
                open={Boolean(feedback)}
                onClose={() => setFeedback(null)}
                severity={feedback?.severity ?? 'info'}
                message={feedback?.message ?? ''}
                scope="content"
                scopeRect={contentScopeRect}
                darkMode={isDarkMode}
            />
        </>
    )
}
