import {
    Alert,
    Box,
    Button,
    Paper,
    Stack,
    TextField,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'

import { useProductAuth } from './product-auth-provider'

type ProductAuthPageProps = {
    mode: 'login' | 'setup'
}

function resolveNext(search: string) {
    const params = new URLSearchParams(search)
    const next = params.get('next')
    return next && next.startsWith('/') ? next : '/users'
}

export function ProductAuthPage({ mode }: ProductAuthPageProps) {
    const { t } = useTranslation('shell')
    const navigate = useNavigate()
    const location = useLocation()
    const { errorMessage, initialize, isLoading, isSubmitting, login, status } = useProductAuth()
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [displayName, setDisplayName] = useState('')
    const [localError, setLocalError] = useState<string | null>(null)
    const nextPath = useMemo(() => resolveNext(location.search), [location.search])

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

        try {
            if (mode === 'setup') {
                await initialize({ username, password, displayName })
            } else {
                await login({ username, password })
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
                px: 2,
                py: 4,
                background:
                    'radial-gradient(circle at top left, rgba(28,118,255,0.14), transparent 38%), linear-gradient(180deg, #eef3f8 0%, #f7f9fc 100%)',
            }}
        >
            <Paper elevation={0} sx={{ width: '100%', maxWidth: 540, p: { xs: 3, md: 4 }, border: '1px solid rgba(15, 23, 42, 0.08)' }}>
                <Stack spacing={3}>
                    <Stack spacing={1}>
                        <Typography color="text.secondary" sx={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.8 }}>
                            {mode === 'setup' ? t('auth.setup.eyebrow') : t('auth.login.eyebrow')}
                        </Typography>
                        <Typography sx={{ fontSize: { xs: 28, md: 34 }, fontWeight: 600, lineHeight: 1.05 }}>
                            {mode === 'setup' ? t('auth.setup.title') : t('auth.login.title')}
                        </Typography>
                        <Typography color="text.secondary">
                            {mode === 'setup' ? t('auth.setup.description') : t('auth.login.description')}
                        </Typography>
                    </Stack>

                    {(localError || errorMessage) && <Alert severity="error">{localError ?? errorMessage}</Alert>}

                    <Stack component="form" spacing={2} onSubmit={handleSubmit}>
                        {mode === 'setup' ? (
                            <TextField
                                label={t('auth.fields.displayName')}
                                onChange={(event) => setDisplayName(event.target.value)}
                                required
                                value={displayName}
                            />
                        ) : null}
                        <TextField label={t('auth.fields.username')} onChange={(event) => setUsername(event.target.value)} required value={username} />
                        <TextField
                            label={t('auth.fields.password')}
                            onChange={(event) => setPassword(event.target.value)}
                            required
                            type="password"
                            value={password}
                        />
                        <Button disabled={isSubmitting} size="large" type="submit" variant="contained">
                            {mode === 'setup'
                                ? isSubmitting
                                    ? t('auth.setup.submitting')
                                    : t('auth.setup.submit')
                                : isSubmitting
                                    ? t('auth.login.submitting')
                                    : t('auth.login.submit')}
                        </Button>
                    </Stack>

                    <Stack spacing={0.75}>
                        <Typography sx={{ fontSize: 13, fontWeight: 600 }}>{t('auth.protectedModulesTitle')}</Typography>
                        <Typography color="text.secondary" variant="body2">
                            {(status?.protected_modules ?? ['users', 'files', 'terminal', 'services', 'logs']).join(', ')}
                        </Typography>
                    </Stack>
                </Stack>
            </Paper>
        </Box>
    )
}