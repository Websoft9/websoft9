import {
    Alert,
    Box,
    Button,
    CircularProgress,
    IconButton,
    InputAdornment,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

/**
 * Docker accelerator editor.
 *
 * The accelerators used to be a single free-text value in the settings list, which meant the
 * order, the credentials and the "use the shipped list instead" state had nowhere to live. The
 * list is now edited as rows that map one to one onto what the backend stores, so what the
 * operator sees is what the pull path will try.
 */

type MirrorEntrySource = 'operator' | 'default' | 'disabled'

type MirrorEntryResponse = {
    id: number | null
    position: number
    url: string
    username: string
    password_set: boolean
    enabled: boolean
    updated_at: string
}
type MirrorPayload = {
    source: MirrorEntrySource
    entries: MirrorEntryResponse[]
    default_mirrors: string[]
    region: string
}

type MirrorDraft = {
    /** Stable across reordering, so React keeps the inputs attached to their row. */
    key: string
    /** The stored row this draft edits; it is what keeps credentials with a renamed address. */
    id: number | null
    url: string
    username: string
    /** Empty means "leave the password as it is"; `passwordSet` says whether one exists. */
    password: string
    passwordSet: boolean
    /** Set when the operator asked for the stored password to be removed. */
    clearPassword: boolean
}

type ProbeResult = {
    reachable: boolean
    authorized: boolean
    /** The registry can serve pulls: a mirror that only asks for a token still counts. */
    usable: boolean
    reason: 'ok' | 'credentials-required' | 'credentials-rejected' | 'error' | 'unreachable'
    latency_ms: number
    detail: string
}

export type MirrorFeedback = { severity: 'success' | 'error' | 'info'; message: string }

const MAX_ACCELERATORS = 10

// The stored form is a registry host, optionally with a port and a path. The console requires
// an explicit HTTPS prefix, then removes it because Docker image references have no scheme.
const MIRROR_ADDRESS_PATTERN =
    /^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?::\d{1,5})?(?:\/[A-Za-z0-9._~\-/]*)?$/i

