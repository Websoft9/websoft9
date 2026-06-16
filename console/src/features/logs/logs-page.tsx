import {
    Alert,
    Box,
    Button,
    CircularProgress,
    FormControlLabel,
    IconButton,
    MenuItem,
    Paper,
    Stack,
    Switch,
    SvgIcon,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { startTransition, useDeferredValue, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { SurfaceStateCard } from '../../shared/design-system/standard-surfaces'
import { useAppColorMode } from '../../app/providers/color-mode'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { useProductAuth } from '../product-auth/product-auth-provider'
import './logs-page.css'

type RuntimeLogEntry = {
    id: string
    timestamp: string | null
    level: 'error' | 'warning' | 'info'
    source: string
    message: string
    raw: string
}

type RuntimeLogsResponse = {
    source: string
    level: string | null
    keyword: string | null
    time_range: string | null
    limit: number
    entries: RuntimeLogEntry[]
    cursor: string | null
}

type RuntimeLogsSnapshotPayload = {
    logs: RuntimeLogsResponse
    refresh_hint_ms: number
}

type RuntimeLogsAppendPayload = {
    append: {
        source: string
        limit: number
        entries: RuntimeLogEntry[]
    }
    refresh_hint_ms: number
}

async function requestJson<T>(input: string): Promise<T> {
    const response = await fetch(input, {
        credentials: 'include',
        headers: {
            Accept: 'application/json',
        },
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

function buildLogsUrl(filters: { timeRange: string; level: string; limit: number; keyword: string }) {
    const params = new URLSearchParams()
    params.set('limit', String(filters.limit))
    if (filters.timeRange !== 'all') {
        params.set('time_range', filters.timeRange)
    }
    if (filters.level !== 'all') {
        params.set('level', filters.level)
    }
    if (filters.keyword.trim()) {
        params.set('keyword', filters.keyword.trim())
    }
    return `/api/logs/runtime?${params.toString()}`
}

function buildLogsStreamUrl(filters: { timeRange: string; level: string; limit: number; keyword: string }) {
    const params = new URLSearchParams()
    params.set('limit', String(filters.limit))
    if (filters.timeRange !== 'all') {
        params.set('time_range', filters.timeRange)
    }
    if (filters.level !== 'all') {
        params.set('level', filters.level)
    }
    if (filters.keyword.trim()) {
        params.set('keyword', filters.keyword.trim())
    }
    return `/api/logs/runtime/stream?${params.toString()}`
}

function formatEntryTime(value: string | null, formatter: Intl.DateTimeFormat): string {
    if (!value) {
        return '--:--:--'
    }
    return formatter.format(new Date(value))
}

function groupEntriesByDate(
    entries: RuntimeLogEntry[],
    labelFormatter: Intl.DateTimeFormat,
    fallbackLabel: string,
): Array<{ key: string; label: string; entries: RuntimeLogEntry[] }> {
    const groups = new Map<string, { key: string; label: string; entries: RuntimeLogEntry[] }>()

    for (const entry of entries) {
        const key = entry.timestamp ? entry.timestamp.slice(0, 10) : 'undated'
        const label = entry.timestamp ? labelFormatter.format(new Date(entry.timestamp)) : fallbackLabel
        const current = groups.get(key)
        if (current) {
            current.entries.push(entry)
            continue
        }
        groups.set(key, { key, label, entries: [entry] })
    }

    return Array.from(groups.values())
}

function RefreshIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M17.65 6.35A7.95 7.95 0 0 0 12 4a8 8 0 1 0 7.75 10h-2.08A6 6 0 1 1 12 6c1.3 0 2.5.42 3.47 1.13L13 10h7V3l-2.35 3.35Z" />
        </SvgIcon>
    )
}

export function LogsPage() {
    const { t, i18n } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const isDarkMode = colorMode === 'dark'
    const { status, isLoading: authLoading } = useProductAuth()
    const queryClient = useQueryClient()
    const pageShellRef = useRef<HTMLDivElement | null>(null)
    const [searchParams] = useSearchParams()
    const initialTimeRange = ['all', '15m', '1h', '6h', '24h', '7d'].includes(searchParams.get('time_range') ?? '')
        ? String(searchParams.get('time_range'))
        : 'all'
    const initialLevel = ['all', 'info', 'warning', 'error'].includes(searchParams.get('level') ?? '')
        ? String(searchParams.get('level'))
        : 'all'
    const initialKeyword = String(searchParams.get('keyword') ?? searchParams.get('service') ?? '')
    const [timeRange, setTimeRange] = useState(initialTimeRange)
    const [level, setLevel] = useState(initialLevel)
    const [limit, setLimit] = useState(200)
    const [keywordInput, setKeywordInput] = useState(initialKeyword)
    const [autoRefresh, setAutoRefresh] = useState(true)
    const [refreshPending, setRefreshPending] = useState(false)
    const streamBodyRef = useRef<HTMLDivElement | null>(null)
    const logLoadMoreAnchorRef = useRef<{ firstNewEntryIndex: number } | null>(null)
    const [pageShellHeight, setPageShellHeight] = useState<number | null>(null)
    const deferredKeyword = useDeferredValue(keywordInput)
    const supportsEventSource = typeof window !== 'undefined' && typeof EventSource !== 'undefined'
    const logsQueryKey = useMemo(
        () => ['runtime-logs', timeRange, level, limit, deferredKeyword] as const,
        [deferredKeyword, level, limit, timeRange],
    )

    const { data, error, isLoading, isFetching, refetch } = useQuery<RuntimeLogsResponse, Error>({
        queryKey: logsQueryKey,
        queryFn: () =>
            requestJson<RuntimeLogsResponse>(
                buildLogsUrl({
                    timeRange,
                    level,
                    limit,
                    keyword: deferredKeyword,
                }),
            ),
        enabled: Boolean(status?.enabled && status?.authenticated),
        placeholderData: (previousData) => previousData,
        staleTime: supportsEventSource ? 10_000 : 5_000,
        refetchInterval: supportsEventSource ? false : autoRefresh ? 15_000 : false,
        refetchIntervalInBackground: !supportsEventSource,
        refetchOnWindowFocus: false,
    })

    useEffect(() => {
        if (!supportsEventSource || !autoRefresh || !status?.enabled || !status?.authenticated) {
            return
        }

        const eventSource = new EventSource(
            buildLogsStreamUrl({
                timeRange,
                level,
                limit,
                keyword: deferredKeyword,
            }),
            { withCredentials: true },
        )
        const handleSnapshot = (event: Event) => {
            try {
                const payload = JSON.parse((event as MessageEvent<string>).data) as RuntimeLogsSnapshotPayload
                if (payload.logs) {
                    startTransition(() => {
                        queryClient.setQueryData(logsQueryKey, payload.logs)
                    })
                }
            } catch {
                // Ignore malformed events and wait for the next snapshot.
            }
        }

        const handleAppend = (event: Event) => {
            try {
                const payload = JSON.parse((event as MessageEvent<string>).data) as RuntimeLogsAppendPayload
                const streamEntries = payload.append?.entries ?? []
                const nextLimit = payload.append?.limit ?? limit

                if (streamEntries.length === 0) {
                    return
                }

                startTransition(() => {
                    queryClient.setQueryData(logsQueryKey, (currentData: RuntimeLogsResponse | undefined) => {
                        const existingEntries = currentData?.entries ?? []
                        const existingIds = new Set(existingEntries.map((entry) => entry.id))
                        const dedupedNewEntries = streamEntries.filter((entry) => !existingIds.has(entry.id))
                        const mergedEntries = dedupedNewEntries.length > 0 ? [...existingEntries, ...dedupedNewEntries] : existingEntries
                        const limitedEntries = mergedEntries.length > nextLimit ? mergedEntries.slice(-nextLimit) : mergedEntries

                        if (currentData) {
                            return {
                                ...currentData,
                                limit: nextLimit,
                                entries: limitedEntries,
                                cursor: limitedEntries[limitedEntries.length - 1]?.id ?? null,
                            }
                        }

                        return {
                            source: payload.append.source,
                            level: level === 'all' ? null : level,
                            keyword: deferredKeyword || null,
                            time_range: timeRange === 'all' ? null : timeRange,
                            limit: nextLimit,
                            entries: limitedEntries,
                            cursor: limitedEntries[limitedEntries.length - 1]?.id ?? null,
                        }
                    })
                })
            } catch {
                // Ignore malformed events and wait for the next valid append.
            }
        }

        eventSource.addEventListener('snapshot', handleSnapshot)
        eventSource.addEventListener('append', handleAppend)

        return () => {
            eventSource.removeEventListener('snapshot', handleSnapshot)
            eventSource.removeEventListener('append', handleAppend)
            eventSource.close()
        }
    }, [autoRefresh, deferredKeyword, level, limit, logsQueryKey, queryClient, status?.authenticated, status?.enabled, supportsEventSource, timeRange])

    const locale = i18n.resolvedLanguage === 'zh-CN' ? 'zh-CN' : 'en-US'

    async function handleRefresh() {
        const startedAt = Date.now()
        setRefreshPending(true)
        try {
            await refetch()
        } finally {
            const elapsed = Date.now() - startedAt
            const remaining = Math.max(0, 300 - elapsed)
            if (remaining > 0) {
                await new Promise((resolve) => window.setTimeout(resolve, remaining))
            }
            setRefreshPending(false)
        }
    }

    const timeFormatter = useMemo(
        () =>
            new Intl.DateTimeFormat(locale, {
                dateStyle: 'short',
                timeStyle: 'medium',
            }),
        [locale],
    )
    const dayFormatter = useMemo(
        () =>
            new Intl.DateTimeFormat(locale, {
                dateStyle: 'full',
            }),
        [locale],
    )

    const entries = useMemo(() => [...(data?.entries ?? [])].reverse(), [data?.entries])
    const groups = useMemo(() => groupEntriesByDate(entries, dayFormatter, t('logsPage.groups.undated')), [entries, dayFormatter, t])
    const showLoadingCard = !authLoading && isLoading && !data
    const isRefreshingLogs = isFetching || refreshPending
    const canLoadMoreLogs = entries.length >= limit && limit < 20000

    useLayoutEffect(() => {
        const shellElement = pageShellRef.current
        const mainElement = shellElement?.closest('main')
        if (!shellElement || !(mainElement instanceof HTMLElement)) {
            return
        }

        const updateHeight = () => {
            const mainRect = mainElement.getBoundingClientRect()
            const shellRect = shellElement.getBoundingClientRect()
            const mainStyles = window.getComputedStyle(mainElement)
            const paddingTop = Number.parseFloat(mainStyles.paddingTop || '0') || 0
            const paddingBottom = Number.parseFloat(mainStyles.paddingBottom || '0') || 0
            const shellTopWithinContent = Math.max(0, shellRect.top - mainRect.top - paddingTop)
            const contentHeight = Math.max(0, mainElement.clientHeight - paddingTop - paddingBottom)
            const nextHeight = Math.max(320, Math.floor(contentHeight - shellTopWithinContent))
            setPageShellHeight(nextHeight)
        }

        updateHeight()

        const resizeObserver = new ResizeObserver(() => updateHeight())
        resizeObserver.observe(mainElement)
        window.addEventListener('resize', updateHeight)

        return () => {
            resizeObserver.disconnect()
            window.removeEventListener('resize', updateHeight)
        }
    }, [])

    useLayoutEffect(() => {
        if (!streamBodyRef.current || !logLoadMoreAnchorRef.current) {
            return
        }

        const anchorIndex = logLoadMoreAnchorRef.current.firstNewEntryIndex
        const anchorElement = streamBodyRef.current.querySelector<HTMLElement>(`[data-log-entry-index="${anchorIndex}"]`)

        if (anchorElement) {
            streamBodyRef.current.scrollTop = Math.max(0, anchorElement.offsetTop)
        }

        logLoadMoreAnchorRef.current = null
    }, [entries.length])

    function handleLoadMoreLogs() {
        logLoadMoreAnchorRef.current = {
            firstNewEntryIndex: entries.length,
        }

        setLimit((current) => {
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
        <Box
            className="logs-page-shell"
            ref={pageShellRef}
            sx={{
                height: pageShellHeight ? `${pageShellHeight}px` : '100%',
                minHeight: 0,
                mx: 0,
                my: 0,
                px: 0,
                py: 0,
                backgroundColor: 'transparent',
                overflow: 'hidden',
            }}
        >
            <Stack spacing={2} sx={{ height: '100%', minHeight: 0 }}>

                <PageDescriptionHeader title={t('nav.logs.label')} description={t('logsPage.hero.description')} descriptionColor="#64748b" />

                {!status?.enabled ? <Alert severity="info">{t('logsPage.states.authDisabled')}</Alert> : null}

                {error ? (
                    <Alert
                        action={
                            <Button color="inherit" size="small" onClick={() => refetch()}>
                                {t('logsPage.states.retry')}
                            </Button>
                        }
                        severity="error"
                    >
                        {error.message || t('logsPage.states.loadError')}
                    </Alert>
                ) : null}

                <Box className="logs-page-grid">
                    <Paper className="logs-page-toolbar-panel" elevation={0}>
                        <Box className="logs-page-toolbar logs-page-toolbar-classic">
                            <TextField
                                className="logs-page-toolbar-field logs-page-toolbar-search"
                                size="small"
                                value={keywordInput}
                                onChange={(event) => setKeywordInput(event.target.value)}
                                placeholder={t('logsPage.filters.keywordPlaceholder')}
                            />

                            <TextField
                                className="logs-page-toolbar-field logs-page-toolbar-select"
                                select
                                size="small"
                                value={timeRange}
                                onChange={(event) => setTimeRange(event.target.value)}
                            >
                                <MenuItem value="all">{t('logsPage.filters.timeRanges.all')}</MenuItem>
                                <MenuItem value="15m">{t('logsPage.filters.timeRanges.15m')}</MenuItem>
                                <MenuItem value="1h">{t('logsPage.filters.timeRanges.1h')}</MenuItem>
                                <MenuItem value="6h">{t('logsPage.filters.timeRanges.6h')}</MenuItem>
                                <MenuItem value="24h">{t('logsPage.filters.timeRanges.24h')}</MenuItem>
                                <MenuItem value="7d">{t('logsPage.filters.timeRanges.7d')}</MenuItem>
                            </TextField>

                            <TextField
                                className="logs-page-toolbar-field logs-page-toolbar-select"
                                select
                                size="small"
                                value={level}
                                onChange={(event) => setLevel(event.target.value)}
                            >
                                <MenuItem value="all">{t('logsPage.filters.levels.all')}</MenuItem>
                                <MenuItem value="info">{t('logsPage.filters.levels.info')}</MenuItem>
                                <MenuItem value="warning">{t('logsPage.filters.levels.warning')}</MenuItem>
                                <MenuItem value="error">{t('logsPage.filters.levels.error')}</MenuItem>
                            </TextField>
                            <Stack className="logs-page-toolbar-actions" direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                                <FormControlLabel
                                    className="logs-page-auto-refresh"
                                    control={<Switch checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} />}
                                    label={autoRefresh ? t('logsPage.actions.autoRefreshOn') : t('logsPage.actions.autoRefreshOff')}
                                />
                                <Tooltip title={isRefreshingLogs ? t('logsPage.states.refreshing') : t('logsPage.actions.refresh')}>
                                    <span>
                                        <IconButton className="logs-page-icon-button" onClick={() => { void handleRefresh() }} disabled={isRefreshingLogs} size="small">
                                            {isRefreshingLogs ? <CircularProgress size={14} color="inherit" /> : <RefreshIcon />}
                                        </IconButton>
                                    </span>
                                </Tooltip>
                            </Stack>
                        </Box>
                    </Paper>

                    <Paper className={`logs-page-panel${isFetching && !isLoading ? ' logs-page-stream-updating' : ''}`} elevation={0}>
                        {showLoadingCard ? <SurfaceStateCard detail={t('logsPage.states.loading')} loading darkMode={isDarkMode} /> : null}

                        {!showLoadingCard ? (
                            <Box className="logs-page-stream">
                                {!isLoading && !error && entries.length === 0 ? (
                                    <Box className="logs-page-empty-state">
                                        <Typography variant="subtitle1">{t('logsPage.states.emptyTitle')}</Typography>
                                        <Typography color="text.secondary" variant="body2">
                                            {keywordInput.trim() || level !== 'all' || timeRange !== 'all'
                                                ? t('logsPage.states.emptyFiltered')
                                                : t('logsPage.states.empty')}
                                        </Typography>
                                    </Box>
                                ) : (
                                    <Box ref={streamBodyRef} className="logs-page-stream-body">
                                        <Stack spacing={2}>
                                            {(() => {
                                                let entryIndex = 0

                                                return groups.map((group) => (
                                                    <Stack key={group.key} spacing={1}>
                                                        <div className="logs-page-group-divider">
                                                            <span className="logs-page-group-title">{group.label}</span>
                                                        </div>
                                                        <Stack spacing={0}>
                                                            {group.entries.map((entry) => {
                                                                const currentIndex = entryIndex
                                                                entryIndex += 1

                                                                return (
                                                                    <Box className={`logs-page-entry logs-page-entry-${entry.level}`} data-log-entry-index={currentIndex} key={entry.id} title={entry.raw}>
                                                                        <div className="logs-page-entry-inline">
                                                                            <span className="logs-page-entry-time">{formatEntryTime(entry.timestamp, timeFormatter)}</span>
                                                                            <span className={`logs-page-level-tag logs-page-level-tag-${entry.level}`}>
                                                                                {entry.level === 'info' ? 'INF' : entry.level === 'warning' ? 'WRN' : 'ERR'}
                                                                            </span>
                                                                            <Typography component="div" className="logs-page-entry-message">
                                                                                {entry.message}
                                                                            </Typography>
                                                                        </div>
                                                                    </Box>
                                                                )
                                                            })}
                                                        </Stack>
                                                    </Stack>
                                                ))
                                            })()}
                                        </Stack>
                                        {canLoadMoreLogs ? (
                                            <Box className="logs-page-load-more-row">
                                                <Button className="logs-page-load-more-button" onClick={handleLoadMoreLogs}>{t('logsPage.actions.loadMoreLogs')}</Button>
                                            </Box>
                                        ) : null}
                                    </Box>
                                )}
                                {!isLoading ? <div className="logs-page-stream-status" aria-hidden={!isRefreshingLogs} data-updating={isRefreshingLogs ? 'true' : 'false'} /> : null}
                            </Box>
                        ) : null}
                    </Paper>
                </Box>
            </Stack>
        </Box>
    )
}