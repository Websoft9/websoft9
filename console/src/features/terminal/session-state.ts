/**
 * Pure helpers for terminal workspace state.
 *
 * They live outside the page component so the rules that caused real regressions
 * (silently switching accounts, shared Terminal/Files view, restoring another
 * operator's sessions) can be unit-tested without a browser.
 */

export type SftpAccessChoice = { mode: 'platform' } | { mode: 'profile'; profileId: string }
export type WorkspaceView = 'terminal' | 'files'

/**
 * Decide which account an application file session should use.
 *
 * An explicit choice always wins. Otherwise the remembered choice is reused so a
 * fresh page never falls back to the default (often automatic) local account.
 */
export function resolveAppFileAccess(options: {
    profileId?: string
    platform?: boolean
    remembered: SftpAccessChoice | null
}): { profileId: string | undefined; usePlatform: boolean } {
    const { profileId, platform, remembered } = options
    const explicitPlatform = Boolean(platform)
    const resolvedProfileId = profileId || (!explicitPlatform && remembered?.mode === 'profile' ? remembered.profileId : undefined)
    const usePlatform = explicitPlatform || (!profileId && remembered?.mode === 'platform')
    return { profileId: resolvedProfileId, usePlatform }
}

/**
 * Whether a stored application file session already belongs to the requested
 * account. A platform session carries no profile id, so `null` and `undefined`
 * must be treated as the same account instead of triggering a replacement.
 * When no account is requested at all the stored snapshot owns the tab.
 */
export function sessionUsesAppFileAccess(
    session: { profile_id?: string | null } | null | undefined,
    access: { profileId?: string; usePlatform: boolean },
): boolean {
    if (!session) return false
    const savedProfileId = session.profile_id || undefined
    if (access.usePlatform) return !savedProfileId
    if (!access.profileId) return true
    return savedProfileId === access.profileId
}

/**
 * Whether a stale "ended" snapshot may be reported as unavailable.
 *
 * Stored snapshots outlive the server session (restart, 30 minute expiry, a
 * closed connection), so an ended entry alone proves nothing: the view must
 * report it only after it was actually open. Reporting it while the reopen
 * attempt is still running aborts that attempt and leaves the operator on an
 * error even though the connection works.
 */
export function shouldReportAppFileUnavailable(options: {
    isAppFiles: boolean
    accessReady: boolean
    status?: string | null
}): boolean {
    return options.isAppFiles && options.accessReady && options.status === 'ended'
}

/**
 * Each connection keeps its own Terminal/Files selection; application files are
 * always shown as files.
 */
export function resolveSessionView(views: Record<string, WorkspaceView>, sessionId: string | null | undefined, isAppFiles: boolean): WorkspaceView {
    if (isAppFiles) return 'files'
    if (!sessionId) return 'terminal'
    return views[sessionId] ?? 'terminal'
}

/** A persisted workspace only belongs to the operator encoded in its scope. */
export function shouldRestoreWorkspace(profileScope: string | null | undefined, operatorId: string | null | undefined): boolean {
    if (!profileScope || !operatorId) return false
    return profileScope.startsWith(`${operatorId}:`)
}
