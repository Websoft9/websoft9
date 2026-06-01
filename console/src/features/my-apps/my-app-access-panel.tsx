import { Alert, Box, Button, CircularProgress, IconButton, Snackbar, Switch, Typography } from '@mui/material'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { SurfaceDialog } from '../../shared/design-system/standard-surfaces'
import { getSurfacePalette } from '../../shared/design-system/surface-theme'
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

type NonWebConnectionEntry = {
    key: string
    title: string
    host: string
    port: string
    address: string
}

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

function IconOpenLink() {
    return <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M14 3h7v7h-2V6.41l-9.29 9.3-1.42-1.42 9.3-9.29H14V3z" /><path d="M5 5h6v2H7v10h10v-4h2v6H5V5z" /></svg>
}

function IconCertExisting() {
    return <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M19 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2zm0 16H5V5h14v14z" /><path d="M7 7h10v2H7zm0 4h10v2H7zm0 4h6v2H7z" /></svg>
}
function IconUploadFile() {
    return <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M5 20h14v-2H5v2zm7-18-5.5 5.5 1.41 1.41L11 6.83V16h2V6.83l3.09 3.08 1.41-1.41L12 2z" /></svg>
}

function IconSslShield() {
    return <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M12 2 4 5v6c0 5.25 3.4 10.16 8 11.78 4.6-1.62 8-6.53 8-11.78V5l-8-3zm-1.1 12.2-2.8-2.8 1.4-1.4 1.4 1.39 3.6-3.59 1.4 1.41-5 4.99z" /></svg>
}

function IconEdit() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" /></svg>
}

function isDomainBindingValue(value: string) {
    const trimmed = value.trim().toLowerCase()
    if (!trimmed) return false
    if (trimmed.includes('://') || trimmed.includes('/') || trimmed.includes(' ')) return false
    if (trimmed.length > 253 || trimmed.endsWith('.')) return false
    if (/^\d{1,3}(?:\.\d{1,3}){3}$/.test(trimmed)) return false
    if (trimmed.includes(':')) return false
    const labels = trimmed.split('.')
    if (labels.length < 2) return false
    if (labels.some((label) => !label || label.length > 63 || label.startsWith('-') || label.endsWith('-') || !/^[a-z0-9-]+$/i.test(label))) {
        return false
    }
    const topLevelLabel = labels[labels.length - 1]
    if (!/^(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})$/i.test(topLevelLabel)) return false
    return true
}

function normalizeConfiguredHost(value?: string | null) {
    const trimmed = value?.trim()
    if (!trimmed) return null
    const withoutScheme = trimmed.replace(/^[a-z]+:\/\//i, '')
    const firstSegment = withoutScheme.split('/')[0] ?? ''
    if (!firstSegment) return null
    if (/^\[[^\]]+\](?::\d+)?$/.test(firstSegment)) {
        return firstSegment.replace(/^\[|\](?::\d+)?$/g, '')
    }
    const lastColonIndex = firstSegment.lastIndexOf(':')
    if (lastColonIndex > -1 && /^\d+$/.test(firstSegment.slice(lastColonIndex + 1))) {
        return firstSegment.slice(0, lastColonIndex)
    }
    return firstSegment
}

function isTruthySetting(value: string | undefined) {
    if (!value) return false
    return !['0', 'false', 'no', 'off', 'none'].includes(value.trim().toLowerCase())
}

function IconEntryApp() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M4 5h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-5l-3 3-3-3H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zm0 2v9h6.83L12 17.17 13.17 16H20V7H4z" /></svg>
}

function IconEntryAdmin() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 1 4 5v6c0 5.25 3.4 10.16 8 11.78 4.6-1.62 8-6.53 8-11.78V5l-8-4zm0 3.18L18 7v4c0 3.9-2.4 7.54-6 9-3.6-1.46-6-5.1-6-9V7l6-2.82zM11 8h2v5h-2zm0 6h2v2h-2z" /></svg>
}

function IconEntryEmpty() {
    return <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor"><path d="M10 3h4v4h5a2 2 0 0 1 2 2v7h-2V9h-4v4H9V9H5v10h7v2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h5V3zm1 1v3h2V4h-2zm7 14 3 3-1.4 1.4L17 19.8l-2.6 2.6L13 21l3-3-3-3 1.4-1.4L17 16.2l2.6-2.6L21 15l-3 3z" /></svg>
}

function formatCertificateLabel(certificate: { nice_name?: string | null; domain_names?: string[]; provider?: string | null } | null | undefined) {
    if (!certificate) return ''
    if (certificate.nice_name?.trim()) return certificate.nice_name.trim()
    if (certificate.domain_names?.length) return certificate.domain_names.join(', ')
    if (certificate.provider?.trim()) return certificate.provider.trim()
    return ''
}

