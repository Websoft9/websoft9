import {
    Alert,
    Button,
    Checkbox,
    CircularProgress,
    IconButton,
    Snackbar,
    Stack,
    SvgIcon,
    TextField,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useRef, useState, type CSSProperties, type ChangeEvent, type MouseEvent as ReactMouseEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { SurfaceDialog } from '../../shared/design-system/standard-surfaces'
import { getSurfacePalette } from '../../shared/design-system/surface-theme'
import '../terminal/terminal-page.css'

type VolumeFileItem = {
    name: string
    path: string
    item_type: 'directory' | 'file'
    size: number
    mode?: string | null
    owner?: string | null
    group?: string | null
    accessed_at?: string | null
    modified_at?: string | null
    created_at?: string | null
    text_editable: boolean
}

type VolumeDirectoryResponse = {
    volume_name: string
    current_path: string
    metadata?: VolumeMetadataResponse
    items: VolumeFileItem[]
}

type VolumeTextFileResponse = {
    volume_name: string
    path: string
    content: string
}

type VolumeMetadataResponse = {
    volume_name: string
    name: string
    path: string
    item_type: 'directory' | 'file'
    size: number
    mode?: string | null
    owner?: string | null
    group?: string | null
    accessed_at?: string | null
    modified_at?: string | null
    created_at?: string | null
    text_editable: boolean
}

type PermissionBits = {
    read: boolean
    write: boolean
    execute: boolean
}

type PropertiesForm = {
    targetName: string
    owner: string
    group: string
    ownerPermissions: PermissionBits
    groupPermissions: PermissionBits
    otherPermissions: PermissionBits
}

type DialogState =
    | { type: 'create-folder' | 'create-file' }
    | { type: 'rename' | 'delete' | 'properties'; item: VolumeFileItem }
    | { type: 'overwrite-upload'; fileName: string; contentBase64: string }
    | null

type FeedbackState = {
    message: string
}

type BrowserClipboardState = {
    path: string
    name: string
    itemType: VolumeFileItem['item_type']
    mode: 'copy' | 'cut'
} | null

type BrowserDisplayMode = 'list' | 'grid'

type ContentScopeRect = {
    top: number
    left: number
    width: number
    height: number
}

type VolumeFileManagerDialogProps = {
    open: boolean
    volumeId: string
    volumeLabel: string
    darkMode: boolean
    scopeRect: ContentScopeRect | null
    onClose: () => void
}

type FileVisualKind = 'directory' | 'image' | 'config' | 'certificate' | 'code' | 'document' | 'archive' | 'spreadsheet' | 'media' | 'file'

const IMAGE_FILE_EXTENSIONS = new Set(['.apng', '.avif', '.bmp', '.gif', '.ico', '.jpeg', '.jpg', '.png', '.svg', '.webp'])
const CONFIG_FILE_EXTENSIONS = new Set(['.conf', '.config', '.env', '.ini', '.properties', '.toml', '.yaml', '.yml'])
const CERTIFICATE_FILE_EXTENSIONS = new Set(['.cert', '.crt', '.key', '.pem', '.p12', '.pfx'])
const CODE_FILE_EXTENSIONS = new Set(['.c', '.cc', '.cpp', '.css', '.go', '.h', '.hpp', '.html', '.java', '.js', '.json', '.mdx', '.php', '.py', '.rb', '.rs', '.sh', '.sql', '.ts', '.tsx', '.vue', '.xml'])
const DOCUMENT_FILE_EXTENSIONS = new Set(['.doc', '.docx', '.md', '.pdf', '.rtf', '.txt'])
const ARCHIVE_FILE_EXTENSIONS = new Set(['.7z', '.bz2', '.gz', '.rar', '.tar', '.tgz', '.xz', '.zip'])
const SPREADSHEET_FILE_EXTENSIONS = new Set(['.csv', '.numbers', '.ods', '.xls', '.xlsx'])
const MEDIA_FILE_EXTENSIONS = new Set(['.aac', '.flac', '.m4a', '.mkv', '.mov', '.mp3', '.mp4', '.ogg', '.wav', '.webm'])

function getDetailDialogPalette(darkMode: boolean) {
    const palette = getSurfacePalette(darkMode)

    return {
        panel: palette.dialogBg,
        panelSoft: palette.panelSoft,
        panelMuted: palette.panelMuted,
        text: palette.text,
        subtleText: palette.subtleText,
        border: palette.borderStrong,
        divider: palette.divider,
        accent: palette.accent,
        danger: palette.danger,
        overlay: palette.overlay,
    }
}

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
    const response = await fetch(input, {
        credentials: 'include',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
            ...(init?.headers ?? {}),
        },
        ...init,
    })

    const payload = (await response.json().catch(() => null)) as { details?: string; message?: string } | T | null
    if (!response.ok) {
        const errorMessage =
            payload && typeof payload === 'object' && 'details' in payload
                ? payload.details ?? payload.message ?? `HTTP ${response.status}`
                : `HTTP ${response.status}`
        throw new Error(errorMessage)
    }

    return payload as T
}

function parentPath(path: string): string {
    if (path === '/') {
        return '/'
    }

    const parts = path.split('/').filter(Boolean)
    if (parts.length <= 1) {
        return '/'
    }

    return `/${parts.slice(0, -1).join('/')}`
}

function buildSiblingPath(path: string, nextName: string): string {
    const parent = parentPath(path)
    return parent === '/' ? `/${nextName}` : `${parent}/${nextName}`
}

function buildVirtualPath(volumeId: string, currentPath: string) {
    return currentPath === '/' ? `/volumes/${volumeId}` : `/volumes/${volumeId}${currentPath}`
}

function parseVirtualPath(volumeId: string, input: string): string | null {
    const trimmed = input.trim()
    const volumePrefix = `/volumes/${volumeId}`
    if (trimmed === volumePrefix || trimmed === `${volumePrefix}/`) {
        return '/'
    }
    if (!trimmed.startsWith(`${volumePrefix}/`)) {
        return null
    }

    const normalized = trimmed.slice(volumePrefix.length)
    const cleaned = normalized.replace(/\/+/g, '/').replace(/\/+$|^$/g, '')
    return cleaned ? `/${cleaned}` : '/'
}

function formatIdentity(value: string | null | undefined): string {
    if (!value) {
        return '—'
    }

    const match = value.match(/^\s*(.+?)\s+\((.+)\)\s*$/)
    if (!match) {
        return value
    }

    return match[1] === match[2] ? match[1] : value
}

