import { Alert, Box, Button, Chip, Paper, Stack, Typography } from '@mui/material'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Navigate, Outlet, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { getIntegrationDefinition, getIntegrationDefinitionByEntrySegment, integrationDefinitions, type IntegrationKey } from './integration-model'
import { useIntegrationSession } from './use-integration-session'
import { useIntegrationStatuses } from './use-integration-status'

type IntegrationWorkspacePageProps = {
    integrationKey?: IntegrationKey
    showCatalogLink?: boolean
    shellPersistent?: boolean
}

export function IntegrationWorkspacePage({ integrationKey: fixedIntegrationKey, showCatalogLink = false, shellPersistent = false }: IntegrationWorkspacePageProps) {
    const { integrationKey: routeIntegrationKey, '*': unmatchedPath } = useParams()
    const definition =
        (fixedIntegrationKey ? getIntegrationDefinition(fixedIntegrationKey) : undefined) ??
        getIntegrationDefinition(routeIntegrationKey) ??
        getIntegrationDefinitionByEntrySegment(unmatchedPath)

    if (!definition) {
        return <Navigate replace to="/repository" />
    }

    if (shellPersistent && (definition.key === 'gitea' || definition.key === 'npm' || definition.key === 'portainer')) {
        return null
    }

    return <IntegrationWorkspaceContent definition={definition} showCatalogLink={showCatalogLink} />
}

export function PersistentIntegrationWorkspaces() {
    const location = useLocation()
    const { refresh, snapshots } = useIntegrationStatuses()
    const activeDefinition = useMemo(() => {
        return integrationDefinitions.find((definition) => location.pathname === `/${definition.entrySegment}`) ?? null
    }, [location.pathname])

    return (
        <Box
            sx={{
                position: 'absolute',
                inset: 0,
                display: activeDefinition ? 'block' : 'none',
                backgroundColor: '#fff',
                zIndex: 1,
            }}
        >
            {integrationDefinitions.map((definition) => (
                <Box
                    key={definition.key}
                    sx={{
                        position: 'absolute',
                        inset: 0,
                        visibility: definition.key === activeDefinition?.key ? 'visible' : 'hidden',
                        pointerEvents: definition.key === activeDefinition?.key ? 'auto' : 'none',
                    }}
                >
                    <DirectIntegrationWorkspaceFrame
                        active={definition.key === activeDefinition?.key}
                        definition={definition}
                        refresh={refresh}
                        snapshot={snapshots[definition.key]}
                    />
                </Box>
            ))}
        </Box>
    )
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

function getIntegrationWorkspaceStorageKey(integrationKey: IntegrationKey) {
    return `websoft9:integration-workspace:${integrationKey}:last-src`
}

function resolveWorkspaceTarget(definition: IntegrationWorkspaceContentProps['definition'], requestedTarget: string | null, rememberedWorkspaceSrc: string | null) {
    if (requestedTarget && (requestedTarget.startsWith(definition.probePath) || requestedTarget.startsWith(definition.directPath))) {
        return requestedTarget
    }

    if (rememberedWorkspaceSrc && (rememberedWorkspaceSrc.startsWith(definition.probePath) || rememberedWorkspaceSrc.startsWith(definition.directPath))) {
        return rememberedWorkspaceSrc
    }

    return definition.workspacePath
}

function rememberIntegrationTarget(definition: IntegrationWorkspaceContentProps['definition'], target: string | null) {
    if (typeof window === 'undefined' || !target) {
        return
    }

    if (target.startsWith(definition.probePath) || target.startsWith(definition.directPath)) {
        window.sessionStorage.setItem(getIntegrationWorkspaceStorageKey(definition.key), target)
    }
}

function handleIntegrationFrameLoad(frame: HTMLIFrameElement, definition: IntegrationWorkspaceContentProps['definition']) {
    applyEmbeddedShellStyle(frame, definition.key)
    try {
        const currentLocation = frame.contentWindow?.location
        const nextPath = currentLocation ? `${currentLocation.pathname}${currentLocation.search}${currentLocation.hash}` : null
        rememberIntegrationTarget(definition, nextPath)
    } catch {
        // Embedded integrations stay same-origin under product-owned paths, but keep a silent fallback.
    }
}

function inspectIntegrationFrame(frame: HTMLIFrameElement, definition: IntegrationWorkspaceContentProps['definition']) {
    try {
        const currentLocation = frame.contentWindow?.location
        const doc = frame.contentDocument
        const pathname = currentLocation?.pathname ?? ''
        const search = currentLocation?.search ?? ''
        const hash = currentLocation?.hash ?? ''
        const resolvedTarget = `${pathname}${search}${hash}`
        const title = doc?.title ?? ''
        const html = doc?.documentElement?.innerHTML ?? ''

        const authPathMatched = definition.authPaths.some((authPath) => resolvedTarget.includes(authPath))
        const authMarkerMatched = definition.authMarkers.some((marker) =>
            title.includes(marker) || html.includes(marker),
        )

        return {
            authSurfaceDetected: authPathMatched || authMarkerMatched,
            resolvedTarget,
        }
    } catch {
        return {
            authSurfaceDetected: false,
            resolvedTarget: null,
        }
    }
}

async function bootstrapIntegrationSession(integrationKey: IntegrationKey, locale: string) {
    const response = await fetch(`/api/integrations/${integrationKey}/session`, {
        method: 'POST',
        credentials: 'include',
        headers: {
            'X-Websoft9-Locale': locale,
        },
    })

    if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { details?: string; message?: string } | null
        throw new Error(payload?.details ?? payload?.message ?? `HTTP ${response.status}`)
    }
}

