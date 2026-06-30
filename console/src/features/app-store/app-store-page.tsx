import {
    Avatar,
    Badge,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    Link,
    MenuItem,
    Stack,
    SvgIcon,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material'
import { yaml as yamlLanguage } from '@codemirror/lang-yaml'
import { useQuery } from '@tanstack/react-query'
import CodeMirror from '@uiw/react-codemirror'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { getSurfaceFieldSx } from '../../shared/design-system/form-field-sx'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { SurfaceFeedbackToast, SurfaceNoticeAlert, SurfaceStateCard } from '../../shared/design-system/standard-surfaces'
import { getSurfacePalette } from '../../shared/design-system/surface-theme'
import { UnifiedAppCard } from '../../shared/design-system/unified-app-card'
import { useAppColorMode } from '../../app/providers/color-mode'
import {
    getAppStoreInstallDistributions,
    getPreferredAppStoreInstallDistribution,
    getPreferredAppStoreScreenshot,
    getAppStoreVersionSummary,
    matchesAppStoreSearch,
    type AppStoreCatalogItem,
    type AppStoreApp,
} from './app-store-model'
import { useAppStoreApps } from './use-app-store-apps'
import { useAppStoreCatalogs } from './use-app-store-catalogs'

function formatRequirement(value: number | undefined) {
    return typeof value === 'number' ? value.toString() : '-'
}

function getAppInitial(value: string | undefined) {
    return (value ?? '?').trim().slice(0, 1).toUpperCase()
}

function getDefaultImagePath(locale: string) {
    return locale.toLowerCase().startsWith('zh') ? '/default.png' : '/default-en.png'
}

function getDefaultScreenshotPath(locale: string) {
    return locale.toLowerCase().startsWith('zh') ? '/default-screenshot-friendly.svg' : '/default-screenshot-friendly-en.svg'
}

function getAppLogoSources(app: AppStoreApp, locale: string) {
    const sources = [app.logo?.imageurl, getDefaultImagePath(locale)]
    return sources.filter((value): value is string => Boolean(value))
}

function getAppScreenshotSources(app: AppStoreApp, locale: string) {
    const screenshot = getPreferredAppStoreScreenshot(app)
    const sources = [screenshot, getDefaultScreenshotPath(locale)]
    return sources.filter((value): value is string => Boolean(value))
}

function normalizeInstallName(value: string) {
    return value.toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 20)
}

function isInstallNameValid(value: string) {
    return /^[a-z][a-z0-9]{1,19}$/.test(value)
}

function normalizeCustomDomain(value: string) {
    return value.trim().toLowerCase()
}

function normalizeMountPath(value: string) {
    return value.trim().replace(/\\+/g, '/').replace(/^\.\//, '')
}

function isValidMountPath(value: string) {
    if (!value || value.startsWith('/') || value === '.' || value === '..') {
        return false
    }

    const parts = value.split('/')
    return parts.every((part) => Boolean(part) && part !== '.' && part !== '..')
}

function isValidCustomDomain(value: string) {
    if (!value || value.length > 253 || /\s/.test(value) || value.includes('://') || value.includes('/') || value.includes(':')) {
        return false
    }

    const labels = value.split('.')
    if (labels.length < 2) {
        return false
    }

    return labels.every((label) => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i.test(label)) && !/^\d+$/.test(labels[labels.length - 1] ?? '')
}

function getInstallPortsValidationMessage(
    settings: Record<string, string>,
    t: (key: string, options?: Record<string, unknown>) => string,
    locale: string,
) {
    const usedPorts = new Set<string>()

    for (const [key, rawValue] of Object.entries(settings)) {
        if (!key.toLowerCase().includes('port')) {
            continue
        }

        const value = rawValue.trim()
        const label = getInstallSettingLabel(key, t, locale)
        if (!/^\d+$/.test(value)) {
            return { key, message: t('appStorePage.install.validation.port', { name: label }) }
        }

        const port = Number(value)
        if (!Number.isInteger(port) || port < 1 || port > 65535) {
            return { key, message: t('appStorePage.install.validation.port', { name: label }) }
        }

        if (usedPorts.has(value)) {
            return { key, message: t('appStorePage.install.validation.portDuplicate', { port: value }) }
        }

        usedPorts.add(value)
    }

    return null
}

type InstallFeedback = {
    severity: 'success' | 'error'
    message: string
}

type InstallFieldErrors = {
    appId?: string
    customDomain?: string
    settings?: Record<string, string | undefined>
}

type InstallError = Error & {
    statusCode?: number
}

type InstallTaskAcceptedResponse = {
    app_id: string
    tracking_id: string
    message: string
    details: string
}

type ProductAuthFavoritesResponse = {
    favorites: string[]
}

type AppStoreSyncStatusResponse = {
    status: 'running' | 'idle'
    lastSyncedAt?: string
    datasetVersion?: string
}

type AppStoreStateResponse = {
    channel?: string
    datasetVersion?: string
    catalogDatasetVersion?: string
    libraryDatasetVersion?: string
    generatedAt?: string
    lastSyncedAt?: string
    syncMode?: string
    updated?: boolean
    snapshotRoot?: string
}

type ComposeEnvironmentRow = {
    id: string
    key: string
    value: string
}

type ComposeMountRow = {
    id: string
    path: string
    content: string
}

const DEFAULT_COMPOSE_TEMPLATE = `services:
  nginx:
    image: nginx:latest
    ports:
      - "8080:80"
    environment:
      - WELCOME_MSG=Hello Websoft9
    volumes:
      - ./html:/usr/share/nginx/html

networks:
  default:
    name: $W9_NETWORK
    external: true
`

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
    const response = await fetch(input, {
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
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

async function fetchFavorites() {
    return requestJson<ProductAuthFavoritesResponse>('/api/auth/favorites', { method: 'GET' })
}

function formatFullSyncTimestamp(value: string | undefined, locale: string) {
    if (!value) {
        return null
    }

    const timestamp = new Date(value)
    if (Number.isNaN(timestamp.getTime())) {
        return null
    }

    if (locale.toLowerCase().startsWith('zh')) {
        const year = timestamp.getFullYear()
        const month = String(timestamp.getMonth() + 1).padStart(2, '0')
        const day = String(timestamp.getDate()).padStart(2, '0')
        const hour = String(timestamp.getHours()).padStart(2, '0')
        const minute = String(timestamp.getMinutes()).padStart(2, '0')
        const second = String(timestamp.getSeconds()).padStart(2, '0')
        return `${year}年${month}月${day}日 ${hour}:${minute}:${second}`
    }

    return new Intl.DateTimeFormat(locale, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
    }).format(timestamp)
}

async function installComposeApp(payload: {
    app_id: string
    compose_content: string
    env: Array<{ key: string; value: string }>
    mounts: Array<{ path: string; content: string }>
    domain?: string
}) {
    return requestJson<InstallTaskAcceptedResponse>('/api/apps/install/compose', {
        method: 'POST',
        body: JSON.stringify(payload),
    })
}

async function installApp(
    app: AppStoreApp,
    appId: string,
    version: string,
    settings: Record<string, string>,
    domainNames: string[],
    proxyEnabled: boolean,
) {
    const distribution = getPreferredAppStoreInstallDistribution(app)
    const response = await fetch('/api/apps/install', {
        method: 'POST',
        credentials: 'include',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            app_name: app.key,
            edition: {
                dist: distribution.dist,
                version,
            },
            app_id: appId,
            proxy_enabled: proxyEnabled,
            domain_names: domainNames,
            settings,
        }),
    })

    if (!response.ok) {
        let detail = `Failed to install app: ${response.status}`

        try {
            const body = (await response.json()) as { details?: string; message?: string }
            detail = body.details || body.message || detail
        } catch {
            // Ignore response parsing failures and fall back to status text.
        }

        const error = new Error(detail) as InstallError
        error.statusCode = response.status
        throw error
    }

    return response.json().catch(() => null) as Promise<InstallTaskAcceptedResponse | null>
}

function AppLogo({ app, locale }: { app: AppStoreApp; locale: string }) {
    const containerRef = useRef<HTMLDivElement | null>(null)
    const [sourceIndex, setSourceIndex] = useState(0)
    const [shouldLoadImage, setShouldLoadImage] = useState(false)
    const label = app.trademark ?? app.key
    const sources = getAppLogoSources(app, locale)

    useEffect(() => {
        setSourceIndex(0)
        setShouldLoadImage(false)
    }, [app.key, app.logo?.imageurl, locale])

    useEffect(() => {
        const node = containerRef.current
        if (!node) {
            return
        }

        if (typeof IntersectionObserver === 'undefined') {
            setShouldLoadImage(true)
            return
        }

        const observer = new IntersectionObserver(
            (entries) => {
                if (entries.some((entry) => entry.isIntersecting || entry.intersectionRatio > 0)) {
                    setShouldLoadImage(true)
                    observer.disconnect()
                }
            },
            {
                rootMargin: '240px 0px',
            },
        )

        observer.observe(node)

        return () => {
            observer.disconnect()
        }
    }, [app.key, app.logo?.imageurl, locale])

    return (
        <Box
            ref={containerRef}
            sx={{
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
            }}
        >
            {!shouldLoadImage || sources.length === 0 || sourceIndex >= sources.length ? (
                <Avatar
                    variant="rounded"
                    sx={{
                        width: '100%',
                        height: '100%',
                        borderRadius: '4px',
                        background: 'var(--ds-color-surface-soft)',
                        color: 'var(--ds-color-text-strong)',
                        fontSize: 28,
                        fontWeight: 600,
                        border: '1px solid var(--ds-color-border)',
                    }}
                >
                    {getAppInitial(label)}
                </Avatar>
            ) : (
                <Box
                    component="img"
                    alt={label ?? 'App'}
                    src={sources[sourceIndex]}
                    loading="lazy"
                    decoding="async"
                    referrerPolicy="no-referrer"
                    onError={() => {
                        setSourceIndex((currentValue) => currentValue + 1)
                    }}
                    sx={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'contain',
                        borderRadius: '4px',
                        backgroundColor: 'transparent',
                        p: 0,
                    }}
                />
            )}
        </Box>
    )
}

function AppScreenshot({ app, locale, alt }: { app: AppStoreApp; locale: string; alt: string }) {
    const [sourceIndex, setSourceIndex] = useState(0)
    const sources = getAppScreenshotSources(app, locale)

    useEffect(() => {
        setSourceIndex(0)
    }, [app.key, app.screenshots, locale])

    if (sources.length === 0 || sourceIndex >= sources.length) {
        return null
    }

    return (
        <Box
            sx={{
                width: 'calc(100% - 16px)',
                maxWidth: 680,
                height: { xs: 240, md: 360 },
                display: 'flex',
                alignItems: 'stretch',
                justifyContent: 'center',
                mx: 'auto',
                mt: 1,
                mb: 1.75,
                overflow: 'hidden',
                backgroundColor: '#fff',
            }}
        >
            <Box
                component="img"
                alt={alt}
                src={sources[sourceIndex]}
                referrerPolicy="no-referrer"
                onError={() => {
                    setSourceIndex((currentValue) => currentValue + 1)
                }}
                sx={{
                    width: '100%',
                    height: '100%',
                    display: 'block',
                    objectFit: 'cover',
                    objectPosition: 'top center',
                    backgroundColor: '#fff',
                }}
            />
        </Box>
    )
}

function GitHubMarkIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M12 2C6.48 2 2 6.59 2 12.25c0 4.52 2.87 8.35 6.84 9.7.5.1.66-.22.66-.49 0-.24-.01-1.03-.01-1.86-2.78.62-3.37-1.22-3.37-1.22-.46-1.2-1.11-1.52-1.11-1.52-.91-.64.07-.63.07-.63 1 .07 1.53 1.06 1.53 1.06.9 1.57 2.35 1.12 2.92.85.09-.67.35-1.12.63-1.38-2.22-.26-4.56-1.15-4.56-5.13 0-1.13.39-2.05 1.03-2.77-.1-.26-.45-1.32.1-2.75 0 0 .84-.28 2.75 1.06A9.3 9.3 0 0 1 12 6.84c.85 0 1.71.12 2.51.36 1.91-1.34 2.75-1.06 2.75-1.06.55 1.43.2 2.49.1 2.75.64.72 1.03 1.64 1.03 2.77 0 3.99-2.35 4.87-4.58 5.12.36.32.69.95.69 1.92 0 1.39-.01 2.5-.01 2.84 0 .27.17.59.67.49A10.1 10.1 0 0 0 22 12.25C22 6.59 17.52 2 12 2Z" />
        </SvgIcon>
    )
}

function DocumentationIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M6 3.75A2.25 2.25 0 0 0 3.75 6v12A2.25 2.25 0 0 0 6 20.25h12A2.25 2.25 0 0 0 20.25 18V8.56a2.25 2.25 0 0 0-.66-1.59l-2.56-2.56a2.25 2.25 0 0 0-1.59-.66H6Zm8.25 1.7 3.3 3.3h-3.3v-3.3ZM8.25 11.25h7.5v1.5h-7.5v-1.5Zm0 3h7.5v1.5h-7.5v-1.5Zm0-6h3.75v1.5H8.25v-1.5Z" />
        </SvgIcon>
    )
}

function FavoriteSectionHeading({ title }: { title: string }) {
    return (
        <Box sx={{ display: 'flex', alignItems: 'center', minHeight: 28 }}>
            <Typography sx={{ fontSize: 15, fontWeight: 600, color: '#111827', lineHeight: 1.35 }}>{title}</Typography>
        </Box>
    )
}

function RefreshIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M17.65 6.35A7.95 7.95 0 0 0 12 4a8 8 0 1 0 7.75 10h-2.08A6 6 0 1 1 12 6c1.3 0 2.5.42 3.47 1.13L13 10h7V3l-2.35 3.35Z" />
        </SvgIcon>
    )
}

function CloseIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M18.3 5.71 12 12l6.3 6.29-1.42 1.42L10.59 13.4 4.29 19.7l-1.41-1.42L9.17 12 2.88 5.71 4.29 4.29l6.3 6.3 6.29-6.3 1.42 1.42Z" />
        </SvgIcon>
    )
}

function RemoveIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24" fontSize="small">
            <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
        </SvgIcon>
    )
}

function FavoriteIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="m12 21.35-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09A5.96 5.96 0 0 1 16.5 3C19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35Z" />
        </SvgIcon>
    )
}

function SyncIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" />
        </SvgIcon>
    )
}

function getDocumentationUrl(app: AppStoreApp, resolvedLanguage: string) {
    const localePrefix = resolvedLanguage.toLowerCase().startsWith('zh') ? '' : 'en/'
    return `https://support.websoft9.com/${localePrefix}docs/${app.key ?? ''}`
}

function getGitHubUrl(app: AppStoreApp) {
    return `https://github.com/Websoft9/docker-library/tree/main/apps/${app.key ?? ''}`
}

const knownInstallSettingLabelKeys: Record<string, string> = {
    W9_HTTP_PORT_SET: 'appStorePage.install.httpPortLabel',
    W9_HTTPS_PORT_SET: 'appStorePage.install.httpsPortLabel',
    W9_DB_PORT_SET: 'appStorePage.install.databasePortLabel',
}

