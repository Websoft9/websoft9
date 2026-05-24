import { useQuery } from '@tanstack/react-query'

export type MyAppAccessProfile = {
    enabled: boolean
    source: 'builtin' | 'profile' | 'unknown'
    locked: boolean
    forward_host?: string | null
    forward_port?: number | null
    forward_scheme: 'http' | 'https'
}

export type MyAppAccessCandidate = {
    container_name: string
    forward_host: string
    forward_port: number
    published_ports: string[]
}

export type MyAppProxyHost = {
    proxy_id: number
    domain_names: string[]
    certificate_id?: number | null
    certificate_name?: string | null
    ssl_forced?: boolean
}

export type MyAppCertificate = {
    id: number
    nice_name?: string | null
    domain_names?: string[]
    provider?: string | null
}

export type MyAppAccessOverview = {
    app_id: string
    app_dist?: string | null
    requires_definition: boolean
    profile: MyAppAccessProfile
    candidates: MyAppAccessCandidate[]
    proxy_hosts: MyAppProxyHost[]
    certificates: MyAppCertificate[]
}

type MyAppAccessError = Error & {
    statusCode?: number
}

async function fetchJson<T>(url: string, errorMessage: string) {
    const response = await fetch(url, {
        credentials: 'include',
        headers: {
            Accept: 'application/json',
        },
    })

    if (!response.ok) {
        const error = new Error(`${errorMessage}: ${response.status}`) as MyAppAccessError
        error.statusCode = response.status
        throw error
    }

    return (await response.json()) as T
}

export function useMyAppAccess(appId: string | undefined) {
    return useQuery<MyAppAccessOverview, MyAppAccessError>({
        queryKey: ['my-app-access', appId],
        enabled: Boolean(appId),
        queryFn: async () => {
            return fetchJson<MyAppAccessOverview>(`/api/apps/${encodeURIComponent(appId ?? '')}/access`, 'Failed to load app access')
        },
        staleTime: 5_000,
    })
}