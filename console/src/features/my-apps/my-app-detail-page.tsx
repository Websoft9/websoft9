import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControlLabel,
    Link,
    Snackbar,
    Stack,
    Switch,
    Tab,
    Tabs,
    Typography,
} from '@mui/material'
import { useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useMyAppDetail } from './use-my-app-detail'
import { MyAppAccessPanel } from './my-app-access-panel'

type DetailTabKey = 'overview' | 'access' | 'runtime' | 'storage' | 'backup' | 'uninstall'
type LifecycleActionKey = 'access' | 'start' | 'stop' | 'restart' | 'redeploy' | 'uninstall'
type ActionFeedback = {
    severity: 'success' | 'error' | 'info'
    message: string
}
type HeaderActionLink = {
    key: 'access'
    label: string
    href: string
    disabled: boolean
    loading: boolean
}
type HeaderActionButton = {
    key: Exclude<LifecycleActionKey, 'access'>
    label: string
    disabled: boolean
    loading: boolean
    onClick: () => void
}
type HeaderActionItem = HeaderActionLink | HeaderActionButton
type RedeployLogEntry = {
    timestamp?: string
    type?: string
    status?: string
    message?: string
    details?: string
    data?: unknown
}

const detailTabs: DetailTabKey[] = ['overview', 'access', 'runtime', 'storage', 'backup', 'uninstall']

function getStatusKey(status: number) {
    if (status === 3) {
        return 'installing'
    }

    if (status === 2) {
        return 'inactive'
    }

    if (status === 4) {
        return 'error'
    }

    return 'active'
}

function getStatusColor(status: number): 'default' | 'success' | 'warning' | 'error' {
    if (status === 1) {
        return 'success'
    }

    if (status === 3) {
        return 'warning'
    }

    if (status === 4) {
        return 'error'
    }

    return 'default'
}

function getDomainEntries(domainNames: Array<Record<string, unknown>> | undefined, env: Record<string, string> | undefined) {
    const domains = (domainNames ?? [])
        .map((entry) => {
            const domainName = entry.domain_name
            const domain = entry.domain

            if (typeof domainName === 'string' && domainName.trim()) {
                return domainName.trim()
            }

            if (typeof domain === 'string' && domain.trim()) {
                return domain.trim()
            }

            return null
        })
        .filter((value): value is string => Boolean(value))

    const envUrl = env?.W9_URL?.trim()
    if (envUrl && !domains.includes(envUrl)) {
        domains.unshift(envUrl)
    }

    return domains
}

function formatCreationDate(value: number | null | undefined, locale: string) {
    if (!value) {
        return '-'
    }

    const normalizedValue = value > 10_000_000_000 ? value : value * 1_000

    try {
        return new Intl.DateTimeFormat(locale, {
            dateStyle: 'medium',
            timeStyle: 'short',
        }).format(new Date(normalizedValue))
    } catch {
        return '-'
    }
}

function getRuntimeSummary(containers: Array<Record<string, unknown>> | undefined, volumes: Array<Record<string, unknown>> | undefined) {
    return {
        containers: containers?.length ?? 0,
        volumes: volumes?.length ?? 0,
    }
}

async function parseJsonError(response: Response, fallbackMessage: string) {
    try {
        const payload = (await response.json()) as { details?: string; message?: string }
        return payload.details || payload.message || fallbackMessage
    } catch {
        return fallbackMessage
    }
}

async function runLifecycleRequest(url: string, method: 'POST' | 'DELETE') {
    const response = await fetch(url, {
        method,
        credentials: 'include',
        headers: {
            Accept: 'application/json',
        },
    })

    if (!response.ok) {
        throw new Error(await parseJsonError(response, `Lifecycle action failed: ${response.status}`))
    }
}

