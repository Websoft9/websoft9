import {
    Avatar,
    Box,
    IconButton,
    List,
    ListItemButton,
    Menu,
    SvgIcon,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAppColorMode } from '../providers/color-mode'
import { useProductAuth } from '../../features/product-auth/product-auth-provider'
import { normalizeSupportedLocale, supportedLocales } from '../../shared/i18n/i18n'
import { PersistentIntegrationWorkspaces } from '../../features/integrations/integration-workspace-page'
import { useIntegrationSessionPrewarm } from '../../features/integrations/integration-session-bootstrap'
import { shellNavigationItems } from './shell-navigation'
import './app-shell.css'

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
const SHELL_NAV_COLLAPSED_STORAGE_KEY = 'websoft9:shell-nav-collapsed'

function ShellNavIcon({ segment }: { segment: string }) {
    switch (segment) {
        case 'dashboard':
            return <SvgIcon viewBox="0 0 24 24"><path d="M4 4h7v7H4V4Zm9 0h7v5h-7V4ZM4 13h7v7H4v-7Zm9-2h7v9h-7v-9Z" /></SvgIcon>
        case 'appstore':
            return <SvgIcon viewBox="0 0 24 24"><path d="M7 4h10l1 4h2v2h-1l-1 9H6L5 10H4V8h2l1-4Zm1.58 4h6.84l-.5-2H9.08l-.5 2ZM8 12v5h2v-5H8Zm6 0v5h2v-5h-2Z" /></SvgIcon>
        case 'myapps':
            return <SvgIcon viewBox="0 0 24 24"><path d="M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm0 4v10h12V8H6Zm2 2h4v4H8v-4Z" /></SvgIcon>
        case 'containers':
            return <SvgIcon viewBox="0 0 24 24"><path d="M3 7.5 12 3l9 4.5V16l-9 5-9-5V7.5Zm2 1.24V14.8l6 3.33V12L5 8.74Zm14 0L13 12v6.13l6-3.33V8.74ZM12 10.26l6.02-3.01L12 4.24 5.98 7.25 12 10.26Z" /></SvgIcon>
        case 'gateway':
            return <SvgIcon viewBox="0 0 24 24"><path d="M12 3 4 7v5c0 4.97 3.44 9.62 8 10.8 4.56-1.18 8-5.83 8-10.8V7l-8-4Zm0 2.18 6 3v3.64c0 3.86-2.52 7.57-6 8.73-3.48-1.16-6-4.87-6-8.73V8.18l6-3ZM8 11h8v2H8v-2Z" /></SvgIcon>
        case 'repository':
            return <SvgIcon viewBox="0 0 24 24"><path d="M5 4h9a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H5V4Zm2 2v12h7a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H7Zm11 1h2v10h-2V7Z" /></SvgIcon>
        case 'files':
            return <SvgIcon viewBox="0 0 24 24"><path d="M4 6a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v8a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V6Zm2 1v9a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V8h-7.17L8.83 7H6Z" /></SvgIcon>
        case 'terminal':
            return <SvgIcon viewBox="0 0 24 24"><path d="M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Zm0 2v10h16V7H4Zm3 2 4 3-4 3v-2l1.5-1L7 11V9Zm6 4h4v2h-4v-2Z" /></SvgIcon>
        case 'services':
            return <SvgIcon viewBox="0 0 24 24"><path d="M13.73 3 15 5.55l2.82.41-2.04 1.99.48 2.81L13.73 9.4 11.2 10.76l.48-2.81-2.04-1.99 2.82-.41L13.73 3ZM6 13h5v2H6v-2Zm0 4h12v2H6v-2Zm7-4h5v2h-5v-2Z" /></SvgIcon>
        case 'logs':
            return <SvgIcon viewBox="0 0 24 24"><path d="M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm1 4v2h10V8H7Zm0 4v2h10v-2H7Zm0 4v2h7v-2H7Z" /></SvgIcon>
        case 'users':
            return <SvgIcon viewBox="0 0 24 24"><path d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Zm0 2c-3.33 0-6 1.79-6 4v1h12v-1c0-2.21-2.67-4-6-4Zm7-4a3 3 0 1 0-2.99-3A3 3 0 0 0 19 10Zm0 5c-.71 0-1.38.08-2 .22A5.55 5.55 0 0 1 20 19v1h2v-1c0-2.21-1.79-4-4-4Z" /></SvgIcon>
        case 'settings':
            return <SvgIcon viewBox="0 0 24 24"><path d="m19.14 12.94.04-.94-.04-.94 2.03-1.58-1.92-3.32-2.39.97a7.4 7.4 0 0 0-1.63-.94L14.96 2h-3.92l-.27 2.19c-.58.22-1.13.53-1.63.94l-2.39-.97-1.92 3.32 2.03 1.58-.04.94.04.94-2.03 1.58 1.92 3.32 2.39-.97c.5.41 1.05.72 1.63.94l.27 2.19h3.92l.27-2.19c.58-.22 1.13-.53 1.63-.94l2.39.97 1.92-3.32-2.03-1.58ZM13 15.5A3.5 3.5 0 1 1 13 8.5a3.5 3.5 0 0 1 0 7Z" /></SvgIcon>
        default:
            return <SvgIcon viewBox="0 0 24 24"><path d="M5 5h14v14H5z" /></SvgIcon>
    }
}

function ChevronLeftIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="m14.41 7.41-1.41-1.41L7.59 11.41 13 16.83l1.41-1.42L10.41 11l4-3.59Z" /></SvgIcon>
}

function ChevronRightIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="m9.59 16.59 1.41 1.41 5.41-5.41L11 7.17 9.59 8.59 13.59 12l-4 4.59Z" /></SvgIcon>
}

function SunIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M6.76 4.84 5.35 3.43 3.93 4.85l1.41 1.41 1.42-1.42ZM1 13h3v-2H1v2Zm10 10h2v-3h-2v3Zm9.07-18.15-1.41-1.42-1.42 1.42 1.41 1.41 1.42-1.41ZM17.66 18.36l1.41 1.41 1.42-1.41-1.42-1.42-1.41 1.42ZM20 13h3v-2h-3v2ZM11 1v3h2V1h-2Zm6 11a5 5 0 1 1-5-5 5 5 0 0 1 5 5ZM4.93 19.07l1.41-1.41-1.42-1.42-1.41 1.42 1.42 1.41Z" /></SvgIcon>
}

function MoonIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 0 1 11.21 3c0-.34.02-.67.05-1A1 1 0 0 0 10 1 10 10 0 1 0 22 13a1 1 0 0 0-1-1 8.36 8.36 0 0 1 0 .79Z" /></SvgIcon>
}

function PersonIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M12 12a4.25 4.25 0 1 0-4.25-4.25A4.26 4.26 0 0 0 12 12Zm0 2.13c-3.45 0-6.25 2.19-6.25 4.87V21h12.5v-2c0-2.68-2.8-4.87-6.25-4.87Z" /></SvgIcon>
}

function LocaleBadgeIcon({ label }: { label: string }) {
    return <Box className="app-shell-locale-badge">{label}</Box>
}

function LogoutIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M10 17v-3H3v-4h7V7l5 5-5 5Zm8 2h-6v-2h6V7h-6V5h6a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2Z" /></SvgIcon>
}

function SelectedIndicatorIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="m9.55 16.6-3.9-3.9 1.4-1.4 2.5 2.5 7.4-7.4 1.4 1.4-8.8 8.8Z" /></SvgIcon>
}

