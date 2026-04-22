import { Box, Chip, Paper, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'

import type { ShellPageKey } from '../shell/shell-navigation'

type ShellPlaceholderPageProps = {
    pageKey: ShellPageKey
}

export function ShellPlaceholderPage({ pageKey }: ShellPlaceholderPageProps) {
    const { t } = useTranslation('shell')

    return (
        <Paper
            elevation={0}
            sx={{
                borderRadius: 4,
                border: '1px solid',
                borderColor: 'divider',
                p: { xs: 3, md: 4 },
                minHeight: 320,
                background:
                    'linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(245,247,251,0.92) 100%)',
            }}
        >
            <Stack spacing={3}>
                <Chip label={t(`pages.${pageKey}.eyebrow`)} color="secondary" sx={{ alignSelf: 'flex-start' }} />
                <Stack spacing={1.5}>
                    <Typography component="h1" variant="h3">
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
                    <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3 }}>
                        <Typography variant="subtitle1">{t(`pages.${pageKey}.nextStepTitle`)}</Typography>
                        <Typography color="text.secondary" sx={{ mt: 1 }} variant="body2">
                            {t(`pages.${pageKey}.nextStepBody`)}
                        </Typography>
                    </Paper>
                    <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3 }}>
                        <Typography variant="subtitle1">{t(`pages.${pageKey}.systemTitle`)}</Typography>
                        <Typography color="text.secondary" sx={{ mt: 1 }} variant="body2">
                            {t(`pages.${pageKey}.systemBody`)}
                        </Typography>
                    </Paper>
                </Box>
            </Stack>
        </Paper>
    )
}