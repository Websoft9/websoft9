import { Alert, Button, CircularProgress, IconButton, MenuItem, Snackbar, TextField } from '@mui/material'
import Accordion from '@mui/material/Accordion'
import AccordionDetails from '@mui/material/AccordionDetails'
import AccordionSummary from '@mui/material/AccordionSummary'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useMyAppAccess } from './use-my-app-access'

type MyAppAccessPanelProps = {
    appId: string
    entryDomains: string[]
    env?: Record<string, string>
    isWebApp: boolean
    onUpdated: () => Promise<void> | void
}

type AccessFeedback = {
    severity: 'success' | 'error'
    message: string
}

type AccountEntry = {
    key: string
    value: string
    isPassword: boolean
}

function IconExpandMore() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z" /></svg>
}

function IconEdit() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75zM20.71 7.04a1.003 1.003 0 0 0 0-1.42L18.37 3.29a1.003 1.003 0 0 0-1.42 0L15.13 5.11l3.75 3.75z" /></svg>
}

function IconDelete() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M6 7h12l-1 14H7L6 7zm3-3h6l1 2h4v2H4V6h4l1-2z" /></svg>
}

function IconCopy() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v12h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z" /></svg>
}

function IconEye() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zm0 12.5a5 5 0 1 1 0-10 5 5 0 0 1 0 10zm0-8a3 3 0 1 0 0 6 3 3 0 0 0 0-6z" /></svg>
}

function IconEyeOff() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M2 4.27 3.28 3 21 20.72 19.73 22l-2.84-2.84A11.74 11.74 0 0 1 12 19.5c-5 0-9.27-3.11-11-7.5a11.82 11.82 0 0 1 4.24-5.01L2 4.27zM7.53 9.8A4.96 4.96 0 0 0 7 12a5 5 0 0 0 5 5c.77 0 1.5-.17 2.15-.47l-1.55-1.55A3 3 0 0 1 9.02 11.4zM12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.27-.36 1.84l-1.55-1.55c.05-.09.08-.19.08-.29a3 3 0 0 0-3-3c-.1 0-.2.03-.29.08L10.33 7.5c.54-.32 1.15-.5 1.67-.5zm0-2.5c5 0 9.27 3.11 11 7.5a12.6 12.6 0 0 1-3.23 4.36l-1.43-1.43A10.63 10.63 0 0 0 21 12c-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7L7.68 6.86A9.78 9.78 0 0 1 12 4.5z" /></svg>
}

function normalizeDomains(value: string) {
    return Array.from(
        new Set(
            value
                .split(/[\n,\s]+/)
                .map((item) => item.trim())
                .filter(Boolean),
        ),
    )
}

function getAccessHref(value: string) {
    if (/^https?:\/\//i.test(value)) {
        return value
    }

    if (/^\d{1,3}(\.\d{1,3}){3}(:\d+)?$/.test(value) || value.includes(':')) {
        return `http://${value}`
    }

    return `https://${value}`
}

function formatAccountLabel(key: string, locale: string, t: (key: string) => string) {
    const upperKey = key.toUpperCase()
    if (upperKey.includes('PASSWORD')) {
        return t('myAppsDetailPage.accessPanel.adminPassword')
    }
    if (upperKey.includes('USER')) {
        return t('myAppsDetailPage.accessPanel.adminUsername')
    }

    return key
        .replace(/^W9_/, '')
        .split('_')
        .filter(Boolean)
        .map((part) => {
            if (locale.startsWith('zh')) {
                return part
            }
            return `${part.charAt(0)}${part.slice(1).toLowerCase()}`
        })
        .join(locale.startsWith('zh') ? '' : ' ')
}

