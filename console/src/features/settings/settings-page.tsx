import {
    Alert,
    Box,
    Button,
    CircularProgress,
    Stack,
    Switch,
    TextField,
    Typography,
} from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

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

export function SettingsPage() {
    const { t, i18n } = useTranslation('shell')
    const queryClient = useQueryClient()
    const [drafts, setDrafts] = useState<Record<string, string>>({})
    const [editingKey, setEditingKey] = useState<string | null>(null)
    const [savingKey, setSavingKey] = useState<string | null>(null)
    const [feedback, setFeedback] = useState<{ severity: 'success' | 'error'; message: string } | null>(null)
    const { data, error, isLoading, refetch, isFetching } = useQuery<SettingsSummaryResponse, SettingsError>({
        queryKey: ['settings-summary'],
        queryFn: fetchSettingsSummary,
        staleTime: 5_000,
    })
    const items = data?.groups.flatMap((group) => group.items) ?? []
    const domainItem = items.find((item) => item.group === 'domain' && item.key === 'wildcard_domain') ?? null
    const httpsItem = items.find((item) => item.group === 'platform_gateway' && item.key === 'https_enabled') ?? null
    const versionItem = items.find((item) => item.group === 'version' && item.key === 'product') ?? null

    function startEditing(item: SettingsSummaryItem) {
        const draftKey = `${item.group}.${item.key}`
        setDrafts((currentDrafts) => ({
            ...currentDrafts,
            [draftKey]: item.masked ? '' : item.value,
        }))
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

    async function handleHttpsToggle(checked: boolean) {
        if (!httpsItem) {
            return
        }

        const draftKey = `${httpsItem.group}.${httpsItem.key}`
        setSavingKey(draftKey)
        setFeedback(null)

        try {
            await updateSetting(httpsItem.group, httpsItem.key, checked ? 'true' : 'false')
            if (!checked && window.location.protocol === 'https:') {
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

    function renderEditableRow(item: SettingsSummaryItem | null) {
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
                    {t(`settingsPage.items.${item.group}.${item.key}`, { defaultValue: `${item.group}.${item.key}` })}：
                </Typography>

                <div className="settings-form-control">
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
                        sx={{
                            '& .MuiOutlinedInput-root': {
                                backgroundColor: isEditing ? '#ffffff' : '#f8fafc',
                            },
                        }}
                    />
                </div>

                <Stack className="settings-form-actions" direction="row" spacing={0.75}>
                    {isEditing ? (
                        <>
                            <Button disabled={isSaving} onClick={() => void handleSave(item)} size="small" variant="contained">
                                {t('settingsPage.actions.save')}
                            </Button>
                            <Button disabled={isSaving} onClick={() => cancelEditing(item)} size="small" variant="text">
                                {t('settingsPage.actions.cancel')}
                            </Button>
                        </>
                    ) : (
                        <Button onClick={() => startEditing(item)} size="small" variant="text">
                            {t('settingsPage.actions.edit')}
                        </Button>
                    )}
                </Stack>
            </div>
        )
    }

    function renderHttpsRow(item: SettingsSummaryItem | null) {
        if (!item) {
            return null
        }

        const draftKey = `${item.group}.${item.key}`
        const isSaving = savingKey === draftKey
        const checked = item.value === 'true'

        return (
            <div className="settings-form-row" key={draftKey}>
                <Typography className="settings-form-label">
                    {t(`settingsPage.items.${item.group}.${item.key}`)}：
                </Typography>

                <Stack className="settings-form-control settings-form-switch" direction="row" spacing={1.5}>
                    <Switch checked={checked} disabled={isSaving} onChange={(_, nextChecked) => void handleHttpsToggle(nextChecked)} />
                    <Typography color="text.secondary" sx={{ fontWeight: 500 }} variant="body2">
                        {checked ? t('settingsPage.https.enabled') : t('settingsPage.https.disabled')}
                    </Typography>
                </Stack>

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

                <div className="settings-form-actions">
                    <Typography className="settings-form-meta" variant="body2">
                        {t('settingsPage.upgrade.comingSoon')}
                    </Typography>
                </div>
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
            <Stack spacing={2}>
                <div className="settings-page-header">
                    <div>
                        <Typography className="settings-page-title" component="h1">
                            {t('settingsPage.hero.title')}
                        </Typography>
                    </div>

                    {isFetching ? (
                        <div className="settings-page-status">
                            <CircularProgress size={16} />
                            <Typography color="text.secondary" variant="body2">
                                {t('settingsPage.states.refreshing')}
                            </Typography>
                        </div>
                    ) : null}
                </div>

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

                <div className="settings-form-shell">
                    <div className="settings-form-table">
                        {renderEditableRow(domainItem)}
                        {renderHttpsRow(httpsItem)}
                        {renderUpgradeRow()}
                        {renderVersionRow()}
                    </div>
                </div>
            </Stack>
        </Box>
    )
}