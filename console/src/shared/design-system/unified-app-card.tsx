import { Box, Card, CardContent, Typography, type SxProps, type Theme } from '@mui/material'
import type { ReactNode } from 'react'

import { getSurfacePalette } from './surface-theme'

type UnifiedAppCardProps = {
    darkMode: boolean
    title: string
    description: string
    media: ReactNode
    onClick?: () => void
    interactive?: boolean
    status?: ReactNode
    actions?: ReactNode
    descriptionColor?: string
    titleColor?: string
    cardSx?: SxProps<Theme>
    orientation?: 'horizontal' | 'vertical'
}

export function UnifiedAppCard({
    darkMode,
    title,
    description,
    media,
    onClick,
    interactive = true,
    status,
    actions,
    descriptionColor,
    titleColor,
    cardSx,
    orientation = 'horizontal',
}: UnifiedAppCardProps) {
    const palette = getSurfacePalette(darkMode)
    const hasActions = Boolean(actions)
    const isVertical = orientation === 'vertical'

    return (
        <Card
            elevation={0}
            onClick={onClick}
            sx={[
                {
                    border: `1px solid ${palette.border}`,
                    borderRadius: '2px',
                    backgroundColor: palette.panelBg,
                    boxShadow: '0 2px 5px rgba(0, 0, 0, 0.1)',
                    cursor: interactive && onClick ? 'pointer' : 'default',
                    transition: 'background-color 120ms ease, box-shadow 120ms ease',
                    '&:hover': interactive && onClick
                        ? {
                            backgroundColor: palette.panelHover,
                            boxShadow: '0 2px 5px rgba(0, 0, 0, 0.1)',
                        }
                        : undefined,
                },
                ...(Array.isArray(cardSx) ? cardSx : cardSx ? [cardSx] : []),
            ]}
        >
            <CardContent sx={{ p: '10px !important' }}>
                <Box sx={{ position: 'relative' }}>
                    {hasActions ? (
                        <Box
                            sx={{
                                position: 'absolute',
                                top: 0,
                                right: 0,
                                zIndex: 1,
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 0.25,
                            }}
                        >
                            {actions}
                        </Box>
                    ) : null}
                    <Box sx={isVertical ? {
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'flex-start',
                        minHeight: 184,
                        px: 0.5,
                        pt: 0.75,
                        pb: 0.25,
                    } : {
                        display: 'grid',
                        gridTemplateColumns: '100px minmax(0, 1fr)',
                        gap: 0,
                        alignItems: 'center',
                        minHeight: 80,
                    }}>
                        <Box sx={isVertical ? {
                            width: 100,
                            minWidth: 100,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            mb: 1.1,
                        } : {
                            width: 100,
                            minWidth: 100,
                            px: '10px',
                            boxSizing: 'border-box',
                        }}>
                            <Box sx={isVertical ? { width: 80, height: 80 } : { width: 80, height: 80 }}>
                                {media}
                            </Box>
                        </Box>
                        <Box sx={isVertical ? {
                            width: '100%',
                            minWidth: 0,
                            textAlign: 'center',
                            px: 0.75,
                        } : {
                            minWidth: 0,
                            textAlign: 'left',
                            pr: hasActions ? 7 : 0,
                        }}>
                            <Box sx={isVertical ? {
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                gap: 0.55,
                                mb: 0.65,
                                minWidth: 0,
                            } : {
                                display: 'flex',
                                alignItems: 'center',
                                gap: 0.75,
                                mb: 0.5,
                                minWidth: 0,
                            }}>
                                <Typography
                                    sx={{
                                        ...(isVertical ? {} : { flex: '1 1 auto' }),
                                        minWidth: 0,
                                        maxWidth: '100%',
                                        fontSize: 17,
                                        fontWeight: 600,
                                        lineHeight: 1.25,
                                        color: titleColor ?? palette.text,
                                        whiteSpace: 'nowrap',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                    }}
                                >
                                    {title}
                                </Typography>
                                {status ? <Box sx={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, flexShrink: 0, flexWrap: 'wrap' }}>{status}</Box> : null}
                            </Box>
                            {description ? (
                                <Typography
                                    sx={{
                                        fontSize: 14,
                                        lineHeight: 1.45,
                                        minHeight: isVertical ? 40 : 44,
                                        color: descriptionColor ?? palette.subtleText,
                                        fontWeight: 400,
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        display: '-webkit-box',
                                        WebkitLineClamp: 2,
                                        WebkitBoxOrient: 'vertical',
                                    }}
                                >
                                    {description}
                                </Typography>
                            ) : null}
                        </Box>
                    </Box>
                </Box>
            </CardContent>
        </Card>
    )
}