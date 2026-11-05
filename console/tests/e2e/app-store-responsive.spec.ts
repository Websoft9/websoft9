import { expect, test, type Page } from '@playwright/test'

import { currentDelta, measureScope } from './scope-geometry'

/**
 * Regression for "an already open app detail does not follow the window".
 *
 * Content-scoped overlays are portalled to `document.body` and positioned with fixed pixel
 * coordinates measured from `#app-shell-main`. The original implementation captured that rectangle
 * once when the overlay opened, so a dialog opened on a small window kept its geometry after the
 * window grew back and only looked right after being closed and reopened. The overlay must keep
 * matching the live content area in both directions - and on layout changes that never resize the
 * window at all (the sidebar collapse), which only an observed element can catch.
 */

const username = process.env.W9_USER || 'websoft9'
const password = process.env.W9_PASSWORD || 'Websoft9@'

const OVERLAY = '[role="dialog"]'

async function apiLogin(page: Page) {
    const response = await page.request.post('/api/auth/login', { data: { username, password } })
    expect(response.ok(), `login failed: ${response.status()}`).toBeTruthy()
}

test('an open app detail keeps tracking the content area when the window is resized', async ({ page }) => {
    await page.setViewportSize({ width: 1400, height: 900 })
    await apiLogin(page)
    await page.goto('/appstore?app=graylog')

    const dialog = page.locator(OVERLAY).first()
    await expect(dialog).toBeVisible({ timeout: 30000 })

    // The overlay starts aligned with the content area.
    await expect.poll(() => currentDelta(page, OVERLAY), { timeout: 15000 }).toBeLessThanOrEqual(1)
    const wide = await measureScope(page, OVERLAY)
    expect(wide).not.toBeNull()

    // Shrink the window: the overlay has to follow, not keep its original geometry.
    await page.setViewportSize({ width: 700, height: 900 })
    await expect.poll(async () => {
        const snapshot = await measureScope(page, OVERLAY)
        if (!snapshot) {
            return -1
        }
        return snapshot.main.width < wide!.main.width - 100 ? snapshot.delta : -1
    }, { timeout: 15000 }).toBeLessThanOrEqual(1)
    const narrow = await measureScope(page, OVERLAY)
    expect(narrow).not.toBeNull()
    // Guard against a frozen overlay: it must have actually shrunk, not merely matched a stale rect.
    expect(Math.abs(narrow!.overlay.width - wide!.overlay.width)).toBeGreaterThan(100)

    // Grow the window again - this is the case that used to stay frozen at the narrow geometry.
    await page.setViewportSize({ width: 1400, height: 900 })
    await expect.poll(async () => {
        const snapshot = await measureScope(page, OVERLAY)
        if (!snapshot) {
            return -1
        }
        return snapshot.main.width > narrow!.main.width + 100 ? snapshot.delta : -1
    }, { timeout: 15000 }).toBeLessThanOrEqual(1)

    const restored = await measureScope(page, OVERLAY)
    expect(restored).not.toBeNull()
    expect(Math.abs(restored!.overlay.width - wide!.overlay.width)).toBeLessThanOrEqual(1)
})

test('an open app detail follows a sidebar collapse, which never resizes the window', async ({ page }) => {
    // 这一条专门覆盖 ResizeObserver 分支:折叠侧边栏只改变内容区尺寸,不会触发 window.resize,
    // 早期版本用一次性快照实现,这里必然失败。
    await page.setViewportSize({ width: 1400, height: 900 })
    await apiLogin(page)
    await page.goto('/appstore?app=graylog')
    await expect(page.locator(OVERLAY).first()).toBeVisible({ timeout: 30000 })
    await expect.poll(() => currentDelta(page, OVERLAY), { timeout: 15000 }).toBeLessThanOrEqual(1)

    const expanded = await measureScope(page, OVERLAY)
    expect(expanded).not.toBeNull()

    const collapseButton = page.locator('.app-shell-nav-item--collapse')
    await expect(collapseButton).toBeVisible({ timeout: 15000 })
    await collapseButton.click()

    await expect.poll(async () => {
        const snapshot = await measureScope(page, OVERLAY)
        if (!snapshot) {
            return -1
        }
        return snapshot.main.width > expanded!.main.width + 50 ? snapshot.delta : -1
    }, { timeout: 15000 }).toBeLessThanOrEqual(1)

    const collapsed = await measureScope(page, OVERLAY)
    expect(collapsed).not.toBeNull()
    expect(collapsed!.overlay.width).toBeGreaterThan(expanded!.overlay.width + 50)

    // 再展开:浮层同样要跟着收回去
    await collapseButton.click()
    await expect.poll(async () => {
        const snapshot = await measureScope(page, OVERLAY)
        if (!snapshot) {
            return -1
        }
        return Math.abs(snapshot.main.width - expanded!.main.width) < 5 ? snapshot.delta : -1
    }, { timeout: 15000 }).toBeLessThanOrEqual(1)
})
