import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControlLabel,
    IconButton,
    ListItemIcon,
    ListItemText,
    Menu,
    MenuItem,
    Snackbar,
    Switch,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAppColorMode } from '../../app/providers/color-mode'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { useMyApps, type MyApp } from './use-my-apps'
import { fetchMyAppDetail } from './use-my-app-detail'
import { LegacyMyAppLogo } from './my-app-media'
import './my-apps-page.css'

// =====================
// Types
// =====================
type StatusFilter = 'all' | '1' | '2' | '3' | '4'
type RemoveType = 'inactive' | 'error'
type AppSourceKey = 'marketplace' | 'compose' | 'runtime'
type SourceFilter = 'all' | AppSourceKey
type ActionFeedback = {
    severity: 'success' | 'error' | 'info'
    message: string
}

// =====================
// Status helpers
// =====================
function getStatusBadgeClass(status: number): string {
    switch (status) {
        case 1: return 'bg-success'
        case 2: return 'bg-warning'
        case 3: return 'bg-info'
        case 4: return 'bg-danger'
        default: return 'bg-dark'
    }
}

function getStatusLabel(status: number): string {
    switch (status) {
        case 1: return 'Active'
        case 2: return 'Inactive'
        case 3: return 'Installing'
        case 4: return 'Error'
        default: return 'Unknown'
    }
}

