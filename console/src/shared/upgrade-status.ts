import { useEffect, useState } from 'react'

export type UpgradeFailure = {
    run_id?: string | null
    /** Machine-readable cause; the console maps it to a plain-language explanation. */
    reason?: string | null
    detail?: string | null
    exit_code?: number | null
    target_version?: string | null
    at?: string | null
    log_path?: string | null
}

export type UpgradePhase = 'prepare' | 'replace' | 'verify'

export type UpgradeStatus = {
    current_version: string
    latest_version: string
    channel: string
    upgrade_available: boolean
    run_id?: string | null
    state?: string
    phase?: UpgradePhase | null
    target_version?: string | null
    detail?: string | null
    /** Cause recorded by the upgrade runner for a terminal failure. */
    reason?: string | null
    exit_code?: number | null
    updated_at?: string | null
    last_failure?: UpgradeFailure | null
    install_command: string
    artifact_url: string
    doc_url: string
}

export type UpgradeLog = {
    run_id: string
    /** file: upgrade log, runner: upgrade runner output, missing: nothing left to show. */
    source: 'file' | 'runner' | 'missing'
    path: string
    lines: string[]
}

/** Poll rapidly only while work is active, and otherwise refresh a pending update unobtrusively. */
export function getUpgradeStatusRefetchInterval(status: UpgradeStatus | undefined): number | false {
    if (status?.state === 'downloading' || status?.state === 'applying') {
        return 2_000
    }
    return status?.upgrade_available && status.state !== 'ready' ? 15_000 : false
}

/** Retry the last failed upgrade using the release that is already staged. */
export async function retryUpgrade(): Promise<UpgradeStatus> {
    const response = await fetch('/api/settings/upgrade/retry', {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { details?: string; message?: string }
        throw new Error(payload.details || payload.message || `Failed to retry the upgrade: ${response.status}`)
    }
    return (await response.json()) as UpgradeStatus
}

/** Shared by the shell notice and the settings module so both read the same cache. */
export const UPGRADE_STATUS_QUERY_KEY = ['upgrade-status']

/** Settings module that owns the upgrade controls, targeted by the shell notice. */
export const UPGRADE_SECTION_HASH = '#version-and-upgrade'

export async function fetchUpgradeStatus(): Promise<UpgradeStatus> {
    const response = await fetch('/api/settings/upgrade/status', {
        credentials: 'include',
        headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
        throw new Error(`Failed to load upgrade status: ${response.status}`)
    }
    return (await response.json()) as UpgradeStatus
}

/** Force a fresh release check; the caller re-reads the status afterwards. */
export async function checkUpgrade(): Promise<void> {
    const response = await fetch('/api/settings/upgrade/check', {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
        throw new Error(`Failed to check for updates: ${response.status}`)
    }
}

/** Read the tail of an upgrade log or the platform container output. */
export async function fetchUpgradeLog(runId: string, tail = 200, source: 'upgrade' | 'platform' = 'upgrade'): Promise<UpgradeLog> {
    const response = await fetch(`/api/settings/upgrade/logs?run_id=${encodeURIComponent(runId)}&tail=${tail}&source=${source}`, {
        credentials: 'include',
        headers: { Accept: 'application/json' },
    })
    if (!response.ok) {
        throw new Error(`Failed to load the upgrade log: ${response.status}`)
    }
    return (await response.json()) as UpgradeLog
}

/**
 * Marks an upgrade (or its rollback) as running for the whole console.
 *
 * An upgrade necessarily recreates the platform container, so every API call fails for a few
 * seconds. The global connection banner would report that as "service unavailable" on top of the
 * upgrade mask, which reads like a second, unexplained incident. The mask already explains the
 * interruption, so the banner stays quiet while the upgrade owns the screen.
 */
let upgradeInProgress = false
const upgradeInProgressListeners = new Set<(active: boolean) => void>()

export function setUpgradeInProgress(active: boolean): void {
    if (upgradeInProgress === active) {
        return
    }
    upgradeInProgress = active
    upgradeInProgressListeners.forEach((listener) => listener(active))
}

export function useUpgradeInProgress(): boolean {
    const [active, setActive] = useState(upgradeInProgress)
    useEffect(() => {
        upgradeInProgressListeners.add(setActive)
        setActive(upgradeInProgress)
        return () => {
            upgradeInProgressListeners.delete(setActive)
        }
    }, [])
    return active
}

/** One-shot marker: the upgrade reloads the console, so the shell greets the operator once. */
export const UPGRADE_COMPLETED_NOTICE_KEY = 'websoft9.upgrade.completed'

export function rememberCompletedUpgrade(version: string): void {
    try {
        window.sessionStorage.setItem(UPGRADE_COMPLETED_NOTICE_KEY, version)
    } catch {
        // Storage can be unavailable; the notice is a nicety, never a requirement.
    }
}

export function takeCompletedUpgradeNotice(): string | null {
    try {
        const version = window.sessionStorage.getItem(UPGRADE_COMPLETED_NOTICE_KEY)
        if (version) {
            window.sessionStorage.removeItem(UPGRADE_COMPLETED_NOTICE_KEY)
        }
        return version
    } catch {
        return null
    }
}
