import { Alert, Box, Card, CardContent, CircularProgress, Dialog, Snackbar, Typography } from '@mui/material'
import type { AlertColor, DialogProps, SnackbarCloseReason, SxProps, Theme } from '@mui/material'
import { type ReactNode, type SyntheticEvent, useEffect, useState } from 'react'

import { getSurfacePalette } from './surface-theme'

type SurfaceLayerScope = 'viewport' | 'content'

type SurfaceScopeRect = {
    top: number
    left: number
    width: number
    height: number
}

type SurfaceStateCardProps = {
    title?: string
    detail: string
    loading?: boolean
    darkMode?: boolean
}

type SurfaceNoticeAlertProps = {
    severity: AlertColor
    title: string
    detail: string
    action?: ReactNode
    darkMode?: boolean
}

type SurfaceFeedbackToastProps = {
    open: boolean
    severity: AlertColor
    message: string
    onClose: (event?: Event | SyntheticEvent, reason?: SnackbarCloseReason) => void
    scope?: SurfaceLayerScope
    scopeRect?: SurfaceScopeRect | null
    darkMode?: boolean
}

type SurfaceStatusBadgeProps = {
    label: string
    tone: 'success' | 'warning' | 'error'
    darkMode?: boolean
}

type SurfaceDialogProps = DialogProps & {
    paperSx?: SxProps<Theme>
    scope?: SurfaceLayerScope
    scopeRect?: SurfaceScopeRect | null
    contentStrategy?: 'container-absolute' | 'viewport-fixed'
    darkMode?: boolean
}

export function SurfaceDialog({ children, paperSx, scope = 'viewport', scopeRect, sx, contentStrategy = 'container-absolute', darkMode = false, ...props }: SurfaceDialogProps) {
    const palette = getSurfacePalette(darkMode)
    const contentScopeSx =
        scope === 'content' && scopeRect
            ? {
                position: contentStrategy === 'viewport-fixed' ? ('fixed' as const) : ('absolute' as const),
                top: contentStrategy === 'viewport-fixed' ? scopeRect.top : 0,
                left: contentStrategy === 'viewport-fixed' ? scopeRect.left : 0,
                width: scopeRect.width,
                height: scopeRect.height,
                ...(contentStrategy === 'viewport-fixed' ? {} : { inset: 'auto' }),
                zIndex: 5,
                '& .MuiBackdrop-root': {
                    position: 'absolute' as const,
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                },
                '& .MuiDialog-container': {
                    position: 'absolute' as const,
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    inset: 'auto',
                    alignItems: 'center',
                    justifyContent: 'center',
                },
            }
            : scope === 'content'
                ? {
                    position: 'absolute' as const,
                    inset: 0,
                    zIndex: 5,
                    '& .MuiBackdrop-root': {
                        position: 'absolute' as const,
                    },
                    '& .MuiDialog-container': {
                        position: 'absolute' as const,
                        inset: 0,
                        alignItems: 'center',
                        justifyContent: 'center',
                    },
                }
                : {}

    return (
        <Dialog
            disableScrollLock={scope === 'content'}
            fullWidth
            scroll="paper"
            {...props}
            sx={[
                {
                    '& .MuiBackdrop-root': {
                        backgroundColor: scope === 'content' ? palette.overlay : darkMode ? 'rgba(2, 6, 23, 0.42)' : 'rgba(15, 23, 42, 0.24)',
                        backdropFilter: scope === 'content' ? 'none' : 'blur(2px)',
                    },
                    '& .MuiDialogTitle-root, & .MuiDialogContent-root, & .MuiDialogActions-root': {
                        backgroundColor: palette.dialogBg,
                        color: palette.text,
                    },
                    '& .MuiDialogContent-root.MuiDialogContent-dividers': {
                        borderTopColor: palette.divider,
                        borderBottomColor: palette.divider,
                    },
                    '& .MuiDialogActions-root': {
                        borderTopColor: palette.divider,
                    },
                    '& .MuiDialog-container': {
                        alignItems: 'center',
                        justifyContent: 'center',
                        px: { xs: 1.5, md: 3 },
                        py: { xs: 1.5, md: 2.5 },
                    },
                },
                contentScopeSx,
                ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
            ]}
            slotProps={{
                paper: {
                    sx: [
                        {
                            width: { xs: 'min(100%, 800px)', md: 'min(800px, calc(100% - 32px))' },
                            maxWidth: '800px',
                            maxHeight:
                                scope === 'content' && scopeRect
                                    ? `calc(${Math.max(Math.round(scopeRect.height) - 32, 240)}px)`
                                    : scope === 'content'
                                        ? 'calc(100% - 32px)'
                                        : 'calc(100dvh - 48px)',
                            margin: 0,
                            borderRadius: '2px',
                            boxShadow: '0 16px 40px rgba(15, 23, 42, 0.16)',
                            backgroundColor: palette.dialogBg,
                            color: palette.text,
                            border: `1px solid ${palette.borderStrong}`,
                            overflow: 'hidden',
                        },
                        ...(Array.isArray(paperSx) ? paperSx : paperSx ? [paperSx] : []),
                    ],
                },
            }}
        >
            {children}
        </Dialog>
    )
}

