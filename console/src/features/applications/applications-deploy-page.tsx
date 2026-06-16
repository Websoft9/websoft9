import { Avatar, Box, Button, Paper, Skeleton, Typography, IconButton, Tooltip } from '@mui/material'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useAppColorMode } from '../../app/providers/color-mode'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import type { AppStoreApp } from '../app-store/app-store-model'
import { useAppStoreApps } from '../app-store/use-app-store-apps'

function StoreIcon() {
    return (
        <Box sx={{ width: 18, height: 18, display: 'grid', placeItems: 'center' }}>
            <Box
                sx={{
                    width: 14,
                    height: 11,
                    border: '2px solid currentColor',
                    borderTopWidth: 3,
                    position: 'relative',
                    '&::before': {
                        content: '""',
                        position: 'absolute',
                        left: 1,
                        right: 1,
                        top: -7,
                        height: 5,
                        border: '2px solid currentColor',
                        borderBottom: 0,
                    },
                }}
            />
        </Box>
    )
}

function ComposeIcon() {
    return (
        <Box
            sx={{
                width: 18,
                height: 18,
                display: 'grid',
                placeItems: 'center',
                fontSize: 9,
                fontWeight: 800,
                letterSpacing: '0.04em',
            }}
        >
            YAML
        </Box>
    )
}

function FlowIcon() {
    return (
        <Box sx={{ position: 'relative', width: 16, height: 16 }}>
            <Box sx={{ position: 'absolute', left: 1, top: 6, width: 4, height: 4, borderRadius: '50%', backgroundColor: 'currentColor' }} />
            <Box sx={{ position: 'absolute', right: 1, top: 2, width: 4, height: 4, borderRadius: '50%', backgroundColor: 'currentColor' }} />
            <Box sx={{ position: 'absolute', right: 1, bottom: 2, width: 4, height: 4, borderRadius: '50%', backgroundColor: 'currentColor' }} />
            <Box sx={{ position: 'absolute', left: 5, top: 7, width: 6, height: 2, backgroundColor: 'currentColor', transform: 'rotate(-20deg)', transformOrigin: 'left center' }} />
            <Box sx={{ position: 'absolute', left: 5, top: 7, width: 6, height: 2, backgroundColor: 'currentColor', transform: 'rotate(18deg)', transformOrigin: 'left center' }} />
        </Box>
    )
}

function ArrowIcon() {
    return (
        <Box
            aria-hidden="true"
            sx={{
                width: 8,
                height: 8,
                borderTop: '2px solid currentColor',
                borderRight: '2px solid currentColor',
                transform: 'rotate(45deg)',
            }}
        />
    )
}

function AutorenewIcon() {
    return (
        <Box
            component="svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            sx={{ width: 13, height: 13 }}
        >
            <polyline points="1 4 1 10 7 10" />
            <polyline points="23 20 23 14 17 14" />
            <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" />
        </Box>
    )
}

function getAppInitial(label: string) {
    return label.trim().charAt(0).toUpperCase() || 'A'
}

