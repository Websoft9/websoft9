import { expect, test } from '@playwright/test'

import { getAppStoreSyncFeedback, resolveAppStoreNotice } from '../../src/features/app-store/app-store-model'

test('only an explicitly successful synchronization shows green success', () => {
    expect(getAppStoreSyncFeedback('ready')).toEqual({
        severity: 'success',
        messageKey: 'appStorePage.feedback.refreshComplete',
    })
})

for (const status of ['failed', undefined, 'unknown']) {
    test(`a failed or missing result is not success: ${status}`, () => {
        expect(getAppStoreSyncFeedback(status)).toEqual({
            severity: 'error',
            messageKey: 'appStorePage.feedback.refreshFailed',
        })
    })
}

test('an unsupported contract is reported as incompatible', () => {
    expect(getAppStoreSyncFeedback('incompatible')).toEqual({
        severity: 'error',
        messageKey: 'appStorePage.feedback.upgradeRequired',
    })
})

test('a failed state request must not reuse stale success data', () => {
    expect(getAppStoreSyncFeedback('ready', true)).toEqual({
        severity: 'error',
        messageKey: 'appStorePage.feedback.refreshFailed',
    })
})

test('notice hides when sync and assets are both ready', () => {
    expect(resolveAppStoreNotice('ready', 'ready')).toBeNull()
})

test('updating assets with ready sync Status uses updating title instead of last sync failed', () => {
    expect(resolveAppStoreNotice('ready', 'updating')).toEqual({
        severity: 'warning',
        titleKey: 'appStorePage.incompatibility.assetsUpdatingTitle',
        detailKind: 'assetsUnavailable',
    })
})

test('incompatible contract keeps incompatibility detail even when no baseline is available', () => {
    expect(resolveAppStoreNotice('incompatible', 'unavailable')).toEqual({
        severity: 'error',
        titleKey: 'appStorePage.incompatibility.title',
        detailKind: 'incompatible',
    })
    expect(resolveAppStoreNotice('incompatible', 'ready')).toEqual({
        severity: 'warning',
        titleKey: 'appStorePage.incompatibility.title',
        detailKind: 'incompatible',
    })
})
