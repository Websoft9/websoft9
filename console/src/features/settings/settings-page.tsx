import {
    Alert,
    Box,
    Button,
    CircularProgress,
    Chip,
    IconButton,
    Paper,
    Stack,
    Switch,
    TextField,
    Typography,
} from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useAppColorMode } from '../../app/providers/color-mode'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import './settings-page.css'

function getSettingsTextFieldSx(isDarkMode: boolean) {
    return {
        '& .MuiOutlinedInput-root': {
            borderRadius: '4px',
            height: 38,
            backgroundColor: isDarkMode ? '#0f172a' : '#ffffff',
        },
        '& .MuiOutlinedInput-root.Mui-disabled': {
            backgroundColor: isDarkMode ? '#162033' : '#f8fafc',
        },
        '& .MuiInputBase-input': {
            fontSize: 14,
            fontWeight: 400,
            color: isDarkMode ? '#e5edf5' : '#334155',
        },
        '& .MuiInputBase-input::placeholder': {
            fontSize: 14,
            fontWeight: 400,
            color: isDarkMode ? '#64748b' : '#94a3b8',
            opacity: 1,
        },
    } as const
}

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
        default_certificate?: string
        certificate_validity_days?: string
    } | null
}

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

function RefreshIcon() {
    return (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
            <path d="M17.65 6.35A7.95 7.95 0 0 0 12 4a8 8 0 1 0 7.75 10h-2.08A6 6 0 1 1 12 6c1.3 0 2.5.42 3.47 1.13L13 10h7V3l-2.35 3.35Z" />
        </svg>
    )
}

const PLATFORM_GATEWAY_CERTIFICATES_BROWSER_PATH = '/volumes/platform-gateway-certificates'

