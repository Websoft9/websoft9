import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { IntegrationKey, IntegrationStatus } from './integration-model'

type IntegrationSessionState = 'idle' | 'bootstrapping' | 'ready' | 'error'

type IntegrationSessionResult = {
    errorMessage: string | null
    requestKey: string
    sessionState: Exclude<IntegrationSessionState, 'idle' | 'bootstrapping'>
}

const integrationSessionCache = new Map<string, IntegrationSessionResult>()

export function useIntegrationSession(
    integrationKey: IntegrationKey,
    integrationStatus: IntegrationStatus,
    refreshToken: string | null,
    enabled = true,
) {
    const { i18n } = useTranslation('shell')
    const [result, setResult] = useState<IntegrationSessionResult | null>(null)
    const canBootstrap = integrationStatus === 'available' || integrationStatus === 'session-error'
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const requestKey = `${integrationKey}:${integrationStatus}:${refreshToken ?? 'initial'}:${locale}`

    useEffect(() => {
        if (!enabled || !canBootstrap) {
            return
        }

        const cachedResult = integrationSessionCache.get(requestKey)
        if (cachedResult) {
            setResult(cachedResult)
            return
        }

        const abortController = new AbortController()

        void fetch(`/api/integrations/${integrationKey}/session`, {
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
                integrationSessionCache.set(requestKey, nextResult)
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
                integrationSessionCache.set(requestKey, nextResult)
                setResult(nextResult)
            })

        return () => {
            abortController.abort()
        }
    }, [canBootstrap, enabled, integrationKey, locale, requestKey])

    const currentResult = result?.requestKey === requestKey ? result : null

    return {
        errorMessage: enabled && canBootstrap ? currentResult?.errorMessage ?? null : null,
        sessionState: !enabled || !canBootstrap ? 'idle' : currentResult?.sessionState ?? 'bootstrapping',
    }
}