import { Alert, Button, CircularProgress, DialogActions, DialogContent, DialogContentText, DialogTitle, FormControlLabel, IconButton, Snackbar, Switch, TextField } from '@mui/material'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { SurfaceDialog } from '../../shared/design-system/standard-surfaces'
import { useMyAppAccess } from './use-my-app-access'

type ContentScopeRect = {
    top: number
    left: number
    width: number
    height: number
}

type MyAppAccessPanelProps = {
    appId: string
    env?: Record<string, string>
    isComposeApp: boolean
    onUpdated: () => Promise<void> | void
    scopeRect?: ContentScopeRect | null
    isDarkMode?: boolean
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

type CertDialogType = 'selfsigned' | 'letsencrypt' | 'custom'

function IconDelete() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M6 7h12l-1 14H7L6 7zm3-3h6l1 2h4v2H4V6h4l1-2z" /></svg>
}

function IconEye() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 5c-5 0-9.27 3.11-11 7 1.73 3.89 6 7 11 7s9.27-3.11 11-7c-1.73-3.89-6-7-11-7zm0 12a5 5 0 1 1 0-10 5 5 0 0 1 0 10zm0-2.2A2.8 2.8 0 1 0 12 9.2a2.8 2.8 0 0 0 0 5.6z" /></svg>
}

function IconEyeOff() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="m3.28 2 18.72 18.72-1.41 1.41-3.02-3.02A12.72 12.72 0 0 1 12 20c-5 0-9.27-3.11-11-7a12.67 12.67 0 0 1 4.32-5.04L1.86 3.41 3.28 2zm6.1 6.1 1.53 1.53A2.96 2.96 0 0 0 9 12c0 1.66 1.34 3 3 3 .52 0 1.01-.13 1.44-.37l1.53 1.53A4.93 4.93 0 0 1 12 17a5 5 0 0 1-5-5c0-1.13.37-2.18 1-3.1zm2.98-2.04A5 5 0 0 1 17 11c0 .72-.15 1.4-.42 2.02l3.1 3.1A12.82 12.82 0 0 0 23 13c-1.73-3.89-6-7-11-7-1.58 0-3.1.31-4.48.88l2.31 2.31A4.98 4.98 0 0 1 12 7c.12 0 .24 0 .36.01z" /></svg>
}

function IconCopy() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M16 1H4a2 2 0 0 0-2 2v12h2V3h12V1zm4 4H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H8V7h12v14z" /></svg>
}

function IconPlus() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" /></svg>
}

function IconExternalLink() {
    return <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M19 19H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z" /></svg>
}

function IconGlobe() {
    return <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" style={{ color: 'var(--myapps-detail-muted)', flexShrink: 0 }}><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z" /></svg>
}

function IconAdmin() {
    return <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M12 1 3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z" /></svg>
}

function IconWarning() {
    return <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" style={{ flexShrink: 0, marginTop: 1 }}><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" /></svg>
}

function IconCertLE() {
    return <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M12 1 3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z" /></svg>
}

function IconCertLock() {
    return <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z" /></svg>
}

function IconEdit() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" /></svg>
}

function normalizeDomains(value: string) {
    return Array.from(new Set(value.split(/[\s,]+/).map((item) => item.trim()).filter(Boolean)))
}

function isDomainBindingValue(value: string) {
    const trimmed = value.trim()
    if (!trimmed) return false
    if (trimmed.includes('://') || trimmed.includes('/') || trimmed.includes(' ')) return false
    const withoutPort = trimmed.replace(/:\d+$/, '')
    if (/^\d{1,3}(?:\.\d{1,3}){3}$/.test(withoutPort)) return false
    if (withoutPort.includes(':')) return false
    return true
}

function formatCertificateLabel(certificate: { nice_name?: string | null; domain_names?: string[]; provider?: string | null } | null | undefined) {
    if (!certificate) return ''
    if (certificate.nice_name?.trim()) return certificate.nice_name.trim()
    if (certificate.domain_names?.length) return certificate.domain_names.join(', ')
    if (certificate.provider?.trim()) return certificate.provider.trim()
    return ''
}

