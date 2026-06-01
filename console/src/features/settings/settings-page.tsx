import {
    Alert,
    Box,
    Button,
    CircularProgress,
    Chip,
    IconButton,
    List,
    ListItemButton,
    Paper,
    Stack,
    Switch,
    TextField,
    Typography,
} from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useAppColorMode } from '../../app/providers/color-mode'
import { getSurfaceFieldSx } from '../../shared/design-system/form-field-sx'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { getSurfacePalette } from '../../shared/design-system/surface-theme'
import './settings-page.css'

type SettingsSummaryItem = {
    group: string
    key: string
    value: string
    sensitive: boolean
    masked: boolean
    editable: boolean
    metadata?: {
        version?: string
        edition_key?: string
        edition_names?: Record<string, string>
        default_value?: string
        cert_path?: string
        key_path?: string
        default_cert_path?: string
        default_key_path?: string
        default_certificate?: string
        certificate_validity_days?: string
    } | null
}

type PlatformGatewayUpdateRequest = {
    bound_domain: string
    https_enabled: string
    force_https: string
    ssl_cert: string
    ssl_key: string
}

type PlatformSslAction = 'default' | 'existing' | 'upload'

type SettingsSummaryGroup = {
    id: string
    items: SettingsSummaryItem[]
}

type SettingsSummaryResponse = {
    groups: SettingsSummaryGroup[]
}

type SettingsError = Error & {
    statusCode?: number
}

async function fetchSettingsSummary() {
    const response = await fetch('/api/settings/summary', {
        credentials: 'include',
        headers: {
            Accept: 'application/json',
        },
    })

    if (!response.ok) {
        const error = new Error(`Failed to load settings summary: ${response.status}`) as SettingsError
        error.statusCode = response.status
        throw error
    }

    return (await response.json()) as SettingsSummaryResponse
}

async function updateSetting(section: string, key: string, value: string) {
    const response = await fetch(`/api/settings/${encodeURIComponent(section)}?key=${encodeURIComponent(key)}&value=${encodeURIComponent(value)}`, {
        method: 'PUT',
        credentials: 'include',
        headers: {
            Accept: 'application/json',
        },
    })

    if (!response.ok) {
        let message = `Failed to update ${section}.${key}: ${response.status}`
        try {
            const payload = (await response.json()) as { details?: string; message?: string }
            message = payload.details || payload.message || message
        } catch {
            // Keep the fallback message.
        }

        throw new Error(message)
    }
}

async function updatePlatformGatewaySettings(payload: PlatformGatewayUpdateRequest) {
    const response = await fetch('/api/settings/platform_gateway/apply', {
        method: 'PUT',
        credentials: 'include',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    })

    if (!response.ok) {
        let message = `Failed to update platform gateway settings: ${response.status}`
        try {
            const errorPayload = (await response.json()) as { details?: string; message?: string }
            message = errorPayload.details || errorPayload.message || message
        } catch {
            // Keep the fallback message.
        }

        throw new Error(message)
    }
}

function RefreshIcon() {
    return (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M17.65 6.35A7.95 7.95 0 0 0 12 4a8 8 0 1 0 7.75 10h-2.08A6 6 0 1 1 12 6c1.3 0 2.5.42 3.47 1.13L13 10h7V3l-2.35 3.35Z" />
        </svg>
    )
}

const PLATFORM_GATEWAY_CERTIFICATES_BROWSER_PATH = '/volumes/platform-gateway-certificates'
const PLATFORM_GATEWAY_CERT_DRAFT_KEY = 'platform_gateway.ssl_cert'
const PLATFORM_GATEWAY_KEY_DRAFT_KEY = 'platform_gateway.ssl_key'
const PLATFORM_GATEWAY_HTTPS_DRAFT_KEY = 'platform_gateway.https_enabled'
const PLATFORM_GATEWAY_FORCE_HTTPS_DRAFT_KEY = 'platform_gateway.force_https'

type SettingsModuleId = 'app-domain' | 'app-mirror' | 'platform-brand' | 'platform-domain' | 'platform-security' | 'platform-system'

type SettingsModuleGroup = 'applications' | 'platform'

type SettingsModule = {
    id: SettingsModuleId
    group: SettingsModuleGroup
    titleKey: string
    descriptionKey: string
}

