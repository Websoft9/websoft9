import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

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

function mapLocaleToApiLocale(locale: string) {
    return locale.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

export async function fetchMyAppDetail(appId: string, apiLocale: string) {
    const response = await fetch(`/api/apps/${encodeURIComponent(appId)}?locale=${encodeURIComponent(apiLocale)}`, {
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
    const { i18n } = useTranslation('shell')
    const resolvedLocale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const apiLocale = mapLocaleToApiLocale(resolvedLocale)

    return useQuery<MyAppDetail, MyAppDetailError>({
        queryKey: ['my-app-detail', appId, apiLocale],
        queryFn: async () => fetchMyAppDetail(appId ?? '', apiLocale),
        enabled: Boolean(appId),
        staleTime: 10_000,
        placeholderData: (previousData) => {
            if (previousData) return previousData
            if (!appId) return undefined

            const apps = queryClient.getQueryData<MyApp[]>(['my-apps', apiLocale])
            return apps?.find((app) => app.app_id === appId)
        },
    })
}