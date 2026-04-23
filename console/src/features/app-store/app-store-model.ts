export type AppStoreCatalogItem = {
    key?: string
    title?: string
    position?: number | null
    linkedFrom?: {
        catalogCollection?: {
            items?: AppStoreCatalogItem[]
        }
    }
    catalogCollection?: {
        items?: AppStoreCatalogItem[]
    }
}

export type AppStoreLogo = {
    imageurl?: string
}

export type AppStoreScreenshot = {
    key?: string
    value?: string
}

export type AppStoreDistribution = {
    key?: string
    value?: string | string[]
}

export type AppStoreApp = {
    key?: string
    hot?: number
    trademark?: string
    summary?: string
    overview?: string
    description?: string | null
    websiteurl?: string
    screenshots?: AppStoreScreenshot[]
    distribution?: AppStoreDistribution[]
    vcpu?: number
    memory?: number
    storage?: number
    logo?: AppStoreLogo
    catalogCollection?: {
        items?: AppStoreCatalogItem[]
    }
    settings?: Record<string, string>
    is_web_app?: boolean
}

export type AppStoreCategory = {
    id: string
    label: string
}

export type AppStoreInstallDistribution = {
    dist: string
    versions: string[]
}

function normalizeLabel(value: string | undefined, fallback: string) {
    return value?.trim() || fallback
}

export function getAppStoreCategories(apps: AppStoreApp[]): AppStoreCategory[] {
    const seen = new Map<string, AppStoreCategory>()

    for (const app of apps) {
        const mainCategories = app.catalogCollection?.items ?? []

        for (const mainCategory of mainCategories) {
            const mainId = normalizeLabel(mainCategory.key, normalizeLabel(mainCategory.title, 'other')).toLowerCase()
            const mainLabel = normalizeLabel(mainCategory.title, normalizeLabel(mainCategory.key, 'Other'))

            if (!seen.has(mainId)) {
                seen.set(mainId, { id: mainId, label: mainLabel })
            }

            const subCategories = mainCategory.catalogCollection?.items ?? []

            for (const subCategory of subCategories) {
                const subId = normalizeLabel(subCategory.key, normalizeLabel(subCategory.title, mainId)).toLowerCase()
                const subLabel = normalizeLabel(subCategory.title, normalizeLabel(subCategory.key, mainLabel))

                if (!seen.has(subId)) {
                    seen.set(subId, { id: subId, label: subLabel })
                }
            }
        }
    }

    return [...seen.values()].sort((left, right) => left.label.localeCompare(right.label))
}

export function getAppStoreSubCategories(apps: AppStoreApp[], selectedCategoryId: string) {
    if (selectedCategoryId === 'all') {
        return []
    }

    const seen = new Map<string, AppStoreCategory>()

    for (const app of apps) {
        for (const mainCategory of app.catalogCollection?.items ?? []) {
            const mainId = normalizeLabel(mainCategory.key, normalizeLabel(mainCategory.title, 'other')).toLowerCase()
            if (mainId !== selectedCategoryId) {
                continue
            }

            for (const subCategory of mainCategory.catalogCollection?.items ?? []) {
                const subId = normalizeLabel(subCategory.key, normalizeLabel(subCategory.title, mainId)).toLowerCase()
                const subLabel = normalizeLabel(subCategory.title, normalizeLabel(subCategory.key, mainCategory.title ?? 'Other'))

                if (!seen.has(subId)) {
                    seen.set(subId, { id: subId, label: subLabel })
                }
            }
        }
    }

    return [...seen.values()].sort((left, right) => left.label.localeCompare(right.label))
}

export function matchesAppStoreMainCategory(app: AppStoreApp, selectedCategoryId: string) {
    if (selectedCategoryId === 'all') {
        return true
    }

    return (app.catalogCollection?.items ?? []).some((mainCategory) => {
        const mainId = normalizeLabel(mainCategory.key, normalizeLabel(mainCategory.title, 'other')).toLowerCase()
        return mainId === selectedCategoryId
    })
}

export function matchesAppStoreSubCategory(app: AppStoreApp, selectedSubCategoryId: string) {
    if (selectedSubCategoryId === 'all') {
        return true
    }

    return (app.catalogCollection?.items ?? []).some((mainCategory) => {
        return (mainCategory.catalogCollection?.items ?? []).some((subCategory) => {
            const subId = normalizeLabel(subCategory.key, normalizeLabel(subCategory.title, mainCategory.key ?? 'other')).toLowerCase()
            return subId === selectedSubCategoryId
        })
    })
}

export function matchesAppStoreCategory(app: AppStoreApp, selectedCategoryId: string) {
    if (selectedCategoryId === 'all') {
        return true
    }

    const mainCategories = app.catalogCollection?.items ?? []

    return mainCategories.some((mainCategory) => {
        const mainId = normalizeLabel(mainCategory.key, normalizeLabel(mainCategory.title, 'other')).toLowerCase()
        if (mainId === selectedCategoryId) {
            return true
        }

        const subCategories = mainCategory.catalogCollection?.items ?? []
        return subCategories.some((subCategory) => normalizeLabel(subCategory.key, normalizeLabel(subCategory.title, mainId)).toLowerCase() === selectedCategoryId)
    })
}

export function matchesAppStoreSearch(app: AppStoreApp, keyword: string) {
    const normalizedKeyword = keyword.trim().toLowerCase()

    if (!normalizedKeyword) {
        return true
    }

    const searchableParts = [app.key, app.trademark, app.summary]

    return searchableParts.some((part) => part?.toLowerCase().includes(normalizedKeyword))
}

export function getAppStoreVersionSummary(app: AppStoreApp) {
    const versions = (app.distribution ?? []).flatMap((item) => {
        if (Array.isArray(item.value)) {
            return item.value
        }

        if (typeof item.value === 'string') {
            return [item.value]
        }

        return []
    })
    return versions.join(', ')
}

export function getAppStoreInstallDistributions(app: AppStoreApp): AppStoreInstallDistribution[] {
    return (app.distribution ?? [])
        .map((item) => {
            const dist = normalizeLabel(item.key, 'community').toLowerCase()
            const versions = Array.isArray(item.value)
                ? item.value.map((value) => value.trim()).filter(Boolean)
                : (item.value ?? '')
                    .split(',')
                    .map((value) => value.trim())
                    .filter(Boolean)

            return {
                dist,
                versions,
            }
        })
        .filter((item) => item.versions.length > 0)
}

export function getPreferredAppStoreInstallDistribution(app: AppStoreApp) {
    const distributions = getAppStoreInstallDistributions(app)
    return distributions[0] ?? { dist: 'community', versions: ['latest'] }
}

export function getPreferredAppStoreScreenshot(app: AppStoreApp) {
    return app.screenshots?.find((item) => item.value)?.value
}

export function getAppStoreCategoryLabels(app: AppStoreApp) {
    const labels = new Set<string>()

    for (const mainCategory of app.catalogCollection?.items ?? []) {
        const mainLabel = normalizeLabel(mainCategory.title, normalizeLabel(mainCategory.key, 'Other'))
        labels.add(mainLabel)

        for (const subCategory of mainCategory.catalogCollection?.items ?? []) {
            labels.add(normalizeLabel(subCategory.title, normalizeLabel(subCategory.key, mainLabel)))
        }
    }

    return [...labels]
}