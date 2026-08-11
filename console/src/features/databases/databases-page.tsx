import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    CircularProgress,
    IconButton,
    Stack,
    SvgIcon,
    Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { markMyAppsDetailOverlayIntent } from '../my-apps/my-app-detail-overlay-intent'
import { useAppColorMode } from '../../app/providers/color-mode'
import { useProductAuth } from '../product-auth/product-auth-provider'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import './databases-page.css'

type ExternalDatabaseAppRef = {
    app_id: string
    app_name: string
    status: number
}

type ExternalDatabaseRecord = {
    type: string
    address: string
    database_name: string
    username: string
    password: string
    apps: ExternalDatabaseAppRef[]
}

function EyeIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M12 5c5.23 0 9.27 4.11 10.75 6.2a1.33 1.33 0 0 1 0 1.6C21.27 14.89 17.23 19 12 19S2.73 14.89 1.25 12.8a1.33 1.33 0 0 1 0-1.6C2.73 9.11 6.77 5 12 5Zm0 2C8.21 7 5.1 9.84 3.39 12 5.1 14.16 8.21 17 12 17s6.9-2.84 8.61-5C18.9 9.84 15.79 7 12 7Zm0 2.25A2.75 2.75 0 1 1 9.25 12 2.75 2.75 0 0 1 12 9.25Zm0 2A.75.75 0 1 0 12.75 12 .75.75 0 0 0 12 11.25Z" />
        </SvgIcon>
    )
}

function EyeOffIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="m4.71 3.29 16 16-1.42 1.42-2.43-2.43A11.65 11.65 0 0 1 12 19c-5.23 0-9.27-4.11-10.75-6.2a1.33 1.33 0 0 1 0-1.6A18.48 18.48 0 0 1 6.4 6.6L3.29 4.71 4.71 3.29Zm8.08 8.08-1.58-1.58a.75.75 0 1 0-1.42.63l2.37 2.37a.75.75 0 0 0 .63-1.42ZM7.96 8.16C6.14 9.09 4.55 10.45 3.39 12 5.1 14.16 8.21 17 12 17c1.16 0 2.26-.27 3.27-.73l-1.71-1.71a4.75 4.75 0 0 1-6.12-6.12L7.96 8.16ZM12 7c3.79 0 6.9 2.84 8.61 5a14.8 14.8 0 0 1-2.35 2.31l-1.43-1.43c.72-.63 1.33-1.28 1.78-1.88C18.9 9.84 15.79 7 12 7c-.73 0-1.43.1-2.1.29L8.19 5.58A9.8 9.8 0 0 1 12 7Z" />
        </SvgIcon>
    )
}

function CopyIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M16 1H4c-1.1 0-2 .9-2 2v12h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z" />
        </SvgIcon>
    )
}

function RefreshIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M17.65 6.35A7.95 7.95 0 0 0 12 4a8 8 0 1 0 7.75 10h-2.08A6 6 0 1 1 12 6c1.3 0 2.5.42 3.47 1.13L13 10h7V3l-2.35 3.35Z" />
        </SvgIcon>
    )
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

async function copyTextWithFallback(value: string) {
    if (navigator.clipboard?.writeText) {
        try {
            await navigator.clipboard.writeText(value)
            return
        } catch {
            // Fall through to execCommand
        }
    }

    const textarea = document.createElement('textarea')
    textarea.value = value
    textarea.setAttribute('readonly', 'true')
    textarea.style.position = 'absolute'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.select()

    const copied = document.execCommand('copy')
    document.body.removeChild(textarea)

    if (!copied) {
        throw new Error('Copy failed')
    }
}