async function runRedeployRequest(
    appId: string,
    pullImage: boolean,
    onLog: (entry: RedeployLogEntry) => void,
) {
    const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/redeploy?pullImage=${String(pullImage)}`, {
        method: 'PUT',
        credentials: 'include',
        headers: {
            Accept: 'text/plain',
        },
    })

    if (!response.ok || !response.body) {
        throw new Error(await parseJsonError(response, `Redeploy failed: ${response.status}`))
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalStatus: 'success' | 'failed' | null = null

    while (true) {
        const { done, value } = await reader.read()
        buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })

        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
            if (!line.trim()) {
                continue
            }

            const parsedEntry = JSON.parse(line) as RedeployLogEntry
            onLog(parsedEntry)

            if (parsedEntry.status === 'success') {
                finalStatus = 'success'
            }

            if (parsedEntry.status === 'failed' || parsedEntry.type === 'error') {
                finalStatus = 'failed'
            }
        }

        if (done) {
            break
        }
    }

    if (buffer.trim()) {
        const parsedEntry = JSON.parse(buffer) as RedeployLogEntry
        onLog(parsedEntry)
        if (parsedEntry.status === 'success') {
            finalStatus = 'success'
        }
        if (parsedEntry.status === 'failed' || parsedEntry.type === 'error') {
            finalStatus = 'failed'
        }
    }

    if (finalStatus !== 'success') {
        throw new Error('Redeploy did not complete successfully.')
    }
}

function isHeaderActionItem(value: HeaderActionItem | null): value is HeaderActionItem {
    return value !== null
}

function getAccessHref(value: string) {
    if (/^https?:\/\//i.test(value)) {
        return value
    }

    if (/^\d{1,3}(\.\d{1,3}){3}(:\d+)?$/.test(value) || value.includes(':')) {
        return `http://${value}`
    }

    return `https://${value}`
}

