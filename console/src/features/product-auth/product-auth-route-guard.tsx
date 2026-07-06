import type { ReactElement } from 'react'
import { Box, CircularProgress, Stack, Typography } from '@mui/material'
import { Navigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useProductAuth } from './product-auth-provider'

type ProductAuthRouteGuardProps = {
    routeSegment: string
    children: ReactElement
    requireAuthentication?: boolean
}

export function ProductAuthRouteGuard({ children, routeSegment, requireAuthentication = false }: ProductAuthRouteGuardProps) {
    const { t } = useTranslation('shell')
    const location = useLocation()
    const { errorMessage, isLoading, status } = useProductAuth()
    const isProtectedRoute = Boolean(status?.enabled && (requireAuthentication || status.protected_modules.includes(routeSegment)))

    if (errorMessage && !isLoading) {
        return (
            <Box sx={{ display: 'grid', minHeight: 'calc(100vh - 120px)', placeItems: 'center', px: 2 }}>
                <Stack spacing={1.5} sx={{ maxWidth: 440 }}>
                    <Typography sx={{ fontSize: 22, fontWeight: 600 }}>{t('auth.statusErrorTitle')}</Typography>
                    <Typography color="text.secondary">{errorMessage}</Typography>
                </Stack>
            </Box>
        )
    }

    if (isLoading || !status) {
        return (
            <Box sx={{ display: 'grid', minHeight: 'calc(100vh - 120px)', placeItems: 'center' }}>
                <Stack spacing={1.5} sx={{ alignItems: 'center' }}>
                    <CircularProgress size={28} />
                    <Typography variant="body2">{t('auth.loading')}</Typography>
                </Stack>
            </Box>
        )
    }

    if (!status.enabled) {
        return children
    }

    if (!isProtectedRoute) {
        return children
    }

    if (status.initialization_required) {
        return <Navigate replace to={status.cloud_marketplace_setup ? '/setup' : `/auth/setup?next=${encodeURIComponent(`${location.pathname}${location.search}`)}`} />
    }

    if (status.cloud_marketplace_setup_pending && status.authenticated) {
        return <Navigate replace to="/setup" />
    }

    if (!status.authenticated) {
        return <Navigate replace to={`/auth/login?next=${encodeURIComponent(`${location.pathname}${location.search}`)}`} />
    }

    return children
}