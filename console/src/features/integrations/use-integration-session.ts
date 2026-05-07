import { useEffect, useState } from 'react'

import type { IntegrationKey, IntegrationStatus } from './integration-model'
import {
    cacheIntegrationSessionResult,
    ensureBulkIntegrationSessionBootstrap,
    getCachedBulkIntegrationSessionResult,
    getCachedIntegrationSessionResult,
    type IntegrationSessionResult,
    useIntegrationSessionBootstrapKey,
} from './integration-session-bootstrap'

export function useIntegrationSession(
    integrationKey: IntegrationKey,
    integrationStatus: IntegrationStatus,
    refreshToken: string | null,
    enabled = true,
) {
    const [result, setResult] = useState<IntegrationSessionResult | null>(null)
    const { authScope, bulkRequestKey, locale } = useIntegrationSessionBootstrapKey()
    const canBootstrap = integrationStatus === 'available' || integrationStatus === 'session-error'
    const requestKey = `${integrationKey}:${integrationStatus}:${refreshToken ?? 'initial'}:${locale}:${authScope}`

    useEffect(() => {
        if (!enabled || !canBootstrap) {
            return
        }

        const cachedResult = getCachedIntegrationSessionResult(requestKey)
        if (cachedResult) {
            setResult(cachedResult)
            return
        }

        const cachedBulkResult = getCachedBulkIntegrationSessionResult(bulkRequestKey, integrationKey)
        if (cachedBulkResult?.sessionState === 'ready') {
            const nextResult = { ...cachedBulkResult, requestKey } satisfies IntegrationSessionResult
            cacheIntegrationSessionResult(requestKey, nextResult)
            setResult(nextResult)
            return
        }

        const abortController = new AbortController()

        void ensureBulkIntegrationSessionBootstrap(bulkRequestKey, locale)
            .then((bulkResults) => {
                if (abortController.signal.aborted) {
                    return
                }

                const bulkResult = bulkResults[integrationKey]
                if (bulkResult?.sessionState === 'ready') {
                    const nextResult = { ...bulkResult, requestKey } satisfies IntegrationSessionResult
                    cacheIntegrationSessionResult(requestKey, nextResult)
                    setResult(nextResult)
                    return
                }

                return fetch(`/api/integrations/${integrationKey}/session`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'X-Websoft9-Locale': locale,
                    },
                    signal: abortController.signal,
                })
                    .then(async (response) => {
                        if (!response.ok) {
                            const payload = (await response.json().catch(() => null)) as { details?: string; message?: string } | null
                            throw new Error(payload?.details ?? payload?.message ?? `HTTP ${response.status}`)
                        }

                        const nextResult = {
                            errorMessage: null,
                            requestKey,
                            sessionState: 'ready',
                        } satisfies IntegrationSessionResult
                        cacheIntegrationSessionResult(requestKey, nextResult)
                        setResult(nextResult)
                    })
                    .catch((error: unknown) => {
                        if (abortController.signal.aborted) {
                            return
                        }

                        const nextResult = {
                            errorMessage: error instanceof Error ? error.message : 'Failed to establish integration session',
                            requestKey,
                            sessionState: 'error',
                        } satisfies IntegrationSessionResult
                        cacheIntegrationSessionResult(requestKey, nextResult)
                        setResult(nextResult)
                    })
            })
            .catch(() => {
                if (abortController.signal.aborted) {
                    return
                }

                fetch(`/api/integrations/${integrationKey}/session`, {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'X-Websoft9-Locale': locale,
                    },
                    signal: abortController.signal,
                })
                    .then(async (response) => {
                        if (!response.ok) {
                            const payload = (await response.json().catch(() => null)) as { details?: string; message?: string } | null
                            throw new Error(payload?.details ?? payload?.message ?? `HTTP ${response.status}`)
                        }

                        const nextResult = {
                            errorMessage: null,
                            requestKey,
                            sessionState: 'ready',
                        } satisfies IntegrationSessionResult
                        cacheIntegrationSessionResult(requestKey, nextResult)
                        setResult(nextResult)
                    })
                    .catch((error: unknown) => {
                        if (abortController.signal.aborted) {
                            return
                        }

                        const nextResult = {
                            errorMessage: error instanceof Error ? error.message : 'Failed to establish integration session',
                            requestKey,
                            sessionState: 'error',
                        } satisfies IntegrationSessionResult
                        cacheIntegrationSessionResult(requestKey, nextResult)
                        setResult(nextResult)
                    })
            })

        return () => {
            abortController.abort()
        }
    }, [bulkRequestKey, canBootstrap, enabled, integrationKey, locale, requestKey])

    const currentResult = result?.requestKey === requestKey ? result : null

    return {
        errorMessage: enabled && canBootstrap ? currentResult?.errorMessage ?? null : null,
        sessionState: !enabled || !canBootstrap ? 'idle' : currentResult?.sessionState ?? 'bootstrapping',
    }
}