import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import { acquireAppFileSession, closeAppFileSession, ConnectionLimitError, FileSessionError, getAppFileErrorKey, getAppFileTitle, getNextWorkspaceTabId, getWorkspaceConnectionCount, MAX_WORKSPACE_CONNECTIONS, readAppFileSessions, reconcileWorkspaceTabOrder, rememberAppFileSession, restoreTerminalSessions, synchronizeAppFileProfiles, TERMINAL_WORKSPACE_STORAGE_KEY } from '../src/features/terminal/app-file-sessions.ts'

let storage
let active
let expired
let created
let validationStatus
let closeStatus

beforeEach(() => {
    storage = new Map()
    active = new Map()
    expired = new Set()
    created = 0
    validationStatus = 200
    closeStatus = 200
    globalThis.window = new EventTarget()
    globalThis.sessionStorage = {
        getItem: (key) => storage.get(key) || null,
        setItem: (key, value) => storage.set(key, value),
        removeItem: (key) => storage.delete(key),
    }
    globalThis.fetch = async (url, options = {}) => {
        if (options.method === 'POST') {
            const payload = JSON.parse(options.body)
            const session = { session_id: `session-${++created}`, app_id: payload.app_id, volume_id: payload.volume_id, profile_id: payload.profile_id, root_path: `/data/${payload.volume_id}` }
            active.set(session.session_id, session)
            return Response.json(session)
        }
        const identifier = url.split('/')[4]
        if (options.method === 'DELETE') {
            if (closeStatus !== 200) return Response.json({ message: 'Close failed' }, { status: closeStatus })
            active.delete(identifier)
            return Response.json({})
        }
        const status = active.has(identifier) && !expired.has(identifier) ? validationStatus : 403
        return Response.json(status === 200 ? {} : { message: 'Unavailable' }, { status })
    }
})

test('new terminal and file tabs append without regrouping existing tabs', () => {
    assert.deepEqual(reconcileWorkspaceTabOrder(['file-a'], ['terminal-a', 'file-a']), ['file-a', 'terminal-a'])
    assert.deepEqual(reconcileWorkspaceTabOrder(['file-a', 'terminal-a'], ['terminal-a', 'terminal-b', 'file-a', 'file-b']), ['file-a', 'terminal-a', 'terminal-b', 'file-b'])
    assert.deepEqual(reconcileWorkspaceTabOrder(['file-a', 'terminal-a'], ['terminal-a', 'file-b']), ['terminal-a', 'file-b'])
})

test('new terminal and file tabs append last and preserve stored order', () => {
    const existing = ['terminal-a', 'file-a', 'terminal-b', 'file-b']
    const available = ['terminal-a', 'terminal-b', 'terminal-c', 'file-a', 'file-b']
    const ordered = reconcileWorkspaceTabOrder(existing, available)
    assert.deepEqual(ordered, ['terminal-a', 'file-a', 'terminal-b', 'file-b', 'terminal-c'])
    sessionStorage.setItem('websoft9:workspace-tab-order', JSON.stringify(ordered))
    assert.deepEqual(reconcileWorkspaceTabOrder(JSON.parse(sessionStorage.getItem('websoft9:workspace-tab-order')), available), ordered)
    assert.deepEqual(reconcileWorkspaceTabOrder(ordered, [...available, 'file-c']), ['terminal-a', 'file-a', 'terminal-b', 'file-b', 'terminal-c', 'file-c'])
})

test('closing tabs selects a remaining neighbor across file and terminal contexts', () => {
    assert.equal(getNextWorkspaceTabId(['file-a', 'terminal-a'], 'terminal-a'), 'file-a')
    assert.equal(getNextWorkspaceTabId(['file-a', 'terminal-a', 'terminal-b'], 'file-a'), 'terminal-a')
    assert.equal(getNextWorkspaceTabId(['file-a', 'terminal-a', 'file-b'], 'terminal-a'), 'file-a')
    assert.equal(getNextWorkspaceTabId(['file-a'], 'file-a'), null)
})

