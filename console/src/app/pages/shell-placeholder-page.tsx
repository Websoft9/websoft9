import { Box, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'

import type { ShellPageKey } from '../shell/shell-navigation'

type ShellPlaceholderPageProps = {
    pageKey: ShellPageKey
}

export function ShellPlaceholderPage({ pageKey }: ShellPlaceholderPageProps) {
    const { t } = useTranslation('shell')

    return (
        <Box
            sx={{
                minHeight: 'calc(100vh - 120px)',
                px: { xs: 0.5, md: 1 },
                py: { xs: 1, md: 1.5 },
            }}
        >
            <Stack spacing={3}>
                <Stack spacing={1.5}>
                    <Typography color="text.secondary" sx={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.6 }}>
                        {t(`pages.${pageKey}.eyebrow`)}
                    </Typography>
                    <Typography component="h1" sx={{ fontSize: { xs: 28, md: 32 }, fontWeight: 500, lineHeight: 1.1 }}>
                        {t(`pages.${pageKey}.title`)}
                    </Typography>
                    <Typography color="text.secondary" variant="body1">
                        {t(`pages.${pageKey}.description`)}
                    </Typography>
                </Stack>
                <Box
                    sx={{
                        display: 'grid',
                        gap: 2,
                        gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' },
                    }}
                >
                    <Box
                        sx={{
                            p: 2.5,
                            border: '1px solid rgba(15, 23, 42, 0.08)',
                            backgroundColor: '#f9fbfd',
                        }}
                    >
                        <Typography variant="subtitle1">{t(`pages.${pageKey}.nextStepTitle`)}</Typography>
                        <Typography color="text.secondary" sx={{ mt: 1 }} variant="body2">
                            {t(`pages.${pageKey}.nextStepBody`)}
                        </Typography>
                    </Box>
                    <Box
                        sx={{
                            p: 2.5,
                            border: '1px solid rgba(15, 23, 42, 0.08)',
                            backgroundColor: '#f9fbfd',
                        }}
                    >
                        <Typography variant="subtitle1">{t(`pages.${pageKey}.systemTitle`)}</Typography>
                        <Typography color="text.secondary" sx={{ mt: 1 }} variant="body2">
                            {t(`pages.${pageKey}.systemBody`)}
                        </Typography>
                    </Box>
                </Box>
            </Stack>
        </Box>
    )
}