function formatAccountLabel(key: string, locale: string, t: (key: string) => string) {
    if (locale.startsWith('zh')) {
        if (key.toLowerCase().includes('user')) return '用户名'
        if (key.toLowerCase().includes('pass')) return '密码'
    }
    if (key.toLowerCase().includes('user')) return t('myAppsDetailPage.accessPanel.username')
    if (key.toLowerCase().includes('pass')) return t('myAppsDetailPage.accessPanel.password')
    return key
}

async function copyTextWithFallback(value: string) {
    if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value)
        return
    }
    const input = document.createElement('textarea')
    input.value = value
    input.style.position = 'fixed'
    input.style.opacity = '0'
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    document.body.removeChild(input)
}

async function parseJsonError(response: Response, fallbackMessage: string) {
    try {
        const payload = await response.json() as { detail?: string; message?: string }
        return payload.detail || payload.message || fallbackMessage
    } catch {
        return fallbackMessage
    }
}

function getCandidateKey(forwardHost?: string | null, forwardPort?: number | null) {
    if (!forwardHost || !forwardPort) return ''
    return `${forwardHost}:${forwardPort}`
}

function getPublishedPort(candidatePorts: string[], targetPort: number | undefined | null) {
    if (!targetPort) return ''
    for (const pair of candidatePorts) {
        const [publicPort, privatePort] = pair.split(':')
        if (Number(privatePort) === targetPort) {
            return publicPort || ''
        }
    }
    return ''
}

