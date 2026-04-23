import { Alert, Box, Button, Chip, Paper, Stack, Typography } from '@mui/material'
import { Navigate, Outlet, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { getIntegrationDefinition, getIntegrationDefinitionByEntrySegment, type IntegrationKey } from './integration-model'
import { useIntegrationSession } from './use-integration-session'
import { useIntegrationStatuses } from './use-integration-status'

type IntegrationWorkspacePageProps = {
    integrationKey?: IntegrationKey
    showCatalogLink?: boolean
}

export function IntegrationWorkspacePage({ integrationKey: fixedIntegrationKey, showCatalogLink = false }: IntegrationWorkspacePageProps) {
    const { integrationKey: routeIntegrationKey, '*': unmatchedPath } = useParams()
    const definition =
        (fixedIntegrationKey ? getIntegrationDefinition(fixedIntegrationKey) : undefined) ??
        getIntegrationDefinition(routeIntegrationKey) ??
        getIntegrationDefinitionByEntrySegment(unmatchedPath)

    if (!definition) {
        return <Navigate replace to="/repository" />
    }

    return <IntegrationWorkspaceContent definition={definition} showCatalogLink={showCatalogLink} />
}

type IntegrationWorkspaceContentProps = {
    definition: NonNullable<ReturnType<typeof getIntegrationDefinition>>
    showCatalogLink: boolean
}

const embeddedShellStyles: Record<IntegrationKey, string> = {
    gitea: `
        body,
        .full.height,
        #page-body {
            background: #ffffff !important;
        }

        .page-footer {
            background: transparent !important;
            border-top: 1px solid rgba(15, 23, 42, 0.06) !important;
            box-shadow: none !important;
            padding: 12px 24px !important;
            color: #64748b !important;
        }

        .page-footer a {
            color: #64748b !important;
        }
    `,
    npm: `
        body,
        .page,
        .page-wrapper,
        .page-body {
            background: #ffffff !important;
        }

        footer,
        .footer,
        .page-footer {
            background: transparent !important;
            border-top: 1px solid rgba(15, 23, 42, 0.06) !important;
            box-shadow: none !important;
            margin-top: 24px !important;
            padding: 12px 24px !important;
            color: #64748b !important;
        }

        footer a,
        .footer a,
        .page-footer a {
            color: #64748b !important;
        }
    `,
    portainer: `
        body,
        #content-wrapper,
        .page-content,
        .page-wrapper {
            background: #ffffff !important;
        }
    `,
}

function applyEmbeddedShellStyle(frame: HTMLIFrameElement, integrationKey: IntegrationKey) {
    const styleText = embeddedShellStyles[integrationKey]
    if (!styleText) {
        return
    }

    try {
        const doc = frame.contentDocument
        if (!doc?.head) {
            return
        }

        const styleId = 'websoft9-embedded-shell-style'
        let style = doc.getElementById(styleId) as HTMLStyleElement | null

        if (!style) {
            style = doc.createElement('style')
            style.id = styleId
            doc.head.appendChild(style)
        }

        style.textContent = styleText
    } catch {
        // Embedded integrations are expected to remain same-origin under product-owned paths.
    }
}

function IntegrationWorkspaceContent({ definition, showCatalogLink }: IntegrationWorkspaceContentProps) {
    const { t } = useTranslation('shell')
    const { refresh, snapshots } = useIntegrationStatuses()
    const directWorkspaceViewportHeight = 'calc(100vh - 76px)'

    const snapshot = snapshots[definition.key]
    const { errorMessage, sessionState } = useIntegrationSession(definition.key, snapshot.status, snapshot.checkedAt)
    const shouldRenderFrame = sessionState === 'ready' && (snapshot.status === 'available' || snapshot.status === 'session-error')
    const detail = snapshot.httpStatus
        ? t(`integrations.states.${snapshot.status}.detailWithCode`, { statusCode: snapshot.httpStatus })
        : t(`integrations.states.${snapshot.status}.detail`)
    const alertSeverity = snapshot.status === 'available' ? 'success' : snapshot.status === 'loading' ? 'info' : 'warning'
    const isDirectWorkspace = definition.key === 'gitea' || definition.key === 'npm' || definition.key === 'portainer'
    const renderDirectWorkspace = isDirectWorkspace && shouldRenderFrame

    if (isDirectWorkspace) {
        return (
            <Box
                sx={{
                    height: directWorkspaceViewportHeight,
                    mx: -3,
                    my: -2.5,
                    backgroundColor: '#fff',
                }}
            >
                {renderDirectWorkspace ? (
                    <Box
                        component="iframe"
                        src={definition.workspacePath}
                        onLoad={(event) => {
                            applyEmbeddedShellStyle(event.currentTarget, definition.key)
                        }}
                        sx={{
                            width: '100%',
                            height: directWorkspaceViewportHeight,
                            border: 0,
                            display: 'block',
                        }}
                        title={t(`integrations.catalog.${definition.key}.title`)}
                    />
                ) : (
                    <Stack
                        spacing={1.25}
                        sx={{
                            height: directWorkspaceViewportHeight,
                            alignItems: 'center',
                            justifyContent: 'center',
                            px: 3,
                            textAlign: 'center',
                        }}
                    >
                        {sessionState === 'error' ? (
                            <>
                                <Chip color="warning" label={t('integrations.workspace.sessionBootstrapFailed')} />
                                <Typography color="text.secondary" variant="body2">
                                    {errorMessage ?? t('integrations.workspace.sessionBootstrapFailedDetail')}
                                </Typography>
                            </>
                        ) : (
                            <>
                                <Chip color="info" label={t('integrations.workspace.bootstrappingSession')} />
                                <Typography color="text.secondary" variant="body2">
                                    {t('integrations.workspace.bootstrappingSessionDetail')}
                                </Typography>
                            </>
                        )}
                    </Stack>
                )}
            </Box>
        )
    }

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
                <Stack spacing={1.75}>
                    <Stack
                        direction={{ xs: 'column', lg: 'row' }}
                        spacing={1.5}
                        sx={{ alignItems: { xs: 'flex-start', lg: 'center' }, justifyContent: 'space-between' }}
                    >
                        <Stack spacing={0.5}>
                            <Typography component="h1" variant="h4">
                                {t(`integrations.catalog.${definition.key}.title`)}
                            </Typography>
                            <Typography color="text.secondary" variant="body2">
                                {t(`integrations.catalog.${definition.key}.workspaceBody`)}
                            </Typography>
                        </Stack>

                        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                            <Chip color={snapshot.status === 'available' ? 'success' : snapshot.status === 'loading' ? 'info' : 'warning'} label={t(`integrations.states.${snapshot.status}.label`)} />
                            {sessionState === 'bootstrapping' ? <Chip color="info" label={t('integrations.workspace.bootstrappingSession')} /> : null}
                            {sessionState === 'error' ? <Chip color="warning" label={t('integrations.workspace.sessionBootstrapFailed')} /> : null}
                        </Stack>
                    </Stack>

                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                        {showCatalogLink ? <Button href="/integrations" variant="text">{t('integrations.workspace.backToCatalog')}</Button> : null}
                        <Button onClick={refresh} variant="outlined">
                            {t('integrations.workspace.retryProbe')}
                        </Button>
                        <Button component="a" href={definition.directPath} target="_blank" rel="noreferrer" variant="outlined">
                            {t('integrations.workspace.openDirect')}
                        </Button>
                    </Stack>

                    <Alert severity={alertSeverity}>
                        <Typography variant="body2">{detail}</Typography>
                    </Alert>
                    {sessionState === 'bootstrapping' ? (
                        <Alert severity="info">
                            <Typography variant="body2">{t('integrations.workspace.bootstrappingSessionDetail')}</Typography>
                        </Alert>
                    ) : null}
                    {sessionState === 'error' ? (
                        <Alert severity="warning">
                            <Typography variant="body2">{errorMessage ?? t('integrations.workspace.sessionBootstrapFailedDetail')}</Typography>
                        </Alert>
                    ) : null}
                </Stack>
            </Paper>

            {shouldRenderFrame ? (
                <Paper
                    elevation={0}
                    sx={{
                        borderRadius: 3,
                        border: '1px solid',
                        borderColor: 'divider',
                        overflow: 'hidden',
                        minHeight: 720,
                        backgroundColor: '#fff',
                    }}
                >
                    <Box
                        sx={{
                            borderBottom: '1px solid',
                            borderColor: 'divider',
                            px: 2,
                            py: 1.25,
                            backgroundColor: '#f8fafc',
                        }}
                    >
                        <Typography color="text.secondary" variant="body2">
                            {t(`integrations.catalog.${definition.key}.title`)}
                        </Typography>
                    </Box>
                    <Box
                        component="iframe"
                        src={definition.workspacePath}
                        onLoad={(event) => {
                            applyEmbeddedShellStyle(event.currentTarget, definition.key)
                        }}
                        sx={{
                            width: '100%',
                            minHeight: 720,
                            border: 0,
                            display: 'block',
                        }}
                        title={t(`integrations.catalog.${definition.key}.title`)}
                    />
                </Paper>
            ) : (
                <Paper
                    elevation={0}
                    sx={{
                        borderRadius: 3,
                        border: '1px solid',
                        borderColor: 'divider',
                        p: { xs: 2.5, md: 3 },
                    }}
                >
                    <Stack spacing={1.25}>
                        <Typography variant="h6">{t('integrations.workspace.recoveryTitle')}</Typography>
                        <Typography color="text.secondary" variant="body2">
                            {t(`integrations.states.${snapshot.status}.recovery`)}
                        </Typography>
                        <Paper variant="outlined" sx={{ borderRadius: 2, p: 2 }}>
                            <Stack spacing={0.75}>
                                <Typography variant="subtitle2">{t('integrations.workspace.diagnosticsTitle')}</Typography>
                                <Typography color="text.secondary" variant="body2">
                                    {t('integrations.workspace.diagnosticsPath', { path: definition.diagnosticsPath })}
                                </Typography>
                                {snapshot.probeUrl ? (
                                    <Typography color="text.secondary" variant="body2">
                                        {t('integrations.workspace.lastResolvedUrl', { url: snapshot.probeUrl })}
                                    </Typography>
                                ) : null}
                            </Stack>
                        </Paper>
                    </Stack>
                </Paper>
            )}

            <Outlet />
        </Stack>
    )
}