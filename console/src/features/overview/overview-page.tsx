import { Alert, Box, Button, Chip, CircularProgress, Paper, Stack, Typography } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

import { useProductAuth } from '../product-auth/product-auth-provider'
import './overview-page.css'

type OverviewAlert = {
    key: string
    level: 'info' | 'warning' | 'error'
    title: string
    detail: string | null
    target_route: string
}

type OverviewProductSummary = {
    available: boolean
    unavailable_reason: string | null
    version: string | null
    edition_key: string | null
    edition_name: string | null
    installed_count: number | null
    available_app_count: number | null
    upgrade_state: string
    target_route: string
}

type OverviewHostSummary = {
    available: boolean
    unavailable_reason: string | null
    hostname: string | null
    os_name: string | null
    kernel_version: string | null
    architecture: string | null
    uptime_seconds: number | null
    target_route: string
}

type OverviewRuntimeSummary = {
    available: boolean
    unavailable_reason: string | null
    runtime_scope: 'container' | 'system'
    health_state: 'healthy' | 'warning' | 'critical'
    cpu_percent: number | null
    cpu_cores: number | null
    cpu_quota_cores: number | null
    memory_percent: number | null
    memory_used_bytes: number | null
    memory_total_bytes: number | null
    disk_percent?: number | null
    disk_used_bytes?: number | null
    disk_total_bytes?: number | null
}

type OverviewAppsSummary = {
    available: boolean
    unavailable_reason: string | null
    installed_count: number
    active_count: number
    inactive_count: number
    installing_count: number
    error_count: number
    target_route: string
}

type OverviewServicesSummary = {
    available: boolean
    unavailable_reason: string | null
    total_count: number
    healthy_count: number
    degraded_count: number
    unavailable_count: number
    target_route: string
}

type OverviewResponse = {
    generated_at: string
    product: OverviewProductSummary
    host: OverviewHostSummary
    apps: OverviewAppsSummary
    runtime: OverviewRuntimeSummary
    host_runtime: OverviewRuntimeSummary
    services: OverviewServicesSummary
    alerts: OverviewAlert[]
}

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
    const response = await fetch(input, {
        credentials: 'include',
        headers: {
            Accept: 'application/json',
            ...(init?.headers ?? {}),
        },
        ...init,
    })

    const payload = (await response.json().catch(() => null)) as { details?: string; message?: string } | T | null
    if (!response.ok) {
        const errorMessage =
            payload && typeof payload === 'object' && 'details' in payload
                ? payload.details ?? payload.message ?? `HTTP ${response.status}`
                : `HTTP ${response.status}`
        throw new Error(errorMessage)
    }

    return payload as T
}

