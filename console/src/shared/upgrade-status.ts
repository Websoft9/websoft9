export type UpgradeFailure = {
    run_id?: string | null
    detail?: string | null
    at?: string | null
}

export type UpgradeStatus = {
    current_version: string
    latest_version: string
    channel: string
    upgrade_available: boolean
    run_id?: string | null
    state?: string
    target_version?: string | null
    detail?: string | null
    updated_at?: string | null
    last_failure?: UpgradeFailure | null
    install_command: string
    artifact_url: string
    doc_url: string
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