const installSettingTokenLabels = {
    en: {
        ADMIN: 'Admin',
        AMQP: 'AMQP',
        API: 'API',
        APP: 'Application',
        BEATS: 'Beats',
        BRIDGE: 'Bridge',
        BROKER: 'Broker',
        BW: 'Bitwarden',
        CLIENT: 'Client',
        CONFIG: 'Config',
        CONTAINER: 'Container',
        DASHBOARD: 'Dashboard',
        DATA: 'Data',
        DB: 'Database',
        DNS: 'DNS',
        ER: 'ER',
        FLV: 'FLV',
        FORWARDER: 'Forwarder',
        GELF: 'GELF',
        GRPC: 'gRPC',
        GUI: 'GUI',
        HTTP: 'HTTP',
        HTTPS: 'HTTPS',
        INNERIP: 'Internal IP',
        INSTALLATION: 'Installation',
        KAFKA: 'Kafka',
        KEY: 'Key',
        MQ: 'Message Queue',
        MQTT: 'MQTT',
        NETWORKID: 'Network ID',
        OPENAI: 'OpenAI',
        OPENWIRE: 'OpenWire',
        PATH: 'Path',
        PORT: 'Port',
        POSTGRESQL: 'PostgreSQL',
        RAW: 'Raw',
        REMOTE: 'Remote',
        RPC: 'RPC',
        SCAN: 'Scan',
        SERVER: 'Server',
        SMTP: 'SMTP',
        SSH: 'SSH',
        STOMP: 'STOMP',
        SYSLOG: 'Syslog',
        TCP: 'TCP',
        TURN: 'TURN',
        UDP: 'UDP',
        URI: 'URI',
        VNC: 'VNC',
        WS: 'WebSocket',
    },
    zh: {
        ADMIN: '管理',
        AMQP: 'AMQP',
        API: 'API',
        APP: '应用',
        BEATS: 'Beats',
        BRIDGE: '桥接',
        BROKER: '代理',
        BW: 'Bitwarden',
        CLIENT: '客户端',
        CONFIG: '配置',
        CONTAINER: '容器',
        DASHBOARD: '控制台',
        DATA: '数据',
        DB: '数据库',
        DNS: 'DNS',
        ER: 'ER',
        FLV: 'FLV',
        FORWARDER: '转发器',
        GELF: 'GELF',
        GRPC: 'gRPC',
        GUI: 'GUI',
        HTTP: 'HTTP',
        HTTPS: 'HTTPS',
        INNERIP: '内网 IP',
        INSTALLATION: '安装',
        KAFKA: 'Kafka',
        KEY: '密钥',
        MQ: '消息队列',
        MQTT: 'MQTT',
        NETWORKID: '网络 ID',
        OPENAI: 'OpenAI',
        OPENWIRE: 'OpenWire',
        PATH: '路径',
        PORT: '端口',
        POSTGRESQL: 'PostgreSQL',
        RAW: '原始',
        REMOTE: '远程',
        RPC: 'RPC',
        SCAN: '扫描',
        SERVER: '服务',
        SMTP: 'SMTP',
        SSH: 'SSH',
        STOMP: 'STOMP',
        SYSLOG: 'Syslog',
        TCP: 'TCP',
        TURN: 'TURN',
        UDP: 'UDP',
        URI: 'URI',
        VNC: 'VNC',
        WS: 'WebSocket',
    },
} as const

function humanizeInstallSettingToken(token: string) {
    return token
        .toLowerCase()
        .replace(/(^|\s)(\w)/g, (value) => value.toUpperCase())
}

function formatInstallSettingName(value: string, locale: string) {
    const localeKey = locale.toLowerCase().startsWith('zh') ? 'zh' : 'en'
    const tokenLabels = installSettingTokenLabels[localeKey]

    return value
        .split('_')
        .filter(Boolean)
        .map((token) => tokenLabels[token.toUpperCase() as keyof typeof tokenLabels] ?? humanizeInstallSettingToken(token))
        .join(localeKey === 'zh' ? ' ' : ' ')
}

function getInstallSettingLabel(key: string, t: (key: string, options?: Record<string, unknown>) => string, locale: string) {
    const knownLabelKey = knownInstallSettingLabelKeys[key]
    if (knownLabelKey) {
        return t(knownLabelKey)
    }

    const normalizedKey = key.replace(/^W9_/, '').replace(/_SET$/, '')
    if (!normalizedKey) {
        return key
    }

    if (normalizedKey.endsWith('_PORT')) {
        const portName = normalizedKey.slice(0, -'_PORT'.length)
        return t('appStorePage.install.dynamicPortLabel', {
            name: formatInstallSettingName(portName, locale),
        })
    }

    return t('appStorePage.install.dynamicSettingLabel', {
        name: formatInstallSettingName(normalizedKey, locale),
    })
}


type DomainSettingsResponse = {
    wildcard_domain?: string | null
}

type CatalogOption = {
    key: string
    title: string
    count: number
}

type DetailDialogSource = 'catalog' | 'favorites'
type InstallSourceKey = 'marketplace' | 'compose'

type AppStorePageProps = {
    lockedInstallSource?: InstallSourceKey
    hideInstallSourceSelector?: boolean
}

type ContentViewportRect = {
    top: number
    left: number
    width: number
    height: number
}

type AppStoreScopedOverlayProps = {
    open: boolean
    scopeRect: ContentViewportRect | null
    onClose: () => void
    maxWidth?: number
    preferredHeight?: number
    verticalPlacement?: 'center' | 'top'
    children: ReactNode
}