export function OverviewPage() {
    const { t, i18n } = useTranslation('shell')
    const { status } = useProductAuth()

    const { data, error, isLoading, isFetching, refetch } = useQuery<OverviewResponse, Error>({
        queryKey: ['overview-summary'],
        queryFn: () => requestJson<OverviewResponse>('/api/overview'),
        enabled: Boolean(status?.enabled && status?.authenticated),
        staleTime: 10_000,
        refetchInterval: 30_000,
        refetchOnWindowFocus: false,
    })

    const locale = i18n.resolvedLanguage === 'zh-CN' ? 'zh-CN' : 'en-US'
    const dateFormatter = useMemo(
        () =>
            new Intl.DateTimeFormat(locale, {
                dateStyle: 'medium',
                timeStyle: 'short',
            }),
        [locale],
    )

    const numberFormatter = useMemo(
        () =>
            new Intl.NumberFormat(locale, {
                maximumFractionDigits: 1,
            }),
        [locale],
    )

    return (
        <Box className="overview-page-shell">
            <Stack spacing={1.75}>
                <Stack className="overview-page-header" direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
                    <Stack spacing={0.45}>
                        <Typography className="overview-page-title">
                            {t('overviewPage.compactHeader.title')}
                        </Typography>
                    </Stack>

                    <Stack className="overview-page-actions" direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                        {data ? (
                            <Typography className="overview-page-updated" color="text.secondary">
                                {t('overviewPage.generatedAt', { value: dateFormatter.format(new Date(data.generated_at)) })}
                            </Typography>
                        ) : null}
                        <Button
                            className="overview-page-refresh-button"
                            onClick={() => void refetch()}
                            size="small"
                            variant="contained"
                        >
                            {isFetching ? t('overviewPage.actions.refreshing') : t('overviewPage.actions.refresh')}
                        </Button>
                    </Stack>
                </Stack>

                {!status?.enabled ? <Alert severity="info">{t('overviewPage.states.authDisabled')}</Alert> : null}

                {error ? (
                    <Alert
                        action={<Button color="inherit" size="small" onClick={() => void refetch()}>{t('overviewPage.actions.retry')}</Button>}
                        severity="error"
                    >
                        {error.message || t('overviewPage.states.loadError')}
                    </Alert>
                ) : null}

                {data?.alerts?.length ? (
                    <Stack spacing={1}>
                        {data.alerts.slice(0, 3).map((alert) => (
                            <Alert
                                key={alert.key}
                                severity={alert.level}
                                variant="outlined"
                                sx={{ borderRadius: 2 }}
                            >
                                <strong>{alert.title}</strong>
                                {alert.detail ? ` - ${alert.detail}` : ''}
                            </Alert>
                        ))}
                    </Stack>
                ) : null}

                {isLoading && !data ? (
                    <Stack sx={{ minHeight: 260, alignItems: 'center', justifyContent: 'center' }}>
                        <CircularProgress size={32} />
                    </Stack>
                ) : null}

                {data ? (
                    <Stack spacing={2}>
                        <Stack className="overview-page-intro" spacing={0.9}>
                            <Typography className="overview-page-description" color="text.secondary">
                                {t('overviewPage.description')}
                            </Typography>
                        </Stack>

                        <Box className="overview-page-grid overview-page-grid-summary">
                            <Paper className="overview-page-panel" elevation={0}>
                                <Stack spacing={1.5}>
                                    <Stack className="overview-page-panel-header" direction={{ xs: 'column', md: 'row' }} spacing={1}>
                                        <Typography className="overview-page-panel-title">{t('overviewPage.cards.product.title')}</Typography>
                                        <Chip className="overview-page-status-chip" color={data.product.available ? 'success' : 'warning'} label={data.product.available ? t('overviewPage.badges.ready') : t('overviewPage.badges.partial')} size="small" />
                                    </Stack>

                                    {data.product.available ? (
                                        <Box className="overview-page-metrics-grid overview-page-metrics-grid-product">
                                            <SummaryMetricCell accent="#2563eb" label={t('overviewPage.cards.product.metrics.version')} value={data.product.version || '--'} />
                                            <SummaryMetricCell accent="#0f766e" label={t('overviewPage.cards.product.metrics.edition')} value={data.product.edition_name || data.product.edition_key || '--'} />
                                            <SummaryMetricCell accent="#d97706" label={t('overviewPage.cards.product.metrics.installedApps')} value={String(data.product.installed_count ?? 0)} />
                                            <SummaryMetricCell accent="#7c3aed" label={t('overviewPage.cards.product.metrics.availableApps')} value={formatAppLimit(data.product.available_app_count, t('overviewPage.cards.product.unlimited'))} />
                                        </Box>
                                    ) : (
                                        <Alert severity="warning">{data.product.unavailable_reason || t('overviewPage.states.sectionUnavailable')}</Alert>
                                    )}
                                </Stack>
                            </Paper>

                            <Paper className="overview-page-panel" elevation={0}>
                                <Stack spacing={1.5}>
                                    <Stack className="overview-page-panel-header" direction={{ xs: 'column', md: 'row' }} spacing={1}>
                                        <Typography className="overview-page-panel-title">{t('overviewPage.cards.host.title')}</Typography>
                                        <Chip className="overview-page-status-chip" color={data.host.available ? 'success' : 'warning'} label={data.host.available ? t('overviewPage.badges.ready') : t('overviewPage.badges.partial')} size="small" />
                                    </Stack>

                                    {data.host.available ? (
                                        <Box className="overview-page-metrics-grid overview-page-metrics-grid-product">
                                            <SummaryMetricCell accent="#1d4ed8" label={t('overviewPage.cards.host.metrics.hostname')} value={data.host.hostname || '--'} />
                                            <SummaryMetricCell accent="#0f766e" label={t('overviewPage.cards.host.metrics.os')} value={data.host.os_name || '--'} />
                                            <SummaryMetricCell accent="#d97706" label={t('overviewPage.cards.host.metrics.kernel')} value={data.host.kernel_version || '--'} />
                                            <SummaryMetricCell accent="#7c3aed" label={t('overviewPage.cards.host.metrics.uptime')} value={formatUptime(data.host.uptime_seconds)} />
                                        </Box>
                                    ) : (
                                        <Alert severity="warning">{data.host.unavailable_reason || t('overviewPage.states.sectionUnavailable')}</Alert>
                                    )}
                                </Stack>
                            </Paper>
                        </Box>

                        <Box className="overview-page-grid overview-page-grid-runtime-panels">
                            <Paper className="overview-page-panel" elevation={0}>
                                <Stack spacing={2}>
                                    <Stack className="overview-page-panel-header" direction={{ xs: 'column', md: 'row' }} spacing={1}>
                                        <Typography className="overview-page-panel-title">{t('overviewPage.cards.runtime.title')}</Typography>
                                        <Chip className="overview-page-status-chip" color={data.runtime.health_state === 'healthy' ? 'success' : data.runtime.health_state === 'warning' ? 'warning' : 'error'} label={t(`overviewPage.cards.runtime.badges.${data.runtime.health_state}`)} size="small" />
                                    </Stack>
                                    {data.runtime.available ? (
                                        <Stack spacing={1.25}>
                                            <Box className="overview-page-runtime-note">
                                                <Typography className="overview-page-runtime-note-badge">
                                                    {t(`overviewPage.runtimeScope.${data.runtime.runtime_scope}`)}
                                                </Typography>
                                                <Typography className="overview-page-runtime-note-text" color="text.secondary">
                                                    {t(`overviewPage.runtimeNote.${data.runtime.runtime_scope}`)}
                                                </Typography>
                                            </Box>
                                            <Box className="overview-page-runtime-grid">
                                                <RuntimeGaugeCard
                                                    accent="#2563eb"
                                                    hint={data.runtime.cpu_quota_cores ? `${t('overviewPage.runtimeMeta.cpuQuota')} ${formatQuotaCores(data.runtime.cpu_quota_cores, numberFormatter)}` : `${t('overviewPage.runtimeMeta.visibleCores')} ${data.runtime.cpu_cores ?? '--'}`}
                                                    label={t('overviewPage.cards.runtime.metrics.cpu')}
                                                    value={data.runtime.cpu_percent}
                                                />
                                                <RuntimeGaugeCard
                                                    accent="#d97706"
                                                    hint={formatUsedOverTotal(data.runtime.memory_used_bytes, data.runtime.memory_total_bytes, numberFormatter)}
                                                    label={t('overviewPage.cards.runtime.metrics.memory')}
                                                    value={data.runtime.memory_percent}
                                                />
                                            </Box>
                                        </Stack>
                                    ) : (
                                        <Alert severity="warning">{data.runtime.unavailable_reason || t('overviewPage.states.sectionUnavailable')}</Alert>
                                    )}
                                </Stack>
                            </Paper>

                            <Paper className="overview-page-panel overview-page-panel-emphasis" elevation={0}>
                                <Stack spacing={2}>
                                    <Stack className="overview-page-panel-header" direction={{ xs: 'column', md: 'row' }} spacing={1}>
                                        <Typography className="overview-page-panel-title">{t('overviewPage.cards.hostRuntime.title')}</Typography>
                                        <Chip className="overview-page-status-chip" color={data.host_runtime.health_state === 'healthy' ? 'success' : data.host_runtime.health_state === 'warning' ? 'warning' : 'error'} label={t(`overviewPage.cards.runtime.badges.${data.host_runtime.health_state}`)} size="small" />
                                    </Stack>
                                    {data.host_runtime.available ? (
                                        <Stack spacing={1.25}>
                                            <Box className="overview-page-runtime-note">
                                                <Typography className="overview-page-runtime-note-badge">
                                                    {t(`overviewPage.runtimeScope.${data.host_runtime.runtime_scope}`)}
                                                </Typography>
                                                <Typography className="overview-page-runtime-note-text" color="text.secondary">
                                                    {t('overviewPage.cards.hostRuntime.description')}
                                                </Typography>
                                            </Box>
                                            <Box className="overview-page-runtime-grid overview-page-runtime-grid-host">
                                                <RuntimeGaugeCard
                                                    accent="#1d4ed8"
                                                    hint={`${t('overviewPage.runtimeMeta.visibleCores')} ${data.host_runtime.cpu_cores ?? '--'}`}
                                                    label={t('overviewPage.cards.hostRuntime.metrics.cpu')}
                                                    value={data.host_runtime.cpu_percent}
                                                />
                                                <RuntimeGaugeCard
                                                    accent="#d97706"
                                                    hint={formatUsedOverTotal(data.host_runtime.memory_used_bytes, data.host_runtime.memory_total_bytes, numberFormatter)}
                                                    label={t('overviewPage.cards.hostRuntime.metrics.memory')}
                                                    value={data.host_runtime.memory_percent}
                                                />
                                                <RuntimeGaugeCard
                                                    accent="#0f766e"
                                                    hint={formatUsedOverTotal(data.host_runtime.disk_used_bytes ?? null, data.host_runtime.disk_total_bytes ?? null, numberFormatter)}
                                                    label={t('overviewPage.cards.hostRuntime.metrics.disk')}
                                                    value={data.host_runtime.disk_percent ?? null}
                                                />
                                            </Box>
                                        </Stack>
                                    ) : (
                                        <Alert severity="warning">{data.host_runtime.unavailable_reason || t('overviewPage.states.sectionUnavailable')}</Alert>
                                    )}
                                </Stack>
                            </Paper>
                        </Box>
                    </Stack>
                ) : null}
            </Stack>
        </Box>
    )
}

