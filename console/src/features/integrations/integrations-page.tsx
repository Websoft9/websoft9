import {
    Alert,
    Box,
    Button,
    Chip,
    Paper,
    Stack,
    Typography,
} from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { integrationDefinitions, type IntegrationKey, type IntegrationStatus } from './integration-model'
import { useIntegrationStatuses, type IntegrationStatusSnapshot } from './use-integration-status'

const statusChipColorMap: Record<IntegrationStatus, 'default' | 'success' | 'warning' | 'error' | 'info'> = {
    loading: 'info',
    available: 'success',
    unavailable: 'warning',
    'configuration-error': 'error',
    'session-error': 'error',
}

function IntegrationCard({
    integrationKey,
    snapshot,
}: {
    integrationKey: IntegrationKey
    snapshot: IntegrationStatusSnapshot
}) {
    const { t } = useTranslation('shell')
    const definition = integrationDefinitions.find((item) => item.key === integrationKey)

    if (!definition) {
        return null
    }

    const statusKey = snapshot.status
    const detail = snapshot.httpStatus
        ? t(`integrations.states.${statusKey}.detailWithCode`, { statusCode: snapshot.httpStatus })
        : t(`integrations.states.${statusKey}.detail`)

    return (
        <Paper
            elevation={0}
            sx={{
                borderRadius: 3,
                border: '1px solid',
                borderColor: 'divider',
                p: 2.5,
                backgroundColor: 'background.paper',
            }}
        >
            <Stack spacing={2.25}>
                <Stack direction="row" spacing={1.25} sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
                    <Stack spacing={0.5}>
                        <Typography variant="h6">{t(`integrations.catalog.${integrationKey}.title`)}</Typography>
                        <Typography color="text.secondary" variant="body2">
                            {t(`integrations.catalog.${integrationKey}.description`)}
                        </Typography>
                    </Stack>
                    <Chip color={statusChipColorMap[statusKey]} label={t(`integrations.states.${statusKey}.label`)} />
                </Stack>

                <Alert severity={statusKey === 'available' ? 'success' : statusKey === 'loading' ? 'info' : 'warning'}>
                    <Typography variant="body2">{t(`integrations.states.${statusKey}.summary`)}</Typography>
                </Alert>

                <Box
                    sx={{
                        display: 'grid',
                        gap: 1.5,
                        gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))' },
                    }}
                >
                    <Paper variant="outlined" sx={{ borderRadius: 3, p: 2 }}>
                        <Typography variant="subtitle2">{t('integrations.card.workspaceTitle')}</Typography>
                        <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body2">
                            {t(`integrations.catalog.${integrationKey}.workspaceBody`)}
                        </Typography>
                    </Paper>
                    <Paper variant="outlined" sx={{ borderRadius: 3, p: 2 }}>
                        <Typography variant="subtitle2">{t('integrations.card.statusTitle')}</Typography>
                        <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body2">
                            {detail}
                        </Typography>
                    </Paper>
                </Box>

                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25}>
                    <Button component={RouterLink} to={definition.key} variant="contained">
                        {t('integrations.card.openWorkspace')}
                    </Button>
                    <Button component="a" href={definition.directPath} target="_blank" rel="noreferrer" variant="text">
                        {t('integrations.card.openDirect')}
                    </Button>
                </Stack>
            </Stack>
        </Paper>
    )
}

export function IntegrationsPage() {
    const { t } = useTranslation('shell')
    const { refresh, snapshots } = useIntegrationStatuses()

    return (
        <Stack spacing={2}>
            <Paper
                elevation={0}
                sx={{
                    borderRadius: 3,
                    border: '1px solid',
                    borderColor: 'divider',
                    p: { xs: 2.5, md: 3 },
                    backgroundColor: 'background.paper',
                }}
            >
                <Stack spacing={1.5}>
                    <Stack
                        direction={{ xs: 'column', md: 'row' }}
                        spacing={1.5}
                        sx={{ alignItems: { xs: 'flex-start', md: 'center' }, justifyContent: 'space-between' }}
                    >
                        <Stack spacing={0.5}>
                            <Typography component="h1" variant="h4">
                                {t('integrations.hero.title')}
                            </Typography>
                            <Typography color="text.secondary" sx={{ maxWidth: 780 }} variant="body2">
                                {t('integrations.hero.description')}
                            </Typography>
                        </Stack>
                        <Button onClick={refresh} variant="outlined">
                            {t('integrations.hero.refresh')}
                        </Button>
                    </Stack>
                </Stack>
            </Paper>

            <Box
                sx={{
                    display: 'grid',
                    gap: 2,
                    gridTemplateColumns: { xs: '1fr', xl: 'repeat(2, minmax(0, 1fr))' },
                }}
            >
                {integrationDefinitions.map((definition) => (
                    <IntegrationCard integrationKey={definition.key} key={definition.key} snapshot={snapshots[definition.key]} />
                ))}
            </Box>
        </Stack>
    )
}