function AppStoreScopedOverlay({ open, scopeRect, onClose, maxWidth = 800, preferredHeight, verticalPlacement = 'center', children, darkMode = false }: AppStoreScopedOverlayProps & { darkMode?: boolean }) {
    const palette = getSurfacePalette(darkMode)

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

    const verticalPadding = verticalPlacement === 'top' ? 20 : 32
    const availableHeight = Math.max(Math.round(scopeRect.height) - verticalPadding, 240)
    const resolvedHeight = preferredHeight ? Math.min(availableHeight, preferredHeight) : null

    return createPortal(
        <Box
            sx={{
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
                    backgroundColor: palette.overlay,
                }}
            />
            <Box
                sx={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: verticalPlacement === 'top' ? 'flex-start' : 'center',
                    justifyContent: 'center',
                    px: { xs: 1.5, md: 1.5 },
                    py: verticalPlacement === 'top' ? { xs: 1.5, md: 2 } : { xs: 1.5, md: 2.5 },
                    pointerEvents: 'none',
                }}
            >
                <Box
                    role="dialog"
                    aria-modal="true"
                    onClick={(event) => {
                        event.stopPropagation()
                    }}
                    sx={{
                        pointerEvents: 'auto',
                        width: { xs: 'min(100%, 800px)', md: `min(${maxWidth}px, calc(100% - 16px))` },
                        maxWidth: `${maxWidth}px`,
                        height: resolvedHeight ? `${resolvedHeight}px` : 'auto',
                        maxHeight: `${availableHeight}px`,
                        display: 'flex',
                        flexDirection: 'column',
                        backgroundColor: palette.dialogBg,
                        color: palette.text,
                        borderRadius: '2px',
                        boxShadow: darkMode ? '0 24px 64px rgba(2, 6, 23, 0.62)' : '0 16px 40px rgba(15, 23, 42, 0.16)',
                        border: `1px solid ${palette.borderStrong}`,
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

function formatCatalogOptionLabel(category: CatalogOption, options?: { hideCount?: boolean }) {
    if (options?.hideCount) {
        return category.title
    }

    return `${category.title}(${category.count})`
}

function getSubCatalogs(catalogs: AppStoreCatalogItem[], selectedMainCatalogKey: string) {
    if (selectedMainCatalogKey === 'all') {
        return []
    }

    const selectedMain = catalogs.find((catalog) => catalog.key === selectedMainCatalogKey)
    const subCatalogs = selectedMain?.linkedFrom?.catalogCollection?.items ?? []

    return [...subCatalogs].sort((left, right) => {
        if (left.position == null && right.position == null) {
            return 0
        }

        if (left.position == null) {
            return 1
        }

        if (right.position == null) {
            return -1
        }

        return left.position - right.position
    })
}

function matchesLegacyMainCatalog(app: AppStoreApp, selectedMainCatalogKey: string) {
    if (selectedMainCatalogKey === 'all') {
        return true
    }

    return (app.catalogCollection?.items ?? []).some((mainCategory) =>
        (mainCategory.catalogCollection?.items ?? []).some((subCategory) => subCategory.key === selectedMainCatalogKey),
    )
}

function matchesLegacySubCatalog(app: AppStoreApp, selectedSubCatalogKey: string) {
    if (selectedSubCatalogKey === 'all') {
        return true
    }

    return (app.catalogCollection?.items ?? []).some((mainCategory) => mainCategory.key === selectedSubCatalogKey)
}

export function AppStorePage({ lockedInstallSource, hideInstallSourceSelector = false }: AppStorePageProps) {
    const { t, i18n } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const location = useLocation()
    const navigate = useNavigate()
    const [searchParams, setSearchParams] = useSearchParams()
    const [searchValue, setSearchValue] = useState(() => searchParams.get('keyword') ?? '')
    const [selectedMainCatalogKey, setSelectedMainCatalogKey] = useState('all')
    const [selectedSubCatalogKey, setSelectedSubCatalogKey] = useState('all')
    const [selectedApp, setSelectedApp] = useState<AppStoreApp | null>(null)
    const [isInstallMode, setIsInstallMode] = useState(false)
    const [installName, setInstallName] = useState('')
    const [selectedVersion, setSelectedVersion] = useState('latest')
    const [installSettings, setInstallSettings] = useState<Record<string, string>>({})
    const [installError, setInstallError] = useState<string | null>(null)
    const [installFieldErrors, setInstallFieldErrors] = useState<InstallFieldErrors>({})
    const [installFeedback, setInstallFeedback] = useState<InstallFeedback | null>(null)
    const [isSubmittingInstall, setIsSubmittingInstall] = useState(false)
    const [isRefreshingStore, setIsRefreshingStore] = useState(false)
    const [isLocalRefreshing, setIsLocalRefreshing] = useState(false)
    const [refreshConfirmOpen, setRefreshConfirmOpen] = useState(false)
    const [refreshFeedback, setRefreshFeedback] = useState<{ severity: 'success' | 'error'; message: string } | null>(null)
    const [wildcardDomain, setWildcardDomain] = useState('')
    const [isDomainEnabled, setIsDomainEnabled] = useState(true)
    const MAX_CUSTOM_DOMAINS = 5
    const [customDomains, setCustomDomains] = useState<string[]>([])
    const [customDomainErrorIndex, setCustomDomainErrorIndex] = useState<number | null>(null)
    const [composeAppId, setComposeAppId] = useState('customapp')
    const [composeDomain, setComposeDomain] = useState('')
    const [composeContent, setComposeContent] = useState(DEFAULT_COMPOSE_TEMPLATE)
    const [composeEnvRows, setComposeEnvRows] = useState<ComposeEnvironmentRow[]>([{ id: 'env-1', key: '', value: '' }])
    const [composeMountRows, setComposeMountRows] = useState<ComposeMountRow[]>([{ id: 'mount-1', path: '', content: '' }])
    const [selectedComposeMountId, setSelectedComposeMountId] = useState('mount-1')
    const [composeEnvExpanded, setComposeEnvExpanded] = useState(false)
    const [composeMountExpanded, setComposeMountExpanded] = useState(false)
    const [composeFieldErrors, setComposeFieldErrors] = useState<{ appId?: string; composeContent?: string; domain?: string; env?: string; mountPath?: string }>({})
    const [isSubmittingCompose, setIsSubmittingCompose] = useState(false)
    const [isFavoritesOpen, setIsFavoritesOpen] = useState(false)
    const [detailDialogSource, setDetailDialogSource] = useState<DetailDialogSource>('catalog')
    const [contentViewportRect, setContentViewportRect] = useState<ContentViewportRect | null>(null)
    const previousSyncStatusRef = useRef<AppStoreSyncStatusResponse['status'] | null>(null)
    const appIdInputRef = useRef<HTMLInputElement | null>(null)
    const customDomainInputRefs = useRef<Record<number, HTMLInputElement | null>>({})
    const composeFileInputRef = useRef<HTMLInputElement | null>(null)
    const composeEnvFileInputRef = useRef<HTMLInputElement | null>(null)
    const composeMountFileInputRef = useRef<HTMLInputElement | null>(null)
    const installSettingInputRefs = useRef<Record<string, HTMLInputElement | null>>({})
    const lastInstallSeverityRef = useRef<'error' | 'success'>('error')
    const lastRefreshSeverityRef = useRef<'success' | 'error'>('success')
    const lastInstallMessageRef = useRef('')
    const lastRefreshMessageRef = useRef('')
    const deferredSearchValue = useDeferredValue(searchValue)
    const { data, error, isLoading, refetch } = useAppStoreApps()
    const { data: catalogsData, refetch: refetchCatalogs } = useAppStoreCatalogs()
    const { data: favoritesData, refetch: refetchFavorites } = useQuery<ProductAuthFavoritesResponse, Error>({
        queryKey: ['product-auth-favorites'],
        queryFn: fetchFavorites,
        staleTime: 10_000,
    })
    const { data: appStoreState, refetch: refetchAppStoreState } = useQuery<AppStoreStateResponse, Error>({
        queryKey: ['appstore-state'],
        queryFn: () => requestJson<AppStoreStateResponse>('/api/appstore/state'),
        staleTime: 30_000,
        refetchOnWindowFocus: true,
    })
    const { data: appStoreSyncStatus, refetch: refetchAppStoreSyncStatus } = useQuery<AppStoreSyncStatusResponse, Error>({
        queryKey: ['appstore-sync-status'],
        queryFn: () => requestJson<AppStoreSyncStatusResponse>('/api/appstore/sync/status'),
        staleTime: 0,
        refetchOnWindowFocus: true,
        refetchInterval: isRefreshingStore ? 2_000 : false,
    })

    const apps = data ?? []
    const catalogs = catalogsData ?? []
    const resolvedLocale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const effectiveIsLoading = isLoading || isLocalRefreshing
    const effectiveIsSyncRunning = isRefreshingStore || appStoreSyncStatus?.status === 'running'
    const lastSyncedAt = appStoreSyncStatus?.lastSyncedAt ?? appStoreState?.lastSyncedAt
    const formattedFullSyncAt = formatFullSyncTimestamp(lastSyncedAt, resolvedLocale)
    const sourceParam = searchParams.get('source')
    const selectedInstallSource: InstallSourceKey = lockedInstallSource ?? (sourceParam === 'compose' ? 'compose' : 'marketplace')
    const quickAppKey = searchParams.get('app')?.trim().toLowerCase() ?? ''
    const directOpenAppKey = typeof location.state === 'object' && location.state && 'openAppKey' in location.state && typeof location.state.openAppKey === 'string'
        ? location.state.openAppKey.trim().toLowerCase()
        : ''
    const contentScopeContainer = typeof document === 'undefined' ? null : document.querySelector('#app-shell-main')
    const favoriteSet = useMemo(() => new Set((favoritesData?.favorites ?? []).map((item) => item.toLowerCase())), [favoritesData?.favorites])
    const selectedAppSettings = useMemo(() => {
        const selectedAppKey = (selectedApp?.key ?? '').toLowerCase()
        if (!selectedAppKey) {
            return selectedApp?.settings ?? {}
        }

        const canonicalSelectedApp = apps.find((app) => (app.key ?? '').toLowerCase() === selectedAppKey)
        return canonicalSelectedApp?.settings ?? selectedApp?.settings ?? {}
    }, [apps, selectedApp])
    const effectiveInstallSettings = useMemo(
        () => (Object.keys(installSettings).length > 0 ? installSettings : selectedAppSettings),
        [installSettings, selectedAppSettings],
    )
    const currentHostname = typeof window === 'undefined' ? '' : window.location.hostname
    const isDarkMode = colorMode === 'dark'
    const palette = getSurfacePalette(isDarkMode)
    const appStoreControlTextSx = {
        fontSize: 14,
        fontWeight: 500,
        color: palette.text,
    }
    const appStoreMenuItemSx = {
        fontSize: 14,
        fontWeight: 500,
        color: palette.text,
        '&.Mui-selected': {
            backgroundColor: palette.accentSoft,
            color: palette.text,
        },
        '&.Mui-selected:hover': {
            backgroundColor: palette.accentSoft,
        },
    }
    const installDialogFieldSx = getSurfaceFieldSx(palette, { helperErrorColor: palette.danger })
    const installDialogSelectMenuProps = {
        disablePortal: true,
        slotProps: {
            paper: {
                sx: {
                    borderRadius: 0,
                    mt: 0.5,
                    zIndex: 1501,
                    backgroundColor: palette.dialogBg,
                    color: palette.text,
                    border: `1px solid ${palette.borderStrong}`,
                    '& .MuiMenuItem-root': appStoreMenuItemSx,
                },
            },
        },
    } as const
    const domainSuffix = wildcardDomain ? `.${wildcardDomain}` : ''
    const normalizedCustomDomains = useMemo(
        () => customDomains.map((d) => normalizeCustomDomain(d)).filter(Boolean),
        [customDomains],
    )
    const availableVersions = selectedApp ? getAppStoreInstallDistributions(selectedApp).flatMap((distribution) => distribution.versions) : []
    const syncStatusTitle = effectiveIsSyncRunning ? t('appStorePage.actions.refreshing') : t('appStorePage.actions.refresh')
    const keywordMatchedApps = useMemo(() => apps.filter((app) => matchesAppStoreSearch(app, deferredSearchValue)), [apps, deferredSearchValue])
    const mainCategoryCounts = useMemo(() => {
        const counts = new Map<string, number>()

        counts.set('all', keywordMatchedApps.length)
        for (const catalog of catalogs) {
            const catalogKey = catalog.key ?? ''
            if (!catalogKey) {
                continue
            }

            counts.set(catalogKey, keywordMatchedApps.filter((app) => matchesLegacyMainCatalog(app, catalogKey)).length)
        }

        return counts
    }, [catalogs, keywordMatchedApps])
    const mainCategories = useMemo<CatalogOption[]>(
        () => [
            {
                key: 'all',
                title: t('appStorePage.filters.allMainCategories'),
                count: mainCategoryCounts.get('all') ?? 0,
            },
            ...catalogs
                .map((catalog) => {
                    const key = catalog.key ?? ''
                    if (!key) {
                        return null
                    }

                    return {
                        key,
                        title: catalog.title ?? key,
                        count: mainCategoryCounts.get(key) ?? 0,
                    }
                })
                .filter((catalog): catalog is CatalogOption => Boolean(catalog)),
        ],
        [catalogs, mainCategoryCounts, t],
    )
    const appsInSelectedMainCategory = useMemo(
        () => keywordMatchedApps.filter((app) => matchesLegacyMainCatalog(app, selectedMainCatalogKey)),
        [keywordMatchedApps, selectedMainCatalogKey],
    )
    const subCategoryCounts = useMemo(() => {
        const counts = new Map<string, number>()

        counts.set('all', appsInSelectedMainCategory.length)
        for (const catalog of getSubCatalogs(catalogs, selectedMainCatalogKey)) {
            const catalogKey = catalog.key ?? ''
            if (!catalogKey) {
                continue
            }

            counts.set(catalogKey, appsInSelectedMainCategory.filter((app) => matchesLegacySubCatalog(app, catalogKey)).length)
        }

        return counts
    }, [appsInSelectedMainCategory, catalogs, selectedMainCatalogKey])
    const subCategories = useMemo(
        () => [
            {
                key: 'all',
                title: t('appStorePage.filters.allSubCategories'),
                count: subCategoryCounts.get('all') ?? 0,
            },
            ...getSubCatalogs(catalogs, selectedMainCatalogKey)
                .map((catalog) => {
                    const key = catalog.key ?? ''
                    if (!key) {
                        return null
                    }

                    return {
                        key,
                        title: catalog.title ?? key,
                        count: subCategoryCounts.get(key) ?? 0,
                    }
                })
                .filter((catalog): catalog is CatalogOption => Boolean(catalog)),
        ],
        [catalogs, selectedMainCatalogKey, subCategoryCounts, t],
    )
    const resultsSectionTitle = useMemo(() => {
        const segments = [t('appStorePage.results.allAppsSectionTitle')]
        const selectedMainCategory = mainCategories.find((category) => category.key === selectedMainCatalogKey)
        const selectedSubCategory = subCategories.find((category) => category.key === selectedSubCatalogKey)

        if (selectedMainCategory && selectedMainCategory.key !== 'all') {
            segments.push(selectedMainCategory.title)
        }

        if (selectedSubCategory && selectedSubCategory.key !== 'all') {
            segments.push(selectedSubCategory.title)
        }

        return segments.join(' / ')
    }, [mainCategories, selectedMainCatalogKey, selectedSubCatalogKey, subCategories, t])

    const filteredApps = useMemo(
        () =>
            apps.filter(
                (app) =>
                    matchesLegacyMainCatalog(app, selectedMainCatalogKey) &&
                    matchesLegacySubCatalog(app, selectedSubCatalogKey) &&
                    matchesAppStoreSearch(app, deferredSearchValue),
            ),
        [apps, deferredSearchValue, selectedMainCatalogKey, selectedSubCatalogKey],
    )
    const favoriteApps = useMemo(() => {
        const favoriteKeys = [...(favoritesData?.favorites ?? [])].reverse()
        const allAppMap = new Map(apps.map((app) => [(app.key ?? '').toLowerCase(), app]))

        return favoriteKeys
            .map((favoriteKey) => allAppMap.get(favoriteKey.toLowerCase()))
            .filter((app): app is AppStoreApp => Boolean(app))
    }, [apps, favoritesData?.favorites])
    const favoriteListAriaLabel = t('appStorePage.actions.favoriteList', { count: favoriteApps.length })
    const installSourceOptions: Array<{ key: InstallSourceKey; label: string; description: string }> = [
        {
            key: 'marketplace',
            label: t('appStorePage.sources.marketplace.label'),
            description: t('appStorePage.sources.marketplace.description'),
        },
        {
            key: 'compose',
            label: t('appStorePage.sources.compose.label'),
            description: t('appStorePage.sources.compose.description'),
        },
    ]
    const pageHeroDescription =
        selectedInstallSource === 'marketplace'
            ? t('appStorePage.hero.description')
            : t(`appStorePage.sources.${selectedInstallSource}.heroDescription`)
    const pageHeroTitle = selectedInstallSource === 'marketplace'
        ? undefined
        : installSourceOptions.find((option) => option.key === selectedInstallSource)?.label
    const selectedComposeMount = composeMountRows.find((row) => row.id === selectedComposeMountId) ?? composeMountRows[0] ?? null
    const showPageHero = selectedInstallSource === 'compose' && !hideInstallSourceSelector

    useEffect(() => {
        if (composeMountRows.some((row) => row.id === selectedComposeMountId)) {
            return
        }

        setSelectedComposeMountId(composeMountRows[0]?.id ?? 'mount-1')
    }, [composeMountRows, selectedComposeMountId])

    useEffect(() => {
        if (selectedMainCatalogKey === 'all') {
            setSelectedSubCatalogKey('all')
        }
    }, [selectedMainCatalogKey])

    useEffect(() => {
        let isActive = true

        void fetch('/api/settings/domain', {
            credentials: 'include',
            headers: {
                Accept: 'application/json',
            },
        })
            .then(async (response) => {
                if (!response.ok) {
                    throw new Error(`Failed to load domain settings: ${response.status}`)
                }

                return (await response.json()) as DomainSettingsResponse
            })
            .then((payload) => {
                if (!isActive) {
                    return
                }

                setWildcardDomain((payload.wildcard_domain ?? '').trim())
            })
            .catch(() => {
                if (!isActive) {
                    return
                }

                setWildcardDomain('')
            })

        return () => {
            isActive = false
        }
    }, [])

    useEffect(() => {
        if (!selectedApp || !isInstallMode) {
            return
        }

        const distribution = getPreferredAppStoreInstallDistribution(selectedApp)
        setInstallName('')
        setSelectedVersion(distribution.versions[0] ?? 'latest')
        setInstallSettings({ ...(selectedApp.settings ?? {}) })
        setInstallError(null)
        setInstallFieldErrors({})
        setIsDomainEnabled(Boolean(wildcardDomain))
        setCustomDomains([])
        setCustomDomainErrorIndex(null)
    }, [isInstallMode, selectedApp, wildcardDomain])

    function captureContentViewport() {
        if (!(contentScopeContainer instanceof HTMLElement)) {
            setContentViewportRect(null)
            return
        }

        const rect = contentScopeContainer.getBoundingClientRect()

        setContentViewportRect({
            top: rect.top,
            left: rect.left,
            width: rect.width,
            height: rect.height,
        })
    }

    function openFavoritesDialog() {
        captureContentViewport()
        setIsFavoritesOpen(true)
    }

    function openAppDetail(app: AppStoreApp, source: DetailDialogSource) {
        captureContentViewport()
        setDetailDialogSource(source)
        setSelectedApp(app)
    }

    useEffect(() => {
        const nextKeyword = searchParams.get('keyword') ?? ''
        if (nextKeyword === searchValue) {
            return
        }

        setSearchValue(nextKeyword)
    }, [searchParams])

    useEffect(() => {
        const pendingOpenAppKey = directOpenAppKey || quickAppKey

        if (!pendingOpenAppKey || selectedApp) {
            return
        }

        const matchedApp = apps.find((app) => (app.key ?? '').toLowerCase() === pendingOpenAppKey)
        if (!matchedApp) {
            return
        }

        openAppDetail(matchedApp, 'catalog')

        if (directOpenAppKey) {
            navigate(`${location.pathname}${location.search}`, { replace: true, state: null })
            return
        }

        const nextParams = new URLSearchParams(searchParams)
        nextParams.delete('app')
        nextParams.delete('keyword')
        setSearchParams(nextParams, { replace: true })
    }, [apps, directOpenAppKey, location.pathname, location.search, navigate, quickAppKey, searchParams, selectedApp, setSearchParams])

    useEffect(() => {
        if (!(contentScopeContainer instanceof HTMLElement) || (!selectedApp && !isFavoritesOpen)) {
            return
        }

        const preventBackgroundScroll = (event: Event) => {
            if (!(event.target instanceof Element)) {
                return
            }

            if (event.target.closest('.MuiDialog-paper')) {
                return
            }

            event.preventDefault()
        }

        contentScopeContainer.addEventListener('wheel', preventBackgroundScroll, { passive: false, capture: true })
        contentScopeContainer.addEventListener('touchmove', preventBackgroundScroll, { passive: false, capture: true })

        return () => {
            contentScopeContainer.removeEventListener('wheel', preventBackgroundScroll, { capture: true })
            contentScopeContainer.removeEventListener('touchmove', preventBackgroundScroll, { capture: true })
        }
    }, [contentScopeContainer, isFavoritesOpen, selectedApp])

    async function handleInstallSubmit() {
        if (!selectedApp) {
            return
        }

        const normalizedAppId = normalizeInstallName(installName)
        const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
        setInstallFieldErrors({})
        setCustomDomainErrorIndex(null)

        if (!normalizedAppId) {
            const message = t('appStorePage.install.validation.appIdRequired')
            setInstallFieldErrors({ appId: message })
            setInstallError(message)
            appIdInputRef.current?.focus()
            return
        }

        if (!isInstallNameValid(normalizedAppId)) {
            const message = t('appStorePage.install.validation.appId')
            setInstallFieldErrors({ appId: message })
            setInstallError(message)
            appIdInputRef.current?.focus()
            return
        }

        // Validate each non-empty custom domain
        const seenDomains = new Set<string>()
        // Pre-compute wildcard domain for conflict detection
        const wildcardDomainName = (selectedApp.is_web_app && Boolean(wildcardDomain) && isDomainEnabled)
            ? `${normalizedAppId}.${wildcardDomain}`
            : null
        if (wildcardDomainName) {
            seenDomains.add(wildcardDomainName)
        }
        for (let i = 0; i < customDomains.length; i++) {
            const rawValue = customDomains[i]
            if (!rawValue.trim()) {
                continue
            }
            const domain = normalizeCustomDomain(rawValue)
            if (!domain || !isValidCustomDomain(domain)) {
                const message = t('appStorePage.install.validation.customDomainFormat')
                setInstallFieldErrors({ customDomain: message })
                setInstallError(message)
                setCustomDomainErrorIndex(i)
                customDomainInputRefs.current[i]?.focus()
                return
            }
            if (seenDomains.has(domain)) {
                const conflictSource = wildcardDomainName && domain === wildcardDomainName
                    ? 'wildcard'
                    : 'custom'
                const message = conflictSource === 'wildcard'
                    ? t('appStorePage.install.validation.customDomainConflictWithDefault', { domain })
                    : t('appStorePage.install.validation.customDomainDuplicate', { domain })
                setInstallFieldErrors({ customDomain: message })
                setInstallError(message)
                setCustomDomainErrorIndex(i)
                customDomainInputRefs.current[i]?.focus()
                return
            }
            seenDomains.add(domain)
        }

        const portsValidationMessage = getInstallPortsValidationMessage(effectiveInstallSettings, t, locale)
        if (portsValidationMessage) {
            setInstallFieldErrors({ settings: { [portsValidationMessage.key]: portsValidationMessage.message } })
            setInstallError(portsValidationMessage.message)
            installSettingInputRefs.current[portsValidationMessage.key]?.focus()
            return
        }

        setIsSubmittingInstall(true)
        setInstallError(null)

        try {
            const hasAnyDomain = (Boolean(wildcardDomain) && isDomainEnabled) || normalizedCustomDomains.length > 0
            const proxyEnabled = selectedApp.is_web_app ? hasAnyDomain : false
            const domainNames: string[] = []
            if (selectedApp.is_web_app) {
                if (Boolean(wildcardDomain) && isDomainEnabled) {
                    domainNames.push(`${normalizedAppId}.${wildcardDomain}`)
                }
                for (const d of normalizedCustomDomains) {
                    if (!domainNames.includes(d)) {
                        domainNames.push(d)
                    }
                }
            }
            if (domainNames.length === 0) {
                domainNames.push(currentHostname)
            }

            const installResult = await installApp(
                selectedApp,
                normalizedAppId,
                selectedVersion,
                effectiveInstallSettings,
                domainNames.length > 0 ? domainNames : [currentHostname],
                proxyEnabled,
            )
            setSelectedApp(null)
            setIsInstallMode(false)
            const nextSearchParams = new URLSearchParams()
            if (installResult?.app_id) {
                nextSearchParams.set('trackedAppId', installResult.app_id)
            }
            if (installResult?.tracking_id) {
                nextSearchParams.set('trackingId', installResult.tracking_id)
            }
            navigate(nextSearchParams.size > 0 ? `/myapps?${nextSearchParams.toString()}` : '/myapps', { replace: true })
        } catch (submitError) {
            let message = submitError instanceof Error ? submitError.message : t('appStorePage.install.feedback.error')
            if (/Exceed the maximum number of apps/i.test(message)) {
                message = t('appStorePage.install.feedback.maxApps')
            }
            // Detect port conflict error from backend and show i18n-friendly message
            const portMatch = message.match(/Port\s+(\d+)\s+is already in use/i)
            if (portMatch) {
                const conflictedPort = portMatch[1]
                message = t('appStorePage.install.feedback.portConflict', { port: conflictedPort })
                const matchedSettingKey = Object.entries(effectiveInstallSettings).find(([, value]) => value.trim() === conflictedPort)?.[0]
                if (matchedSettingKey) {
                    setInstallFieldErrors({ settings: { [matchedSettingKey]: message } })
                    installSettingInputRefs.current[matchedSettingKey]?.focus()
                }
            }
            setInstallError(message)
        } finally {
            setIsSubmittingInstall(false)
        }
    }

    function handleCloseModal() {
        const shouldRestoreFavorites = detailDialogSource === 'favorites'

        setSelectedApp(null)
        setIsInstallMode(false)
        setInstallError(null)
        setInstallFieldErrors({})
        setCustomDomainErrorIndex(null)
        setDetailDialogSource('catalog')
        setContentViewportRect(null)

        if (shouldRestoreFavorites) {
            openFavoritesDialog()
        }
    }

    function handleCatalogClick(subCategory: AppStoreCatalogItem, mainCategory?: AppStoreCatalogItem) {
        setSelectedMainCatalogKey(mainCategory?.key ?? 'all')
        setSelectedSubCatalogKey(subCategory.key ?? 'all')
        handleCloseModal()
    }

    function handleInstallSourceChange(source: InstallSourceKey) {
        if (lockedInstallSource || hideInstallSourceSelector) {
            return
        }

        const nextParams = new URLSearchParams(searchParams)
        if (source === 'marketplace') {
            nextParams.delete('source')
        } else {
            nextParams.set('source', source)
        }

        setSearchParams(nextParams, { replace: true })
        setSelectedApp(null)
        setIsInstallMode(false)
    }

    function clearComposeFeedback() {
        setInstallError(null)
        setInstallFeedback(null)
    }

    function updateComposeEnvRow(id: string, field: 'key' | 'value', value: string) {
        clearComposeFeedback()
        setComposeFieldErrors((currentValue) => ({ ...currentValue, env: undefined }))
        setComposeEnvRows((currentValue) => currentValue.map((row) => (row.id === id ? { ...row, [field]: value } : row)))
    }

    function addComposeEnvRow() {
        clearComposeFeedback()
        setComposeEnvExpanded(true)
        setComposeEnvRows((currentValue) => [...currentValue, { id: `env-${Date.now()}-${currentValue.length}`, key: '', value: '' }])
    }

    function removeComposeEnvRow(id: string) {
        clearComposeFeedback()
        setComposeEnvRows((currentValue) => {
            const nextRows = currentValue.filter((row) => row.id !== id)
            return nextRows.length > 0 ? nextRows : [{ id: 'env-1', key: '', value: '' }]
        })
    }

    function updateComposeMountRow(id: string, field: 'path' | 'content', value: string) {
        clearComposeFeedback()
        setComposeFieldErrors((currentValue) => ({ ...currentValue, mountPath: undefined }))
        setComposeMountRows((currentValue) => currentValue.map((row) => (row.id === id ? { ...row, [field]: value } : row)))
    }

    function addComposeMountRow() {
        clearComposeFeedback()
        const nextId = `mount-${Date.now()}-${composeMountRows.length}`
        setComposeMountExpanded(true)
        setComposeMountRows((currentValue) => [...currentValue, { id: nextId, path: '', content: '' }])
        setSelectedComposeMountId(nextId)
    }

    function removeComposeMountRow(id: string) {
        clearComposeFeedback()
        setComposeMountRows((currentValue) => {
            const nextRows = currentValue.filter((row) => row.id !== id)
            return nextRows.length > 0 ? nextRows : [{ id: 'mount-1', path: '', content: '' }]
        })
    }

    function resetComposeToSample() {
        clearComposeFeedback()
        setComposeFieldErrors((currentValue) => ({ ...currentValue, composeContent: undefined }))
        setComposeContent(DEFAULT_COMPOSE_TEMPLATE)
    }

    async function handleComposeFileSelected(file: File | null) {
        if (!file) {
            return
        }

        const text = await file.text()
        clearComposeFeedback()
        setComposeFieldErrors((currentValue) => ({ ...currentValue, composeContent: undefined }))
        setComposeContent(text)
    }

    async function handleComposeEnvFileSelected(file: File | null) {
        if (!file) {
            return
        }

        const text = await file.text()
        const rows = text
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter((line) => line && !line.startsWith('#'))
            .map((line, index) => {
                const separatorIndex = line.indexOf('=')
                return {
                    id: `env-import-${Date.now()}-${index}`,
                    key: separatorIndex >= 0 ? line.slice(0, separatorIndex).trim() : line,
                    value: separatorIndex >= 0 ? line.slice(separatorIndex + 1) : '',
                }
            })

        clearComposeFeedback()
        setComposeEnvExpanded(true)
        setComposeFieldErrors((currentValue) => ({ ...currentValue, env: undefined }))
        setComposeEnvRows(rows.length > 0 ? rows : [{ id: 'env-1', key: '', value: '' }])
    }

    async function handleComposeMountFilesSelected(files: FileList | null) {
        if (!files || files.length === 0) {
            return
        }

        const importedRows = await Promise.all(
            Array.from(files).map(async (file, index) => ({
                id: `mount-import-${Date.now()}-${index}`,
                path: normalizeMountPath(file.name),
                content: await file.text(),
            })),
        )

        clearComposeFeedback()
        setComposeMountExpanded(true)
        setComposeFieldErrors((currentValue) => ({ ...currentValue, mountPath: undefined }))
        setComposeMountRows((currentValue) => {
            const preservedRows = currentValue.filter((row) => row.path.trim() || row.content.trim())
            return [...preservedRows, ...importedRows]
        })
        if (importedRows[0]) {
            setSelectedComposeMountId(importedRows[0].id)
        }
    }

    async function handleComposeInstall() {
        const nextErrors: { appId?: string; composeContent?: string; domain?: string; env?: string; mountPath?: string } = {}
        const normalizedComposeAppId = normalizeInstallName(composeAppId)
        const normalizedComposeDomain = normalizeCustomDomain(composeDomain)
        const envRows = composeEnvRows.filter((row) => row.key.trim() || row.value.trim())
        const mountRows = composeMountRows
            .map((row) => ({ ...row, path: normalizeMountPath(row.path) }))
            .filter((row) => row.path || row.content.trim())

        if (!normalizedComposeAppId) {
            nextErrors.appId = t('appStorePage.sources.compose.workspace.appIdRequired')
        } else if (!isInstallNameValid(normalizedComposeAppId)) {
            nextErrors.appId = t('appStorePage.install.validation.appId')
        }

        if (!composeContent.trim()) {
            nextErrors.composeContent = t('appStorePage.sources.compose.workspace.composeRequired')
        }

        if (normalizedComposeDomain && !isValidCustomDomain(normalizedComposeDomain)) {
            nextErrors.domain = t('appStorePage.install.validation.customDomainFormat')
        }

        if (envRows.some((row) => row.value.trim() && !row.key.trim())) {
            nextErrors.env = t('appStorePage.sources.compose.workspace.envKeyRequired')
        }

        if (mountRows.some((row) => row.content.trim() && !row.path)) {
            nextErrors.mountPath = t('appStorePage.sources.compose.workspace.mountPathRequired')
        } else if (mountRows.some((row) => row.path && !isValidMountPath(row.path))) {
            nextErrors.mountPath = t('appStorePage.sources.compose.workspace.mountPathInvalid')
        } else {
            const uniqueMountPaths = new Set<string>()
            for (const row of mountRows) {
                if (!row.path) {
                    continue
                }
                if (uniqueMountPaths.has(row.path)) {
                    nextErrors.mountPath = t('appStorePage.sources.compose.workspace.mountPathDuplicate')
                    break
                }
                uniqueMountPaths.add(row.path)
            }
        }

        setComposeAppId(normalizedComposeAppId || composeAppId)
        setComposeDomain(normalizedComposeDomain)
        setComposeMountRows((currentValue) => currentValue.map((row) => ({ ...row, path: normalizeMountPath(row.path) })))
        setComposeFieldErrors(nextErrors)
        clearComposeFeedback()

        if (Object.keys(nextErrors).length > 0) {
            setInstallError(Object.values(nextErrors)[0] ?? null)
            return
        }

        setIsSubmittingCompose(true)
        try {
            const installResult = await installComposeApp({
                app_id: normalizedComposeAppId,
                compose_content: composeContent,
                env: envRows.map((row) => ({ key: row.key.trim(), value: row.value })),
                mounts: mountRows.map((row) => ({ path: row.path, content: row.content })),
                ...(normalizedComposeDomain ? { domain: normalizedComposeDomain } : {}),
            })
            const nextSearchParams = new URLSearchParams()
            if (installResult?.app_id) {
                nextSearchParams.set('trackedAppId', installResult.app_id)
            }
            if (installResult?.tracking_id) {
                nextSearchParams.set('trackingId', installResult.tracking_id)
            }
            navigate(nextSearchParams.size > 0 ? `/myapps?${nextSearchParams.toString()}` : '/myapps', { replace: true })
        } catch (submitError) {
            setInstallError(submitError instanceof Error ? submitError.message : t('appStorePage.sources.compose.workspace.installFailedTitle'))
        } finally {
            setIsSubmittingCompose(false)
        }
    }

    function handleSearchChange(value: string) {
        setSearchValue(value)
    }

    useEffect(() => {
        const currentStatus = appStoreSyncStatus?.status
        if (!currentStatus) {
            return
        }

        const previousStatus = previousSyncStatusRef.current
        previousSyncStatusRef.current = currentStatus

        if (currentStatus === 'running') {
            if (!isRefreshingStore) {
                setIsRefreshingStore(true)
            }
            return
        }

        if (previousStatus === 'running') {
            setIsRefreshingStore(false)
            void Promise.all([
                refetch(),
                refetchCatalogs(),
                refetchFavorites(),
                refetchAppStoreState(),
            ])
                .then(() => {
                    setRefreshFeedback({
                        severity: 'success',
                        message: t('appStorePage.feedback.refreshComplete'),
                    })
                })
                .catch(() => {
                    setRefreshFeedback({
                        severity: 'error',
                        message: t('appStorePage.states.errorTitle'),
                    })
                })
            return
        }

        if (isRefreshingStore) {
            setIsRefreshingStore(false)
        }
    }, [appStoreSyncStatus?.status, isRefreshingStore, refetch, refetchAppStoreState, refetchCatalogs, refetchFavorites, t])

    async function handleLocalRefresh() {
        setIsLocalRefreshing(true)
        try {
            await Promise.all([
                refetch(),
                refetchAppStoreState(),
                refetchCatalogs(),
                refetchFavorites(),
                refetchAppStoreSyncStatus(),
            ])
        } finally {
            setIsLocalRefreshing(false)
        }
    }

    async function handleRefreshStore() {
        if (effectiveIsSyncRunning) {
            setInstallError(t('appStorePage.actions.syncAlreadyRunning'))
            return
        }

        // Check if a sync is already running
        try {
            const statusResp = await requestJson<{ status: string }>('/api/appstore/sync/status')
            if (statusResp.status === 'running') {
                setInstallError(t('appStorePage.actions.syncAlreadyRunning'))
                return
            }
        } catch {
            // proceed even if status check fails
        }

        captureContentViewport()
        setRefreshConfirmOpen(true)
    }

    async function executeRefreshStore() {
        setRefreshConfirmOpen(false)
        setIsRefreshingStore(true)
        setRefreshFeedback(null)

        try {
            const syncResult = await requestJson<{ status: string; message?: string }>('/api/appstore/sync', {
                method: 'POST',
            })

            if (syncResult.status !== 'accepted' && syncResult.status !== 'already_running') {
                throw new Error(syncResult.message || t('appStorePage.states.errorTitle'))
            }
            await Promise.all([
                refetchAppStoreSyncStatus(),
                refetchAppStoreState(),
            ])
        } catch (refreshError) {
            setIsRefreshingStore(false)
            setInstallError(refreshError instanceof Error ? refreshError.message : t('appStorePage.states.errorTitle'))
        }
    }

    async function handleToggleFavorite(appKey: string | undefined, options?: { closeDetail?: boolean }) {
        if (!appKey) {
            return
        }

        const normalizedKey = appKey.toLowerCase()
        if (favoriteSet.has(normalizedKey)) {
            await requestJson<ProductAuthFavoritesResponse>(`/api/auth/favorites/${normalizedKey}`, { method: 'DELETE' })
        } else {
            await requestJson<ProductAuthFavoritesResponse>('/api/auth/favorites', {
                method: 'POST',
                body: JSON.stringify({ app_key: normalizedKey }),
            })
        }

        await refetchFavorites()

        if (options?.closeDetail) {
            const shouldRestoreFavorites = detailDialogSource === 'favorites'

            setSelectedApp(null)
            setIsInstallMode(false)
            setInstallError(null)
            setDetailDialogSource('catalog')
            setContentViewportRect(null)

            if (shouldRestoreFavorites) {
                openFavoritesDialog()
            }
        }
    }

    // Keep severity and message stable during Snackbar exit animation to prevent flash
    const installToastActive = Boolean(installFeedback) || Boolean(installError)
    if (installToastActive) {
        lastInstallSeverityRef.current = installError ? 'error' : installFeedback!.severity
        lastInstallMessageRef.current = installError ?? installFeedback?.message ?? ''
    }
    const installToastSeverity = installToastActive ? (installError ? 'error' : installFeedback!.severity) : lastInstallSeverityRef.current
    const installToastMessage = installToastActive ? (installError ?? installFeedback?.message ?? '') : lastInstallMessageRef.current

    const refreshToastActive = Boolean(refreshFeedback)
    if (refreshToastActive) {
        lastRefreshSeverityRef.current = refreshFeedback!.severity
        lastRefreshMessageRef.current = refreshFeedback!.message
    }
    const refreshToastSeverity = refreshToastActive ? refreshFeedback!.severity : lastRefreshSeverityRef.current
    const refreshToastMessage = refreshToastActive ? refreshFeedback!.message : lastRefreshMessageRef.current

    return (
        <>
            <Box
                sx={{
                    height: 'calc(100vh - 120px)',
                    position: 'relative',
                    mx: { xs: -1, md: -3 },
                    my: { xs: -1.25, md: -2.25 },
                    px: { xs: 2, md: 3 },
                    py: { xs: 1.25, md: 1.5 },
                    backgroundColor: palette.pageBg,
                    color: palette.text,
                    overflow: 'hidden',
                    '& .MuiCard-root': {
                        background: `${palette.panelBg} !important`,
                        borderColor: `${palette.borderStrong} !important`,
                        color: `${palette.text} !important`,
                    },
                    '& .MuiPaper-root': {
                        backgroundColor: `${palette.panelBg} !important`,
                        color: `${palette.text} !important`,
                    },
                    '& .MuiOutlinedInput-root': {
                        backgroundColor: `${palette.panelBg} !important`,
                        color: `${palette.text} !important`,
                    },
                    '& .MuiOutlinedInput-notchedOutline': {
                        borderColor: `${palette.border} !important`,
                    },
                    '& .MuiInputLabel-root, & .MuiInputBase-input, & .MuiSelect-select': {
                        color: `${palette.text} !important`,
                    },
                    '& .MuiInputBase-input::placeholder': {
                        color: `${palette.placeholderText} !important`,
                        opacity: '1 !important',
                    },
                    '& .MuiMenuItem-root': {
                        color: `${palette.text} !important`,
                    },
                    '& .MuiTypography-root': {
                        color: palette.text,
                    },
                    '& .MuiAlert-root': {
                        backgroundColor: `${palette.panelBg} !important`,
                        color: `${palette.text} !important`,
                        border: `1px solid ${palette.border}`,
                    },
                }}
            >
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, width: '100%', height: '100%', minHeight: 0 }}>
                    {showPageHero || !hideInstallSourceSelector ? (
                        <Box
                            sx={{
                                flexShrink: 0,
                                display: 'grid',
                                gap: 1,
                            }}
                        >
                            {showPageHero ? (
                                <PageDescriptionHeader
                                    title={pageHeroTitle}
                                    description={pageHeroDescription}
                                    titleColor={palette.text}
                                    descriptionColor={palette.subtleText}
                                    sx={{ mt: 0, pt: pageHeroTitle ? 0.5 : 0, mb: 0.5 }}
                                />
                            ) : null}
                            {!hideInstallSourceSelector ? (
                                <Box
                                    sx={{
                                        display: 'grid',
                                        gap: 1,
                                        gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' },
                                    }}
                                >
                                    {installSourceOptions.map((option) => {
                                        const active = option.key === selectedInstallSource
                                        return (
                                            <Button
                                                key={option.key}
                                                onClick={() => {
                                                    handleInstallSourceChange(option.key)
                                                }}
                                                variant="outlined"
                                                sx={{
                                                    alignItems: 'flex-start',
                                                    justifyContent: 'flex-start',
                                                    textAlign: 'left',
                                                    textTransform: 'none',
                                                    borderRadius: '2px',
                                                    minHeight: 88,
                                                    px: 1.5,
                                                    py: 1.25,
                                                    borderColor: active ? palette.accent : palette.border,
                                                    backgroundColor: active ? palette.accentSoft : palette.panelBg,
                                                    color: palette.text,
                                                    '&:hover': {
                                                        borderColor: active ? palette.accent : palette.borderStrong,
                                                        backgroundColor: active ? palette.accentSoft : palette.panelSoft,
                                                    },
                                                }}
                                            >
                                                <Box>
                                                    <Typography sx={{ fontSize: 15, fontWeight: 600, lineHeight: 1.35, color: palette.text }}>
                                                        {option.label}
                                                    </Typography>
                                                    <Typography sx={{ mt: 0.5, fontSize: 13.5, lineHeight: 1.55, color: palette.subtleText }}>
                                                        {option.description}
                                                    </Typography>
                                                </Box>
                                            </Button>
                                        )
                                    })}
                                </Box>
                            ) : null}
                        </Box>
                    ) : null}

                    {selectedInstallSource === 'marketplace' ? (
                        <Box
                            sx={{
                                flexShrink: 0,
                                display: 'grid',
                                gap: 2.25,
                                py: 0,
                                pr: { md: '18px' },
                                backgroundColor: palette.panelBg,
                                boxShadow: 'none',
                            }}
                        >
                            <PageDescriptionHeader
                                title={t('nav.appStore.label')}
                                description={t('appStorePage.hero.description')}
                                titleColor={palette.text}
                                descriptionColor={palette.subtleText}
                                sx={{ mb: 0.75 }}
                                actions={(
                                    <Box
                                        sx={{
                                            display: { xs: 'flex', md: 'grid' },
                                            gridTemplateColumns: { md: '26px 26px 26px' },
                                            gridTemplateRows: { md: '20px' },
                                            columnGap: { md: 0 },
                                            gap: { xs: 0.75, md: 0 },
                                            justifyContent: 'flex-end',
                                            justifyItems: { md: 'center' },
                                            alignItems: 'center',
                                            flexShrink: 0,
                                            alignSelf: 'start',
                                            pt: 0,
                                            mt: 0.05,
                                        }}
                                    >
                                        <Tooltip title={t('appStorePage.actions.favoriteList', { count: favoriteApps.length }).replace(/\s*\(\d+\)$/, '')}>
                                            <IconButton
                                                color="inherit"
                                                onClick={() => {
                                                    openFavoritesDialog()
                                                }}
                                                size="small"
                                                aria-label={favoriteListAriaLabel}
                                                className="app-shell-page-action"
                                                sx={{
                                                    width: { xs: 34, md: 26 },
                                                    minWidth: { xs: 34, md: 26 },
                                                    maxWidth: { xs: 34, md: 26 },
                                                    height: { xs: 34, md: 26 },
                                                    minHeight: { xs: 34, md: 26 },
                                                    maxHeight: { xs: 34, md: 26 },
                                                    padding: 0.25,
                                                    borderRadius: { xs: '10px', md: '2px' },
                                                    color: palette.subtleText,
                                                    gridColumn: { md: '1' },
                                                    gridRow: { md: '1' },
                                                    '&:hover': {
                                                        background: palette.panelSoft,
                                                        color: palette.text,
                                                        boxShadow: '0 1px 2px rgba(15, 23, 42, 0.06)',
                                                    },
                                                    '& .MuiSvgIcon-root': {
                                                        fontSize: 18,
                                                    },
                                                    '& .MuiBadge-badge': {
                                                        backgroundColor: palette.danger,
                                                        color: palette.accentContrast,
                                                        minWidth: 13,
                                                        height: 13,
                                                        padding: '0 3px',
                                                        fontSize: 8,
                                                        lineHeight: 1,
                                                        transform: 'translate(42%, -42%) scale(0.92)',
                                                        transformOrigin: '100% 0%',
                                                    },
                                                }}
                                                title={favoriteListAriaLabel}
                                            >
                                                <Badge
                                                    badgeContent={favoriteApps.length}
                                                    color="error"
                                                    max={99}
                                                    overlap="circular"
                                                    anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
                                                >
                                                    <FavoriteIcon />
                                                </Badge>
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title={isLocalRefreshing ? t('appStorePage.actions.localRefreshing') : t('appStorePage.actions.localRefresh')}>
                                            <IconButton
                                                color="inherit"
                                                onClick={() => {
                                                    void handleLocalRefresh()
                                                }}
                                                size="small"
                                                title={t('appStorePage.actions.localRefresh')}
                                                disabled={isLocalRefreshing}
                                                className="app-shell-page-action"
                                                sx={{
                                                    width: { xs: 34, md: 26 },
                                                    minWidth: { xs: 34, md: 26 },
                                                    maxWidth: { xs: 34, md: 26 },
                                                    height: { xs: 34, md: 26 },
                                                    minHeight: { xs: 34, md: 26 },
                                                    maxHeight: { xs: 34, md: 26 },
                                                    padding: 0.25,
                                                    borderRadius: { xs: '10px', md: '2px' },
                                                    color: palette.subtleText,
                                                    gridColumn: { md: '2' },
                                                    gridRow: { md: '1' },
                                                    ml: { xs: 0, md: -0.2 },
                                                    '&:hover': {
                                                        background: palette.panelSoft,
                                                        color: palette.text,
                                                        boxShadow: '0 1px 2px rgba(15, 23, 42, 0.06)',
                                                    },
                                                    '& .MuiSvgIcon-root': {
                                                        fontSize: 16.5,
                                                    },
                                                }}
                                            >
                                                {isLocalRefreshing ? <CircularProgress size={14} color="inherit" /> : <RefreshIcon />}
                                            </IconButton>
                                        </Tooltip>
                                        <Tooltip title={syncStatusTitle}>
                                            <IconButton
                                                color="inherit"
                                                onClick={() => {
                                                    void handleRefreshStore()
                                                }}
                                                size="small"
                                                title={syncStatusTitle}
                                                className="app-shell-page-action"
                                                sx={{
                                                    width: { xs: 34, md: 26 },
                                                    minWidth: { xs: 34, md: 26 },
                                                    maxWidth: { xs: 34, md: 26 },
                                                    height: { xs: 34, md: 26 },
                                                    minHeight: { xs: 34, md: 26 },
                                                    maxHeight: { xs: 34, md: 26 },
                                                    padding: 0.25,
                                                    borderRadius: { xs: '10px', md: '2px' },
                                                    color: palette.subtleText,
                                                    gridColumn: { md: '3' },
                                                    gridRow: { md: '1' },
                                                    ml: { xs: 0, md: -0.2 },
                                                    '&:hover': {
                                                        background: palette.panelSoft,
                                                        color: palette.text,
                                                        boxShadow: '0 1px 2px rgba(15, 23, 42, 0.06)',
                                                    },
                                                    '& .MuiSvgIcon-root': {
                                                        fontSize: 16.5,
                                                    },
                                                }}
                                            >
                                                {effectiveIsSyncRunning ? <CircularProgress size={14} color="inherit" /> : <SyncIcon />}
                                            </IconButton>
                                        </Tooltip>
                                    </Box>
                                )}
                            />
                            <Box
                                sx={{
                                    flexShrink: 0,
                                    display: 'grid',
                                    gap: 1.25,
                                    gridTemplateColumns: {
                                        xs: '1fr',
                                        md: 'repeat(2, minmax(0, 1fr))',
                                        xl: 'repeat(4, minmax(0, 1fr))',
                                    },
                                    alignItems: 'stretch',
                                }}
                            >
                                <TextField
                                    select
                                    size="small"
                                    value={selectedMainCatalogKey}
                                    onChange={(event) => {
                                        setSelectedMainCatalogKey(event.target.value)
                                    }}
                                    sx={{
                                        gridColumn: { md: 'span 1', xl: 'span 1' },
                                        '& .MuiOutlinedInput-root': {
                                            borderRadius: '4px',
                                            backgroundColor: palette.panelBg,
                                            minHeight: 42,
                                        },
                                        '& .MuiSelect-select': appStoreControlTextSx,
                                    }}
                                    slotProps={{
                                        select: {
                                            MenuProps: {
                                                slotProps: {
                                                    paper: {
                                                        sx: {
                                                            borderRadius: 0,
                                                            mt: 0.5,
                                                            '& .MuiMenuItem-root': appStoreMenuItemSx,
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    }}
                                >
                                    {mainCategories.map((category) => (
                                        <MenuItem key={category.key} value={category.key}>
                                            {formatCatalogOptionLabel(category)}
                                        </MenuItem>
                                    ))}
                                </TextField>
                                <TextField
                                    select
                                    size="small"
                                    value={selectedSubCatalogKey}
                                    onChange={(event) => {
                                        setSelectedSubCatalogKey(event.target.value)
                                    }}
                                    sx={{
                                        gridColumn: { md: 'span 1', xl: 'span 1' },
                                        '& .MuiOutlinedInput-root': {
                                            borderRadius: '4px',
                                            backgroundColor: palette.panelBg,
                                            minHeight: 42,
                                        },
                                        '& .MuiSelect-select': appStoreControlTextSx,
                                    }}
                                    slotProps={{
                                        select: {
                                            MenuProps: {
                                                slotProps: {
                                                    paper: {
                                                        sx: {
                                                            borderRadius: 0,
                                                            mt: 0.5,
                                                            '& .MuiMenuItem-root': appStoreMenuItemSx,
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                    }}
                                >
                                    {subCategories.map((category) => (
                                        <MenuItem key={category.key} value={category.key}>
                                            {formatCatalogOptionLabel(category, { hideCount: category.key === 'all' })}
                                        </MenuItem>
                                    ))}
                                </TextField>
                                <Box
                                    sx={{
                                        gridColumn: { xs: '1 / -1', md: 'span 2', xl: 'span 2' },
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'flex-start',
                                        justifySelf: 'stretch',
                                        width: '100%',
                                        minWidth: 0,
                                        gap: 0.5,
                                        minHeight: 42,
                                    }}
                                >
                                    <TextField
                                        size="small"
                                        value={searchValue}
                                        onChange={(event) => {
                                            handleSearchChange(event.target.value)
                                        }}
                                        placeholder={t('appStorePage.filters.searchPlaceholder')}
                                        sx={{
                                            width: '100%',
                                            maxWidth: '100%',
                                            flex: '1 1 auto',
                                            minWidth: 0,
                                            '& .MuiOutlinedInput-root': {
                                                borderRadius: '4px',
                                                backgroundColor: palette.panelBg,
                                                minHeight: 42,
                                                border: `1px solid ${palette.border}`,
                                                boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
                                            },
                                            '& .MuiInputBase-input': appStoreControlTextSx,
                                            '& .MuiInputBase-input::placeholder': {
                                                fontSize: 14,
                                                fontWeight: 400,
                                                color: '#94a3b8',
                                                opacity: 1,
                                            },
                                        }}
                                    />
                                </Box>
                            </Box>
                        </Box>
                    ) : selectedInstallSource === 'compose' ? (
                        <Box sx={{ flex: '1 1 auto', minHeight: 0, overflow: 'hidden', px: { xs: 0, md: 0.25 } }}>
                            <Box
                                sx={{
                                    display: 'grid',
                                    gridTemplateRows: 'auto auto minmax(0, 1fr)',
                                    gap: 1,
                                    height: '100%',
                                    minHeight: 0,
                                }}
                            >
                                <PageDescriptionHeader
                                    title={t('appStorePage.sources.compose.heroTitle')}
                                    description={t('appStorePage.sources.compose.heroDescription')}
                                    titleColor={palette.text}
                                    descriptionColor={palette.subtleText}
                                    sx={{ mt: 0, mb: 0.25 }}
                                    actions={hideInstallSourceSelector ? (
                                        <Button
                                            color="inherit"
                                            onClick={() => {
                                                navigate('/applications/deploy')
                                            }}
                                            size="small"
                                            className="app-shell-page-pill"
                                            sx={{ px: 1.5 }}
                                        >
                                            {t('appStorePage.sources.compose.backAction')}
                                        </Button>
                                    ) : undefined}
                                />

                                <Box
                                    sx={{
                                        display: 'grid',
                                        gap: 1,
                                        gridTemplateColumns: { xs: '1fr', lg: 'minmax(0, 1fr) minmax(220px, 280px) auto auto' },
                                        alignItems: 'start',
                                        borderRadius: '2px',
                                        border: `1px solid ${palette.border}`,
                                        backgroundColor: palette.panelBg,
                                        p: 1.1,
                                        flexShrink: 0,
                                    }}
                                >
                                    <TextField
                                        fullWidth
                                        label={t('appStorePage.sources.compose.workspace.appIdLabel')}
                                        placeholder={t('appStorePage.sources.compose.workspace.appIdPlaceholder')}
                                        value={composeAppId}
                                        onChange={(event) => {
                                            clearComposeFeedback()
                                            setComposeFieldErrors((currentValue) => ({ ...currentValue, appId: undefined }))
                                            setComposeAppId(event.target.value)
                                        }}
                                        error={Boolean(composeFieldErrors.appId)}
                                        helperText={composeFieldErrors.appId}
                                    />
                                    <TextField
                                        fullWidth
                                        label={t('appStorePage.sources.compose.workspace.domainLabel')}
                                        placeholder={t('appStorePage.sources.compose.workspace.domainPlaceholder')}
                                        value={composeDomain}
                                        onChange={(event) => {
                                            clearComposeFeedback()
                                            setComposeFieldErrors((currentValue) => ({ ...currentValue, domain: undefined }))
                                            setComposeDomain(event.target.value)
                                        }}
                                        error={Boolean(composeFieldErrors.domain)}
                                        helperText={composeFieldErrors.domain || ' '}
                                    />
                                    <Box sx={{ display: 'grid', gap: 0.75, justifyContent: 'end' }}>
                                        <Button
                                            onClick={() => composeFileInputRef.current?.click()}
                                            variant="outlined"
                                            sx={{ minHeight: 44, borderRadius: '2px', textTransform: 'none', fontWeight: 700, whiteSpace: 'nowrap' }}
                                        >
                                            {composeContent.trim() ? t('appStorePage.sources.compose.workspace.replaceUpload') : t('appStorePage.sources.compose.workspace.upload')}
                                        </Button>
                                    </Box>
                                    <Box sx={{ display: 'grid', gap: 0.75, justifyContent: 'end' }}>
                                        <Button
                                            onClick={() => void handleComposeInstall()}
                                            variant="contained"
                                            disabled={isSubmittingCompose}
                                            sx={{ minHeight: 44, borderRadius: '2px', textTransform: 'none', boxShadow: 'none', fontWeight: 800, whiteSpace: 'nowrap' }}
                                        >
                                            {isSubmittingCompose ? t('appStorePage.sources.compose.workspace.installing') : t('appStorePage.sources.compose.workspace.install')}
                                        </Button>
                                    </Box>
                                </Box>

                                <Box
                                    sx={{
                                        display: 'grid',
                                        gap: 1.5,
                                        gridTemplateColumns: { xs: '1fr', xl: 'minmax(0, 1.6fr) minmax(360px, 0.84fr)' },
                                        height: '100%',
                                        minHeight: 0,
                                        alignItems: 'stretch',
                                    }}
                                >
                                    <Box
                                        sx={{
                                            minHeight: 0,
                                            display: 'grid',
                                            gridTemplateRows: 'auto minmax(0, 1fr) auto',
                                            borderRadius: '2px',
                                            border: `1px solid ${composeFieldErrors.composeContent ? palette.danger : palette.border}`,
                                            backgroundColor: palette.panelBg,
                                            overflow: 'hidden',
                                        }}
                                    >
                                        <Box
                                            sx={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center',
                                                gap: 1,
                                                px: { xs: 1.25, md: 1.5 },
                                                py: 1,
                                                borderBottom: `1px solid ${palette.border}`,
                                                backgroundColor: palette.panelBg,
                                            }}
                                        >
                                            <Typography sx={{ fontSize: 16, fontWeight: 800, color: palette.text }}>
                                                {t('appStorePage.sources.compose.workspace.composeTitle')}
                                            </Typography>
                                            <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                                                <input
                                                    ref={composeFileInputRef}
                                                    type="file"
                                                    accept=".yml,.yaml,text/yaml,text/x-yaml,application/x-yaml"
                                                    hidden
                                                    onChange={(event) => {
                                                        void handleComposeFileSelected(event.target.files?.[0] ?? null)
                                                        event.target.value = ''
                                                    }}
                                                />
                                                <Button onClick={resetComposeToSample} variant="outlined" sx={{ minHeight: 36, borderRadius: '2px', textTransform: 'none', fontWeight: 700 }}>
                                                    {t('appStorePage.sources.compose.workspace.useSample')}
                                                </Button>
                                            </Box>
                                        </Box>

                                        <Box
                                            sx={{
                                                minHeight: 0,
                                                backgroundColor: '#f8fbff',
                                                '& .cm-editor': {
                                                    height: '100%',
                                                    fontSize: 13.5,
                                                },
                                                '& .cm-scroller': {
                                                    overflow: 'auto',
                                                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace',
                                                },
                                            }}
                                        >
                                            <CodeMirror
                                                value={composeContent}
                                                height="100%"
                                                extensions={[yamlLanguage()]}
                                                onChange={(value) => {
                                                    clearComposeFeedback()
                                                    setComposeFieldErrors((currentValue) => ({ ...currentValue, composeContent: undefined }))
                                                    setComposeContent(value)
                                                }}
                                                basicSetup={{
                                                    lineNumbers: true,
                                                    foldGutter: true,
                                                    highlightActiveLine: true,
                                                    highlightActiveLineGutter: true,
                                                }}
                                            />
                                        </Box>

                                        <Box sx={{ px: { xs: 1.25, md: 1.5 }, py: 0.85, borderTop: `1px solid ${palette.border}`, backgroundColor: palette.panelBg }}>
                                            <Typography sx={{ fontSize: 12.5, lineHeight: 1.6, color: composeFieldErrors.composeContent ? palette.danger : palette.subtleText }}>
                                                {composeFieldErrors.composeContent ?? t('appStorePage.sources.compose.workspace.composeHelper')}
                                            </Typography>
                                        </Box>
                                    </Box>

                                    <Box sx={{ minHeight: 0, display: 'grid', gap: 1.5, gridTemplateRows: 'minmax(0, 1fr) minmax(0, 1fr) auto' }}>
                                        <Box
                                            sx={{
                                                minHeight: 0,
                                                display: 'grid',
                                                gridTemplateRows: 'auto minmax(0, 1fr)',
                                                borderRadius: '2px',
                                                border: `1px solid ${palette.border}`,
                                                backgroundColor: palette.panelBg,
                                                overflow: 'hidden',
                                            }}
                                        >
                                            <Button
                                                onClick={() => setComposeEnvExpanded((currentValue) => !currentValue)}
                                                color="inherit"
                                                sx={{ width: '100%', justifyContent: 'space-between', alignItems: 'center', textTransform: 'none', px: 1.4, py: 1.05, borderRadius: 0 }}
                                            >
                                                <Typography sx={{ fontSize: 15, fontWeight: 800, color: palette.text }}>
                                                    {t('appStorePage.sources.compose.workspace.envTitle')}
                                                </Typography>
                                                <Typography sx={{ fontSize: 20, lineHeight: 1, fontWeight: 500, color: palette.subtleText }}>
                                                    {composeEnvExpanded ? '−' : '+'}
                                                </Typography>
                                            </Button>

                                            {composeEnvExpanded ? (
                                                <Box sx={{ minHeight: 0, display: 'grid', gridTemplateRows: 'auto minmax(0, 1fr) auto', gap: 1.25, px: { xs: 1.25, md: 1.5 }, pb: { xs: 1.25, md: 1.5 }, borderTop: `1px solid ${palette.border}` }}>
                                                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', pt: 1.25 }}>
                                                        <input
                                                            ref={composeEnvFileInputRef}
                                                            type="file"
                                                            accept=".env,text/plain"
                                                            hidden
                                                            onChange={(event) => {
                                                                void handleComposeEnvFileSelected(event.target.files?.[0] ?? null)
                                                                event.target.value = ''
                                                            }}
                                                        />
                                                        <Button onClick={addComposeEnvRow} variant="outlined" sx={{ borderRadius: '2px', textTransform: 'none', fontWeight: 700 }}>
                                                            {t('appStorePage.sources.compose.workspace.addEnv')}
                                                        </Button>
                                                        <Button onClick={() => composeEnvFileInputRef.current?.click()} variant="outlined" sx={{ borderRadius: '2px', textTransform: 'none', fontWeight: 700 }}>
                                                            {t('appStorePage.sources.compose.workspace.uploadEnv')}
                                                        </Button>
                                                    </Box>

                                                    <Box sx={{ minHeight: 0, overflowY: 'auto', pr: 0.25, display: 'grid', gap: 1 }}>
                                                        {composeEnvRows.map((row, index) => (
                                                            <Box
                                                                key={row.id}
                                                                sx={{
                                                                    display: 'grid',
                                                                    gap: 1,
                                                                    p: 1.2,
                                                                    borderRadius: '2px',
                                                                    border: `1px solid ${palette.border}`,
                                                                    backgroundColor: palette.panelBg,
                                                                    gridTemplateColumns: { xs: '1fr', xl: 'minmax(0, 0.92fr) minmax(0, 1.08fr) auto' },
                                                                    alignItems: 'start',
                                                                }}
                                                            >
                                                                <TextField fullWidth label={t('appStorePage.sources.compose.workspace.envKeyLabel')} value={row.key} onChange={(event) => updateComposeEnvRow(row.id, 'key', event.target.value)} />
                                                                <TextField fullWidth label={t('appStorePage.sources.compose.workspace.envValueLabel')} value={row.value} onChange={(event) => updateComposeEnvRow(row.id, 'value', event.target.value)} />
                                                                <Button
                                                                    onClick={() => removeComposeEnvRow(row.id)}
                                                                    variant="text"
                                                                    color="inherit"
                                                                    disabled={composeEnvRows.length === 1 && index === 0 && !row.key && !row.value}
                                                                    sx={{ minHeight: 40, alignSelf: { xs: 'flex-end', xl: 'center' }, textTransform: 'none', fontWeight: 700 }}
                                                                >
                                                                    {t('appStorePage.sources.compose.workspace.removeEnv')}
                                                                </Button>
                                                            </Box>
                                                        ))}
                                                    </Box>
                                                    {composeFieldErrors.env ? <Typography sx={{ fontSize: 13, lineHeight: 1.65, color: palette.danger }}>{composeFieldErrors.env}</Typography> : null}
                                                </Box>
                                            ) : null}
                                        </Box>

                                        <Box
                                            sx={{
                                                minHeight: 0,
                                                display: 'grid',
                                                gridTemplateRows: 'auto minmax(0, 1fr)',
                                                borderRadius: '2px',
                                                border: `1px solid ${palette.border}`,
                                                backgroundColor: palette.panelBg,
                                                overflow: 'hidden',
                                            }}
                                        >
                                            <Button
                                                onClick={() => setComposeMountExpanded((currentValue) => !currentValue)}
                                                color="inherit"
                                                sx={{ width: '100%', justifyContent: 'space-between', alignItems: 'center', textTransform: 'none', px: 1.4, py: 1.05, borderRadius: 0 }}
                                            >
                                                <Typography sx={{ fontSize: 15, fontWeight: 800, color: palette.text }}>
                                                    {t('appStorePage.sources.compose.workspace.mountTitle')}
                                                </Typography>
                                                <Typography sx={{ fontSize: 20, lineHeight: 1, fontWeight: 500, color: palette.subtleText }}>
                                                    {composeMountExpanded ? '−' : '+'}
                                                </Typography>
                                            </Button>

                                            {composeMountExpanded ? (
                                                <Box sx={{ minHeight: 0, display: 'grid', gridTemplateRows: 'auto minmax(0, 1fr)', gap: 1.25, px: { xs: 1.25, md: 1.5 }, pb: { xs: 1.25, md: 1.5 }, borderTop: `1px solid ${palette.border}` }}>
                                                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', pt: 1.25 }}>
                                                        <input
                                                            ref={composeMountFileInputRef}
                                                            type="file"
                                                            hidden
                                                            multiple
                                                            onChange={(event) => {
                                                                void handleComposeMountFilesSelected(event.target.files)
                                                                event.target.value = ''
                                                            }}
                                                        />
                                                        <Button onClick={addComposeMountRow} variant="outlined" sx={{ borderRadius: '2px', textTransform: 'none', fontWeight: 700 }}>
                                                            {t('appStorePage.sources.compose.workspace.addMount')}
                                                        </Button>
                                                        <Button onClick={() => composeMountFileInputRef.current?.click()} variant="outlined" sx={{ borderRadius: '2px', textTransform: 'none', fontWeight: 700 }}>
                                                            {t('appStorePage.sources.compose.workspace.uploadMountFiles')}
                                                        </Button>
                                                    </Box>

                                                    {selectedComposeMount ? (
                                                        <Box sx={{ minHeight: 0, display: 'grid', gap: 1.25, gridTemplateColumns: { xs: '1fr', lg: 'minmax(160px, 200px) minmax(0, 1fr)' } }}>
                                                            <Box sx={{ minHeight: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'stretch', gap: 0.75, pr: 0.2 }}>
                                                                {composeMountRows.map((row, index) => {
                                                                    const label = row.path || `${t('appStorePage.sources.compose.workspace.mountUntitled')} ${index + 1}`
                                                                    const active = row.id === selectedComposeMount.id
                                                                    return (
                                                                        <Button
                                                                            key={row.id}
                                                                            onClick={() => setSelectedComposeMountId(row.id)}
                                                                            variant="text"
                                                                            sx={{ justifyContent: 'flex-start', textAlign: 'left', textTransform: 'none', p: 1.05, minHeight: 44, borderRadius: '2px', border: `1px solid ${active ? palette.accent : palette.border}`, backgroundColor: active ? palette.accentSoft : palette.panelBg, color: palette.text, flex: '0 0 auto' }}
                                                                        >
                                                                            <Typography sx={{ fontSize: 13.5, fontWeight: 700, color: palette.text, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                                                {label}
                                                                            </Typography>
                                                                        </Button>
                                                                    )
                                                                })}
                                                            </Box>

                                                            <Box sx={{ minHeight: 0, display: 'grid', gap: 1.1, gridTemplateRows: 'auto minmax(220px, 1fr)' }}>
                                                                <Box sx={{ display: 'grid', gap: 1, p: 1.15, borderRadius: '2px', border: `1px solid ${palette.border}`, backgroundColor: palette.panelBg }}>
                                                                    <TextField
                                                                        fullWidth
                                                                        label={t('appStorePage.sources.compose.workspace.mountPathLabel')}
                                                                        placeholder={t('appStorePage.sources.compose.workspace.mountPathPlaceholder')}
                                                                        value={selectedComposeMount.path}
                                                                        onChange={(event) => updateComposeMountRow(selectedComposeMount.id, 'path', event.target.value)}
                                                                        error={Boolean(composeFieldErrors.mountPath)}
                                                                        helperText={composeFieldErrors.mountPath ?? t('appStorePage.sources.compose.workspace.mountPathHelper')}
                                                                    />
                                                                    <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                                                                        <Button onClick={() => removeComposeMountRow(selectedComposeMount.id)} variant="text" color="inherit" disabled={composeMountRows.length === 1 && !selectedComposeMount.path && !selectedComposeMount.content} sx={{ textTransform: 'none', fontWeight: 700 }}>
                                                                            {t('appStorePage.sources.compose.workspace.removeMount')}
                                                                        </Button>
                                                                    </Box>
                                                                </Box>

                                                                <Box
                                                                    sx={{
                                                                        minHeight: 0,
                                                                        borderRadius: '2px',
                                                                        overflow: 'hidden',
                                                                        border: `1px solid ${palette.borderStrong}`,
                                                                        backgroundColor: '#f8fbff',
                                                                        '& .cm-editor': { height: '100%', fontSize: 13.5 },
                                                                        '& .cm-scroller': {
                                                                            overflow: 'auto',
                                                                            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace',
                                                                        },
                                                                    }}
                                                                >
                                                                    <CodeMirror
                                                                        value={selectedComposeMount.content}
                                                                        height="100%"
                                                                        onChange={(value) => updateComposeMountRow(selectedComposeMount.id, 'content', value)}
                                                                        basicSetup={{ lineNumbers: true, highlightActiveLine: true, highlightActiveLineGutter: true }}
                                                                    />
                                                                </Box>
                                                            </Box>
                                                        </Box>
                                                    ) : null}
                                                </Box>
                                            ) : null}
                                        </Box>

                                        {installError ? <Typography sx={{ px: 0.5, fontSize: 13, lineHeight: 1.65, color: palette.danger }}>{installError}</Typography> : null}
                                    </Box>
                                </Box>
                            </Box>
                        </Box>
                    ) : null}

                    {selectedInstallSource === 'marketplace' ? (
                        <Box sx={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', overflowX: 'hidden', pr: 0.5 }}>
                            <Stack spacing={1.5} sx={{ pb: 0.5 }}>
                                <FavoriteSectionHeading title={resultsSectionTitle} />

                                {effectiveIsLoading ? (
                                    <SurfaceStateCard detail={t('appStorePage.states.loading')} loading darkMode={isDarkMode} />
                                ) : null}

                                {!effectiveIsLoading && error ? (
                                    <SurfaceNoticeAlert
                                        detail={t('appStorePage.states.errorDetail', { statusCode: error.statusCode ?? 'unknown' })}
                                        action={
                                            <Button color="inherit" size="small" onClick={() => void refetch()}>
                                                {t('appStorePage.states.retry')}
                                            </Button>
                                        }
                                        severity="warning"
                                        title={t('appStorePage.states.errorTitle')}
                                        darkMode={isDarkMode}
                                    />
                                ) : null}

                                {!effectiveIsLoading && !error && filteredApps.length === 0 ? (
                                    <SurfaceStateCard detail={t('appStorePage.states.emptyDetail')} title={t('appStorePage.states.emptyTitle')} darkMode={isDarkMode} />
                                ) : null}

                                {!effectiveIsLoading && !error && filteredApps.length > 0 ? (
                                    <Stack spacing={1.5}>
                                        <Box
                                            sx={{
                                                display: 'grid',
                                                gap: 2.25,
                                                gridTemplateColumns: {
                                                    xs: '1fr',
                                                    md: 'repeat(2, minmax(0, 1fr))',
                                                    xl: 'repeat(4, minmax(0, 1fr))',
                                                },
                                            }}
                                        >
                                            {filteredApps.map((app) => {
                                                const isDevApp = app.production === false
                                                return (
                                                    <UnifiedAppCard
                                                        key={app.key ?? app.trademark}
                                                        darkMode={isDarkMode}
                                                        onClick={() => {
                                                            openAppDetail(app, 'catalog')
                                                        }}
                                                        title={app.trademark ?? app.key ?? t('appStorePage.card.summaryFallback')}
                                                        description={app.summary || app.overview || t('appStorePage.card.summaryFallback')}
                                                        media={<AppLogo app={app} locale={resolvedLocale} />}
                                                        actions={
                                                            isDevApp ? (
                                                                <Chip
                                                                    label="TODO"
                                                                    size="small"
                                                                    sx={{
                                                                        height: 22,
                                                                        fontSize: 11,
                                                                        fontWeight: 600,
                                                                        borderRadius: '2px',
                                                                        backgroundColor: '#f59e0b',
                                                                        color: '#fff',
                                                                        '& .MuiChip-label': { px: 0.75 },
                                                                    }}
                                                                />
                                                            ) : undefined
                                                        }
                                                    />
                                                )
                                            })}
                                        </Box>
                                    </Stack>
                                ) : null}
                            </Stack>
                        </Box>
                    ) : null}
                </Box>

                <AppStoreScopedOverlay open={isFavoritesOpen} onClose={() => setIsFavoritesOpen(false)} scopeRect={contentViewportRect} maxWidth={832} preferredHeight={720} darkMode={isDarkMode}>
                    <DialogTitle sx={{ px: { xs: 2, md: 2.5 }, py: { xs: 1.5, md: 1.75 }, flexShrink: 0, backgroundColor: palette.dialogBg }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5 }}>
                            <Typography sx={{ fontSize: 18, fontWeight: 600, lineHeight: 1.2, color: palette.text }}>
                                {t('appStorePage.actions.favoriteList', { count: favoriteApps.length })}
                            </Typography>
                            <IconButton
                                color="inherit"
                                onClick={() => {
                                    setIsFavoritesOpen(false)
                                }}
                                size="small"
                                sx={{
                                    width: 38,
                                    height: 38,
                                    color: palette.subtleText,
                                    borderRadius: '999px',
                                    backgroundColor: 'transparent',
                                    '&:hover': {
                                        backgroundColor: 'transparent',
                                        color: palette.text,
                                        opacity: 0.84,
                                    },
                                }}
                                title={t('appStorePage.actions.close')}
                            >
                                <CloseIcon />
                            </IconButton>
                        </Box>
                    </DialogTitle>
                    <DialogContent dividers sx={{ flex: 1, minHeight: 0, overflowY: 'auto', px: { xs: 2, md: 2.5 }, py: 2, backgroundColor: palette.dialogBg, '&.MuiDialogContent-dividers': { borderTopColor: palette.border, borderBottomColor: palette.border } }}>
                        {favoriteApps.length === 0 ? (
                            <SurfaceStateCard title={t('appStorePage.results.favoriteEmptyTitle')} detail={t('appStorePage.results.favoriteEmptyDetail')} darkMode={isDarkMode} />
                        ) : (
                            <Box
                                sx={{
                                    display: 'grid',
                                    gap: 2,
                                    gridTemplateColumns: {
                                        xs: '1fr',
                                        sm: 'repeat(2, minmax(0, 1fr))',
                                        md: 'repeat(3, minmax(0, 1fr))',
                                    },
                                }}
                            >
                                {favoriteApps.map((app) => (
                                    <Card
                                        key={`favorites-dialog-${app.key ?? app.trademark}`}
                                        elevation={0}
                                        onClick={() => {
                                            setIsFavoritesOpen(false)
                                            openAppDetail(app, 'favorites')
                                        }}
                                        sx={{
                                            border: `1px solid ${palette.border}`,
                                            borderRadius: '2px',
                                            background: isDarkMode ? 'linear-gradient(180deg, #162033 0%, #111827 100%)' : 'linear-gradient(180deg, #fffdf5 0%, #ffffff 100%)',
                                            boxShadow: isDarkMode ? '0 12px 28px rgba(2, 6, 23, 0.28)' : '0 2px 5px rgba(0, 0, 0, 0.08)',
                                            cursor: 'pointer',
                                            transition: 'background-color 120ms ease, box-shadow 120ms ease',
                                            '&:hover': {
                                                backgroundColor: isDarkMode ? palette.panelHover : 'rgb(245, 241, 224)',
                                                boxShadow: isDarkMode ? '0 12px 28px rgba(2, 6, 23, 0.32)' : '0 2px 5px rgba(0, 0, 0, 0.1)',
                                            },
                                        }}
                                    >
                                        <CardContent sx={{ p: '10px !important' }}>
                                            <Box sx={{ display: 'grid', gridTemplateColumns: '88px minmax(0, 1fr)', gap: 0, alignItems: 'center' }}>
                                                <Box sx={{ width: 88, minWidth: 88, px: '8px', boxSizing: 'border-box' }}>
                                                    <Box sx={{ width: 72, height: 72 }}>
                                                        <AppLogo app={app} locale={resolvedLocale} />
                                                    </Box>
                                                </Box>
                                                <Box sx={{ minWidth: 0, textAlign: 'left' }}>
                                                    <Typography sx={{ fontSize: 16, fontWeight: 600, lineHeight: 1.25, mb: 0.5, color: palette.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                        {app.trademark ?? app.key}
                                                    </Typography>
                                                    <Typography sx={{ fontSize: 13.5, lineHeight: 1.45, height: 40, overflow: 'hidden', textOverflow: 'ellipsis', color: palette.subtleText, fontWeight: 400 }}>
                                                        {app.summary || app.overview || t('appStorePage.card.summaryFallback')}
                                                    </Typography>
                                                </Box>
                                            </Box>
                                        </CardContent>
                                    </Card>
                                ))}
                            </Box>
                        )}
                    </DialogContent>
                    <DialogActions sx={{ px: 2.5, py: 1.5, borderTop: `1px solid ${palette.border}`, backgroundColor: palette.dialogBg }}>
                        <Button
                            color="inherit"
                            onClick={() => setIsFavoritesOpen(false)}
                            variant="contained"
                            sx={{
                                minWidth: 68,
                                backgroundColor: palette.actionBg,
                                color: palette.subtleText,
                                borderRadius: 0,
                                boxShadow: 'none',
                                '&:hover': { backgroundColor: palette.actionHover, boxShadow: 'none', color: palette.text },
                            }}
                        >
                            {t('appStorePage.actions.close')}
                        </Button>
                    </DialogActions>
                </AppStoreScopedOverlay>

                <AppStoreScopedOverlay
                    open={Boolean(selectedApp)}
                    onClose={handleCloseModal}
                    scopeRect={contentViewportRect}
                    maxWidth={840}
                    verticalPlacement="top"
                    darkMode={isDarkMode}
                >
                    {selectedApp ? (
                        <>
                            <DialogTitle sx={{ px: { xs: 2, md: 2.5 }, py: { xs: 1.75, md: 2 }, flexShrink: 0, backgroundColor: palette.dialogBg }}>
                                <Box sx={{ display: 'grid', gridTemplateColumns: '72px minmax(0, 1fr) auto', gap: 1.5, alignItems: 'center' }}>
                                    <Box sx={{ width: 72, height: 72, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                        <AppLogo app={selectedApp} locale={resolvedLocale} />
                                    </Box>
                                    <Box sx={{ minWidth: 0 }}>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                                            <Typography sx={{ fontSize: { xs: 18, md: 20 }, fontWeight: 600, lineHeight: 1.2, color: palette.text }}>{selectedApp.trademark ?? selectedApp.key}</Typography>
                                            <Tooltip title="Documentation">
                                                <IconButton
                                                    component="a"
                                                    href={getDocumentationUrl(selectedApp, i18n.resolvedLanguage ?? i18n.language ?? 'en')}
                                                    rel="noreferrer"
                                                    size="small"
                                                    target="_blank"
                                                    sx={{ p: 0.5, color: palette.subtleText, border: `1px solid ${palette.border}`, borderRadius: '4px', '& svg': { fontSize: 18 } }}
                                                >
                                                    <DocumentationIcon />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title="GitHub">
                                                <IconButton
                                                    component="a"
                                                    href={getGitHubUrl(selectedApp)}
                                                    rel="noreferrer"
                                                    size="small"
                                                    target="_blank"
                                                    sx={{ p: 0.5, color: palette.text, border: `1px solid ${palette.border}`, borderRadius: '4px', '& svg': { fontSize: 18 } }}
                                                >
                                                    <GitHubMarkIcon />
                                                </IconButton>
                                            </Tooltip>
                                        </Box>
                                        <Typography sx={{ mt: 0.5, fontSize: 14, fontWeight: 400, color: palette.subtleText }}>
                                            {t('appStorePage.detail.versionLine', { version: getAppStoreVersionSummary(selectedApp) || '-' })}
                                        </Typography>
                                        <Typography sx={{ mt: 0.15, fontSize: 14, fontWeight: 400, color: palette.subtleText }}>
                                            {t('appStorePage.detail.requirementLine', {
                                                cpu: formatRequirement(selectedApp.vcpu),
                                                memory: formatRequirement(selectedApp.memory),
                                                storage: formatRequirement(selectedApp.storage),
                                            })}
                                        </Typography>
                                        <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 0.5, mt: 0.15, color: 'primary.main', fontSize: 14 }}>
                                            <Typography component="span" sx={{ color: palette.subtleText, fontSize: 14, fontWeight: 400 }}>
                                                {t('appStorePage.detail.categoriesLabel')}
                                            </Typography>
                                            {(selectedApp.catalogCollection?.items ?? []).map((mainCategory, index) => (
                                                <Box key={`${mainCategory.key}-${index}`} sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                                                    <Link
                                                        component="button"
                                                        onClick={() => handleCatalogClick(mainCategory, mainCategory.catalogCollection?.items?.[0])}
                                                        sx={{
                                                            color: palette.accent,
                                                            fontSize: 14,
                                                            fontWeight: 400,
                                                            textDecoration: 'none',
                                                            border: 0,
                                                            background: 'transparent',
                                                            cursor: 'pointer',
                                                            p: 0,
                                                        }}
                                                    >
                                                        {mainCategory.title}
                                                    </Link>
                                                    {index !== (selectedApp.catalogCollection?.items?.length ?? 0) - 1 ? <Typography color="text.secondary">|</Typography> : null}
                                                </Box>
                                            ))}
                                        </Box>
                                    </Box>
                                    <IconButton
                                        onClick={handleCloseModal}
                                        size="small"
                                        aria-label={t('appStorePage.actions.close')}
                                        title={t('appStorePage.actions.close')}
                                        sx={{
                                            width: 40,
                                            height: 40,
                                            justifySelf: 'end',
                                            alignSelf: 'center',
                                            mr: -0.25,
                                            color: palette.subtleText,
                                            borderRadius: '999px',
                                            backgroundColor: 'transparent',
                                            transition: 'color 120ms ease, opacity 120ms ease',
                                            '&:hover': {
                                                color: palette.text,
                                                backgroundColor: 'transparent',
                                                opacity: 0.84,
                                            },
                                        }}
                                    >
                                        <CloseIcon />
                                    </IconButton>
                                </Box>
                            </DialogTitle>
                            <DialogContent dividers sx={{ px: 0, py: 0, flex: 1, overflowY: 'auto', backgroundColor: palette.dialogBg, '&.MuiDialogContent-dividers': { borderTopColor: palette.border, borderBottomColor: palette.border } }}>
                                {!isInstallMode ? (
                                    <>
                                        <AppScreenshot
                                            alt={selectedApp.trademark ?? selectedApp.key ?? t('appStorePage.card.imageFallbackAlt')}
                                            app={selectedApp}
                                            locale={i18n.resolvedLanguage ?? i18n.language ?? 'en'}
                                        />

                                        <Box sx={{ px: { xs: 2, md: 2.5 }, pt: 0.5, pb: 2.25 }}>
                                            <Typography sx={{ fontSize: 16, fontWeight: 700, mb: 0.9, color: palette.text }}>{t('appStorePage.detail.overviewTitle')}</Typography>
                                            <Typography sx={{ mb: 2.5, lineHeight: 1.75, fontSize: 14, color: palette.subtleText, fontWeight: 400 }}>
                                                {selectedApp.overview || selectedApp.summary || t('appStorePage.card.summaryFallback')}
                                            </Typography>

                                            <Typography sx={{ fontSize: 16, fontWeight: 700, mb: 0.9, color: palette.text }}>{t('appStorePage.detail.descriptionTitle')}</Typography>
                                            <Typography sx={{ lineHeight: 1.75, whiteSpace: 'pre-wrap', fontSize: 14, color: palette.subtleText, fontWeight: 400 }}>
                                                {selectedApp.description || selectedApp.overview || selectedApp.summary || t('appStorePage.card.summaryFallback')}
                                            </Typography>
                                        </Box>
                                    </>
                                ) : (
                                    <Box sx={{ display: 'grid', gap: 1.25, px: { xs: 2, md: 2.5 }, py: 2.25 }}>
                                        <Box>
                                            <Typography sx={{ mb: 0.75, fontSize: 14, fontWeight: 400, color: palette.subtleText }}>{t('appStorePage.install.appIdLabel')}</Typography>
                                            <Box
                                                sx={{
                                                    display: 'grid',
                                                    gridTemplateColumns:
                                                        selectedApp.is_web_app && wildcardDomain
                                                            ? 'minmax(0, 1fr) 180px 74px'
                                                            : '1fr',
                                                    gap: 0,
                                                    alignItems: 'center',
                                                }}
                                            >
                                                <TextField
                                                    autoFocus
                                                    error={Boolean(installFieldErrors.appId)}
                                                    fullWidth
                                                    inputRef={appIdInputRef}
                                                    placeholder={t('appStorePage.install.appIdPlaceholder')}
                                                    size="small"
                                                    value={installName}
                                                    onChange={(event) => {
                                                        setInstallFieldErrors((currentValue) => ({ ...currentValue, appId: undefined }))
                                                        setInstallError(null)
                                                        setInstallName(normalizeInstallName(event.target.value))
                                                    }}
                                                    sx={{
                                                        ...installDialogFieldSx,
                                                        '& .MuiOutlinedInput-root': {
                                                            ...installDialogFieldSx['& .MuiOutlinedInput-root'],
                                                            borderRadius: selectedApp.is_web_app && wildcardDomain ? '4px 0 0 4px' : '4px',
                                                        },
                                                    }}
                                                />
                                                {selectedApp.is_web_app && wildcardDomain ? (
                                                    <>
                                                        <Box
                                                            sx={{
                                                                display: 'flex',
                                                                alignItems: 'center',
                                                                px: 1.25,
                                                                border: `1px solid ${palette.border}`,
                                                                borderLeft: 0,
                                                                backgroundColor: isDomainEnabled ? palette.panelBg : palette.panelSoft,
                                                                color: isDomainEnabled ? palette.subtleText : palette.placeholderText,
                                                                fontSize: 13.5,
                                                                height: 38,
                                                                boxSizing: 'border-box',
                                                            }}
                                                        >
                                                            <Box
                                                                component="span"
                                                                sx={{
                                                                    display: 'inline-block',
                                                                    textDecoration: isDomainEnabled ? 'none' : 'line-through',
                                                                    textDecorationThickness: isDomainEnabled ? undefined : '1px',
                                                                    textDecorationColor: isDomainEnabled ? undefined : palette.placeholderText,
                                                                }}
                                                            >
                                                                {domainSuffix}
                                                            </Box>
                                                        </Box>
                                                        <Button
                                                            onClick={() => setIsDomainEnabled((currentValue) => !currentValue)}
                                                            sx={{
                                                                minWidth: 82,
                                                                border: `1px solid ${isDomainEnabled ? palette.borderStrong : palette.accent}`,
                                                                background: isDomainEnabled ? palette.actionBg : palette.accentSoft,
                                                                color: isDomainEnabled ? palette.subtleText : palette.accent,
                                                                boxShadow: 'none',
                                                                borderRadius: '0 4px 4px 0',
                                                                '&:hover': {
                                                                    background: isDomainEnabled ? palette.actionHover : palette.accentSoft,
                                                                    color: isDomainEnabled ? palette.text : palette.accent,
                                                                    boxShadow: 'none',
                                                                },
                                                            }}
                                                            variant="contained"
                                                        >
                                                            {isDomainEnabled ? t('appStorePage.install.disableDomain') : t('appStorePage.install.enableDomain')}
                                                        </Button>
                                                    </>
                                                ) : null}
                                            </Box>
                                        </Box>

                                        {selectedApp.is_web_app ? (
                                            <Box sx={{ mt: 1 }}>
                                                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: customDomains.length > 0 ? 0.75 : 0 }}>
                                                    <Typography sx={{ fontSize: 14, fontWeight: 400, color: palette.subtleText }}>{t('appStorePage.install.customDomainLabel')}</Typography>
                                                    {customDomains.length < MAX_CUSTOM_DOMAINS ? (
                                                        <Button
                                                            onClick={() => {
                                                                setCustomDomainErrorIndex(null)
                                                                setInstallFieldErrors((currentValue) => ({ ...currentValue, customDomain: undefined }))
                                                                setInstallError(null)
                                                                setCustomDomains((currentValue) => [...currentValue, ''])
                                                            }}
                                                            variant="text"
                                                            size="small"
                                                            sx={{
                                                                fontSize: 13,
                                                                fontWeight: 500,
                                                                color: palette.accent,
                                                                textTransform: 'none',
                                                                px: 1,
                                                                py: 0.25,
                                                                minWidth: 0,
                                                                '&:hover': { backgroundColor: palette.accentSoft },
                                                            }}
                                                        >
                                                            + {t('appStorePage.install.addCustomDomain')}
                                                        </Button>
                                                    ) : null}
                                                </Box>
                                                {customDomains.length > 0 ? (
                                                    <Box sx={{ display: 'grid', gap: 1 }}>
                                                        {customDomains.map((domain, index) => (
                                                            <Box key={index} sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                                                                <TextField
                                                                    error={customDomainErrorIndex === index}
                                                                    fullWidth
                                                                    inputRef={(element) => {
                                                                        customDomainInputRefs.current[index] = element
                                                                    }}
                                                                    placeholder={t('appStorePage.install.customDomainPlaceholder')}
                                                                    size="small"
                                                                    value={domain}
                                                                    onChange={(event) => {
                                                                        setCustomDomainErrorIndex(null)
                                                                        setInstallFieldErrors((currentValue) => ({ ...currentValue, customDomain: undefined }))
                                                                        setInstallError(null)
                                                                        setCustomDomains((currentValue) => {
                                                                            const next = [...currentValue]
                                                                            next[index] = event.target.value
                                                                            return next
                                                                        })
                                                                    }}
                                                                    sx={installDialogFieldSx}
                                                                />
                                                                <IconButton
                                                                    onClick={() => {
                                                                        setCustomDomainErrorIndex(null)
                                                                        setInstallFieldErrors((currentValue) => ({ ...currentValue, customDomain: undefined }))
                                                                        setInstallError(null)
                                                                        setCustomDomains((currentValue) => currentValue.filter((_, i) => i !== index))
                                                                    }}
                                                                    size="small"
                                                                    sx={{
                                                                        mt: 0.5,
                                                                        width: 32,
                                                                        height: 32,
                                                                        color: palette.subtleText,
                                                                        borderRadius: '4px',
                                                                        '&:hover': { color: palette.danger, backgroundColor: palette.panelHover },
                                                                    }}
                                                                    title={t('appStorePage.install.removeCustomDomain')}
                                                                >
                                                                    <RemoveIcon />
                                                                </IconButton>
                                                            </Box>
                                                        ))}
                                                    </Box>
                                                ) : null}
                                            </Box>
                                        ) : null}

                                        <Box>
                                            <Typography sx={{ mb: 0.75, fontSize: 14, fontWeight: 400, color: palette.subtleText }}>{t('appStorePage.install.versionLabel')}</Typography>
                                            {availableVersions.length > 1 ? (
                                                <TextField
                                                    select
                                                    fullWidth
                                                    size="small"
                                                    value={selectedVersion}
                                                    onChange={(event) => {
                                                        setInstallError(null)
                                                        setSelectedVersion(event.target.value)
                                                    }}
                                                    sx={{
                                                        ...installDialogFieldSx,
                                                        '& .MuiSelect-select': {
                                                            ...appStoreControlTextSx,
                                                            color: palette.text,
                                                        },
                                                    }}
                                                    slotProps={{
                                                        select: {
                                                            MenuProps: installDialogSelectMenuProps,
                                                        },
                                                    }}
                                                >
                                                    {availableVersions.map((version) => (
                                                        <MenuItem key={version} value={version}>
                                                            {version}
                                                        </MenuItem>
                                                    ))}
                                                </TextField>
                                            ) : (
                                                <TextField
                                                    fullWidth
                                                    size="small"
                                                    value={availableVersions[0] ?? selectedVersion}
                                                    slotProps={{
                                                        input: {
                                                            readOnly: true,
                                                        },
                                                    }}
                                                    sx={{
                                                        ...installDialogFieldSx,
                                                        '& .MuiOutlinedInput-root': {
                                                            ...installDialogFieldSx['& .MuiOutlinedInput-root'],
                                                            backgroundColor: palette.panelSoft,
                                                        },
                                                        '& .MuiInputBase-input': {
                                                            ...appStoreControlTextSx,
                                                            color: palette.text,
                                                            WebkitTextFillColor: palette.text,
                                                        },
                                                    }}
                                                />
                                            )}
                                        </Box>

                                        {Object.entries(effectiveInstallSettings).map(([key, value]) => (
                                            <Box key={key}>
                                                {(() => {

                                                    return (
                                                        <>
                                                            <Typography sx={{ mb: 0.75, fontSize: 14, fontWeight: 400, color: palette.subtleText }}>{getInstallSettingLabel(key, t, i18n.resolvedLanguage ?? i18n.language ?? 'en')}</Typography>
                                                            <TextField
                                                                error={Boolean(installFieldErrors.settings?.[key])}
                                                                fullWidth
                                                                inputRef={(element) => {
                                                                    installSettingInputRefs.current[key] = element
                                                                }}
                                                                size="small"
                                                                value={value}
                                                                onChange={(event) => {
                                                                    setInstallFieldErrors((currentValue) => ({
                                                                        ...currentValue,
                                                                        settings: currentValue.settings ? { ...currentValue.settings, [key]: undefined } : currentValue.settings,
                                                                    }))
                                                                    setInstallError(null)
                                                                    setInstallSettings((currentValue) => ({
                                                                        ...currentValue,
                                                                        [key]: event.target.value,
                                                                    }))
                                                                }}
                                                                slotProps={{
                                                                    htmlInput: key.toLowerCase().includes('port')
                                                                        ? {
                                                                            inputMode: 'numeric',
                                                                            pattern: '[0-9]*',
                                                                        }
                                                                        : undefined,
                                                                }}
                                                                sx={{
                                                                    ...installDialogFieldSx,
                                                                    '& .MuiInputBase-input': {
                                                                        ...appStoreControlTextSx,
                                                                        color: palette.text,
                                                                        WebkitTextFillColor: palette.text,
                                                                    },
                                                                }}
                                                            />
                                                        </>
                                                    )
                                                })()}
                                            </Box>
                                        ))}

                                    </Box>
                                )}
                            </DialogContent>
                            <DialogActions sx={{ px: 2.5, py: 2, flexShrink: 0, borderTop: `1px solid ${palette.border}`, backgroundColor: palette.dialogBg }}>
                                <Button
                                    color="inherit"
                                    onClick={handleCloseModal}
                                    variant="contained"
                                    sx={{
                                        minWidth: 68,
                                        backgroundColor: palette.actionBg,
                                        color: palette.subtleText,
                                        borderRadius: 0,
                                        boxShadow: 'none',
                                        '&:hover': { backgroundColor: palette.actionHover, boxShadow: 'none', color: palette.text },
                                    }}
                                >
                                    {t('appStorePage.actions.close')}
                                </Button>
                                <Button
                                    onClick={() => void handleToggleFavorite(selectedApp.key, { closeDetail: true })}
                                    variant="contained"
                                    color="inherit"
                                    aria-label={favoriteSet.has((selectedApp.key ?? '').toLowerCase()) ? t('appStorePage.actions.unfavorite') : t('appStorePage.actions.favorite')}
                                    sx={{
                                        minWidth: 68,
                                        backgroundColor: palette.actionBg,
                                        color: palette.text,
                                        borderRadius: 0,
                                        border: `1px solid ${palette.border}`,
                                        boxShadow: 'none',
                                        '&:hover': { backgroundColor: palette.actionHover, boxShadow: 'none' },
                                    }}
                                >
                                    {favoriteSet.has((selectedApp.key ?? '').toLowerCase()) ? t('appStorePage.actions.unfavorite') : t('appStorePage.actions.favorite')}
                                </Button>
                                {!isInstallMode ? (
                                    <Button
                                        onClick={() => {
                                            setIsInstallMode(true)
                                        }}
                                        variant="contained"
                                        sx={{ minWidth: 68, borderRadius: 0, boxShadow: 'none' }}
                                    >
                                        {t('appStorePage.actions.install')}
                                    </Button>
                                ) : (
                                    <Button disabled={isSubmittingInstall} onClick={() => void handleInstallSubmit()} variant="contained" sx={{ minWidth: 68, borderRadius: 0, boxShadow: 'none' }}>
                                        {isSubmittingInstall ? t('appStorePage.install.submitting') : t('appStorePage.actions.install')}
                                    </Button>
                                )}
                            </DialogActions>
                        </>
                    ) : null}
                </AppStoreScopedOverlay>

                <AppStoreScopedOverlay
                    open={refreshConfirmOpen}
                    scopeRect={contentViewportRect}
                    onClose={() => setRefreshConfirmOpen(false)}
                    maxWidth={440}
                    verticalPlacement="top"
                    darkMode={isDarkMode}
                >
                    <DialogTitle sx={{ px: { xs: 2, md: 2.5 }, py: { xs: 1.5, md: 1.75 }, flexShrink: 0, backgroundColor: palette.dialogBg }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5 }}>
                            <Typography sx={{ fontSize: 18, fontWeight: 600, lineHeight: 1.2, color: palette.text }}>
                                {t('appStorePage.actions.refreshConfirmTitle')}
                            </Typography>
                            <IconButton
                                color="inherit"
                                onClick={() => {
                                    setRefreshConfirmOpen(false)
                                }}
                                size="small"
                                sx={{
                                    width: 38,
                                    height: 38,
                                    color: palette.subtleText,
                                    borderRadius: '999px',
                                    backgroundColor: 'transparent',
                                    '&:hover': {
                                        backgroundColor: 'transparent',
                                        color: palette.text,
                                        opacity: 0.84,
                                    },
                                }}
                                title={t('appStorePage.actions.close')}
                            >
                                <CloseIcon />
                            </IconButton>
                        </Box>
                    </DialogTitle>
                    <DialogContent
                        dividers
                        sx={{
                            px: { xs: 2, md: 2.5 },
                            py: 2,
                            backgroundColor: palette.dialogBg,
                            '&.MuiDialogContent-dividers': {
                                borderTopColor: palette.border,
                                borderBottomColor: palette.border,
                            },
                        }}
                    >
                        <Box sx={{ display: 'grid', gap: 1.25 }}>
                            <Typography sx={{ fontSize: 14, color: palette.subtleText, lineHeight: 1.7 }}>
                                {t('appStorePage.actions.refreshConfirmMessage')}
                            </Typography>
                            {formattedFullSyncAt ? (
                                <Typography sx={{ fontSize: 13, color: palette.text, lineHeight: 1.6, fontWeight: 500 }}>
                                    {t('appStorePage.actions.lastSyncAt', { value: formattedFullSyncAt })}
                                </Typography>
                            ) : (
                                <Typography sx={{ fontSize: 13, color: palette.subtleText, lineHeight: 1.6 }}>
                                    {t('appStorePage.actions.syncNever')}
                                </Typography>
                            )}
                        </Box>
                    </DialogContent>
                    <DialogActions sx={{ px: 2.5, py: 1.5, borderTop: `1px solid ${palette.border}`, backgroundColor: palette.dialogBg }}>
                        <Button
                            color="inherit"
                            onClick={() => setRefreshConfirmOpen(false)}
                            variant="contained"
                            sx={{
                                minWidth: 68,
                                backgroundColor: palette.actionBg,
                                color: palette.subtleText,
                                borderRadius: 0,
                                boxShadow: 'none',
                                '&:hover': { backgroundColor: palette.actionHover, boxShadow: 'none', color: palette.text },
                            }}
                        >
                            {t('appStorePage.actions.cancel')}
                        </Button>
                        <Button
                            variant="contained"
                            onClick={() => void executeRefreshStore()}
                            sx={{ minWidth: 92, borderRadius: 0, textTransform: 'none', boxShadow: 'none' }}
                        >
                            {t('appStorePage.actions.confirmRefresh')}
                        </Button>
                    </DialogActions>
                </AppStoreScopedOverlay>
            </Box>

            <SurfaceFeedbackToast
                message={installToastMessage}
                onClose={() => {
                    setInstallFeedback(null)
                    setInstallError(null)
                }}
                open={installToastActive}
                scope="content"
                scopeRect={contentViewportRect}
                severity={installToastSeverity}
                darkMode={isDarkMode}
            />

            <SurfaceFeedbackToast
                message={refreshToastMessage}
                onClose={() => setRefreshFeedback(null)}
                open={refreshToastActive}
                scope="content"
                scopeRect={contentViewportRect}
                severity={refreshToastSeverity}
                darkMode={isDarkMode}
            />
        </>
    )
}