import { Accordion, AccordionDetails, AccordionSummary, Alert, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, FormControlLabel, IconButton, Snackbar, Switch, TextField } from '@mui/material'
import type { ReactNode } from 'react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useMyAppAccess } from './use-my-app-access'

type MyAppAccessPanelProps = {
    appId: string
    env?: Record<string, string>
    isComposeApp: boolean
    onUpdated: () => Promise<void> | void
}

type AccessFeedback = {
    severity: 'success' | 'error'
    message: string
}

type DomainTagEditorProps = {
    label?: string
    helperText: string
    placeholder: string
    value: string[]
    onChange: (nextValue: string[]) => void
    actions?: ReactNode
}

type PickerOption = {
    value: string
    title: string
    description?: string
}

type AccountEntry = {
    key: string
    value: string
    isPassword: boolean
}

function IconDelete() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M6 7h12l-1 14H7L6 7zm3-3h6l1 2h4v2H4V6h4l1-2z" /></svg>
}

function IconExpandMore() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z" /></svg>
}

function IconEdit() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zm2.92 2.33H5v-.92l8.06-8.06.92.92L5.92 19.58zM20.71 7.04a1.003 1.003 0 0 0 0-1.42L18.37 3.29a1.003 1.003 0 0 0-1.42 0l-1.83 1.83 3.75 3.75 1.84-1.83z" /></svg>
}

function IconSave() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M17 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7l-4-4zM7 5h8v4H7V5zm12 14H5V5h1v6h10V5h.17L19 7.83V19zm-7-1a4 4 0 1 1 0-8 4 4 0 0 1 0 8z" /></svg>
}

function IconCancel() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm5 13.59L15.59 17 12 13.41 8.41 17 7 15.59 10.59 12 7 8.41 8.41 7 12 10.59 15.59 7 17 8.41 13.41 12z" /></svg>
}

function IconEye() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M12 5c-5 0-9.27 3.11-11 7 1.73 3.89 6 7 11 7s9.27-3.11 11-7c-1.73-3.89-6-7-11-7zm0 12a5 5 0 1 1 0-10 5 5 0 0 1 0 10zm0-2.2A2.8 2.8 0 1 0 12 9.2a2.8 2.8 0 0 0 0 5.6z" /></svg>
}

function IconEyeOff() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="m3.28 2 18.72 18.72-1.41 1.41-3.02-3.02A12.72 12.72 0 0 1 12 20c-5 0-9.27-3.11-11-7a12.67 12.67 0 0 1 4.32-5.04L1.86 3.41 3.28 2zm6.1 6.1 1.53 1.53A2.96 2.96 0 0 0 9 12c0 1.66 1.34 3 3 3 .52 0 1.01-.13 1.44-.37l1.53 1.53A4.93 4.93 0 0 1 12 17a5 5 0 0 1-5-5c0-1.13.37-2.18 1-3.1zm2.98-2.04A5 5 0 0 1 17 11c0 .72-.15 1.4-.42 2.02l3.1 3.1A12.82 12.82 0 0 0 23 13c-1.73-3.89-6-7-11-7-1.58 0-3.1.31-4.48.88l2.31 2.31A4.98 4.98 0 0 1 12 7c.12 0 .24 0 .36.01z" /></svg>
}

function IconCopy() {
    return <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M16 1H4a2 2 0 0 0-2 2v12h2V3h12V1zm4 4H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H8V7h12v14z" /></svg>
}

function normalizeDomains(value: string) {
    return Array.from(new Set(value.split(/[\s,]+/).map((item) => item.trim()).filter(Boolean)))
}

const REQUEST_NEW_CERTIFICATE_VALUE = '__request_new_certificate__'

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

