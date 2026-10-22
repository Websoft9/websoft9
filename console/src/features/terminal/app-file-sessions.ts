import { useSyncExternalStore } from 'react'

export type AppFileSession = { session_id: string; root_path: string; app_id: string; volume_id: string; profile_id: string | null; profile_available?: boolean; host?: string; username?: string; port?: number; expires_at?: number; path?: string; status?: 'connected' | 'ended'; verified_at?: number }
export const MAX_WORKSPACE_CONNECTIONS = 10
export const PLATFORM_SFTP_PROFILE_ID = 'platform-sftp'
export const TERMINAL_WORKSPACE_STORAGE_KEY = 'websoft9:terminal-workspace-v1'
export const HOST_PROFILE_DELETED_EVENT = 'websoft9:host-profile-deleted'
const SESSIONS_KEY = 'websoft9:app-files-sessions'
const LEGACY_SESSION_KEY = 'websoft9:app-files-session'
const CHANGE_EVENT = 'websoft9:app-files-sessions-changed'
const pending = new Map<string, Promise<AppFileSession>>()
const creating = new Set<string>()

export class ConnectionLimitError extends Error {
    constructor() {
        super(`Open at most ${MAX_WORKSPACE_CONNECTIONS} connections at the same time.`)
        this.name = 'ConnectionLimitError'
    }
}

export function getWorkspaceConnectionCount(terminalSessionCount?: number) {
    let terminalCount = terminalSessionCount ?? 0
    if (terminalSessionCount === undefined) {
        try {
            const workspace = JSON.parse(sessionStorage.getItem(TERMINAL_WORKSPACE_STORAGE_KEY) || 'null')
            terminalCount = Array.isArray(workspace?.sessions) ? workspace.sessions.length : 0
        } catch {
            terminalCount = 0
        }
    }
    return terminalCount + readAppFileSessions().length + creating.size
}

export function getAppFileTitle(session: Pick<AppFileSession, 'app_id' | 'volume_id'>) {
    return session.volume_id
}

export function reconcileWorkspaceTabOrder(previous: string[], available: string[]) {
    const remaining = new Set(available)
    const ordered = previous.filter(identifier => remaining.delete(identifier))
    ordered.push(...remaining)
    return ordered
}

export function getNextWorkspaceTabId(ordered: string[], closingId: string) {
    const index = ordered.indexOf(closingId)
    const remaining = ordered.filter(identifier => identifier !== closingId)
    return remaining[Math.max(0, index - 1)] ?? remaining[0] ?? null
}

export function restoreTerminalSessions<Session extends { profileId: string | null; status: string; profileAvailable?: boolean; transportDisconnected?: boolean }>(sessions: Session[], profileIds: string[]) {
    const available = new Set(profileIds)
    return sessions.map(session => {
        const profileAvailable = Boolean(session.profileId && available.has(session.profileId))
        return { ...session, profileAvailable, status: !profileAvailable || (session.status === 'ended' && !session.transportDisconnected) ? 'ended' as const : 'idle' as const }
    })
}

function snapshot() {
    return sessionStorage.getItem(SESSIONS_KEY) || sessionStorage.getItem(LEGACY_SESSION_KEY) || '[]'
}

function parseSessions(raw: string): AppFileSession[] {
    try {
        const parsed = JSON.parse(raw)
        const sessions: AppFileSession[] = Array.isArray(parsed) ? parsed : [parsed]
        return sessions.filter((session) => session && typeof session.session_id === 'string' && typeof session.app_id === 'string' && typeof session.volume_id === 'string' && typeof session.root_path === 'string')
    } catch {
        return []
    }
}

export function readAppFileSessions() {
    return parseSessions(snapshot())
}

export function getAppFileRoute(session: Pick<AppFileSession, 'app_id' | 'volume_id'>) {
    return `/terminal?${new URLSearchParams({ app_file_app: session.app_id, app_file_volume: session.volume_id })}`
}

function saveSessions(sessions: AppFileSession[]) {
    const next = JSON.stringify(sessions)
    if (sessionStorage.getItem(SESSIONS_KEY) === next) return
    sessionStorage.setItem(SESSIONS_KEY, next)
    sessionStorage.removeItem(LEGACY_SESSION_KEY)
    window.dispatchEvent(new Event(CHANGE_EVENT))
}

export function rememberAppFileSession(session: AppFileSession) {
    const sessions = readAppFileSessions()
    const index = sessions.findIndex((entry) => entry.app_id === session.app_id && entry.volume_id === session.volume_id)
    if (index < 0) sessions.push(session)
    else sessions[index] = { ...sessions[index], ...session }
    saveSessions(sessions)
}

export function forgetAppFileSession(identifier: string) {
    saveSessions(readAppFileSessions().filter((session) => session.session_id !== identifier))
}

export function synchronizeAppFileProfiles(profileIds: string[]) {
    const available = new Set(profileIds)
    saveSessions(readAppFileSessions().map((session) => session.profile_id ? { ...session, profile_available: available.has(session.profile_id), ...(!available.has(session.profile_id) ? { status: 'ended' as const } : {}) } : session))
}