export function MyAppDetailPage() {
    const { t, i18n } = useTranslation('shell')
    const { appId } = useParams()
    const navigate = useNavigate()
    const queryClient = useQueryClient()
    const [selectedTab, setSelectedTab] = useState<DetailTabKey>('overview')
    const [actionInProgress, setActionInProgress] = useState<LifecycleActionKey | null>(null)
    const [feedback, setFeedback] = useState<ActionFeedback | null>(null)
    const [redeployDialogOpen, setRedeployDialogOpen] = useState(false)
    const [redeployPullImage, setRedeployPullImage] = useState(false)
    const [redeployLogs, setRedeployLogs] = useState<RedeployLogEntry[]>([])
    const [uninstallDialogOpen, setUninstallDialogOpen] = useState(false)
    const [purgeData, setPurgeData] = useState(false)
    const { data, error, isLoading, refetch, isFetching } = useMyAppDetail(appId)
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'

    const domains = useMemo(() => getDomainEntries(data?.domain_names, data?.env), [data?.domain_names, data?.env])
    const runtimeSummary = useMemo(() => getRuntimeSummary(data?.containers, data?.volumes), [data?.containers, data?.volumes])

    async function refreshAfterAction() {
        await Promise.all([
            queryClient.invalidateQueries({ queryKey: ['my-apps'] }),
            queryClient.invalidateQueries({ queryKey: ['my-app-detail', appId] }),
        ])

        setTimeout(() => {
            void queryClient.invalidateQueries({ queryKey: ['my-apps'] })
            void queryClient.invalidateQueries({ queryKey: ['my-app-detail', appId] })
        }, 1500)
    }

    async function handleSimpleAction(actionKey: Extract<LifecycleActionKey, 'start' | 'stop' | 'restart'>) {
        if (!data) {
            return
        }

        const actionMap = {
            start: {
                method: 'POST' as const,
                url: `/api/apps/${encodeURIComponent(data.app_id)}/start`,
                successMessage: t('myAppsDetailPage.feedback.startSuccess', { appId: data.app_id }),
            },
            stop: {
                method: 'POST' as const,
                url: `/api/apps/${encodeURIComponent(data.app_id)}/stop`,
                successMessage: t('myAppsDetailPage.feedback.stopSuccess', { appId: data.app_id }),
            },
            restart: {
                method: 'POST' as const,
                url: `/api/apps/${encodeURIComponent(data.app_id)}/restart`,
                successMessage: t('myAppsDetailPage.feedback.restartSuccess', { appId: data.app_id }),
            },
        }

        const actionConfig = actionMap[actionKey]
        setActionInProgress(actionKey)

        try {
            await runLifecycleRequest(actionConfig.url, actionConfig.method)
            await refreshAfterAction()
            setFeedback({ severity: 'success', message: actionConfig.successMessage })
        } catch (actionError) {
            setFeedback({
                severity: 'error',
                message: actionError instanceof Error ? actionError.message : t('myAppsDetailPage.feedback.genericError'),
            })
        } finally {
            setActionInProgress(null)
        }
    }

    async function handleRedeploy() {
        if (!data) {
            return
        }

        setActionInProgress('redeploy')
        setRedeployLogs([])

        try {
            await runRedeployRequest(data.app_id, redeployPullImage, (entry) => {
                setRedeployLogs((currentValue) => [...currentValue, entry])
            })
            await refreshAfterAction()
            setFeedback({ severity: 'success', message: t('myAppsDetailPage.feedback.redeploySuccess', { appId: data.app_id }) })
        } catch (actionError) {
            setFeedback({
                severity: 'error',
                message: actionError instanceof Error ? actionError.message : t('myAppsDetailPage.feedback.genericError'),
            })
        } finally {
            setActionInProgress(null)
        }
    }

    async function handleUninstall() {
        if (!data) {
            return
        }

        setActionInProgress('uninstall')

        try {
            await runLifecycleRequest(`/api/apps/${encodeURIComponent(data.app_id)}/uninstall?purge_data=${String(purgeData)}`, 'DELETE')
            await queryClient.invalidateQueries({ queryKey: ['my-apps'] })
            setFeedback({ severity: 'success', message: t('myAppsDetailPage.feedback.uninstallSuccess', { appId: data.app_id }) })
            navigate('/myapps')
        } catch (actionError) {
            setFeedback({
                severity: 'error',
                message: actionError instanceof Error ? actionError.message : t('myAppsDetailPage.feedback.genericError'),
            })
        } finally {
            setActionInProgress(null)
            setUninstallDialogOpen(false)
        }
    }

    const rawActionItems: Array<HeaderActionItem | null> = data
        ? [
              domains.length > 0
                  ? {
                        key: 'access' as const,
                        label: t('myAppsDetailPage.actions.access'),
                        href: getAccessHref(domains[0]),
                        disabled: false,
                        loading: false,
                    }
                  : null,
              {
                  key: 'start' as const,
                  label: t('myAppsDetailPage.actions.start'),
                  disabled: data.status === 1 || actionInProgress !== null,
                  loading: actionInProgress === 'start',
                  onClick: () => void handleSimpleAction('start'),
              },
              {
                  key: 'stop' as const,
                  label: t('myAppsDetailPage.actions.stop'),
                  disabled: data.status !== 1 || actionInProgress !== null,
                  loading: actionInProgress === 'stop',
                  onClick: () => void handleSimpleAction('stop'),
              },
              {
                  key: 'restart' as const,
                  label: t('myAppsDetailPage.actions.restart'),
                  disabled: data.status !== 1 || actionInProgress !== null,
                  loading: actionInProgress === 'restart',
                  onClick: () => void handleSimpleAction('restart'),
              },
              {
                  key: 'redeploy' as const,
                  label: t('myAppsDetailPage.actions.redeploy'),
                  disabled: data.status === 3 || actionInProgress !== null,
                  loading: actionInProgress === 'redeploy',
                  onClick: () => {
                      setRedeployLogs([])
                      setRedeployDialogOpen(true)
                  },
              },
              {
                  key: 'uninstall' as const,
                  label: t('myAppsDetailPage.actions.uninstall'),
                  disabled: actionInProgress !== null,
                  loading: actionInProgress === 'uninstall',
                  onClick: () => {
                      setUninstallDialogOpen(true)
                  },
              },
                    ]
        : []

        const actionItems = rawActionItems.filter(isHeaderActionItem)

    return (
        <Box
            sx={{
                minHeight: 'calc(100vh - 120px)',
                px: { xs: 0.5, md: 1 },
                py: { xs: 1, md: 1.5 },
            }}
        >
            <Stack spacing={2.5}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} sx={{ justifyContent: 'space-between', alignItems: { md: 'center' } }}>
                    <Box>
                        <Button component={RouterLink} to="/myapps" size="small" sx={{ px: 0, mb: 1, textTransform: 'none' }}>
                            {t('myAppsDetailPage.back')}
                        </Button>
                        <Typography color="text.secondary" sx={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.6 }}>
                            {t('myAppsDetailPage.hero.eyebrow')}
                        </Typography>
                        <Typography component="h1" sx={{ fontSize: { xs: 28, md: 32 }, fontWeight: 500, lineHeight: 1.1 }}>
                            {data?.app_name || data?.app_id || appId}
                        </Typography>
                        <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body1">
                            {t('myAppsDetailPage.hero.description')}
                        </Typography>
                    </Box>
                    <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap', justifyContent: { md: 'flex-end' } }}>
                        {data ? <Chip color={getStatusColor(data.status)} label={t(`myAppsPage.status.${getStatusKey(data.status)}`)} size="small" /> : null}
                        {actionItems.map((actionItem) => {
                            if ('href' in actionItem) {
                                return (
                                    <Button
                                        component={Link}
                                        href={actionItem.href}
                                        key={actionItem.key}
                                        rel="noreferrer"
                                        size="small"
                                        target="_blank"
                                        underline="none"
                                        variant="contained"
                                    >
                                        {actionItem.label}
                                    </Button>
                                )
                            }

                            return (
                                <Button
                                    color={actionItem.key === 'uninstall' ? 'error' : 'primary'}
                                    disabled={actionItem.disabled}
                                    key={actionItem.key}
                                    onClick={actionItem.onClick}
                                    size="small"
                                    variant={actionItem.key === 'uninstall' ? 'outlined' : 'contained'}
                                >
                                    {actionItem.loading ? t('myAppsDetailPage.actions.running') : actionItem.label}
                                </Button>
                            )
                        })}
                        <Button onClick={() => void refetch()} variant="outlined">
                            {t('myAppsDetailPage.hero.refresh')}
                        </Button>
                    </Stack>
                </Stack>

                {isLoading ? (
                    <Card elevation={0} sx={{ border: '1px solid rgba(15, 23, 42, 0.08)' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1.5, py: 5 }}>
                                <CircularProgress size={28} />
                                <Typography color="text.secondary" variant="body2">
                                    {t('myAppsDetailPage.states.loading')}
                                </Typography>
                            </Box>
                        </CardContent>
                    </Card>
                ) : null}

                {!isLoading && error ? (
                    <Alert
                        action={
                            <Button color="inherit" size="small" onClick={() => void refetch()}>
                                {t('myAppsDetailPage.states.retry')}
                            </Button>
                        }
                        severity="warning"
                        variant="outlined"
                    >
                        <Typography sx={{ fontWeight: 600 }}>{t('myAppsDetailPage.states.errorTitle')}</Typography>
                        <Typography variant="body2">{t('myAppsDetailPage.states.errorDetail', { statusCode: error.statusCode ?? 'unknown' })}</Typography>
                    </Alert>
                ) : null}

                {!isLoading && !error && data ? (
                    <>
                        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', xl: 'repeat(3, minmax(0, 1fr))' } }}>
                            <Card elevation={0} sx={{ border: '1px solid rgba(15, 23, 42, 0.08)' }}>
                                <CardContent>
                                    <Typography color="text.secondary" variant="body2">
                                        {t('myAppsDetailPage.summary.identityTitle')}
                                    </Typography>
                                    <Typography sx={{ mt: 1, fontWeight: 600 }}>{data.app_id}</Typography>
                                    <Typography color="text.secondary" sx={{ mt: 1 }} variant="body2">
                                        {t('myAppsDetailPage.summary.identityBody', {
                                            version: data.app_version || '-',
                                            edition: data.app_dist || '-',
                                            createdAt: formatCreationDate(data.creationDate, locale),
                                        })}
                                    </Typography>
                                </CardContent>
                            </Card>
                            <Card elevation={0} sx={{ border: '1px solid rgba(15, 23, 42, 0.08)' }}>
                                <CardContent>
                                    <Typography color="text.secondary" variant="body2">
                                        {t('myAppsDetailPage.summary.accessTitle')}
                                    </Typography>
                                    <Stack spacing={0.75} sx={{ mt: 1 }}>
                                        {domains.length > 0 ? (
                                            domains.map((domain) => (
                                                <Link href={getAccessHref(domain)} key={domain} rel="noreferrer" target="_blank" underline="hover">
                                                    {domain}
                                                </Link>
                                            ))
                                        ) : (
                                            <Typography color="text.secondary" variant="body2">
                                                {t('myAppsDetailPage.summary.noAccess')}
                                            </Typography>
                                        )}
                                    </Stack>
                                </CardContent>
                            </Card>
                            <Card elevation={0} sx={{ border: '1px solid rgba(15, 23, 42, 0.08)' }}>
                                <CardContent>
                                    <Typography color="text.secondary" variant="body2">
                                        {t('myAppsDetailPage.summary.runtimeTitle')}
                                    </Typography>
                                    <Typography sx={{ mt: 1, fontWeight: 600 }}>
                                        {t('myAppsDetailPage.summary.runtimeBody', runtimeSummary)}
                                    </Typography>
                                    {isFetching ? (
                                        <Typography color="text.secondary" sx={{ mt: 1 }} variant="body2">
                                            {t('myAppsDetailPage.summary.refreshing')}
                                        </Typography>
                                    ) : null}
                                </CardContent>
                            </Card>
                        </Box>

                        {data.error ? <Alert severity="error" variant="outlined">{data.error}</Alert> : null}

                        <Card elevation={0} sx={{ border: '1px solid rgba(15, 23, 42, 0.08)' }}>
                            <CardContent sx={{ p: 0 }}>
                                <Tabs
                                    value={selectedTab}
                                    onChange={(_, value: DetailTabKey) => {
                                        setSelectedTab(value)
                                    }}
                                    variant="scrollable"
                                    sx={{ borderBottom: '1px solid rgba(15, 23, 42, 0.08)', px: 2 }}
                                >
                                    {detailTabs.map((tabKey) => (
                                        <Tab key={tabKey} label={t(`myAppsDetailPage.tabs.${tabKey}.label`)} value={tabKey} />
                                    ))}
                                </Tabs>

                                <Box sx={{ p: 2.5 }}>
                                    <Typography sx={{ fontSize: 18, fontWeight: 600 }}>{t(`myAppsDetailPage.tabs.${selectedTab}.title`)}</Typography>
                                    <Typography color="text.secondary" sx={{ mt: 1 }} variant="body2">
                                        {t(`myAppsDetailPage.tabs.${selectedTab}.description`)}
                                    </Typography>

                                    {selectedTab === 'overview' ? (
                                        <Stack spacing={1.25} sx={{ mt: 2 }}>
                                            <Typography variant="body2">{t('myAppsDetailPage.tabs.overview.items.status', { status: t(`myAppsPage.status.${getStatusKey(data.status)}`) })}</Typography>
                                            <Typography variant="body2">{t('myAppsDetailPage.tabs.overview.items.proxy', { enabled: data.proxy_enabled ? t('myAppsDetailPage.common.enabled') : t('myAppsDetailPage.common.disabled') })}</Typography>
                                            <Typography variant="body2">{t('myAppsDetailPage.tabs.overview.items.endpoint', { endpointId: data.endpointId ?? '-' })}</Typography>
                                        </Stack>
                                    ) : null}

                                    {selectedTab === 'access' ? <MyAppAccessPanel appId={data.app_id} entryDomains={domains} isWebApp={Boolean(data.env?.W9_URL)} onUpdated={refreshAfterAction} /> : null}

                                    {selectedTab === 'runtime' ? (
                                        <Stack spacing={1.25} sx={{ mt: 2 }}>
                                            <Typography variant="body2">{t('myAppsDetailPage.tabs.runtime.items.containers', { count: runtimeSummary.containers })}</Typography>
                                            <Typography variant="body2">{t('myAppsDetailPage.tabs.runtime.items.volumes', { count: runtimeSummary.volumes })}</Typography>
                                            <Typography variant="body2">{t('myAppsDetailPage.tabs.runtime.items.stack', { branch: String(data.gitConfig?.ConfigVersion ?? '-') })}</Typography>
                                        </Stack>
                                    ) : null}

                                    {selectedTab === 'storage' ? (
                                        <Stack spacing={1.25} sx={{ mt: 2 }}>
                                            {(data.volumes ?? []).length > 0 ? (
                                                (data.volumes ?? []).map((volume, index) => (
                                                    <Typography key={`${String(volume.Name ?? volume.name ?? 'volume')}-${index}`} variant="body2">
                                                        {String(volume.Name ?? volume.name ?? volume.Mountpoint ?? '-')}
                                                    </Typography>
                                                ))
                                            ) : (
                                                <Typography color="text.secondary" variant="body2">
                                                    {t('myAppsDetailPage.tabs.storage.empty')}
                                                </Typography>
                                            )}
                                        </Stack>
                                    ) : null}

                                    {selectedTab === 'backup' ? (
                                        <Box sx={{ mt: 2 }}>
                                            <Alert severity="info" variant="outlined">
                                                {t('myAppsDetailPage.tabs.backup.placeholder')}
                                            </Alert>
                                        </Box>
                                    ) : null}

                                    {selectedTab === 'uninstall' ? (
                                        <Box sx={{ mt: 2 }}>
                                            <Alert severity="warning" variant="outlined">
                                                {t('myAppsDetailPage.tabs.uninstall.placeholder')}
                                            </Alert>
                                        </Box>
                                    ) : null}
                                </Box>
                            </CardContent>
                        </Card>
                    </>
                ) : null}
            </Stack>

            <Dialog fullWidth maxWidth="md" open={redeployDialogOpen} onClose={() => setRedeployDialogOpen(false)}>
                <DialogTitle>{t('myAppsDetailPage.dialogs.redeployTitle')}</DialogTitle>
                <DialogContent dividers>
                    <Stack spacing={2}>
                        <Typography color="text.secondary" variant="body2">
                            {t('myAppsDetailPage.dialogs.redeployBody')}
                        </Typography>
                        <FormControlLabel
                            control={<Switch checked={redeployPullImage} onChange={(event) => setRedeployPullImage(event.target.checked)} />}
                            label={t('myAppsDetailPage.dialogs.redeployPullImage')}
                        />
                        {redeployLogs.length > 0 ? (
                            <Box sx={{ maxHeight: 260, overflowY: 'auto', bgcolor: '#0f172a', color: '#e2e8f0', p: 1.5 }}>
                                <Stack spacing={1}>
                                    {redeployLogs.map((entry, index) => (
                                        <Typography key={`${entry.timestamp ?? 'entry'}-${index}`} sx={{ fontFamily: 'monospace', fontSize: 12, whiteSpace: 'pre-wrap' }}>
                                            {entry.timestamp ? `[${entry.timestamp}] ` : ''}
                                            {entry.message ?? (typeof entry.data === 'string' ? entry.data : JSON.stringify(entry.data ?? entry.status ?? '', null, 2))}
                                        </Typography>
                                    ))}
                                </Stack>
                            </Box>
                        ) : null}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setRedeployDialogOpen(false)}>{t('myAppsDetailPage.dialogs.cancel')}</Button>
                    <Button disabled={actionInProgress !== null} onClick={() => void handleRedeploy()} variant="contained">
                        {actionInProgress === 'redeploy' ? t('myAppsDetailPage.actions.running') : t('myAppsDetailPage.actions.redeploy')}
                    </Button>
                </DialogActions>
            </Dialog>

            <Dialog fullWidth maxWidth="sm" open={uninstallDialogOpen} onClose={() => setUninstallDialogOpen(false)}>
                <DialogTitle>{t('myAppsDetailPage.dialogs.uninstallTitle')}</DialogTitle>
                <DialogContent dividers>
                    <Stack spacing={2}>
                        <Typography color="text.secondary" variant="body2">
                            {t('myAppsDetailPage.dialogs.uninstallBody', { appId: data?.app_id ?? appId ?? '-' })}
                        </Typography>
                        <FormControlLabel
                            control={<Switch checked={purgeData} onChange={(event) => setPurgeData(event.target.checked)} />}
                            label={t('myAppsDetailPage.dialogs.uninstallPurge')}
                        />
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setUninstallDialogOpen(false)}>{t('myAppsDetailPage.dialogs.cancel')}</Button>
                    <Button color="error" disabled={actionInProgress !== null} onClick={() => void handleUninstall()} variant="contained">
                        {actionInProgress === 'uninstall' ? t('myAppsDetailPage.actions.running') : t('myAppsDetailPage.actions.uninstall')}
                    </Button>
                </DialogActions>
            </Dialog>

            {feedback ? (
                <Snackbar autoHideDuration={4000} onClose={() => setFeedback(null)} open>
                    <Alert onClose={() => setFeedback(null)} severity={feedback.severity} sx={{ width: '100%' }} variant="filled">
                        {feedback.message}
                    </Alert>
                </Snackbar>
            ) : null}
        </Box>
    )
}