test('refresh retains ended terminals and output when every host was deleted', () => {
    const sessions = [{ id: 'terminal-a', profileId: 'removed', status: 'connected', buffer: 'previous output' }, { id: 'terminal-b', profileId: 'removed', status: 'ended', buffer: 'ended output' }]
    const restored = restoreTerminalSessions(sessions, [])
    assert.equal(restored.length, 2)
    assert.deepEqual(restored.map(session => [session.id, session.status, session.profileAvailable, session.buffer]), [['terminal-a', 'ended', false, 'previous output'], ['terminal-b', 'ended', false, 'ended output']])
    assert.equal(sessions[0].status, 'connected')
})

test('refresh reconnects available live terminals but never automatically reconnects ended terminals', () => {
    const restored = restoreTerminalSessions([{ profileId: 'available', status: 'connected' }, { profileId: 'available', status: 'ended' }, { profileId: 'removed', status: 'idle' }], ['available'])
    assert.deepEqual(restored.map(session => [session.status, session.profileAvailable]), [['idle', true], ['ended', true], ['ended', false]])
})

test('repeated entry reuses a validated session and its directory', async () => {
    const first = await acquireAppFileSession('app-a', 'volume-a')
    rememberAppFileSession({ ...first, path: '/data/volume-a/subdir' })
    const reused = await acquireAppFileSession('app-a', 'volume-a')
    assert.equal(reused.session_id, first.session_id)
    assert.equal(reused.path, '/data/volume-a/subdir')
    assert.equal(created, 1)
})

test('refresh reattaches transport-disconnected terminals but never resurrects deleted profiles', () => {
    const restored = restoreTerminalSessions([{ profileId: 'available', status: 'ended', transportDisconnected: true }, { profileId: 'deleted', status: 'ended', transportDisconnected: true }, { profileId: 'available', status: 'ended', transportDisconnected: false }], ['available'])
    assert.deepEqual(restored.map(session => [session.status, session.profileAvailable]), [['idle', true], ['ended', false], ['ended', true]])
})

test('different applications and volumes retain independent sessions', async () => {
    await acquireAppFileSession('app-a', 'volume-a')
    await acquireAppFileSession('app-a', 'volume-b')
    await acquireAppFileSession('app-b', 'volume-c')
    assert.equal(readAppFileSessions().length, 3)
    assert.equal(created, 3)
})

test('expired sessions are replaced without removing other sessions', async () => {
    const first = await acquireAppFileSession('app-a', 'volume-a')
    const second = await acquireAppFileSession('app-b', 'volume-b')
    expired.add(first.session_id)
    const renewed = await acquireAppFileSession('app-a', 'volume-a')
    assert.notEqual(renewed.session_id, first.session_id)
    assert.deepEqual(readAppFileSessions().map(session => session.session_id).sort(), [second.session_id, renewed.session_id].sort())
})

test('concurrent entry only creates one session', async () => {
    const first = acquireAppFileSession('app-a', 'volume-a')
    const second = acquireAppFileSession('app-a', 'volume-a')
    assert.equal(first, second)
    assert.equal((await first).session_id, (await second).session_id)
    assert.equal(created, 1)
})

test('closing one session preserves the other connections', async () => {
    const first = await acquireAppFileSession('app-a', 'volume-a')
    const second = await acquireAppFileSession('app-b', 'volume-b')
    await closeAppFileSession(first.session_id)
    assert.deepEqual(readAppFileSessions().map(session => session.session_id), [second.session_id])
    assert.ok(active.has(second.session_id))
})

test('choosing another profile replaces only the target volume session', async () => {
    const first = await acquireAppFileSession('app-a', 'volume-a', 'profile-a')
    const other = await acquireAppFileSession('app-a', 'volume-b', 'profile-a')
    const replaced = await acquireAppFileSession('app-a', 'volume-a', 'profile-b')
    assert.notEqual(replaced.session_id, first.session_id)
    assert.equal(replaced.profile_id, 'profile-b')
    assert.equal(active.has(first.session_id), false)
    assert.ok(active.has(other.session_id))
    assert.equal(readAppFileSessions().length, 2)
})

test('transient validation and close failures do not discard a session', async () => {
    const first = await acquireAppFileSession('app-a', 'volume-a')
    validationStatus = 503
    await assert.rejects(acquireAppFileSession('app-a', 'volume-a'), /Unavailable/)
    closeStatus = 400
    await assert.rejects(closeAppFileSession(first.session_id), /Close failed/)
    assert.equal(readAppFileSessions()[0].session_id, first.session_id)
    assert.equal(created, 1)
})

