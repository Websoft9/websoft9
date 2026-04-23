import { Alert, Box, Button, Chip, CircularProgress, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useMyAppAccess } from './use-my-app-access'

type MyAppAccessPanelProps = {
    appId: string
    entryDomains: string[]
    isWebApp: boolean
    onUpdated: () => Promise<void> | void
}

type AccessFeedback = {
    severity: 'success' | 'error'
    message: string
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

async function parseJsonError(response: Response, fallbackMessage: string) {
    try {
        const payload = (await response.json()) as { details?: string; message?: string }
        return payload.details || payload.message || fallbackMessage
    } catch {
        return fallbackMessage
    }
}

export function MyAppAccessPanel({ appId, entryDomains, isWebApp, onUpdated }: MyAppAccessPanelProps) {
    const { t } = useTranslation('shell')
    const [domainInputValue, setDomainInputValue] = useState('')
    const [selectedCertificateId, setSelectedCertificateId] = useState('0')
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [feedback, setFeedback] = useState<AccessFeedback | null>(null)
    const { data, error, isLoading, refetch, isFetching } = useMyAppAccess(appId, isWebApp)

    const currentDomains = useMemo(() => {
        const proxyDomains = data?.proxyHosts.flatMap((host) => host.domain_names) ?? []
        const mergedDomains = proxyDomains.length > 0 ? proxyDomains : entryDomains

        return Array.from(new Set(mergedDomains.map((item) => item.trim()).filter(Boolean)))
    }, [data?.proxyHosts, entryDomains])

    useEffect(() => {
        setDomainInputValue(currentDomains.join('\n'))
    }, [currentDomains])

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

    if (!isWebApp) {
        return <Alert severity="info" variant="outlined">{t('myAppsDetailPage.accessPanel.notWebApp')}</Alert>
    }

    return (
        <Stack spacing={2} sx={{ mt: 2 }}>
            {isLoading ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <CircularProgress size={18} />
                    <Typography color="text.secondary" variant="body2">
                        {t('myAppsDetailPage.accessPanel.loading')}
                    </Typography>
                </Box>
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

            {feedback ? (
                <Alert severity={feedback.severity} variant="outlined">
                    {feedback.message}
                </Alert>
            ) : null}

            {data?.proxyHosts.length && data.proxyHosts.length > 1 ? (
                <Alert severity="info" variant="outlined">
                    {t('myAppsDetailPage.accessPanel.multipleHosts')}
                </Alert>
            ) : null}

            <Box>
                <Typography sx={{ fontWeight: 600 }}>{t('myAppsDetailPage.accessPanel.currentDomains')}</Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1, mt: 1 }}>
                    {currentDomains.length > 0 ? (
                        currentDomains.map((domain) => <Chip component="a" clickable href={getAccessHref(domain)} key={domain} label={domain} target="_blank" />)
                    ) : (
                        <Typography color="text.secondary" variant="body2">
                            {t('myAppsDetailPage.accessPanel.emptyDomains')}
                        </Typography>
                    )}
                </Stack>
            </Box>

            <Box>
                <Typography sx={{ fontWeight: 600 }}>{t('myAppsDetailPage.accessPanel.certificateStatus')}</Typography>
                <Typography color="text.secondary" sx={{ mt: 1 }} variant="body2">
                    {data ? t('myAppsDetailPage.accessPanel.certificateCount', { count: data.certificates.length }) : '-'}
                </Typography>
            </Box>

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

            {data?.proxyHosts[0]?.certificate_name ? (
                <Alert severity="info" variant="outlined">
                    {t('myAppsDetailPage.accessPanel.boundCertificate', {
                        name: data.proxyHosts[0].certificate_name,
                    })}
                </Alert>
            ) : null}

            <TextField
                fullWidth
                helperText={t('myAppsDetailPage.accessPanel.helper')}
                label={t('myAppsDetailPage.accessPanel.inputLabel')}
                minRows={4}
                multiline
                onChange={(event) => setDomainInputValue(event.target.value)}
                value={domainInputValue}
            />

            <Stack direction="row" spacing={1}>
                <Button disabled={isSubmitting} onClick={() => void handleSubmit()} variant="contained">
                    {isSubmitting ? t('myAppsDetailPage.actions.running') : t('myAppsDetailPage.accessPanel.save')}
                </Button>
                {isFetching && !isLoading ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <CircularProgress size={16} />
                        <Typography color="text.secondary" variant="body2">
                            {t('myAppsDetailPage.accessPanel.refreshing')}
                        </Typography>
                    </Box>
                ) : null}
            </Stack>
        </Stack>
    )
}