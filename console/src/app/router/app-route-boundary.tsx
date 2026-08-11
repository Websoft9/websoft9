import { Box, Button, Stack, Typography } from '@mui/material'
import { useEffect } from 'react'
import { Outlet, useRouteError } from 'react-router-dom'

const CHUNK_RELOAD_KEY = 'websoft9:chunk-load-reload'
const CHUNK_RELOAD_WINDOW_MS = 30_000

function getErrorMessage(error: unknown) {
    return error instanceof Error ? error.message : String(error ?? '')
}

function isChunkLoadError(message: string) {
    return (
        message.includes('dynamically imported module') ||
        message.includes('error loading dynamically imported module') ||
        message.includes('Failed to fetch dynamically imported module')
    )
}

function shouldRetryChunkLoad() {
    const lastReloadAt = Number(window.sessionStorage.getItem(CHUNK_RELOAD_KEY) ?? '0')
    return !Number.isFinite(lastReloadAt) || Date.now() - lastReloadAt > CHUNK_RELOAD_WINDOW_MS
}

export function AppRouteBoundary() {
    return <Outlet />
}

export function AppRouteErrorBoundary() {
    const error = useRouteError()
    const message = getErrorMessage(error)
    const shouldReload = isChunkLoadError(message) && shouldRetryChunkLoad()

    useEffect(() => {
        if (!shouldReload) {
            return
        }

        window.sessionStorage.setItem(CHUNK_RELOAD_KEY, String(Date.now()))
        window.location.reload()
    }, [message, shouldReload])

    if (shouldReload) {
        return null
    }

    return (
        <Box component="main" sx={{ display: 'grid', minHeight: '100dvh', placeItems: 'center', px: 2, bgcolor: '#f6f8fc' }}>
            <Stack spacing={2} sx={{ width: 'min(440px, 100%)' }}>
                <Stack spacing={0.75}>
                    <Typography sx={{ fontSize: 24, fontWeight: 600 }}>页面加载失败</Typography>
                    <Typography color="text.secondary">页面资源未能加载，可能是系统已更新或网络暂时异常。</Typography>
                </Stack>
                <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button variant="contained" onClick={() => window.location.reload()}>刷新页面</Button>
                </Box>
            </Stack>
        </Box>
    )
}