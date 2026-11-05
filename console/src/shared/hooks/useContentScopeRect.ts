import { useCallback, useLayoutEffect, useState } from 'react'

/**
 * Rectangle of the console content area, expressed in viewport coordinates.
 */
export type ContentScopeRect = {
    top: number
    left: number
    width: number
    height: number
}

const CONTENT_SCOPE_SELECTOR = '#app-shell-main'
const VISUAL_VIEWPORT_EVENTS = ['resize', 'scroll'] as const

/**
 * Resolves the console content area every content-scoped overlay is aligned to.
 */
export function getContentScopeContainer(): HTMLElement | null {
    if (typeof document === 'undefined') {
        return null
    }

    return document.querySelector<HTMLElement>(CONTENT_SCOPE_SELECTOR)
}

function readScopeRect(element: HTMLElement | null): ContentScopeRect | null {
    if (!element) {
        return null
    }

    const rect = element.getBoundingClientRect()

    return {
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
    }
}

/**
 * Reports whether two measurements describe the same rectangle.
 *
 * Exported so the de-duplication rule (which keeps continuous resizing from re-rendering on every
 * pixel) can be asserted without a DOM.
 */
export function isSameScopeRect(left: ContentScopeRect | null, right: ContentScopeRect | null) {
    if (!left || !right) {
        return left === right
    }

    return left.top === right.top && left.left === right.left && left.width === right.width && left.height === right.height
}

/**
 * Keeps a live viewport rectangle for the console content area.
 *
 * Content-scoped overlays are portalled to `document.body` and positioned with fixed pixel
 * coordinates read from that rectangle, so a snapshot taken once can never follow the layout:
 * an already open dialog kept its old geometry after the window was resized and only looked
 * right after being closed and reopened. A `window.resize` listener is not enough either -
 * collapsing the sidebar, a scrollbar appearing or a browser zoom change can move or resize
 * the content area without resizing the window. Observing the element itself covers all of
 * those cases; measurements are coalesced into one animation frame and skipped when the
 * rectangle did not actually change, so continuous resizing does not re-render on every pixel.
 */
export function useContentScopeRect(element: HTMLElement | null) {
    const [rect, setRect] = useState<ContentScopeRect | null>(null)

    const refresh = useCallback(() => {
        const next = readScopeRect(element)
        setRect((previous) => (isSameScopeRect(previous, next) ? previous : next))
    }, [element])

    useLayoutEffect(() => {
        if (typeof window === 'undefined') {
            return
        }

        // Measure before the first paint so an overlay opened right after mount is not misplaced.
        refresh()

        let frame: number | null = null

        const scheduleRefresh = () => {
            if (frame !== null) {
                return
            }

            frame = window.requestAnimationFrame(() => {
                frame = null
                refresh()
            })
        }

        const resizeObserver = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(scheduleRefresh)
        if (element) {
            resizeObserver?.observe(element)
        }

        window.addEventListener('resize', scheduleRefresh)
        // Mobile browser chrome and pinch zoom resize the visual viewport without resizing the window.
        for (const eventName of VISUAL_VIEWPORT_EVENTS) {
            window.visualViewport?.addEventListener(eventName, scheduleRefresh)
        }

        return () => {
            resizeObserver?.disconnect()
            window.removeEventListener('resize', scheduleRefresh)
            for (const eventName of VISUAL_VIEWPORT_EVENTS) {
                window.visualViewport?.removeEventListener(eventName, scheduleRefresh)
            }

            if (frame !== null) {
                window.cancelAnimationFrame(frame)
                frame = null
            }
        }
    }, [element, refresh])

    return { rect, refresh }
}
