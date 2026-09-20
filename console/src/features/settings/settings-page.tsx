import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    IconButton,
    List,
    ListItemButton,
    Stack,
    Step,
    StepLabel,
    Stepper,
    Switch,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router-dom'

import { useAppColorMode } from '../../app/providers/color-mode'
import { useProductAuth } from '../product-auth/product-auth-provider'
import { getSurfaceFieldSx } from '../../shared/design-system/form-field-sx'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { getSurfacePalette } from '../../shared/design-system/surface-theme'
import { SurfaceDialog, SurfaceFeedbackToast } from '../../shared/design-system/standard-surfaces'
import { useConnectionUnavailable } from '../../shared/connection/connection-provider'
import { isPlatformUnavailableError } from '../../shared/lib/api-error'
import {
    fetchUpgradeLog,
    fetchUpgradeStatus,
    getUpgradeStatusRefetchInterval,
    retryUpgrade,
    setUpgradeInProgress,
    UPGRADE_SECTION_HASH,
    UPGRADE_STATUS_QUERY_KEY,
} from '../../shared/upgrade-status'
import { checkUpgrade, rememberCompletedUpgrade } from '../../shared/upgrade-status'
import type { UpgradeLog, UpgradeStatus } from '../../shared/upgrade-status'
import './settings-page.css'

// Lines requested from the upgrade log endpoint; reaching this count means the tail was cut off.
const UPGRADE_LOG_TAIL = 200
const COMPLETION_VERIFY_DELAY_MS = 1_000

// The ticket / support desk is the same destination the shell footer links to.
function UPGRADE_SUPPORT_URL(isChinese: boolean): string {
    return isChinese
        ? 'https://support.websoft9.com/docs/helpdesk/#contact'
        : 'https://support.websoft9.com/en/docs/helpdesk#contact'
}

type SettingsSummaryItem = {
    group: string
    key: string
    value: string
    sensitive: boolean
    masked: boolean
    editable: boolean
    metadata?: {
        version?: string
        edition_key?: string
        edition_names?: Record<string, string>
        default_value?: string
        cert_path?: string
        key_path?: string
        default_cert_path?: string
        default_key_path?: string
        default_certificate?: string
        certificate_validity_days?: string
        cert_expiry?: string
        cert_subject_cn?: string
    } | null
}

type PlatformGatewayUpdateRequest = {
    bound_domain: string
    https_enabled: string
    force_https: string
    ssl_cert: string
    ssl_key: string
}

type SettingsSummaryGroup = {
    id: string
    items: SettingsSummaryItem[]
}

type SettingsSummaryResponse = {
    groups: SettingsSummaryGroup[]
}

type SettingsError = Error & {
    statusCode?: number
}

type SettingsModuleId = 'app-domain' | 'app-mirror' | 'app-ports' | 'platform-brand' | 'platform-domain' | 'platform-system'

type SettingsModuleGroup = 'applications' | 'platform'

type SettingsModule = {
    id: SettingsModuleId
    group: SettingsModuleGroup
    titleKey: string
    descriptionKey: string
}

async function fetchSettingsSummary() {
    const response = await fetch('/api/settings/summary', {
        credentials: 'include',
        headers: {
            Accept: 'application/json',
        },
    })

    if (!response.ok) {
        const error = new Error(`Failed to load settings summary: ${response.status}`) as SettingsError
        error.statusCode = response.status
        throw error
    }

    return (await response.json()) as SettingsSummaryResponse
}

async function updateSetting(section: string, key: string, value: string) {
    const response = await fetch(`/api/settings/${encodeURIComponent(section)}?key=${encodeURIComponent(key)}&value=${encodeURIComponent(value)}`, {
        method: 'PUT',
        credentials: 'include',
        headers: {
            Accept: 'application/json',
        },
    })

    if (!response.ok) {
        let message = `Failed to update ${section}.${key}: ${response.status}`
        try {
            const payload = (await response.json()) as { details?: string; message?: string }
            message = payload.details || payload.message || message
        } catch {
            // Keep the fallback message.
        }

        throw new Error(message)
    }
}

type ContentScopeRect = {
    top: number
    left: number
    width: number
    height: number
}

class UpgradeRequestError extends Error {
    readonly status: number

    constructor(status: number, message: string) {
        super(message)
        this.name = 'UpgradeRequestError'
        this.status = status
    }
}

