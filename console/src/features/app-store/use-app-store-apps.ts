import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import type { AppStoreApp } from './app-store-model'

type AppStoreError = Error & {
    statusCode?: number
}

function mapLocaleToApiLocale(locale: string) {
    return locale.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

type AppStoreInstallMetadata = {
    initial_apps?: string[]
    apps?: Record<
        string,
        {
            settings?: Record<string, string>
            is_web_app?: boolean
        }
    >
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

function mergeAppStoreInstallMetadata(apps: AppStoreApp[], metadata: AppStoreInstallMetadata) {
    const configuredAppKeys = (metadata.initial_apps ?? []).filter(Boolean)
    const allowedAppKeys = configuredAppKeys.length > 0 ? new Set(configuredAppKeys) : null

    return apps
        .filter((app) => {
            if (!allowedAppKeys) {
                return true
            }

            return Boolean(app.key && allowedAppKeys.has(app.key))
        })
        .map((app) => {
            const appMetadata = app.key ? metadata.apps?.[app.key] : undefined

            return {
                ...app,
                settings: appMetadata?.settings ?? {},
                is_web_app: appMetadata?.is_web_app ?? false,
            }
        })
}

async function fetchAppStoreAppsFromStatic(apiLocale: string) {
    const [apps, metadata] = await Promise.all([
        fetchJson<AppStoreApp[]>(`/media/json/product_${apiLocale}.json`, 'Failed to load static app store data'),
        fetchJson<AppStoreInstallMetadata>('/media/json/app-store-install-metadata.json', 'Failed to load app install metadata'),
    ])

    return mergeAppStoreInstallMetadata(apps, metadata)
}

async function fetchAppStoreAppsFromApi(apiLocale: string) {
    // Compatibility-only fallback while the static product JSON path becomes the
    // primary browse contract for the App Store.
    return fetchJson<AppStoreApp[]>(`/api/apps/available/${apiLocale}`, 'Failed to load app store data')
}

export function useAppStoreApps() {
    const { i18n } = useTranslation('shell')
    const resolvedLocale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const apiLocale = mapLocaleToApiLocale(resolvedLocale)

    return useQuery<AppStoreApp[], AppStoreError>({
        queryKey: ['app-store-apps', apiLocale],
        queryFn: async () => {
            try {
                return await fetchAppStoreAppsFromStatic(apiLocale)
            } catch {
                return fetchAppStoreAppsFromApi(apiLocale)
            }
        },
        staleTime: 60_000,
    })
}