export function SettingsPage() {
    const { t, i18n } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const isDarkMode = colorMode === 'dark'
    const navigate = useNavigate()
    const queryClient = useQueryClient()
    const [drafts, setDrafts] = useState<Record<string, string>>({})
    const [mirrorPendingInputs, setMirrorPendingInputs] = useState<Record<string, string>>({})
    const [editingKey, setEditingKey] = useState<string | null>(null)
    const [savingKey, setSavingKey] = useState<string | null>(null)
    const [feedback, setFeedback] = useState<{ severity: 'success' | 'error'; message: string } | null>(null)
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
    const versionItem = items.find((item) => item.group === 'version' && item.key === 'product') ?? null
    const isDefaultCertificate = httpsItem?.metadata?.default_certificate === 'true'
    function handleOpenCertificateDirectory() {
        navigate(`/files?path=${encodeURIComponent(PLATFORM_GATEWAY_CERTIFICATES_BROWSER_PATH)}`)
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

        setSavingKey(draftKey)
        setFeedback(null)

        try {
            await updateSetting(item.group, item.key, nextValue)
            await refetch()
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

    async function handleGatewayToggle(item: SettingsSummaryItem | null, checked: boolean) {
        if (!item) {
            return
        }

        const draftKey = `${item.group}.${item.key}`
        setSavingKey(draftKey)
        setFeedback(null)

        try {
            await updateSetting(item.group, item.key, checked ? 'true' : 'false')
            if (item.key === 'https_enabled' && !checked && window.location.protocol === 'https:') {
                window.setTimeout(() => {
                    const nextUrl = new URL(window.location.href)
                    nextUrl.protocol = 'http:'
                    window.location.replace(nextUrl.toString())
                }, 800)
                setFeedback({ severity: 'success', message: t('settingsPage.feedback.httpsDisabledRedirecting') })
                return
            }
            await refreshSettingsSummaryAfterGatewayRestart()
            setFeedback({ severity: 'success', message: t('settingsPage.feedback.httpsSuccess') })
        } catch (saveError) {
            setFeedback({
                severity: 'error',
                message: saveError instanceof Error ? saveError.message : t('settingsPage.feedback.httpsError'),
            })
        } finally {
            setSavingKey(null)
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

    function renderEditableRow(item: SettingsSummaryItem | null, options?: { labelKey?: string; helperText?: string }) {
        if (!item) {
            return null
        }

        const draftKey = `${item.group}.${item.key}`
        const isEditing = editingKey === draftKey
        const isSaving = savingKey === draftKey
        const currentValue = drafts[draftKey] ?? (item.masked ? '' : item.value)

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
                            value={isEditing ? currentValue : item.value}
                            onChange={(event) =>
                                setDrafts((currentDrafts) => ({
                                    ...currentDrafts,
                                    [draftKey]: event.target.value,
                                }))
                            }
                            disabled={!isEditing}
                            placeholder={t('settingsPage.actions.editValue')}
                            sx={getSettingsTextFieldSx(isDarkMode)}
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
                            {typeof item.metadata?.default_value === 'string' ? (
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
        const summary = isDefaultCertificate
            ? t('settingsPage.https.defaultCertificate')
            : t('settingsPage.https.customCertificate')

        return (
            <div className="settings-form-row">
                <Typography className="settings-form-label">{t('settingsPage.items.platform_gateway.certificates')}：</Typography>

                <div className="settings-form-control">
                    <div className="settings-inline-content settings-inline-content--summary">
                        <Typography className="settings-form-value settings-form-value--muted" variant="body2">
                            {summary}
                        </Typography>
                        <Typography className="settings-field-helper settings-field-helper--inline">{t('settingsPage.certificates.helper')}</Typography>
                    </div>
                </div>

                <div className="settings-form-actions">
                    <Button className="settings-action-button" onClick={handleOpenCertificateDirectory} size="small" variant="outlined">
                        {t('settingsPage.actions.configure')}
                    </Button>
                </div>
            </div>
        )
    }

    function renderHttpsOptionsRow() {
        const httpsSaving = savingKey === `${httpsItem?.group}.${httpsItem?.key}`
        const forceSaving = savingKey === `${forceHttpsItem?.group}.${forceHttpsItem?.key}`
        const httpsEnabled = httpsItem?.value === 'true'

        return (
            <div className="settings-form-row">
                <Typography className="settings-form-label">{t('settingsPage.items.platform_gateway.httpsOptions')}：</Typography>

                <div className="settings-form-control settings-form-control--field settings-form-control--switches">
                    <Box className="settings-switch-stack">
                        <Box className="settings-switch-item settings-switch-item--rowless">
                            <Typography className="settings-switch-label">{t('settingsPage.items.platform_gateway.https_enabled')}</Typography>
                            <Stack className="settings-form-switch" direction="row" spacing={1.25}>
                                <Switch checked={httpsItem?.value === 'true'} disabled={httpsSaving} onChange={(_, nextChecked) => void handleGatewayToggle(httpsItem, nextChecked)} />
                                <Typography color="text.secondary" sx={{ fontWeight: 500 }} variant="body2">
                                    {httpsItem?.value === 'true' ? t('settingsPage.https.enabled') : t('settingsPage.https.disabled')}
                                </Typography>
                            </Stack>
                            <Typography className="settings-field-helper settings-field-helper--switch">{t('settingsPage.platformSsl.httpsHelper')}</Typography>
                        </Box>
                        <Box className="settings-switch-item settings-switch-item--rowless">
                            <Typography className="settings-switch-label">{t('settingsPage.items.platform_gateway.force_https')}</Typography>
                            <Stack className="settings-form-switch" direction="row" spacing={1.25}>
                                <Switch checked={forceHttpsItem?.value === 'true'} disabled={forceSaving || !httpsEnabled} onChange={(_, nextChecked) => void handleGatewayToggle(forceHttpsItem, nextChecked)} />
                                <Typography color="text.secondary" sx={{ fontWeight: 500 }} variant="body2">
                                    {forceHttpsItem?.value === 'true' ? t('settingsPage.https.enabled') : t('settingsPage.https.disabled')}
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

                <Box className="settings-page-grid">
                    <Box className="settings-panels-grid">
                        <Paper className="settings-panel" elevation={0}>
                            <Box className="settings-panel-header">
                                <Typography className="settings-panel-title">{t('settingsPage.sections.platform.title')}</Typography>
                            </Box>

                            <Box className="settings-form-table">
                                {renderEditableRow(boundDomainItem, { helperText: t('settingsPage.domain.boundDomainHelper') })}
                                {renderHttpsOptionsRow()}
                                {renderCertificateRow()}
                            </Box>
                        </Paper>

                        <Paper className="settings-panel" elevation={0}>
                            <Box className="settings-panel-header">
                                <Typography className="settings-panel-title">{t('settingsPage.sections.applications.title')}</Typography>
                            </Box>

                            <Box className="settings-form-table">
                                {renderEditableRow(globalDomainItem, { helperText: t('settingsPage.domain.globalDomainHelper') })}
                                {renderMirrorRow(mirrorItem)}
                            </Box>
                        </Paper>

                        <Paper className="settings-panel settings-panel--system" elevation={0}>
                            <Box className="settings-panel-header settings-panel-header--with-action">
                                <Box>
                                    <Typography className="settings-panel-title">{t('settingsPage.sections.system.title')}</Typography>
                                </Box>
                                <IconButton className="settings-toolbar-icon-button settings-header-icon-button" onClick={() => void refetch()} disabled={isFetching} size="small" title={t('settingsPage.actions.refresh')}>
                                    {isFetching ? <CircularProgress size={14} color="inherit" /> : <RefreshIcon />}
                                </IconButton>
                            </Box>

                            <Box className="settings-form-table">
                                {renderVersionRow()}
                                {renderUpgradeRow()}
                            </Box>
                        </Paper>
                    </Box>
                </Box>

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