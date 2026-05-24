import { useQuery } from '@tanstack/react-query'
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

export function useMyApps() {
    const { i18n } = useTranslation('shell')
    const resolvedLocale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const apiLocale = mapLocaleToApiLocale(resolvedLocale)

    return useQuery<MyApp[], MyAppsError>({
        queryKey: ['my-apps', apiLocale],
        queryFn: () => fetchMyApps(apiLocale),
        select: (apps) => sortMyApps(deduplicateApps(apps)),
        staleTime: 2_000,
        refetchInterval: (query) => {
            const apps = query.state.data ?? []
            // Poll every 3s during install, 5s otherwise (fast enough to catch Portainer deletions)
            return apps.some((app) => app.status === 3) ? 3_000 : 5_000
        },
    })
}