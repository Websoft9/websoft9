import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Box, Button, DialogActions, DialogContent, DialogTitle, Radio, Stack, Typography } from '@mui/material'
import { SurfaceDialog, SurfaceFeedbackToast } from '../../shared/design-system/standard-surfaces'
import { getSurfacePalette } from '../../shared/design-system/surface-theme'
import { acquireAppFileSession, clearSftpAccessChoice, FileSessionError, getAppFileErrorKey, getAppFileRoute, MAX_WORKSPACE_CONNECTIONS, readSftpAccessChoice, saveSftpAccessChoice, type SftpAccessChoice } from '../terminal/app-file-sessions'

type LocalConnection = {
    profile_id: string
    name?: string
    host?: string
    username?: string
    port?: number
    is_local?: boolean
    managed?: boolean
    has_password?: boolean
    has_private_key?: boolean
}

const readAccessChoice: () => SftpAccessChoice | null = readSftpAccessChoice
const saveAccessChoice = saveSftpAccessChoice
const clearAccessChoice = clearSftpAccessChoice

/**
 * Report whether the platform SFTP account still exists. A remembered choice is
 * only reused while the account is present; otherwise the operator is asked
 * again instead of silently recreating the account.
 */
async function platformAccountReady(): Promise<boolean> {
    try {
        const response = await fetch('/api/host-access/app-files/account', { credentials: 'include' })
        if (!response.ok) return false
        const body = await response.json() as { state?: string }
        return body?.state === 'ready'
    } catch {
        return false
    }
}

/**
 * Ask the operator how to open application files: the platform account or one of
 * the saved local SSH connections. The last successful choice is remembered so
 * later applications open directly unless that choice is no longer available.
 */