const SETTINGS_MODULES: SettingsModule[] = [
    {
        id: 'app-domain',
        group: 'applications',
        titleKey: 'settingsPage.modules.appDomain.title',
        descriptionKey: 'settingsPage.modules.appDomain.description',
    },
    {
        id: 'app-mirror',
        group: 'applications',
        titleKey: 'settingsPage.modules.appMirror.title',
        descriptionKey: 'settingsPage.modules.appMirror.description',
    },
    {
        id: 'platform-brand',
        group: 'platform',
        titleKey: 'settingsPage.modules.platformBrand.title',
        descriptionKey: 'settingsPage.modules.platformBrand.description',
    },
    {
        id: 'platform-domain',
        group: 'platform',
        titleKey: 'settingsPage.modules.platformDomain.title',
        descriptionKey: 'settingsPage.modules.platformDomain.description',
    },
    {
        id: 'platform-security',
        group: 'platform',
        titleKey: 'settingsPage.modules.platformSecurity.title',
        descriptionKey: 'settingsPage.modules.platformSecurity.description',
    },
    {
        id: 'platform-system',
        group: 'platform',
        titleKey: 'settingsPage.modules.platformSystem.title',
        descriptionKey: 'settingsPage.modules.platformSystem.description',
    },
]

export function SettingsPage() {
    const { t, i18n } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const isDarkMode = colorMode === 'dark'
    const surfacePalette = getSurfacePalette(isDarkMode)
    const settingsFieldSx = getSurfaceFieldSx(surfacePalette)
    const navigate = useNavigate()
    const queryClient = useQueryClient()
    const [drafts, setDrafts] = useState<Record<string, string>>({})
    const [mirrorPendingInputs, setMirrorPendingInputs] = useState<Record<string, string>>({})
    const [editingKey, setEditingKey] = useState<string | null>(null)
    const [savingKey, setSavingKey] = useState<string | null>(null)
    const [activeModule, setActiveModule] = useState<SettingsModuleId>('app-domain')
    const [feedback, setFeedback] = useState<{ severity: 'success' | 'error'; message: string } | null>(null)
    const [platformSslAction, setPlatformSslAction] = useState<PlatformSslAction>('default')
    const [platformSecuritySaving, setPlatformSecuritySaving] = useState(false)
    const { data, error, isLoading, refetch, isFetching } = useQuery<SettingsSummaryResponse, SettingsError>({
        queryKey: ['settings-summary'],
        queryFn: fetchSettingsSummary,
        staleTime: 5_000,
    })
    const items = data?.groups.flatMap((group) => group.items) ?? []
    const boundDomainItem = items.find((item) => item.group === 'platform_gateway' && item.key === 'bound_domain') ?? null
    const globalDomainItem = items.find((item) => item.group === 'domain' && item.key === 'wildcard_domain') ?? null
    const httpsItem = items.find((item) => item.group === 'platform_gateway' && item.key === 'https_enabled') ?? null
    const forceHttpsItem = items.find((item) => item.group === 'platform_gateway' && item.key === 'force_https') ?? null
    const mirrorItem = items.find((item) => item.group === 'docker_mirror' && item.key === 'url') ?? null
    const brandTitleItem = items.find((item) => item.group === 'platform_brand' && item.key === 'title') ?? null
    const brandLogoItem = items.find((item) => item.group === 'platform_brand' && item.key === 'logo_url') ?? null
    const brandFaviconItem = items.find((item) => item.group === 'platform_brand' && item.key === 'favicon_url') ?? null
    const versionItem = items.find((item) => item.group === 'version' && item.key === 'product') ?? null
    const activeModuleConfig = SETTINGS_MODULES.find((module) => module.id === activeModule) ?? SETTINGS_MODULES[0]
    const defaultPlatformSslCert = httpsItem?.metadata?.default_cert_path?.trim() || httpsItem?.metadata?.cert_path?.trim() || ''
    const defaultPlatformSslKey = httpsItem?.metadata?.default_key_path?.trim() || httpsItem?.metadata?.key_path?.trim() || ''
    const currentSummarySslCert = httpsItem?.metadata?.cert_path?.trim() || defaultPlatformSslCert
    const currentSummarySslKey = httpsItem?.metadata?.key_path?.trim() || defaultPlatformSslKey
    const httpsEnabled = (drafts[PLATFORM_GATEWAY_HTTPS_DRAFT_KEY] ?? httpsItem?.value ?? 'false') === 'true'
    const forceHttpsEnabled = httpsEnabled && (drafts[PLATFORM_GATEWAY_FORCE_HTTPS_DRAFT_KEY] ?? forceHttpsItem?.value ?? 'false') === 'true'
    const currentPlatformSslCert = drafts[PLATFORM_GATEWAY_CERT_DRAFT_KEY] ?? currentSummarySslCert
    const currentPlatformSslKey = drafts[PLATFORM_GATEWAY_KEY_DRAFT_KEY] ?? currentSummarySslKey
    const navGroups = useMemo(
        () => [
            {
                id: 'applications' as const,
                title: t('settingsPage.navigation.groups.applications'),
                modules: SETTINGS_MODULES.filter((module) => module.group === 'applications'),
            },
            {
                id: 'platform' as const,
                title: t('settingsPage.navigation.groups.platform'),
                modules: SETTINGS_MODULES.filter((module) => module.group === 'platform'),
            },
        ],
        [t],
    )

    useEffect(() => {
        const usesDefaultCertificate =
            httpsItem?.metadata?.default_certificate === 'true'
            || (currentSummarySslCert === defaultPlatformSslCert && currentSummarySslKey === defaultPlatformSslKey)

        setPlatformSslAction(usesDefaultCertificate ? 'default' : 'existing')
    }, [httpsItem?.metadata?.default_certificate, currentSummarySslCert, currentSummarySslKey, defaultPlatformSslCert, defaultPlatformSslKey])

    function handleOpenCertificateDirectory() {
        navigate(`/files?path=${encodeURIComponent(PLATFORM_GATEWAY_CERTIFICATES_BROWSER_PATH)}`)
    }

    function resetPlatformSecurityDrafts() {
        setDrafts((currentDrafts) => {
            const nextDrafts = { ...currentDrafts }
            delete nextDrafts[PLATFORM_GATEWAY_CERT_DRAFT_KEY]
            delete nextDrafts[PLATFORM_GATEWAY_KEY_DRAFT_KEY]
            delete nextDrafts[PLATFORM_GATEWAY_HTTPS_DRAFT_KEY]
            delete nextDrafts[PLATFORM_GATEWAY_FORCE_HTTPS_DRAFT_KEY]
            return nextDrafts
        })

        const usesDefaultCertificate =
            httpsItem?.metadata?.default_certificate === 'true'
            || (currentSummarySslCert === defaultPlatformSslCert && currentSummarySslKey === defaultPlatformSslKey)

        setPlatformSslAction(usesDefaultCertificate ? 'default' : 'existing')
    }

    function handleHttpsDraftChange(checked: boolean) {
        setDrafts((currentDrafts) => ({
            ...currentDrafts,
            [PLATFORM_GATEWAY_HTTPS_DRAFT_KEY]: checked ? 'true' : 'false',
            ...(checked ? {} : { [PLATFORM_GATEWAY_FORCE_HTTPS_DRAFT_KEY]: 'false' }),
        }))
    }

    function handleForceHttpsDraftChange(checked: boolean) {
        setDrafts((currentDrafts) => ({
            ...currentDrafts,
            [PLATFORM_GATEWAY_FORCE_HTTPS_DRAFT_KEY]: checked ? 'true' : 'false',
        }))
    }

    function isPlatformBrandLogoUrl(value: string) {
        const trimmed = value.trim()
        if (!trimmed) {
            return false
        }

        if (trimmed.startsWith('/')) {
            return true
        }

        try {
            const parsed = new URL(trimmed)
            return parsed.protocol === 'http:' || parsed.protocol === 'https:'
        } catch {
            return false
        }
    }

    function emitPlatformBrandUpdate(key: string, value: string) {
        window.dispatchEvent(
            new CustomEvent('websoft9:platform-brand-updated', {
                detail: {
                    key,
                    value,
                },
            }),
        )
    }

    function parseMirrorEntries(value: string) {
        return value
            .split(/\r?\n|,/)
            .map((item) => item.trim())
            .filter(Boolean)
    }

    function isMirrorManifestUrl(value: string) {
        const trimmed = value.trim()
        if (!trimmed || /[\r\n,]/.test(trimmed)) {
            return false
        }

        try {
            const parsed = new URL(trimmed)
            return parsed.pathname.endsWith('.json')
        } catch {
            return false
        }
    }

    function startEditing(item: SettingsSummaryItem) {
        const draftKey = `${item.group}.${item.key}`
        setDrafts((currentDrafts) => ({
            ...currentDrafts,
            [draftKey]: item.masked ? '' : item.value,
        }))
        if (item.group === 'docker_mirror' && item.key === 'url') {
            setMirrorPendingInputs((currentInputs) => ({
                ...currentInputs,
                [draftKey]: '',
            }))
        }
        setEditingKey(draftKey)
        setFeedback(null)
    }

    function cancelEditing(item: SettingsSummaryItem) {
        const draftKey = `${item.group}.${item.key}`
        setDrafts((currentDrafts) => {
            const nextDrafts = { ...currentDrafts }
            delete nextDrafts[draftKey]
            return nextDrafts
        })
        setMirrorPendingInputs((currentInputs) => {
            const nextInputs = { ...currentInputs }
            delete nextInputs[draftKey]
            return nextInputs
        })
        if (editingKey === draftKey) {
            setEditingKey(null)
        }
    }

    async function handleSave(item: SettingsSummaryItem) {
        const draftKey = `${item.group}.${item.key}`
        const nextValue = drafts[draftKey] ?? ''

        if (!nextValue.trim()) {
            setFeedback({ severity: 'error', message: t('settingsPage.validation.required') })
            return
        }

        if (item.group === 'docker_mirror' && item.key === 'url') {
            const mirrorEntries = parseMirrorEntries(nextValue)
            if (!isMirrorManifestUrl(nextValue) && !mirrorEntries.length) {
                setFeedback({ severity: 'error', message: t('settingsPage.validation.url') })
                return
            }
        }

        if (item.group === 'platform_brand' && item.key === 'logo_url' && !isPlatformBrandLogoUrl(nextValue)) {
            setFeedback({ severity: 'error', message: t('settingsPage.validation.logoUrl') })
            return
        }

        setSavingKey(draftKey)
        setFeedback(null)

        try {
            await updateSetting(item.group, item.key, nextValue)
            await refetch()
            if (item.group === 'platform_brand') {
                emitPlatformBrandUpdate(item.key, nextValue)
            }
            setFeedback({ severity: 'success', message: t('settingsPage.feedback.saveSuccess', { key: draftKey }) })
            setDrafts((currentDrafts) => {
                const nextDrafts = { ...currentDrafts }
                delete nextDrafts[draftKey]
                return nextDrafts
            })
            setMirrorPendingInputs((currentInputs) => {
                const nextInputs = { ...currentInputs }
                delete nextInputs[draftKey]
                return nextInputs
            })
            if (editingKey === draftKey) {
                setEditingKey(null)
            }
        } catch (saveError) {
            setFeedback({
                severity: 'error',
                message: saveError instanceof Error ? saveError.message : t('settingsPage.feedback.saveError'),
            })
        } finally {
            setSavingKey(null)
        }
    }

    async function handleRestoreDefault(item: SettingsSummaryItem) {
        const defaultValue = typeof item.metadata?.default_value === 'string' ? item.metadata.default_value : ''
        if (!defaultValue) {
            return
        }

        const draftKey = `${item.group}.${item.key}`
        setDrafts((currentDrafts) => ({
            ...currentDrafts,
            [draftKey]: defaultValue,
        }))
        setEditingKey(draftKey)

        setSavingKey(draftKey)
        setFeedback(null)

        try {
            await updateSetting(item.group, item.key, defaultValue)
            await refetch()
            if (item.group === 'platform_brand') {
                emitPlatformBrandUpdate(item.key, defaultValue)
            }
            setFeedback({ severity: 'success', message: t('settingsPage.feedback.saveSuccess', { key: draftKey }) })
            setDrafts((currentDrafts) => {
                const nextDrafts = { ...currentDrafts }
                delete nextDrafts[draftKey]
                return nextDrafts
            })
            setMirrorPendingInputs((currentInputs) => {
                const nextInputs = { ...currentInputs }
                delete nextInputs[draftKey]
                return nextInputs
            })
            if (editingKey === draftKey) {
                setEditingKey(null)
            }
        } catch (saveError) {
            setFeedback({
                severity: 'error',
                message: saveError instanceof Error ? saveError.message : t('settingsPage.feedback.saveError'),
            })
        } finally {
            setSavingKey(null)
        }
    }

    async function handleSavePlatformSecurity() {
        setPlatformSecuritySaving(true)
        setFeedback(null)

        try {
            const nextHttpsEnabled = httpsEnabled ? 'true' : 'false'
            const nextForceHttps = httpsEnabled && forceHttpsEnabled ? 'true' : 'false'
            let nextSslCert = currentPlatformSslCert.trim()
            let nextSslKey = currentPlatformSslKey.trim()

            if (httpsEnabled) {
                if (platformSslAction === 'default' || platformSslAction === 'upload') {
                    nextSslCert = defaultPlatformSslCert
                    nextSslKey = defaultPlatformSslKey
                }

                if (!nextSslCert || !nextSslKey) {
                    throw new Error(t('settingsPage.platformSsl.pathRequired'))
                }
            }

            await updatePlatformGatewaySettings({
                bound_domain: boundDomainItem?.value ?? '',
                https_enabled: nextHttpsEnabled,
                force_https: nextForceHttps,
                ssl_cert: nextSslCert,
                ssl_key: nextSslKey,
            })

            if (nextHttpsEnabled === 'false' && window.location.protocol === 'https:') {
                window.setTimeout(() => {
                    const nextUrl = new URL(window.location.href)
                    nextUrl.protocol = 'http:'
                    window.location.replace(nextUrl.toString())
                }, 800)
                setFeedback({ severity: 'success', message: t('settingsPage.feedback.httpsDisabledRedirecting') })
            } else {
                await refreshSettingsSummaryAfterGatewayRestart()
                setFeedback({ severity: 'success', message: t('settingsPage.feedback.platformGatewaySuccess') })
            }

            resetPlatformSecurityDrafts()
        } catch (saveError) {
            setFeedback({
                severity: 'error',
                message: saveError instanceof Error ? saveError.message : t('settingsPage.feedback.httpsError'),
            })
        } finally {
            setPlatformSecuritySaving(false)
        }
    }

    async function refreshSettingsSummaryAfterGatewayRestart() {
        let lastError: unknown = null

        for (const delayMs of [150, 300, 500, 800, 1200, 1600]) {
            await new Promise((resolve) => window.setTimeout(resolve, delayMs))
            try {
                const summary = await fetchSettingsSummary()
                queryClient.setQueryData(['settings-summary'], summary)
                return
            } catch (error) {
                lastError = error
            }
        }

        throw lastError instanceof Error ? lastError : new Error(t('settingsPage.feedback.httpsError'))
    }

    function renderEditableRow(item: SettingsSummaryItem | null, options?: { labelKey?: string; helperText?: string; placeholder?: string; hideRestore?: boolean; maskDisplayValue?: boolean }) {
        if (!item) {
            return null
        }

        const draftKey = `${item.group}.${item.key}`
        const isEditing = editingKey === draftKey
        const isSaving = savingKey === draftKey
        const currentValue = drafts[draftKey] ?? (item.masked ? '' : item.value)
        const displayValue = options?.maskDisplayValue ? '' : item.value

        return (
            <div className="settings-form-row" key={draftKey}>
                <Typography className="settings-form-label">
                    {options?.labelKey ? t(options.labelKey) : t(`settingsPage.items.${item.group}.${item.key}`, { defaultValue: `${item.group}.${item.key}` })}：
                </Typography>

                <div className="settings-form-control settings-form-control--field">
                    <div className="settings-inline-content">
                        <TextField
                            fullWidth
                            size="small"
                            value={isEditing ? currentValue : displayValue}
                            onChange={(event) =>
                                setDrafts((currentDrafts) => ({
                                    ...currentDrafts,
                                    [draftKey]: event.target.value,
                                }))
                            }
                            disabled={!isEditing}
                            placeholder={options?.placeholder ?? t('settingsPage.actions.editValue')}
                            sx={settingsFieldSx}
                        />
                        {options?.helperText ? <Typography className="settings-field-helper settings-field-helper--inline">{options.helperText}</Typography> : null}
                    </div>
                </div>

                <Stack className="settings-form-actions" direction="row" spacing={0.75}>
                    {isEditing ? (
                        <>
                            <Button className="settings-action-button" disabled={isSaving} onClick={() => void handleSave(item)} size="small" variant="contained">
                                {t('settingsPage.actions.save')}
                            </Button>
                            <Button className="settings-action-button" disabled={isSaving} onClick={() => cancelEditing(item)} size="small" variant="outlined">
                                {t('settingsPage.actions.cancel')}
                            </Button>
                            {!options?.hideRestore && typeof item.metadata?.default_value === 'string' ? (
                                <Button className="settings-action-button" disabled={isSaving} onClick={() => void handleRestoreDefault(item)} size="small" variant="outlined">
                                    {t('settingsPage.actions.restore')}
                                </Button>
                            ) : null}
                        </>
                    ) : (
                        <Button className="settings-action-button" onClick={() => startEditing(item)} size="small" variant="outlined">
                            {t('settingsPage.actions.edit')}
                        </Button>
                    )}
                </Stack>
            </div>
        )
    }

    function renderMirrorRow(item: SettingsSummaryItem | null) {
        if (!item) {
            return null
        }

        const draftKey = `${item.group}.${item.key}`
        const isEditing = editingKey === draftKey
        const isSaving = savingKey === draftKey
        const currentValue = drafts[draftKey] ?? item.value
        const entries = parseMirrorEntries(isEditing ? currentValue : item.value)
        const pendingInput = mirrorPendingInputs[draftKey] ?? ''

        function commitPendingMirrorValue() {
            const nextValue = pendingInput.trim().replace(/,+$/, '')
            if (!nextValue) {
                return
            }

            setDrafts((currentDrafts) => ({
                ...currentDrafts,
                [draftKey]: [...entries, nextValue].join(','),
            }))
            setMirrorPendingInputs((currentInputs) => ({
                ...currentInputs,
                [draftKey]: '',
            }))
        }

        function removeMirrorEntry(entryToRemove: string, indexToRemove: number) {
            const nextEntries = entries.filter((entry, index) => !(entry === entryToRemove && index === indexToRemove))
            setDrafts((currentDrafts) => ({
                ...currentDrafts,
                [draftKey]: nextEntries.join(','),
            }))
        }

        return (
            <div className="settings-form-row" key={`${draftKey}-mirrors`}>
                <Typography className="settings-form-label">{t('settingsPage.items.docker_mirror.url')}：</Typography>

                <div className="settings-form-control settings-form-control--field">
                    <div className="settings-inline-content">
                        {isEditing ? (
                            <Box className="settings-mirror-edit-box">
                                {entries.map((entry, index) => (
                                    <Chip className="settings-mirror-edit-chip" key={`${entry}-${index}`} label={entry} onDelete={() => removeMirrorEntry(entry, index)} size="small" />
                                ))}
                                <input
                                    className="settings-mirror-inline-input"
                                    value={pendingInput}
                                    onBlur={commitPendingMirrorValue}
                                    onChange={(event) => {
                                        setMirrorPendingInputs((currentInputs) => ({
                                            ...currentInputs,
                                            [draftKey]: event.target.value,
                                        }))
                                    }}
                                    onKeyDown={(event) => {
                                        if (event.key === 'Enter' || event.key === ',') {
                                            event.preventDefault()
                                            commitPendingMirrorValue()
                                            return
                                        }

                                        if (event.key === 'Backspace' && !pendingInput && entries.length) {
                                            event.preventDefault()
                                            const lastIndex = entries.length - 1
                                            removeMirrorEntry(entries[lastIndex], lastIndex)
                                        }
                                    }}
                                    placeholder={entries.length ? '' : t('settingsPage.mirror.placeholderInline')}
                                />
                            </Box>
                        ) : (
                            <Box className="settings-mirror-box">
                                {entries.length ? entries.map((entry) => <Box className="settings-mirror-chip" key={entry}>{entry}</Box>) : <Typography className="settings-form-value" variant="body2">{t('settingsPage.values.notConfigured')}</Typography>}
                            </Box>
                        )}
                        <Typography className="settings-field-helper settings-field-helper--inline">{t('settingsPage.mirror.helper')}</Typography>
                    </div>
                </div>

                <Stack className="settings-form-actions" direction="row" spacing={0.75}>
                    {isEditing ? (
                        <>
                            <Button className="settings-action-button" disabled={isSaving} onClick={() => void handleSave(item)} size="small" variant="contained">
                                {t('settingsPage.actions.save')}
                            </Button>
                            <Button className="settings-action-button" disabled={isSaving} onClick={() => cancelEditing(item)} size="small" variant="outlined">
                                {t('settingsPage.actions.cancel')}
                            </Button>
                            <Button className="settings-action-button" disabled={isSaving} onClick={() => void handleRestoreDefault(item)} size="small" variant="outlined">
                                {t('settingsPage.actions.restore')}
                            </Button>
                        </>
                    ) : (
                        <Button className="settings-action-button" onClick={() => startEditing(item)} size="small" variant="outlined">
                            {t('settingsPage.actions.edit')}
                        </Button>
                    )}
                </Stack>
            </div>
        )
    }

    function renderCertificateRow() {
        const saveDisabled = platformSecuritySaving || (httpsEnabled && platformSslAction === 'existing' && (!currentPlatformSslCert.trim() || !currentPlatformSslKey.trim()))

        return (
            <div className="settings-form-row">
                <Typography className="settings-form-label">{t('settingsPage.items.platform_gateway.certificates')}：</Typography>

                <div className="settings-form-control">
                    {httpsEnabled ? (
                        <div className="settings-inline-content settings-inline-content--summary">
                            <div className="settings-choice-grid">
                                <button className={`settings-choice-button ${platformSslAction === 'default' ? 'active' : ''}`} onClick={() => setPlatformSslAction('default')} type="button">
                                    <span className="settings-choice-title">{t('settingsPage.platformSsl.defaultTitle')}</span>
                                    <span className="settings-choice-description">{t('settingsPage.platformSsl.defaultDescription')}</span>
                                    <span className="settings-choice-meta">{t('settingsPage.platformSsl.pathPairLabel', { cert: defaultPlatformSslCert, key: defaultPlatformSslKey })}</span>
                                </button>
                                <button className={`settings-choice-button ${platformSslAction === 'existing' ? 'active' : ''}`} onClick={() => setPlatformSslAction('existing')} type="button">
                                    <span className="settings-choice-title">{t('settingsPage.platformSsl.existingTitle')}</span>
                                    <span className="settings-choice-description">{t('settingsPage.platformSsl.existingDescription')}</span>
                                    <span className="settings-choice-meta">{t('settingsPage.platformSsl.pathPairLabel', { cert: currentSummarySslCert || t('settingsPage.values.notConfigured'), key: currentSummarySslKey || t('settingsPage.values.notConfigured') })}</span>
                                </button>
                                <button className={`settings-choice-button ${platformSslAction === 'upload' ? 'active' : ''}`} onClick={() => setPlatformSslAction('upload')} type="button">
                                    <span className="settings-choice-title">{t('settingsPage.platformSsl.uploadTitle')}</span>
                                    <span className="settings-choice-description">{t('settingsPage.platformSsl.uploadDescription')}</span>
                                    <span className="settings-choice-meta">{PLATFORM_GATEWAY_CERTIFICATES_BROWSER_PATH}</span>
                                </button>
                            </div>

                            {platformSslAction === 'existing' ? (
                                <div className="settings-platform-ssl-detail">
                                    <TextField
                                        fullWidth
                                        size="small"
                                        value={currentPlatformSslCert}
                                        onChange={(event) =>
                                            setDrafts((currentDrafts) => ({
                                                ...currentDrafts,
                                                [PLATFORM_GATEWAY_CERT_DRAFT_KEY]: event.target.value,
                                            }))
                                        }
                                        placeholder={t('settingsPage.platformSsl.certPathPlaceholder')}
                                        sx={settingsFieldSx}
                                    />
                                    <TextField
                                        fullWidth
                                        size="small"
                                        value={currentPlatformSslKey}
                                        onChange={(event) =>
                                            setDrafts((currentDrafts) => ({
                                                ...currentDrafts,
                                                [PLATFORM_GATEWAY_KEY_DRAFT_KEY]: event.target.value,
                                            }))
                                        }
                                        placeholder={t('settingsPage.platformSsl.keyPathPlaceholder')}
                                        sx={settingsFieldSx}
                                    />
                                    <Typography className="settings-field-helper settings-field-helper--inline">{t('settingsPage.platformSsl.existingDetail')}</Typography>
                                </div>
                            ) : null}

                            {platformSslAction === 'upload' ? (
                                <div className="settings-platform-ssl-detail">
                                    <Typography className="settings-field-helper settings-field-helper--inline">{t('settingsPage.platformSsl.uploadDetail')}</Typography>
                                    <Box className="settings-inline-actions">
                                        <Button className="settings-action-button" onClick={handleOpenCertificateDirectory} size="small" variant="outlined">
                                            {t('settingsPage.actions.configure')}
                                        </Button>
                                    </Box>
                                </div>
                            ) : null}
                        </div>
                    ) : (
                        <div className="settings-inline-content settings-inline-content--summary">
                            <Typography className="settings-form-value settings-form-value--muted" variant="body2">
                                {t('settingsPage.platformSsl.disabledHint')}
                            </Typography>
                        </div>
                    )}
                </div>

                <Stack className="settings-form-actions" direction="row" spacing={0.75}>
                    <Button className="settings-action-button" disabled={saveDisabled} onClick={() => void handleSavePlatformSecurity()} size="small" variant="contained">
                        {t('settingsPage.actions.save')}
                    </Button>
                    <Button className="settings-action-button" disabled={platformSecuritySaving} onClick={resetPlatformSecurityDrafts} size="small" variant="outlined">
                        {t('settingsPage.actions.cancel')}
                    </Button>
                </Stack>
            </div>
        )
    }

    function renderHttpsOptionsRow() {
        return (
            <div className="settings-form-row">
                <Typography className="settings-form-label">{t('settingsPage.items.platform_gateway.httpsOptions')}：</Typography>

                <div className="settings-form-control settings-form-control--field settings-form-control--switches">
                    <Box className="settings-switch-stack">
                        <Box className="settings-switch-item settings-switch-item--rowless">
                            <Typography className="settings-switch-label">{t('settingsPage.items.platform_gateway.https_enabled')}</Typography>
                            <Stack className="settings-form-switch" direction="row" spacing={1.25}>
                                <Switch checked={httpsEnabled} disabled={platformSecuritySaving} onChange={(_, nextChecked) => handleHttpsDraftChange(nextChecked)} />
                                <Typography color="text.secondary" sx={{ fontWeight: 500 }} variant="body2">
                                    {httpsEnabled ? t('settingsPage.https.enabled') : t('settingsPage.https.disabled')}
                                </Typography>
                            </Stack>
                            <Typography className="settings-field-helper settings-field-helper--switch">{t('settingsPage.platformSsl.httpsHelper')}</Typography>
                        </Box>
                        <Box className="settings-switch-item settings-switch-item--rowless">
                            <Typography className="settings-switch-label">{t('settingsPage.items.platform_gateway.force_https')}</Typography>
                            <Stack className="settings-form-switch" direction="row" spacing={1.25}>
                                <Switch checked={forceHttpsEnabled} disabled={platformSecuritySaving || !httpsEnabled} onChange={(_, nextChecked) => handleForceHttpsDraftChange(nextChecked)} />
                                <Typography color="text.secondary" sx={{ fontWeight: 500 }} variant="body2">
                                    {forceHttpsEnabled ? t('settingsPage.https.enabled') : t('settingsPage.https.disabled')}
                                </Typography>
                            </Stack>
                            <Typography className="settings-field-helper settings-field-helper--switch">{t('settingsPage.platformSsl.forceHttpsHelper')}</Typography>
                        </Box>
                    </Box>
                </div>

                <div className="settings-form-actions" />
            </div>
        )
    }

    function renderUpgradeRow() {
        return (
            <div className="settings-form-row">
                <Typography className="settings-form-label">
                    {t('settingsPage.upgrade.label')}：
                </Typography>

                <Stack className="settings-form-control" direction={{ xs: 'column', md: 'row' }} spacing={1}>
                    <Button disabled size="small" variant="contained">
                        {t('settingsPage.upgrade.actions.precheck')}
                    </Button>
                    <Button disabled size="small" variant="outlined">
                        {t('settingsPage.upgrade.actions.start')}
                    </Button>
                </Stack>

                <div className="settings-form-actions" />
            </div>
        )
    }

    function renderVersionRow() {
        const locale = i18n.resolvedLanguage === 'zh-CN' ? 'zh-CN' : 'en'
        const localizedEditionName = versionItem?.metadata?.edition_names?.[locale] || versionItem?.metadata?.edition_names?.en || versionItem?.metadata?.edition_names?.['zh-CN'] || ''
        const semanticVersion = versionItem?.metadata?.version || ''
        const displayVersion = `${localizedEditionName} ${semanticVersion}`.trim() || versionItem?.value || t('settingsPage.values.notConfigured')

        return (
            <div className="settings-form-row">
                <Typography className="settings-form-label">
                    {t('settingsPage.version.label')}：
                </Typography>

                <div className="settings-form-control">
                    <Typography className="settings-form-value" variant="body2">
                        {displayVersion}
                    </Typography>
                </div>

                <div className="settings-form-actions" />
            </div>
        )
    }

    function renderActiveModuleRows() {
        if (activeModule === 'app-domain') {
            return renderEditableRow(globalDomainItem, { helperText: t('settingsPage.domain.globalDomainHelper') })
        }

        if (activeModule === 'app-mirror') {
            return renderMirrorRow(mirrorItem)
        }

        if (activeModule === 'platform-brand') {
            return (
                <>
                    {renderEditableRow(brandTitleItem, { helperText: t('settingsPage.brand.titleHelper'), placeholder: t('settingsPage.brand.titlePlaceholder') })}
                    {renderEditableRow(brandLogoItem, { helperText: t('settingsPage.brand.logoHelper'), placeholder: t('settingsPage.brand.logoPlaceholder'), hideRestore: true, maskDisplayValue: true })}
                    {renderEditableRow(brandFaviconItem, { helperText: t('settingsPage.brand.faviconHelper'), placeholder: t('settingsPage.brand.faviconPlaceholder'), hideRestore: true, maskDisplayValue: true })}
                </>
            )
        }

        if (activeModule === 'platform-domain') {
            return renderEditableRow(boundDomainItem, { helperText: t('settingsPage.domain.boundDomainHelper') })
        }

        if (activeModule === 'platform-security') {
            return (
                <>
                    {renderHttpsOptionsRow()}
                    {renderCertificateRow()}
                </>
            )
        }

        return (
            <>
                {renderVersionRow()}
                {renderUpgradeRow()}
            </>
        )
    }

    if (isLoading) {
        return (
            <Box className="settings-page settings-page--loading">
                <CircularProgress size={28} />
                <Typography color="text.secondary" variant="body2">
                    {t('settingsPage.states.loading')}
                </Typography>
            </Box>
        )
    }


    return (
        <Box className="settings-page">
            <Stack spacing={2} sx={{ height: '100%', minHeight: 0 }}>
                <PageDescriptionHeader title={t('nav.settings.label')} description={t('settingsPage.hero.description')} descriptionColor="var(--settings-muted)" />

                <Paper className="settings-shell-card" elevation={0}>
                    <Box className="settings-page-grid">
                        <Box className="settings-nav-panel">
                            <Box className="settings-nav-content">
                                {navGroups.map((group) => (
                                    <Box className="settings-nav-group" key={group.id}>
                                        <Typography className="settings-nav-group-title">{group.title}</Typography>
                                        <List disablePadding className="settings-nav-list">
                                            {group.modules.map((module) => (
                                                <ListItemButton
                                                    className={`settings-nav-item ${activeModule === module.id ? 'active' : ''}`}
                                                    key={module.id}
                                                    onClick={() => setActiveModule(module.id)}
                                                >
                                                    <Typography className="settings-nav-item-label">
                                                        {t(module.titleKey)}
                                                    </Typography>
                                                </ListItemButton>
                                            ))}
                                        </List>
                                    </Box>
                                ))}
                            </Box>
                        </Box>

                        <Paper className="settings-panel settings-panel--module" elevation={0}>
                            <Box className="settings-panel-header settings-panel-header--with-action">
                                <Box className="settings-panel-headline">
                                    <Typography className="settings-panel-title">{t(activeModuleConfig.titleKey)}</Typography>
                                    <Typography className="settings-panel-subtitle">{t(activeModuleConfig.descriptionKey)}</Typography>
                                </Box>
                                <IconButton className="settings-toolbar-icon-button settings-header-icon-button" onClick={() => void refetch()} disabled={isFetching} size="small" title={t('settingsPage.actions.refresh')}>
                                    {isFetching ? <CircularProgress size={14} color="inherit" /> : <RefreshIcon />}
                                </IconButton>
                            </Box>

                            <Box className="settings-form-table">{renderActiveModuleRows()}</Box>
                        </Paper>
                    </Box>
                </Paper>

                {error ? (
                    <Alert severity="error">
                        {error.message}
                    </Alert>
                ) : null}

                {feedback ? (
                    <Alert severity={feedback.severity}>
                        {feedback.message}
                    </Alert>
                ) : null}
            </Stack>
        </Box>
    )
}