import { Box, Typography } from '@mui/material'
import type { SxProps, Theme } from '@mui/material/styles'
import type { ReactNode } from 'react'

type PageDescriptionHeaderProps = {
    title?: string
    description: string
    actions?: ReactNode
    descriptionColor?: string
    titleColor?: string
    descriptionMaxWidth?: number
    sx?: SxProps<Theme>
}

export function PageDescriptionHeader({
    title,
    description,
    actions,
    descriptionColor,
    titleColor,
    descriptionMaxWidth = 760,
    sx,
}: PageDescriptionHeaderProps) {
    return (
        <Box
            sx={[
                {
                    mt: { xs: -0.35, md: -0.45 },
                    mb: 2.25,
                    display: 'grid',
                    gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1fr) auto' },
                    alignItems: 'flex-start',
                    gap: 2,
                },
                ...(Array.isArray(sx) ? sx : [sx]),
            ]}
        >
            <Box sx={{ minWidth: 0, flex: '1 1 460px' }}>
                {title ? (
                    <Typography sx={{ mb: 0.4, fontSize: 16, fontWeight: 600, lineHeight: 1.25, color: titleColor }}>
                        {title}
                    </Typography>
                ) : null}
                <Typography sx={{ maxWidth: descriptionMaxWidth, fontSize: 14, lineHeight: 1.6, color: descriptionColor }}>
                    {description}
                </Typography>
            </Box>
            {actions ? (
                <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: { xs: 'flex-start', md: 'flex-end' }, gap: 1, flexWrap: 'wrap' }}>
                    {actions}
                </Box>
            ) : null}
        </Box>
    )
}