function resolveAppSource(app: MyApp): AppSourceKey {
    if (app.app_official) {
        return 'marketplace'
    }

    const haystack = [
        app.app_dist,
        JSON.stringify(app.env ?? {}),
        JSON.stringify(app.gitConfig ?? {}),
    ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()

    if (/(runtime|python|php|java|node|go|dotnet|gunicorn|tomcat|pm2)/.test(haystack)) {
        return 'runtime'
    }

    return 'compose'
}

// =====================
// SVG Icons (dripicons equivalents)
// =====================
function IconRedeploy() {
    return (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M12 5a7 7 0 1 1-6.32 10H8a5 5 0 1 0 .53-4.25L11 13H4V6l2.58 2.58A6.96 6.96 0 0 1 12 5z" />
        </svg>
    )
}

function IconRefresh() {
    return (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
            <path d="M20 12A8 8 0 1 1 17.66 6.34" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M20 4v6h-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    )
}

function IconAppStore() {
    return (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M7 4h10l1 4h2v2h-1l-1 9H6L5 10H4V8h2l1-4Zm1.58 4h6.84l-.5-2H9.08l-.5 2ZM8 12v5h2v-5H8Zm6 0v5h2v-5h-2Z" />
        </svg>
    )
}

function IconCompose() {
    return (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
            <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M7 5v14M17 5v14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" opacity="0.7" />
        </svg>
    )
}

function IconRuntime() {
    return (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
            <path d="M12 2 4 6.5V17.5L12 22l8-4.5V6.5L12 2Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
            <path d="M12 7v10M7.5 9.5 12 12l4.5-2.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    )
}

function IconDeployMenu() {
    return (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
            <path d="M12 3v10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="m8 9 4 4 4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M5 19h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
    )
}

function IconChevronDown() {
    return (
        <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
            <path d="m7 10 5 5 5-5H7Z" />
        </svg>
    )
}

function IconTrash() {
    return (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M9 3h6l1 2h4v2H4V5h4l1-2zm1 6h2v8h-2V9zm4 0h2v8h-2V9zM7 9h2v8H7V9z" />
        </svg>
    )
}

function IconInfo() {
    return (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M11 10h2v7h-2v-7zm0-3h2v2h-2V7zm1-5C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" />
        </svg>
    )
}

// =====================
// Log formatting
// =====================
function formatInstallLogLine(value: unknown): string {
    if (typeof value === 'string') return value
    if (typeof value === 'number' || typeof value === 'boolean') return String(value)
    if (!value || typeof value !== 'object') return ''

    const entry = value as {
        status?: unknown
        id?: unknown
        message?: unknown
        details?: unknown
        progressDetail?: { current?: unknown; total?: unknown } | null
    }

    const parts: string[] = []
    if (typeof entry.status === 'string') parts.push(entry.status)
    if (typeof entry.message === 'string') parts.push(entry.message)
    if (typeof entry.details === 'string') parts.push(entry.details)
    if (typeof entry.id === 'string') parts.push(`#${entry.id}`)
    if (entry.progressDetail && typeof entry.progressDetail === 'object') {
        const nums = [entry.progressDetail.current, entry.progressDetail.total].filter((n) => typeof n === 'number')
        if (nums.length > 0) parts.push(`(${nums.join('/')})`)
    }
    if (parts.length > 0) return parts.join(' ')
    try { return JSON.stringify(value) } catch { return String(value) }
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

async function runDeleteRequest(url: string) {
    const response = await fetch(url, {
        method: 'DELETE',
        credentials: 'include',
        headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
        throw new Error(await parseJsonError(response, `Action failed: ${response.status}`))
    }
}

async function runRedeployRequest(appId: string, pullImage: boolean) {
    const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/redeploy?pullImage=${String(pullImage)}`, {
        method: 'PUT',
        credentials: 'include',
        headers: { Accept: 'text/plain' },
    })
    if (!response.ok) {
        throw new Error(await parseJsonError(response, `Redeploy failed: ${response.status}`))
    }
    await response.text()
}

// =====================
// Log / Error Dialog
// =====================
// Max sub-log lines shown inside the active stage (tail view, no scroll)
const MAX_STAGE_LOG_LINES = 24

function LogDialog({ app, onClose }: { app: MyApp | null; onClose: () => void }) {
    const { t } = useTranslation('shell')
    const isError = Boolean(app?.error)
    const isInstalling = app?.status === 3

    // stages from backend; last stage with sub_logs is the "active" one
    const stages = app?.logs ?? []
    const hasLogs = stages.some((s) => s.sub_logs && s.sub_logs.length > 0)

    return (
        <Dialog
            fullWidth
            maxWidth="md"
            open={Boolean(app)}
            onClose={onClose}
            sx={{
                '& .MuiDialog-paper': {
                    borderRadius: '4px',
                    height: '62vh',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                },
            }}
        >
            {/* ── Header ── */}
            <DialogTitle
                sx={{
                    backgroundColor: isError ? '#fa5c7c' : '#39afd1',
                    color: '#fff',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    py: 1.2,
                    px: 2,
                    flexShrink: 0,
                    userSelect: 'none',
                    fontSize: '14px',
                    fontWeight: 600,
                }}
            >
                {isInstalling && (
                    <CircularProgress size={15} thickness={5} sx={{ color: 'rgba(255,255,255,0.85)', flexShrink: 0 }} />
                )}
                <span style={{ flex: 1 }}>
                    {isError
                        ? `${t('myAppsPage.dialog.errorTitle')} — ${app?.app_id}`
                        : `${t('myAppsPage.dialog.logsTitle')} — ${app?.app_id}`}
                </span>
                <IconButton
                    size="small"
                    onClick={onClose}
                    sx={{ color: 'rgba(255,255,255,0.8)', '&:hover': { color: '#fff', backgroundColor: 'rgba(255,255,255,0.15)' } }}
                >
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                    </svg>
                </IconButton>
            </DialogTitle>

            {/* ── Error message panel ── */}
            {isError && app?.error ? (
                <div style={{
                    flexShrink: 0,
                    backgroundColor: '#fff',
                    borderBottom: '1px solid #dee2e6',
                    borderLeft: '4px solid #fa5c7c',
                    padding: '12px 18px',
                    display: 'flex',
                    gap: 10,
                    alignItems: 'flex-start',
                    maxHeight: hasLogs ? '160px' : '100%',
                    overflow: 'auto',
                }}>
                    <span style={{
                        flexShrink: 0,
                        width: 22,
                        height: 22,
                        borderRadius: '50%',
                        backgroundColor: '#fa5c7c',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#fff',
                        fontSize: '12px',
                        fontWeight: 700,
                        marginTop: 1,
                    }}>!</span>
                    <div style={{ flex: 1 }}>
                        <div style={{
                            fontSize: '12px',
                            color: '#313a46',
                            lineHeight: '1.7',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-all',
                            fontFamily: 'Menlo, Consolas, "Courier New", monospace',
                        }}>
                            {app.error}
                        </div>
                    </div>
                </div>
            ) : null}

            {/* ── Log body: 3-step stage list + tail log area ── */}
            <DialogContent sx={{ p: 0, flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', backgroundColor: '#f8f9fa' }}>

                {/* Stage tracker strip */}
                {stages.length > 0 && (
                    <div style={{
                        flexShrink: 0,
                        display: 'flex',
                        alignItems: 'stretch',
                        gap: 0,
                        borderBottom: '1px solid #dee2e6',
                        backgroundColor: '#fff',
                        padding: '0 16px',
                    }}>
                        {stages.map((stage, idx) => {
                            const isActive = idx === stages.length - 1 && isInstalling
                            const isDone = !isInstalling || idx < stages.length - 1
                            return (
                                <div key={idx} style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 6,
                                    padding: '8px 14px 8px 0',
                                    marginRight: 16,
                                    borderBottom: isActive ? '2px solid #39afd1' : isDone ? '2px solid #0acf97' : '2px solid transparent',
                                    fontSize: '12px',
                                    fontWeight: isActive ? 700 : 500,
                                    color: isActive ? '#39afd1' : isDone ? '#0acf97' : '#adb5bd',
                                    userSelect: 'none',
                                    whiteSpace: 'nowrap',
                                }}>
                                    {isActive
                                        ? <CircularProgress size={11} thickness={6} sx={{ color: '#39afd1', flexShrink: 0 }} />
                                        : isDone
                                            ? <svg viewBox="0 0 24 24" width="12" height="12" fill="#0acf97"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" /></svg>
                                            : <span style={{ width: 12, height: 12, borderRadius: '50%', border: '2px solid #dee2e6', display: 'inline-block' }} />
                                    }
                                    <span>{`${idx + 1}. ${stage.title}`}</span>
                                </div>
                            )
                        })}
                    </div>
                )}

                {/* Active stage sub-logs (tail view, no scroll) */}
                <div style={{
                    flex: 1,
                    overflow: 'hidden',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'flex-end',
                    fontFamily: 'Menlo, Consolas, "Courier New", monospace',
                    fontSize: '12px',
                    lineHeight: '1.7',
                    padding: '10px 16px 10px 16px',
                    boxSizing: 'border-box',
                }}>
                    {!hasLogs && !isError && (
                        <div style={{
                            flex: 1,
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: 14,
                            color: '#6c757d',
                        }}>
                            {isInstalling ? (
                                <>
                                    <CircularProgress size={28} thickness={4} sx={{ color: '#39afd1' }} />
                                    <span style={{ fontSize: '13px', color: '#39afd1', fontFamily: 'inherit', letterSpacing: '0.01em' }}>
                                        {stages.length > 0 ? stages[stages.length - 1].title : 'Preparing…'}
                                    </span>
                                </>
                            ) : (
                                <span style={{ fontSize: '12px', color: '#adb5bd' }}>
                                    {t('myAppsPage.dialog.noSubLogs')}
                                </span>
                            )}
                        </div>
                    )}

                    {/* Show logs of the last stage that has sub_logs */}
                    {(() => {
                        // find last stage with sub_logs
                        const activeStage = [...stages].reverse().find((s) => s.sub_logs && s.sub_logs.length > 0)
                        if (!activeStage) return null
                        const lines = (activeStage.sub_logs ?? []).filter((l) => l != null)
                        const tail = lines.slice(-MAX_STAGE_LOG_LINES)
                        const offset = lines.length - tail.length // for line numbers
                        return tail.map((line, i) => (
                            <div key={i} style={{
                                display: 'flex',
                                gap: 10,
                                padding: '1px 0',
                                color: '#313a46',
                                borderBottom: '1px solid rgba(0,0,0,0.04)',
                            }}>
                                <span style={{ color: '#adb5bd', userSelect: 'none', minWidth: 28, textAlign: 'right', flexShrink: 0, fontSize: '11px' }}>
                                    {offset + i + 1}
                                </span>
                                <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', flex: 1, overflow: 'hidden' }}>
                                    {formatInstallLogLine(line)}
                                </span>
                            </div>
                        ))
                    })()}

                    {isInstalling && hasLogs && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#39afd1', marginTop: 4 }}>
                            <CircularProgress size={10} thickness={6} sx={{ color: '#39afd1' }} />
                            <span style={{ fontSize: '11px' }}>installing…</span>
                        </div>
                    )}
                </div>
            </DialogContent>

            {/* ── Footer ── */}
            <DialogActions sx={{ borderTop: '1px solid #dee2e6', px: 2, py: 1, backgroundColor: '#fff', flexShrink: 0 }}>
                <Button onClick={onClose} size="small" variant="outlined" color="inherit" sx={{ color: '#6c757d', borderColor: '#ced4da' }}>
                    {t('myAppsPage.dialog.close')}
                </Button>
                {isError && (
                    <Button
                        size="small"
                        variant="contained"
                        sx={{ backgroundColor: '#fa5c7c', '&:hover': { backgroundColor: '#e04a68' } }}
                        onClick={() => window.open('https://www.websoft9.com/ticket', '_blank')}
                    >
                        {t('myAppsPage.dialog.support')}
                    </Button>
                )}
            </DialogActions>
        </Dialog>
    )
}

// =====================
// Main component
// =====================
export function MyAppsPage() {
    const { t, i18n } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const queryClient = useQueryClient()
    const navigate = useNavigate()
    const isDarkMode = colorMode === 'dark'
    const [searchValue, setSearchValue] = useState('')
    const [selectedStatus, setSelectedStatus] = useState<StatusFilter>('all')
    const [selectedSource, setSelectedSource] = useState<SourceFilter>('all')
    // Store only the identifier so the dialog always reads live data from the query
    const [logDialogKey, setLogDialogKey] = useState<string | null>(null)
    const [removeApp, setRemoveApp] = useState<MyApp | null>(null)
    const [removeType, setRemoveType] = useState<RemoveType>('inactive')
    const [redeployApp, setRedeployApp] = useState<MyApp | null>(null)
    const [pullImage, setPullImage] = useState(false)
    const [actionBusy, setActionBusy] = useState(false)
    const [feedback, setFeedback] = useState<ActionFeedback | null>(null)
    const [manualRefreshing, setManualRefreshing] = useState(false)
    const [deployMenuAnchor, setDeployMenuAnchor] = useState<HTMLElement | null>(null)

    const { data, error, isLoading, refetch } = useMyApps()
    const apps = data ?? []
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const palette = {
        pageBg: isDarkMode ? '#0f172a' : '#ffffff',
        panelBg: isDarkMode ? '#111827' : '#ffffff',
        panelSoft: isDarkMode ? '#162033' : '#f8fafc',
        border: isDarkMode ? 'rgba(71, 85, 105, 0.65)' : 'rgba(15, 23, 42, 0.08)',
        text: isDarkMode ? '#f8fafc' : '#111827',
        subtleText: isDarkMode ? '#94a3b8' : '#64748b',
    } as const

    async function handleManualRefresh() {
        setManualRefreshing(true)
        try {
            await refetch()
        } finally {
            setManualRefreshing(false)
        }
    }

    function getSourceLabel(source: AppSourceKey) {
        return t(`myAppsPage.source.${source}`)
    }

    useEffect(() => {
        if (apps.length === 0) return

        const activeApps = apps.filter((app) => app.status === 1)
        if (activeApps.length === 0) return

        const schedule = typeof window !== 'undefined' && 'requestIdleCallback' in window
            ? window.requestIdleCallback.bind(window)
            : (callback: IdleRequestCallback) => window.setTimeout(() => callback({
                didTimeout: false,
                timeRemaining: () => 0,
            } as IdleDeadline), 250)

        const cancel = (handle: number) => {
            if (typeof window !== 'undefined' && 'cancelIdleCallback' in window) {
                window.cancelIdleCallback(handle)
                return
            }
            clearTimeout(handle)
        }

        const handle = schedule(() => {
            activeApps.slice(0, 6).forEach((app) => {
                void queryClient.prefetchQuery({
                    queryKey: ['my-app-detail', app.app_id],
                    queryFn: async () => fetchMyAppDetail(app.app_id),
                    staleTime: 10_000,
                })
            })
        })

        return () => cancel(handle)
    }, [apps, queryClient])

    // Resolve the live app for the log dialog (auto-refreshes with the query)
    const logDialogApp = useMemo(
        () => logDialogKey ? (apps.find((a) => (a.tracking_id ?? a.app_id) === logDialogKey) ?? null) : null,
        [logDialogKey, apps],
    )

    const filteredApps = useMemo(
        () => apps.filter((app) => {
            const matchesStatus = selectedStatus === 'all' || String(app.status) === selectedStatus
            const source = resolveAppSource(app)
            const matchesSource = selectedSource === 'all' || source === selectedSource
            const searchText = [app.app_name, app.app_id, app.app_version, app.error, app.app_dist].filter(Boolean).join(' ').toLowerCase()
            const matchesSearch = !searchValue.trim() || searchText.includes(searchValue.trim().toLowerCase())
            return matchesStatus && matchesSource && matchesSearch
        }),
        [apps, searchValue, selectedSource, selectedStatus],
    )

    const marketplaceApps = useMemo(() => filteredApps.filter((app) => resolveAppSource(app) === 'marketplace'), [filteredApps])
    const runtimeApps = useMemo(() => filteredApps.filter((app) => resolveAppSource(app) === 'runtime'), [filteredApps])
    const composeApps = useMemo(() => filteredApps.filter((app) => resolveAppSource(app) === 'compose'), [filteredApps])

    const hasVisibleMarketplaceApps = marketplaceApps.length > 0
    const hasVisibleRuntimeApps = runtimeApps.length > 0
    const hasVisibleComposeApps = composeApps.length > 0

    function handleCardClick(app: MyApp) {
        if (!app.app_official) return
        if (app.status === 1) {
            const contentScopeContainer = typeof document === 'undefined' ? null : document.querySelector('#app-shell-main')
            const backgroundScrollTop = contentScopeContainer instanceof HTMLElement ? contentScopeContainer.scrollTop : 0

            void navigate(`/myapps/${encodeURIComponent(app.app_id)}`, {
                state: {
                    backgroundScrollTop,
                },
            })
        } else if (app.status === 3 || app.status === 4) {
            setLogDialogKey(app.tracking_id ?? app.app_id)
        }
    }

    async function handleConfirmRemove() {
        if (!removeApp) return
        setActionBusy(true)
        try {
            if (removeType === 'error') {
                await runDeleteRequest(`/api/apps/${encodeURIComponent(removeApp.app_id)}/error/remove`)
            } else {
                await runDeleteRequest(`/api/apps/${encodeURIComponent(removeApp.app_id)}/remove`)
            }
            setRemoveApp(null)
            setFeedback({ severity: 'success', message: t('myAppsPage.dialog.actionSuccess') })
            await refetch()
        } catch (err) {
            setFeedback({ severity: 'error', message: err instanceof Error ? err.message : t('myAppsPage.dialog.actionFailed') })
        } finally {
            setActionBusy(false)
        }
    }

    async function handleConfirmRedeploy() {
        if (!redeployApp) return
        setActionBusy(true)
        try {
            await runRedeployRequest(redeployApp.app_id, pullImage)
            setRedeployApp(null)
            setFeedback({ severity: 'success', message: t('myAppsPage.dialog.actionSuccess') })
            await refetch()
        } catch (err) {
            setFeedback({ severity: 'error', message: err instanceof Error ? err.message : t('myAppsPage.dialog.actionFailed') })
        } finally {
            setActionBusy(false)
        }
    }

    function renderCards(appList: MyApp[]) {
        return appList.map((app) => (
            <div
                key={`${app.app_id}-${app.tracking_id ?? 'stable'}`}
                className="appstore-item"
            >
                <div
                    className={`appstore-item-content text-align-center${app.app_official ? ' highlight' : ''}`}
                    onClick={() => handleCardClick(app)}
                    style={{ cursor: app.app_official ? 'pointer' : 'default' }}
                >
                    {/* Top-right action icons */}
                    {app.status === 2 ? (
                        <>
                            <div className="float-end arrow-none card-drop p-0">
                                <span
                                    className="noti-icon"
                                    title={t('myAppsDetailPage.actions.redeploy')}
                                    style={{ marginRight: '10px' }}
                                    onClick={(e) => {
                                        e.stopPropagation()
                                        setRedeployApp(app)
                                        setPullImage(false)
                                    }}
                                >
                                    <IconRedeploy />
                                </span>
                                <span
                                    className="noti-icon"
                                    title={t('myAppsDetailPage.actions.uninstall')}
                                    onClick={(e) => {
                                        e.stopPropagation()
                                        setRemoveApp(app)
                                        setRemoveType('inactive')
                                    }}
                                >
                                    <IconTrash />
                                </span>
                            </div>
                            <div className="clearfix"></div>
                        </>
                    ) : app.status === 4 ? (
                        <>
                            <div className="float-end arrow-none card-drop p-0">
                                <span
                                    className="noti-icon"
                                    title={t('myAppsPage.card.openError', { defaultValue: 'Error Info' })}
                                    style={{ paddingRight: '10px' }}
                                    onClick={(e) => {
                                        e.stopPropagation()
                                        setLogDialogKey(app.tracking_id ?? app.app_id)
                                    }}
                                >
                                    <IconInfo />
                                </span>
                                <span
                                    className="noti-icon"
                                    title={t('myAppsDetailPage.actions.uninstall')}
                                    onClick={(e) => {
                                        e.stopPropagation()
                                        setRemoveApp(app)
                                        setRemoveType('error')
                                    }}
                                >
                                    <IconTrash />
                                </span>
                            </div>
                            <div className="clearfix"></div>
                        </>
                    ) : (
                        <>
                            <div className="float-end arrow-none card-drop p-0">
                                <span className="noti-icon" style={{ opacity: 0, pointerEvents: 'none' }}>
                                    <IconInfo />
                                </span>
                            </div>
                            <div className="clearfix"></div>
                        </>
                    )}

                    {/* App icon */}
                    <div>
                        <LegacyMyAppLogo
                            appId={app.app_id}
                            appName={app.app_name}
                            locale={locale}
                            size={80}
                            marginY={2.5}
                            title={app.app_name || app.app_id}
                        />
                    </div>

                    {/* App title + status */}
                    <div>
                        <h3 className="appstore-item-content-title" style={{ color: '#2196f3', margin: '0 0 4px' }}>
                            {app.app_id}
                        </h3>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
                            {app.app_official ? (
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                    {app.status === 3 ? <span className="spinner-border-sm me-1" /> : null}
                                    <div className="m-2">
                                        <span className={`badge ${getStatusBadgeClass(app.status)}`}>
                                            {getStatusLabel(app.status)}
                                        </span>
                                    </div>
                                </div>
                            ) : (
                                <div style={{ visibility: 'hidden', display: 'flex' }}>
                                    <div className="m-2">&nbsp;</div>
                                </div>
                            )}
                            <div style={{ fontSize: 12, lineHeight: 1.45, color: palette.subtleText }}>
                                {getSourceLabel(resolveAppSource(app))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        ))
    }

    return (
        <Box
            className="myapps-page-shell"
            sx={{
                height: 'calc(100vh - 120px)',
                position: 'relative',
                mx: { xs: -1, md: -3 },
                my: { xs: -1.25, md: -2.25 },
                px: { xs: 2, md: 3 },
                py: { xs: 1.25, md: 1.5 },
                backgroundColor: palette.pageBg,
                color: palette.text,
                overflowY: 'auto',
                overflowX: 'hidden',
            }}
        >
            <PageDescriptionHeader
                title={t('nav.myApps.label')}
                description={t('myAppsPage.hero.description')}
                descriptionColor={palette.subtleText}
                actions={(
                    <>
                        <Button
                            color="inherit"
                            onClick={(event) => {
                                setDeployMenuAnchor(event.currentTarget)
                            }}
                            size="small"
                            className="app-shell-page-pill"
                            title={t('applicationsHubPage.menu.action')}
                            startIcon={<IconDeployMenu />}
                            endIcon={<IconChevronDown />}
                        >
                            {t('applicationsHubPage.menu.action')}
                        </Button>
                        <IconButton
                            color="inherit"
                            onClick={() => {
                                void handleManualRefresh()
                            }}
                            size="small"
                            disabled={manualRefreshing}
                            className="app-shell-page-action"
                            title={manualRefreshing ? t('appStorePage.actions.refreshing') : t('appStorePage.actions.refresh')}
                        >
                            {manualRefreshing ? <CircularProgress size={14} color="inherit" /> : <IconRefresh />}
                        </IconButton>
                    </>
                )}
                sx={{ mb: 1.5 }}
            />

            <Menu
                anchorEl={deployMenuAnchor}
                open={Boolean(deployMenuAnchor)}
                onClose={() => setDeployMenuAnchor(null)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            >
                <MenuItem onClick={() => { setDeployMenuAnchor(null); navigate('/appstore') }}>
                    <ListItemIcon><IconAppStore /></ListItemIcon>
                    <ListItemText>{t('applicationsHubPage.menu.marketplace')}</ListItemText>
                </MenuItem>
                <MenuItem onClick={() => { setDeployMenuAnchor(null); navigate('/applications/custom-install') }}>
                    <ListItemIcon><IconCompose /></ListItemIcon>
                    <ListItemText>{t('applicationsHubPage.menu.customInstall')}</ListItemText>
                </MenuItem>
                <MenuItem onClick={() => { setDeployMenuAnchor(null); navigate('/applications/runtime') }}>
                    <ListItemIcon><IconRuntime /></ListItemIcon>
                    <ListItemText>{t('applicationsHubPage.menu.runtime')}</ListItemText>
                </MenuItem>
            </Menu>

            {/* Toolbar */}
            <div className="myapps-toolbar">
                <div className="myapps-toolbar-select">
                    <select
                        className="form-select"
                        value={selectedSource}
                        onChange={(e) => setSelectedSource(e.target.value as SourceFilter)}
                    >
                        <option value="all">{t('myAppsPage.filters.allSources')}</option>
                        <option value="marketplace">{t('myAppsPage.filters.marketplaceSource')}</option>
                        <option value="compose">{t('myAppsPage.filters.composeSource')}</option>
                        <option value="runtime">{t('myAppsPage.filters.runtimeSource')}</option>
                    </select>
                </div>
                <div className="myapps-toolbar-select">
                    <select
                        className="form-select"
                        value={selectedStatus}
                        onChange={(e) => setSelectedStatus(e.target.value as StatusFilter)}
                    >
                        <option value="all">{t('myAppsPage.filters.allStates')}</option>
                        <option value="1">Active</option>
                        <option value="2">Inactive</option>
                        <option value="3">Installing</option>
                        <option value="4">Error</option>
                    </select>
                </div>
                <div className="myapps-toolbar-search">
                    <input
                        type="text"
                        className="form-control"
                        placeholder={t('myAppsPage.filters.searchPlaceholderLegacy')}
                        value={searchValue}
                        onChange={(e) => setSearchValue(e.target.value)}
                    />
                </div>
            </div>

            {/* Loading – same pattern as App Store page */}
            {isLoading ? (
                <Card elevation={0} sx={{ border: `1px solid ${palette.border}`, mt: 2, backgroundColor: palette.panelBg }}>
                    <CardContent>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, padding: '40px 24px' }}>
                            <CircularProgress size={28} />
                            <Typography color={palette.subtleText} variant="body2">
                                {t('myAppsPage.states.loading')}
                            </Typography>
                        </div>
                    </CardContent>
                </Card>
            ) : null}

            {/* Error */}
            {!isLoading && error ? (
                <Alert
                    action={<Button color="inherit" size="small" onClick={() => void refetch()}>{t('myAppsPage.states.retry')}</Button>}
                    severity="warning"
                    variant="outlined"
                    sx={{ mt: 2 }}
                >
                    <Typography sx={{ fontWeight: 600 }}>{t('myAppsPage.states.errorTitle')}</Typography>
                    <Typography variant="body2">{t('myAppsPage.states.errorDetail', { statusCode: (error as { statusCode?: number }).statusCode ?? 'unknown' })}</Typography>
                </Alert>
            ) : null}

            {/* Content */}
            {!isLoading && !error ? (
                <>
                    {filteredApps.length === 0 ? (
                        <Card elevation={0} sx={{ border: `1px solid ${palette.border}`, mt: 2, backgroundColor: palette.panelBg }}>
                            <CardContent>
                                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '48px 24px', gap: 12 }}>
                                    {/* Box icon */}
                                    <svg viewBox="0 0 64 64" width="64" height="64" fill="none" xmlns="http://www.w3.org/2000/svg">
                                        <rect width="64" height="64" rx="16" fill={isDarkMode ? '#162033' : '#f1f2f7'} />
                                        <path d="M32 16l14 7v14l-14 7-14-7V23l14-7z" stroke={isDarkMode ? '#64748b' : '#b0b8d1'} strokeWidth="2" strokeLinejoin="round" />
                                        <path d="M32 16v14M18 23l14 7 14-7" stroke={isDarkMode ? '#64748b' : '#b0b8d1'} strokeWidth="2" />
                                    </svg>
                                    <Typography sx={{ fontWeight: 600, fontSize: 16, color: palette.text, mt: 1 }}>
                                        {apps.length === 0 ? t('myAppsPage.states.noAppsInstalled') : t('myAppsPage.states.noAppsFound')}
                                    </Typography>
                                    <Typography color={palette.subtleText} variant="body2" sx={{ textAlign: 'center', maxWidth: 400, lineHeight: 1.7 }}>
                                        {apps.length === 0 ? t('myAppsPage.states.emptyDetail') : t('myAppsPage.states.filterHint')}
                                    </Typography>
                                    <button
                                        className="myapps-empty-btn"
                                        onClick={() => navigate('/applications/deploy')}
                                    >
                                        {t('applicationsHubPage.menu.action')}
                                    </button>
                                </div>
                            </CardContent>
                        </Card>
                    ) : (
                        <>
                            {hasVisibleMarketplaceApps ? (
                                <div>
                                    <h4 className="myapps-section-heading">{t('myAppsPage.sections.officialApps')}</h4>
                                    <div className="myapps-card-grid">
                                        {renderCards(marketplaceApps)}
                                    </div>
                                </div>
                            ) : null}

                            {hasVisibleRuntimeApps ? (
                                <div>
                                    <h4 className="myapps-section-heading is-secondary">{t('applicationsHubPage.menu.runtime')}</h4>
                                    <div className="myapps-card-grid">
                                        {renderCards(runtimeApps)}
                                    </div>
                                </div>
                            ) : null}

                            {hasVisibleComposeApps ? (
                                <div>
                                    <h4 className="myapps-section-heading is-secondary">{t('myAppsPage.sections.otherApps')}</h4>
                                    <div className="myapps-card-grid">
                                        {renderCards(composeApps)}
                                    </div>
                                </div>
                            ) : null}
                        </>
                    )}
                </>
            ) : null}

            {/* Log / Error info dialog */}
            <LogDialog
                app={logDialogApp}
                onClose={() => setLogDialogKey(null)}
            />

            {/* Remove confirm dialog */}
            <Dialog
                fullWidth
                maxWidth="sm"
                open={Boolean(removeApp)}
                onClose={() => setRemoveApp(null)}
                sx={{ '& .MuiDialog-paper': { borderRadius: 0 } }}
            >
                <DialogTitle sx={{ backgroundColor: '#ffbc00', color: '#313a46' }}>
                    {t('myAppsPage.dialog.removeTitle')} {removeApp?.app_id}
                </DialogTitle>
                <DialogContent dividers>
                    <p style={{ margin: '10px 0' }}>
                        {t('myAppsPage.dialog.removeBody', { appId: removeApp?.app_id })}
                    </p>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setRemoveApp(null)}>{t('myAppsDetailPage.dialogs.cancel')}</Button>
                    <Button
                        disabled={actionBusy}
                        onClick={() => void handleConfirmRemove()}
                        sx={{ backgroundColor: '#ffbc00', color: '#313a46', '&:hover': { backgroundColor: '#e0a800' } }}
                    >
                        {actionBusy ? <span className="spinner-border-sm me-1" /> : null}
                        {t('myAppsPage.dialog.removeConfirm')}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Redeploy confirm dialog */}
            <Dialog
                fullWidth
                maxWidth="sm"
                open={Boolean(redeployApp)}
                onClose={() => setRedeployApp(null)}
                sx={{ '& .MuiDialog-paper': { borderRadius: 0 } }}
            >
                <DialogTitle sx={{ backgroundColor: '#ffbc00', color: '#313a46' }}>
                    {t('myAppsDetailPage.actions.redeploy')} {redeployApp?.app_id}
                </DialogTitle>
                <DialogContent dividers>
                    <p style={{ margin: '10px 0' }}>
                        {t('myAppsDetailPage.dialogs.redeployBody')}
                    </p>
                    <FormControlLabel
                        control={<Switch checked={pullImage} onChange={(e) => setPullImage(e.target.checked)} />}
                        label={t('myAppsDetailPage.dialogs.redeployPullImage')}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setRedeployApp(null)}>{t('myAppsDetailPage.dialogs.cancel')}</Button>
                    <Button
                        disabled={actionBusy}
                        onClick={() => void handleConfirmRedeploy()}
                        sx={{ backgroundColor: '#ffbc00', color: '#313a46', '&:hover': { backgroundColor: '#e0a800' } }}
                    >
                        {actionBusy ? <span className="spinner-border-sm me-1" /> : null}
                        {t('myAppsDetailPage.actions.redeploy')}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Feedback toast */}
            <Snackbar
                open={Boolean(feedback)}
                autoHideDuration={3000}
                onClose={() => setFeedback(null)}
                anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            >
                <Alert
                    onClose={() => setFeedback(null)}
                    severity={feedback?.severity ?? 'info'}
                    variant="filled"
                    elevation={6}
                    sx={{ width: '100%' }}
                >
                    {feedback?.message}
                </Alert>
            </Snackbar>
        </Box>
    )
}
