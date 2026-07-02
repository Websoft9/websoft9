import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    List,
    ListItemButton,
    Stack,
    Switch,
    TextField,
    Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useAppColorMode } from '../../app/providers/color-mode'
import { getSurfaceFieldSx } from '../../shared/design-system/form-field-sx'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { getSurfacePalette } from '../../shared/design-system/surface-theme'
import { SurfaceFeedbackToast } from '../../shared/design-system/standard-surfaces'
import './settings-page.css'

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

type SettingsModuleId = 'app-domain' | 'app-mirror' | 'platform-brand' | 'platform-domain' | 'platform-system'

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

const SETTINGS_MODULES: SettingsModule[] = [
    {
        id: 'app-domain',
        group: 'applications',
        titleKey: 'settingsPage.modules.appDomain.title',
        descriptionKey: 'settingsPage.modules.appDomain.description',
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
    const isDarkMode = colorMode === 'dark'
    const surfacePalette = getSurfacePalette(isDarkMode)
    const settingsFieldSx = getSurfaceFieldSx(surfacePalette)
    const [drafts, setDrafts] = useState<Record<string, string>>({})
    const [mirrorPendingInputs, setMirrorPendingInputs] = useState<Record<string, string>>({})
    const [activeModule, setActiveModule] = useState<SettingsModuleId>('app-domain')
    const [feedback, setFeedback] = useState<{ severity: 'success' | 'error'; message: string } | null>(null)
    const [toastOpen, setToastOpen] = useState(false)
    const [savingModule, setSavingModule] = useState<SettingsModuleId | null>(null)
    const [reuseLogo, setReuseLogo] = useState<boolean>(false)
    const [useDomain, setUseDomain] = useState<boolean>(false)
    const [uploadingLogo, setUploadingLogo] = useState(false)
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
    const { data, error, isLoading, refetch } = useQuery<SettingsSummaryResponse, SettingsError>({
        queryKey: ['settings-summary'],
        queryFn: fetchSettingsSummary,
        staleTime: 5_000,
    })

    const items = data?.groups.flatMap((group) => group.items) ?? []
    const boundDomainItem = items.find((item) => item.group === 'platform_gateway' && item.key === 'bound_domain') ?? null
    const globalDomainItem = items.find((item) => item.group === 'domain' && item.key === 'wildcard_domain') ?? null
    const httpsItem = items.find((item) => item.group === 'platform_gateway' && item.key === 'https_enabled') ?? null
    const forceHttpsItem = items.find((item) => item.group === 'platform_gateway' && item.key === 'force_https') ?? null
    const mirrorItem = items.find((item) => item.group === 'docker_mirror' && item.key === 'url') ?? null
    const brandTitleItem = items.find((item) => item.group === 'platform_brand' && item.key === 'title') ?? null
    const brandLogoItem = items.find((item) => item.group === 'platform_brand' && item.key === 'logo_url') ?? null
    const brandFaviconItem = items.find((item) => item.group === 'platform_brand' && item.key === 'favicon_url') ?? null
    const versionItem = items.find((item) => item.group === 'version' && item.key === 'product') ?? null
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

        if (moduleId === 'platform-brand') {
            return [brandTitleItem, brandLogoItem, brandFaviconItem].filter((item): item is SettingsSummaryItem => item !== null)
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

        return getModuleItems(moduleId).map(getDraftKey)
    }

    function resetActiveModuleDrafts() {
        clearDraftKeys(getModuleDraftKeys(activeModule))
        setFeedback(null)
    }

    function validateItemValue(item: SettingsSummaryItem, nextValue: string) {
        const trimmed = nextValue.trim()

        if (!trimmed && item.group !== 'domain') {
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
                return t('settingsPage.validation.url')
            }
        }

        if (item.group === 'platform_brand' && (item.key === 'logo_url' || item.key === 'favicon_url') && !isPlatformBrandLogoUrl(nextValue)) {
            return t('settingsPage.validation.logoUrl')
        }

        return null
    }

    async function saveSimpleModule(moduleId: SettingsModuleId) {
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
                            <img className="settings-brand-preview-logo" key={previewLogoSrc} src={previewLogoSrc} alt="Logo preview" />
                            <span className="settings-brand-preview-title">{previewTitle}</span>
                        </div>
                        <div className="settings-brand-preview-browser">
                            <div className="settings-brand-preview-tab">
                                <img className="settings-brand-preview-favicon" key={previewFaviconSrc} src={previewFaviconSrc} alt="Favicon preview" />
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
            </>
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
        return (
            <div className="settings-form-row">
                <Typography className="settings-form-label">{t('settingsPage.upgrade.label')}：</Typography>

                <Stack className="settings-form-control" direction={{ xs: 'column', md: 'row' }} spacing={1}>
                    <Button disabled size="small" variant="contained">
                        {t('settingsPage.upgrade.actions.precheck')}
                    </Button>
                    <Button disabled size="small" variant="outlined">
                        {t('settingsPage.upgrade.actions.start')}
                    </Button>
                </Stack>

                <div className="settings-form-actions" />
            </div>
        )
    }

    function renderVersionRow() {
        const locale = i18n.resolvedLanguage === 'zh-CN' ? 'zh-CN' : 'en'
        const localizedEditionName = versionItem?.metadata?.edition_names?.[locale] || versionItem?.metadata?.edition_names?.en || versionItem?.metadata?.edition_names?.['zh-CN'] || ''
        const semanticVersion = versionItem?.metadata?.version || ''
        const displayVersion = `${localizedEditionName} ${semanticVersion}`.trim() || versionItem?.value || t('settingsPage.values.notConfigured')

        return (
            <div className="settings-form-row">
                <Typography className="settings-form-label">{t('settingsPage.version.label')}：</Typography>

                <div className="settings-form-control">
                    <Typography className="settings-form-value" variant="body2">
                        {displayVersion}
                    </Typography>
                </div>

                <div className="settings-form-actions" />
            </div>
        )
    }

    function renderActiveModuleRows() {
        if (activeModule === 'app-domain') {
            return renderDomainRow(globalDomainItem)
        }

        if (activeModule === 'app-mirror') {
            return renderMirrorRow(mirrorItem)
        }

        if (activeModule === 'platform-brand') {
            return renderBrandRows()
        }

        if (activeModule === 'platform-domain') {
            return renderPlatformDomainRows()
        }

        return (
            <>
                {renderVersionRow()}
                {renderUpgradeRow()}
            </>
        )
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

                <Box className="settings-page-shell">
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

                            <Box className="settings-module-area">
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

                {error ? <Alert severity="error">{error.message}</Alert> : null}

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