import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    CircularProgress,
    IconButton,
    Switch,
    Tooltip,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAppColorMode } from '../../app/providers/color-mode'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { SurfaceDialog, SurfaceFeedbackToast } from '../../shared/design-system/standard-surfaces'
import { getSurfacePalette } from '../../shared/design-system/surface-theme'
import { clearMyAppsDetailOverlayIntent, markMyAppsDetailOverlayIntent } from './my-app-detail-overlay-intent'
import { useMyApps, type MyApp } from './use-my-apps'
import { fetchMyAppDetail } from './use-my-app-detail'
import { LegacyMyAppLogo } from './my-app-media'
import './my-apps-page.css'

// =====================
// Types
// =====================
type StatusFilter = 'all' | '1' | '2' | '3' | '4'
type RemoveType = 'inactive' | 'error'
type ActionFeedback = {
    severity: 'success' | 'warning' | 'info'
    message: string
}

type ContentScopeRect = {
    top: number
    left: number
    width: number
    height: number
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

function getStatusBadgeClass(status: number): string {
    switch (status) {
        case 1: return 'is-active'
        case 2: return 'is-inactive'
        case 3: return 'is-installing'
        case 4: return 'is-error'
        default: return 'is-unknown'
    }
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

function IconCompose() {
    return (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M4 6.5A2.5 2.5 0 0 1 6.5 4H11v2H6.5a.5.5 0 0 0-.5.5V11H4V6.5Zm9-2.5h4.5A2.5 2.5 0 0 1 20 6.5V11h-2V6.5a.5.5 0 0 0-.5-.5H13V4ZM4 13h2v4.5a.5.5 0 0 0 .5.5H11v2H6.5A2.5 2.5 0 0 1 4 17.5V13Zm14 0h2v4.5a2.5 2.5 0 0 1-2.5 2.5H13v-2h4.5a.5.5 0 0 0 .5-.5V13Zm-7-4 5 3-5 3V9Z" />
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

function LogDialog({
    app,
    onClose,
    darkMode,
    scopeRect,
}: {
    app: MyApp | null
    onClose: () => void
    darkMode: boolean
    scopeRect: ContentScopeRect | null
}) {
    const { t } = useTranslation('shell')
    const isError = Boolean(app?.error)
    const isInstalling = app?.status === 3
    const stages = app?.logs ?? []
    const hasLogs = stages.some((stage) => stage.sub_logs && stage.sub_logs.length > 0)
    const dialogPalette = getSurfacePalette(darkMode)

    return (
        <SurfaceDialog
            darkMode={darkMode}
            onClose={onClose}
            open={Boolean(app)}
            scope="content"
            scopeRect={scopeRect}
            contentStrategy="viewport-fixed"
            paperSx={{
                width: { xs: 'min(100%, 880px)', md: 'min(880px, calc(100% - 20px))' },
                maxWidth: '880px',
                height: '62vh',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                backgroundColor: dialogPalette.dialogBg,
                color: dialogPalette.text,
                border: `1px solid ${dialogPalette.border}`,
                boxShadow: darkMode ? '0 24px 64px rgba(2, 6, 23, 0.56)' : '0 16px 40px rgba(15, 23, 42, 0.16)',
            }}
        >
            <Box
                sx={{
                    backgroundColor: dialogPalette.dialogBg,
                    color: dialogPalette.text,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    py: { xs: 1.5, md: 1.75 },
                    px: { xs: 2, md: 2.5 },
                    flexShrink: 0,
                    userSelect: 'none',
                    borderBottom: `1px solid ${dialogPalette.border}`,
                }}
            >
                {isInstalling ? <CircularProgress size={15} thickness={5} sx={{ color: dialogPalette.accent, flexShrink: 0 }} /> : null}
                <Typography sx={{ flex: 1, fontSize: { xs: 18, md: 20 }, fontWeight: 600, lineHeight: 1.2, color: dialogPalette.text }}>
                    {isError ? `${t('myAppsPage.dialog.errorTitle')} - ${app?.app_id}` : `${t('myAppsPage.dialog.logsTitle')} - ${app?.app_id}`}
                </Typography>
                <IconButton size="small" onClick={onClose} sx={{ width: 40, height: 40, color: dialogPalette.subtleText, borderRadius: '999px', backgroundColor: 'transparent', '&:hover': { color: dialogPalette.text, backgroundColor: 'transparent', opacity: 0.84 } }}>
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                    </svg>
                </IconButton>
            </Box>

            {isError && app?.error ? (
                <div style={{
                    flexShrink: 0,
                    backgroundColor: dialogPalette.dialogBg,
                    borderBottom: `1px solid ${dialogPalette.border}`,
                    padding: '14px 20px',
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
                        backgroundColor: dialogPalette.actionBg,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: dialogPalette.subtleText,
                        fontSize: '12px',
                        fontWeight: 700,
                        marginTop: 1,
                    }}>!</span>
                    <div style={{ flex: 1 }}>
                        <div style={{
                            fontSize: '12px',
                            color: dialogPalette.text,
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

            <Box sx={{ p: 0, flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', backgroundColor: dialogPalette.dialogBg }}>
                {stages.length > 0 ? (
                    <div style={{
                        flexShrink: 0,
                        display: 'flex',
                        alignItems: 'stretch',
                        gap: 0,
                        borderBottom: `1px solid ${dialogPalette.border}`,
                        backgroundColor: dialogPalette.dialogBg,
                        padding: '0 16px',
                    }}>
                        {stages.map((stage, idx) => {
                            const isActive = idx === stages.length - 1 && isInstalling
                            const isDone = !isInstalling || idx < stages.length - 1
                            return (
                                <div
                                    key={idx}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 6,
                                        padding: '8px 14px 8px 0',
                                        marginRight: 16,
                                        borderBottom: isActive ? `2px solid ${dialogPalette.accent}` : isDone ? '2px solid #0acf97' : '2px solid transparent',
                                        fontSize: '12px',
                                        fontWeight: isActive ? 700 : 500,
                                        color: isActive ? dialogPalette.accent : isDone ? '#0acf97' : dialogPalette.subtleText,
                                        userSelect: 'none',
                                        whiteSpace: 'nowrap',
                                    }}
                                >
                                    {isActive
                                        ? <CircularProgress size={11} thickness={6} sx={{ color: dialogPalette.accent, flexShrink: 0 }} />
                                        : isDone
                                            ? <svg viewBox="0 0 24 24" width="12" height="12" fill="#0acf97"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" /></svg>
                                            : <span style={{ width: 12, height: 12, borderRadius: '50%', border: `2px solid ${dialogPalette.divider}`, display: 'inline-block' }} />}
                                    <span>{`${idx + 1}. ${stage.title}`}</span>
                                </div>
                            )
                        })}
                    </div>
                ) : null}

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
                    {!hasLogs && !isError ? (
                        <div style={{
                            flex: 1,
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: 14,
                            color: dialogPalette.subtleText,
                        }}>
                            {isInstalling ? (
                                <>
                                    <CircularProgress size={28} thickness={4} sx={{ color: dialogPalette.accent }} />
                                    <span style={{ fontSize: '13px', color: dialogPalette.accent, fontFamily: 'inherit', letterSpacing: '0.01em' }}>
                                        {stages.length > 0 ? stages[stages.length - 1].title : 'Preparing…'}
                                    </span>
                                </>
                            ) : (
                                <span style={{ fontSize: '12px', color: dialogPalette.subtleText }}>{t('myAppsPage.dialog.noSubLogs')}</span>
                            )}
                        </div>
                    ) : null}

                    {(() => {
                        const activeStage = [...stages].reverse().find((stage) => stage.sub_logs && stage.sub_logs.length > 0)
                        if (!activeStage) {
                            return null
                        }

                        const lines = (activeStage.sub_logs ?? []).filter((line) => line != null)
                        const tail = lines.slice(-MAX_STAGE_LOG_LINES)
                        const offset = lines.length - tail.length

                        return tail.map((line, index) => (
                            <div key={index} style={{ display: 'flex', gap: 10, padding: '1px 0', color: dialogPalette.text, borderBottom: `1px solid ${dialogPalette.divider}` }}>
                                <span style={{ color: dialogPalette.subtleText, userSelect: 'none', minWidth: 28, textAlign: 'right', flexShrink: 0, fontSize: '11px' }}>
                                    {offset + index + 1}
                                </span>
                                <span style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', flex: 1, overflow: 'hidden' }}>
                                    {formatInstallLogLine(line)}
                                </span>
                            </div>
                        ))
                    })()}

                    {isInstalling && hasLogs ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: dialogPalette.accent, marginTop: 4 }}>
                            <CircularProgress size={10} thickness={6} sx={{ color: dialogPalette.accent }} />
                            <span style={{ fontSize: '11px' }}>installing…</span>
                        </div>
                    ) : null}
                </div>
            </Box>

            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.5, py: 2, backgroundColor: dialogPalette.dialogBg, borderTop: `1px solid ${dialogPalette.border}`, flexShrink: 0 }}>
                <Button color="inherit" onClick={onClose} variant="contained" sx={{ minWidth: 68, backgroundColor: dialogPalette.actionBg, color: dialogPalette.subtleText, borderRadius: 0, boxShadow: 'none', '&:hover': { backgroundColor: dialogPalette.actionHover, boxShadow: 'none', color: dialogPalette.text } }}>
                    {t('myAppsPage.dialog.close')}
                </Button>
                {isError ? (
                    <Button
                        onClick={() => window.open('https://www.websoft9.com/ticket', '_blank')}
                        variant="contained"
                        sx={{ minWidth: 68, borderRadius: 0, boxShadow: 'none' }}
                    >
                        {t('myAppsPage.dialog.support')}
                    </Button>
                ) : null}
            </Box>
        </SurfaceDialog>
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
    const location = useLocation()
    const isDarkMode = colorMode === 'dark'
    const [searchValue, setSearchValue] = useState('')
    const [selectedStatus, setSelectedStatus] = useState<StatusFilter>('all')
    // Store only the identifier so the dialog always reads live data from the query
    const [logDialogKey, setLogDialogKey] = useState<string | null>(null)
    const [removeApp, setRemoveApp] = useState<MyApp | null>(null)
    const [removeType, setRemoveType] = useState<RemoveType>('inactive')
    const [redeployApp, setRedeployApp] = useState<MyApp | null>(null)
    const [pullImage, setPullImage] = useState(false)
    const [actionBusy, setActionBusy] = useState(false)
    const [feedback, setFeedback] = useState<ActionFeedback | null>(null)
    const [manualRefreshing, setManualRefreshing] = useState(false)
    const [contentScopeRect, setContentScopeRect] = useState<ContentScopeRect | null>(null)

    const { data, error, isLoading, refetch } = useMyApps()
    const apps = data ?? []
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const apiLocale = locale.toLowerCase().startsWith('zh') ? 'zh' : 'en'
    const palette = getSurfacePalette(isDarkMode)
    const dialogPalette = getSurfacePalette(isDarkMode)
    const contentScopedDialogPlacementSx = useMemo(() => ({
        '& .MuiDialog-container': {
            alignItems: 'flex-start',
            justifyContent: 'center',
            pt: { xs: 3, md: 3 },
            pb: { xs: 1.5, md: 2.5 },
        },
    }), [])
    const contentScopeContainer = typeof document === 'undefined' ? null : document.querySelector('#app-shell-main')

    function closeAllMyAppsOverlays() {
        clearMyAppsDetailOverlayIntent()
        setLogDialogKey(null)
        setRemoveApp(null)
        setRedeployApp(null)
        setActionBusy(false)
    }

    async function handleManualRefresh() {
        closeAllMyAppsOverlays()
        if (location.pathname !== '/myapps') {
            navigate('/myapps', { replace: true })
        }
        setManualRefreshing(true)
        try {
            await refetch()
        } finally {
            setManualRefreshing(false)
        }
    }

    useEffect(() => {
        if (!(contentScopeContainer instanceof HTMLElement)) {
            setContentScopeRect(null)
            return
        }

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
    }, [contentScopeContainer])

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
                    queryKey: ['my-app-detail', app.app_id, apiLocale],
                    queryFn: async () => fetchMyAppDetail(app.app_id, apiLocale),
                    staleTime: 10_000,
                })
            })
        })

        return () => cancel(handle)
    }, [apiLocale, apps, queryClient])

    // Resolve the live app for the log dialog (auto-refreshes with the query)
    const logDialogApp = useMemo(
        () => logDialogKey ? (apps.find((a) => (a.tracking_id ?? a.app_id) === logDialogKey) ?? null) : null,
        [logDialogKey, apps],
    )

    const filteredApps = useMemo(
        () => apps.filter((app) => {
            const matchesStatus = selectedStatus === 'all' || String(app.status) === selectedStatus
            const searchText = [app.app_name, app.app_id, app.app_version, app.error, app.app_dist].filter(Boolean).join(' ').toLowerCase()
            const matchesSearch = !searchValue.trim() || searchText.includes(searchValue.trim().toLowerCase())
            return matchesStatus && matchesSearch
        }),
        [apps, searchValue, selectedStatus],
    )

    const platformApps = useMemo(() => filteredApps.filter((app) => app.app_official), [filteredApps])
    const otherApps = useMemo(() => filteredApps.filter((app) => !app.app_official), [filteredApps])

    const hasVisiblePlatformApps = platformApps.length > 0
    const hasVisibleOtherApps = otherApps.length > 0
    const showLoadingState = isLoading || manualRefreshing

    function handleCardClick(app: MyApp) {
        if (!app.app_official) return
        if (app.status === 1) {
            const contentScopeContainer = typeof document === 'undefined' ? null : document.querySelector('#app-shell-main')
            const backgroundScrollTop = contentScopeContainer instanceof HTMLElement ? contentScopeContainer.scrollTop : 0

            markMyAppsDetailOverlayIntent(app.app_id)
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
                try {
                    await runDeleteRequest(`/api/apps/${encodeURIComponent(removeApp.app_id)}/error/remove`)
                } catch {
                    await runDeleteRequest(`/api/apps/${encodeURIComponent(removeApp.app_id)}/remove`)
                }
            } else {
                await runDeleteRequest(`/api/apps/${encodeURIComponent(removeApp.app_id)}/remove`)
            }
            setRemoveApp(null)
            setFeedback({ severity: 'success', message: t('myAppsPage.dialog.actionSuccess') })
            await refetch()
        } catch (err) {
            setFeedback({ severity: 'warning', message: err instanceof Error ? err.message : t('myAppsPage.dialog.actionFailed') })
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
            setFeedback({ severity: 'warning', message: err instanceof Error ? err.message : t('myAppsPage.dialog.actionFailed') })
        } finally {
            setActionBusy(false)
        }
    }

    function renderCards(appList: MyApp[], variant: 'managed' | 'other') {
        return appList.map((app) => {
            const canOpenDetail = app.app_official
            const showStatus = variant === 'managed' && canOpenDetail
            const logoSize = 80

            const statusNode = showStatus ? (
                <span className={`myapps-status-badge ${getStatusBadgeClass(app.status)}`}>
                    {app.status === 3 ? <CircularProgress size={8} sx={{ mr: 0.5, verticalAlign: 'middle', color: 'inherit' }} /> : null}
                    {getStatusLabel(app.status)}
                </span>
            ) : undefined

            let actionsNode: ReactNode | undefined
            if (app.status === 2) {
                actionsNode = (
                    <>
                        <Tooltip title={t('myAppsDetailPage.actions.redeploy')}>
                            <button
                                type="button"
                                className="myapps-card-icon-btn noti-icon"
                                onClick={(event) => {
                                    event.stopPropagation()
                                    setRedeployApp(app)
                                    setPullImage(false)
                                }}
                            >
                                <IconRedeploy />
                            </button>
                        </Tooltip>
                        <Tooltip title={t('myAppsDetailPage.actions.uninstall')}>
                            <button
                                type="button"
                                className="myapps-card-icon-btn noti-icon"
                                onClick={(event) => {
                                    event.stopPropagation()
                                    setRemoveApp(app)
                                    setRemoveType('inactive')
                                }}
                            >
                                <IconTrash />
                            </button>
                        </Tooltip>
                    </>
                )
            } else if (app.status === 4) {
                actionsNode = (
                    <>
                        <Tooltip title={t('myAppsPage.card.openError', { defaultValue: 'Error Info' })}>
                            <button
                                type="button"
                                className="myapps-card-icon-btn noti-icon"
                                onClick={(event) => {
                                    event.stopPropagation()
                                    setLogDialogKey(app.tracking_id ?? app.app_id)
                                }}
                            >
                                <IconInfo />
                            </button>
                        </Tooltip>
                        <Tooltip title={t('myAppsDetailPage.actions.uninstall')}>
                            <button
                                type="button"
                                className="myapps-card-icon-btn noti-icon"
                                onClick={(event) => {
                                    event.stopPropagation()
                                    setRemoveApp(app)
                                    setRemoveType('error')
                                }}
                            >
                                <IconTrash />
                            </button>
                        </Tooltip>
                    </>
                )
            }

            return (
                <div
                    key={`${app.app_id}-${app.tracking_id ?? 'stable'}`}
                    className={`myapps-vcard myapps-vcard--${variant}${canOpenDetail ? ' highlight' : ''}`}
                    onClick={canOpenDetail ? () => handleCardClick(app) : undefined}
                    role={canOpenDetail ? 'button' : undefined}
                    tabIndex={canOpenDetail ? 0 : undefined}
                    onKeyDown={canOpenDetail ? (e) => { if (e.key === 'Enter' || e.key === ' ') handleCardClick(app) } : undefined}
                >
                    <div className="myapps-vcard-top">
                        {actionsNode ? <div className="myapps-vcard-actions">{actionsNode}</div> : <div className="myapps-vcard-actions myapps-vcard-actions--placeholder" />}
                    </div>
                    <div className="myapps-vcard-icon">
                        <LegacyMyAppLogo
                            appId={app.app_id}
                            appName={app.app_name}
                            logoUrl={app.logo_url}
                            locale={locale}
                            size={logoSize}
                            marginY={0}
                        />
                    </div>
                    <div
                        className={`myapps-vcard-name myapps-vcard-name--${variant}${canOpenDetail ? ' is-official' : ''}`}
                    >
                        {app.app_id}
                    </div>
                    <div className={`myapps-vcard-footer myapps-vcard-footer--${variant}`}>
                        {statusNode ? <div className="myapps-vcard-badge">{statusNode}</div> : <div className="myapps-vcard-badge myapps-vcard-badge--placeholder" />}
                    </div>
                </div>
            )
        })
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
                            onClick={() => {
                                navigate('/applications/deploy')
                            }}
                            size="small"
                            className="app-shell-page-pill"
                            title={t('applicationsHubPage.menu.action')}
                            startIcon={<IconCompose />}
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

            {/* Toolbar */}
            <div className="myapps-toolbar">
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
            {showLoadingState ? (
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
            {!showLoadingState && error ? (
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
            {!showLoadingState && !error ? (
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
                                        {t('myAppsPage.states.goToAppStore')}
                                    </button>
                                </div>
                            </CardContent>
                        </Card>
                    ) : (
                        <>
                            {hasVisiblePlatformApps ? (
                                <div>
                                    <h4 className="myapps-section-heading">{t('myAppsPage.sections.officialApps')}</h4>
                                    <div className="myapps-card-grid">
                                        {renderCards(platformApps, 'managed')}
                                    </div>
                                </div>
                            ) : null}

                            {hasVisibleOtherApps ? (
                                <div>
                                    <h4 className="myapps-section-heading is-secondary">{t('myAppsPage.sections.otherApps')}</h4>
                                    <div className="myapps-card-grid">
                                        {renderCards(otherApps, 'other')}
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
                darkMode={isDarkMode}
                scopeRect={contentScopeRect}
            />

            {/* Remove confirm dialog */}
            <SurfaceDialog
                darkMode={isDarkMode}
                onClose={() => setRemoveApp(null)}
                open={Boolean(removeApp)}
                scope="content"
                scopeRect={contentScopeRect}
                contentStrategy="viewport-fixed"
                sx={contentScopedDialogPlacementSx}
                paperSx={{
                    width: { xs: 'min(100%, 560px)', md: 'min(560px, calc(100% - 20px))' },
                    maxWidth: '560px',
                    backgroundColor: dialogPalette.dialogBg,
                    color: dialogPalette.text,
                    border: `1px solid ${dialogPalette.border}`,
                }}
            >
                <Box sx={{ px: { xs: 2, md: 2.5 }, py: { xs: 1.5, md: 1.75 }, borderBottom: `1px solid ${dialogPalette.border}`, backgroundColor: dialogPalette.dialogBg, display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Typography sx={{ flex: 1, fontSize: { xs: 18, md: 20 }, fontWeight: 600, lineHeight: 1.2, color: dialogPalette.text }}>
                        {t('myAppsPage.dialog.removeTitle')} {removeApp?.app_id}
                    </Typography>
                    <IconButton onClick={() => setRemoveApp(null)} size="small" sx={{ width: 40, height: 40, color: dialogPalette.subtleText, borderRadius: '999px', backgroundColor: 'transparent', '&:hover': { backgroundColor: 'transparent', color: dialogPalette.text, opacity: 0.84 } }}>
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" /></svg>
                    </IconButton>
                </Box>
                <Box sx={{ px: { xs: 2, md: 2.5 }, py: 2.25, borderBottom: `1px solid ${dialogPalette.border}`, backgroundColor: dialogPalette.dialogBg }}>
                    <Typography sx={{ m: 0, fontSize: 14, lineHeight: 1.75, color: dialogPalette.subtleText, fontWeight: 400 }}>
                        {t('myAppsPage.dialog.removeBody', { appId: removeApp?.app_id })}
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.5, py: 2, borderTop: `1px solid ${dialogPalette.border}`, backgroundColor: dialogPalette.dialogBg }}>
                    <Button onClick={() => setRemoveApp(null)} variant="contained" sx={{ minWidth: 68, backgroundColor: dialogPalette.actionBg, color: dialogPalette.subtleText, borderRadius: 0, boxShadow: 'none', '&:hover': { backgroundColor: dialogPalette.actionHover, boxShadow: 'none', color: dialogPalette.text } }}>{t('myAppsDetailPage.dialogs.cancel')}</Button>
                    <Button
                        disabled={actionBusy}
                        onClick={() => void handleConfirmRemove()}
                        variant="contained"
                        sx={{ minWidth: 68, borderRadius: 0, boxShadow: 'none' }}
                    >
                        {actionBusy ? <span className="spinner-border-sm me-1" /> : null}
                        {t('myAppsPage.dialog.removeConfirm')}
                    </Button>
                </Box>
            </SurfaceDialog>

            {/* Redeploy confirm dialog */}
            <SurfaceDialog
                darkMode={isDarkMode}
                onClose={() => setRedeployApp(null)}
                open={Boolean(redeployApp)}
                scope="content"
                scopeRect={contentScopeRect}
                contentStrategy="viewport-fixed"
                sx={contentScopedDialogPlacementSx}
                paperSx={{
                    width: { xs: 'min(100%, 560px)', md: 'min(560px, calc(100% - 20px))' },
                    maxWidth: '560px',
                    backgroundColor: dialogPalette.dialogBg,
                    color: dialogPalette.text,
                    border: `1px solid ${dialogPalette.border}`,
                }}
            >
                <Box sx={{ px: { xs: 2, md: 2.5 }, py: { xs: 1.5, md: 1.75 }, borderBottom: `1px solid ${dialogPalette.border}`, backgroundColor: dialogPalette.dialogBg, display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Typography sx={{ flex: 1, fontSize: { xs: 18, md: 20 }, fontWeight: 600, lineHeight: 1.2, color: dialogPalette.text }}>{t('myAppsDetailPage.actions.redeploy')} {redeployApp?.app_id}</Typography>
                    <IconButton onClick={() => setRedeployApp(null)} size="small" sx={{ width: 40, height: 40, color: dialogPalette.subtleText, borderRadius: '999px', backgroundColor: 'transparent', '&:hover': { backgroundColor: 'transparent', color: dialogPalette.text, opacity: 0.84 } }}>
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" /></svg>
                    </IconButton>
                </Box>
                <Box sx={{ px: { xs: 2, md: 2.5 }, py: 2.25, borderBottom: `1px solid ${dialogPalette.border}`, backgroundColor: dialogPalette.dialogBg }}>
                    <Typography sx={{ m: 0, mb: 1.25, fontSize: 14, lineHeight: 1.75, color: dialogPalette.subtleText, fontWeight: 400 }}>
                        {t('myAppsDetailPage.dialogs.redeployBody')}
                    </Typography>
                    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75, color: dialogPalette.text }}>
                        <Typography sx={{ fontSize: 14, color: dialogPalette.text }}>{t('myAppsDetailPage.dialogs.redeployPullImage')}</Typography>
                        <Switch checked={pullImage} onChange={(e) => setPullImage(e.target.checked)} />
                    </Box>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.5, py: 2, borderTop: `1px solid ${dialogPalette.border}`, backgroundColor: dialogPalette.dialogBg }}>
                    <Button onClick={() => setRedeployApp(null)} variant="contained" sx={{ minWidth: 68, backgroundColor: dialogPalette.actionBg, color: dialogPalette.subtleText, borderRadius: 0, boxShadow: 'none', '&:hover': { backgroundColor: dialogPalette.actionHover, boxShadow: 'none', color: dialogPalette.text } }}>{t('myAppsDetailPage.dialogs.cancel')}</Button>
                    <Button
                        disabled={actionBusy}
                        onClick={() => void handleConfirmRedeploy()}
                        variant="contained"
                        sx={{ minWidth: 68, borderRadius: 0, boxShadow: 'none' }}
                    >
                        {actionBusy ? <span className="spinner-border-sm me-1" /> : null}
                        {t('myAppsDetailPage.actions.redeploy')}
                    </Button>
                </Box>
            </SurfaceDialog>

            {/* Feedback toast */}
            <SurfaceFeedbackToast
                open={Boolean(feedback)}
                onClose={() => setFeedback(null)}
                severity={feedback?.severity ?? 'info'}
                message={feedback?.message ?? ''}
                scope="content"
                scopeRect={contentScopeRect}
                darkMode={isDarkMode}
            />

            <Outlet />
        </Box>
    )
}
