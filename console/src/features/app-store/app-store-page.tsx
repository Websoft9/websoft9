import {
    Avatar,
    Badge,
    Box,
    Button,
    Card,
    CardContent,
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
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { SurfaceFeedbackToast, SurfaceNoticeAlert, SurfaceStateCard } from '../../shared/design-system/standard-surfaces'
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

function getMediaFileName(value: string | undefined) {
    return value?.split('?')[0].split('/').pop()
}

function mapLocaleToMediaDirectory(locale: string) {
    return locale.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

function getAppLogoSources(app: AppStoreApp) {
    const fileName = getMediaFileName(app.logo?.imageurl)
    const sources = [fileName ? `/media/logos/${fileName}` : null, app.logo?.imageurl]
    return sources.filter((value): value is string => Boolean(value))
}

function getAppScreenshotSources(app: AppStoreApp, locale: string) {
    const screenshot = getPreferredAppStoreScreenshot(app)
    const fileName = getMediaFileName(screenshot)
    const mediaDirectory = mapLocaleToMediaDirectory(locale)
    const sources = [fileName ? `/media/screenshots/${mediaDirectory}/${fileName}` : null, screenshot]
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

type ComposeEnvironmentRow = {
    id: string
    key: string
    value: string
}

type ComposeValidationResponse = {
    valid: boolean
    services: string[]
    environment_keys: string[]
    details: string
}

const DEFAULT_COMPOSE_TEMPLATE = `services:
    web:
        image: nginx:latest
        ports:
            - "8080:80"
`

const INSTALL_WORKSPACE_CARD_SX = {
    borderRadius: '2px',
    border: '1px solid rgba(203, 213, 225, 0.9)',
    background: 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
    boxShadow: '0 8px 24px rgba(15, 23, 42, 0.06)',
}

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

async function validateComposeInstall(payload: {
    app_id: string
    display_name: string
    compose_content: string
    env: Array<{ key: string; value: string }>
}) {
    return requestJson<ComposeValidationResponse>('/api/apps/install/compose/validate', {
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

function AppLogo({ app }: { app: AppStoreApp }) {
    const [sourceIndex, setSourceIndex] = useState(0)
    const label = app.trademark ?? app.key
    const sources = getAppLogoSources(app)

    useEffect(() => {
        setSourceIndex(0)
    }, [app.key, app.logo?.imageurl])

    if (sources.length === 0 || sourceIndex >= sources.length) {
        return (
            <Avatar
                variant="rounded"
                sx={{
                    width: '100%',
                    height: '100%',
                    borderRadius: '4px',
                    background: '#eef2ff',
                    color: '#334155',
                    fontSize: 28,
                    fontWeight: 600,
                    border: '1px solid rgba(226, 232, 240, 0.95)',
                }}
            >
                {getAppInitial(label)}
            </Avatar>
        )
    }

    return (
        <Box
            component="img"
            alt={label ?? 'App'}
            src={sources[sourceIndex]}
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

function FavoriteIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="m12 21.35-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09A5.96 5.96 0 0 1 16.5 3C19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35Z" />
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

function isWebAccessPortSetting(key: string) {
    return key === 'W9_HTTP_PORT_SET' || key === 'W9_HTTPS_PORT_SET'
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
type InstallSourceKey = 'marketplace' | 'compose' | 'runtime'

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
    verticalPlacement?: 'center' | 'top'
    children: ReactNode
}

function AppStoreScopedOverlay({ open, scopeRect, onClose, maxWidth = 800, verticalPlacement = 'center', children, darkMode = false }: AppStoreScopedOverlayProps & { darkMode?: boolean }) {
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
                    backgroundColor: 'rgba(15, 23, 42, 0.18)',
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
                        height: 'auto',
                        maxHeight: `${availableHeight}px`,
                        display: 'flex',
                        flexDirection: 'column',
                        backgroundColor: darkMode ? '#182235' : '#fff',
                        color: darkMode ? '#e5edf5' : '#111827',
                        borderRadius: '2px',
                        boxShadow: darkMode ? '0 24px 64px rgba(2, 6, 23, 0.62)' : '0 16px 40px rgba(15, 23, 42, 0.16)',
                        border: darkMode ? '1px solid rgba(148, 163, 184, 0.22)' : undefined,
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
    const navigate = useNavigate()
    const [searchParams, setSearchParams] = useSearchParams()
    const [searchValue, setSearchValue] = useState('')
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
    const [wildcardDomain, setWildcardDomain] = useState('')
    const [isDomainEnabled, setIsDomainEnabled] = useState(true)
    const [customDomain, setCustomDomain] = useState('')
    const [composeAppId, setComposeAppId] = useState('customapp')
    const [composeDisplayName, setComposeDisplayName] = useState('Custom Compose App')
    const [composeDomain, setComposeDomain] = useState('')
    const [composeContent, setComposeContent] = useState(DEFAULT_COMPOSE_TEMPLATE)
    const [composeEnvRows, setComposeEnvRows] = useState<ComposeEnvironmentRow[]>([{ id: 'env-1', key: '', value: '' }])
    const [composeValidation, setComposeValidation] = useState<ComposeValidationResponse | null>(null)
    const [composeValidationError, setComposeValidationError] = useState<string | null>(null)
    const [composeFieldErrors, setComposeFieldErrors] = useState<{ appId?: string; displayName?: string; composeContent?: string; domain?: string; env?: string }>({})
    const [isValidatingCompose, setIsValidatingCompose] = useState(false)
    const [isFavoritesOpen, setIsFavoritesOpen] = useState(false)
    const [detailDialogSource, setDetailDialogSource] = useState<DetailDialogSource>('catalog')
    const [contentViewportRect, setContentViewportRect] = useState<ContentViewportRect | null>(null)
    const appIdInputRef = useRef<HTMLInputElement | null>(null)
    const customDomainInputRef = useRef<HTMLInputElement | null>(null)
    const composeFileInputRef = useRef<HTMLInputElement | null>(null)
    const installSettingInputRefs = useRef<Record<string, HTMLInputElement | null>>({})
    const deferredSearchValue = useDeferredValue(searchValue)
    const { data, error, isLoading, refetch } = useAppStoreApps()
    const { data: catalogsData } = useAppStoreCatalogs()
    const { data: favoritesData, refetch: refetchFavorites } = useQuery<ProductAuthFavoritesResponse, Error>({
        queryKey: ['product-auth-favorites'],
        queryFn: fetchFavorites,
        staleTime: 10_000,
    })

    const apps = data ?? []
    const catalogs = catalogsData ?? []
    const sourceParam = searchParams.get('source')
    const selectedInstallSource: InstallSourceKey = lockedInstallSource ?? (sourceParam === 'compose' || sourceParam === 'runtime' ? sourceParam : 'marketplace')
    const contentScopeContainer = typeof document === 'undefined' ? null : document.querySelector('#app-shell-main')
    const favoriteSet = useMemo(() => new Set((favoritesData?.favorites ?? []).map((item) => item.toLowerCase())), [favoritesData?.favorites])
    const currentHostname = typeof window === 'undefined' ? '' : window.location.hostname
    const isDarkMode = colorMode === 'dark'
    const appStoreControlTextSx = {
        fontSize: 14,
        fontWeight: 500,
        color: isDarkMode ? '#e5edf5' : '#334155',
    }
    const appStoreMenuItemSx = {
        fontSize: 14,
        fontWeight: 500,
        color: isDarkMode ? '#e5edf5' : '#334155',
        '&.Mui-selected': {
            backgroundColor: isDarkMode ? 'rgba(37, 99, 235, 0.28)' : 'rgba(37, 99, 235, 0.12)',
            color: isDarkMode ? '#f9fafb' : '#1e293b',
        },
        '&.Mui-selected:hover': {
            backgroundColor: isDarkMode ? 'rgba(37, 99, 235, 0.36)' : 'rgba(37, 99, 235, 0.18)',
        },
    }
    const palette = {
        panelBg: isDarkMode ? '#111827' : '#ffffff',
        dialogBg: isDarkMode ? '#182235' : '#ffffff',
        panelSoft: isDarkMode ? '#0f172a' : '#f8fafc',
        panelHover: isDarkMode ? '#1f2937' : 'rgb(229, 230, 229)',
        text: isDarkMode ? '#f9fafb' : '#111827',
        subtleText: isDarkMode ? '#9fb0c3' : '#475569',
        border: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(226, 232, 240, 0.95)',
        borderStrong: isDarkMode ? 'rgba(148, 163, 184, 0.22)' : 'rgba(203, 213, 225, 0.9)',
        actionBg: isDarkMode ? '#1f2937' : '#eef2f7',
        actionHover: isDarkMode ? '#334155' : '#e2e8f0',
    }
    const installDialogFieldSx = {
        '& .MuiOutlinedInput-root': {
            borderRadius: '4px',
            minHeight: 38,
            backgroundColor: palette.panelBg,
        },
        '& .MuiOutlinedInput-root.Mui-disabled': {
            backgroundColor: palette.panelSoft,
        },
        '& .MuiOutlinedInput-notchedOutline': {
            borderColor: palette.borderStrong,
        },
        '& .MuiInputLabel-root': {
            color: palette.subtleText,
        },
        '& .MuiInputLabel-root.Mui-focused': {
            color: palette.subtleText,
        },
        '& .MuiInputBase-input, & .MuiSelect-select': {
            fontSize: 14,
            fontWeight: 400,
            color: palette.text,
            WebkitTextFillColor: palette.text,
        },
        '& .MuiInputBase-input::placeholder': {
            fontSize: 14,
            fontWeight: 400,
            color: isDarkMode ? '#64748b' : '#94a3b8',
            WebkitTextFillColor: isDarkMode ? '#64748b' : '#94a3b8',
            opacity: 1,
        },
        '& .MuiInputBase-input::-webkit-input-placeholder': {
            color: isDarkMode ? '#64748b' : '#94a3b8',
            WebkitTextFillColor: isDarkMode ? '#64748b' : '#94a3b8',
            opacity: 1,
        },
        '& .MuiInputBase-input::-moz-placeholder': {
            color: isDarkMode ? '#64748b' : '#94a3b8',
            opacity: 1,
        },
        '& .MuiInputBase-input.Mui-disabled': {
            WebkitTextFillColor: palette.text,
            color: palette.text,
            opacity: 1,
        },
        '& .MuiFormHelperText-root': {
            color: palette.subtleText,
            mx: 0,
            mt: 0.75,
        },
        '& .MuiFormHelperText-root.Mui-error': {
            color: '#fda4af',
        },
    } as const
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
    const normalizedCustomDomain = normalizeCustomDomain(customDomain)
    const hasCustomAccessDomain = Boolean(normalizedCustomDomain)
    const availableVersions = selectedApp ? getAppStoreInstallDistributions(selectedApp).flatMap((distribution) => distribution.versions) : []
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
    const favoriteListLabel = t('appStorePage.actions.favoriteListLabel')
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
        {
            key: 'runtime',
            label: t('appStorePage.sources.runtime.label'),
            description: t('appStorePage.sources.runtime.description'),
        },
    ]
    const pageHeroDescription =
        selectedInstallSource === 'marketplace'
            ? t('appStorePage.hero.description')
            : t(`appStorePage.sources.${selectedInstallSource}.heroDescription`)
    const pageHeroTitle = selectedInstallSource === 'marketplace'
        ? undefined
        : installSourceOptions.find((option) => option.key === selectedInstallSource)?.label
    const selectedMainCategory = mainCategories.find((category) => category.key === selectedMainCatalogKey) ?? mainCategories[0]
    const selectedSubCategory = subCategories.find((category) => category.key === selectedSubCatalogKey) ?? subCategories[0]
    const currentListTitle = useMemo(() => {
        const segments = [t('appStorePage.results.allAppsSectionTitle')]

        if (selectedMainCatalogKey !== 'all') {
            segments.push(selectedMainCategory?.title ?? t('appStorePage.filters.allMainCategories'))
        }

        if (selectedSubCatalogKey !== 'all') {
            segments.push(selectedSubCategory?.title ?? t('appStorePage.filters.allSubCategories'))
        }

        return segments.join(' / ')
    }, [selectedMainCatalogKey, selectedMainCategory?.title, selectedSubCatalogKey, selectedSubCategory?.title, t])
    const sourceWorkspaceBackTarget = hideInstallSourceSelector && selectedInstallSource !== 'marketplace' ? '/applications' : '/appstore'
    const sourceWorkspaceBackLabel = hideInstallSourceSelector && selectedInstallSource !== 'marketplace'
        ? t('appStorePage.actions.backToApplications')
        : t('appStorePage.actions.backToMarketplace')
    const showPageHero = !(hideInstallSourceSelector && selectedInstallSource === 'marketplace')

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
        setCustomDomain('')
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
        const normalizedCustomDomain = normalizeCustomDomain(customDomain)
        const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
        setInstallFieldErrors({})

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

        if (normalizedCustomDomain && !isValidCustomDomain(normalizedCustomDomain)) {
            const message = t('appStorePage.install.validation.customDomainFormat')
            setInstallFieldErrors({ customDomain: message })
            setInstallError(message)
            customDomainInputRef.current?.focus()
            return
        }

        const portsValidationMessage = getInstallPortsValidationMessage(installSettings, t, locale)
        if (portsValidationMessage) {
            setInstallFieldErrors({ settings: { [portsValidationMessage.key]: portsValidationMessage.message } })
            setInstallError(portsValidationMessage.message)
            installSettingInputRefs.current[portsValidationMessage.key]?.focus()
            return
        }

        setIsSubmittingInstall(true)
        setInstallError(null)

        try {
            const proxyEnabled = selectedApp.is_web_app ? (Boolean(wildcardDomain) && isDomainEnabled) || Boolean(normalizedCustomDomain) : false
            const domainNames = selectedApp.is_web_app
                ? Boolean(normalizedCustomDomain) && Boolean(wildcardDomain) && isDomainEnabled
                    ? [normalizedCustomDomain, `${normalizedAppId}.${wildcardDomain}`]
                    : Boolean(normalizedCustomDomain)
                        ? [normalizedCustomDomain]
                        : Boolean(wildcardDomain) && isDomainEnabled
                            ? [`${normalizedAppId}.${wildcardDomain}`]
                            : [currentHostname]
                : [currentHostname]

            const installResult = await installApp(
                selectedApp,
                normalizedAppId,
                selectedVersion,
                installSettings,
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
                const matchedSettingKey = Object.entries(installSettings).find(([, value]) => value.trim() === conflictedPort)?.[0]
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
        setComposeValidation(null)
        setComposeValidationError(null)
    }

    function updateComposeEnvRow(id: string, field: 'key' | 'value', value: string) {
        clearComposeFeedback()
        setComposeFieldErrors((currentValue) => ({ ...currentValue, env: undefined }))
        setComposeEnvRows((currentValue) => currentValue.map((row) => (row.id === id ? { ...row, [field]: value } : row)))
    }

    function addComposeEnvRow() {
        clearComposeFeedback()
        setComposeEnvRows((currentValue) => [...currentValue, { id: `env-${Date.now()}-${currentValue.length}`, key: '', value: '' }])
    }

    function removeComposeEnvRow(id: string) {
        clearComposeFeedback()
        setComposeEnvRows((currentValue) => {
            const nextRows = currentValue.filter((row) => row.id !== id)
            return nextRows.length > 0 ? nextRows : [{ id: 'env-1', key: '', value: '' }]
        })
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

    async function handleValidateCompose() {
        const nextErrors: { appId?: string; displayName?: string; composeContent?: string; domain?: string; env?: string } = {}
        const normalizedComposeAppId = normalizeInstallName(composeAppId)
        const normalizedComposeDomain = normalizeCustomDomain(composeDomain)
        const envRows = composeEnvRows.filter((row) => row.key.trim() || row.value.trim())

        if (!normalizedComposeAppId) {
            nextErrors.appId = t('appStorePage.sources.compose.workspace.appIdRequired')
        } else if (!isInstallNameValid(normalizedComposeAppId)) {
            nextErrors.appId = t('appStorePage.install.validation.appId')
        }

        if (!composeDisplayName.trim()) {
            nextErrors.displayName = t('appStorePage.sources.compose.workspace.displayNameRequired')
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

        setComposeAppId(normalizedComposeAppId || composeAppId)
        setComposeDomain(normalizedComposeDomain)
        setComposeFieldErrors(nextErrors)
        clearComposeFeedback()

        if (Object.keys(nextErrors).length > 0) {
            setComposeValidationError(Object.values(nextErrors)[0] ?? null)
            return
        }

        setIsValidatingCompose(true)
        try {
            const response = await validateComposeInstall({
                app_id: normalizedComposeAppId,
                display_name: composeDisplayName.trim(),
                compose_content: composeContent,
                env: envRows.map((row) => ({ key: row.key.trim(), value: row.value })),
            })
            setComposeValidation(response)
        } catch (validationError) {
            setComposeValidationError(validationError instanceof Error ? validationError.message : t('appStorePage.sources.compose.workspace.validationFailedTitle'))
        } finally {
            setIsValidatingCompose(false)
        }
    }

    function handleSearchChange(value: string) {
        setSearchValue(value)
    }

    async function handleRefreshStore() {
        if (isRefreshingStore) {
            return
        }

        setIsRefreshingStore(true)

        try {
            const [appsResult, favoritesResult] = await Promise.all([
                refetch(),
                refetchFavorites(),
                new Promise((resolve) => {
                    window.setTimeout(resolve, 450)
                }),
            ])

            if (appsResult.error) {
                throw appsResult.error
            }

            if (favoritesResult.error) {
                throw favoritesResult.error
            }

        } catch (refreshError) {
            setInstallError(refreshError instanceof Error ? refreshError.message : t('appStorePage.states.errorTitle'))
        } finally {
            setIsRefreshingStore(false)
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

    return (
        <Box
            sx={{
                height: 'calc(100vh - 120px)',
                position: 'relative',
                mx: { xs: -1, md: -3 },
                my: { xs: -1.25, md: -2.25 },
                px: { xs: 2, md: 3 },
                py: { xs: 1.25, md: 1.5 },
                backgroundColor: isDarkMode ? '#0f172a' : '#ffffff',
                color: isDarkMode ? '#f9fafb' : '#111827',
                overflow: 'hidden',
                '& .MuiCard-root': {
                    background: `${isDarkMode ? '#111827' : '#ffffff'} !important`,
                    borderColor: `${isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(203, 213, 225, 0.9)'} !important`,
                    color: `${isDarkMode ? '#f9fafb' : '#111827'} !important`,
                },
                '& .MuiPaper-root': {
                    backgroundColor: `${isDarkMode ? '#111827' : '#ffffff'} !important`,
                    color: `${isDarkMode ? '#f9fafb' : '#111827'} !important`,
                },
                '& .MuiOutlinedInput-root': {
                    backgroundColor: `${isDarkMode ? '#111827' : '#ffffff'} !important`,
                    color: `${isDarkMode ? '#f9fafb' : '#111827'} !important`,
                },
                '& .MuiOutlinedInput-notchedOutline': {
                    borderColor: `${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(226, 232, 240, 0.95)'} !important`,
                },
                '& .MuiInputLabel-root, & .MuiInputBase-input, & .MuiSelect-select': {
                    color: `${isDarkMode ? '#e5edf5' : '#111827'} !important`,
                },
                '& .MuiInputBase-input::placeholder': {
                    color: `${isDarkMode ? '#94a3b8' : '#94a3b8'} !important`,
                    opacity: '1 !important',
                },
                '& .MuiMenuItem-root': {
                    color: `${isDarkMode ? '#e5edf5' : '#111827'} !important`,
                },
                '& .MuiTypography-root': {
                    color: isDarkMode ? '#e5edf5' : undefined,
                },
                '& .MuiAlert-root': {
                    backgroundColor: `${isDarkMode ? '#111827' : '#ffffff'} !important`,
                    color: `${isDarkMode ? '#e5edf5' : '#111827'} !important`,
                    border: `1px solid ${isDarkMode ? 'rgba(255,255,255,0.08)' : 'rgba(226,232,240,0.95)'}`,
                },
            }}
        >
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, width: '100%', height: '100%', minHeight: 0 }}>
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
                                gridTemplateColumns: { xs: '1fr', md: 'repeat(3, minmax(0, 1fr))' },
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
                                            borderColor: active ? 'rgba(59, 130, 246, 0.42)' : palette.border,
                                            backgroundColor: active ? (isDarkMode ? 'rgba(37, 99, 235, 0.18)' : '#eff6ff') : palette.panelBg,
                                            color: palette.text,
                                            '&:hover': {
                                                borderColor: active ? 'rgba(59, 130, 246, 0.58)' : 'rgba(148, 163, 184, 0.95)',
                                                backgroundColor: active ? (isDarkMode ? 'rgba(37, 99, 235, 0.24)' : '#dbeafe') : palette.panelSoft,
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

                {selectedInstallSource === 'marketplace' ? (
                    <Box
                        sx={{
                            flexShrink: 0,
                            gap: 2.25,
                            display: 'grid',
                            py: 0,
                            pr: { md: '18px' },
                            backgroundColor: isDarkMode ? '#0f172a' : '#ffffff',
                            boxShadow: 'none',
                        }}
                    >
                        <PageDescriptionHeader
                            title={t('nav.appStore.label')}
                            description={t('appStorePage.hero.description')}
                            titleColor={palette.text}
                            descriptionColor={palette.subtleText}
                            sx={{ mt: 0, mb: 0.75 }}
                            actions={(
                                <Box
                                    sx={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 0.5,
                                        flexShrink: 0,
                                    }}
                                >
                                    <Tooltip title={t('appStorePage.actions.favoriteList', { count: favoriteApps.length }).replace(/\s*\(\d+\)$/, '')}>
                                        <Button
                                            color="inherit"
                                            onClick={() => {
                                                openFavoritesDialog()
                                            }}
                                            size="small"
                                            className="app-shell-page-pill"
                                            startIcon={
                                                <Badge badgeContent={favoriteApps.length} color="error" max={99} overlap="circular">
                                                    <FavoriteIcon />
                                                </Badge>
                                            }
                                            aria-label={t('appStorePage.actions.favoriteList', { count: favoriteApps.length })}
                                            sx={{
                                                px: 1.5,
                                                '&:hover': {
                                                    borderColor: 'rgba(203, 213, 225, 0.85)',
                                                    background: palette.panelSoft,
                                                    boxShadow: '0 1px 2px rgba(15, 23, 42, 0.06)',
                                                },
                                                '& .MuiButton-startIcon': {
                                                    marginLeft: 0,
                                                    marginRight: 1,
                                                },
                                                '& .MuiSvgIcon-root': {
                                                    fontSize: 18,
                                                },
                                                '& .MuiBadge-badge': {
                                                    backgroundColor: '#e11d48',
                                                    color: '#fff',
                                                },
                                            }}
                                            title={t('appStorePage.actions.favoriteList', { count: favoriteApps.length })}
                                        >
                                            {favoriteListLabel}
                                        </Button>
                                    </Tooltip>
                                    <Tooltip title={isRefreshingStore ? t('appStorePage.actions.refreshing') : t('appStorePage.actions.refresh')}>
                                        <IconButton
                                            color="inherit"
                                            onClick={() => {
                                                void handleRefreshStore()
                                            }}
                                            size="small"
                                            disabled={isRefreshingStore}
                                            className="app-shell-page-action"
                                            title={isRefreshingStore ? t('appStorePage.actions.refreshing') : t('appStorePage.actions.refresh')}
                                        >
                                            {isRefreshingStore ? <CircularProgress size={14} color="inherit" /> : <RefreshIcon />}
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
                    <Box sx={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', overflowX: 'hidden', pr: 0.5 }}>
                        <Stack spacing={1.5} sx={{ pb: 0.5 }}>
                            <SurfaceStateCard
                                title={t('appStorePage.sources.compose.workspace.title')}
                                detail={t('appStorePage.sources.compose.workspace.description')}
                            />

                            <Card sx={INSTALL_WORKSPACE_CARD_SX}>
                                <CardContent>
                                    <Stack spacing={2}>
                                        <Box>
                                            <Typography variant="subtitle2" sx={{ color: '#0f172a', fontWeight: 700 }}>
                                                {t('appStorePage.sources.compose.workspace.metadataTitle')}
                                            </Typography>
                                            <Typography variant="body2" sx={{ color: '#475569', mt: 0.5 }}>
                                                {t('appStorePage.sources.compose.workspace.metadataDetail')}
                                            </Typography>
                                        </Box>
                                        <Box
                                            sx={{
                                                display: 'grid',
                                                gap: 1.5,
                                                gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' },
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
                                                helperText={composeFieldErrors.appId ?? ' '}
                                            />
                                            <TextField
                                                fullWidth
                                                label={t('appStorePage.sources.compose.workspace.displayNameLabel')}
                                                placeholder={t('appStorePage.sources.compose.workspace.displayNamePlaceholder')}
                                                value={composeDisplayName}
                                                onChange={(event) => {
                                                    clearComposeFeedback()
                                                    setComposeFieldErrors((currentValue) => ({ ...currentValue, displayName: undefined }))
                                                    setComposeDisplayName(event.target.value)
                                                }}
                                                error={Boolean(composeFieldErrors.displayName)}
                                                helperText={composeFieldErrors.displayName ?? ' '}
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
                                                helperText={composeFieldErrors.domain ?? ' '}
                                            />
                                        </Box>
                                    </Stack>
                                </CardContent>
                            </Card>

                            <Card sx={INSTALL_WORKSPACE_CARD_SX}>
                                <CardContent>
                                    <Stack spacing={2}>
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                                            <Box>
                                                <Typography variant="subtitle2" sx={{ color: '#0f172a', fontWeight: 700 }}>
                                                    {t('appStorePage.sources.compose.workspace.envTitle')}
                                                </Typography>
                                                <Typography variant="body2" sx={{ color: '#475569', mt: 0.5 }}>
                                                    {t('appStorePage.sources.compose.workspace.envDetail')}
                                                </Typography>
                                            </Box>
                                            <Button onClick={addComposeEnvRow} variant="outlined" sx={{ borderRadius: '2px', textTransform: 'none' }}>
                                                {t('appStorePage.sources.compose.workspace.addEnv')}
                                            </Button>
                                        </Box>
                                        <Stack spacing={1}>
                                            {composeEnvRows.map((row, index) => (
                                                <Box
                                                    key={row.id}
                                                    sx={{
                                                        display: 'grid',
                                                        gap: 1,
                                                        gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1fr) minmax(0, 1fr) auto' },
                                                        alignItems: 'start',
                                                    }}
                                                >
                                                    <TextField
                                                        fullWidth
                                                        label={t('appStorePage.sources.compose.workspace.envKeyLabel')}
                                                        value={row.key}
                                                        onChange={(event) => updateComposeEnvRow(row.id, 'key', event.target.value)}
                                                    />
                                                    <TextField
                                                        fullWidth
                                                        label={t('appStorePage.sources.compose.workspace.envValueLabel')}
                                                        value={row.value}
                                                        onChange={(event) => updateComposeEnvRow(row.id, 'value', event.target.value)}
                                                    />
                                                    <Button
                                                        onClick={() => removeComposeEnvRow(row.id)}
                                                        variant="text"
                                                        color="inherit"
                                                        disabled={composeEnvRows.length === 1 && index === 0 && !row.key && !row.value}
                                                        sx={{ mt: { xs: 0, md: 1 }, justifySelf: 'start', textTransform: 'none' }}
                                                    >
                                                        {t('appStorePage.sources.compose.workspace.removeEnv')}
                                                    </Button>
                                                </Box>
                                            ))}
                                        </Stack>
                                        {composeFieldErrors.env ? (
                                            <Typography variant="body2" sx={{ color: '#b91c1c' }}>
                                                {composeFieldErrors.env}
                                            </Typography>
                                        ) : null}
                                    </Stack>
                                </CardContent>
                            </Card>

                            <Card sx={INSTALL_WORKSPACE_CARD_SX}>
                                <CardContent>
                                    <Stack spacing={2}>
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
                                            <Box>
                                                <Typography variant="subtitle2" sx={{ color: '#0f172a', fontWeight: 700 }}>
                                                    {t('appStorePage.sources.compose.workspace.composeTitle')}
                                                </Typography>
                                                <Typography variant="body2" sx={{ color: '#475569', mt: 0.5 }}>
                                                    {t('appStorePage.sources.compose.workspace.composeDetail')}
                                                </Typography>
                                            </Box>
                                            <>
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
                                                <Button
                                                    onClick={() => composeFileInputRef.current?.click()}
                                                    variant="outlined"
                                                    sx={{ borderRadius: '2px', textTransform: 'none' }}
                                                >
                                                    {composeContent.trim() ? t('appStorePage.sources.compose.workspace.replaceUpload') : t('appStorePage.sources.compose.workspace.upload')}
                                                </Button>
                                            </>
                                        </Box>
                                        <TextField
                                            fullWidth
                                            multiline
                                            minRows={16}
                                            label={t('appStorePage.sources.compose.workspace.composeLabel')}
                                            placeholder={t('appStorePage.sources.compose.workspace.composePlaceholder')}
                                            value={composeContent}
                                            onChange={(event) => {
                                                clearComposeFeedback()
                                                setComposeFieldErrors((currentValue) => ({ ...currentValue, composeContent: undefined }))
                                                setComposeContent(event.target.value)
                                            }}
                                            error={Boolean(composeFieldErrors.composeContent)}
                                            helperText={composeFieldErrors.composeContent ?? ' '}
                                        />
                                    </Stack>
                                </CardContent>
                            </Card>

                            <SurfaceNoticeAlert
                                severity="info"
                                title={t('appStorePage.sources.compose.label')}
                                detail={t('appStorePage.sources.compose.workspace.validationOnly')}
                            />

                            {composeValidation ? (
                                <SurfaceNoticeAlert
                                    severity="success"
                                    title={t('appStorePage.sources.compose.workspace.validatedTitle')}
                                    detail={t('appStorePage.sources.compose.workspace.validatedDetail', { count: composeValidation.services.length })}
                                />
                            ) : null}

                            {composeValidationError ? (
                                <SurfaceNoticeAlert
                                    severity="warning"
                                    title={t('appStorePage.sources.compose.workspace.validationFailedTitle')}
                                    detail={composeValidationError}
                                />
                            ) : null}

                            <Card sx={INSTALL_WORKSPACE_CARD_SX}>
                                <CardContent>
                                    <Stack spacing={1.5}>
                                        <Typography variant="subtitle2" sx={{ color: '#0f172a', fontWeight: 700 }}>
                                            {t('appStorePage.sources.compose.workspace.services')}
                                        </Typography>
                                        {composeValidation?.services.length ? (
                                            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                                {composeValidation.services.map((serviceName) => (
                                                    <Box
                                                        key={serviceName}
                                                        sx={{
                                                            px: 1.25,
                                                            py: 0.75,
                                                            borderRadius: '999px',
                                                            border: '1px solid rgba(148, 163, 184, 0.45)',
                                                            backgroundColor: '#f8fafc',
                                                            color: '#0f172a',
                                                            fontSize: '0.85rem',
                                                            fontWeight: 600,
                                                        }}
                                                    >
                                                        {serviceName}
                                                    </Box>
                                                ))}
                                            </Box>
                                        ) : (
                                            <Typography variant="body2" sx={{ color: '#64748b' }}>
                                                {t('appStorePage.sources.compose.workspace.noServices')}
                                            </Typography>
                                        )}
                                    </Stack>
                                </CardContent>
                            </Card>

                            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                <Button
                                    onClick={() => void handleValidateCompose()}
                                    variant="contained"
                                    disabled={isValidatingCompose}
                                    sx={{ borderRadius: '2px', textTransform: 'none', boxShadow: 'none' }}
                                >
                                    {isValidatingCompose ? t('appStorePage.sources.compose.workspace.validating') : t('appStorePage.sources.compose.workspace.validate')}
                                </Button>
                                <Button onClick={() => navigate('/myapps')} variant="outlined" sx={{ borderRadius: '2px', textTransform: 'none' }}>
                                    {t('appStorePage.actions.openInstalledApps')}
                                </Button>
                                <Button onClick={() => navigate(sourceWorkspaceBackTarget)} variant="text" sx={{ borderRadius: '2px', textTransform: 'none' }}>
                                    {sourceWorkspaceBackLabel}
                                </Button>
                            </Box>
                        </Stack>
                    </Box>
                ) : (
                    <Box sx={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', overflowX: 'hidden', pr: 0.5 }}>
                        <Stack spacing={1.5} sx={{ pb: 0.5 }}>
                            <SurfaceStateCard
                                title={t(`appStorePage.sources.${selectedInstallSource}.emptyTitle`)}
                                detail={t(`appStorePage.sources.${selectedInstallSource}.emptyDetail`)}
                            />
                            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                <Button onClick={() => navigate('/myapps')} variant="outlined" sx={{ borderRadius: '2px', textTransform: 'none' }}>
                                    {t('appStorePage.actions.openInstalledApps')}
                                </Button>
                                <Button onClick={() => navigate(sourceWorkspaceBackTarget)} variant="contained" sx={{ borderRadius: '2px', textTransform: 'none', boxShadow: 'none' }}>
                                    {sourceWorkspaceBackLabel}
                                </Button>
                            </Box>
                        </Stack>
                    </Box>
                )}

                {selectedInstallSource === 'marketplace' ? (
                    <Box sx={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', overflowX: 'hidden', pr: 0.5 }}>
                        <Stack spacing={1.5} sx={{ pb: 0.5 }}>
                            <FavoriteSectionHeading title={currentListTitle} />

                            {isLoading || isRefreshingStore ? (
                                <SurfaceStateCard detail={isRefreshingStore ? t('appStorePage.actions.refreshing') : t('appStorePage.states.loading')} loading />
                            ) : null}

                            {!isLoading && !isRefreshingStore && error ? (
                                <SurfaceNoticeAlert
                                    detail={t('appStorePage.states.errorDetail', { statusCode: error.statusCode ?? 'unknown' })}
                                    action={
                                        <Button color="inherit" size="small" onClick={() => void refetch()}>
                                            {t('appStorePage.states.retry')}
                                        </Button>
                                    }
                                    severity="warning"
                                    title={t('appStorePage.states.errorTitle')}
                                />
                            ) : null}

                            {!isLoading && !isRefreshingStore && !error && filteredApps.length === 0 ? (
                                <SurfaceStateCard detail={t('appStorePage.states.emptyDetail')} title={t('appStorePage.states.emptyTitle')} />
                            ) : null}

                            {!isLoading && !isRefreshingStore && !error && filteredApps.length > 0 ? (
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
                                            return (
                                                <Card
                                                    key={app.key ?? app.trademark}
                                                    elevation={0}
                                                    onClick={() => {
                                                        openAppDetail(app, 'catalog')
                                                    }}
                                                    sx={{
                                                        border: `1px solid ${palette.border}`,
                                                        borderRadius: '2px',
                                                        backgroundColor: palette.panelBg,
                                                        boxShadow: '0 2px 5px rgba(0, 0, 0, 0.1)',
                                                        cursor: 'pointer',
                                                        transition: 'background-color 120ms ease, box-shadow 120ms ease',
                                                        '&:hover': {
                                                            backgroundColor: palette.panelHover,
                                                            boxShadow: '0 2px 5px rgba(0, 0, 0, 0.1)',
                                                        },
                                                    }}
                                                >
                                                    <CardContent sx={{ p: '10px !important' }}>
                                                        <Box sx={{ display: 'grid', gridTemplateColumns: '100px minmax(0, 1fr)', gap: 0, alignItems: 'center' }}>
                                                            <Box sx={{ width: 100, minWidth: 100, px: '10px', boxSizing: 'border-box' }}>
                                                                <Box sx={{ width: 80, height: 80 }}>
                                                                    <AppLogo app={app} />
                                                                </Box>
                                                            </Box>
                                                            <Box sx={{ minWidth: 0, textAlign: 'left' }}>
                                                                <Typography sx={{ fontSize: 17, fontWeight: 600, lineHeight: 1.25, mb: 0.5, color: palette.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                                    {app.trademark ?? app.key}
                                                                </Typography>
                                                                <Typography sx={{ fontSize: 14, lineHeight: 1.45, height: 44, overflow: 'hidden', textOverflow: 'ellipsis', color: palette.subtleText, fontWeight: 400 }}>
                                                                    {app.summary || app.overview || t('appStorePage.card.summaryFallback')}
                                                                </Typography>
                                                            </Box>
                                                        </Box>
                                                    </CardContent>
                                                </Card>
                                            )
                                        })}
                                    </Box>
                                </Stack>
                            ) : null}
                        </Stack>
                    </Box>
                ) : null}
            </Box>

            <AppStoreScopedOverlay open={isFavoritesOpen} onClose={() => setIsFavoritesOpen(false)} scopeRect={contentViewportRect} maxWidth={832} darkMode={isDarkMode}>
                <DialogTitle sx={{ px: { xs: 2, md: 2.5 }, py: { xs: 1.5, md: 1.75 }, backgroundColor: palette.dialogBg }}>
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
                                borderRadius: '12px',
                                border: `1px solid ${palette.border}`,
                                background: palette.actionBg,
                                color: palette.subtleText,
                                boxShadow: '0 1px 2px rgba(15, 23, 42, 0.05)',
                                '&:hover': {
                                    background: palette.actionHover,
                                    color: palette.text,
                                },
                            }}
                            title={t('appStorePage.actions.close')}
                        >
                            <CloseIcon />
                        </IconButton>
                    </Box>
                </DialogTitle>
                <DialogContent dividers sx={{ px: { xs: 2, md: 2.5 }, py: 2, backgroundColor: palette.dialogBg, '&.MuiDialogContent-dividers': { borderTopColor: palette.border, borderBottomColor: palette.border } }}>
                    {favoriteApps.length === 0 ? (
                        <SurfaceStateCard title={t('appStorePage.results.favoriteEmptyTitle')} detail={t('appStorePage.results.favoriteEmptyDetail')} />
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
                                                    <AppLogo app={app} />
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
                                    <AppLogo app={selectedApp} />
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
                                                sx={{ p: 0.5, color: isDarkMode ? '#f9fafb' : '#000', border: `1px solid ${palette.border}`, borderRadius: '4px', '& svg': { fontSize: 18 } }}
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
                                                        color: '#2563eb',
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
                                <IconButton onClick={handleCloseModal} size="small" sx={{ color: '#94a3b8', alignSelf: 'start', mr: -0.5 }}>
                                    <Box component="span" sx={{ fontSize: 28, lineHeight: 1 }}>x</Box>
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
                                                helperText={installFieldErrors.appId}
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
                                                            color: isDomainEnabled ? palette.subtleText : '#94a3b8',
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
                                                                textDecorationColor: isDomainEnabled ? undefined : '#94a3b8',
                                                            }}
                                                        >
                                                            {domainSuffix}
                                                        </Box>
                                                    </Box>
                                                    <Button
                                                        onClick={() => setIsDomainEnabled((currentValue) => !currentValue)}
                                                        sx={{
                                                            minWidth: 82,
                                                            border: isDomainEnabled ? '1px solid rgba(251, 146, 60, 0.32)' : '1px solid rgba(34, 197, 94, 0.28)',
                                                            borderLeft: 0,
                                                            background: isDomainEnabled
                                                                ? 'linear-gradient(180deg, #fff7ed 0%, #ffedd5 100%)'
                                                                : 'linear-gradient(180deg, #f0fdf4 0%, #dcfce7 100%)',
                                                            color: isDomainEnabled ? '#b45309' : '#15803d',
                                                            boxShadow: 'none',
                                                            borderRadius: '0 4px 4px 0',
                                                            '&:hover': {
                                                                background: isDomainEnabled
                                                                    ? 'linear-gradient(180deg, #ffedd5 0%, #fed7aa 100%)'
                                                                    : 'linear-gradient(180deg, #dcfce7 0%, #bbf7d0 100%)',
                                                                color: isDomainEnabled ? '#9a3412' : '#166534',
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
                                        <Box>
                                            <Typography sx={{ mb: 0.75, fontSize: 14, fontWeight: 400, color: palette.subtleText }}>{t('appStorePage.install.customDomainLabel')}</Typography>
                                            <Box sx={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: 1 }}>
                                                <TextField
                                                    fullWidth
                                                    error={Boolean(installFieldErrors.customDomain)}
                                                    inputRef={customDomainInputRef}
                                                    helperText={installFieldErrors.customDomain ?? t('appStorePage.install.customDomainHelper')}
                                                    placeholder={t('appStorePage.install.customDomainPlaceholder')}
                                                    size="small"
                                                    value={customDomain}
                                                    onChange={(event) => {
                                                        setInstallFieldErrors((currentValue) => ({ ...currentValue, customDomain: undefined }))
                                                        setInstallError(null)
                                                        setCustomDomain(normalizeCustomDomain(event.target.value))
                                                    }}
                                                    sx={installDialogFieldSx}
                                                />
                                            </Box>
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

                                    {Object.entries(installSettings).map(([key, value]) => (
                                        <Box key={key}>
                                            {(() => {
                                                const isProxyManagedPort = hasCustomAccessDomain && isWebAccessPortSetting(key)
                                                const hasFieldError = Boolean(installFieldErrors.settings?.[key])
                                                const shouldDisableSetting = isProxyManagedPort && !hasFieldError
                                                const helperText = installFieldErrors.settings?.[key]

                                                return (
                                                    <>
                                            <Typography sx={{ mb: 0.75, fontSize: 14, fontWeight: 400, color: palette.subtleText }}>{getInstallSettingLabel(key, t, i18n.resolvedLanguage ?? i18n.language ?? 'en')}</Typography>
                                            <TextField
                                                disabled={shouldDisableSetting}
                                                error={Boolean(installFieldErrors.settings?.[key])}
                                                fullWidth
                                                helperText={helperText}
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

            <SurfaceFeedbackToast
                message={installError ?? installFeedback?.message ?? ''}
                onClose={() => {
                    setInstallFeedback(null)
                    setInstallError(null)
                }}
                open={Boolean(installFeedback) || Boolean(installError)}
                scope="content"
                scopeRect={contentViewportRect}
                severity={installError ? 'error' : installFeedback?.severity ?? 'success'}
            />
        </Box>
    )
}