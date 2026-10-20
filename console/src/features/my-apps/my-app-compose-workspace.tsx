import { yaml as yamlLanguage } from '@codemirror/lang-yaml'
import { Alert, Box, Button, CircularProgress, Tooltip, Typography } from '@mui/material'
import CodeMirror from '@uiw/react-codemirror'
import { ArrowLeft, CornerLeftUp, ExternalLink, FileCode2, FileText, Folder, RefreshCw, RotateCcw, Save } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { getSurfacePalette } from '../../shared/design-system/surface-theme'

export type RepositoryFileEntry = {
    path: string
    name: string
    type: 'dir' | 'file'
    size: number
    sha: string
    last_commit_sha?: string
    last_modified?: string
}

type RepositoryTreeResponse = {
    app_id: string
    current_dir: string
    head_sha: string
    deployed_sha: string
    pending_redeploy: boolean
    files: RepositoryFileEntry[]
}

type RepositoryFileContentResponse = {
    path: string
    name: string
    sha: string
    content: string
}

type MyAppComposeWorkspaceProps = {
    appId: string
    isDarkMode: boolean
    redeployDisabled: boolean
    onOpenRepository: (filePath?: string) => void
    onRequestRedeploy: () => void
    onFeedback: (feedback: { severity: 'success' | 'error'; message: string }) => void
}

function formatByteSize(bytes: number) {
    if (!bytes || bytes <= 0) return '0 B'
    if (bytes < 1024) return `${bytes} B`
    return `${(bytes / 1024).toFixed(bytes >= 10 * 1024 ? 0 : 1)} KB`
}

function formatModifiedTime(raw: string | undefined, locale: string) {
    if (!raw) return '-'
    const parsed = Date.parse(raw)
    if (Number.isNaN(parsed)) return raw
    try {
        return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(parsed))
    } catch {
        return raw
    }
}

async function parseError(response: Response, fallback: string) {
    try {
        const payload = (await response.json()) as { details?: string; detail?: string; message?: string }
        return payload.details || payload.detail || payload.message || fallback
    } catch {
        return fallback
    }
}