/** The address as the platform stores it: no scheme, no trailing slash. */
function normalizeAddress(value: string): string {
    return value.trim().replace(/^https:\/\//i, '').replace(/\/+$/, '')
}

type AddressIssue = 'required' | 'scheme' | 'invalid' | 'duplicate'

/** What is wrong with one address, checked the way the platform checks it on save. */
function addressIssue(value: string, taken: string[]): AddressIssue | null {
    const trimmed = value.trim()
    if (!trimmed) {
        return 'required'
    }
    if (!/^https:\/\//i.test(trimmed)) {
        return 'scheme'
    }
    const normalized = normalizeAddress(trimmed)
    if (!MIRROR_ADDRESS_PATTERN.test(normalized)) {
        return 'invalid'
    }
    if (taken.includes(normalized)) {
        return 'duplicate'
    }
    return null
}

function validationMessage(
    entry: MirrorDraft,
    taken: string[],
    t: (key: string) => string,
): string | null {
    const issue = addressIssue(entry.url, taken)
    if (issue === 'required') {
        return t('settingsPage.mirror.validationRequired')
    }
    if (issue === 'scheme') {
        return t('settingsPage.mirror.validationScheme')
    }
    if (issue === 'duplicate') {
        return t('settingsPage.mirror.validationDuplicate')
    }
    if (issue === 'invalid') {
        return t('settingsPage.mirror.validationInvalid')
    }
    if (entry.username.trim() && ((!entry.password && !entry.passwordSet) || entry.clearPassword)) {
        return t('settingsPage.mirror.validationPasswordRequired')
    }
    return null
}

function newDraft(): MirrorDraft {
    return {
        key: `new-${Date.now()}`,
        id: null,
        url: '',
        username: '',
        password: '',
        passwordSet: false,
        clearPassword: false,
    }
}

function GripIcon() {
    return (
        <svg aria-hidden="true" fill="currentColor" height="14" viewBox="0 0 24 24" width="14">
            <circle cx="9" cy="6" r="1.6" />
            <circle cx="15" cy="6" r="1.6" />
            <circle cx="9" cy="12" r="1.6" />
            <circle cx="15" cy="12" r="1.6" />
            <circle cx="9" cy="18" r="1.6" />
            <circle cx="15" cy="18" r="1.6" />
        </svg>
    )
}

/** Reachability, which is what "test" checks: can the platform talk to this address. */
function TestIcon() {
    return (
        <svg aria-hidden="true" fill="none" height="17" viewBox="0 0 24 24" width="17">
            <path d="M4.6 9.4a11 11 0 0 1 14.8 0" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
            <path d="M7.6 12.8a6.6 6.6 0 0 1 8.8 0" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
            <circle cx="12" cy="17" fill="currentColor" r="1.7" />
        </svg>
    )
}

/** The address answered: the icon carries the verdict so the row needs no extra line. */
function TestOkIcon() {
    return (
        <svg aria-hidden="true" fill="none" height="17" viewBox="0 0 24 24" width="17">
            <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
            <path d="m8.1 12.4 2.7 2.7 5.1-5.6" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
        </svg>
    )
}

function TestFailedIcon() {
    return (
        <svg aria-hidden="true" fill="none" height="17" viewBox="0 0 24 24" width="17">
            <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
            <path d="M12 7.6v5.2" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
            <circle cx="12" cy="16.2" fill="currentColor" r="1.15" />
        </svg>
    )
}

/** Shows the optional account fields for one row, and marks a row that already has them. */
function CredentialsIcon() {
    return (
        <svg aria-hidden="true" fill="none" height="16" viewBox="0 0 24 24" width="16">
            <circle cx="8.4" cy="14.6" fill="none" r="3.4" stroke="currentColor" strokeWidth="1.7" />
            <path d="M10.9 12.1 19.6 3.4M15.6 7.4l2.2 2.2M12.7 10.4l2.2 2.2" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" />
        </svg>
    )
}

function DeleteIcon() {
    return (
        <svg aria-hidden="true" fill="none" height="16" viewBox="0 0 24 24" width="16">
            <path
                d="M4.6 6.9h14.8M9.7 6.9V4.7h4.6v2.2M6.7 6.9l.8 12.1a1.6 1.6 0 0 0 1.6 1.5h5.8a1.6 1.6 0 0 0 1.6-1.5l.8-12.1"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.7"
            />
            <path d="M10.4 10.5v6.2M13.6 10.5v6.2" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7" />
        </svg>
    )
}

/** Drops the stored password on the next save. */
function ClearPasswordIcon() {
    return (
        <svg aria-hidden="true" fill="none" height="14" viewBox="0 0 24 24" width="14">
            <circle cx="12" cy="12" fill="none" r="9" stroke="currentColor" strokeWidth="1.8" />
            <path d="m9 9 6 6M15 9l-6 6" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
        </svg>
    )
}

/** Takes back a pending removal, so the stored password is kept. */
function KeepPasswordIcon() {
    return (
        <svg aria-hidden="true" fill="none" height="14" viewBox="0 0 24 24" width="14">
            <path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
            <path d="M4.4 5.4v4.4H8.8" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
        </svg>
    )
}

async function readError(response: Response): Promise<string> {
    try {
        const payload = await response.json()
        return String(payload?.details ?? payload?.message ?? '')
    } catch {
        return ''
    }
}

async function fetchMirrors(): Promise<MirrorPayload> {
    const response = await fetch('/api/settings/docker_mirrors/entries', { credentials: 'include' })
    if (!response.ok) {
        throw new Error(await readError(response))
    }
    return (await response.json()) as MirrorPayload
}

async function saveMirrors(entries: MirrorDraft[]): Promise<MirrorPayload> {
    const response = await fetch('/api/settings/docker_mirrors/entries', {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            entries: entries.map((entry) => ({
                // The id is what keeps a renamed address attached to its stored password.
                id: entry.id,
                url: entry.url.trim(),
                username: entry.username.trim(),
                // null keeps the stored password, an empty string removes it. Both are
                // actions the operator can mean, so they must stay distinguishable.
                password: entry.clearPassword ? '' : entry.password === '' ? null : entry.password,
            })),
        }),
    })
    if (!response.ok) {
        throw new Error(await readError(response))
    }
    return (await response.json()) as MirrorPayload
}

