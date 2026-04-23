import {
    Alert,
    Box,
    Button,
    CircularProgress,
    Divider,
    Paper,
    Stack,
    TextField,
    Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

type SettingsSummaryItem = {
    group: string
    key: string
    value: string
    sensitive: boolean
    masked: boolean
    editable: boolean
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
    const { t } = useTranslation('shell')
    const [drafts, setDrafts] = useState<Record<string, string>>({})
    const [savingKey, setSavingKey] = useState<string | null>(null)
    const [feedback, setFeedback] = useState<{ severity: 'success' | 'error'; message: string } | null>(null)
    const { data, error, isLoading, refetch, isFetching } = useQuery<SettingsSummaryResponse, SettingsError>({
        queryKey: ['settings-summary'],
        queryFn: fetchSettingsSummary,
        staleTime: 5_000,
    })

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
        } catch (saveError) {
            setFeedback({
                severity: 'error',
                message: saveError instanceof Error ? saveError.message : t('settingsPage.feedback.saveError'),
            })
        } finally {
            setSavingKey(null)
        }
    }

    return (
        <Box
            sx={{
                minHeight: 'calc(100vh - 120px)',
                px: { xs: 0.5, md: 1 },
                py: { xs: 1, md: 1.5 },
            }}
        >
            <Stack spacing={3}>
                <Stack spacing={1.5}>
                    <Typography color="text.secondary" sx={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.6 }}>
                        {t('settingsPage.hero.eyebrow')}
                    </Typography>
                    <Typography component="h1" sx={{ fontSize: { xs: 28, md: 32 }, fontWeight: 500, lineHeight: 1.1 }}>
                        {t('settingsPage.hero.title')}
                    </Typography>
                    <Typography color="text.secondary" variant="body1">
                        {t('settingsPage.hero.description')}
                    </Typography>
                </Stack>

                {feedback ? <Alert severity={feedback.severity} variant="outlined">{feedback.message}</Alert> : null}

                {error ? (
                    <Alert
                        action={
                            <Button color="inherit" onClick={() => void refetch()} size="small">
                                {t('settingsPage.states.retry')}
                            </Button>
                        }
                        severity="warning"
                        variant="outlined"
                    >
                        {t('settingsPage.states.loadError', { statusCode: error.statusCode ?? 'unknown' })}
                    </Alert>
                ) : null}

                {isLoading ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <CircularProgress size={18} />
                        <Typography color="text.secondary" variant="body2">
                            {t('settingsPage.states.loading')}
                        </Typography>
                    </Box>
                ) : null}

                <Box
                    sx={{
                        display: 'grid',
                        gap: 2,
                        gridTemplateColumns: { xs: '1fr', xl: 'repeat(2, minmax(0, 1fr))' },
                    }}
                >
                    {data?.groups.map((group) => (
                        <Paper
                            elevation={0}
                            key={group.id}
                            sx={{
                                p: 2.5,
                                border: '1px solid rgba(15, 23, 42, 0.08)',
                                backgroundColor: '#f9fbfd',
                            }}
                        >
                            <Stack divider={<Divider flexItem />} spacing={2.5}>
                                <Stack spacing={0.75}>
                                    <Typography sx={{ fontSize: 18, fontWeight: 600 }}>
                                        {t(`settingsPage.groups.${group.id}.title`)}
                                    </Typography>
                                    <Typography color="text.secondary" variant="body2">
                                        {t(`settingsPage.groups.${group.id}.description`)}
                                    </Typography>
                                </Stack>

                                {group.items.map((item) => {
                                    const draftKey = `${item.group}.${item.key}`
                                    const currentValue = drafts[draftKey] ?? (item.masked ? '' : item.value)
                                    const isSaving = savingKey === draftKey

                                    return (
                                        <Stack key={draftKey} spacing={1}>
                                            <Typography sx={{ fontWeight: 600 }}>
                                                {t(`settingsPage.items.${item.group}.${item.key}`, { defaultValue: `${item.group}.${item.key}` })}
                                            </Typography>
                                            <Typography color="text.secondary" variant="body2">
                                                {item.value || t('settingsPage.values.notConfigured')}
                                            </Typography>
                                            {item.editable ? (
                                                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.25}>
                                                    <TextField
                                                        fullWidth
                                                        helperText={item.masked ? t('settingsPage.values.maskedHelper') : undefined}
                                                        onChange={(event) =>
                                                            setDrafts((currentDrafts) => ({
                                                                ...currentDrafts,
                                                                [draftKey]: event.target.value,
                                                            }))
                                                        }
                                                        placeholder={t('settingsPage.actions.editValue')}
                                                        size="small"
                                                        value={currentValue}
                                                    />
                                                    <Button disabled={isSaving} onClick={() => void handleSave(item)} variant="contained">
                                                        {isSaving ? t('settingsPage.actions.saving') : t('settingsPage.actions.save')}
                                                    </Button>
                                                </Stack>
                                            ) : (
                                                <Typography color="text.secondary" variant="caption">
                                                    {item.sensitive ? t('settingsPage.values.readOnlySensitive') : t('settingsPage.values.readOnly')}
                                                </Typography>
                                            )}
                                        </Stack>
                                    )
                                })}
                            </Stack>
                        </Paper>
                    ))}
                </Box>

                {isFetching && !isLoading ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <CircularProgress size={16} />
                        <Typography color="text.secondary" variant="body2">
                            {t('settingsPage.states.refreshing')}
                        </Typography>
                    </Box>
                ) : null}
            </Stack>
        </Box>
    )
}