export function MyAppComposeWorkspace({
    appId,
    isDarkMode,
    redeployDisabled,
    onOpenRepository,
    onRequestRedeploy,
    onFeedback,
}: MyAppComposeWorkspaceProps) {
    const { t, i18n } = useTranslation('shell')
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'zh'
    const palette = getSurfacePalette(isDarkMode)

    const [currentDir, setCurrentDir] = useState<string>('')
    const [files, setFiles] = useState<RepositoryFileEntry[]>([])
    const [pendingRedeploy, setPendingRedeploy] = useState(false)
    const [treeLoading, setTreeLoading] = useState(false)
    const [treeError, setTreeError] = useState<string | null>(null)

    const [editingPath, setEditingPath] = useState<string>('')
    const [fileSha, setFileSha] = useState<string>('')
    const [originalContent, setOriginalContent] = useState<string>('')
    const [draftContent, setDraftContent] = useState<string>('')
    const [fileLoading, setFileLoading] = useState(false)
    const [fileError, setFileError] = useState<string | null>(null)
    const [savingMode, setSavingMode] = useState<'save' | 'save-redeploy' | null>(null)

    const isEditing = editingPath !== ''
    const isDirty = isEditing && draftContent !== originalContent
    const isYamlFile = /\.ya?ml$/i.test(editingPath)

    const editorExtensions = useMemo(() => {
        return isYamlFile ? [yamlLanguage()] : []
    }, [isYamlFile])

    const dirSegments = useMemo(() => {
        return currentDir.split('/').filter(Boolean)
    }, [currentDir])

    const editingSegments = useMemo(() => {
        return editingPath.split('/').filter(Boolean)
    }, [editingPath])

    const loadDirectory = useCallback(async (targetDir: string) => {
        if (!appId) return
        setTreeLoading(true)
        setTreeError(null)
        try {
            const query = targetDir ? `?path=${encodeURIComponent(targetDir)}` : ''
            const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/repository/files${query}`, {
                credentials: 'include',
                cache: 'no-store',
                headers: { Accept: 'application/json' },
            })
            if (!response.ok) {
                throw new Error(await parseError(response, t('myAppsDetailPage.tabs.compose.workspace.loadFilesFailed')))
            }
            const data = (await response.json()) as RepositoryTreeResponse
            setCurrentDir(data.current_dir ?? targetDir)
            setFiles(data.files ?? [])
            setPendingRedeploy(Boolean(data.pending_redeploy))
        } catch (err) {
            setTreeError(err instanceof Error ? err.message : t('myAppsDetailPage.tabs.compose.workspace.loadFilesFailed'))
        } finally {
            setTreeLoading(false)
        }
    }, [appId, t])

    const openFileEditor = useCallback(async (targetPath: string) => {
        if (!appId || !targetPath) return
        setEditingPath(targetPath)
        setFileLoading(true)
        setFileError(null)
        try {
            const response = await fetch(
                `/api/apps/${encodeURIComponent(appId)}/repository/file?path=${encodeURIComponent(targetPath)}`,
                {
                    credentials: 'include',
                    cache: 'no-store',
                    headers: { Accept: 'application/json' },
                },
            )
            if (!response.ok) {
                throw new Error(await parseError(response, t('myAppsDetailPage.tabs.compose.workspace.loadFileFailed')))
            }
            const data = (await response.json()) as RepositoryFileContentResponse
            setEditingPath(data.path)
            setFileSha(data.sha)
            setOriginalContent(data.content)
            setDraftContent(data.content)
        } catch (err) {
            setFileError(err instanceof Error ? err.message : t('myAppsDetailPage.tabs.compose.workspace.loadFileFailed'))
        } finally {
            setFileLoading(false)
        }
    }, [appId, t])

    function closeFileEditor(targetDir?: string) {
        if (savingMode !== null) return
        const nextDir = targetDir !== undefined ? targetDir : currentDir
        setEditingPath('')
        setFileSha('')
        setOriginalContent('')
        setDraftContent('')
        setFileError(null)
        void loadDirectory(nextDir)
    }

    useEffect(() => {
        setEditingPath('')
        setCurrentDir('')
        void loadDirectory('')
    }, [appId, loadDirectory])

    useEffect(() => {
        const handleWindowFocus = () => {
            if (!isEditing) {
                void loadDirectory(currentDir)
            } else if (!isDirty && editingPath) {
                void openFileEditor(editingPath)
            }
        }
        window.addEventListener('focus', handleWindowFocus)
        return () => window.removeEventListener('focus', handleWindowFocus)
    }, [currentDir, editingPath, isDirty, isEditing, loadDirectory, openFileEditor])

    async function handleSave(triggerRedeploy: boolean) {
        if (!editingPath || savingMode !== null) return
        setSavingMode(triggerRedeploy ? 'save-redeploy' : 'save')
        setFileError(null)
        try {
            const response = await fetch(`/api/apps/${encodeURIComponent(appId)}/repository/file`, {
                method: 'PUT',
                credentials: 'include',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    path: editingPath,
                    content: draftContent,
                    sha: fileSha || undefined,
                }),
            })
            if (!response.ok) {
                if (response.status === 409) {
                    throw new Error(t('myAppsDetailPage.tabs.compose.workspace.conflictError'))
                }
                throw new Error(await parseError(response, t('myAppsDetailPage.tabs.compose.workspace.saveFailed')))
            }
            const result = (await response.json()) as { sha?: string; pending_redeploy?: boolean }
            const newSize = new Blob([draftContent]).size
            if (result.sha) setFileSha(result.sha)
            setOriginalContent(draftContent)
            setPendingRedeploy(result.pending_redeploy ?? true)
            setFiles((prev) => prev.map((item) => item.path === editingPath ? { ...item, sha: result.sha || item.sha, size: newSize } : item))
            onFeedback({ severity: 'success', message: t('myAppsDetailPage.tabs.compose.workspace.saveSuccess', { file: editingPath }) })
            if (triggerRedeploy) {
                onRequestRedeploy()
            }
        } catch (err) {
            const msg = err instanceof Error ? err.message : t('myAppsDetailPage.tabs.compose.workspace.saveFailed')
            setFileError(msg)
            onFeedback({ severity: 'error', message: msg })
        } finally {
            setSavingMode(null)
        }
    }

    const parentDir = useMemo(() => {
        if (!currentDir) return ''
        const parts = currentDir.split('/').filter(Boolean)
        parts.pop()
        return parts.join('/')
    }, [currentDir])

    return (
        <div className="myapps-access-section myapps-compose-section">
            <div className="myapps-access-section-head">
                <div className="myapps-section-label-bar">
                    <span className="myapps-section-label-indicator" />
                    <div className="myapps-section-label-stack">
                        <span className="myapps-section-label-text">{t('myAppsDetailPage.tabs.compose.title')}</span>
                        <p className="myapps-section-label-desc">{t('myAppsDetailPage.tabs.compose.description')}</p>
                    </div>
                </div>
                <div className="myapps-card-header-actions" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Button
                        size="small"
                        variant="outlined"
                        onClick={() => {
                        if (isEditing) {
                            void openFileEditor(editingPath)
                        } else {
                            void loadDirectory(currentDir)
                        }
                        }}
                        disabled={treeLoading || fileLoading || savingMode !== null}
                        startIcon={(treeLoading || fileLoading) ? <CircularProgress size={13} color="inherit" /> : <RefreshCw size={14} />}
                        sx={{
                        textTransform: 'none',
                        borderRadius: 0,
                        fontSize: 12.5,
                        borderColor: palette.borderStrong,
                        color: palette.subtleText,
                        '&:hover': { borderColor: palette.text, color: palette.text },
                        }}
                    >
                        {t('myAppsDetailPage.tabs.compose.workspace.refresh')}
                    </Button>
                    <Button
                        size="small"
                        variant="outlined"
                        onClick={() => onOpenRepository(isEditing ? editingPath : (currentDir || undefined))}
                        endIcon={<ExternalLink size={13} />}
                        sx={{
                        textTransform: 'none',
                        borderRadius: 0,
                        fontSize: 12.5,
                        borderColor: palette.borderStrong,
                        color: palette.subtleText,
                        '&:hover': { borderColor: palette.text, color: palette.text },
                        }}
                    >
                        {t('myAppsDetailPage.tabs.compose.workspace.openGitea')}
                    </Button>
                    <Tooltip title={pendingRedeploy ? t('myAppsDetailPage.tabs.compose.workspace.pendingRedeployNotice') : ''}>
                        <span>
                        <Button
                            size="small"
                            variant={pendingRedeploy ? 'contained' : 'outlined'}
                            disabled={redeployDisabled || savingMode !== null}
                            onClick={onRequestRedeploy}
                            sx={{
                                textTransform: 'none',
                                borderRadius: 0,
                                fontSize: 12.5,
                                boxShadow: 'none',
                                position: 'relative',
                                ...(pendingRedeploy
                                    ? {}
                                    : {
                                        borderColor: palette.borderStrong,
                                        color: palette.text,
                                        '&:hover': { borderColor: palette.accent, color: palette.accent },
                                    }),
                            }}
                        >
                            {t('myAppsDetailPage.tabs.compose.steps.redeploy.action')}
                            {pendingRedeploy ? (
                                <Box
                                    component="span"
                                    sx={{
                                        ml: 0.75,
                                        width: 6,
                                        height: 6,
                                        borderRadius: '50%',
                                        backgroundColor: '#fbbf24',
                                        display: 'inline-block',
                                    }}
                                />
                            ) : null}
                        </Button>
                        </span>
                    </Tooltip>
                </div>
            </div>

            <div className="myapps-php-card-body">
                {treeError ? (
                    <Alert
                        severity="error"
                        variant="outlined"
                        sx={{ mb: 1.5, borderRadius: 0 }}
                        action={
                        <Button color="inherit" size="small" onClick={() => void loadDirectory(currentDir)}>
                            {t('myAppsDetailPage.states.retry')}
                        </Button>
                        }
                    >
                        {treeError}
                    </Alert>
                ) : null}

                {!isEditing ? (
                    <div className="myapps-php-runtime-card myapps-volume-runtime-card">
                        <Box
                        sx={{
                            px: 1.75,
                            py: 1,
                            borderBottom: `1px solid ${palette.border}`,
                            backgroundColor: palette.panelSoft,
                            display: 'flex',
                            alignItems: 'center',
                            flexWrap: 'wrap',
                            gap: 0.5,
                            fontSize: 13,
                        }}
                        >
                        <Box
                            component="button"
                            type="button"
                            onClick={() => void loadDirectory('')}
                            sx={{
                                border: 0,
                                background: 'none',
                                p: 0,
                                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                                fontSize: 13,
                                fontWeight: currentDir ? 500 : 700,
                                color: currentDir ? palette.accent : palette.text,
                                cursor: currentDir ? 'pointer' : 'default',
                                '&:hover': currentDir ? { textDecoration: 'underline' } : {},
                            }}
                        >
                            {appId}
                        </Box>
                        {dirSegments.map((segment, index) => {
                            const segmentPath = dirSegments.slice(0, index + 1).join('/')
                            const isLast = index === dirSegments.length - 1
                            return (
                                <Box key={segmentPath} sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                                    <span style={{ color: palette.placeholderText }}>/</span>
                                    <Box
                                        component="button"
                                        type="button"
                                        onClick={() => {
                                            if (!isLast) void loadDirectory(segmentPath)
                                        }}
                                        sx={{
                                            border: 0,
                                            background: 'none',
                                            p: 0,
                                            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                                            fontSize: 13,
                                            fontWeight: isLast ? 700 : 500,
                                            color: isLast ? palette.text : palette.accent,
                                            cursor: isLast ? 'default' : 'pointer',
                                            '&:hover': !isLast ? { textDecoration: 'underline' } : {},
                                        }}
                                    >
                                        {segment}
                                    </Box>
                                </Box>
                            )
                        })}
                        </Box>

                        <div className="myapps-table-wrap">
                        <table className="myapps-detail-table myapps-volume-files-table" role="table">
                            <thead>
                                <tr>
                                    <th>{t('myAppsDetailPage.tabs.compose.workspace.columns.name')}</th>
                                    <th>{t('myAppsDetailPage.tabs.compose.workspace.columns.size')}</th>
                                    <th>{t('myAppsDetailPage.tabs.compose.workspace.columns.modified')}</th>
                                    <th className="myapps-cell-center">{t('myAppsDetailPage.tabs.compose.workspace.columns.action')}</th>
                                </tr>
                            </thead>
                            <tbody>
                                {currentDir ? (
                                    <tr
                                        onDoubleClick={() => void loadDirectory(parentDir)}
                                        style={{ cursor: 'pointer' }}
                                    >
                                        <td colSpan={4}>
                                            <Box
                                                component="button"
                                                type="button"
                                                onClick={() => void loadDirectory(parentDir)}
                                                sx={{
                                                    display: 'inline-flex',
                                                    alignItems: 'center',
                                                    gap: 1,
                                                    border: 0,
                                                    background: 'none',
                                                    p: 0,
                                                    color: palette.accent,
                                                    cursor: 'pointer',
                                                    fontSize: 13.5,
                                                    fontWeight: 600,
                                                }}
                                            >
                                                <CornerLeftUp size={15} />
                                                <span>..</span>
                                            </Box>
                                        </td>
                                    </tr>
                                ) : null}

                                {treeLoading && files.length === 0 ? (
                                    <tr>
                                        <td colSpan={4} className="myapps-empty-cell">
                                            <div className="myapps-table-inline-loading" aria-live="polite">
                                                <CircularProgress size={18} />
                                                <span>{t('myAppsDetailPage.tabs.compose.workspace.loadingFiles')}</span>
                                            </div>
                                        </td>
                                    </tr>
                                ) : files.length === 0 ? (
                                    <tr>
                                        <td colSpan={4} className="myapps-empty-cell">
                                            {t('myAppsDetailPage.tabs.compose.workspace.emptyFiles')}
                                        </td>
                                    </tr>
                                ) : (
                                    files.map((entry) => {
                                        const isDir = entry.type === 'dir'
                                        const isCore = !isDir && (entry.name === 'docker-compose.yml' || entry.name === 'docker-compose.yaml' || entry.name === '.env')
                                        return (
                                            <tr
                                                key={entry.path}
                                                onDoubleClick={() => {
                                                    if (isDir) void loadDirectory(entry.path)
                                                    else void openFileEditor(entry.path)
                                                }}
                                                style={{ cursor: 'pointer', userSelect: 'none' }}
                                            >
                                                <td>
                                                    <Box
                                                        component="button"
                                                        type="button"
                                                        onClick={() => {
                                                            if (isDir) void loadDirectory(entry.path)
                                                            else void openFileEditor(entry.path)
                                                        }}
                                                        sx={{
                                                            display: 'inline-flex',
                                                            alignItems: 'center',
                                                            gap: 1,
                                                            border: 0,
                                                            background: 'none',
                                                            p: 0,
                                                            color: isDir ? palette.accent : palette.text,
                                                            fontWeight: isDir || isCore ? 600 : 400,
                                                            fontSize: 13.5,
                                                            cursor: 'pointer',
                                                            textAlign: 'left',
                                                            '&:hover': { color: palette.accent, textDecoration: 'underline' },
                                                        }}
                                                    >
                                                        {isDir ? (
                                                            <Folder size={15} style={{ flexShrink: 0, color: '#3b82f6' }} />
                                                        ) : isCore ? (
                                                            <FileCode2 size={15} style={{ flexShrink: 0, color: palette.accent }} />
                                                        ) : (
                                                            <FileText size={15} style={{ flexShrink: 0, color: palette.subtleText }} />
                                                        )}
                                                        <span>{entry.name}</span>
                                                    </Box>
                                                </td>
                                                <td>{isDir ? '-' : formatByteSize(entry.size)}</td>
                                                <td>{formatModifiedTime(entry.last_modified, locale)}</td>
                                                <td className="myapps-cell-center">
                                                    <div className="myapps-table-actions-inline">
                                                        {isDir ? (
                                                            <button
                                                                type="button"
                                                                className="myapps-inline-link"
                                                                onClick={() => void loadDirectory(entry.path)}
                                                            >
                                                                {t('myAppsDetailPage.tabs.compose.workspace.openDir')}
                                                            </button>
                                                        ) : (
                                                            <button
                                                                type="button"
                                                                className="myapps-inline-link"
                                                                onClick={() => void openFileEditor(entry.path)}
                                                            >
                                                                {t('myAppsDetailPage.tabs.compose.workspace.editFile')}
                                                            </button>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        )
                                    })
                                )}
                            </tbody>
                        </table>
                        </div>
                    </div>
                ) : (
                    <Box
                        sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        border: `1px solid ${palette.border}`,
                        backgroundColor: palette.panelBg,
                        minHeight: 440,
                        height: 'min(540px, 62vh)',
                        }}
                    >
                        <Box
                        sx={{
                            px: 1.5,
                            py: 0.75,
                            borderBottom: `1px solid ${palette.border}`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            flexWrap: 'wrap',
                            gap: 1,
                            backgroundColor: palette.panelSoft,
                            flexShrink: 0,
                            minHeight: 41,
                            boxSizing: 'border-box',
                        }}
                        >
                        <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 0.75, minWidth: 0 }}>
                            <Button
                                size="small"
                                variant="text"
                                disabled={savingMode !== null}
                                onClick={() => closeFileEditor()}
                                startIcon={<ArrowLeft size={14} />}
                                sx={{ textTransform: 'none', borderRadius: 0, fontSize: 12.5, color: palette.subtleText, minWidth: 'auto', px: 0.75 }}
                            >
                                {t('myAppsDetailPage.tabs.compose.workspace.backToList')}
                            </Button>
                            <span style={{ color: palette.borderStrong }}>|</span>
                            <Box
                                component="button"
                                type="button"
                                disabled={savingMode !== null}
                                onClick={() => closeFileEditor('')}
                                sx={{
                                    border: 0,
                                    background: 'none',
                                    p: 0,
                                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                                    fontSize: 13,
                                    fontWeight: 500,
                                    color: palette.accent,
                                    cursor: 'pointer',
                                    '&:hover': { textDecoration: 'underline' },
                                }}
                            >
                                {appId}
                            </Box>
                            {editingSegments.map((segment, index) => {
                                const segmentPath = editingSegments.slice(0, index + 1).join('/')
                                const isLast = index === editingSegments.length - 1
                                return (
                                    <Box key={segmentPath} sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                                        <span style={{ color: palette.placeholderText }}>/</span>
                                        <Box
                                            component={isLast ? 'span' : 'button'}
                                            type={isLast ? undefined : 'button'}
                                            disabled={!isLast && savingMode !== null}
                                            onClick={() => {
                                                if (!isLast) closeFileEditor(segmentPath)
                                            }}
                                            sx={{
                                                border: 0,
                                                background: 'none',
                                                p: 0,
                                                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                                                fontSize: 13,
                                                fontWeight: isLast ? 600 : 500,
                                                color: isLast ? palette.text : palette.accent,
                                                cursor: isLast ? 'default' : 'pointer',
                                                '&:hover': !isLast ? { textDecoration: 'underline' } : {},
                                            }}
                                        >
                                            {segment}
                                        </Box>
                                    </Box>
                                )
                            })}
                            {isDirty ? (
                                <Box
                                    component="span"
                                    sx={{
                                        ml: 0.25,
                                        px: 0.75,
                                        py: 0.125,
                                        fontSize: 11,
                                        fontWeight: 600,
                                        color: '#d97706',
                                        backgroundColor: isDarkMode ? 'rgba(245, 158, 11, 0.16)' : '#fef3c7',
                                    }}
                                >
                                    {t('myAppsDetailPage.tabs.compose.workspace.unsavedBadge')}
                                </Box>
                            ) : null}
                        </Box>

                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                            {isDirty ? (
                                <Button
                                    size="small"
                                    variant="text"
                                    disabled={savingMode !== null}
                                    onClick={() => setDraftContent(originalContent)}
                                    startIcon={<RotateCcw size={13} />}
                                    sx={{ textTransform: 'none', borderRadius: 0, fontSize: 12, color: palette.subtleText }}
                                >
                                    {t('myAppsDetailPage.tabs.compose.workspace.reset')}
                                </Button>
                            ) : null}
                            <Button
                                size="small"
                                variant="outlined"
                                disabled={!isDirty || savingMode !== null || fileLoading}
                                onClick={() => void handleSave(false)}
                                startIcon={savingMode === 'save' ? <CircularProgress size={12} color="inherit" /> : <Save size={13} />}
                                sx={{ textTransform: 'none', borderRadius: 0, fontSize: 12 }}
                            >
                                {t('myAppsDetailPage.tabs.compose.workspace.save')}
                            </Button>
                            <Button
                                size="small"
                                variant="contained"
                                disabled={!isDirty || savingMode !== null || fileLoading || redeployDisabled}
                                onClick={() => void handleSave(true)}
                                sx={{ textTransform: 'none', borderRadius: 0, fontSize: 12, boxShadow: 'none' }}
                            >
                                {savingMode === 'save-redeploy'
                                    ? <CircularProgress size={13} color="inherit" />
                                    : t('myAppsDetailPage.tabs.compose.workspace.saveAndRedeploy')}
                            </Button>
                        </Box>
                        </Box>

                        {fileError ? (
                        <Box sx={{ px: 1.5, pt: 1 }}>
                            <Alert
                                severity="error"
                                variant="outlined"
                                sx={{ borderRadius: 0 }}
                                action={
                                    <Button color="inherit" size="small" onClick={() => void openFileEditor(editingPath)}>
                                        {t('myAppsDetailPage.tabs.compose.workspace.reloadFile')}
                                    </Button>
                                }
                            >
                                {fileError}
                            </Alert>
                        </Box>
                        ) : null}

                        <Box sx={{ flex: 1, minHeight: 320, position: 'relative' }}>
                        {fileLoading ? (
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 1, color: palette.subtleText }}>
                                <CircularProgress size={18} />
                                <Typography sx={{ fontSize: 13 }}>{t('myAppsDetailPage.tabs.compose.workspace.loadingContent')}</Typography>
                            </Box>
                        ) : (
                            <Box
                                sx={{
                                    position: 'absolute',
                                    top: 0,
                                    left: 0,
                                    right: 0,
                                    bottom: 0,
                                    overflow: 'hidden',
                                    '& .cm-editor': { height: '100%', fontSize: 13 },
                                    '& .cm-scroller': {
                                        overflow: 'auto',
                                        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace',
                                    },
                                    '& .cm-gutters': isDarkMode ? {
                                        backgroundColor: '#0d1117',
                                        borderRight: '1px solid rgba(255,255,255,0.06)',
                                    } : {},
                                }}
                            >
                                <CodeMirror
                                    value={draftContent}
                                    height="100%"
                                    style={{ height: '100%' }}
                                    theme={isDarkMode ? 'dark' : 'light'}
                                    extensions={editorExtensions}
                                    onChange={(value) => setDraftContent(value)}
                                    basicSetup={{
                                        lineNumbers: true,
                                        foldGutter: true,
                                        highlightActiveLine: true,
                                        highlightActiveLineGutter: true,
                                    }}
                                />
                            </Box>
                        )}
                        </Box>
                    </Box>
                )}
            </div>
        </div>
    )
}