async function copyTextWithFallback(value: string) {
    if (navigator.clipboard?.writeText) {
        try {
            await navigator.clipboard.writeText(value)
            return
        } catch {
            // Fall through to the legacy path.
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

async function parseJsonError(response: Response, fallbackMessage: string) {
    try {
        const payload = (await response.json()) as { details?: string; message?: string }
        return payload.details || payload.message || fallbackMessage
    } catch {
        return fallbackMessage
    }
}

export function MyAppAccessPanel({ appId, entryDomains, env, isWebApp, onUpdated }: MyAppAccessPanelProps) {
    const { t, i18n } = useTranslation('shell')
    const navigate = useNavigate()
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const [domainInputValue, setDomainInputValue] = useState('')
    const [selectedCertificateId, setSelectedCertificateId] = useState('0')
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [isDeleting, setIsDeleting] = useState(false)
    const [feedback, setFeedback] = useState<AccessFeedback | null>(null)
    const [editingMode, setEditingMode] = useState<'none' | 'add' | 'edit'>('none')
    const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({})
    const { data, error, isLoading, refetch, isFetching } = useMyAppAccess(appId, isWebApp)
    const currentProxyHost = data?.proxyHosts[0]
    const currentCertificateId = currentProxyHost?.certificate_id ?? 0
    const appPort = env?.W9_HTTP_PORT_SET || env?.W9_HTTPS_PORT_SET || ''
    const isHttps = Boolean(env?.W9_HTTPS_PORT_SET)
    const hostName = typeof window !== 'undefined' ? window.location.hostname : ''

    const currentDomains = useMemo(() => {
        const proxyDomains = data?.proxyHosts.flatMap((host) => host.domain_names) ?? []
        const mergedDomains = proxyDomains.length > 0 ? proxyDomains : entryDomains

        return Array.from(new Set(mergedDomains.map((item) => item.trim()).filter(Boolean)))
    }, [data?.proxyHosts, entryDomains])

    const accountEntries = useMemo<AccountEntry[]>(() => {
        if (!env) return []

        return Object.keys(env)
            .filter((key) => key.startsWith('W9_LOGIN'))
            .sort((a, b) => {
                if (a.includes('PASSWORD') || b.includes('PASSWORD')) {
                    if (a.includes('PASSWORD') && b.includes('PASSWORD')) return 0
                    return a.includes('PASSWORD') ? 1 : -1
                }
                if (a.includes('USER') || b.includes('USER')) {
                    if (a.includes('USER') && b.includes('USER')) return 0
                    return a.includes('USER') ? 1 : -1
                }
                return a.localeCompare(b)
            })
            .map((key) => ({
                key,
                value: env[key] || '-',
                isPassword: key.includes('PASSWORD'),
            }))
    }, [env])

    const adminHref = currentDomains.length > 0 && env?.W9_URL && env?.W9_ADMIN_PATH
        ? `${isHttps ? 'https' : 'http'}://${env.W9_URL}${env.W9_ADMIN_PATH}`
        : null
    const frontendHref = appPort ? `${isHttps ? 'https' : 'http'}://${hostName}:${appPort}` : null
    const backendHref = frontendHref && env?.W9_ADMIN_PATH ? `${frontendHref}${env.W9_ADMIN_PATH}` : null

    useEffect(() => {
        if (editingMode === 'none') {
            setDomainInputValue(currentDomains.join('\n'))
        }
    }, [currentDomains, editingMode])

    useEffect(() => {
        const firstProxyHost = data?.proxyHosts[0]
        setSelectedCertificateId(String(firstProxyHost?.certificate_id ?? 0))
    }, [data?.proxyHosts])

    async function waitForProxyTask(taskId: string) {
        for (let attempt = 0; attempt < 40; attempt += 1) {
            const response = await fetch(`/api/proxys/tasks/${encodeURIComponent(taskId)}`, {
                credentials: 'include',
                headers: {
                    Accept: 'application/json',
                },
            })

            if (!response.ok) {
                throw new Error(await parseJsonError(response, `Failed to load proxy task: ${response.status}`))
            }

            const payload = (await response.json()) as {
                status: 'pending' | 'running' | 'completed' | 'failed'
                error?: string
            }

            if (payload.status === 'completed') {
                return
            }

            if (payload.status === 'failed') {
                throw new Error(payload.error || t('myAppsDetailPage.accessPanel.genericError'))
            }

            await new Promise((resolve) => {
                window.setTimeout(resolve, 1500)
            })
        }

        throw new Error(t('myAppsDetailPage.accessPanel.taskTimeout'))
    }

    async function handleSubmit() {
        const nextDomains = normalizeDomains(domainInputValue)
        if (nextDomains.length === 0) {
            setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.validation') })
            return
        }

        setIsSubmitting(true)
        setFeedback(null)

        try {
            const firstProxyHost = data?.proxyHosts[0]
            const response = await fetch(
                firstProxyHost
                    ? `/api/proxys/${firstProxyHost.proxy_id}?async_task=true`
                    : `/api/proxys/${encodeURIComponent(appId)}?async_task=true`,
                {
                    method: firstProxyHost ? 'PUT' : 'POST',
                    credentials: 'include',
                    headers: {
                        Accept: 'application/json',
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        domain_names: nextDomains,
                        certificate_id: selectedCertificateId === '0' ? null : Number(selectedCertificateId),
                    }),
                },
            )

            if (!response.ok) {
                throw new Error(await parseJsonError(response, `Failed to save access settings: ${response.status}`))
            }

            const taskPayload = (await response.json()) as { task_id?: string }
            if (!taskPayload.task_id) {
                throw new Error(t('myAppsDetailPage.accessPanel.genericError'))
            }

            setFeedback({ severity: 'success', message: t('myAppsDetailPage.accessPanel.taskAccepted') })
            await waitForProxyTask(taskPayload.task_id)

            await refetch()
            await onUpdated()
            setEditingMode('none')
            setFeedback({
                severity: 'success',
                message: t(firstProxyHost ? 'myAppsDetailPage.accessPanel.updateSuccess' : 'myAppsDetailPage.accessPanel.createSuccess'),
            })
        } catch (submitError) {
            setFeedback({
                severity: 'error',
                message: submitError instanceof Error ? submitError.message : t('myAppsDetailPage.accessPanel.genericError'),
            })
        } finally {
            setIsSubmitting(false)
        }
    }

    async function handleDelete() {
        if (!currentProxyHost) return

        setIsDeleting(true)
        setFeedback(null)
        try {
            const response = await fetch(`/api/proxys/${currentProxyHost.proxy_id}`, {
                method: 'DELETE',
                credentials: 'include',
                headers: {
                    Accept: 'application/json',
                },
            })

            if (!response.ok && response.status !== 204) {
                throw new Error(await parseJsonError(response, `Failed to delete access settings: ${response.status}`))
            }

            await refetch()
            await onUpdated()
            setEditingMode('none')
            setFeedback({ severity: 'success', message: t('myAppsDetailPage.accessPanel.deleteSuccess') })
        } catch (deleteError) {
            setFeedback({
                severity: 'error',
                message: deleteError instanceof Error ? deleteError.message : t('myAppsDetailPage.accessPanel.deleteFailed'),
            })
        } finally {
            setIsDeleting(false)
        }
    }

    function startAdd() {
        setDomainInputValue('')
        setSelectedCertificateId(String(currentCertificateId || 0))
        setEditingMode('add')
    }

    function startEdit() {
        setDomainInputValue(currentDomains.join('\n'))
        setSelectedCertificateId(String(currentCertificateId || 0))
        setEditingMode('edit')
    }

    function cancelEditing() {
        setDomainInputValue(currentDomains.join('\n'))
        setSelectedCertificateId(String(currentCertificateId || 0))
        setEditingMode('none')
    }

    if (!isWebApp) {
        return <Alert severity="info" variant="outlined">{t('myAppsDetailPage.accessPanel.notWebApp')}</Alert>
    }

    return (
        <div className="myapps-access-panel">
            {isLoading ? (
                <div className="myapps-access-loading">
                    <CircularProgress size={18} />
                    <span>{t('myAppsDetailPage.accessPanel.loading')}</span>
                </div>
            ) : null}

            {error ? (
                <Alert
                    action={
                        <Button color="inherit" onClick={() => void refetch()} size="small">
                            {t('myAppsDetailPage.states.retry')}
                        </Button>
                    }
                    severity="warning"
                    variant="outlined"
                >
                    {t('myAppsDetailPage.accessPanel.loadError', { statusCode: error.statusCode ?? 'unknown' })}
                </Alert>
            ) : null}

            {data?.proxyHosts.length && data.proxyHosts.length > 1 ? (
                <Alert severity="info" variant="outlined">
                    {t('myAppsDetailPage.accessPanel.multipleHosts')}
                </Alert>
            ) : null}

            <Accordion defaultExpanded className="myapps-access-accordion">
                <AccordionSummary expandIcon={<IconExpandMore />}>
                    <div className="myapps-access-summary-copy">
                        <label className="myapps-access-summary-title">{t('myAppsDetailPage.accessPanel.domainAccessTitle')}</label>
                        <span className="myapps-access-summary-desc">
                            {t('myAppsDetailPage.accessPanel.domainAccessDescription')}
                            {' '}
                            <button className="myapps-access-inline-link" onClick={(event) => {
                                event.preventDefault()
                                event.stopPropagation()
                                navigate(`/gateway?target=${encodeURIComponent('/w9proxy/nginx/proxy-hosts')}`)
                            }}>
                                {t('myAppsDetailPage.accessPanel.more')}
                            </button>
                        </span>
                    </div>
                </AccordionSummary>
                <AccordionDetails>
                    <div className="myapps-card myapps-access-card">
                        <div className="myapps-access-card-header">
                            <div />
                            <div className="myapps-card-header-actions">
                                {currentDomains.length === 0 && editingMode === 'none' ? (
                                    <button className="myapps-card-header-btn" onClick={startAdd}>{t('myAppsDetailPage.accessPanel.addDomain')}</button>
                                ) : null}
                                {adminHref ? (
                                    <button className="myapps-card-header-btn" onClick={() => window.location.assign(adminHref)}>{t('myAppsDetailPage.accessPanel.adminPage')}</button>
                                ) : null}
                            </div>
                        </div>
                        <div className="myapps-access-card-body">
                            {editingMode !== 'none' ? (
                                <div className="myapps-access-form">
                                    <TextField
                                        fullWidth
                                        label={t('myAppsDetailPage.accessPanel.certificateSelectLabel')}
                                        onChange={(event) => setSelectedCertificateId(event.target.value)}
                                        select
                                        value={selectedCertificateId}
                                    >
                                        <MenuItem value="0">{t('myAppsDetailPage.accessPanel.noCertificate')}</MenuItem>
                                        {(data?.certificates ?? []).map((certificate) => (
                                            <MenuItem key={certificate.id} value={String(certificate.id)}>
                                                {certificate.nice_name || certificate.domain_names?.join(', ') || `#${certificate.id}`}
                                            </MenuItem>
                                        ))}
                                    </TextField>

                                    {currentProxyHost?.certificate_name ? (
                                        <Alert severity="info" variant="outlined">
                                            {t('myAppsDetailPage.accessPanel.boundCertificate', {
                                                name: currentProxyHost.certificate_name,
                                            })}
                                        </Alert>
                                    ) : null}

                                    <TextField
                                        fullWidth
                                        helperText={t('myAppsDetailPage.accessPanel.helper')}
                                        label={t('myAppsDetailPage.accessPanel.inputLabel')}
                                        minRows={3}
                                        multiline
                                        onChange={(event) => setDomainInputValue(event.target.value)}
                                        value={domainInputValue}
                                    />

                                    <div className="myapps-access-form-actions">
                                        <button className="myapps-card-header-btn" disabled={isSubmitting} onClick={() => void handleSubmit()}>
                                            {isSubmitting ? t('myAppsDetailPage.actions.running') : t('myAppsDetailPage.accessPanel.save')}
                                        </button>
                                        <button className="myapps-card-header-btn myapps-card-header-btn-secondary" onClick={cancelEditing}>
                                            {t('myAppsDetailPage.accessPanel.cancel')}
                                        </button>
                                        {isFetching && !isLoading ? (
                                            <div className="myapps-access-refreshing">
                                                <CircularProgress size={16} />
                                                <span>{t('myAppsDetailPage.accessPanel.refreshing')}</span>
                                            </div>
                                        ) : null}
                                    </div>
                                </div>
                            ) : currentDomains.length > 0 ? (
                                <div className="myapps-access-domain-row">
                                    <a className="myapps-access-domain-field" href={getAccessHref(currentDomains[0])} target="_blank" rel="noreferrer">
                                        {currentDomains.join(', ')}
                                    </a>
                                    <IconButton onClick={startEdit} size="small" title={t('myAppsDetailPage.accessPanel.editDomain')}>
                                        <IconEdit />
                                    </IconButton>
                                    <IconButton disabled={isDeleting} onClick={() => void handleDelete()} size="small" title={t('myAppsDetailPage.accessPanel.deleteDomain')}>
                                        <IconDelete />
                                    </IconButton>
                                </div>
                            ) : (
                                <div className="myapps-access-domain-empty" />
                            )}
                        </div>
                    </div>
                </AccordionDetails>
            </Accordion>

            {currentDomains.length === 0 && appPort ? (
                <Accordion defaultExpanded className="myapps-access-accordion">
                    <AccordionSummary expandIcon={<IconExpandMore />}>
                        <div className="myapps-access-summary-copy">
                            <label className="myapps-access-summary-title">{t('myAppsDetailPage.accessPanel.noDomainAccessTitle')}</label>
                            <span className="myapps-access-summary-desc">{t('myAppsDetailPage.accessPanel.noDomainAccessDescription')}</span>
                        </div>
                    </AccordionSummary>
                    <AccordionDetails>
                        <div className="myapps-card myapps-access-card">
                            <div className="myapps-access-card-body">
                                {frontendHref ? (
                                    <div className="myapps-access-link-row">
                                        <span className="myapps-access-link-label">{t('myAppsDetailPage.accessPanel.frontend')}</span>
                                        <a href={frontendHref} target="_blank" rel="noreferrer">{frontendHref}</a>
                                    </div>
                                ) : null}
                                {backendHref ? (
                                    <div className="myapps-access-link-row">
                                        <span className="myapps-access-link-label">{t('myAppsDetailPage.accessPanel.backend')}</span>
                                        <a href={backendHref} target="_blank" rel="noreferrer">{backendHref}</a>
                                    </div>
                                ) : null}
                            </div>
                        </div>
                    </AccordionDetails>
                </Accordion>
            ) : null}

            {accountEntries.length > 0 ? (
                <Accordion defaultExpanded={!isWebApp} className="myapps-access-accordion">
                    <AccordionSummary expandIcon={<IconExpandMore />}>
                        <div className="myapps-access-summary-copy">
                            <label className="myapps-access-summary-title">{t('myAppsDetailPage.accessPanel.initialAccountTitle')}</label>
                            <span className="myapps-access-summary-desc">{t('myAppsDetailPage.accessPanel.initialAccountDescription')}</span>
                        </div>
                    </AccordionSummary>
                    <AccordionDetails>
                        <div className="myapps-card myapps-access-card">
                            <div className="myapps-access-card-body">
                                {accountEntries.map((entry) => (
                                    <div className="myapps-access-account-row" key={entry.key}>
                                        <label className="myapps-access-account-label">{formatAccountLabel(entry.key, locale, t)}</label>
                                        <div className="myapps-access-account-field-wrap">
                                            <input
                                                className="myapps-access-account-field"
                                                readOnly
                                                type={entry.isPassword && !showPasswords[entry.key] ? 'password' : 'text'}
                                                value={entry.value}
                                            />
                                            {entry.isPassword ? (
                                                <div className="myapps-access-account-actions">
                                                    <IconButton onClick={() => setShowPasswords((prev) => ({ ...prev, [entry.key]: !prev[entry.key] }))} size="small" title={showPasswords[entry.key] ? t('myAppsDetailPage.tabs.database.hidePassword') : t('myAppsDetailPage.tabs.database.showPassword')}>
                                                        {showPasswords[entry.key] ? <IconEyeOff /> : <IconEye />}
                                                    </IconButton>
                                                    <IconButton onClick={async () => {
                                                        try {
                                                            await copyTextWithFallback(entry.value)
                                                            setFeedback({ severity: 'success', message: t('myAppsDetailPage.accessPanel.copySuccess') })
                                                        } catch {
                                                            setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.copyFailed') })
                                                        }
                                                    }} size="small" title={t('myAppsDetailPage.tabs.database.copy')}>
                                                        <IconCopy />
                                                    </IconButton>
                                                </div>
                                            ) : null}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </AccordionDetails>
                </Accordion>
            ) : null}

            <Snackbar open={Boolean(feedback)} autoHideDuration={3000} onClose={() => setFeedback(null)} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
                <Alert onClose={() => setFeedback(null)} severity={feedback?.severity ?? 'success'} variant="filled" sx={{ width: '100%' }}>
                    {feedback?.message}
                </Alert>
            </Snackbar>
        </div>
    )
}