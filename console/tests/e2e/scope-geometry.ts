import type { Page } from '@playwright/test'

/**
 * Geometry helpers shared by the content-scoped overlay regressions.
 *
 * Content-scoped overlays are portalled to `document.body` and positioned with fixed pixel
 * coordinates measured from `#app-shell-main`, so "does the overlay still match the live content
 * area?" is the single assertion every one of these tests needs.
 */

export type Geometry = { top: number; left: number; width: number; height: number }

export type ScopeSnapshot = {
    main: Geometry
    overlay: Geometry
    delta: number
}

/**
 * Compares the content area with the fixed host of `overlaySelector`.
 *
 * The selector may point at the fixed element itself or at something inside it; the closest fixed
 * ancestor wins. `delta` is the largest difference in pixels, so `delta <= 1` means "the overlay
 * tracks the content area".
 */
export async function measureScope(page: Page, overlaySelector: string): Promise<ScopeSnapshot | null> {
    return page.evaluate((selector) => {
        const read = (element: Element) => {
            const rect = element.getBoundingClientRect()
            return { top: rect.top, left: rect.left, width: rect.width, height: rect.height }
        }

        const main = document.querySelector('#app-shell-main')
        const overlay = document.querySelector(selector)
        if (!main || !overlay) {
            return null
        }

        let host: Element | null = overlay
        while (host && getComputedStyle(host).position !== 'fixed') {
            host = host.parentElement
        }
        if (!host) {
            return null
        }

        const mainRect = read(main)
        const overlayRect = read(host)

        return {
            main: mainRect,
            overlay: overlayRect,
            delta: Math.max(
                Math.abs(mainRect.top - overlayRect.top),
                Math.abs(mainRect.left - overlayRect.left),
                Math.abs(mainRect.width - overlayRect.width),
                Math.abs(mainRect.height - overlayRect.height),
            ),
        }
    }, overlaySelector)
}

/** Polling value used with `expect.poll`: the delta, or -1 while the overlay is not ready. */
export async function currentDelta(page: Page, overlaySelector: string): Promise<number> {
    return (await measureScope(page, overlaySelector))?.delta ?? -1
}
