import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import type { AppStoreCatalogItem } from './app-store-model'

type AppStoreCatalogError = Error & {
    statusCode?: number
}

function mapLocaleToApiLocale(locale: string) {
    return locale.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

async function fetchCatalogJson<T>(url: string, errorMessage: string) {
    const response = await fetch(url, {
        headers: {
            Accept: 'application/json',
        },
    })

    if (!response.ok) {
        const error = new Error(`${errorMessage}: ${response.status}`) as AppStoreCatalogError
        error.statusCode = response.status
        throw error
    }

    return (await response.json()) as T
}

function sortCatalogs(items: AppStoreCatalogItem[]) {
    return [...items].sort((left, right) => {
        if (left.position == null && right.position == null) {
            return 0
        }

        if (left.position == null) {
            return 1
        }

        if (right.position == null) {
            return -1
        }

        return left.position - right.position
    })
}

async function fetchCatalogs(apiLocale: string) {
    try {
        return await fetchCatalogJson<AppStoreCatalogItem[]>(`/media/json/catalog_${apiLocale}.json`, 'Failed to load static app store catalogs')
    } catch {
        return fetchCatalogJson<AppStoreCatalogItem[]>(`/api/apps/catalog/${apiLocale}`, 'Failed to load app store catalogs')
    }
}

export function useAppStoreCatalogs() {
    const { i18n } = useTranslation('shell')
    const resolvedLocale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const apiLocale = mapLocaleToApiLocale(resolvedLocale)

    return useQuery<AppStoreCatalogItem[], AppStoreCatalogError>({
        queryKey: ['app-store-catalogs', apiLocale],
        queryFn: async () => {
            const catalogs = await fetchCatalogs(apiLocale)
            return sortCatalogs(catalogs)
        },
        staleTime: 60_000,
    })
}