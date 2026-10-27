import { expect, test } from '@playwright/test'

import { resolveAppFileAccess, resolveSessionView, shouldRestoreWorkspace } from '../../src/features/terminal/session-state'

test.describe('application file access resolution', () => {
    test('an explicit connection always wins', () => {
        const access = resolveAppFileAccess({ profileId: 'chosen', remembered: { mode: 'profile', profileId: 'old' } })
        expect(access).toEqual({ profileId: 'chosen', usePlatform: false })
    })

    test('an explicit platform choice is never replaced by a remembered connection', () => {
        const access = resolveAppFileAccess({ platform: true, remembered: { mode: 'profile', profileId: 'old' } })
        expect(access).toEqual({ profileId: undefined, usePlatform: true })
    })

    test('a fresh page reuses the remembered connection instead of the default account', () => {
        const access = resolveAppFileAccess({ remembered: { mode: 'profile', profileId: 'sftpadmin' } })
        expect(access).toEqual({ profileId: 'sftpadmin', usePlatform: false })
    })

    test('a remembered platform choice opens the dedicated account', () => {
        const access = resolveAppFileAccess({ remembered: { mode: 'platform' } })
        expect(access).toEqual({ profileId: undefined, usePlatform: true })
    })

    test('without any memory nothing is invented', () => {
        expect(resolveAppFileAccess({ remembered: null })).toEqual({ profileId: undefined, usePlatform: false })
    })
})

test.describe('terminal/files view per connection', () => {
    test('application files are always the file view', () => {
        expect(resolveSessionView({ a: 'terminal' }, 'a', true)).toBe('files')
    })

    test('each connection restores its own view', () => {
        const views = { a: 'terminal', b: 'files' } as const
        expect(resolveSessionView(views, 'a', false)).toBe('terminal')
        expect(resolveSessionView(views, 'b', false)).toBe('files')
    })

    test('unknown connection defaults to the terminal view', () => {
        expect(resolveSessionView({}, 'new-session', false)).toBe('terminal')
        expect(resolveSessionView({}, null, false)).toBe('terminal')
    })
})

test.describe('workspace ownership', () => {
    test('only the same operator may restore a workspace', () => {
        expect(shouldRestoreWorkspace('operator-1:profile:host:user', 'operator-1')).toBe(true)
        expect(shouldRestoreWorkspace('operator-2:profile:host:user', 'operator-1')).toBe(false)
        expect(shouldRestoreWorkspace('', 'operator-1')).toBe(false)
        expect(shouldRestoreWorkspace('operator-1:profile', null)).toBe(false)
    })
})
