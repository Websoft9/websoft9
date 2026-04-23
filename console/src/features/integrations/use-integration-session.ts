import { useEffect, useState } from 'react'

import type { IntegrationKey, IntegrationStatus } from './integration-model'

type IntegrationSessionState = 'idle' | 'bootstrapping' | 'ready' | 'error'

type IntegrationSessionResult = {
    errorMessage: string | null
    requestKey: string
    sessionState: Exclude<IntegrationSessionState, 'idle' | 'bootstrapping'>
}

export function useIntegrationSession(integrationKey: IntegrationKey, integrationStatus: IntegrationStatus, refreshToken: string | null) {
    const [result, setResult] = useState<IntegrationSessionResult | null>(null)
    const canBootstrap = integrationStatus === 'available' || integrationStatus === 'session-error'
    const requestKey = `${integrationKey}:${integrationStatus}:${refreshToken ?? 'initial'}`

    useEffect(() => {
        if (!canBootstrap) {
            return
        }

        const abortController = new AbortController()

        void fetch(`/api/integrations/${integrationKey}/session`, {
            method: 'POST',
            credentials: 'include',
            signal: abortController.signal,
        })
            .then(async (response) => {
                if (!response.ok) {
                    const payload = (await response.json().catch(() => null)) as { details?: string; message?: string } | null
                    throw new Error(payload?.details ?? payload?.message ?? `HTTP ${response.status}`)
                }

                setResult({
                    errorMessage: null,
                    requestKey,
                    sessionState: 'ready',
                })
            })
            .catch((error: unknown) => {
                if (abortController.signal.aborted) {
                    return
                }

                setResult({
                    errorMessage: error instanceof Error ? error.message : 'Failed to establish integration session',
                    requestKey,
                    sessionState: 'error',
                })
            })

        return () => {
            abortController.abort()
        }
    }, [canBootstrap, integrationKey, requestKey])

    const currentResult = result?.requestKey === requestKey ? result : null

    return {
        errorMessage: canBootstrap ? currentResult?.errorMessage ?? null : null,
        sessionState: !canBootstrap ? 'idle' : currentResult?.sessionState ?? 'bootstrapping',
    }
}