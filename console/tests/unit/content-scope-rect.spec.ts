import { expect, test } from '@playwright/test'

import { isSameScopeRect } from '../../src/shared/hooks/useContentScopeRect'

/**
 * The content-scope rectangle drives every content-scoped overlay. Two rules matter and both are
 * cheap to break:
 *  - a rectangle that did not change must keep the previous object, otherwise continuous resizing
 *    re-renders the whole page on every animation frame;
 *  - any pixel change (position or size) must be reported, otherwise a dialog keeps stale geometry.
 */

const base = { top: 56, left: 220, width: 900, height: 640 }

test.describe('content scope rectangle comparison', () => {
    test('identical measurements are treated as unchanged', () => {
        expect(isSameScopeRect(base, { ...base })).toBe(true)
    })

    test('a sidebar collapse that only moves and widens the area counts as a change', () => {
        expect(isSameScopeRect(base, { ...base, left: 68, width: 1052 })).toBe(false)
    })

    test('a window resize that only changes the width counts as a change', () => {
        expect(isSameScopeRect(base, { ...base, width: 640 })).toBe(false)
    })

    test('a scroll or header change that only moves the area counts as a change', () => {
        expect(isSameScopeRect(base, { ...base, top: 40, height: 656 })).toBe(false)
    })

    test('a sub-pixel difference still counts as a change', () => {
        expect(isSameScopeRect(base, { ...base, width: base.width + 0.5 })).toBe(false)
    })

    test('two missing measurements are unchanged and a first measurement is a change', () => {
        expect(isSameScopeRect(null, null)).toBe(true)
        expect(isSameScopeRect(null, base)).toBe(false)
        expect(isSameScopeRect(base, null)).toBe(false)
    })
})