export function DatabasesPage() {
    const { t } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const isDarkMode = colorMode === 'dark'
    const { status } = useProductAuth()
    const navigate = useNavigate()
    const pageShellRef = useRef<HTMLDivElement | null>(null)
    const [searchValue, setSearchValue] = useState('')
    const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({})

    const { data, error, isLoading, isFetching, refetch } = useQuery<ExternalDatabaseRecord[], Error>({
        queryKey: ['external-databases'],
        queryFn: async () => {
            const result = await requestJson<ExternalDatabaseRecord[]>('/api/databases')
            return result
        },
        enabled: Boolean(status?.enabled && status?.authenticated),
        staleTime: 15_000,
        refetchOnWindowFocus: false,
    })

    const databases = data ?? []

    const filteredDatabases = useMemo(() => {
        const normalizedQuery = searchValue.trim().toLowerCase()
        if (!normalizedQuery) return databases

        return databases.filter(
            (db) =>
                db.type.toLowerCase().includes(normalizedQuery) ||
                db.address.toLowerCase().includes(normalizedQuery) ||
                db.database_name.toLowerCase().includes(normalizedQuery) ||
                db.username.toLowerCase().includes(normalizedQuery) ||
                db.apps.some((a) => a.app_id.toLowerCase().includes(normalizedQuery)),
        )
    }, [databases, searchValue])

    const palette = {
        pageBg: isDarkMode ? '#0f172a' : '#ffffff',
        cardBg: isDarkMode ? '#111827' : '#ffffff',
        tableHead: isDarkMode ? '#162033' : '#f8fafc',
        text: isDarkMode ? '#f8fafc' : '#0f172a',
        subtleText: isDarkMode ? '#94a3b8' : '#64748b',
        actionText: isDarkMode ? '#f8fafc' : '#475569',
        border: isDarkMode ? 'rgba(71, 85, 105, 0.65)' : 'rgba(226, 232, 240, 0.95)',
        borderStrong: isDarkMode ? 'rgba(148, 163, 184, 0.2)' : 'rgba(203, 213, 225, 0.9)',
        idleBg: isDarkMode ? '#111827' : '#ffffff',
        idleHover: isDarkMode ? '#162033' : '#f8fafc',
        buttonHover: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(145, 158, 171, 0.12)',
        accent: isDarkMode ? '#60a5fa' : '#1767d1',
    } as const

    return (
        <Box
            className="databases-page-shell"
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
                                {t('databasesPage.actions.retry')}
                            </Button>
                        }
                        severity="error"
                    >
                        {error.message || t('databasesPage.states.loadError')}
                    </Alert>
                ) : null}

                <PageDescriptionHeader title={t('databasesPage.hero.title')} description={t('databasesPage.hero.description')} descriptionColor={palette.subtleText} />

                <Card elevation={0} sx={{ borderRadius: '2px', border: `1px solid ${palette.border}`, background: palette.cardBg, boxShadow: isDarkMode ? '0 12px 28px rgba(2, 6, 23, 0.28)' : '0 8px 24px rgba(15, 23, 42, 0.05)' }}>
                    <CardContent sx={{ pt: 2.5, pb: 2, '&:last-child': { pb: 2 } }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 1, mb: 2 }}>
                            <Box className="databases-search-box" sx={{ width: 440 }}>
                                <input
                                    className="databases-search-input"
                                    placeholder={t('databasesPage.searchPlaceholder')}
                                    value={searchValue}
                                    onChange={(e) => setSearchValue(e.target.value)}
                                />
                                <span className="databases-search-icon" aria-hidden="true">
                                    <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                                        <path d="M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5Zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14Z" />
                                    </svg>
                                </span>
                            </Box>
                            <IconButton
                                onClick={() => refetch()}
                                disabled={isFetching}
                                size="small"
                                title={t('databasesPage.actions.refresh')}
                                sx={{
                                    color: palette.actionText,
                                    '&:hover': { backgroundColor: palette.buttonHover },
                                    animation: isFetching ? 'spin 1s linear infinite' : 'none',
                                }}
                            >
                                <RefreshIcon />
                            </IconButton>
                        </Box>

                        {(isLoading || isFetching) ? (
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 180, gap: 2 }}>
                                <CircularProgress size={24} />
                                <Typography sx={{ fontSize: 15, color: palette.subtleText }}>{t('databasesPage.states.loading')}</Typography>
                            </Box>
                        ) : (
                            <Box>
                                {/* Table header — always visible when not loading */}
                                <Box
                                    sx={{
                                        display: 'grid',
                                        gridTemplateColumns: '0.7fr 1.4fr 1fr 1fr 0.9fr 1.1fr',
                                        alignItems: 'center',
                                        gap: 1.25,
                                        px: 1.25,
                                        py: 1.25,
                                        borderBottom: `1px solid ${palette.borderStrong}`,
                                        backgroundColor: palette.tableHead,
                                    }}
                                >
                                    <Typography sx={{ fontSize: 13, fontWeight: 700, color: palette.subtleText }}>{t('databasesPage.columns.type')}</Typography>
                                    <Typography sx={{ fontSize: 13, fontWeight: 700, color: palette.subtleText }}>{t('databasesPage.columns.address')}</Typography>
                                    <Typography sx={{ fontSize: 13, fontWeight: 700, color: palette.subtleText }}>{t('databasesPage.columns.name')}</Typography>
                                    <Typography sx={{ fontSize: 13, fontWeight: 700, color: palette.subtleText }}>{t('databasesPage.columns.username')}</Typography>
                                    <Typography sx={{ fontSize: 13, fontWeight: 700, color: palette.subtleText }}>{t('databasesPage.columns.password')}</Typography>
                                    <Typography sx={{ fontSize: 13, fontWeight: 700, color: palette.subtleText, textAlign: 'right' }}>{t('databasesPage.columns.appName')}</Typography>
                                </Box>

                                {!isLoading && !isFetching && data && databases.length === 0 ? (
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 6, px: 3 }}>
                                        <Typography sx={{ fontSize: 15, color: palette.subtleText }}>{t('databasesPage.states.empty')}</Typography>
                                    </Box>
                                ) : null}

                                {!isLoading && !isFetching && data && databases.length > 0 && filteredDatabases.length === 0 ? (
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 6, px: 3 }}>
                                        <Typography sx={{ fontSize: 15, color: palette.subtleText }}>{t('databasesPage.states.noResults')}</Typography>
                                    </Box>
                                ) : null}

                                {filteredDatabases.length > 0 && filteredDatabases.map((db, index) => {
                                    const passwordKey = `${db.type}-${db.address}-${index}`
                                    const isPasswordVisible = Boolean(showPasswords[passwordKey])
                                    return (
                                        <Box
                                            key={passwordKey}
                                            sx={{
                                                display: 'grid',
                                                gridTemplateColumns: '0.7fr 1.4fr 1fr 1fr 0.9fr 1.1fr',
                                                alignItems: 'center',
                                                gap: 1.25,
                                                px: 1.25,
                                                py: 1.35,
                                                borderBottom: `1px solid ${palette.borderStrong}`,
                                                backgroundColor: palette.idleBg,
                                                '&:hover': { backgroundColor: palette.idleHover },
                                            }}
                                        >
                                            <Typography sx={{ fontSize: 13.5, color: palette.text, textTransform: 'capitalize' }}>{db.type}</Typography>
                                            <Typography sx={{ fontSize: 13.5, color: palette.text, fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={db.address}>{db.address}</Typography>
                                            <Typography sx={{ fontSize: 13.5, color: palette.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={db.database_name}>{db.database_name}</Typography>
                                            <Typography sx={{ fontSize: 13.5, color: palette.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={db.username}>{db.username}</Typography>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 0 }}>
                                                <Typography
                                                    className="databases-password-text"
                                                    sx={{
                                                        fontSize: 13.5,
                                                        color: palette.text,
                                                        fontFamily: 'monospace',
                                                        letterSpacing: isPasswordVisible ? 0 : 2,
                                                        overflow: 'hidden',
                                                        textOverflow: 'ellipsis',
                                                        whiteSpace: 'nowrap',
                                                        minWidth: 0,
                                                    }}
                                                >
                                                    {isPasswordVisible ? db.password : '•'.repeat(Math.min(db.password.length, 16))}
                                                </Typography>
                                                <button
                                                    className="databases-icon-btn"
                                                    title={isPasswordVisible ? t('databasesPage.columns.hidePassword') : t('databasesPage.columns.showPassword')}
                                                    onClick={() => setShowPasswords((prev) => ({ ...prev, [passwordKey]: !prev[passwordKey] }))}
                                                >
                                                    {isPasswordVisible ? <EyeOffIcon /> : <EyeIcon />}
                                                </button>
                                                <button
                                                    className="databases-icon-btn"
                                                    title={t('databasesPage.columns.copy')}
                                                    onClick={async () => {
                                                        try {
                                                            await copyTextWithFallback(db.password)
                                                        } catch {
                                                            // ignore
                                                        }
                                                    }}
                                                >
                                                    <CopyIcon />
                                                </button>
                                            </Box>
                                            <Box sx={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'flex-end', gap: 0.5 }}>
                                                {db.apps.map((appRef, i) => (
                                                    <Box key={appRef.app_id} sx={{ display: 'flex', alignItems: 'center' }}>
                                                        <Box
                                                            component="span"
                                                            className="databases-app-link"
                                                            onClick={() => {
                                                                if (appRef.status === 1) {
                                                                    markMyAppsDetailOverlayIntent(appRef.app_id)
                                                                    navigate(`/myapps/${encodeURIComponent(appRef.app_id)}`)
                                                                } else {
                                                                    navigate('/myapps')
                                                                }
                                                            }}
                                                            title={appRef.app_id}
                                                        >
                                                            {appRef.app_id}
                                                        </Box>
                                                        {i < db.apps.length - 1 ? (
                                                            <Box component="span" sx={{ color: palette.subtleText, mx: 0.25 }}>,</Box>
                                                        ) : null}
                                                    </Box>
                                                ))}
                                            </Box>
                                        </Box>
                                    )
                                })}
                            </Box>
                        )}
                    </CardContent>
                </Card>
            </Stack>
        </Box>
    )
}
