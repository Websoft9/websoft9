import {
    Box,
    Button,
    IconButton,
    InputAdornment,
    Paper,
    Stack,
    TextField,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

const DEFAULT_LOGO = '/websoft9.png'
const DEFAULT_TITLE = 'Websoft9'
const DEFAULT_BG =
    'radial-gradient(circle at top left, rgba(59,130,246,0.14), transparent 28%), radial-gradient(circle at bottom right, rgba(14,165,233,0.1), transparent 24%), linear-gradient(180deg, #edf3fb 0%, #f8fafc 100%)'

function isValidUrl(value: string) {
    const trimmed = value.trim()
    if (!trimmed) return false
    if (trimmed.startsWith('/')) return true
    return /^https?:\/\//i.test(trimmed)
}

function EyeIcon() {
    return (
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zm0 12.5a5 5 0 1 1 0-10 5 5 0 0 1 0 10zm0-8a3 3 0 1 0 0 6 3 3 0 0 0 0-6z" />
        </svg>
    )
}

export function BrandPreviewPage() {
    const { t } = useTranslation('shell')
    const [searchParams] = useSearchParams()
    const [bgImage, setBgImage] = useState('')
    const [logoSrc, setLogoSrc] = useState(DEFAULT_LOGO)
    const [title, setTitle] = useState(DEFAULT_TITLE)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        // URL params take priority — enables preview of unsaved drafts
        const paramTitle = searchParams.get('title')
        const paramLogo = searchParams.get('logo')
        const paramBg = searchParams.get('bg')

        if (paramTitle || paramLogo || paramBg) {
            if (paramTitle) setTitle(paramTitle)
            if (paramLogo && isValidUrl(paramLogo)) setLogoSrc(paramLogo)
            if (paramBg && isValidUrl(paramBg)) setBgImage(paramBg)
            setLoading(false)
            return
        }

        // Fall back to API (saved values)
        let disposed = false

        async function load() {
            try {
                const response = await fetch('/api/settings/platform_brand', {
                    credentials: 'include',
                    headers: { Accept: 'application/json' },
                })
                if (!response.ok) return
                const payload = (await response.json()) as {
                    title?: unknown
                    logo_url?: unknown
                    login_background?: unknown
                }
                if (disposed) return

                const resolvedTitle =
                    typeof payload.title === 'string' && payload.title.trim()
                        ? payload.title.trim()
                        : DEFAULT_TITLE
                const resolvedLogo =
                    typeof payload.logo_url === 'string' && isValidUrl(payload.logo_url)
                        ? payload.logo_url.trim()
                        : DEFAULT_LOGO
                const resolvedBg =
                    typeof payload.login_background === 'string' && isValidUrl(payload.login_background)
                        ? payload.login_background.trim()
                        : ''

                setTitle(resolvedTitle)
                setLogoSrc(resolvedLogo)
                setBgImage(resolvedBg)
            } catch {
                // keep defaults
            } finally {
                if (!disposed) setLoading(false)
            }
        }

        void load()
        return () => {
            disposed = true
        }
    }, [searchParams])

    const background = bgImage
        ? `url(${bgImage}) center/cover no-repeat`
        : DEFAULT_BG

    // Mirror authFieldSx from product-auth-page.tsx
    const authFieldSx = useMemo(
        () => ({
            '& .MuiOutlinedInput-root': {
                borderRadius: '4px',
                backgroundColor: '#fbfdff',
            },
            '& input:-webkit-autofill': {
                WebkitBoxShadow: '0 0 0 100px #fbfdff inset',
                WebkitTextFillColor: '#0f172a',
                caretColor: '#0f172a',
                borderRadius: '4px',
                transition: 'background-color 9999s ease-out 0s',
            },
        }),
        [],
    )

    if (loading) {
        return (
            <Box
                sx={{
                    minHeight: '100vh',
                    display: 'grid',
                    placeItems: 'center',
                    background: DEFAULT_BG,
                }}
            >
                <Typography color="text.secondary">{t('states.loading')}</Typography>
            </Box>
        )
    }

    return (
        <Box
            sx={{
                minHeight: '100vh',
                display: 'grid',
                placeItems: 'center',
                px: { xs: 2, md: 4 },
                py: { xs: 3, md: 5 },
                background,
            }}
        >
            <Paper
                elevation={0}
                sx={{
                    width: '100%',
                    maxWidth: 480,
                    p: { xs: 3, md: 4 },
                    borderRadius: '4px',
                    border: '1px solid rgba(148, 163, 184, 0.18)',
                    background: 'rgba(255,255,255,0.97)',
                    backdropFilter: 'blur(12px)',
                    boxShadow: '0 20px 60px rgba(15, 23, 42, 0.08)',
                }}
            >
                <Stack spacing={3}>
                    {/* Header — identical to ProductAuthPage */}
                    <Stack spacing={1.25}>
                        <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                            <Box
                                component="img"
                                alt={title}
                                src={logoSrc}
                                onError={(e: React.SyntheticEvent<HTMLImageElement>) => {
                                    (e.target as HTMLImageElement).src = DEFAULT_LOGO
                                }}
                                sx={{
                                    width: 44,
                                    height: 44,
                                    borderRadius: '6px',
                                    objectFit: 'contain',
                                    backgroundColor: '#ffffff',
                                    border: '1px solid rgba(148, 163, 184, 0.22)',
                                    p: 0.75,
                                }}
                            />
                            <Stack spacing={0.25}>
                                <Typography sx={{ fontSize: 18, fontWeight: 700, color: '#0f172a', lineHeight: 1.1 }}>
                                    {title}
                                </Typography>
                            </Stack>
                        </Stack>
                    </Stack>

                    {/* Form — using real MUI components, identical to ProductAuthPage */}
                    <Stack component="form" spacing={1} onSubmit={(e) => e.preventDefault()}>
                        <TextField
                            label={t('auth.fields.username')}
                            size="medium"
                            sx={authFieldSx}
                            helperText=" "
                        />
                        <TextField
                            label={t('auth.fields.password')}
                            size="medium"
                            type="password"
                            sx={authFieldSx}
                            helperText=" "
                            slotProps={{
                                input: {
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <IconButton edge="end" onClick={(e) => e.preventDefault()}>
                                                <EyeIcon />
                                            </IconButton>
                                        </InputAdornment>
                                    ),
                                },
                            }}
                        />
                        <Button
                            size="large"
                            type="submit"
                            variant="contained"
                            onClick={(e) => e.preventDefault()}
                            sx={{
                                minHeight: 54,
                                borderRadius: '4px',
                                fontWeight: 600,
                                boxShadow: '0 12px 28px rgba(37,99,235,0.22)',
                            }}
                        >
                            {t('auth.login.submit')}
                        </Button>
                    </Stack>
                </Stack>
            </Paper>


        </Box>
    )
}