function DirectIntegrationWorkspaceFrame({
    active,
    definition,
    refresh,
    snapshot,
}: {
    active: boolean
    definition: IntegrationWorkspaceContentProps['definition']
    refresh: () => void
    snapshot: ReturnType<typeof useIntegrationStatuses>['snapshots'][IntegrationKey]
}) {
    const { t, i18n } = useTranslation('shell')
    const [searchParams] = useSearchParams()
    const [hasInitializedFrame, setHasInitializedFrame] = useState(false)
    const [frameVersion, setFrameVersion] = useState(0)
    const [recoveryState, setRecoveryState] = useState<'idle' | 'recovering' | 'error'>('idle')
    const [recoveryError, setRecoveryError] = useState<string | null>(null)
    const [lastRecoveryTarget, setLastRecoveryTarget] = useState<string | null>(null)
    const inspectionTimeoutRef = useRef<number | null>(null)
    const { errorMessage, sessionState } = useIntegrationSession(definition.key, snapshot.status, snapshot.checkedAt, active || hasInitializedFrame)
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const shouldRenderFrame =
        (active || hasInitializedFrame) &&
        sessionState === 'ready' &&
        recoveryState !== 'recovering' &&
        recoveryState !== 'error' &&
        (snapshot.status === 'available' || snapshot.status === 'session-error')
    const requestedTarget = active ? searchParams.get('target') : null
    const rememberedWorkspaceSrc = useMemo(() => {
        if (typeof window === 'undefined') {
            return null
        }

        return window.sessionStorage.getItem(getIntegrationWorkspaceStorageKey(definition.key))
    }, [definition.key])
    const iframeSrc = resolveWorkspaceTarget(definition, requestedTarget, rememberedWorkspaceSrc)

    useEffect(() => {
        rememberIntegrationTarget(definition, requestedTarget)
    }, [definition, requestedTarget])

    useEffect(() => {
        if (active && sessionState === 'ready') {
            setHasInitializedFrame(true)
        }
    }, [active, sessionState])

    useEffect(() => {
        if (sessionState !== 'ready') {
            setRecoveryState('idle')
            setRecoveryError(null)
        }
    }, [sessionState])

    useEffect(() => {
        return () => {
            if (inspectionTimeoutRef.current !== null) {
                window.clearTimeout(inspectionTimeoutRef.current)
            }
        }
    }, [])

    async function recoverIntegrationSession(target: string | null, options?: { force?: boolean }) {
        const recoveryTarget = target || iframeSrc
        if (recoveryState === 'recovering') {
            return
        }

        if (!options?.force && lastRecoveryTarget === recoveryTarget) {
            setRecoveryState('error')
            setRecoveryError(t('integrations.workspace.sessionRefreshFailedDetail'))
            return
        }

        setRecoveryState('recovering')
        setRecoveryError(null)
        setLastRecoveryTarget(recoveryTarget)

        try {
            await bootstrapIntegrationSession(definition.key, locale)
            setRecoveryState('idle')
            setRecoveryError(null)
            setFrameVersion((current) => current + 1)
        } catch (error) {
            setRecoveryState('error')
            setRecoveryError(error instanceof Error ? error.message : t('integrations.workspace.sessionRefreshFailedDetail'))
        }
    }

    if (!active && !hasInitializedFrame) {
        return null
    }

    return shouldRenderFrame ? (
        <Box
            component="iframe"
            key={`${definition.key}:${frameVersion}`}
            src={iframeSrc}
            onLoad={(event) => {
                if (inspectionTimeoutRef.current !== null) {
                    window.clearTimeout(inspectionTimeoutRef.current)
                    inspectionTimeoutRef.current = null
                }

                handleIntegrationFrameLoad(event.currentTarget, definition)

                const inspectFrame = () => {
                    const inspection = inspectIntegrationFrame(event.currentTarget, definition)
                    if (!inspection.authSurfaceDetected) {
                        setRecoveryState('idle')
                        setRecoveryError(null)
                        setLastRecoveryTarget(null)
                        return
                    }

                    void recoverIntegrationSession(inspection.resolvedTarget)
                }

                const inspectionDelayMs = definition.key === 'portainer' ? 2000 : 0
                if (inspectionDelayMs > 0) {
                    inspectionTimeoutRef.current = window.setTimeout(() => {
                        inspectionTimeoutRef.current = null
                        inspectFrame()
                    }, inspectionDelayMs)
                    return
                }

                inspectFrame()
            }}
            sx={{
                width: '100%',
                height: 'calc(100vh - 76px)',
                border: 0,
                display: 'block',
                backgroundColor: '#fff',
            }}
            title={t(`integrations.catalog.${definition.key}.title`)}
        />
    ) : (
        <Stack
            spacing={1.25}
            sx={{
                height: 'calc(100vh - 76px)',
                alignItems: 'center',
                justifyContent: 'center',
                px: 3,
                textAlign: 'center',
            }}
        >
            {recoveryState === 'recovering' ? (
                <>
                    <Chip color="info" label={t('integrations.workspace.refreshingSession')} />
                    <Typography color="text.secondary" variant="body2">
                        {t('integrations.workspace.refreshingSessionDetail')}
                    </Typography>
                </>
            ) : recoveryState === 'error' ? (
                <>
                    <Chip color="warning" label={t('integrations.workspace.sessionRefreshFailed')} />
                    <Typography color="text.secondary" variant="body2">
                        {recoveryError ?? t('integrations.workspace.sessionRefreshFailedDetail')}
                    </Typography>
                    <Button onClick={() => void recoverIntegrationSession(null, { force: true })} variant="outlined">
                        {t('integrations.workspace.retryProbe')}
                    </Button>
                </>
            ) : sessionState === 'error' ? (
                <>
                    <Chip color="warning" label={t('integrations.workspace.sessionBootstrapFailed')} />
                    <Typography color="text.secondary" variant="body2">
                        {errorMessage ?? t('integrations.workspace.sessionBootstrapFailedDetail')}
                    </Typography>
                    <Button onClick={refresh} variant="outlined">
                        {t('integrations.workspace.retryProbe')}
                    </Button>
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
    )
}

function IntegrationWorkspaceContent({ definition, showCatalogLink }: IntegrationWorkspaceContentProps) {
    const { t } = useTranslation('shell')
    const [searchParams] = useSearchParams()
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
    const requestedTarget = searchParams.get('target')
    const rememberedWorkspaceSrc = useMemo(() => {
        if (typeof window === 'undefined') {
            return null
        }

        return window.sessionStorage.getItem(getIntegrationWorkspaceStorageKey(definition.key))
    }, [definition.key])
    const iframeSrc = resolveWorkspaceTarget(definition, requestedTarget, rememberedWorkspaceSrc)

    useEffect(() => {
        rememberIntegrationTarget(definition, requestedTarget)
    }, [definition, requestedTarget])

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
                        src={iframeSrc}
                        onLoad={(event) => {
                            handleIntegrationFrameLoad(event.currentTarget, definition)
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
                        src={iframeSrc}
                        onLoad={(event) => {
                            applyEmbeddedShellStyle(event.currentTarget, definition.key)
                            try {
                                const currentLocation = event.currentTarget.contentWindow?.location
                                const nextPath = currentLocation ? `${currentLocation.pathname}${currentLocation.search}${currentLocation.hash}` : null
                                if (nextPath && (nextPath.startsWith(definition.probePath) || nextPath.startsWith(definition.directPath))) {
                                    window.sessionStorage.setItem(getIntegrationWorkspaceStorageKey(definition.key), nextPath)
                                }
                            } catch {
                                // Embedded integrations stay same-origin under product-owned paths, but keep a silent fallback.
                            }
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