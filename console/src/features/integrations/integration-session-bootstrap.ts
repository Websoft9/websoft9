import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

import { useProductAuth } from '../product-auth/product-auth-provider'
import type { IntegrationKey } from './integration-model'

export type IntegrationSessionState = 'idle' | 'bootstrapping' | 'ready' | 'error'

export type IntegrationSessionResult = {
    errorMessage: string | null
    requestKey: string
    sessionState: Exclude<IntegrationSessionState, 'idle' | 'bootstrapping'>
}

type BulkBootstrapPayload = {
    status: 'ok' | 'partial'
    integrations: Partial<Record<IntegrationKey, { status: 'ok' | 'error'; message?: string }>>
}

const integrationSessionCache = new Map<string, IntegrationSessionResult>()
const bulkBootstrapCache = new Map<string, Partial<Record<IntegrationKey, IntegrationSessionResult>>>()
const bulkBootstrapPromises = new Map<string, Promise<Partial<Record<IntegrationKey, IntegrationSessionResult>>>>()

function buildBulkRequestKey(locale: string, authScope: string) {
    return `${authScope}:${locale}`
}

export function prewarmAuthenticatedIntegrationSessions(locale: string, authScope: string) {
    return ensureBulkIntegrationSessionBootstrap(buildBulkRequestKey(locale, authScope), locale)
}

async function requestBulkBootstrap(locale: string) {
    const response = await fetch('/api/integrations/session', {
        method: 'POST',
        credentials: 'include',
        headers: {
            'X-Websoft9-Locale': locale,
        },
    })

    const payload = (await response.json().catch(() => null)) as
        | { details?: string; message?: string }
        | BulkBootstrapPayload
        | null

    if (!response.ok) {
        const errorMessage =
            payload && typeof payload === 'object' && 'details' in payload
                ? payload.details ?? payload.message ?? `HTTP ${response.status}`
                : `HTTP ${response.status}`
        throw new Error(errorMessage)
    }

    return payload as BulkBootstrapPayload
}

export function clearIntegrationSessionBootstrapCache() {
    integrationSessionCache.clear()
    bulkBootstrapCache.clear()
    bulkBootstrapPromises.clear()
}

export function getCachedBulkIntegrationSessionResult(requestKey: string, integrationKey: IntegrationKey) {
    return bulkBootstrapCache.get(requestKey)?.[integrationKey] ?? null
}

export function ensureBulkIntegrationSessionBootstrap(requestKey: string, locale: string) {
    const cached = bulkBootstrapCache.get(requestKey)
    if (cached) {
        return Promise.resolve(cached)
    }

    const existingPromise = bulkBootstrapPromises.get(requestKey)
    if (existingPromise) {
        return existingPromise
    }

    const nextPromise = requestBulkBootstrap(locale)
        .then((payload) => {
            const nextResults = Object.fromEntries(
                (Object.entries(payload.integrations) as Array<[IntegrationKey, { status: 'ok' | 'error'; message?: string }]>)
                    .map(([integrationKey, result]) => [
                        integrationKey,
                        {
                            errorMessage: result.status === 'error' ? result.message ?? 'Failed to establish integration session' : null,
                            requestKey,
                            sessionState: result.status === 'error' ? 'error' : 'ready',
                        } satisfies IntegrationSessionResult,
                    ]),
            ) as Partial<Record<IntegrationKey, IntegrationSessionResult>>

            bulkBootstrapCache.set(requestKey, nextResults)
            bulkBootstrapPromises.delete(requestKey)
            return nextResults
        })
        .catch((error: unknown) => {
            bulkBootstrapPromises.delete(requestKey)
            throw error
        })

    bulkBootstrapPromises.set(requestKey, nextPromise)
    return nextPromise
}

export function cacheIntegrationSessionResult(requestKey: string, result: IntegrationSessionResult) {
    integrationSessionCache.set(requestKey, result)
}

export function getCachedIntegrationSessionResult(requestKey: string) {
    return integrationSessionCache.get(requestKey) ?? null
}

export function useIntegrationSessionPrewarm() {
    const { i18n } = useTranslation('shell')
    const { status } = useProductAuth()
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const authScope = status?.authenticated && status.current_user ? status.current_user.id : null

    useEffect(() => {
        if (!authScope) {
            clearIntegrationSessionBootstrapCache()
            return
        }

        void ensureBulkIntegrationSessionBootstrap(buildBulkRequestKey(locale, authScope), locale).catch(() => {
            // Keep shell initialization non-blocking; workspace-level retry remains the fallback.
        })

        return () => {
            clearIntegrationSessionBootstrapCache()
        }
    }, [authScope, locale])
}

export function useIntegrationSessionBootstrapKey() {
    const { i18n } = useTranslation('shell')
    const { status } = useProductAuth()
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const authScope = status?.authenticated && status.current_user ? status.current_user.id : 'anonymous'

    return {
        authScope,
        bulkRequestKey: buildBulkRequestKey(locale, authScope),
        locale,
    }
}