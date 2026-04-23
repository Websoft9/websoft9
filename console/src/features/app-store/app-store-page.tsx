import {
    Alert,
    Avatar,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    Link,
    MenuItem,
    Snackbar,
    SvgIcon,
    TextField,
    Typography,
} from '@mui/material'
import { useNavigate } from 'react-router-dom'
import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

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

type InstallFeedback = {
    severity: 'success' | 'error'
    message: string
}

type InstallError = Error & {
    statusCode?: number
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

    return response.json().catch(() => null)
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
                backgroundColor: '#fff',
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
            component="img"
            alt={alt}
            src={sources[sourceIndex]}
            onError={() => {
                setSourceIndex((currentValue) => currentValue + 1)
            }}
            sx={{
                width: '80%',
                height: 300,
                display: 'block',
                objectFit: 'contain',
                mx: 'auto',
                mt: 2.5,
                backgroundColor: '#fff',
                mb: 3,
            }}
        />
    )
}

function GitHubMarkIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M12 2C6.48 2 2 6.59 2 12.25c0 4.52 2.87 8.35 6.84 9.7.5.1.66-.22.66-.49 0-.24-.01-1.03-.01-1.86-2.78.62-3.37-1.22-3.37-1.22-.46-1.2-1.11-1.52-1.11-1.52-.91-.64.07-.63.07-.63 1 .07 1.53 1.06 1.53 1.06.9 1.57 2.35 1.12 2.92.85.09-.67.35-1.12.63-1.38-2.22-.26-4.56-1.15-4.56-5.13 0-1.13.39-2.05 1.03-2.77-.1-.26-.45-1.32.1-2.75 0 0 .84-.28 2.75 1.06A9.3 9.3 0 0 1 12 6.84c.85 0 1.71.12 2.51.36 1.91-1.34 2.75-1.06 2.75-1.06.55 1.43.2 2.49.1 2.75.64.72 1.03 1.64 1.03 2.77 0 3.99-2.35 4.87-4.58 5.12.36.32.69.95.69 1.92 0 1.39-.01 2.5-.01 2.84 0 .27.17.59.67.49A10.1 10.1 0 0 0 22 12.25C22 6.59 17.52 2 12 2Z" />
        </SvgIcon>
    )
}

const appStoreControlTextSx = {
    fontSize: 14,
    fontWeight: 500,
    color: '#334155',
}