function formatAccountLabel(key: string, t: (key: string) => string) {
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

function getConnectionTitle(t: (key: string, options?: Record<string, unknown>) => string) {
    return t('myAppsDetailPage.accessPanel.serviceConnectionTitle')
}

export function MyAppAccessPanel({ appId, env, isComposeApp, onUpdated, scopeRect, isDarkMode = false }: MyAppAccessPanelProps) {
    const { t } = useTranslation('shell')
    const palette = getSurfacePalette(isDarkMode)
    const [selectedProxyId, setSelectedProxyId] = useState<number | null>(null)
    const [selectedDomainName, setSelectedDomainName] = useState<string | null>(null)
    const [selectedCandidateKey, setSelectedCandidateKey] = useState('')
    const [selectedContainerName, setSelectedContainerName] = useState('')
    const [selectedTargetPort, setSelectedTargetPort] = useState('')
    const [selectedScheme, setSelectedScheme] = useState<'http' | 'https'>('http')
    const [certificateEmail, setCertificateEmail] = useState('')
    const [customCertName, setCustomCertName] = useState('')
    const [customCertKeyPem, setCustomCertKeyPem] = useState('')
    const [customCertPem, setCustomCertPem] = useState('')
    const [customCertIntermediate, setCustomCertIntermediate] = useState('')
    const [isCustomCertNameAuto, setIsCustomCertNameAuto] = useState(true)
    const [isBindDialogOpen, setIsBindDialogOpen] = useState(false)
    const [bindDialogProxyId, setBindDialogProxyId] = useState<number | null>(null)
    const [bindDialogDomains, setBindDialogDomains] = useState<string[]>([])
    const [bindDialogInitialDomainCount, setBindDialogInitialDomainCount] = useState(0)
    const [bindDialogDomainInput, setBindDialogDomainInput] = useState('')
    const [bindDialogCertId, setBindDialogCertId] = useState<number | null>(null)
    const [bindDialogCertAction, setBindDialogCertAction] = useState<'letsencrypt' | 'upload' | 'existing'>('letsencrypt')
    const [bindDialogDomainInputError, setBindDialogDomainInputError] = useState<string | null>(null)
    const [bindDialogSslEnabled, setBindDialogSslEnabled] = useState(false)
    const [bindDialogForceHttps, setBindDialogForceHttps] = useState(false)
    const [isBindDialogSubmitting, setIsBindDialogSubmitting] = useState(false)
    const [isDeleting, setIsDeleting] = useState(false)
    const [isRootUrlSubmitting, setIsRootUrlSubmitting] = useState(false)
    const [feedback, setFeedback] = useState<AccessFeedback | null>(null)
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
    const [visibleCredKeys, setVisibleCredKeys] = useState<Set<string>>(new Set())
    const customCertKeyFileRef = useRef<HTMLInputElement | null>(null)
    const customCertPemFileRef = useRef<HTMLInputElement | null>(null)
    const customCertIntermediateFileRef = useRef<HTMLInputElement | null>(null)
    const { data, error, isLoading, refetch } = useMyAppAccess(appId)
    const proxyHosts = data?.proxy_hosts ?? []
    const currentProxyHost = proxyHosts.find((host) => host.proxy_id === selectedProxyId) ?? proxyHosts[0] ?? null
    const currentProfile = data?.profile
    const hostName = typeof window !== 'undefined' ? window.location.hostname : ''
    const configuredRootDomain = useMemo(() => normalizeConfiguredHost(env?.W9_URL), [env?.W9_URL])
    const supportsRootUrlSelection = useMemo(() => isTruthySetting(env?.W9_URL_REPLACE) && Boolean(env?.W9_URL?.trim()), [env?.W9_URL, env?.W9_URL_REPLACE])

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
    const showComposeTargetSelector = isComposeApp
    const showDomainAccessSection = isComposeApp || Boolean(currentProfile?.enabled) || proxyHosts.length > 0 || Boolean(frontendHref || backendHref)
    const currentCertificate = useMemo(
        () => data?.certificates.find((certificate) => certificate.id === currentProxyHost?.certificate_id) ?? null,
        [currentProxyHost?.certificate_id, data?.certificates],
    )
    const currentCertificateLabel = currentProxyHost?.certificate_name || formatCertificateLabel(currentCertificate)
    const containerOptions = useMemo(() => {
        const seen = new Set<string>()
        return (data?.candidates ?? []).filter((candidate) => {
            if (!candidate.container_name || seen.has(candidate.container_name)) return false
            seen.add(candidate.container_name)
            return true
        })
    }, [data?.candidates])
    const selectedContainerCandidates = useMemo(
        () => (data?.candidates ?? []).filter((candidate) => candidate.container_name === selectedContainerName),
        [data?.candidates, selectedContainerName],
    )
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
    const hasStandaloneAdmin = Boolean(env?.W9_ADMIN_PATH?.trim())
    const bindingSummaries = useMemo(() => proxyHosts.map((host) => {
        const hostDomains = host.domain_names.filter(isDomainBindingValue)
        const domain = hostDomains[0] ?? null
        const hostScheme = host.certificate_id ? 'https' : (currentProfile?.forward_scheme ?? 'http')
        const baseUrl = domain ? `${hostScheme}://${domain}` : null
        const adminUrl = baseUrl && env?.W9_ADMIN_PATH ? `${baseUrl}${env.W9_ADMIN_PATH}` : null
        const cert = data?.certificates.find((certificate) => certificate.id === host.certificate_id)

        return {
            host,
            cert,
            hostDomains,
            domain,
            hostScheme,
            baseUrl,
            adminUrl,
            certIsLE: cert?.provider === 'letsencrypt',
        }
    }), [currentProfile?.forward_scheme, data?.certificates, env?.W9_ADMIN_PATH, hasStandaloneAdmin, proxyHosts])
    const totalBoundDomains = useMemo(() => bindingSummaries.reduce((count, binding) => count + binding.hostDomains.length, 0), [bindingSummaries])
    const activeRootDomain = useMemo(() => {
        if (configuredRootDomain && bindingSummaries.some((binding) => binding.hostDomains.includes(configuredRootDomain))) {
            return configuredRootDomain
        }
        return bindingSummaries.flatMap((binding) => binding.hostDomains)[0] ?? null
    }, [bindingSummaries, configuredRootDomain])
    const showRootUrlUi = supportsRootUrlSelection && totalBoundDomains > 1
    const domainBindingCards = useMemo(() => bindingSummaries.flatMap((binding) => {
        return {
            key: String(binding.host.proxy_id),
            proxyId: binding.host.proxy_id,
            domains: binding.hostDomains,
            hostScheme: binding.hostScheme,
            rootDomain: showRootUrlUi ? (binding.hostDomains.find((domain) => activeRootDomain === domain) ?? null) : null,
            sslEnabled: Boolean(binding.host.certificate_id),
            sslTone: binding.certIsLE ? 'le' : 'custom',
            sslTooltip: t('myAppsDetailPage.accessPanel.sslEnabled'),
        }
    }), [activeRootDomain, bindingSummaries, showRootUrlUi, t])
    const rootUrlDomainOptions = useMemo(() => bindingSummaries.flatMap((binding) => binding.hostDomains.map((domain) => ({
        key: `${binding.host.proxy_id}-${domain}`,
        domain,
        url: `${binding.hostScheme}://${domain}`,
        isRoot: activeRootDomain === domain,
    }))), [activeRootDomain, bindingSummaries])
    const serviceAccessCards = useMemo(() => {
        if (bindingSummaries.length > 0) {
            const cards: Array<{
                key: string
                title: string
                subtitle: string
                url: string
                tone: 'app' | 'admin'
            }> = []
            const rootBinding = bindingSummaries.find((item) => activeRootDomain ? item.hostDomains.includes(activeRootDomain) : false) ?? bindingSummaries[0]
            const rootScheme = rootBinding?.host.certificate_id ? 'https' : (currentProfile?.forward_scheme ?? 'http')
            const rootBaseUrl = activeRootDomain ? `${rootScheme}://${activeRootDomain}` : rootBinding?.baseUrl ?? null
            if (rootBaseUrl) {
                cards.push({
                    key: `app-${rootBinding?.host.proxy_id ?? 'root'}`,
                    title: t('myAppsDetailPage.accessPanel.entryCardAppTitle'),
                    subtitle: t('myAppsDetailPage.accessPanel.entryAddressLabel'),
                    url: rootBaseUrl,
                    tone: 'app',
                })
            }

            if (hasStandaloneAdmin && rootBaseUrl && env?.W9_ADMIN_PATH) {
                const adminUrl = `${rootBaseUrl}${env.W9_ADMIN_PATH}`
                if (adminUrl) {
                    cards.push({
                        key: `admin-${rootBinding?.host.proxy_id ?? 'root'}`,
                        title: t('myAppsDetailPage.accessPanel.entryCardAdminTitle'),
                        subtitle: t('myAppsDetailPage.accessPanel.entryAddressLabel'),
                        url: adminUrl,
                        tone: 'admin',
                    })
                }
            }

            return cards
        }

        const cards: Array<{
            key: string
            title: string
            subtitle: string
            url: string
            tone: 'app' | 'admin'
        }> = []
        if (frontendHref) {
            cards.push({
                key: 'direct-app',
                title: t('myAppsDetailPage.accessPanel.entryCardAppTitle'),
                subtitle: t('myAppsDetailPage.accessPanel.entryAddressLabel'),
                url: frontendHref,
                tone: 'app',
            })
        }
        if (hasStandaloneAdmin && backendHref) {
            cards.push({
                key: 'direct-admin',
                title: t('myAppsDetailPage.accessPanel.entryCardAdminTitle'),
                subtitle: t('myAppsDetailPage.accessPanel.entryAddressLabel'),
                url: backendHref,
                tone: 'admin',
            })
        }
        return cards
    }, [activeRootDomain, backendHref, bindingSummaries, currentProfile?.forward_scheme, env?.W9_ADMIN_PATH, frontendHref, hasStandaloneAdmin, t])
    const nonWebConnections = useMemo<NonWebConnectionEntry[]>(() => {
        if (isComposeApp || serviceAccessCards.length > 0 || !env) return []

        const resolvedHost = configuredRootDomain || currentDomains[0] || hostName || '-'

        return Object.entries(env)
            .filter(([key, value]) => key.endsWith('PORT_SET') && !['W9_HTTP_PORT_SET', 'W9_HTTPS_PORT_SET'].includes(key) && value?.trim())
            .map(([key, value]) => {
                const port = String(value).trim()
                const host = resolvedHost
                return {
                    key,
                    title: getConnectionTitle(t),
                    host,
                    port,
                    address: host && host !== '-' ? `${host}:${port}` : port,
                }
            })
    }, [configuredRootDomain, currentDomains, env, hostName, isComposeApp, serviceAccessCards.length, t])
    const showRootUrlCard = showRootUrlUi
    const combinedSectionTitle = accountEntries.length > 0
        ? (serviceAccessCards.length > 0
            ? t('myAppsDetailPage.accessPanel.credentialsTitle')
            : t('myAppsDetailPage.accessPanel.credentialsOnlyTitle'))
        : t('myAppsDetailPage.accessPanel.serviceEntryTitle')
    const isEditingBinding = bindDialogProxyId !== null
    const usesChipDomainEditor = isEditingBinding && bindDialogInitialDomainCount > 1
    const bindDialogEditableCount = isEditingBinding ? Math.max(bindDialogInitialDomainCount, 1) : 1
    const canAppendBindDialogDomain = usesChipDomainEditor && bindDialogDomains.length < bindDialogInitialDomainCount
    const canSubmitBindDialog = isEditingBinding
        ? (usesChipDomainEditor ? bindDialogDomains.length > 0 : Boolean(bindDialogDomainInput.trim()))
        : Boolean(bindDialogDomainInput.trim())
    const canSubmitBindDialogWithTarget = canSubmitBindDialog && (!showComposeTargetSelector || Boolean(selectedCandidateKey))
    const defaultCustomCertName = useMemo(() => {
        if (bindDialogProxyId !== null) {
            return bindDialogDomains[0] ?? ''
        }
        return bindDialogDomainInput.trim()
    }, [bindDialogDomainInput, bindDialogDomains, bindDialogProxyId])

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
    useEffect(() => {
        if (bindDialogCertAction !== 'upload' || !isCustomCertNameAuto) return
        setCustomCertName(defaultCustomCertName)
    }, [bindDialogCertAction, defaultCustomCertName, isCustomCertNameAuto])

    async function persistProfileSelection() {
        if (!showComposeTargetSelector) return
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

        const deleteDomain = selectedDomainName?.trim() ?? null
        const remainingDomains = currentProxyHost.domain_names
            .map((item) => item.trim())
            .filter((item) => item && item !== deleteDomain)

        setIsDeleting(true)
        setFeedback(null)
        try {
            if (deleteDomain && remainingDomains.length > 0) {
                await ensureDomainBinding(remainingDomains, currentProxyHost.certificate_id ?? null, Boolean(currentProxyHost.ssl_forced && currentProxyHost.certificate_id), currentProxyHost.proxy_id)
            } else {
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
            }

            await refetch()
            await onUpdated()
            setShowDeleteConfirm(false)
            setSelectedDomainName(null)
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

    async function handleRootUrlSelect(domainName: string) {
        if (!supportsRootUrlSelection || !domainName || isRootUrlSubmitting || activeRootDomain === domainName) return

        setIsRootUrlSubmitting(true)
        setFeedback(null)
        try {
            const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/access/root-url`, {
                method: 'PUT',
                credentials: 'include',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ domain_name: domainName }),
            })

            if (!response.ok) {
                throw new Error(await parseJsonError(response, `Failed to update root URL: ${response.status}`))
            }

            await refetch()
            await onUpdated()
            setFeedback({ severity: 'success', message: t('myAppsDetailPage.accessPanel.rootUrlUpdated') })
        } catch (rootUrlError) {
            setFeedback({
                severity: 'error',
                message: rootUrlError instanceof Error ? rootUrlError.message : t('myAppsDetailPage.accessPanel.genericError'),
            })
        } finally {
            setIsRootUrlSubmitting(false)
        }
    }

    async function readPemFile(file: File) {
        return new Promise<string>((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '')
            reader.onerror = () => reject(new Error(t('myAppsDetailPage.accessPanel.fileReadFailed')))
            reader.readAsText(file)
        })
    }

    async function handlePemFilePick(
        event: React.ChangeEvent<HTMLInputElement>,
        setter: (value: string) => void,
    ) {
        const file = event.target.files?.[0]
        if (!file) return
        try {
            const text = await readPemFile(file)
            setter(text.trim())
        } catch (error) {
            setFeedback({
                severity: 'error',
                message: error instanceof Error ? error.message : t('myAppsDetailPage.accessPanel.fileReadFailed'),
            })
        } finally {
            event.target.value = ''
        }
    }

    function validateDomainDraft(rawValue: string) {
        const raw = rawValue.trim()
        if (!raw) return t('myAppsDetailPage.accessPanel.domainInvalidError')
        if (raw.includes('://')) return t('myAppsDetailPage.accessPanel.domainNoSchemeError')
        return isDomainBindingValue(raw) ? null : t('myAppsDetailPage.accessPanel.domainInvalidError')
    }

    function commitPendingBindDialogDomain() {
        const pendingRaw = bindDialogDomainInput.trim()
        if (!pendingRaw) {
            setBindDialogDomainInputError(null)
            return
        }

        const validationMessage = validateDomainDraft(pendingRaw)
        if (validationMessage) {
            setBindDialogDomainInputError(validationMessage)
            return
        }

        if (bindDialogDomains.includes(pendingRaw)) {
            setBindDialogDomainInput('')
            setBindDialogDomainInputError(null)
            return
        }

        if (!canAppendBindDialogDomain) {
            setBindDialogDomainInput('')
            setBindDialogDomainInputError(null)
            return
        }

        setBindDialogDomains((prev) => [...prev, pendingRaw])
        setBindDialogDomainInput('')
        setBindDialogDomainInputError(null)
    }

    function removeBindDialogDomainAt(index: number) {
        setBindDialogDomains((prev) => prev.filter((_, domainIndex) => domainIndex !== index))
        if (bindDialogDomainInputError) setBindDialogDomainInputError(null)
    }

    function openBindDialog(proxyId: number | null) {
        if (proxyId !== null) {
            const host = proxyHosts.find((h) => h.proxy_id === proxyId)
            if (host) {
                const domains = host.domain_names.filter(isDomainBindingValue)
                setBindDialogDomains(domains)
                setBindDialogInitialDomainCount(domains.length)
                setBindDialogDomainInput(domains.length > 1 ? '' : (domains[0] ?? ''))
                setBindDialogForceHttps(Boolean(host.ssl_forced && host.certificate_id))
                setBindDialogCertId(host.certificate_id ?? null)
                setBindDialogSslEnabled(Boolean(host.certificate_id))
                setBindDialogCertAction(host.certificate_id ? 'existing' : 'letsencrypt')
            }
            setBindDialogProxyId(proxyId)
        } else {
            setBindDialogDomains([])
            setBindDialogInitialDomainCount(0)
            setBindDialogDomainInput('')
            setBindDialogForceHttps(false)
            setBindDialogCertId(null)
            setBindDialogProxyId(null)
            setBindDialogSslEnabled(false)
            setBindDialogCertAction('letsencrypt')
        }
        setCertificateEmail('')
        setCustomCertName('')
        setIsCustomCertNameAuto(true)
        setCustomCertKeyPem('')
        setCustomCertPem('')
        setCustomCertIntermediate('')
        setIsBindDialogOpen(true)
    }

    function resetBindDialogState() {
        setIsBindDialogOpen(false)
        setBindDialogDomains([])
        setBindDialogInitialDomainCount(0)
        setBindDialogDomainInput('')
        setBindDialogCertId(null)
        setBindDialogCertAction('letsencrypt')
        setBindDialogDomainInputError(null)
        setBindDialogSslEnabled(false)
        setBindDialogForceHttps(false)
        setCertificateEmail('')
        setCustomCertName('')
        setIsCustomCertNameAuto(true)
        setCustomCertKeyPem('')
        setCustomCertPem('')
        setCustomCertIntermediate('')
    }

    function handleCloseBindDialog() {
        if (isBindDialogSubmitting) return
        resetBindDialogState()
    }

    async function handleBindDialogSubmit() {
        // Block if there's an active validation error in domain input
        if (bindDialogDomainInputError) return

        const rawInput = bindDialogDomainInput.trim()
        let domains: string[] = []

        if (isEditingBinding) {
            if (!usesChipDomainEditor) {
                const validationMessage = validateDomainDraft(rawInput)
                if (validationMessage) {
                    setBindDialogDomainInputError(validationMessage)
                    return
                }
                domains = [rawInput]
            } else {
                const editedDomains = bindDialogDomains
                    .map((domain) => domain.trim())
                    .filter(Boolean)

                const invalidEditedDomain = editedDomains.find((domain) => validateDomainDraft(domain) !== null)
                if (invalidEditedDomain) {
                    setBindDialogDomainInputError(validateDomainDraft(invalidEditedDomain))
                    return
                }

                domains = Array.from(new Set(editedDomains))

                if (rawInput) {
                    const validationMessage = validateDomainDraft(rawInput)
                    if (validationMessage) {
                        setBindDialogDomainInputError(validationMessage)
                        return
                    }
                    if (!domains.includes(rawInput)) {
                        if (!canAppendBindDialogDomain) {
                            setBindDialogDomainInput('')
                            setBindDialogDomainInputError(null)
                            return
                        }
                        domains.push(rawInput)
                    }
                }

                if (domains.length > bindDialogEditableCount) {
                    setBindDialogDomainInputError(t('myAppsDetailPage.accessPanel.domainEditLimitError'))
                    return
                }
            }
        } else {
            const validationMessage = validateDomainDraft(rawInput)
            if (validationMessage) {
                setBindDialogDomainInputError(validationMessage)
                return
            }
            domains = [rawInput]
        }

        if (domains.length === 0) {
            setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.validation') })
            return
        }

        // Validate cert-action-specific fields
        if (bindDialogSslEnabled && bindDialogCertAction === 'letsencrypt' && !certificateEmail.trim()) {
            setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.emailValidation') })
            return
        }
        if (bindDialogSslEnabled && bindDialogCertAction === 'existing' && bindDialogCertId === null) {
            setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.existingCertRequired') })
            return
        }
        if (bindDialogSslEnabled && bindDialogCertAction === 'upload' && (!customCertPem.trim() || !customCertKeyPem.trim())) {
            setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.customCertValidation') })
            return
        }

        setIsBindDialogSubmitting(true)
        setFeedback(null)
        try {
            await persistProfileSelection()

            if (bindDialogSslEnabled && bindDialogCertAction === 'letsencrypt') {
                const binding = await ensureDomainBinding(domains, null, false, bindDialogProxyId)
                const effectiveProxyId = (binding.proxy_id ?? (binding as { id?: number }).id ?? bindDialogProxyId) as number | null
                const certResp = await fetch(`/api/apps/${encodeURIComponent(appId)}/access/certificates/letsencrypt`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: certificateEmail.trim(), domain_names: domains, proxy_id: effectiveProxyId }),
                })
                if (!certResp.ok) throw new Error(await parseJsonError(certResp, 'Failed to request certificate'))
                const cert = await certResp.json() as { id?: number }
                if (cert.id) {
                    await ensureDomainBinding(domains, cert.id, bindDialogForceHttps, effectiveProxyId)
                }
                await refetch()
                await onUpdated()
                resetBindDialogState()
                setFeedback({ severity: 'success', message: t('myAppsDetailPage.accessPanel.certificateIssued') })
            } else if (bindDialogSslEnabled && bindDialogCertAction === 'upload') {
                const binding = await ensureDomainBinding(domains, null, false, bindDialogProxyId)
                const effectiveProxyId = (binding.proxy_id ?? (binding as { id?: number }).id ?? bindDialogProxyId) as number | null
                const certResp = await fetch(`/api/apps/${encodeURIComponent(appId)}/access/certificates/custom`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        nice_name: customCertName.trim() || domains[0],
                        certificate_pem: customCertIntermediate.trim()
                            ? `${customCertPem.trim()}
${customCertIntermediate.trim()}`
                            : customCertPem.trim(),
                        key_pem: customCertKeyPem.trim(),
                        proxy_id: effectiveProxyId,
                        domain_names: domains,
                    }),
                })
                if (!certResp.ok) throw new Error(await parseJsonError(certResp, 'Failed to upload certificate'))
                const cert = await certResp.json() as { id?: number }
                if (cert.id) {
                    await ensureDomainBinding(domains, cert.id, bindDialogForceHttps, effectiveProxyId)
                }
                await refetch()
                await onUpdated()
                resetBindDialogState()
                setFeedback({ severity: 'success', message: t('myAppsDetailPage.accessPanel.customCertUploaded') })
            } else {
                const certificateId = bindDialogSslEnabled ? bindDialogCertId : null
                const sslForced = bindDialogSslEnabled && bindDialogCertId !== null && bindDialogForceHttps
                await ensureDomainBinding(domains, certificateId, sslForced, bindDialogProxyId)
                await refetch()
                await onUpdated()
                resetBindDialogState()
                setFeedback({ severity: 'success', message: t(bindDialogProxyId !== null ? 'myAppsDetailPage.accessPanel.updateSuccess' : 'myAppsDetailPage.accessPanel.createSuccess') })
            }
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

            {showDomainAccessSection ? (
                <div className="myapps-access-section myapps-access-binding-section">
                    <div className="myapps-access-section-head">
                        <div className="myapps-section-label-stack">
                            <div className="myapps-section-label-bar">
                                <span className="myapps-section-label-indicator" />
                                <span className="myapps-section-label-text">{t('myAppsDetailPage.accessPanel.customBindingTitle')}</span>
                            </div>
                        </div>
                        <button className="myapps-bind-domain-btn" onClick={() => openBindDialog(null)} type="button">
                            <IconPlus />
                            {t('myAppsDetailPage.accessPanel.bindDomain')}
                        </button>
                    </div>

                    {domainBindingCards.length > 0 ? (
                        <div className="myapps-binding-card-list">
                            {domainBindingCards.map((binding) => (
                                <div className="myapps-binding-card" key={binding.key}>
                                    <div className="myapps-binding-card-main">
                                        <div className="myapps-binding-card-copy">
                                            <div className="myapps-binding-card-domain-row">
                                                {binding.domains.map((domain) => (
                                                    <a
                                                        href={`${binding.hostScheme}://${domain}`}
                                                        key={domain}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                        className="myapps-route-domain-chip"
                                                    >
                                                        {domain}
                                                    </a>
                                                ))}
                                                {binding.rootDomain ? (
                                                    <span className="myapps-route-root-badge">{t('myAppsDetailPage.accessPanel.rootUrlBadge')}</span>
                                                ) : null}
                                            </div>
                                        </div>
                                    </div>
                                    <div className="myapps-binding-card-side">
                                        {binding.sslEnabled ? (
                                            <span className={`myapps-cert-type-chip is-${binding.sslTone} is-ssl-only`} title={binding.sslTooltip} aria-label={binding.sslTooltip}>
                                                <IconSslShield />
                                            </span>
                                        ) : null}
                                        <div className="myapps-binding-card-actions">
                                            <IconButton onClick={() => openBindDialog(binding.proxyId)} size="small" title={t('myAppsDetailPage.accessPanel.edit')}>
                                                <IconEdit />
                                            </IconButton>
                                            <IconButton onClick={() => { setSelectedProxyId(binding.proxyId); setSelectedDomainName(null); setShowDeleteConfirm(true) }} size="small" title={t('myAppsDetailPage.accessPanel.deleteDomain')}>
                                                <IconDelete />
                                            </IconButton>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="myapps-access-binding-empty">
                            <div className="myapps-access-binding-empty-icon">
                                <IconEntryEmpty />
                            </div>
                            <div className="myapps-access-binding-empty-title">{t('myAppsDetailPage.accessPanel.bindingEmptyTitle')}</div>
                        </div>
                    )}
                </div>
            ) : null}

            {showRootUrlCard ? (
                <div className="myapps-access-section myapps-root-url-section">
                    <div className="myapps-access-section-head">
                        <div className="myapps-section-label-stack">
                            <div className="myapps-section-label-bar">
                                <span className="myapps-section-label-indicator" />
                                <span className="myapps-section-label-text">{t('myAppsDetailPage.accessPanel.rootUrlCardTitle')}</span>
                            </div>
                            <p className="myapps-section-label-desc">{t('myAppsDetailPage.accessPanel.rootUrlCardDescription')}</p>
                        </div>
                    </div>
                    <div className="myapps-root-url-list">
                        {rootUrlDomainOptions.map((option) => (
                            <button
                                className={`myapps-root-url-option ${option.isRoot ? 'is-active' : ''}`}
                                disabled={isRootUrlSubmitting || option.isRoot}
                                key={option.key}
                                onClick={() => void handleRootUrlSelect(option.domain)}
                                title={option.isRoot ? t('myAppsDetailPage.accessPanel.rootUrlBadge') : t('myAppsDetailPage.accessPanel.setAsRootUrl')}
                                type="button"
                            >
                                <span className={`myapps-root-url-indicator ${option.isRoot ? 'is-active' : ''}`} aria-hidden="true">
                                    <span className="myapps-route-root-dot" />
                                </span>
                                <span className="myapps-root-url-copy">
                                    <span className="myapps-root-url-domain">{option.domain}</span>
                                    <span className="myapps-root-url-link">{option.url}</span>
                                </span>
                                <span className={`myapps-root-url-status ${option.isRoot ? 'is-active' : ''}`}>
                                    {option.isRoot ? t('myAppsDetailPage.accessPanel.rootUrlBadge') : t('myAppsDetailPage.accessPanel.setAsRootUrl')}
                                </span>
                            </button>
                        ))}
                    </div>
                </div>
            ) : null}

            {nonWebConnections.length > 0 ? (
                <div className="myapps-access-section myapps-service-connection-section">
                    <div className="myapps-access-section-head">
                        <div className="myapps-section-label-stack">
                            <div className="myapps-section-label-bar">
                                <span className="myapps-section-label-indicator" />
                                <span className="myapps-section-label-text">{t('myAppsDetailPage.accessPanel.serviceConnectionTitle')}</span>
                            </div>
                            <p className="myapps-section-label-desc">{t('myAppsDetailPage.accessPanel.serviceConnectionDescription')}</p>
                        </div>
                    </div>
                    <div className={`myapps-service-connection-grid ${nonWebConnections.length === 1 ? 'is-single' : ''}`}>
                        {nonWebConnections.map((connection) => (
                            <div className="myapps-service-connection-card" key={connection.key}>
                                <div className="myapps-service-connection-title">{connection.title}</div>
                                <div className="myapps-service-connection-body">
                                    <div className="myapps-service-connection-row">
                                        <span className="myapps-service-connection-label">{t('myAppsDetailPage.accessPanel.connectionAddressLabel')}</span>
                                        <span className="myapps-service-connection-value">
                                            <span className="myapps-service-connection-value-text">{connection.address}</span>
                                            <button
                                                className="myapps-creds-copy-btn"
                                                onClick={async () => {
                                                    try {
                                                        await copyTextWithFallback(connection.address)
                                                        setFeedback({ severity: 'success', message: t('myAppsDetailPage.accessPanel.copySuccess') })
                                                    } catch {
                                                        setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.copyFailed') })
                                                    }
                                                }}
                                                title={t('myAppsDetailPage.accessPanel.copySuccess')}
                                                type="button"
                                            >
                                                <IconCopy />
                                            </button>
                                        </span>
                                    </div>
                                    <div className="myapps-service-connection-row">
                                        <span className="myapps-service-connection-label">{t('myAppsDetailPage.accessPanel.connectionHostLabel')}</span>
                                        <span className="myapps-service-connection-value">
                                            <span className="myapps-service-connection-value-text">{connection.host}</span>
                                        </span>
                                    </div>
                                    <div className="myapps-service-connection-row">
                                        <span className="myapps-service-connection-label">{t('myAppsDetailPage.accessPanel.connectionPortLabel')}</span>
                                        <span className="myapps-service-connection-value">
                                            <span className="myapps-service-connection-value-text">{connection.port}</span>
                                        </span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ) : null}

            {(serviceAccessCards.length > 0 || accountEntries.length > 0) ? (
                <div className="myapps-creds-section">
                    <div className="myapps-creds-section-head">
                        <div className="myapps-section-label-bar">
                            <span className="myapps-section-label-indicator" />
                            <span className="myapps-section-label-text">{combinedSectionTitle}</span>
                        </div>
                    </div>
                    {serviceAccessCards.length > 0 ? (
                        <div className={`myapps-access-entry-grid ${serviceAccessCards.length === 1 ? 'is-single' : ''}`}>
                            {serviceAccessCards.map((card) => {
                                const isAdminCard = card.tone === 'admin'
                                return (
                                    <div className={`myapps-access-entry-card ${isAdminCard ? 'is-admin' : 'is-app'}`} key={card.key}>
                                        <div className="myapps-access-entry-card-main">
                                            <div className={`myapps-access-entry-icon ${isAdminCard ? 'is-admin' : 'is-app'}`}>
                                                {isAdminCard ? <IconEntryAdmin /> : <IconEntryApp />}
                                            </div>
                                            <div className="myapps-access-entry-copy">
                                                <div className="myapps-access-entry-title-row">
                                                    <div className="myapps-access-entry-title">{card.title}</div>
                                                </div>
                                                <div className="myapps-access-entry-link-row">
                                                    <span className="myapps-access-entry-subtitle">{card.subtitle}</span>
                                                    <a className="myapps-access-entry-link" href={card.url} rel="noreferrer" target="_blank">
                                                        {card.url}
                                                    </a>
                                                    <button className="myapps-access-entry-copy-btn" onClick={() => void copyTextWithFallback(card.url)} title={t('myAppsDetailPage.accessPanel.copySuccess')} type="button">
                                                        <IconCopy />
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                        <a
                                            aria-label={card.url}
                                            className="myapps-access-entry-action"
                                            href={card.url}
                                            rel="noreferrer"
                                            target="_blank"
                                            title={card.url}
                                        >
                                            <IconOpenLink />
                                        </a>
                                    </div>
                                )
                            })}
                        </div>
                    ) : null}
                    {accountEntries.length > 0 ? (
                        <div className="myapps-creds-rows">
                            {accountEntries.map((entry) => (
                                <div className="myapps-creds-row" key={entry.key}>
                                    <label className="myapps-creds-label">{formatAccountLabel(entry.key, t)}</label>
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
                    ) : null}
                </div>
            ) : null}

            <SurfaceDialog
                fullWidth
                maxWidth="md"
                onClose={handleCloseBindDialog}
                open={isBindDialogOpen}
                scope="content"
                scopeRect={scopeRect ?? null}
                contentStrategy="viewport-fixed"
                darkMode={isDarkMode}
                sx={{
                    zIndex: 1510,
                    '& .MuiDialog-container': {
                        alignItems: 'flex-start',
                        justifyContent: 'center',
                        pt: { xs: 3, md: 3 },
                        pb: { xs: 1.5, md: 2.5 },
                    },
                }}
                paperSx={{
                    width: { xs: 'min(100%, 780px)', md: 'min(780px, calc(100% - 20px))' },
                    maxWidth: '780px',
                    borderRadius: 0,
                    backgroundColor: palette.dialogBg,
                    color: palette.text,
                    border: `1px solid ${palette.borderStrong}`,
                    boxShadow: isDarkMode ? '0 24px 64px rgba(2,6,23,0.56)' : '0 16px 40px rgba(15,23,42,0.16)',
                }}
            >
                <Box sx={{ px: { xs: 2, md: 2.5 }, py: { xs: 1.75, md: 2 }, borderBottom: `1px solid ${palette.divider}`, backgroundColor: palette.dialogBg, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
                    <Typography sx={{ fontSize: { xs: 18, md: 20 }, fontWeight: 600, color: palette.text }}>
                        {bindDialogProxyId !== null ? t('myAppsDetailPage.accessPanel.editBindTitle') : t('myAppsDetailPage.accessPanel.bindNewTitle')}
                    </Typography>
                    <IconButton disabled={isBindDialogSubmitting} onClick={handleCloseBindDialog} size="small" sx={{ color: palette.subtleText, borderRadius: 0 }}>
                        <svg fill="currentColor" height="18" viewBox="0 0 24 24" width="18"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" /></svg>
                    </IconButton>
                </Box>
                <Box sx={{ px: { xs: 2, md: 2.5 }, py: 1.125, overflowY: 'auto', maxHeight: '65vh' }}>
                    <div className="myapps-bind-dialog-form">
                        {showComposeTargetSelector ? (
                            <div className="myapps-bind-target-group">
                                <div className="myapps-domain-field myapps-bind-target-field-block">
                                    <label className="myapps-domain-field-label" style={{ color: palette.text }}>
                                        {t('myAppsDetailPage.accessPanel.proxyTargetTitle')}
                                        <span className="myapps-field-required">*</span>
                                    </label>
                                    {containerOptions.length > 0 ? (
                                        <>
                                            <div className="myapps-bind-target-inline-grid myapps-access-editor-enter">
                                                <div className="myapps-bind-target-field">
                                                    <select
                                                        className="form-select myapps-access-target-select"
                                                        aria-label={t('myAppsDetailPage.accessPanel.targetContainerLabel')}
                                                        onChange={(event) => setSelectedContainerName(event.target.value)}
                                                        title={t('myAppsDetailPage.accessPanel.targetContainerLabel')}
                                                        value={selectedContainerName}
                                                    >
                                                        {containerOptions.map((candidate) => (
                                                            <option key={candidate.container_name} value={candidate.container_name}>{candidate.container_name}</option>
                                                        ))}
                                                    </select>
                                                </div>

                                                <div className="myapps-bind-target-field">
                                                    <select
                                                        className="form-select myapps-access-target-select"
                                                        aria-label={t('myAppsDetailPage.accessPanel.targetPortLabel')}
                                                        onChange={(event) => setSelectedTargetPort(event.target.value)}
                                                        title={t('myAppsDetailPage.accessPanel.targetPortLabel')}
                                                        value={selectedTargetPort}
                                                    >
                                                        {selectedContainerCandidates.map((candidate) => (
                                                            <option
                                                                key={getCandidateKey(candidate.forward_host, candidate.forward_port)}
                                                                value={String(candidate.forward_port)}
                                                            >
                                                                {candidate.forward_port}
                                                            </option>
                                                        ))}
                                                    </select>
                                                </div>

                                                <div className="myapps-bind-target-field">
                                                    <select
                                                        className="form-select myapps-access-target-select"
                                                        aria-label={t('myAppsDetailPage.accessPanel.schemeLabel')}
                                                        onChange={(event) => setSelectedScheme(event.target.value === 'https' ? 'https' : 'http')}
                                                        title={t('myAppsDetailPage.accessPanel.schemeLabel')}
                                                        value={selectedScheme}
                                                    >
                                                        <option value="http">{t('myAppsDetailPage.accessPanel.schemeHttpDescription')}</option>
                                                        <option value="https">{t('myAppsDetailPage.accessPanel.schemeHttpsDescription')}</option>
                                                    </select>
                                                </div>
                                            </div>
                                            <p className="myapps-domain-chip-helper">{t('myAppsDetailPage.accessPanel.proxyTargetDescription')}</p>
                                        </>
                                    ) : (
                                        <p className="myapps-domain-chip-helper">{t('myAppsDetailPage.accessPanel.composeDefinitionRequired')}</p>
                                    )}
                                </div>
                            </div>
                        ) : null}

                        <div className="myapps-domain-field">
                            <label className="myapps-domain-field-label" style={{ color: palette.text }}>
                                {t('myAppsDetailPage.accessPanel.domainInputLabel')}
                                <span className="myapps-field-required">*</span>
                            </label>
                            {usesChipDomainEditor ? (
                                <div
                                    className="myapps-domain-chip-box myapps-domain-chip-box-editlike"
                                    onClick={(e) => (e.currentTarget.querySelector('input') as HTMLInputElement | null)?.focus()}
                                >
                                    {bindDialogDomains.map((domain, index) => (
                                        <span className="myapps-domain-chip-item" key={`${domain}-${index}`}>
                                            <span className="myapps-domain-chip-item-text">{domain}</span>
                                            <button
                                                className="myapps-domain-chip-item-remove"
                                                disabled={isBindDialogSubmitting}
                                                onClick={(event) => {
                                                    event.preventDefault()
                                                    event.stopPropagation()
                                                    removeBindDialogDomainAt(index)
                                                }}
                                                title={t('myAppsDetailPage.accessPanel.deleteDomain')}
                                                type="button"
                                            >
                                                <svg fill="currentColor" height="12" viewBox="0 0 24 24" width="12"><path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" /></svg>
                                            </button>
                                        </span>
                                    ))}
                                    <input
                                        className="myapps-domain-chip-input myapps-domain-chip-input-inline"
                                        disabled={isBindDialogSubmitting || !canAppendBindDialogDomain}
                                        onBlur={commitPendingBindDialogDomain}
                                        onChange={(e) => {
                                            setBindDialogDomainInput(e.target.value)
                                            if (bindDialogDomainInputError) setBindDialogDomainInputError(null)
                                        }}
                                        onKeyDown={(event) => {
                                            if (event.key === 'Enter' || event.key === ',') {
                                                event.preventDefault()
                                                commitPendingBindDialogDomain()
                                                return
                                            }

                                            if (event.key === 'Backspace' && !bindDialogDomainInput && bindDialogDomains.length) {
                                                event.preventDefault()
                                                removeBindDialogDomainAt(bindDialogDomains.length - 1)
                                            }
                                        }}
                                        placeholder={canAppendBindDialogDomain ? t('myAppsDetailPage.accessPanel.domainExample') : ''}
                                        value={bindDialogDomainInput}
                                    />
                                </div>
                            ) : (
                                <div
                                    className="myapps-domain-chip-box"
                                    onClick={(e) => (e.currentTarget.querySelector('input') as HTMLInputElement | null)?.focus()}
                                >
                                    <input
                                        className="myapps-domain-chip-input"
                                        disabled={isBindDialogSubmitting}
                                        onBlur={() => {
                                            const raw = bindDialogDomainInput.trim()
                                            if (!raw) {
                                                setBindDialogDomainInputError(null)
                                                return
                                            }
                                            setBindDialogDomainInputError(validateDomainDraft(raw))
                                        }}
                                        onChange={(e) => {
                                            setBindDialogDomainInput(e.target.value)
                                            if (bindDialogDomainInputError) setBindDialogDomainInputError(null)
                                        }}
                                        placeholder={t('myAppsDetailPage.accessPanel.domainExample')}
                                        value={bindDialogDomainInput}
                                    />
                                </div>
                            )}
                            {bindDialogDomainInputError ? (
                                <p className="myapps-domain-chip-helper" style={{ color: palette.danger }}>{bindDialogDomainInputError}</p>
                            ) : null}
                            {!isEditingBinding ? <p className="myapps-domain-chip-helper">{t('myAppsDetailPage.accessPanel.domainInputHelper')}</p> : null}
                        </div>
                        <div className="myapps-bind-cert-section">
                            <div className="myapps-bind-cert-switch">
                                <div className="myapps-bind-https-label">
                                    <span className="myapps-bind-https-label-title">{t('myAppsDetailPage.accessPanel.sslCertScheme')}</span>
                                    <span className="myapps-bind-https-label-desc">{t('myAppsDetailPage.accessPanel.sslCertSwitchHelper')}</span>
                                </div>
                                <Switch
                                    checked={bindDialogSslEnabled}
                                    disabled={isBindDialogSubmitting}
                                    onChange={(e) => {
                                        const enabled = e.target.checked
                                        setBindDialogSslEnabled(enabled)
                                        if (enabled && bindDialogCertId === null) {
                                            setBindDialogCertAction('letsencrypt')
                                        }
                                    }}
                                    size="small"
                                />
                            </div>
                            {bindDialogSslEnabled ? (
                                <>
                                    <div className="myapps-bind-cert-choice-grid myapps-bind-cert-choice-grid-three">
                                        <button
                                            className={`myapps-bind-cert-choice ${bindDialogCertAction === 'letsencrypt' ? 'is-active' : ''}`}
                                            disabled={isBindDialogSubmitting}
                                            onClick={() => setBindDialogCertAction('letsencrypt')}
                                            type="button"
                                        >
                                            <span className="myapps-bind-cert-choice-badge">{t('myAppsDetailPage.accessPanel.recommendedLabel')}</span>
                                            <div className="myapps-bind-cert-choice-title-row">
                                                <svg fill="currentColor" height="14" viewBox="0 0 24 24" width="14" style={{ flexShrink: 0 }}><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 4l5 2.18V11c0 3.5-2.33 6.79-5 7.93-2.67-1.14-5-4.43-5-7.93V7.18L12 5zm-1 3v4h2V8h-2zm0 5v2h2v-2h-2z" /></svg>
                                                <span>{t('myAppsDetailPage.accessPanel.certApplyTitle')}</span>
                                            </div>
                                            <span className="myapps-bind-cert-choice-desc">{t('myAppsDetailPage.accessPanel.certApplyCardHint')}</span>
                                        </button>
                                        <button
                                            className={`myapps-bind-cert-choice ${bindDialogCertAction === 'existing' ? 'is-active' : ''}`}
                                            disabled={isBindDialogSubmitting}
                                            onClick={() => setBindDialogCertAction('existing')}
                                            type="button"
                                        >
                                            <div className="myapps-bind-cert-choice-title-row">
                                                <IconCertExisting />
                                                <span>{t('myAppsDetailPage.accessPanel.certExistingTitle')}</span>
                                            </div>
                                            <span className="myapps-bind-cert-choice-desc">{t('myAppsDetailPage.accessPanel.certExistingHint')}</span>
                                        </button>
                                        <button
                                            className={`myapps-bind-cert-choice ${bindDialogCertAction === 'upload' ? 'is-active' : ''}`}
                                            disabled={isBindDialogSubmitting}
                                            onClick={() => setBindDialogCertAction('upload')}
                                            type="button"
                                        >
                                            <div className="myapps-bind-cert-choice-title-row">
                                                <svg fill="currentColor" height="14" viewBox="0 0 24 24" width="14" style={{ flexShrink: 0 }}><path d="M9 16h6v-6h4l-7-7-7 7h4v6zm-4 2h14v2H5v-2z" /></svg>
                                                <span>{t('myAppsDetailPage.accessPanel.certUploadTitle')}</span>
                                            </div>
                                            <span className="myapps-bind-cert-choice-desc">{t('myAppsDetailPage.accessPanel.certUploadCardHint')}</span>
                                        </button>
                                    </div>
                                    {bindDialogCertAction === 'existing' ? (
                                        <div className="myapps-bind-cert-subform myapps-bind-cert-subform-panel">
                                            <label className="myapps-domain-field-label" style={{ color: palette.text }}>
                                                {t('myAppsDetailPage.accessPanel.relatedExistingCertLabel')}
                                                <span className="myapps-field-required">*</span>
                                            </label>
                                            <select
                                                className="myapps-bind-cert-select"
                                                disabled={isBindDialogSubmitting}
                                                value={String(bindDialogCertId ?? 'none')}
                                                onChange={(e) => setBindDialogCertId(e.target.value === 'none' ? null : Number(e.target.value))}
                                            >
                                                <option value="none">{t('myAppsDetailPage.accessPanel.selectCertPlaceholder')}</option>
                                                {availableCertificates.map((cert) => (
                                                    <option key={cert.id} value={cert.id}>
                                                        {formatCertificateLabel(cert) || `#${cert.id}`}
                                                    </option>
                                                ))}
                                            </select>
                                        </div>
                                    ) : null}
                                    {bindDialogCertAction === 'letsencrypt' && (
                                        <div className="myapps-bind-cert-subform myapps-bind-cert-subform-panel myapps-bind-cert-subform-le">
                                            <label className="myapps-domain-field-label" style={{ color: palette.text }}>
                                                {t('myAppsDetailPage.accessPanel.certificateEmailLabel')}
                                                <span className="myapps-field-required">*</span>
                                            </label>
                                            <div
                                                className="myapps-domain-chip-box"
                                                onClick={(e) => (e.currentTarget.querySelector('input') as HTMLInputElement | null)?.focus()}
                                            >
                                                <input
                                                    className="myapps-domain-chip-input"
                                                    disabled={isBindDialogSubmitting}
                                                    placeholder="admin@example.com"
                                                    type="email"
                                                    value={certificateEmail}
                                                    onChange={(e) => setCertificateEmail(e.target.value)}
                                                />
                                            </div>
                                            <p className="myapps-domain-chip-helper">{t('myAppsDetailPage.accessPanel.certificateEmailHint')}</p>
                                        </div>
                                    )}
                                    {bindDialogCertAction === 'upload' && (
                                        <div className="myapps-bind-cert-subform myapps-bind-cert-subform-panel">
                                            <label className="myapps-domain-field-label" style={{ color: palette.text }}>
                                                {t('myAppsDetailPage.accessPanel.customCertName')}
                                                <span className="myapps-field-required">*</span>
                                            </label>
                                            <div
                                                className="myapps-domain-chip-box"
                                                onClick={(e) => (e.currentTarget.querySelector('input') as HTMLInputElement | null)?.focus()}
                                            >
                                                <input
                                                    className="myapps-domain-chip-input"
                                                    disabled={isBindDialogSubmitting}
                                                    placeholder="my-site.com"
                                                    value={customCertName}
                                                    onChange={(e) => {
                                                        setIsCustomCertNameAuto(false)
                                                        setCustomCertName(e.target.value)
                                                    }}
                                                />
                                            </div>
                                            <div className="myapps-bind-cert-upload-grid">
                                                <div className="myapps-bind-cert-upload-field">
                                                    <div className="myapps-bind-cert-upload-head">
                                                        <label className="myapps-domain-field-label" style={{ color: palette.text }}>
                                                            {t('myAppsDetailPage.accessPanel.customCertKey')}
                                                            <span className="myapps-field-required">*</span>
                                                        </label>
                                                        <button
                                                            className="myapps-bind-upload-btn"
                                                            disabled={isBindDialogSubmitting}
                                                            onClick={() => customCertKeyFileRef.current?.click()}
                                                            title={t('myAppsDetailPage.accessPanel.uploadFile')}
                                                            type="button"
                                                        >
                                                            <IconUploadFile />
                                                        </button>
                                                        <input
                                                            accept=".pem,.key,.crt,.cer,.txt"
                                                            hidden
                                                            onChange={(event) => void handlePemFilePick(event, setCustomCertKeyPem)}
                                                            ref={customCertKeyFileRef}
                                                            type="file"
                                                        />
                                                    </div>
                                                    <div
                                                        className="myapps-domain-chip-box myapps-bind-cert-textarea-shell"
                                                        onClick={(e) => (e.currentTarget.querySelector('textarea') as HTMLTextAreaElement | null)?.focus()}
                                                    >
                                                        <textarea
                                                            className="myapps-domain-chip-input myapps-bind-cert-textarea"
                                                            disabled={isBindDialogSubmitting}
                                                            placeholder="-----BEGIN PRIVATE KEY-----"
                                                            rows={4}
                                                            value={customCertKeyPem}
                                                            onChange={(e) => setCustomCertKeyPem(e.target.value)}
                                                        />
                                                    </div>
                                                </div>
                                                <div className="myapps-bind-cert-upload-field">
                                                    <div className="myapps-bind-cert-upload-head">
                                                        <label className="myapps-domain-field-label" style={{ color: palette.text }}>
                                                            {t('myAppsDetailPage.accessPanel.customCertPem')}
                                                            <span className="myapps-field-required">*</span>
                                                        </label>
                                                        <button
                                                            className="myapps-bind-upload-btn"
                                                            disabled={isBindDialogSubmitting}
                                                            onClick={() => customCertPemFileRef.current?.click()}
                                                            title={t('myAppsDetailPage.accessPanel.uploadFile')}
                                                            type="button"
                                                        >
                                                            <IconUploadFile />
                                                        </button>
                                                        <input
                                                            accept=".pem,.crt,.cer,.txt"
                                                            hidden
                                                            onChange={(event) => void handlePemFilePick(event, setCustomCertPem)}
                                                            ref={customCertPemFileRef}
                                                            type="file"
                                                        />
                                                    </div>
                                                    <div
                                                        className="myapps-domain-chip-box myapps-bind-cert-textarea-shell"
                                                        onClick={(e) => (e.currentTarget.querySelector('textarea') as HTMLTextAreaElement | null)?.focus()}
                                                    >
                                                        <textarea
                                                            className="myapps-domain-chip-input myapps-bind-cert-textarea"
                                                            disabled={isBindDialogSubmitting}
                                                            placeholder="-----BEGIN CERTIFICATE-----"
                                                            rows={4}
                                                            value={customCertPem}
                                                            onChange={(e) => setCustomCertPem(e.target.value)}
                                                        />
                                                    </div>
                                                </div>
                                            </div>
                                            <p className="myapps-domain-chip-helper">{t('myAppsDetailPage.accessPanel.uploadCertHint')}</p>
                                            <p className="myapps-domain-chip-helper">{t('myAppsDetailPage.accessPanel.customCertPassphraseHint')}</p>
                                            <div className="myapps-bind-cert-upload-field">
                                                <div className="myapps-bind-cert-upload-head">
                                                    <label className="myapps-domain-field-label" style={{ color: palette.text }}>{t('myAppsDetailPage.accessPanel.customCertIntermediate')}</label>
                                                    <button
                                                        className="myapps-bind-upload-btn"
                                                        disabled={isBindDialogSubmitting}
                                                        onClick={() => customCertIntermediateFileRef.current?.click()}
                                                        title={t('myAppsDetailPage.accessPanel.uploadFile')}
                                                        type="button"
                                                    >
                                                        <IconUploadFile />
                                                    </button>
                                                    <input
                                                        accept=".pem,.crt,.cer,.txt"
                                                        hidden
                                                        onChange={(event) => void handlePemFilePick(event, setCustomCertIntermediate)}
                                                        ref={customCertIntermediateFileRef}
                                                        type="file"
                                                    />
                                                </div>
                                                <div
                                                    className="myapps-domain-chip-box myapps-bind-cert-textarea-shell"
                                                    onClick={(e) => (e.currentTarget.querySelector('textarea') as HTMLTextAreaElement | null)?.focus()}
                                                >
                                                    <textarea
                                                        className="myapps-domain-chip-input myapps-bind-cert-textarea"
                                                        disabled={isBindDialogSubmitting}
                                                        placeholder="-----BEGIN CERTIFICATE-----"
                                                        rows={3}
                                                        value={customCertIntermediate}
                                                        onChange={(e) => setCustomCertIntermediate(e.target.value)}
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                    <div className="myapps-bind-cert-switch myapps-bind-force-https-switch">
                                        <div className="myapps-bind-https-label">
                                            <span className="myapps-bind-https-label-title">{t('myAppsDetailPage.accessPanel.forceHttpsLabel')}</span>
                                            <span className="myapps-bind-https-label-desc">{t('myAppsDetailPage.accessPanel.forceHttpsHelper')}</span>
                                        </div>
                                        <Switch
                                            checked={bindDialogForceHttps}
                                            disabled={isBindDialogSubmitting || (bindDialogCertAction === 'existing' && bindDialogCertId === null)}
                                            onChange={(e) => setBindDialogForceHttps(e.target.checked)}
                                            size="small"
                                        />
                                    </div>
                                </>
                            ) : null}
                        </div>
                    </div>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.5, py: 1.5, borderTop: `1px solid ${palette.divider}`, backgroundColor: palette.dialogBg }}>
                    <Button
                        disabled={isBindDialogSubmitting}
                        onClick={handleCloseBindDialog}
                        sx={{
                            minWidth: 84, borderRadius: 0, boxShadow: 'none',
                            border: `1px solid ${palette.borderStrong}`,
                            backgroundColor: palette.actionBg, color: palette.subtleText,
                            '&:hover': { backgroundColor: palette.actionHover, color: palette.text, boxShadow: 'none' },
                        }}
                    >
                        {t('myAppsDetailPage.accessPanel.cancel')}
                    </Button>
                    <Button
                        disabled={isBindDialogSubmitting || !canSubmitBindDialogWithTarget}
                        onClick={() => void handleBindDialogSubmit()}
                        sx={{ minWidth: 112, borderRadius: 0, boxShadow: 'none', '&:hover': { boxShadow: 'none' } }}
                        variant="contained"
                    >
                        {isBindDialogSubmitting ? <CircularProgress color="inherit" size={16} /> : t('myAppsDetailPage.accessPanel.saveConfig')}
                    </Button>
                </Box>
            </SurfaceDialog>

            <SurfaceDialog
                onClose={() => { if (!isDeleting) setShowDeleteConfirm(false) }}
                open={showDeleteConfirm}
                scope="content"
                scopeRect={scopeRect ?? null}
                contentStrategy="viewport-fixed"
                darkMode={isDarkMode}
                sx={{ zIndex: 1510 }}
                paperSx={{
                    maxWidth: '480px',
                    borderRadius: 0,
                    backgroundColor: palette.dialogBg,
                    color: palette.text,
                    border: `1px solid ${palette.borderStrong}`,
                    boxShadow: isDarkMode ? '0 24px 64px rgba(2,6,23,0.56)' : '0 16px 40px rgba(15,23,42,0.16)',
                }}
            >
                <Box sx={{ px: 2.25, py: 1.5, borderBottom: `1px solid ${palette.divider}`, backgroundColor: palette.warningSoft }}>
                    <Typography sx={{ fontSize: 16, fontWeight: 700, color: palette.warning }}>
                        {t('myAppsDetailPage.accessPanel.deleteConfirmTitle')}
                    </Typography>
                </Box>
                <Box sx={{ px: 2.25, py: 2, borderBottom: `1px solid ${palette.divider}` }}>
                    <Typography sx={{ m: 0, fontSize: 14, lineHeight: 1.7, color: palette.subtleText }}>
                        {t('myAppsDetailPage.accessPanel.deleteConfirmDescription', {
                            domains: currentDomains.join(', ') || '-',
                        })}
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.25, py: 1.25 }}>
                    <Button
                        disabled={isDeleting}
                        onClick={() => setShowDeleteConfirm(false)}
                        sx={{
                            minWidth: 68, borderRadius: 0, boxShadow: 'none',
                            border: `1px solid ${palette.borderStrong}`,
                            backgroundColor: palette.actionBg, color: palette.subtleText,
                            '&:hover': { backgroundColor: palette.actionHover, color: palette.text, boxShadow: 'none' },
                        }}
                    >
                        {t('myAppsDetailPage.accessPanel.cancel')}
                    </Button>
                    <Button
                        disabled={isDeleting}
                        onClick={() => void handleDelete()}
                        sx={{
                            minWidth: 68, borderRadius: 0, boxShadow: 'none',
                            backgroundColor: '#ffbc00', border: '1px solid #ffbc00', color: '#313a46',
                            '&:hover': { backgroundColor: '#e0a700', border: '1px solid #e0a700', boxShadow: 'none' },
                        }}
                        variant="contained"
                    >
                        {isDeleting ? <CircularProgress color="inherit" size={16} /> : t('myAppsDetailPage.accessPanel.deleteDomain')}
                    </Button>
                </Box>
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
