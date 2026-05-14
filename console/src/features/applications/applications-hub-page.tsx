import { Box, Button, Card, CardContent, Stack, Typography } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'

const hubCardSx = {
    borderRadius: '2px',
    border: '1px solid rgba(226, 232, 240, 0.95)',
    boxShadow: '0 10px 30px rgba(15, 23, 42, 0.06)',
    background: 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
}

export function DeploymentHubPage() {
    const navigate = useNavigate()
    const { t } = useTranslation('shell')

    const entries = [
        {
            key: 'marketplace',
            title: t('nav.appStore.label'),
            description: t('appStorePage.hero.description'),
            action: t('applicationsHubPage.menu.marketplace'),
            target: '/appstore',
        },
        {
            key: 'customInstall',
            title: t('applicationsHubPage.cards.customInstall.title'),
            description: t('applicationsHubPage.cards.customInstall.description'),
            action: t('applicationsHubPage.cards.customInstall.action'),
            target: '/applications/custom-install',
        },
        {
            key: 'runtime',
            title: t('applicationsHubPage.cards.runtime.title'),
            description: t('applicationsHubPage.cards.runtime.description'),
            action: t('applicationsHubPage.cards.runtime.action'),
            target: '/applications/runtime',
        },
    ]

    return (
        <Box
            sx={{
                height: 'calc(100vh - 120px)',
                position: 'relative',
                mx: { xs: -1, md: -3 },
                my: { xs: -1.25, md: -2.25 },
                px: { xs: 2, md: 3 },
                py: { xs: 1.25, md: 1.5 },
                backgroundColor: '#ffffff',
                overflowY: 'auto',
            }}
        >
            <Stack spacing={2.5}>
                <PageDescriptionHeader
                    title={t('applicationsHubPage.hero.title')}
                    description={t('applicationsHubPage.hero.description')}
                    descriptionColor="#526170"
                />

                <Box
                    sx={{
                        display: 'grid',
                        gap: 2,
                        gridTemplateColumns: { xs: '1fr', md: 'repeat(3, minmax(0, 1fr))' },
                    }}
                >
                    {entries.map((entry) => (
                        <Card key={entry.key} elevation={0} sx={hubCardSx}>
                            <CardContent>
                                <Stack spacing={2}>
                                    <Box>
                                        <Typography sx={{ fontSize: 18, fontWeight: 600, color: '#111827' }}>
                                            {entry.title}
                                        </Typography>
                                        <Typography sx={{ mt: 0.75, fontSize: 14, lineHeight: 1.65, color: '#526170' }}>
                                            {entry.description}
                                        </Typography>
                                    </Box>
                                    <Box>
                                        <Button
                                            onClick={() => {
                                                navigate(entry.target)
                                            }}
                                            variant="contained"
                                            sx={{ borderRadius: '2px', textTransform: 'none', boxShadow: 'none' }}
                                        >
                                            {entry.action}
                                        </Button>
                                    </Box>
                                </Stack>
                            </CardContent>
                        </Card>
                    ))}
                </Box>
            </Stack>
        </Box>
    )
}