import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { SurfaceFeedbackToast } from '../../shared/design-system/standard-surfaces'
import { acquireAppFileSession, ConnectionLimitError, FileSessionError, getAppFileErrorKey, getAppFileRoute, MAX_WORKSPACE_CONNECTIONS } from '../terminal/app-file-sessions'
import { AppFileConnectionPrompt } from '../terminal/terminal-page'

export function AppSftpDialog({ appId, volumeId, initialError, darkMode, scopeRect, onClose }: { appId: string; volumeId: string; initialError?: string; darkMode: boolean; scopeRect: { top: number; left: number; width: number; height: number } | null; onClose: () => void }) {
    const { t } = useTranslation('shell')
    const navigate = useNavigate()
    const [failureKey, setFailureKey] = useState(initialError ? getAppFileErrorKey(initialError) : null)
    const [error, setError] = useState(initialError && getAppFileErrorKey(initialError) !== 'sftpConnectionRequired' ? t(`myAppsDetailPage.tabs.volumes.fileManager.${getAppFileErrorKey(initialError)}`) : '')
    const [visible, setVisible] = useState(Boolean(initialError))
    const [booting, setBooting] = useState(true)
    const [limitReached, setLimitReached] = useState(false)
    const [busy, setBusy] = useState(false)
    const dismissedRef = useRef(false)

    function handleClose() {
        // Only an explicit user action should suppress the workspace navigation.
        dismissedRef.current = true
        onClose()
    }

    async function createLocalConnection() {
        if (busy) return
        setBusy(true)
        setError('')
        try {
            const response = await fetch('/api/host-access/app-files/account/prepare', { method: 'POST', credentials: 'include' })
            const body = await response.json()
            if (!response.ok) throw new FileSessionError(body.details || body.detail || body.message || response.statusText, response.status, body.code || body.message)
            const session = await acquireAppFileSession(appId, volumeId)
            onClose()
            navigate(getAppFileRoute(session))
        } catch (failure) {
            const key = getAppFileErrorKey(failure)
            setFailureKey(key)
            setLimitReached(failure instanceof ConnectionLimitError)
            setError(key === 'sftpConnectionRequired' && failure instanceof Error ? failure.message : t(`myAppsDetailPage.tabs.volumes.fileManager.${key}`, { count: MAX_WORKSPACE_CONNECTIONS }))
        } finally {
            setBusy(false)
        }
    }

    const prepareConnection = useEffectEvent(async () => {
        if (initialError) {
            setBooting(false)
            setVisible(true)
            return
        }
        try {
            const session = await acquireAppFileSession(appId, volumeId)
            if (dismissedRef.current) return
            navigate(getAppFileRoute(session))
        } catch (failure) {
            if (dismissedRef.current) return
            setBooting(false)
            const atLimit = failure instanceof ConnectionLimitError
            const key = getAppFileErrorKey(failure)
            setFailureKey(key)
            setLimitReached(atLimit)
            setError(key === 'sftpConnectionRequired' || key === 'sftpAuthorizationMissing' ? '' : t(`myAppsDetailPage.tabs.volumes.fileManager.${key}`, { count: MAX_WORKSPACE_CONNECTIONS }))
            setVisible(true)
        }
    })

    useEffect(() => {
        void prepareConnection()
    }, [appId, volumeId])

    if (limitReached) return <SurfaceFeedbackToast open severity="info" message={error} onClose={handleClose} darkMode={darkMode} scope="content" scopeRect={scopeRect} />
    if (booting && !visible) return <SurfaceFeedbackToast open severity="info" message={t('myAppsDetailPage.tabs.volumes.fileManager.sftpConnecting')} onClose={handleClose} darkMode={darkMode} scope="content" scopeRect={scopeRect} />
    return visible ? <AppFileConnectionPrompt error={error} blocked={failureKey === 'sftpDirectoryPermissionDenied' || failureKey === 'sftpScopeDenied'} darkMode={darkMode} scopeRect={scopeRect} busy={busy} onAutomatic={() => void createLocalConnection()} onClose={handleClose} onConfirm={() => { onClose(); navigate(`/terminal?${new URLSearchParams({ new_connection: '1', app_file_app: appId, app_file_volume: volumeId })}`) }} /> : null
}