export function MyAppAccessPanel({ appId, env, isComposeApp, onUpdated, scopeRect, isDarkMode = false }: MyAppAccessPanelProps) {
    const { t, i18n } = useTranslation('shell')
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const [selectedProxyId, setSelectedProxyId] = useState<number | null>(null)
    const [selectedCandidateKey, setSelectedCandidateKey] = useState('')
    const [selectedContainerName, setSelectedContainerName] = useState('')
    const [selectedTargetPort, setSelectedTargetPort] = useState('')
    const [selectedScheme, setSelectedScheme] = useState<'http' | 'https'>('http')
    const [certificateEmail, setCertificateEmail] = useState('')
    const [customCertName, setCustomCertName] = useState('')
    const [customCertPem, setCustomCertPem] = useState('')
    const [customCertKeyPem, setCustomCertKeyPem] = useState('')
    const [isBindDialogOpen, setIsBindDialogOpen] = useState(false)
    const [bindDialogProxyId, setBindDialogProxyId] = useState<number | null>(null)
    const [bindDialogDomain, setBindDialogDomain] = useState('')
    const [bindDialogCertType, setBindDialogCertType] = useState<CertDialogType>('selfsigned')
    const [bindDialogForceHttps, setBindDialogForceHttps] = useState(false)
    const [isBindDialogSubmitting, setIsBindDialogSubmitting] = useState(false)
    const [isDeleting, setIsDeleting] = useState(false)
    const [feedback, setFeedback] = useState<AccessFeedback | null>(null)
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
    const [visibleCredKeys, setVisibleCredKeys] = useState<Set<string>>(new Set())
    const { data, error, isLoading, refetch } = useMyAppAccess(appId)
    const proxyHosts = data?.proxy_hosts ?? []
    const currentProxyHost = proxyHosts.find((host) => host.proxy_id === selectedProxyId) ?? proxyHosts[0] ?? null
    const currentProfile = data?.profile
    const hostName = typeof window !== 'undefined' ? window.location.hostname : ''

    const currentDomains = useMemo(() => {
        const domains = currentProxyHost?.domain_names ?? []
        return Array.from(new Set(domains.map((item) => item.trim()).filter(isDomainBindingValue)))
    }, [currentProxyHost])

    const accountEntries = useMemo<AccountEntry[]>(() => {
        if (!env) return []
        return Object.entries(env)
            .filter(([key, value]) => key.startsWith('W9_LOGIN') && value?.trim())
            .map(([key, value]) => ({
                key,
                value,
                isPassword: key.toLowerCase().includes('password') || key.toLowerCase().includes('pass'),
            }))
            .sort((left, right) => {
                const rank = (entry: AccountEntry) => {
                    if (entry.key.toLowerCase().includes('user')) return 0
                    if (entry.key.toLowerCase().includes('pass')) return 1
                    return 2
                }
                return rank(left) - rank(right)
            })
    }, [env])

    const profileCandidate = useMemo(
        () => data?.candidates.find((candidate) => getCandidateKey(candidate.forward_host, candidate.forward_port) === getCandidateKey(currentProfile?.forward_host, currentProfile?.forward_port)) ?? null,
        [currentProfile?.forward_host, currentProfile?.forward_port, data?.candidates],
    )
    const resolvedPublicPort = profileCandidate ? getPublishedPort(profileCandidate.published_ports, currentProfile?.forward_port) : ''
    const directPort = env?.W9_HTTP_PORT_SET || env?.W9_HTTPS_PORT_SET || resolvedPublicPort
    const frontendHref = directPort ? `${currentProfile?.forward_scheme === 'https' ? 'https' : 'http'}://${hostName}:${directPort}` : null
    const backendHref = frontendHref && env?.W9_ADMIN_PATH ? `${frontendHref}${env.W9_ADMIN_PATH}` : null
    const showTargetSection = isComposeApp || !currentProfile?.locked
    const showDomainAccessSection = isComposeApp || Boolean(env?.W9_URL?.trim()) || proxyHosts.length > 0 || Boolean(frontendHref || backendHref)
    const currentCertificate = useMemo(
        () => data?.certificates.find((certificate) => certificate.id === currentProxyHost?.certificate_id) ?? null,
        [currentProxyHost?.certificate_id, data?.certificates],
    )
    const currentCertificateLabel = currentProxyHost?.certificate_name || formatCertificateLabel(currentCertificate)
    const availableCertificates = useMemo(() => {
        const certificates = [...(data?.certificates ?? [])]
        if (currentProxyHost?.certificate_id && !certificates.some((certificate) => certificate.id === currentProxyHost.certificate_id)) {
            certificates.unshift({
                id: currentProxyHost.certificate_id,
                nice_name: currentCertificateLabel || `#${currentProxyHost.certificate_id}`,
                domain_names: currentDomains,
                provider: 'letsencrypt',
            })
        }
        return certificates
    }, [currentCertificateLabel, currentDomains, currentProxyHost?.certificate_id, data?.certificates])
    const defaultSelfSignedCert = useMemo(
        () => availableCertificates.find((cert) => cert.provider !== 'letsencrypt') ?? null,
        [availableCertificates],
    )

    useEffect(() => {
        if (proxyHosts.length === 0) {
            if (selectedProxyId !== null) setSelectedProxyId(null)
            return
        }
        if (selectedProxyId === null || !proxyHosts.some((host) => host.proxy_id === selectedProxyId)) {
            setSelectedProxyId(proxyHosts[0].proxy_id)
        }
    }, [proxyHosts, selectedProxyId])

    useEffect(() => {
        if (!currentProfile) return
        setSelectedScheme(currentProfile.forward_scheme)
        setSelectedContainerName(currentProfile.forward_host ?? '')
        setSelectedTargetPort(currentProfile.forward_port ? String(currentProfile.forward_port) : '')
        setSelectedCandidateKey(getCandidateKey(currentProfile.forward_host, currentProfile.forward_port))
    }, [currentProfile])

    useEffect(() => {
        if (selectedContainerName || (data?.candidates?.length ?? 0) === 0) return
        const firstCandidate = data?.candidates?.[0]
        if (!firstCandidate) return
        setSelectedContainerName(firstCandidate.container_name)
        setSelectedTargetPort(String(firstCandidate.forward_port))
        setSelectedCandidateKey(getCandidateKey(firstCandidate.forward_host, firstCandidate.forward_port))
    }, [data?.candidates, selectedContainerName])

    useEffect(() => {
        if (!selectedContainerName) {
            setSelectedCandidateKey('')
            return
        }

        const matchingCandidates = (data?.candidates ?? []).filter((candidate) => candidate.container_name === selectedContainerName)
        if (matchingCandidates.length === 0) {
            setSelectedCandidateKey('')
            return
        }

        const matchingPort = selectedTargetPort ? matchingCandidates.find((candidate) => String(candidate.forward_port) === selectedTargetPort) : null
        const resolvedCandidate = matchingPort ?? matchingCandidates[0]
        setSelectedTargetPort(String(resolvedCandidate.forward_port))
        setSelectedCandidateKey(getCandidateKey(resolvedCandidate.forward_host, resolvedCandidate.forward_port))
    }, [data?.candidates, selectedContainerName, selectedTargetPort])

    async function persistProfileSelection() {
        if (!showTargetSection) return
        if (!selectedCandidateKey) {
            throw new Error(t('myAppsDetailPage.accessPanel.composeDefinitionRequired'))
        }

        const [forwardHost, forwardPort] = selectedCandidateKey.split(':')
        const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/access/profile`, {
            method: 'PUT',
            credentials: 'include',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                enabled: true,
                forward_host: forwardHost || null,
                forward_port: Number(forwardPort || 0) || null,
                forward_scheme: selectedScheme,
            }),
        })

        if (!response.ok) {
            throw new Error(await parseJsonError(response, `Failed to save access target: ${response.status}`))
        }
    }

    async function ensureDomainBinding(nextDomains: string[], certificateId: number | null, sslForced: boolean, overrideProxyId?: number | null) {
        const effectiveProxyId = overrideProxyId !== undefined ? overrideProxyId : (currentProxyHost?.proxy_id ?? null)
        const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/access/domains`, {
            method: 'PUT',
            credentials: 'include',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                domain_names: nextDomains,
                certificate_id: certificateId,
                ssl_forced: sslForced,
                proxy_id: effectiveProxyId,
            }),
        })

        if (!response.ok) {
            throw new Error(await parseJsonError(response, `Failed to save access settings: ${response.status}`))
        }

        return response.json() as Promise<{ proxy_id?: number }>
    }

    async function handleDelete() {
        if (!currentProxyHost) return

        setIsDeleting(true)
        setFeedback(null)
        try {
            const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/access/domains/${currentProxyHost.proxy_id}`, {
                method: 'DELETE',
                credentials: 'include',
                headers: {
                    Accept: 'application/json',
                },
            })

            if (!response.ok) {
                throw new Error(await parseJsonError(response, `Failed to delete access settings: ${response.status}`))
            }

            await refetch()
            await onUpdated()
            setShowDeleteConfirm(false)
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

    function openBindDialog(proxyId: number | null) {
        if (proxyId !== null) {
            const host = proxyHosts.find((h) => h.proxy_id === proxyId)
            if (host) {
                const domains = host.domain_names.filter(isDomainBindingValue)
                setBindDialogDomain(domains.join(', '))
                setBindDialogForceHttps(Boolean(host.ssl_forced && host.certificate_id))
                const cert = data?.certificates.find((c) => c.id === host.certificate_id)
                setBindDialogCertType(cert?.provider === 'letsencrypt' ? 'letsencrypt' : 'selfsigned')
            }
            setBindDialogProxyId(proxyId)
        } else {
            setBindDialogDomain('')
            setBindDialogForceHttps(false)
            setBindDialogCertType('selfsigned')
            setBindDialogProxyId(null)
        }
        setCertificateEmail('')
        setCustomCertName('')
        setCustomCertPem('')
        setCustomCertKeyPem('')
        setIsBindDialogOpen(true)
    }

    function handleCloseBindDialog() {
        if (isBindDialogSubmitting) return
        setIsBindDialogOpen(false)
        setBindDialogDomain('')
        setBindDialogCertType('selfsigned')
        setBindDialogForceHttps(false)
        setCertificateEmail('')
        setCustomCertName('')
        setCustomCertPem('')
        setCustomCertKeyPem('')
    }

    async function handleBindDialogSubmit() {
        const domains = normalizeDomains(bindDialogDomain).filter(isDomainBindingValue)
        if (domains.length === 0) {
            setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.validation') })
            return
        }

        setIsBindDialogSubmitting(true)
        setFeedback(null)
        try {
            await persistProfileSelection()

            if (bindDialogCertType === 'letsencrypt') {
                if (!certificateEmail.trim()) {
                    setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.emailValidation') })
                    return
                }
                const binding = await ensureDomainBinding(domains, null, false, bindDialogProxyId)
                const proxyId = binding.proxy_id ?? bindDialogProxyId
                const certResp = await fetch(`/api/apps/${encodeURIComponent(appId)}/access/certificates/letsencrypt`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: certificateEmail.trim(), domain_names: domains, proxy_id: proxyId }),
                })
                if (!certResp.ok) throw new Error(await parseJsonError(certResp, 'Failed to request certificate'))
                const cert = await certResp.json() as { id?: number }
                if (cert.id) {
                    await ensureDomainBinding(domains, cert.id, bindDialogForceHttps, proxyId ?? bindDialogProxyId)
                }
            } else if (bindDialogCertType === 'custom') {
                if (!customCertName.trim() || !customCertPem.trim() || !customCertKeyPem.trim()) {
                    setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.customCertValidation') })
                    return
                }
                const binding = await ensureDomainBinding(domains, null, false, bindDialogProxyId)
                const proxyId = binding.proxy_id ?? bindDialogProxyId
                const certResp = await fetch(`/api/apps/${encodeURIComponent(appId)}/access/certificates/custom`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        nice_name: customCertName.trim(),
                        certificate_pem: customCertPem.trim(),
                        key_pem: customCertKeyPem.trim(),
                        proxy_id: proxyId,
                        domain_names: domains,
                    }),
                })
                if (!certResp.ok) throw new Error(await parseJsonError(certResp, 'Failed to upload certificate'))
                const cert = await certResp.json() as { id?: number }
                if (cert.id) {
                    await ensureDomainBinding(domains, cert.id, bindDialogForceHttps, proxyId ?? bindDialogProxyId)
                }
            } else {
                // selfsigned
                const selfCertId = defaultSelfSignedCert?.id ?? null
                await ensureDomainBinding(domains, selfCertId, selfCertId !== null && bindDialogForceHttps, bindDialogProxyId)
            }

            await refetch()
            await onUpdated()
            handleCloseBindDialog()
            setFeedback({ severity: 'success', message: t(bindDialogProxyId !== null ? 'myAppsDetailPage.accessPanel.updateSuccess' : 'myAppsDetailPage.accessPanel.createSuccess') })
        } catch (err) {
            setFeedback({ severity: 'error', message: err instanceof Error ? err.message : t('myAppsDetailPage.accessPanel.genericError') })
        } finally {
            setIsBindDialogSubmitting(false)
        }
    }

    return (
        <div className="myapps-access-panel">
            {isLoading ? (
                <div className="myapps-access-loading-overlay">
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

            {/* ── Access section ── */}
            {showDomainAccessSection ? (
                <div className="myapps-access-section">
                    <div className="myapps-access-section-head">
                        <div className="myapps-section-label-bar">
                            <span className="myapps-section-label-indicator" />
                            <span className="myapps-section-label-text">
                                {proxyHosts.length > 0
                                    ? t('myAppsDetailPage.accessPanel.domainListTitle')
                                    : t('myAppsDetailPage.accessPanel.defaultAccessTitle')}
                            </span>
                        </div>
                        {proxyHosts.length === 0 && frontendHref ? (
                            <button className="myapps-bind-domain-btn" onClick={() => openBindDialog(null)} type="button">
                                <IconPlus />
                                {t('myAppsDetailPage.accessPanel.bindDomain')}
                            </button>
                        ) : proxyHosts.length > 0 ? (
                            <button className="myapps-bind-domain-btn" onClick={() => openBindDialog(null)} type="button">
                                <IconPlus />
                                {t('myAppsDetailPage.accessPanel.bindDomain')}
                            </button>
                        ) : null}
                    </div>

                    {proxyHosts.length === 0 ? (
                        /* No-domain: default access row */
                        <div className="myapps-default-access-no-domain">
                            <div className="myapps-default-access-row">
                                {frontendHref ? (
                                    <div className="myapps-default-access-url-group">
                                        <IconGlobe />
                                        <span className="myapps-default-access-url">{frontendHref.replace(/^https?:\/\//, '')}</span>
                                        <button className="myapps-default-access-copy" onClick={() => void copyTextWithFallback(frontendHref)} title={t('myAppsDetailPage.accessPanel.copySuccess')} type="button">
                                            <IconCopy />
                                        </button>
                                    </div>
                                ) : null}
                                <div className="myapps-default-access-actions">
                                    {frontendHref ? (
                                        <a className="myapps-default-access-action-btn" href={frontendHref} rel="noreferrer" target="_blank">
                                            <IconExternalLink />
                                            {t('myAppsDetailPage.accessPanel.openAppHome')}
                                        </a>
                                    ) : null}
                                    {backendHref ? (
                                        <a className="myapps-default-access-action-btn is-admin" href={backendHref} rel="noreferrer" target="_blank">
                                            <IconExternalLink />
                                            {t('myAppsDetailPage.accessPanel.openAdminConsole')}
                                        </a>
                                    ) : null}
                                </div>
                            </div>
                            {/^\d{1,3}(\.\d{1,3}){3}$/.test(hostName) ? (
                                <p className="myapps-ip-access-tip">
                                    <IconWarning />
                                    {t('myAppsDetailPage.accessPanel.ipAccessWarning')}
                                </p>
                            ) : null}
                        </div>
                    ) : (
                        /* Has domains: routing table */
                        <table className="myapps-route-table">
                            <thead>
                                <tr>
                                    <th>{t('myAppsDetailPage.accessPanel.colExternalDomain')}</th>
                                    <th>{t('myAppsDetailPage.accessPanel.colCertType')}</th>
                                    <th>{t('myAppsDetailPage.accessPanel.colEndpoints')}</th>
                                    <th>{t('myAppsDetailPage.accessPanel.colActions')}</th>
                                </tr>
                            </thead>
                            <tbody>
                                {proxyHosts.map((host) => {
                                    const hostDomains = host.domain_names.filter(isDomainBindingValue)
                                    const cert = data?.certificates.find((c) => c.id === host.certificate_id)
                                    const certIsLE = cert?.provider === 'letsencrypt'
                                    const hostScheme = host.certificate_id ? 'https' : (currentProfile?.forward_scheme ?? 'http')
                                    const domain = hostDomains[0] ?? null
                                    const frontUrl = domain ? `${hostScheme}://${domain}` : null
                                    const backUrl = frontUrl && env?.W9_ADMIN_PATH ? `${frontUrl}${env.W9_ADMIN_PATH}` : null
                                    return (
                                        <tr key={host.proxy_id}>
                                            <td className="myapps-route-col-domain">
                                                {domain ?? <span className="myapps-route-empty">—</span>}
                                            </td>
                                            <td className="myapps-route-col-cert">
                                                {host.certificate_id ? (
                                                    certIsLE ? (
                                                        <span className="myapps-cert-type-chip is-le">
                                                            <IconCertLE />
                                                            {t('myAppsDetailPage.accessPanel.certTypeLE')}
                                                        </span>
                                                    ) : (
                                                        <span className="myapps-cert-type-chip is-custom">
                                                            <IconCertLock />
                                                            {t('myAppsDetailPage.accessPanel.certTypeCustom')}
                                                        </span>
                                                    )
                                                ) : (
                                                    <span className="myapps-cert-type-chip is-http">
                                                        {t('myAppsDetailPage.accessPanel.certTypeHttpOnly')}
                                                    </span>
                                                )}
                                            </td>
                                            <td className="myapps-route-col-endpoints">
                                                {frontUrl ? (
                                                    <a className="myapps-route-endpoint-link" href={frontUrl} rel="noreferrer" target="_blank">
                                                        <IconExternalLink />
                                                        {t('myAppsDetailPage.accessPanel.appAccess')}
                                                    </a>
                                                ) : null}
                                                {backUrl ? (
                                                    <a className="myapps-route-endpoint-link is-admin" href={backUrl} rel="noreferrer" target="_blank">
                                                        <IconAdmin />
                                                        {t('myAppsDetailPage.accessPanel.adminAccess')}
                                                    </a>
                                                ) : null}
                                            </td>
                                            <td className="myapps-route-col-actions">
                                                <IconButton onClick={() => openBindDialog(host.proxy_id)} size="small" title={t('myAppsDetailPage.accessPanel.edit')}>
                                                    <IconEdit />
                                                </IconButton>
                                                <IconButton onClick={() => { setSelectedProxyId(host.proxy_id); setShowDeleteConfirm(true) }} size="small">
                                                    <IconDelete />
                                                </IconButton>
                                            </td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    )}
                </div>
            ) : null}

            {/* ── Initial credentials ── */}
            {accountEntries.length > 0 ? (
                <div className="myapps-creds-section">
                    <div className="myapps-creds-section-head">
                        <div className="myapps-section-label-bar">
                            <span className="myapps-section-label-indicator" />
                            <span className="myapps-section-label-text">{t('myAppsDetailPage.accessPanel.credentialsTitle')}</span>
                        </div>
                    </div>
                    <div className="myapps-creds-rows">
                        {accountEntries.map((entry) => (
                            <div className="myapps-creds-row" key={entry.key}>
                                <label className="myapps-creds-label">{formatAccountLabel(entry.key, locale, t)}</label>
                                <span className="myapps-creds-value">
                                    <span className="myapps-creds-value-text">
                                        {entry.isPassword && !visibleCredKeys.has(entry.key)
                                            ? <span className="myapps-creds-dots">{'•'.repeat(10)}</span>
                                            : entry.value}
                                    </span>
                                    <span className="myapps-creds-actions">
                                        {entry.isPassword ? (
                                            <button className="myapps-creds-eye-btn" onClick={() => {
                                                setVisibleCredKeys((prev) => {
                                                    const next = new Set(prev)
                                                    if (next.has(entry.key)) next.delete(entry.key)
                                                    else next.add(entry.key)
                                                    return next
                                                })
                                            }} title={visibleCredKeys.has(entry.key) ? t('myAppsDetailPage.accessPanel.hidePlainText') : t('myAppsDetailPage.accessPanel.showPlainText')} type="button">
                                                {visibleCredKeys.has(entry.key) ? <IconEyeOff /> : <IconEye />}
                                            </button>
                                        ) : null}
                                        <button className="myapps-creds-copy-btn" onClick={async () => {
                                            try {
                                                await copyTextWithFallback(entry.value)
                                                setFeedback({ severity: 'success', message: t('myAppsDetailPage.accessPanel.copySuccess') })
                                            } catch {
                                                setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.copyFailed') })
                                            }
                                        }} title={t('myAppsDetailPage.accessPanel.copySuccess')} type="button">
                                            <IconCopy />
                                        </button>
                                    </span>
                                </span>
                            </div>
                        ))}
                    </div>
                    <p className="myapps-creds-note">
                        <IconWarning />
                        {t('myAppsDetailPage.accessPanel.credNote')}
                    </p>
                </div>
            ) : null}

            <SurfaceDialog fullWidth maxWidth="sm" onClose={handleCloseBindDialog} open={isBindDialogOpen} scope="content" scopeRect={scopeRect ?? null} contentStrategy="viewport-fixed" darkMode={isDarkMode} sx={{ zIndex: 1510 }}>
                <DialogTitle sx={{ pb: 1 }}>
                    {bindDialogProxyId !== null ? t('myAppsDetailPage.accessPanel.editBindTitle') : t('myAppsDetailPage.accessPanel.bindNewTitle')}
                </DialogTitle>
                <DialogContent>
                    <div className="myapps-bind-dialog-form">
                        <TextField
                            className="myapps-access-form-control"
                            fullWidth
                            helperText={t('myAppsDetailPage.accessPanel.domainInputHelper')}
                            label={t('myAppsDetailPage.accessPanel.domainInputLabel')}
                            onChange={(e) => setBindDialogDomain(e.target.value)}
                            placeholder="wp.domain.com"
                            size="small"
                            value={bindDialogDomain}
                        />
                        <div className="myapps-bind-cert-section">
                            <span className="myapps-bind-cert-label">{t('myAppsDetailPage.accessPanel.sslCertScheme')}</span>
                            <div className="myapps-cert-type-tabs">
                                {(['selfsigned', 'letsencrypt', 'custom'] as CertDialogType[]).map((type) => (
                                    <button
                                        className={`myapps-cert-type-tab ${bindDialogCertType === type ? 'is-active' : ''}`}
                                        key={type}
                                        onClick={() => setBindDialogCertType(type)}
                                        type="button"
                                    >
                                        {type === 'selfsigned'
                                            ? t('myAppsDetailPage.accessPanel.certTabSelfSigned')
                                            : type === 'letsencrypt'
                                                ? t('myAppsDetailPage.accessPanel.certTabLetsEncrypt')
                                                : t('myAppsDetailPage.accessPanel.certTabCustom')}
                                    </button>
                                ))}
                            </div>
                            {bindDialogCertType === 'selfsigned' ? (
                                <Alert severity="warning" sx={{ mt: 0.5 }}>{t('myAppsDetailPage.accessPanel.selfSignedWarning')}</Alert>
                            ) : bindDialogCertType === 'letsencrypt' ? (
                                <TextField
                                    className="myapps-access-form-control"
                                    fullWidth
                                    label={t('myAppsDetailPage.accessPanel.certificateEmailLabel')}
                                    onChange={(e) => setCertificateEmail(e.target.value)}
                                    placeholder="admin@example.com"
                                    size="small"
                                    value={certificateEmail}
                                />
                            ) : (
                                <div className="myapps-bind-custom-cert-fields">
                                    <TextField
                                        className="myapps-access-form-control"
                                        fullWidth
                                        label={t('myAppsDetailPage.accessPanel.customCertName')}
                                        onChange={(e) => setCustomCertName(e.target.value)}
                                        placeholder="my-site.com"
                                        size="small"
                                        value={customCertName}
                                    />
                                    <TextField
                                        className="myapps-access-form-control"
                                        fullWidth
                                        label={t('myAppsDetailPage.accessPanel.customCertPem')}
                                        multiline
                                        onChange={(e) => setCustomCertPem(e.target.value)}
                                        placeholder="-----BEGIN CERTIFICATE-----"
                                        rows={3}
                                        size="small"
                                        value={customCertPem}
                                    />
                                    <TextField
                                        className="myapps-access-form-control"
                                        fullWidth
                                        label={t('myAppsDetailPage.accessPanel.customCertKey')}
                                        multiline
                                        onChange={(e) => setCustomCertKeyPem(e.target.value)}
                                        placeholder="-----BEGIN PRIVATE KEY-----"
                                        rows={3}
                                        size="small"
                                        value={customCertKeyPem}
                                    />
                                </div>
                            )}
                        </div>
                        <div className="myapps-bind-https-toggle">
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={bindDialogForceHttps}
                                        disabled={bindDialogCertType === 'selfsigned' && !defaultSelfSignedCert}
                                        onChange={(e) => setBindDialogForceHttps(e.target.checked)}
                                        size="small"
                                    />
                                }
                                label={
                                    <div className="myapps-bind-https-label">
                                        <span className="myapps-bind-https-label-title">{t('myAppsDetailPage.accessPanel.forceHttpsLabel')}</span>
                                        <span className="myapps-bind-https-label-desc">{t('myAppsDetailPage.accessPanel.forceHttpsHelper')}</span>
                                    </div>
                                }
                            />
                        </div>
                    </div>
                </DialogContent>
                <DialogActions>
                    <Button disabled={isBindDialogSubmitting} onClick={handleCloseBindDialog}>
                        {t('myAppsDetailPage.accessPanel.cancel')}
                    </Button>
                    <Button
                        disabled={isBindDialogSubmitting || !bindDialogDomain.trim()}
                        onClick={() => void handleBindDialogSubmit()}
                        variant="contained"
                    >
                        {isBindDialogSubmitting ? <CircularProgress color="inherit" size={16} /> : t('myAppsDetailPage.accessPanel.saveConfig')}
                    </Button>
                </DialogActions>
            </SurfaceDialog>

            <SurfaceDialog onClose={() => {
                if (!isDeleting) setShowDeleteConfirm(false)
            }} open={showDeleteConfirm} scope="content" scopeRect={scopeRect ?? null} contentStrategy="viewport-fixed" darkMode={isDarkMode} sx={{ zIndex: 1510 }}>
                <DialogTitle>{t('myAppsDetailPage.accessPanel.deleteConfirmTitle')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {t('myAppsDetailPage.accessPanel.deleteConfirmDescription', {
                            domains: currentDomains.join(', ') || '-',
                        })}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button disabled={isDeleting} onClick={() => setShowDeleteConfirm(false)}>{t('myAppsDetailPage.accessPanel.cancel')}</Button>
                    <Button color="error" disabled={isDeleting} onClick={() => void handleDelete()} variant="contained">
                        {isDeleting ? <CircularProgress color="inherit" size={16} /> : t('myAppsDetailPage.accessPanel.deleteDomain')}
                    </Button>
                </DialogActions>
            </SurfaceDialog>

            <Snackbar
                anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
                autoHideDuration={3000}
                onClose={() => setFeedback(null)}
                open={Boolean(feedback)}
            >
                <Alert onClose={() => setFeedback(null)} severity={feedback?.severity ?? 'success'} variant="filled" sx={{ width: '100%' }}>
                    {feedback?.message}
                </Alert>
            </Snackbar>
        </div>
    )
}
