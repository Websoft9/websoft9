import { useQuery } from '@tanstack/react-query'

export type MyAppProxyHost = {
    proxy_id: number
    domain_names: string[]
    certificate_id?: number | null
    certificate_name?: string | null
}

export type MyAppCertificate = {
    id: number
    nice_name?: string | null
    domain_names?: string[]
    provider?: string | null
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

export function useMyAppAccess(appId: string | undefined, enabled: boolean) {
    return useQuery<{ proxyHosts: MyAppProxyHost[]; certificates: MyAppCertificate[] }, MyAppAccessError>({
        queryKey: ['my-app-access', appId],
        enabled: Boolean(appId) && enabled,
        queryFn: async () => {
            const [proxyHosts, certificates] = await Promise.all([
                fetchJson<MyAppProxyHost[]>(`/api/proxys/${encodeURIComponent(appId ?? '')}`, 'Failed to load proxy hosts'),
                fetchJson<MyAppCertificate[]>('/api/proxys/ssl/certificates', 'Failed to load certificates'),
            ])

            return {
                proxyHosts,
                certificates,
            }
        },
        staleTime: 5_000,
    })
}