test('legacy single-session storage migrates without creating another session', async () => {
    const session = { session_id: 'legacy', app_id: 'app-a', volume_id: 'volume-a', profile_id: 'local', root_path: '/data/volume-a' }
    active.set(session.session_id, session)
    storage.set('websoft9:app-files-session', JSON.stringify(session))
    assert.equal((await acquireAppFileSession('app-a', 'volume-a')).session_id, 'legacy')
    rememberAppFileSession({ ...session, path: '/data/volume-a/subdir' })
    assert.equal(storage.get('websoft9:app-files-session'), undefined)
    assert.equal(readAppFileSessions()[0].path, '/data/volume-a/subdir')
    assert.equal(created, 0)
})

test('file tab titles preserve the complete volume name', () => {
    assert.equal(getAppFileTitle({ app_id: 'openclaw_xx9gw', volume_id: 'openclaw_xx9gw_openclaw_data' }), 'openclaw_xx9gw_openclaw_data')
    assert.equal(getAppFileTitle({ app_id: 'app-a', volume_id: 'shared_data' }), 'shared_data')
})

test('connection failures distinguish authorization, login, network and directory permissions', () => {
    assert.equal(getAppFileErrorKey(new FileSessionError('Prepared credentials are unsafe', 400, 'Local SSH Setup Unavailable')), 'sftpAuthorizationMissing')
    assert.equal(getAppFileErrorKey(new FileSessionError('Permission denied (publickey)', 400, 'SSH Authentication Failed')), 'sftpAuthenticationFailed')
    assert.equal(getAppFileErrorKey(new FileSessionError('Unable to connect to port 22', 400, 'SSH Authentication Failed')), 'sftpHostUnreachable')
    assert.equal(getAppFileErrorKey(new FileSessionError('[Errno 13] Permission denied', 400, 'File Browser Failed')), 'sftpDirectoryPermissionDenied')
    assert.equal(getAppFileErrorKey(new FileSessionError('Path outside volume', 403, 'SFTP Scope Denied')), 'sftpScopeDenied')
})

test('terminal and file sessions share the same connection limit', async () => {
    assert.equal(MAX_WORKSPACE_CONNECTIONS, 10)
    storage.set(TERMINAL_WORKSPACE_STORAGE_KEY, JSON.stringify({ sessions: [{}, {}, {}] }))
    for (let index = 0; index < MAX_WORKSPACE_CONNECTIONS - 3; index += 1) await acquireAppFileSession('app-a', `volume-${index}`)
    assert.equal(getWorkspaceConnectionCount(), MAX_WORKSPACE_CONNECTIONS)
    await assert.rejects(acquireAppFileSession('app-b', 'overflow'), ConnectionLimitError)
    assert.equal(created, MAX_WORKSPACE_CONNECTIONS - 3)
})

test('concurrent creation reserves slots and cannot exceed the limit', async () => {
    const attempts = Array.from({ length: MAX_WORKSPACE_CONNECTIONS + 1 }, (_, index) => acquireAppFileSession('app-a', `volume-${index}`))
    const outcomes = await Promise.allSettled(attempts)
    assert.equal(outcomes.filter(outcome => outcome.status === 'fulfilled').length, MAX_WORKSPACE_CONNECTIONS)
    assert.ok(outcomes.at(-1).reason instanceof ConnectionLimitError)
    assert.equal(created, MAX_WORKSPACE_CONNECTIONS)
})

test('a full workspace can reuse and renew its existing file session', async () => {
    storage.set(TERMINAL_WORKSPACE_STORAGE_KEY, JSON.stringify({ sessions: Array.from({ length: MAX_WORKSPACE_CONNECTIONS - 1 }, () => ({})) }))
    const first = await acquireAppFileSession('app-a', 'volume-a')
    assert.equal((await acquireAppFileSession('app-a', 'volume-a')).session_id, first.session_id)
    expired.add(first.session_id)
    assert.notEqual((await acquireAppFileSession('app-a', 'volume-a')).session_id, first.session_id)
    assert.equal(getWorkspaceConnectionCount(), MAX_WORKSPACE_CONNECTIONS)
})

