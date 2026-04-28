import type { ReactElement } from 'react'
import { useEffect, useState } from 'react'
import { Box, CircularProgress, Stack, Typography } from '@mui/material'
import { Navigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useProductAuth } from './product-auth-provider'

type ProductAuthRouteGuardProps = {
    routeSegment: string
    children: ReactElement
}

export function ProductAuthRouteGuard({ children, routeSegment }: ProductAuthRouteGuardProps) {
    const { t } = useTranslation('shell')
    const location = useLocation()
    const { errorMessage, isLoading, refresh, status } = useProductAuth()
    const [isCheckingAccess, setIsCheckingAccess] = useState(false)
    const routeKey = `${location.pathname}${location.search}`
    const isProtectedRoute = Boolean(status?.enabled && status.protected_modules.includes(routeSegment))

    useEffect(() => {
        if (!isProtectedRoute) {
            setIsCheckingAccess(false)
            return
        }

        let active = true
        setIsCheckingAccess(true)
        void refresh().finally(() => {
            if (!active) {
                return
            }
            setIsCheckingAccess(false)
        })

        return () => {
            active = false
        }
    }, [isProtectedRoute, refresh, routeKey])

    if (errorMessage && !isLoading && !isCheckingAccess) {
        return (
            <Box sx={{ display: 'grid', minHeight: 'calc(100vh - 120px)', placeItems: 'center', px: 2 }}>
                <Stack spacing={1.5} sx={{ maxWidth: 440 }}>
                    <Typography sx={{ fontSize: 22, fontWeight: 600 }}>{t('auth.statusErrorTitle')}</Typography>
                    <Typography color="text.secondary">{errorMessage}</Typography>
                </Stack>
            </Box>
        )
    }

    if (isLoading || !status || isCheckingAccess) {
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
        return <Navigate replace to={`/auth/setup?next=${encodeURIComponent(`${location.pathname}${location.search}`)}`} />
    }

    if (!status.authenticated) {
        return <Navigate replace to={`/auth/login?next=${encodeURIComponent(`${location.pathname}${location.search}`)}`} />
    }

    return children
}