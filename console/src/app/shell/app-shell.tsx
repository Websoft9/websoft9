import {
    Avatar,
    Box,
    Button,
    List,
    ListItemButton,
    Menu,
    MenuItem,
    Stack,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { supportedLocales } from '../../shared/i18n/i18n'
import { PersistentIntegrationWorkspaces } from '../../features/integrations/integration-workspace-page'
import { shellNavigationItems } from './shell-navigation'

const navigationSections = [
    {
        key: 'system',
        segments: ['dashboard', 'appstore', 'myapps', 'containers', 'gateway', 'repository', 'files', 'terminal'],
    },
    {
        key: 'tools',
        segments: ['services', 'logs', 'users', 'settings'],
    },
] as const

const LAST_MYAPP_DETAIL_ROUTE_KEY = 'websoft9:last-myapp-detail-route'

export function AppShell() {
    const { t, i18n } = useTranslation('shell')
    const location = useLocation()
    const [localeMenuAnchor, setLocaleMenuAnchor] = useState<HTMLElement | null>(null)
    const [userMenuAnchor, setUserMenuAnchor] = useState<HTMLElement | null>(null)

    const resolvedLocale = i18n.resolvedLanguage ?? supportedLocales[0]
    const activeIntegrationRoute = /^\/(containers|gateway|repository)$/.test(location.pathname)

    useEffect(() => {
        if (typeof window === 'undefined') {
            return
        }

        const pathWithSearch = `${location.pathname}${location.search}`

        if (/^\/myapps\/[^/]+/.test(location.pathname)) {
            window.sessionStorage.setItem(LAST_MYAPP_DETAIL_ROUTE_KEY, pathWithSearch)
            return
        }

        if (location.pathname === '/myapps') {
            window.sessionStorage.removeItem(LAST_MYAPP_DETAIL_ROUTE_KEY)
        }
    }, [location.pathname, location.search])

    const rememberedMyAppDetailRoute = useMemo(() => {
        if (typeof window === 'undefined') {
            return null
        }

        return window.sessionStorage.getItem(LAST_MYAPP_DETAIL_ROUTE_KEY)
    }, [location.pathname, location.search])

    return (
        <Box
            sx={{
                height: '100vh',
                overflow: 'hidden',
                backgroundColor: '#e8edf4',
            }}
        >
            <Box
                sx={{
                    height: 76,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    px: { xs: 2, md: 3 },
                    backgroundColor: '#f7f9fc',
                    borderBottom: '1px solid rgba(15, 23, 42, 0.05)',
                }}
            >
                <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                    <Box
                        aria-label={t('brand.logoAriaLabel')}
                        sx={{
                            width: 34,
                            height: 34,
                            borderRadius: 1.5,
                            border: '1px solid rgba(15, 23, 42, 0.1)',
                            backgroundColor: '#ffffff',
                            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.7)',
                        }}
                    />
                    <Typography sx={{ fontSize: 28, fontWeight: 500, lineHeight: 1.1 }}>
                        {t('brand.title')}
                    </Typography>
                </Stack>

                <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                    <Button
                        color="inherit"
                        onClick={(event) => {
                            setLocaleMenuAnchor(event.currentTarget)
                        }}
                        sx={{
                            borderRadius: 1.5,
                            border: '1px solid rgba(15, 23, 42, 0.08)',
                            px: 1.25,
                            py: 0.625,
                            textTransform: 'none',
                        }}
                    >
                        <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
                            <Typography color="text.secondary" sx={{ fontSize: 12 }}>
                                {t('localeSwitcher.label')}
                            </Typography>
                            <Typography sx={{ fontSize: 13, fontWeight: 600 }}>
                                {t(`locales.${resolvedLocale}`)}
                            </Typography>
                        </Stack>
                    </Button>

                    <Button
                        color="inherit"
                        onClick={(event) => {
                            setUserMenuAnchor(event.currentTarget)
                        }}
                        sx={{
                            borderRadius: 1.5,
                            border: '1px solid rgba(15, 23, 42, 0.08)',
                            px: 0.875,
                            py: 0.5,
                            textTransform: 'none',
                        }}
                    >
                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                            <Avatar sx={{ width: 30, height: 30, bgcolor: '#d7e3f4', color: '#24446b', fontSize: 13 }}>U</Avatar>
                            <Stack spacing={0} sx={{ alignItems: 'flex-start' }}>
                                <Typography sx={{ fontSize: 13, fontWeight: 600, lineHeight: 1.1 }}>
                                    {t('user.name')}
                                </Typography>
                                <Typography color="text.secondary" sx={{ fontSize: 11, lineHeight: 1.1 }}>
                                    {t('user.role')}
                                </Typography>
                            </Stack>
                        </Stack>
                    </Button>
                </Stack>
            </Box>

            <Menu
                anchorEl={localeMenuAnchor}
                onClose={() => {
                    setLocaleMenuAnchor(null)
                }}
                open={Boolean(localeMenuAnchor)}
            >
                {supportedLocales.map((locale) => (
                    <MenuItem
                        key={locale}
                        onClick={() => {
                            void i18n.changeLanguage(locale)
                            setLocaleMenuAnchor(null)
                        }}
                        selected={resolvedLocale === locale}
                    >
                        {t(`locales.${locale}`)}
                    </MenuItem>
                ))}
            </Menu>

            <Menu
                anchorEl={userMenuAnchor}
                onClose={() => {
                    setUserMenuAnchor(null)
                }}
                open={Boolean(userMenuAnchor)}
            >
                <MenuItem
                    onClick={() => {
                        setUserMenuAnchor(null)
                    }}
                >
                    {t('user.menu.profile')}
                </MenuItem>
                <MenuItem
                    onClick={() => {
                        setUserMenuAnchor(null)
                    }}
                >
                    {t('user.menu.preferences')}
                </MenuItem>
                <MenuItem
                    onClick={() => {
                        setUserMenuAnchor(null)
                    }}
                >
                    {t('user.menu.signOut')}
                </MenuItem>
            </Menu>

            <Box
                sx={{
                    display: 'grid',
                    height: 'calc(100vh - 76px)',
                    overflow: 'hidden',
                    gridTemplateColumns: { xs: '1fr', lg: '238px minmax(0, 1fr)' },
                }}
            >
                <Box
                    component="aside"
                    sx={{
                        backgroundColor: '#f6f8fb',
                        borderRight: { lg: '1px solid rgba(15, 23, 42, 0.04)' },
                        borderBottom: { xs: '1px solid rgba(15, 23, 42, 0.04)', lg: 'none' },
                        px: 1.5,
                        py: 1.75,
                        overflowY: 'auto',
                    }}
                >
                    <Stack spacing={2.25} sx={{ pl: 1.25 }}>
                        {navigationSections.map((section) => (
                            <Stack key={section.key} spacing={0.875}>
                                <Typography
                                    color="text.secondary"
                                    sx={{
                                        px: 1.5,
                                        pt: 0.25,
                                        fontSize: 14,
                                        fontWeight: 700,
                                        letterSpacing: 0,
                                        lineHeight: 1.3,
                                    }}
                                >
                                    {t(`navigation.sections.${section.key}`)}
                                </Typography>
                                <List disablePadding>
                                    {section.segments.map((segment) => {
                                        const item = shellNavigationItems.find((entry) => entry.segment === segment)

                                        if (!item) {
                                            return null
                                        }

                                        return (
                                            <ListItemButton
                                                component={NavLink}
                                                key={item.segment}
                                                sx={{
                                                    minHeight: 40,
                                                    borderRadius: 1.5,
                                                    mb: 0.625,
                                                    px: 1.5,
                                                    py: 0.625,
                                                    color: '#2d3748',
                                                    transition: 'background-color 120ms ease, color 120ms ease',
                                                    '&.active': {
                                                        backgroundColor: '#ffffff',
                                                        color: '#1f2937',
                                                        boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
                                                        '& .MuiTypography-root': {
                                                            fontWeight: 600,
                                                        },
                                                    },
                                                    '&:hover': {
                                                        backgroundColor: 'rgba(255,255,255,0.62)',
                                                    },
                                                }}
                                                to={item.segment === 'myapps' && rememberedMyAppDetailRoute && !location.pathname.startsWith('/myapps')
                                                    ? rememberedMyAppDetailRoute
                                                    : `/${item.segment}`}
                                            >
                                                <Typography sx={{ fontSize: 14, fontWeight: 500, lineHeight: 1.35 }} variant="body2">
                                                    {t(`nav.${item.pageKey}.label`)}
                                                </Typography>
                                            </ListItemButton>
                                        )
                                    })}
                                </List>
                            </Stack>
                        ))}
                    </Stack>
                </Box>

                <Box
                    component="main"
                    sx={{
                        minWidth: 0,
                        backgroundColor: '#ffffff',
                        px: activeIntegrationRoute ? 0 : { xs: 2, md: 3 },
                        py: activeIntegrationRoute ? 0 : { xs: 2, md: 2.5 },
                        overflowY: activeIntegrationRoute ? 'hidden' : 'auto',
                    }}
                >
                    <PersistentIntegrationWorkspaces />
                    <Outlet />
                </Box>
            </Box>
        </Box>
    )
}