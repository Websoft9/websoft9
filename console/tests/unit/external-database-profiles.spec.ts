import { expect, test } from '@playwright/test'

import { withoutExternalDatabaseProfiles } from '../../src/features/app-store/external-database-profiles'
import type { AppStoreApp } from '../../src/features/app-store/app-store-model'

/**
 * The static manifest is served without the API policy. Installing an external
 * database needs the API, so the fallback must never expose that profile.
 */

function app(overrides: Partial<AppStoreApp> = {}): AppStoreApp {
    return { key: 'canvas', ...overrides }
}

test.describe('static App Store fallback profiles', () => {
    test('removes the external database profile and keeps other profiles', () => {
        const [filtered] = withoutExternalDatabaseProfiles([
            app({
                profiles: {
                    'external-db': { settings: {}, is_external_database: true },
                    'high-availability': { settings: {} },
                },
            }),
        ])

        expect(Object.keys(filtered.profiles ?? {})).toEqual(['high-availability'])
    })

    test('drops the profiles object when external-db was its only entry', () => {
        const [filtered] = withoutExternalDatabaseProfiles([
            app({ key: 'wordpress', profiles: { 'external-db': { is_external_database: true } } }),
        ])

        expect(filtered.profiles).toBeUndefined()
    })

    test('leaves applications without an external profile untouched', () => {
        const original = app({ profiles: { 'high-availability': { settings: {} } } })
        const [filtered] = withoutExternalDatabaseProfiles([original])

        expect(filtered).toBe(original)
    })

    test('does not mutate the manifest payload', () => {
        const original = app({ profiles: { 'external-db': { is_external_database: true } } })

        withoutExternalDatabaseProfiles([original])

        expect(original.profiles?.['external-db']).toBeDefined()
    })
})
