import { useQuery, useQueryClient } from '@tanstack/react-query'

import type { MyApp } from './use-my-apps'

export type MyAppDetail = MyApp & {
    endpointId?: number
    env?: Record<string, string>
    gitConfig?: Record<string, unknown>
    containers?: Array<Record<string, unknown>>
    volumes?: Array<Record<string, unknown>>
}

type MyAppDetailError = Error & {
    statusCode?: number
}

export async function fetchMyAppDetail(appId: string) {
    const response = await fetch(`/api/apps/${encodeURIComponent(appId)}`, {
        credentials: 'include',
        headers: {
            Accept: 'application/json',
        },
    })

    if (!response.ok) {
        const error = new Error(`Failed to load app detail: ${response.status}`) as MyAppDetailError
        error.statusCode = response.status
        throw error
    }

    return (await response.json()) as MyAppDetail
}

export function useMyAppDetail(appId: string | undefined) {
    const queryClient = useQueryClient()

    return useQuery<MyAppDetail, MyAppDetailError>({
        queryKey: ['my-app-detail', appId],
        queryFn: async () => fetchMyAppDetail(appId ?? ''),
        enabled: Boolean(appId),
        staleTime: 10_000,
        initialData: () => {
            if (!appId) return undefined
            const apps = queryClient.getQueryData<MyApp[]>(['my-apps'])
            return apps?.find((app) => app.app_id === appId)
        },
    })
}