function DomainTagEditor({ label, helperText, placeholder, value, onChange, actions }: DomainTagEditorProps) {
    const [inputValue, setInputValue] = useState('')

    function commit(rawValue: string) {
        const nextValue = Array.from(new Set([
            ...value,
            ...normalizeDomains(rawValue).filter(isDomainBindingValue),
        ]))
        if (nextValue.length !== value.length) {
            onChange(nextValue)
        }
        setInputValue('')
    }

    function removeTag(tag: string) {
        onChange(value.filter((item) => item !== tag))
    }

    return (
        <div className="myapps-domain-editor">
            {label ? <div className="myapps-domain-editor-label">{label}</div> : null}
            <div className="myapps-domain-editor-row">
                <div className="myapps-domain-editor-shell">
                    {value.map((tag) => (
                        <Chip className="myapps-domain-editor-chip" key={tag} label={tag} onDelete={() => removeTag(tag)} size="small" />
                    ))}
                    <input
                        className="myapps-domain-editor-input"
                        onBlur={() => {
                            if (inputValue.trim()) commit(inputValue)
                        }}
                        onChange={(event) => setInputValue(event.target.value)}
                        onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ',' || event.key === ' ') {
                                event.preventDefault()
                                commit(inputValue)
                                return
                            }
                            if (event.key === 'Backspace' && !inputValue && value.length > 0) {
                                event.preventDefault()
                                removeTag(value[value.length - 1])
                            }
                        }}
                        placeholder={value.length === 0 ? placeholder : ''}
                        type="text"
                        value={inputValue}
                    />
                </div>
                {actions ? <div className="myapps-domain-editor-actions">{actions}</div> : null}
            </div>
            <div className="myapps-domain-editor-helper">{helperText}</div>
        </div>
    )
}

