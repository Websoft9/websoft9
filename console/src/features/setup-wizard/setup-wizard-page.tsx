import {
    Alert,
    Box,
    Button,
    CircularProgress,
    IconButton,
    InputAdornment,
    Paper,
    Stack,
    Step,
    StepLabel,
    Stepper,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useProductAuth } from '../product-auth/product-auth-provider'
import { markMyAppsDetailOverlayIntent } from '../my-apps/my-app-detail-overlay-intent'
import { normalizeSupportedLocale } from '../../shared/i18n/i18n'

type WizardStep = 'welcome' | 'platform_init' | 'app_init_ready' | 'app_init_running' | 'app_init_failed' | 'complete'

type SetupWizardError = {
    code: string
    message: string
    retryable: boolean
    field_names?: string[]
}

type SetupWizardState = {
    enabled: boolean
    current_step: WizardStep
    app_slug: string | null
    default_locale?: string | null
    installed_app_id: string | null
    completed: boolean
    tracking_id: string | null
    pending_app_id: string | null
    last_error: SetupWizardError | null
    updated_at: string
    completed_at?: string | null
}

type SetupWizardInputField = {
    name: string
    label: string
    type: 'text' | 'number' | 'password'
    required: boolean
    default_value?: string | null
    placeholder?: string | null
    description?: string | null
}

type SetupWizardApp = {
    app_slug: string
    display_name: string
    logo_url?: string | null
    edition: string
    default_app_id: string
    is_web_app: boolean
    requires_user_inputs: boolean
    required_inputs: SetupWizardInputField[]
    settings: Record<string, string>
}

type SetupWizardInstallAcceptedResponse = {
    tracking_id: string
    current_step: WizardStep
}

type SetupWizardInstallStatusResponse = {
    status: 'running' | 'succeeded' | 'failed'
    current_step: WizardStep
    installed_app_id: string | null
    last_error: SetupWizardError | null
}

type SetupWizardInstalledAppSummary = {
    app_id: string
    status: number
    error?: string | null
}

type ProductAuthStatus = {
    authenticated: boolean
    initialization_required: boolean
    cloud_marketplace_setup_pending?: boolean
}

const STARTUP_MIN_VISIBLE_MS = 5000
const STARTUP_MAX_WAIT_MS = 180000

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