export function SurfaceStateCard({ title, detail, loading = false, darkMode = false }: SurfaceStateCardProps) {
    const palette = getSurfacePalette(darkMode)

    return (
        <Card elevation={0} sx={{ border: `1px solid ${palette.border}`, borderRadius: '2px', backgroundColor: palette.panelBg, color: palette.text }}>
            <CardContent>
                <Box sx={{ display: 'grid', justifyItems: 'center', gap: 1.5, py: 4.5, textAlign: 'center' }}>
                    {loading ? <CircularProgress size={28} /> : null}
                    {title ? <Typography sx={{ fontSize: 16, fontWeight: 600, color: palette.text }}>{title}</Typography> : null}
                    <Typography variant="body2" sx={{ color: palette.subtleText }}>
                        {detail}
                    </Typography>
                </Box>
            </CardContent>
        </Card>
    )
}

export function SurfaceStatusBadge({ label, tone, darkMode = false }: SurfaceStatusBadgeProps) {
    const palette =
        tone === 'success'
            ? darkMode
                ? { color: '#dcfce7', backgroundColor: 'rgba(34, 197, 94, 0.24)', border: '1px solid rgba(74, 222, 128, 0.24)' }
                : { color: '#166534', backgroundColor: 'rgba(34, 197, 94, 0.14)', border: '1px solid rgba(34, 197, 94, 0.16)' }
            : tone === 'warning'
                ? darkMode
                    ? { color: '#fef3c7', backgroundColor: 'rgba(245, 158, 11, 0.24)', border: '1px solid rgba(251, 191, 36, 0.24)' }
                    : { color: '#b45309', backgroundColor: 'rgba(245, 158, 11, 0.16)', border: '1px solid rgba(245, 158, 11, 0.16)' }
                : darkMode
                    ? { color: '#fee2e2', backgroundColor: 'rgba(239, 68, 68, 0.24)', border: '1px solid rgba(248, 113, 113, 0.24)' }
                    : { color: '#b91c1c', backgroundColor: 'rgba(239, 68, 68, 0.14)', border: '1px solid rgba(239, 68, 68, 0.14)' }

    return (
        <Box
            sx={{
                display: 'inline-flex',
                alignItems: 'center',
                minHeight: 24,
                px: 1,
                borderRadius: '999px',
                fontSize: 12,
                lineHeight: 1.2,
                fontWeight: 700,
                ...palette,
            }}
        >
            {label}
        </Box>
    )
}

export function SurfaceNoticeAlert({ severity, title, detail, action, darkMode = false }: SurfaceNoticeAlertProps) {
    const palette = getSurfacePalette(darkMode)

    return (
        <Alert action={action} severity={severity} variant="outlined" sx={{ borderRadius: '2px', alignItems: 'flex-start', backgroundColor: palette.panelBg, color: palette.text, borderColor: palette.borderStrong }}>
            <Typography sx={{ fontWeight: 600, color: palette.text }}>{title}</Typography>
            <Typography variant="body2" sx={{ color: palette.subtleText }}>{detail}</Typography>
        </Alert>
    )
}

export function SurfaceFeedbackToast({ open, severity, message, onClose, scope = 'viewport', scopeRect, darkMode = false }: SurfaceFeedbackToastProps) {
    const palette = getSurfacePalette(darkMode)
    const [visibleMessage, setVisibleMessage] = useState(message)
    const [visibleSeverity, setVisibleSeverity] = useState(severity)

    // Keep the last non-empty message and its severity visible during the exit
    // animation to prevent a blank/miscolored flash when feedback is cleared
    useEffect(() => {
        if (message) {
            setVisibleMessage(message)
            setVisibleSeverity(severity)
        }
    }, [message, severity])

    // When the snackbar closes and the exit animation finishes, clear preserved state
    const handleExited = () => {
        setVisibleMessage('')
    }

    return (
        <Snackbar
            autoHideDuration={4000}
            disableWindowBlurListener
            onClose={onClose}
            open={open}
            resumeHideDuration={2500}
            slotProps={{ transition: { onExited: handleExited } }}
            anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            sx={
                scope === 'content' && scopeRect
                    ? {
                        position: 'fixed',
                        top: scopeRect.top + 24,
                        left: `${scopeRect.left}px !important`,
                        width: `${scopeRect.width}px !important`,
                        display: 'flex',
                        justifyContent: 'center',
                        transform: 'none !important',
                        right: 'auto !important',
                        zIndex: 1502,
                    }
                    : scope === 'content'
                        ? {
                            position: 'absolute',
                            top: 24,
                            left: '0 !important',
                            width: '100% !important',
                            display: 'flex',
                            justifyContent: 'center',
                            transform: 'none !important',
                            right: 'auto !important',
                            zIndex: 6,
                        }
                        : undefined
            }
        >
            <Alert
                onClose={onClose}
                severity={visibleSeverity}
                variant="filled"
                sx={{
                    width: 'auto',
                    minWidth: 0,
                    maxWidth: 'min(1200px, calc(100vw - 48px))',
                    borderRadius: '2px',
                    boxShadow: darkMode ? `0 10px 24px ${palette.overlay}` : '0 10px 24px rgba(15, 23, 42, 0.18)',
                    overflow: 'visible',
                    '& .MuiAlert-message': {
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        minWidth: 0,
                        maxWidth: 'min(1100px, calc(100vw - 120px))',
                    },
                    '& .MuiAlert-action': {
                        alignItems: 'center',
                        overflow: 'visible',
                        flexShrink: 0,
                    },
                }}
            >
                {visibleMessage}
            </Alert>
        </Snackbar>
    )
}