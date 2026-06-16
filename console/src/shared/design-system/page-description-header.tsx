import { Box, Typography } from '@mui/material'
import type { SxProps, Theme } from '@mui/material/styles'
import type { ReactNode } from 'react'

type PageDescriptionHeaderProps = {
    title?: string
    description?: string
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
                    gridTemplateColumns: 'minmax(0, 1fr) auto',
                    alignItems: 'flex-start',
                    columnGap: { xs: 1, md: 2 },
                    rowGap: { xs: 0.35, md: 0.6 },
                },
                ...(Array.isArray(sx) ? sx : [sx]),
            ]}
        >
            <Box sx={{ minWidth: 0, flex: '1 1 460px' }}>
                {title ? (
                    <Typography sx={{ mb: { xs: 0.2, md: 0.4 }, fontSize: 16, fontWeight: 600, lineHeight: 1.25, color: titleColor, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {title}
                    </Typography>
                ) : null}
                {description ? (
                    <Typography
                        sx={{
                            maxWidth: descriptionMaxWidth,
                            fontSize: 14,
                            lineHeight: { xs: 1.45, md: 1.6 },
                            color: descriptionColor,
                            whiteSpace: { xs: 'nowrap', md: 'normal' },
                            overflow: 'hidden',
                            textOverflow: { xs: 'ellipsis', md: 'clip' },
                        }}
                    >
                        {description}
                    </Typography>
                ) : null}
            </Box>
            {actions ? (
                <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'flex-end', width: 'auto', gap: 1, flexWrap: 'nowrap', alignSelf: 'start' }}>
                    {actions}
                </Box>
            ) : null}
        </Box>
    )
}