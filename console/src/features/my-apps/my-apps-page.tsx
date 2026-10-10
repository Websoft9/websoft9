import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    CircularProgress,
    IconButton,
    Link,
    Switch,
    Tooltip,
    Typography,
} from '@mui/material'
import type { SxProps, Theme } from '@mui/material'
import { Check, ChevronRight, CircleAlert, Copy, Download, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Link as RouterLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAppColorMode } from '../../app/providers/color-mode'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { SurfaceDialog, SurfaceFeedbackToast } from '../../shared/design-system/standard-surfaces'
import { getSurfacePalette } from '../../shared/design-system/surface-theme'
import { useConnectionUnavailable } from '../../shared/connection/connection-provider'
import { isPlatformUnavailableError } from '../../shared/lib/api-error'
import { clearMyAppsDetailOverlayIntent, markMyAppsDetailOverlayIntent } from './my-app-detail-overlay-intent'
import { useMyApps, type MyApp } from './use-my-apps'
import { fetchMyAppDetail } from './use-my-app-detail'
import { LegacyMyAppLogo } from './my-app-media'
import { buildInstallLogRows, formatInstallSourceReason, getInstallError, getInstallExportText, getInstallSourceGroups, getInstallSourceSummary, getInstallSteps } from './install-log-model'
import './my-apps-page.css'

// =====================
// Types
// =====================
type StatusFilter = 'all' | '1' | '2' | '3' | '4' | '6'
type RemoveType = 'inactive' | 'error' | 'cancelled'
type ActionFeedback = {
    severity: 'success' | 'warning' | 'info'
    message: string
    cancellingInstallKey?: string
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
        case 6: return 'Cancelled'
        default: return 'Unknown'
    }
}