function InlineOptionPicker({
    emptyDescription,
    helperText,
    label,
    menuPlacement = 'bottom',
    onSelect,
    open,
    options,
    selectedValue,
    setOpen,
}: {
    emptyDescription?: string
    helperText?: string
    label?: string
    menuPlacement?: 'bottom' | 'top'
    onSelect: (value: string) => void
    open: boolean
    options: PickerOption[]
    selectedValue: string
    setOpen: (open: boolean) => void
}) {
    const selectedOption = selectedValue ? options.find((option) => option.value === selectedValue) ?? null : null
    const selectedCopy = selectedOption?.description ?? (!selectedOption ? emptyDescription || '' : '')

    return (
        <div className="myapps-access-picker-shell">
            <button
                className={`myapps-access-picker-trigger ${open ? 'is-open' : ''}`}
                onClick={() => setOpen(!open)}
                type="button"
            >
                <div className="myapps-access-select-option">
                    {label ? <span className="myapps-access-select-option-label">{label}</span> : null}
                    <span className="myapps-access-select-option-title">{selectedOption?.title ?? ''}</span>
                    {selectedCopy ? <span className="myapps-access-select-option-copy">{selectedCopy}</span> : null}
                </div>
                <span className={`myapps-access-picker-icon ${open ? 'is-open' : ''}`}>
                    <IconExpandMore />
                </span>
            </button>
            {open ? (
                <div className={`myapps-access-picker-menu ${menuPlacement === 'top' ? 'is-top' : ''}`}>
                    {options.map((option) => (
                        <button
                            className={`myapps-access-picker-option ${option.value === selectedValue ? 'is-selected' : ''}`}
                            key={option.value}
                            onClick={() => {
                                onSelect(option.value)
                                setOpen(false)
                            }}
                            type="button"
                        >
                            <div className="myapps-access-select-option">
                                <span className="myapps-access-select-option-title">{option.title}</span>
                                {option.description ? <span className="myapps-access-select-option-copy">{option.description}</span> : null}
                            </div>
                        </button>
                    ))}
                </div>
            ) : null}
            {helperText ? <div className="myapps-access-picker-helper">{helperText}</div> : null}
        </div>
    )
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

export function MyAppAccessPanel({ appId, env, isComposeApp, onUpdated }: MyAppAccessPanelProps) {
    const { t, i18n } = useTranslation('shell')
    const navigate = useNavigate()
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const [selectedProxyId, setSelectedProxyId] = useState<number | null>(null)
    const [selectedCertificateId, setSelectedCertificateId] = useState('0')
    const [selectedCandidateKey, setSelectedCandidateKey] = useState('')
    const [selectedContainerName, setSelectedContainerName] = useState('')
    const [selectedTargetPort, setSelectedTargetPort] = useState('')
    const [selectedScheme, setSelectedScheme] = useState<'http' | 'https'>('http')
    const [domainDrafts, setDomainDrafts] = useState<string[]>([])
    const [certificateEmail, setCertificateEmail] = useState('')
    const [forceHttps, setForceHttps] = useState(false)
    const [isCertificateMenuOpen, setIsCertificateMenuOpen] = useState(false)
    const [isTargetMenuOpen, setIsTargetMenuOpen] = useState(false)
    const [isPortMenuOpen, setIsPortMenuOpen] = useState(false)
    const [isSchemeMenuOpen, setIsSchemeMenuOpen] = useState(false)
    const [isEditingDomains, setIsEditingDomains] = useState(false)
    const [isEditingCertificate, setIsEditingCertificate] = useState(false)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [isDeleting, setIsDeleting] = useState(false)
    const [isRequestingCertificate, setIsRequestingCertificate] = useState(false)
    const [feedback, setFeedback] = useState<AccessFeedback | null>(null)
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
    const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({})
    const { data, error, isLoading, refetch, isFetching } = useMyAppAccess(appId)
    const proxyHosts = data?.proxy_hosts ?? []
    const currentProxyHost = proxyHosts.find((host) => host.proxy_id === selectedProxyId) ?? proxyHosts[0] ?? null
    const previewProxyHost = proxyHosts[0] ?? null
    const currentProfile = data?.profile
    const hostName = typeof window !== 'undefined' ? window.location.hostname : ''

    const currentDomains = useMemo(() => {
        const domains = currentProxyHost?.domain_names ?? []
        return Array.from(new Set(domains.map((item) => item.trim()).filter(isDomainBindingValue)))
    }, [currentProxyHost])
    const previewDomains = useMemo(() => {
        const domains = previewProxyHost?.domain_names ?? []
        return Array.from(new Set(domains.map((item) => item.trim()).filter(isDomainBindingValue)))
    }, [previewProxyHost])
    const previewDomain = previewDomains[0] ?? null

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
    const previewScheme = previewProxyHost?.certificate_id ? 'https' : currentProfile?.forward_scheme ?? 'http'
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
    const certificateOptions = useMemo(() => {
        const existingOptions = availableCertificates.map((certificate) => ({
            value: String(certificate.id),
            title: certificate.nice_name || certificate.domain_names?.join(', ') || `#${certificate.id}`,
        }))

        return [
            ...existingOptions,
            {
                value: REQUEST_NEW_CERTIFICATE_VALUE,
                title: t('myAppsDetailPage.accessPanel.requestNewCertificate'),
            },
            {
                value: '0',
                title: t('myAppsDetailPage.accessPanel.noCertificate'),
            },
        ]
    }, [availableCertificates, t])
    const selectedCertificateOption = useMemo(() => {
        return certificateOptions.find((option) => option.value === selectedCertificateId) ?? certificateOptions[certificateOptions.length - 1] ?? null
    }, [certificateOptions, selectedCertificateId])
    const candidateOptions = useMemo<PickerOption[]>(() => {
        const seen = new Set<string>()
        return (data?.candidates ?? []).flatMap((candidate) => {
            if (seen.has(candidate.container_name)) {
                return []
            }
            seen.add(candidate.container_name)
            return [{
                value: candidate.container_name,
                title: candidate.container_name,
            }]
        })
    }, [data?.candidates])
    const portOptions = useMemo<PickerOption[]>(() => {
        return (data?.candidates ?? [])
            .filter((candidate) => candidate.container_name === selectedContainerName)
            .map((candidate) => ({
                value: String(candidate.forward_port),
                title: String(candidate.forward_port),
            }))
    }, [data?.candidates, selectedContainerName])
    const schemeOptions = useMemo<PickerOption[]>(() => ([
        { value: 'http', title: 'HTTP' },
        { value: 'https', title: 'HTTPS' },
    ]), [])
    const isRequestingNewCertificate = selectedCertificateId === REQUEST_NEW_CERTIFICATE_VALUE
    const isEditingSettings = isEditingDomains || isEditingCertificate

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
        setDomainDrafts(currentDomains)
    }, [currentDomains])

    useEffect(() => {
        setSelectedCertificateId(String(currentProxyHost?.certificate_id ?? 0))
    }, [currentProxyHost?.certificate_id])

    useEffect(() => {
        if (!isEditingDomains) {
            setDomainDrafts(currentDomains)
        }
    }, [currentDomains, isEditingDomains])

    useEffect(() => {
        if (!isEditingCertificate) {
            setSelectedCertificateId(String(currentProxyHost?.certificate_id ?? 0))
            setCertificateEmail('')
        }
    }, [currentProxyHost?.certificate_id, isEditingCertificate])

    useEffect(() => {
        setForceHttps(Boolean(currentProxyHost?.ssl_forced && currentProxyHost?.certificate_id))
    }, [currentProxyHost?.certificate_id, currentProxyHost?.ssl_forced])

    useEffect(() => {
        if (!isEditingSettings) {
            setIsCertificateMenuOpen(false)
            setIsTargetMenuOpen(false)
            setIsPortMenuOpen(false)
            setIsSchemeMenuOpen(false)
        }
    }, [isEditingSettings])

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

    async function ensureDomainBinding(nextDomains: string[], certificateId: number | null, sslForced: boolean) {
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
                proxy_id: currentProxyHost?.proxy_id ?? null,
            }),
        })

        if (!response.ok) {
            throw new Error(await parseJsonError(response, `Failed to save access settings: ${response.status}`))
        }

        return response.json() as Promise<{ proxy_id?: number }>
    }

    async function handleSubmit() {
        const nextDomains = domainDrafts
        if (nextDomains.length === 0) {
            setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.validation') })
            return
        }
        if (forceHttps && selectedCertificateId === '0') {
            setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.forceHttpsRequiresCertificate') })
            return
        }

        setIsSubmitting(true)
        setFeedback(null)

        try {
            await persistProfileSelection()
            const binding = await ensureDomainBinding(nextDomains, selectedCertificateId === '0' ? null : Number(selectedCertificateId), forceHttps)
            if (binding.proxy_id) {
                setSelectedProxyId(binding.proxy_id)
            }

            await refetch()
            await onUpdated()
            setIsEditingDomains(false)
            setIsEditingCertificate(false)
            setFeedback({
                severity: 'success',
                message: t(currentProxyHost ? 'myAppsDetailPage.accessPanel.updateSuccess' : 'myAppsDetailPage.accessPanel.createSuccess'),
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
            setIsEditingDomains(false)
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

    async function handleRequestCertificate() {
        const nextDomains = domainDrafts
        if (nextDomains.length === 0) {
            setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.validation') })
            return
        }
        if (!certificateEmail.trim()) {
            setFeedback({ severity: 'error', message: t('myAppsDetailPage.accessPanel.emailValidation') })
            return
        }

        setIsRequestingCertificate(true)
        setFeedback(null)

        try {
            await persistProfileSelection()
            if (!currentProxyHost) {
                const binding = await ensureDomainBinding(nextDomains, null, forceHttps)
                if (binding.proxy_id) {
                    setSelectedProxyId(binding.proxy_id)
                }
            }

            const bindingResult = await refetch()
            const proxyId = bindingResult.data?.proxy_hosts?.find((host) => host.proxy_id === selectedProxyId)?.proxy_id
                ?? currentProxyHost?.proxy_id
                ?? bindingResult.data?.proxy_hosts?.[0]?.proxy_id
                ?? null
            const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/access/certificates/letsencrypt`, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: certificateEmail.trim(),
                    domain_names: nextDomains,
                    proxy_id: proxyId,
                }),
            })

            if (!response.ok) {
                throw new Error(await parseJsonError(response, `Failed to request certificate: ${response.status}`))
            }

            const certificate = await response.json() as { id?: number }
            if (certificate.id) {
                setSelectedCertificateId(String(certificate.id))
            }
            await refetch()
            setIsEditingCertificate(false)
            setFeedback({
                severity: 'success',
                message: proxyId ? t('myAppsDetailPage.accessPanel.certificateIssuedAndBound') : t('myAppsDetailPage.accessPanel.certificateIssued'),
            })
        } catch (requestError) {
            setFeedback({
                severity: 'error',
                message: requestError instanceof Error ? requestError.message : t('myAppsDetailPage.accessPanel.certificateFailed'),
            })
        } finally {
            setIsRequestingCertificate(false)
        }
    }

    async function handleSettingsSubmit() {
        if (selectedCertificateId === REQUEST_NEW_CERTIFICATE_VALUE) {
            await handleRequestCertificate()
            return
        }

        await handleSubmit()
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
                            <div className="myapps-access-card-body">
                                <div className="myapps-access-settings-group">
                                    {isEditingSettings ? (
                                        <div className="myapps-access-editor-enter myapps-access-settings-editor">
                                            <div className="myapps-access-settings-editor-header">
                                                <span className="myapps-access-settings-title">{t('myAppsDetailPage.accessPanel.domainAccessTitle')}</span>
                                                <div className="myapps-domain-editor-actions">
                                                    <IconButton disabled={isSubmitting || isRequestingCertificate || (showTargetSection && !selectedCandidateKey)} onClick={() => void handleSettingsSubmit()} size="small" title={t('myAppsDetailPage.accessPanel.save')}>
                                                        {(isSubmitting || isRequestingCertificate) ? <CircularProgress size={16} /> : <IconSave />}
                                                    </IconButton>
                                                    <IconButton disabled={isSubmitting || isDeleting || isRequestingCertificate} onClick={() => {
                                                        setIsEditingDomains(false)
                                                        setIsEditingCertificate(false)
                                                        setDomainDrafts(currentDomains)
                                                        setSelectedCertificateId(String(currentProxyHost?.certificate_id ?? 0))
                                                        setForceHttps(Boolean(currentProxyHost?.ssl_forced && currentProxyHost?.certificate_id))
                                                        setIsCertificateMenuOpen(false)
                                                        setIsTargetMenuOpen(false)
                                                        setIsPortMenuOpen(false)
                                                        setIsSchemeMenuOpen(false)
                                                        setCertificateEmail('')
                                                    }} size="small" title={t('myAppsDetailPage.accessPanel.cancel')}>
                                                        <IconCancel />
                                                    </IconButton>
                                                    {currentProxyHost ? (
                                                        <IconButton disabled={isSubmitting || isDeleting || isRequestingCertificate} onClick={() => setShowDeleteConfirm(true)} size="small" title={t('myAppsDetailPage.accessPanel.deleteDomain')}>
                                                            {isDeleting ? <CircularProgress size={16} /> : <IconDelete />}
                                                        </IconButton>
                                                    ) : null}
                                                </div>
                                            </div>

                                            {showTargetSection ? (
                                                <div className="myapps-access-settings-field">
                                                    <span className="myapps-access-settings-field-label">{t('myAppsDetailPage.accessPanel.targetSelectLabel')}</span>
                                                    <div className="myapps-access-target-inline-grid">
                                                        <InlineOptionPicker
                                                            emptyDescription={t('myAppsDetailPage.accessPanel.composeDefinitionRequired')}
                                                            label={t('myAppsDetailPage.accessPanel.targetContainerLabel')}
                                                            onSelect={(value) => {
                                                                setSelectedContainerName(value)
                                                                setIsTargetMenuOpen(false)
                                                            }}
                                                            open={isTargetMenuOpen}
                                                            options={candidateOptions}
                                                            selectedValue={selectedContainerName}
                                                            setOpen={setIsTargetMenuOpen}
                                                        />
                                                        <InlineOptionPicker
                                                            emptyDescription={t('myAppsDetailPage.accessPanel.targetPortDescription')}
                                                            label={t('myAppsDetailPage.accessPanel.targetPortLabel')}
                                                            onSelect={(value) => setSelectedTargetPort(value)}
                                                            open={isPortMenuOpen}
                                                            options={portOptions}
                                                            selectedValue={selectedTargetPort}
                                                            setOpen={setIsPortMenuOpen}
                                                        />
                                                        <InlineOptionPicker
                                                            label={t('myAppsDetailPage.accessPanel.schemeLabel')}
                                                            onSelect={(value) => setSelectedScheme(value as 'http' | 'https')}
                                                            open={isSchemeMenuOpen}
                                                            options={schemeOptions}
                                                            selectedValue={selectedScheme}
                                                            setOpen={setIsSchemeMenuOpen}
                                                        />
                                                    </div>
                                                </div>
                                            ) : null}

                                            <div className="myapps-access-settings-field">
                                                <span className="myapps-access-settings-field-label">{t('myAppsDetailPage.accessPanel.inputLabel')}</span>
                                                <DomainTagEditor
                                                    helperText={t('myAppsDetailPage.accessPanel.helper')}
                                                    onChange={setDomainDrafts}
                                                    placeholder={t('myAppsDetailPage.accessPanel.domainPlaceholder')}
                                                    value={domainDrafts}
                                                />
                                            </div>

                                            <div className="myapps-access-settings-field">
                                                <span className="myapps-access-settings-field-label">{t('myAppsDetailPage.accessPanel.certificateSelectLabel')}</span>
                                                <div className={`myapps-access-target-grid ${isRequestingNewCertificate ? '' : 'myapps-access-target-grid-single'}`}>
                                                    <InlineOptionPicker
                                                        emptyDescription={t('myAppsDetailPage.accessPanel.certificateSelectPlaceholder')}
                                                        helperText={availableCertificates.length > 0 ? t('myAppsDetailPage.accessPanel.certificateCount', { count: availableCertificates.length }) : t('myAppsDetailPage.accessPanel.certificateEmptyHint')}
                                                        menuPlacement="top"
                                                        onSelect={(value) => {
                                                            setSelectedCertificateId(value)
                                                            setIsEditingCertificate(true)
                                                            if (value === '0') {
                                                                setForceHttps(false)
                                                            }
                                                        }}
                                                        open={isCertificateMenuOpen}
                                                        options={certificateOptions}
                                                        selectedValue={selectedCertificateOption?.value || selectedCertificateId}
                                                        setOpen={setIsCertificateMenuOpen}
                                                    />
                                                    {isRequestingNewCertificate ? (
                                                        <TextField
                                                            className="myapps-access-form-control"
                                                            fullWidth
                                                            label={t('myAppsDetailPage.accessPanel.certificateEmailLabel')}
                                                            onChange={(event) => setCertificateEmail(event.target.value)}
                                                            placeholder="admin@example.com"
                                                            size="small"
                                                            value={certificateEmail}
                                                        />
                                                    ) : null}
                                                </div>
                                            </div>

                                            <div className="myapps-access-settings-field">
                                                <span className="myapps-access-settings-field-label">{t('myAppsDetailPage.accessPanel.forceHttpsLabel')}</span>
                                                <div className="myapps-access-toggle-field">
                                                    <FormControlLabel
                                                        control={<Switch checked={forceHttps} disabled={selectedCertificateId === '0'} onChange={(event) => setForceHttps(event.target.checked)} size="small" />}
                                                        label=""
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="myapps-access-settings-summary">
                                            <div className="myapps-access-settings-summary-main">
                                                {proxyHosts.length > 0 ? proxyHosts.map((host) => {
                                                    const hostDomains = host.domain_names.filter(isDomainBindingValue)
                                                    const hostCertificate = host.certificate_name || formatCertificateLabel(data?.certificates.find((certificate) => certificate.id === host.certificate_id))

                                                    return (
                                                        <div className="myapps-access-binding-item" key={host.proxy_id}>
                                                            <div className="myapps-access-binding-content">
                                                                <div className="myapps-access-settings-field myapps-access-settings-field-summary">
                                                                    <span className="myapps-access-settings-field-label">{t('myAppsDetailPage.accessPanel.inputLabel')}</span>
                                                                    <div className="myapps-access-status-values">
                                                                        {hostDomains.length > 0 ? hostDomains.map((domain) => (
                                                                            <Chip className="myapps-access-status-chip" key={domain} label={domain} size="small" />
                                                                        )) : <span className="myapps-access-inline-empty">{t('myAppsDetailPage.accessPanel.emptyDomains')}</span>}
                                                                    </div>
                                                                </div>
                                                                <div className="myapps-access-settings-field myapps-access-settings-field-summary">
                                                                    <span className="myapps-access-settings-field-label">{t('myAppsDetailPage.accessPanel.certificateSelectLabel')}</span>
                                                                    <div className="myapps-access-status-copy">
                                                                        <span>{hostCertificate || t('myAppsDetailPage.accessPanel.noCertificateBound')}</span>
                                                                        {host.ssl_forced ? <span>{t('myAppsDetailPage.accessPanel.forceHttpsEnabled')}</span> : null}
                                                                    </div>
                                                                </div>
                                                            </div>
                                                            <button className="myapps-inline-icon-action" onClick={() => {
                                                                setSelectedProxyId(host.proxy_id)
                                                                setIsEditingDomains(true)
                                                                setIsEditingCertificate(true)
                                                            }} type="button">
                                                                <IconEdit />
                                                                <span>{t('myAppsDetailPage.accessPanel.editSettings')}</span>
                                                            </button>
                                                        </div>
                                                    )
                                                }) : (
                                                    <div className="myapps-access-settings-field myapps-access-settings-field-summary">
                                                        <span className="myapps-access-settings-field-label">{t('myAppsDetailPage.accessPanel.inputLabel')}</span>
                                                        <div className="myapps-access-status-values">
                                                            <span className="myapps-access-inline-empty">{t('myAppsDetailPage.accessPanel.emptyDomains')}</span>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>

                                            {proxyHosts.length === 0 ? (
                                                <button className="myapps-inline-icon-action" onClick={() => {
                                                    setSelectedProxyId(null)
                                                    setIsEditingDomains(true)
                                                    setIsEditingCertificate(true)
                                                }} type="button">
                                                    <IconEdit />
                                                    <span>{t('myAppsDetailPage.accessPanel.editSettings')}</span>
                                                </button>
                                            ) : null}
                                        </div>
                                    )}
                                </div>

                                <div className="myapps-access-form">
                                    {isFetching && !isLoading ? (
                                        <div className="myapps-access-refreshing">
                                            <CircularProgress size={16} />
                                            <span>{t('myAppsDetailPage.accessPanel.refreshing')}</span>
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        </div>
                    </AccordionDetails>
                </Accordion>
            ) : null}

            {showDomainAccessSection && (previewDomain || frontendHref || backendHref) ? (
                <Accordion defaultExpanded className="myapps-access-accordion">
                    <AccordionSummary expandIcon={<IconExpandMore />}>
                        <div className="myapps-access-summary-copy">
                            <label className="myapps-access-summary-title">
                                {currentDomains.length > 0 ? t('myAppsDetailPage.accessPanel.previewTitle') : t('myAppsDetailPage.accessPanel.noDomainAccessTitle')}
                            </label>
                            <span className="myapps-access-summary-desc">
                                {currentDomains.length > 0 ? t('myAppsDetailPage.accessPanel.previewDescription') : t('myAppsDetailPage.accessPanel.noDomainAccessDescription')}
                            </span>
                        </div>
                    </AccordionSummary>
                    <AccordionDetails>
                        <div className="myapps-card myapps-access-card">
                            <div className="myapps-access-card-body">
                                {previewDomain ? (
                                    <div className="myapps-access-link-stack">
                                        <div className="myapps-access-link-group">
                                            <div className="myapps-access-link-row">
                                                <span className="myapps-access-link-label">{t('myAppsDetailPage.accessPanel.frontend')}</span>
                                                <a href={`${previewScheme}://${previewDomain}`} target="_blank" rel="noreferrer">{`${previewScheme}://${previewDomain}`}</a>
                                            </div>
                                            {env?.W9_ADMIN_PATH ? (
                                                <div className="myapps-access-link-row">
                                                    <span className="myapps-access-link-label">{t('myAppsDetailPage.accessPanel.backend')}</span>
                                                    <a href={`${previewScheme}://${previewDomain}${env.W9_ADMIN_PATH}`} target="_blank" rel="noreferrer">{`${previewScheme}://${previewDomain}${env.W9_ADMIN_PATH}`}</a>
                                                </div>
                                            ) : null}
                                        </div>
                                    </div>
                                ) : (
                                    <div className="myapps-access-link-stack">
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
                                )}
                            </div>
                        </div>
                    </AccordionDetails>
                </Accordion>
            ) : null}

            {accountEntries.length > 0 ? (
                <Accordion defaultExpanded={!currentProfile?.enabled} className="myapps-access-accordion">
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

            <Dialog onClose={() => {
                if (!isDeleting) setShowDeleteConfirm(false)
            }} open={showDeleteConfirm}>
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
            </Dialog>

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