export function AppShell() {
    const { t, i18n } = useTranslation('shell')
    const navigate = useNavigate()
    const location = useLocation()
    const { isSubmitting, logout, refresh, status } = useProductAuth()
    const [userMenuAnchor, setUserMenuAnchor] = useState<HTMLElement | null>(null)
    const { colorMode, setColorMode } = useAppColorMode()
    const [navCollapsed, setNavCollapsed] = useState<boolean>(() => {
        if (typeof window === 'undefined') {
            return false
        }

        return window.localStorage.getItem(SHELL_NAV_COLLAPSED_STORAGE_KEY) === 'true'
    })

    const resolvedLocale = i18n.resolvedLanguage ?? supportedLocales[0]
    const activeIntegrationRoute = /^\/(containers|gateway|repository)$/.test(location.pathname)
    const isChineseLocale = resolvedLocale === 'zh-CN'
    const footerLinks = useMemo(
        () => [
            {
                key: 'website',
                href: isChineseLocale ? 'https://websoft9.com/' : 'https://websoft9.com/en-US/',
                label: t('footer.website'),
            },
            {
                key: 'github',
                href: 'https://github.com/Websoft9/',
                label: t('footer.github'),
            },
            {
                key: 'manual',
                href: isChineseLocale ? 'https://support.websoft9.com/' : 'https://support.websoft9.com/en/',
                label: t('footer.manual'),
            },
            {
                key: 'ticket',
                href: isChineseLocale ? 'https://websoft9.com/ticket' : 'https://websoft9.com/en-US/ticket',
                label: t('footer.ticket'),
            },
        ],
        [isChineseLocale, t],
    )

    useIntegrationSessionPrewarm()

    useEffect(() => {
        if (typeof window === 'undefined') {
            return
        }

        window.localStorage.setItem(SHELL_NAV_COLLAPSED_STORAGE_KEY, String(navCollapsed))
    }, [navCollapsed])

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

    async function persistCurrentUserLocale(locale: string) {
        const currentUser = status?.current_user
        if (!status?.enabled || !status.authenticated || !currentUser) {
            return
        }

        await fetch(`/api/auth/users/${encodeURIComponent(currentUser.id)}`, {
            method: 'PUT',
            credentials: 'include',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                display_name: currentUser.display_name,
                locale,
            }),
        })

        await refresh()
    }

    return (
        <Box className={`app-shell-root app-shell-root--${colorMode} ${navCollapsed ? 'app-shell-root--collapsed' : ''}`}>
            <Box className="app-shell-frame">
                <Box component="aside" className="app-shell-sidebar">
                    <Box className="app-shell-sidebar-inner">
                        <Box className="app-shell-sidebar-header">
                            <Box className="app-shell-brand">
                                <Box component="img" alt={t('brand.logoAriaLabel')} className="app-shell-brand-mark" src="/websoft9.png" />
                                <Box className="app-shell-brand-copy">
                                    <Typography className="app-shell-brand-title">{t('brand.title')}</Typography>
                                </Box>
                            </Box>
                        </Box>

                        <Box className="app-shell-nav-scroll">
                            {navigationSections.map((section) => (
                                <Box key={section.key} className="app-shell-nav-section">
                                    <Typography className="app-shell-section-label">
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
                                                    className="app-shell-nav-item"
                                                    title={t(`nav.${item.pageKey}.label`)}
                                                    to={item.segment === 'myapps' && rememberedMyAppDetailRoute && !location.pathname.startsWith('/myapps')
                                                        ? rememberedMyAppDetailRoute
                                                        : `/${item.segment}`}
                                                >
                                                    <Box className="app-shell-nav-item-icon" aria-hidden="true">
                                                        <ShellNavIcon segment={item.segment} />
                                                    </Box>
                                                    <Typography className="app-shell-nav-item-label" variant="body2">
                                                        {t(`nav.${item.pageKey}.label`)}
                                                    </Typography>
                                                </ListItemButton>
                                            )
                                        })}
                                    </List>
                                </Box>
                            ))}
                        </Box>
                    </Box>
                </Box>

                <IconButton
                    color="inherit"
                    className="app-shell-sidebar-toggle"
                    sx={{
                        position: 'absolute',
                        top: 'calc(var(--shell-topbar-height) / 2)',
                        left: 'var(--shell-sidebar-width)',
                        transform: 'translate(-50%, -50%)',
                        border: '1px solid var(--shell-topbar-border)',
                        backgroundColor: 'var(--shell-surface-bg)',
                        boxShadow: '0 8px 18px rgba(145, 158, 171, 0.18)',
                        '&:hover': {
                            backgroundColor: 'var(--shell-surface-soft)',
                        },
                    }}
                    onClick={() => {
                        setNavCollapsed((currentValue) => !currentValue)
                    }}
                    aria-label={navCollapsed ? t('navigation.expand', { defaultValue: 'Expand menu' }) : t('navigation.collapse', { defaultValue: 'Collapse menu' })}
                    title={navCollapsed ? t('navigation.expand', { defaultValue: 'Expand menu' }) : t('navigation.collapse', { defaultValue: 'Collapse menu' })}
                >
                    {navCollapsed ? <ChevronRightIcon /> : <ChevronLeftIcon />}
                </IconButton>

                <Box className="app-shell-content">
                    <Box className="app-shell-topbar">
                        <Box className="app-shell-topbar-actions">
                            <IconButton
                                color="inherit"
                                onClick={(event) => {
                                    if (userMenuAnchor) {
                                        setUserMenuAnchor(null)
                                        return
                                    }

                                    setUserMenuAnchor(event.currentTarget)
                                }}
                                className="app-shell-user-trigger"
                                aria-label={t('user.menu.profile')}
                                title={t('user.menu.profile')}
                            >
                                <Avatar className="app-shell-user-avatar">
                                    <PersonIcon />
                                </Avatar>
                            </IconButton>
                        </Box>
                    </Box>

                    <Box
                        component="main"
                        className={`app-shell-main ${location.pathname === '/dashboard' ? 'app-shell-main--dashboard' : ''}`}
                        sx={{
                            px: activeIntegrationRoute ? 0 : { xs: 2, md: 3 },
                            py: activeIntegrationRoute ? 0 : { xs: 2, md: 2.5 },
                            overflowY: activeIntegrationRoute ? 'hidden' : 'auto',
                        }}
                    >
                        <Box className="app-shell-main-body">
                            <PersistentIntegrationWorkspaces />
                            <Outlet />
                        </Box>
                    </Box>

                    <Box component="footer" className="app-shell-footer">
                        <Box className="app-shell-footer-inner">
                            <Typography component="span" className="app-shell-footer-copy">{t('footer.copyright')}</Typography>
                            {footerLinks.map((link) => (
                                <Box key={link.key} sx={{ display: 'contents' }}>
                                    <span className="app-shell-footer-separator" aria-hidden="true">|</span>
                                    <a className="app-shell-footer-link" href={link.href} rel="noreferrer" target="_blank">
                                        {link.label}
                                    </a>
                                </Box>
                            ))}
                        </Box>
                    </Box>
                </Box>
            </Box>

            <Menu
                anchorEl={userMenuAnchor}
                open={Boolean(userMenuAnchor)}
                onClose={() => {
                    setUserMenuAnchor(null)
                }}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                slotProps={{
                    paper: {
                        className: `app-shell-account-menu app-shell-account-menu--${colorMode}`,
                    },
                }}
            >
                <Box className="app-shell-account-panel">
                    <List disablePadding className="app-shell-account-links">
                        <Typography className="app-shell-account-section-label">
                            {t('user.menu.session')}
                        </Typography>

                        <ListItemButton
                            className={`app-shell-account-link ${location.pathname.startsWith('/users') ? 'active' : ''}`}
                            onClick={() => {
                                setUserMenuAnchor(null)
                                navigate('/users')
                            }}
                        >
                            <Box className="app-shell-account-link-icon"><ShellNavIcon segment="users" /></Box>
                            <Typography className="app-shell-account-link-title">{t('user.menu.profile')}</Typography>
                        </ListItemButton>

                        <ListItemButton
                            className="app-shell-account-link app-shell-account-link--danger"
                            onClick={() => {
                                if (!status?.enabled || !status.authenticated || isSubmitting) {
                                    return
                                }

                                setUserMenuAnchor(null)

                                void logout().then(() => {
                                    navigate('/auth/login', { replace: true })
                                })
                            }}
                            disabled={!status?.enabled || !status.authenticated || isSubmitting}
                        >
                            <Box className="app-shell-account-link-icon"><LogoutIcon /></Box>
                            <Typography className="app-shell-account-link-title">{t('user.menu.signOut')}</Typography>
                        </ListItemButton>

                        <Typography className="app-shell-account-section-label">
                            {t('preferences.language')}
                        </Typography>

                        {supportedLocales.map((locale) => {
                            const isActive = resolvedLocale === locale

                            return (
                                <ListItemButton
                                    key={locale}
                                    className={`app-shell-account-link ${isActive ? 'active app-shell-account-link--selected' : ''}`}
                                    onClick={() => {
                                        const normalizedLocale = normalizeSupportedLocale(locale)
                                        if (normalizedLocale === normalizeSupportedLocale(i18n.resolvedLanguage ?? i18n.language ?? 'en')) {
                                            return
                                        }

                                        setUserMenuAnchor(null)
                                        void i18n.changeLanguage(normalizedLocale)
                                        void persistCurrentUserLocale(normalizedLocale)
                                    }}
                                >
                                    <Box className="app-shell-account-link-icon">
                                        {locale === 'en' ? <LocaleBadgeIcon label="EN" /> : <LocaleBadgeIcon label="中" />}
                                    </Box>
                                    <Typography className="app-shell-account-link-title">{t(`locales.${locale}`)}</Typography>
                                    {isActive ? <Box className="app-shell-account-link-trailing"><SelectedIndicatorIcon /></Box> : null}
                                </ListItemButton>
                            )
                        })}

                        <Typography className="app-shell-account-section-label">
                            {t('preferences.appearance')}
                        </Typography>

                        <ListItemButton
                            className={`app-shell-account-link ${colorMode === 'light' ? 'active app-shell-account-link--selected' : ''}`}
                            onClick={() => {
                                setUserMenuAnchor(null)
                                setColorMode('light')
                            }}
                        >
                            <Box className="app-shell-account-link-icon"><SunIcon /></Box>
                            <Typography className="app-shell-account-link-title">{t('preferences.light')}</Typography>
                            {colorMode === 'light' ? <Box className="app-shell-account-link-trailing"><SelectedIndicatorIcon /></Box> : null}
                        </ListItemButton>

                        <ListItemButton
                            className={`app-shell-account-link ${colorMode === 'dark' ? 'active app-shell-account-link--selected' : ''}`}
                            onClick={() => {
                                setUserMenuAnchor(null)
                                setColorMode('dark')
                            }}
                        >
                            <Box className="app-shell-account-link-icon"><MoonIcon /></Box>
                            <Typography className="app-shell-account-link-title">{t('preferences.dark')}</Typography>
                            {colorMode === 'dark' ? <Box className="app-shell-account-link-trailing"><SelectedIndicatorIcon /></Box> : null}
                        </ListItemButton>
                    </List>
                </Box>
            </Menu>
        </Box>
    )
}