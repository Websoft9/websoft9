import { Alert, Box, Button, CircularProgress, IconButton, LinearProgress, Paper, Stack, SvgIcon, Tooltip, Typography } from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { SurfaceStateCard, SurfaceStatusBadge } from '../../shared/design-system/standard-surfaces'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { useAppColorMode } from '../../app/providers/color-mode'
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
    catalog_app_count: number | null
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

type OverviewTaskItem = {
    key: string
    kind: string
    title: string
    status: 'running' | 'success' | 'failed'
    detail: string | null
    updated_at: string
    target_route: string
}

type OverviewTasksSummary = {
    available: boolean
    unavailable_reason: string | null
    items: OverviewTaskItem[]
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
    tasks: OverviewTasksSummary
    alerts: OverviewAlert[]
}

type OverviewStreamPayload = {
    overview?: OverviewResponse
    digest?: string
    refresh_hint_ms?: number
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

function RefreshIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M17.65 6.35A7.95 7.95 0 0 0 12 4a8 8 0 1 0 7.75 10h-2.08A6 6 0 1 1 12 6c1.3 0 2.5.42 3.47 1.13L13 10h7V3l-2.35 3.35Z" />
        </SvgIcon>
    )
}

export function OverviewPage() {
    const { t, i18n } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const isDarkMode = colorMode === 'dark'
    const { status } = useProductAuth()
    const queryClient = useQueryClient()
    const [isManualRefreshing, setIsManualRefreshing] = useState(false)
    const supportsEventSource = typeof window !== 'undefined' && typeof EventSource !== 'undefined'

    const { data, error, isLoading, refetch } = useQuery<OverviewResponse, Error>({
        queryKey: ['overview-summary'],
        queryFn: () => requestJson<OverviewResponse>('/api/overview'),
        enabled: Boolean(status?.enabled && status?.authenticated),
        staleTime: supportsEventSource ? 10_000 : 2_000,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
        refetchInterval: false,
    })

    useEffect(() => {
        if (!supportsEventSource || !status?.enabled || !status?.authenticated || !data) {
            return
        }

        const eventSource = new EventSource('/api/overview/stream', { withCredentials: true })
        const handleSnapshot = (event: Event) => {
            try {
                const payload = JSON.parse((event as MessageEvent<string>).data) as OverviewStreamPayload
                if (payload.overview) {
                    queryClient.setQueryData(['overview-summary'], payload.overview)
                }
            } catch {
                // Ignore malformed events and wait for the next snapshot.
            }
        }

        eventSource.addEventListener('snapshot', handleSnapshot)

        return () => {
            eventSource.removeEventListener('snapshot', handleSnapshot)
            eventSource.close()
        }
    }, [Boolean(data), queryClient, status?.authenticated, status?.enabled, supportsEventSource])

    async function handleManualRefresh() {
        setIsManualRefreshing(true)
        try {
            await refetch()
        } finally {
            setIsManualRefreshing(false)
        }
    }

    const locale = i18n.resolvedLanguage === 'zh-CN' ? 'zh-CN' : 'en-US'
    const numberFormatter = useMemo(
        () =>
            new Intl.NumberFormat(locale, {
                maximumFractionDigits: 1,
            }),
        [locale],
    )
    const localizedEditionName = getLocalizedEditionName(data?.product.edition_key ?? null, data?.product.edition_name ?? null, t)
    const runtimeAlertSummary = useMemo(() => {
        if (!data || data.runtime.health_state === 'healthy') {
            return null
        }

        const runtimeAlert = data.alerts[0]
        if (runtimeAlert) {
            return runtimeAlert.detail ? `${runtimeAlert.title} - ${runtimeAlert.detail}` : runtimeAlert.title
        }

        if (typeof data.runtime.cpu_percent === 'number' && data.runtime.cpu_percent >= 85) {
            return t('overviewPage.cards.runtime.warningReasonCpu', { value: formatPercent(data.runtime.cpu_percent) })
        }

        if (typeof data.runtime.memory_percent === 'number' && data.runtime.memory_percent >= 85) {
            return t('overviewPage.cards.runtime.warningReasonMemory', { value: formatPercent(data.runtime.memory_percent) })
        }

        if (data.runtime.unavailable_reason) {
            return data.runtime.unavailable_reason
        }

        return t('overviewPage.cards.runtime.warningReasonGeneric')
    }, [data, t])

    return (
        <Box className="overview-page-shell">
            <Stack spacing={2}>
                <PageDescriptionHeader
                    title={t('nav.dashboard.label')}
                    description={t('overviewPage.description')}
                    descriptionColor={colorMode === 'dark' ? '#94a3b8' : '#64748b'}
                    actions={(
                        <Tooltip title={isManualRefreshing ? t('appStorePage.actions.refreshing') : t('appStorePage.actions.refresh')}>
                            <span>
                                <IconButton
                                    color="inherit"
                                    onClick={() => {
                                        void handleManualRefresh()
                                    }}
                                    size="small"
                                    disabled={isManualRefreshing}
                                    className="app-shell-page-action"
                                    title={isManualRefreshing ? t('appStorePage.actions.refreshing') : t('appStorePage.actions.refresh')}
                                >
                                    {isManualRefreshing ? <CircularProgress size={14} color="inherit" /> : <RefreshIcon />}
                                </IconButton>
                            </span>
                        </Tooltip>
                    )}
                />

                {!status?.enabled ? <Alert severity="info">{t('overviewPage.states.authDisabled')}</Alert> : null}

                {error ? (
                    <Alert
                        action={<Button color="inherit" size="small" onClick={() => void refetch()}>{t('overviewPage.actions.retry')}</Button>}
                        severity="error"
                    >
                        {error.message || t('overviewPage.states.loadError')}
                    </Alert>
                ) : null}

                {(isLoading && !data) || isManualRefreshing ? (
                    <SurfaceStateCard detail={t('overviewPage.states.loading')} loading darkMode={isDarkMode} />
                ) : null}

                {data && !isManualRefreshing ? (
                    <Stack spacing={2}>
                        <Box className="overview-page-summary-strip">
                            <CompactSummaryCard
                                label={t('overviewPage.summary.availableApps')}
                                value={typeof data.product.catalog_app_count === 'number' ? String(data.product.catalog_app_count) : '--'}
                                accent="amber"
                                icon={<StorefrontSummaryIcon />}
                            />
                            <CompactSummaryCard
                                label={t('overviewPage.summary.installedApps')}
                                value={String(data.apps.installed_count ?? 0)}
                                accent="teal"
                                icon={<AppsSummaryIcon />}
                            />
                            <CompactSummaryCard
                                label={t('overviewPage.stats.activeApps')}
                                value={String(data.apps.active_count ?? 0)}
                                accent="green"
                                icon={<CheckSummaryIcon />}
                            />
                            <CompactSummaryCard
                                label={t('overviewPage.summary.errorApps')}
                                value={String(data.apps.error_count ?? 0)}
                                accent="violet"
                                icon={<AlertSummaryIcon />}
                            />
                        </Box>

                        <Box className="overview-page-dashboard-grid">
                            <Paper className="overview-page-panel overview-page-panel-runtime" elevation={0}>
                                <Stack className="overview-page-panel-stack" spacing={2.8}>
                                    <Stack className="overview-page-panel-header" direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
                                        <Box sx={{ minWidth: 0, flex: '1 1 auto' }}>
                                            <Typography className="overview-page-panel-title">{t('overviewPage.cards.runtime.title')}</Typography>
                                            <Typography className="overview-page-panel-subtitle">{t('overviewPage.cards.runtime.subtitle')}</Typography>
                                            {runtimeAlertSummary ? (
                                                <Typography sx={{ mt: 0.5, fontSize: 12.5, lineHeight: 1.45, color: '#b45309' }}>
                                                    {t('overviewPage.cards.runtime.warningReason', { reason: runtimeAlertSummary })}
                                                </Typography>
                                            ) : null}
                                        </Box>
                                        <SurfaceStatusBadge
                                            label={t(`overviewPage.cards.runtime.badges.${data.runtime.health_state}`)}
                                            tone={data.runtime.health_state === 'healthy' ? 'success' : data.runtime.health_state === 'warning' ? 'warning' : 'error'}
                                            darkMode={colorMode === 'dark'}
                                        />
                                    </Stack>

                                    {data.runtime.available ? (
                                        <>
                                            <Box className="overview-page-info-grid overview-page-info-grid--platform">
                                                <InfoBlock label={t('overviewPage.cards.product.metrics.version')} value={data.product.version || '--'} />
                                                <InfoBlock label={t('overviewPage.cards.product.metrics.edition')} value={localizedEditionName} />
                                                <InfoBlock label={t('overviewPage.stats.healthyServices')} value={`${data.services.healthy_count ?? 0}/${data.services.total_count ?? 0}`} />
                                                <InfoBlock label={t('overviewPage.cards.product.metrics.availableApps')} value={typeof data.product.available_app_count === 'number' ? String(data.product.available_app_count) : t('overviewPage.cards.product.unlimited')} />
                                            </Box>

                                            <Stack className="overview-page-resource-stack" spacing={1.5}>
                                                <ResourceMeterRow
                                                    accent="blue"
                                                    label={t('overviewPage.cards.runtime.metrics.cpu')}
                                                    meta={data.runtime.cpu_quota_cores ? `${t('overviewPage.runtimeMeta.cpuQuota')} ${formatQuotaCores(data.runtime.cpu_quota_cores, numberFormatter)}` : `${t('overviewPage.runtimeMeta.visibleCores')} ${data.runtime.cpu_cores ?? '--'}`}
                                                    value={data.runtime.cpu_percent}
                                                />
                                                <ResourceMeterRow
                                                    accent="amber"
                                                    label={t('overviewPage.cards.runtime.metrics.memory')}
                                                    meta={formatUsedOverTotal(data.runtime.memory_used_bytes, data.runtime.memory_total_bytes, numberFormatter)}
                                                    value={data.runtime.memory_percent}
                                                />
                                            </Stack>
                                        </>
                                    ) : (
                                        <Alert severity="warning">{data.runtime.unavailable_reason || t('overviewPage.states.sectionUnavailable')}</Alert>
                                    )}
                                </Stack>
                            </Paper>

                            <Paper className="overview-page-panel overview-page-panel-server" elevation={0}>
                                <Stack className="overview-page-panel-stack" spacing={2.8}>
                                    <Stack className="overview-page-panel-header" direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
                                        <Box sx={{ minWidth: 0, flex: '1 1 auto' }}>
                                            <Typography className="overview-page-panel-title">{t('overviewPage.cards.host.title')}</Typography>
                                            <Typography className="overview-page-panel-subtitle">{t('overviewPage.cards.hostRuntime.description')}</Typography>
                                        </Box>
                                        <SurfaceStatusBadge
                                            label={data.host.available ? t('overviewPage.badges.ready') : t('overviewPage.badges.partial')}
                                            tone={data.host.available ? 'success' : 'warning'}
                                            darkMode={colorMode === 'dark'}
                                        />
                                    </Stack>

                                    {data.host.available ? (
                                        <>
                                            <Box className="overview-page-info-grid">
                                                <InfoBlock label={t('overviewPage.cards.host.metrics.hostname')} value={data.host.hostname || '--'} />
                                                <InfoBlock label={t('overviewPage.cards.host.metrics.os')} value={data.host.os_name || '--'} />
                                                <InfoBlock label={t('overviewPage.cards.host.metrics.kernel')} value={data.host.kernel_version || data.host.architecture || '--'} />
                                                <InfoBlock label={t('overviewPage.cards.host.metrics.uptime')} value={formatUptime(data.host.uptime_seconds)} />
                                            </Box>

                                            {data.host_runtime.available ? (
                                                <Stack className="overview-page-resource-stack" spacing={1.5}>
                                                    <ResourceMeterRow
                                                        accent="blue"
                                                        label={t('overviewPage.cards.hostRuntime.metrics.cpu')}
                                                        meta={`${t('overviewPage.runtimeMeta.visibleCores')} ${data.host_runtime.cpu_cores ?? '--'}`}
                                                        value={data.host_runtime.cpu_percent}
                                                    />
                                                    <ResourceMeterRow
                                                        accent="amber"
                                                        label={t('overviewPage.cards.hostRuntime.metrics.memory')}
                                                        meta={formatUsedOverTotal(data.host_runtime.memory_used_bytes, data.host_runtime.memory_total_bytes, numberFormatter)}
                                                        value={data.host_runtime.memory_percent}
                                                    />
                                                    <ResourceMeterRow
                                                        accent="teal"
                                                        label={t('overviewPage.cards.hostRuntime.metrics.disk')}
                                                        meta={formatUsedOverTotal(data.host_runtime.disk_used_bytes ?? null, data.host_runtime.disk_total_bytes ?? null, numberFormatter)}
                                                        value={data.host_runtime.disk_percent ?? null}
                                                    />
                                                </Stack>
                                            ) : (
                                                <Alert severity="warning">{data.host_runtime.unavailable_reason || t('overviewPage.states.sectionUnavailable')}</Alert>
                                            )}
                                        </>
                                    ) : (
                                        <Alert severity="warning">{data.host.unavailable_reason || t('overviewPage.states.sectionUnavailable')}</Alert>
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

function getLocalizedEditionName(
    editionKey: string | null,
    editionName: string | null,
    t: (key: string) => string,
): string {
    const normalizedKey = (editionKey || editionName || '').trim().toLowerCase()
    if (normalizedKey === 'free' || editionName === '免费版' || editionName === 'Free') {
        return t('overviewPage.cards.product.editionNames.community')
    }

    return editionName || editionKey || '--'
}

function InfoBlock({
    label,
    value,
}: {
    label: string
    value: string
}) {
    return (
        <Box className="overview-page-info-block">
            <Box className="overview-page-info-block__body">
                <Typography className="overview-page-info-label">{label}</Typography>
                <Typography className="overview-page-info-value">{value}</Typography>
            </Box>
        </Box>
    )
}

function CompactSummaryCard({
    label,
    value,
    accent,
    icon,
}: {
    label: string
    value: string
    accent: 'amber' | 'teal' | 'green' | 'violet'
    icon: ReactNode
}) {
    return (
        <Box className={`overview-page-summary-card overview-page-summary-card--${accent}`}>
            <Box className="overview-page-summary-icon-wrap">{icon}</Box>
            <Typography className="overview-page-summary-value">{value}</Typography>
            <Typography className="overview-page-summary-label">{label}</Typography>
        </Box>
    )
}

function StorefrontSummaryIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M5 5.5 6.2 3h11.6L19 5.5V8a2.5 2.5 0 0 1-1.5 2.3V19a2 2 0 0 1-2 2h-7a2 2 0 0 1-2-2v-8.7A2.5 2.5 0 0 1 5 8V5.5Zm2 1V8a.5.5 0 0 0 .5.5h1A1.5 1.5 0 0 0 10 7V6.5H7Zm5 0V7A1.5 1.5 0 0 0 13.5 8.5h1a.5.5 0 0 0 .5-.5V6.5h-3Zm4.8 0h-1.3V8a2.48 2.48 0 0 1-.5 1.5V19h1V6.5ZM8.5 10.5V19h7v-8.5A3.38 3.38 0 0 1 12 8.7a3.38 3.38 0 0 1-3.5 1.8Z" /></SvgIcon>
}

function AppsSummaryIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M5 5h6v6H5V5Zm8 0h6v6h-6V5ZM5 13h6v6H5v-6Zm8 0h6v2h-6v-2Zm0 4h6v2h-6v-2Z" /></SvgIcon>
}

function CheckSummaryIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M9.55 16.6 5.4 12.45l1.4-1.4 2.75 2.75 7.65-7.65 1.4 1.4-9.05 9.05Z" /></SvgIcon>
}

function AlertSummaryIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M12 3 2 20h20L12 3Zm1 13h-2v-2h2v2Zm0-4h-2V8h2v4Z" /></SvgIcon>
}

function ResourceMeterRow({
    label,
    value,
    meta,
    accent,
}: {
    label: string
    value: number | null
    meta: string
    accent: 'blue' | 'teal' | 'amber'
}) {
    const normalizedValue = typeof value === 'number' && !Number.isNaN(value) ? Math.max(0, Math.min(value, 100)) : 0

    return (
        <Box className={`overview-page-resource-meter overview-page-resource-meter--${accent}`}>
            <Stack direction="row" spacing={1} sx={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
                <Typography className="overview-page-resource-label">{label}</Typography>
                <Typography className="overview-page-resource-value">{formatPercent(value)}</Typography>
            </Stack>
            <LinearProgress
                className="overview-page-resource-progress"
                variant="determinate"
                value={normalizedValue}
                sx={{
                    height: 8,
                    borderRadius: '999px',
                    '& .MuiLinearProgress-bar': {
                        borderRadius: '999px',
                    },
                }}
            />
            <Typography className="overview-page-resource-meta">{meta}</Typography>
        </Box>
    )
}

