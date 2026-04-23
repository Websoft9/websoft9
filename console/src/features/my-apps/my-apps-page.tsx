import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Dialog,
    DialogContent,
    DialogTitle,
    Link,
    Stack,
    TextField,
    Typography,
} from '@mui/material'
import { useMemo, useState } from 'react'
import { Link as RouterLink, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useMyApps, type MyApp, type MyAppLogStage } from './use-my-apps'

type StatusFilter = 'all' | 'installing' | 'active' | 'inactive' | 'error'

const statusFilterOrder: StatusFilter[] = ['all', 'installing', 'active', 'inactive', 'error']

function getStatusFilterKey(status: number): Exclude<StatusFilter, 'all'> | 'active' {
    if (status === 3) {
        return 'installing'
    }

    if (status === 2) {
        return 'inactive'
    }

    if (status === 4) {
        return 'error'
    }

    return 'active'
}

function getStatusChipColor(status: number): 'default' | 'success' | 'warning' | 'error' {
    if (status === 3) {
        return 'warning'
    }

    if (status === 4) {
        return 'error'
    }

    if (status === 1) {
        return 'success'
    }

    return 'default'
}

function getDomainSummary(app: MyApp) {
    return (app.domain_names ?? [])
        .map((entry) => {
            const domainName = entry.domain_name
            const domain = entry.domain

            if (typeof domainName === 'string' && domainName.trim()) {
                return domainName.trim()
            }

            if (typeof domain === 'string' && domain.trim()) {
                return domain.trim()
            }

            return null
        })
        .filter((value): value is string => Boolean(value))
        .join(', ')
}

    function getPrimaryAccessEntry(app: MyApp) {
        return getDomainSummary(app)
        .split(',')
        .map((value) => value.trim())
        .find(Boolean)
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

function getLatestLogLine(logs: MyAppLogStage[] | null | undefined) {
    if (!logs || logs.length === 0) {
        return null
    }

    const lastStage = logs[logs.length - 1]
    const lastLine = lastStage.sub_logs?.filter(Boolean).at(-1)

    if (lastLine) {
        return `${lastStage.title}: ${formatInstallLogLine(lastLine)}`
    }

    return lastStage.title
}

function formatInstallLogLine(value: unknown) {
    if (typeof value === 'string') {
        return value
    }

    if (typeof value === 'number' || typeof value === 'boolean') {
        return String(value)
    }

    if (!value || typeof value !== 'object') {
        return ''
    }

    const entry = value as {
        status?: unknown
        id?: unknown
        message?: unknown
        details?: unknown
        progressDetail?: { current?: unknown; total?: unknown } | null
        progress?: unknown
    }

    const status = typeof entry.status === 'string' ? entry.status : null
    const message = typeof entry.message === 'string' ? entry.message : null
    const details = typeof entry.details === 'string' ? entry.details : null
    const layerId = typeof entry.id === 'string' ? entry.id : null
    const progress =
        entry.progressDetail && typeof entry.progressDetail === 'object'
            ? [entry.progressDetail.current, entry.progressDetail.total]
                  .filter((item) => typeof item === 'number')
                  .join('/')
            : null

    const parts = [status, message, details, layerId ? `#${layerId}` : null, progress ? `(${progress})` : null].filter(Boolean)

    if (parts.length > 0) {
        return parts.join(' ')
    }

    try {
        return JSON.stringify(value)
    } catch {
        return String(value)
    }
}

function formatCreationDate(app: MyApp, locale: string) {
    if (!app.creationDate) {
        return '-'
    }

    const value = app.creationDate > 10_000_000_000 ? app.creationDate : app.creationDate * 1_000

    try {
        return new Intl.DateTimeFormat(locale, {
            dateStyle: 'medium',
            timeStyle: 'short',
        }).format(new Date(value))
    } catch {
        return '-'
    }
}

function getTrackedAlertSeverity(app: MyApp | undefined): 'info' | 'success' | 'error' {
    if (!app) {
        return 'info'
    }

    if (app.status === 4) {
        return 'error'
    }

    if (app.status === 1 || app.status === 2) {
        return 'success'
    }

    return 'info'
}

export function MyAppsPage() {
    const { t, i18n } = useTranslation('shell')
    const [searchParams] = useSearchParams()
    const [searchValue, setSearchValue] = useState('')
    const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
    const [selectedApp, setSelectedApp] = useState<MyApp | null>(null)
    const { data, error, isLoading, isFetching, refetch } = useMyApps()

    const apps = data ?? []
    const trackedAppId = searchParams.get('trackedAppId')
    const trackingId = searchParams.get('trackingId')
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'

    const trackedApp = useMemo(
        () => apps.find((app) => (trackingId ? app.tracking_id === trackingId : false) || (trackedAppId ? app.app_id === trackedAppId : false)),
        [apps, trackedAppId, trackingId],
    )

    const filteredApps = useMemo(() => {
        const normalizedSearch = searchValue.trim().toLowerCase()

        return apps.filter((app) => {
            const matchesFilter = statusFilter === 'all' ? true : getStatusFilterKey(app.status) === statusFilter
            const searchText = [app.app_name, app.app_id, app.app_version, app.error].filter(Boolean).join(' ').toLowerCase()
            const matchesSearch = normalizedSearch ? searchText.includes(normalizedSearch) : true

            return matchesFilter && matchesSearch
        })
    }, [apps, searchValue, statusFilter])

    const counts = useMemo(
        () => ({
            all: apps.length,
            installing: apps.filter((app) => app.status === 3).length,
            active: apps.filter((app) => app.status === 1).length,
            inactive: apps.filter((app) => app.status === 2).length,
            error: apps.filter((app) => app.status === 4).length,
        }),
        [apps],
    )

    return (
        <Box
            sx={{
                minHeight: 'calc(100vh - 120px)',
                px: { xs: 0.5, md: 1 },
                py: { xs: 1, md: 1.5 },
            }}
        >
            <Stack spacing={2.5}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ justifyContent: 'space-between', alignItems: { md: 'center' } }}>
                    <Box>
                        <Typography color="text.secondary" sx={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.6 }}>
                            {t('myAppsPage.hero.eyebrow')}
                        </Typography>
                        <Typography component="h1" sx={{ fontSize: { xs: 28, md: 32 }, fontWeight: 500, lineHeight: 1.1 }}>
                            {t('myAppsPage.hero.title')}
                        </Typography>
                        <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body1">
                            {t('myAppsPage.hero.description')}
                        </Typography>
                    </Box>
                    <Button onClick={() => void refetch()} variant="outlined">
                        {t('myAppsPage.hero.refresh')}
                    </Button>
                </Stack>

                {trackedAppId || trackingId ? (
                    <Alert severity={getTrackedAlertSeverity(trackedApp)} variant="outlined">
                        {trackedApp
                            ? t(`myAppsPage.tracking.${getStatusFilterKey(trackedApp.status)}`, {
                                appId: trackedApp.app_id,
                            })
                            : t('myAppsPage.tracking.pending', {
                                appId: trackedAppId ?? trackingId,
                            })}
                    </Alert>
                ) : null}

                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                    {statusFilterOrder.map((filterKey) => (
                        <Chip
                            key={filterKey}
                            color={statusFilter === filterKey ? 'primary' : 'default'}
                            label={t(`myAppsPage.filters.${filterKey}`, { count: counts[filterKey] })}
                            onClick={() => {
                                setStatusFilter(filterKey)
                            }}
                            variant={statusFilter === filterKey ? 'filled' : 'outlined'}
                        />
                    ))}
                    {isFetching && !isLoading ? <CircularProgress size={18} sx={{ alignSelf: 'center', ml: 0.5 }} /> : null}
                </Stack>

                <TextField
                    fullWidth
                    size="small"
                    placeholder={t('myAppsPage.filters.searchPlaceholder')}
                    value={searchValue}
                    onChange={(event) => {
                        setSearchValue(event.target.value)
                    }}
                />

                {isLoading ? (
                    <Card elevation={0} sx={{ border: '1px solid rgba(15, 23, 42, 0.08)' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1.5, py: 5 }}>
                                <CircularProgress size={28} />
                                <Typography color="text.secondary" variant="body2">
                                    {t('myAppsPage.states.loading')}
                                </Typography>
                            </Box>
                        </CardContent>
                    </Card>
                ) : null}

                {!isLoading && error ? (
                    <Alert
                        action={
                            <Button color="inherit" size="small" onClick={() => void refetch()}>
                                {t('myAppsPage.states.retry')}
                            </Button>
                        }
                        severity="warning"
                        variant="outlined"
                    >
                        <Typography sx={{ fontWeight: 600 }}>{t('myAppsPage.states.errorTitle')}</Typography>
                        <Typography variant="body2">{t('myAppsPage.states.errorDetail', { statusCode: error.statusCode ?? 'unknown' })}</Typography>
                    </Alert>
                ) : null}

                {!isLoading && !error && filteredApps.length === 0 ? (
                    <Card elevation={0} sx={{ border: '1px solid rgba(15, 23, 42, 0.08)' }}>
                        <CardContent>
                            <Box sx={{ py: 4, textAlign: 'center' }}>
                                <Typography sx={{ fontWeight: 600 }}>{t('myAppsPage.states.emptyTitle')}</Typography>
                                <Typography color="text.secondary" variant="body2">
                                    {t('myAppsPage.states.emptyDetail')}
                                </Typography>
                            </Box>
                        </CardContent>
                    </Card>
                ) : null}

                {!isLoading && !error && filteredApps.length > 0 ? (
                    <Box
                        sx={{
                            display: 'grid',
                            gap: 2,
                            gridTemplateColumns: {
                                xs: '1fr',
                                xl: 'repeat(2, minmax(0, 1fr))',
                            },
                        }}
                    >
                        {filteredApps.map((app) => {
                            const isTracked = (trackingId && app.tracking_id === trackingId) || (trackedAppId && app.app_id === trackedAppId)
                            const latestLogLine = getLatestLogLine(app.logs)
                            const domainSummary = getDomainSummary(app)
                            const primaryAccessEntry = getPrimaryAccessEntry(app)
                            const canViewDetails = app.app_official && (app.status === 1 || app.status === 2)

                            return (
                                <Card
                                    key={`${app.app_id}-${app.tracking_id ?? 'stable'}`}
                                    elevation={0}
                                    sx={{
                                        border: isTracked ? '1px solid #2563eb' : '1px solid rgba(15, 23, 42, 0.08)',
                                        boxShadow: isTracked ? '0 0 0 3px rgba(37, 99, 235, 0.12)' : 'none',
                                    }}
                                >
                                    <CardContent>
                                        <Stack spacing={1.5}>
                                            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} sx={{ justifyContent: 'space-between' }}>
                                                <Box>
                                                    <Typography sx={{ fontSize: 18, fontWeight: 600 }}>
                                                        {app.app_name || app.app_id}
                                                    </Typography>
                                                    <Typography color="text.secondary" variant="body2">
                                                        {t('myAppsPage.card.identifier', { appId: app.app_id })}
                                                    </Typography>
                                                </Box>
                                                <Chip color={getStatusChipColor(app.status)} label={t(`myAppsPage.status.${getStatusFilterKey(app.status)}`)} size="small" />
                                            </Stack>

                                            <Typography color="text.secondary" variant="body2">
                                                {t('myAppsPage.card.meta', {
                                                    version: app.app_version || '-',
                                                    createdAt: formatCreationDate(app, locale),
                                                })}
                                            </Typography>

                                            {domainSummary ? (
                                                <Typography variant="body2">{t('myAppsPage.card.domain', { domains: domainSummary })}</Typography>
                                            ) : (
                                                <Typography color="text.secondary" variant="body2">
                                                    {t('myAppsPage.card.noAccess')}
                                                </Typography>
                                            )}

                                            {latestLogLine ? (
                                                <Alert severity={app.status === 4 ? 'error' : 'info'} variant="outlined">
                                                    {latestLogLine}
                                                </Alert>
                                            ) : null}

                                            {app.error ? (
                                                <Typography color="error" variant="body2">
                                                    {t('myAppsPage.card.error', { error: app.error })}
                                                </Typography>
                                            ) : null}

                                            <Stack direction="row" spacing={1}>
                                                {canViewDetails ? (
                                                    <Button component={RouterLink} size="small" to={`/myapps/${encodeURIComponent(app.app_id)}`} variant="contained">
                                                        {t('myAppsPage.card.viewDetails')}
                                                    </Button>
                                                ) : null}
                                                {primaryAccessEntry ? (
                                                    <Button
                                                        component={Link}
                                                        href={getAccessHref(primaryAccessEntry)}
                                                        rel="noreferrer"
                                                        size="small"
                                                        target="_blank"
                                                        underline="none"
                                                        variant="outlined"
                                                    >
                                                        {t('myAppsPage.card.openAccess')}
                                                    </Button>
                                                ) : null}
                                                {(app.logs?.length ?? 0) > 0 ? (
                                                    <Button
                                                        size="small"
                                                        variant="outlined"
                                                        onClick={() => {
                                                            setSelectedApp(app)
                                                        }}
                                                    >
                                                        {t('myAppsPage.card.openLogs')}
                                                    </Button>
                                                ) : null}
                                                {app.error ? (
                                                    <Button
                                                        color="error"
                                                        size="small"
                                                        variant="text"
                                                        onClick={() => {
                                                            setSelectedApp(app)
                                                        }}
                                                    >
                                                        {t('myAppsPage.card.openError')}
                                                    </Button>
                                                ) : null}
                                            </Stack>
                                        </Stack>
                                    </CardContent>
                                </Card>
                            )
                        })}
                    </Box>
                ) : null}
            </Stack>

            <Dialog fullWidth maxWidth="sm" open={Boolean(selectedApp)} onClose={() => setSelectedApp(null)}>
                <DialogTitle>{selectedApp?.error ? t('myAppsPage.dialog.errorTitle') : t('myAppsPage.dialog.logsTitle')}</DialogTitle>
                <DialogContent dividers>
                    {selectedApp?.error ? (
                        <Alert severity="error" variant="outlined">
                            {selectedApp.error}
                        </Alert>
                    ) : null}

                    <Stack spacing={1.5} sx={{ mt: selectedApp?.error ? 2 : 0 }}>
                        {(selectedApp?.logs ?? []).map((stage) => (
                            <Box key={`${selectedApp?.app_id}-${stage.title}`} sx={{ border: '1px solid rgba(15, 23, 42, 0.08)', p: 1.5 }}>
                                <Typography sx={{ fontWeight: 600 }}>{stage.title}</Typography>
                                <Stack spacing={0.75} sx={{ mt: 1 }}>
                                    {(stage.sub_logs ?? []).filter(Boolean).length > 0 ? (
                                        (stage.sub_logs ?? []).filter(Boolean).map((line, index) => (
                                            <Typography key={`${stage.title}-${index}`} color="text.secondary" variant="body2">
                                                {formatInstallLogLine(line)}
                                            </Typography>
                                        ))
                                    ) : (
                                        <Typography color="text.secondary" variant="body2">
                                            {t('myAppsPage.dialog.noSubLogs')}
                                        </Typography>
                                    )}
                                </Stack>
                            </Box>
                        ))}
                    </Stack>
                </DialogContent>
            </Dialog>
        </Box>
    )
}