function subscribe(listener: () => void) {
    window.addEventListener(CHANGE_EVENT, listener)
    window.addEventListener('storage', listener)
    return () => {
        window.removeEventListener(CHANGE_EVENT, listener)
        window.removeEventListener('storage', listener)
    }
}

export function useAppFileSessions() {
    return parseSessions(useSyncExternalStore(subscribe, snapshot, () => '[]'))
}

export class FileSessionError extends Error {
    readonly status: number
    readonly code?: string
    constructor(message: string, status: number, code?: string) { super(message); this.status = status; this.code = code }
}

export function getAppFileErrorKey(error: unknown) {
    if (error instanceof ConnectionLimitError) return 'sftpConnectionLimit'
    const code = error instanceof FileSessionError ? error.code : undefined
    const message = error instanceof Error ? error.message : typeof error === 'string' ? error : ''
    if (code === 'Local SSH Setup Revoked') return 'sftpAuthorizationRevoked'
    if (code === 'Host Access Profile Not Found' || message.includes('The requested host profile is unavailable for file operations')) return 'sftpConnectionUnavailable'
    if (code === 'SFTP Scope Denied') return 'sftpScopeDenied'
    if (code === 'SFTP Account Unavailable') return 'sftpAuthorizationMissing'
    if (code === 'SFTP Path Unsupported' || code === 'SFTP Authorization Failed') return 'sftpDirectoryPermissionDenied'
    if (code === 'SFTP Container Not Running') return 'sftpConnectionUnavailable'
    if (code === 'Local SSH Setup Unavailable' || /authorization has not been prepared|prepared local ssh credentials|no local ssh credentials/i.test(message)) return 'sftpAuthorizationMissing'
    if (/connection refused|timed out|timeout|no route to host|network is unreachable|unable to connect to port|connection reset|error reading ssh protocol banner/i.test(message)) return 'sftpHostUnreachable'
    if (code === 'SSH Authentication Failed' || /authentication failed|authentication rejected|authenticationexception|rejected the prepared key|invalid private key/i.test(message)) return 'sftpAuthenticationFailed'
    if (/permission denied|permissionerror|errno 13|eacces|operation not permitted|read-only/i.test(message)) return 'sftpDirectoryPermissionDenied'
    return 'sftpConnectionRequired'
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
    const response = await fetch(url, { ...init, credentials: 'include', headers: { 'Content-Type': 'application/json' } })
    const body = await response.json()
    if (!response.ok) throw new FileSessionError(body.detail || body.details || body.message || response.statusText, response.status, body.code || body.message)
    return body as T
}

export async function closeAppFileSession(identifier: string) {
    try {
        await request(`/api/host-access/app-files/${identifier}/session`, { method: 'DELETE' })
    } catch (error) {
        if (!(error instanceof FileSessionError && (error.status === 403 || error.status === 404))) throw error
    }
    forgetAppFileSession(identifier)
}

export function acquireAppFileSession(appId: string, volumeId: string, profileId?: string): Promise<AppFileSession> {
    const key = JSON.stringify([appId, volumeId, profileId || null])
    const existing = pending.get(key)
    if (existing) return existing
    const operation = (async () => {
        const saved = readAppFileSessions().find((session) => session.app_id === appId && session.volume_id === volumeId)
        if (saved?.profile_available === false && (!profileId || saved.profile_id === profileId)) {
            throw new FileSessionError('The requested host profile is unavailable for file operations', 400, 'Host Access Profile Not Found')
        }
        if (saved && (!profileId || saved.profile_id === profileId)) {
            if (saved.status !== 'ended' && typeof saved.verified_at === 'number' && Date.now() - saved.verified_at < 60000) {
                return { ...saved, status: 'connected' as const }
            }
            try {
                await request(`/api/host-access/app-files/${saved.session_id}/tree?${new URLSearchParams({ path: saved.root_path })}`)
                const verified = { ...saved, status: 'connected' as const, verified_at: Date.now() }
                rememberAppFileSession(verified)
                return verified
            } catch (error) {
                if (!(error instanceof FileSessionError && (error.status === 403 || error.status === 404 || error.code === 'Host Access Profile Not Found'))) throw error
                forgetAppFileSession(saved.session_id)
            }
        } else if (saved) {
            await closeAppFileSession(saved.session_id)
        }
        if (getWorkspaceConnectionCount() >= MAX_WORKSPACE_CONNECTIONS) throw new ConnectionLimitError()
        creating.add(key)
        try {
            const session = await request<AppFileSession>('/api/host-access/app-files/sessions', {
                method: 'POST', body: JSON.stringify({ app_id: appId, volume_id: volumeId, profile_id: profileId || null }),
            })
            creating.delete(key)
            const connected = { ...session, status: 'connected' as const, verified_at: Date.now() }
            rememberAppFileSession(connected)
            return connected
        } finally {
            creating.delete(key)
        }
    })().finally(() => pending.delete(key))
    pending.set(key, operation)
    return operation
}