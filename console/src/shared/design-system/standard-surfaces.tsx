import { Alert, Box, Card, CardContent, CircularProgress, Dialog, Snackbar, Typography } from '@mui/material'
import type { AlertColor, DialogProps, SnackbarCloseReason, SxProps, Theme } from '@mui/material'
import type { ReactNode, SyntheticEvent } from 'react'

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
}

type SurfaceNoticeAlertProps = {
    severity: AlertColor
    title: string
    detail: string
    action?: ReactNode
}

type SurfaceFeedbackToastProps = {
    open: boolean
    severity: AlertColor
    message: string
    onClose: (event?: Event | SyntheticEvent, reason?: SnackbarCloseReason) => void
    scope?: SurfaceLayerScope
    scopeRect?: SurfaceScopeRect | null
}

type SurfaceDialogProps = DialogProps & {
    paperSx?: SxProps<Theme>
    scope?: SurfaceLayerScope
    scopeRect?: SurfaceScopeRect | null
    contentStrategy?: 'container-absolute' | 'viewport-fixed'
}

export function SurfaceDialog({ children, paperSx, scope = 'viewport', scopeRect, sx, contentStrategy = 'container-absolute', ...props }: SurfaceDialogProps) {
    const isViewportFixedContent = scope === 'content' && scopeRect && contentStrategy === 'viewport-fixed'
    const contentScopeSx =
        scope === 'content' && scopeRect
            ? {
                position: contentStrategy === 'viewport-fixed' ? ('fixed' as const) : ('absolute' as const),
                top: 0,
                left: 0,
                width: scopeRect.width,
                height: scopeRect.height,
                inset: 'auto',
                transform: isViewportFixedContent ? `translate(${scopeRect.left}px, ${scopeRect.top}px)` : 'none',
                zIndex: 5,
                '& .MuiBackdrop-root': {
                    position: contentStrategy === 'viewport-fixed' ? ('fixed' as const) : ('absolute' as const),
                    top: 0,
                    left: 0,
                    width: scopeRect.width,
                    height: scopeRect.height,
                    transform: isViewportFixedContent ? `translate(${scopeRect.left}px, ${scopeRect.top}px)` : 'none',
                },
                '& .MuiDialog-container': {
                    position: contentStrategy === 'viewport-fixed' ? ('fixed' as const) : ('absolute' as const),
                    top: 0,
                    left: 0,
                    width: scopeRect.width,
                    height: scopeRect.height,
                    inset: 'auto',
                    transform: isViewportFixedContent ? `translate(${scopeRect.left}px, ${scopeRect.top}px)` : 'none',
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
                        backgroundColor: scope === 'content' ? 'rgba(15, 23, 42, 0.12)' : 'rgba(15, 23, 42, 0.24)',
                        backdropFilter: scope === 'content' ? 'none' : 'blur(2px)',
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

export function SurfaceStateCard({ title, detail, loading = false }: SurfaceStateCardProps) {
    return (
        <Card elevation={0} sx={{ border: '1px solid rgba(15, 23, 42, 0.08)', borderRadius: '2px' }}>
            <CardContent>
                <Box sx={{ display: 'grid', justifyItems: 'center', gap: 1.5, py: 4.5, textAlign: 'center' }}>
                    {loading ? <CircularProgress size={28} /> : null}
                    {title ? <Typography sx={{ fontSize: 16, fontWeight: 600, color: '#0f172a' }}>{title}</Typography> : null}
                    <Typography color="text.secondary" variant="body2">
                        {detail}
                    </Typography>
                </Box>
            </CardContent>
        </Card>
    )
}

export function SurfaceNoticeAlert({ severity, title, detail, action }: SurfaceNoticeAlertProps) {
    return (
        <Alert action={action} severity={severity} variant="outlined" sx={{ borderRadius: '2px', alignItems: 'flex-start' }}>
            <Typography sx={{ fontWeight: 600 }}>{title}</Typography>
            <Typography variant="body2">{detail}</Typography>
        </Alert>
    )
}

export function SurfaceFeedbackToast({ open, severity, message, onClose, scope = 'viewport', scopeRect }: SurfaceFeedbackToastProps) {
    return (
        <Snackbar
            autoHideDuration={4000}
            disableWindowBlurListener
            onClose={onClose}
            open={open}
            resumeHideDuration={2500}
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
                severity={severity}
                variant="filled"
                sx={{ width: 'auto', maxWidth: 'min(560px, calc(100% - 32px))', borderRadius: '12px', boxShadow: '0 10px 24px rgba(15, 23, 42, 0.18)' }}
            >
                {message}
            </Alert>
        </Snackbar>
    )
}