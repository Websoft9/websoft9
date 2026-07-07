import {
    Alert,
    Box,
    Button,
    CircularProgress,
    MenuItem,
    Paper,
    Stack,
    Step,
    StepLabel,
    Stepper,
    TextField,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useProductAuth } from '../product-auth/product-auth-provider'
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
    default_locale: 'en' | 'zh-CN'
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
    default_locale: 'en' | 'zh-CN'
    display_name: string
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

type ProductAuthStatus = {
    authenticated: boolean
    initialization_required: boolean
    cloud_marketplace_setup_pending?: boolean
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

function resolveApiLocale(locale: string) {
    return locale.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

function isValidEmail(value: string) {
    return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value.trim())
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

export function SetupWizardPage() {
    const { i18n } = useTranslation('shell')
    const navigate = useNavigate()
    const { initialize, isLoading, isSubmitting, status } = useProductAuth() as {
        initialize: (payload: { username: string; password: string; email: string; locale: string }) => Promise<ProductAuthStatus>
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
    const [username, setUsername] = useState('admin')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [selectedLocale, setSelectedLocale] = useState<'en' | 'zh-CN'>(() => (i18n.resolvedLanguage === 'zh-CN' ? 'zh-CN' : 'en'))
    const [wizardLocale, setWizardLocale] = useState<'en' | 'zh-CN'>(() => normalizeSupportedLocale(i18n.resolvedLanguage ?? i18n.language ?? 'en'))
    const [inputValues, setInputValues] = useState<Record<string, string>>({})
    const [completedAppId, setCompletedAppId] = useState<string | null>(null)
    const pollTimerRef = useRef<number | null>(null)
    const apiLocale = resolveApiLocale(wizardLocale)
    const platformInitializationRequired = Boolean(status?.initialization_required)

    const displayName = appInfo?.display_name ?? wizardState?.app_slug ?? 'Websoft9 App'
    const stepIndex = useMemo(() => {
        if (currentStep === 'welcome') return 0
        if (currentStep === 'platform_init') return 1
        return 2
    }, [currentStep])

    const steps = useMemo(() => (
        apiLocale === 'zh'
            ? ['欢迎', '创建账号', '启动应用']
            : ['Welcome', 'Create Account', 'Launch App']
    ), [apiLocale])

    const titleText = apiLocale === 'zh' ? `开始使用 ${displayName}` : `Get Started with ${displayName}`
    const introTitle = apiLocale === 'zh' ? `${displayName} 即将就绪` : `Your ${displayName} Is Almost Ready`
    const welcomeBodyText = apiLocale === 'zh'
        ? `此镜像由 Websoft9 提供 ${displayName} 的运行与管理。请先创建一个管理员账号，随后 Websoft9 将自动为您启动 ${displayName}。`
        : `This image is powered by Websoft9. Create an admin account, and we'll start ${displayName} for you.`
    const welcomeNoteText = apiLocale === 'zh'
        ? `${displayName} 启动后，您可在 ${displayName} 中完成站点名称、后台账号等设置。`
        : `After ${displayName} starts, you can set up your site name and admin account from within ${displayName}.`
    const welcomeSteps = apiLocale === 'zh'
        ? ['创建管理员账号', `自动启动 ${displayName}`, `进入 ${displayName}`]
        : ['Create admin account', `Start ${displayName} automatically`, `Enter ${displayName}`]
    const primaryActionLabel = apiLocale === 'zh' ? '开始' : 'Get Started'
    const completionTitle = apiLocale === 'zh' ? 'Websoft9 已完成准备' : 'Websoft9 Is Ready'
    const completionBody = apiLocale === 'zh'
        ? `${displayName} 已启动。接下来，您可以先进入应用管理，或直接回到 Websoft9 控制台继续操作。`
        : `${displayName} has started. You can open the app workspace first or return to the Websoft9 console.`
    const completionNote = apiLocale === 'zh'
        ? `${displayName} 内的站点名称、后台账号和业务配置，仍将在应用中继续完成。`
        : `Site details, admin credentials, and business configuration will continue inside ${displayName}.`
    const appWorkspaceLabel = apiLocale === 'zh' ? `进入 ${displayName} 管理` : `Open ${displayName}`
    const dashboardLabel = apiLocale === 'zh' ? '进入控制台' : 'Open Dashboard'

    useEffect(() => () => {
        if (pollTimerRef.current !== null) {
            window.clearTimeout(pollTimerRef.current)
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
                const nextLocale = normalizeSupportedLocale(statePayload.default_locale)
                const appPayload = await requestJson<SetupWizardApp>(`/api/setup-wizard/app?locale=${encodeURIComponent(resolveApiLocale(nextLocale))}`, { method: 'GET' })
                if (!active) {
                    return
                }
                setWizardLocale(nextLocale)
                setSelectedLocale(nextLocale)
                if ((i18n.resolvedLanguage ?? i18n.language) !== nextLocale) {
                    await i18n.changeLanguage(nextLocale)
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
                setCurrentStep(statePayload.current_step)
                setError(mapSetupWizardErrorMessage(statePayload.last_error?.message ?? null, apiLocale))
            })
            .catch((loadError) => {
                if (!active) {
                    return
                }
                setError(loadError instanceof Error ? mapSetupWizardErrorMessage(loadError.message, apiLocale) : apiLocale === 'zh' ? '初始化向导加载失败。' : 'Failed to load setup wizard.')
            })
            .finally(() => {
                if (active) {
                    setPageLoading(false)
                }
            })

        return () => {
            active = false
        }
    }, [i18n, isLoading, status])

    useEffect(() => {
        if (isLoading || !status || pageLoading || !wizardState) {
            return
        }

        if (!wizardState.enabled) {
            if (status.initialization_required) {
                navigate('/auth/setup', { replace: true })
                return
            }

            navigate(status.authenticated ? '/dashboard' : '/auth/login', { replace: true })
            return
        }

        if (!status.authenticated && !platformInitializationRequired) {
            navigate('/auth/login?next=%2Fsetup', { replace: true })
            return
        }

        if (wizardState.completed) {
            setCompletedAppId(wizardState.installed_app_id)
            setCurrentStep('complete')
        }
    }, [isLoading, navigate, pageLoading, platformInitializationRequired, status, wizardState])

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
                    setCurrentStep('app_init_failed')
                    setError(mapSetupWizardErrorMessage(payload.last_error?.message ?? (apiLocale === 'zh' ? '准备失败，请重试。' : 'Preparation failed. Please retry.'), apiLocale))
                    setWizardState((currentValue) => currentValue ? {
                        ...currentValue,
                        current_step: 'app_init_failed',
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
                        setCurrentStep('complete')
                        setWizardState((currentValue) => currentValue ? {
                            ...currentValue,
                            current_step: 'complete',
                            completed: true,
                            installed_app_id: completion.installed_app_id,
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

        if (!isValidEmail(email)) {
            setError(apiLocale === 'zh' ? '请输入有效邮箱地址。' : 'Enter a valid email address.')
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
            await initialize({ username, password, email: email.trim(), locale: selectedLocale })
            const nextState = await requestJson<{ current_step: WizardStep }>('/api/setup-wizard/platform-init-complete', {
                method: 'POST',
                body: JSON.stringify({}),
            })
            setCurrentStep(nextState.current_step)
            setWizardState((currentValue) => currentValue ? {
                ...currentValue,
                current_step: nextState.current_step,
                last_error: null,
            } : currentValue)
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
            setCurrentStep(payload.current_step)
            setWizardState((currentValue) => currentValue ? {
                ...currentValue,
                current_step: payload.current_step,
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
            setCurrentStep('app_init_ready')
        }
    }

    function handleOpenAppWorkspace() {
        if (!completedAppId) {
            navigate('/dashboard', { replace: true })
            return
        }

        navigate(`/myapps/${encodeURIComponent(completedAppId)}`, { replace: true })
    }

    return (
        <Box
            sx={{
                minHeight: '100vh',
                display: 'grid',
                placeItems: 'center',
                px: { xs: 2, md: 4 },
                py: { xs: 3, md: 5 },
                background:
                    'radial-gradient(circle at top left, rgba(59, 130, 246, 0.14), transparent 28%), radial-gradient(circle at bottom right, rgba(14, 165, 233, 0.1), transparent 24%), linear-gradient(180deg, #edf3fb 0%, #f8fafc 100%)',
            }}
        >
            <Paper elevation={0} sx={{ width: '100%', maxWidth: 720, borderRadius: 3, p: { xs: 3, md: 4 }, boxShadow: '0 24px 64px rgba(15, 23, 42, 0.12)' }}>
                <Stack spacing={3}>
                    {(pageLoading || isLoading) ? (
                        <Stack spacing={2} sx={{ alignItems: 'center', py: 6 }}>
                            <CircularProgress size={30} />
                            <Typography color="text.secondary">{apiLocale === 'zh' ? '正在加载…' : 'Loading…'}</Typography>
                        </Stack>
                    ) : (
                        <>
                            <Box>
                                <Typography sx={{ fontSize: { xs: 28, md: 32 }, fontWeight: 700, color: '#0f172a' }}>{titleText}</Typography>
                            </Box>

                            <Stepper activeStep={stepIndex} alternativeLabel>
                                {steps.map((label) => (
                                    <Step key={label}>
                                        <StepLabel>{label}</StepLabel>
                                    </Step>
                                ))}
                            </Stepper>

                            {!pageLoading && error ? <Alert severity="error">{error}</Alert> : null}

                            {!pageLoading && currentStep === 'welcome' ? (
                                <Stack spacing={3}>
                                    <Box sx={{ borderRadius: 3, border: '1px solid #dbe4f0', backgroundColor: '#f8fbff', px: 3, py: 4 }}>
                                        <Typography sx={{ fontSize: 24, fontWeight: 700, color: '#0f172a' }}>{introTitle}</Typography>
                                        <Typography sx={{ mt: 1.5, color: '#475569' }}>
                                            {welcomeBodyText}
                                        </Typography>
                                        <Typography sx={{ mt: 1.5, color: '#64748b', fontSize: '0.875rem' }}>
                                            {welcomeNoteText}
                                        </Typography>
                                        <Stack component="ol" spacing={1} sx={{ mt: 2.5, pl: 2.5, color: '#334155' }}>
                                            {welcomeSteps.map((step) => (
                                                <Typography key={step} component="li">{step}</Typography>
                                            ))}
                                        </Stack>
                                    </Box>
                                    <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                                        <Button variant="contained" size="large" onClick={handleWelcomeContinue}>
                                            {primaryActionLabel}
                                        </Button>
                                    </Box>
                                </Stack>
                            ) : null}

                            {!pageLoading && currentStep === 'platform_init' && platformInitializationRequired ? (
                                <Box component="form" onSubmit={handlePlatformInitSubmit}>
                                    <Stack spacing={2.5}>
                                        <Typography sx={{ fontSize: 22, fontWeight: 700, color: '#0f172a' }}>
                                            {apiLocale === 'zh' ? '创建管理员账号' : 'Create Admin Account'}
                                        </Typography>
                                        <Typography color="text.secondary">
                                            {apiLocale === 'zh'
                                                ? `通过 Websoft9，您可以集中管理 ${displayName} 的运行、访问与后续维护。`
                                                : `Use Websoft9 to manage how ${displayName} runs, how it is accessed, and how it is maintained.`}
                                        </Typography>
                                        <TextField label={apiLocale === 'zh' ? '用户名' : 'Username'} value={username} onChange={(event) => setUsername(event.target.value)} required />
                                        <TextField label={apiLocale === 'zh' ? '邮箱' : 'Email'} value={email} onChange={(event) => setEmail(event.target.value)} required />
                                        <TextField label={apiLocale === 'zh' ? '密码' : 'Password'} type="password" value={password} onChange={(event) => setPassword(event.target.value)} required helperText={apiLocale === 'zh' ? '至少 8 位，包含大小写、数字和符号。' : 'At least 8 characters with uppercase, lowercase, number, and symbol.'} />
                                        <TextField label={apiLocale === 'zh' ? '确认密码' : 'Confirm password'} type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required />
                                        <TextField select label={apiLocale === 'zh' ? '语言' : 'Language'} value={selectedLocale} onChange={(event) => setSelectedLocale(event.target.value as 'en' | 'zh-CN')}>
                                            <MenuItem value="en">English</MenuItem>
                                            <MenuItem value="zh-CN">简体中文</MenuItem>
                                        </TextField>
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', pt: 1 }}>
                                            <Button color="inherit" onClick={() => setCurrentStep('welcome')} disabled={busy || isSubmitting}>
                                                {apiLocale === 'zh' ? '上一步' : 'Back'}
                                            </Button>
                                            <Button type="submit" variant="contained" disabled={busy || isSubmitting}>
                                                {busy || isSubmitting ? (apiLocale === 'zh' ? '创建中…' : 'Creating…') : (apiLocale === 'zh' ? '下一步' : 'Continue')}
                                            </Button>
                                        </Box>
                                    </Stack>
                                </Box>
                            ) : null}

                            {!pageLoading && (currentStep === 'app_init_ready' || currentStep === 'app_init_failed') ? (
                                <Stack spacing={2.5}>
                                    <Typography sx={{ fontSize: 22, fontWeight: 700, color: '#0f172a' }}>
                                        {apiLocale === 'zh' ? `启动 ${displayName}` : `Start ${displayName}`}
                                    </Typography>
                                    <Typography color="text.secondary">
                                        {apiLocale === 'zh'
                                            ? `Websoft9 将自动完成最后的准备工作并启动 ${displayName}。`
                                            : `Websoft9 will finish the final setup steps and start ${displayName} for you.`}
                                    </Typography>
                                    <Typography color="text.secondary" sx={{ fontSize: '0.925rem' }}>
                                        {apiLocale === 'zh'
                                            ? `${displayName} 启动后，站点名称、后台账号和内容配置仍会在应用内继续完成。`
                                            : `After ${displayName} starts, site details, admin credentials, and content setup continue inside the app.`}
                                    </Typography>
                                    {(appInfo?.required_inputs ?? []).map((field) => (
                                        <TextField
                                            key={field.name}
                                            label={field.label}
                                            type={field.type === 'password' ? 'password' : field.type === 'number' ? 'number' : 'text'}
                                            value={inputValues[field.name] ?? ''}
                                            onChange={(event) => setInputValues((currentValue) => ({ ...currentValue, [field.name]: event.target.value }))}
                                            required={field.required}
                                            helperText={field.description ?? undefined}
                                        />
                                    ))}
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', pt: 1 }}>
                                        <Button color="inherit" onClick={() => setCurrentStep('platform_init')} disabled={busy}>
                                            {apiLocale === 'zh' ? '上一步' : 'Back'}
                                        </Button>
                                        <Button variant="contained" onClick={handleStartUsing} disabled={busy}>
                                            {busy ? (apiLocale === 'zh' ? '正在启动…' : 'Starting…') : (apiLocale === 'zh' ? `启动 ${displayName}` : `Start ${displayName}`)}
                                        </Button>
                                    </Box>
                                </Stack>
                            ) : null}

                            {!pageLoading && currentStep === 'app_init_running' ? (
                                <Stack spacing={2.5} sx={{ alignItems: 'center', py: 5 }}>
                                    <CircularProgress size={36} />
                                    <Typography sx={{ fontSize: 24, fontWeight: 700, color: '#0f172a' }}>
                                        {apiLocale === 'zh' ? `正在启动 ${displayName}…` : `Starting ${displayName}…`}
                                    </Typography>
                                    <Typography color="text.secondary" sx={{ textAlign: 'center', maxWidth: 420 }}>
                                        {apiLocale === 'zh' ? '预计 1～2 分钟，请稍候。' : 'This usually takes 1-2 minutes.'}
                                    </Typography>
                                </Stack>
                            ) : null}

                            {!pageLoading && currentStep === 'complete' ? (
                                <Stack spacing={3} sx={{ py: 2 }}>
                                    <Box sx={{ borderRadius: 3, border: '1px solid #dbe4f0', backgroundColor: '#f8fbff', px: 3, py: 4 }}>
                                        <Typography sx={{ fontSize: 24, fontWeight: 700, color: '#0f172a' }}>
                                            {completionTitle}
                                        </Typography>
                                        <Typography sx={{ mt: 1.5, color: '#475569' }}>
                                            {completionBody}
                                        </Typography>
                                        <Typography sx={{ mt: 1.5, color: '#64748b', fontSize: '0.875rem' }}>
                                            {completionNote}
                                        </Typography>
                                    </Box>
                                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1.5, flexWrap: 'wrap' }}>
                                        <Button color="inherit" onClick={() => navigate('/dashboard', { replace: true })}>
                                            {dashboardLabel}
                                        </Button>
                                        <Button variant="contained" onClick={handleOpenAppWorkspace}>
                                            {appWorkspaceLabel}
                                        </Button>
                                    </Box>
                                </Stack>
                            ) : null}
                        </>
                    )}
                </Stack>
            </Paper>
        </Box>
    )
}