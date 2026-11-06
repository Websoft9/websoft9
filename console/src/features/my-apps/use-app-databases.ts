import { useQuery } from '@tanstack/react-query'

export type AppDatabaseUsage = 'application' | 'initialization' | 'administration'

export type AppDatabaseAccount = {
    user: string
    usage: string[]
    password: string | null
}

export type AppDatabaseTool = {
    label: string
    app_key: string
}

export type AppDatabaseComponent = {
    id: string
    driver: string
    service: string | null
    mode: 'internal' | 'external' | 'unknown'
    host: string | null
    port: number | null
    port_from_dictionary: boolean
    names: string[]
    accounts: AppDatabaseAccount[]
    auth: 'password' | 'none' | 'unknown'
    unknown_fields: string[]
    tools: AppDatabaseTool[]
}

export type AppDatabases = {
    app_id: string
    declaration: 'v2' | 'legacy' | 'missing'
    external_active: boolean
    components: AppDatabaseComponent[]
}

/**
 * Fetch the resolved database declaration of one installed app.
 *
 * `declaration: 'legacy' | 'missing'` means the installation predates the
 * `database[]` contract; callers must keep their previous rendering.
 */
export async function fetchAppDatabases(appId: string, endpointId?: number) {
    const query = endpointId === undefined ? '' : `?endpointId=${encodeURIComponent(String(endpointId))}`
    const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/databases${query}`, {
        credentials: 'include',
        headers: {
            Accept: 'application/json',
        },
    })

    if (!response.ok) {
        throw new Error(`Failed to load databases: ${response.status}`)
    }

    return (await response.json()) as AppDatabases
}

export function useAppDatabases(appId: string | undefined, enabled = true) {
    return useQuery<AppDatabases>({
        queryKey: ['my-app-databases', appId],
        queryFn: () => fetchAppDatabases(appId ?? ''),
        enabled: Boolean(appId) && enabled,
        staleTime: 30_000,
        retry: false,
    })
}
