import { expect, test, type Page } from '@playwright/test'

import { currentDelta, measureScope } from './scope-geometry'

/**
 * The same content-scoped overlay rule as the app store, for an installed application's detail page.
 *
 * This page is rendered through a child route (`/myapps/:appId`) inside the shell, so its overlay is
 * a sibling of the content area rather than a child of it. It therefore has its own copy of the
 * "measure the content area and follow it" logic and its own regression test - plus a check that the
 * layout switches through the container query instead of the viewport.
 */

const username = process.env.W9_USER || 'websoft9'
const password = process.env.W9_PASSWORD || 'Websoft9@'

const OVERLAY = '.myapps-detail-overlay'
// 1000px 视口下内容列约 780px,正好落在容器查询的 820px 断点内侧;
// 再窄会切到移动端外壳,那是另一套布局,不在本用例范围内。
const NARROW_VIEWPORT = 1000

async function apiLogin(page: Page) {
    const response = await page.request.post('/api/auth/login', { data: { username, password } })
    expect(response.ok(), `login failed: ${response.status()}`).toBeTruthy()
}

/** Picks an installed application from the API so the test does not depend on a fixture name. */
async function firstInstalledAppId(page: Page): Promise<string> {
    const response = await page.request.get('/api/apps')
    expect(response.ok(), `cannot list apps: ${response.status()}`).toBeTruthy()
    const apps = (await response.json()) as Array<{ app_id?: string }>
    const appId = apps.map((app) => app.app_id).find((value): value is string => Boolean(value))
    expect(appId, 'the platform has no installed application to open').toBeTruthy()
    return appId as string
}

async function openDetail(page: Page, width: number) {
    await page.setViewportSize({ width, height: 900 })
    await apiLogin(page)
    const appId = await firstInstalledAppId(page)
    await page.goto(`/myapps/${appId}`)
    await expect(page.locator(OVERLAY).first()).toBeVisible({ timeout: 30000 })
    return appId
}

test('an open application detail follows the content area on resize and on sidebar collapse', async ({ page }) => {
    await openDetail(page, 1400)
    await expect.poll(() => currentDelta(page, OVERLAY), { timeout: 15000 }).toBeLessThanOrEqual(1)

    const wide = await measureScope(page, OVERLAY)
    expect(wide).not.toBeNull()

    // 1. Window resize (the original bug report).
    await page.setViewportSize({ width: NARROW_VIEWPORT, height: 900 })
    await expect.poll(async () => {
        const snapshot = await measureScope(page, OVERLAY)
        if (!snapshot) {
            return -1
        }
        return snapshot.main.width < wide!.main.width - 100 ? snapshot.delta : -1
    }, { timeout: 15000 }).toBeLessThanOrEqual(1)

    await page.setViewportSize({ width: 1400, height: 900 })
    await expect.poll(async () => {
        const snapshot = await measureScope(page, OVERLAY)
        if (!snapshot) {
            return -1
        }
        return Math.abs(snapshot.main.width - wide!.main.width) < 5 ? snapshot.delta : -1
    }, { timeout: 15000 }).toBeLessThanOrEqual(1)

    // 2. Layout change without any window resize: only an observed element notices this.
    const collapseButton = page.locator('.app-shell-nav-item--collapse')
    await expect(collapseButton).toBeVisible({ timeout: 15000 })
    await collapseButton.click()

    await expect.poll(async () => {
        const snapshot = await measureScope(page, OVERLAY)
        if (!snapshot) {
            return -1
        }
        return snapshot.main.width > wide!.main.width + 50 ? snapshot.delta : -1
    }, { timeout: 15000 }).toBeLessThanOrEqual(1)

    await collapseButton.click()
    await expect.poll(async () => {
        const snapshot = await measureScope(page, OVERLAY)
        if (!snapshot) {
            return -1
        }
        return Math.abs(snapshot.main.width - wide!.main.width) < 5 ? snapshot.delta : -1
    }, { timeout: 15000 }).toBeLessThanOrEqual(1)
})

test('the application detail switches to a stacked layout through the container query', async ({ page }) => {
    await openDetail(page, 1400)
    const layout = page.locator('.myapps-detail-layout').first()
    await expect(layout).toBeVisible({ timeout: 30000 })

    // 宽内容列:侧栏 + 内容两栏并排
    await expect.poll(async () => layout.evaluate((element) => getComputedStyle(element).flexDirection), {
        timeout: 15000,
    }).toBe('row')

    await page.setViewportSize({ width: NARROW_VIEWPORT, height: 900 })

    // 窄内容列:容器查询切成单列,导航占满整行
    await expect.poll(async () => layout.evaluate((element) => getComputedStyle(element).flexDirection), {
        timeout: 15000,
    }).toBe('column')

    const narrow = await page.evaluate(() => {
        const layoutElement = document.querySelector('.myapps-detail-layout') as HTMLElement
        const navColumn = document.querySelector('.myapps-detail-nav-col') as HTMLElement
        const shell = document.querySelector('.myapps-detail-shell') as HTMLElement
        return {
            layoutWidth: layoutElement.getBoundingClientRect().width,
            navWidth: navColumn.getBoundingClientRect().width,
            overflow: shell.scrollWidth - shell.clientWidth,
        }
    })

    expect(narrow.navWidth).toBeGreaterThan(narrow.layoutWidth - 2)
    // 变窄后不能出现横向滚动条:宽表格改为在自身容器内横向滚动
    expect(narrow.overflow).toBeLessThanOrEqual(1)
})
