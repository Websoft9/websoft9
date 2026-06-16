import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    CircularProgress,
    DialogContent,
    DialogTitle,
    FormControlLabel,
    IconButton,
    MenuItem,
    Stack,
    Switch,
    SvgIcon,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { startTransition, useDeferredValue, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { SurfaceStateCard, SurfaceStatusBadge } from '../../shared/design-system/standard-surfaces'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { useAppColorMode } from '../../app/providers/color-mode'
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
    id: string
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
    cursor: string | null
    unavailable_reason: string | null
}

type ServiceLogsSnapshotPayload = {
    logs: ServiceLogsResponse
    refresh_hint_ms: number
}

type ServiceLogsAppendPayload = {
    append: {
        service: string
        limit: number
        entries: ServiceLogEntry[]
    }
    refresh_hint_ms: number
}

type LogLoadMoreAnchor = {
    firstNewEntryIndex: number
}

type ContentScopeRect = {
    top: number
    left: number
    width: number
    height: number
}

type ServicesScopedOverlayProps = {
    open: boolean
    scopeRect: ContentScopeRect | null
    onClose: () => void
    darkMode: boolean
    maxWidth?: number
    children: ReactNode
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

function buildServiceLogsStreamUrl(serviceKey: string, filters: { limit: number; keyword: string; level: string; timeRange: string }) {
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
    return `/api/services/${serviceKey}/logs/stream?${params.toString()}`
}

function getServiceStatusTone(state: string): 'success' | 'warning' | 'error' {
    if (state === 'running' || state === 'healthy') {
        return 'success'
    }
    if (state === 'starting' || state === 'degraded') {
        return 'warning'
    }
    return 'error'
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

function ServicesScopedOverlay({ open, scopeRect, onClose, darkMode, maxWidth = 1100, children }: ServicesScopedOverlayProps) {
    useEffect(() => {
        if (!open) {
            return
        }

        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                onClose()
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => {
            window.removeEventListener('keydown', handleKeyDown)
        }
    }, [onClose, open])

    if (!open || !scopeRect || typeof document === 'undefined') {
        return null
    }

    const availableHeight = Math.max(Math.round(scopeRect.height) - 16, 240)

    return createPortal(
        <Box
            className={darkMode ? 'app-shell-root--dark' : undefined}
            sx={{
                '--ds-color-page-bg': darkMode ? '#111827' : '#f4f6f8',
                '--ds-color-surface-bg': darkMode ? '#111827' : '#ffffff',
                '--ds-color-surface-soft': darkMode ? '#111827' : '#f4f6f8',
                '--ds-color-border': darkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(145, 158, 171, 0.16)',
                '--ds-color-border-strong': darkMode ? 'color-mix(in srgb, rgba(255, 255, 255, 0.08) 65%, #f9fafb 35%)' : 'rgba(203, 213, 225, 0.9)',
                '--ds-color-text-strong': darkMode ? '#f9fafb' : '#212b36',
                '--ds-color-text-muted': darkMode ? '#9aa4b2' : '#637381',
                '--ds-color-floating-bg': darkMode ? 'rgba(17, 24, 39, 0.96)' : 'rgba(255, 255, 255, 0.92)',
                '--ds-color-accent': darkMode ? '#60a5fa' : '#1767d1',
                '--ds-color-accent-strong': darkMode ? '#93c5fd' : '#2563eb',
                '--ds-color-accent-soft': darkMode ? 'rgba(96, 165, 250, 0.18)' : 'rgba(37, 99, 235, 0.18)',
                '--ds-focus-ring': darkMode ? '0 0 0 0.2rem rgba(147, 197, 253, 0.18)' : '0 0 0 0.2rem rgba(23, 103, 209, 0.15)',
                '--ds-shadow-sm': darkMode ? '0 12px 28px rgba(2, 6, 23, 0.24)' : '0 2px 5px rgba(15, 23, 42, 0.08)',
                '--ds-shadow-md': darkMode ? '0 16px 36px rgba(2, 6, 23, 0.28)' : '0 10px 28px rgba(15, 23, 42, 0.06)',
                '--ds-shadow-lg': darkMode ? '0 20px 48px rgba(0, 0, 0, 0.36)' : '0 20px 40px rgba(145, 158, 171, 0.16)',
                position: 'fixed',
                top: scopeRect.top,
                left: scopeRect.left,
                width: scopeRect.width,
                height: scopeRect.height,
                zIndex: 1400,
            }}
        >
            <Box
                onClick={onClose}
                sx={{
                    position: 'absolute',
                    inset: 0,
                    backgroundColor: 'rgba(15, 23, 42, 0.18)',
                }}
            />
            <Box
                sx={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'center',
                    px: { xs: 1.5, md: 3 },
                    py: { xs: 0.75, md: 1 },
                    pointerEvents: 'none',
                }}
            >
                <Box
                    role="dialog"
                    aria-modal="true"
                    onClick={(event) => event.stopPropagation()}
                    className="services-page-dialog-paper"
                    sx={{
                        pointerEvents: 'auto',
                        width: { xs: 'min(100%, 1100px)', md: `min(${maxWidth}px, calc(100% - 16px))` },
                        maxWidth: `${maxWidth}px`,
                        height: `${availableHeight}px`,
                        maxHeight: `${availableHeight}px`,
                        display: 'flex',
                        flexDirection: 'column',
                        backgroundColor: darkMode ? '#111827' : '#ffffff',
                        color: darkMode ? '#e5edf5' : '#0f172a',
                        borderRadius: '2px',
                        border: darkMode ? '1px solid rgba(148, 163, 184, 0.2)' : undefined,
                        boxShadow: darkMode ? '0 24px 64px rgba(2, 6, 23, 0.62)' : '0 16px 40px rgba(15, 23, 42, 0.16)',
                        overflow: 'hidden',
                    }}
                >
                    {children}
                </Box>
            </Box>
        </Box>,
        document.body,
    )
}

export function ServicesPage() {
    const { t, i18n } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const isDarkMode = colorMode === 'dark'
    const { status } = useProductAuth()
    const queryClient = useQueryClient()
    const pageShellRef = useRef<HTMLDivElement | null>(null)
    const logBodyRef = useRef<HTMLDivElement | null>(null)
    const logLoadMoreAnchorRef = useRef<LogLoadMoreAnchor | null>(null)
    const [contentScopeRect, setContentScopeRect] = useState<ContentScopeRect | null>(null)
    const [activeLogServiceKey, setActiveLogServiceKey] = useState<string | null>(null)
    const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true)
    const [searchValue, setSearchValue] = useState('')
    const [stateFilter, setStateFilter] = useState('all')
    const [logKeywordInput, setLogKeywordInput] = useState('')
    const [logLevel, setLogLevel] = useState('all')
    const [logTimeRange, setLogTimeRange] = useState('all')
    const [logLimit, setLogLimit] = useState(100)
    const deferredKeyword = useDeferredValue(logKeywordInput)
    const supportsEventSource = typeof window !== 'undefined' && typeof EventSource !== 'undefined'

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

        return services
            .filter((service) => {
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
            .sort((a, b) => a.label.localeCompare(b.label))
    }, [searchValue, services, stateFilter])

    const activeLogService = useMemo(
        () => services.find((service) => service.key === activeLogServiceKey) ?? null,
        [activeLogServiceKey, services],
    )
    const logsQueryKey = useMemo(
        () => ['core-service-logs', activeLogServiceKey, deferredKeyword, logLevel, logTimeRange, logLimit] as const,
        [activeLogServiceKey, deferredKeyword, logLevel, logLimit, logTimeRange],
    )

    const logsQuery = useQuery<ServiceLogsResponse, Error>({
        queryKey: logsQueryKey,
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
        staleTime: supportsEventSource ? 10_000 : 5_000,
        refetchInterval: supportsEventSource ? false : activeLogServiceKey && autoRefreshEnabled ? 15_000 : false,
        refetchIntervalInBackground: !supportsEventSource,
        refetchOnWindowFocus: false,
    })

    useEffect(() => {
        if (!supportsEventSource || !activeLogServiceKey || !autoRefreshEnabled || !status?.enabled || !status?.authenticated) {
            return
        }

        const eventSource = new EventSource(
            buildServiceLogsStreamUrl(activeLogServiceKey, {
                limit: logLimit,
                keyword: deferredKeyword,
                level: logLevel,
                timeRange: logTimeRange,
            }),
            { withCredentials: true },
        )
        const handleSnapshot = (event: Event) => {
            try {
                const payload = JSON.parse((event as MessageEvent<string>).data) as ServiceLogsSnapshotPayload
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
                const payload = JSON.parse((event as MessageEvent<string>).data) as ServiceLogsAppendPayload
                const streamEntries = payload.append?.entries ?? []
                const nextLimit = payload.append?.limit ?? logLimit

                if (streamEntries.length === 0) {
                    return
                }

                startTransition(() => {
                    queryClient.setQueryData(logsQueryKey, (currentData: ServiceLogsResponse | undefined) => {
                        const existingEntries = currentData?.entries ?? []
                        const existingIds = new Set(existingEntries.map((entry) => entry.id))
                        const dedupedNewEntries = streamEntries.filter((entry) => !existingIds.has(entry.id))
                        const mergedEntries = dedupedNewEntries.length > 0 ? [...existingEntries, ...dedupedNewEntries] : existingEntries
                        const limitedEntries = mergedEntries.length > nextLimit ? mergedEntries.slice(-nextLimit) : mergedEntries

                        if (currentData) {
                            return {
                                ...currentData,
                                available: true,
                                limit: nextLimit,
                                entries: limitedEntries,
                                cursor: limitedEntries[limitedEntries.length - 1]?.id ?? null,
                                unavailable_reason: null,
                            }
                        }

                        return {
                            service: payload.append.service,
                            available: true,
                            keyword: deferredKeyword || null,
                            level: logLevel === 'all' ? null : logLevel,
                            time_range: logTimeRange,
                            limit: nextLimit,
                            entries: limitedEntries,
                            cursor: limitedEntries[limitedEntries.length - 1]?.id ?? null,
                            unavailable_reason: null,
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
    }, [activeLogServiceKey, autoRefreshEnabled, deferredKeyword, logLevel, logLimit, logTimeRange, logsQueryKey, queryClient, status?.authenticated, status?.enabled, supportsEventSource])

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

    const palette = {
        pageBg: isDarkMode ? '#0f172a' : '#ffffff',
        cardBg: isDarkMode ? '#111827' : '#ffffff',
        cardSoft: isDarkMode ? '#0b1220' : '#f8fafc',
        tableHead: isDarkMode ? '#162033' : '#f8fafc',
        text: isDarkMode ? '#f8fafc' : '#0f172a',
        subtleText: isDarkMode ? '#94a3b8' : '#64748b',
        actionText: isDarkMode ? '#f8fafc' : '#475569',
        border: isDarkMode ? 'rgba(71, 85, 105, 0.65)' : 'rgba(226, 232, 240, 0.95)',
        borderStrong: isDarkMode ? 'rgba(148, 163, 184, 0.2)' : 'rgba(203, 213, 225, 0.9)',
        idleBg: isDarkMode ? '#111827' : '#ffffff',
        idleHover: isDarkMode ? '#162033' : '#f8fafc',
        idleText: isDarkMode ? '#e5edf5' : '#334155',
        buttonHover: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(145, 158, 171, 0.12)',
    } as const

    const surfaceCardSx = {
        borderRadius: '2px',
        border: `1px solid ${palette.border}`,
        background: palette.cardBg,
        boxShadow: isDarkMode ? '0 12px 28px rgba(2, 6, 23, 0.28)' : '0 8px 24px rgba(15, 23, 42, 0.05)',
    } as const

    const topActionButtonSx = {
        borderRadius: 0,
        textTransform: 'none',
        px: 1.25,
        color: palette.actionText,
        fontWeight: 600,
        backgroundColor: 'transparent',
        '&:hover': {
            backgroundColor: palette.buttonHover,
        },
    } as const

    const serviceFilterSelectSx = {
        '& .MuiOutlinedInput-root': {
            borderRadius: '4px',
            backgroundColor: palette.cardBg,
            border: `1px solid ${palette.borderStrong}`,
            boxShadow: isDarkMode ? 'none' : '0 1px 2px rgba(15, 23, 42, 0.04)',
        },
        '& .MuiSelect-select': {
            color: isDarkMode ? '#cbd5e1' : '#334155',
            fontSize: 14,
            fontWeight: 400,
            lineHeight: 1.5,
            display: 'flex',
            alignItems: 'center',
        },
    } as const

    const controlMenuItemSx = {
        fontSize: 14,
        fontWeight: 400,
        minHeight: 40,
        color: isDarkMode ? '#e5edf5' : '#0f172a',
    } as const

    const filterMenuProps = useMemo(
        () => ({
            disablePortal: true,
            slotProps: {
                paper: {
                    sx: {
                        borderRadius: 0,
                        mt: 0.5,
                        zIndex: 1501,
                        backgroundColor: isDarkMode ? '#182235' : '#ffffff',
                        color: isDarkMode ? '#e5edf5' : '#0f172a',
                        border: isDarkMode ? '1px solid rgba(148, 163, 184, 0.2)' : '1px solid rgba(226, 232, 240, 0.9)',
                        boxShadow: isDarkMode ? '0 24px 64px rgba(2, 6, 23, 0.48)' : '0 12px 32px rgba(15, 23, 42, 0.12)',
                        '& .MuiMenuItem-root': controlMenuItemSx,
                    },
                },
            },
        }),
        [controlMenuItemSx, isDarkMode],
    )

    useLayoutEffect(() => {
        const shellElement = pageShellRef.current
        const mainElement = shellElement?.closest('main')
        if (!shellElement || !(mainElement instanceof HTMLElement)) {
            return
        }

        const updateScopeRect = () => {
            const rect = mainElement.getBoundingClientRect()
            setContentScopeRect({
                top: rect.top,
                left: rect.left,
                width: rect.width,
                height: rect.height,
            })
        }

        updateScopeRect()

        const resizeObserver = new ResizeObserver(() => updateScopeRect())
        resizeObserver.observe(mainElement)
        window.addEventListener('resize', updateScopeRect)

        return () => {
            resizeObserver.disconnect()
            window.removeEventListener('resize', updateScopeRect)
        }
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
        <Box
            className="services-page-shell"
            ref={pageShellRef}
            sx={{
                minHeight: 0,
                position: 'relative',
                mx: { xs: -1, md: -3 },
                my: { xs: -1.25, md: -2.25 },
                px: { xs: 2, md: 3 },
                py: { xs: 1.25, md: 1.5 },
                backgroundColor: palette.pageBg,
                overflowY: 'visible',
                overflowX: 'hidden',
            }}
        >
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

                <PageDescriptionHeader title={t('nav.services.label')} description={t('servicesPage.hero.description')} descriptionColor={palette.subtleText} />

                <Box className="services-page-grid">
                    <Card elevation={0} sx={surfaceCardSx}>
                        <CardContent sx={{ pt: 2.5, pb: 2 }}>
                            <Stack spacing={1.5} sx={{ minHeight: 0 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 1.5, flexWrap: 'wrap' }}>
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
                                            sx={serviceFilterSelectSx}
                                            slotProps={{
                                                select: {
                                                    MenuProps: filterMenuProps,
                                                },
                                            }}
                                        >
                                            <MenuItem value="all">{t('servicesPage.filters.stateOptions.all')}</MenuItem>
                                            <MenuItem value="running">{t('servicesPage.filters.stateOptions.running')}</MenuItem>
                                            <MenuItem value="starting">{t('servicesPage.filters.stateOptions.starting')}</MenuItem>
                                            <MenuItem value="stopped">{t('servicesPage.filters.stateOptions.stopped')}</MenuItem>
                                            <MenuItem value="unavailable">{t('servicesPage.filters.stateOptions.unavailable')}</MenuItem>
                                        </TextField>
                                        <Box className="services-page-toolbar-refresh">
                                            <Tooltip title={isFetching ? t('servicesPage.states.loading') : t('servicesPage.actions.refresh')}>
                                                <span>
                                                    <IconButton className="services-page-icon-button" onClick={() => { void refetch() }} disabled={isFetching} size="small" sx={topActionButtonSx}>
                                                        {isFetching ? <CircularProgress size={14} color="inherit" /> : <RefreshIcon />}
                                                    </IconButton>
                                                </span>
                                            </Tooltip>
                                        </Box>
                                    </Stack>
                                </Box>

                                {showInventoryLoadingCard ? (
                                    <SurfaceStateCard detail={t('servicesPage.states.loading')} loading darkMode={isDarkMode} />
                                ) : null}

                                {!showInventoryLoadingCard ? (
                                    <Box sx={{ overflowX: 'auto', border: `1px solid ${palette.border}` }}>
                                        <Box sx={{ minWidth: 1080 }}>
                                            <Box
                                                sx={{
                                                    display: 'grid',
                                                    gridTemplateColumns: '1.05fr 1.7fr .78fr .78fr .92fr .72fr',
                                                    alignItems: 'center',
                                                    minHeight: 52,
                                                    px: 1.25,
                                                    borderBottom: `1px solid ${palette.border}`,
                                                    background: palette.tableHead,
                                                }}
                                            >
                                                {[
                                                    t('servicesPage.columns.service'),
                                                    t('servicesPage.columns.description'),
                                                    t('servicesPage.columns.runtime'),
                                                    t('servicesPage.columns.health'),
                                                    t('servicesPage.columns.updatedAt'),
                                                    t('servicesPage.columns.actions'),
                                                ].map((column, index) => (
                                                    <Typography
                                                        key={column}
                                                        sx={{
                                                            fontSize: 13,
                                                            fontWeight: 700,
                                                            color: palette.subtleText,
                                                            textAlign: index === 5 ? 'right' : 'left',
                                                        }}
                                                    >
                                                        {column}
                                                    </Typography>
                                                ))}
                                            </Box>

                                            {showInventoryRefreshRow ? (
                                                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1.25, minHeight: 140, px: 3, color: palette.subtleText }}>
                                                    <CircularProgress size={18} />
                                                    <Typography sx={{ fontSize: 14, color: palette.subtleText }}>
                                                        {t('servicesPage.states.loading')}
                                                    </Typography>
                                                </Box>
                                            ) : null}

                                            {!showInventoryRefreshRow && filteredServices.length === 0 ? (
                                                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 180, px: 3 }}>
                                                    <Stack spacing={1} sx={{ alignItems: 'center', textAlign: 'center' }}>
                                                        <Typography sx={{ fontSize: 16, fontWeight: 700, color: palette.text }}>{t('servicesPage.states.emptyTitle')}</Typography>
                                                        <Typography sx={{ fontSize: 14, lineHeight: 1.7, color: palette.subtleText }}>
                                                            {services.length > 0 ? t('servicesPage.states.noResults') : t('servicesPage.states.empty')}
                                                        </Typography>
                                                    </Stack>
                                                </Box>
                                            ) : null}

                                            {!showInventoryRefreshRow ? filteredServices.map((service) => (
                                                <Box
                                                    className="services-page-list-row"
                                                    key={service.key}
                                                    sx={{
                                                        display: 'grid',
                                                        gridTemplateColumns: '1.05fr 1.7fr .78fr .78fr .92fr .72fr',
                                                        alignItems: 'center',
                                                        gap: 1.25,
                                                        px: 1.25,
                                                        py: 1.35,
                                                        minHeight: 56,
                                                        borderBottom: `1px solid ${palette.borderStrong}`,
                                                        backgroundColor: palette.idleBg,
                                                        '&:hover': {
                                                            backgroundColor: palette.idleHover,
                                                        },
                                                    }}
                                                >
                                                    <Stack className="services-page-service-stack" spacing={0.45} sx={{ minWidth: 0 }}>
                                                        <Typography className="services-page-service-name-text" sx={{ fontSize: 14, fontWeight: 400, color: palette.text }}>{service.label}</Typography>
                                                    </Stack>
                                                    <Typography className="services-page-description-text" sx={{ fontSize: 13.5, lineHeight: 1.6, color: palette.subtleText }}>
                                                        {getServiceDescription(service.key, service.description, t)}
                                                    </Typography>
                                                    <Box className="services-page-badge-cell">
                                                        <SurfaceStatusBadge label={t(`servicesPage.runtimeStates.${service.runtime_state}`)} tone={getServiceStatusTone(service.runtime_state)} darkMode={isDarkMode} />
                                                    </Box>
                                                    <Box className="services-page-badge-cell">
                                                        <SurfaceStatusBadge label={t(`servicesPage.healthStates.${service.health_state}`)} tone={getServiceStatusTone(service.health_state)} darkMode={isDarkMode} />
                                                    </Box>
                                                    <Typography className="services-page-updated-text" sx={{ fontSize: 13, color: palette.subtleText }}>{formatDateTime(service.updated_at, dateFormatter)}</Typography>
                                                    <Box className="services-page-action-cell" sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                                                        <Button
                                                            className="services-page-action-button"
                                                            disabled={!service.logs_available}
                                                            onClick={() => handleOpenLogs(service.key)}
                                                            size="small"
                                                            variant="outlined"
                                                            sx={topActionButtonSx}
                                                        >
                                                            {t('servicesPage.actions.viewLogs')}
                                                        </Button>
                                                    </Box>
                                                </Box>
                                            )) : null}
                                        </Box>
                                    </Box>
                                ) : null}
                            </Stack>
                        </CardContent>
                    </Card>
                </Box>
            </Stack>

            <ServicesScopedOverlay
                darkMode={isDarkMode}
                maxWidth={1100}
                onClose={() => setActiveLogServiceKey(null)}
                open={Boolean(activeLogService)}
                scopeRect={contentScopeRect}
            >
                <DialogTitle sx={{ px: 3, py: 2, backgroundColor: isDarkMode ? '#111827' : '#ffffff', borderBottom: `1px solid ${isDarkMode ? 'rgba(71, 85, 105, 0.65)' : 'rgba(226, 232, 240, 0.9)'}` }}>
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
                <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', px: 3, py: 2, backgroundColor: isDarkMode ? '#111827' : '#ffffff', '&.MuiDialogContent-dividers': { borderTop: 'none', borderBottom: 'none' } }}>
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
                                slotProps={{
                                    select: {
                                        MenuProps: filterMenuProps,
                                    },
                                }}
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
                                slotProps={{
                                    select: {
                                        MenuProps: filterMenuProps,
                                    },
                                }}
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
                                            <Box className="services-page-log-entry" data-log-entry-index={index} key={entry.id} title={entry.raw}>
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
            </ServicesScopedOverlay>
        </Box>
    )
}