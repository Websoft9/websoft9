import {
    Alert,
    Box,
    Button,
    IconButton,
    InputAdornment,
    MenuItem,
    Paper,
    Stack,
    TextField,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'

import { prewarmAuthenticatedIntegrationSessions } from '../integrations/integration-session-bootstrap'
import { useProductAuth } from './product-auth-provider'

type ProductAuthPageProps = {
    mode: 'login' | 'setup'
}

type PlatformBrandState = {
    title: string
    logoUrl: string
    loginBackground: string
}

const DEFAULT_PLATFORM_BRAND_LOGO_URL = '/websoft9.png'

function isValidPlatformBrandLogoUrl(value: string) {
    const trimmed = value.trim()
    if (!trimmed) {
        return false
    }
    if (trimmed.startsWith('/')) {
        return true
    }
    return /^https?:\/\//i.test(trimmed)
}

function resolveNext(search: string) {
    const params = new URLSearchParams(search)
    const next = params.get('next')
    return next && next.startsWith('/') ? next : '/dashboard'
}

function targetsIntegrationWorkspace(path: string) {
    return /^\/(containers|gateway|repository)(?:[/?#]|$)/.test(path)
}

function mapAuthErrorMessage(message: string | null, t: (key: string) => string) {
    if (!message) {
        return null
    }

    const normalized = message.trim().toLowerCase()
    if (normalized === 'invalid username or password') {
        return t('auth.errors.invalidCredentials')
    }

    if (normalized === 'user account is disabled') {
        return t('auth.errors.userDisabled')
    }

    if (normalized === 'password must be at least 8 characters and include uppercase, lowercase, number, and special character') {
        return t('auth.errors.passwordComplexity')
    }

    if (normalized === 'account has no bound email') {
        return t('auth.errors.noBoundEmail')
    }

    if (normalized === 'account or bound email not found') {
        return t('auth.errors.accountNotFound')
    }

    if (normalized === 'operator password reset is not allowed for this account') {
        return t('auth.errors.resetNotAllowed')
    }

    if (normalized === 'smtp is not configured') {
        return t('auth.errors.smtpNotConfigured')
    }

    if (normalized === 'invalid or expired verification code') {
        return t('auth.errors.invalidResetCode')
    }

    if (normalized === 'please wait before requesting another verification code') {
        return t('auth.errors.rateLimited')
    }

    return message
}

function IconEye() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zm0 12.5a5 5 0 1 1 0-10 5 5 0 0 1 0 10zm0-8a3 3 0 1 0 0 6 3 3 0 0 0 0-6z" /></svg>
}

function IconEyeOff() {
    return <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M12 7a5 5 0 0 1 5 5c0 .64-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46A11.8 11.8 0 0 0 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65a3 3 0 0 0 3 3c.22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53a5 5 0 0 1-5-5c0-.79.2-1.53.53-2.2zm4.31-.78 3.15 3.15.02-.16a3 3 0 0 0-3-3l-.17.01z" /></svg>
}

export function ProductAuthPage({ mode }: ProductAuthPageProps) {
    const { t, i18n } = useTranslation('shell')
    const navigate = useNavigate()
    const location = useLocation()
    const { errorMessage, initialize, isLoading, isSubmitting, login, status } = useProductAuth()
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [confirmPassword, setConfirmPassword] = useState('')
    const [showConfirmPassword, setShowConfirmPassword] = useState(false)
    const [email, setEmail] = useState('')
    const [emailTouched, setEmailTouched] = useState(false)
    const [localError, setLocalError] = useState<string | null>(null)
    const [localSuccess, setLocalSuccess] = useState<string | null>(null)
    const [forgotMode, setForgotMode] = useState(false)
    const [forgotIdentifier, setForgotIdentifier] = useState('')
    const [forgotEmailTouched, setForgotEmailTouched] = useState(false)
    const [forgotEmailStatus, setForgotEmailStatus] = useState<'idle' | 'checking' | 'valid' | 'invalid'>('idle')
    const [forgotEmailError, setForgotEmailError] = useState<string | null>(null)
    const forgotEmailRequest = useRef(0)
    const [forgotCodeSent, setForgotCodeSent] = useState(false)
    const [forgotCountdown, setForgotCountdown] = useState(0)
    const [forgotSendingCode, setForgotSendingCode] = useState(false)
    const [forgotCode, setForgotCode] = useState('')
    const [forgotNewPassword, setForgotNewPassword] = useState('')
    const [showForgotNewPassword, setShowForgotNewPassword] = useState(false)
    const [forgotConfirmPassword, setForgotConfirmPassword] = useState('')
    const [showForgotConfirmPassword, setShowForgotConfirmPassword] = useState(false)
    const [forgotSubmitting, setForgotSubmitting] = useState(false)
    const [selectedLocale, setSelectedLocale] = useState<'en' | 'zh-CN'>(() => (i18n.resolvedLanguage === 'zh-CN' ? 'zh-CN' : 'en'))
    const [platformBrand, setPlatformBrand] = useState<PlatformBrandState>({
        title: t('brand.title'),
        logoUrl: DEFAULT_PLATFORM_BRAND_LOGO_URL,
        loginBackground: '',
    })
    const [brandLogoSrc, setBrandLogoSrc] = useState(DEFAULT_PLATFORM_BRAND_LOGO_URL)
    const nextPath = useMemo(() => resolveNext(location.search), [location.search])
    const setupPasswordValid = useMemo(
        () => password.length >= 8 && /[A-Z]/.test(password) && /[a-z]/.test(password) && /\d/.test(password) && /[^A-Za-z0-9]/.test(password),
        [password],
    )
    const setupEmailValid = useMemo(
        () => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim()),
        [email],
    )
    const setupPasswordsMatch = useMemo(
        () => confirmPassword.length > 0 && password === confirmPassword,
        [confirmPassword, password],
    )
    const forgotPasswordValid = useMemo(
        () => forgotNewPassword.length >= 8 && /[A-Z]/.test(forgotNewPassword) && /[a-z]/.test(forgotNewPassword) && /\d/.test(forgotNewPassword) && /[^A-Za-z0-9]/.test(forgotNewPassword),
        [forgotNewPassword],
    )
    const forgotPasswordsMatch = useMemo(
        () => forgotConfirmPassword.length > 0 && forgotNewPassword === forgotConfirmPassword,
        [forgotConfirmPassword, forgotNewPassword],
    )
    const forgotEmailValid = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(forgotIdentifier.trim())
    const authFieldSx = useMemo(
        () => ({
            '& .MuiOutlinedInput-root': {
                borderRadius: 0,
                backgroundColor: '#fbfdff',
            },
            '& input:-webkit-autofill': {
                WebkitBoxShadow: '0 0 0 100px #fbfdff inset',
                WebkitTextFillColor: '#0f172a',
                caretColor: '#0f172a',
                borderRadius: 0,
                transition: 'background-color 9999s ease-out 0s',
            },
            '& input:-webkit-autofill:hover': {
                WebkitBoxShadow: '0 0 0 100px #fbfdff inset',
                WebkitTextFillColor: '#0f172a',
            },
            '& input:-webkit-autofill:focus': {
                WebkitBoxShadow: '0 0 0 100px #fbfdff inset',
                WebkitTextFillColor: '#0f172a',
            },
        }),
        [],
    )

    useEffect(() => {
        setLocalSuccess(null)
        setForgotMode(false)
        setUsername('')
        setPassword('')
        setShowPassword(false)
        setConfirmPassword('')
        setShowConfirmPassword(false)
        setEmail('')
        setEmailTouched(false)
        setLocalError(null)
    }, [mode])

    useEffect(() => {
        setSelectedLocale(i18n.resolvedLanguage === 'zh-CN' ? 'zh-CN' : 'en')
    }, [i18n.resolvedLanguage])

    useEffect(() => {
        if (forgotCountdown <= 0) {
            return
        }
        const timerId = window.setInterval(() => {
            setForgotCountdown((current) => (current > 1 ? current - 1 : 0))
        }, 1000)
        return () => {
            window.clearInterval(timerId)
        }
    }, [forgotCountdown])

    useEffect(() => {
        let disposed = false

        async function loadPlatformBrand() {
            try {
                const response = await fetch('/api/settings/platform_brand', {
                    credentials: 'include',
                    headers: {
                        Accept: 'application/json',
                    },
                })

                if (!response.ok) {
                    return
                }

                const payload = (await response.json()) as { title?: unknown; logo_url?: unknown; login_background?: unknown }
                if (disposed) {
                    return
                }

                const resolvedTitle = typeof payload.title === 'string' && payload.title.trim() ? payload.title.trim() : t('brand.title')
                const resolvedLogoUrlRaw = typeof payload.logo_url === 'string' ? payload.logo_url.trim() : ''
                const resolvedLogoUrl = isValidPlatformBrandLogoUrl(resolvedLogoUrlRaw) ? resolvedLogoUrlRaw : DEFAULT_PLATFORM_BRAND_LOGO_URL
                const resolvedLoginBgRaw = typeof payload.login_background === 'string' ? payload.login_background.trim() : ''
                const resolvedLoginBg = isValidPlatformBrandLogoUrl(resolvedLoginBgRaw) ? resolvedLoginBgRaw : ''

                setPlatformBrand({
                    title: resolvedTitle,
                    logoUrl: resolvedLogoUrl,
                    loginBackground: resolvedLoginBg,
                })
                setBrandLogoSrc(resolvedLogoUrl)
            } catch {
                if (!disposed) {
                    setPlatformBrand({
                        title: t('brand.title'),
                        logoUrl: DEFAULT_PLATFORM_BRAND_LOGO_URL,
                        loginBackground: '',
                    })
                    setBrandLogoSrc(DEFAULT_PLATFORM_BRAND_LOGO_URL)
                }
            }
        }

        void loadPlatformBrand()

        return () => {
            disposed = true
        }
    }, [t])

    useEffect(() => {
        function handlePlatformBrandUpdate(event: Event) {
            const customEvent = event as CustomEvent<{ key?: string; value?: string }>
            const key = customEvent.detail?.key
            const value = customEvent.detail?.value
            if (typeof key !== 'string' || typeof value !== 'string') {
                return
            }

            if (key === 'title') {
                setPlatformBrand((current) => ({
                    ...current,
                    title: value.trim() || t('brand.title'),
                }))
                return
            }

            if (key === 'logo_url') {
                const nextLogoUrl = isValidPlatformBrandLogoUrl(value) ? value.trim() : DEFAULT_PLATFORM_BRAND_LOGO_URL
                setPlatformBrand((current) => ({
                    ...current,
                    logoUrl: nextLogoUrl,
                }))
                setBrandLogoSrc(nextLogoUrl)
            }

            if (key === 'login_background') {
                const nextLoginBg = isValidPlatformBrandLogoUrl(value) ? value.trim() : ''
                setPlatformBrand((current) => ({
                    ...current,
                    loginBackground: nextLoginBg,
                }))
            }
        }

        window.addEventListener('websoft9:platform-brand-updated', handlePlatformBrandUpdate as EventListener)
        return () => {
            window.removeEventListener('websoft9:platform-brand-updated', handlePlatformBrandUpdate as EventListener)
        }
    }, [t])

    useEffect(() => {
        if (!status || isLoading) {
            return
        }

        if (!status.enabled) {
            navigate('/dashboard', { replace: true })
            return
        }

        if (status.authenticated) {
            navigate(nextPath, { replace: true })
            return
        }

        if (mode === 'setup' && !status.initialization_required && !status.cloud_marketplace_setup_pending) {
            navigate(`/auth/login?next=${encodeURIComponent(nextPath)}`, { replace: true })
            return
        }

        if (mode === 'setup' && (status.initialization_required || status.cloud_marketplace_setup_pending) && status.cloud_marketplace_setup) {
            navigate('/setup', { replace: true })
            return
        }

        if (mode === 'login' && status.initialization_required) {
            navigate(status.cloud_marketplace_setup ? '/setup' : `/auth/setup?next=${encodeURIComponent(nextPath)}`, { replace: true })
        }
    }, [isLoading, mode, navigate, nextPath, status])

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        setLocalError(null)

        if (mode === 'setup') {
            if (!setupEmailValid) {
                setLocalError(t('auth.errors.invalidEmail'))
                return
            }
            if (!setupPasswordValid) {
                setLocalError(t('auth.errors.passwordComplexity'))
                return
            }
            if (!setupPasswordsMatch) {
                setLocalError(t('auth.errors.passwordMismatch'))
                return
            }
        }

        try {
            const locale = selectedLocale
            const nextStatus =
                mode === 'setup'
                    ? await initialize({
                        username,
                        password,
                        email: email.trim(),
                        locale,
                        createSession: Boolean(status?.cloud_marketplace_setup),
                    })
                    : await login({ username, password })

            if (mode === 'setup') {
                if (nextStatus.cloud_marketplace_setup) {
                    navigate('/setup', { replace: true })
                    return
                }
                navigate('/auth/login', { replace: true })
                return
            }

            const prewarmPromise =
                nextStatus.authenticated && nextStatus.current_user
                    ? prewarmAuthenticatedIntegrationSessions(locale, nextStatus.current_user.id)
                    : Promise.resolve()

            if (targetsIntegrationWorkspace(nextPath)) {
                await prewarmPromise.catch(() => {
                    // Keep login/setup success independent from integration prewarm failures.
                })
            } else {
                void prewarmPromise.catch(() => {
                    // Non-integration destinations should not wait on third-party session prewarm.
                })
            }

            navigate(nextPath, { replace: true })
        } catch (error) {
            setLocalError(error instanceof Error ? error.message : t('auth.genericError'))
        }
    }

    const validateForgotEmail = async (identifier = forgotIdentifier) => {
        if (identifier === forgotIdentifier && forgotEmailStatus === 'valid') return true
        const requestId = ++forgotEmailRequest.current
        setForgotEmailTouched(true)
        setForgotEmailError(null)
        if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(identifier.trim())) {
            setForgotEmailStatus('invalid')
            return false
        }
        setForgotEmailStatus('checking')
        try {
            const response = await fetch('/api/auth/forgot-password/validate-email', {
                method: 'POST',
                credentials: 'include',
                headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
                body: JSON.stringify({ identifier: identifier.trim() }),
            })
            if (!response.ok) {
                const payload = (await response.json().catch(() => ({}))) as { details?: string; message?: string }
                throw new Error(payload.details || payload.message || t('auth.genericError'))
            }
            if (requestId !== forgotEmailRequest.current) return false
            setForgotEmailStatus('valid')
            return true
        } catch (error) {
            if (requestId !== forgotEmailRequest.current) return false
            setForgotEmailStatus('invalid')
            setForgotEmailError(error instanceof Error ? error.message : t('auth.genericError'))
            return false
        }
    }

    const handleSendForgotCode = async () => {
        setLocalError(null)
        setLocalSuccess(null)
        const trimmedIdentifier = forgotIdentifier.trim()
        if (!forgotEmailValid || forgotEmailStatus !== 'valid') {
            await validateForgotEmail()
            return
        }
        setForgotSendingCode(true)
        try {
            const response = await fetch('/api/auth/forgot-password/send-code', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ identifier: trimmedIdentifier }),
            })
            if (!response.ok) {
                const payload = (await response.json().catch(() => ({}))) as { details?: string; message?: string }
                throw new Error(payload.details || payload.message || t('auth.genericError'))
            }
            const data = (await response.json()) as { masked_email?: string | null }
            setForgotCodeSent(true)
            setForgotCountdown(60)
            setLocalSuccess(
                data.masked_email
                    ? t('auth.forgot.codeSentHint', { email: data.masked_email })
                    : t('auth.forgot.codeSentGenericHint'),
            )
        } catch (error) {
            setLocalError(error instanceof Error ? error.message : t('auth.genericError'))
        } finally {
            setForgotSendingCode(false)
        }
    }

    const handleResetForgotPassword = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        setLocalError(null)
        setLocalSuccess(null)

        if (!forgotEmailValid || forgotEmailStatus !== 'valid') {
            await validateForgotEmail()
            return
        }
        if (!forgotPasswordValid) {
            setLocalError(t('auth.errors.passwordComplexity'))
            return
        }
        if (!forgotPasswordsMatch) {
            setLocalError(t('auth.errors.passwordMismatch'))
            return
        }

        setForgotSubmitting(true)
        try {
            const response = await fetch('/api/auth/forgot-password/reset', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    identifier: forgotIdentifier.trim(),
                    code: forgotCode.trim(),
                    password: forgotNewPassword,
                }),
            })
            if (!response.ok) {
                const payload = (await response.json().catch(() => ({}))) as { details?: string; message?: string }
                throw new Error(payload.details || payload.message || t('auth.genericError'))
            }
            setUsername(forgotIdentifier.trim())
            setPassword('')
            setForgotMode(false)
            setForgotCodeSent(false)
            setForgotCountdown(0)
            setForgotCode('')
            setForgotNewPassword('')
            setForgotConfirmPassword('')
            setLocalSuccess(t('auth.forgot.resetSuccess'))
        } catch (error) {
            setLocalError(error instanceof Error ? error.message : t('auth.genericError'))
        } finally {
            setForgotSubmitting(false)
        }
    }

    const authPageBackground = useMemo(() => {
        if (platformBrand.loginBackground) {
            return `url(${platformBrand.loginBackground}) center/cover no-repeat`
        }
        return 'radial-gradient(circle at top left, rgba(59, 130, 246, 0.14), transparent 28%), radial-gradient(circle at bottom right, rgba(14, 165, 233, 0.1), transparent 24%), linear-gradient(180deg, #edf3fb 0%, #f8fafc 100%)'
    }, [platformBrand.loginBackground])

    return (
        <Box
            sx={{
                minHeight: '100vh',
                display: 'grid',
                placeItems: 'center',
                px: { xs: 2, md: 4 },
                py: { xs: 3, md: 5 },
                background: authPageBackground,
            }}
        >
            <Paper
                elevation={0}
                sx={{
                    width: '100%',
                    maxWidth: 480,
                    p: { xs: 3, md: 4 },
                    borderRadius: 0,
                    border: '1px solid rgba(148, 163, 184, 0.18)',
                    background: 'rgba(255,255,255,0.97)',
                    backdropFilter: 'blur(12px)',
                    boxShadow: '0 20px 60px rgba(15, 23, 42, 0.08)',
                }}
            >
                <Stack spacing={3}>
                    <Stack spacing={1.25}>
                        <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                            <Box
                                component="img"
                                alt={platformBrand.title}
                                onError={() => setBrandLogoSrc(DEFAULT_PLATFORM_BRAND_LOGO_URL)}
                                src={brandLogoSrc}
                                sx={{
                                    width: 44,
                                    height: 44,
                                    borderRadius: 0,
                                    objectFit: 'contain',
                                    backgroundColor: '#ffffff',
                                    border: '1px solid rgba(148, 163, 184, 0.22)',
                                    p: 0.75,
                                }}
                            />
                            <Stack spacing={0.25}>
                                <Typography sx={{ fontSize: 18, fontWeight: 700, color: '#0f172a', lineHeight: 1.1 }}>
                                    {platformBrand.title}
                                </Typography>
                                {mode === 'setup' ? (
                                    <Typography color="text.secondary" sx={{ fontSize: 13 }}>
                                        {t('auth.setup.subtitle')}
                                    </Typography>
                                ) : forgotMode && status?.smtp_enabled !== false ? (
                                    <Typography color="text.secondary" sx={{ fontSize: 13 }}>
                                        {t('auth.forgot.subtitle')}
                                    </Typography>
                                ) : null}
                            </Stack>
                        </Stack>
                    </Stack>

                    {(localError || errorMessage) && (
                        <Alert severity="error" sx={{ borderRadius: 0 }}>
                            {mapAuthErrorMessage(localError ?? errorMessage, t)}
                        </Alert>
                    )}
                    {localSuccess && (
                        <Alert severity="success" sx={{ borderRadius: 0 }}>
                            {localSuccess}
                        </Alert>
                    )}

                    {mode === 'login' && forgotMode ? (
                        <Stack component="form" spacing={1} onSubmit={handleResetForgotPassword}>
                            {status?.smtp_enabled === false ? (
                                <Alert severity="info" sx={{ mb: 1, borderRadius: 0 }}>
                                    {t('auth.forgot.cliFallbackHint')}
                                </Alert>
                            ) : (
                                <>
                                    <TextField
                                        autoComplete="email"
                                        disabled={forgotSubmitting || forgotSendingCode}
                                        error={forgotEmailTouched && (!forgotEmailValid || forgotEmailStatus === 'invalid')}
                                        label={t('auth.fields.email')}
                                        onBlur={() => void validateForgotEmail()}
                                        onChange={(event) => {
                                            ++forgotEmailRequest.current
                                            setForgotIdentifier(event.target.value)
                                            setForgotEmailStatus('idle')
                                            setForgotEmailError(null)
                                            setForgotCodeSent(false)
                                            setForgotCode('')
                                            setLocalError(null)
                                            setLocalSuccess(null)
                                        }}
                                        required
                                        size="medium"
                                        sx={authFieldSx}
                                        type="email"
                                        value={forgotIdentifier}
                                        helperText={
                                            forgotEmailTouched && !forgotEmailValid
                                                ? t('auth.errors.invalidEmail')
                                                : forgotEmailError
                                                    ? mapAuthErrorMessage(forgotEmailError, t)
                                                    : forgotEmailStatus === 'checking'
                                                        ? t('auth.forgot.checkingEmail')
                                                        : ' '
                                        }
                                    />
                                    <TextField
                                        label={t('auth.fields.verificationCode')}
                                        onChange={(event) => setForgotCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                                        required
                                        size="medium"
                                        sx={authFieldSx}
                                        value={forgotCode}
                                        helperText=" "
                                        slotProps={{
                                            input: {
                                                endAdornment: (
                                                    <InputAdornment position="end">
                                                        <Button
                                                            disabled={
                                                                forgotSubmitting ||
                                                                forgotSendingCode ||
                                                                forgotCountdown > 0 ||
                                                                !forgotEmailValid ||
                                                                forgotEmailStatus !== 'valid'
                                                            }
                                                            onClick={() => void handleSendForgotCode()}
                                                            size="small"
                                                            sx={{ borderRadius: 0, textTransform: 'none', whiteSpace: 'nowrap' }}
                                                        >
                                                            {forgotSendingCode
                                                                ? t('auth.forgot.sendingCode')
                                                                : forgotCountdown > 0
                                                                    ? t('auth.forgot.resendCountdown', { seconds: forgotCountdown })
                                                                    : forgotCodeSent
                                                                        ? t('auth.forgot.resendCode')
                                                                        : t('auth.forgot.sendCode')}
                                                        </Button>
                                                    </InputAdornment>
                                                ),
                                            },
                                        }}
                                    />
                                    <TextField
                                        autoComplete="new-password"
                                        error={forgotNewPassword.length > 0 && !forgotPasswordValid}
                                        helperText={
                                            forgotNewPassword.length > 0 && !forgotPasswordValid
                                                ? t('auth.errors.passwordComplexity')
                                                : ' '
                                        }
                                        label={t('auth.fields.newPassword')}
                                        onChange={(event) => setForgotNewPassword(event.target.value)}
                                        required
                                        size="medium"
                                        sx={authFieldSx}
                                        type={showForgotNewPassword ? 'text' : 'password'}
                                        value={forgotNewPassword}
                                        slotProps={{
                                            input: {
                                                endAdornment: (
                                                    <InputAdornment position="end">
                                                        <IconButton
                                                            aria-label={showForgotNewPassword ? t('auth.actions.hidePassword') : t('auth.actions.showPassword')}
                                                            edge="end"
                                                            onClick={() => setShowForgotNewPassword((current) => !current)}
                                                        >
                                                            {showForgotNewPassword ? <IconEyeOff /> : <IconEye />}
                                                        </IconButton>
                                                    </InputAdornment>
                                                ),
                                            },
                                        }}
                                    />
                                    <TextField
                                        autoComplete="new-password"
                                        error={forgotConfirmPassword.length > 0 && !forgotPasswordsMatch}
                                        helperText={
                                            forgotConfirmPassword.length > 0 && !forgotPasswordsMatch
                                                ? t('auth.errors.passwordMismatch')
                                                : ' '
                                        }
                                        label={t('auth.fields.confirmPassword')}
                                        onChange={(event) => setForgotConfirmPassword(event.target.value)}
                                        required
                                        size="medium"
                                        sx={authFieldSx}
                                        type={showForgotConfirmPassword ? 'text' : 'password'}
                                        value={forgotConfirmPassword}
                                        slotProps={{
                                            input: {
                                                endAdornment: (
                                                    <InputAdornment position="end">
                                                        <IconButton
                                                            aria-label={showForgotConfirmPassword ? t('auth.actions.hidePassword') : t('auth.actions.showPassword')}
                                                            edge="end"
                                                            onClick={() => setShowForgotConfirmPassword((current) => !current)}
                                                        >
                                                            {showForgotConfirmPassword ? <IconEyeOff /> : <IconEye />}
                                                        </IconButton>
                                                    </InputAdornment>
                                                ),
                                            },
                                        }}
                                    />
                                    <Button
                                        disabled={
                                            forgotSubmitting ||
                                            !forgotEmailValid ||
                                            forgotEmailStatus !== 'valid' ||
                                            forgotCode.trim().length !== 6 ||
                                            !forgotPasswordValid ||
                                            !forgotPasswordsMatch
                                        }
                                        size="large"
                                        type="submit"
                                        variant="contained"
                                        sx={{ minHeight: 54, borderRadius: 0, fontWeight: 600, boxShadow: '0 12px 28px rgba(37,99,235,0.22)' }}
                                    >
                                        {forgotSubmitting ? t('auth.forgot.resetSubmitting') : t('auth.forgot.resetSubmit')}
                                    </Button>
                                </>
                            )}
                            <Box sx={{ display: 'flex', justifyContent: 'center', pt: 0.5 }}>
                                <Button
                                    onClick={() => {
                                        ++forgotEmailRequest.current
                                        setForgotMode(false)
                                        setForgotCodeSent(false)
                                        setForgotCountdown(0)
                                        setForgotCode('')
                                        setForgotNewPassword('')
                                        setForgotConfirmPassword('')
                                        setLocalError(null)
                                        setLocalSuccess(null)
                                    }}
                                    size="small"
                                    sx={{ borderRadius: 0, textTransform: 'none' }}
                                >
                                    {t('auth.forgot.backToLogin')}
                                </Button>
                            </Box>
                        </Stack>
                    ) : (
                        <Stack component="form" spacing={1} onSubmit={handleSubmit}>
                            {mode === 'setup' ? (
                                <TextField
                                    label={t('auth.fields.language')}
                                    onChange={(event) => {
                                        const nextLocale = event.target.value === 'zh-CN' ? 'zh-CN' : 'en'
                                        setSelectedLocale(nextLocale)
                                        void i18n.changeLanguage(nextLocale)
                                    }}
                                    select
                                    size="medium"
                                    sx={authFieldSx}
                                    value={selectedLocale}
                                    helperText=" "
                                >
                                    <MenuItem value="en">{t('locales.en')}</MenuItem>
                                    <MenuItem value="zh-CN">{t('locales.zh-CN')}</MenuItem>
                                </TextField>
                            ) : null}
                            {mode === 'setup' ? (
                                <TextField
                                    autoComplete="email"
                                    label={t('auth.fields.email')}
                                    onBlur={() => setEmailTouched(true)}
                                    onChange={(event) => {
                                        setEmail(event.target.value)
                                        if (!emailTouched) {
                                            setEmailTouched(true)
                                        }
                                    }}
                                    error={emailTouched && !setupEmailValid}
                                    helperText={emailTouched && !setupEmailValid ? t('auth.errors.invalidEmail') : ' '}
                                    required
                                    size="medium"
                                    sx={authFieldSx}
                                    type="email"
                                    value={email}
                                />
                            ) : null}
                            <TextField
                                autoComplete="username"
                                label={mode === 'setup' ? t('auth.fields.setupUsername') : t('auth.fields.username')}
                                onChange={(event) => setUsername(event.target.value)}
                                required
                                size="medium"
                                sx={authFieldSx}
                                value={username}
                                helperText=" "
                            />
                            <TextField
                                autoComplete={mode === 'setup' ? 'new-password' : 'current-password'}
                                label={t('auth.fields.password')}
                                onChange={(event) => setPassword(event.target.value)}
                                error={mode === 'setup' && password.length > 0 && !setupPasswordValid}
                                helperText={
                                    mode === 'setup'
                                        ? password.length > 0 && !setupPasswordValid
                                            ? t('auth.errors.passwordComplexity')
                                            : ' '
                                        : undefined
                                }
                                required
                                size="medium"
                                type={showPassword ? 'text' : 'password'}
                                sx={authFieldSx}
                                value={password}
                                slotProps={{
                                    input: {
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <IconButton
                                                    aria-label={showPassword ? t('auth.actions.hidePassword') : t('auth.actions.showPassword')}
                                                    edge="end"
                                                    onClick={() => setShowPassword((currentValue) => !currentValue)}
                                                >
                                                    {showPassword ? <IconEyeOff /> : <IconEye />}
                                                </IconButton>
                                            </InputAdornment>
                                        ),
                                    },
                                }}
                            />
                            {mode === 'setup' ? (
                                <TextField
                                    autoComplete="new-password"
                                    error={confirmPassword.length > 0 && !setupPasswordsMatch}
                                    helperText={confirmPassword.length > 0 && !setupPasswordsMatch ? t('auth.errors.passwordMismatch') : ' '}
                                    label={t('auth.fields.confirmPassword')}
                                    onChange={(event) => setConfirmPassword(event.target.value)}
                                    required
                                    size="medium"
                                    type={showConfirmPassword ? 'text' : 'password'}
                                    sx={authFieldSx}
                                    value={confirmPassword}
                                    slotProps={{
                                        input: {
                                            endAdornment: (
                                                <InputAdornment position="end">
                                                    <IconButton
                                                        aria-label={showConfirmPassword ? t('auth.actions.hidePassword') : t('auth.actions.showPassword')}
                                                        edge="end"
                                                        onClick={() => setShowConfirmPassword((currentValue) => !currentValue)}
                                                    >
                                                        {showConfirmPassword ? <IconEyeOff /> : <IconEye />}
                                                    </IconButton>
                                                </InputAdornment>
                                            ),
                                        },
                                    }}
                                />
                            ) : (
                                <Box sx={{ display: 'flex', justifyContent: 'flex-end', pt: 0.25, pb: 0.75 }}>
                                    <Typography
                                        component="button"
                                        onClick={() => {
                                            const initialEmail = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(username.trim()) ? username.trim() : ''
                                            ++forgotEmailRequest.current
                                            setForgotIdentifier(initialEmail)
                                            setForgotEmailTouched(false)
                                            setForgotEmailStatus('idle')
                                            setForgotEmailError(null)
                                            if (initialEmail) void validateForgotEmail(initialEmail)
                                            setForgotMode(true)
                                            setForgotCodeSent(false)
                                            setForgotCountdown(0)
                                            setForgotCode('')
                                            setForgotNewPassword('')
                                            setForgotConfirmPassword('')
                                            setLocalError(null)
                                            setLocalSuccess(null)
                                        }}
                                        sx={{
                                            border: 0,
                                            p: 0,
                                            background: 'transparent',
                                            fontSize: 13,
                                            fontWeight: 500,
                                            color: '#64748b',
                                            cursor: 'pointer',
                                            transition: 'color 150ms ease',
                                            '&:hover': {
                                                color: '#2563eb',
                                            },
                                        }}
                                        type="button"
                                    >
                                        {t('auth.login.forgotPassword')}
                                    </Typography>
                                </Box>
                            )}
                            <Button
                                disabled={isSubmitting || (mode === 'setup' && (!setupPasswordValid || !setupEmailValid || !setupPasswordsMatch))}
                                size="large"
                                type="submit"
                                variant="contained"
                                sx={{ minHeight: 54, borderRadius: 0, fontWeight: 600, boxShadow: '0 12px 28px rgba(37,99,235,0.22)' }}
                            >
                                {mode === 'setup'
                                    ? isSubmitting
                                        ? t('auth.setup.submitting')
                                        : t('auth.setup.submit')
                                    : isSubmitting
                                        ? t('auth.login.submitting')
                                        : t('auth.login.submit')}
                            </Button>
                        </Stack>
                    )}
                </Stack>
            </Paper>
        </Box>
    )
}