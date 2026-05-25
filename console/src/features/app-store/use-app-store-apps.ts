import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import type { AppStoreApp } from './app-store-model'

type AppStoreError = Error & {
    statusCode?: number
}

type AppStoreInstallMetadata = {
    settings?: Record<string, string>
    is_web_app?: boolean
}

type AppStoreInstallMetadataManifest = {
    apps?: Record<string, AppStoreInstallMetadata>
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

function mergeInstallMetadata(apps: AppStoreApp[], metadataManifest: AppStoreInstallMetadataManifest | null) {
    const installMetadataByKey = metadataManifest?.apps ?? {}

    return apps.map((app) => {
        const appKey = (app.key ?? '').trim()
        if (!appKey) {
            return app
        }

        const installMetadata = installMetadataByKey[appKey]
        if (!installMetadata) {
            return app
        }

        return {
            ...app,
            settings: installMetadata.settings ?? app.settings ?? {},
            is_web_app: installMetadata.is_web_app ?? app.is_web_app ?? false,
        }
    })
}

async function fetchAppStoreAppsFromStaticAssets(apiLocale: string) {
    const apps = await fetchJson<AppStoreApp[]>(`/media/json/product_${apiLocale}.json`, 'Failed to load static app store data')

    try {
        const installMetadata = await fetchJson<AppStoreInstallMetadataManifest>(
            '/media/json/app-store-install-metadata.json',
            'Failed to load app store install metadata',
        )

        return mergeInstallMetadata(apps, installMetadata)
    } catch {
        return apps
    }
}

async function fetchAppStoreAppsFromApi(apiLocale: string) {
    return fetchJson<AppStoreApp[]>(`/api/apps/available/${apiLocale}`, 'Failed to load app store data')
}

async function fetchAppStoreApps(apiLocale: string) {
    try {
        const staticApps = await fetchAppStoreAppsFromStaticAssets(apiLocale)
        const hasInstallMetadata = staticApps.some((app) => {
            const settings = app.settings ?? {}
            return Object.keys(settings).length > 0 || Boolean(app.is_web_app)
        })

        if (hasInstallMetadata) {
            return staticApps
        }
    } catch {
        // Fall back to compatibility API below.
    }

    return fetchAppStoreAppsFromApi(apiLocale)
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