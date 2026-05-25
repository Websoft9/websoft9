import {
    Avatar,
    Box,
    Button,
    IconButton,
    List,
    ListItemButton,
    Menu,
    Paper,
    Popper,
    SvgIcon,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAppColorMode } from '../providers/color-mode'
import { useProductAuth } from '../../features/product-auth/product-auth-provider'
import { normalizeSupportedLocale } from '../../shared/i18n/i18n'
import { PersistentIntegrationWorkspaces } from '../../features/integrations/integration-workspace-page'
import { useIntegrationSessionPrewarm } from '../../features/integrations/integration-session-bootstrap'
import { getRememberedMyAppsDetailRoute, rememberMyAppsDetailRoute } from '../../features/my-apps/my-app-detail-overlay-intent'
import { shellNavigationItems } from './shell-navigation'
import './app-shell.css'

type AppNavIconSegment = (typeof shellNavigationItems)[number]['segment'] | 'appstore' | 'custom-install'

type ApplicationSubNavigationItem = {
    key: string
    label: string
    to: string
    active: boolean
    icon: AppNavIconSegment
}

const navigationSections = [
    {
        key: 'system',
        segments: ['dashboard', 'applications', 'containers', 'gateway', 'repository'],
    },
    {
        key: 'tools',
        segments: ['terminal', 'services', 'logs', 'users', 'settings'],
    },
] as const

const LAST_APPLICATIONS_ROUTE_KEY = 'websoft9:last-applications-route'
const SHELL_NAV_COLLAPSED_STORAGE_KEY = 'websoft9:shell-nav-collapsed'

function ShellNavIcon({ segment }: { segment: AppNavIconSegment }) {
    switch (segment) {
        case 'dashboard':
            return <SvgIcon viewBox="0 0 24 24"><path d="M4 4h7v7H4V4Zm9 0h7v5h-7V4ZM4 13h7v7H4v-7Zm9-2h7v9h-7v-9Z" /></SvgIcon>
        case 'applications':
            return <SvgIcon viewBox="0 0 24 24"><path d="M4 5h7v6H4V5Zm9 0h7v6h-7V5ZM4 13h7v6H4v-6Zm9 0h7v6h-7v-6Zm-7-6v2h3V7H6Zm9 0v2h3V7h-3Zm-9 8v2h3v-2H6Zm9 0v2h3v-2h-3Z" /></SvgIcon>
        case 'appstore':
            return <SvgIcon viewBox="0 0 24 24"><path d="M6.2 4h11.6l1.35 4.6h1.1v1.8H19V18a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7.6H3.75V8.6h1.1L6.2 4Zm1.35 1.8-.82 2.8h10.54l-.82-2.8H7.55ZM6.8 10.4V18a.2.2 0 0 0 .2.2h10a.2.2 0 0 0 .2-.2v-7.6H6.8Zm2.2 2.2h6v1.8H9v-1.8Z" /></SvgIcon>
        case 'myapps':
            return <SvgIcon viewBox="0 0 24 24"><path d="M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm0 4v10h12V8H6Zm2 2h4v4H8v-4Z" /></SvgIcon>
        case 'custom-install':
            return <SvgIcon viewBox="0 0 24 24"><path d="M4 6.5A2.5 2.5 0 0 1 6.5 4H11v2H6.5a.5.5 0 0 0-.5.5V11H4V6.5Zm9-2.5h4.5A2.5 2.5 0 0 1 20 6.5V11h-2V6.5a.5.5 0 0 0-.5-.5H13V4ZM4 13h2v4.5a.5.5 0 0 0 .5.5H11v2H6.5A2.5 2.5 0 0 1 4 17.5V13Zm14 0h2v4.5a2.5 2.5 0 0 1-2.5 2.5H13v-2h4.5a.5.5 0 0 0 .5-.5V13Zm-7-4 5 3-5 3V9Z" /></SvgIcon>
        case 'containers':
            return <SvgIcon viewBox="0 0 24 24"><path d="M3 7.5 12 3l9 4.5V16l-9 5-9-5V7.5Zm2 1.24V14.8l6 3.33V12L5 8.74Zm14 0L13 12v6.13l6-3.33V8.74ZM12 10.26l6.02-3.01L12 4.24 5.98 7.25 12 10.26Z" /></SvgIcon>
        case 'gateway':
            return <SvgIcon viewBox="0 0 24 24"><path d="M12 3 4 7v5c0 4.97 3.44 9.62 8 10.8 4.56-1.18 8-5.83 8-10.8V7l-8-4Zm0 2.18 6 3v3.64c0 3.86-2.52 7.57-6 8.73-3.48-1.16-6-4.87-6-8.73V8.18l6-3ZM8 11h8v2H8v-2Z" /></SvgIcon>
        case 'repository':
            return <SvgIcon viewBox="0 0 24 24"><path d="M5 4h9a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3H5V4Zm2 2v12h7a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H7Zm11 1h2v10h-2V7Z" /></SvgIcon>
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

function SidebarCollapseIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="m14.41 7.41-1.41-1.41L7.59 11.41a.83.83 0 0 0 0 1.18L13 18l1.41-1.41L9.83 12l4.58-4.59Z" /></SvgIcon>
}

function SidebarExpandIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="m9.59 16.59 1.41 1.41 5.41-5.41a.83.83 0 0 0 0-1.18L11 6l-1.41 1.41L14.17 12l-4.58 4.59Z" /></SvgIcon>
}

function ExpandMoreIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="m7 10 5 5 5-5H7Z" /></SvgIcon>
}

function ChevronSmallRightIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="m10 7 5 5-5 5V7Z" /></SvgIcon>
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

function GlobeIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2Zm0 2c.55 0 1.33.6 2.04 2H9.96C10.67 4.6 11.45 4 12 4Zm-2.5.44A9.08 9.08 0 0 0 7.33 8H4.61A8.03 8.03 0 0 1 9.5 4.44ZM4.06 10h3.22a15.28 15.28 0 0 0-.2 2c0 .68.07 1.35.2 2H4.06A8.07 8.07 0 0 1 4 12c0-.7.02-1.38.06-2Zm.55 6h2.72A9.08 9.08 0 0 0 9.5 19.56 8.03 8.03 0 0 1 4.61 16Zm5.35 3.56C10.67 21.4 11.45 22 12 22c.55 0 1.33-.6 2.04-2H9.96v-.44Zm4.54-3.56a9.08 9.08 0 0 0 2.17-3.56h2.72A8.03 8.03 0 0 1 14.5 19.56ZM19.94 14h-3.22c.13-.65.2-1.32.2-2s-.07-1.35-.2-2h3.22c.04.62.06 1.3.06 2s-.02 1.38-.06 2Zm-.55-6h-2.72A9.08 9.08 0 0 0 14.5 4.44 8.03 8.03 0 0 1 19.39 8ZM9.96 8c.44-1.56 1.16-2.66 1.85-2.94A4.5 4.5 0 0 1 12 5c.06 0 .13 0 .19.06C12.88 5.34 13.6 6.44 14.04 8H9.96Zm-.68 2h5.44c.14.63.21 1.3.21 2s-.07 1.37-.21 2H9.28A12.9 12.9 0 0 1 9.07 12c0-.7.07-1.37.21-2Z" /></SvgIcon>
}

function HamburgerIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M3 6h18v2H3V6Zm0 5h18v2H3v-2Zm0 5h18v2H3v-2Z" /></SvgIcon>
}

function ChevronDownIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="m7 10 5 5 5-5H7Z" /></SvgIcon>
}

function LogoutIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M10 17v-3H3v-4h7V7l5 5-5 5Zm8 2h-6v-2h6V7h-6V5h6a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2Z" /></SvgIcon>
}

