import { expect, test, type Page } from '@playwright/test'

/**
 * Real UI regression: every connection keeps its own Terminal/Files view, and
 * switching tabs must not flash an empty pane.
 */

const username = process.env.W9_USER || 'websoft9'
const password = process.env.W9_PASSWORD || 'Websoft9@'

async function apiLogin(page: Page) {
    const response = await page.request.post('/api/auth/login', { data: { username, password } })
    expect(response.ok(), `login failed: ${response.status()}`).toBeTruthy()
}

function connectableRows(page: Page) {
    return page.locator('.terminal-connections-table-row').filter({ has: page.locator('button.terminal-connections-row-action-button-primary') })
}

async function openHostList(page: Page) {
    await page.locator('button', { hasText: '主机列表' }).first().click()
    await expect(connectableRows(page).first()).toBeVisible({ timeout: 15000 })
}

async function connectProfiles(page: Page, count: number) {
    let opened = 0
    for (let index = 0; index < count; index += 1) {
        await openHostList(page)
        const rows = connectableRows(page)
        if (await rows.count() <= index) break
        await rows.nth(index).locator('button.terminal-connections-row-action-button-primary').click()
        opened += 1
        await page.waitForTimeout(2000)
    }
    return opened
}

async function firstApplicationVolume(page: Page): Promise<{ appId: string; volumeId: string } | null> {
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

test('switching tabs never drops a tab', async ({ page }) => {
    await apiLogin(page)
    const target = await firstApplicationVolume(page)
    test.skip(!target, 'needs an application volume on this host')

    // Open the application file tab first and remember its session.
    await page.goto(`/terminal?${new URLSearchParams({ app_file_app: target!.appId, app_file_volume: target!.volumeId })}`)
    await expect(page.locator('.terminal-session-tab:visible').first()).toBeVisible({ timeout: 20000 })
    const staleId = await page.evaluate(() => {
        const raw = sessionStorage.getItem('websoft9:app-files-sessions')
        const entries = raw ? JSON.parse(raw) as Array<{ session_id?: string }> : []
        return entries[0]?.session_id || ''
    })
    expect(staleId).not.toBe('')

    // Then add a terminal tab from the host workspace.
    await page.goto('/terminal')
    await expect(page.locator('body')).toContainText('终端', { timeout: 15000 })
    const opened = await connectProfiles(page, 1)
    test.skip(opened < 1, 'needs a saved connection on this host')
    await page.keyboard.press('Escape')

    // The server forgets this session (restart) while the tab stays on screen.
    await page.request.delete(`/api/host-access/app-files/${staleId}/session`)
    await page.evaluate(() => {
        const key = 'websoft9:app-files-sessions'
        const raw = sessionStorage.getItem(key)
        const entries = raw ? JSON.parse(raw) as Array<Record<string, unknown>> : []
        if (entries.length) {
            entries[0].verified_at = 0
            entries[0].status = 'connected'
            sessionStorage.setItem(key, JSON.stringify(entries))
        }
    })
    await page.reload()
    await expect(page.locator('.terminal-session-tab:visible').first()).toBeVisible({ timeout: 20000 })

    const visibleTabs = page.locator('.terminal-session-tab:visible')
    const initial = await visibleTabs.count()
    expect(initial).toBeGreaterThanOrEqual(2)

    await page.evaluate(() => {
        const counts: number[] = []
        ;(window as unknown as { __tabCounts: number[] }).__tabCounts = counts
        const read = () => Array.from(document.querySelectorAll('.terminal-session-tab')).filter((node) => (node as HTMLElement).offsetParent !== null).length
        counts.push(read())
        const timer = setInterval(() => counts.push(read()), 50)
        ;(window as unknown as { __tabTimer: number }).__tabTimer = timer
    })

    for (let index = 0; index < initial; index += 1) {
        await visibleTabs.nth(index).click()
        await page.waitForTimeout(800)
    }

    const counts = await page.evaluate(() => {
        clearInterval((window as unknown as { __tabTimer: number }).__tabTimer)
        return (window as unknown as { __tabCounts: number[] }).__tabCounts
    })
    expect(Math.min(...counts)).toBe(initial)
    expect(await visibleTabs.count()).toBe(initial)
})

test('each connection keeps its own terminal/files view', async ({ page }) => {
    await apiLogin(page)
    await page.goto('/terminal')
    await expect(page.locator('body')).toContainText('终端', { timeout: 15000 })

    const opened = await connectProfiles(page, 2)
    test.skip(opened < 2, 'needs at least two saved connections on this host')

    await page.keyboard.press('Escape')
    const tabs = page.locator('.terminal-session-tab')
    expect(await tabs.count()).toBeGreaterThanOrEqual(2)

    // Connection 1 → Files view.
    await tabs.nth(0).click()
    await page.locator('.terminal-view-nav-button', { hasText: '文件' }).first().click()
    await expect(page.locator('.terminal-view-nav-button-active')).toHaveText('文件', { timeout: 15000 })
    await expect(page.locator('.terminal-files-shell').first()).toBeVisible({ timeout: 15000 })

    // Connection 2 keeps its own (terminal) view, with no intermediate flash.
    await page.evaluate(() => {
        const changes: string[] = []
            ; (window as unknown as { __viewChanges: string[] }).__viewChanges = changes
        const nav = document.querySelector('.terminal-view-nav')
        const observer = new MutationObserver(() => {
            const label = document.querySelector('.terminal-view-nav-button-active')?.textContent || ''
            if (changes[changes.length - 1] !== label) changes.push(label)
        })
        if (nav) observer.observe(nav, { subtree: true, attributes: true, childList: true })
    })
    await tabs.nth(1).click()
    await expect(page.locator('.terminal-view-nav-button-active')).toHaveText('终端', { timeout: 10000 })
    const transitions = await page.evaluate(() => (window as unknown as { __viewChanges: string[] }).__viewChanges)
    // One switch, never back and forth.
    expect(transitions).toEqual(['终端'])

    // Back to connection 1: still Files.
    await tabs.nth(0).click()
    await expect(page.locator('.terminal-view-nav-button-active')).toHaveText('文件', { timeout: 10000 })
})

test('tab order stays stable while switching and after a reload', async ({ page }) => {
    await apiLogin(page)
    await page.goto('/terminal')
    await expect(page.locator('body')).toContainText('终端', { timeout: 15000 })

    const opened = await connectProfiles(page, 3)
    test.skip(opened < 2, 'needs at least two saved connections on this host')
    await page.keyboard.press('Escape')

    const titles = () => page.locator('.terminal-session-tab .terminal-session-tab-title').allTextContents()
    const initial = await titles()
    expect(initial.length).toBeGreaterThanOrEqual(2)

    // Switching between tabs must not reshuffle them.
    const tabs = page.locator('.terminal-session-tab')
    for (let index = tabs ? 0 : 0; index < initial.length; index += 1) {
        await tabs.nth(index).click()
        await page.waitForTimeout(300)
    }
    expect(await titles()).toEqual(initial)

    // A page reload keeps the operator's order as well.
    await page.reload()
    await expect(page.locator('.terminal-session-tab').first()).toBeVisible({ timeout: 15000 })
    expect(await titles()).toEqual(initial)
})
