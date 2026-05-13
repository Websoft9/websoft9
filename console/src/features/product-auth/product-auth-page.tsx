import {
    Alert,
    Box,
    Button,
    IconButton,
    InputAdornment,
    Paper,
    Stack,
    TextField,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'

import { prewarmAuthenticatedIntegrationSessions } from '../integrations/integration-session-bootstrap'
import { useProductAuth } from './product-auth-provider'

type ProductAuthPageProps = {
    mode: 'login' | 'setup'
}

function resolveNext(search: string) {
    const params = new URLSearchParams(search)
    const next = params.get('next')
    return next && next.startsWith('/') ? next : '/users'
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
    const [displayName, setDisplayName] = useState('')
    const [localError, setLocalError] = useState<string | null>(null)
    const nextPath = useMemo(() => resolveNext(location.search), [location.search])
    const setupPasswordValid = useMemo(
        () => password.length >= 8 && /[A-Z]/.test(password) && /[a-z]/.test(password) && /\d/.test(password) && /[^A-Za-z0-9]/.test(password),
        [password],
    )
    const authFieldSx = useMemo(
        () => ({
            '& .MuiOutlinedInput-root': {
                borderRadius: '18px',
                backgroundColor: '#fbfdff',
            },
            '& input:-webkit-autofill': {
                WebkitBoxShadow: '0 0 0 100px #fbfdff inset',
                WebkitTextFillColor: '#0f172a',
                caretColor: '#0f172a',
                borderRadius: '18px',
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

        if (mode === 'setup' && !status.initialization_required) {
            navigate(`/auth/login?next=${encodeURIComponent(nextPath)}`, { replace: true })
            return
        }

        if (mode === 'login' && status.initialization_required) {
            navigate(`/auth/setup?next=${encodeURIComponent(nextPath)}`, { replace: true })
        }
    }, [isLoading, mode, navigate, nextPath, status])

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        setLocalError(null)

        if (mode === 'setup') {
            if (!setupPasswordValid) {
                setLocalError(t('auth.errors.passwordComplexity'))
                return
            }
        }

        try {
            const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
            const nextStatus =
                mode === 'setup'
                    ? await initialize({ username, password, displayName })
                    : await login({ username, password })

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
            <Paper
                elevation={0}
                sx={{
                    width: '100%',
                    maxWidth: 440,
                    p: { xs: 3, md: 4 },
                    borderRadius: '28px',
                    border: '1px solid rgba(148, 163, 184, 0.18)',
                    background: 'rgba(255,255,255,0.97)',
                    backdropFilter: 'blur(12px)',
                    boxShadow: '0 20px 60px rgba(15, 23, 42, 0.08)',
                }}
            >
                <Stack spacing={3}>
                    <Stack spacing={1.25}>
                        <Typography color="text.secondary" sx={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.8, textTransform: 'uppercase' }}>
                            {mode === 'setup' ? t('auth.setup.eyebrow') : t('auth.login.eyebrow')}
                        </Typography>
                        <Typography sx={{ fontSize: { xs: 24, md: 28 }, fontWeight: 600, lineHeight: 1.08, color: '#0f172a', letterSpacing: '-0.02em' }}>
                            {mode === 'setup' ? t('auth.setup.title') : t('auth.login.title')}
                        </Typography>
                    </Stack>

                    {(localError || errorMessage) && <Alert severity="error">{mapAuthErrorMessage(localError ?? errorMessage, t)}</Alert>}

                    <Stack component="form" spacing={2.25} onSubmit={handleSubmit}>
                        {mode === 'setup' ? (
                            <TextField
                                label={t('auth.fields.displayName')}
                                onChange={(event) => setDisplayName(event.target.value)}
                                required
                                size="medium"
                                sx={authFieldSx}
                                value={displayName}
                            />
                        ) : null}
                        <TextField
                            label={t('auth.fields.username')}
                            onChange={(event) => setUsername(event.target.value)}
                            required
                            size="medium"
                            sx={authFieldSx}
                            value={username}
                        />
                        <TextField
                            label={t('auth.fields.password')}
                            onChange={(event) => setPassword(event.target.value)}
                            helperText={mode === 'setup' ? t('auth.passwordPolicy') : ' '}
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
                        <Button
                            disabled={isSubmitting || (mode === 'setup' && !setupPasswordValid)}
                            size="large"
                            type="submit"
                            variant="contained"
                            sx={{ minHeight: 54, borderRadius: '18px', fontWeight: 600, boxShadow: '0 12px 28px rgba(37,99,235,0.22)' }}
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
                </Stack>
            </Paper>
        </Box>
    )
}