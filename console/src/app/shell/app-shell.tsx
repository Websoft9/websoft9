import {
    AppBar,
    Box,
    Button,
    Container,
    List,
    ListItemButton,
    ListItemText,
    Paper,
    Stack,
    Toolbar,
    Typography,
} from '@mui/material'
import { NavLink, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { supportedLocales } from '../../shared/i18n/i18n'
import { shellNavigationItems } from './shell-navigation'

export function AppShell() {
    const { t, i18n } = useTranslation('shell')

    return (
        <Box
            sx={{
                minHeight: '100vh',
                background:
                    'radial-gradient(circle at top left, rgba(23,103,209,0.14), transparent 36%), radial-gradient(circle at top right, rgba(15,140,114,0.12), transparent 28%), linear-gradient(180deg, #f7f9fc 0%, #eef3f8 100%)',
            }}
        >
            <AppBar
                color="transparent"
                elevation={0}
                position="sticky"
                sx={{ backdropFilter: 'blur(14px)', borderBottom: '1px solid', borderColor: 'divider' }}
            >
                <Toolbar sx={{ gap: 2, justifyContent: 'space-between', px: { xs: 2, md: 4 } }}>
                    <Stack spacing={0.25}>
                        <Typography variant="overline">{t('brand.kicker')}</Typography>
                        <Typography variant="h6">{t('brand.title')}</Typography>
                    </Stack>
                    <Stack direction="row" spacing={1}>
                        {supportedLocales.map((locale) => {
                            const selected = i18n.resolvedLanguage === locale

                            return (
                                <Button
                                    key={locale}
                                    color={selected ? 'secondary' : 'inherit'}
                                    onClick={() => {
                                        void i18n.changeLanguage(locale)
                                    }}
                                    size="small"
                                    variant={selected ? 'contained' : 'text'}
                                >
                                    {t(`locales.${locale}`)}
                                </Button>
                            )
                        })}
                    </Stack>
                </Toolbar>
            </AppBar>

            <Container maxWidth="xl" sx={{ py: { xs: 3, md: 4 } }}>
                <Box
                    sx={{
                        display: 'grid',
                        gap: 3,
                        alignItems: 'start',
                        gridTemplateColumns: { xs: '1fr', lg: '280px minmax(0, 1fr)' },
                    }}
                >
                    <Paper
                        elevation={0}
                        sx={{
                            borderRadius: 4,
                            border: '1px solid',
                            borderColor: 'divider',
                            p: 2,
                            position: { lg: 'sticky' },
                            top: { lg: 96 },
                        }}
                    >
                        <Stack spacing={2}>
                            <Box>
                                <Typography variant="subtitle2">{t('navigation.title')}</Typography>
                                <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body2">
                                    {t('navigation.description')}
                                </Typography>
                            </Box>
                            <List disablePadding>
                                {shellNavigationItems.map((item) => (
                                    <ListItemButton
                                        component={NavLink}
                                        key={item.segment}
                                        sx={{
                                            borderRadius: 3,
                                            mb: 0.75,
                                            '&.active': {
                                                backgroundColor: 'primary.main',
                                                color: 'primary.contrastText',
                                            },
                                        }}
                                        to={`/${item.segment}`}
                                    >
                                        <ListItemText
                                            primary={t(`nav.${item.pageKey}.label`)}
                                            secondary={t(`nav.${item.pageKey}.hint`)}
                                            slotProps={{
                                                secondary: {
                                                    sx: {
                                                        color: 'inherit',
                                                        opacity: 0.74,
                                                    },
                                                },
                                            }}
                                        />
                                    </ListItemButton>
                                ))}
                            </List>
                        </Stack>
                    </Paper>

                    <Stack spacing={2.5}>
                        <Paper
                            elevation={0}
                            sx={{
                                borderRadius: 4,
                                border: '1px solid',
                                borderColor: 'divider',
                                p: { xs: 3, md: 4 },
                                overflow: 'hidden',
                                position: 'relative',
                            }}
                        >
                            <Box
                                sx={{
                                    position: 'absolute',
                                    inset: 0,
                                    background:
                                        'linear-gradient(120deg, rgba(23,103,209,0.10) 0%, rgba(15,140,114,0.08) 36%, transparent 72%)',
                                }}
                            />
                            <Stack spacing={1.5} sx={{ position: 'relative' }}>
                                <Typography variant="overline">{t('hero.kicker')}</Typography>
                                <Typography variant="h3">{t('hero.title')}</Typography>
                                <Typography color="text.secondary" sx={{ maxWidth: 720 }} variant="body1">
                                    {t('hero.description')}
                                </Typography>
                            </Stack>
                        </Paper>
                        <Outlet />
                    </Stack>
                </Box>
            </Container>
        </Box>
    )
}