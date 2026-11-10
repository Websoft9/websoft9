import type { AppStoreApp } from './app-store-model'

const EXTERNAL_DATABASE_PROFILE = 'external-db'

/**
 * The static manifest carries the library capability declaration for every
 * application. The API applies the platform policy before serving it, but the
 * static fallback bypasses that layer. Installing an external database needs
 * the API anyway, so the fallback never offers that profile.
 */
export function withoutExternalDatabaseProfiles(apps: AppStoreApp[]): AppStoreApp[] {
    return apps.map((app) => {
        const profiles = app.profiles
        if (!profiles || !(EXTERNAL_DATABASE_PROFILE in profiles)) {
            return app
        }

        const remaining = { ...profiles }
        delete remaining[EXTERNAL_DATABASE_PROFILE]
        const filtered: AppStoreApp = { ...app, profiles: remaining }
        if (Object.keys(remaining).length === 0) {
            delete filtered.profiles
        }
        return filtered
    })
}