function AppCardItem({
    app,
    fallbackLabel,
    onClick,
    isDark,
}: {
    app?: AppStoreApp
    fallbackLabel: string
    onClick: () => void
    isDark: boolean
}) {
    const [imageFailed, setImageFailed] = useState(false)
    const label = app?.trademark?.trim() || app?.key?.trim() || fallbackLabel
    const imageUrl = app?.logo?.imageurl?.trim() || ''
    const description = app?.summary?.trim() || app?.overview?.trim() || app?.description?.trim() || ''

    return (
        <Button
            variant="text"
            onClick={onClick}
            sx={{
                width: '100%',
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', sm: 'auto minmax(0, 1fr) auto' },
                alignItems: { xs: 'center', sm: 'center' },
                justifyItems: { xs: 'center', sm: 'stretch' },
                gap: { xs: 0.65, sm: 1.5 },
                minWidth: 0,
                minHeight: { xs: 92, sm: 'auto' },
                p: { xs: '10px 8px', sm: '16px 16px' },
                borderRadius: 0,
                border: '1px solid var(--ds-color-border)',
                backgroundColor: 'var(--ds-color-surface-bg)',
                textTransform: 'none',
                boxShadow: 'var(--ds-shadow-sm)',
                textAlign: { xs: 'center', sm: 'left' },
                '&:hover': {
                    backgroundColor: isDark ? 'rgba(37, 99, 235, 0.06)' : 'rgba(37, 99, 235, 0.02)',
                    borderColor: 'rgba(37, 99, 235, 0.25)',
                },
            }}
        >
            {imageUrl && !imageFailed ? (
                <Box
                    component="img"
                    alt={label}
                    src={imageUrl}
                    referrerPolicy="no-referrer"
                    onError={() => setImageFailed(true)}
                    sx={{ width: { xs: 30, sm: 38 }, height: { xs: 30, sm: 38 }, objectFit: 'contain', borderRadius: 0, flexShrink: 0 }}
                />
            ) : (
                <Avatar
                    variant="square"
                    sx={{
                        width: { xs: 30, sm: 38 },
                        height: { xs: 30, sm: 38 },
                        borderRadius: 0,
                        backgroundColor: isDark ? 'rgba(148, 163, 184, 0.16)' : 'rgba(148, 163, 184, 0.1)',
                        color: 'var(--ds-color-text-muted)',
                        fontSize: { xs: 12, sm: 15 },
                        fontWeight: 700,
                        flexShrink: 0,
                    }}
                >
                    {getAppInitial(label)}
                </Avatar>
            )}

            <Box sx={{ minWidth: 0, width: '100%' }}>
                <Typography
                    sx={{
                        fontSize: { xs: 11, sm: 13.5 },
                        fontWeight: 700,
                        lineHeight: { xs: 1.25, sm: 1.35 },
                        color: 'var(--ds-color-text-strong)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: '-webkit-box',
                        textAlign: { xs: 'center', sm: 'left' },
                        WebkitLineClamp: { xs: 2, sm: 1 },
                        WebkitBoxOrient: 'vertical',
                    }}
                >
                    {label}
                </Typography>
                {description && description !== label ? (
                    <Typography
                        sx={{
                            mt: 0.3,
                            fontSize: 12,
                            lineHeight: 1.45,
                            color: 'var(--ds-color-text-muted)',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            display: { xs: 'none', sm: '-webkit-box' },
                            WebkitLineClamp: 1,
                            WebkitBoxOrient: 'vertical',
                        }}
                    >
                        {description}
                    </Typography>
                ) : null}
            </Box>

            <Box
                aria-hidden="true"
                sx={{
                    width: 7,
                    height: 7,
                    borderTop: '2px solid rgba(148, 163, 184, 0.7)',
                    borderRight: '2px solid rgba(148, 163, 184, 0.7)',
                    transform: 'rotate(45deg)',
                    flexShrink: 0,
                    display: { xs: 'none', sm: 'block' },
                }}
            />
        </Button>
    )
}

