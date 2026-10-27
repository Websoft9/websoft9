import { expect, test, type Page } from '@playwright/test'

/**
 * API-level checks against the running console. These cover the flows that
 * regressed in production but were invisible to unit tests:
 *  - application file sessions must use exactly the chosen connection
 *  - administrator mode state must not leak between host and application views
 */

const username = process.env.W9_USER || 'websoft9'
const password = process.env.W9_PASSWORD || 'Websoft9@'

async function apiLogin(page: Page) {
    const response = await page.request.post('/api/auth/login', { data: { username, password } })
    expect(response.ok(), `login failed: ${response.status()}`).toBeTruthy()
}

type SavedProfile = { profile_id: string; username?: string; is_local?: boolean; managed?: boolean; has_password?: boolean; has_private_key?: boolean }

async function localProfiles(page: Page): Promise<SavedProfile[]> {
    const response = await page.request.get('/api/host-access/profile')
    const body = await response.json() as { saved_profiles?: SavedProfile[] }
    return (body.saved_profiles || []).filter((item) => !item.managed && item.is_local && (item.has_password || item.has_private_key))
}

async function localProfile(page: Page): Promise<SavedProfile | undefined> {
    return (await localProfiles(page))[0]
}

async function sampleVolume(page: Page): Promise<{ appId: string; volumeId: string } | null> {
    const appsResponse = await page.request.get('/api/apps')
    if (!appsResponse.ok()) return null
    const apps = await appsResponse.json() as Array<{ app_id: string }>
    for (const app of apps.slice(0, 5)) {
        const detail = await page.request.get(`/api/apps/${encodeURIComponent(app.app_id)}`)
        if (!detail.ok()) continue
        const body = await detail.json() as { volumes?: Array<{ Name?: string }> }
        const volume = (body.volumes || []).find((item) => Boolean(item?.Name))
        if (volume?.Name) return { appId: app.app_id, volumeId: volume.Name }
    }
    return null
}

test('application file session rejects an unknown connection instead of switching accounts', async ({ page }) => {
    await apiLogin(page)
    const target = await sampleVolume(page)
    test.skip(!target, 'no application volume available on this host')

    const response = await page.request.post('/api/host-access/app-files/sessions', {
        data: { app_id: target!.appId, volume_id: target!.volumeId, profile_id: 'missing-connection' },
    })
    expect(response.status()).toBe(400)
    const body = await response.json() as { message?: string }
    expect(body.message).toBe('Host Access Profile Not Found')
})

test('application file session uses the selected connection', async ({ page }) => {
    await apiLogin(page)
    const profile = await localProfile(page)
    const target = await sampleVolume(page)
    test.skip(!profile || !target, 'needs a saved local connection and an application volume')

    const response = await page.request.post('/api/host-access/app-files/sessions', {
        data: { app_id: target!.appId, volume_id: target!.volumeId, profile_id: profile!.profile_id },
    })
    expect(response.ok(), `session creation failed: ${response.status()}`).toBeTruthy()
    const session = await response.json() as { session_id: string; profile_id: string | null; account?: string }
    expect(session.profile_id).toBe(profile!.profile_id)
    expect(session.account).toBe(profile!.username)

    await page.request.delete(`/api/host-access/app-files/${session.session_id}/session`)
})

test('administrator mode stays separate per view', async ({ page }) => {
    await apiLogin(page)
    const profiles = await localProfiles(page)
    test.skip(!profiles.length, 'needs a saved local connection')

    const statusOf = async (profileId: string, extra: Record<string, string> = {}) => {
        const response = await page.request.get(`/api/host-access/files/elevation?${new URLSearchParams({ profile_id: profileId, ...extra })}`)
        return await response.json() as { enabled?: boolean; can_elevate?: boolean; requires_password?: boolean }
    }

    // Pick a connection that can elevate without a sudo password.
    let profile: SavedProfile | undefined
    for (const candidate of profiles) {
        const status = await statusOf(candidate.profile_id)
        if (status.can_elevate === true && status.requires_password === false) {
            profile = candidate
            break
        }
    }
    test.skip(!profile, 'no passwordless sudo connection on this host')

    const status = async (scope: string, appId = '', volumeId = '') => ({ body: await statusOf(profile!.profile_id, { scope, app_id: appId, volume_id: volumeId }) })
    const otherStatus = async (otherProfileId: string) => await statusOf(otherProfileId)

    const initial = await status('host')
    test.skip(initial.body.can_elevate !== true, 'this connection cannot elevate on this host')

    try {
        const enabled = await page.request.post('/api/host-access/files/elevation', { data: { enabled: true, profile_id: profile!.profile_id } })
        expect(enabled.ok(), `enable failed: ${enabled.status()}`).toBeTruthy()
        expect((await status('host')).body.enabled).toBe(true)
        expect((await status('app', 'demo-app', 'demo-volume')).body.enabled).toBe(false)
        expect((await status('app', 'deepseekharness_i5o8a', 'deepseekharness_i5o8a_dsh_workspace')).body.enabled).toBe(false)

        // Another saved connection must not inherit administrator mode.
        const other = profiles.find((item) => item.profile_id !== profile!.profile_id)
        if (other) expect((await otherStatus(other.profile_id)).enabled).toBe(false)
    } finally {
        await page.request.post('/api/host-access/files/elevation', { data: { enabled: false, profile_id: profile!.profile_id } })
    }

    const after = await status('host')
    expect(after.body.enabled).toBe(false)
    expect(after.body.can_elevate).toBe(true)
})