async function probeMirror(entry: MirrorDraft): Promise<ProbeResult> {
    const response = await fetch('/api/settings/docker_mirrors/test', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            id: entry.id,
            url: entry.url.trim(),
            username: entry.username.trim(),
            password: entry.clearPassword ? '' : entry.password === '' ? null : entry.password,
        }),
    })
    if (!response.ok) {
        throw new Error(await readError(response))
    }
    return (await response.json()) as ProbeResult
}

function toDrafts(entries: MirrorEntryResponse[]): MirrorDraft[] {
    return entries.map((entry) => ({
        key: `entry-${entry.id ?? entry.url}`,
        id: entry.id,
        url: `https://${entry.url}`,
        username: entry.username,
        password: '',
        passwordSet: entry.password_set,
        clearPassword: false,
    }))
}

function draftsEqual(left: MirrorDraft[], right: MirrorDraft[]): boolean {
    if (left.length !== right.length) {
        return false
    }
    return left.every((entry, index) => {
        const other = right[index]
        return (
            entry.url.trim() === other.url.trim() &&
            entry.username.trim() === other.username.trim() &&
            entry.password === other.password &&
            entry.clearPassword === other.clearPassword
        )
    })
}

export function MirrorAccelerators({
    addRequest,
    onFeedback,
}: {
    addRequest: number
    onFeedback: (feedback: MirrorFeedback) => void
}) {
    const { t } = useTranslation('shell')
    const queryClient = useQueryClient()
    const { data, isError, isLoading } = useQuery({
        queryKey: ['docker-mirrors'],
        queryFn: fetchMirrors,
    })

    const [drafts, setDrafts] = useState<MirrorDraft[] | null>(null)
    // The account fields stay out of the way until an accelerator needs them; the row is a
    // list of addresses first.
    const [openCredentials, setOpenCredentials] = useState<Record<string, boolean>>({})
    const [probes, setProbes] = useState<Record<string, ProbeResult>>({})
    const [testingKey, setTestingKey] = useState<string | null>(null)
    const [draggingKey, setDraggingKey] = useState<string | null>(null)
    const [savePending, setSavePending] = useState(false)
    const lastAddRequest = useRef(addRequest)
    const [invalidFields, setInvalidFields] = useState<Record<string, 'url' | 'password'>>({})
    const inputRefs = useRef<Record<string, HTMLInputElement | null>>({})

    const storedDrafts = useMemo(() => toDrafts(data?.entries ?? []), [data])
    const rows = drafts ?? storedDrafts

    // A stored state that changes underneath an untouched editor (a refresh, or a save from
    // another tab) must show up here, otherwise Save would write a stale order back.
    useEffect(() => {
        if (drafts === null) {
            return
        }
        if (draftsEqual(drafts, storedDrafts)) {
            setDrafts(null)
        }
    }, [drafts, storedDrafts])

    const hasChanges = drafts !== null && !draftsEqual(drafts, storedDrafts)

    function updateRow(key: string, patch: Partial<MirrorDraft>) {
        setDrafts(rows.map((entry) => (entry.key === key ? { ...entry, ...patch } : entry)))
        setInvalidFields((current) => {
            if (!(key in current)) {
                return current
            }
            const next = { ...current }
            delete next[key]
            return next
        })
        setProbes((current) => {
            if (!(key in current)) {
                return current
            }
            const next = { ...current }
            delete next[key]
            return next
        })
    }

    useEffect(() => {
        if (addRequest <= lastAddRequest.current) {
            return
        }
        lastAddRequest.current = addRequest
        const currentRows = drafts ?? storedDrafts
        if (currentRows.length >= MAX_ACCELERATORS) {
            onFeedback({ severity: 'info', message: t('settingsPage.mirror.maxEntries', { count: MAX_ACCELERATORS }) })
            return
        }
        setDrafts((current) => [
            ...(current ?? storedDrafts),
            newDraft(),
        ])
    }, [addRequest, drafts, onFeedback, storedDrafts, t])

    function removeRow(key: string) {
        setDrafts(rows.filter((entry) => entry.key !== key))
        setProbes((current) => {
            const next = { ...current }
            delete next[key]
            return next
        })
    }

    function moveRow(fromIndex: number, toIndex: number) {
        if (fromIndex === toIndex || toIndex < 0 || toIndex >= rows.length) {
            return
        }
        const next = [...rows]
        const [moved] = next.splice(fromIndex, 1)
        next.splice(toIndex, 0, moved)
        setDrafts(next)
    }

    async function handleTest(entry: MirrorDraft) {
        const message = validationMessage(entry, [], t)
        if (message) {
            onFeedback({ severity: 'error', message })
            return
        }
        setTestingKey(entry.key)
        try {
            const result = await probeMirror(entry)
            setProbes((current) => ({ ...current, [entry.key]: result }))
        } catch (error) {
            onFeedback({ severity: 'error', message: (error as Error).message || t('settingsPage.mirror.testFailed') })
        } finally {
            setTestingKey(null)
        }
    }

    async function handleSave() {
        const taken: string[] = []
        for (const entry of rows) {
            const message = validationMessage(entry, taken, t)
            if (message) {
                const field = addressIssue(entry.url, taken) ? 'url' : 'password'
                setInvalidFields({ [entry.key]: field })
                onFeedback({ severity: 'error', message })
                window.setTimeout(() => inputRefs.current[`${entry.key}:${field}`]?.focus(), 0)
                return
            }
            taken.push(normalizeAddress(entry.url))
        }
        setSavePending(true)
        try {
            const payload = await saveMirrors(rows)
            setDrafts(null)
            setProbes({})
            queryClient.setQueryData(['docker-mirrors'], payload)
            onFeedback({ severity: 'success', message: t('settingsPage.mirror.saved') })
        } catch (error) {
            onFeedback({
                severity: 'error',
                message: (error as Error).message || t('settingsPage.mirror.saveFailed'),
            })
        } finally {
            setSavePending(false)
        }
    }

    if (isLoading) {
        return (
            <Box className="settings-mirror-panel settings-mirror-panel--loading">
                <CircularProgress size={22} />
            </Box>
        )
    }

    if (isError || !data) {
        return (
            <Alert severity="error" variant="outlined">
                {t('settingsPage.mirror.loadFailed')}
            </Alert>
        )
    }

    return (
        <Box className="settings-mirror-panel">
            <div className="settings-mirror-list">
                {rows.map((entry, index) => {
                    const probe = probes[entry.key]
                    const testDisabled = testingKey === entry.key || Boolean(validationMessage(entry, [], t))
                    const showCredentials =
                        openCredentials[entry.key] ||
                        Boolean(entry.username || entry.passwordSet || entry.clearPassword)
                    const probeMessage = probe
                        ? probe.reason === 'ok'
                            ? t('settingsPage.mirror.testOk', { latency: probe.latency_ms })
                            : probe.reason === 'credentials-required'
                                ? t('settingsPage.mirror.testCredentialsRequired')
                                : probe.reason === 'credentials-rejected'
                                    ? t('settingsPage.mirror.testCredentials')
                                    : probe.reachable
                                        ? t('settingsPage.mirror.testError')
                                        : t('settingsPage.mirror.testUnreachable')
                        : t('settingsPage.mirror.test')
                    return (
                        <div
                            className={`settings-mirror-row${draggingKey === entry.key ? ' settings-mirror-row--dragging' : ''}`}
                            key={entry.key}
                            onDragEnd={() => setDraggingKey(null)}
                            onDragOver={(event) => event.preventDefault()}
                            onDrop={(event) => {
                                event.preventDefault()
                                const fromIndex = rows.findIndex((item) => item.key === draggingKey)
                                if (fromIndex >= 0) {
                                    moveRow(fromIndex, index)
                                }
                                setDraggingKey(null)
                            }}
                        >
                            <div className="settings-mirror-row-main">
                                <Tooltip title={t('settingsPage.mirror.reorder')}>
                                    <span
                                        aria-hidden="true"
                                        className="settings-mirror-drag-handle"
                                        draggable
                                        onDragStart={() => setDraggingKey(entry.key)}
                                    >
                                        <GripIcon />
                                    </span>
                                </Tooltip>
                                <TextField
                                    className="settings-mirror-url-field"
                                    error={invalidFields[entry.key] === 'url'}
                                    inputRef={(element) => {
                                        inputRefs.current[`${entry.key}:url`] = element
                                    }}
                                    onChange={(event) => updateRow(entry.key, { url: event.target.value })}
                                    placeholder={t('settingsPage.mirror.urlPlaceholder')}
                                    size="small"
                                    value={entry.url}
                                    variant="outlined"
                                />
                                {showCredentials && (
                                    <>
                                        <TextField
                                            className="settings-mirror-username-field"
                                            onChange={(event) => {
                                                const username = event.target.value
                                                updateRow(
                                                    entry.key,
                                                    username.trim()
                                                        ? { username }
                                                        : {
                                                            username: '',
                                                            password: '',
                                                            passwordSet: false,
                                                            clearPassword: Boolean(entry.passwordSet || entry.password || entry.clearPassword),
                                                        },
                                                )
                                            }}
                                            placeholder={t('settingsPage.mirror.usernamePlaceholder')}
                                            size="small"
                                            value={entry.username}
                                            variant="outlined"
                                        />
                                        <TextField
                                            className="settings-mirror-password-field"
                                            autoComplete="new-password"
                                            error={invalidFields[entry.key] === 'password'}
                                            inputRef={(element) => {
                                                inputRefs.current[`${entry.key}:password`] = element
                                            }}
                                            onChange={(event) =>
                                                updateRow(entry.key, {
                                                    password: event.target.value,
                                                    clearPassword: false,
                                                })
                                            }
                                            placeholder={
                                                entry.clearPassword
                                                    ? t('settingsPage.mirror.passwordWillClear')
                                                    : entry.passwordSet
                                                        ? t('settingsPage.mirror.passwordStored')
                                                        : t('settingsPage.mirror.passwordPlaceholder')
                                            }
                                            size="small"
                                            slotProps={{
                                                input: {
                                                    endAdornment:
                                                        entry.passwordSet || entry.clearPassword ? (
                                                            <InputAdornment position="end">
                                                                <Tooltip
                                                                    title={
                                                                        entry.clearPassword
                                                                            ? t('settingsPage.mirror.passwordClearUndo')
                                                                            : t('settingsPage.mirror.passwordClear')
                                                                    }
                                                                >
                                                                    <IconButton
                                                                        aria-label={t('settingsPage.mirror.passwordClear')}
                                                                        className="settings-mirror-field-icon"
                                                                        onClick={() =>
                                                                            updateRow(entry.key, {
                                                                                password: '',
                                                                                passwordSet: !entry.clearPassword,
                                                                                clearPassword: !entry.clearPassword,
                                                                            })
                                                                        }
                                                                        size="small"
                                                                        type="button"
                                                                    >
                                                                        {entry.clearPassword ? (
                                                                            <KeepPasswordIcon />
                                                                        ) : (
                                                                            <ClearPasswordIcon />
                                                                        )}
                                                                    </IconButton>
                                                                </Tooltip>
                                                            </InputAdornment>
                                                        ) : null,
                                                },
                                            }}
                                            type="password"
                                            value={entry.password}
                                            variant="outlined"
                                        />
                                    </>
                                )}
                                <Tooltip title={t('settingsPage.mirror.credentialsToggle')}>
                                    <IconButton
                                        aria-label={t('settingsPage.mirror.credentialsToggle')}
                                        className={`settings-mirror-icon-button${showCredentials ? ' settings-mirror-icon-button--active' : ''
                                            }`}
                                        onClick={() =>
                                            setOpenCredentials((current) => ({
                                                ...current,
                                                [entry.key]: !showCredentials,
                                            }))
                                        }
                                        size="small"
                                        type="button"
                                    >
                                        <CredentialsIcon />
                                    </IconButton>
                                </Tooltip>
                                <Tooltip title={probeMessage}>
                                    <span>
                                        <IconButton
                                            aria-label={t('settingsPage.mirror.test')}
                                            className={`settings-mirror-icon-button${probe
                                                ? probe.usable
                                                    ? ' settings-mirror-test-icon--ok'
                                                    : ' settings-mirror-test-icon--failed'
                                                : ''
                                                }`}
                                            disabled={testDisabled}
                                            onClick={() => handleTest(entry)}
                                            size="small"
                                            type="button"
                                        >
                                            {testingKey === entry.key ? (
                                                <CircularProgress size={14} />
                                            ) : probe ? (
                                                probe.usable ? (
                                                    <TestOkIcon />
                                                ) : (
                                                    <TestFailedIcon />
                                                )
                                            ) : (
                                                <TestIcon />
                                            )}
                                        </IconButton>
                                    </span>
                                </Tooltip>
                                <Tooltip title={t('settingsPage.mirror.remove')}>
                                    <IconButton
                                        aria-label={t('settingsPage.mirror.remove')}
                                        className="settings-mirror-icon-button"
                                        onClick={() => removeRow(entry.key)}
                                        size="small"
                                        type="button"
                                    >
                                        <DeleteIcon />
                                    </IconButton>
                                </Tooltip>
                            </div>
                        </div>
                    )
                })}
            </div>

            <Typography className="settings-field-helper settings-field-helper--inline settings-port-hint settings-mirror-hint">
                <svg className="settings-port-hint-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
                    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
                    <path d="M12 11.2v5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                    <circle cx="12" cy="7.9" r="1.15" fill="currentColor" />
                </svg>
                <span>{t('settingsPage.mirror.helper')}</span>
            </Typography>
            <Typography className="settings-field-helper settings-field-helper--inline settings-port-hint settings-mirror-hint">
                <svg className="settings-port-hint-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
                    <path d="M7 4.7h10M7 12h10M7 19.3h10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                    <path d="m14.2 16.5 2.8 2.8-2.8 2.8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span>{t('settingsPage.mirror.orderHelper')}</span>
            </Typography>
            <Typography className="settings-field-helper settings-field-helper--inline settings-port-hint settings-mirror-hint">
                <svg className="settings-port-hint-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
                    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
                    <path d="M12 7.7v4.8l3.2 1.9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span>{t('settingsPage.mirror.testHelper')}</span>
            </Typography>

            {rows.length > 0 || hasChanges ? (
                <div className="settings-mirror-actions">
                    <Button
                        disabled={savePending || !hasChanges}
                        onClick={handleSave}
                        size="small"
                        type="button"
                        variant="contained"
                    >
                        {savePending ? t('settingsPage.actions.saving') : t('settingsPage.actions.save')}
                    </Button>
                </div>
            ) : null}
        </Box>
    )
}
