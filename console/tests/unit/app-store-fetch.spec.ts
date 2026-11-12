import { expect, test } from '@playwright/test'

import {
    AppStoreAssetsUnavailableError,
    fetchAppStoreJson,
    fetchAppStoreWithFallback,
} from '../../src/features/app-store/app-store-fetch'

const originalFetch = globalThis.fetch

test.afterEach(() => {
    globalThis.fetch = originalFetch
})

test('a verified unavailable response cannot be bypassed with static files', async () => {
    globalThis.fetch = async () => new Response(JSON.stringify({
        message: 'App Store Assets Unavailable', details: 'Incomplete dataset',
    }), { status: 503 })
    let staticRequests = 0
    await expect(fetchAppStoreWithFallback('/api/apps', 'failed', async () => {
        staticRequests++
        return []
    })).rejects.toBeInstanceOf(AppStoreAssetsUnavailableError)
    expect(staticRequests).toBe(0)
})

for (const status of [500, 503]) {
    test(`ordinary HTTP ${status} errors retain static fallback`, async () => {
        globalThis.fetch = async () => new Response('<html>proxy unavailable</html>', { status })
        expect(await fetchAppStoreWithFallback('/api/apps', 'failed', async () => ['static'])).toEqual(['static'])
    })
}

test('network errors retain static fallback', async () => {
    globalThis.fetch = async () => { throw new TypeError('network unavailable') }
    expect(await fetchAppStoreWithFallback('/api/apps', 'failed', async () => ['static'])).toEqual(['static'])
})

test('successful API requests do not read static files', async () => {
    globalThis.fetch = async () => new Response(JSON.stringify(['api']))
    expect(await fetchAppStoreWithFallback('/api/apps', 'failed', async () => {
        throw new Error('unexpected fallback')
    })).toEqual(['api'])
})

test('static fallback failure is surfaced rather than becoming an empty catalog', async () => {
    globalThis.fetch = async () => new Response('', { status: 500 })
    await expect(fetchAppStoreWithFallback('/api/apps', 'failed', async () => {
        throw new Error('static manifest unavailable')
    })).rejects.toThrow('static manifest unavailable')
})

test('JSON fetch preserves normal HTTP status errors', async () => {
    globalThis.fetch = async () => new Response('', { status: 404 })
    await expect(fetchAppStoreJson('/api/apps', 'failed')).rejects.toMatchObject({
        message: 'failed: 404', statusCode: 404,
    })
})