test('failed creation releases the reserved slot', async () => {
    storage.set(TERMINAL_WORKSPACE_STORAGE_KEY, JSON.stringify({ sessions: Array.from({ length: MAX_WORKSPACE_CONNECTIONS - 1 }, () => ({})) }))
    const originalFetch = globalThis.fetch
    globalThis.fetch = async () => Response.json({ message: 'Unavailable' }, { status: 503 })
    await assert.rejects(acquireAppFileSession('app-a', 'volume-a'), /Unavailable/)
    assert.equal(getWorkspaceConnectionCount(), MAX_WORKSPACE_CONNECTIONS - 1)
    globalThis.fetch = originalFetch
    await acquireAppFileSession('app-a', 'volume-a')
    assert.equal(getWorkspaceConnectionCount(), MAX_WORKSPACE_CONNECTIONS)
})

test('removing a host profile ends only its matching file sessions', async () => {
    const removed = await acquireAppFileSession('app-a', 'volume-a', 'deleted-host')
    const retained = await acquireAppFileSession('app-b', 'volume-b', 'remaining-host')
    synchronizeAppFileProfiles(['remaining-host'])
    assert.equal(readAppFileSessions().find(session => session.session_id === removed.session_id).status, 'ended')
    assert.equal(readAppFileSessions().find(session => session.session_id === removed.session_id).profile_available, false)
    assert.equal(readAppFileSessions().find(session => session.session_id === retained.session_id).status, 'connected')
    assert.equal(readAppFileSessions().length, 2)
})

test('missing host errors resolve to a localized message key', async () => {
    globalThis.fetch = async () => Response.json({ message: 'Host Access Profile Not Found', details: 'The requested host profile is unavailable for file operations' }, { status: 400 })
    await assert.rejects(acquireAppFileSession('app-a', 'volume-a'), error => getAppFileErrorKey(error) === 'sftpConnectionUnavailable')
    assert.equal(getAppFileErrorKey('The requested host profile is unavailable for file operations'), 'sftpConnectionUnavailable')
    assert.equal(getAppFileErrorKey(new FileSessionError('Local SSH Setup Revoked', 400, 'Local SSH Setup Revoked')), 'sftpAuthorizationRevoked')
})

test('selecting a file whose host was deleted retains the ended tab without recreating it', async () => {
    const first = await acquireAppFileSession('app-a', 'volume-a', 'deleted-host')
    synchronizeAppFileProfiles([])
    globalThis.fetch = async () => { throw new Error('Deleted-host tabs must not send requests') }
    await assert.rejects(acquireAppFileSession('app-a', 'volume-a'), error => getAppFileErrorKey(error) === 'sftpConnectionUnavailable')
    assert.equal(readAppFileSessions()[0].session_id, first.session_id)
    assert.equal(readAppFileSessions()[0].status, 'ended')
    assert.equal(created, 1)
})

test('unavailable file tabs can be closed and release their connection slot', async () => {
    const session = await acquireAppFileSession('app-a', 'volume-a', 'deleted-host')
    synchronizeAppFileProfiles([])
    closeStatus = 404
    await closeAppFileSession(session.session_id)
    assert.equal(readAppFileSessions().length, 0)
    assert.equal(getWorkspaceConnectionCount(), 0)
})

test('a file whose host was deleted can explicitly switch to a replacement profile', async () => {
    const first = await acquireAppFileSession('app-a', 'volume-a', 'deleted-host')
    synchronizeAppFileProfiles([])
    const replacement = await acquireAppFileSession('app-a', 'volume-a', 'replacement-host')
    assert.notEqual(replacement.session_id, first.session_id)
    assert.equal(replacement.profile_id, 'replacement-host')
    assert.equal(readAppFileSessions().length, 1)
})

test('a removed host profile does not prevent reopening files with a new local connection', async () => {
    const first = await acquireAppFileSession('app-a', 'volume-a', 'deleted-host')
    const originalFetch = globalThis.fetch
    globalThis.fetch = async (url, options = {}) => {
        if (!options.method && url.includes(`/app-files/${first.session_id}/`)) return Response.json({ message: 'Host Access Profile Not Found', details: 'The requested host profile is unavailable for file operations' }, { status: 400 })
        return originalFetch(url, options)
    }
    const renewed = await acquireAppFileSession('app-a', 'volume-a')
    assert.notEqual(renewed.session_id, first.session_id)
    assert.equal(renewed.status, 'connected')
    assert.equal(readAppFileSessions().length, 1)
})