export function ApplicationsDeployPage() {
    const navigate = useNavigate()
    const { t } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const { data: appStoreApps, isLoading: appStoreLoading } = useAppStoreApps()
    const isDark = colorMode === 'dark'
    const panelShadow = 'var(--ds-shadow-sm)'
    const panelBorder = isDark ? 'rgba(148, 163, 184, 0.22)' : 'rgba(37, 99, 235, 0.08)'
    const subtleDivider = isDark ? 'rgba(148, 163, 184, 0.16)' : 'rgba(15, 23, 42, 0.06)'
    const pillBackground = isDark ? 'rgba(148, 163, 184, 0.16)' : 'rgba(148, 163, 184, 0.12)'

    const STORE_PAGE_SIZE = 15
    const [storePageIndex, setStorePageIndex] = useState(0)

    const hotApps = useMemo(() => {
        return (appStoreApps ?? [])
            .filter((app) => app.key)
            .sort((a, b) => (b.hot ?? 0) - (a.hot ?? 0))
            .slice(0, 30)
    }, [appStoreApps])

    const totalStorePages = Math.max(1, Math.ceil(hotApps.length / STORE_PAGE_SIZE))
    const currentStoreApps = hotApps.slice(storePageIndex * STORE_PAGE_SIZE, (storePageIndex + 1) * STORE_PAGE_SIZE)
    function handleShuffle() {
        setStorePageIndex((idx) => (idx + 1) % totalStorePages)
    }
    const composeSteps = [
        {
            key: 'prepare',
            index: '1',
            title: t('applicationsHubPage.deployPage.cards.compose.flow.prepare.title'),
            detail: t('applicationsHubPage.deployPage.cards.compose.flow.prepare.detail'),
            state: 'active' as const,
        },
        {
            key: 'configure',
            index: '2',
            title: t('applicationsHubPage.deployPage.cards.compose.flow.configure.title'),
            detail: t('applicationsHubPage.deployPage.cards.compose.flow.configure.detail'),
            state: 'ready' as const,
        },
        {
            key: 'launch',
            index: '3',
            title: t('applicationsHubPage.deployPage.cards.compose.flow.launch.title'),
            detail: t('applicationsHubPage.deployPage.cards.compose.flow.launch.detail'),
            state: 'idle' as const,
        },
    ]
    const composeCapabilities = [
        {
            key: 'compose',
            title: t('applicationsHubPage.deployPage.cards.compose.capabilities.compose'),
            detail: t('applicationsHubPage.deployPage.cards.compose.metrics.compose'),
            badges: t('applicationsHubPage.deployPage.cards.compose.tags.compose').split('|'),
        },
        {
            key: 'env',
            title: t('applicationsHubPage.deployPage.cards.compose.capabilities.env'),
            detail: t('applicationsHubPage.deployPage.cards.compose.metrics.env'),
            badges: t('applicationsHubPage.deployPage.cards.compose.tags.env').split('|'),
        },
        {
            key: 'mounts',
            title: t('applicationsHubPage.deployPage.cards.compose.capabilities.mounts'),
            detail: t('applicationsHubPage.deployPage.cards.compose.metrics.mounts'),
            badges: t('applicationsHubPage.deployPage.cards.compose.tags.mounts').split('|'),
        },
    ]
    function openFeaturedApp(appKey: string) {
        navigate('/appstore', { state: { openAppKey: appKey } })
    }

    return (
        <Box sx={{ display: 'grid', gap: 2, alignContent: 'start', minHeight: 0 }}>
            <PageDescriptionHeader
                title={t('applicationsHubPage.deployPage.title')}
                description={t('applicationsHubPage.deployPage.description')}
                sx={{ mt: 0, mb: 0.5 }}
            />

            <Box
                sx={{
                    display: 'flex',
                    flexDirection: { xs: 'column', md: 'row' },
                    gap: 1.5,
                    alignItems: 'stretch',
                }}
            >
                <Box sx={{ flex: { xs: '1 1 auto', md: '1.5 1 0%' }, minWidth: 0, width: '100%', display: 'flex' }}>
                    <Paper
                        elevation={0}
                        sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            flex: 1,
                            p: 1.5,
                            borderRadius: 0,
                            border: '1px solid var(--ds-color-border)',
                            backgroundColor: 'var(--ds-color-surface-bg)',
                            boxShadow: panelShadow,
                        }}
                    >
                        <Box sx={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto', gap: 1, alignItems: 'center', px: 0.5, py: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.1, minWidth: 0 }}>
                                <Box
                                    sx={{
                                        width: 36,
                                        height: 36,
                                        borderRadius: 0,
                                        display: 'grid',
                                        placeItems: 'center',
                                        background: isDark ? 'rgba(37, 99, 235, 0.16)' : 'rgba(37, 99, 235, 0.08)',
                                        color: '#2563eb',
                                        flex: '0 0 auto',
                                    }}
                                >
                                    <StoreIcon />
                                </Box>
                                <Box sx={{ minWidth: 0 }}>
                                    <Typography sx={{ fontSize: 14, fontWeight: 800, lineHeight: 1.3, color: 'var(--ds-color-text-strong)' }}>
                                        {t('applicationsHubPage.deployPage.cards.marketplace.title')}
                                    </Typography>
                                    <Typography sx={{ mt: 0.2, fontSize: 12, lineHeight: 1.45, color: 'var(--ds-color-text-muted)' }}>
                                        {t('applicationsHubPage.deployPage.cards.marketplace.description')}
                                    </Typography>
                                </Box>
                            </Box>
                            {hotApps.length > STORE_PAGE_SIZE && !appStoreLoading && (
                                <Tooltip title={t('applicationsHubPage.deployPage.cards.marketplace.shuffle')} placement="top">
                                    <IconButton
                                        size="small"
                                        onClick={handleShuffle}
                                        sx={{
                                            display: 'inline-flex',
                                            alignItems: 'center',
                                            gap: 0.5,
                                            px: { xs: 0.8, sm: 1 },
                                            py: 0.5,
                                            borderRadius: 0,
                                            border: '1px solid var(--ds-color-border)',
                                            color: 'var(--ds-color-text-muted)',
                                            fontSize: 12,
                                            fontWeight: 700,
                                            minHeight: 34,
                                            '&:hover': { color: '#2563eb', borderColor: '#2563eb', backgroundColor: isDark ? 'rgba(37,99,235,0.08)' : 'rgba(37,99,235,0.05)' },
                                        }}
                                    >
                                        <AutorenewIcon />
                                        <Box component="span" sx={{ fontSize: 12, fontWeight: 700, ml: 0.4, display: { xs: 'none', sm: 'inline' } }}>
                                            {t('applicationsHubPage.deployPage.cards.marketplace.shuffle')}
                                        </Box>
                                    </IconButton>
                                </Tooltip>
                            )}
                        </Box>

                        <Box sx={{ height: '1px', backgroundColor: subtleDivider, mx: 0.5 }} />

                        <Box sx={{ px: 0.5, pt: 1, pb: 0.5, display: 'flex', flexDirection: 'column', gap: 1, flex: 1 }}>
                            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: { xs: 0.75, sm: 1.25, md: 1.5 } }}>
                                {appStoreLoading
                                    ? Array.from({ length: STORE_PAGE_SIZE }).map((_, i) => (
                                        <Box
                                            key={`skeleton-${i}`}
                                            sx={{
                                                display: 'grid',
                                                gridTemplateColumns: { xs: '1fr', sm: 'auto minmax(0, 1fr) auto' },
                                                alignItems: { xs: 'flex-start', sm: 'center' },
                                                gap: { xs: 0.65, sm: 1.25 },
                                                minHeight: { xs: 92, sm: 'auto' },
                                                p: { xs: '10px 8px', sm: '16px 16px' },
                                                borderRadius: 0,
                                                border: '1px solid var(--ds-color-border)',
                                                backgroundColor: 'var(--ds-color-surface-bg)',
                                            }}
                                        >
                                            <Skeleton variant="rectangular" width={30} height={30} />
                                            <Box sx={{ minWidth: 0 }}>
                                                <Skeleton variant="text" width={`${55 + (i % 3) * 12}%`} height={16} />
                                                <Skeleton variant="text" width={`${40 + (i % 4) * 10}%`} height={12} sx={{ mt: 0.5, display: { xs: 'none', sm: 'block' } }} />
                                            </Box>
                                            <Skeleton variant="circular" width={8} height={8} sx={{ display: { xs: 'none', sm: 'block' } }} />
                                        </Box>
                                    ))
                                    : currentStoreApps.map((app) => (
                                        <AppCardItem
                                            key={app.key}
                                            app={app}
                                            fallbackLabel={app.trademark?.trim() || app.key || ''}
                                            onClick={() => openFeaturedApp(app.key ?? '')}
                                            isDark={isDark}
                                        />
                                    ))}
                            </Box>

                            <Box
                                sx={{
                                    pt: 1,
                                    mt: 'auto',
                                    borderTop: `1px solid ${subtleDivider}`,
                                    display: 'flex',
                                    justifyContent: { xs: 'stretch', sm: 'flex-end' },
                                }}
                            >
                                <Button
                                    variant="contained"
                                    onClick={() => navigate('/appstore')}
                                    sx={{
                                        minHeight: { xs: 40, sm: 38 },
                                        px: 2.1,
                                        width: { xs: '100%', sm: 'auto' },
                                        borderRadius: 0,
                                        textTransform: 'none',
                                        boxShadow: 'none',
                                        fontWeight: 800,
                                        backgroundColor: '#2563eb',
                                        '&:hover': { backgroundColor: '#1d4ed8' },
                                    }}
                                >
                                    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}>
                                        <span>{t('applicationsHubPage.deployPage.cards.marketplace.action')}</span>
                                        <ArrowIcon />
                                    </Box>
                                </Button>
                            </Box>
                        </Box>
                    </Paper>
                </Box>

                <Box sx={{ flex: { xs: '1 1 auto', md: '1 1 0%' }, minWidth: 0, width: '100%', display: 'flex' }}>
                    <Paper
                        elevation={0}
                        sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            flex: 1,
                            p: 1.5,
                            borderRadius: 0,
                            border: '1px solid var(--ds-color-border)',
                            backgroundColor: 'var(--ds-color-surface-bg)',
                            boxShadow: panelShadow,
                        }}
                    >
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, flex: 1 }}>
                            <Box sx={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: 1.25, alignItems: 'center', pb: 1.25, borderBottom: `1px solid ${subtleDivider}` }}>
                                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.15, minWidth: 0 }}>
                                    <Box
                                        sx={{
                                            width: 36,
                                            height: 36,
                                            borderRadius: 0,
                                            display: 'grid',
                                            placeItems: 'center',
                                            backgroundColor: isDark ? 'rgba(37, 99, 235, 0.16)' : 'rgba(37, 99, 235, 0.08)',
                                            color: '#2563eb',
                                            flex: '0 0 auto',
                                        }}
                                    >
                                        <ComposeIcon />
                                    </Box>
                                    <Box sx={{ minWidth: 0 }}>
                                        <Typography sx={{ fontSize: 14, fontWeight: 900, lineHeight: 1.25, color: 'var(--ds-color-text-strong)' }}>
                                            {t('applicationsHubPage.deployPage.cards.compose.title')}
                                        </Typography>
                                        <Typography sx={{ mt: 0.2, fontSize: 12, lineHeight: 1.45, color: 'var(--ds-color-text-muted)' }}>
                                            {t('applicationsHubPage.deployPage.cards.compose.description')}
                                        </Typography>
                                    </Box>
                                </Box>
                            </Box>

                            <Box
                                sx={{
                                    p: 1.5,
                                    borderRadius: 0,
                                    border: `1px solid ${panelBorder}`,
                                    backgroundColor: 'var(--ds-color-surface-bg)',
                                }}
                            >
                                <Box sx={{ display: 'grid', gap: 1.5 }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6, color: '#2563eb' }}>
                                        <FlowIcon />
                                        <Typography sx={{ fontSize: 12, fontWeight: 800, color: 'var(--ds-color-text-strong)' }}>
                                            {t('applicationsHubPage.deployPage.cards.compose.flow.title')}
                                        </Typography>
                                    </Box>

                                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0 }}>
                                        {composeSteps.map((step, index) => (
                                            <Box key={step.key} sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.75, position: 'relative', px: 0.5 }}>
                                                <Box
                                                    sx={{
                                                        width: 32,
                                                        height: 32,
                                                        borderRadius: '50%',
                                                        display: 'grid',
                                                        placeItems: 'center',
                                                        fontSize: 13,
                                                        fontWeight: 800,
                                                        color: '#ffffff',
                                                        backgroundColor: '#2563eb',
                                                        position: 'relative',
                                                        zIndex: 1,
                                                    }}
                                                >
                                                    {step.index}
                                                </Box>
                                                {index < composeSteps.length - 1 ? (
                                                    <Box
                                                        sx={{
                                                            position: 'absolute',
                                                            top: 15,
                                                            left: 'calc(50% + 16px)',
                                                            right: 'calc(-50% + 16px)',
                                                            height: 2,
                                                            backgroundColor: isDark ? 'rgba(148, 163, 184, 0.22)' : 'rgba(148, 163, 184, 0.28)',
                                                        }}
                                                    />
                                                ) : null}
                                                <Typography sx={{ fontSize: 12, fontWeight: 700, lineHeight: 1.3, color: 'var(--ds-color-text-strong)', textAlign: 'center' }}>
                                                    {step.title}
                                                </Typography>
                                                <Typography sx={{ fontSize: 10.5, lineHeight: 1.4, color: 'var(--ds-color-text-muted)', textAlign: 'center' }}>
                                                    {step.detail}
                                                </Typography>
                                            </Box>
                                        ))}
                                    </Box>
                                </Box>
                            </Box>

                            <Box sx={{ display: 'grid', gap: 2 }}>
                                {composeCapabilities.map((item) => (
                                    <Box
                                        key={item.key}
                                        sx={{
                                            display: 'flex',
                                            alignItems: 'flex-start',
                                            gap: 1,
                                            p: '10px 12px',
                                            borderRadius: 0,
                                            border: '1px solid var(--ds-color-border)',
                                            backgroundColor: 'var(--ds-color-surface-bg)',
                                        }}
                                    >
                                        <Box
                                            sx={{
                                                width: 28,
                                                height: 28,
                                                borderRadius: 0,
                                                display: 'grid',
                                                placeItems: 'center',
                                                backgroundColor: isDark ? 'rgba(37, 99, 235, 0.16)' : 'rgba(37, 99, 235, 0.08)',
                                                color: '#2563eb',
                                                flexShrink: 0,
                                                fontSize: 10,
                                                fontWeight: 800,
                                            }}
                                        >
                                            {item.key === 'compose' ? '{}' : item.key === 'env' ? '$' : 'M'}
                                        </Box>
                                        <Box sx={{ minWidth: 0, flex: 1 }}>
                                            <Typography sx={{ fontSize: 12.5, fontWeight: 700, lineHeight: 1.35, color: 'var(--ds-color-text-strong)' }}>
                                                {item.title}
                                            </Typography>
                                            <Typography sx={{ mt: 0.2, fontSize: 11.5, lineHeight: 1.45, color: 'var(--ds-color-text-muted)' }}>
                                                {item.detail}
                                            </Typography>
                                            <Box sx={{ mt: 0.5, display: 'flex', flexWrap: 'wrap', gap: 0.4 }}>
                                                {item.badges.map((badge) => (
                                                    <Box
                                                        key={badge}
                                                        sx={{
                                                            display: 'inline-flex',
                                                            alignItems: 'center',
                                                            minHeight: 18,
                                                            px: 0.55,
                                                            borderRadius: '999px',
                                                            backgroundColor: pillBackground,
                                                            fontSize: 10,
                                                            fontWeight: 700,
                                                            color: '#94a3b8',
                                                        }}
                                                    >
                                                        {badge}
                                                    </Box>
                                                ))}
                                            </Box>
                                        </Box>
                                    </Box>
                                ))}
                            </Box>

                            <Box
                                sx={{
                                    pt: 1.25,
                                    mt: 'auto',
                                    px: 0.5,
                                    borderTop: `1px solid ${subtleDivider}`,
                                    display: 'flex',
                                    justifyContent: { xs: 'stretch', sm: 'flex-end' },
                                }}
                            >
                                <Button
                                    variant="contained"
                                    onClick={() => navigate('/applications/custom-install')}
                                    sx={{
                                        minHeight: { xs: 40, sm: 38 },
                                        px: 2.1,
                                        width: { xs: '100%', sm: 'auto' },
                                        borderRadius: 0,
                                        textTransform: 'none',
                                        boxShadow: 'none',
                                        fontWeight: 800,
                                        backgroundColor: '#2563eb',
                                        '&:hover': { backgroundColor: '#1d4ed8' },
                                    }}
                                >
                                    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}>
                                        <span>{t('applicationsHubPage.deployPage.cards.compose.action')}</span>
                                        <ArrowIcon />
                                    </Box>
                                </Button>
                            </Box>
                        </Box>
                    </Paper>
                </Box>
            </Box>
        </Box>
    )
}