import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { resolveAppCatalogLocale } from '../../shared/i18n/i18n'
import { withoutExternalDatabaseProfiles } from './external-database-profiles'
import { fetchAppStoreJson, fetchAppStoreWithFallback } from './app-store-fetch'
import type { AppStoreApp } from './app-store-model'

type AppStoreError = Error & {
    statusCode?: number
}

type AppStoreManifest = {
    schemaVersion?: string
    locale?: string
    apps?: AppStoreApp[]
}

async function fetchAppStoreAppsFromStaticAssets(apiLocale: string) {
    const manifest = await fetchAppStoreJson<AppStoreManifest>(
        `/media/json/app-store-manifest_${apiLocale}.json`,
        'Failed to load static app store manifest',
    )
    if (manifest.schemaVersion !== '1' || manifest.locale !== apiLocale || !Array.isArray(manifest.apps)) {
        throw new Error('Static app store manifest has an invalid schema, locale or apps array')
    }
    return withoutExternalDatabaseProfiles(manifest.apps)
}

async function fetchAppStoreApps(apiLocale: string) {
    return fetchAppStoreWithFallback(
        `/api/apps/available/${apiLocale}`,
        'Failed to load app store data',
        () => fetchAppStoreAppsFromStaticAssets(apiLocale),
    )
}

export function useAppStoreApps() {
    const { i18n } = useTranslation('shell')
    const resolvedLocale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const apiLocale = resolveAppCatalogLocale(resolvedLocale)

    return useQuery<AppStoreApp[], AppStoreError>({
        queryKey: ['app-store-apps', apiLocale],
        queryFn: () => fetchAppStoreApps(apiLocale),
        staleTime: 60_000,
    })
}
