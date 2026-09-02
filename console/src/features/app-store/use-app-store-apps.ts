import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import type { AppStoreApp } from './app-store-model'

type AppStoreError = Error & {
    statusCode?: number
}

type AppStoreManifest = {
    apps?: AppStoreApp[]
}

function mapLocaleToApiLocale(locale: string) {
    return locale.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

async function fetchJson<T>(url: string, errorMessage: string) {
    const response = await fetch(url, {
        headers: {
            Accept: 'application/json',
        },
    })

    if (!response.ok) {
        const error = new Error(`${errorMessage}: ${response.status}`) as AppStoreError
        error.statusCode = response.status
        throw error
    }

    return (await response.json()) as T
}

async function fetchAppStoreAppsFromStaticAssets(apiLocale: string) {
    const manifest = await fetchJson<AppStoreManifest>(
        `/media/json/app-store-manifest_${apiLocale}.json`,
        'Failed to load static app store manifest',
    )
    if (!Array.isArray(manifest.apps)) {
        throw new Error('Static app store manifest has no apps array')
    }
    return manifest.apps
}

async function fetchAppStoreAppsFromApi(apiLocale: string) {
    return fetchJson<AppStoreApp[]>(`/api/apps/available/${apiLocale}`, 'Failed to load app store data')
}

async function fetchAppStoreApps(apiLocale: string) {
    try {
        return await fetchAppStoreAppsFromApi(apiLocale)
    } catch {
        return fetchAppStoreAppsFromStaticAssets(apiLocale)
    }
}

export function useAppStoreApps() {
    const { i18n } = useTranslation('shell')
    const resolvedLocale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const apiLocale = mapLocaleToApiLocale(resolvedLocale)

    return useQuery<AppStoreApp[], AppStoreError>({
        queryKey: ['app-store-apps', apiLocale],
        queryFn: () => fetchAppStoreApps(apiLocale),
        staleTime: 60_000,
    })
}