function resolveApiLocale(locale: string) {
    return locale.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

function isValidPassword(value: string) {
    return value.length >= 8 && /[A-Z]/.test(value) && /[a-z]/.test(value) && /\d/.test(value) && /[^A-Za-z0-9]/.test(value)
}

function mapSetupWizardErrorMessage(message: string | null, locale: 'zh' | 'en') {
    if (!message) {
        return locale === 'zh' ? '操作失败，请重试。' : 'The request failed. Please try again.'
    }

    const normalized = message.trim().toLowerCase()
    if (normalized === 'sign in before continuing the setup wizard') {
        return locale === 'zh' ? '当前会话已失效，请刷新页面后重试。' : 'Your session expired. Refresh the page and try again.'
    }

    if (normalized === 'authentication required') {
        return locale === 'zh' ? '当前会话已失效，请刷新页面后重试。' : 'Your session expired. Refresh the page and try again.'
    }

    return message
}

function normalizeVisibleStep(step: WizardStep): WizardStep {
    if (step === 'app_init_ready' || step === 'app_init_failed') {
        return 'app_init_running'
    }
    return step
}

export function SetupWizardPage() {
    const { i18n } = useTranslation('shell')
    const navigate = useNavigate()
    const { initialize, isLoading, isSubmitting, status } = useProductAuth() as {
        initialize: (payload: { username: string; password: string; email: string; locale: string; createSession?: boolean }) => Promise<ProductAuthStatus>
        isLoading: boolean
        isSubmitting: boolean
        status: (ProductAuthStatus & { enabled?: boolean }) | null
    }
    const [wizardState, setWizardState] = useState<SetupWizardState | null>(null)
    const [appInfo, setAppInfo] = useState<SetupWizardApp | null>(null)
    const [currentStep, setCurrentStep] = useState<WizardStep>('welcome')
    const [pageLoading, setPageLoading] = useState(true)
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [inputValues, setInputValues] = useState<Record<string, string>>({})
    const [completedAppId, setCompletedAppId] = useState<string | null>(null)
    const [showPassword, setShowPassword] = useState(false)
    const [showConfirmPassword, setShowConfirmPassword] = useState(false)

    const pollTimerRef = useRef<number | null>(null)
    const appStatusTimerRef = useRef<number | null>(null)
    const startupStartedAtRef = useRef<number | null>(null)
    const activationWaitStartedAtRef = useRef<number | null>(null)
    const resolvedWizardLocale = normalizeSupportedLocale(i18n.resolvedLanguage ?? i18n.language ?? 'en')
    const apiLocale = resolveApiLocale(resolvedWizardLocale)
    const platformInitializationRequired = Boolean(status?.initialization_required)
    const setupClosed = typeof window !== 'undefined' && window.sessionStorage.getItem('websoft9_setup_closed') === '1'

    function openMyAppsWithDetail(appId: string | null | undefined, options?: { replace?: boolean }) {
        const normalizedAppId = (appId ?? '').trim()
        if (normalizedAppId) {
            markMyAppsDetailOverlayIntent(normalizedAppId)
            navigate(`/myapps/${encodeURIComponent(normalizedAppId)}`, { replace: options?.replace ?? true })
            return
        }
        navigate('/myapps', { replace: options?.replace ?? true })
    }

    const displayName = appInfo?.display_name ?? wizardState?.app_slug ?? (apiLocale === 'zh' ? '应用' : 'App')
    const stepIndex = useMemo(() => {
        if (currentStep === 'welcome') return 0
        if (currentStep === 'platform_init') return 1
        return 2
    }, [currentStep])

    const steps = useMemo(() => (
        apiLocale === 'zh'
            ? ['开始使用', '创建平台账号', `启动 ${displayName}`]
            : ['Get Started', 'Create Platform Account', `Launch ${displayName}`]
    ), [apiLocale, displayName])

    const headerTitle = apiLocale === 'zh' ? `欢迎使用 ${displayName} on Websoft9` : `Welcome to ${displayName} on Websoft9`
    const welcomeBodyText = apiLocale === 'zh'
        ? `${displayName} 马上就绪。完成以下步骤后，即可通过 Websoft9 进入应用，并在同一个控制台中统一管理访问入口、运行状态与日常运维。`
        : `${displayName} is ready. Complete the steps below to enter the app through Websoft9 and manage access, runtime status, and daily operations from one console.`
    const welcomeIntroDetail = apiLocale === 'zh'
        ? platformInitializationRequired
            ? `完成后，你将获得统一的应用入口、运行状态查看与日常运维能力，无需再分散管理。`
            : `平台账号已就绪，可直接继续完成 ${displayName} 初始化，开始使用平台的统一管理能力。`
        : platformInitializationRequired
            ? `When done, you'll have a unified app entry, runtime status visibility, and daily operations — no more scattered management.`
            : `A platform account is already available. Continue with ${displayName} initialization to start using the platform's unified management capabilities.`
    const primaryActionLabel = apiLocale === 'zh' ? '下一步' : 'Next Step'
    const completionTitle = apiLocale === 'zh' ? '一切就绪' : 'All Set'
    const completionBody = apiLocale === 'zh'
        ? `初始化完成。进入控制台即可管理 ${displayName} 的安全、访问、监控与维护。`
        : `Setup complete. Enter the console to manage ${displayName} security, access, monitoring, and maintenance.`
    const completionNote = apiLocale === 'zh'
        ? null
        : null
    const appWorkspaceLabel = apiLocale === 'zh' ? '进入控制台' : 'Open Console'
    const welcomePlatformPoints = apiLocale === 'zh'
        ? [
            '统一管理应用入口、访问地址与对外路由',
            '集中查看运行状态、服务日志与基础资源信息',
            '提供终端、文件、权限、备份等应用运维与平台管理能力',
        ]
        : [
            'Unified application entry, access address, and external routing',
            'Centralized runtime status, service logs, and basic resource visibility',
            'Terminal, file, permissions, backup, and platform management capabilities',
        ]
    const setupFieldSx = useMemo(
        () => ({
            '& .MuiOutlinedInput-root': {
                borderRadius: '4px',
                backgroundColor: '#ffffff',
            },
            '& input:-webkit-autofill': {
                WebkitBoxShadow: '0 0 0 100px #ffffff inset',
                WebkitTextFillColor: '#0f172a',
                caretColor: '#0f172a',
                borderRadius: '4px',
                transition: 'background-color 9999s ease-out 0s',
            },
            '& input:-webkit-autofill:hover': {
                WebkitBoxShadow: '0 0 0 100px #ffffff inset',
                WebkitTextFillColor: '#0f172a',
            },
            '& input:-webkit-autofill:focus': {
                WebkitBoxShadow: '0 0 0 100px #ffffff inset',
                WebkitTextFillColor: '#0f172a',
            },
        }),
        [],
    )
    const setupPasswordValid = useMemo(() => password.length === 0 || isValidPassword(password), [password])
    const setupPasswordsMatch = useMemo(
        () => confirmPassword.length === 0 || password === confirmPassword,
        [confirmPassword, password],
    )
    const summaryCardSx = {
        borderRadius: '4px',
        border: '1px solid #dbe4f0',
        background: '#ffffff',
        px: { xs: 2.5, md: 3.25 },
        py: { xs: 2.5, md: 3.25 },
        boxShadow: 'none',
    }
    const actionRowSx = {
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'center',
        gap: 1.25,
        pt: 1,
    }
    const primaryActionButtonSx = {
        minWidth: 170,
        py: 1.1,
        fontSize: 15,
        fontWeight: 600,
        borderRadius: '4px',
    }

    useEffect(() => () => {
        if (pollTimerRef.current !== null) {
            window.clearTimeout(pollTimerRef.current)
        }
        if (appStatusTimerRef.current !== null) {
            window.clearTimeout(appStatusTimerRef.current)
        }
    }, [])

    useEffect(() => {
        if (isLoading || !status) {
            return
        }

        let active = true
        setPageLoading(true)
        requestJson<SetupWizardState>('/api/setup-wizard/state', { method: 'GET' })
            .then(async (statePayload) => {
                // If the marketplace bootstrap specifies a default locale and the
                // user hasn't explicitly switched languages, apply it immediately.
                const bootstrapLocale = statePayload.default_locale
                if (bootstrapLocale && normalizeSupportedLocale(bootstrapLocale) !== resolvedWizardLocale) {
                    await i18n.changeLanguage(normalizeSupportedLocale(bootstrapLocale))
                }
                const effectiveLocale = normalizeSupportedLocale(i18n.language ?? 'en')
                const effectiveApiLocale = resolveApiLocale(effectiveLocale)
                const appPayload = await requestJson<SetupWizardApp>(`/api/setup-wizard/app?locale=${encodeURIComponent(effectiveApiLocale)}`, { method: 'GET' })
                if (!active) {
                    return
                }
                setWizardState(statePayload)
                setAppInfo(appPayload)
                setInputValues((currentValue) => {
                    const nextValues = { ...currentValue }
                    for (const field of appPayload.required_inputs ?? []) {
                        if (!(field.name in nextValues)) {
                            nextValues[field.name] = field.default_value ?? ''
                        }
                    }
                    return nextValues
                })
                setCurrentStep(normalizeVisibleStep(statePayload.current_step))
                setError(statePayload.last_error?.message ? mapSetupWizardErrorMessage(statePayload.last_error.message, apiLocale) : null)
            })
            .catch(() => {
                if (!active) {
                    return
                }
                // Setup wizard is not enabled in this runtime (non-cloud environment).
                // Redirect based on current auth state instead of showing an error.
                if (status?.initialization_required) {
                    navigate('/auth/setup', { replace: true })
                } else if (!status?.authenticated) {
                    navigate('/auth/login', { replace: true })
                } else {
                    navigate('/dashboard', { replace: true })
                }
            })
            .finally(() => {
                if (active) {
                    setPageLoading(false)
                }
            })

        return () => {
            active = false
        }
    }, [apiLocale, isLoading, status])

    useEffect(() => {
        if (isLoading || !status || pageLoading || !wizardState) {
            return
        }

        if (!wizardState.completed) {
            if (typeof window !== 'undefined') {
                window.sessionStorage.removeItem('websoft9_setup_closed')
            }
        }

        if (setupClosed && status.authenticated && wizardState.completed) {
            openMyAppsWithDetail(wizardState.installed_app_id, { replace: true })
            return
        }

        if (!wizardState.enabled) {
            if (status.initialization_required) {
                navigate('/auth/setup', { replace: true })
                return
            }

            if (status.authenticated) {
                openMyAppsWithDetail(wizardState.installed_app_id, { replace: true })
            } else {
                navigate('/auth/login', { replace: true })
            }
            return
        }

        if (!status.authenticated && !platformInitializationRequired) {
            navigate('/auth/login?next=%2Fsetup', { replace: true })
            return
        }

        if (wizardState.completed) {
            setCompletedAppId(wizardState.installed_app_id)
            setError(null)
            return
        }
    }, [isLoading, navigate, pageLoading, platformInitializationRequired, setupClosed, status, wizardState])

    useEffect(() => {
        if (!wizardState?.completed || !wizardState.installed_app_id) {
            if (appStatusTimerRef.current !== null) {
                window.clearTimeout(appStatusTimerRef.current)
                appStatusTimerRef.current = null
            }
            return
        }

        let cancelled = false
        setCompletedAppId(wizardState.installed_app_id)
        setError(null)
        setCurrentStep('app_init_running')
        activationWaitStartedAtRef.current = Date.now()

        const finishWithReadyState = () => {
            if (cancelled) {
                return
            }
            setCurrentStep('complete')
            setError(null)
            if (typeof window !== 'undefined') {
                window.sessionStorage.setItem('websoft9_setup_closed', '1')
            }
            openMyAppsWithDetail(wizardState.installed_app_id, { replace: true })
        }

        const pollInstalledAppStatus = async () => {
            try {
                const waitElapsed = Date.now() - (activationWaitStartedAtRef.current ?? Date.now())
                if (waitElapsed >= STARTUP_MAX_WAIT_MS) {
                    setError(null)
                    if (typeof window !== 'undefined') {
                        window.sessionStorage.setItem('websoft9_setup_closed', '1')
                    }
                    openMyAppsWithDetail(wizardState.installed_app_id, { replace: true })
                    return
                }

                const apps = await requestJson<SetupWizardInstalledAppSummary[]>(`/api/apps?locale=${encodeURIComponent(apiLocale)}`, { method: 'GET' })
                if (cancelled) {
                    return
                }

                const targetApp = apps.find((app) => app.app_id === wizardState.installed_app_id)
                if (!targetApp || targetApp.status === 3) {
                    appStatusTimerRef.current = window.setTimeout(pollInstalledAppStatus, 2000)
                    return
                }

                if (targetApp.status === 4) {
                    setError(mapSetupWizardErrorMessage(targetApp.error ?? (apiLocale === 'zh' ? '应用启动失败。' : 'App launch failed.'), apiLocale))
                    setCurrentStep('app_init_running')
                    return
                }

                const startupElapsed = Date.now() - (startupStartedAtRef.current ?? Date.now())
                const remainingVisible = Math.max(0, STARTUP_MIN_VISIBLE_MS - startupElapsed)
                if (remainingVisible > 0) {
                    appStatusTimerRef.current = window.setTimeout(finishWithReadyState, remainingVisible)
                    return
                }

                finishWithReadyState()
            } catch {
                if (!cancelled) {
                    appStatusTimerRef.current = window.setTimeout(pollInstalledAppStatus, 3000)
                }
            }
        }

        void pollInstalledAppStatus()
        return () => {
            cancelled = true
            if (appStatusTimerRef.current !== null) {
                window.clearTimeout(appStatusTimerRef.current)
                appStatusTimerRef.current = null
            }
        }
    }, [apiLocale, wizardState?.completed, wizardState?.installed_app_id])

    useEffect(() => {
        if (!wizardState?.tracking_id || currentStep !== 'app_init_running') {
            if (pollTimerRef.current !== null) {
                window.clearTimeout(pollTimerRef.current)
                pollTimerRef.current = null
            }
            return
        }

        let cancelled = false
        const poll = async () => {
            try {
                const payload = await requestJson<SetupWizardInstallStatusResponse>(`/api/setup-wizard/install/${encodeURIComponent(wizardState.tracking_id as string)}`, { method: 'GET' })
                if (cancelled) {
                    return
                }
                if (payload.status === 'running') {
                    pollTimerRef.current = window.setTimeout(poll, 2000)
                    return
                }
                if (payload.status === 'failed') {
                    setCurrentStep('app_init_running')
                    setError(mapSetupWizardErrorMessage(payload.last_error?.message ?? (apiLocale === 'zh' ? '准备失败，请重试。' : 'Preparation failed. Please retry.'), apiLocale))
                    setWizardState((currentValue) => currentValue ? {
                        ...currentValue,
                        current_step: 'app_init_running',
                        tracking_id: null,
                        last_error: payload.last_error,
                    } : currentValue)
                    return
                }

                if (payload.installed_app_id) {
                    const completion = await requestJson<{ installed_app_id: string }>('/api/setup-wizard/complete', {
                        method: 'POST',
                        body: JSON.stringify({}),
                    })
                    if (!cancelled) {
                        setCompletedAppId(completion.installed_app_id)
                        setError(null)
                        setCurrentStep('app_init_running')
                        setWizardState((currentValue) => currentValue ? {
                            ...currentValue,
                            current_step: 'complete',
                            completed: true,
                            installed_app_id: completion.installed_app_id,
                            tracking_id: null,
                            last_error: null,
                        } : currentValue)
                    }
                }
            } catch (pollError) {
                if (!cancelled) {
                    setError(pollError instanceof Error ? mapSetupWizardErrorMessage(pollError.message, apiLocale) : apiLocale === 'zh' ? '正在准备时发生错误。' : 'An error occurred while preparing the app.')
                }
            }
        }

        void poll()
        return () => {
            cancelled = true
            if (pollTimerRef.current !== null) {
                window.clearTimeout(pollTimerRef.current)
                pollTimerRef.current = null
            }
        }
    }, [apiLocale, currentStep, navigate, wizardState])

    async function handlePlatformInitSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setError(null)

        if (!username.trim()) {
            setError(apiLocale === 'zh' ? '请输入用户名。' : 'Enter a username.')
            return
        }
        if (!isValidPassword(password)) {
            setError(apiLocale === 'zh' ? '密码至少 8 位，且包含大小写、数字和符号。' : 'Password must be at least 8 characters and include uppercase, lowercase, number, and symbol.')
            return
        }
        if (password !== confirmPassword) {
            setError(apiLocale === 'zh' ? '两次输入的密码不一致。' : 'Passwords do not match.')
            return
        }

        setBusy(true)
        try {
            const initLocale = apiLocale === 'zh' ? 'zh-CN' : 'en'
            await initialize({ username: username.trim(), password, email: '', locale: initLocale })
            await requestJson<{ current_step: WizardStep }>('/api/setup-wizard/platform-init-complete', {
                method: 'POST',
                body: JSON.stringify({}),
            })
            // Jump to the running page and trigger install immediately
            setCurrentStep('app_init_running')
            setWizardState((currentValue) => currentValue ? {
                ...currentValue,
                current_step: 'app_init_running',
                tracking_id: null,
                last_error: null,
            } : currentValue)
            await handleStartUsing()
        } catch (submitError) {
            setError(submitError instanceof Error ? mapSetupWizardErrorMessage(submitError.message, apiLocale) : apiLocale === 'zh' ? '管理员创建失败。' : 'Failed to create the admin account.')
        } finally {
            setBusy(false)
        }
    }

    async function handleStartUsing() {
        if (!appInfo) {
            return
        }

        startupStartedAtRef.current = Date.now()
        activationWaitStartedAtRef.current = null
        setCurrentStep('app_init_running')
        setBusy(true)
        setError(null)
        try {
            const payload = await requestJson<SetupWizardInstallAcceptedResponse>('/api/setup-wizard/install', {
                method: 'POST',
                body: JSON.stringify({
                    app_id: appInfo.default_app_id,
                    edition: appInfo.edition,
                    domain_name: window.location.hostname || '127.0.0.1',
                    user_inputs: inputValues,
                }),
            })
            setCurrentStep(normalizeVisibleStep(payload.current_step))
            setWizardState((currentValue) => currentValue ? {
                ...currentValue,
                current_step: normalizeVisibleStep(payload.current_step),
                tracking_id: payload.tracking_id,
                pending_app_id: appInfo.default_app_id,
                last_error: null,
            } : currentValue)
        } catch (submitError) {
            setError(submitError instanceof Error ? mapSetupWizardErrorMessage(submitError.message, apiLocale) : apiLocale === 'zh' ? '开始使用失败。' : 'Failed to start the app.')
        } finally {
            setBusy(false)
        }
    }

    function handleWelcomeContinue() {
        if (platformInitializationRequired) {
            setCurrentStep('platform_init')
        } else {
            void handleStartUsing()
        }
    }

    function handleOpenAppWorkspace() {
        window.sessionStorage.setItem('websoft9_setup_closed', '1')
        openMyAppsWithDetail(completedAppId ?? wizardState?.installed_app_id, { replace: true })
    }

    function handleOpenPlatformOverview() {
        window.sessionStorage.setItem('websoft9_setup_failure_access', '1')
        window.sessionStorage.setItem('websoft9_setup_closed', '1')
        openMyAppsWithDetail(completedAppId ?? wizardState?.installed_app_id, { replace: true })
    }

    const installFailed = currentStep === 'app_init_running' && !wizardState?.tracking_id && Boolean(error)
    const installRunning = currentStep === 'app_init_running' && !installFailed
    const showTopError = !pageLoading && error && !installFailed && currentStep !== 'complete'
    const failedRawMessage = error ?? (apiLocale === 'zh' ? '暂无错误详情。' : 'No error details available.')

    return (
        <Box
            sx={{
                minHeight: '100vh',
                display: 'grid',
                placeItems: 'center',
                px: { xs: 2, md: 4 },
                py: { xs: 3, md: 5 },
                position: 'relative',
                background: '#f8fafc',
            }}
        >
            <Paper
                elevation={0}
                sx={{
                    width: '100%',
                    maxWidth: 1120,
                    borderRadius: '4px',
                    border: '1px solid rgba(148, 163, 184, 0.16)',
                    borderTop: '3px solid #1767d1',
                    background: '#ffffff',
                    p: { xs: 3, md: 5 },
                    boxShadow: '0 1px 3px rgba(15, 23, 42, 0.06), 0 20px 60px rgba(15, 23, 42, 0.07)',
                    position: 'relative',
                    zIndex: 1,
                    '& .MuiButton-root': {
                        borderRadius: '4px',
                        boxShadow: 'none',
                        textTransform: 'none',
                    },
                    '& .MuiAlert-root': {
                        borderRadius: '4px',
                    },
                    '& .MuiOutlinedInput-root': {
                        borderRadius: '4px',
                    },
                }}
            >
                <Stack spacing={3.5}>
                    {(pageLoading || isLoading) ? (
                        <Stack spacing={2} sx={{ alignItems: 'center', py: 6 }}>
                            <CircularProgress size={30} />
                            <Typography color="text.secondary">{apiLocale === 'zh' ? '正在加载…' : 'Loading…'}</Typography>
                        </Stack>
                    ) : (
                        <>
                            <Stack spacing={2.25} sx={{ pb: 0.5 }}>
                                <Stack spacing={0.35} sx={{ alignItems: 'center' }}>
                                    <Typography sx={{ fontSize: { xs: 26, md: 34 }, lineHeight: 1.12, fontWeight: 700, color: '#0f172a', letterSpacing: '-0.03em', textAlign: 'center' }}>
                                        {headerTitle}
                                    </Typography>
                                </Stack>

                                <Stepper
                                    activeStep={stepIndex}
                                    alternativeLabel
                                    sx={{
                                        px: { xs: 0.5, md: 1.5 },
                                        py: 1.25,
                                        borderRadius: '4px',
                                        border: '1px solid #dbe4f0',
                                        background: '#f8fbff',
                                        '& .MuiStep-root': { px: { xs: 0.25, md: 0.75 } },
                                        '& .MuiStepLabel-labelContainer': { overflow: 'visible' },
                                        '& .MuiStepLabel-label': {
                                            fontSize: { xs: 12, md: 13 },
                                            color: '#64748b',
                                            whiteSpace: 'pre-line',
                                            lineHeight: 1.35,
                                            wordBreak: 'break-word',
                                            textAlign: 'center',
                                            minHeight: { xs: 32, md: 36 },
                                        },
                                        '& .MuiStepLabel-label.Mui-active': { color: '#1767d1', fontWeight: 800 },
                                        '& .MuiStepLabel-label.Mui-completed': { color: '#1767d1', fontWeight: 700 },
                                        '& .MuiStepConnector-line': { borderColor: '#c9d8ef', borderTopWidth: 2 },
                                        '& .MuiStepIcon-root': { color: '#c9d8ef' },
                                        '& .MuiStepIcon-text': { fontSize: 11, fontWeight: 700 },
                                        '& .MuiStepIcon-root.Mui-active': { color: '#1767d1' },
                                        '& .MuiStepIcon-root.Mui-completed': { color: '#1767d1' },
                                    }}
                                >
                                    {steps.map((label) => (
                                        <Step key={label}>
                                            <StepLabel>{label}</StepLabel>
                                        </Step>
                                    ))}
                                </Stepper>
                            </Stack>

                            {showTopError ? <Alert severity="error">{error}</Alert> : null}

                            {!pageLoading && currentStep === 'welcome' ? (
                                <Box
                                    sx={{
                                        display: 'grid',
                                        gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' },
                                        gap: { xs: 3, lg: 4 },
                                        alignItems: 'stretch',
                                        py: { xs: 2, md: 4 },
                                    }}
                                >
                                    <Box sx={{ minWidth: 0, display: 'flex' }}>
                                        <Box sx={{ ...summaryCardSx, height: '100%', width: '100%', display: 'flex', flexDirection: 'column' }}>
                                            <Box>
                                                <Typography sx={{ color: '#475569', lineHeight: 1.8, fontSize: 15, maxWidth: 760 }}>
                                                    {welcomeBodyText}
                                                </Typography>
                                                <Typography sx={{ mt: 1.5, color: '#64748b', lineHeight: 1.8, fontSize: 15, maxWidth: 760 }}>
                                                    {welcomeIntroDetail}
                                                </Typography>
                                            </Box>
                                        </Box>
                                    </Box>

                                    <Box
                                        sx={{
                                            ...summaryCardSx,
                                            background: '#f8fbff',
                                            height: '100%',
                                        }}
                                    >
                                        <Stack spacing={2}>
                                            <Typography sx={{ fontSize: 15, fontWeight: 700, color: '#0f172a', letterSpacing: '-0.02em' }}>
                                                {apiLocale === 'zh' ? 'Websoft9 平台能力' : 'Websoft9 platform capabilities'}
                                            </Typography>
                                            <Stack spacing={1.5}>
                                                {welcomePlatformPoints.map((point) => (
                                                    <Box key={point} sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start' }}>
                                                        <Box sx={{ width: 8, height: 8, mt: 0.72, borderRadius: '999px', background: '#1767d1', flexShrink: 0 }} />
                                                        <Typography sx={{ color: '#475569', lineHeight: 1.75, fontSize: 14 }}>
                                                            {point}
                                                        </Typography>
                                                    </Box>
                                                ))}
                                            </Stack>
                                        </Stack>
                                    </Box>

                                    <Box sx={{ gridColumn: '1 / -1' }}>
                                        <Box sx={actionRowSx}>
                                            <Button
                                                variant="contained"
                                                size="large"
                                                onClick={handleWelcomeContinue}
                                                sx={{ ...primaryActionButtonSx, minWidth: { xs: '100%', sm: 170 } }}
                                            >
                                                {primaryActionLabel}
                                            </Button>
                                        </Box>
                                    </Box>
                                </Box>
                            ) : null}

                            {!pageLoading && currentStep === 'platform_init' && platformInitializationRequired ? (
                                <Box component="form" onSubmit={handlePlatformInitSubmit}>
                                    <Box
                                        sx={{
                                            display: 'grid',
                                            gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' },
                                            gap: { xs: 3, lg: 4 },
                                            alignItems: 'stretch',
                                            py: { xs: 1, md: 2 },
                                        }}
                                    >
                                        {/* Left: info card */}
                                        <Box sx={{ ...summaryCardSx, height: '100%', background: '#f8fbff' }}>
                                            <Typography sx={{ fontSize: 15, fontWeight: 700, color: '#0f172a', letterSpacing: '-0.02em', mb: 1.5 }}>
                                                {apiLocale === 'zh' ? '创建平台管理员账号' : 'Create the platform admin account'}
                                            </Typography>
                                            <Typography sx={{ color: '#475569', lineHeight: 1.8, fontSize: 15 }}>
                                                {apiLocale === 'zh'
                                                    ? `该账号用于登录 Websoft9 控制台，后续管理 ${displayName} 的访问、运行状态、日志与维护任务。`
                                                    : `This account is used to sign in to the Websoft9 console and manage ${displayName} access, runtime status, logs, and maintenance tasks.`}
                                            </Typography>
                                            <Stack spacing={1.2} sx={{ mt: 2 }}>
                                                {/* Password rule row — with inline generator button */}
                                                <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start' }}>
                                                    <Box sx={{ width: 8, height: 8, mt: 0.72, borderRadius: '999px', background: '#1767d1', flexShrink: 0 }} />
                                                    <Typography sx={{ color: '#475569', lineHeight: 1.7, fontSize: 14 }}>
                                                        {apiLocale === 'zh' ? '用户名至少 3 位，支持英文字母和数字' : 'Username must be at least 3 characters using letters and numbers'}
                                                    </Typography>
                                                </Box>

                                                {/* Password rule row */}
                                                <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start' }}>
                                                    <Box sx={{ width: 8, height: 8, mt: 0.72, borderRadius: '999px', background: '#1767d1', flexShrink: 0 }} />
                                                    <Typography sx={{ color: '#475569', lineHeight: 1.7, fontSize: 14 }}>
                                                        {apiLocale === 'zh' ? '密码 8 位以上，含大小写、数字和符号' : 'Min 8 chars with uppercase, lowercase, number, symbol'}
                                                    </Typography>
                                                </Box>

                                                <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start' }}>
                                                    <Box sx={{ width: 8, height: 8, mt: 0.72, borderRadius: '999px', background: '#1767d1', flexShrink: 0 }} />
                                                    <Typography sx={{ color: '#475569', lineHeight: 1.7, fontSize: 14 }}>
                                                        {apiLocale === 'zh' ? '请妥善保管登录凭据，这是平台唯一管理员账号' : 'Keep your credentials safe — this is the sole platform admin account'}
                                                    </Typography>
                                                </Box>
                                            </Stack>
                                        </Box>

                                        {/* Right: form card */}
                                        <Stack spacing={3.5} sx={{ ...summaryCardSx, height: '100%' }}>
                                            <Typography sx={{ fontSize: 15, fontWeight: 700, color: '#0f172a', letterSpacing: '-0.02em', mb: 0.5 }}>
                                                {apiLocale === 'zh' ? '管理员账号' : 'Admin account'}
                                            </Typography>
                                            <Box>
                                                <TextField size="small" label={apiLocale === 'zh' ? '用户名' : 'Username'} value={username} onChange={(event) => setUsername(event.target.value)} required sx={{ ...setupFieldSx, width: '100%' }} autoComplete="username" />
                                                {username.length > 0 && username.trim().length < 3 ? (
                                                    <Typography sx={{ fontSize: 12, color: '#d32f2f', mt: 0.5, ml: 0.5 }}>
                                                        {apiLocale === 'zh' ? '用户名至少 3 位。' : 'Username must be at least 3 characters.'}
                                                    </Typography>
                                                ) : null}
                                            </Box>
                                            <TextField
                                                size="small"
                                                label={apiLocale === 'zh' ? '密码' : 'Password'}
                                                type={showPassword ? 'text' : 'password'}
                                                value={password}
                                                onChange={(event) => setPassword(event.target.value)}
                                                required
                                                error={password.length > 0 && !setupPasswordValid}
                                                helperText={password.length > 0 && !setupPasswordValid ? (apiLocale === 'zh' ? '至少 8 位，包含大小写、数字和符号。' : 'At least 8 characters with uppercase, lowercase, number, and symbol.') : undefined}
                                                sx={{ ...setupFieldSx, width: '100%' }}
                                                autoComplete="new-password"
                                                slotProps={{
                                                    input: {
                                                        endAdornment: (
                                                            <InputAdornment position="end">
                                                                <Tooltip title={apiLocale === 'zh' ? '生成强密码' : 'Generate'}>
                                                                    <IconButton
                                                                        size="small"
                                                                        onClick={() => {
                                                                            const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%^&*'
                                                                            const pick = (set: string) => set[Math.floor(Math.random() * set.length)]
                                                                            const pwd = [
                                                                                pick('ABCDEFGHJKLMNPQRSTUVWXYZ'),
                                                                                pick('abcdefghjkmnpqrstuvwxyz'),
                                                                                pick('23456789'),
                                                                                pick('!@#$%^&*'),
                                                                                ...Array.from({ length: 12 }, () => pick(chars)),
                                                                            ].sort(() => Math.random() - 0.5).join('')
                                                                            setPassword(pwd)
                                                                            setConfirmPassword(pwd)
                                                                            setShowPassword(true)
                                                                            setShowConfirmPassword(true)
                                                                        }}
                                                                        edge={false}
                                                                        sx={{ color: '#1767d1', mr: 0.25 }}
                                                                    >
                                                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" /></svg>
                                                                    </IconButton>
                                                                </Tooltip>
                                                                <IconButton size="small" onClick={() => setShowPassword((v) => !v)} edge="end">
                                                                    {showPassword
                                                                        ? <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z" /></svg>
                                                                        : <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z" /></svg>
                                                                    }
                                                                </IconButton>
                                                            </InputAdornment>
                                                        ),
                                                    },
                                                }}
                                            />
                                            <TextField
                                                size="small"
                                                label={apiLocale === 'zh' ? '确认密码' : 'Confirm password'}
                                                type={showConfirmPassword ? 'text' : 'password'}
                                                value={confirmPassword}
                                                onChange={(event) => setConfirmPassword(event.target.value)}
                                                required
                                                error={confirmPassword.length > 0 && !setupPasswordsMatch}
                                                helperText={confirmPassword.length > 0 && !setupPasswordsMatch ? (apiLocale === 'zh' ? '两次输入的密码不一致。' : 'Passwords do not match.') : undefined}
                                                sx={setupFieldSx}
                                                autoComplete="new-password"
                                                slotProps={{
                                                    input: {
                                                        endAdornment: (
                                                            <InputAdornment position="end">
                                                                <IconButton size="small" onClick={() => setShowConfirmPassword((v) => !v)} edge="end">
                                                                    {showConfirmPassword
                                                                        ? <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z" /></svg>
                                                                        : <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z" /></svg>
                                                                    }
                                                                </IconButton>
                                                            </InputAdornment>
                                                        ),
                                                    },
                                                }}
                                            />
                                        </Stack>

                                        {/* Full-width button row below both cards */}
                                        <Box sx={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'space-between', alignItems: 'center', pt: 0.5 }}>
                                            <Button color="inherit" onClick={() => setCurrentStep('welcome')} disabled={busy || isSubmitting}>
                                                {apiLocale === 'zh' ? '上一步' : 'Back'}
                                            </Button>
                                            <Button type="submit" variant="contained" disabled={busy || isSubmitting} sx={primaryActionButtonSx}>
                                                {busy || isSubmitting ? (apiLocale === 'zh' ? '创建中…' : 'Creating…') : primaryActionLabel}
                                            </Button>
                                        </Box>
                                    </Box>
                                </Box>
                            ) : null}

                            {!pageLoading && currentStep === 'app_init_running' ? (
                                <Stack spacing={3} sx={{ py: 2 }}>
                                    <Box sx={{ ...summaryCardSx, textAlign: 'center' }}>
                                        <Stack spacing={2.5} sx={{ alignItems: 'center' }}>
                                            {installRunning ? (
                                                <Box sx={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 100, height: 100 }}>
                                                    <CircularProgress
                                                        size={100}
                                                        thickness={3}
                                                        sx={{
                                                            color: '#1767d1',
                                                            '& .MuiCircularProgress-circle': { strokeLinecap: 'round' },
                                                        }}
                                                    />
                                                </Box>
                                            ) : null}

                                            <Box>
                                                <Typography sx={{ fontSize: 20, fontWeight: 700, color: '#0f172a' }}>
                                                    {installFailed
                                                        ? (apiLocale === 'zh' ? `${displayName} 启动失败` : `${displayName} launch failed`)
                                                        : (apiLocale === 'zh' ? `${displayName} 正在初始化…` : `Initializing ${displayName}…`)}
                                                </Typography>
                                                <Typography color="text.secondary" sx={{ mt: 0.75, fontSize: 14 }}>
                                                    {installFailed
                                                        ? (apiLocale === 'zh' ? '你可以重试启动，或进入平台查看日志与处理建议。' : 'You can retry launch, or open the platform for logs and guidance.')
                                                        : (apiLocale === 'zh' ? '预计 1–2 分钟，完成后自动进入控制台，请保持当前页面开启。' : 'About 1–2 min. You\'ll enter the console when done — please keep this page open.')}
                                                </Typography>
                                            </Box>

                                            {installFailed ? (
                                                <Box
                                                    sx={{
                                                        width: '100%',
                                                        maxWidth: 900,
                                                        textAlign: 'left',
                                                        borderRadius: '4px',
                                                        border: '1px solid #fecaca',
                                                        background: '#fff5f5',
                                                        px: { xs: 1.75, md: 2.25 },
                                                        py: { xs: 1.5, md: 1.75 },
                                                        maxHeight: 240,
                                                        overflow: 'auto',
                                                    }}
                                                >
                                                    <Typography
                                                        sx={{
                                                            fontSize: 12,
                                                            lineHeight: 1.65,
                                                            color: '#7f1d1d',
                                                            whiteSpace: 'pre-wrap',
                                                            wordBreak: 'break-word',
                                                            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, Courier New, monospace',
                                                        }}
                                                    >
                                                        {failedRawMessage}
                                                    </Typography>
                                                </Box>
                                            ) : null}
                                        </Stack>
                                    </Box>
                                    {installFailed ? (
                                        <Box sx={actionRowSx}>
                                            <Button variant="outlined" onClick={handleStartUsing} disabled={busy} sx={primaryActionButtonSx}>
                                                {busy ? (apiLocale === 'zh' ? '重试中…' : 'Retrying…') : (apiLocale === 'zh' ? '重试' : 'Retry')}
                                            </Button>
                                            <Button variant="contained" onClick={handleOpenPlatformOverview} sx={primaryActionButtonSx}>
                                                {apiLocale === 'zh' ? '进入平台' : 'Open Platform'}
                                            </Button>
                                        </Box>
                                    ) : null}
                                </Stack>
                            ) : null}

                            {!pageLoading && currentStep === 'complete' ? (
                                <Stack spacing={3} sx={{ py: 2 }}>
                                    <Box sx={summaryCardSx}>
                                        <Typography sx={{ fontSize: 24, fontWeight: 700, color: '#0f172a' }}>
                                            {completionTitle}
                                        </Typography>
                                        <Typography sx={{ mt: 1.5, color: '#475569' }}>
                                            {completionBody}
                                        </Typography>
                                        {completionNote ? (
                                            <Typography sx={{ mt: 1.5, color: '#64748b', fontSize: '0.875rem' }}>
                                                {completionNote}
                                            </Typography>
                                        ) : null}
                                    </Box>
                                    <Box sx={actionRowSx}>
                                        <Button variant="contained" onClick={handleOpenAppWorkspace} sx={primaryActionButtonSx}>
                                            {appWorkspaceLabel}
                                        </Button>
                                    </Box>
                                </Stack>
                            ) : null}

                        </>
                    )}
                </Stack>
            </Paper>

            {/* Websoft9 brand link — bottom center */}
            <Box
                component="a"
                href="https://www.websoft9.com"
                target="_blank"
                rel="noopener noreferrer"
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    mt: 3,
                    textDecoration: 'none',
                    opacity: 0.5,
                    transition: 'opacity 0.2s',
                    '&:hover': { opacity: 0.9 },
                }}
            >
                <Box component="img" src={apiLocale === 'zh' ? '/websoft-zh.svg' : '/websoft9-en.svg'} alt="Websoft9" sx={{ height: 40, objectFit: 'contain' }} />
            </Box>
        </Box>
    )
}