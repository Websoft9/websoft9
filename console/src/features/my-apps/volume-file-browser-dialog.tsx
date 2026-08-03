import {
    Alert,
    Button,
    IconButton,
    SvgIcon,
    TextField,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { SurfaceDialog, SurfaceFeedbackToast } from '../../shared/design-system/standard-surfaces'
import { getSurfacePalette } from '../../shared/design-system/surface-theme'
import '../terminal/terminal-page.css'

type VolumeFileItem = {
    name: string
    path: string
    item_type: 'directory' | 'file'
    size: number
    mode: string
    owner: string
    group: string
    accessed_at: number
    modified_at: number
    created_at: number
    text_viewable: boolean
}

type VolumeDirectoryResponse = {
    volume_name: string
    source_container: string
    current_path: string
    directory: VolumeFileItem
    truncated: boolean
    items: VolumeFileItem[]
}

type VolumeTextFileResponse = {
    volume_name: string
    source_container: string
    path: string
    content: string
}

type BrowserDisplayMode = 'list' | 'grid'
type FileVisualKind = 'directory' | 'config' | 'certificate' | 'code' | 'document' | 'archive' | 'spreadsheet' | 'media' | 'file'

type ContentScopeRect = {
    top: number
    left: number
    width: number
    height: number
}

type VolumeFileBrowserDialogProps = {
    open: boolean
    appId: string
    volumeId: string
    volumeLabel: string
    darkMode: boolean
    scopeRect: ContentScopeRect | null
    onClose: () => void
}

async function requestJson<T>(input: string): Promise<T> {
    const response = await fetch(input, {
        credentials: 'include',
        headers: { Accept: 'application/json' },
    })
    const payload = (await response.json().catch(() => null)) as { details?: string; message?: string } | T | null
    if (!response.ok) {
        const message = payload && typeof payload === 'object' && 'details' in payload
            ? payload.details ?? payload.message ?? `HTTP ${response.status}`
            : `HTTP ${response.status}`
        throw new Error(message)
    }
    return payload as T
}

function parentPath(path: string): string {
    const parts = path.split('/').filter(Boolean)
    return parts.length <= 1 ? '/' : `/${parts.slice(0, -1).join('/')}`
}

function buildVirtualPath(volumeId: string, currentPath: string) {
    return currentPath === '/' ? `/volumes/${volumeId}` : `/volumes/${volumeId}${currentPath}`
}

function parseVirtualPath(volumeId: string, input: string): string | null {
    const root = `/volumes/${volumeId}`
    const trimmed = input.trim().replace(/\/+$/, '')
    if (trimmed === root) return '/'
    if (!trimmed.startsWith(`${root}/`)) return null
    return trimmed.slice(root.length).replace(/\/+/g, '/') || '/'
}

function formatFileSize(size: number) {
    if (size < 1024) return `${size} B`
    const units = ['KB', 'MB', 'GB', 'TB']
    let value = size / 1024
    let index = 0
    while (value >= 1024 && index < units.length - 1) {
        value /= 1024
        index += 1
    }
    return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[index]}`
}

function formatTimestamp(value: number, locale: string) {
    if (!value) return '—'
    return new Intl.DateTimeFormat(locale === 'zh-CN' ? 'zh-CN' : 'en-US', {
        year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    }).format(new Date(value * 1000))
}

function BrowserIcon({ kind }: { kind: 'back' | 'forward' | 'up' | 'refresh' | 'close' | 'grid' | 'list' | 'eye' | 'eyeOff' }) {
    const pathByKind = {
        back: <path d="m14 6-6 6 6 6M8 12h9" />,
        forward: <path d="m10 6 6 6-6 6m6-6H7" />,
        up: <path d="m12 18V6m0 0-5 5m5-5 5 5" />,
        refresh: <path d="M19 8a7 7 0 1 0 1 6M19 4v4h-4" />,
        close: <path d="m7 7 10 10M17 7 7 17" />,
        grid: <path d="M4 4h6v6H4zm10 0h6v6h-6zM4 14h6v6H4zm10 0h6v6h-6z" />,
        list: <path d="M7 6h13M7 12h13M7 18h13M4 6h.01M4 12h.01M4 18h.01" />,
        eye: <><path d="M2.5 12s3.3-5.5 9.5-5.5S21.5 12 21.5 12 18.2 17.5 12 17.5 2.5 12 2.5 12Z" /><circle cx="12" cy="12" r="2.7" /></>,
        eyeOff: <><path d="m3 3 18 18M10.6 6.7A9.6 9.6 0 0 1 12 6.5c6.2 0 9.5 5.5 9.5 5.5a17 17 0 0 1-3.1 3.6M6.2 6.2A17 17 0 0 0 2.5 12s3.3 5.5 9.5 5.5c1.4 0 2.6-.3 3.7-.8" /><path d="M9.8 9.8a3 3 0 0 0 4.4 4.4" /></>,
    }
    return <SvgIcon fontSize="small" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.9">{pathByKind[kind]}</g></SvgIcon>
}

function getVisualKind(entry: VolumeFileItem): FileVisualKind {
    if (entry.item_type === 'directory') return 'directory'
    const extension = entry.name.slice(entry.name.lastIndexOf('.')).toLowerCase()
    if (['.conf', '.config', '.env', '.ini', '.properties', '.toml', '.yaml', '.yml'].includes(extension)) return 'config'
    if (['.cert', '.crt', '.key', '.pem', '.p12', '.pfx'].includes(extension)) return 'certificate'
    if (['.c', '.css', '.go', '.html', '.java', '.js', '.json', '.php', '.py', '.sh', '.sql', '.ts', '.tsx', '.xml'].includes(extension)) return 'code'
    if (['.doc', '.docx', '.md', '.pdf', '.rtf', '.txt'].includes(extension)) return 'document'
    if (['.7z', '.bz2', '.gz', '.rar', '.tar', '.tgz', '.xz', '.zip'].includes(extension)) return 'archive'
    if (['.csv', '.ods', '.xls', '.xlsx'].includes(extension)) return 'spreadsheet'
    if (['.aac', '.flac', '.m4a', '.mkv', '.mov', '.mp3', '.mp4', '.ogg', '.wav', '.webm'].includes(extension)) return 'media'
    return 'file'
}

function FileItemGlyph({ kind, variant }: { kind: FileVisualKind; variant: 'card' | 'list' }) {
    const className = variant === 'card' ? `terminal-files-card-visual terminal-files-card-visual-${kind}` : `terminal-files-list-icon terminal-files-list-icon-${kind}`
    if (kind === 'directory') {
        return <span className={className}><svg aria-hidden="true" className="terminal-files-item-glyph-svg" viewBox="0 0 64 64"><path d="M10 16a5 5 0 0 1 5-5h12.5c1.7 0 3.3.8 4.3 2.1l2.2 2.9H49a5 5 0 0 1 5 5v5H10v-10Z" fill="currentColor" opacity=".88" /><path d="M7 24.5A5.5 5.5 0 0 1 12.5 19H51a6 6 0 0 1 6 6V43a8 8 0 0 1-8 8H15a8 8 0 0 1-8-8V24.5Z" fill="currentColor" /><path d="M12 27h40" fill="none" stroke="rgba(255,255,255,.25)" strokeLinecap="round" strokeWidth="2.2" /></svg></span>
    }
    const accent = kind === 'code' ? <path d="m24 28-6 6 6 6m16-12 6 6-6 6m-8 4 4-20" fill="none" stroke="rgba(255,255,255,.92)" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
        : kind === 'certificate' ? <path d="M32 22 41 26v8c0 6-4.1 10.9-9 12-4.9-1.1-9-6-9-12v-8l9-4Z" fill="rgba(255,255,255,.92)" />
            : kind === 'media' ? <path d="M26 22v20l16-10-16-10Z" fill="rgba(255,255,255,.92)" />
                : <><path d="M22 27h20M22 35h20M22 43h14" fill="none" stroke="rgba(255,255,255,.92)" strokeLinecap="round" strokeWidth="3" />{kind === 'spreadsheet' ? <path d="M22 22h22v24H22zM29 22v24m7-24v24M22 30h22m-22 8h22" fill="none" stroke="rgba(255,255,255,.7)" strokeWidth="2" /> : null}</>
    return <span className={className}><svg aria-hidden="true" className="terminal-files-item-glyph-svg" viewBox="0 0 64 64"><path d="M16 6h24l10 10v38a6 6 0 0 1-6 6H20a6 6 0 0 1-6-6V12a6 6 0 0 1 2-4.4A5.8 5.8 0 0 1 20 6Z" fill="currentColor" /><path d="M40 6v10a3 3 0 0 0 3 3h10" fill="none" stroke="rgba(255,255,255,.72)" strokeLinejoin="round" strokeWidth="2.2" />{accent}</svg></span>
}

export function VolumeFileBrowserDialog({ open, appId, volumeId, volumeLabel, darkMode, scopeRect, onClose }: VolumeFileBrowserDialogProps) {
    const { t, i18n } = useTranslation('shell')
    const navigate = useNavigate()
    const palette = useMemo(() => getSurfacePalette(darkMode), [darkMode])
    const [currentPath, setCurrentPath] = useState('/')
    const [pathInputValue, setPathInputValue] = useState(buildVirtualPath(volumeId, '/'))
    const [history, setHistory] = useState<string[]>(['/'])
    const [historyIndex, setHistoryIndex] = useState(0)
    const [entries, setEntries] = useState<VolumeFileItem[]>([])
    const [, setSourceContainer] = useState('')
    const [truncated, setTruncated] = useState(false)
    const [loading, setLoading] = useState(false)
    const [previewLoading, setPreviewLoading] = useState(false)
    const [preview, setPreview] = useState<VolumeTextFileResponse | null>(null)
    const [search, setSearch] = useState('')
    const [displayMode, setDisplayMode] = useState<BrowserDisplayMode>('grid')
    const [showHiddenFiles, setShowHiddenFiles] = useState(false)
    const [selectedEntry, setSelectedEntry] = useState<VolumeFileItem | null>(null)
    const [feedback, setFeedback] = useState<string | null>(null)

    function showBrowseError(requestError: unknown) {
        const message = requestError instanceof Error ? requestError.message : ''
        const keyByMessage: Record<string, string> = {
            'Binary files cannot be previewed in the browser': 'myAppsDetailPage.tabs.volumes.fileManager.feedback.binaryFile',
            'Only UTF-8 text files can be previewed in the browser': 'myAppsDetailPage.tabs.volumes.fileManager.feedback.utf8Only',
            'Only files up to 1 MB can be previewed in the browser': 'myAppsDetailPage.tabs.volumes.fileManager.feedback.fileTooLarge',
            'The requested path does not exist or cannot be browsed': 'myAppsDetailPage.tabs.volumes.fileManager.feedback.fileNotFound',
            'The requested volume does not exist': 'myAppsDetailPage.tabs.volumes.fileManager.feedback.volumeNotFound',
            'The requested volume does not belong to this application': 'myAppsDetailPage.tabs.volumes.fileManager.feedback.volumeAccessDenied',
            'The application is not running or does not mount this volume': 'myAppsDetailPage.tabs.volumes.fileManager.feedback.volumeUnavailable',
            'The requested volume is mounted multiple times in one application container': 'myAppsDetailPage.tabs.volumes.fileManager.feedback.unsupportedMount',
            'The application container does not support volume file browsing': 'myAppsDetailPage.tabs.volumes.fileManager.feedback.containerUnsupported',
            'Application ID and volume ID are required': 'myAppsDetailPage.tabs.volumes.fileManager.feedback.invalidRequest',
            'Requested path resolves outside the allowed volume root': 'myAppsDetailPage.tabs.volumes.fileManager.feedback.invalidPath',
            'The volume root is not a valid file target': 'myAppsDetailPage.tabs.volumes.fileManager.feedback.invalidPath',
        }
        const key = keyByMessage[message]
            ?? (message.startsWith('Failed to list application containers:') ? 'myAppsDetailPage.tabs.volumes.fileManager.feedback.dockerUnavailable' : undefined)
            ?? (message.startsWith('Failed to browse the application container:') ? 'myAppsDetailPage.tabs.volumes.fileManager.feedback.containerFailed' : undefined)
            ?? (message.startsWith('The application container returned an invalid directory') ? 'myAppsDetailPage.tabs.volumes.fileManager.feedback.invalidResponse' : undefined)
            ?? 'myAppsDetailPage.tabs.volumes.fileManager.feedback.genericError'
        setFeedback(t(key))
    }

    const dialogStyle = useMemo(() => ({
        '& .MuiDialog-paper': {
            width: scopeRect ? `${Math.min(scopeRect.width * 0.95, 1440)}px` : 'min(95vw, 1440px)',
            maxWidth: scopeRect ? `${Math.min(scopeRect.width * 0.95, 1440)}px` : '1440px',
            height: scopeRect ? `${Math.max(scopeRect.height - 40, 560)}px` : 'calc(100dvh - 40px)',
            maxHeight: scopeRect ? `${Math.max(scopeRect.height - 40, 560)}px` : 'calc(100dvh - 40px)',
            borderRadius: 0,
            overflow: 'hidden',
        },
    }), [scopeRect])

    const themeVars = useMemo(() => ({
        '--terminal-files-surface-bg': palette.dialogBg,
        '--terminal-files-surface-soft': palette.panelSoft,
        '--terminal-files-border': palette.borderStrong,
        '--terminal-files-text': palette.text,
        '--terminal-files-subtle-text': palette.subtleText,
        '--terminal-files-editor-bg': palette.panelBg,
    }) as CSSProperties, [palette])

    const visibleEntries = useMemo(() => {
        const keyword = search.trim().toLowerCase()
        return entries
            .filter((entry) => showHiddenFiles || !entry.name.startsWith('.'))
            .filter((entry) => !keyword || entry.name.toLowerCase().includes(keyword))
            .sort((left, right) => left.item_type === right.item_type ? left.name.localeCompare(right.name, undefined, { numeric: true }) : left.item_type === 'directory' ? -1 : 1)
    }, [entries, search, showHiddenFiles])

    async function loadDirectory(path: string, historyAction: 'push' | 'none' = 'push') {
        if (!appId || !volumeId) return
        setLoading(true)
        setPreview(null)
        try {
            const response = await requestJson<VolumeDirectoryResponse>(`/api/myapps/${encodeURIComponent(appId)}/volumes/${encodeURIComponent(volumeId)}/browse/tree?path=${encodeURIComponent(path)}`)
            setCurrentPath(response.current_path)
            setPathInputValue(buildVirtualPath(volumeId, response.current_path))
            setEntries(response.items)
            setSourceContainer(response.source_container)
            setTruncated(response.truncated)
            setSelectedEntry(response.directory)
            if (historyAction === 'push') {
                setHistory((current) => current[current.length - 1] === response.current_path ? current : [...current.slice(0, historyIndex + 1), response.current_path])
                setHistoryIndex((current) => history[current] === response.current_path ? current : current + 1)
            }
        } catch (requestError) {
            showBrowseError(requestError)
        } finally {
            setLoading(false)
        }
    }

    async function openEntry(entry: VolumeFileItem) {
        if (entry.item_type === 'directory') {
            await loadDirectory(entry.path)
            return
        }
        if (!entry.text_viewable) return
        setPreviewLoading(true)
        try {
            const response = await requestJson<VolumeTextFileResponse>(`/api/myapps/${encodeURIComponent(appId)}/volumes/${encodeURIComponent(volumeId)}/browse/content?path=${encodeURIComponent(entry.path)}`)
            setPreview(response)
            setSourceContainer(response.source_container)
        } catch (requestError) {
            showBrowseError(requestError)
        } finally {
            setPreviewLoading(false)
        }
    }

    useEffect(() => {
        if (!open) return
        setCurrentPath('/')
        setPathInputValue(buildVirtualPath(volumeId, '/'))
        setHistory(['/'])
        setHistoryIndex(0)
        setSearch('')
        setPreview(null)
        setSelectedEntry(null)
        void loadDirectory('/', 'none')
    }, [open, appId, volumeId])

    const directoryCount = visibleEntries.filter((entry) => entry.item_type === 'directory').length
    const fileEntries = visibleEntries.filter((entry) => entry.item_type === 'file')
    const fileSize = fileEntries.reduce((sum, entry) => sum + entry.size, 0)

    return (
        <SurfaceDialog open={open} onClose={(_, reason) => { if (reason !== 'backdropClick' && reason !== 'escapeKeyDown') onClose() }} maxWidth="lg" darkMode={darkMode} scope="content" scopeRect={scopeRect} contentStrategy="viewport-fixed" sx={[dialogStyle, { zIndex: 1605 }]}>
            <div className={darkMode ? 'app-shell-root--dark' : undefined} style={{ height: '100%', padding: '14px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', minHeight: 0, backgroundColor: palette.dialogBg }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '0 2px 12px', flex: '0 0 auto' }}>
                    <div>
                        <Typography sx={{ fontSize: 18, fontWeight: 700, color: palette.text, lineHeight: 1.35 }}>{t('myAppsDetailPage.tabs.volumes.fileManager.title', { name: volumeLabel })}</Typography>
                    </div>
                    <Button onClick={onClose} variant="text" sx={{ minWidth: 'auto', color: palette.subtleText }}>{t('filesPage.actions.close')}</Button>
                </div>

                <div className="terminal-files-shell" style={{ ...themeVars, flex: '1 1 auto', minHeight: 0, gap: 12 }}>
                    <div className="terminal-files-toolbar-row">
                        <div className="terminal-files-toolbar-group">
                            <button className="terminal-files-toolbar-button" disabled={historyIndex <= 0 || loading || preview !== null} onClick={() => { const next = history[historyIndex - 1]; setHistoryIndex(historyIndex - 1); void loadDirectory(next, 'none') }} title={t('filesPage.actions.back')} type="button"><BrowserIcon kind="back" /></button>
                            <button className="terminal-files-toolbar-button" disabled={historyIndex >= history.length - 1 || loading || preview !== null} onClick={() => { const next = history[historyIndex + 1]; setHistoryIndex(historyIndex + 1); void loadDirectory(next, 'none') }} title={t('filesPage.actions.forward')} type="button"><BrowserIcon kind="forward" /></button>
                            <button className="terminal-files-toolbar-button" disabled={currentPath === '/' || loading || preview !== null} onClick={() => void loadDirectory(parentPath(currentPath))} title={t('filesPage.actions.up')} type="button"><BrowserIcon kind="up" /></button>
                            <button className="terminal-files-toolbar-button terminal-files-toolbar-button-primary" disabled={loading || preview !== null} onClick={() => void loadDirectory(currentPath, 'none')} title={t('myAppsDetailPage.tabs.volumes.fileManager.actions.refresh')} type="button"><BrowserIcon kind="refresh" /></button>
                        </div>
                        <div className="terminal-files-toolbar-paths">
                            <TextField className="terminal-files-path-input" size="small" value={pathInputValue} disabled={preview !== null} onChange={(event) => setPathInputValue(event.target.value)} onBlur={() => setPathInputValue(buildVirtualPath(volumeId, currentPath))} onKeyDown={(event) => { if (event.key !== 'Enter') return; const path = parseVirtualPath(volumeId, pathInputValue); if (path) void loadDirectory(path); else setFeedback(t('myAppsDetailPage.tabs.volumes.fileManager.feedback.invalidPath')) }} />
                            <TextField className="terminal-files-search-input" size="small" value={search} disabled={preview !== null} onChange={(event) => setSearch(event.target.value)} placeholder={t('filesPage.filters.searchPlaceholder')} />
                        </div>
                    </div>

                    <Alert
                        severity="info"
                        action={<Button color="inherit" size="small" onClick={() => { onClose(); navigate('/terminal') }}>{t('myAppsDetailPage.tabs.volumes.fileManager.actions.openTerminal')}</Button>}
                    >
                        {t('myAppsDetailPage.tabs.volumes.fileManager.readOnlyNotice')}
                    </Alert>
                    {truncated ? <Alert severity="info">Only the first 500 entries in this directory are shown.</Alert> : null}

                    <div className="terminal-files-layout">
                        <div className="terminal-files-browser-panel">
                            {loading || previewLoading ? <div className="terminal-files-progress" /> : null}
                            {preview ? (
                                <div className="terminal-files-browser-editor">
                                    <div className="terminal-files-browser-editor-header"><div className="terminal-files-browser-editor-header-main"><div className="terminal-files-browser-editor-title terminal-files-truncate">{buildVirtualPath(volumeId, preview.path)}</div><IconButton className="terminal-files-toolbar-button" onClick={() => setPreview(null)} title={t('filesPage.actions.close')}><BrowserIcon kind="close" /></IconButton></div></div>
                                    <pre className="terminal-files-browser-editor-body" style={{ margin: 0, padding: 16, overflow: 'auto', whiteSpace: 'pre', fontFamily: 'monospace', fontSize: 13 }}>{preview.content}</pre>
                                </div>
                            ) : !loading && visibleEntries.length > 0 ? (
                                displayMode === 'list' ? <div className="terminal-files-list-view"><div className="terminal-files-list-header terminal-files-list-row-frame"><div>{t('filesPage.table.name')}</div><div>{t('filesPage.table.size')}</div></div><div className="terminal-files-list-body">{visibleEntries.map((entry) => { const selected = selectedEntry?.path === entry.path; return <button key={entry.path} className={`terminal-files-list-row terminal-files-list-row-frame ${selected ? 'terminal-files-list-row-selected' : ''}`} onClick={() => setSelectedEntry(entry)} onDoubleClick={() => void openEntry(entry)} type="button"><div className="terminal-files-list-name"><FileItemGlyph kind={getVisualKind(entry)} variant="list" /><span className="terminal-files-truncate">{entry.name}</span></div><div>{entry.item_type === 'file' ? formatFileSize(entry.size) : '—'}</div></button> })}</div></div> : <div className="terminal-files-grid-body">{visibleEntries.map((entry) => { const selected = selectedEntry?.path === entry.path; return <button key={entry.path} className="terminal-files-grid-card" onClick={() => setSelectedEntry(entry)} onDoubleClick={() => void openEntry(entry)} type="button"><div className={`terminal-files-grid-card-hitbox ${selected ? 'terminal-files-grid-card-hitbox-selected' : ''}`}><FileItemGlyph kind={getVisualKind(entry)} variant="card" /><div className="terminal-files-grid-card-body"><div className="terminal-files-grid-card-title">{entry.name}</div></div></div></button> })}</div>
                            ) : !loading ? <div className="terminal-files-empty"><Typography sx={{ fontSize: 13.5, color: palette.subtleText }}>{t('myAppsDetailPage.tabs.volumes.fileManager.empty')}</Typography></div> : null}
                        </div>
                        <div className="terminal-files-inspector-panel">
                            <div className="terminal-files-inspector-header"><div className="terminal-files-inspector-header-main"><div className="terminal-files-inspector-header-title terminal-files-truncate">{selectedEntry?.name || t('filesPage.inspector.emptyTitle')}</div></div></div>
                            <div className="terminal-files-inspector-body terminal-files-inspector-body-classic">{selectedEntry ? <div className="terminal-files-inspector-rows terminal-files-inspector-rows-classic"><div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.metadata.mode')}</Typography><Typography className="terminal-files-inspector-value">{selectedEntry.mode || '—'}</Typography></div><div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.metadata.owner')}</Typography><Typography className="terminal-files-inspector-value">{selectedEntry.owner || '—'}</Typography></div><div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.metadata.group')}</Typography><Typography className="terminal-files-inspector-value">{selectedEntry.group || '—'}</Typography></div><div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.table.size')}</Typography><Typography className="terminal-files-inspector-value">{selectedEntry.item_type === 'file' ? formatFileSize(selectedEntry.size) : '—'}</Typography></div><div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.metadata.modified')}</Typography><Typography className="terminal-files-inspector-value">{formatTimestamp(selectedEntry.modified_at, i18n.language)}</Typography></div><div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.metadata.accessed')}</Typography><Typography className="terminal-files-inspector-value">{formatTimestamp(selectedEntry.accessed_at, i18n.language)}</Typography></div><div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.metadata.created')}</Typography><Typography className="terminal-files-inspector-value">{formatTimestamp(selectedEntry.created_at, i18n.language)}</Typography></div></div> : <div className="terminal-files-empty terminal-files-empty-inspector"><Typography sx={{ fontSize: 13.5, color: palette.subtleText }}>{t('filesPage.inspector.emptyBody')}</Typography></div>}</div>
                        </div>
                    </div>

                    <div className="terminal-files-footer"><div className="terminal-files-footer-stats">{`${directoryCount} ${t('filesPage.footer.directories')}, ${fileEntries.length} ${t('filesPage.footer.files')} (${formatFileSize(fileSize)})`}</div><div className="terminal-files-footer-actions"><IconButton className={`terminal-files-footer-button ${showHiddenFiles ? 'terminal-files-footer-button-active' : ''}`} onClick={() => setShowHiddenFiles((current) => !current)} title={t('filesPage.footer.hiddenFiles')}>{showHiddenFiles ? <BrowserIcon kind="eyeOff" /> : <BrowserIcon kind="eye" />}</IconButton><IconButton className="terminal-files-footer-button" onClick={() => setDisplayMode((current) => current === 'grid' ? 'list' : 'grid')} title={displayMode === 'grid' ? t('filesPage.footer.listView') : t('filesPage.footer.gridView')}><BrowserIcon kind={displayMode === 'grid' ? 'list' : 'grid'} /></IconButton></div></div>
                </div>
            </div>
            <SurfaceFeedbackToast open={Boolean(feedback)} severity="error" message={feedback ?? ''} onClose={() => setFeedback(null)} scope="content" scopeRect={scopeRect} darkMode={darkMode} zIndex={1610} />
        </SurfaceDialog>
    )
}
