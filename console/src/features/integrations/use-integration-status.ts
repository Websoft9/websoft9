import { useEffect, useMemo, useState } from 'react'

import {
    classifyIntegrationStatus,
    type IntegrationDefinition,
    integrationDefinitions,
    type IntegrationKey,
    type IntegrationStatus,
} from './integration-model'

export type IntegrationStatusSnapshot = {
    checkedAt: string | null
    httpStatus: number | null
    probeUrl: string | null
    status: IntegrationStatus
}

const integrationKeys = integrationDefinitions.map((definition) => definition.key)

const loadingSnapshot: IntegrationStatusSnapshot = {
    checkedAt: null,
    httpStatus: null,
    probeUrl: null,
    status: 'loading',
}

function createFailureSnapshot(status: IntegrationStatus): IntegrationStatusSnapshot {
    return {
        checkedAt: new Date().toISOString(),
        httpStatus: null,
        probeUrl: null,
        status,
    }
}

function containsAuthMarkers(definition: IntegrationDefinition, body: string, resolvedUrl: string) {
    return (
        definition.authPaths.some((path) => resolvedUrl.includes(path)) ||
        definition.authMarkers.some((marker) => body.includes(marker))
    )
}

async function probeIntegration(definition: IntegrationDefinition, signal: AbortSignal) {
    const response = await fetch(definition.probePath, {
        method: 'GET',
        redirect: 'follow',
        signal,
    })

    const body = await response.text()
    const resolvedUrl = response.url || definition.probePath
    const status =
        response.ok && containsAuthMarkers(definition, body, resolvedUrl)
            ? ('session-error' satisfies IntegrationStatus)
            : classifyIntegrationStatus(response)

    return {
        checkedAt: new Date().toISOString(),
        httpStatus: response.status,
        probeUrl: resolvedUrl,
        status,
    } satisfies IntegrationStatusSnapshot
}

export function useIntegrationStatuses(scope: IntegrationKey[] = integrationKeys) {
    const [refreshNonce, setRefreshNonce] = useState(0)
    const [snapshots, setSnapshots] = useState<Record<IntegrationKey, IntegrationStatusSnapshot>>({
        gitea: loadingSnapshot,
        portainer: loadingSnapshot,
        npm: loadingSnapshot,
    })

    useEffect(() => {
        const abortController = new AbortController()
        const scopedDefinitions = integrationDefinitions.filter((definition) => scope.includes(definition.key))

        void Promise.all(
            scopedDefinitions.map(async (definition) => {
                try {
                    const snapshot = await probeIntegration(definition, abortController.signal)
                    return [definition.key, snapshot] as const
                } catch {
                    if (abortController.signal.aborted) {
                        return [definition.key, loadingSnapshot] as const
                    }

                    return [
                        definition.key,
                        createFailureSnapshot('unavailable'),
                    ] as const
                }
            }),
        ).then((entries) => {
            setSnapshots((current) => ({
                ...current,
                ...Object.fromEntries(entries),
            }))
        })

        return () => {
            abortController.abort()
        }
    }, [refreshNonce, scope])

    return useMemo(
        () => ({
            refresh: () => {
                setSnapshots({
                    gitea: loadingSnapshot,
                    portainer: loadingSnapshot,
                    npm: loadingSnapshot,
                })
                setRefreshNonce((current) => current + 1)
            },
            snapshots,
        }),
        [snapshots],
    )
}