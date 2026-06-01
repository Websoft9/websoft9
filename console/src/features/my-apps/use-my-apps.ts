import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

export type MyAppLogStage = {
    title: string
    sub_logs?: unknown[]
}

export type MyApp = {
    app_id: string
    tracking_id?: string | null
    endpointId?: number
    app_name?: string | null
    logo_url?: string | null
    app_dist?: string | null
    app_version?: string | null
    app_official: boolean
    is_php_app?: boolean
    is_monitor_app?: boolean
    proxy_enabled: boolean
    status: number
    creationDate?: number | null
    domain_names?: Array<Record<string, unknown>>
    env?: Record<string, string>
    gitConfig?: Record<string, unknown>
    containers?: Array<Record<string, unknown>>
    volumes?: Array<Record<string, unknown>>
    error?: string | null
    logs?: MyAppLogStage[] | null
}

export type MyAppStatusKey = 'installing' | 'active' | 'inactive' | 'error'

type MyAppsError = Error & {
    statusCode?: number
}

type MyAppsStreamPayload = {
    apps?: MyApp[]
    digest?: string
    refresh_hint_ms?: number
}

const statusOrder: Record<MyAppStatusKey, number> = {
    installing: 0,
    active: 1,
    inactive: 2,
    error: 3,
}

export function getMyAppStatusKey(status: number): MyAppStatusKey {
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

export function getMyAppDomains(app: MyApp) {
    return (app.domain_names ?? [])
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
}

export function getMyAppPrimaryAccessEntry(app: MyApp) {
    return getMyAppDomains(app)[0]
}

export function sortMyApps(apps: MyApp[]) {
    return [...apps].sort((left, right) => {
        const leftStatus = statusOrder[getMyAppStatusKey(left.status)]
        const rightStatus = statusOrder[getMyAppStatusKey(right.status)]

        if (leftStatus !== rightStatus) {
            return leftStatus - rightStatus
        }

        return (right.creationDate ?? 0) - (left.creationDate ?? 0)
    })
}

/**
 * When the API returns multiple records for the same app_id (e.g. a successful
 * install and a stale error tracking entry), keep only the entry with the best
 * status (lowest statusOrder value: installing > active > inactive > error).
 */
function deduplicateApps(apps: MyApp[]): MyApp[] {
    const map = new Map<string, MyApp>()
    for (const app of apps) {
        const existing = map.get(app.app_id)
        if (!existing) {
            map.set(app.app_id, app)
        } else {
            const existingOrder = statusOrder[getMyAppStatusKey(existing.status)]
            const appOrder = statusOrder[getMyAppStatusKey(app.status)]
            if (appOrder < existingOrder) {
                map.set(app.app_id, app)
            }
        }
    }
    return [...map.values()]
}

function mapLocaleToApiLocale(locale: string) {
    return locale.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

async function fetchMyApps(apiLocale: string) {
    const response = await fetch(`/api/apps?locale=${encodeURIComponent(apiLocale)}`, {
        credentials: 'include',
        headers: {
            Accept: 'application/json',
        },
    })

    if (!response.ok) {
        const error = new Error(`Failed to load my apps: ${response.status}`) as MyAppsError
        error.statusCode = response.status
        throw error
    }

    return (await response.json()) as MyApp[]
}

function buildMyAppsStreamUrl(apiLocale: string) {
    return `/api/apps/stream?locale=${encodeURIComponent(apiLocale)}`
}

function mergeMyAppSummaryIntoDetail(previousData: MyApp, app: MyApp): MyApp {
    return {
        ...previousData,
        ...app,
        app_name: app.app_name ?? previousData.app_name,
        logo_url: app.logo_url ?? previousData.logo_url,
        app_dist: app.app_dist ?? previousData.app_dist,
        app_version: app.app_version ?? previousData.app_version,
        env: Object.keys(app.env ?? {}).length > 0 ? app.env : previousData.env,
        gitConfig: app.gitConfig ?? previousData.gitConfig,
        volumes: (app.volumes ?? []).length > 0 ? app.volumes : previousData.volumes,
        error: app.error ?? previousData.error,
        logs: app.logs ?? previousData.logs,
    }
}

export function useMyApps() {
    const { i18n } = useTranslation('shell')
    const queryClient = useQueryClient()
    const resolvedLocale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const apiLocale = mapLocaleToApiLocale(resolvedLocale)
    const supportsEventSource = typeof window !== 'undefined' && typeof EventSource !== 'undefined'

    useEffect(() => {
        if (!supportsEventSource) {
            return
        }

        const eventSource = new EventSource(buildMyAppsStreamUrl(apiLocale), { withCredentials: true })
        const applySnapshot = (apps: MyApp[]) => {
            const normalizedApps = sortMyApps(deduplicateApps(apps))
            queryClient.setQueryData<MyApp[]>(['my-apps', apiLocale], normalizedApps)

            normalizedApps.forEach((app) => {
                const detailQueryKey = ['my-app-detail', app.app_id, apiLocale]
                if (!queryClient.getQueryState(detailQueryKey)) {
                    return
                }

                queryClient.setQueryData(detailQueryKey, (previousData: MyApp | undefined) => {
                    if (!previousData) {
                        return app
                    }

                    return mergeMyAppSummaryIntoDetail(previousData, app)
                })
            })
        }

        const handleSnapshot = (event: Event) => {
            try {
                const payload = JSON.parse((event as MessageEvent<string>).data) as MyAppsStreamPayload
                if (Array.isArray(payload.apps)) {
                    applySnapshot(payload.apps)
                }
            } catch {
                // Ignore malformed events and wait for the next snapshot.
            }
        }

        eventSource.addEventListener('snapshot', handleSnapshot)

        return () => {
            eventSource.removeEventListener('snapshot', handleSnapshot)
            eventSource.close()
        }
    }, [apiLocale, queryClient, supportsEventSource])

    return useQuery<MyApp[], MyAppsError>({
        queryKey: ['my-apps', apiLocale],
        queryFn: () => fetchMyApps(apiLocale),
        select: (apps) => sortMyApps(deduplicateApps(apps)),
        staleTime: supportsEventSource ? 10_000 : 2_000,
        refetchInterval: supportsEventSource
            ? false
            : (query) => {
                const apps = query.state.data ?? []
                return apps.some((app) => app.status === 3) ? 3_000 : 5_000
            },
    })
}