export function AppSftpDialog({ appId, volumeId, initialError, darkMode, scopeRect, onClose, switchMode = false, currentProfileId = null, onSwitched }: { appId: string; volumeId: string; initialError?: string; darkMode: boolean; scopeRect: { top: number; left: number; width: number; height: number } | null; onClose: () => void; switchMode?: boolean; currentProfileId?: string | null; onSwitched?: (profileId: string | null, platform: boolean) => void }) {
    const { t } = useTranslation('shell')
    const navigate = useNavigate()
    const palette = getSurfacePalette(darkMode)
    const prefix = 'myAppsDetailPage.tabs.volumes.fileManager.'
    const [connections, setConnections] = useState<LocalConnection[]>([])
    const [loadingConnections, setLoadingConnections] = useState(true)
    const [choice, setChoice] = useState('platform')
    const [error, setError] = useState(initialError && getAppFileErrorKey(initialError) !== 'sftpConnectionRequired' ? t(`${prefix}${getAppFileErrorKey(initialError)}`) : '')
    const [booting, setBooting] = useState(!initialError && !switchMode)
    const [busy, setBusy] = useState(false)
    const [permissionIssue, setPermissionIssue] = useState(false)
    const dismissedRef = useRef(false)
    const startedRef = useRef(false)

    function handleClose() {
        dismissedRef.current = true
        onClose()
    }

    useEffect(() => {
        let cancelled = false
        void (async () => {
            let loaded: LocalConnection[] = []
            try {
                const response = await fetch('/api/host-access/profile', { credentials: 'include' })
                if (response.ok) {
                    const body = await response.json() as { saved_profiles?: LocalConnection[] }
                    const list = Array.isArray(body?.saved_profiles) ? body.saved_profiles : []
                    loaded = list.filter((item) => !item.managed && (item.has_password || item.has_private_key))
                }
            } catch {
                // Keep the empty state when the profile list cannot be loaded.
            }
            if (cancelled) return
            setConnections(loaded)
            setLoadingConnections(false)
            if (initialError || startedRef.current) {
                setBooting(false)
                return
            }
            if (switchMode) {
                // Opened from the application file view: keep the current choice and
                // wait for the operator to confirm instead of connecting again.
                setChoice(currentProfileId || 'platform')
                setBooting(false)
                return
            }
            const saved = readAccessChoice()
            if (saved?.mode === 'platform') {
                if (await platformAccountReady()) {
                    if (cancelled || startedRef.current) return
                    setChoice('platform')
                    startedRef.current = true
                    void connectWithPlatformAccount()
                    return
                }
                if (cancelled) return
                // The platform account was removed: ask again instead of recreating it.
                clearAccessChoice()
                setBooting(false)
            } else if (saved?.mode === 'profile' && loaded.some((item) => item.profile_id === saved.profileId)) {
                setChoice(saved.profileId)
                startedRef.current = true
                void connectWith(saved.profileId)
            } else {
                // The remembered connection is gone (deleted or no credentials):
                // forget it so the operator picks an access method again.
                if (saved?.mode === 'profile') clearAccessChoice()
                setBooting(false)
            }
        })()
        return () => { cancelled = true }
    }, [])

    async function openSession(profileId?: string, platform = false) {
        const session = await acquireAppFileSession(appId, volumeId, profileId, platform ? { platform: true } : undefined)
        if (dismissedRef.current) return
        onClose()
        if (switchMode) {
            onSwitched?.(session.profile_id ?? null, !session.profile_id)
            return
        }
        navigate(getAppFileRoute(session))
    }

    function showFailure(failure: unknown) {
        const key = getAppFileErrorKey(failure)
        // A deleted or unavailable saved connection must not be reused automatically.
        if (key === 'sftpConnectionUnavailable' || key === 'sftpAuthorizationRevoked') clearAccessChoice()
        const denied = key === 'sftpDirectoryPermissionDenied' || key === 'sftpScopeDenied'
        setPermissionIssue(denied)
        setError(denied
            ? t(`${prefix}sftpDirectoryPermissionShort`)
            : key === 'sftpConnectionRequired' && failure instanceof Error ? failure.message : t(`${prefix}${key}`, { count: MAX_WORKSPACE_CONNECTIONS }))
        setBooting(false)
        setBusy(false)
    }

    async function connectWith(profileId?: string) {
        if (busy) return
        setBusy(true)
        setError('')
        setBooting(true)
        try {
            await openSession(profileId)
        } catch (failure) {
            if (!dismissedRef.current) showFailure(failure)
        } finally {
            setBusy(false)
        }
    }

    async function connectWithPlatformAccount() {
        if (busy) return
        setBusy(true)
        setError('')
        setBooting(true)
        try {
            const response = await fetch('/api/host-access/app-files/account/prepare', { method: 'POST', credentials: 'include' })
            const body = await response.json()
            if (!response.ok) throw new FileSessionError(body.details || body.detail || body.message || response.statusText, response.status, body.code || body.message)
            await openSession(undefined, true)
        } catch (failure) {
            if (!dismissedRef.current) showFailure(failure)
        } finally {
            setBusy(false)
        }
    }

    function handleConnect() {
        if (choice === 'platform') {
            saveAccessChoice({ mode: 'platform' })
            void connectWithPlatformAccount()
            return
        }
        saveAccessChoice({ mode: 'profile', profileId: choice })
        void connectWith(choice)
    }

    function selectChoice(value: string) {
        setChoice(value)
        // The提示 describes the previous attempt; drop it once the operator picks
        // another access method so it cannot be mistaken for the new choice.
        setError('')
        setPermissionIssue(false)
    }

    function openTerminalFiles() {
        handleClose()
        navigate('/terminal?view=files')
    }

    function openNewConnection() {
        handleClose()
        navigate(`/terminal?${new URLSearchParams({ new_connection: '1', app_file_app: appId, app_file_volume: volumeId })}`)
    }

    if (booting) return <SurfaceFeedbackToast open severity="info" message={t(`${prefix}sftpConnecting`)} onClose={() => undefined} darkMode={darkMode} scope="content" scopeRect={scopeRect} />

    const hintSx = { m: 0, fontSize: 12.5, lineHeight: 1.7, color: palette.subtleText }
    const radioSx = { p: 0.25, color: palette.border, '&.Mui-checked': { color: palette.accent } }
    const sectionTitleSx = { mb: 0.75, fontSize: 12, fontWeight: 600, letterSpacing: '0.02em', color: palette.subtleText }
    const rowSx = (selected: boolean) => ({
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        width: '100%',
        textAlign: 'left',
        font: 'inherit',
        cursor: 'pointer',
        px: 1.5,
        py: 1,
        border: 'none',
        borderTop: `1px solid ${palette.border}`,
        borderLeft: `3px solid ${selected ? palette.accent : 'transparent'}`,
        borderRadius: 0,
        backgroundColor: selected ? palette.accentSoft : 'transparent',
        '&:first-of-type': { borderTop: 'none' },
        '&:hover': { backgroundColor: selected ? palette.accentSoft : palette.panelHover },
    })
    const rowTitleSx = { flexShrink: 0, fontSize: 13.5, fontWeight: 600, color: palette.text, whiteSpace: 'nowrap' }
    const rowMetaSx = { minWidth: 0, fontSize: 12.5, color: palette.subtleText, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }

    return <>
        <SurfaceDialog
            open
            onClose={busy ? undefined : handleClose}
            darkMode={darkMode}
            scope="content"
            scopeRect={scopeRect}
            contentStrategy="viewport-fixed"
            maxWidth="md"
            paperSx={{ width: 'min(680px, calc(100% - 24px))', maxWidth: 680, borderRadius: 0 }}
            sx={{ zIndex: 1506, '& .MuiDialog-container': { alignItems: 'flex-start', pt: { xs: 1.5, sm: 2, md: 2.5 } }, '& .MuiDialog-paper, & .MuiButton-root, & .MuiAlert-root': { borderRadius: 0 } }}
        >
            <DialogTitle sx={{ px: 2.5, py: 1.5 }}>
                <Typography sx={{ fontSize: 16, fontWeight: 700, color: palette.text }}>{t(`${prefix}sftpAccessChoiceTitle`)}</Typography>
                <Typography sx={{ mt: 0.25, fontSize: 12.5, color: palette.subtleText }}>{t(`${prefix}sftpAccessChoicePrompt`)}</Typography>
            </DialogTitle>
            <DialogContent dividers sx={{ px: 2.5, py: 2, minHeight: 0 }}>
                {error ? (
                    <Box
                        sx={{
                            mb: 1.75,
                            display: 'flex',
                            alignItems: 'center',
                            px: 1.5,
                            py: 1,
                            border: '1px solid rgba(180, 35, 24, 0.22)',
                            borderLeft: '3px solid #b42318',
                            backgroundColor: 'rgba(180, 35, 24, 0.08)',
                        }}
                    >
                        <Typography sx={{ minWidth: 0, fontSize: 12.5, lineHeight: 1.7, color: '#b42318', overflowWrap: 'anywhere' }}>{error}</Typography>
                        {permissionIssue ? (
                            <Button onClick={openTerminalFiles} size="small" sx={{ ml: 'auto', flexShrink: 0, borderRadius: 0, textTransform: 'none', whiteSpace: 'nowrap' }}>{t(`${prefix}sftpOpenTerminalFiles`)}</Button>
                        ) : null}
                    </Box>
                ) : null}

                <Typography sx={sectionTitleSx}>{t(`${prefix}sftpPlatformSection`)}</Typography>
                <Box sx={{ border: `1px solid ${palette.border}` }}>
                    <Box component="button" type="button" onClick={() => selectChoice('platform')} sx={rowSx(choice === 'platform')}>
                        <Radio checked={choice === 'platform'} size="small" sx={radioSx} tabIndex={-1} />
                        <Typography sx={rowTitleSx}>{t(`${prefix}sftpPlatformAccountOption`)}</Typography>
                        <Typography sx={rowMetaSx}>{t(`${prefix}sftpPlatformAccountHint`)}</Typography>
                    </Box>
                </Box>

                <Typography sx={{ ...sectionTitleSx, mt: 2.25 }}>{t(`${prefix}sftpLocalSection`)}</Typography>
                <Box sx={{ border: `1px solid ${palette.border}` }}>
                    <Stack sx={{ maxHeight: 240, overflowY: 'auto' }}>
                        {connections.map((connection) => (
                            <Box
                                component="button"
                                type="button"
                                key={connection.profile_id}
                                onClick={() => selectChoice(connection.profile_id)}
                                sx={rowSx(choice === connection.profile_id)}
                            >
                                <Radio checked={choice === connection.profile_id} size="small" sx={radioSx} tabIndex={-1} />
                                <Typography sx={rowTitleSx}>{connection.name || connection.host}</Typography>
                                <Typography sx={rowMetaSx}>{`${connection.username || '-'}@${connection.host || '-'}${connection.port ? `:${connection.port}` : ''}`}</Typography>
                                {currentProfileId === connection.profile_id ? (
                                    <Box component="span" sx={{ ml: 'auto', flexShrink: 0, px: 0.75, border: `1px solid ${palette.border}`, color: palette.subtleText, fontSize: 11, fontWeight: 700 }}>{t(`${prefix}sftpCurrentConnection`)}</Box>
                                ) : null}
                            </Box>
                        ))}
                        {!connections.length ? (
                            <Box sx={{ px: 1.5, py: 1.25 }}>
                                <Typography sx={hintSx}>{loadingConnections ? t(`${prefix}sftpConnecting`) : t(`${prefix}sftpNoLocalConnections`)}</Typography>
                            </Box>
                        ) : null}
                        <Box
                            component="button"
                            type="button"
                            disabled={busy}
                            onClick={openNewConnection}
                            sx={{ ...rowSx(false), alignItems: 'center' }}
                        >
                            <Typography sx={{ pl: 0.5, fontSize: 13.5, color: palette.accent }}>＋</Typography>
                            <Typography sx={{ fontSize: 13.5, color: palette.accent }}>{t(`${prefix}sftpCreateConnectionEntry`)}</Typography>
                        </Box>
                    </Stack>
                </Box>
            </DialogContent>
            <DialogActions sx={{ px: 2, py: 1.5, gap: 0.5, flexWrap: 'wrap' }}>
                <Button disabled={busy} onClick={handleClose}>{t('myAppsDetailPage.dialogs.cancel')}</Button>
                <Button variant="contained" disabled={busy || (!choice)} onClick={handleConnect}>{t(`${prefix}sftpConnectAction`)}</Button>
            </DialogActions>
        </SurfaceDialog>
    </>
}