function formatPercent(value: number | null): string {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        return '--'
    }
    return `${value.toFixed(1)}%`
}

function formatBytes(value: number | null, formatter: Intl.NumberFormat): string {
    if (typeof value !== 'number' || Number.isNaN(value) || value < 0) {
        return '--'
    }

    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let size = value
    let unitIndex = 0
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024
        unitIndex += 1
    }
    return `${formatter.format(size)} ${units[unitIndex]}`
}

function formatAppLimit(value: number | null, unlimitedLabel: string): string {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        return unlimitedLabel
    }
    return String(value)
}

function formatUsedOverTotal(used: number | null, total: number | null, formatter: Intl.NumberFormat): string {
    return `${formatBytes(used, formatter)} / ${formatBytes(total, formatter)}`
}

function formatQuotaCores(value: number | null, formatter: Intl.NumberFormat): string {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        return '--'
    }
    return `${formatter.format(value)}`
}

function formatUptime(value: number | null): string {
    if (typeof value !== 'number' || Number.isNaN(value) || value < 0) {
        return '--'
    }

    const days = Math.floor(value / 86_400)
    const hours = Math.floor((value % 86_400) / 3_600)

    if (days > 0) {
        return `${days}d ${hours}h`
    }

    const minutes = Math.floor((value % 3_600) / 60)
    return `${hours}h ${minutes}m`
}

