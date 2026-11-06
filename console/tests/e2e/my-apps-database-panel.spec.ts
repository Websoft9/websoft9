import { expect, test, type Page } from '@playwright/test'

/**
 * The database section of the "Data" tab renders whatever the installed app
 * declares in `variables.json` (`database[]`).
 *
 * Installations created before that contract have no declaration, and the page
 * keeps its previous rendering for them. This spec therefore looks for an app
 * that does declare components and skips when the platform has none, so it only
 * runs once the library ships declarations.
 */

const username = process.env.W9_USER || 'websoft9'
const password = process.env.W9_PASSWORD || 'Websoft9@'

const OVERLAY = '.myapps-detail-overlay'
const RESOLVED_TABLE = '.myapps-database-table-resolved'
const LEGACY_TABLE = '.myapps-database-table:not(.myapps-database-table-resolved)'
const DATA_TAB = /数据|Data/

async function login(page: Page): Promise<void> {
    const response = await page.request.post('/api/auth/login', { data: { username, password } })
    expect(response.ok(), `login failed: ${response.status()}`).toBeTruthy()
}

async function declaredAppId(page: Page): Promise<string | null> {
    const response = await page.request.get('/api/apps')
    expect(response.ok(), `cannot list apps: ${response.status()}`).toBeTruthy()
    const apps = (await response.json()) as Array<{ app_id?: string }>
    for (const app of apps) {
        if (!app.app_id) continue
        const databases = await page.request.get(`/api/apps/${encodeURIComponent(app.app_id)}/databases`)
        if (!databases.ok()) continue
        const payload = (await databases.json()) as { declaration?: string; components?: unknown[] }
        if (payload.declaration === 'v2' && (payload.components ?? []).length > 0) {
            return app.app_id
        }
    }
    return null
}

test('the data tab renders the database components an app declares', async ({ page }) => {
    // The detail page and the declaration endpoint both talk to Gitea, Portainer
    // and the docker socket, so a cold backend easily exceeds the default budget.
    test.setTimeout(120_000)
    await page.setViewportSize({ width: 1400, height: 1000 })
    await login(page)

    const appId = await declaredAppId(page)
    test.skip(appId === null, 'no installed application declares database[] yet')

    await page.goto(`/myapps/${appId}`)
    await expect(page.locator(OVERLAY).first()).toBeVisible({ timeout: 30000 })
    await page.getByRole('button', { name: DATA_TAB }).click()

    const table = page.locator(RESOLVED_TABLE)
    await expect(table.first()).toBeVisible({ timeout: 15000 })

    // The host column explains itself instead of relying on the old "address"
    // wording, and unresolved values degrade to an em dash rather than a guess.
    await expect(table.locator('thead')).toContainText(/主机|Host/)
    await expect(table.locator('thead')).toContainText(/端口|Port/)
    expect((await table.locator('tbody tr').count()) > 0).toBeTruthy()
})

test('the legacy table never flashes while the declaration is loading', async ({ page }) => {
    test.setTimeout(120_000)
    await page.setViewportSize({ width: 1400, height: 1000 })
    await login(page)

    const appId = await declaredAppId(page)
    test.skip(appId === null, 'no installed application declares database[] yet')

    // The declaration comes from a separate endpoint that talks to Gitea,
    // Portainer and the container runtime, so it always answers long after the
    // app detail itself. Holding it back makes the loading window observable.
    await page.route('**/api/apps/*/databases*', async (route) => {
        await new Promise((resolve) => setTimeout(resolve, 4000))
        await route.continue()
    })

    await page.goto(`/myapps/${appId}`)
    await expect(page.locator(OVERLAY).first()).toBeVisible({ timeout: 30000 })

    const dataTab = page.getByRole('button', { name: DATA_TAB }).first()
    await dataTab.waitFor({ state: 'visible', timeout: 15000 })
    await dataTab.click()

    // Still inside the artificial delay: nothing may claim to know the
    // configuration yet, neither the old table nor the new one.
    await expect(page.locator(RESOLVED_TABLE)).toHaveCount(0)
    await expect(page.locator(LEGACY_TABLE)).toHaveCount(0)

    // Once the declaration lands the resolved table replaces the placeholder.
    await expect(page.locator(RESOLVED_TABLE).first()).toBeVisible({ timeout: 30000 })
    await expect(page.locator(LEGACY_TABLE)).toHaveCount(0)
})