const appStoreMenuItemSx = {
    fontSize: 14,
    fontWeight: 500,
    color: '#334155',
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

export function AppStorePage() {
    const { t, i18n } = useTranslation('shell')
    const navigate = useNavigate()
    const [searchValue, setSearchValue] = useState('')
    const [selectedMainCatalogKey, setSelectedMainCatalogKey] = useState('all')
    const [selectedSubCatalogKey, setSelectedSubCatalogKey] = useState('all')
    const [selectedApp, setSelectedApp] = useState<AppStoreApp | null>(null)
    const [isInstallMode, setIsInstallMode] = useState(false)
    const [installName, setInstallName] = useState('')
    const [selectedVersion, setSelectedVersion] = useState('latest')
    const [installSettings, setInstallSettings] = useState<Record<string, string>>({})
    const [installError, setInstallError] = useState<string | null>(null)
    const [installFeedback, setInstallFeedback] = useState<InstallFeedback | null>(null)
    const [isSubmittingInstall, setIsSubmittingInstall] = useState(false)
    const [wildcardDomain, setWildcardDomain] = useState('')
    const [isDomainEnabled, setIsDomainEnabled] = useState(true)
    const [isCustomDomainVisible, setIsCustomDomainVisible] = useState(false)
    const [customDomain, setCustomDomain] = useState('')
    const deferredSearchValue = useDeferredValue(searchValue)
    const { data, error, isLoading, isFetching, refetch } = useAppStoreApps()
    const { data: catalogsData } = useAppStoreCatalogs()

    const apps = data ?? []
    const catalogs = catalogsData ?? []
    const currentHostname = typeof window === 'undefined' ? '' : window.location.hostname
    const domainSuffix = wildcardDomain ? `.${wildcardDomain}` : ''
    const mainCategories = useMemo(() => [{ key: 'all', title: t('appStorePage.filters.allMainCategories') }, ...catalogs], [catalogs, t])
    const subCategories = useMemo(
        () => [{ key: 'all', title: t('appStorePage.filters.allSubCategories') }, ...getSubCatalogs(catalogs, selectedMainCatalogKey)],
        [catalogs, selectedMainCatalogKey, t],
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
        setIsDomainEnabled(Boolean(wildcardDomain))
        setIsCustomDomainVisible(false)
        setCustomDomain('')
    }, [isInstallMode, selectedApp, wildcardDomain])

    async function handleInstallSubmit() {
        if (!selectedApp) {
            return
        }

        const normalizedAppId = normalizeInstallName(installName)
        if (!isInstallNameValid(normalizedAppId)) {
            setInstallError(t('appStorePage.install.validation.appId'))
            return
        }

        if (isCustomDomainVisible && !customDomain.trim()) {
            setInstallError(t('appStorePage.install.validation.customDomain'))
            return
        }

        setIsSubmittingInstall(true)
        setInstallError(null)

        try {
            const proxyEnabled = selectedApp.is_web_app ? (Boolean(wildcardDomain) && isDomainEnabled) || Boolean(customDomain.trim()) : false
            const domainNames = selectedApp.is_web_app
                ? Boolean(customDomain.trim()) && Boolean(wildcardDomain) && isDomainEnabled
                    ? [customDomain.trim(), `${normalizedAppId}.${wildcardDomain}`]
                    : Boolean(customDomain.trim())
                        ? [customDomain.trim()]
                        : Boolean(wildcardDomain) && isDomainEnabled
                            ? [`${normalizedAppId}.${wildcardDomain}`]
                            : [currentHostname]
                : [currentHostname]

            await installApp(
                selectedApp,
                normalizedAppId,
                selectedVersion,
                installSettings,
                domainNames.length > 0 ? domainNames : [currentHostname],
                proxyEnabled,
            )
            setInstallFeedback({ severity: 'success', message: t('appStorePage.install.feedback.success') })
            setSelectedApp(null)
            setIsInstallMode(false)
        } catch (submitError) {
            const message = submitError instanceof Error ? submitError.message : t('appStorePage.install.feedback.error')
            setInstallError(message)
        } finally {
            setIsSubmittingInstall(false)
        }
    }

    function handleCloseModal() {
        setSelectedApp(null)
        setIsInstallMode(false)
        setInstallError(null)
    }

    function handleCatalogClick(subCategory: AppStoreCatalogItem, mainCategory?: AppStoreCatalogItem) {
        setSelectedMainCatalogKey(mainCategory?.key ?? 'all')
        setSelectedSubCatalogKey(subCategory.key ?? 'all')
        handleCloseModal()
    }

    function handleSearchChange(value: string) {
        setSelectedMainCatalogKey('all')
        setSelectedSubCatalogKey('all')
        setSearchValue(value)
    }

    return (
        <Box
            sx={{
                minHeight: 'calc(100vh - 120px)',
                mx: { xs: -1, md: -3 },
                my: { xs: -1.5, md: -2.5 },
                px: { xs: 2, md: 3 },
                py: { xs: 1.5, md: 2.25 },
                backgroundColor: '#ffffff',
            }}
        >
            <Box sx={{ display: 'grid', gap: 2, width: '100%' }}>
                <Box
                    sx={{
                        display: 'grid',
                        gap: 1.5,
                        gridTemplateColumns: { xs: '1fr', md: '220px 220px minmax(0, 1fr)' },
                        alignItems: 'center',
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
                            '& .MuiOutlinedInput-root': {
                                borderRadius: '4px',
                                backgroundColor: '#fff',
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
                            <MenuItem key={category.key} value={category.key ?? 'all'}>
                                {category.title}
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
                            '& .MuiOutlinedInput-root': {
                                borderRadius: '4px',
                                backgroundColor: '#fff',
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
                            <MenuItem key={category.key} value={category.key ?? 'all'}>
                                {category.title}
                            </MenuItem>
                        ))}
                    </TextField>
                    <TextField
                        fullWidth
                        size="small"
                        value={searchValue}
                        onChange={(event) => {
                            handleSearchChange(event.target.value)
                        }}
                        placeholder={t('appStorePage.filters.searchPlaceholder')}
                        sx={{
                            '& .MuiOutlinedInput-root': {
                                borderRadius: '4px',
                                backgroundColor: '#fff',
                                minHeight: 42,
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

                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', minHeight: 34, px: 0.25 }}>
                    <Typography sx={{ fontSize: 16, fontWeight: 400, color: '#111827' }}>{t('appStorePage.results.sectionTitle')}</Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {isFetching && !isLoading ? <CircularProgress size={16} /> : null}
                        <Typography color="text.secondary" sx={{ fontSize: 12.5 }}>
                            {t('appStorePage.results.helper')}
                        </Typography>
                    </Box>
                </Box>

                {isLoading ? (
                    <Card elevation={0} sx={{ border: '1px solid rgba(15, 23, 42, 0.08)' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1.5, py: 5 }}>
                                <CircularProgress size={28} />
                                <Typography color="text.secondary" variant="body2">
                                    {t('appStorePage.states.loading')}
                                </Typography>
                            </Box>
                        </CardContent>
                    </Card>
                ) : null}

                {!isLoading && error ? (
                    <Alert
                        action={
                            <Button color="inherit" size="small" onClick={() => void refetch()}>
                                {t('appStorePage.states.retry')}
                            </Button>
                        }
                        severity="warning"
                        variant="outlined"
                    >
                        <Typography sx={{ fontWeight: 600 }}>{t('appStorePage.states.errorTitle')}</Typography>
                        <Typography variant="body2">
                            {t('appStorePage.states.errorDetail', { statusCode: error.statusCode ?? 'unknown' })}
                        </Typography>
                    </Alert>
                ) : null}

                {!isLoading && !error && filteredApps.length === 0 ? (
                    <Card elevation={0} sx={{ border: '1px solid rgba(15, 23, 42, 0.08)' }}>
                        <CardContent>
                            <Box sx={{ py: 4, textAlign: 'center' }}>
                                <Typography sx={{ fontWeight: 600 }}>{t('appStorePage.states.emptyTitle')}</Typography>
                                <Typography color="text.secondary" variant="body2">
                                    {t('appStorePage.states.emptyDetail')}
                                </Typography>
                            </Box>
                        </CardContent>
                    </Card>
                ) : null}

                {!isLoading && !error && filteredApps.length > 0 ? (
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
                                        setSelectedApp(app)
                                    }}
                                    sx={{
                                        border: '1px solid rgba(229, 231, 235, 0.92)',
                                        borderRadius: '2px',
                                        backgroundColor: '#fff',
                                        boxShadow: '0 2px 5px rgba(0, 0, 0, 0.1)',
                                        cursor: 'pointer',
                                        transition: 'background-color 120ms ease, box-shadow 120ms ease',
                                        '&:hover': {
                                            backgroundColor: 'rgb(229, 230, 229)',
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
                                                <Typography sx={{ fontSize: 17, fontWeight: 600, lineHeight: 1.25, mb: 0.5, color: '#1f2937', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                    {app.trademark ?? app.key}
                                                </Typography>
                                                <Typography sx={{ fontSize: 14, lineHeight: 1.45, height: 44, overflow: 'hidden', textOverflow: 'ellipsis', color: '#475569', fontWeight: 400 }}>
                                                    {app.summary || app.overview || t('appStorePage.card.summaryFallback')}
                                                </Typography>
                                            </Box>
                                        </Box>
                                    </CardContent>
                                </Card>
                            )
                        })}
                    </Box>
                ) : null}
            </Box>

            <Dialog
                fullWidth
                maxWidth="md"
                open={Boolean(selectedApp)}
                onClose={handleCloseModal}
                slotProps={{
                    paper: {
                        sx: {
                            width: 'min(800px, calc(100vw - 32px))',
                            maxWidth: '800px',
                            borderRadius: '2px',
                            boxShadow: '0 12px 36px rgba(15, 23, 42, 0.18)',
                        },
                    },
                }}
            >
                {selectedApp ? (
                    <>
                        <DialogTitle sx={{ px: 3, py: 2.25 }}>
                            <Box sx={{ display: 'grid', gridTemplateColumns: '88px minmax(0, 1fr) auto', gap: 2, alignItems: 'start' }}>
                                <Box sx={{ width: 88, height: 88 }}>
                                    <AppLogo app={selectedApp} />
                                </Box>
                                <Box sx={{ minWidth: 0 }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                                        <Typography sx={{ fontSize: 22, fontWeight: 600, lineHeight: 1.2, color: '#334155' }}>{selectedApp.trademark ?? selectedApp.key}</Typography>
                                        <Button
                                            component="a"
                                            href={getDocumentationUrl(selectedApp, i18n.resolvedLanguage ?? i18n.language ?? 'en')}
                                            rel="noreferrer"
                                            size="small"
                                            target="_blank"
                                            variant="contained"
                                            sx={{
                                                minWidth: 'auto',
                                                px: 1.25,
                                                py: 0.2,
                                                borderRadius: '999px',
                                                textTransform: 'none',
                                                fontSize: 13.5,
                                                fontWeight: 500,
                                                lineHeight: 1.8,
                                                boxShadow: 'none',
                                            }}
                                        >
                                            Documentation
                                        </Button>
                                        <IconButton component="a" href={getGitHubUrl(selectedApp)} rel="noreferrer" size="small" target="_blank" sx={{ p: 0.25, color: '#000' }}>
                                            <GitHubMarkIcon />
                                        </IconButton>
                                    </Box>
                                    <Typography sx={{ mt: 0.5, fontSize: 14, fontWeight: 400, color: '#475569' }}>
                                        {t('appStorePage.detail.versionLine', { version: getAppStoreVersionSummary(selectedApp) || '-' })}
                                    </Typography>
                                    <Typography sx={{ mt: 0.25, fontSize: 14, fontWeight: 400, color: '#475569' }}>
                                        {t('appStorePage.detail.requirementLine', {
                                            cpu: formatRequirement(selectedApp.vcpu),
                                            memory: formatRequirement(selectedApp.memory),
                                            storage: formatRequirement(selectedApp.storage),
                                        })}
                                    </Typography>
                                    <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 0.5, mt: 0.25, color: 'primary.main', fontSize: 14 }}>
                                        <Typography component="span" sx={{ color: '#475569', fontSize: 14, fontWeight: 400 }}>
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
                                <IconButton onClick={handleCloseModal} size="small" sx={{ color: '#94a3b8', mt: 0.5 }}>
                                    <Box component="span" sx={{ fontSize: 28, lineHeight: 1 }}>x</Box>
                                </IconButton>
                            </Box>
                        </DialogTitle>
                        <DialogContent dividers sx={{ px: 0, py: 0 }}>
                            {!isInstallMode ? (
                                <>
                                    <AppScreenshot
                                        alt={selectedApp.trademark ?? selectedApp.key ?? t('appStorePage.card.imageFallbackAlt')}
                                        app={selectedApp}
                                        locale={i18n.resolvedLanguage ?? i18n.language ?? 'en'}
                                    />

                                    <Box sx={{ px: 3, pt: 1.5, pb: 2.5 }}>
                                        <Typography sx={{ fontSize: 17, fontWeight: 700, mb: 1.25, color: '#475569' }}>{t('appStorePage.detail.overviewTitle')}</Typography>
                                        <Typography sx={{ mb: 3.25, lineHeight: 1.75, fontSize: 14, color: '#475569', fontWeight: 400 }}>
                                            {selectedApp.overview || selectedApp.summary || t('appStorePage.card.summaryFallback')}
                                        </Typography>

                                        <Typography sx={{ fontSize: 17, fontWeight: 700, mb: 1.25, color: '#475569' }}>{t('appStorePage.detail.descriptionTitle')}</Typography>
                                        <Typography sx={{ lineHeight: 1.75, whiteSpace: 'pre-wrap', fontSize: 14, color: '#475569', fontWeight: 400 }}>
                                            {selectedApp.description || selectedApp.overview || selectedApp.summary || t('appStorePage.card.summaryFallback')}
                                        </Typography>
                                    </Box>
                                </>
                            ) : (
                                <Box sx={{ display: 'grid', gap: 1.25, px: 2.5, py: 2.25 }}>
                                    <Box>
                                        <Typography sx={{ mb: 0.75, fontSize: 14, fontWeight: 400, color: '#475569' }}>{t('appStorePage.install.appIdLabel')}</Typography>
                                        <Box
                                            sx={{
                                                display: 'grid',
                                                gridTemplateColumns:
                                                    selectedApp.is_web_app && wildcardDomain
                                                        ? 'minmax(0, 1fr) 180px 74px'
                                                        : selectedApp.is_web_app
                                                            ? 'minmax(0, 1fr) 180px'
                                                            : '1fr',
                                                gap: selectedApp.is_web_app && !wildcardDomain ? 1.5 : 0,
                                                alignItems: 'center',
                                            }}
                                        >
                                            <TextField
                                                fullWidth
                                                placeholder={t('appStorePage.install.appIdHelper')}
                                                value={installName}
                                                onChange={(event) => {
                                                    setInstallName(normalizeInstallName(event.target.value))
                                                }}
                                                sx={{
                                                    '& .MuiOutlinedInput-root': {
                                                        borderRadius: selectedApp.is_web_app && wildcardDomain ? '4px 0 0 4px' : '4px',
                                                        height: 38,
                                                    },
                                                    '& .MuiInputBase-input': {
                                                        fontSize: 14,
                                                        fontWeight: 400,
                                                        color: '#334155',
                                                    },
                                                    '& .MuiInputBase-input::placeholder': {
                                                        fontSize: 14,
                                                        fontWeight: 400,
                                                        color: '#94a3b8',
                                                        opacity: 1,
                                                    },
                                                }}
                                            />
                                            {selectedApp.is_web_app && !wildcardDomain ? (
                                                <Chip
                                                    clickable
                                                    color="primary"
                                                    label={t('appStorePage.install.setGlobalDomain')}
                                                    onClick={() => navigate('/settings')}
                                                    sx={{
                                                        justifySelf: 'start',
                                                        borderRadius: '999px',
                                                        color: '#fff',
                                                        fontWeight: 500,
                                                        px: 0.75,
                                                        height: 38,
                                                        fontSize: 14,
                                                    }}
                                                />
                                            ) : null}
                                            {selectedApp.is_web_app && wildcardDomain ? (
                                                <>
                                                    <Box
                                                        sx={{
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            px: 1.25,
                                                            borderTop: '1px solid rgba(203, 213, 225, 0.9)',
                                                            borderBottom: '1px solid rgba(203, 213, 225, 0.9)',
                                                            backgroundColor: isDomainEnabled ? '#fff' : '#f8fafc',
                                                            color: isDomainEnabled ? '#64748b' : '#cbd5e1',
                                                            fontSize: 13.5,
                                                        }}
                                                    >
                                                        {domainSuffix}
                                                    </Box>
                                                    <Button
                                                        onClick={() => setIsDomainEnabled((currentValue) => !currentValue)}
                                                        sx={{
                                                            minWidth: 74,
                                                            backgroundColor: isDomainEnabled ? '#ff5f8f' : '#3b82f6',
                                                            color: '#fff',
                                                            boxShadow: '0 8px 14px rgba(255, 95, 143, 0.18)',
                                                            borderRadius: '0 4px 4px 0',
                                                            '&:hover': {
                                                                backgroundColor: isDomainEnabled ? '#fb4d83' : '#2563eb',
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

                                    {selectedApp.is_web_app && !isCustomDomainVisible ? (
                                        <Box>
                                            <Chip
                                                clickable
                                                color="primary"
                                                label={t('appStorePage.install.addDomain')}
                                                onClick={() => setIsCustomDomainVisible((currentValue) => !currentValue)}
                                                sx={{
                                                    borderRadius: '999px',
                                                    color: '#fff',
                                                    fontWeight: 500,
                                                    px: 0.5,
                                                    height: 34,
                                                }}
                                            />
                                        </Box>
                                    ) : null}

                                    {selectedApp.is_web_app && isCustomDomainVisible ? (
                                        <Box>
                                            <Typography sx={{ mb: 0.75, fontSize: 14, fontWeight: 400, color: '#475569' }}>{t('appStorePage.install.customDomainLabel')}</Typography>
                                            <Box sx={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 84px', gap: 1 }}>
                                                <TextField
                                                    fullWidth
                                                    placeholder={t('appStorePage.install.customDomainPlaceholder')}
                                                    value={customDomain}
                                                    onChange={(event) => {
                                                        setCustomDomain(event.target.value)
                                                    }}
                                                    sx={{
                                                        '& .MuiOutlinedInput-root': {
                                                            borderRadius: '4px',
                                                            height: 38,
                                                        },
                                                        '& .MuiInputBase-input': {
                                                            fontSize: 14,
                                                            fontWeight: 400,
                                                            color: '#334155',
                                                        },
                                                    }}
                                                />
                                                <Button
                                                    color="error"
                                                    onClick={() => {
                                                        setIsCustomDomainVisible(false)
                                                        setCustomDomain('')
                                                    }}
                                                    sx={{ minWidth: 84, boxShadow: 'none' }}
                                                    variant="contained"
                                                >
                                                    {t('appStorePage.actions.delete')}
                                                </Button>
                                            </Box>
                                        </Box>
                                    ) : null}

                                    <Box>
                                        <Typography sx={{ mb: 0.75, fontSize: 14, fontWeight: 400, color: '#475569' }}>{t('appStorePage.install.versionLabel')}</Typography>
                                        <TextField
                                            select
                                            fullWidth
                                            value={selectedVersion}
                                            onChange={(event) => {
                                                setSelectedVersion(event.target.value)
                                            }}
                                            sx={{
                                                '& .MuiOutlinedInput-root': {
                                                    borderRadius: '4px',
                                                    height: 38,
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
                                            {getAppStoreInstallDistributions(selectedApp).flatMap((distribution) =>
                                                distribution.versions.map((version) => (
                                                    <MenuItem key={`${distribution.dist}-${version}`} value={version}>
                                                        {version}
                                                    </MenuItem>
                                                )),
                                            )}
                                        </TextField>
                                    </Box>

                                    {Object.entries(installSettings).map(([key, value]) => (
                                        <Box key={key}>
                                            <Typography sx={{ mb: 0.75, fontSize: 14, fontWeight: 400, color: '#475569' }}>{getInstallSettingLabel(key, t, i18n.resolvedLanguage ?? i18n.language ?? 'en')}</Typography>
                                            <TextField
                                                fullWidth
                                                value={value}
                                                onChange={(event) => {
                                                    setInstallSettings((currentValue) => ({
                                                        ...currentValue,
                                                        [key]: event.target.value,
                                                    }))
                                                }}
                                                sx={{
                                                    '& .MuiOutlinedInput-root': {
                                                        borderRadius: '4px',
                                                        height: 38,
                                                    },
                                                    '& .MuiInputBase-input': {
                                                        fontSize: 14,
                                                        fontWeight: 400,
                                                        color: '#334155',
                                                    },
                                                }}
                                            />
                                        </Box>
                                    ))}

                                </Box>
                            )}
                        </DialogContent>
                        <DialogActions sx={{ px: 2.5, py: 2, borderTop: '1px solid rgba(226, 232, 240, 0.9)' }}>
                            <Button
                                color="inherit"
                                onClick={handleCloseModal}
                                variant="contained"
                                sx={{
                                    minWidth: 68,
                                    backgroundColor: '#eef2f7',
                                    color: '#475569',
                                    borderRadius: 0,
                                    boxShadow: 'none',
                                    '&:hover': { backgroundColor: '#e2e8f0', boxShadow: 'none' },
                                }}
                            >
                                {t('appStorePage.actions.close')}
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
            </Dialog>

            <Snackbar
                autoHideDuration={4000}
                onClose={() => {
                    setInstallFeedback(null)
                    setInstallError(null)
                }}
                open={Boolean(installFeedback) || Boolean(installError)}
                anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            >
                {installError ? (
                    <Alert severity="error" variant="filled" sx={{ width: '100%' }}>
                        {installError}
                    </Alert>
                ) : installFeedback ? (
                    <Alert severity={installFeedback.severity} variant="filled" sx={{ width: '100%' }}>
                        {installFeedback.message}
                    </Alert>
                ) : (
                    <Box />
                )}
            </Snackbar>
        </Box>
    )
}