function getStatusBadgeClass(status: number): string {
    switch (status) {
        case 1: return 'is-active'
        case 2: return 'is-inactive'
        case 3: return 'is-installing'
        case 4: return 'is-error'
        case 6: return 'is-cancelled'
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
    if (!response.ok || !response.body) {
        throw new Error(await parseJsonError(response, `Redeploy failed: ${response.status}`))
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalStatus: 'success' | 'failed' | null = null
    let lastErrorDetail: string | null = null

    while (true) {
        const { done, value } = await reader.read()
        buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
            if (!line.trim()) continue
            try {
                const entry = JSON.parse(line) as { status?: string; type?: string; details?: string; message?: string }
                if (entry.status === 'failed' || entry.type === 'error') {
                    finalStatus = 'failed'
                    if (entry.details) lastErrorDetail = entry.details
                    else if (entry.message) lastErrorDetail = entry.message
                }
                if (entry.status === 'success') finalStatus = 'success'
            } catch { /* skip unparseable lines */ }
        }

        if (done) break
    }

    if (buffer.trim()) {
        try {
            const entry = JSON.parse(buffer) as { status?: string; type?: string; details?: string; message?: string }
            if (entry.status === 'failed' || entry.type === 'error') {
                finalStatus = 'failed'
                if (entry.details) lastErrorDetail = entry.details
                else if (entry.message) lastErrorDetail = entry.message
            }
            if (entry.status === 'success') finalStatus = 'success'
        } catch { /* skip */ }
    }

    if (finalStatus !== 'success') throw new Error(lastErrorDetail ?? 'Redeploy did not complete successfully.')
}

// =====================
// Log / Error Dialog
// =====================
const MAX_INSTALL_LOG_LINES = 500

function LogDialog({
    app,
    onClose,
    onCancelInstall,
    onRemoveApp,
    confirmationPlacementSx,
    darkMode,
    scopeRect,
}: {
    app: MyApp | null
    onClose: () => void
    onCancelInstall: (appId: string) => Promise<void>
    onRemoveApp: (app: MyApp) => void
    confirmationPlacementSx: SxProps<Theme>
    darkMode: boolean
    scopeRect: ContentScopeRect | null
}) {
    const { t, i18n } = useTranslation('shell')
    const supportUrl = (i18n.resolvedLanguage ?? i18n.language ?? 'en').toLowerCase().startsWith('zh')
        ? 'https://support.websoft9.com/docs/helpdesk#contact'
        : 'https://support.websoft9.com/en/docs/helpdesk#contact'
    const followLogs = useRef(true)
    const copyContainerRef = useRef<HTMLDivElement>(null)
    const [copyMessage, setCopyMessage] = useState('')
    const [isCancelling, setIsCancelling] = useState(false)
    const cancelRequestInFlightRef = useRef(false)
    const [cancelConfirmationAppId, setCancelConfirmationAppId] = useState<string | null>(null)
    const isCancelled = app?.status === 6
    const isError = !isCancelled && (Boolean(app?.error) || app?.status === 4)
    const isInstalling = app?.status === 3
    const canCancelInstall = isInstalling && app?.phase === 'pulling' && !app.cancel_requested
    useEffect(() => {
        setCancelConfirmationAppId(null)
    }, [app?.app_id, app?.tracking_id, canCancelInstall])
    const stages = app?.logs ?? []
    const steps = app ? getInstallSteps(app) : []
    const failure = app ? getInstallError(app) : null
    const dialogPalette = getSurfacePalette(darkMode)
    const stageKeys: Record<string, string> = {
        'Initializing installation': 'initializing',
        'Pulling docker image': 'pulling',
        'Starting the services': 'starting',
        'Configuring the domain': 'domain',
        'Installation complete': 'complete',
        'Installation cancelled': 'cancelled',
    }
    const stageTitle = (title: string) => stageKeys[title] ? t(`myAppsPage.dialog.stages.${stageKeys[title]}`) : title
    const logRows = buildInstallLogRows(stages)
    const hasLogs = logRows.length > 0
    const visibleRows = logRows.slice(-MAX_INSTALL_LOG_LINES)
    const logOffset = logRows.length - visibleRows.length
    const exportText = app ? getInstallExportText(app, stageTitle) : ''
    const canExport = Boolean(exportText)
    const installationNotice = isCancelled || isError ? <Box role={isCancelled ? 'status' : undefined} sx={{ display: 'flex', gap: 1.25, px: 2.5, py: 1.75, flexShrink: 0, backgroundColor: isCancelled ? darkMode ? 'rgba(245, 158, 11, 0.14)' : '#fff7e6' : darkMode ? dialogPalette.dangerSoft : '#fff5f5', color: isCancelled ? darkMode ? '#fbbf24' : '#a16207' : dialogPalette.danger, borderBottom: `1px solid ${dialogPalette.border}` }}>
        <CircleAlert size={20} style={{ flexShrink: 0, marginTop: 2 }} />
        <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontSize: 15, fontWeight: 600 }}>{t(isCancelled ? 'myAppsPage.dialog.cancelledTitle' : `myAppsPage.dialog.errors.${failure?.category ?? 'unknown'}.title`)}</Typography>
            <Typography sx={{ mt: 0.5, fontSize: 13, lineHeight: 1.7 }}>{t(isCancelled ? 'myAppsPage.dialog.cancelledDescription' : `myAppsPage.dialog.errors.${failure?.category ?? 'unknown'}.description`)}</Typography>
        </Box>
    </Box> : null
    const detailSx = {
        borderBottom: `1px solid ${dialogPalette.border}`,
        '& summary': { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 16px', alignItems: 'center', gap: 1.25, py: 1.25, cursor: 'pointer', fontSize: 13, fontWeight: 600, listStyle: 'none', overflowWrap: 'anywhere' },
        '& summary::-webkit-details-marker': { display: 'none' },
        '& summary:focus-visible': { outline: `2px solid ${dialogPalette.accent}`, outlineOffset: 2 },
        '&[open] > summary .detail-chevron': { transform: 'rotate(90deg)' },
        '& .detail-chevron': { color: dialogPalette.subtleText, flexShrink: 0 },
        '& pre': { m: 0, mb: 1.75, p: 1.75, backgroundColor: dialogPalette.panelSoft, fontSize: 12, lineHeight: 1.8, fontFamily: 'Menlo, Consolas, "Courier New", monospace', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', color: dialogPalette.subtleText },
    }

    async function copyLogs() {
        try {
            let copied = false
            if (navigator.clipboard?.writeText) {
                try {
                    await navigator.clipboard.writeText(exportText)
                    copied = true
                } catch {
                    copied = false
                }
            }
            if (!copied) {
                const container = copyContainerRef.current
                if (!container) throw new Error('Copy container unavailable')
                const previousFocus = document.activeElement
                const textarea = document.createElement('textarea')
                textarea.value = exportText
                textarea.readOnly = true
                textarea.style.position = 'fixed'
                textarea.style.opacity = '0'
                textarea.style.width = '1px'
                textarea.style.height = '1px'
                textarea.tabIndex = -1
                container.appendChild(textarea)
                try {
                    textarea.focus({ preventScroll: true })
                    textarea.select()
                    if (!document.execCommand('copy')) throw new Error('Copy failed')
                } finally {
                    textarea.remove()
                    if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus({ preventScroll: true })
                }
            }
            setCopyMessage(t('myAppsPage.dialog.copiedError'))
        } catch {
            setCopyMessage(t('myAppsPage.dialog.copyErrorFailed'))
        }
    }

    function downloadLogs() {
        const url = URL.createObjectURL(new Blob([exportText], { type: 'text/plain;charset=utf-8' }))
        const link = document.createElement('a')
        link.href = url
        link.download = `${app?.app_id ?? 'installation'}-install.log`
        link.click()
        window.setTimeout(() => URL.revokeObjectURL(url), 0)
    }

    async function cancelInstall() {
        if (!app || cancelRequestInFlightRef.current || !canCancelInstall || cancelConfirmationAppId !== app.app_id) return
        cancelRequestInFlightRef.current = true
        setCancelConfirmationAppId(null)
        setIsCancelling(true)
        try {
            await onCancelInstall(app.app_id)
        } finally {
            cancelRequestInFlightRef.current = false
            setIsCancelling(false)
        }
    }

    return (<>
        <SurfaceDialog
            darkMode={darkMode}
            onClose={onClose}
            open={Boolean(app)}
            scope="content"
            scopeRect={scopeRect}
            contentStrategy="viewport-fixed"
            aria-labelledby="installation-log-title"
            sx={{ '& .MuiDialog-container': { alignItems: 'flex-start', px: 1.5, py: 2 } }}
            paperSx={{
                width: 'min(960px, 100%)',
                maxWidth: '960px',
                height: 'min(560px, 72dvh)',
                maxHeight: 'calc(100% - 32px)',
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
                ref={copyContainerRef}
                sx={{
                    backgroundColor: dialogPalette.dialogBg,
                    color: dialogPalette.text,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    py: 1.5,
                    px: 2,
                    flexShrink: 0,
                    userSelect: 'none',
                    borderBottom: `1px solid ${dialogPalette.border}`,
                }}
            >
                <Box sx={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'baseline', flexWrap: 'wrap', gap: '4px 12px' }}>
                    <Typography id="installation-log-title" sx={{ fontSize: 16, fontWeight: 600, lineHeight: 1.5, flexShrink: 0 }}>
                        {t(isError ? 'myAppsPage.dialog.errorTitle' : 'myAppsPage.dialog.logsTitle')}
                    </Typography>
                    <Typography sx={{ fontSize: 12, color: dialogPalette.subtleText, overflowWrap: 'anywhere', borderLeft: `1px solid ${dialogPalette.border}`, pl: 1.5 }}>{app?.app_id}</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', flexShrink: 0, gap: 0.5 }}>
                    {isError ? <>
                        <Tooltip title={t('myAppsPage.dialog.copyError')}><span><IconButton aria-label={t('myAppsPage.dialog.copyError')} disabled={!canExport} size="small" onClick={() => void copyLogs()} sx={{ color: dialogPalette.subtleText }}><Copy size={17} /></IconButton></span></Tooltip>
                        <Tooltip title={t('myAppsPage.dialog.downloadError')}><span><IconButton aria-label={t('myAppsPage.dialog.downloadError')} disabled={!canExport} size="small" onClick={downloadLogs} sx={{ color: dialogPalette.subtleText }}><Download size={17} /></IconButton></span></Tooltip>
                    </> : null}
                    <Tooltip title={t('myAppsPage.dialog.close')}><IconButton aria-label={t('myAppsPage.dialog.close')} size="small" onClick={onClose} sx={{ color: dialogPalette.subtleText }}><X size={18} /></IconButton></Tooltip>
                </Box>
            </Box>

            {isError && failure ? <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
                {installationNotice}
                <Box sx={{ px: { xs: 2, sm: 3 }, py: 2.75 }}>
                    {failure.object ? <Box sx={{ mb: 2.25 }}>
                        <Typography sx={{ fontSize: 12, color: dialogPalette.subtleText }}>{t(failure.category === 'image' ? 'myAppsPage.dialog.imageObject' : 'myAppsPage.dialog.failureObject')}</Typography>
                        <Typography sx={{ mt: 0.875, fontSize: 13, color: dialogPalette.text, fontFamily: 'Menlo, Consolas, "Courier New", monospace', overflowWrap: 'anywhere' }}>{failure.object}</Typography>
                    </Box> : null}
                    {getInstallSourceGroups(failure.sources).map(group => (
                        <Box key={group.nameKey ?? group.label} sx={{ display: 'grid', gridTemplateColumns: { xs: 'minmax(0, 1fr)', sm: '108px minmax(0, 1fr)' }, columnGap: 2, borderTop: `1px solid ${dialogPalette.border}` }}>
                            <Typography sx={{ alignSelf: { xs: 'start', sm: 'center' }, pt: { xs: 2, sm: 0 }, fontSize: 13, fontWeight: 500, color: dialogPalette.text }}>{group.nameKey ? t(`myAppsPage.dialog.${group.nameKey}`) : group.label}</Typography>
                            <Box sx={{ minWidth: 0 }}>
                                {group.sources.map((source, index) => {
                                    const summary = getInstallSourceSummary(source)
                                    return <Box component="details" key={`${index}:${source.reference}`} sx={{ ...detailSx, '&:last-child': { borderBottom: 0 }, '& summary': { ...detailSx['& summary'], gridTemplateColumns: 'minmax(0, 1fr) auto 16px', gap: { xs: 1, sm: 2 }, py: 2 } }}>
                                        <summary>
                                            <Box component="span" title={source.reference} sx={{ fontSize: { xs: 11, sm: 12 }, fontWeight: 400, fontFamily: 'Menlo, Consolas, "Courier New", monospace', color: dialogPalette.subtleText, overflowWrap: 'anywhere', minWidth: 0 }}>{summary.registry}</Box>
                                            <Box component="span" sx={{ fontSize: { xs: 11, sm: 12 }, fontWeight: 400, color: dialogPalette.subtleText, whiteSpace: 'nowrap' }}>{t(`myAppsPage.dialog.sourceResults.${summary.result}`)}</Box>
                                            <ChevronRight size={16} className="detail-chevron" />
                                        </summary>
                                        <pre>{formatInstallSourceReason(source.reason)}</pre>
                                    </Box>
                                })}
                            </Box>
                        </Box>
                    ))}
                    {!failure.sources.length ? <Box component="pre" sx={{ m: 0, p: 1.5, borderLeft: `2px solid ${dialogPalette.border}`, backgroundColor: dialogPalette.panelSoft, color: dialogPalette.subtleText, fontFamily: 'Menlo, Consolas, "Courier New", monospace', fontSize: 12, lineHeight: 1.8, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{failure.raw || t('myAppsPage.dialog.noErrorDetails')}</Box> : null}
                </Box>
            </Box> : null}

            {!isError ? <Box sx={{ p: 0, flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', backgroundColor: dialogPalette.dialogBg }}>
                {!isCancelled && steps.length > 0 ? (
                    <Box sx={{
                        flexShrink: 0,
                        display: 'grid',
                        gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', sm: 'repeat(4, minmax(0, 1fr))' },
                        alignItems: 'stretch',
                        columnGap: 1.5,
                        rowGap: 1.5,
                        borderBottom: `1px solid ${dialogPalette.border}`,
                        backgroundColor: dialogPalette.panelSoft,
                        padding: '16px 24px',
                    }}>
                        {steps.map((step, idx) => {
                            const isActive = step.state === 'active'
                            const isDone = step.state === 'done'
                            return (
                                <Box
                                    key={step.key}
                                    sx={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 1,
                                        minWidth: 0,
                                        fontSize: 13,
                                        fontWeight: isActive ? 600 : 400,
                                        color: isActive ? dialogPalette.accent : dialogPalette.subtleText,
                                        userSelect: 'none',
                                        whiteSpace: 'normal',
                                    }}
                                >
                                    <Box component="span" sx={{ width: 22, height: 22, flexShrink: 0, borderRadius: '50%', display: 'grid', placeItems: 'center', fontSize: 11, fontWeight: 600, backgroundColor: isActive ? dialogPalette.accent : isDone ? darkMode ? 'rgba(52, 211, 153, 0.14)' : '#eaf7f1' : dialogPalette.actionBg, color: isActive ? '#fff' : isDone ? darkMode ? '#34d399' : '#169c78' : dialogPalette.subtleText }}>
                                        {isDone ? <Check size={13} /> : step.state === 'interrupted' ? <X size={13} /> : idx + 1}
                                    </Box>
                                    <Box component="span" sx={{ minWidth: 0 }}>{`${t(`myAppsPage.dialog.stages.${step.key}`)}${step.state === 'skipped' ? ` (${t('myAppsPage.dialog.skipped')})` : ''}`}</Box>
                                    {idx < steps.length - 1 ? <Box aria-hidden="true" sx={{ height: '1px', backgroundColor: dialogPalette.border, flex: 1, minWidth: 8, ml: 0.5, display: { xs: idx % 2 === 0 ? 'block' : 'none', sm: 'block' } }} /> : null}
                                </Box>
                            )
                        })}
                    </Box>
                ) : null}

                {isCancelled ? installationNotice : null}

                <div ref={(container) => {
                    if (container && followLogs.current) container.scrollTop = container.scrollHeight
                }} role="log" aria-label={t('myAppsPage.dialog.logsTitle')} aria-live="off" onScroll={(event) => {
                    const container = event.currentTarget
                    followLogs.current = container.scrollHeight - container.scrollTop - container.clientHeight < 48
                }} style={{
                    flex: 1,
                    minHeight: 0,
                    overflowY: 'auto',
                    overflowX: 'hidden',
                    fontFamily: 'Menlo, Consolas, "Courier New", monospace',
                    fontSize: '12px',
                    lineHeight: '1.8',
                    padding: '12px 16px',
                    boxSizing: 'border-box',
                    backgroundColor: dialogPalette.dialogBg,
                }}>
                    {!hasLogs && !isError ? (
                        <div style={{
                            height: '100%',
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
                                    <span style={{ fontSize: '13px', color: dialogPalette.subtleText, fontFamily: 'inherit' }}>
                                        {stages.length > 0 ? stageTitle(stages[stages.length - 1].title) : t('myAppsPage.dialog.preparing')}
                                    </span>
                                </>
                            ) : (
                                <span style={{ fontSize: '12px', color: dialogPalette.subtleText }}>{t('myAppsPage.dialog.noSubLogs')}</span>
                            )}
                        </div>
                    ) : null}

                    {visibleRows.map((row, index) => (
                        <Box key={row.key}>
                            {index === 0 || visibleRows[index - 1].stageIndex !== row.stageIndex ? (
                                <Typography sx={{ pl: '44px', py: 1, mt: index === 0 ? 0 : 1, fontSize: 11, fontWeight: 600, color: dialogPalette.subtleText }}>{stageTitle(stages[row.stageIndex].title)}</Typography>
                            ) : null}
                            {row.image && (index === 0 || visibleRows[index - 1].image !== row.image || visibleRows[index - 1].stageIndex !== row.stageIndex) ? <Typography sx={{ pl: '44px', pt: 1, pb: 0.5, fontSize: 12, fontWeight: 600, color: dialogPalette.text, overflowWrap: 'anywhere' }}>{row.image}</Typography> : null}
                            <Box sx={{ display: 'grid', gridTemplateColumns: '32px minmax(0, 1fr)', gap: '12px', py: '2px', '&:hover': { backgroundColor: dialogPalette.panelHover } }}>
                                <Box component="span" sx={{ color: dialogPalette.placeholderText, userSelect: 'none', textAlign: 'right', fontSize: 11 }}>{logOffset + index + 1}</Box>
                                <Box component="span" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', color: /\b(error|failed|fatal)\b/i.test(row.text) ? dialogPalette.danger : dialogPalette.text }}>{row.text}</Box>
                            </Box>
                        </Box>
                    ))}
                </div>
            </Box> : null}

            <Box sx={{ display: 'flex', justifyContent: 'flex-end', flexWrap: 'wrap', gap: 1, px: 2, py: 1.25, backgroundColor: dialogPalette.dialogBg, borderTop: `1px solid ${dialogPalette.border}`, flexShrink: 0 }}>
                {isError && failure?.category === 'image' ? <Link component={RouterLink} to="/settings#app-mirror" onClick={onClose} underline="always" sx={{ width: { xs: '100%', sm: 'auto' }, mr: 'auto', alignSelf: 'center', fontSize: 13, color: dialogPalette.subtleText, '&:hover': { color: dialogPalette.text } }}>{t('myAppsPage.dialog.imageSettings')}</Link> : null}
                <Button color="inherit" onClick={onClose} variant="contained" sx={{ minWidth: 68, backgroundColor: dialogPalette.actionBg, color: dialogPalette.subtleText, borderRadius: 0, boxShadow: 'none', '&:hover': { backgroundColor: dialogPalette.actionHover, boxShadow: 'none', color: dialogPalette.text } }}>
                    {t('myAppsPage.dialog.close')}
                </Button>
                {canCancelInstall ? (
                    <Button disabled={isCancelling} onClick={() => setCancelConfirmationAppId(app?.app_id ?? null)} variant="contained" sx={{ minWidth: 104, borderRadius: 0, boxShadow: 'none', backgroundColor: '#ffbc00', color: '#313a46', '&:hover': { backgroundColor: '#e0a700', boxShadow: 'none' } }}>
                        {t(isCancelling ? 'myAppsPage.dialog.status.cancelling' : 'myAppsPage.dialog.cancelInstall')}
                    </Button>
                ) : null}
                {isError ? (
                    <Button
                        onClick={() => window.open(supportUrl, '_blank')}
                        variant="contained"
                        sx={{ minWidth: 68, backgroundColor: dialogPalette.actionBg, color: dialogPalette.subtleText, borderRadius: 0, boxShadow: 'none', '&:hover': { backgroundColor: dialogPalette.actionHover, boxShadow: 'none', color: dialogPalette.text } }}
                    >
                        {t('myAppsPage.dialog.support')}
                    </Button>
                ) : null}
                {app && (isCancelled || isError) ? <Button onClick={() => onRemoveApp(app)} variant="contained" sx={{ minWidth: 104, borderRadius: 0, boxShadow: 'none', backgroundColor: '#ffbc00', color: '#313a46', '&:hover': { backgroundColor: '#e0a700', boxShadow: 'none' } }}>{t('myAppsPage.dialog.removeTitle')}</Button> : null}
            </Box>
        </SurfaceDialog>
        <SurfaceDialog
            darkMode={darkMode}
            open={Boolean(app && cancelConfirmationAppId === app.app_id && canCancelInstall)}
            onClose={() => setCancelConfirmationAppId(null)}
            scope="content"
            scopeRect={scopeRect}
            contentStrategy="viewport-fixed"
            sx={confirmationPlacementSx}
            aria-labelledby="cancel-install-title"
            aria-describedby="cancel-install-description"
            paperSx={{ width: { xs: 'min(100%, 560px)', md: 'min(560px, calc(100% - 20px))' }, maxWidth: '560px', backgroundColor: dialogPalette.dialogBg, color: dialogPalette.text, border: `1px solid ${dialogPalette.border}` }}
        >
            <Box sx={{ px: { xs: 2, md: 2.5 }, py: { xs: 1.5, md: 1.75 }, borderBottom: `1px solid ${dialogPalette.border}`, display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Typography id="cancel-install-title" sx={{ flex: 1, fontSize: { xs: 18, md: 20 }, fontWeight: 600, lineHeight: 1.2 }}>{t('myAppsPage.dialog.cancelConfirmTitle')}</Typography>
                <IconButton aria-label={t('myAppsPage.dialog.close')} onClick={() => setCancelConfirmationAppId(null)} size="small" sx={{ width: 40, height: 40, color: dialogPalette.subtleText, backgroundColor: 'transparent', '&:hover': { backgroundColor: 'transparent', color: dialogPalette.text, opacity: 0.84 } }}><X size={16} /></IconButton>
            </Box>
            <Box sx={{ px: { xs: 2, md: 2.5 }, py: 2.25, borderBottom: `1px solid ${dialogPalette.border}` }}>
                <Typography id="cancel-install-description" sx={{ fontSize: 14, lineHeight: 1.75, color: dialogPalette.subtleText, overflowWrap: 'anywhere' }}>{t('myAppsPage.dialog.cancelConfirmDescription', { app: app?.app_id })}</Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', flexWrap: 'wrap', gap: 1, px: 2.5, py: 2, borderTop: `1px solid ${dialogPalette.border}` }}>
                <Button autoFocus onClick={() => setCancelConfirmationAppId(null)} variant="contained" sx={{ minWidth: 68, backgroundColor: dialogPalette.actionBg, color: dialogPalette.subtleText, borderRadius: 0, boxShadow: 'none', '&:hover': { backgroundColor: dialogPalette.actionHover, boxShadow: 'none', color: dialogPalette.text } }}>{t('myAppsPage.dialog.continueInstall')}</Button>
                <Button disabled={isCancelling || !canCancelInstall} onClick={() => void cancelInstall()} variant="contained" sx={{ minWidth: 68, borderRadius: 0, boxShadow: 'none' }}>{t('myAppsPage.dialog.confirmCancel')}</Button>
            </Box>
        </SurfaceDialog>
        <SurfaceFeedbackToast darkMode={darkMode} open={Boolean(copyMessage)} onClose={() => setCopyMessage('')} message={copyMessage} severity="info" />
    </>)
}

// =====================
// Main component
// =====================
export function MyAppsPage() {
    const { t, i18n } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const isConnectionUnavailable = useConnectionUnavailable()
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
    const prefetchedActiveAppSignatureRef = useRef<string | null>(null)

    const { data, error, isLoading, refetch } = useMyApps()
    const apps = data ?? []
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const apiLocale = locale.toLowerCase().startsWith('zh') ? 'zh' : 'en'
    const cancellationFeedbackKey = feedback?.cancellingInstallKey
    const cancellationFeedbackApp = cancellationFeedbackKey ? apps.find((app) => (app.tracking_id ?? app.app_id) === cancellationFeedbackKey) : undefined
    const cancellationFeedbackIsVisible = !cancellationFeedbackKey || cancellationFeedbackApp?.status === 3
    useEffect(() => {
        if (cancellationFeedbackKey && !cancellationFeedbackIsVisible) {
            setFeedback((current) => current?.cancellingInstallKey === cancellationFeedbackKey ? null : current)
        }
    }, [cancellationFeedbackKey, cancellationFeedbackIsVisible])
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

        const prefetchTargets = activeApps.slice(0, 6)
        const prefetchSignature = `${apiLocale}:${prefetchTargets.map((app) => app.app_id).join('|')}`
        if (prefetchedActiveAppSignatureRef.current === prefetchSignature) {
            return
        }
        prefetchedActiveAppSignatureRef.current = prefetchSignature

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
            prefetchTargets.forEach((app) => {
                void queryClient.prefetchQuery({
                    queryKey: ['my-app-detail', app.app_id, apiLocale],
                    queryFn: async () => fetchMyAppDetail(app.app_id, apiLocale),
                    staleTime: 10_000,
                })
            })
        })

        return () => cancel(handle)
    }, [apiLocale, apps, queryClient])

    // Auto-trigger detail/log dialog after setup wizard completes
    const setupAutoTriggeredRef = useRef(false)
    useEffect(() => {
        if (setupAutoTriggeredRef.current || apps.length === 0) return
        const targetAppId = typeof window !== 'undefined' ? window.sessionStorage.getItem('websoft9_setup_target_app') : null
        if (!targetAppId) return

        const app = apps.find((a) => a.app_id === targetAppId)
        if (!app) return

        setupAutoTriggeredRef.current = true
        window.sessionStorage.removeItem('websoft9_setup_target_app')

        if (app.status === 1) {
            markMyAppsDetailOverlayIntent(app.app_id)
            navigate(`/myapps/${encodeURIComponent(app.app_id)}`, { replace: true })
        } else if (app.status === 3 || app.status === 4) {
            setLogDialogKey(app.tracking_id ?? app.app_id)
        }
    }, [apps, navigate])

    // Resolve the live app for the log dialog (auto-refreshes with the query)
    const logDialogApp = useMemo(
        () => logDialogKey ? (apps.find((a) => (a.tracking_id ?? a.app_id) === logDialogKey) ?? null) : null,
        [logDialogKey, apps],
    )

    const statusCounts = useMemo(() => {
        const counts: Record<string, number> = { '1': 0, '2': 0, '3': 0, '4': 0, '6': 0 }
        for (const app of apps) {
            const key = String(app.status)
            if (key in counts) counts[key]++
        }
        return counts
    }, [apps])

    const filteredApps = useMemo(
        () => apps.filter((app) => {
            const matchesStatus = selectedStatus === 'all' || String(app.status) === selectedStatus
            const searchText = [app.app_name, app.app_id, app.app_version, app.error, app.app_dist].filter(Boolean).join(' ').toLowerCase()
            const matchesSearch = !searchValue.trim() || searchText.includes(searchValue.trim().toLowerCase())
            return matchesStatus && matchesSearch
        }),
        [apps, searchValue, selectedStatus],
    )

    const isWebsoft9App = (app: MyApp) => app.app_official || Boolean(app.gitConfig && Object.keys(app.gitConfig).length > 0)
    const platformApps = useMemo(() => filteredApps.filter(isWebsoft9App), [filteredApps])
    const otherApps = useMemo(() => filteredApps.filter((app) => !isWebsoft9App(app)), [filteredApps])

    const hasVisiblePlatformApps = platformApps.length > 0
    const hasVisibleOtherApps = otherApps.length > 0
    const showLoadingState = isLoading || manualRefreshing

    function handleCardClick(app: MyApp) {
        if (!isWebsoft9App(app) && app.status !== 4 && app.status !== 6) return
        if (app.status === 1) {
            const contentScopeContainer = typeof document === 'undefined' ? null : document.querySelector('#app-shell-main')
            const backgroundScrollTop = contentScopeContainer instanceof HTMLElement ? contentScopeContainer.scrollTop : 0

            markMyAppsDetailOverlayIntent(app.app_id)
            void navigate(`/myapps/${encodeURIComponent(app.app_id)}`, {
                state: {
                    backgroundScrollTop,
                },
            })
        } else if (app.status === 3 || app.status === 4 || app.status === 6) {
            setLogDialogKey(app.tracking_id ?? app.app_id)
        }
    }

    async function handleConfirmRemove() {
        if (!removeApp) return
        setActionBusy(true)
        try {
            if (removeType === 'error' || removeType === 'cancelled') {
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

    async function handleCancelInstall(appId: string) {
        const installation = queryClient.getQueryData<MyApp[]>(['my-apps', apiLocale])?.find((app) => app.app_id === appId)
        const installationKey = installation?.tracking_id ?? appId
        try {
            const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/install/cancel`, {
                method: 'POST',
                credentials: 'include',
                headers: { Accept: 'application/json' },
            })
            if (!response.ok) throw new Error(await parseJsonError(response, `Cancel failed: ${response.status}`))
            const currentInstallation = queryClient.getQueryData<MyApp[]>(['my-apps', apiLocale])?.find((app) => (app.tracking_id ?? app.app_id) === installationKey)
            if (currentInstallation?.status === 3) {
                setFeedback({ severity: 'info', message: t('myAppsPage.dialog.cancelling'), cancellingInstallKey: installationKey })
            }
            await refetch()
        } catch (err) {
            setFeedback({ severity: 'warning', message: err instanceof Error ? err.message : t('myAppsPage.dialog.cancelFailed') })
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
            const canOpenDetail = app.app_official || Boolean(app.gitConfig && Object.keys(app.gitConfig).length > 0)
            const canOpenCard = canOpenDetail || app.status === 4 || app.status === 6
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
            }

            return (
                <div
                    key={`${app.app_id}-${app.tracking_id ?? 'stable'}`}
                    className={`myapps-vcard myapps-vcard--${variant}${canOpenCard ? ' highlight' : ''}`}
                    onClick={canOpenCard ? () => handleCardClick(app) : undefined}
                    role={canOpenCard ? 'button' : undefined}
                    tabIndex={canOpenCard ? 0 : undefined}
                    onKeyDown={canOpenCard ? (e) => { if (e.key === 'Enter' || e.key === ' ') handleCardClick(app) } : undefined}
                >
                    {!app.app_official && isWebsoft9App(app) ? (
                        <div className="myapps-vcard-ribbon">
                            <span>{t('myAppsPage.card.customDeploy')}</span>
                        </div>
                    ) : null}
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
                '--myapps-surface': palette.panelBg,
                '--myapps-surface-soft': palette.panelBg,
                '--myapps-surface-hover': palette.panelHover,
                '--myapps-border': palette.borderStrong,
                '--myapps-text': palette.text,
                '--myapps-muted': palette.subtleText,
                '--myapps-heading': palette.subtleText,
                '--myapps-input-bg': palette.panelBg,
                '--myapps-primary': palette.accent,
                '--myapps-badge-success-bg': 'var(--ds-color-success-bg)',
                '--myapps-badge-success-text': 'var(--ds-color-success-text)',
                '--myapps-badge-warning-bg': 'var(--ds-color-warning-bg)',
                '--myapps-badge-warning-text': 'var(--ds-color-warning-text)',
                '--myapps-badge-info-bg': 'var(--ds-color-info-bg)',
                '--myapps-badge-info-text': 'var(--ds-color-info-text)',
                '--myapps-badge-danger-bg': 'var(--ds-color-danger-bg)',
                '--myapps-badge-danger-text': 'var(--ds-color-danger-text)',
                '--myapps-badge-dark-bg': 'var(--ds-color-neutral-bg)',
                '--myapps-badge-dark-text': 'var(--ds-color-neutral-text)',
                height: 'calc(100vh - 120px)',
                position: 'relative',
                mx: { xs: -1, md: -3 },
                my: { xs: -1.25, md: -2.25 },
                px: { xs: 2, md: 3 },
                py: { xs: 1.25, md: 1.5 },
                backgroundColor: palette.panelBg,
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
                    <Box
                        sx={{
                            display: { xs: 'flex', md: 'grid' },
                            gridTemplateColumns: { md: '26px 26px' },
                            gridTemplateRows: { md: '20px' },
                            columnGap: { md: 0 },
                            gap: { xs: 0.75, md: 0 },
                            justifyContent: 'flex-end',
                            justifyItems: { md: 'center' },
                            alignItems: 'center',
                            flexShrink: 0,
                            alignSelf: 'start',
                            pt: 0,
                            mt: 0.05,
                        }}
                    >
                        <Tooltip title={t('applicationsHubPage.menu.action')}>
                            <IconButton
                                color="inherit"
                                onClick={() => {
                                    navigate('/applications/deploy')
                                }}
                                size="small"
                                className="app-shell-page-action"
                                title={t('applicationsHubPage.menu.action')}
                                sx={{
                                    width: { xs: 34, md: 26 },
                                    minWidth: { xs: 34, md: 26 },
                                    maxWidth: { xs: 34, md: 26 },
                                    height: { xs: 34, md: 26 },
                                    minHeight: { xs: 34, md: 26 },
                                    maxHeight: { xs: 34, md: 26 },
                                    padding: 0.25,
                                    borderRadius: { xs: '10px', md: '2px' },
                                    color: palette.subtleText,
                                    gridColumn: { md: '1' },
                                    gridRow: { md: '1' },
                                    '&:hover': {
                                        background: palette.panelSoft,
                                        color: palette.text,
                                        boxShadow: '0 1px 2px rgba(15, 23, 42, 0.06)',
                                    },
                                    '& .MuiSvgIcon-root': {
                                        fontSize: 16.5,
                                    },
                                }}
                            >
                                <IconCompose />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title={manualRefreshing ? t('myAppsPage.hero.refreshing') : t('myAppsPage.hero.refresh')}>
                            <IconButton
                                color="inherit"
                                onClick={() => {
                                    void handleManualRefresh()
                                }}
                                size="small"
                                disabled={manualRefreshing}
                                className="app-shell-page-action"
                                title={manualRefreshing ? t('myAppsPage.hero.refreshing') : t('myAppsPage.hero.refresh')}
                                sx={{
                                    width: { xs: 34, md: 26 },
                                    minWidth: { xs: 34, md: 26 },
                                    maxWidth: { xs: 34, md: 26 },
                                    height: { xs: 34, md: 26 },
                                    minHeight: { xs: 34, md: 26 },
                                    maxHeight: { xs: 34, md: 26 },
                                    padding: 0.25,
                                    borderRadius: { xs: '10px', md: '2px' },
                                    color: palette.subtleText,
                                    gridColumn: { md: '2' },
                                    gridRow: { md: '1' },
                                    ml: { xs: 0, md: -0.2 },
                                    '&:hover': {
                                        background: palette.panelSoft,
                                        color: palette.text,
                                        boxShadow: '0 1px 2px rgba(15, 23, 42, 0.06)',
                                    },
                                    '& .MuiSvgIcon-root': {
                                        fontSize: 16.5,
                                    },
                                }}
                            >
                                {manualRefreshing ? <CircularProgress size={14} color="inherit" /> : <IconRefresh />}
                            </IconButton>
                        </Tooltip>
                    </Box>
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
                        <option value="all">{t('myAppsPage.filters.allStates')} ({apps.length})</option>
                        <option value="1">Active ({statusCounts['1']})</option>
                        <option value="2">Inactive ({statusCounts['2']})</option>
                        <option value="3">Installing ({statusCounts['3']})</option>
                        <option value="4">Error ({statusCounts['4']})</option>
                        <option value="6">Cancelled ({statusCounts['6']})</option>
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
            {!showLoadingState && error && !(isConnectionUnavailable && isPlatformUnavailableError(error)) ? (
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
                                        <rect width="64" height="64" rx="16" fill={palette.panelSoft} />
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
                            ) : hasVisibleOtherApps ? (
                                <div>
                                    <h4 className="myapps-section-heading">{t('myAppsPage.sections.officialApps')}</h4>
                                    <Card elevation={0} sx={{ border: `1px solid ${palette.border}`, mt: 2, backgroundColor: palette.panelBg }}>
                                        <CardContent>
                                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '48px 24px', gap: 12 }}>
                                                <svg viewBox="0 0 64 64" width="64" height="64" fill="none" xmlns="http://www.w3.org/2000/svg">
                                                    <rect width="64" height="64" rx="16" fill={palette.panelSoft} />
                                                    <path d="M32 16l14 7v14l-14 7-14-7V23l14-7z" stroke={isDarkMode ? '#64748b' : '#b0b8d1'} strokeWidth="2" strokeLinejoin="round" />
                                                    <path d="M32 16v14M18 23l14 7 14-7" stroke={isDarkMode ? '#64748b' : '#b0b8d1'} strokeWidth="2" />
                                                </svg>
                                                <Typography sx={{ fontWeight: 600, fontSize: 16, color: palette.text, mt: 1 }}>
                                                    {t('myAppsPage.states.noAppsInstalled')}
                                                </Typography>
                                                <Typography color={palette.subtleText} variant="body2" sx={{ textAlign: 'center', maxWidth: 400, lineHeight: 1.7 }}>
                                                    {t('myAppsPage.states.emptyDetail')}
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
                key={logDialogApp?.app_id ?? 'closed'}
                app={logDialogApp}
                onClose={() => setLogDialogKey(null)}
                onCancelInstall={handleCancelInstall}
                onRemoveApp={(app) => {
                    setLogDialogKey(null)
                    setRemoveApp(app)
                    setRemoveType(app.status === 6 ? 'cancelled' : 'error')
                }}
                confirmationPlacementSx={contentScopedDialogPlacementSx}
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
                        sx={{ minWidth: 68, borderRadius: 0, boxShadow: 'none', backgroundColor: '#ffbc00', color: '#313a46', '&:hover': { backgroundColor: '#e0a700', boxShadow: 'none' } }}
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
            {cancellationFeedbackIsVisible ? <SurfaceFeedbackToast
                key={cancellationFeedbackKey ? `cancel-install-${cancellationFeedbackKey}` : 'general-feedback'}
                open={Boolean(feedback)}
                onClose={() => setFeedback(null)}
                severity={feedback?.severity ?? 'info'}
                message={feedback?.message ?? ''}
                scope="content"
                scopeRect={contentScopeRect}
                darkMode={isDarkMode}
                autoHideDuration={cancellationFeedbackKey ? null : undefined}
            /> : null}

            <Outlet />
        </Box>
    )
}