function formatTimestamp(value: string | null | undefined, locale: string) {
    if (!value) {
        return '—'
    }

    return new Intl.DateTimeFormat(locale === 'zh-CN' ? 'zh-CN' : 'en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    }).format(new Date(value))
}

function formatFileSize(size: number) {
    if (size < 1024) {
        return `${size} B`
    }
    const units = ['KB', 'MB', 'GB', 'TB']
    let value = size / 1024
    let unitIndex = 0
    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024
        unitIndex += 1
    }
    return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`
}

function normalizeActionErrorMessage(message: string, fallbackName?: string) {
    const normalized = message.toLowerCase()
    if (normalized.includes('already exists') || normalized.includes('file exists') || normalized.includes('exists')) {
        return fallbackName ? `${fallbackName} 已存在。` : '当前目录中已存在同名条目。'
    }

    if (normalized.includes('does not exist') || normalized.includes('not found')) {
        return fallbackName ? `${fallbackName} 已不存在。` : '目标条目已不存在。'
    }

    return message
}

function getFileExtension(name: string): string {
    const lastDotIndex = name.lastIndexOf('.')
    if (lastDotIndex < 0) {
        return ''
    }

    return name.slice(lastDotIndex).toLowerCase()
}

function getVisualKind(item: Pick<VolumeFileItem, 'item_type' | 'name'>): FileVisualKind {
    if (item.item_type === 'directory') {
        return 'directory'
    }

    const extension = getFileExtension(item.name)
    if (IMAGE_FILE_EXTENSIONS.has(extension)) return 'image'
    if (CONFIG_FILE_EXTENSIONS.has(extension)) return 'config'
    if (CERTIFICATE_FILE_EXTENSIONS.has(extension)) return 'certificate'
    if (CODE_FILE_EXTENSIONS.has(extension)) return 'code'
    if (DOCUMENT_FILE_EXTENSIONS.has(extension)) return 'document'
    if (ARCHIVE_FILE_EXTENSIONS.has(extension)) return 'archive'
    if (SPREADSHEET_FILE_EXTENSIONS.has(extension)) return 'spreadsheet'
    if (MEDIA_FILE_EXTENSIONS.has(extension)) return 'media'
    return 'file'
}

function fileToBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onerror = () => reject(new Error('Failed to read file'))
        reader.onload = () => {
            const result = reader.result
            if (typeof result !== 'string') {
                reject(new Error('Failed to read file'))
                return
            }
            resolve(result.includes(',') ? result.split(',')[1] : result)
        }
        reader.readAsDataURL(file)
    })
}

function parsePermissionMode(mode: string | null | undefined): [PermissionBits, PermissionBits, PermissionBits] {
    const normalized = (mode || '').padEnd(10, '-')
    const readBits = (segment: string): PermissionBits => ({
        read: segment[0] === 'r',
        write: segment[1] === 'w',
        execute: ['x', 's', 't'].includes(segment[2] ?? '-'),
    })
    return [readBits(normalized.slice(1, 4)), readBits(normalized.slice(4, 7)), readBits(normalized.slice(7, 10))]
}

function createPropertiesForm(item: VolumeFileItem): PropertiesForm {
    const [ownerPermissions, groupPermissions, otherPermissions] = parsePermissionMode(item.mode)
    return {
        targetName: item.name,
        owner: formatIdentity(item.owner),
        group: formatIdentity(item.group),
        ownerPermissions,
        groupPermissions,
        otherPermissions,
    }
}

function createDirectoryMetadata(volumeName: string, currentPath: string, metadata?: VolumeMetadataResponse | null): VolumeMetadataResponse {
    if (metadata) {
        return metadata
    }

    const trimmed = currentPath === '/' ? volumeName : currentPath.split('/').filter(Boolean).at(-1) || volumeName
    return {
        volume_name: volumeName,
        name: trimmed,
        path: currentPath,
        item_type: 'directory',
        size: 0,
        mode: null,
        owner: null,
        group: null,
        accessed_at: null,
        modified_at: null,
        created_at: null,
        text_editable: false,
    }
}

function ToolbarGlyph({ kind }: { kind: 'download' | 'rename' | 'trash' | 'edit' | 'save' | 'close' | 'copy' | 'move' | 'properties' }) {
    const strokes = { fill: 'none', stroke: 'currentColor', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, strokeWidth: 2.1 }
    if (kind === 'download') return <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24"><path {...strokes} d="M12 4V14" /><path {...strokes} d="M8 10L12 14L16 10" /><path {...strokes} d="M5 19H19" /></svg>
    if (kind === 'rename') return <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24"><path {...strokes} d="M4 17.5V20H6.5L16.8 9.7L14.3 7.2L4 17.5Z" /><path {...strokes} d="M13.6 7.9L16.1 10.4" /></svg>
    if (kind === 'trash') return <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24"><path {...strokes} d="M4 7H20" /><path {...strokes} d="M9 7V5.5C9 4.67 9.67 4 10.5 4H13.5C14.33 4 15 4.67 15 5.5V7" /><path {...strokes} d="M7 7L8 19C8.07 19.84 8.77 20.5 9.61 20.5H14.39C15.23 20.5 15.93 19.84 16 19L17 7" /><path {...strokes} d="M10 11V17" /><path {...strokes} d="M14 11V17" /></svg>
    if (kind === 'save') return <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24"><path {...strokes} d="M6 4H16L19 7V20H5V5C5 4.4 5.4 4 6 4Z" /><path {...strokes} d="M8 4V9H15V4" /><path {...strokes} d="M8 15H16" /></svg>
    if (kind === 'close') return <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24"><path {...strokes} d="M7 7L17 17" /><path {...strokes} d="M17 7L7 17" /></svg>
    if (kind === 'copy') return <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24"><path {...strokes} d="M9 9h11v11H9z" /><path {...strokes} d="M4 15V4h11" /></svg>
    if (kind === 'move') return <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24"><path {...strokes} d="M13 5L19 11L13 17" /><path {...strokes} d="M5 11H19" /></svg>
    if (kind === 'properties') return <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" strokeWidth="2" /><path {...strokes} d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09A1.65 1.65 0 0 0 15 4.6a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.17.55.73.93 1.31 1H21a2 2 0 0 1 0 4h-.29c-.58.07-1.14.45-1.31 1Z" /></svg>
    if (kind === 'edit') return <ToolbarGlyph kind="rename" />
    return null
}

function FileItemGlyph({ kind, variant, active = false }: { kind: FileVisualKind; variant: 'card' | 'list'; active?: boolean }) {
    const className = variant === 'card' ? `terminal-files-card-visual terminal-files-card-visual-${kind}` : `terminal-files-list-icon terminal-files-list-icon-${kind}`
    if (kind === 'directory') {
        return (
            <span className={className}>
                <svg aria-hidden="true" className="terminal-files-item-glyph-svg" viewBox="0 0 64 64">
                    {active ? (
                        <>
                            <path d="M11 19a5 5 0 0 1 5-5h10.8c1.7 0 3.3.8 4.3 2.1l1.8 2.4H49a5 5 0 0 1 4.9 5.9l-1.2 7.2A8 8 0 0 1 44.8 38H15.2a8 8 0 0 1-7.9-9.3l1.2-7.2A5 5 0 0 1 11 19Z" fill="currentColor" opacity="0.9" />
                            <path d="M8 29.5A6.5 6.5 0 0 1 14.5 23H53a4 4 0 0 1 3.9 4.8l-2.3 11.8A8 8 0 0 1 46.8 46H15a8 8 0 0 1-7.8-9.8L8 29.5Z" fill="currentColor" />
                            <path d="M16 27h17" fill="none" stroke="rgba(255,255,255,0.28)" strokeLinecap="round" strokeWidth="2.2" />
                        </>
                    ) : (
                        <>
                            <path d="M10 16a5 5 0 0 1 5-5h12.5c1.7 0 3.3.8 4.3 2.1l2.2 2.9H49a5 5 0 0 1 5 5v5H10v-10Z" fill="currentColor" opacity="0.88" />
                            <path d="M7 24.5A5.5 5.5 0 0 1 12.5 19H51a6 6 0 0 1 6 6V43a8 8 0 0 1-8 8H15a8 8 0 0 1-8-8V24.5Z" fill="currentColor" />
                            <path d="M12 27h40" fill="none" stroke="rgba(255,255,255,0.22)" strokeLinecap="round" strokeWidth="2.2" />
                            <path d="M13 18h17.5c1.1 0 2.2.5 2.8 1.4l1 1.6H13.5a.5.5 0 0 1-.5-.5v-2a.5.5 0 0 1 .5-.5Z" fill="rgba(255,255,255,0.34)" />
                        </>
                    )}
                </svg>
            </span>
        )
    }

    const accent = (() => {
        if (kind === 'image') {
            return (
                <>
                    <circle cx="24" cy="29" r="4" fill="rgba(255,255,255,0.92)" />
                    <path d="M18 47l8-9 6 6 5-7 9 10H18Z" fill="rgba(255,255,255,0.92)" />
                </>
            )
        }
        if (kind === 'config') {
            return (
                <>
                    <path d="M22 27h18" fill="none" stroke="rgba(255,255,255,0.92)" strokeLinecap="round" strokeWidth="3" />
                    <path d="M22 36h18" fill="none" stroke="rgba(255,255,255,0.92)" strokeLinecap="round" strokeWidth="3" />
                    <circle cx="28" cy="27" r="3.6" fill="currentColor" opacity="0.32" />
                    <circle cx="35" cy="36" r="3.6" fill="currentColor" opacity="0.32" />
                </>
            )
        }
        if (kind === 'certificate') {
            return (
                <>
                    <path d="M32 22 41 26v8c0 6-4.1 10.9-9 12-4.9-1.1-9-6-9-12v-8l9-4Z" fill="rgba(255,255,255,0.92)" />
                    <path d="m28.5 33 2.5 2.5 5-5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.6" opacity="0.4" />
                </>
            )
        }
        if (kind === 'code') {
            return <path d="m24 28-6 6 6 6m16-12 6 6-6 6m-8 4 4-20" fill="none" stroke="rgba(255,255,255,0.92)" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
        }
        if (kind === 'document') {
            return (
                <>
                    <path d="M22 26h20" fill="none" stroke="rgba(255,255,255,0.92)" strokeLinecap="round" strokeWidth="3" />
                    <path d="M22 34h20" fill="none" stroke="rgba(255,255,255,0.92)" strokeLinecap="round" strokeWidth="3" />
                    <path d="M22 42h14" fill="none" stroke="rgba(255,255,255,0.92)" strokeLinecap="round" strokeWidth="3" />
                </>
            )
        }
        if (kind === 'archive') {
            return (
                <>
                    <path d="M29 20h6v24h-6Z" fill="rgba(255,255,255,0.92)" />
                    <path d="M29 24h6M29 30h6M29 36h6" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" opacity="0.3" />
                </>
            )
        }
        if (kind === 'spreadsheet') {
            return (
                <>
                    <path d="M21 24h22v20H21Z" fill="rgba(255,255,255,0.92)" />
                    <path d="M28.5 24v20M35.5 24v20M21 31h22M21 38h22" fill="none" stroke="currentColor" strokeWidth="2.2" opacity="0.28" />
                </>
            )
        }
        if (kind === 'media') {
            return <path d="M26 22v20l16-10-16-10Z" fill="rgba(255,255,255,0.92)" />
        }

        return <path d="M22 26h20M22 34h16M22 42h12" fill="none" stroke="rgba(255,255,255,0.92)" strokeLinecap="round" strokeWidth="3" />
    })()

    return (
        <span className={className}>
            <svg aria-hidden="true" className="terminal-files-item-glyph-svg" viewBox="0 0 64 64">
                <path d="M16 6h24l10 10v38a6 6 0 0 1-6 6H20a6 6 0 0 1-6-6V12a6 6 0 0 1 2-4.4A5.8 5.8 0 0 1 20 6Z" fill="currentColor" />
                <path d="M40 6v10a3 3 0 0 0 3 3h10" fill="rgba(255,255,255,0.3)" />
                <path d="M40 6v10a3 3 0 0 0 3 3h10" fill="none" stroke="rgba(255,255,255,0.82)" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" />
                <path d="M20 17h14" fill="none" stroke="rgba(255,255,255,0.18)" strokeLinecap="round" strokeWidth="2.2" />
                {accent}
            </svg>
        </span>
    )
}

function TerminalNavGlyph({ kind }: { kind: 'back' | 'forward' | 'up' | 'refresh' | 'search' }) {
    return <span className={`terminal-files-toolbar-glyph terminal-files-toolbar-glyph-${kind}`} aria-hidden="true" />
}

function FolderCreateIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M3 6.75A1.75 1.75 0 0 1 4.75 5h4.17c.46 0 .9.18 1.24.51l1.08 1.07c.16.16.37.25.59.25h7.42A1.75 1.75 0 0 1 21 8.58v8.67A1.75 1.75 0 0 1 19.25 19H4.75A1.75 1.75 0 0 1 3 17.25V6.75Zm10 2.75v2h2a.75.75 0 0 1 0 1.5h-2v2a.75.75 0 0 1-1.5 0v-2h-2a.75.75 0 0 1 0-1.5h2v-2a.75.75 0 0 1 1.5 0Z" />
        </SvgIcon>
    )
}

function FileCreateIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M7.75 3A1.75 1.75 0 0 0 6 4.75v14.5C6 20.22 6.78 21 7.75 21h8.5A1.75 1.75 0 0 0 18 19.25V8.56c0-.46-.18-.9-.5-1.23l-3.83-3.83A1.74 1.74 0 0 0 12.44 3H7.75Zm4.75 7.75v2h2a.75.75 0 0 1 0 1.5h-2v2a.75.75 0 0 1-1.5 0v-2h-2a.75.75 0 0 1 0-1.5h2v-2a.75.75 0 0 1 1.5 0Z" />
        </SvgIcon>
    )
}

function UploadFileIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M12 3.75a.75.75 0 0 1 .53.22l4 4a.75.75 0 1 1-1.06 1.06l-2.72-2.72V15a.75.75 0 0 1-1.5 0V6.31L8.53 9.03a.75.75 0 0 1-1.06-1.06l4-4A.75.75 0 0 1 12 3.75ZM5.75 14A.75.75 0 0 1 6.5 14.75v2.5c0 .41.34.75.75.75h9.5a.75.75 0 0 0 .75-.75v-2.5a.75.75 0 0 1 1.5 0v2.5c0 1.24-1.01 2.25-2.25 2.25h-9.5A2.25 2.25 0 0 1 5 17.25v-2.5A.75.75 0 0 1 5.75 14Z" />
        </SvgIcon>
    )
}

function GridViewIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M4.75 4h4.5C10.22 4 11 4.78 11 5.75v4.5C11 11.22 10.22 12 9.25 12h-4.5A1.75 1.75 0 0 1 3 10.25v-4.5C3 4.78 3.78 4 4.75 4Zm10 0h4.5C20.22 4 21 4.78 21 5.75v4.5c0 .97-.78 1.75-1.75 1.75h-4.5A1.75 1.75 0 0 1 13 10.25v-4.5c0-.97.78-1.75 1.75-1.75Zm-10 10h4.5c.97 0 1.75.78 1.75 1.75v4.5c0 .97-.78 1.75-1.75 1.75h-4.5A1.75 1.75 0 0 1 3 20.25v-4.5C3 14.78 3.78 14 4.75 14Zm10 0h4.5c.97 0 1.75.78 1.75 1.75v4.5c0 .97-.78 1.75-1.75 1.75h-4.5A1.75 1.75 0 0 1 13 20.25v-4.5c0-.97.78-1.75 1.75-1.75Z" />
        </SvgIcon>
    )
}

function ListViewIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M5 5.25A1.25 1.25 0 1 1 2.5 5.25 1.25 1.25 0 0 1 5 5.25Zm16 .75H7a.75.75 0 0 1 0-1.5h14a.75.75 0 0 1 0 1.5ZM5 12a1.25 1.25 0 1 1-2.5 0A1.25 1.25 0 0 1 5 12Zm16 .75H7a.75.75 0 0 1 0-1.5h14a.75.75 0 0 1 0 1.5ZM5 18.75A1.25 1.25 0 1 1 2.5 18.75 1.25 1.25 0 0 1 5 18.75ZM21 19.5H7a.75.75 0 0 1 0-1.5h14a.75.75 0 0 1 0 1.5Z" />
        </SvgIcon>
    )
}

function HiddenFilesIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M12 5c5.05 0 8.88 3.48 10.24 5.63a1.4 1.4 0 0 1 0 1.5C20.88 14.27 17.05 17.75 12 17.75S3.12 14.27 1.76 12.13a1.4 1.4 0 0 1 0-1.5C3.12 8.48 6.95 5 12 5Zm0 2C8.4 7 5.43 9.3 3.36 11.38 5.43 13.46 8.4 15.75 12 15.75s6.57-2.3 8.64-4.37C18.57 9.3 15.6 7 12 7Zm0 1.75A2.63 2.63 0 1 1 9.38 11.38 2.63 2.63 0 0 1 12 8.75Zm0 1.5a1.13 1.13 0 1 0 1.13 1.13A1.13 1.13 0 0 0 12 10.25Z" />
        </SvgIcon>
    )
}

function HiddenFilesOffIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="m4.03 3.97 16 16-1.06 1.06-3.02-3.01c-1.19.47-2.49.73-3.95.73-5.05 0-8.88-3.48-10.24-5.62a1.4 1.4 0 0 1 0-1.5A16.77 16.77 0 0 1 6.1 7.44L2.97 4.31l1.06-1.06ZM7.25 8.59c-1.57.85-2.93 2.01-3.89 2.99 2.07 2.08 5.04 4.37 8.64 4.37 1 0 1.91-.18 2.76-.5l-1.58-1.58a2.63 2.63 0 0 1-3.05-3.05L7.25 8.59ZM12 5c5.05 0 8.88 3.48 10.24 5.63a1.4 1.4 0 0 1 0 1.5 16.7 16.7 0 0 1-4.48 4.19l-1.12-1.12c1.65-.95 3.03-2.19 3.99-3.19C18.57 9.3 15.6 7 12 7c-.9 0-1.75.14-2.53.4L8.15 6.08C9.33 5.39 10.61 5 12 5Z" />
        </SvgIcon>
    )
}

function PermissionMatrix({
    label,
    value,
    onChange,
}: {
    label: string
    value: PermissionBits
    onChange: (next: PermissionBits) => void
}) {
    return (
        <div style={{ display: 'grid', gridTemplateColumns: '110px repeat(3, auto)', alignItems: 'center', gap: 8 }}>
            <Typography sx={{ fontSize: 13, fontWeight: 600 }}>{label}</Typography>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><Checkbox size="small" checked={value.read} onChange={(event) => onChange({ ...value, read: event.target.checked })} />R</label>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><Checkbox size="small" checked={value.write} onChange={(event) => onChange({ ...value, write: event.target.checked })} />W</label>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><Checkbox size="small" checked={value.execute} onChange={(event) => onChange({ ...value, execute: event.target.checked })} />X</label>
        </div>
    )
}

export function VolumeFileManagerDialog({
    open,
    volumeId,
    volumeLabel,
    darkMode,
    scopeRect,
    onClose,
}: VolumeFileManagerDialogProps) {
    const { t, i18n } = useTranslation('shell')
    const locale = i18n.resolvedLanguage ?? i18n.language ?? 'en'
    const uploadInputRef = useRef<HTMLInputElement | null>(null)
    const browserPanelRef = useRef<HTMLDivElement | null>(null)
    const contextMenuNodeRef = useRef<HTMLDivElement | null>(null)
    const contextMenuCleanupRef = useRef<(() => void) | null>(null)
    const [currentPath, setCurrentPath] = useState('/')
    const [history, setHistory] = useState<string[]>(['/'])
    const [historyIndex, setHistoryIndex] = useState(0)
    const [entries, setEntries] = useState<VolumeFileItem[]>([])
    const [currentDirectoryMetadata, setCurrentDirectoryMetadata] = useState<VolumeMetadataResponse | null>(null)
    const [loading, setLoading] = useState(false)
    const [actionSubmitting, setActionSubmitting] = useState(false)
    const [selectedEntry, setSelectedEntry] = useState<VolumeFileItem | null>(null)
    const [editorPath, setEditorPath] = useState<string | null>(null)
    const [editorContent, setEditorContent] = useState('')
    const [editorInitialContent, setEditorInitialContent] = useState('')
    const [editorLoading, setEditorLoading] = useState(false)
    const [pathInputValue, setPathInputValue] = useState(buildVirtualPath(volumeId, '/'))
    const [directorySearch, setDirectorySearch] = useState('')
    const [displayMode, setDisplayMode] = useState<BrowserDisplayMode>('grid')
    const [showHiddenFiles, setShowHiddenFiles] = useState(false)
    const [dialogState, setDialogState] = useState<DialogState>(null)
    const [dialogValue, setDialogValue] = useState('')
    const [propertiesForm, setPropertiesForm] = useState<PropertiesForm | null>(null)
    const [browserClipboard, setBrowserClipboard] = useState<BrowserClipboardState>(null)
    const [feedback, setFeedback] = useState<FeedbackState | null>(null)
    const surfacePalette = useMemo(() => getSurfacePalette(darkMode), [darkMode])
    const dialogPalette = useMemo(() => getDetailDialogPalette(darkMode), [darkMode])

    const contentScopedDialogPlacementSx = useMemo(() => ({
        '& .MuiDialog-container': {
            alignItems: 'flex-start',
            justifyContent: 'center',
            pt: { xs: 3, md: 3 },
            pb: { xs: 1.5, md: 2.5 },
        },
    }), [])

    const dialogCancelButtonSx = useMemo(() => ({
        minWidth: 68,
        borderRadius: 0,
        boxShadow: 'none',
        border: `1px solid ${dialogPalette.border}`,
        backgroundColor: surfacePalette.actionBg,
        color: dialogPalette.subtleText,
        '&:hover': {
            backgroundColor: surfacePalette.actionHover,
            color: dialogPalette.text,
            boxShadow: 'none',
        },
    }), [dialogPalette.border, dialogPalette.subtleText, dialogPalette.text, surfacePalette.actionBg, surfacePalette.actionHover])

    const dialogPrimaryButtonSx = useMemo(() => ({
        minWidth: 68,
        borderRadius: 0,
        boxShadow: 'none',
        '&:hover': {
            boxShadow: 'none',
        },
    }), [])

    const dialogAccentButtonSx = useMemo(() => ({
        ...dialogPrimaryButtonSx,
        backgroundColor: dialogPalette.accent,
        color: '#ffffff',
        '&:hover': {
            backgroundColor: darkMode ? '#2b7be0' : '#1d4ed8',
            boxShadow: 'none',
        },
    }), [darkMode, dialogPalette.accent, dialogPrimaryButtonSx])

    const dialogWarningButtonSx = useMemo(() => ({
        ...dialogPrimaryButtonSx,
        backgroundColor: '#ffbc00',
        border: '1px solid #ffbc00',
        color: '#313a46',
        '&:hover': {
            backgroundColor: '#e0a700',
            border: '1px solid #e0a700',
            boxShadow: 'none',
        },
    }), [dialogPrimaryButtonSx])

    const dialogStyle = useMemo(() => ({
        '& .MuiDialog-container': {
            alignItems: 'flex-start',
            justifyContent: 'center',
            pt: scopeRect ? `${Math.max(scopeRect.top + 8, 16)}px` : { xs: 1.5, md: 2 },
            pb: { xs: 1.5, md: 2 },
        },
        '& .MuiDialog-paper': {
            width: scopeRect ? `${Math.min(scopeRect.width * 0.95, 1440)}px` : 'min(95vw, 1440px)',
            maxWidth: scopeRect ? `${Math.min(scopeRect.width * 0.95, 1440)}px` : '1440px',
            height: scopeRect ? `${Math.max(scopeRect.height - 24, 560)}px` : 'calc(100dvh - 40px)',
            maxHeight: scopeRect ? `${Math.max(scopeRect.height - 24, 560)}px` : 'calc(100dvh - 40px)',
            borderRadius: 0,
            overflow: 'hidden',
        },
    }), [scopeRect])

    const terminalFilesThemeVars = useMemo(() => ({
        '--terminal-files-surface-bg': darkMode ? '#111827' : '#ffffff',
        '--terminal-files-surface-soft': darkMode ? 'rgba(15, 23, 42, 0.85)' : '#f8fafc',
        '--terminal-files-border': darkMode ? 'rgba(71, 85, 105, 0.65)' : 'rgba(203, 213, 225, 0.9)',
        '--terminal-files-text': darkMode ? '#f8fafc' : '#334155',
        '--terminal-files-subtle-text': darkMode ? '#94a3b8' : '#64748b',
        '--terminal-files-editor-bg': darkMode ? '#0f172a' : '#ffffff',
    }) as CSSProperties, [darkMode])

    const editorDirty = editorPath !== null && editorContent !== editorInitialContent
    const filteredEntries = useMemo(() => {
        const keyword = directorySearch.trim().toLowerCase()
        const visibleEntries = showHiddenFiles ? entries : entries.filter((entry) => !entry.name.startsWith('.'))
        if (!keyword) {
            return visibleEntries
        }
        return visibleEntries.filter((entry) => entry.name.toLowerCase().includes(keyword) || entry.path.toLowerCase().includes(keyword))
    }, [directorySearch, entries, showHiddenFiles])
    const orderedFilteredEntries = useMemo(
        () => [...filteredEntries].sort((left, right) => {
            if (left.item_type !== right.item_type) {
                return left.item_type === 'directory' ? -1 : 1
            }
            return left.name.localeCompare(right.name, undefined, { numeric: true, sensitivity: 'base' })
        }),
        [filteredEntries],
    )
    const entryByPath = useMemo(() => new Map(entries.map((entry) => [entry.path, entry])), [entries])
    const directoryCount = useMemo(() => filteredEntries.filter((item) => item.item_type === 'directory').length, [filteredEntries])
    const fileCount = useMemo(() => filteredEntries.filter((item) => item.item_type === 'file').length, [filteredEntries])
    const fileSize = useMemo(() => filteredEntries.filter((item) => item.item_type === 'file').reduce((sum, item) => sum + item.size, 0), [filteredEntries])
    const protectedMainDialogOnClose = useMemo(() => (_event: object, reason: 'backdropClick' | 'escapeKeyDown') => {
        if (reason === 'backdropClick' || reason === 'escapeKeyDown') {
            return
        }
    }, [])
    const closeActionDialog = () => openActionDialog(null)
    const protectedActionDialogOnClose = useMemo(() => (_event: object, reason: 'backdropClick' | 'escapeKeyDown') => {
        if (reason === 'backdropClick' || reason === 'escapeKeyDown') {
            return
        }
    }, [])

    async function loadDirectory(path: string, nextHistory?: { replace?: boolean }) {
        setLoading(true)
        try {
            const response = await requestJson<VolumeDirectoryResponse>(`/api/files/tree?volume_id=${encodeURIComponent(volumeId)}&path=${encodeURIComponent(path)}`, { method: 'GET' })
            setCurrentPath(response.current_path)
            setEntries(response.items)
            setCurrentDirectoryMetadata(createDirectoryMetadata(response.volume_name || volumeLabel, response.current_path, response.metadata ?? null))
            setPathInputValue(buildVirtualPath(volumeId, response.current_path))
            if (selectedEntry) {
                setSelectedEntry((current) => current ? response.items.find((item) => item.path === current.path) ?? null : current)
            }
            if (nextHistory?.replace) {
                setHistory((current) => current.map((item, index) => (index === historyIndex ? response.current_path : item)))
                return
            }
            setHistory((current) => {
                const prefix = current.slice(0, historyIndex + 1)
                if (prefix[prefix.length - 1] === response.current_path) {
                    return prefix
                }
                return [...prefix, response.current_path]
            })
            setHistoryIndex((current) => {
                if (history[current] === response.current_path) {
                    return current
                }
                return current + 1
            })
        } catch (error) {
            setFeedback({ message: error instanceof Error ? error.message : t('filesPage.feedback.genericError') })
        } finally {
            setLoading(false)
        }
    }

    async function refreshCurrentDirectory() {
        setLoading(true)
        try {
            const response = await requestJson<VolumeDirectoryResponse>(`/api/files/tree?volume_id=${encodeURIComponent(volumeId)}&path=${encodeURIComponent(currentPath)}`, { method: 'GET' })
            setEntries(response.items)
            setCurrentPath(response.current_path)
            setCurrentDirectoryMetadata(createDirectoryMetadata(response.volume_name || volumeLabel, response.current_path, response.metadata ?? null))
            setPathInputValue(buildVirtualPath(volumeId, response.current_path))
            setSelectedEntry((current) => current ? response.items.find((item) => item.path === current.path) ?? null : current)
        } catch (error) {
            setFeedback({ message: error instanceof Error ? error.message : t('filesPage.feedback.genericError') })
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (!open) {
            return
        }
        setCurrentPath('/')
        setHistory(['/'])
        setHistoryIndex(0)
        setSelectedEntry(null)
        setCurrentDirectoryMetadata(createDirectoryMetadata(volumeLabel, '/', null))
        setEditorPath(null)
        setEditorContent('')
        setEditorInitialContent('')
        setDirectorySearch('')
        setPathInputValue(buildVirtualPath(volumeId, '/'))
        closeBrowserContextMenu()
        setBrowserClipboard(null)
        void loadDirectory('/')
    }, [open, volumeId, volumeLabel])

    useEffect(() => {
        return () => {
            closeBrowserContextMenu()
        }
    }, [])

    useEffect(() => {
        const panel = browserPanelRef.current
        if (!panel) {
            return
        }

        const resolveEntryFromTarget = (target: EventTarget | null) => {
            if (!(target instanceof Element)) {
                return null
            }
            const itemElement = target.closest<HTMLElement>('[data-entry-path]')
            if (!itemElement) {
                return null
            }
            const itemPath = itemElement.dataset.entryPath?.trim()
            return itemPath ? entryByPath.get(itemPath) ?? null : null
        }

        const handleNativeContextGesture = (event: MouseEvent | PointerEvent) => {
            if ('button' in event && event.button !== 2) {
                return
            }
            if (editorPath) {
                return
            }
            const item = resolveEntryFromTarget(event.target)
            const nextMouseX = event.clientX + 2
            const nextMouseY = event.clientY - 6
            event.preventDefault()
            event.stopPropagation()
            window.requestAnimationFrame(() => {
                setSelectedEntry(item)
                showBrowserContextMenu(item, nextMouseX, nextMouseY)
            })
        }

        panel.addEventListener('contextmenu', handleNativeContextGesture, true)
        panel.addEventListener('pointerdown', handleNativeContextGesture, true)

        return () => {
            panel.removeEventListener('contextmenu', handleNativeContextGesture, true)
            panel.removeEventListener('pointerdown', handleNativeContextGesture, true)
        }
    }, [editorPath, entryByPath])

    function clearEditorState() {
        setEditorPath(null)
        setEditorContent('')
        setEditorInitialContent('')
    }

    function closeBrowserContextMenu() {
        contextMenuCleanupRef.current?.()
        contextMenuCleanupRef.current = null
        if (contextMenuNodeRef.current) {
            contextMenuNodeRef.current.remove()
            contextMenuNodeRef.current = null
        }
    }

    function showBrowserContextMenu(item: VolumeFileItem | null, mouseX: number, mouseY: number) {
        if (typeof document === 'undefined' || typeof window === 'undefined') {
            return
        }

        closeBrowserContextMenu()

        try {
            const menuWidth = 188
            const actionItems = item
                ? [
                    { key: 'copy', label: t('myAppsDetailPage.tabs.volumes.fileManager.actions.copy'), disabled: actionSubmitting },
                    { key: 'cut', label: t('myAppsDetailPage.tabs.volumes.fileManager.actions.move'), disabled: actionSubmitting || item.path === '/' || item.path === currentPath },
                    { key: 'download', label: t('filesPage.actions.download'), disabled: item.item_type !== 'file' || actionSubmitting },
                    { key: 'rename', label: t('filesPage.actions.rename'), disabled: actionSubmitting },
                    { key: 'delete', label: t('filesPage.actions.delete'), disabled: actionSubmitting || (item.path === '/' && item.item_type === 'directory') },
                    { key: 'properties', label: t('myAppsDetailPage.tabs.volumes.fileManager.actions.properties'), disabled: actionSubmitting },
                    { key: 'edit', label: t('filesPage.actions.edit'), disabled: !item.text_editable || item.item_type !== 'file' || actionSubmitting },
                ]
                : [
                    { key: 'paste', label: t('filesPage.actions.paste'), disabled: !browserClipboard || actionSubmitting },
                    { key: 'create-folder', label: t('filesPage.actions.createFolder'), disabled: actionSubmitting },
                    { key: 'create-file', label: t('filesPage.actions.createFile'), disabled: actionSubmitting },
                    { key: 'properties', label: t('myAppsDetailPage.tabs.volumes.fileManager.actions.properties'), disabled: !currentDirectoryMetadata || actionSubmitting },
                ]
            const menuHeight = actionItems.length * 36 + 12
            const left = Math.max(12, Math.min(mouseX, window.innerWidth - menuWidth - 12))
            const top = Math.max(12, Math.min(mouseY, window.innerHeight - menuHeight - 12))

            const node = document.createElement('div')
            node.style.position = 'fixed'
            node.style.left = `${left}px`
            node.style.top = `${top}px`
            node.style.minWidth = `${menuWidth}px`
            node.style.padding = '6px 0'
            node.style.border = `1px solid ${darkMode ? 'rgba(71, 85, 105, 0.72)' : '#cbd5e1'}`
            node.style.borderRadius = '2px'
            node.style.background = darkMode ? '#111827' : '#ffffff'
            node.style.color = darkMode ? '#f8fafc' : '#334155'
            node.style.boxShadow = darkMode ? '0 18px 44px rgba(2, 6, 23, 0.58)' : '0 18px 40px rgba(15, 23, 42, 0.18)'
            node.style.overflow = 'hidden'
            node.style.zIndex = '1708'
            node.setAttribute('data-volume-context-menu', 'true')

            actionItems.forEach((action) => {
                const button = document.createElement('button')
                button.type = 'button'
                button.textContent = action.label
                button.disabled = action.disabled
                button.style.display = 'flex'
                button.style.alignItems = 'center'
                button.style.width = '100%'
                button.style.minHeight = '36px'
                button.style.padding = '0 14px'
                button.style.border = 'none'
                button.style.background = 'transparent'
                button.style.color = action.disabled ? (darkMode ? '#64748b' : '#94a3b8') : (darkMode ? '#f8fafc' : '#334155')
                button.style.cursor = action.disabled ? 'default' : 'pointer'
                button.style.fontSize = '13.5px'
                button.style.textAlign = 'left'
                button.addEventListener('click', (event) => {
                    event.preventDefault()
                    event.stopPropagation()
                    if (action.disabled) {
                        return
                    }
                    closeBrowserContextMenu()
                    void handleBrowserContextAction(action.key as 'copy' | 'cut' | 'paste' | 'download' | 'rename' | 'delete' | 'create-folder' | 'create-file' | 'properties' | 'edit', item)
                })
                button.addEventListener('mouseenter', () => {
                    if (!action.disabled) {
                        button.style.background = darkMode ? 'rgba(59, 130, 246, 0.18)' : 'rgba(37, 99, 235, 0.08)'
                    }
                })
                button.addEventListener('mouseleave', () => {
                    button.style.background = 'transparent'
                })
                node.appendChild(button)
            })

            const handlePointerDown = (event: MouseEvent) => {
                if (event.button === 2) {
                    return
                }
                const target = event.target
                if (target instanceof Node && node.contains(target)) {
                    return
                }
                closeBrowserContextMenu()
            }
            const handleKeyDown = (event: KeyboardEvent) => {
                if (event.key === 'Escape') {
                    closeBrowserContextMenu()
                }
            }

            document.body.appendChild(node)
            document.addEventListener('mousedown', handlePointerDown, true)
            window.addEventListener('keydown', handleKeyDown, true)
            contextMenuNodeRef.current = node
            contextMenuCleanupRef.current = () => {
                document.removeEventListener('mousedown', handlePointerDown, true)
                window.removeEventListener('keydown', handleKeyDown, true)
            }
        } catch (error) {
            setFeedback({ message: error instanceof Error ? error.message : String(error) })
        }
    }

    function handleBrowserBackgroundClick(event: ReactMouseEvent<HTMLElement>, itemSelector: string) {
        const target = event.target
        if (!(target instanceof HTMLElement)) {
            return
        }
        if (!target.closest(itemSelector)) {
            setSelectedEntry(null)
        }
    }

    async function handleDownload(item: VolumeFileItem) {
        setActionSubmitting(true)
        try {
            const response = await fetch(`/api/files/download?volume_id=${encodeURIComponent(volumeId)}&path=${encodeURIComponent(item.path)}`, {
                method: 'GET',
                credentials: 'include',
            })
            if (!response.ok) {
                const payload = (await response.json().catch(() => null)) as { details?: string; message?: string } | null
                throw new Error(payload?.details ?? payload?.message ?? `HTTP ${response.status}`)
            }
            const blob = await response.blob()
            const objectUrl = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = objectUrl
            link.download = item.name
            document.body.appendChild(link)
            link.click()
            document.body.removeChild(link)
            URL.revokeObjectURL(objectUrl)
        } catch (error) {
            setFeedback({ message: error instanceof Error ? error.message : t('filesPage.feedback.genericError') })
        } finally {
            setActionSubmitting(false)
        }
    }

    async function handleBrowserContextAction(action: 'copy' | 'cut' | 'paste' | 'download' | 'rename' | 'delete' | 'create-folder' | 'create-file' | 'properties' | 'edit', contextItemOverride?: VolumeFileItem | null) {
        const contextItem = contextItemOverride ?? null
        closeBrowserContextMenu()

        if (action === 'copy' || action === 'cut') {
            if (!contextItem) {
                return
            }
            setBrowserClipboard({ path: contextItem.path, name: contextItem.name, itemType: contextItem.item_type, mode: action })
            return
        }

        if (action === 'paste') {
            if (!browserClipboard) {
                return
            }
            const destinationPath = contextItem?.item_type === 'directory' ? contextItem.path : currentPath
            setActionSubmitting(true)
            try {
                await requestJson(`/api/files/${browserClipboard.mode === 'cut' ? 'move' : 'copy'}`, {
                    method: 'POST',
                    body: JSON.stringify({ volume_id: volumeId, source_path: browserClipboard.path, destination_path: destinationPath }),
                })
                if (browserClipboard.mode === 'cut') {
                    setBrowserClipboard(null)
                }
                await refreshCurrentDirectory()
            } catch (error) {
                setFeedback({ message: error instanceof Error ? normalizeActionErrorMessage(error.message, browserClipboard.name) : t('filesPage.feedback.genericError') })
            } finally {
                setActionSubmitting(false)
            }
            return
        }

        if (action === 'download') {
            if (contextItem) {
                await handleDownload(contextItem)
            }
            return
        }

        if (action === 'rename' && contextItem) {
            openActionDialog({ type: 'rename', item: contextItem })
            return
        }

        if (action === 'delete') {
            const target = contextItem ?? currentDirectoryMetadata
            if (target) {
                openActionDialog({ type: 'delete', item: target })
            }
            return
        }

        if (action === 'properties') {
            const target = contextItem ?? currentDirectoryMetadata
            if (target) {
                openActionDialog({ type: 'properties', item: target })
            }
            return
        }

        if (action === 'edit' && contextItem?.item_type === 'file' && contextItem.text_editable) {
            await openEntry(contextItem)
            return
        }

        if (action === 'create-folder' || action === 'create-file') {
            openActionDialog({ type: action })
        }
    }

    async function openEntry(entry: VolumeFileItem) {
        setSelectedEntry(entry)
        if (entry.item_type === 'directory') {
            clearEditorState()
            await loadDirectory(entry.path)
            return
        }

        if (!entry.text_editable) {
            return
        }

        setEditorLoading(true)
        try {
            const response = await requestJson<VolumeTextFileResponse>(`/api/files/content?volume_id=${encodeURIComponent(volumeId)}&path=${encodeURIComponent(entry.path)}`, { method: 'GET' })
            setEditorPath(response.path)
            setEditorContent(response.content)
            setEditorInitialContent(response.content)
        } catch (error) {
            setFeedback({ message: error instanceof Error ? error.message : t('filesPage.feedback.genericError') })
        } finally {
            setEditorLoading(false)
        }
    }

    async function handleSaveEditor() {
        if (!editorPath) {
            return
        }
        setActionSubmitting(true)
        try {
            await requestJson('/api/files/content', {
                method: 'PUT',
                body: JSON.stringify({ volume_id: volumeId, path: editorPath, content: editorContent }),
            })
            setEditorInitialContent(editorContent)
            await refreshCurrentDirectory()
        } catch (error) {
            setFeedback({ message: error instanceof Error ? error.message : t('filesPage.feedback.genericError') })
        } finally {
            setActionSubmitting(false)
        }
    }

    function openActionDialog(nextState: DialogState) {
        setDialogState(nextState)
        if (!nextState) {
            setDialogValue('')
            setPropertiesForm(null)
            return
        }
        if (nextState.type === 'rename') {
            setDialogValue(nextState.item.name)
            return
        }
        if (nextState.type === 'properties') {
            setPropertiesForm(createPropertiesForm(nextState.item))
            return
        }
        setDialogValue('')
    }

    async function submitDialogAction() {
        if (!dialogState) {
            return
        }

        const trimmedValue = dialogValue.trim()
        const affectsCurrentDirectory = 'item' in dialogState && dialogState.item.path === currentPath
        let refreshPath = currentPath
        let replaceHistory = false
        const duplicateTarget = entries.find((item) => {
            if (dialogState.type === 'rename' && item.path === dialogState.item.path) {
                return false
            }
            return item.name.localeCompare(trimmedValue, undefined, { sensitivity: 'accent' }) === 0
        })

        if ((dialogState.type === 'create-folder' || dialogState.type === 'create-file' || dialogState.type === 'rename') && trimmedValue && duplicateTarget) {
            setFeedback({ message: t('filesPage.feedback.nameExists', { name: trimmedValue }) })
            return
        }

        setActionSubmitting(true)
        try {
            if (dialogState.type === 'create-folder') {
                await requestJson('/api/files/folders', {
                    method: 'POST',
                    body: JSON.stringify({ volume_id: volumeId, parent_path: currentPath, name: trimmedValue }),
                })
            }

            if (dialogState.type === 'create-file') {
                await requestJson('/api/files/items', {
                    method: 'POST',
                    body: JSON.stringify({ volume_id: volumeId, parent_path: currentPath, name: trimmedValue }),
                })
            }

            if (dialogState.type === 'rename') {
                const renamedPath = buildSiblingPath(dialogState.item.path, trimmedValue)
                await requestJson('/api/files/rename', {
                    method: 'POST',
                    body: JSON.stringify({ volume_id: volumeId, source_path: dialogState.item.path, target_name: trimmedValue }),
                })
                if (affectsCurrentDirectory) {
                    setCurrentPath(renamedPath)
                    setPathInputValue(buildVirtualPath(volumeId, renamedPath))
                    setHistory((current) => current.map((item, index) => (index === historyIndex ? renamedPath : item)))
                    setCurrentDirectoryMetadata((current) => current ? { ...current, name: trimmedValue, path: renamedPath } : current)
                    refreshPath = renamedPath
                    replaceHistory = true
                }
                setSelectedEntry((current) => current && current.path === dialogState.item.path ? { ...current, name: trimmedValue, path: renamedPath } : current)
                if (editorPath === dialogState.item.path) {
                    setEditorPath(renamedPath)
                }
            }

            if (dialogState.type === 'delete') {
                await requestJson('/api/files/item', {
                    method: 'DELETE',
                    body: JSON.stringify({ volume_id: volumeId, path: dialogState.item.path }),
                })
                if (selectedEntry?.path === dialogState.item.path) {
                    setSelectedEntry(null)
                }
                if (editorPath === dialogState.item.path) {
                    clearEditorState()
                }
                if (affectsCurrentDirectory) {
                    const nextPath = parentPath(dialogState.item.path)
                    setCurrentPath(nextPath)
                    setPathInputValue(buildVirtualPath(volumeId, nextPath))
                    setHistory((current) => current.map((item, index) => (index === historyIndex ? nextPath : item)))
                    setCurrentDirectoryMetadata(null)
                    refreshPath = nextPath
                    replaceHistory = true
                }
            }

            if (dialogState.type === 'properties' && propertiesForm) {
                const response = await requestJson<{ metadata: VolumeMetadataResponse }>('/api/files/attributes', {
                    method: 'PUT',
                    body: JSON.stringify({
                        volume_id: volumeId,
                        source_path: dialogState.item.path,
                        target_name: propertiesForm.targetName.trim(),
                        owner: propertiesForm.owner.trim(),
                        group: propertiesForm.group.trim(),
                        owner_permissions: propertiesForm.ownerPermissions,
                        group_permissions: propertiesForm.groupPermissions,
                        other_permissions: propertiesForm.otherPermissions,
                    }),
                })
                const nextPath = response.metadata.path
                if (affectsCurrentDirectory) {
                    setCurrentPath(nextPath)
                    setPathInputValue(buildVirtualPath(volumeId, nextPath))
                    setHistory((current) => current.map((item, index) => (index === historyIndex ? nextPath : item)))
                    setCurrentDirectoryMetadata(response.metadata)
                    refreshPath = nextPath
                    replaceHistory = true
                }
                setSelectedEntry({
                    ...dialogState.item,
                    name: response.metadata.name,
                    path: nextPath,
                    mode: response.metadata.mode,
                    owner: response.metadata.owner,
                    group: response.metadata.group,
                    size: response.metadata.size,
                    modified_at: response.metadata.modified_at,
                    created_at: response.metadata.created_at,
                    accessed_at: response.metadata.accessed_at,
                    text_editable: response.metadata.text_editable,
                })
                if (editorPath === dialogState.item.path) {
                    setEditorPath(nextPath)
                }
            }

            openActionDialog(null)
            if (replaceHistory) {
                await loadDirectory(refreshPath, { replace: true })
            } else {
                await refreshCurrentDirectory()
            }
        } catch (error) {
            const name = dialogState.type === 'create-folder' || dialogState.type === 'create-file'
                ? trimmedValue
                : dialogState.type === 'properties'
                    ? propertiesForm?.targetName
                    : 'item' in dialogState
                        ? dialogState.item.name
                        : undefined
            setFeedback({ message: error instanceof Error ? normalizeActionErrorMessage(error.message, name) : t('filesPage.feedback.genericError') })
        } finally {
            setActionSubmitting(false)
        }
    }

    async function handleUploadChange(event: ChangeEvent<HTMLInputElement>) {
        const file = event.target.files?.[0]
        if (!file) {
            return
        }

        const duplicateEntry = entries.find((item) => item.name === file.name)
        const contentBase64 = await fileToBase64(file)
        if (duplicateEntry) {
            if (duplicateEntry.item_type !== 'file') {
                event.target.value = ''
                setFeedback({ message: t('filesPage.feedback.nameExists', { name: file.name }) })
                return
            }

            openActionDialog({ type: 'overwrite-upload', fileName: file.name, contentBase64 })
            return
        }

        event.target.value = ''

        setActionSubmitting(true)
        try {
            await requestJson('/api/files/upload', {
                method: 'POST',
                body: JSON.stringify({ volume_id: volumeId, parent_path: currentPath, file_name: file.name, content_base64: contentBase64 }),
            })
            await refreshCurrentDirectory()
        } catch (error) {
            setFeedback({ message: error instanceof Error ? normalizeActionErrorMessage(error.message, file.name) : t('filesPage.feedback.genericError') })
        } finally {
            setActionSubmitting(false)
        }
    }

    function navigateToHistory(nextIndex: number) {
        const target = history[nextIndex]
        if (!target) {
            return
        }
        setHistoryIndex(nextIndex)
        void loadDirectory(target, { replace: true })
    }

    const selectedBrowserEntry = selectedEntry
    const activeBrowserEntry = selectedBrowserEntry ?? currentDirectoryMetadata
    const inspectorEntry = activeBrowserEntry
    const canDeleteSelectedItem = Boolean(activeBrowserEntry && activeBrowserEntry.path !== '/' && editorPath === null && !actionSubmitting)
    const canShowInspectorProperties = Boolean(activeBrowserEntry) && !actionSubmitting
    const canEditSelectedItem = Boolean(selectedBrowserEntry?.item_type === 'file' && selectedBrowserEntry?.text_editable) && !actionSubmitting
    const actionDialogTitle = dialogState?.type === 'create-folder'
        ? t('filesPage.dialogs.createFolderTitle')
        : dialogState?.type === 'create-file'
            ? t('filesPage.dialogs.createFileTitle')
            : dialogState?.type === 'rename'
                ? t('filesPage.dialogs.renameTitle')
                : dialogState?.type === 'overwrite-upload'
                    ? t('filesPage.dialogs.overwriteTitle')
                    : dialogState?.type === 'delete'
                        ? t('filesPage.dialogs.deleteTitle')
                        : t('myAppsDetailPage.tabs.volumes.fileManager.dialogs.propertiesTitle')
    const actionDialogConfirmSx = dialogState?.type === 'delete' ? dialogWarningButtonSx : dialogAccentButtonSx
    const actionDialogWidth = dialogState?.type === 'properties' ? '780px' : '560px'

    async function handleOverwriteUpload() {
        if (!dialogState || dialogState.type !== 'overwrite-upload') {
            return
        }

        setActionSubmitting(true)
        try {
            await requestJson('/api/files/upload', {
                method: 'POST',
                body: JSON.stringify({
                    volume_id: volumeId,
                    parent_path: currentPath,
                    file_name: dialogState.fileName,
                    content_base64: dialogState.contentBase64,
                }),
            })
            closeActionDialog()
            await refreshCurrentDirectory()
        } catch (error) {
            setFeedback({
                message: error instanceof Error ? normalizeActionErrorMessage(error.message, dialogState.fileName) : t('filesPage.feedback.genericError'),
            })
        } finally {
            if (uploadInputRef.current) {
                uploadInputRef.current.value = ''
            }
            setActionSubmitting(false)
        }
    }

    return (
        <>
            <SurfaceDialog
                open={open}
                onClose={protectedMainDialogOnClose}
                maxWidth="lg"
                darkMode={darkMode}
                sx={[dialogStyle, { zIndex: 1605 }]}
            >
                <div className={darkMode ? 'app-shell-root--dark' : undefined} style={{ height: '100%', padding: '14px 14px 16px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '0 2px 12px', flex: '0 0 auto' }}>
                        <div>
                            <Typography sx={{ fontSize: 18, fontWeight: 700, color: darkMode ? '#e2e8f0' : '#334155', lineHeight: 1.35 }}>{t('myAppsDetailPage.tabs.volumes.fileManager.title', { name: volumeLabel })}</Typography>
                        </div>
                        <Button onClick={onClose} variant="text" sx={{ minWidth: 'auto', color: darkMode ? '#94a3b8' : '#64748b' }}>{t('filesPage.actions.close')}</Button>
                    </div>

                    <div className="terminal-files-shell" style={{ ...terminalFilesThemeVars, color: darkMode ? '#e5edf5' : '#334155', gap: 12, flex: '1 1 auto', minHeight: 0 }}>
                        <div className="terminal-files-toolbar-row">
                            <div className="terminal-files-toolbar-group">
                                <button className="terminal-files-toolbar-button" disabled={historyIndex <= 0 || loading} onClick={() => navigateToHistory(historyIndex - 1)} title={t('filesPage.actions.back')} type="button">
                                    <TerminalNavGlyph kind="back" />
                                </button>
                                <button className="terminal-files-toolbar-button" disabled={historyIndex >= history.length - 1 || loading} onClick={() => navigateToHistory(historyIndex + 1)} title={t('filesPage.actions.forward')} type="button">
                                    <TerminalNavGlyph kind="forward" />
                                </button>
                                <button className="terminal-files-toolbar-button" disabled={currentPath === '/' || loading} onClick={() => void loadDirectory(parentPath(currentPath))} title={t('filesPage.actions.up')} type="button">
                                    <TerminalNavGlyph kind="up" />
                                </button>
                                <button className="terminal-files-toolbar-button terminal-files-toolbar-button-primary" disabled={loading} onClick={() => void refreshCurrentDirectory()} title={t('myAppsDetailPage.tabs.volumes.fileManager.actions.refresh')} type="button">
                                    <TerminalNavGlyph kind="refresh" />
                                </button>
                            </div>

                            <div className="terminal-files-toolbar-paths">
                                <TextField
                                    className="terminal-files-path-input"
                                    size="small"
                                    value={pathInputValue}
                                    onChange={(event) => setPathInputValue(event.target.value)}
                                    onBlur={() => setPathInputValue(buildVirtualPath(volumeId, currentPath))}
                                    onKeyDown={(event) => {
                                        if (event.key !== 'Enter') {
                                            return
                                        }
                                        event.preventDefault()
                                        const parsedPath = parseVirtualPath(volumeId, pathInputValue)
                                        if (!parsedPath) {
                                            setFeedback({ message: t('myAppsDetailPage.tabs.volumes.fileManager.feedback.invalidPath') })
                                            setPathInputValue(buildVirtualPath(volumeId, currentPath))
                                            return
                                        }
                                        void loadDirectory(parsedPath)
                                    }}
                                />
                                <TextField
                                    className="terminal-files-search-input"
                                    size="small"
                                    value={directorySearch}
                                    onChange={(event) => setDirectorySearch(event.target.value)}
                                    placeholder={t('filesPage.filters.searchPlaceholder')}
                                    slotProps={{ input: { endAdornment: <TerminalNavGlyph kind="search" /> } }}
                                />
                            </div>

                            <div className="terminal-files-toolbar-group terminal-files-toolbar-group-actions">
                                <button className="terminal-files-toolbar-button terminal-files-toolbar-button-primary" disabled={actionSubmitting} onClick={() => openActionDialog({ type: 'create-folder' })} title={t('filesPage.actions.createFolder')} type="button">
                                    <FolderCreateIcon />
                                </button>
                                <button className="terminal-files-toolbar-button terminal-files-toolbar-button-primary" disabled={actionSubmitting} onClick={() => openActionDialog({ type: 'create-file' })} title={t('filesPage.actions.createFile')} type="button">
                                    <FileCreateIcon />
                                </button>
                                <button className="terminal-files-toolbar-button terminal-files-toolbar-button-primary" disabled={actionSubmitting} onClick={() => uploadInputRef.current?.click()} title={t('filesPage.actions.upload')} type="button">
                                    <UploadFileIcon />
                                </button>
                                <input ref={uploadInputRef} hidden type="file" onChange={(event) => void handleUploadChange(event)} />
                            </div>
                        </div>

                        <div className="terminal-files-layout">
                            <div
                                className="terminal-files-browser-panel"
                                ref={browserPanelRef}
                                onClick={(event) => handleBrowserBackgroundClick(event, '.terminal-files-list-row, .terminal-files-grid-card')}
                            >
                                {loading ? <div className="terminal-files-progress" /> : null}
                                {editorLoading ? (
                                    <div className="terminal-files-empty"><Typography sx={{ fontSize: 13.5, color: darkMode ? '#94a3b8' : '#64748b' }}>{t('filesPage.editor.loading')}</Typography></div>
                                ) : editorPath ? (
                                    <div className="terminal-files-browser-editor">
                                        <div className="terminal-files-browser-editor-header">
                                            <div className="terminal-files-browser-editor-header-main">
                                                <div className="terminal-files-browser-editor-title terminal-files-truncate">{buildVirtualPath(volumeId, editorPath)}</div>
                                                <div className="terminal-files-editor-actions terminal-files-editor-actions-header">
                                                    <button className="terminal-files-editor-action terminal-files-editor-action-close" onClick={clearEditorState} title={t('filesPage.actions.close')} type="button">
                                                        <ToolbarGlyph kind="close" />
                                                    </button>
                                                    <button className="terminal-files-editor-action terminal-files-editor-action-save" disabled={!editorDirty || actionSubmitting} onClick={() => void handleSaveEditor()} title={t('filesPage.actions.save')} type="button">
                                                        <ToolbarGlyph kind="save" />
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="terminal-files-browser-editor-body">
                                            <TextField
                                                className="terminal-files-editor-textarea"
                                                fullWidth
                                                multiline
                                                value={editorContent}
                                                onChange={(event) => setEditorContent(event.target.value)}
                                                slotProps={{ htmlInput: { wrap: 'off', spellCheck: false } }}
                                                sx={{ height: '100%', '& .MuiInputBase-root': { height: '100%' } }}
                                            />
                                        </div>
                                    </div>
                                ) : filteredEntries.length > 0 ? (
                                    <div className="terminal-files-list-view">
                                        {displayMode === 'list' ? (
                                            <>
                                                <div className="terminal-files-list-header terminal-files-list-row-frame">
                                                    <div>{t('filesPage.table.name')}</div>
                                                    <div>{t('filesPage.metadata.mode')}</div>
                                                    <div>{t('filesPage.metadata.owner')}</div>
                                                    <div>{t('filesPage.metadata.group')}</div>
                                                    <div>{t('filesPage.table.size')}</div>
                                                    <div>{t('filesPage.metadata.modified')}</div>
                                                    <div>{t('filesPage.metadata.created')}</div>
                                                </div>
                                                <div className="terminal-files-list-body" onClick={(event) => handleBrowserBackgroundClick(event, '.terminal-files-list-row')}>
                                                    {orderedFilteredEntries.map((entry) => {
                                                        const selected = selectedEntry?.path === entry.path
                                                        return (
                                                            <button
                                                                key={entry.path}
                                                                className={`terminal-files-list-row terminal-files-list-row-frame ${selected ? 'terminal-files-list-row-selected' : ''}`}
                                                                data-entry-path={entry.path}
                                                                onClick={() => setSelectedEntry(entry)}
                                                                onDoubleClick={() => void openEntry(entry)}
                                                                type="button"
                                                            >
                                                                <div className="terminal-files-list-name">
                                                                    <FileItemGlyph kind={getVisualKind(entry)} variant="list" active={selected && entry.item_type === 'directory'} />
                                                                    <span className="terminal-files-truncate">{entry.name}</span>
                                                                </div>
                                                                <div>{entry.mode || '—'}</div>
                                                                <div>{formatIdentity(entry.owner)}</div>
                                                                <div>{formatIdentity(entry.group)}</div>
                                                                <div>{entry.item_type === 'file' ? formatFileSize(entry.size) : '—'}</div>
                                                                <div>{formatTimestamp(entry.modified_at, locale)}</div>
                                                                <div>{formatTimestamp(entry.created_at, locale)}</div>
                                                            </button>
                                                        )
                                                    })}
                                                </div>
                                            </>
                                        ) : (
                                            <div className="terminal-files-grid-body" onClick={(event) => handleBrowserBackgroundClick(event, '.terminal-files-grid-card')}>
                                                {orderedFilteredEntries.map((entry) => {
                                                    const selected = selectedEntry?.path === entry.path
                                                    return (
                                                        <button key={entry.path} className="terminal-files-grid-card" data-entry-path={entry.path} onClick={() => setSelectedEntry(entry)} onDoubleClick={() => void openEntry(entry)} type="button">
                                                            <div className={`terminal-files-grid-card-hitbox ${selected ? 'terminal-files-grid-card-hitbox-selected' : ''}`}>
                                                                <FileItemGlyph kind={getVisualKind(entry)} variant="card" active={selected && entry.item_type === 'directory'} />
                                                                <div className="terminal-files-grid-card-body">
                                                                    <div className="terminal-files-grid-card-title">{entry.name}</div>
                                                                </div>
                                                            </div>
                                                        </button>
                                                    )
                                                })}
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    <div className="terminal-files-empty"><Typography sx={{ fontSize: 13.5, color: darkMode ? '#94a3b8' : '#64748b' }}>{loading ? t('filesPage.states.loadingDirectory') : t('myAppsDetailPage.tabs.volumes.fileManager.empty')}</Typography></div>
                                )}
                            </div>

                            <div className="terminal-files-inspector-panel">
                                <div className="terminal-files-inspector-header terminal-files-inspector-header-classic">
                                    <div className="terminal-files-inspector-header-main">
                                        <div className="terminal-files-inspector-header-title terminal-files-truncate">{inspectorEntry?.name || t('filesPage.inspector.emptyTitle')}</div>
                                        <div className="terminal-files-inspector-header-actions">
                                            <IconButton className="terminal-files-toolbar-button terminal-files-toolbar-button-small terminal-files-toolbar-button-danger" disabled={!canDeleteSelectedItem} onClick={() => inspectorEntry ? openActionDialog({ type: 'delete', item: inspectorEntry }) : undefined} size="small" title={t('filesPage.actions.delete')}>
                                                <ToolbarGlyph kind="trash" />
                                            </IconButton>
                                            <IconButton className="terminal-files-toolbar-button terminal-files-toolbar-button-small" disabled={!canShowInspectorProperties} onClick={() => inspectorEntry ? openActionDialog({ type: 'properties', item: inspectorEntry }) : undefined} size="small" title={t('myAppsDetailPage.tabs.volumes.fileManager.actions.properties')}>
                                                <ToolbarGlyph kind="properties" />
                                            </IconButton>
                                            <IconButton className="terminal-files-toolbar-button terminal-files-toolbar-button-small" disabled={!canEditSelectedItem} onClick={() => selectedBrowserEntry ? void openEntry(selectedBrowserEntry) : undefined} size="small" title={t('filesPage.actions.edit')}>
                                                <ToolbarGlyph kind="edit" />
                                            </IconButton>
                                        </div>
                                    </div>
                                </div>
                                <div className="terminal-files-inspector-body terminal-files-inspector-body-classic">
                                    {inspectorEntry ? (
                                        <div className="terminal-files-inspector-rows terminal-files-inspector-rows-classic">
                                            <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.metadata.mode')}</Typography><Typography className="terminal-files-inspector-value">{inspectorEntry.mode || '—'}</Typography></div>
                                            <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.metadata.owner')}</Typography><Typography className="terminal-files-inspector-value">{formatIdentity(inspectorEntry.owner)}</Typography></div>
                                            <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.metadata.group')}</Typography><Typography className="terminal-files-inspector-value">{formatIdentity(inspectorEntry.group)}</Typography></div>
                                            <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.table.size')}</Typography><Typography className="terminal-files-inspector-value">{inspectorEntry.item_type === 'file' ? formatFileSize(inspectorEntry.size) : '—'}</Typography></div>
                                            <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.metadata.modified')}</Typography><Typography className="terminal-files-inspector-value">{formatTimestamp(inspectorEntry.modified_at, locale)}</Typography></div>
                                            <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.metadata.accessed')}</Typography><Typography className="terminal-files-inspector-value">{formatTimestamp(inspectorEntry.accessed_at, locale)}</Typography></div>
                                            <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{t('filesPage.metadata.created')}</Typography><Typography className="terminal-files-inspector-value">{formatTimestamp(inspectorEntry.created_at, locale)}</Typography></div>
                                        </div>
                                    ) : (
                                        <div className="terminal-files-empty terminal-files-empty-inspector"><Typography sx={{ fontSize: 13.5, color: darkMode ? '#94a3b8' : '#64748b' }}>{t('filesPage.inspector.emptyBody')}</Typography></div>
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="terminal-files-footer">
                            <div className="terminal-files-footer-stats">{`${directoryCount} ${t('filesPage.footer.directories')}, ${fileCount} ${t('filesPage.footer.files')} (${formatFileSize(fileSize)})`}</div>
                            <div className="terminal-files-footer-actions">
                                <button className={`terminal-files-footer-button ${showHiddenFiles ? 'terminal-files-footer-button-active' : ''}`} onClick={() => setShowHiddenFiles((current) => !current)} title={t('filesPage.footer.hiddenFiles')} type="button">
                                    {showHiddenFiles ? <HiddenFilesOffIcon /> : <HiddenFilesIcon />}
                                </button>
                                <button className={`terminal-files-footer-button ${displayMode === 'grid' ? 'terminal-files-footer-button-active' : ''}`} onClick={() => setDisplayMode((current) => current === 'list' ? 'grid' : 'list')} title={displayMode === 'list' ? t('filesPage.footer.gridView') : t('filesPage.footer.listView')} type="button">
                                    {displayMode === 'list' ? <GridViewIcon /> : <ListViewIcon />}
                                </button>
                            </div>
                        </div>

                    </div>
                </div>

                <SurfaceDialog
                    open={dialogState !== null}
                    onClose={protectedActionDialogOnClose}
                    maxWidth={dialogState?.type === 'properties' ? 'md' : 'sm'}
                    scope="content"
                    scopeRect={scopeRect}
                    contentStrategy="viewport-fixed"
                    darkMode={darkMode}
                    sx={[contentScopedDialogPlacementSx, { zIndex: 1610, '& .MuiBackdrop-root': { backgroundColor: dialogPalette.overlay } }]}
                    paperSx={{
                        width: { xs: `min(100%, ${actionDialogWidth})`, md: `min(${actionDialogWidth}, calc(100% - 20px))` },
                        maxWidth: actionDialogWidth,
                        borderRadius: 0,
                        backgroundColor: dialogPalette.panel,
                        color: dialogPalette.text,
                        border: `1px solid ${dialogPalette.border}`,
                        boxShadow: darkMode ? '0 24px 64px rgba(2, 6, 23, 0.56)' : '0 16px 40px rgba(15, 23, 42, 0.16)',
                    }}
                >
                    <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                        <div style={{ padding: '12px 18px', borderBottom: `1px solid ${dialogPalette.divider}`, backgroundColor: dialogPalette.panelSoft }}>
                            <Typography sx={{ fontSize: 16, fontWeight: 700, color: dialogPalette.text }}>{actionDialogTitle}</Typography>
                        </div>
                        <div style={{ padding: '16px 18px', borderBottom: `1px solid ${dialogPalette.divider}`, display: 'grid', gap: 16, minHeight: 0 }}>
                            {dialogState?.type === 'delete' ? (
                                <Typography sx={{ m: 0, fontSize: 14, lineHeight: 1.7, color: dialogPalette.subtleText }}>{t('filesPage.dialogs.deleteBody', { name: dialogState.item.name })}</Typography>
                            ) : null}

                            {dialogState?.type === 'overwrite-upload' ? (
                                <Typography sx={{ m: 0, fontSize: 14, lineHeight: 1.7, color: dialogPalette.subtleText }}>{t('filesPage.dialogs.overwriteBody', { name: dialogState.fileName })}</Typography>
                            ) : null}

                            {dialogState?.type === 'create-folder' || dialogState?.type === 'create-file' || dialogState?.type === 'rename' ? (
                                <TextField
                                    autoFocus
                                    fullWidth
                                    size="small"
                                    label={t('filesPage.dialogs.nameField')}
                                    value={dialogValue}
                                    onChange={(event) => setDialogValue(event.target.value)}
                                />
                            ) : null}

                            {dialogState?.type === 'properties' && propertiesForm ? (
                                <Stack spacing={2}>
                                    <TextField fullWidth size="small" label={t('filesPage.dialogs.nameField')} value={propertiesForm.targetName} onChange={(event) => setPropertiesForm((current) => current ? { ...current, targetName: event.target.value } : current)} />
                                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                                        <TextField fullWidth size="small" label={t('filesPage.metadata.owner')} value={propertiesForm.owner} onChange={(event) => setPropertiesForm((current) => current ? { ...current, owner: event.target.value } : current)} />
                                        <TextField fullWidth size="small" label={t('filesPage.metadata.group')} value={propertiesForm.group} onChange={(event) => setPropertiesForm((current) => current ? { ...current, group: event.target.value } : current)} />
                                    </Stack>
                                    <div style={{ display: 'grid', gap: 10, border: `1px solid ${dialogPalette.divider}`, background: dialogPalette.panelSoft, padding: 14 }}>
                                        <PermissionMatrix label={t('myAppsDetailPage.tabs.volumes.fileManager.permissions.owner')} value={propertiesForm.ownerPermissions} onChange={(next) => setPropertiesForm((current) => current ? { ...current, ownerPermissions: next } : current)} />
                                        <PermissionMatrix label={t('myAppsDetailPage.tabs.volumes.fileManager.permissions.group')} value={propertiesForm.groupPermissions} onChange={(next) => setPropertiesForm((current) => current ? { ...current, groupPermissions: next } : current)} />
                                        <PermissionMatrix label={t('myAppsDetailPage.tabs.volumes.fileManager.permissions.other')} value={propertiesForm.otherPermissions} onChange={(next) => setPropertiesForm((current) => current ? { ...current, otherPermissions: next } : current)} />
                                    </div>
                                </Stack>
                            ) : null}
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, padding: '10px 18px' }}>
                            <Button onClick={closeActionDialog} sx={dialogCancelButtonSx}>{t('filesPage.dialogs.cancel')}</Button>
                            <Button
                                variant="contained"
                                sx={actionDialogConfirmSx}
                                disabled={actionSubmitting || (dialogState?.type !== 'delete' && dialogState?.type !== 'properties' && dialogState?.type !== 'overwrite-upload' && !dialogValue.trim())}
                                onClick={() => {
                                    if (dialogState?.type === 'overwrite-upload') {
                                        void handleOverwriteUpload()
                                        return
                                    }
                                    void submitDialogAction()
                                }}
                            >
                                {actionSubmitting ? <CircularProgress size={16} color="inherit" /> : t('myAppsDetailPage.tabs.volumes.fileManager.dialogs.confirm')}
                            </Button>
                        </div>
                    </div>
                </SurfaceDialog>
            </SurfaceDialog>

            <Snackbar
                open={feedback !== null}
                onClose={() => setFeedback(null)}
                autoHideDuration={4000}
                anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
                sx={
                    scopeRect
                        ? {
                            position: 'fixed',
                            top: Math.max(scopeRect.top + 20, 20),
                            left: `${scopeRect.left}px !important`,
                            width: `${scopeRect.width}px !important`,
                            display: 'flex',
                            justifyContent: 'center',
                            transform: 'none !important',
                            right: 'auto !important',
                            zIndex: 1712,
                        }
                        : { zIndex: 1712 }
                }
            >
                <Alert onClose={() => setFeedback(null)} severity="error" variant="filled" sx={{ width: 'fit-content', maxWidth: 'min(760px, calc(100vw - 32px))' }}>
                    {feedback?.message ?? ''}
                </Alert>
            </Snackbar>
        </>
    )
}
