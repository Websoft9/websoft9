import { useQuery } from '@tanstack/react-query'

export type MyAppLogStage = {
    title: string
    sub_logs?: unknown[]
}

export type MyApp = {
    app_id: string
    tracking_id?: string | null
    app_name?: string | null
    app_dist?: string | null
    app_version?: string | null
    app_official: boolean
    proxy_enabled: boolean
    status: number
    creationDate?: number | null
    domain_names?: Array<Record<string, unknown>>
    error?: string | null
    logs?: MyAppLogStage[] | null
}

type MyAppsError = Error & {
    statusCode?: number
}

async function fetchMyApps() {
    const response = await fetch('/api/apps', {
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
    return useQuery<MyApp[], MyAppsError>({
        queryKey: ['my-apps'],
        queryFn: fetchMyApps,
        staleTime: 2_000,
        refetchInterval: (query) => {
            const apps = query.state.data ?? []
            return apps.some((app) => app.status === 3) ? 3_000 : 15_000
        },
    })
}