export function AppShell() {
    const { t, i18n } = useTranslation('shell')
    const navigate = useNavigate()
    const location = useLocation()
    const { isSubmitting, logout, refresh, status } = useProductAuth()
    const [userMenuAnchor, setUserMenuAnchor] = useState<HTMLElement | null>(null)
    const [localeMenuAnchor, setLocaleMenuAnchor] = useState<HTMLElement | null>(null)
    const [appearanceMenuAnchor, setAppearanceMenuAnchor] = useState<HTMLElement | null>(null)
    const [collapsedApplicationsAnchor, setCollapsedApplicationsAnchor] = useState<HTMLElement | null>(null)
    const collapsedApplicationsCloseTimerRef = useRef<number | null>(null)
    const { colorMode, setColorMode } = useAppColorMode()
    const [navCollapsed, setNavCollapsed] = useState<boolean>(() => {
        if (typeof window === 'undefined') {
            return false
        }

        return window.localStorage.getItem(SHELL_NAV_COLLAPSED_STORAGE_KEY) === 'true'
    })
    const [applicationsExpanded, setApplicationsExpanded] = useState(true)
    const [mobileNavOpen, setMobileNavOpen] = useState(false)

    const resolvedLocale = i18n.resolvedLanguage ?? 'en'
    const activeIntegrationRoute = /^\/(containers|gateway|repository)$/.test(location.pathname)
    const terminalRoute = location.pathname === '/terminal'
    const useWhiteWorkspaceSurface =
        location.pathname === '/applications' ||
        location.pathname.startsWith('/applications/') ||
        location.pathname === '/appstore' ||
        location.pathname === '/myapps' ||
        location.pathname.startsWith('/myapps/') ||
        location.pathname === '/dashboard' ||
        location.pathname === '/terminal' ||
        location.pathname === '/services' ||
        location.pathname === '/logs' ||
        location.pathname === '/users' ||
        location.pathname === '/settings'
    const isChineseLocale = resolvedLocale === 'zh-CN'
    const currentUserLabel = status?.current_user?.username || status?.current_user?.display_name || t('user.menu.profile')
    const normalizedLocale = normalizeSupportedLocale(resolvedLocale)
    const currentLocaleLabel = t(`locales.${normalizedLocale}`)
    const currentAppearanceLabel = colorMode === 'light' ? t('preferences.light') : t('preferences.dark')
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
        const pathWithSearch = `${location.pathname}${location.search}`

        if (/^\/myapps\/[^/]+/.test(location.pathname)) {
            rememberMyAppsDetailRoute(pathWithSearch)
            return
        }

        if (location.pathname === '/myapps') {
            rememberMyAppsDetailRoute(null)
        }
    }, [location.pathname, location.search])

    useEffect(() => {
        if (typeof window === 'undefined') {
            return
        }

        const pathWithSearch = `${location.pathname}${location.search}`

        if (location.pathname === '/applications/deploy' || location.pathname === '/applications/custom-install') {
            window.sessionStorage.setItem(LAST_APPLICATIONS_ROUTE_KEY, pathWithSearch)
        }
    }, [location.pathname, location.search])

    const rememberedMyAppDetailRoute = useMemo(() => {
        return getRememberedMyAppsDetailRoute()
    }, [location.pathname, location.search])
    const myAppsNavigationTarget = rememberedMyAppDetailRoute && !location.pathname.startsWith('/myapps')
        ? rememberedMyAppDetailRoute
        : '/myapps'
    const rememberedApplicationsRoute = useMemo(() => {
        if (typeof window === 'undefined') {
            return null
        }

        return window.sessionStorage.getItem(LAST_APPLICATIONS_ROUTE_KEY)
    }, [location.pathname, location.search])
    const applicationsNavigationTarget = rememberedApplicationsRoute && !location.pathname.startsWith('/applications')
        ? rememberedApplicationsRoute
        : '/applications/deploy'
    const isApplicationsContext = /^\/(applications|appstore|myapps)(\/|$)/.test(location.pathname)
    const applicationSubNavigation = useMemo<ApplicationSubNavigationItem[]>(
        () => [
            {
                key: 'myapps',
                label: t('nav.myApps.label'),
                to: '/myapps',
                active: location.pathname === '/myapps' || location.pathname.startsWith('/myapps/'),
                icon: 'myapps',
            },
            {
                key: 'appstore',
                label: t('nav.appStore.label'),
                to: '/appstore',
                active: location.pathname === '/appstore',
                icon: 'appstore',
            },
            {
                key: 'deploy',
                label: t('applicationsHubPage.menu.action'),
                to: applicationsNavigationTarget,
                active: location.pathname === '/applications/deploy' || location.pathname === '/applications/custom-install',
                icon: 'custom-install',
            },
        ],
        [applicationsNavigationTarget, location.pathname, t],
    )

    useEffect(() => {
        if (isApplicationsContext) {
            setApplicationsExpanded(true)
        }
    }, [isApplicationsContext])

    useEffect(() => {
        if (!navCollapsed && collapsedApplicationsAnchor) {
            setCollapsedApplicationsAnchor(null)
        }
    }, [collapsedApplicationsAnchor, navCollapsed])

    useEffect(() => {
        setCollapsedApplicationsAnchor(null)
        setLocaleMenuAnchor(null)
        setAppearanceMenuAnchor(null)
        setMobileNavOpen(false)
    }, [location.pathname])

    useEffect(() => {
        return () => {
            if (collapsedApplicationsCloseTimerRef.current) {
                window.clearTimeout(collapsedApplicationsCloseTimerRef.current)
            }
        }
    }, [])

    function openCollapsedApplicationsMenu(anchor: HTMLElement) {
        if (collapsedApplicationsCloseTimerRef.current) {
            window.clearTimeout(collapsedApplicationsCloseTimerRef.current)
            collapsedApplicationsCloseTimerRef.current = null
        }

        setCollapsedApplicationsAnchor(anchor)
    }

    function closeCollapsedApplicationsMenuWithDelay() {
        if (collapsedApplicationsCloseTimerRef.current) {
            window.clearTimeout(collapsedApplicationsCloseTimerRef.current)
        }

        collapsedApplicationsCloseTimerRef.current = window.setTimeout(() => {
            setCollapsedApplicationsAnchor(null)
            collapsedApplicationsCloseTimerRef.current = null
        }, 220)
    }

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

    function handleSelectColorMode(nextMode: 'light' | 'dark') {
        setAppearanceMenuAnchor(null)
        setColorMode(nextMode)
    }

    function handleSelectLocale(nextLocale: 'en' | 'zh-CN') {
        const nextNormalizedLocale = normalizeSupportedLocale(nextLocale)
        setLocaleMenuAnchor(null)
        void i18n.changeLanguage(nextNormalizedLocale)
        void persistCurrentUserLocale(nextNormalizedLocale)
    }

    return (
        <Box className={`app-shell-root app-shell-root--${colorMode} ${navCollapsed ? 'app-shell-root--collapsed' : ''} ${mobileNavOpen ? 'app-shell-root--mobile-nav-open' : ''}`}>
            <Box className="app-shell-frame">
                <Box className="app-shell-mobile-backdrop" onClick={() => setMobileNavOpen(false)} />
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

                                            if (item.segment === 'applications') {
                                                return (
                                                    <Box key={item.segment} className="app-shell-nav-group">
                                                        <ListItemButton
                                                            className={`app-shell-nav-item app-shell-nav-item--parent ${(isApplicationsContext || Boolean(collapsedApplicationsAnchor)) ? 'active' : ''}`}
                                                            component={NavLink}
                                                            to={myAppsNavigationTarget}
                                                            onMouseEnter={(event) => {
                                                                if (navCollapsed) {
                                                                    openCollapsedApplicationsMenu(event.currentTarget)
                                                                }
                                                            }}
                                                            onMouseLeave={() => {
                                                                if (navCollapsed) {
                                                                    closeCollapsedApplicationsMenuWithDelay()
                                                                }
                                                            }}
                                                            onClick={() => {
                                                                if (!navCollapsed) {
                                                                    setApplicationsExpanded(true)
                                                                }
                                                            }}
                                                        >
                                                            <Box className="app-shell-nav-item-leading" aria-hidden="true">
                                                                <Box className="app-shell-nav-item-icon">
                                                                    <ShellNavIcon segment={item.segment} />
                                                                </Box>
                                                                {navCollapsed ? (
                                                                    <Box className="app-shell-nav-item-collapsed-indicator">
                                                                        <ChevronSmallRightIcon />
                                                                    </Box>
                                                                ) : null}
                                                            </Box>
                                                            <Typography className="app-shell-nav-item-label" variant="body2">
                                                                {t(`nav.${item.pageKey}.label`)}
                                                            </Typography>
                                                            {!navCollapsed ? (
                                                                <Box
                                                                    className="app-shell-nav-item-trailing"
                                                                    aria-hidden="true"
                                                                    onClick={(event) => {
                                                                        event.preventDefault()
                                                                        event.stopPropagation()
                                                                        setApplicationsExpanded((currentValue) => !currentValue)
                                                                    }}
                                                                >
                                                                    {applicationsExpanded ? <ExpandMoreIcon /> : <ChevronSmallRightIcon />}
                                                                </Box>
                                                            ) : null}
                                                        </ListItemButton>

                                                        {!navCollapsed && applicationsExpanded ? (
                                                            <Box className="app-shell-subnav">
                                                                {applicationSubNavigation.map((subItem) => (
                                                                    <ListItemButton
                                                                        component={NavLink}
                                                                        key={subItem.key}
                                                                        className={`app-shell-nav-item app-shell-nav-item--secondary ${subItem.active ? 'active' : ''}`}
                                                                        to={subItem.key === 'myapps' ? myAppsNavigationTarget : subItem.to}
                                                                    >
                                                                        <Box className="app-shell-nav-item-icon" aria-hidden="true">
                                                                            <ShellNavIcon segment={subItem.icon} />
                                                                        </Box>
                                                                        <Typography className="app-shell-nav-item-label app-shell-nav-item-label--secondary" variant="body2">
                                                                            {subItem.label}
                                                                        </Typography>
                                                                    </ListItemButton>
                                                                ))}
                                                            </Box>
                                                        ) : null}

                                                        {navCollapsed ? (
                                                            <Popper
                                                                anchorEl={collapsedApplicationsAnchor}
                                                                open={Boolean(collapsedApplicationsAnchor)}
                                                                placement="right"
                                                                sx={{ zIndex: 1400 }}
                                                                modifiers={[
                                                                    {
                                                                        name: 'offset',
                                                                        options: {
                                                                            offset: [0, 0],
                                                                        },
                                                                    },
                                                                ]}
                                                            >
                                                                <Paper
                                                                    elevation={0}
                                                                    className={`app-shell-collapsed-submenu app-shell-collapsed-submenu--${colorMode}`}
                                                                    onMouseEnter={() => {
                                                                        if (collapsedApplicationsCloseTimerRef.current) {
                                                                            window.clearTimeout(collapsedApplicationsCloseTimerRef.current)
                                                                            collapsedApplicationsCloseTimerRef.current = null
                                                                        }
                                                                    }}
                                                                    onMouseLeave={() => {
                                                                        closeCollapsedApplicationsMenuWithDelay()
                                                                    }}
                                                                >
                                                                    <Box className="app-shell-collapsed-submenu-list">
                                                                        {applicationSubNavigation.map((subItem) => (
                                                                            <ListItemButton
                                                                                component={NavLink}
                                                                                key={subItem.key}
                                                                                className={`app-shell-collapsed-submenu-item ${subItem.active ? 'active' : ''}`}
                                                                                to={subItem.key === 'myapps' ? myAppsNavigationTarget : subItem.to}
                                                                                onClick={() => {
                                                                                    setCollapsedApplicationsAnchor(null)
                                                                                }}
                                                                            >
                                                                                <Box className="app-shell-collapsed-submenu-icon" aria-hidden="true">
                                                                                    <ShellNavIcon segment={subItem.icon} />
                                                                                </Box>
                                                                                <Typography className="app-shell-collapsed-submenu-label">
                                                                                    {subItem.label}
                                                                                </Typography>
                                                                            </ListItemButton>
                                                                        ))}
                                                                    </Box>
                                                                </Paper>
                                                            </Popper>
                                                        ) : null}
                                                    </Box>
                                                )
                                            }

                                            return (
                                                <ListItemButton
                                                    component={NavLink}
                                                    key={item.segment}
                                                    className="app-shell-nav-item"
                                                    to={item.segment === 'myapps' ? myAppsNavigationTarget : `/${item.segment}`}
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
                    className="app-shell-divider-toggle"
                    onClick={() => {
                        setNavCollapsed((currentValue) => !currentValue)
                    }}
                    aria-label={navCollapsed ? t('navigation.expand', { defaultValue: 'Expand menu' }) : t('navigation.collapse', { defaultValue: 'Collapse menu' })}
                    title={navCollapsed ? t('navigation.expand', { defaultValue: 'Expand menu' }) : t('navigation.collapse', { defaultValue: 'Collapse menu' })}
                >
                    {navCollapsed ? <SidebarExpandIcon /> : <SidebarCollapseIcon />}
                </IconButton>

                <Box className="app-shell-content">
                    <Box className="app-shell-topbar">
                        <IconButton
                            className="app-shell-hamburger app-shell-icon-button"
                            onClick={() => setMobileNavOpen(true)}
                            aria-label={t('navigation.expand', { defaultValue: 'Open navigation' })}
                        >
                            <HamburgerIcon />
                        </IconButton>
                        <Box className="app-shell-topbar-actions">
                            <Button
                                color="inherit"
                                onClick={(event) => {
                                    setLocaleMenuAnchor(event.currentTarget)
                                }}
                                size="small"
                                className="app-shell-topbar-pill"
                                title={t('preferences.language')}
                                startIcon={<GlobeIcon />}
                                endIcon={<ChevronDownIcon />}
                            >
                                {currentLocaleLabel}
                            </Button>
                            <Button
                                color="inherit"
                                onClick={(event) => {
                                    setAppearanceMenuAnchor(event.currentTarget)
                                }}
                                className="app-shell-topbar-pill app-shell-topbar-pill--appearance"
                                aria-label={t('preferences.appearance')}
                                title={t('preferences.appearance')}
                                startIcon={colorMode === 'light' ? <SunIcon /> : <MoonIcon />}
                                endIcon={<ChevronDownIcon />}
                            >
                                {currentAppearanceLabel}
                            </Button>
                            <Button
                                color="inherit"
                                onClick={(event) => {
                                    if (userMenuAnchor) {
                                        setUserMenuAnchor(null)
                                        return
                                    }

                                    setUserMenuAnchor(event.currentTarget)
                                }}
                                className="app-shell-user-trigger app-shell-user-trigger--topbar"
                                aria-label={t('user.menu.profile')}
                                title={currentUserLabel}
                                startIcon={
                                    <Avatar className="app-shell-user-avatar app-shell-user-avatar--topbar">
                                        <PersonIcon />
                                    </Avatar>
                                }
                            >
                                <Box className="app-shell-user-trigger-copy">
                                    <Typography className="app-shell-user-trigger-name">{currentUserLabel}</Typography>
                                </Box>
                            </Button>
                        </Box>
                    </Box>
                    <Box
                        component="main"
                        className={`app-shell-main ${location.pathname === '/dashboard' ? 'app-shell-main--dashboard' : ''} ${useWhiteWorkspaceSurface ? 'app-shell-main--white-surface' : ''}`}
                        id="app-shell-main"
                        sx={{
                            px: activeIntegrationRoute ? 0 : { xs: 2, md: 3 },
                            py: activeIntegrationRoute ? 0 : terminalRoute ? { xs: 1, md: 1.25 } : location.pathname === '/dashboard' ? { xs: 2, md: 2.25 } : { xs: 2.5, md: 3 },
                            overflowX: terminalRoute ? 'hidden' : undefined,
                            overflowY: activeIntegrationRoute ? 'hidden' : location.pathname === '/dashboard' || terminalRoute ? 'hidden' : 'auto',
                        }}
                    >
                        <Box className="app-shell-main-body">
                            <PersistentIntegrationWorkspaces />
                            <Outlet />
                        </Box>
                    </Box>

                    <Box component="footer" className={`app-shell-footer ${useWhiteWorkspaceSurface ? 'app-shell-footer--white-surface' : ''}`}>
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
                anchorEl={localeMenuAnchor}
                open={Boolean(localeMenuAnchor)}
                onClose={() => {
                    setLocaleMenuAnchor(null)
                }}
                sx={{ zIndex: 1700 }}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                slotProps={{
                    paper: {
                        className: `app-shell-account-menu app-shell-account-menu--${colorMode}`,
                    },
                }}
            >
                <Box className="app-shell-account-panel">
                    <Typography className="app-shell-account-section-label">{t('preferences.language')}</Typography>
                    <List disablePadding className="app-shell-account-links">
                        {(['zh-CN', 'en'] as const).map((locale) => {
                            const active = normalizedLocale === locale

                            return (
                                <ListItemButton
                                    key={locale}
                                    className={`app-shell-account-link ${active ? 'app-shell-account-link--selected' : ''}`}
                                    onClick={() => {
                                        handleSelectLocale(locale)
                                    }}
                                >
                                    <Box className="app-shell-account-link-icon">
                                        <GlobeIcon />
                                    </Box>
                                    <Typography className="app-shell-account-link-title">{t(`locales.${locale}`)}</Typography>
                                </ListItemButton>
                            )
                        })}
                    </List>
                </Box>
            </Menu>

            <Menu
                anchorEl={appearanceMenuAnchor}
                open={Boolean(appearanceMenuAnchor)}
                onClose={() => {
                    setAppearanceMenuAnchor(null)
                }}
                sx={{ zIndex: 1700 }}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                slotProps={{
                    paper: {
                        className: `app-shell-account-menu app-shell-account-menu--${colorMode}`,
                    },
                }}
            >
                <Box className="app-shell-account-panel">
                    <Typography className="app-shell-account-section-label">{t('preferences.appearance')}</Typography>
                    <List disablePadding className="app-shell-account-links">
                        {(['light', 'dark'] as const).map((mode) => {
                            const active = colorMode === mode

                            return (
                                <ListItemButton
                                    key={mode}
                                    className={`app-shell-account-link ${active ? 'app-shell-account-link--selected' : ''}`}
                                    onClick={() => {
                                        handleSelectColorMode(mode)
                                    }}
                                >
                                    <Box className="app-shell-account-link-icon">
                                        {mode === 'light' ? <SunIcon /> : <MoonIcon />}
                                    </Box>
                                    <Typography className="app-shell-account-link-title">{t(`preferences.${mode}`)}</Typography>
                                </ListItemButton>
                            )
                        })}
                    </List>
                </Box>
            </Menu>

            <Menu
                anchorEl={userMenuAnchor}
                open={Boolean(userMenuAnchor)}
                onClose={() => {
                    setUserMenuAnchor(null)
                }}
                sx={{ zIndex: 1700 }}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                slotProps={{
                    paper: {
                        className: `app-shell-account-menu app-shell-account-menu--${colorMode}`,
                    },
                }}
            >
                <Box className="app-shell-account-panel">
                    <Typography className="app-shell-account-section-label">{t('nav.users.label')}</Typography>
                    <List disablePadding className="app-shell-account-links">
                        <ListItemButton
                            className={`app-shell-account-link ${location.pathname.startsWith('/users') ? 'active' : ''}`}
                            onClick={() => {
                                setUserMenuAnchor(null)
                                navigate('/users', {
                                    state: {
                                        openCurrentUserEditor: true,
                                        profileDialogNonce: Date.now(),
                                    },
                                })
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

                    </List>
                </Box>
            </Menu>
        </Box>
    )
}