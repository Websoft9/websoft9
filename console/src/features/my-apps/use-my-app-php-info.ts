import { useQuery } from '@tanstack/react-query'

export type MyAppPhpInfo = {
    version: string
    modules: Record<string, string[]>
}

type MyAppPhpInfoError = Error & {
    statusCode?: number
    details?: string
}

async function fetchMyAppPhpInfo(appId: string) {
    const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/php`, {
        credentials: 'include',
        headers: {
            Accept: 'application/json',
        },
    })

    if (!response.ok) {
        let payload: { details?: string; message?: string } | null = null
        try {
            payload = await response.json() as { details?: string; message?: string }
        } catch {
            payload = null
        }

        const error = new Error(payload?.message || `Failed to load PHP info: ${response.status}`) as MyAppPhpInfoError
        error.statusCode = response.status
        error.details = payload?.details
        throw error
    }

    return (await response.json()) as MyAppPhpInfo
}

export function useMyAppPhpInfo(appId: string | undefined, enabled: boolean) {
    return useQuery<MyAppPhpInfo, MyAppPhpInfoError>({
        queryKey: ['my-app-php-info', appId],
        queryFn: async () => fetchMyAppPhpInfo(appId ?? ''),
        enabled: Boolean(appId) && enabled,
        staleTime: 5_000,
    })
}