function SummaryMetricCell({
    label,
    value,
    accent,
}: {
    label: string
    value: string
    accent: string
}) {
    return (
        <Box
            className="overview-page-metric-cell"
        >
            <Box className="overview-page-metric-accent" sx={{ backgroundColor: accent }} />
            <Stack className="overview-page-metric-stack">
                <Typography className="overview-page-metric-label" color="text.secondary">
                    {label}
                </Typography>
                <Typography className="overview-page-metric-value">{value}</Typography>
            </Stack>
        </Box>
    )
}

function RuntimeGaugeCard({
    label,
    value,
    hint,
    accent,
}: {
    label: string
    value: number | null
    hint: string
    accent: string
}) {
    const normalizedValue = typeof value === 'number' && !Number.isNaN(value) ? Math.max(0, Math.min(value, 100)) : 0

    return (
        <Paper
            elevation={0}
            className="overview-page-runtime-card"
        >
            <Stack className="overview-page-runtime-card-stack" spacing={1.25}>
                <Box className="overview-page-runtime-gauge-wrap">
                    <CircularProgress className="overview-page-runtime-gauge-bg" size={104} thickness={3.2} value={100} variant="determinate" />
                    <CircularProgress
                        size={104}
                        thickness={3.2}
                        value={normalizedValue}
                        variant="determinate"
                        sx={{
                            color: accent,
                            '& .MuiCircularProgress-circle': {
                                strokeLinecap: 'round',
                            },
                        }}
                    />
                    <Stack className="overview-page-runtime-gauge-center">
                        <Typography className="overview-page-runtime-gauge-value">{formatPercent(value)}</Typography>
                        <Typography className="overview-page-runtime-gauge-label" color="text.secondary">
                            {label}
                        </Typography>
                    </Stack>
                </Box>
                <Typography className="overview-page-runtime-hint" color="text.secondary">
                    {hint}
                </Typography>
            </Stack>
        </Paper>
    )
}