async function prepareUpgrade(): Promise<UpgradeStatus> {
    const response = await fetch('/api/settings/upgrade/prepare', {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
        const payload = await response.json().catch(() => ({})) as { details?: string; message?: string }
        throw new UpgradeRequestError(response.status, payload.details || payload.message || `Failed to prepare upgrade: ${response.status}`)
    }
    return (await response.json()) as UpgradeStatus
}

async function applyUpgrade(): Promise<UpgradeStatus> {
    const response = await fetch('/api/settings/upgrade/apply', {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
        const payload = await response.json().catch(() => ({})) as { details?: string; message?: string }
        throw new Error(payload.details || payload.message || `Failed to start upgrade: ${response.status}`)
    }
    return (await response.json()) as UpgradeStatus
}

async function updatePlatformGatewaySettings(payload: PlatformGatewayUpdateRequest) {
    const response = await fetch('/api/settings/platform_gateway/apply', {
        method: 'PUT',
        credentials: 'include',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    })

    if (!response.ok) {
        let message = `Failed to update platform gateway settings: ${response.status}`
        try {
            // Try JSON first
            const text = await response.text()
            if (text) {
                try {
                    const errorPayload = JSON.parse(text) as { details?: string; message?: string }
                    message = errorPayload.details || errorPayload.message || message
                } catch {
                    // Not JSON — use raw text if short enough
                    if (text.length < 200) message = text
                }
            }
        } catch {
            // Keep the fallback message.
        }

        throw new Error(message)
    }
}

const PLATFORM_GATEWAY_BOUND_DOMAIN_DRAFT_KEY = 'platform_gateway.bound_domain'
const PLATFORM_GATEWAY_CERT_DRAFT_KEY = 'platform_gateway.ssl_cert'
const PLATFORM_GATEWAY_KEY_DRAFT_KEY = 'platform_gateway.ssl_key'
const PLATFORM_GATEWAY_HTTPS_DRAFT_KEY = 'platform_gateway.https_enabled'
const PLATFORM_GATEWAY_FORCE_HTTPS_DRAFT_KEY = 'platform_gateway.force_https'
const PLATFORM_GATEWAY_LETSENCRYPT_EMAIL_DRAFT_KEY = 'platform_gateway.letsencrypt_email'
const PLATFORM_GATEWAY_UPLOAD_CERT_PEM_DRAFT_KEY = 'platform_gateway.upload_cert_pem'
const PLATFORM_GATEWAY_UPLOAD_KEY_PEM_DRAFT_KEY = 'platform_gateway.upload_key_pem'
const PLATFORM_GATEWAY_UPLOAD_INTERMEDIATE_PEM_DRAFT_KEY = 'platform_gateway.upload_intermediate_pem'
const PORT_RANGE_START_DRAFT_SUFFIX = ':start'
const PORT_RANGE_END_DRAFT_SUFFIX = ':end'
const PORTS_SECTION_HASH = '#application-ports'

function parsePortRangeValue(value: string | undefined) {
    const match = /^\s*(\d{1,5})\s*-\s*(\d{1,5})\s*$/.exec(value ?? '')
    if (!match) {
        return { start: (value ?? '').trim(), end: '' }
    }
    return { start: match[1], end: match[2] }
}

const SETTINGS_MODULES: SettingsModule[] = [
    {
        id: 'app-domain',
        group: 'applications',
        titleKey: 'settingsPage.modules.appDomain.title',
        descriptionKey: 'settingsPage.modules.appDomain.description',
    },
    {
        id: 'app-ports',
        group: 'applications',
        titleKey: 'settingsPage.modules.appPorts.title',
        descriptionKey: 'settingsPage.modules.appPorts.description',
    },
    {
        id: 'app-mirror',
        group: 'applications',
        titleKey: 'settingsPage.modules.appMirror.title',
        descriptionKey: 'settingsPage.modules.appMirror.description',
    },
    {
        id: 'platform-brand',
        group: 'platform',
        titleKey: 'settingsPage.modules.platformBrand.title',
        descriptionKey: 'settingsPage.modules.platformBrand.description',
    },
    {
        id: 'platform-domain',
        group: 'platform',
        titleKey: 'settingsPage.modules.platformDomain.title',
        descriptionKey: 'settingsPage.modules.platformDomain.description',
    },
    {
        id: 'platform-system',
        group: 'platform',
        titleKey: 'settingsPage.modules.platformSystem.title',
        descriptionKey: 'settingsPage.modules.platformSystem.description',
    },
]

export function SettingsPage() {
    const { t, i18n } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const { status: authStatus } = useProductAuth()
    const isConnectionUnavailable = useConnectionUnavailable()
    const location = useLocation()
    const isDarkMode = colorMode === 'dark'
    const surfacePalette = getSurfacePalette(isDarkMode)
    const settingsFieldSx = getSurfaceFieldSx(surfacePalette)
    const [drafts, setDrafts] = useState<Record<string, string>>({})
    const [mirrorPendingInputs, setMirrorPendingInputs] = useState<Record<string, string>>({})
    const [activeModule, setActiveModule] = useState<SettingsModuleId>('app-domain')
    const [feedback, setFeedback] = useState<{ severity: 'success' | 'error' | 'info'; message: string } | null>(null)
    const [toastOpen, setToastOpen] = useState(false)
    const [savingModule, setSavingModule] = useState<SettingsModuleId | null>(null)
    const [reuseLogo, setReuseLogo] = useState<boolean>(false)
    const [useDomain, setUseDomain] = useState<boolean>(false)
    const [uploadingLogo, setUploadingLogo] = useState(false)
    const [uploadingBackground, setUploadingBackground] = useState(false)
    const [letsEncryptEmail, setLetsEncryptEmail] = useState('')
    const [certAction, setCertAction] = useState<'letsencrypt' | 'existing' | 'upload'>('letsencrypt')
    const [certValidityDays, setCertValidityDays] = useState(3650)
    const [certPem, setCertPem] = useState('')
    const [keyPem, setKeyPem] = useState('')
    const [intermediatePem, setIntermediatePem] = useState('')
    const [certName, setCertName] = useState('')
    const [showCertConfig, setShowCertConfig] = useState(false)
    const certPemFileRef = useRef<HTMLInputElement | null>(null)
    const keyPemFileRef = useRef<HTMLInputElement | null>(null)
    const intermediatePemFileRef = useRef<HTMLInputElement | null>(null)
    const logoUploadRef = useRef<HTMLInputElement | null>(null)
    const faviconUploadRef = useRef<HTMLInputElement | null>(null)
    const backgroundUploadRef = useRef<HTMLInputElement | null>(null)
    const [activeApplyRunId, setActiveApplyRunId] = useState<string | null>(null)
    // One-shot reload after a completed upgrade; kept in a ref so the status effect above can
    // re-run without cancelling it.
    const upgradeReloadTimerRef = useRef<number | null>(null)
    const completionVerifyTimerRef = useRef<number | null>(null)
    const sawVerificationPhaseRef = useRef(false)
    const completionScheduledRef = useRef(false)
    // The overlay cannot read progress from the backend while the platform container is being
    // replaced, so it falls back to a phase timeline driven by elapsed time.
    const [applyStartedAt, setApplyStartedAt] = useState<number | null>(null)
    const [applyElapsedSeconds, setApplyElapsedSeconds] = useState(0)
    // Keeps the mask on screen between "upgrade finished" and the reload, so the page never
    // flashes back to an interactive console for a few seconds.
    const [applyFinishing, setApplyFinishing] = useState(false)
    const { data, error, isLoading, refetch } = useQuery<SettingsSummaryResponse, SettingsError>({
        queryKey: ['settings-summary'],
        queryFn: fetchSettingsSummary,
        staleTime: 5_000,
    })

    const {
        data: upgradeStatus,
        error: upgradeStatusError,
        isLoading: isUpgradeStatusLoading,
        isFetching: isUpgradeStatusFetching,
        refetch: refetchUpgradeStatus,
    } = useQuery<UpgradeStatus, Error>({
        queryKey: UPGRADE_STATUS_QUERY_KEY,
        queryFn: fetchUpgradeStatus,
        staleTime: 60_000,
        // The endpoint sits behind the gateway session, so it must not run before the operator
        // is authenticated: a 401 here sticks until something retries the query.
        enabled: Boolean(authStatus?.enabled && authStatus?.authenticated),
        refetchInterval: (query) => getUpgradeStatusRefetchInterval(query.state.data),
    })

    const [copied, setCopied] = useState(false)
    const [preparingUpgrade, setPreparingUpgrade] = useState(false)
    // Only a download started from this page load may surface a failure: a reload clears the
    // marker, so the operator always gets back to a plain "Download update" action while the
    // record itself stays available through the API and the upgrade logs.
    const [initiatedUpgradeRunId, setInitiatedUpgradeRunId] = useState<string | null>(null)
    const [applyConfirmationOpen, setApplyConfirmationOpen] = useState(false)
    const [applyingUpgrade, setApplyingUpgrade] = useState(false)
    const [upgradeManualOpen, setUpgradeManualOpen] = useState(false)
    const [checkingUpgrade, setCheckingUpgrade] = useState(false)
    // A failed upgrade keeps only the essentials: what happened, why, the log, and a way to reach
    // support. Everything else belongs to the normal upgrade rows.
    const [upgradeLogOpen, setUpgradeLogOpen] = useState(false)
    // Set when a retry had to download the release again: the upgrade then starts by itself once
    // the release is staged, so a retry is always a single operator action.
    const [autoApplyPending, setAutoApplyPending] = useState(false)
    const [upgradeLog, setUpgradeLog] = useState<UpgradeLog | null>(null)
    const [upgradeLogLoading, setUpgradeLogLoading] = useState(false)
    const [upgradeLogFailed, setUpgradeLogFailed] = useState(false)
    const [upgradeLogCopied, setUpgradeLogCopied] = useState(false)

    useEffect(() => {
        const terminalStates = new Set(['completed', 'degraded', 'rolled_back', 'rollback_failed', 'apply_interrupted'])
        const isActiveRun = activeApplyRunId === 'pending' || upgradeStatus?.run_id === activeApplyRunId
        if (isActiveRun && upgradeStatus?.state && terminalStates.has(upgradeStatus.state)) {
            if (upgradeStatus.state === 'completed') {
                if (completionScheduledRef.current) {
                    return
                }
                completionScheduledRef.current = true
                // Report the version we actually installed: the channel may already have moved on.
                const installedVersion = String(upgradeStatus.target_version || upgradeStatus.latest_version || '')
                rememberCompletedUpgrade(installedVersion)
                const finishUpgrade = () => {
                    setApplyFinishing(true)
                    upgradeReloadTimerRef.current = window.setTimeout(() => window.location.replace('/'), 3_000)
                }
                if (!sawVerificationPhaseRef.current) {
                    completionVerifyTimerRef.current = window.setTimeout(finishUpgrade, COMPLETION_VERIFY_DELAY_MS)
                } else {
                    finishUpgrade()
                }
                return
            }
            setActiveApplyRunId(null)
            // The run is over: the console goes back to reporting connection problems normally.
            setUpgradeInProgress(false)
        }
    }, [activeApplyRunId, upgradeStatus?.run_id, upgradeStatus?.state, upgradeStatus?.latest_version, upgradeStatus?.target_version, t])

    const settingsPageShellRef = useRef<HTMLDivElement | null>(null)
    const [upgradeDialogScopeRect, setUpgradeDialogScopeRect] = useState<ContentScopeRect | null>(null)

    useEffect(() => () => {
        if (completionVerifyTimerRef.current !== null) {
            window.clearTimeout(completionVerifyTimerRef.current)
        }
        if (upgradeReloadTimerRef.current !== null) {
            window.clearTimeout(upgradeReloadTimerRef.current)
        }
    }, [])

    useEffect(() => {
        if (!autoApplyPending || upgradeStatus?.state !== 'ready') {
            return
        }
        setAutoApplyPending(false)
        setApplyFinishing(false)
        setApplyStartedAt(Date.now())
        setApplyElapsedSeconds(0)
        sawVerificationPhaseRef.current = false
        completionScheduledRef.current = false
        setActiveApplyRunId(upgradeStatus.run_id ?? 'pending')
        setUpgradeInProgress(true)
        void applyUpgrade()
            .then(() => refetchUpgradeStatus())
            .catch(() => {
                setActiveApplyRunId(null)
                setUpgradeInProgress(false)
            })
    }, [autoApplyPending, upgradeStatus?.state, upgradeStatus?.run_id, refetchUpgradeStatus])

    useEffect(() => {
        // The clock follows the run itself, not the button this tab pressed: after a reload the
        // marker is gone but the upgrade is still on screen and must keep counting.
        if (applyStartedAt === null) {
            return
        }
        setApplyElapsedSeconds(Math.max(0, Math.round((Date.now() - applyStartedAt) / 1000)))
        const timer = window.setInterval(() => {
            setApplyElapsedSeconds(Math.max(0, Math.round((Date.now() - applyStartedAt) / 1000)))
        }, 1_000)
        return () => window.clearInterval(timer)
    }, [applyStartedAt])

    /**
     * The backend owns the truth about a running upgrade: it may have been started here, in another
     * tab, or before this page was reloaded. Locking the console and muting the connection banner
     * therefore follows the reported state, not just the button this tab happened to press.
     */
    useEffect(() => {
        if (upgradeStatus?.state === 'applying') {
            if (upgradeStatus.phase === 'verify') {
                sawVerificationPhaseRef.current = true
            }
            setUpgradeInProgress(true)
            setApplyStartedAt((current) => current ?? Date.now())
            return
        }
        if (!activeApplyRunId) {
            setUpgradeInProgress(false)
        }
    }, [upgradeStatus?.state, activeApplyRunId])

    const reportedApplyPhaseIndex = upgradeStatus?.phase === 'prepare'
        ? 0
        : upgradeStatus?.phase === 'replace'
            ? 1
            : upgradeStatus?.phase === 'verify'
                ? 2
                : null
    // Older release artifacts do not report a phase. Keep their conservative time-based display
    // until every supported Runner writes an explicit stage.
    const applyPhaseIndex = reportedApplyPhaseIndex ?? (applyElapsedSeconds < 8 ? 0 : applyElapsedSeconds < 75 ? 1 : 2)
    const applyPhaseKeys = ['settingsPage.upgrade.phases.prepare', 'settingsPage.upgrade.phases.replace', 'settingsPage.upgrade.phases.verify']

    // Keep the manual-upgrade dialog inside the workspace area so it never covers the
    // navigation, matching the other scoped dialogs of the console.
    useLayoutEffect(() => {
        const shellElement = settingsPageShellRef.current
        const mainElement = shellElement?.closest('main')
        if (!shellElement || !(mainElement instanceof HTMLElement)) {
            return
        }

        const updateScopeRect = () => {
            const rect = mainElement.getBoundingClientRect()
            setUpgradeDialogScopeRect({ top: rect.top, left: rect.left, width: rect.width, height: rect.height })
        }

        updateScopeRect()

        const resizeObserver = new ResizeObserver(() => updateScopeRect())
        resizeObserver.observe(mainElement)
        window.addEventListener('resize', updateScopeRect)

        return () => {
            resizeObserver.disconnect()
            window.removeEventListener('resize', updateScopeRect)
        }
    }, [isLoading])

    const upgradeDialogCancelButtonSx = {
        minWidth: 68,
        borderRadius: 0,
        boxShadow: 'none',
        border: `1px solid ${surfacePalette.borderStrong}`,
        backgroundColor: surfacePalette.actionBg,
        color: surfacePalette.subtleText,
        '&:hover': {
            backgroundColor: surfacePalette.actionHover,
            color: surfacePalette.text,
            boxShadow: 'none',
        },
    }

    const upgradeDialogPrimaryButtonSx = {
        minWidth: 68,
        borderRadius: 0,
        boxShadow: 'none',
        backgroundColor: surfacePalette.accent,
        color: surfacePalette.accentContrast,
        '&:hover': {
            backgroundColor: surfacePalette.accent,
            filter: 'brightness(0.94)',
            boxShadow: 'none',
        },
    }

    useEffect(() => {
        if (location.hash === UPGRADE_SECTION_HASH) {
            setActiveModule('platform-system')
        } else if (location.hash === PORTS_SECTION_HASH) {
            setActiveModule('app-ports')
        }
    }, [location.hash])

    const items = data?.groups.flatMap((group) => group.items) ?? []
    const boundDomainItem = items.find((item) => item.group === 'platform_gateway' && item.key === 'bound_domain') ?? null
    const globalDomainItem = items.find((item) => item.group === 'domain' && item.key === 'wildcard_domain') ?? null
    const httpsItem = items.find((item) => item.group === 'platform_gateway' && item.key === 'https_enabled') ?? null
    const forceHttpsItem = items.find((item) => item.group === 'platform_gateway' && item.key === 'force_https') ?? null
    const mirrorItem = items.find((item) => item.group === 'docker_mirror' && item.key === 'url') ?? null
    const portRangeItem = items.find((item) => item.group === 'port_allocation' && item.key === 'range') ?? null
    const brandTitleItem = items.find((item) => item.group === 'platform_brand' && item.key === 'title') ?? null
    const brandLogoItem = items.find((item) => item.group === 'platform_brand' && item.key === 'logo_url') ?? null
    const brandFaviconItem = items.find((item) => item.group === 'platform_brand' && item.key === 'favicon_url') ?? null
    const brandLoginBgItem = items.find((item) => item.group === 'platform_brand' && item.key === 'login_background') ?? null
    const brandCopyrightItem = items.find((item) => item.group === 'platform_brand' && item.key === 'copyright_text') ?? null
    const activeModuleConfig = SETTINGS_MODULES.find((module) => module.id === activeModule) ?? SETTINGS_MODULES[0]
    const currentSslCert = httpsItem?.metadata?.cert_path?.trim() || ''
    const currentSslKey = httpsItem?.metadata?.key_path?.trim() || ''
    const certExpiry = httpsItem?.metadata?.cert_expiry || ''
    const certSubjectCn = httpsItem?.metadata?.cert_subject_cn || ''
    const httpsEnabled = (drafts[PLATFORM_GATEWAY_HTTPS_DRAFT_KEY] ?? httpsItem?.value ?? 'false') === 'true'
    const forceHttpsEnabled = httpsEnabled && (drafts[PLATFORM_GATEWAY_FORCE_HTTPS_DRAFT_KEY] ?? forceHttpsItem?.value ?? 'false') === 'true'
    const boundDomainValue = drafts[PLATFORM_GATEWAY_BOUND_DOMAIN_DRAFT_KEY] ?? boundDomainItem?.value ?? ''
    // Derived cert state — used by both the save logic and the card render
    const hasCert = !!(currentSslCert && currentSslKey)
    const isDefaultCert = httpsItem?.metadata?.default_certificate === 'true'
    const certMatchesDomain = certSubjectCn
        ? (() => {
            const domain = (boundDomainValue || boundDomainItem?.value || '').toLowerCase()
            const cn = certSubjectCn.toLowerCase()
            if (!domain || !cn) return false
            if (domain === cn) return true
            // Handle wildcard certs: *.example.com matches sub.example.com
            if (cn.startsWith('*.')) {
                const suffix = cn.slice(1) // ".example.com"
                return domain.endsWith(suffix) && domain.indexOf('.') !== domain.lastIndexOf('.')
            }
            return false
        })()
        : false
    const existingValidCert = useDomain && hasCert && !isDefaultCert && certMatchesDomain
    const certMismatch = useDomain && hasCert && !isDefaultCert && !!certSubjectCn && !certMatchesDomain
    // Auto-expand the config section when there's no usable cert yet
    // (no files at all, or only the auto-generated self-signed cert).
    const shouldAutoExpand = !hasCert || isDefaultCert
    // Current cert/key — use draft if set, otherwise current config
    const sslCert = (drafts[PLATFORM_GATEWAY_CERT_DRAFT_KEY] ?? currentSslCert).trim()
    const sslKey = (drafts[PLATFORM_GATEWAY_KEY_DRAFT_KEY] ?? currentSslKey).trim()
    const navGroups = useMemo(
        () => [
            {
                id: 'applications' as const,
                title: t('settingsPage.navigation.groups.applications'),
                modules: SETTINGS_MODULES.filter((module) => module.group === 'applications'),
            },
            {
                id: 'platform' as const,
                title: t('settingsPage.navigation.groups.platform'),
                modules: SETTINGS_MODULES.filter((module) => module.group === 'platform'),
            },
        ],
        [t],
    )

    useEffect(() => {
        const logoVal = brandLogoItem?.value ?? ''
        const favVal = brandFaviconItem?.value ?? ''
        if (logoVal && favVal === logoVal) {
            setReuseLogo(true)
        }
    }, [brandLogoItem?.value, brandFaviconItem?.value])

    useEffect(() => {
        const currentDomain = boundDomainItem?.value ?? ''
        setUseDomain(Boolean(currentDomain.trim()))
    }, [boundDomainItem?.value])

    function getDraftKey(item: SettingsSummaryItem) {
        return `${item.group}.${item.key}`
    }

    function hasDraftValue(draftKey: string) {
        return Object.prototype.hasOwnProperty.call(drafts, draftKey)
    }

    function setDraftValue(draftKey: string, value: string) {
        setDrafts((currentDrafts) => ({
            ...currentDrafts,
            [draftKey]: value,
        }))
    }

    function clearDraftKeys(draftKeys: string[]) {
        if (!draftKeys.length) {
            return
        }

        setDrafts((currentDrafts) => {
            const nextDrafts = { ...currentDrafts }
            for (const draftKey of draftKeys) {
                delete nextDrafts[draftKey]
            }
            return nextDrafts
        })

        setMirrorPendingInputs((currentInputs) => {
            const nextInputs = { ...currentInputs }
            for (const draftKey of draftKeys) {
                delete nextInputs[draftKey]
            }
            return nextInputs
        })
    }

    function isPlatformBrandLogoUrl(value: string) {
        const trimmed = value.trim()
        if (!trimmed) {
            return false
        }

        if (trimmed.startsWith('/')) {
            return true
        }

        try {
            const parsed = new URL(trimmed)
            return parsed.protocol === 'http:' || parsed.protocol === 'https:'
        } catch {
            return false
        }
    }

    function emitPlatformBrandUpdate(key: string, value: string) {
        window.dispatchEvent(
            new CustomEvent('websoft9:platform-brand-updated', {
                detail: {
                    key,
                    value,
                },
            }),
        )
    }

    function parseMirrorEntries(value: string) {
        return value
            .split(/\r?\n|,/)
            .map((item) => item.trim())
            .filter(Boolean)
    }

    function isMirrorManifestUrl(value: string) {
        const trimmed = value.trim()
        if (!trimmed || /[\r\n,]/.test(trimmed)) {
            return false
        }

        try {
            const parsed = new URL(trimmed)
            return parsed.pathname.endsWith('.json')
        } catch {
            return false
        }
    }

    function getModuleItems(moduleId: SettingsModuleId) {
        if (moduleId === 'app-domain') {
            return globalDomainItem ? [globalDomainItem] : []
        }

        if (moduleId === 'app-mirror') {
            return mirrorItem ? [mirrorItem] : []
        }

        if (moduleId === 'app-ports') {
            return portRangeItem ? [portRangeItem] : []
        }

        if (moduleId === 'platform-brand') {
            return [brandTitleItem, brandLogoItem, brandFaviconItem, brandLoginBgItem, brandCopyrightItem].filter((item): item is SettingsSummaryItem => item !== null)
        }

        if (moduleId === 'platform-domain') {
            return boundDomainItem ? [boundDomainItem] : []
        }

        return []
    }

    function getModuleDraftKeys(moduleId: SettingsModuleId) {
        if (moduleId === 'platform-domain') {
            return [
                PLATFORM_GATEWAY_BOUND_DOMAIN_DRAFT_KEY,
                PLATFORM_GATEWAY_HTTPS_DRAFT_KEY,
                PLATFORM_GATEWAY_FORCE_HTTPS_DRAFT_KEY,
                PLATFORM_GATEWAY_CERT_DRAFT_KEY,
                PLATFORM_GATEWAY_KEY_DRAFT_KEY,
                PLATFORM_GATEWAY_LETSENCRYPT_EMAIL_DRAFT_KEY,
                PLATFORM_GATEWAY_UPLOAD_CERT_PEM_DRAFT_KEY,
                PLATFORM_GATEWAY_UPLOAD_KEY_PEM_DRAFT_KEY,
                PLATFORM_GATEWAY_UPLOAD_INTERMEDIATE_PEM_DRAFT_KEY,
            ]
        }

        if (moduleId === 'app-ports' && portRangeItem) {
            const draftKey = getDraftKey(portRangeItem)
            return [`${draftKey}${PORT_RANGE_START_DRAFT_SUFFIX}`, `${draftKey}${PORT_RANGE_END_DRAFT_SUFFIX}`]
        }

        return getModuleItems(moduleId).map(getDraftKey)
    }

    function resetActiveModuleDrafts() {
        clearDraftKeys(getModuleDraftKeys(activeModule))
        setFeedback(null)
    }

    function validateItemValue(item: SettingsSummaryItem, nextValue: string) {
        const trimmed = nextValue.trim()

        if (!trimmed && item.group !== 'domain' && item.group !== 'docker_mirror' && !(item.group === 'platform_brand' && (item.key === 'login_background' || item.key === 'copyright_text'))) {
            return t('settingsPage.validation.required')
        }

        if (item.group === 'domain' && item.key === 'wildcard_domain' && trimmed) {
            if (/^https?:\/\//i.test(trimmed)) {
                return t('settingsPage.validation.domainNoProtocol')
            }
        }

        if (item.group === 'docker_mirror' && item.key === 'url') {
            const mirrorEntries = parseMirrorEntries(nextValue)
            if (!isMirrorManifestUrl(nextValue) && !mirrorEntries.length) {
                return null
            }
        }

        if (item.group === 'platform_brand' && (item.key === 'logo_url' || item.key === 'favicon_url' || item.key === 'login_background') && trimmed && !isPlatformBrandLogoUrl(nextValue)) {
            return t('settingsPage.validation.logoUrl')
        }

        return null
    }

    async function saveSimpleModule(moduleId: SettingsModuleId) {
        if (moduleId === 'app-ports' && portRangeItem) {
            const draftKey = getDraftKey(portRangeItem)
            const startDraftKey = `${draftKey}${PORT_RANGE_START_DRAFT_SUFFIX}`
            const endDraftKey = `${draftKey}${PORT_RANGE_END_DRAFT_SUFFIX}`
            const currentRange = parsePortRangeValue(portRangeItem.value)
            const startValue = (drafts[startDraftKey] ?? currentRange.start).trim()
            const endValue = (drafts[endDraftKey] ?? currentRange.end).trim()

            if (!/^\d{1,5}$/.test(startValue) || !/^\d{1,5}$/.test(endValue)) {
                throw new Error(t('settingsPage.validation.portInvalid'))
            }

            const startPort = Number(startValue)
            const endPort = Number(endValue)
            if (startPort < 1 || startPort > 65535 || endPort < 1 || endPort > 65535) {
                throw new Error(t('settingsPage.validation.portInvalid'))
            }

            if (startPort > endPort) {
                throw new Error(t('settingsPage.validation.portRangeBounds'))
            }

            const nextRange = `${startPort}-${endPort}`
            if (nextRange !== portRangeItem.value.trim()) {
                await updateSetting(portRangeItem.group, portRangeItem.key, nextRange)
                await refetch()
            }
            clearDraftKeys([startDraftKey, endDraftKey])
            return
        }

        const moduleItems = getModuleItems(moduleId)
        const changedEntries = moduleItems
            .map((item) => {
                const draftKey = getDraftKey(item)
                const nextValue = drafts[draftKey] ?? item.value
                return {
                    item,
                    draftKey,
                    nextValue,
                    changed: hasDraftValue(draftKey) && nextValue !== item.value,
                }
            })
            .filter((entry) => entry.changed)

        for (const entry of changedEntries) {
            const validationError = validateItemValue(entry.item, entry.nextValue)
            if (validationError) {
                throw new Error(validationError)
            }
        }

        if (!changedEntries.length) {
            return
        }

        for (const entry of changedEntries) {
            await updateSetting(entry.item.group, entry.item.key, entry.nextValue)
        }

        await refetch()

        for (const entry of changedEntries) {
            if (entry.item.group === 'platform_brand') {
                emitPlatformBrandUpdate(entry.item.key, entry.nextValue)
            }
        }

        clearDraftKeys(changedEntries.map((entry) => entry.draftKey))
    }

    async function handleSavePlatformDomainModule() {
        const nextHttpsEnabled = httpsEnabled ? 'true' : 'false'
        const nextForceHttps = httpsEnabled && forceHttpsEnabled ? 'true' : 'false'
        let nextSslCert = sslCert
        let nextSslKey = sslKey

        // Domain validation
        if (useDomain) {
            const domain = boundDomainValue.trim()
            if (!domain) {
                throw new Error(t('settingsPage.platformSsl.domainRequired'))
            }
            // Reject protocol prefixes and invalid characters
            if (domain.includes('://') || domain.includes('/') || domain.includes(' ')) {
                throw new Error(t('settingsPage.platformSsl.domainInvalid'))
            }
            // Must contain at least one dot for a valid domain
            if (!domain.includes('.')) {
                throw new Error(t('settingsPage.platformSsl.domainInvalid'))
            }
        }

        if (httpsEnabled) {
            if (!useDomain) {
                // IP mode: auto-generate self-signed cert if needed
                if (!nextSslCert || !nextSslKey) {
                    const resp = await fetch('/api/settings/platform_gateway/generate-self-signed-cert', {
                        method: 'POST',
                        credentials: 'include',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ domain: '', validity_days: certValidityDays }),
                    })
                    if (!resp.ok) {
                        const err = await resp.json().catch(() => ({})) as { details?: string }
                        throw new Error(err.details || 'Certificate generation failed')
                    }
                    const data = await resp.json() as { ssl_cert?: string; ssl_key?: string }
                    if (data.ssl_cert) nextSslCert = data.ssl_cert
                    if (data.ssl_key) nextSslKey = data.ssl_key
                }
            } else if (certAction === 'letsencrypt') {
                // Skip only when the user hasn't explicitly opened the config
                // to replace the cert (valid or mismatched).
                if ((existingValidCert || certMismatch) && !showCertConfig) {
                    // A valid CA cert already exists for this domain.
                    // Keep it — no need to re-apply.
                } else {
                    // Domain mode + Let's Encrypt: apply on save
                    if (!letsEncryptEmail.trim()) {
                        throw new Error(t('settingsPage.platformSsl.emailRequired'))
                    }
                    const resp = await fetch('/api/settings/platform_gateway/apply-letsencrypt-cert', {
                        method: 'POST',
                        credentials: 'include',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ domain: boundDomainValue.trim(), email: letsEncryptEmail.trim() }),
                    })
                    if (!resp.ok) {
                        const err = await resp.json().catch(() => ({})) as { details?: string }
                        throw new Error(err.details || 'Let\'s Encrypt application failed')
                    }
                    const data = await resp.json() as { ssl_cert?: string; ssl_key?: string }
                    if (data.ssl_cert) nextSslCert = data.ssl_cert
                    if (data.ssl_key) nextSslKey = data.ssl_key
                }
            } else if (certAction === 'existing') {
                // Domain mode + existing cert: keep current certificate paths unchanged.
                // The server already has valid cert and key files on disk.
                if (!nextSslCert || !nextSslKey) {
                    throw new Error(t('settingsPage.platformSsl.noExistingCert'))
                }
            } else {
                // Domain mode + upload: save PEM content first
                const uploadCertPem = (drafts[PLATFORM_GATEWAY_UPLOAD_CERT_PEM_DRAFT_KEY] ?? certPem).trim()
                const uploadKeyPem = (drafts[PLATFORM_GATEWAY_UPLOAD_KEY_PEM_DRAFT_KEY] ?? keyPem).trim()
                const uploadIntermediatePem = (drafts[PLATFORM_GATEWAY_UPLOAD_INTERMEDIATE_PEM_DRAFT_KEY] ?? intermediatePem).trim()
                if (!uploadCertPem || !uploadKeyPem) {
                    throw new Error(t('settingsPage.platformSsl.pemRequired'))
                }
                const resp = await fetch('/api/settings/platform_gateway/upload-cert', {
                    method: 'POST',
                    credentials: 'include',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        cert_pem: uploadCertPem,
                        key_pem: uploadKeyPem,
                        intermediate_pem: uploadIntermediatePem,
                    }),
                })
                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({})) as { details?: string }
                    throw new Error(err.details || 'Certificate upload failed')
                }
                const data = await resp.json() as { ssl_cert?: string; ssl_key?: string }
                if (data.ssl_cert) nextSslCert = data.ssl_cert
                if (data.ssl_key) nextSslKey = data.ssl_key
            }
        }

        const payload = {
            bound_domain: boundDomainValue.trim(),
            https_enabled: nextHttpsEnabled,
            force_https: nextForceHttps,
            ssl_cert: nextSslCert,
            ssl_key: nextSslKey,
        }

        let saveSucceeded = false
        try {
            await updatePlatformGatewaySettings(payload)
            saveSucceeded = true
        } catch (saveError) {
            // Gateway restarts after SSL changes — network errors are expected and mean success.
            const isNetworkError =
                saveError instanceof TypeError ||
                (saveError instanceof Error && saveError.message.includes('NetworkError'))
            if (!isNetworkError) throw saveError
            // Network error: assume the save reached the backend and nginx is restarting.
            saveSucceeded = true
        }

        if (!saveSucceeded) return

        setFeedback({ severity: 'success', message: t('settingsPage.feedback.platformGatewaySuccess') })

        // After saving domain / SSL settings the gateway restarts, so the
        // current origin may no longer be reachable.  Build the target URL
        // from the newly saved configuration and redirect there.
        window.setTimeout(() => {
            const targetHost = useDomain && boundDomainValue.trim()
                ? boundDomainValue.trim()
                : window.location.hostname
            const targetProtocol = nextHttpsEnabled === 'true' ? 'https:' : 'http:'
            const targetPort = window.location.port
            window.location.href = `${targetProtocol}//${targetHost}:${targetPort}/settings`
        }, 2000)
    }

    async function handleSaveActiveModule() {
        setSavingModule(activeModule)
        setFeedback(null)

        try {
            if (activeModule === 'platform-domain') {
                await handleSavePlatformDomainModule()
            } else if (activeModule !== 'platform-system') {
                await saveSimpleModule(activeModule)
                setFeedback({ severity: 'success', message: t('settingsPage.feedback.saveSuccess', { key: t(activeModuleConfig.titleKey) }) })
            }
            setToastOpen(true)
        } catch (saveError) {
            setFeedback({
                severity: 'error',
                message: saveError instanceof Error ? saveError.message : t('settingsPage.feedback.saveError'),
            })
            setToastOpen(true)
        } finally {
            setSavingModule(null)
        }
    }

    function handleRestoreDefault(item: SettingsSummaryItem | null) {
        const defaultValue = item?.metadata?.default_value
        if (!item || typeof defaultValue !== 'string') {
            return
        }

        setDraftValue(getDraftKey(item), defaultValue)
    }

    function renderDomainRow(item: SettingsSummaryItem | null) {
        if (!item) {
            return null
        }

        const draftKey = getDraftKey(item)
        const currentValue = drafts[draftKey] ?? item.value
        const isChinese = i18n.resolvedLanguage === 'zh-CN'
        const helpUrl = isChinese
            ? 'https://support.websoft9.com/docs/domain-prepare#wildcard'
            : 'https://support.websoft9.com/en/docs/domain-prepare#wildcard'

        return (
            <div className="settings-form-row settings-form-row--domain-stacked" key={draftKey}>
                <div className="settings-domain-label-row">
                    <Typography className="settings-form-label">
                        {t('settingsPage.items.domain.wildcard_domain')}
                    </Typography>
                    <Box
                        className="settings-domain-help-icon"
                        component="a"
                        href={helpUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={t('settingsPage.domain.helpLink')}
                    >
                        ?
                    </Box>
                </div>

                <div className="settings-form-control settings-form-control--field">
                    <div className="settings-inline-content">
                        <TextField
                            fullWidth
                            size="small"
                            value={currentValue}
                            onChange={(event) => setDraftValue(draftKey, event.target.value)}
                            placeholder={t('settingsPage.domain.placeholder')}
                            sx={settingsFieldSx}
                        />
                        <Typography className="settings-field-helper settings-field-helper--inline">
                            {t('settingsPage.domain.globalDomainHelper')}
                        </Typography>
                    </div>
                </div>
            </div>
        )
    }

    function renderBrandRows() {
        const titleDraftKey = brandTitleItem ? getDraftKey(brandTitleItem) : ''
        const logoDraftKey = brandLogoItem ? getDraftKey(brandLogoItem) : ''
        const faviconDraftKey = brandFaviconItem ? getDraftKey(brandFaviconItem) : ''

        const titleValue = brandTitleItem ? (drafts[titleDraftKey] ?? brandTitleItem.value) : ''
        const previewTitle = titleValue || 'Websoft9'
        const logoValue = brandLogoItem ? (drafts[logoDraftKey] ?? brandLogoItem.value) : ''
        const faviconValue = brandFaviconItem ? (drafts[faviconDraftKey] ?? brandFaviconItem.value) : ''
        const loginBgDraftKey = brandLoginBgItem ? getDraftKey(brandLoginBgItem) : ''
        const loginBgValue = brandLoginBgItem ? (drafts[loginBgDraftKey] ?? brandLoginBgItem.value) : ''

        // Build preview URL with current draft values so unsaved changes are visible
        const previewParams = new URLSearchParams()
        if (previewTitle) previewParams.set('title', previewTitle)
        if (logoValue) previewParams.set('logo', logoValue)
        if (loginBgValue) previewParams.set('bg', loginBgValue)
        const previewQuery = previewParams.toString()
        const previewHref = `/settings/brand-preview${previewQuery ? `?${previewQuery}` : ''}`

        function handleUpload(file: File, draftKey: string) {
            if (!draftKey) return
            setUploadingLogo(true)
            const formData = new FormData()
            formData.append('file', file)

            fetch('/api/media/upload', {
                method: 'POST',
                body: formData,
                credentials: 'include',
            })
                .then(async (res) => {
                    if (!res.ok) throw new Error('Upload failed')
                    const data = await res.json() as { url?: string }
                    if (data.url) {
                        setDraftValue(draftKey, data.url)
                        if (reuseLogo && faviconDraftKey && draftKey === logoDraftKey) {
                            setDraftValue(faviconDraftKey, data.url)
                        }
                    }
                })
                .catch(() => { })
                .finally(() => setUploadingLogo(false))
        }

        function handleReuseToggle(next: boolean) {
            setReuseLogo(next)
            if (next && logoDraftKey && faviconDraftKey) {
                const currentLogo = drafts[logoDraftKey] ?? brandLogoItem?.value ?? ''
                setDraftValue(faviconDraftKey, currentLogo)
            }
        }

        const previewLogoSrc = logoValue || '/websoft9.png'
        const previewFaviconSrc = faviconValue || logoValue || '/favicon.ico?v=20260509c'

        return (
            <>
                {/* Preview card */}
                <div className="settings-form-row settings-form-row--domain-stacked">
                    <div className="settings-brand-preview-card">
                        <div className="settings-brand-preview-sidebar">
                            <img className="settings-brand-preview-logo" key={previewLogoSrc} src={previewLogoSrc} alt="Logo preview" onError={(e) => { (e.target as HTMLImageElement).src = '/websoft9.png' }} />
                            <span className="settings-brand-preview-title">{previewTitle}</span>
                        </div>
                        <div className="settings-brand-preview-browser">
                            <div className="settings-brand-preview-tab">
                                <img className="settings-brand-preview-favicon" key={previewFaviconSrc} src={previewFaviconSrc} alt="Favicon preview" onError={(e) => { (e.target as HTMLImageElement).src = '/favicon.ico?v=20260509c' }} />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Title – first */}
                <div className="settings-form-row settings-form-row--domain-stacked">
                    <Typography className="settings-form-label">{t('settingsPage.items.platform_brand.title')}</Typography>
                    <div className="settings-form-control settings-form-control--field">
                        <div className="settings-inline-content">
                            <TextField
                                fullWidth
                                size="small"
                                value={titleValue}
                                onChange={(event) => { if (titleDraftKey) setDraftValue(titleDraftKey, event.target.value) }}
                                placeholder={t('settingsPage.brand.titlePlaceholder')}
                                sx={settingsFieldSx}
                            />
                            <Typography className="settings-field-helper settings-field-helper--inline">
                                {t('settingsPage.brand.titleHelper')}
                            </Typography>
                        </div>
                    </div>
                </div>

                {/* Logo – with upload */}
                <div className="settings-form-row settings-form-row--domain-stacked">
                    <Typography className="settings-form-label">{t('settingsPage.items.platform_brand.logo_url')}</Typography>
                    <div className="settings-form-control settings-form-control--field">
                        <div className="settings-inline-content">
                            <div className="settings-brand-upload-row">
                                <TextField
                                    fullWidth
                                    size="small"
                                    value={logoValue}
                                    onChange={(event) => {
                                        if (logoDraftKey) setDraftValue(logoDraftKey, event.target.value)
                                        if (reuseLogo && faviconDraftKey) setDraftValue(faviconDraftKey, event.target.value)
                                    }}
                                    placeholder={t('settingsPage.brand.logoPlaceholder')}
                                    sx={settingsFieldSx}
                                />
                                <Button
                                    className="settings-action-button"
                                    size="small"
                                    variant="outlined"
                                    disabled={uploadingLogo || savingModule === activeModule}
                                    onClick={() => logoUploadRef.current?.click()}
                                >
                                    {uploadingLogo ? '...' : t('settingsPage.brand.uploadLogo')}
                                </Button>
                                <input
                                    ref={logoUploadRef}
                                    type="file"
                                    accept="image/*"
                                    style={{ display: 'none' }}
                                    onChange={(e) => {
                                        const file = e.target.files?.[0]
                                        if (file) handleUpload(file, logoDraftKey)
                                        e.target.value = ''
                                    }}
                                />
                            </div>
                            <Typography className="settings-field-helper settings-field-helper--inline">
                                {t('settingsPage.brand.uploadLogoHint')}
                            </Typography>
                        </div>
                    </div>
                </div>

                {/* Favicon – with upload + reuse toggle inline */}
                <div className="settings-form-row settings-form-row--domain-stacked">
                    <div className="settings-brand-favicon-header">
                        <Typography className="settings-form-label">{t('settingsPage.items.platform_brand.favicon_url')}</Typography>
                        <label className="settings-brand-reuse-toggle">
                            <Typography className="settings-brand-reuse-label">{t('settingsPage.brand.reuseLogoAsFavicon')}</Typography>
                            <Switch
                                size="small"
                                checked={reuseLogo}
                                disabled={savingModule === activeModule}
                                onChange={(_, next) => handleReuseToggle(next)}
                            />
                        </label>
                    </div>
                    <div className="settings-form-control settings-form-control--field">
                        {reuseLogo ? (
                            <Typography className="settings-field-helper settings-field-helper--inline">
                                {t('settingsPage.brand.reuseLogoAsFaviconHelper')}
                            </Typography>
                        ) : (
                            <div className="settings-inline-content">
                                <div className="settings-brand-upload-row">
                                    <TextField
                                        fullWidth
                                        size="small"
                                        value={faviconValue}
                                        onChange={(event) => { if (faviconDraftKey) setDraftValue(faviconDraftKey, event.target.value) }}
                                        placeholder={t('settingsPage.brand.faviconPlaceholder')}
                                        sx={settingsFieldSx}
                                    />
                                    <Button
                                        className="settings-action-button"
                                        size="small"
                                        variant="outlined"
                                        disabled={uploadingLogo || savingModule === activeModule}
                                        onClick={() => faviconUploadRef.current?.click()}
                                    >
                                        {uploadingLogo ? '...' : t('settingsPage.brand.uploadLogo')}
                                    </Button>
                                    <input
                                        ref={faviconUploadRef}
                                        type="file"
                                        accept="image/*"
                                        style={{ display: 'none' }}
                                        onChange={(e) => {
                                            const file = e.target.files?.[0]
                                            if (file) handleUpload(file, faviconDraftKey)
                                            e.target.value = ''
                                        }}
                                    />
                                </div>
                                <Typography className="settings-field-helper settings-field-helper--inline">
                                    {t('settingsPage.brand.faviconHelper')}
                                </Typography>
                            </div>
                        )}
                    </div>
                </div>

                {/* Login Background – with upload + preview link */}
                <div className="settings-form-row settings-form-row--domain-stacked">
                    <Typography className="settings-form-label">{t('settingsPage.items.platform_brand.login_background')}</Typography>
                    <div className="settings-form-control settings-form-control--field">
                        <div className="settings-inline-content">
                            <div className="settings-brand-upload-row">
                                <TextField
                                    fullWidth
                                    size="small"
                                    value={brandLoginBgItem ? (drafts[getDraftKey(brandLoginBgItem)] ?? brandLoginBgItem.value) : ''}
                                    onChange={(event) => { if (brandLoginBgItem) setDraftValue(getDraftKey(brandLoginBgItem), event.target.value) }}
                                    placeholder={t('settingsPage.brand.loginBackgroundPlaceholder')}
                                    sx={settingsFieldSx}
                                />
                                <Button
                                    className="settings-action-button"
                                    size="small"
                                    variant="outlined"
                                    disabled={uploadingBackground || savingModule === activeModule}
                                    onClick={() => backgroundUploadRef.current?.click()}
                                >
                                    {uploadingBackground ? '...' : t('settingsPage.brand.uploadBackground')}
                                </Button>
                                <input
                                    ref={backgroundUploadRef}
                                    type="file"
                                    accept="image/*"
                                    style={{ display: 'none' }}
                                    onChange={(e) => {
                                        const file = e.target.files?.[0]
                                        if (file && brandLoginBgItem) {
                                            setUploadingBackground(true)
                                            const formData = new FormData()
                                            formData.append('file', file)
                                            fetch('/api/media/upload', {
                                                method: 'POST',
                                                body: formData,
                                                credentials: 'include',
                                            })
                                                .then(async (res) => {
                                                    if (!res.ok) throw new Error('Upload failed')
                                                    const data = await res.json() as { url?: string }
                                                    if (data.url) {
                                                        setDraftValue(getDraftKey(brandLoginBgItem), data.url)
                                                    }
                                                })
                                                .catch(() => { })
                                                .finally(() => setUploadingBackground(false))
                                        }
                                        e.target.value = ''
                                    }}
                                />
                            </div>
                            <Typography className="settings-field-helper settings-field-helper--inline">
                                {t('settingsPage.brand.uploadBackgroundHint')}
                                {' · '}
                                <a
                                    href={previewHref}
                                    target="_blank"
                                    rel="noreferrer"
                                    style={{ color: 'inherit' }}
                                >
                                    {t('settingsPage.brand.loginPreview')}
                                </a>
                            </Typography>
                        </div>
                    </div>
                </div>

                {/* Copyright text */}
                <div className="settings-form-row settings-form-row--domain-stacked">
                    <Typography className="settings-form-label">{t('settingsPage.items.platform_brand.copyright_text')}</Typography>
                    <div className="settings-form-control settings-form-control--field">
                        <div className="settings-inline-content">
                            <TextField
                                fullWidth
                                size="small"
                                value={brandCopyrightItem ? (drafts[getDraftKey(brandCopyrightItem)] ?? brandCopyrightItem.value) : ''}
                                onChange={(event) => { if (brandCopyrightItem) setDraftValue(getDraftKey(brandCopyrightItem), event.target.value) }}
                                placeholder={t('settingsPage.brand.copyrightPlaceholder')}
                                sx={settingsFieldSx}
                            />
                            <Typography className="settings-field-helper settings-field-helper--inline">
                                {t('settingsPage.brand.copyrightHelper')}
                            </Typography>
                        </div>
                    </div>
                </div>
            </>
        )
    }

    function renderPortRangeRow(item: SettingsSummaryItem | null) {
        if (!item) {
            return null
        }

        const draftKey = getDraftKey(item)
        const startDraftKey = `${draftKey}${PORT_RANGE_START_DRAFT_SUFFIX}`
        const endDraftKey = `${draftKey}${PORT_RANGE_END_DRAFT_SUFFIX}`
        const currentRange = parsePortRangeValue(item.value)
        const startValue = drafts[startDraftKey] ?? currentRange.start
        const endValue = drafts[endDraftKey] ?? currentRange.end

        return (
            <div className="settings-form-row settings-form-row--domain-stacked" key={draftKey}>
                <div className="settings-domain-label-row">
                    <Typography className="settings-form-label">
                        {t('settingsPage.items.port_allocation.range')}
                    </Typography>
                </div>

                <div className="settings-form-control settings-form-control--field">
                    <div className="settings-inline-content">
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: { xs: '100%', sm: '50%' } }}>
                            <TextField
                                size="small"
                                value={startValue}
                                onChange={(event) => setDraftValue(startDraftKey, event.target.value)}
                                placeholder={t('settingsPage.portRange.startPlaceholder')}
                                sx={{ ...settingsFieldSx, flex: 1, minWidth: 0 }}
                            />
                            <Typography color="text.secondary">-</Typography>
                            <TextField
                                size="small"
                                value={endValue}
                                onChange={(event) => setDraftValue(endDraftKey, event.target.value)}
                                placeholder={t('settingsPage.portRange.endPlaceholder')}
                                sx={{ ...settingsFieldSx, flex: 1, minWidth: 0 }}
                            />
                        </Box>
                        <Typography className="settings-field-helper settings-field-helper--inline settings-port-hint">
                            <svg className="settings-port-hint-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
                                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
                                <path d="M12 11.2v5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                                <circle cx="12" cy="7.9" r="1.15" fill="currentColor" />
                            </svg>
                            <span>{t('settingsPage.portRange.helper')}</span>
                        </Typography>
                        <Typography className="settings-field-helper settings-field-helper--inline settings-port-hint">
                            <svg className="settings-port-hint-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
                                <path d="M12 3.5 18.4 6v4.7c0 4-2.6 7-6.4 8.7-3.8-1.7-6.4-4.7-6.4-8.7V6L12 3.5Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
                                <path d="M12 8.9v3.3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                                <circle cx="12" cy="15.2" r="1.05" fill="currentColor" />
                            </svg>
                            <span>{t('settingsPage.portRange.securityHint')}</span>
                        </Typography>
                    </div>
                </div>
            </div>
        )
    }

    function renderMirrorRow(item: SettingsSummaryItem | null) {
        if (!item) {
            return null
        }

        const draftKey = getDraftKey(item)
        const currentValue = drafts[draftKey] ?? item.value
        const entries = parseMirrorEntries(currentValue)
        const pendingInput = mirrorPendingInputs[draftKey] ?? ''

        function commitPendingMirrorValue() {
            const nextValue = pendingInput.trim().replace(/,+$/, '')
            if (!nextValue) {
                return
            }

            setDraftValue(draftKey, [...entries, nextValue].join(','))
            setMirrorPendingInputs((currentInputs) => ({
                ...currentInputs,
                [draftKey]: '',
            }))
        }

        function removeMirrorEntry(entryToRemove: string, indexToRemove: number) {
            const nextEntries = entries.filter((entry, index) => !(entry === entryToRemove && index === indexToRemove))
            setDraftValue(draftKey, nextEntries.join(','))
        }

        return (
            <div className="settings-form-row settings-form-row--domain-stacked" key={`${draftKey}-mirrors`}>
                <Typography className="settings-form-label">{t('settingsPage.items.docker_mirror.url')}</Typography>

                <div className="settings-form-control settings-form-control--field">
                    <div className="settings-inline-content">
                        <Box className="settings-mirror-edit-box">
                            {entries.map((entry, index) => (
                                <Chip className="settings-mirror-edit-chip" key={`${entry}-${index}`} label={entry} onDelete={() => removeMirrorEntry(entry, index)} size="small" />
                            ))}
                            <input
                                className="settings-mirror-inline-input"
                                value={pendingInput}
                                onBlur={commitPendingMirrorValue}
                                onChange={(event) => {
                                    setMirrorPendingInputs((currentInputs) => ({
                                        ...currentInputs,
                                        [draftKey]: event.target.value,
                                    }))
                                }}
                                onKeyDown={(event) => {
                                    if (event.key === 'Enter' || event.key === ',') {
                                        event.preventDefault()
                                        commitPendingMirrorValue()
                                        return
                                    }

                                    if (event.key === 'Backspace' && !pendingInput && entries.length) {
                                        event.preventDefault()
                                        const lastIndex = entries.length - 1
                                        removeMirrorEntry(entries[lastIndex], lastIndex)
                                    }
                                }}
                                placeholder={entries.length ? '' : t('settingsPage.mirror.placeholderInline')}
                            />
                        </Box>
                        <div className="settings-mirror-helper-row">
                            <Typography className="settings-field-helper settings-field-helper--inline">{t('settingsPage.mirror.helper')}</Typography>
                            <Box
                                className="settings-restore-link"
                                component="button"
                                disabled={savingModule === activeModule}
                                onClick={() => handleRestoreDefault(item)}
                                type="button"
                            >
                                {t('settingsPage.actions.restore')}
                            </Box>
                        </div>
                    </div>
                </div>
            </div>
        )
    }

    function renderPlatformDomainRows() {
        const boundDraftKey = boundDomainItem ? getDraftKey(boundDomainItem) : ''
        const boundValue = boundDomainItem ? (drafts[boundDraftKey] ?? boundDomainItem.value) : ''
        const certLabel = isDefaultCert
            ? t('settingsPage.platformSsl.certTypeSelfSigned')
            : t('settingsPage.platformSsl.certTypeCaIssued')

        function handleModeSelect(domain: boolean) {
            setUseDomain(domain)
            if (domain) {
                setDraftValue(PLATFORM_GATEWAY_HTTPS_DRAFT_KEY, 'false')
                setDraftValue(PLATFORM_GATEWAY_FORCE_HTTPS_DRAFT_KEY, 'false')
                setCertAction('letsencrypt')
            } else {
                if (boundDraftKey) setDraftValue(boundDraftKey, '')
                setDraftValue(PLATFORM_GATEWAY_FORCE_HTTPS_DRAFT_KEY, 'false')
            }
        }

        function handlePemFilePick(event: React.ChangeEvent<HTMLInputElement>, setter: (value: string) => void) {
            const file = event.target.files?.[0]
            if (!file) return
            const reader = new FileReader()
            reader.onload = () => setter(reader.result as string)
            reader.readAsText(file)
            event.target.value = ''
        }

        return (
            <>
                {/* Access mode – always visible */}
                <div className="settings-form-row settings-form-row--domain-stacked">
                    <Typography className="settings-form-label">{t('settingsPage.platformSsl.accessModeTitle')}</Typography>
                    <div className="settings-form-control settings-form-control--field">
                        <div className="settings-access-card">
                            <div className="settings-access-card-body">
                                <div className="settings-domain-mode-radios">
                                    <label className={`settings-domain-mode-radio-label ${!useDomain ? 'checked' : ''}`} onClick={() => handleModeSelect(false)}>
                                        <span className="settings-domain-mode-radio-btn"><span className="settings-domain-mode-radio-dot" /></span>
                                        <span className="settings-domain-mode-radio-text">{t('settingsPage.platformSsl.ipModeTitle')}</span>
                                    </label>
                                    <label className={`settings-domain-mode-radio-label ${useDomain ? 'checked' : ''}`} onClick={() => handleModeSelect(true)}>
                                        <span className="settings-domain-mode-radio-btn"><span className="settings-domain-mode-radio-dot" /></span>
                                        <span className="settings-domain-mode-radio-text">{t('settingsPage.platformSsl.domainModeTitle')}</span>
                                    </label>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Domain address – only in domain mode */}
                {useDomain ? (
                    <div className="settings-form-row settings-form-row--domain-stacked">
                        <Typography className="settings-form-label">{t('settingsPage.platformSsl.domainInputLabel')}</Typography>
                        <div className="settings-form-control settings-form-control--field">
                            <div className="settings-inline-content">
                                <TextField fullWidth size="small" value={boundValue}
                                    onChange={(e) => { if (boundDraftKey) setDraftValue(boundDraftKey, e.target.value) }}
                                    placeholder={t('settingsPage.platformSsl.domainPlaceholder')} sx={settingsFieldSx} />
                                <Typography className="settings-field-helper settings-field-helper--inline">{t('settingsPage.platformSsl.domainHint')}</Typography>
                            </div>
                        </div>
                    </div>
                ) : null}

                <div className="settings-ssl-card">
                    <div className="settings-ssl-card-header">
                        <div className="settings-ssl-card-headline">
                            <span className="settings-ssl-card-title">{t('settingsPage.platformSsl.switchTitle')}</span>
                            <span className="settings-ssl-card-subtitle">{t('settingsPage.platformSsl.switchHelper')}</span>
                        </div>
                        <Switch checked={httpsEnabled} disabled={savingModule === activeModule}
                            onChange={(_, n) => { setDraftValue(PLATFORM_GATEWAY_HTTPS_DRAFT_KEY, n ? 'true' : 'false'); if (!n) setDraftValue(PLATFORM_GATEWAY_FORCE_HTTPS_DRAFT_KEY, 'false') }} />
                    </div>
                </div>

                {httpsEnabled ? (
                    <>
                        {existingValidCert ? (
                            <div className="settings-ssl-card">
                                <div className="settings-ssl-card-header">
                                    <span className="settings-ssl-card-title">{t('settingsPage.platformSsl.currentCertTitle')}</span>
                                    <span className="settings-ssl-cert-current-info">
                                        <span className={`settings-ssl-cert-status-badge ${isDefaultCert ? 'settings-ssl-cert-status-badge--selfsigned' : 'settings-ssl-cert-status-badge--issued'}`}>
                                            {certLabel}
                                        </span>
                                        {certExpiry ? (
                                            <span className="settings-ssl-cert-expiry">{t('settingsPage.platformSsl.expiry')}{certExpiry}</span>
                                        ) : null}
                                        <button
                                            className="settings-ssl-cert-toggle-btn"
                                            type="button"
                                            onClick={() => setShowCertConfig(!showCertConfig)}
                                        >
                                            {showCertConfig ? t('settingsPage.platformSsl.collapseCert') : t('settingsPage.platformSsl.replaceCert')}
                                        </button>
                                    </span>
                                </div>
                            </div>
                        ) : certMismatch ? (
                            <div className="settings-ssl-card settings-ssl-card--warn">
                                <div className="settings-ssl-card-header">
                                    <svg className="settings-ssl-warn-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
                                        <path d="M12 2L2 22h20L12 2z" fill="#f59e0b" stroke="#d97706" strokeWidth="1.5" strokeLinejoin="round" />
                                        <path d="M12 10v4" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
                                        <circle cx="12" cy="17" r="1" fill="#fff" />
                                    </svg>
                                    <span className="settings-ssl-card-title">{t('settingsPage.platformSsl.certMismatchTitle')}</span>
                                    <div className="settings-ssl-mismatch-grid">
                                        <span className="settings-ssl-mismatch-cell">
                                            <span className="settings-ssl-mismatch-tag settings-ssl-mismatch-tag--domain">{t('settingsPage.platformSsl.certMismatchDomain')}</span>
                                            <span className="settings-ssl-mismatch-value">{boundDomainValue || boundDomainItem?.value || ''}</span>
                                        </span>
                                        <span className="settings-ssl-mismatch-cell">
                                            <span className="settings-ssl-mismatch-tag settings-ssl-mismatch-tag--cert">{t('settingsPage.platformSsl.certMismatchIssued')}</span>
                                            <span className="settings-ssl-mismatch-value settings-ssl-mismatch-value--dim">{certSubjectCn}</span>
                                        </span>
                                    </div>
                                    <button
                                        className="settings-ssl-cert-toggle-btn"
                                        type="button"
                                        onClick={() => setShowCertConfig(!showCertConfig)}
                                    >
                                        {showCertConfig ? t('settingsPage.platformSsl.collapseCert') : t('settingsPage.platformSsl.replaceCert')}
                                    </button>
                                </div>
                            </div>
                        ) : null}
                        {showCertConfig || shouldAutoExpand ? (
                            <div className="settings-ssl-card settings-ssl-card--content">
                                <div className="settings-ssl-card-header">
                                    <span className="settings-ssl-card-title">{!useDomain ? t('settingsPage.platformSsl.selfSignedTitle') : t('settingsPage.platformSsl.certConfigTitle')}</span>
                                </div>
                                <div className="settings-ssl-card-body">
                                    {existingValidCert || certMismatch ? (
                                        <Typography className="settings-field-helper" sx={{ mb: 1.5 }}>{t('settingsPage.platformSsl.replaceCertWarning')}</Typography>
                                    ) : null}
                                    {!useDomain ? (
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                            <Typography variant="body2" sx={{ fontSize: 12, color: 'text.secondary', flexShrink: 0 }}>{t('settingsPage.platformSsl.validityLabel')}</Typography>
                                            <select className="settings-validity-select" value={certValidityDays} onChange={(e) => setCertValidityDays(Number(e.target.value))}>
                                                <option value={365}>{t('settingsPage.platformSsl.validity1y')}</option>
                                                <option value={1095}>{t('settingsPage.platformSsl.validity3y')}</option>
                                                <option value={1825}>{t('settingsPage.platformSsl.validity5y')}</option>
                                                <option value={3650}>{t('settingsPage.platformSsl.validity10y')}</option>
                                            </select>
                                        </Box>
                                    ) : (
                                        <>
                                            <div className="settings-ssl-cert-options settings-ssl-cert-options--two">
                                                <button className={`settings-choice-button ${certAction === 'letsencrypt' ? 'active' : ''}`} onClick={() => setCertAction('letsencrypt')} type="button">
                                                    <span className="settings-choice-badge">{t('settingsPage.platformSsl.recommendedBadge')}</span>
                                                    <span className="settings-choice-title">{t('settingsPage.platformSsl.letsencryptTitle')}</span>
                                                    <span className="settings-choice-description">{t('settingsPage.platformSsl.letsencryptDescription')}</span>
                                                </button>
                                                <button className={`settings-choice-button ${certAction === 'upload' ? 'active' : ''}`} onClick={() => { setCertAction('upload'); if (!certName) setCertName(boundDomainValue || boundDomainItem?.value || '') }} type="button">
                                                    <span className="settings-choice-title">{t('settingsPage.platformSsl.uploadTitle')}</span>
                                                    <span className="settings-choice-description">{t('settingsPage.platformSsl.uploadDescription')}</span>
                                                </button>
                                            </div>
                                            {certAction === 'letsencrypt' ? (
                                                <div className="settings-ssl-cert-actions">
                                                    <span className="settings-ssl-cert-field-label">{t('settingsPage.platformSsl.emailLabel')}<span className="settings-field-required">*</span></span>
                                                    <TextField fullWidth size="small" value={letsEncryptEmail} onChange={(e) => { setLetsEncryptEmail(e.target.value); setDraftValue(PLATFORM_GATEWAY_LETSENCRYPT_EMAIL_DRAFT_KEY, e.target.value) }} placeholder={t('settingsPage.platformSsl.emailPlaceholder')} sx={settingsFieldSx} required />
                                                </div>
                                            ) : (
                                                <div className="settings-ssl-cert-fields">
                                                    <div className="settings-ssl-cert-field">
                                                        <span className="settings-ssl-cert-field-label">{t('settingsPage.platformSsl.certNameLabel')}</span>
                                                        <input className="settings-ssl-cert-name-input" value={certName} onChange={(e) => { setCertName(e.target.value); setDraftValue(PLATFORM_GATEWAY_UPLOAD_CERT_PEM_DRAFT_KEY, `${e.target.value}\n${keyPem}`) }} placeholder="my-site.com" />
                                                    </div>
                                                    <div className="settings-ssl-cert-grid">
                                                        <div className="settings-ssl-cert-field">
                                                            <div className="settings-ssl-cert-field-head">
                                                                <span className="settings-ssl-cert-field-label">{t('settingsPage.platformSsl.keyPemLabel')}</span>
                                                                <button className="settings-ssl-upload-btn" onClick={() => keyPemFileRef.current?.click()} title={t('settingsPage.actions.upload')} type="button"><svg fill="currentColor" height="14" viewBox="0 0 24 24" width="14"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z" /></svg></button>
                                                                <input ref={keyPemFileRef} accept=".pem,.key,.crt,.cer,.txt" hidden onChange={(e) => { handlePemFilePick(e, (val) => { setKeyPem(val); setDraftValue(PLATFORM_GATEWAY_UPLOAD_KEY_PEM_DRAFT_KEY, val) }) }} type="file" />
                                                            </div>
                                                            <textarea className="settings-ssl-cert-textarea" rows={5} value={keyPem} onChange={(e) => { setKeyPem(e.target.value); setDraftValue(PLATFORM_GATEWAY_UPLOAD_KEY_PEM_DRAFT_KEY, e.target.value) }} placeholder="-----BEGIN PRIVATE KEY-----" />
                                                        </div>
                                                        <div className="settings-ssl-cert-field">
                                                            <div className="settings-ssl-cert-field-head">
                                                                <span className="settings-ssl-cert-field-label">{t('settingsPage.platformSsl.certPemLabel')}</span>
                                                                <button className="settings-ssl-upload-btn" onClick={() => certPemFileRef.current?.click()} title={t('settingsPage.actions.upload')} type="button"><svg fill="currentColor" height="14" viewBox="0 0 24 24" width="14"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z" /></svg></button>
                                                                <input ref={certPemFileRef} accept=".pem,.crt,.cer,.txt" hidden onChange={(e) => { handlePemFilePick(e, (val) => { setCertPem(val); setDraftValue(PLATFORM_GATEWAY_UPLOAD_CERT_PEM_DRAFT_KEY, val) }) }} type="file" />
                                                            </div>
                                                            <textarea className="settings-ssl-cert-textarea" rows={5} value={certPem} onChange={(e) => { setCertPem(e.target.value); setDraftValue(PLATFORM_GATEWAY_UPLOAD_CERT_PEM_DRAFT_KEY, e.target.value) }} placeholder="-----BEGIN CERTIFICATE-----" />
                                                        </div>
                                                    </div>
                                                    <div className="settings-ssl-cert-field">
                                                        <div className="settings-ssl-cert-field-head">
                                                            <span className="settings-ssl-cert-field-label">{t('settingsPage.platformSsl.intermediatePemLabel')}</span>
                                                            <button className="settings-ssl-upload-btn" onClick={() => intermediatePemFileRef.current?.click()} title={t('settingsPage.actions.upload')} type="button"><svg fill="currentColor" height="14" viewBox="0 0 24 24" width="14"><path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z" /></svg></button>
                                                            <input ref={intermediatePemFileRef} accept=".pem,.crt,.cer,.txt" hidden onChange={(e) => { handlePemFilePick(e, (val) => { setIntermediatePem(val); setDraftValue(PLATFORM_GATEWAY_UPLOAD_INTERMEDIATE_PEM_DRAFT_KEY, val) }) }} type="file" />
                                                        </div>
                                                        <textarea className="settings-ssl-cert-textarea" rows={3} value={intermediatePem} onChange={(e) => { setIntermediatePem(e.target.value); setDraftValue(PLATFORM_GATEWAY_UPLOAD_INTERMEDIATE_PEM_DRAFT_KEY, e.target.value) }} placeholder={t('settingsPage.platformSsl.intermediatePemOptional')} />
                                                    </div>
                                                    <Typography className="settings-field-helper">{t('settingsPage.platformSsl.uploadFormatHint')}</Typography>
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            </div>
                        ) : null}
                        {/* FIXME: force_https toggle currently has no backend consumer.
                           The 497 redirect (HTTP→HTTPS) is now always active when
                           HTTPS is enabled.  Keep the code commented for future use. */}
                        {/*
                        <div className="settings-ssl-card">
                            <div className="settings-ssl-card-header">
                                <div className="settings-ssl-card-headline">
                                    <span className="settings-ssl-card-title">{t('settingsPage.platformSsl.redirectLabel')}</span>
                                    <span className="settings-ssl-card-subtitle">{t('settingsPage.platformSsl.redirectHelper')}</span>
                                </div>
                                <Switch checked={forceHttpsEnabled} disabled={savingModule === activeModule || !httpsEnabled}
                                    onChange={(_, n) => setDraftValue(PLATFORM_GATEWAY_FORCE_HTTPS_DRAFT_KEY, n ? 'true' : 'false')} />
                            </div>
                        </div>
                        */}
                    </>
                ) : null}
            </>
        )
    }

    function renderUpgradeRow() {
        const status = upgradeStatus
        const currentVersion = status?.current_version || t('settingsPage.values.notConfigured')
        const sessionFailure = status?.last_failure && initiatedUpgradeRunId && status.last_failure.run_id === initiatedUpgradeRunId
            ? status.last_failure
            : null
        const upgradeFailureDetail = sessionFailure?.detail === 'download_interrupted'
            ? t('settingsPage.upgrade.downloadInterrupted')
            : sessionFailure?.detail || t('settingsPage.upgrade.actions.downloadFailed')
        const upgradeCheckBusy = checkingUpgrade || isUpgradeStatusFetching
        const isChineseLocale = i18n.resolvedLanguage === 'zh-CN'

        function copyPlainText(text: string) {
            if (navigator.clipboard && window.isSecureContext) {
                void navigator.clipboard.writeText(text).catch(() => { /* clipboard can be blocked */ })
                return
            }
            // Fallback for non-HTTPS deployments, where the clipboard API is unavailable.
            const textarea = document.createElement('textarea')
            textarea.value = text
            textarea.style.position = 'fixed'
            textarea.style.left = '-9999px'
            document.body.appendChild(textarea)
            textarea.focus()
            textarea.select()
            try {
                document.execCommand('copy')
            } catch {
                // Nothing else to try; the text stays selectable in the dialog.
            }
            document.body.removeChild(textarea)
        }

        async function loadUpgradeLog(runId: string) {
            setUpgradeLogLoading(true)
            setUpgradeLogFailed(false)
            try {
                setUpgradeLog(await fetchUpgradeLog(runId, UPGRADE_LOG_TAIL))
            } catch {
                setUpgradeLog(null)
                setUpgradeLogFailed(true)
            } finally {
                setUpgradeLogLoading(false)
            }
        }

        function openUpgradeLog(runId: string) {
            setUpgradeLogOpen(true)
            void loadUpgradeLog(runId)
        }

        async function handleCheckUpgrade() {
            setCheckingUpgrade(true)
            let failed = false
            try {
                // Forces a fresh check against the artifact channel, then re-reads the cache.
                await checkUpgrade()
            } catch {
                failed = true
            } finally {
                setCheckingUpgrade(false)
            }

            if (failed) {
                setFeedback({ severity: 'error', message: t('settingsPage.upgrade.checkFailed') })
                setToastOpen(true)
                return
            }

            // Report the outcome here: the row itself has no state to change when nothing is found.
            const result = await refetchUpgradeStatus()
            setFeedback({
                severity: 'success',
                message: result.data?.upgrade_available
                    ? t('settingsPage.upgrade.foundNewVersion', { version: result.data.latest_version })
                    : t('settingsPage.upgrade.upToDate'),
            })
            setToastOpen(true)
        }

        function handleCopy() {
            const text = status?.install_command
            if (!text) return

            // Try modern clipboard API first, fall back to execCommand
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(text).then(
                    () => { setCopied(true); setTimeout(() => setCopied(false), 2000) },
                    () => { /* ignore */ },
                )
            } else {
                // Fallback for non-HTTPS environments
                const textarea = document.createElement('textarea')
                textarea.value = text
                textarea.style.position = 'fixed'
                textarea.style.left = '-9999px'
                textarea.style.top = '-9999px'
                document.body.appendChild(textarea)
                textarea.focus()
                textarea.select()
                try {
                    document.execCommand('copy')
                    setCopied(true)
                    setTimeout(() => setCopied(false), 2000)
                } catch {
                    // ignore
                }
                document.body.removeChild(textarea)
            }
        }

        async function handlePrepareUpgrade() {
            setPreparingUpgrade(true)
            try {
                const started = await prepareUpgrade()
                setInitiatedUpgradeRunId(started.run_id ?? null)
                await refetchUpgradeStatus()
            } catch (prepareError) {
                if (prepareError instanceof UpgradeRequestError && prepareError.status === 409) {
                    // Another tab or operator already owns the upgrade job. That is a concurrency
                    // conflict, not a failed download, so report it as information and re-read the
                    // status to follow whatever is actually running.
                    setFeedback({ severity: 'info', message: t('settingsPage.upgrade.actions.alreadyRunning') })
                } else {
                    setFeedback({
                        severity: 'error',
                        message: prepareError instanceof Error ? prepareError.message : t('settingsPage.upgrade.actions.downloadFailed'),
                    })
                }
                setToastOpen(true)
                await refetchUpgradeStatus()
            } finally {
                setPreparingUpgrade(false)
            }
        }

        async function handleApplyUpgrade() {
            setApplyConfirmationOpen(false)
            setApplyingUpgrade(true)
            try {
                const started = await applyUpgrade()
                setApplyFinishing(false)
                setApplyStartedAt(Date.now())
                setApplyElapsedSeconds(0)
                sawVerificationPhaseRef.current = false
                completionScheduledRef.current = false
                setActiveApplyRunId(started.run_id ?? 'pending')
                // From here the platform container will be recreated (and possibly rolled back),
                // so the console owns the screen until the run reaches a terminal state.
                setUpgradeInProgress(true)
                await refetchUpgradeStatus()
            } catch (applyError) {
                setFeedback({
                    severity: 'error',
                    message: applyError instanceof Error ? applyError.message : t('settingsPage.upgrade.actions.applyFailed'),
                })
                setToastOpen(true)
            } finally {
                setApplyingUpgrade(false)
            }
        }

        async function handleRetryUpgrade() {
            setApplyingUpgrade(true)
            let started: Awaited<ReturnType<typeof retryUpgrade>> | null = null
            try {
                // The staged release of the failed run is still on disk, so one click restarts the
                // same attempt: no second download and no "upgrade now" confirmation afterwards.
                started = await retryUpgrade()
            } catch {
                // Nothing left to reuse: download the release again and continue automatically.
                setAutoApplyPending(true)
            } finally {
                setApplyingUpgrade(false)
            }
            if (started) {
                setApplyFinishing(false)
                setApplyStartedAt(Date.now())
                setApplyElapsedSeconds(0)
                sawVerificationPhaseRef.current = false
                completionScheduledRef.current = false
                setActiveApplyRunId(started.run_id ?? 'pending')
                setUpgradeInProgress(true)
                // A refresh can fail while the platform restarts; the run itself is unaffected.
                void refetchUpgradeStatus().catch(() => undefined)
                return
            }
            await handlePrepareUpgrade()
        }

        if (isUpgradeStatusLoading) {
            return (
                <div className="settings-form-row">
                    <Typography className="settings-form-label">{t('settingsPage.upgrade.status')}{t('settingsPage.upgrade.labelSuffix')}</Typography>
                    <div className="settings-form-control">
                        <Typography variant="body2" color="text.secondary">{t('settingsPage.upgrade.checking')}</Typography>
                    </div>
                    <div className="settings-form-actions" />
                </div>
            )
        }

        if (activeApplyRunId || upgradeStatus?.state === 'applying') {
            return (
                <>
                    <div className="settings-form-row">
                        <Typography className="settings-form-label">{t('settingsPage.upgrade.status')}{t('settingsPage.upgrade.labelSuffix')}</Typography>
                        <div className="settings-form-control">
                            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                                <CircularProgress size={16} />
                                <Typography variant="body2" color="text.secondary">
                                    {t('settingsPage.upgrade.applying')}
                                </Typography>
                            </Stack>
                        </div>
                        <div className="settings-form-actions" />
                    </div>
                    {/* The platform container is being replaced, so the whole console must stay
                        read-only: a full-screen mask stops the operator from retrying an upgrade
                        that is already running while the backend is briefly unreachable. */}
                    <SurfaceDialog
                        open
                        onClose={() => undefined}
                        darkMode={isDarkMode}
                        paperSx={{
                            width: { xs: 'min(100%, 460px)', md: '460px' },
                            maxWidth: '460px',
                            backgroundColor: surfacePalette.dialogBg,
                            color: surfacePalette.text,
                            border: `1px solid ${surfacePalette.borderStrong}`,
                        }}
                    >
                        <Box sx={{ px: 3, py: 3, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1.5, textAlign: 'center' }}>
                            {applyFinishing ? (
                                <>
                                    <Box component="svg" viewBox="0 0 24 24" sx={{ width: 32, height: 32, color: surfacePalette.accent }}>
                                        <path fill="currentColor" d="M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                                    </Box>
                                    <Typography sx={{ m: 0, fontSize: 14, lineHeight: 1.7, color: surfacePalette.subtleText }}>
                                        {t('settingsPage.upgrade.result.completed', {
                                            version: upgradeStatus?.target_version || upgradeStatus?.latest_version || '',
                                        })}
                                    </Typography>
                                </>
                            ) : (
                                <>
                                    <CircularProgress size={32} />
                                    <Typography sx={{ fontSize: 16, fontWeight: 700, color: surfacePalette.text }}>
                                        {t('settingsPage.upgrade.applying')}
                                    </Typography>
                                    <Typography sx={{ m: 0, fontSize: 14, lineHeight: 1.7, color: surfacePalette.subtleText }}>
                                        {t('settingsPage.upgrade.applyingHint')}
                                    </Typography>
                                    <Stepper activeStep={applyPhaseIndex} orientation="vertical" sx={{ mt: 1, textAlign: 'left', '& .MuiStepLabel-label': { fontSize: 13 } }}>
                                        {applyPhaseKeys.map((phaseKey) => (
                                            <Step key={phaseKey}>
                                                <StepLabel>{t(phaseKey)}</StepLabel>
                                            </Step>
                                        ))}
                                    </Stepper>
                                    <Typography sx={{ m: 0, fontSize: 12, color: surfacePalette.subtleText }}>
                                        {t('settingsPage.upgrade.applyingElapsed', { seconds: applyElapsedSeconds })}
                                    </Typography>
                                    {applyElapsedSeconds > 180 && (
                                        <Typography sx={{ m: 0, fontSize: 12, color: surfacePalette.subtleText }}>
                                            {t('settingsPage.upgrade.applyingSlow')}
                                        </Typography>
                                    )}
                                </>
                            )}
                        </Box>
                    </SurfaceDialog>
                </>
            )
        }

        if (upgradeStatusError || !status) {
            return (
                <>
                    <div className="settings-form-row">
                        <Typography className="settings-form-label">{t('settingsPage.upgrade.currentVersion')}{t('settingsPage.upgrade.labelSuffix')}</Typography>
                        <div className="settings-form-control">
                            <Typography className="settings-form-value" variant="body2">
                                {currentVersion}
                            </Typography>
                        </div>
                        <div className="settings-form-actions" />
                    </div>

                    <div className="settings-form-row">
                        <Typography className="settings-form-label">{t('settingsPage.upgrade.status')}{t('settingsPage.upgrade.labelSuffix')}</Typography>
                        <div className="settings-form-control">
                            <Typography variant="body2" component="span" color="error.main">
                                {t('settingsPage.upgrade.unavailable')}
                            </Typography>
                            <Button
                                size="small"
                                variant="contained"
                                sx={{ ml: 1.5, verticalAlign: 'middle' }}
                                onClick={() => void handleCheckUpgrade()}
                                disabled={upgradeCheckBusy}
                            >
                                {checkingUpgrade ? t('settingsPage.upgrade.actions.checking') : t('settingsPage.upgrade.actions.check')}
                            </Button>
                        </div>
                        <div className="settings-form-actions" />
                    </div>
                </>
            )
        }

        // Terminal outcomes of an upgrade stay actionable long after it finished, so they remain
        // on screen until the next download or upgrade overwrites the recorded state. The banner
        // states what happened and why; the log carries the evidence, and support is one click away.
        const upgradeFailure = status.last_failure ?? null
        // Causes are grouped instead of translated one by one: an operator needs to know whether
        // the platform was left untouched, needs a fix, or is in between versions.
        const upgradeFailureGroup = (() => {
            const reason = String(upgradeFailure?.reason || '')
            if (reason.startsWith('download')) return 'download'
            if (reason.startsWith('rollback')) return 'rollback'
            if (reason === 'health_check_degraded') return 'degraded'
            if (reason === 'apply_interrupted' || reason === 'runner_exit') return 'interrupted'
            if (reason.startsWith('container') || reason.startsWith('health') || reason.startsWith('strict')) return 'container'
            return reason ? 'unknown' : ''
        })()
        const failureReason = upgradeFailureGroup
            ? t(`settingsPage.upgrade.reason.${upgradeFailureGroup}`, { defaultValue: '' })
            : ''
        const failureRunId = upgradeFailure?.run_id ? String(upgradeFailure.run_id) : ''
        const upgradeResultNotice = (() => {
            const target = status.target_version || status.latest_version
            switch (status.state) {
                case 'degraded':
                    return { severity: 'warning' as const, message: t('settingsPage.upgrade.result.degraded', { version: target }) }
                case 'rolled_back':
                    // Name the version the platform actually runs now; that is the fact the
                    // operator cares about, and it avoids quoting the same number twice.
                    return {
                        severity: 'warning' as const,
                        message: String(currentVersion || '')
                            ? t('settingsPage.upgrade.result.rolledBack', { current: currentVersion })
                            : t('settingsPage.upgrade.result.rolledBackUnknown'),
                    }
                case 'rollback_failed':
                    return { severity: 'error' as const, message: t('settingsPage.upgrade.result.rollbackFailed', { version: target }) }
                case 'apply_interrupted':
                    return { severity: 'error' as const, message: t('settingsPage.upgrade.result.interrupted') }
                default:
                    return null
            }
        })()

        return (
            <>
                {upgradeResultNotice && (
                    <div className="settings-form-row">
                        <Alert
                            severity={upgradeResultNotice.severity}
                            sx={{
                                gridColumn: '1 / -1',
                                '& .MuiAlert-message': { width: '100%' },
                                // The actions sit vertically centred in the banner, matching the
                                // height of the message block next to them.
                                '& .MuiAlert-action': { alignItems: 'center', alignSelf: 'stretch', my: 0 },
                            }}
                            action={(
                                <Stack
                                    direction="row"
                                    spacing={1}
                                    sx={{ alignItems: 'center', flexWrap: 'nowrap', flexShrink: 0, whiteSpace: 'nowrap' }}
                                >
                                    {failureRunId && (
                                        <Button
                                            size="small"
                                            variant="outlined"
                                            color="inherit"
                                            sx={{ fontWeight: 600 }}
                                            onClick={() => openUpgradeLog(failureRunId)}
                                        >
                                            {t('settingsPage.upgrade.diagnostic.viewLog')}
                                        </Button>
                                    )}
                                    {status.upgrade_available && (
                                        <Button
                                            size="small"
                                            variant="outlined"
                                            color="inherit"
                                            sx={{ fontWeight: 600 }}
                                            disabled={upgradeCheckBusy || status.state === 'downloading' || preparingUpgrade}
                                            onClick={() => void handleRetryUpgrade()}
                                        >
                                            {t('settingsPage.upgrade.actions.retry')}
                                        </Button>
                                    )}
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        color="inherit"
                                        sx={{ fontWeight: 600 }}
                                        onClick={() => window.open(UPGRADE_SUPPORT_URL(isChineseLocale), '_blank', 'noopener,noreferrer')}
                                    >
                                        {t('settingsPage.upgrade.diagnostic.support')}
                                    </Button>
                                </Stack>
                            )}
                        >
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                {upgradeResultNotice.message}
                            </Typography>
                            {failureReason && (
                                <Typography variant="body2" sx={{ mt: 0.5 }}>
                                    <Box component="span" sx={{ color: 'text.secondary' }}>{t('settingsPage.upgrade.reasonLabel')}</Box>
                                    {failureReason}
                                </Typography>
                            )}
                        </Alert>
                    </div>
                )}
                <div className="settings-form-row">
                    <Typography className="settings-form-label">{t('settingsPage.upgrade.currentVersion')}{t('settingsPage.upgrade.labelSuffix')}</Typography>
                    <div className="settings-form-control">
                        <Typography className="settings-form-value" variant="body2" component="span">
                            {currentVersion}
                        </Typography>
                        {!status.upgrade_available && (
                            <Button
                                size="small"
                                variant="contained"
                                sx={{ ml: 1.5, verticalAlign: 'middle' }}
                                onClick={() => void handleCheckUpgrade()}
                                disabled={upgradeCheckBusy}
                            >
                                {/* Only a manual check relabels the button. Background status refreshes
                                    merely disable it, so the label never flickers. */}
                                {checkingUpgrade ? t('settingsPage.upgrade.actions.checking') : t('settingsPage.upgrade.actions.check')}
                            </Button>
                        )}
                    </div>
                    <div className="settings-form-actions" />
                </div>

                {status.upgrade_available && (
                    <>
                        <div className="settings-form-row">
                            <Typography className="settings-form-label">{t('settingsPage.upgrade.latestVersion')}{t('settingsPage.upgrade.labelSuffix')}</Typography>
                            <div className="settings-form-control">
                                <Stack direction="row" spacing={3} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                                    <Typography className="settings-form-value" variant="body2">
                                        {status.latest_version}
                                    </Typography>
                                    <Stack direction="row" spacing={1.5} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                                        {status.state === 'downloading' || status.state === 'applying' || preparingUpgrade ? (
                                            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                                                <CircularProgress size={16} />
                                                <Typography variant="body2" color="text.secondary">
                                                    {status.state === 'applying'
                                                        ? t('settingsPage.upgrade.applying')
                                                        : t('settingsPage.upgrade.actions.downloading')}
                                                </Typography>
                                            </Stack>
                                        ) : status.state === 'ready' ? (
                                            <Button size="small" color="warning" variant="contained" onClick={() => setApplyConfirmationOpen(true)} disabled={applyingUpgrade}>
                                                {t('settingsPage.upgrade.actions.apply')}
                                            </Button>
                                        ) : upgradeResultNotice ? (
                                            // After a failure the retry lives in the failure banner, so the
                                            // same action is not offered twice on one screen.
                                            null
                                        ) : (
                                            <Button size="small" variant="contained" onClick={handlePrepareUpgrade}>
                                                {t('settingsPage.upgrade.actions.download')}
                                            </Button>
                                        )}
                                        {sessionFailure && (
                                            <Tooltip title={upgradeFailureDetail}>
                                                <Typography variant="caption" sx={{ color: 'error.main', cursor: 'help' }}>
                                                    {t('settingsPage.upgrade.actions.downloadFailed')}
                                                </Typography>
                                            </Tooltip>
                                        )}
                                    </Stack>
                                </Stack>
                                {status.state === 'ready' && (
                                    <Typography variant="caption" sx={{ mt: 0.5, display: 'block', color: 'text.secondary' }}>
                                        {t('settingsPage.upgrade.downloadedHint')}
                                    </Typography>
                                )}
                            </div>
                            <div className="settings-form-actions" />
                        </div>

                    </>
                )}

                <div className="settings-form-row">
                    <Typography className="settings-form-label">{t('settingsPage.upgrade.manualLabel')}{t('settingsPage.upgrade.labelSuffix')}</Typography>
                    <div className="settings-form-control">
                        <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>
                            {t('settingsPage.upgrade.manualHint')}
                        </Typography>
                    </div>
                    <div className="settings-form-actions">
                        <Button size="small" variant="text" onClick={() => setUpgradeManualOpen(true)}>
                            {t('settingsPage.upgrade.actions.viewMethod')}
                        </Button>
                    </div>
                </div>

                <SurfaceDialog
                    open={upgradeManualOpen}
                    onClose={() => setUpgradeManualOpen(false)}
                    scope="content"
                    scopeRect={upgradeDialogScopeRect}
                    contentStrategy="viewport-fixed"
                    darkMode={isDarkMode}
                    maxWidth="sm"
                    // A short dialog reads better anchored near the top than dead centre.
                    sx={{
                        '& .MuiDialog-container': {
                            alignItems: 'flex-start',
                            pt: { xs: 3, md: 6 },
                        },
                    }}
                    paperSx={{
                        width: { xs: 'min(100%, 560px)', md: 'min(560px, calc(100% - 20px))' },
                        maxWidth: '560px',
                        backgroundColor: surfacePalette.dialogBg,
                        color: surfacePalette.text,
                        border: `1px solid ${surfacePalette.borderStrong}`,
                    }}
                >
                    <Box sx={{ px: 2.25, py: 1.5, borderBottom: `1px solid ${surfacePalette.divider}`, backgroundColor: surfacePalette.dialogBg }}>
                        <Typography sx={{ fontSize: 16, fontWeight: 700, color: surfacePalette.text }}>
                            {t('settingsPage.upgrade.manualLabel')}
                        </Typography>
                    </Box>
                    <Box sx={{ px: 2.25, py: 2, borderBottom: `1px solid ${surfacePalette.divider}`, backgroundColor: surfacePalette.dialogBg }}>
                        <Typography sx={{ m: 0, fontSize: 14, lineHeight: 1.7, color: surfacePalette.subtleText }}>
                            {t('settingsPage.upgrade.manualHint')}
                        </Typography>
                        <Box
                            component="pre"
                            sx={{
                                m: 0,
                                mt: 1.5,
                                p: 1.5,
                                fontSize: '0.8rem',
                                lineHeight: 1.6,
                                borderRadius: '2px',
                                border: `1px solid ${surfacePalette.border}`,
                                bgcolor: surfacePalette.panelSoft,
                                color: surfacePalette.text,
                                overflowX: 'auto',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-all',
                            }}
                        >
                            {status.install_command}
                        </Box>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.25, py: 1.25, backgroundColor: surfacePalette.dialogBg }}>
                        <Button onClick={() => setUpgradeManualOpen(false)} sx={upgradeDialogCancelButtonSx}>
                            {t('settingsPage.upgrade.actions.close')}
                        </Button>
                        <Button variant="contained" onClick={handleCopy} sx={upgradeDialogPrimaryButtonSx}>
                            {copied ? t('settingsPage.upgrade.actions.copied') : t('settingsPage.upgrade.actions.copy')}
                        </Button>
                    </Box>
                </SurfaceDialog>

                <SurfaceDialog
                    open={applyConfirmationOpen}
                    onClose={() => setApplyConfirmationOpen(false)}
                    scope="content"
                    scopeRect={upgradeDialogScopeRect}
                    contentStrategy="viewport-fixed"
                    darkMode={isDarkMode}
                    // A short dialog reads better anchored near the top than dead centre.
                    sx={{
                        '& .MuiDialog-container': {
                            alignItems: 'flex-start',
                            pt: { xs: 3, md: 6 },
                        },
                    }}
                    paperSx={{
                        width: { xs: 'min(100%, 560px)', md: 'min(560px, calc(100% - 20px))' },
                        maxWidth: '560px',
                        backgroundColor: surfacePalette.dialogBg,
                        color: surfacePalette.text,
                        border: `1px solid ${surfacePalette.borderStrong}`,
                    }}
                >
                    <Box sx={{ px: 2.25, py: 1.5, borderBottom: `1px solid ${surfacePalette.divider}`, backgroundColor: surfacePalette.dialogBg, display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <Typography sx={{ flex: 1, fontSize: 16, fontWeight: 700, color: surfacePalette.text }}>
                            {t('settingsPage.upgrade.confirm.title')}
                        </Typography>
                        <IconButton
                            onClick={() => setApplyConfirmationOpen(false)}
                            size="small"
                            sx={{ width: 36, height: 36, color: surfacePalette.subtleText, borderRadius: '999px', backgroundColor: 'transparent', '&:hover': { backgroundColor: 'transparent', color: surfacePalette.text, opacity: 0.84 } }}
                        >
                            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" /></svg>
                        </IconButton>
                    </Box>
                    <Box sx={{ px: 2.25, py: 2, borderBottom: `1px solid ${surfacePalette.divider}`, backgroundColor: surfacePalette.dialogBg }}>
                        <Typography sx={{ m: 0, fontSize: 14, lineHeight: 1.7, color: surfacePalette.subtleText }}>
                            {t('settingsPage.upgrade.confirm.body')}
                        </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.25, py: 1.25, backgroundColor: surfacePalette.dialogBg }}>
                        <Button onClick={() => setApplyConfirmationOpen(false)} sx={upgradeDialogCancelButtonSx}>
                            {t('settingsPage.upgrade.confirm.cancel')}
                        </Button>
                        <Button variant="contained" onClick={() => void handleApplyUpgrade()} sx={upgradeDialogPrimaryButtonSx}>
                            {t('settingsPage.upgrade.confirm.confirm')}
                        </Button>
                    </Box>
                </SurfaceDialog>

                {/* Failure explanation: the operator can read the run log without leaving the console. */}
                <SurfaceDialog
                    open={upgradeLogOpen}
                    onClose={() => setUpgradeLogOpen(false)}
                    scope="content"
                    scopeRect={upgradeDialogScopeRect}
                    contentStrategy="viewport-fixed"
                    darkMode={isDarkMode}
                    maxWidth="sm"
                    sx={{
                        '& .MuiDialog-container': {
                            alignItems: 'flex-start',
                            pt: { xs: 3, md: 6 },
                        },
                    }}
                    paperSx={{
                        // Same footprint as the service log dialog so both read the same way.
                        width: { xs: 'min(100%, 1100px)', md: 'min(1100px, calc(100% - 16px))' },
                        maxWidth: '1100px',
                        backgroundColor: surfacePalette.dialogBg,
                        color: surfacePalette.text,
                        border: `1px solid ${surfacePalette.borderStrong}`,
                    }}
                >
                    <Box sx={{ px: 2.25, py: 1.5, borderBottom: `1px solid ${surfacePalette.divider}`, backgroundColor: surfacePalette.dialogBg, display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        <Typography sx={{ flex: 1, fontSize: 16, fontWeight: 700, color: surfacePalette.text }}>
                            {failureRunId
                                ? `${t('settingsPage.upgrade.diagnostic.logTitle')} · ${failureRunId}`
                                : t('settingsPage.upgrade.diagnostic.logTitle')}
                        </Typography>
                        <Button
                            size="small"
                            variant="text"
                            disabled={upgradeLogLoading || !upgradeFailure?.run_id}
                            onClick={() => {
                                if (upgradeFailure?.run_id) {
                                    void loadUpgradeLog(String(upgradeFailure.run_id))
                                }
                            }}
                        >
                            {t('settingsPage.upgrade.diagnostic.refresh')}
                        </Button>
                        <IconButton
                            onClick={() => setUpgradeLogOpen(false)}
                            size="small"
                            sx={{ width: 36, height: 36, color: surfacePalette.subtleText, borderRadius: '999px', backgroundColor: 'transparent', '&:hover': { backgroundColor: 'transparent', color: surfacePalette.text, opacity: 0.84 } }}
                        >
                            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" /></svg>
                        </IconButton>
                    </Box>
                    <Box sx={{ px: 2.25, py: 2, borderBottom: `1px solid ${surfacePalette.divider}`, backgroundColor: surfacePalette.dialogBg }}>
                        {upgradeLogLoading ? (
                            <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                                <CircularProgress size={16} />
                                <Typography variant="body2" color="text.secondary">
                                    {t('settingsPage.upgrade.diagnostic.logLoading')}
                                </Typography>
                            </Stack>
                        ) : upgradeLogFailed ? (
                            <Typography variant="body2" color="error.main">
                                {t('settingsPage.upgrade.diagnostic.logFailed')}
                            </Typography>
                        ) : upgradeLog && upgradeLog.lines.length > 0 ? (
                            <>
                                {upgradeLog.source === 'runner' && (
                                    <Typography variant="caption" sx={{ display: 'block', mb: 1, color: surfacePalette.subtleText }}>
                                        {t('settingsPage.upgrade.diagnostic.logFromRunner')}
                                    </Typography>
                                )}
                                <Box
                                    component="pre"
                                    sx={{
                                        m: 0,
                                        p: 1.5,
                                        maxHeight: '46vh',
                                        overflow: 'auto',
                                        fontSize: '0.78rem',
                                        lineHeight: 1.6,
                                        borderRadius: '2px',
                                        border: `1px solid ${surfacePalette.border}`,
                                        bgcolor: surfacePalette.panelSoft,
                                        color: surfacePalette.text,
                                        whiteSpace: 'pre-wrap',
                                        wordBreak: 'break-all',
                                    }}
                                >
                                    {upgradeLog.lines.join('\n')}
                                </Box>
                                <Typography variant="caption" sx={{ display: 'block', mt: 1, color: surfacePalette.subtleText }}>
                                    {/* Only mention the window when the log was actually cut off. */}
                                    {upgradeLog.lines.length >= UPGRADE_LOG_TAIL
                                        ? t('settingsPage.upgrade.diagnostic.logTruncated', { count: upgradeLog.lines.length })
                                        : null}
                                </Typography>
                            </>
                        ) : (
                            <Typography variant="body2" color="text.secondary">
                                {t('settingsPage.upgrade.diagnostic.logEmpty')}
                            </Typography>
                        )}
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.25, py: 1.25, backgroundColor: surfacePalette.dialogBg }}>
                        <Button onClick={() => setUpgradeLogOpen(false)} sx={upgradeDialogCancelButtonSx}>
                            {t('settingsPage.upgrade.actions.close')}
                        </Button>
                        <Button
                            variant="contained"
                            disabled={!upgradeLog || upgradeLog.lines.length === 0}
                            onClick={() => {
                                if (upgradeLog) {
                                    copyPlainText(upgradeLog.lines.join('\n'))
                                    setUpgradeLogCopied(true)
                                    window.setTimeout(() => setUpgradeLogCopied(false), 2_000)
                                }
                            }}
                            sx={upgradeDialogPrimaryButtonSx}
                        >
                            {upgradeLogCopied ? t('settingsPage.upgrade.actions.copied') : t('settingsPage.upgrade.diagnostic.copyLog')}
                        </Button>
                    </Box>
                </SurfaceDialog>
            </>
        )
    }

    function renderActiveModuleRows() {
        if (activeModule === 'app-domain') {
            return renderDomainRow(globalDomainItem)
        }

        if (activeModule === 'app-mirror') {
            return renderMirrorRow(mirrorItem)
        }

        if (activeModule === 'app-ports') {
            return renderPortRangeRow(portRangeItem)
        }

        if (activeModule === 'platform-brand') {
            return renderBrandRows()
        }

        if (activeModule === 'platform-domain') {
            return renderPlatformDomainRows()
        }

        return renderUpgradeRow()
    }

    function moduleHasChanges(moduleId: SettingsModuleId) {
        const draftKeys = getModuleDraftKeys(moduleId)
        const hasDrafts = draftKeys.some((draftKey) => hasDraftValue(draftKey))

        if (moduleId === 'app-mirror') {
            const mirrorDraftKey = mirrorItem ? getDraftKey(mirrorItem) : ''
            return hasDrafts || Boolean(mirrorDraftKey && (mirrorPendingInputs[mirrorDraftKey] ?? '').trim())
        }

        return hasDrafts
    }

    const showModuleFooter = activeModule !== 'platform-system'
    const saveDisabled = savingModule === activeModule || !moduleHasChanges(activeModule)
    const resetDisabled = savingModule === activeModule || !moduleHasChanges(activeModule)

    if (isLoading) {
        return (
            <Box className="settings-page settings-page--loading">
                <CircularProgress size={28} />
                <Typography color="text.secondary" variant="body2">
                    {t('settingsPage.states.loading')}
                </Typography>
            </Box>
        )
    }

    return (
        <Box className="settings-page">
            <Stack spacing={2}>
                <PageDescriptionHeader title={t('nav.settings.label')} description={t('settingsPage.hero.description')} />

                <Box className="settings-page-shell" ref={settingsPageShellRef}>
                    <Box className="settings-outer-card">
                        <Box className="settings-page-grid">
                            <Box className="settings-nav-area">
                                <Box className="settings-nav-content">
                                    {navGroups.map((group) => (
                                        <Box className="settings-nav-group" key={group.id}>
                                            <Typography className="settings-nav-group-title">{group.title}</Typography>
                                            <List disablePadding className="settings-nav-list">
                                                {group.modules.map((module) => (
                                                    <ListItemButton
                                                        className={`settings-nav-item ${activeModule === module.id ? 'active' : ''}`}
                                                        key={module.id}
                                                        onClick={() => setActiveModule(module.id)}
                                                    >
                                                        <Typography className="settings-nav-item-label">{t(module.titleKey)}</Typography>
                                                    </ListItemButton>
                                                ))}
                                            </List>
                                        </Box>
                                    ))}
                                </Box>
                            </Box>

                            <Box className="settings-module-area" id={activeModule === 'platform-system' ? 'version-and-upgrade' : activeModule === 'app-ports' ? 'application-ports' : undefined}>
                                <Box className="settings-module-header">
                                    <span className="settings-module-indicator" />
                                    <Box className="settings-module-headline">
                                        <Typography className="settings-module-title">{t(activeModuleConfig.titleKey)}</Typography>
                                        <Typography className="settings-module-subtitle">{t(activeModuleConfig.descriptionKey)}</Typography>
                                    </Box>
                                </Box>

                                <Box className="settings-module-card">
                                    <Box className="settings-form-table">{renderActiveModuleRows()}</Box>

                                    {showModuleFooter ? (
                                        <Box className="settings-panel-footer">
                                            <Stack direction="row" spacing={1}>
                                                <Button className="settings-action-button settings-action-button--primary" disabled={saveDisabled} onClick={() => void handleSaveActiveModule()} size="small" variant="contained">
                                                    {savingModule === activeModule ? t('settingsPage.actions.saving') : t('settingsPage.actions.save')}
                                                </Button>
                                                <Button className="settings-action-button" disabled={resetDisabled} onClick={resetActiveModuleDrafts} size="small" variant="outlined">
                                                    {t('settingsPage.actions.reset')}
                                                </Button>
                                            </Stack>
                                        </Box>
                                    ) : null}
                                </Box>
                            </Box>
                        </Box>
                    </Box>
                </Box>

                {error && !(isConnectionUnavailable && isPlatformUnavailableError(error)) ? <Alert severity="error">{error.message}</Alert> : null}

                <SurfaceFeedbackToast
                    open={toastOpen}
                    severity={feedback?.severity ?? 'success'}
                    message={feedback?.message ?? ''}
                    onClose={() => setToastOpen(false)}
                />
            </Stack>
        </Box>
    )
}