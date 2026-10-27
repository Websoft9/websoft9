import { expect, test, type Page } from '@playwright/test'

/**
 * Console smoke tests for the flows that broke repeatedly:
 *  - signing out closes sessions and clears browser snapshots
 *  - signing in again never resurrects "disconnected" tabs
 *  - administrator mode endpoints stay authenticated
 */

const username = process.env.W9_USER || 'websoft9'
const password = process.env.W9_PASSWORD || 'Websoft9@'

async function apiLogin(page: Page) {
    const response = await page.request.post('/api/auth/login', { data: { username, password } })
    expect(response.ok(), `login failed: ${response.status()}`).toBeTruthy()
}

test('console loads after signing in', async ({ page }) => {
    await apiLogin(page)
    await page.goto('/terminal')
    await expect(page.locator('body')).toContainText('终端', { timeout: 15000 })
    // A fresh sign-in starts from an empty session list.
    const stored = await page.evaluate(() => sessionStorage.getItem('websoft9:app-files-sessions'))
    expect(stored ?? '[]').toBe('[]')
})

test('stale application file sessions are marked ended after a restart', async ({ page }) => {
    await apiLogin(page)
    await page.goto('/terminal')
    await page.evaluate(() => {
        sessionStorage.setItem('websoft9:app-files-sessions', JSON.stringify([
            { session_id: 'session-that-no-longer-exists', root_path: '/', app_id: 'demo', volume_id: 'demo-volume', profile_id: null, status: 'connected' },
        ]))
    })
    await page.reload()
    await expect.poll(async () => page.evaluate(() => {
        const raw = sessionStorage.getItem('websoft9:app-files-sessions')
        const entries = raw ? JSON.parse(raw) as Array<{ status?: string }> : []
        return entries[0]?.status
    }), { timeout: 15000 }).toBe('ended')
})

test('signing out closes sessions and clears browser snapshots', async ({ page }) => {
    await apiLogin(page)
    await page.goto('/terminal')
    await expect(page.locator('body')).toContainText('终端', { timeout: 15000 })

    await page.evaluate(() => {
        sessionStorage.setItem('websoft9:terminal-workspace-v1', JSON.stringify({ accessReady: true, sessions: [{ id: 'stale' }], activeSessionId: 'stale', workspaceView: 'terminal', browserPath: '/', selectedEntryPath: null, profileScope: 'someone:' }))
        localStorage.setItem('websoft9:sftp-access-choice', JSON.stringify({ mode: 'platform' }))
    })

    const trigger = page.locator('.app-shell-user-trigger').first()
    await expect(trigger).toBeVisible({ timeout: 15000 })
    await trigger.click()
    const signOut = page.locator('.app-shell-account-link--danger').first()
    await expect(signOut).toBeVisible({ timeout: 10000 })
    await signOut.click()
    await expect(page).toHaveURL(/auth\/login/, { timeout: 30000 })

    const snapshots = await page.evaluate(() => ({
        workspace: sessionStorage.getItem('websoft9:terminal-workspace-v1'),
        accessChoice: localStorage.getItem('websoft9:sftp-access-choice'),
    }))
    expect(snapshots.workspace).toBeNull()
    expect(snapshots.accessChoice).toBeNull()

    // The server side session is gone as well.
    await expect.poll(async () => (await page.request.get('/api/host-access/profile')).status(), { timeout: 10000 }).toBe(401)
})

test('administrator mode requires an authenticated session', async ({ page }) => {
    await apiLogin(page)
    const response = await page.request.get('/api/host-access/files/elevation?scope=app&app_id=demo&volume_id=data')
    expect([200, 400]).toContain(response.status())
    expect(response.status()).not.toBe(500)

    await page.request.post('/api/auth/logout')
    const anonymous = await page.request.get('/api/host-access/files/elevation')
    expect(anonymous.status()).toBe(401)
})
