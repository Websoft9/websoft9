import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogContent,
    DialogTitle,
    FormControlLabel,
    IconButton,
    MenuItem,
    Paper,
    Stack,
    Switch,
    SvgIcon,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useDeferredValue, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { SurfaceStateCard } from '../../shared/design-system/standard-surfaces'
import { useProductAuth } from '../product-auth/product-auth-provider'
import './services-page.css'

type ServiceIndicator = {
    key: string
    status: string
    value: string | null
    detail: string | null
}

type CoreServiceSummary = {
    key: string
    label: string
    description: string
    runtime_state: string
    runtime_detail: string | null
    health_state: string
    updated_at: string
    workspace_route: string | null
    integration_key: string | null
    logs_available: boolean
    runtime_logs_href: string | null
    indicators: ServiceIndicator[]
}

type CoreServicesInventoryResponse = {
    services: CoreServiceSummary[]
}

type ServiceLogEntry = {
    timestamp: string | null
    level: string | null
    source: string | null
    message: string
    raw: string
}

type ServiceLogsResponse = {
    service: string
    available: boolean
    keyword: string | null
    level: string | null
    time_range: string
    limit: number
    entries: ServiceLogEntry[]
    unavailable_reason: string | null
}

type LogLoadMoreAnchor = {
    firstNewEntryIndex: number
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

function buildServiceLogsUrl(serviceKey: string, filters: { limit: number; keyword: string; level: string; timeRange: string }) {
    const params = new URLSearchParams()
    params.set('limit', String(filters.limit))
    if (filters.keyword.trim()) {
        params.set('keyword', filters.keyword.trim())
    }
    if (filters.level !== 'all') {
        params.set('level', filters.level)
    }
    if (filters.timeRange !== 'all') {
        params.set('time_range', filters.timeRange)
    }
    return `/api/services/${serviceKey}/logs?${params.toString()}`
}

function chipColorFromState(state: string): 'default' | 'success' | 'warning' | 'error' {
    if (state === 'running' || state === 'healthy') {
        return 'success'
    }
    if (state === 'starting' || state === 'degraded') {
        return 'warning'
    }
    if (state === 'stopped' || state === 'unavailable') {
        return 'error'
    }
    return 'default'
}

function formatDateTime(value: string | null, formatter: Intl.DateTimeFormat): string {
    if (!value) {
        return '--'
    }
    return formatter.format(new Date(value))
}

function formatEntryTime(value: string | null, formatter: Intl.DateTimeFormat): string {
    if (!value) {
        return '--:--:--'
    }
    return formatter.format(new Date(value))
}

function RefreshIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M17.65 6.35A7.95 7.95 0 0 0 12 4a8 8 0 1 0 7.75 10h-2.08A6 6 0 1 1 12 6c1.3 0 2.5.42 3.47 1.13L13 10h7V3l-2.35 3.35Z" />
        </SvgIcon>
    )
}

function getServiceDescription(serviceKey: string, description: string, t: (key: string, options?: Record<string, unknown>) => string) {
    return t(`servicesPage.descriptions.${serviceKey}`, { defaultValue: description })
}

export function ServicesPage() {
    const { t, i18n } = useTranslation('shell')
    const { status } = useProductAuth()
    const pageShellRef = useRef<HTMLDivElement | null>(null)
    const logBodyRef = useRef<HTMLDivElement | null>(null)
    const logLoadMoreAnchorRef = useRef<LogLoadMoreAnchor | null>(null)
    const [contentAreaElement, setContentAreaElement] = useState<HTMLElement | null>(null)
    const [activeLogServiceKey, setActiveLogServiceKey] = useState<string | null>(null)
    const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true)
    const [searchValue, setSearchValue] = useState('')
    const [stateFilter, setStateFilter] = useState('all')
    const [logKeywordInput, setLogKeywordInput] = useState('')
    const [logLevel, setLogLevel] = useState('all')
    const [logTimeRange, setLogTimeRange] = useState('all')
    const [logLimit, setLogLimit] = useState(100)
    const deferredKeyword = useDeferredValue(logKeywordInput)

    const { data, error, isLoading, isFetching, refetch } = useQuery<CoreServicesInventoryResponse, Error>({
        queryKey: ['core-services'],
        queryFn: () => requestJson<CoreServicesInventoryResponse>('/api/services'),
        enabled: Boolean(status?.enabled && status?.authenticated),
        staleTime: 5_000,
        refetchOnWindowFocus: false,
    })

    const services = data?.services ?? []

    const filteredServices = useMemo(() => {
        const normalizedQuery = searchValue.trim().toLowerCase()

        return services.filter((service) => {
            const matchesQuery =
                !normalizedQuery ||
                service.label.toLowerCase().includes(normalizedQuery) ||
                service.description.toLowerCase().includes(normalizedQuery) ||
                service.key.toLowerCase().includes(normalizedQuery)

            if (!matchesQuery) {
                return false
            }

            if (stateFilter === 'all') {
                return true
            }

            return service.runtime_state === stateFilter
        })
    }, [searchValue, services, stateFilter])

    const activeLogService = useMemo(
        () => services.find((service) => service.key === activeLogServiceKey) ?? null,
        [activeLogServiceKey, services],
    )

    const logsQuery = useQuery<ServiceLogsResponse, Error>({
        queryKey: ['core-service-logs', activeLogServiceKey, deferredKeyword, logLevel, logTimeRange, logLimit],
        queryFn: () =>
            requestJson<ServiceLogsResponse>(
                buildServiceLogsUrl(String(activeLogServiceKey), {
                    limit: logLimit,
                    keyword: deferredKeyword,
                    level: logLevel,
                    timeRange: logTimeRange,
                }),
            ),
        enabled: Boolean(status?.enabled && status?.authenticated && activeLogServiceKey),
        placeholderData: (previousData) => previousData,
        staleTime: 5_000,
        refetchInterval: activeLogServiceKey && autoRefreshEnabled ? 15_000 : false,
        refetchIntervalInBackground: true,
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
    const timeFormatter = useMemo(
        () =>
            new Intl.DateTimeFormat(locale, {
                dateStyle: 'short',
                timeStyle: 'medium',
            }),
        [locale],
    )

    const logEntries = useMemo(() => [...(logsQuery.data?.entries ?? [])].reverse(), [logsQuery.data?.entries])
    const canLoadMoreLogs = logEntries.length >= logLimit && logLimit < 20000
    const showInventoryLoadingCard = isLoading && !data
    const showInventoryRefreshRow = isFetching && Boolean(data)

    useEffect(() => {
        setContentAreaElement(pageShellRef.current?.closest('main') ?? null)
    }, [])

    useEffect(() => {
        if (!activeLogServiceKey || !logBodyRef.current) {
            return
        }
        logBodyRef.current.scrollTop = 0
        logLoadMoreAnchorRef.current = null
    }, [activeLogServiceKey])

    useLayoutEffect(() => {
        if (!logBodyRef.current || !logLoadMoreAnchorRef.current) {
            return
        }

        const anchorIndex = logLoadMoreAnchorRef.current.firstNewEntryIndex
        const anchorElement = logBodyRef.current.querySelector<HTMLElement>(`[data-log-entry-index="${anchorIndex}"]`)

        if (anchorElement) {
            logBodyRef.current.scrollTop = Math.max(0, anchorElement.offsetTop)
        }

        logLoadMoreAnchorRef.current = null
    }, [logEntries.length])

    function handleOpenLogs(serviceKey: string) {
        setActiveLogServiceKey(serviceKey)
        setAutoRefreshEnabled(true)
        setLogKeywordInput('')
        setLogLevel('all')
        setLogTimeRange('all')
        setLogLimit(100)
    }

    function handleLoadMoreLogs() {
        logLoadMoreAnchorRef.current = {
            firstNewEntryIndex: logEntries.length,
        }

        setLogLimit((current) => {
            if (current < 200) {
                return 200
            }
            if (current < 500) {
                return 500
            }
            if (current < 1000) {
                return 1000
            }
            if (current < 2000) {
                return 2000
            }
            if (current < 5000) {
                return 5000
            }
            if (current < 10000) {
                return 10000
            }
            return 20000
        })
    }

    return (
        <Box className="services-page-shell" ref={pageShellRef}>
            <Stack spacing={2} sx={{ height: '100%', minHeight: 0 }}>
                {!status?.enabled ? <Alert severity="info">{t('servicesPage.states.authDisabled')}</Alert> : null}

                {error ? (
                    <Alert
                        action={
                            <Button color="inherit" size="small" onClick={() => refetch()}>
                                {t('servicesPage.actions.retry')}
                            </Button>
                        }
                        severity="error"
                    >
                        {error.message || t('servicesPage.states.loadError')}
                    </Alert>
                ) : null}

                <Box className="services-page-grid">
                    <Paper className="services-page-toolbar-panel" elevation={0}>
                        <Stack className="services-page-toolbar-row" direction={{ xs: 'column', lg: 'row' }} spacing={2}>
                            <Stack className="services-page-toolbar" direction={{ xs: 'column', md: 'row' }} spacing={1.25}>
                                <TextField
                                    className="services-page-toolbar-field services-page-toolbar-search"
                                    onChange={(event) => setSearchValue(event.target.value)}
                                    placeholder={t('servicesPage.filters.searchPlaceholder')}
                                    size="small"
                                    slotProps={{ inputLabel: { shrink: false } }}
                                    value={searchValue}
                                />
                                <TextField
                                    className="services-page-toolbar-field services-page-toolbar-select"
                                    onChange={(event) => setStateFilter(event.target.value)}
                                    select
                                    size="small"
                                    value={stateFilter}
                                >
                                    <MenuItem value="all">{t('servicesPage.filters.stateOptions.all')}</MenuItem>
                                    <MenuItem value="running">{t('servicesPage.filters.stateOptions.running')}</MenuItem>
                                    <MenuItem value="starting">{t('servicesPage.filters.stateOptions.starting')}</MenuItem>
                                    <MenuItem value="stopped">{t('servicesPage.filters.stateOptions.stopped')}</MenuItem>
                                    <MenuItem value="unavailable">{t('servicesPage.filters.stateOptions.unavailable')}</MenuItem>
                                </TextField>
                                <Tooltip title={isFetching ? t('servicesPage.states.loading') : t('servicesPage.actions.refresh')}>
                                    <span>
                                        <IconButton className="services-page-icon-button" onClick={() => { void refetch() }} disabled={isFetching} size="small">
                                            {isFetching ? <CircularProgress size={14} color="inherit" /> : <RefreshIcon />}
                                        </IconButton>
                                    </span>
                                </Tooltip>
                            </Stack>
                        </Stack>
                    </Paper>

                    <Paper className="services-page-panel services-page-list" elevation={0}>
                        <Stack spacing={1.5} sx={{ minHeight: 0 }}>
                            {showInventoryLoadingCard ? (
                                <SurfaceStateCard detail={t('servicesPage.states.loading')} loading />
                            ) : null}

                            {!showInventoryLoadingCard ? (
                                <TableContainer className="services-page-table-container">
                                    <Table className="services-page-table">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>{t('servicesPage.columns.service')}</TableCell>
                                                <TableCell>{t('servicesPage.columns.description')}</TableCell>
                                                <TableCell>{t('servicesPage.columns.runtime')}</TableCell>
                                                <TableCell>{t('servicesPage.columns.health')}</TableCell>
                                                <TableCell>{t('servicesPage.columns.updatedAt')}</TableCell>
                                                <TableCell align="right">{t('servicesPage.columns.actions')}</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {showInventoryRefreshRow ? (
                                                <TableRow>
                                                    <TableCell className="services-page-table-state-cell" colSpan={6}>
                                                        <Box className="services-page-table-state">
                                                            <CircularProgress size={18} />
                                                            <Typography color="text.secondary" variant="body2">
                                                                {t('servicesPage.states.loading')}
                                                            </Typography>
                                                        </Box>
                                                    </TableCell>
                                                </TableRow>
                                            ) : null}

                                            {!showInventoryRefreshRow && filteredServices.length === 0 ? (
                                                <TableRow>
                                                    <TableCell className="services-page-table-state-cell" colSpan={6}>
                                                        <Box className="services-page-empty-state services-page-table-state-box">
                                                            <Typography variant="subtitle1">{t('servicesPage.states.emptyTitle')}</Typography>
                                                            <Typography color="text.secondary" variant="body2">
                                                                {services.length > 0 ? t('servicesPage.states.noResults') : t('servicesPage.states.empty')}
                                                            </Typography>
                                                        </Box>
                                                    </TableCell>
                                                </TableRow>
                                            ) : null}

                                            {!showInventoryRefreshRow ? filteredServices.map((service) => (
                                                <TableRow key={service.key}>
                                                    <TableCell>
                                                        <Stack className="services-page-service-cell" spacing={0.5}>
                                                            <Typography className="services-page-service-title">{service.label}</Typography>
                                                        </Stack>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Typography className="services-page-service-description">{getServiceDescription(service.key, service.description, t)}</Typography>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Chip color={chipColorFromState(service.runtime_state)} label={t(`servicesPage.runtimeStates.${service.runtime_state}`)} size="small" />
                                                    </TableCell>
                                                    <TableCell>
                                                        <Chip color={chipColorFromState(service.health_state)} label={t(`servicesPage.healthStates.${service.health_state}`)} size="small" />
                                                    </TableCell>
                                                    <TableCell className="services-page-updated-at-cell">{formatDateTime(service.updated_at, dateFormatter)}</TableCell>
                                                    <TableCell align="right">
                                                        <Box className="services-page-row-actions">
                                                            <Button
                                                                className="services-page-action-button"
                                                                disabled={!service.logs_available}
                                                                onClick={() => handleOpenLogs(service.key)}
                                                                size="small"
                                                                variant="outlined"
                                                            >
                                                                {t('servicesPage.actions.viewLogs')}
                                                            </Button>
                                                        </Box>
                                                    </TableCell>
                                                </TableRow>
                                            )) : null}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            ) : null}
                        </Stack>
                    </Paper>
                </Box>
            </Stack>

            <Dialog
                fullWidth
                maxWidth="lg"
                open={Boolean(activeLogService)}
                onClose={() => setActiveLogServiceKey(null)}
                disablePortal
                container={contentAreaElement}
                sx={{
                    position: 'absolute',
                    inset: 0,
                    '& .MuiBackdrop-root': {
                        position: 'absolute',
                        inset: 0,
                        backgroundColor: 'rgba(15, 23, 42, 0.18)',
                    },
                    '& .MuiDialog-container': {
                        position: 'absolute',
                        inset: 0,
                        alignItems: 'flex-start',
                        justifyContent: 'center',
                        px: { xs: 1.5, md: 3 },
                        py: { xs: 1.5, md: 2.5 },
                        overflow: 'hidden',
                    },
                }}
                slotProps={{
                    paper: {
                        className: 'services-page-dialog-paper',
                        square: true,
                        sx: {
                            borderRadius: '2px !important',
                        },
                    },
                }}
            >
                <DialogTitle>
                    <Box className="services-page-dialog-titlebar">
                        <Typography className="services-page-log-title" variant="subtitle1">
                            {activeLogService ? t('servicesPage.dialogs.logsTitle', { service: activeLogService.label }) : t('servicesPage.dialogs.logsFallbackTitle')}
                        </Typography>
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                            <IconButton aria-label={t('servicesPage.actions.close')} className="services-page-icon-button" onClick={() => setActiveLogServiceKey(null)} size="small">
                                <span className="services-page-dialog-close-glyph">×</span>
                            </IconButton>
                        </Stack>
                    </Box>
                </DialogTitle>
                <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', px: 3, py: 2 }}>
                    <Stack spacing={2} sx={{ flex: 1, minHeight: 0 }}>
                        <Stack
                            className="services-page-log-toolbar"
                            direction={{ xs: 'column', md: 'row' }}
                            spacing={1}
                            sx={{ alignItems: { xs: 'stretch', md: 'center' }, flexWrap: 'wrap' }}
                        >
                            <TextField
                                className="services-page-toolbar-field services-page-toolbar-search services-page-log-search"
                                size="small"
                                value={logKeywordInput}
                                onChange={(event) => setLogKeywordInput(event.target.value)}
                                placeholder={t('servicesPage.logs.keywordPlaceholder')}
                            />
                            <TextField
                                className="services-page-toolbar-field services-page-toolbar-select services-page-log-select"
                                select
                                size="small"
                                value={logTimeRange}
                                onChange={(event) => setLogTimeRange(event.target.value)}
                            >
                                <MenuItem value="all">{t('servicesPage.logs.timeRanges.all')}</MenuItem>
                                <MenuItem value="15m">{t('servicesPage.logs.timeRanges.15m')}</MenuItem>
                                <MenuItem value="1h">{t('servicesPage.logs.timeRanges.1h')}</MenuItem>
                                <MenuItem value="6h">{t('servicesPage.logs.timeRanges.6h')}</MenuItem>
                                <MenuItem value="24h">{t('servicesPage.logs.timeRanges.24h')}</MenuItem>
                                <MenuItem value="7d">{t('servicesPage.logs.timeRanges.7d')}</MenuItem>
                            </TextField>
                            <TextField
                                className="services-page-toolbar-field services-page-toolbar-select services-page-log-select"
                                select
                                size="small"
                                value={logLevel}
                                onChange={(event) => setLogLevel(event.target.value)}
                            >
                                <MenuItem value="all">{t('servicesPage.logs.levels.all')}</MenuItem>
                                <MenuItem value="info">{t('servicesPage.logs.levels.info')}</MenuItem>
                                <MenuItem value="warning">{t('servicesPage.logs.levels.warning')}</MenuItem>
                                <MenuItem value="error">{t('servicesPage.logs.levels.error')}</MenuItem>
                                <MenuItem value="fatal">{t('servicesPage.logs.levels.fatal')}</MenuItem>
                            </TextField>
                            <Tooltip title={logsQuery.isFetching ? t('servicesPage.states.loadingLogs') : t('servicesPage.actions.refreshLogs')}>
                                <span>
                                    <IconButton className="services-page-icon-button services-page-log-refresh-button" onClick={() => { void logsQuery.refetch() }} disabled={logsQuery.isFetching} size="small">
                                        {logsQuery.isFetching ? <CircularProgress size={14} color="inherit" /> : <RefreshIcon />}
                                    </IconButton>
                                </span>
                            </Tooltip>
                            <FormControlLabel
                                className="services-page-autorefresh-toggle"
                                control={
                                    <Switch
                                        checked={autoRefreshEnabled}
                                        onChange={(event) => setAutoRefreshEnabled(event.target.checked)}
                                        size="small"
                                    />
                                }
                                label={t('servicesPage.actions.autoRefresh')}
                            />
                        </Stack>

                        {logsQuery.isLoading ? (
                            <Box className="services-page-loading">
                                <CircularProgress size={18} />
                                <Typography color="text.secondary" variant="body2">
                                    {t('servicesPage.states.loadingLogs')}
                                </Typography>
                            </Box>
                        ) : null}

                        {logsQuery.error ? <Alert severity="error">{logsQuery.error.message || t('servicesPage.states.logError')}</Alert> : null}

                        {!logsQuery.isLoading && logsQuery.data && !logsQuery.data.available ? (
                            <Alert severity="warning">{logsQuery.data.unavailable_reason || t('servicesPage.states.logUnavailable')}</Alert>
                        ) : null}

                        {!logsQuery.isLoading && logEntries.length === 0 ? (
                            <Box className="services-page-empty-state services-page-dialog-empty">
                                <Typography variant="subtitle1">{t('servicesPage.states.logEmptyTitle')}</Typography>
                                <Typography color="text.secondary" variant="body2">
                                    {t('servicesPage.states.logEmpty')}
                                </Typography>
                            </Box>
                        ) : null}

                        {logEntries.length > 0 ? (
                            <Box className="services-page-log-panel">
                                <Box className="services-page-log-body services-page-log-body-dialog" ref={logBodyRef}>
                                    <Stack spacing={0}>
                                        {logEntries.map((entry, index) => (
                                            <Box className="services-page-log-entry" data-log-entry-index={index} key={`${entry.source}-${index}-${entry.raw}`} title={entry.raw}>
                                                <div className="services-page-log-content">
                                                    <div className="services-page-log-inline">
                                                        {entry.timestamp ? <span className="services-page-log-time">{formatEntryTime(entry.timestamp, timeFormatter)}</span> : null}
                                                        {entry.level ? (
                                                            <span className={`services-page-log-level services-page-log-level-${entry.level.toLowerCase()}`}>
                                                                {entry.level}
                                                            </span>
                                                        ) : null}
                                                        <Typography component="div" className="services-page-log-message">
                                                            {entry.message}
                                                        </Typography>
                                                    </div>
                                                </div>
                                            </Box>
                                        ))}
                                        {canLoadMoreLogs ? (
                                            <Box className="services-page-log-more-row">
                                                <Button className="services-page-action-button" onClick={handleLoadMoreLogs}>{t('servicesPage.actions.loadMoreLogs')}</Button>
                                            </Box>
                                        ) : null}
                                    </Stack>
                                </Box>
                            </Box>
                        ) : null}
                    </Stack>
                </DialogContent>
            </Dialog>
        </Box>
    )
}