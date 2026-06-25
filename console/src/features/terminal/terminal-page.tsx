import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Checkbox,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControlLabel,
    IconButton,
    InputAdornment,
    Menu,
    MenuItem,
    Skeleton,
    Stack,
    SvgIcon,
    TextField,
    Tooltip,
    Typography,
    Chip,
} from '@mui/material'
import type { SnackbarCloseReason } from '@mui/material'
import { alpha } from '@mui/material/styles'
import type { CSSProperties, ChangeEvent, MouseEvent as ReactMouseEvent, ReactNode } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FitAddon } from '@xterm/addon-fit'
import { ClipboardAddon } from '@xterm/addon-clipboard'
import { Terminal as XTerm } from 'xterm'

import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { SurfaceFeedbackToast } from '../../shared/design-system/standard-surfaces'
import { getSurfacePalette } from '../../shared/design-system/surface-theme'
import { useAppColorMode } from '../../app/providers/color-mode'
import { useProductAuth } from '../product-auth/product-auth-provider'
import 'xterm/css/xterm.css'
import './terminal-page.css'

type SessionStatus = 'connected' | 'idle' | 'ended'
type WorkspaceView = 'terminal' | 'files'
type AuthMethod = 'password' | 'key'
type ShellPreset = 'bash' | 'zsh' | 'sh' | 'fish' | 'custom'

type AccessForm = {
    profileId: string | null
    authMethod: AuthMethod
    name: string
    host: string
    username: string
    port: string
    password: string
    privateKey: string
    passphrase: string
    workingDirectory: string
    shellPreset: ShellPreset
    customShell: string
    shell: string
    remember: boolean
    isLocal: boolean
    hasExistingPassword: boolean
    hasExistingKey: boolean
}

type AccessFieldName = 'host' | 'username' | 'port' | 'password' | 'privateKey'

type TerminalSession = {
    id: string
    profileId: string | null
    title: string
    host: string
    user: string
    cwd: string
    status: SessionStatus
    startedAt: string
    transport: string
    buffer: string
}

type HostAccessProfileResponse = {
    configured: boolean
    remembered: boolean
    host: string
    local_host_ip?: string
    username: string
    port: number
    shell: string
    working_directory: string
    active_profile_id?: string | null
    default_profile_id?: string | null
    auth_method?: AuthMethod
    has_password?: boolean
    has_private_key?: boolean
    saved_profiles?: HostAccessSavedProfileSummary[]
    file_preferences?: HostAccessFilePreferences
    file_references?: string[]
    show_hidden_files: boolean
}

type HostAccessSavedProfileSummary = {
    profile_id: string
    name: string
    description: string
    host: string
    username: string
    auth_method: AuthMethod
    port: number
    shell: string
    is_default: boolean
    is_local: boolean
    has_password: boolean
    has_private_key: boolean
    created_at?: string | null
    text_editable: boolean
    working_directory?: string | null
}

type HostAccessFileItem = {
    path: string
    name: string
    item_type: 'file' | 'directory' | 'symlink'
    size: number
    mode?: string | null
    owner?: string | null
    group?: string | null
    owner_name?: string | null
    group_name?: string | null
    modified_at?: string | null
    created_at?: string | null
    accessed_at?: string | null
    symlink_target?: string | null
    mime_type?: string | null
    text_editable: boolean
}

type HostAccessFilePreferences = {
    view_mode: BrowserDisplayMode
    show_hidden_files: boolean
}

type HostAccessFileMetadata = HostAccessFileItem

type HostAccessDirectoryResponse = {
    current_path: string
    metadata: HostAccessFileMetadata
    items: HostAccessFileItem[]
}

type HostAccessTextFileResponse = {
    path: string
    content: string
}

type HostAccessMutationResponse = {
    path: string
    operation: string
}

type HostAccessPermissionBits = {
    read: boolean
    write: boolean
    execute: boolean
}

type HostAccessAttributesMutationResponse = HostAccessMutationResponse & {
    metadata: HostAccessFileMetadata
}

type BrowserDisplayMode = 'list' | 'grid'

type BrowserDialogState =
    | { type: 'create-folder' | 'create-file'; parentPath?: string }
    | { type: 'rename'; item: HostAccessFileItem }
    | { type: 'delete'; item: HostAccessFileItem }
    | { type: 'properties'; item: HostAccessFileItem }
    | null

type BrowserPropertiesForm = {
    owner: string
    group: string
    ownerPermissions: HostAccessPermissionBits
    groupPermissions: HostAccessPermissionBits
    otherPermissions: HostAccessPermissionBits
}

type BrowserClipboardState = {
    path: string
    name: string
    itemType: HostAccessFileItem['item_type']
    mode: 'copy' | 'cut'
} | null

type BrowserContextMenuState = {
    mouseX: number
    mouseY: number
    item: HostAccessFileItem | null
} | null

type FileVisualKind = 'directory' | 'image' | 'config' | 'certificate' | 'code' | 'document' | 'archive' | 'spreadsheet' | 'media' | 'file'

type HostAccessConnectionTestResponse = {
    success: boolean
    message: string
    host: string
    port: number
    username: string
}

type FeedbackState = {
    severity: 'success' | 'error' | 'info'
    message: string
}

type TerminalSocketMessage =
    | { type: 'ready'; session_id?: string; cwd?: string; username?: string }
    | { type: 'output'; session_id?: string; data?: string }
    | { type: 'closed'; session_id?: string }
    | { type: 'error'; message?: string; details?: string }

type FullscreenTarget = HTMLDivElement | null

type PersistedTerminalWorkspace = {
    accessReady: boolean
    sessions: TerminalSession[]
    activeSessionId: string | null
    workspaceView: WorkspaceView
    browserPath: string
    selectedEntryPath: string | null
    profileScope: string | null
}

const DEFAULT_HOST_ACCESS_FILE_PREFERENCES: HostAccessFilePreferences = {
    view_mode: 'list',
    show_hidden_files: false,
}

const IMAGE_FILE_EXTENSIONS = new Set(['.apng', '.avif', '.bmp', '.gif', '.ico', '.jpeg', '.jpg', '.png', '.svg', '.webp'])
const CONFIG_FILE_EXTENSIONS = new Set(['.conf', '.config', '.env', '.ini', '.properties', '.toml', '.yaml', '.yml'])
const CERTIFICATE_FILE_EXTENSIONS = new Set(['.cert', '.crt', '.key', '.pem', '.p12', '.pfx'])
const CODE_FILE_EXTENSIONS = new Set(['.c', '.cc', '.cpp', '.css', '.go', '.h', '.hpp', '.html', '.java', '.js', '.json', '.mdx', '.php', '.py', '.rb', '.rs', '.sh', '.sql', '.ts', '.tsx', '.vue', '.xml'])
const DOCUMENT_FILE_EXTENSIONS = new Set(['.doc', '.docx', '.md', '.pdf', '.rtf', '.txt'])
const ARCHIVE_FILE_EXTENSIONS = new Set(['.7z', '.bz2', '.gz', '.rar', '.tar', '.tgz', '.xz', '.zip'])
const SPREADSHEET_FILE_EXTENSIONS = new Set(['.csv', '.numbers', '.ods', '.xls', '.xlsx'])
const MEDIA_FILE_EXTENSIONS = new Set(['.aac', '.flac', '.m4a', '.mkv', '.mov', '.mp3', '.mp4', '.ogg', '.wav', '.webm'])

const LOCAL_HOST = '127.0.0.1'
const MAX_TERMINAL_SESSIONS = 6
const TERMINAL_WORKSPACE_STORAGE_KEY = 'websoft9:terminal-workspace-v1'
const TERMINAL_WORKSPACE_SKIP_RESTORE_KEY = 'websoft9:terminal-workspace-skip-restore-once'
let terminalWorkspaceMountCount = 0
const SHELL_PRESETS: Record<Exclude<ShellPreset, 'custom'>, string> = {
    bash: '/bin/bash',
    zsh: '/bin/zsh',
    sh: '/bin/sh',
    fish: '/usr/bin/fish',
}

const DEFAULT_ACCESS_FORM: AccessForm = {
    profileId: null,
    authMethod: 'password',
    name: '',
    host: '',
    username: '',
    port: '22',
    password: '',
    privateKey: '',
    passphrase: '',
    workingDirectory: '',
    shellPreset: 'bash',
    customShell: '',
    shell: '/bin/bash',
    remember: true,
    isLocal: false,
    hasExistingPassword: false,
    hasExistingKey: false,
}

const EMPTY_PERMISSION_BITS: HostAccessPermissionBits = {
    read: false,
    write: false,
    execute: false,
}

function resolveDefaultDirectory(username: string, workingDirectory: string): string {
    const trimmed = workingDirectory.trim()
    if (trimmed) {
        return normalizeDirectory(trimmed)
    }
    const fallbackUser = username.trim()
    return fallbackUser ? normalizeDirectory(`/home/${fallbackUser}`) : '/'
}

function normalizeDirectory(path: string): string {
    const parts = path.split('/').filter(Boolean)
    const normalized: string[] = []
    for (const part of parts) {
        if (part === '.') {
            continue
        }
        if (part === '..') {
            normalized.pop()
            continue
        }
        normalized.push(part)
    }
    return normalized.length ? `/${normalized.join('/')}` : '/'
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

function getFileExtension(name: string): string {
    const lastDotIndex = name.lastIndexOf('.')
    if (lastDotIndex < 0) {
        return ''
    }

    return name.slice(lastDotIndex).toLowerCase()
}

function getVisualKind(item: Pick<HostAccessFileItem, 'item_type' | 'name'>): FileVisualKind {
    if (item.item_type === 'directory') {
        return 'directory'
    }

    const extension = getFileExtension(item.name)
    if (IMAGE_FILE_EXTENSIONS.has(extension)) {
        return 'image'
    }
    if (CONFIG_FILE_EXTENSIONS.has(extension)) {
        return 'config'
    }
    if (CERTIFICATE_FILE_EXTENSIONS.has(extension)) {
        return 'certificate'
    }
    if (CODE_FILE_EXTENSIONS.has(extension)) {
        return 'code'
    }
    if (DOCUMENT_FILE_EXTENSIONS.has(extension)) {
        return 'document'
    }
    if (ARCHIVE_FILE_EXTENSIONS.has(extension)) {
        return 'archive'
    }
    if (SPREADSHEET_FILE_EXTENSIONS.has(extension)) {
        return 'spreadsheet'
    }
    if (MEDIA_FILE_EXTENSIONS.has(extension)) {
        return 'media'
    }

    return 'file'
}

function getBrowserEntryCategoryLabel(entry: Pick<HostAccessFileItem, 'item_type' | 'name'>, locale: string): string {
    const zh = isChineseLocale(locale)
    if (entry.item_type === 'symlink') {
        return zh ? '符号链接' : 'Symbolic link'
    }

    const kind = getVisualKind(entry)
    if (kind === 'directory') {
        return zh ? '文件夹' : 'Folder'
    }
    if (kind === 'image') {
        return zh ? '图片' : 'Image'
    }
    if (kind === 'config') {
        return zh ? '配置' : 'Config'
    }
    if (kind === 'certificate') {
        return zh ? '证书' : 'Certificate'
    }
    if (kind === 'code') {
        return zh ? '代码' : 'Code'
    }
    if (kind === 'document') {
        return zh ? '文档' : 'Document'
    }
    if (kind === 'archive') {
        return zh ? '压缩包' : 'Archive'
    }
    if (kind === 'spreadsheet') {
        return zh ? '表格' : 'Spreadsheet'
    }
    if (kind === 'media') {
        return zh ? '媒体' : 'Media'
    }

    return zh ? '文件' : 'File'
}

function getBrowserCategoryLabel(locale: string): string {
    return isChineseLocale(locale) ? '类别' : 'Type'
}

function parentDirectory(path: string): string {
    const normalized = normalizeDirectory(path)
    if (normalized === '/') {
        return '/'
    }
    const parts = normalized.split('/').filter(Boolean)
    return parts.length <= 1 ? '/' : `/${parts.slice(0, -1).join('/')}`
}

function buildPalette(isDarkMode: boolean) {
    const surfacePalette = getSurfacePalette(isDarkMode)
    return {
        pageBg: surfacePalette.panelBg,
        cardBg: surfacePalette.panelBg,
        cardSoft: surfacePalette.panelSoft,
        terminalBg: isDarkMode ? '#020617' : '#0b1220',
        terminalTab: surfacePalette.panelBg,
        terminalTabActive: surfacePalette.accent,
        text: surfacePalette.text,
        subtleText: surfacePalette.subtleText,
        border: surfacePalette.borderStrong,
        accent: surfacePalette.accent,
        success: '#059669',
        warning: '#d97706',
        danger: surfacePalette.danger,
        shadow: isDarkMode ? '0 12px 28px rgba(2, 6, 23, 0.28)' : '0 8px 24px rgba(15, 23, 42, 0.06)',
    } as const
}

function getStatusTone(status: SessionStatus, palette: ReturnType<typeof buildPalette>) {
    if (status === 'connected') {
        return palette.success
    }
    if (status === 'idle') {
        return palette.warning
    }
    return palette.danger
}

function inferShellPreset(shell: string): ShellPreset {
    const entry = Object.entries(SHELL_PRESETS).find(([, value]) => value === shell)
    return (entry?.[0] as ShellPreset | undefined) ?? 'custom'
}

function formatFileSize(size: number): string {
    if (size >= 1024 * 1024) {
        return `${(size / (1024 * 1024)).toFixed(1)} MB`
    }
    if (size >= 1024) {
        return `${Math.max(1, Math.round(size / 102.4) / 10)} KB`
    }
    return `${size} B`
}

function formatBrowserTimestamp(value: string | null | undefined, locale: string): string {
    if (!value) {
        return '—'
    }

    return new Date(value).toLocaleString(locale)
}

function formatBrowserIdentity(value: string | null | undefined): string {
    return value || '—'
}

function parsePermissionBits(mode: string | null | undefined, offset: number): HostAccessPermissionBits {
    if (!mode || mode.length < offset + 3) {
        return { ...EMPTY_PERMISSION_BITS }
    }
    const segment = mode.slice(offset, offset + 3)
    return {
        read: segment[0] === 'r',
        write: segment[1] === 'w',
        execute: ['x', 's', 't'].includes(segment[2] || ''),
    }
}

function createPropertiesForm(entry: HostAccessFileItem): BrowserPropertiesForm {
    return {
        owner: entry.owner || '',
        group: entry.group || '',
        ownerPermissions: parsePermissionBits(entry.mode, 1),
        groupPermissions: parsePermissionBits(entry.mode, 4),
        otherPermissions: parsePermissionBits(entry.mode, 7),
    }
}

function formatPermissionSegment(bits: HostAccessPermissionBits): string {
    return `${bits.read ? 'r' : '-'}${bits.write ? 'w' : '-'}${bits.execute ? 'x' : '-'}`
}

function buildModePreview(itemType: HostAccessFileItem['item_type'], form: BrowserPropertiesForm | null): string {
    if (!form) {
        return '—'
    }
    return `${itemType === 'directory' ? 'd' : '-'}${formatPermissionSegment(form.ownerPermissions)}${formatPermissionSegment(form.groupPermissions)}${formatPermissionSegment(form.otherPermissions)}`
}

function encodeFileToBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onerror = () => reject(reader.error ?? new Error('Failed to read file'))
        reader.onload = () => {
            const result = String(reader.result || '')
            const marker = 'base64,'
            const index = result.indexOf(marker)
            resolve(index >= 0 ? result.slice(index + marker.length) : result)
        }
        reader.readAsDataURL(file)
    })
}

function VisibilityOnIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M12 5c5.23 0 9.27 4.11 10.75 6.2a1.33 1.33 0 0 1 0 1.6C21.27 14.89 17.23 19 12 19S2.73 14.89 1.25 12.8a1.33 1.33 0 0 1 0-1.6C2.73 9.11 6.77 5 12 5Zm0 2C8.21 7 5.1 9.84 3.39 12 5.1 14.16 8.21 17 12 17s6.9-2.84 8.61-5C18.9 9.84 15.79 7 12 7Zm0 2.25A2.75 2.75 0 1 1 9.25 12 2.75 2.75 0 0 1 12 9.25Zm0 2A.75.75 0 1 0 12.75 12 .75.75 0 0 0 12 11.25Z" />
        </SvgIcon>
    )
}

function VisibilityOffIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="m4.71 3.29 16 16-1.42 1.42-2.43-2.43A11.65 11.65 0 0 1 12 19c-5.23 0-9.27-4.11-10.75-6.2a1.33 1.33 0 0 1 0-1.6A18.48 18.48 0 0 1 6.4 6.6L3.29 4.71 4.71 3.29Zm8.08 8.08-1.58-1.58a.75.75 0 1 0-1.42.63l2.37 2.37a.75.75 0 0 0 .63-1.42ZM7.96 8.16C6.14 9.09 4.55 10.45 3.39 12 5.1 14.16 8.21 17 12 17c1.16 0 2.26-.27 3.27-.73l-1.71-1.71a4.75 4.75 0 0 1-6.12-6.12L7.96 8.16ZM12 7c3.79 0 6.9 2.84 8.61 5a14.8 14.8 0 0 1-2.35 2.31l-1.43-1.43c.72-.63 1.33-1.28 1.78-1.88C18.9 9.84 15.79 7 12 7c-.73 0-1.43.1-2.1.29L8.19 5.58A9.8 9.8 0 0 1 12 7Z" />
        </SvgIcon>
    )
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

function RefreshActionIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M20 11a8 8 0 1 1-2.35-5.65" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
            <path d="M20 4v5h-5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
        </SvgIcon>
    )
}

function EditActionIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M4 17.5V20H6.5L16.8 9.7L14.3 7.2L4 17.5Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="2" />
            <path d="M13.6 7.9L16.1 10.4" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
            <path d="M14.9 6.6L16.1 5.4C16.8 4.7 18 4.7 18.7 5.4L18.8 5.5C19.5 6.2 19.5 7.4 18.8 8.1L17.6 9.3" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
        </SvgIcon>
    )
}

function ConnectActionIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
        </SvgIcon>
    )
}

function LocalHostIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M3 9.5L12 3L21 9.5V20H15V15H9V20H3V9.5Z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
        </SvgIcon>
    )
}

function TestActionIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M5 12.55a11 11 0 0 1 14 0" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
            <path d="M1.42 9a16 16 0 0 1 21.16 0" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
            <path d="M8.53 16.11a6 6 0 0 1 6.95 0" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
            <circle cx="12" cy="20" fill="currentColor" r="1.5" />
        </SvgIcon>
    )
}

function DeleteActionIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M5 7H19" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
            <path d="M9 7V5.5C9 4.67 9.67 4 10.5 4H13.5C14.33 4 15 4.67 15 5.5V7" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
            <path d="M7 7L7.8 18.2C7.87 19.18 8.68 19.94 9.66 19.94H14.34C15.32 19.94 16.13 19.18 16.2 18.2L17 7" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="2.2" />
            <path d="M10 10.5V16M14 10.5V16" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
        </SvgIcon>
    )
}

function CloseActionIcon() {
    return (
        <SvgIcon fontSize="small" viewBox="0 0 24 24">
            <path d="M7 7L17 17" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
            <path d="M17 7L7 17" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
        </SvgIcon>
    )
}

function EmptyTerminalIcon() {
    return (
        <SvgIcon viewBox="0 0 64 64">
            <path d="M18 18h28l8 8v22H10V26l8-8Z" fill="currentColor" opacity="0.08" />
            <path d="M18 18h28l8 8v22H10V26l8-8Z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.4" />
            <path d="M46 18v8h8" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.4" />
            <path d="M22 33h20" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.4" />
            <path d="M22 39h12" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.4" />
        </SvgIcon>
    )
}

function TerminalScopedOverlay({ open, onClose, centered = false, children }: { open: boolean; onClose: () => void; centered?: boolean; children: ReactNode }) {
    useEffect(() => {
        if (!open) {
            return
        }

        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                onClose()
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => {
            window.removeEventListener('keydown', handleKeyDown)
        }
    }, [onClose, open])

    if (!open) {
        return null
    }

    return (
        <Box
            sx={{
                position: 'absolute',
                inset: 0,
                zIndex: 20,
            }}
        >
            <Box
                onClick={onClose}
                sx={{
                    position: 'absolute',
                    inset: 0,
                    backgroundColor: 'rgba(15, 23, 42, 0.18)',
                }}
            />
            <Box
                sx={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: centered ? 'center' : 'flex-start',
                    justifyContent: 'center',
                    px: { xs: 1, sm: 1.5, md: 2 },
                    py: { xs: 1.5, sm: 2, md: 2.5 },
                    pointerEvents: 'none',
                }}
            >
                <Box
                    sx={{
                        pointerEvents: 'auto',
                        width: '100%',
                        maxWidth: '100%',
                        maxHeight: '100%',
                        overflowY: 'auto',
                        overscrollBehavior: 'contain',
                        WebkitOverflowScrolling: 'touch',
                    }}
                >
                    {children}
                </Box>
            </Box>
        </Box>
    )
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

function ToolbarGlyph({ kind }: { kind: 'properties' | 'rename' | 'trash' | 'edit' | 'save' | 'close' }) {
    if (kind === 'properties') {
        return (
            <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <circle cx="12" cy="12" fill="none" r="8" stroke="currentColor" strokeWidth="2.2" />
                <path d="M12 10V16" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
                <circle cx="12" cy="7.2" fill="currentColor" r="1.4" />
            </svg>
        )
    }

    if (kind === 'rename') {
        return (
            <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <path d="M4 17.5V20H6.5L16.8 9.7L14.3 7.2L4 17.5Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="2" />
                <path d="M13.6 7.9L16.1 10.4" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
                <path d="M14.9 6.6L16.1 5.4C16.8 4.7 18 4.7 18.7 5.4L18.8 5.5C19.5 6.2 19.5 7.4 18.8 8.1L17.6 9.3" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
            </svg>
        )
    }

    if (kind === 'trash') {
        return (
            <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <path d="M5 7H19" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
                <path d="M9 7V5.5C9 4.67 9.67 4 10.5 4H13.5C14.33 4 15 4.67 15 5.5V7" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
                <path d="M7 7L7.8 18.2C7.87 19.18 8.68 19.94 9.66 19.94H14.34C15.32 19.94 16.13 19.18 16.2 18.2L17 7" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="2.2" />
                <path d="M10 10.5V16M14 10.5V16" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
            </svg>
        )
    }

    if (kind === 'edit') {
        return (
            <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <path d="M4 17.5V20H6.5L16.8 9.7L14.3 7.2L4 17.5Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="2" />
                <path d="M13.6 7.9L16.1 10.4" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
                <path d="M14.9 6.6L16.1 5.4C16.8 4.7 18 4.7 18.7 5.4L18.8 5.5C19.5 6.2 19.5 7.4 18.8 8.1L17.6 9.3" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
            </svg>
        )
    }

    if (kind === 'save') {
        return (
            <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <path d="M6 4H16L19 7V20H5V5C5 4.4 5.4 4 6 4Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="2" />
                <path d="M8 4V9H15V4" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="2" />
                <path d="M8 15H16" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
            </svg>
        )
    }

    return (
        <svg aria-hidden="true" className="terminal-files-toolbar-glyph-svg" viewBox="0 0 24 24">
            <path d="M7 7L17 17" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
            <path d="M17 7L7 17" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
        </svg>
    )
}

function buildSessionBaseTitle(access: Pick<AccessForm, 'host' | 'username'>): string {
    const host = access.host.trim() || LOCAL_HOST
    const username = access.username.trim()
    return username ? `${username}@${host}` : host
}

function buildUniqueSessionTitle(baseTitle: string, sessions: TerminalSession[]): string {
    if (!sessions.some((session) => session.title === baseTitle)) {
        return baseTitle
    }

    let suffix = 2
    while (sessions.some((session) => session.title === `${baseTitle}-${suffix}`)) {
        suffix += 1
    }
    return `${baseTitle}-${suffix}`
}

function isChineseLocale(value: string | null | undefined): boolean {
    return String(value || '').toLowerCase().startsWith('zh')
}

function buildWorkspaceProfileScope(operatorId: string | null | undefined, profileId: string | null | undefined, host: string | null | undefined, username: string | null | undefined, port: number | string | null | undefined): string {
    const normalizedOperatorId = String(operatorId || 'anonymous').trim() || 'anonymous'
    const normalizedProfileId = String(profileId || '').trim()
    const normalizedHost = String(host || '').trim().toLowerCase()
    const normalizedUsername = String(username || '').trim().toLowerCase()
    const normalizedPort = String(port || '').trim() || '22'
    return normalizedProfileId
        ? `${normalizedOperatorId}:${normalizedProfileId}`
        : `${normalizedOperatorId}:${normalizedHost}:${normalizedUsername}:${normalizedPort}`
}

function createSession(access: AccessForm, sessions: TerminalSession[], locale: string): TerminalSession {
    const baseTitle = buildSessionBaseTitle(access)
    return {
        id: `session-${Date.now()}-${sessions.length + 1}-${Math.random().toString(16).slice(2)}`,
        profileId: access.profileId,
        title: buildUniqueSessionTitle(baseTitle, sessions),
        host: access.host.trim() || LOCAL_HOST,
        user: access.username,
        cwd: resolveDefaultDirectory(access.username, access.workingDirectory),
        status: 'idle',
        startedAt: new Date().toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', hour12: false }),
        transport: 'AppHub WebSocket + SSH PTY',
        buffer: '',
    }
}

function buildTerminalSocketUrl(sessionId: string): string {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = new URL(`${protocol}://${window.location.host}/host-access/terminal/ws`)
    url.searchParams.set('session_id', sessionId)
    url.searchParams.set('cols', '120')
    url.searchParams.set('rows', '32')
    return url.toString()
}

function profileToAccessForm(profile: HostAccessProfileResponse): AccessForm {
    const shell = profile.shell || DEFAULT_ACCESS_FORM.shell
    const shellPreset = inferShellPreset(shell)
    const host = profile.host || DEFAULT_ACCESS_FORM.host
    const isLocal = !host || host === LOCAL_HOST || host.toLowerCase() === 'localhost'
    return {
        profileId: profile.active_profile_id || null,
        authMethod: profile.auth_method || 'password',
        name: DEFAULT_ACCESS_FORM.name,
        host,
        username: profile.username || DEFAULT_ACCESS_FORM.username,
        port: String(profile.port || DEFAULT_ACCESS_FORM.port),
        password: '',
        privateKey: '',
        passphrase: '',
        workingDirectory: profile.working_directory || '',
        shellPreset,
        customShell: shellPreset === 'custom' ? shell : '',
        shell,
        remember: profile.remembered,
        isLocal,
        hasExistingPassword: profile.has_password ?? false,
        hasExistingKey: profile.has_private_key ?? false,
    }
}

function savedProfileToAccessForm(profile: HostAccessSavedProfileSummary): AccessForm {
    const shell = profile.shell || DEFAULT_ACCESS_FORM.shell
    const shellPreset = inferShellPreset(shell)
    return {
        profileId: profile.profile_id,
        authMethod: profile.auth_method,
        name: profile.name,
        host: profile.host,
        username: profile.username,
        port: String(profile.port || DEFAULT_ACCESS_FORM.port),
        password: '',
        privateKey: '',
        passphrase: '',
        workingDirectory: '',
        shellPreset,
        customShell: shellPreset === 'custom' ? shell : '',
        shell,
        remember: true,
        isLocal: profile.is_local,
        hasExistingPassword: profile.has_password,
        hasExistingKey: profile.has_private_key ?? false,
    }
}

function loadPersistedTerminalWorkspace(): PersistedTerminalWorkspace | null {
    if (typeof window === 'undefined') {
        return null
    }

    try {
        const raw = window.sessionStorage.getItem(TERMINAL_WORKSPACE_STORAGE_KEY)
        if (!raw) {
            return null
        }
        return JSON.parse(raw) as PersistedTerminalWorkspace
    } catch {
        return null
    }
}

function savePersistedTerminalWorkspace(state: PersistedTerminalWorkspace) {
    if (typeof window === 'undefined') {
        return
    }

    window.sessionStorage.setItem(TERMINAL_WORKSPACE_STORAGE_KEY, JSON.stringify(state))
}

function clearPersistedTerminalWorkspace() {
    if (typeof window === 'undefined') {
        return
    }

    window.sessionStorage.removeItem(TERMINAL_WORKSPACE_STORAGE_KEY)
}

function markSkipRestoreOnNextLoad() {
    if (typeof window === 'undefined') {
        return
    }

    window.sessionStorage.setItem(TERMINAL_WORKSPACE_SKIP_RESTORE_KEY, '1')
}

function consumeSkipRestoreOnNextLoad(): boolean {
    if (typeof window === 'undefined') {
        return false
    }

    const shouldSkip = window.sessionStorage.getItem(TERMINAL_WORKSPACE_SKIP_RESTORE_KEY) === '1'
    if (shouldSkip) {
        window.sessionStorage.removeItem(TERMINAL_WORKSPACE_SKIP_RESTORE_KEY)
    }
    return shouldSkip
}

function isReloadNavigation(): boolean {
    if (typeof window === 'undefined' || typeof window.performance === 'undefined') {
        return false
    }

    const [navigationEntry] = window.performance.getEntriesByType('navigation') as PerformanceNavigationTiming[]
    return navigationEntry?.type === 'reload'
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

    if (!response.ok) {
        let detail = `Request failed: ${response.status}`
        try {
            const body = (await response.json()) as { details?: string; message?: string }
            detail = body.details || body.message || detail
        } catch {
        }
        throw new Error(detail)
    }

    return response.json() as Promise<T>
}

export function TerminalPage() {
    const { t, i18n } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const { status } = useProductAuth()
    const isDarkMode = colorMode === 'dark'
    const palette = useMemo(() => buildPalette(isDarkMode), [isDarkMode])
    const isChinese = isChineseLocale(i18n.resolvedLanguage || i18n.language)
    const locale = isChinese ? 'zh-CN' : 'en-US'

    const copy = useMemo(
        () =>
            isChinese
                ? {
                    description: '连接主机，执行终端命令和文件管理',
                    localServerTitle: '主机',
                    disconnect: '关闭当前会话',
                    hostSelectorTitle: '主机列表',
                    newConnectionTitle: '新建连接',
                    quickConnectNewHost: '新建连接',
                    emptyTerminalTitle: '暂无终端连接',
                    emptyTerminalHint: '点击上方 + 新建连接，或从右上角主机列表选择已保存主机。',
                    emptyTerminalShellTitle: '终端工作区',
                    disconnectedStateLabel: '未连接',
                    workspaceIdleTitle: '尚未连接主机',
                    workspaceIdleSubtitle: '点击上方 + 新建连接，或从右上角主机列表选择已保存主机。',
                    accessTitle: '登录主机',
                    accessSubtitle: '已保存的登录信息会按当前平台用户隔离存储。选择已有账号可直接登录，也可以新增一条登录信息。',
                    currentLoginTitle: '添加连接信息',
                    currentLoginSubtitle: '填写主机连接参数，可先测试，再手动连接。',
                    authPassword: '密码',
                    authKey: '密钥',
                    port: '端口',
                    username: '用户名',
                    password: '密码',
                    showPassword: '显示密码',
                    hidePassword: '隐藏密码',
                    privateKey: '私钥内容',
                    privateKeyUploadAction: '上传私钥文件',
                    passphrase: '密钥口令',
                    privateKeyHint: '粘贴 OpenSSH 或 PEM 私钥内容。',
                    remember: '保存凭证',
                    keepExistingPassword: '（保留已保存的密码）',
                    keepExistingKey: '（保留已保存的密钥）',
                    accessSubmit: '确定',
                    connectionTestTitle: '连接测试',
                    connectionTestSuccess: '连接测试成功',
                    viewTerminal: '终端',
                    viewFiles: '文件',
                    newSessionAria: '新建会话',
                    sessionLimitReached: `最多同时打开 ${MAX_TERMINAL_SESSIONS} 个会话。`,
                    enterFullscreen: '进入全屏',
                    exitFullscreen: '退出全屏',
                    sessionEmpty: '点击 + 打开新会话',
                    syncCwd: '终端进入此目录',
                    browseBack: '后退',
                    browseForward: '前进',
                    browseUp: '上一级',
                    refresh: '刷新',
                    createFolder: '新建目录',
                    createFile: '新建文件',
                    uploadFile: '上传文件',
                    listView: '列表视图',
                    gridView: '网格视图',
                    toggleView: '切换显示模式',
                    showHiddenFiles: '显示隐藏文件',
                    hideHiddenFiles: '隐藏隐藏文件',
                    pathPlaceholder: '输入目录路径后回车',
                    searchPlaceholder: '在当前目录中搜索',
                    invalidPath: '输入的路径无效或不可访问',
                    createFolderTitle: '新建目录',
                    createFileTitle: '新建文件',
                    renameTitle: '重命名',
                    deleteTitle: '删除',
                    nameLabel: '名称',
                    createConfirm: '创建',
                    renameConfirm: '重命名',
                    deleteConfirm: '删除',
                    renameAction: '重命名',
                    deleteAction: '删除',
                    copyAction: '复制',
                    cutAction: '剪切',
                    pasteAction: '粘贴',
                    downloadAction: '下载',
                    propertiesAction: '属性',
                    editAction: '编辑',
                    saveFile: '保存文件',
                    closeEditor: '关闭编辑',
                    editorEmpty: '双击可编辑文件后，可在这里直接修改并保存。',
                    editorLoading: '正在读取文件…',
                    uploadSuccess: '文件上传成功',
                    createSuccess: '创建成功',
                    renameSuccess: '重命名成功',
                    deleteSuccess: '删除成功',
                    copySuccess: '已复制到剪贴板',
                    pasteSuccess: '粘贴成功',
                    saveSuccess: '文件已保存',
                    nameExists: '同名文件或目录已存在',
                    deletePrompt: '删除后不能恢复，是否确定？',
                    deleteTargetLabel: '正在删除',
                    reconnect: '重新连接',
                    authMethodLabel: '认证方式',
                    shellPresetLabel: 'Shell 类型',
                    promptReconnect: '会话已断开，可重新连接。',
                    fileEmpty: '这个目录下暂时没有可展示的内容。',
                    filePreviewTitle: '编辑器',
                    filePreviewEmpty: '双击可编辑文本文件后，可在这里编辑。',
                    browserLoading: '正在读取目录…',
                    sessionBadgeConnected: '运行中',
                    sessionBadgeIdle: '连接中',
                    sessionBadgeEnded: '已结束',
                    noAuthAlert: '当前流程已关闭产品侧认证，因此终端工作区暂不可用。',
                    browserErrorTitle: '目录读取失败',
                    inspectorTitle: '属性',
                    detailsEmpty: '单击选择文件或目录后，可在这里查看属性。',
                    modeLabel: '模式',
                    ownerLabel: '所有者',
                    groupLabel: '用户组',
                    modifiedLabel: '修改时间',
                    sizeLabel: '大小',
                    accessedLabel: '访问时间',
                    createdLabel: '创建时间',
                    accessErrorTitle: '宿主机登录失败',
                    accessValidationTitle: '请先补全连接信息',
                    terminalErrorTitle: '终端连接失败',
                    directoryLabel: '目录',
                    filesLabel: '文件',
                    propertiesTitle: '属性',
                    propertiesSave: '保存属性',
                    propertiesSuccess: '属性已更新',
                    permissionsTitle: '权限',
                    permissionsOwner: '所有者',
                    permissionsGroup: '用户组',
                    permissionsOther: '其他用户',
                    permissionsRead: '读',
                    permissionsWrite: '写',
                    permissionsExecute: '执行',
                    modePreviewLabel: '模式预览',
                    savedProfilesTitle: '主机列表',
                    savedProfilesEmpty: '当前还没有保存的连接信息。',
                    savedProfilesSubtitle: '通过列表选择已保存连接，或新增主机后再连接。',
                    addHostAction: '添加主机',
                    connectionNameLabel: '名称',
                    searchConnectionsPlaceholder: '搜索主机或用户名',
                    actionsLabel: '操作',
                    localLabel: 'Local',
                    noSavedProfilesResults: '没有匹配的连接。',
                    updatedAtLabel: '更新时间',
                    savedLogin: '连接',
                    setDefault: '设为默认',
                    deleteProfile: '删除',
                    defaultLabel: '默认',
                    currentProfileLabel: '当前',
                    defaultUpdated: '默认登录信息已更新',
                    profileDeleted: '连接已删除',
                    disconnectingAction: '关闭会话中…',
                    connectingAction: '连接中…',
                    deleteProfileTitle: '删除连接',
                    deleteProfilePrompt: '确定删除这个已保存连接吗？删除后需要重新输入认证信息。',
                    cancel: '取消',
                    confirmDelete: '确认删除',
                    host: '主机',
                    hostRequired: '请输入主机地址',
                    duplicateUsername: '该主机和用户名的连接已存在，请勿重复添加。',
                    authMethodPasswordHint: '密码登录',
                    authMethodKeyHint: '密钥登录',
                    usernameRequired: '请输入用户名',
                    passwordRequired: '请输入密码',
                    privateKeyRequired: '请输入私钥内容',
                    portInvalid: '请输入 1 到 65535 之间的端口',
                    localHostOption: '本地主机',
                    remoteHostOption: '远程主机',
                }
                : {
                    description: 'Connect to a host to run terminal commands and manage files.',
                    localServerTitle: 'Host',
                    disconnect: 'Close current session',
                    hostSelectorTitle: 'Host list',
                    newConnectionTitle: 'New connection',
                    quickConnectNewHost: 'New connection',
                    emptyTerminalTitle: 'No terminal connection',
                    emptyTerminalHint: 'Use + above to create a connection, or open the host list in the top-right corner to choose a saved host.',
                    emptyTerminalShellTitle: 'Terminal workspace',
                    disconnectedStateLabel: 'Disconnected',
                    workspaceIdleTitle: 'No host connected',
                    workspaceIdleSubtitle: 'Use + above to create a connection, or open the host list in the top-right corner to choose a saved host.',
                    accessTitle: 'Sign in to host',
                    accessSubtitle: 'Saved login information is isolated per signed-in platform operator. Pick an existing login or add a new one.',
                    currentLoginTitle: 'Add connection information',
                    currentLoginSubtitle: 'Enter the host settings, test the connection, then connect manually.',
                    authPassword: 'Password',
                    authKey: 'Private key',
                    port: 'Port',
                    username: 'Username',
                    password: 'Password',
                    showPassword: 'Show password',
                    hidePassword: 'Hide password',
                    privateKey: 'Private key',
                    privateKeyUploadAction: 'Upload private key file',
                    passphrase: 'Passphrase',
                    privateKeyHint: 'Paste an OpenSSH or PEM private key.',
                    remember: 'Save credential',
                    keepExistingPassword: '(keep saved password)',
                    keepExistingKey: '(keep saved key)',
                    accessSubmit: 'Confirm',
                    connectionTestTitle: 'Connection test',
                    connectionTestSuccess: 'Connection test succeeded',
                    viewTerminal: 'Terminal',
                    viewFiles: 'Files',
                    newSessionAria: 'New session',
                    sessionLimitReached: `Open at most ${MAX_TERMINAL_SESSIONS} sessions at the same time.`,
                    enterFullscreen: 'Enter fullscreen',
                    exitFullscreen: 'Exit fullscreen',
                    sessionEmpty: 'Use + to open a session',
                    syncCwd: 'Open directory in terminal',
                    browseBack: 'Back',
                    browseForward: 'Forward',
                    browseUp: 'Up',
                    refresh: 'Refresh',
                    createFolder: 'Create folder',
                    createFile: 'Create file',
                    uploadFile: 'Upload file',
                    listView: 'List view',
                    gridView: 'Grid view',
                    toggleView: 'Switch display mode',
                    showHiddenFiles: 'Show hidden files',
                    hideHiddenFiles: 'Hide hidden files',
                    pathPlaceholder: 'Enter a directory path and press Enter',
                    searchPlaceholder: 'Search in current directory',
                    invalidPath: 'The requested path is invalid or inaccessible',
                    createFolderTitle: 'Create folder',
                    createFileTitle: 'Create file',
                    renameTitle: 'Rename',
                    deleteTitle: 'Delete',
                    nameLabel: 'Name',
                    createConfirm: 'Create',
                    renameConfirm: 'Rename',
                    deleteConfirm: 'Delete',
                    renameAction: 'Rename',
                    deleteAction: 'Delete',
                    copyAction: 'Copy',
                    cutAction: 'Cut',
                    pasteAction: 'Paste',
                    downloadAction: 'Download',
                    propertiesAction: 'Properties',
                    editAction: 'Edit',
                    saveFile: 'Save file',
                    closeEditor: 'Close editor',
                    editorEmpty: 'Double-click an editable file to edit it here.',
                    editorLoading: 'Loading file…',
                    uploadSuccess: 'File uploaded',
                    createSuccess: 'Created successfully',
                    renameSuccess: 'Renamed successfully',
                    deleteSuccess: 'Deleted successfully',
                    copySuccess: 'Copied to clipboard',
                    pasteSuccess: 'Pasted successfully',
                    saveSuccess: 'File saved',
                    nameExists: 'An item with the same name already exists',
                    deletePrompt: 'This action cannot be undone. Continue?',
                    deleteTargetLabel: 'Deleting',
                    reconnect: 'Reconnect',
                    authMethodLabel: 'Authentication',
                    shellPresetLabel: 'Shell type',
                    promptReconnect: 'The session is disconnected. Reconnect to continue.',
                    fileEmpty: 'No entries are available in this directory.',
                    filePreviewTitle: 'Editor',
                    filePreviewEmpty: 'Double-click an editable text file to edit it here.',
                    browserLoading: 'Loading directory…',
                    sessionBadgeConnected: 'Connected',
                    sessionBadgeIdle: 'Connecting',
                    sessionBadgeEnded: 'Ended',
                    noAuthAlert: 'Product-side authentication is disabled, so the terminal workspace is not available in the current flow.',
                    browserErrorTitle: 'Directory load failed',
                    inspectorTitle: 'Details',
                    detailsEmpty: 'Select a file or directory to view its details here.',
                    modeLabel: 'Mode',
                    ownerLabel: 'Owner',
                    groupLabel: 'Group',
                    modifiedLabel: 'Modified',
                    sizeLabel: 'Size',
                    accessedLabel: 'Accessed',
                    createdLabel: 'Created',
                    accessErrorTitle: 'Local host sign-in failed',
                    accessValidationTitle: 'Complete the required connection information first',
                    terminalErrorTitle: 'Terminal connection failed',
                    directoryLabel: 'Directory',
                    filesLabel: 'files',
                    propertiesTitle: 'Properties',
                    propertiesSave: 'Save properties',
                    propertiesSuccess: 'Properties updated',
                    permissionsTitle: 'Permissions',
                    permissionsOwner: 'Owner',
                    permissionsGroup: 'Group',
                    permissionsOther: 'Others',
                    permissionsRead: 'Read',
                    permissionsWrite: 'Write',
                    permissionsExecute: 'Execute',
                    modePreviewLabel: 'Mode preview',
                    savedProfilesTitle: 'Host list',
                    savedProfilesEmpty: 'No saved connection information is available yet.',
                    savedProfilesSubtitle: 'Choose a saved connection from the list, or add a host before connecting.',
                    addHostAction: 'Add host',
                    connectionNameLabel: 'Name',
                    searchConnectionsPlaceholder: 'Search host or username',
                    actionsLabel: 'Actions',
                    localLabel: 'Local',
                    noSavedProfilesResults: 'No connections match the search.',
                    updatedAtLabel: 'Updated',
                    savedLogin: 'Connect',
                    setDefault: 'Set default',
                    deleteProfile: 'Delete',
                    defaultLabel: 'Default',
                    currentProfileLabel: 'Current',
                    defaultUpdated: 'Default login information updated',
                    profileDeleted: 'Connection deleted',
                    disconnectingAction: 'Closing session…',
                    connectingAction: 'Connecting…',
                    deleteProfileTitle: 'Delete connection',
                    deleteProfilePrompt: 'Delete this saved connection? You will need to enter the credentials again afterwards.',
                    cancel: 'Cancel',
                    confirmDelete: 'Delete',
                    host: 'Host',
                    hostRequired: 'Enter a host address',
                    duplicateUsername: 'A connection with this host and username already exists.',
                    authMethodPasswordHint: 'Password login',
                    authMethodKeyHint: 'Private key login',
                    usernameRequired: 'Enter a username',
                    passwordRequired: 'Enter a password',
                    privateKeyRequired: 'Enter the private key content',
                    portInvalid: 'Enter a port between 1 and 65535',
                    localHostOption: 'Local host',
                    remoteHostOption: 'Remote host',
                },
        [isChinese],
    )

    const [accessForm, setAccessForm] = useState<AccessForm>(DEFAULT_ACCESS_FORM)
    const [savedProfiles, setSavedProfiles] = useState<HostAccessSavedProfileSummary[]>([])
    const [, setActiveProfileId] = useState<string | null>(null)
    const [currentProfileScope, setCurrentProfileScope] = useState<string | null>(null)
    const [sessions, setSessions] = useState<TerminalSession[]>([])
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
    const [workspaceView, setWorkspaceView] = useState<WorkspaceView>('terminal')
    const [browserPath, setBrowserPath] = useState('/')
    const [browserRefreshNonce, setBrowserRefreshNonce] = useState(0)
    const [browserHistory, setBrowserHistory] = useState<string[]>(['/'])
    const [browserHistoryIndex, setBrowserHistoryIndex] = useState(0)
    const [pathInputValue, setPathInputValue] = useState('/')
    const [pathSuggestions, setPathSuggestions] = useState<string[]>([])
    const [directorySearch, setDirectorySearch] = useState('')
    const [selectedEntryPath, setSelectedEntryPath] = useState<string | null>(null)
    const [browserMetadata, setBrowserMetadata] = useState<HostAccessFileMetadata | null>(null)
    const [browserDisplayMode, setBrowserDisplayMode] = useState<BrowserDisplayMode>('list')
    const [showHiddenFiles, setShowHiddenFiles] = useState(false)
    const [accessReady, setAccessReady] = useState(false)
    const [accessBootstrapped, setAccessBootstrapped] = useState(false)
    const [isTerminalFullscreen, setIsTerminalFullscreen] = useState(false)
    const [isTerminalOverlayFullscreen, setIsTerminalOverlayFullscreen] = useState(false)
    const [feedback, setFeedback] = useState<FeedbackState | null>(null)
    const [isAccessDialogOpen, setIsAccessDialogOpen] = useState(false)
    const [accessDialogMode, setAccessDialogMode] = useState<'new-connection' | 'add-host' | 'edit'>('add-host')
    const [localHostIp, setLocalHostIp] = useState('172.17.0.1')
    const [isHostSelectorOpen, setIsHostSelectorOpen] = useState(false)
    const [createSessionAnchorEl, setCreateSessionAnchorEl] = useState<HTMLElement | null>(null)
    const [profileSearchValue, setProfileSearchValue] = useState('')
    const [pendingDeleteProfile, setPendingDeleteProfile] = useState<HostAccessSavedProfileSummary | null>(null)
    const [isSubmittingAccess, setIsSubmittingAccess] = useState(false)
    const [isTestingConnection, setIsTestingConnection] = useState(false)
    const [isRefreshingProfiles, setIsRefreshingProfiles] = useState(false)
    const [isDisconnecting, setIsDisconnecting] = useState(false)
    const [activatingProfileId, setActivatingProfileId] = useState<string | null>(null)
    const [testingProfileId, setTestingProfileId] = useState<string | null>(null)
    const [accessErrors, setAccessErrors] = useState<Partial<Record<AccessFieldName, string>>>({})
    const [passwordVisible, setPasswordVisible] = useState(false)
    const [browserLoading, setBrowserLoading] = useState(false)
    const [isEditorLoading, setIsEditorLoading] = useState(false)
    const [isFileActionSubmitting, setIsFileActionSubmitting] = useState(false)
    const [browserEntries, setBrowserEntries] = useState<HostAccessFileItem[]>([])
    const [editorPath, setEditorPath] = useState<string | null>(null)
    const [editorContent, setEditorContent] = useState('')
    const [editorInitialContent, setEditorInitialContent] = useState('')
    const [browserDialogState, setBrowserDialogState] = useState<BrowserDialogState>(null)
    const [browserDialogName, setBrowserDialogName] = useState('')
    const [browserPropertiesForm, setBrowserPropertiesForm] = useState<BrowserPropertiesForm | null>(null)
    const [browserClipboard, setBrowserClipboard] = useState<BrowserClipboardState>(null)
    const [browserContextMenu, setBrowserContextMenu] = useState<BrowserContextMenuState>(null)
    const formBusy = isSubmittingAccess || isTestingConnection

    const terminalHostRef = useRef<HTMLDivElement | null>(null)
    const terminalShellRef = useRef<HTMLDivElement | null>(null)
    const terminalWorkspaceShellRef = useRef<HTMLDivElement | null>(null)
    const browserInspectorBodyRef = useRef<HTMLDivElement | null>(null)
    const xtermRef = useRef<XTerm | null>(null)
    const fitAddonRef = useRef<FitAddon | null>(null)
    const activeSessionRef = useRef<TerminalSession | null>(null)
    const terminalWrittenRef = useRef<Record<string, number>>({})
    const lastRenderedSessionIdRef = useRef<string | null>(null)
    const browserRequestIdRef = useRef(0)
    const fileContentRequestIdRef = useRef(0)
    const sessionSocketRef = useRef<Record<string, WebSocket>>({})
    const sessionSocketCloseModeRef = useRef<Record<string, 'detach' | 'terminate' | 'remote'>>({})
    const accessFieldRefs = useRef<Partial<Record<AccessFieldName, HTMLInputElement | HTMLTextAreaElement | null>>>({})
    const accessPrivateKeyUploadInputRef = useRef<HTMLInputElement | null>(null)
    const uploadInputRef = useRef<HTMLInputElement | null>(null)

    const activeSession = sessions.find((item) => item.id === activeSessionId) ?? sessions[0] ?? null
    const activeFileProfileId = activeSession?.profileId ?? null
    const filesViewEnabled = accessReady && activeSession !== null && activeSession.status !== 'ended'
    const filteredSavedProfiles = useMemo(() => {
        const keyword = profileSearchValue.trim().toLowerCase()
        const filtered = keyword
            ? savedProfiles.filter((profile) => [profile.name, profile.host, profile.username, String(profile.port)].some((value) => String(value || '').toLowerCase().includes(keyword)))
            : savedProfiles
        return [...filtered].sort((a, b) => {
            if (a.is_local !== b.is_local) return a.is_local ? -1 : 1
            return (a.name || a.host).localeCompare(b.name || b.host)
        })
    }, [profileSearchValue, savedProfiles])
    const visibleBrowserEntries = useMemo(() => {
        if (showHiddenFiles) {
            return browserEntries
        }
        return browserEntries.filter((entry) => !entry.name.startsWith('.'))
    }, [browserEntries, showHiddenFiles])
    const filteredBrowserEntries = useMemo(() => {
        const normalizedSearch = directorySearch.trim().toLowerCase()
        if (!normalizedSearch) {
            return visibleBrowserEntries
        }
        return visibleBrowserEntries.filter((entry) => entry.name.toLowerCase().includes(normalizedSearch))
    }, [visibleBrowserEntries, directorySearch])
    const visibleDirectoryCount = useMemo(() => visibleBrowserEntries.filter((entry) => entry.item_type === 'directory').length, [visibleBrowserEntries])
    const visibleFileEntries = useMemo(() => visibleBrowserEntries.filter((entry) => entry.item_type === 'file'), [visibleBrowserEntries])
    const visibleFileCount = visibleFileEntries.length
    const visibleFileSize = useMemo(() => visibleFileEntries.reduce((total, entry) => total + entry.size, 0), [visibleFileEntries])
    const selectedBrowserEntry = useMemo(() => browserEntries.find((entry) => entry.path === selectedEntryPath) ?? null, [browserEntries, selectedEntryPath])
    const activeBrowserEntry = selectedBrowserEntry ?? browserMetadata
    const inspectorEntry = selectedBrowserEntry ?? browserMetadata
    const canDeleteSelectedItem = Boolean(activeBrowserEntry && activeBrowserEntry.path !== '/') && editorPath === null && !isFileActionSubmitting
    const canEditSelectedItem = Boolean(selectedBrowserEntry?.item_type === 'file' && selectedBrowserEntry?.text_editable) && !isFileActionSubmitting
    const canShowInspectorProperties = Boolean(activeBrowserEntry) && !isFileActionSubmitting
    const editorDirty = editorPath !== null && editorContent !== editorInitialContent
    const terminalFieldSx = useMemo(
        () => ({
            '& .MuiOutlinedInput-root': {
                minHeight: 38,
                borderRadius: '4px',
                backgroundColor: palette.cardBg,
                '& fieldset': {
                    borderColor: palette.border,
                },
                '&:hover fieldset': {
                    borderColor: alpha(palette.accent, 0.4),
                },
                '&.Mui-focused fieldset': {
                    borderColor: palette.accent,
                    boxShadow: '0 0 0 1px rgba(59, 130, 246, 0.18)',
                },
                '&.Mui-error fieldset': {
                    borderColor: '#dc2626',
                },
                '&.Mui-error:hover fieldset': {
                    borderColor: '#dc2626',
                },
                '&.Mui-focused.Mui-error fieldset': {
                    borderColor: '#dc2626',
                    boxShadow: 'none',
                },
            },
            '& .MuiInputLabel-root': {
                color: palette.subtleText,
            },
            '& .MuiInputLabel-root.Mui-focused': {
                color: palette.subtleText,
            },
            '& .MuiInputBase-input, & .MuiSelect-select': {
                fontSize: 14,
                fontWeight: 400,
                color: palette.text,
                WebkitTextFillColor: palette.text,
            },
            '& .MuiInputBase-input::placeholder': {
                fontSize: 14,
                fontWeight: 400,
                color: palette.subtleText,
                WebkitTextFillColor: palette.subtleText,
                opacity: 1,
            },
            '& .MuiFormHelperText-root': {
                color: palette.subtleText,
                mx: 0,
                mt: 0.7,
                fontSize: 12.5,
                lineHeight: 1.45,
            },
            '& .MuiFormHelperText-root.Mui-error': {
                color: '#dc2626',
            },
        }),
        [palette],
    )
    const browserDialogFieldSx = useMemo(
        () => ({
            '& .MuiOutlinedInput-root': {
                minHeight: 40,
                borderRadius: '2px',
                backgroundColor: palette.cardBg,
                boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
                '& fieldset': {
                    borderColor: palette.border,
                },
                '&:hover fieldset': {
                    borderColor: alpha(palette.accent, 0.38),
                },
                '&.Mui-focused fieldset': {
                    borderColor: palette.accent,
                    borderWidth: 1,
                },
            },
            '& .MuiInputLabel-root': {
                color: palette.subtleText,
                fontSize: 13,
            },
            '& .MuiInputLabel-root.Mui-focused': {
                color: palette.subtleText,
            },
        }),
        [palette],
    )
    const editorTextareaSx = useMemo(
        () => ({
            '& .MuiOutlinedInput-root': {
                alignItems: 'stretch',
                borderRadius: '2px',
                backgroundColor: isDarkMode ? alpha(palette.terminalBg, 0.72) : palette.cardBg,
                color: palette.text,
                '& fieldset': {
                    borderColor: palette.border,
                },
                '&:hover fieldset': {
                    borderColor: alpha(palette.accent, 0.38),
                },
                '&.Mui-focused fieldset': {
                    borderColor: palette.accent,
                },
            },
            '& .MuiInputBase-inputMultiline': {
                color: palette.text,
                fontFamily: "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace",
                fontSize: 13.5,
                lineHeight: 1.55,
                WebkitTextFillColor: palette.text,
            },
        }),
        [isDarkMode, palette],
    )
    const terminalFilesThemeVars = useMemo(
        () => ({
            '--terminal-files-surface-bg': palette.cardBg,
            '--terminal-files-surface-soft': isDarkMode ? alpha(palette.pageBg, 0.52) : '#f8fafc',
            '--terminal-files-border': palette.border,
            '--terminal-files-text': palette.text,
            '--terminal-files-subtle-text': palette.subtleText,
            '--terminal-files-editor-bg': isDarkMode ? alpha(palette.terminalBg, 0.72) : palette.cardBg,
        }) as CSSProperties,
        [isDarkMode, palette],
    )
    const xtermTheme = useMemo(
        () => (isDarkMode
            ? {
                background: '#020617',
                foreground: '#e2e8f0',
                cursor: '#f8fafc',
                black: '#020617',
                brightBlack: '#475569',
                red: '#fca5a5',
                brightRed: '#fca5a5',
                green: '#86efac',
                brightGreen: '#86efac',
                yellow: '#fde68a',
                brightYellow: '#fde68a',
                blue: '#93c5fd',
                brightBlue: '#bfdbfe',
                magenta: '#c4b5fd',
                brightMagenta: '#ddd6fe',
                cyan: '#67e8f9',
                brightCyan: '#a5f3fc',
                white: '#e2e8f0',
                brightWhite: '#f8fafc',
            }
            : {
                background: '#f8fafc',
                foreground: '#0f172a',
                cursor: '#0f172a',
                black: '#1e293b',
                brightBlack: '#64748b',
                red: '#b91c1c',
                brightRed: '#dc2626',
                green: '#15803d',
                brightGreen: '#16a34a',
                yellow: '#a16207',
                brightYellow: '#ca8a04',
                blue: '#1d4ed8',
                brightBlue: '#2563eb',
                magenta: '#7c3aed',
                brightMagenta: '#8b5cf6',
                cyan: '#0f766e',
                brightCyan: '#0891b2',
                white: '#334155',
                brightWhite: '#0f172a',
            }),
        [isDarkMode],
    )
    const selectMenuProps = useMemo(
        () => ({
            disablePortal: true,
            slotProps: {
                paper: {
                    sx: {
                        mt: 0.5,
                        borderRadius: '4px',
                        border: `1px solid ${palette.border}`,
                        backgroundColor: palette.cardBg,
                        boxShadow: '0 14px 30px rgba(15, 23, 42, 0.12)',
                        '& .MuiMenuItem-root': {
                            minHeight: 36,
                            fontSize: 13.5,
                            color: palette.text,
                        },
                    },
                },
            },
        }),
        [palette],
    )
    const terminalMenuItemSx = useMemo(
        () => ({
            fontSize: 14,
            fontWeight: 500,
            color: palette.text,
            '&.Mui-selected': {
                backgroundColor: alpha(palette.accent, 0.1),
            },
            '&.Mui-selected:hover': {
                backgroundColor: alpha(palette.accent, 0.1),
            },
        }),
        [palette],
    )
    const surfaceCardSx = useMemo(
        () => ({
            borderRadius: '2px',
            border: `1px solid ${palette.border}`,
            background: palette.cardBg,
            boxShadow: '0 8px 24px rgba(15, 23, 42, 0.05)',
        }),
        [palette],
    )

    function buildFileApiUrl(pathname: string, searchParams?: Record<string, string | null | undefined>) {
        const url = new URL(pathname, window.location.origin)
        if (activeFileProfileId) {
            url.searchParams.set('profile_id', activeFileProfileId)
        }
        Object.entries(searchParams ?? {}).forEach(([key, value]) => {
            if (value) {
                url.searchParams.set(key, value)
            }
        })
        return `${url.pathname}${url.search}`
    }

    function invalidateFileBrowserRequests() {
        browserRequestIdRef.current += 1
        fileContentRequestIdRef.current += 1
    }

    useEffect(() => {
        activeSessionRef.current = activeSession
    }, [activeSession])

    useEffect(() => {
        const reloadNavigation = isReloadNavigation()
        const skipRestore = consumeSkipRestoreOnNextLoad()
        const shouldClearPersistedWorkspace = terminalWorkspaceMountCount === 0 && (reloadNavigation || skipRestore)
        if (shouldClearPersistedWorkspace) {
            clearPersistedTerminalWorkspace()
        }
        terminalWorkspaceMountCount += 1
    }, [])

    useEffect(() => {
        const handleBeforeUnload = () => {
            markSkipRestoreOnNextLoad()
        }

        window.addEventListener('beforeunload', handleBeforeUnload)
        return () => {
            window.removeEventListener('beforeunload', handleBeforeUnload)
        }
    }, [])

    useEffect(() => {
        if (!accessBootstrapped) {
            return
        }

        if (!accessReady || sessions.length === 0) {
            clearPersistedTerminalWorkspace()
            return
        }

        savePersistedTerminalWorkspace({
            accessReady,
            sessions,
            activeSessionId,
            workspaceView,
            browserPath,
            selectedEntryPath,
            profileScope: currentProfileScope ?? '',
        })
    }, [accessBootstrapped, accessReady, sessions, activeSessionId, workspaceView, browserPath, selectedEntryPath, currentProfileScope])

    function updateAccessForm<K extends keyof AccessForm>(key: K, value: AccessForm[K]) {
        if (key === 'authMethod') {
            setAccessErrors((current) => {
                const next = { ...current }
                delete next.password
                delete next.privateKey
                return next
            })
        }
        if (key === 'host' || key === 'username' || key === 'port' || key === 'password' || key === 'privateKey') {
            setAccessErrors((current) => {
                const fieldKey = key as AccessFieldName
                if (!current[fieldKey]) {
                    return current
                }
                const next = { ...current }
                delete next[fieldKey]
                return next
            })
        }
        setAccessForm((current) => ({ ...current, [key]: value }))
    }

    function showFeedback(severity: FeedbackState['severity'], message: string) {
        setFeedback({ severity, message })
    }

    function openAddHostDialog(mode: 'new-connection' | 'add-host' = 'add-host') {
        resetAccessForm()
        setAccessDialogMode(mode)
        setFeedback(null)
        setCreateSessionAnchorEl(null)
        setIsHostSelectorOpen(false)
        setIsAccessDialogOpen(true)
    }

    function openEditHostDialog(profile: HostAccessSavedProfileSummary) {
        setAccessForm(savedProfileToAccessForm(profile))
        setAccessDialogMode('edit')
        setAccessErrors({})
        setPasswordVisible(false)
        setFeedback(null)
        setCreateSessionAnchorEl(null)
        setIsHostSelectorOpen(false)
        setIsAccessDialogOpen(true)
    }

    function openHostSelector() {
        setFeedback(null)
        setProfileSearchValue('')
        setCreateSessionAnchorEl(null)
        setIsHostSelectorOpen(true)
        void refreshSavedProfiles()
    }

    function openCreateSessionMenu(anchor: HTMLElement) {
        setFeedback(null)
        setProfileSearchValue('')
        setIsHostSelectorOpen(false)
        setCreateSessionAnchorEl(anchor)
        void refreshSavedProfiles()
    }

    function closeCreateSessionMenu() {
        setCreateSessionAnchorEl(null)
    }

    async function handlePrivateKeyFileSelected(event: ChangeEvent<HTMLInputElement>) {
        const file = event.target.files?.[0]
        event.target.value = ''
        if (!file) {
            return
        }
        try {
            const content = await file.text()
            updateAccessForm('privateKey', content)
        } catch (error) {
            showFeedback('error', `${copy.privateKey}: ${error instanceof Error ? error.message : copy.accessErrorTitle}`)
        }
    }

    async function refreshSavedProfiles() {
        setIsRefreshingProfiles(true)
        try {
            const profile = await requestJson<HostAccessProfileResponse>('/api/host-access/profile', { method: 'GET' })
            setSavedProfiles(profile.saved_profiles ?? [])
            setActiveProfileId(profile.active_profile_id ?? null)
            if (profile.local_host_ip) {
                setLocalHostIp(profile.local_host_ip)
            }
            if (profile.configured && profile.username) {
                setAccessForm((current) => ({
                    ...current,
                    profileId: profile.active_profile_id ?? current.profileId,
                    host: profile.host || current.host,
                    username: profile.username || current.username,
                    port: String(profile.port || current.port || DEFAULT_ACCESS_FORM.port),
                    authMethod: profile.auth_method || current.authMethod,
                    workingDirectory: profile.working_directory || current.workingDirectory,
                    shell: profile.shell || current.shell,
                }))
            }
        } catch (error) {
            showFeedback('error', `${copy.accessErrorTitle}: ${error instanceof Error ? error.message : copy.accessErrorTitle}`)
        } finally {
            setIsRefreshingProfiles(false)
        }
    }

    function resetAccessForm(host = DEFAULT_ACCESS_FORM.host) {
        setAccessForm({ ...DEFAULT_ACCESS_FORM, host })
        setAccessErrors({})
        setPasswordVisible(false)
    }

    function focusAccessField(name: AccessFieldName) {
        const field = accessFieldRefs.current[name]
        field?.focus()
        field?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }

    function validateAccessForm(): boolean {
        const nextErrors: Partial<Record<AccessFieldName, string>> = {}
        const normalizedHost = accessForm.host.trim().toLowerCase()
        const normalizedUsername = accessForm.username.trim().toLowerCase()

        if (!accessForm.host.trim()) {
            nextErrors.host = copy.hostRequired
            setAccessErrors(nextErrors)
            focusAccessField('host')
            showFeedback('error', copy.hostRequired)
            return false
        }

        if (!accessForm.username.trim()) {
            nextErrors.username = copy.usernameRequired
            setAccessErrors(nextErrors)
            focusAccessField('username')
            showFeedback('error', copy.usernameRequired)
            return false
        }

        if (
            accessForm.remember
            && savedProfiles.some(
                (profile) => profile.profile_id !== accessForm.profileId
                    && profile.host.trim().toLowerCase() === normalizedHost
                    && profile.username.trim().toLowerCase() === normalizedUsername,
            )
        ) {
            nextErrors.username = copy.duplicateUsername
            setAccessErrors(nextErrors)
            focusAccessField('username')
            showFeedback('error', copy.duplicateUsername)
            return false
        }

        if (accessForm.authMethod === 'password' && !accessForm.password.trim() && !accessForm.hasExistingPassword) {
            nextErrors.password = copy.passwordRequired
        }

        if (accessForm.authMethod === 'key' && !accessForm.privateKey.trim() && !accessForm.hasExistingKey) {
            nextErrors.privateKey = copy.privateKeyRequired
        }

        const parsedPort = Number(accessForm.port)
        if (!Number.isInteger(parsedPort) || parsedPort < 1 || parsedPort > 65535) {
            nextErrors.port = copy.portInvalid
        }

        setAccessErrors(nextErrors)
        const firstErrorField = (['host', 'username', 'password', 'privateKey', 'port'] as AccessFieldName[]).find((field) => nextErrors[field])
        if (firstErrorField) {
            focusAccessField(firstErrorField)
            showFeedback('error', nextErrors[firstErrorField] || copy.accessValidationTitle)
            return false
        }
        return true
    }

    function applyProfileResponse(response: HostAccessProfileResponse, fallbackAccess?: AccessForm, options?: { autoConnect?: boolean; appendSession?: boolean }) {
        const autoConnect = options?.autoConnect ?? true
        const appendSession = options?.appendSession ?? false
        setSavedProfiles(response.saved_profiles ?? [])
        setBrowserDisplayMode(response.file_preferences?.view_mode ?? DEFAULT_HOST_ACCESS_FILE_PREFERENCES.view_mode)
        setShowHiddenFiles(response.file_preferences?.show_hidden_files ?? DEFAULT_HOST_ACCESS_FILE_PREFERENCES.show_hidden_files)

        if (response.configured && response.username) {
            const nextAccess = fallbackAccess
                ? {
                    ...fallbackAccess,
                    host: response.host || fallbackAccess.host,
                    username: response.username,
                    workingDirectory: response.working_directory || fallbackAccess.workingDirectory,
                    shell: response.shell || fallbackAccess.shell,
                }
                : profileToAccessForm(response)
            setAccessForm(nextAccess)

            if (!autoConnect) {
                const nextProfileScope = buildWorkspaceProfileScope(status?.current_user?.id, response.active_profile_id, response.host, response.username, response.port)
                const fallbackPath = normalizeDirectory(response.working_directory || resolveDefaultDirectory(nextAccess.username, nextAccess.workingDirectory))
                const persistedWorkspace = loadPersistedTerminalWorkspace()
                if (persistedWorkspace?.accessReady && (
                    persistedWorkspace.profileScope === nextProfileScope ||
                    persistedWorkspace.sessions.length > 1
                )) {
                    const restoredSessions = persistedWorkspace.sessions.map((session) => ({
                        ...session,
                        title: session.title || buildSessionBaseTitle({ host: session.host, username: session.user }),
                        user: session.user || nextAccess.username,
                        cwd: normalizeDirectory(session.cwd || fallbackPath),
                        status: 'idle' as SessionStatus,
                        buffer: '',
                    }))
                    const restoredActiveSessionId = restoredSessions.some((session) => session.id === persistedWorkspace.activeSessionId)
                        ? persistedWorkspace.activeSessionId
                        : restoredSessions.at(-1)?.id ?? null
                    setSessions(restoredSessions)
                    setActiveSessionId(restoredActiveSessionId)
                    setActiveProfileId(response.active_profile_id ?? null)
                    setBrowserPath(normalizeDirectory(persistedWorkspace.browserPath || fallbackPath))
                    setSelectedEntryPath(persistedWorkspace.selectedEntryPath ?? null)
                    setBrowserHistory([normalizeDirectory(persistedWorkspace.browserPath || fallbackPath)])
                    setBrowserHistoryIndex(0)
                    setEditorPath(null)
                    setEditorContent('')
                    setEditorInitialContent('')
                    setBrowserMetadata(null)
                    setCurrentProfileScope(persistedWorkspace.profileScope || null)
                    setAccessReady(true)
                    setWorkspaceView(persistedWorkspace.workspaceView === 'files' ? 'files' : 'terminal')
                    return
                }
                if (persistedWorkspace?.accessReady) {
                    clearPersistedTerminalWorkspace()
                }
                setAccessReady(false)
                setActiveProfileId(null)
                setCurrentProfileScope(null)
                setSessions([])
                setActiveSessionId(null)
                setBrowserEntries([])
                setSelectedEntryPath(null)
                setBrowserMetadata(null)
                setBrowserPath('/')
                setBrowserHistory(['/'])
                setBrowserHistoryIndex(0)
                setPathInputValue('/')
                setDirectorySearch('')
                setPathSuggestions([])
                setEditorPath(null)
                setEditorContent('')
                setEditorInitialContent('')
                return
            }

            setActiveProfileId(response.active_profile_id ?? null)
            const nextProfileScope = buildWorkspaceProfileScope(status?.current_user?.id, response.active_profile_id, response.host, response.username, response.port)
            setCurrentProfileScope(nextProfileScope)

            const fallbackPath = normalizeDirectory(response.working_directory || resolveDefaultDirectory(nextAccess.username, nextAccess.workingDirectory))

            if (appendSession && sessions.length > 0) {
                if (sessions.length >= MAX_TERMINAL_SESSIONS) {
                    showFeedback('error', copy.sessionLimitReached)
                    return
                }

                const nextSession = createSession(nextAccess, sessions, locale)
                setSessions((current) => [...current, nextSession])
                setActiveSessionId(nextSession.id)
                setAccessReady(true)
                setWorkspaceView('terminal')
                setSelectedEntryPath(null)
                setBrowserMetadata(null)
                setEditorPath(null)
                setEditorContent('')
                setEditorInitialContent('')
                return
            }

            const persistedWorkspace = loadPersistedTerminalWorkspace()
            if (persistedWorkspace?.accessReady && (
                persistedWorkspace.profileScope === nextProfileScope ||
                persistedWorkspace.sessions.length > 1
            )) {
                const restoredSessions = persistedWorkspace.sessions.map((session) => ({
                    ...session,
                    title: session.title || buildSessionBaseTitle({ host: session.host, username: session.user }),
                    user: session.user || nextAccess.username,
                    cwd: normalizeDirectory(session.cwd || fallbackPath),
                    status: 'idle' as SessionStatus,
                    buffer: '',
                }))
                const restoredActiveSessionId = restoredSessions.some((session) => session.id === persistedWorkspace.activeSessionId)
                    ? persistedWorkspace.activeSessionId
                    : restoredSessions.at(-1)?.id ?? null
                setSessions(restoredSessions)
                setActiveSessionId(restoredActiveSessionId)
                setBrowserPath(normalizeDirectory(persistedWorkspace.browserPath || fallbackPath))
                setSelectedEntryPath(persistedWorkspace.selectedEntryPath ?? null)
                setBrowserHistory([normalizeDirectory(persistedWorkspace.browserPath || fallbackPath)])
                setBrowserHistoryIndex(0)
                setEditorPath(null)
                setEditorContent('')
                setEditorInitialContent('')
                setBrowserMetadata(null)
                setCurrentProfileScope(persistedWorkspace.profileScope || null)
                setAccessReady(true)
                setWorkspaceView(persistedWorkspace.workspaceView === 'files' ? 'files' : 'terminal')
                return
            }

            if (persistedWorkspace?.accessReady) {
                clearPersistedTerminalWorkspace()
            }

            const nextSession = createSession(nextAccess, [], locale)
            setSessions([nextSession])
            setActiveSessionId(nextSession.id)
            setBrowserPath(fallbackPath)
            setBrowserHistory([fallbackPath])
            setBrowserHistoryIndex(0)
            setSelectedEntryPath(null)
            setBrowserMetadata(null)
            setEditorPath(null)
            setEditorContent('')
            setEditorInitialContent('')
            setAccessReady(true)
            setWorkspaceView('terminal')
            return
        }

        setAccessReady(false)
        setActiveProfileId(null)
        setCurrentProfileScope(null)
        setSessions([])
        setActiveSessionId(null)
        setBrowserEntries([])
        setSelectedEntryPath(null)
        setBrowserMetadata(null)
        setBrowserPath('/')
        setBrowserHistory(['/'])
        setBrowserHistoryIndex(0)
        setPathInputValue('/')
        setDirectorySearch('')
        setPathSuggestions([])
        setEditorPath(null)
        setEditorContent('')
        setEditorInitialContent('')
        resetAccessForm(response.host || DEFAULT_ACCESS_FORM.host)
        clearPersistedTerminalWorkspace()
    }

    function closeSocket(sessionId: string, options?: { terminate?: boolean; mode?: 'detach' | 'terminate' | 'remote' }) {
        const socket = sessionSocketRef.current[sessionId]
        if (socket) {
            sessionSocketCloseModeRef.current[sessionId] = options?.mode ?? (options?.terminate ? 'terminate' : 'remote')
            if (options?.terminate && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ type: 'terminate' }))
            }
            socket.close()
            delete sessionSocketRef.current[sessionId]
        }
    }

    function closeAllSockets(options?: { terminate?: boolean; mode?: 'detach' | 'terminate' | 'remote' }) {
        Object.keys(sessionSocketRef.current).forEach((sessionId) => {
            closeSocket(sessionId, options)
        })
    }

    function updateSession(sessionId: string, updater: (session: TerminalSession) => TerminalSession) {
        setSessions((current) => current.map((session) => (session.id === sessionId ? updater(session) : session)))
    }

    function appendSessionBuffer(sessionId: string, chunk: string) {
        updateSession(sessionId, (session) => ({ ...session, buffer: `${session.buffer}${chunk}` }))
    }

    function sendSessionPayload(sessionId: string, payload: Record<string, unknown>) {
        const socket = sessionSocketRef.current[sessionId]
        if (socket?.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(payload))
        }
    }

    function sendActiveResize() {
        const terminal = xtermRef.current
        const session = activeSessionRef.current
        if (!terminal || !session) {
            return
        }
        sendSessionPayload(session.id, { type: 'resize', cols: terminal.cols, rows: terminal.rows })
    }

    function connectSession(sessionId: string) {
        if (typeof window === 'undefined' || sessionSocketRef.current[sessionId]) {
            return
        }

        const socket = new WebSocket(buildTerminalSocketUrl(sessionId))
        let receivedReady = false
        let handledError = false
        sessionSocketRef.current[sessionId] = socket
        updateSession(sessionId, (session) => ({ ...session, status: 'idle' }))

        socket.onopen = () => {
            sendActiveResize()
        }

        socket.onmessage = (event) => {
            let message: TerminalSocketMessage
            const fallbackMessage = String(event.data ?? '')
            try {
                message = JSON.parse(event.data) as TerminalSocketMessage
            } catch {
                appendSessionBuffer(sessionId, fallbackMessage)
                return
            }

            if (message.type === 'ready') {
                receivedReady = true
                updateSession(sessionId, (session) => ({
                    ...session,
                    status: 'connected',
                    cwd: normalizeDirectory(message.cwd || session.cwd),
                    user: message.username || session.user,
                }))
                return
            }

            if (message.type === 'output') {
                appendSessionBuffer(sessionId, message.data || '')
                return
            }

            if (message.type === 'error') {
                handledError = true
                showFeedback('error', `${copy.terminalErrorTitle}: ${message.details || message.message || copy.terminalErrorTitle}`)
                updateSession(sessionId, (session) => ({
                    ...session,
                    status: 'ended',
                    buffer: `${session.buffer}\r\n${message.details || message.message || copy.terminalErrorTitle}\r\n`,
                }))
                closeSocket(sessionId, { mode: 'remote' })
                return
            }

            if (message.type === 'closed') {
                updateSession(sessionId, (session) => ({ ...session, status: 'ended' }))
                closeSocket(sessionId, { mode: 'remote' })
            }
        }

        socket.onerror = () => { }

        socket.onclose = () => {
            const closeMode = sessionSocketCloseModeRef.current[sessionId] ?? 'remote'
            delete sessionSocketCloseModeRef.current[sessionId]

            if (closeMode !== 'remote') {
                delete sessionSocketRef.current[sessionId]
                return
            }

            if (!receivedReady && !handledError) {
                showFeedback('error', copy.terminalErrorTitle)
            }
            updateSession(sessionId, (session) => ({
                ...session,
                status: session.status === 'connected' || !receivedReady ? 'ended' : session.status,
            }))
            delete sessionSocketRef.current[sessionId]
        }
    }

    useEffect(() => {
        let cancelled = false

        async function bootstrapProfile() {
            if (!status?.enabled) {
                setAccessBootstrapped(true)
                return
            }
            try {
                const profile = await requestJson<HostAccessProfileResponse>('/api/host-access/profile', { method: 'GET' })
                if (cancelled) {
                    return
                }
                applyProfileResponse(profile, undefined, { autoConnect: false })
            } catch (error) {
                if (!cancelled) {
                    showFeedback('error', `${copy.accessErrorTitle}: ${error instanceof Error ? error.message : copy.accessErrorTitle}`)
                }
            } finally {
                if (!cancelled) {
                    setAccessBootstrapped(true)
                }
            }
        }

        void bootstrapProfile()
        return () => {
            cancelled = true
            closeAllSockets({ mode: 'detach' })
        }
    }, [status?.enabled])

    useEffect(() => {
        sessions.forEach((session) => {
            if (session.status !== 'ended' && !sessionSocketRef.current[session.id] && accessReady) {
                connectSession(session.id)
            }
        })
    }, [sessions, accessReady])

    useEffect(() => {
        if (!activeSession) {
            invalidateFileBrowserRequests()
            setBrowserEntries([])
            setPathSuggestions([])
            setBrowserLoading(false)
            setIsEditorLoading(false)
            return
        }
        invalidateFileBrowserRequests()
        const nextPath = normalizeDirectory(activeSession.cwd)
        setBrowserPath(nextPath)
        setBrowserHistory([nextPath])
        setBrowserHistoryIndex(0)
        setBrowserEntries([])
        setSelectedEntryPath(null)
        setBrowserMetadata(null)
        setPathSuggestions([])
        setBrowserContextMenu(null)
        setBrowserDialogState(null)
        setBrowserDialogName('')
        setBrowserPropertiesForm(null)
        setBrowserClipboard(null)
        setBrowserLoading(true)
        setIsEditorLoading(false)
        setEditorPath(null)
        setEditorContent('')
        setEditorInitialContent('')
    }, [activeSession?.cwd, activeSession?.id])

    useEffect(() => {
        if (!accessBootstrapped || !status?.enabled || !status?.authenticated) {
            return
        }

        const timeoutId = window.setTimeout(() => {
            void requestJson<HostAccessFilePreferences>('/api/host-access/preferences', {
                method: 'PUT',
                body: JSON.stringify({
                    view_mode: browserDisplayMode,
                    show_hidden_files: showHiddenFiles,
                }),
            }).catch(() => undefined)
        }, 180)

        return () => {
            window.clearTimeout(timeoutId)
        }
    }, [accessBootstrapped, browserDisplayMode, showHiddenFiles, status?.authenticated, status?.enabled])

    useEffect(() => {
        setPathInputValue(browserPath)
    }, [browserPath])

    useEffect(() => {
        const normalizedInput = pathInputValue.trim()
        if (!normalizedInput.startsWith('/')) {
            setPathSuggestions([])
            return
        }

        if (normalizeDirectory(normalizedInput) === browserPath && !normalizedInput.endsWith('/')) {
            setPathSuggestions([])
            return
        }

        const normalizedPath = normalizeDirectory(normalizedInput)
        const lastSlashIndex = normalizedPath.lastIndexOf('/')
        const parentPath = normalizedInput.endsWith('/') || normalizedPath === '/'
            ? normalizedPath
            : normalizedPath.slice(0, lastSlashIndex) || '/'
        const partialName = normalizedInput.endsWith('/') || normalizedPath === '/'
            ? ''
            : normalizedPath.slice(lastSlashIndex + 1).toLowerCase()

        let cancelled = false
        const requestSessionId = activeSessionRef.current?.id ?? null
        const requestProfileId = activeSessionRef.current?.profileId ?? null
        const timeoutId = window.setTimeout(() => {
            void (async () => {
                try {
                    const suggestionEntries = normalizeDirectory(parentPath) === browserPath
                        ? browserEntries
                        : (await requestJson<HostAccessDirectoryResponse>(buildFileApiUrl('/api/host-access/files/tree', { path: parentPath }), { method: 'GET' })).items

                    const currentSession = activeSessionRef.current
                    if (cancelled || currentSession?.id !== requestSessionId || currentSession?.profileId !== requestProfileId) {
                        return
                    }

                    setPathSuggestions(
                        suggestionEntries
                            .filter((entry) => entry.item_type === 'directory')
                            .filter((entry) => !partialName || entry.name.toLowerCase().includes(partialName))
                            .map((entry) => entry.path)
                            .slice(0, 12),
                    )
                } catch {
                    const currentSession = activeSessionRef.current
                    if (!cancelled && currentSession?.id === requestSessionId && currentSession?.profileId === requestProfileId) {
                        setPathSuggestions([])
                    }
                }
            })()
        }, 160)

        return () => {
            cancelled = true
            window.clearTimeout(timeoutId)
        }
    }, [activeFileProfileId, activeSession?.id, browserEntries, browserPath, pathInputValue])

    useEffect(() => {
        const handleFullscreenChange = () => {
            const isNativeFullscreen = document.fullscreenElement === terminalShellRef.current
            if (!isNativeFullscreen && isTerminalOverlayFullscreen) {
                setIsTerminalOverlayFullscreen(false)
            }
            setIsTerminalFullscreen(isNativeFullscreen)
        }

        document.addEventListener('fullscreenchange', handleFullscreenChange)
        return () => {
            document.removeEventListener('fullscreenchange', handleFullscreenChange)
        }
    }, [isTerminalOverlayFullscreen])

    useEffect(() => {
        if (!isTerminalOverlayFullscreen) {
            return
        }
        const handleEscape = (event: KeyboardEvent) => {
            if (event.key !== 'Escape') {
                return
            }
            setIsTerminalOverlayFullscreen(false)
            setIsTerminalFullscreen(false)
        }
        document.addEventListener('keydown', handleEscape)
        return () => {
            document.removeEventListener('keydown', handleEscape)
        }
    }, [isTerminalOverlayFullscreen])

    useEffect(() => {
        if (!accessReady || !activeSession) {
            return
        }
        const requestId = browserRequestIdRef.current + 1
        const requestSessionId = activeSession.id
        const requestProfileId = activeFileProfileId
        browserRequestIdRef.current = requestId
        let cancelled = false
        setBrowserLoading(true)
        void requestJson<HostAccessDirectoryResponse>(buildFileApiUrl('/api/host-access/files/tree', { path: browserPath }), { method: 'GET' })
            .then((response) => {
                const currentSession = activeSessionRef.current
                if (cancelled || browserRequestIdRef.current !== requestId || currentSession?.id !== requestSessionId || currentSession?.profileId !== requestProfileId) {
                    return
                }
                setBrowserEntries(response.items)
                setBrowserMetadata(response.metadata)
                if (response.current_path !== browserPath) {
                    setBrowserPath(response.current_path)
                }
                setSelectedEntryPath((current) => (current && response.items.some((entry) => entry.path === current) ? current : null))
                if (editorPath && !response.items.some((entry) => entry.path === editorPath)) {
                    setEditorPath(null)
                    setEditorContent('')
                    setEditorInitialContent('')
                }
            })
            .catch((error) => {
                const currentSession = activeSessionRef.current
                if (!cancelled && browserRequestIdRef.current === requestId && currentSession?.id === requestSessionId && currentSession?.profileId === requestProfileId) {
                    showFeedback('error', `${copy.browserErrorTitle}: ${error instanceof Error ? error.message : copy.browserErrorTitle}`)
                    setBrowserEntries([])
                    setBrowserMetadata(null)
                }
            })
            .finally(() => {
                const currentSession = activeSessionRef.current
                if (!cancelled && browserRequestIdRef.current === requestId && currentSession?.id === requestSessionId && currentSession?.profileId === requestProfileId) {
                    setBrowserLoading(false)
                }
            })

        return () => {
            cancelled = true
        }
    }, [accessReady, activeSession?.id, activeFileProfileId, browserPath, browserRefreshNonce, editorPath, copy.browserErrorTitle])

    useEffect(() => {
        if (!activeSession) {
            return
        }
        setSelectedEntryPath(null)
        setBrowserMetadata(null)
        clearEditorState()
    }, [activeSession?.id])

    useEffect(() => {
        if (!accessReady || workspaceView === 'files' || !activeSession || !terminalHostRef.current) {
            xtermRef.current?.dispose()
            xtermRef.current = null
            fitAddonRef.current = null
            return
        }

        if (xtermRef.current) {
            return
        }

        const terminal = new XTerm({
            allowProposedApi: true,
            cursorBlink: true,
            convertEol: false,
            fontFamily: 'SFMono-Regular, Consolas, Liberation Mono, Menlo, monospace',
            fontSize: 13,
            lineHeight: 1.45,
            theme: xtermTheme,
        })
        const fitAddon = new FitAddon()
        terminal.loadAddon(fitAddon)
        const clipboardAddon = new ClipboardAddon()
        terminal.loadAddon(clipboardAddon)
        terminal.open(terminalHostRef.current)
        fitAddon.fit()
        terminal.onData((data) => {
            const session = activeSessionRef.current
            if (!session || session.status !== 'connected') {
                return
            }
            sendSessionPayload(session.id, { type: 'input', data })
        })

        terminal.attachCustomKeyEventHandler((event) => {
            if (event.ctrlKey && event.shiftKey && (event.key === 'C' || event.key === 'c')) {
                return true
            }
            if (event.ctrlKey && event.shiftKey && (event.key === 'V' || event.key === 'v')) {
                return true
            }
            if (event.ctrlKey && event.key === 'c' && terminal.hasSelection()) {
                document.execCommand('copy')
                return false
            }
            return true
        })

        const observer = new ResizeObserver(() => {
            fitAddon.fit()
            sendActiveResize()
        })
        observer.observe(terminalHostRef.current.parentElement ?? terminalHostRef.current)

        xtermRef.current = terminal
        fitAddonRef.current = fitAddon

        return () => {
            observer.disconnect()
            terminal.dispose()
            xtermRef.current = null
            fitAddonRef.current = null
        }
    }, [accessReady, workspaceView, activeSession?.id, xtermTheme])

    useEffect(() => {
        const terminal = xtermRef.current
        if (!terminal) {
            return
        }

        terminal.options.theme = xtermTheme
        fitAddonRef.current?.fit()
        terminal.refresh(0, Math.max(terminal.rows - 1, 0))
    }, [xtermTheme])

    useEffect(() => {
        const terminal = xtermRef.current
        if (!terminal) {
            return
        }

        if (workspaceView === 'files') {
            return
        }

        if (!activeSession) {
            terminal.clear()
            terminal.reset()
            terminal.writeln(copy.sessionEmpty)
            fitAddonRef.current?.fit()
            return
        }

        const alreadyWritten = terminalWrittenRef.current[activeSession.id] ?? 0
        const sessionChanged = lastRenderedSessionIdRef.current !== activeSession.id
        if (sessionChanged || alreadyWritten === 0 || alreadyWritten > activeSession.buffer.length) {
            // New session, tab switch, or buffer reset – clear and replay full buffer
            terminal.clear()
            terminal.reset()
            if (activeSession.buffer) {
                terminal.write(activeSession.buffer)
            }
            terminalWrittenRef.current[activeSession.id] = activeSession.buffer.length
            lastRenderedSessionIdRef.current = activeSession.id
        } else {
            // Incremental write only – do NOT clear the terminal
            const newContent = activeSession.buffer.slice(alreadyWritten)
            if (newContent) {
                terminal.write(newContent)
                terminalWrittenRef.current[activeSession.id] = activeSession.buffer.length
            }
            lastRenderedSessionIdRef.current = activeSession.id
        }
        terminal.scrollToBottom()
    }, [activeSession?.buffer, activeSession?.id, copy.sessionEmpty, workspaceView])

    useEffect(() => {
        if (workspaceView === 'files') {
            return
        }
        const timer = window.setTimeout(() => {
            const terminal = xtermRef.current
            fitAddonRef.current?.fit()
            if (terminal) {
                terminal.refresh(0, Math.max(terminal.rows - 1, 0))
                terminal.focus()
            }
            sendActiveResize()
        }, 0)
        return () => {
            window.clearTimeout(timer)
        }
    }, [workspaceView, isTerminalFullscreen])

    useEffect(() => {
        if (workspaceView !== 'files') {
            return
        }

        browserInspectorBodyRef.current?.scrollTo({ top: 0 })
    }, [workspaceView, inspectorEntry?.path])

    async function handleAccessSubmit() {
        if (!validateAccessForm()) {
            return
        }
        setIsSubmittingAccess(true)
        try {
            const profile = await requestJson<HostAccessProfileResponse>('/api/host-access/profile', {
                method: 'PUT',
                body: JSON.stringify({
                    name: accessForm.name.trim(),
                    host: accessForm.host.trim(),
                    profile_id: accessForm.profileId,
                    auth_method: accessForm.authMethod,
                    username: accessForm.username,
                    port: Number(accessForm.port || 22),
                    password: accessForm.password,
                    private_key: accessForm.privateKey,
                    passphrase: accessForm.passphrase,
                    working_directory: accessForm.workingDirectory.trim(),
                    remember: accessForm.remember,
                }),
            })

            const nextAccess = {
                ...accessForm,
                workingDirectory: profile.working_directory || accessForm.workingDirectory,
                shell: profile.shell || DEFAULT_ACCESS_FORM.shell,
            }
            setIsAccessDialogOpen(false)
            setIsHostSelectorOpen(false)
            setCreateSessionAnchorEl(null)
            applyProfileResponse(profile, nextAccess, { appendSession: accessReady && sessions.length > 0 })
        } catch (error) {
            showFeedback('error', `${copy.accessErrorTitle}: ${error instanceof Error ? error.message : copy.accessErrorTitle}`)
        } finally {
            setIsSubmittingAccess(false)
        }
    }

    async function handleConnectionTest() {
        if (!validateAccessForm()) {
            return
        }
        setIsTestingConnection(true)
        try {
            const response = await requestJson<HostAccessConnectionTestResponse>('/api/host-access/profile/test', {
                method: 'POST',
                body: JSON.stringify({
                    name: accessForm.name.trim(),
                    host: accessForm.host.trim(),
                    profile_id: accessForm.profileId,
                    auth_method: accessForm.authMethod,
                    username: accessForm.username,
                    port: Number(accessForm.port || 22),
                    password: accessForm.password,
                    private_key: accessForm.privateKey,
                    passphrase: accessForm.passphrase,
                    working_directory: accessForm.workingDirectory.trim(),
                    remember: accessForm.remember,
                }),
            })
            showFeedback('success', `${copy.connectionTestSuccess}: ${response.host}:${response.port}`)
        } catch (error) {
            showFeedback('error', `${copy.connectionTestTitle}: ${error instanceof Error ? error.message : copy.accessErrorTitle}`)
        } finally {
            setIsTestingConnection(false)
        }
    }

    async function handleTestSavedProfile(profileId: string) {
        setTestingProfileId(profileId)
        try {
            const response = await requestJson<HostAccessConnectionTestResponse>(`/api/host-access/profiles/${encodeURIComponent(profileId)}/test`, { method: 'POST' })
            showFeedback('success', `${copy.connectionTestSuccess}: ${response.host}:${response.port}`)
        } catch (error) {
            showFeedback('error', `${copy.connectionTestTitle}: ${error instanceof Error ? error.message : copy.accessErrorTitle}`)
        } finally {
            setTestingProfileId(null)
        }
    }

    async function handleToggleTerminalFullscreen() {
        const shell = terminalShellRef.current as FullscreenTarget
        if (!shell) {
            return
        }
        if (isTerminalOverlayFullscreen) {
            setIsTerminalOverlayFullscreen(false)
            setIsTerminalFullscreen(false)
            if (document.fullscreenElement === shell) {
                await document.exitFullscreen().catch(() => undefined)
            }
            return
        }
        if (document.fullscreenElement === shell) {
            await document.exitFullscreen().catch(() => undefined)
            return
        }
        setIsTerminalOverlayFullscreen(true)
        setIsTerminalFullscreen(true)
        if (!document.fullscreenElement) {
            await shell.requestFullscreen?.().catch(() => undefined)
        }
    }

    function handleCloseSession(sessionId: string) {
        closeSocket(sessionId, { terminate: true })
        setIsDisconnecting(true)
        window.setTimeout(() => setIsDisconnecting(false), 800)
        setSessions((current) => {
            const closingIndex = current.findIndex((session) => session.id === sessionId)
            const next = current.filter((session) => session.id !== sessionId)
            const nextActive = activeSessionId === sessionId
                ? (next[Math.max(0, closingIndex - 1)]?.id ?? next[0]?.id ?? null)
                : activeSessionId
            if (next.length === 0) {
                setAccessReady(false)
                setActiveProfileId(null)
                setCurrentProfileScope(null)
                setBrowserEntries([])
                setSelectedEntryPath(null)
                setBrowserMetadata(null)
                setBrowserPath('/')
                setBrowserHistory(['/'])
                setBrowserHistoryIndex(0)
                setPathInputValue('/')
                setPathSuggestions([])
                setDirectorySearch('')
                clearEditorState()
                setWorkspaceView('terminal')
                clearPersistedTerminalWorkspace()
            }
            setActiveSessionId(nextActive)
            return next
        })
    }

    async function ensureMinimumBusyDuration(startedAt: number, minimumDurationMs = 900) {
        const remainingMs = minimumDurationMs - (Date.now() - startedAt)
        if (remainingMs > 0) {
            await new Promise((resolve) => window.setTimeout(resolve, remainingMs))
        }
    }

    async function handleLogout() {
        if (!activeSession) {
            return
        }
        handleCloseSession(activeSession.id)
    }

    async function handleActivateSavedProfile(profileId: string) {
        const startedAt = Date.now()
        setActivatingProfileId(profileId)
        try {
            setIsAccessDialogOpen(false)
            setIsHostSelectorOpen(false)
            setCreateSessionAnchorEl(null)
            const response = await requestJson<HostAccessProfileResponse>(`/api/host-access/profiles/${encodeURIComponent(profileId)}/activate`, { method: 'POST' })
            await ensureMinimumBusyDuration(startedAt)
            applyProfileResponse(response, undefined, { appendSession: accessReady && sessions.length > 0 })
        } catch (error) {
            await ensureMinimumBusyDuration(startedAt)
            showFeedback('error', `${copy.accessErrorTitle}: ${error instanceof Error ? error.message : copy.accessErrorTitle}`)
        } finally {
            setActivatingProfileId(null)
        }
    }

    async function handleDeleteSavedProfile(profileId: string) {
        try {
            const response = await requestJson<HostAccessProfileResponse>(`/api/host-access/profiles/${encodeURIComponent(profileId)}`, { method: 'DELETE' })
            setSavedProfiles(response.saved_profiles ?? [])
            setActiveProfileId(response.active_profile_id ?? null)
            setCurrentProfileScope(
                response.configured && response.username
                    ? buildWorkspaceProfileScope(status?.current_user?.id, response.active_profile_id, response.host, response.username, response.port)
                    : null,
            )
            showFeedback('success', copy.profileDeleted)
        } catch (error) {
            showFeedback('error', `${copy.accessErrorTitle}: ${error instanceof Error ? error.message : copy.accessErrorTitle}`)
        }
    }

    async function handleConfirmDeleteProfile() {
        if (!pendingDeleteProfile) {
            return
        }
        const profileId = pendingDeleteProfile.profile_id
        setPendingDeleteProfile(null)
        await handleDeleteSavedProfile(profileId)
    }

    function handleCreateSession(event: ReactMouseEvent<HTMLButtonElement>) {
        if (createSessionAnchorEl === event.currentTarget) {
            closeCreateSessionMenu()
            return
        }
        openCreateSessionMenu(event.currentTarget)
    }

    function handleReconnect() {
        if (!activeSession) {
            return
        }
        closeSocket(activeSession.id, { terminate: true })
        updateSession(activeSession.id, (session) => ({
            ...session,
            status: 'idle',
            buffer: `${session.buffer}\r\n# reconnect requested\r\n`,
        }))
    }

    function clearEditorState() {
        setEditorPath(null)
        setEditorContent('')
        setEditorInitialContent('')
    }

    function closeBrowserContextMenu() {
        setBrowserContextMenu(null)
    }

    function openBrowserContextMenu(event: ReactMouseEvent<HTMLElement>, item: HostAccessFileItem | null) {
        event.preventDefault()
        event.stopPropagation()
        setSelectedEntryPath(item?.path ?? null)
        setBrowserContextMenu({
            mouseX: event.clientX + 2,
            mouseY: event.clientY - 6,
            item,
        })
    }

    function resolveContextTargetDirectory(item: HostAccessFileItem | null): string {
        if (item?.item_type === 'directory') {
            return item.path
        }
        return browserPath
    }

    function handleShowInspectorProperties() {
        if (!canShowInspectorProperties) {
            return
        }
        if (activeBrowserEntry) {
            openBrowserActionDialog({ type: 'properties', item: activeBrowserEntry })
        }
    }

    function navigateBrowser(nextPath: string, options?: { recordHistory?: boolean }) {
        const normalizedPath = normalizeDirectory(nextPath)
        setBrowserPath(normalizedPath)
        setSelectedEntryPath(null)
        clearEditorState()

        if (options?.recordHistory === false) {
            return
        }

        setBrowserHistory((previous) => {
            const current = previous[browserHistoryIndex] ?? browserPath
            if (current === normalizedPath) {
                return previous
            }
            const nextHistory = previous.slice(0, browserHistoryIndex + 1)
            nextHistory.push(normalizedPath)
            setBrowserHistoryIndex(nextHistory.length - 1)
            return nextHistory
        })
    }

    async function openBrowserFile(path: string) {
        const requestId = fileContentRequestIdRef.current + 1
        const requestSessionId = activeSessionRef.current?.id ?? null
        const requestProfileId = activeSessionRef.current?.profileId ?? null
        fileContentRequestIdRef.current = requestId
        setIsEditorLoading(true)
        try {
            const response = await requestJson<HostAccessTextFileResponse>(buildFileApiUrl('/api/host-access/files/content', { path }), { method: 'GET' })
            const currentSession = activeSessionRef.current
            if (fileContentRequestIdRef.current !== requestId || currentSession?.id !== requestSessionId || currentSession?.profileId !== requestProfileId) {
                return
            }
            setEditorPath(response.path)
            setEditorContent(response.content)
            setEditorInitialContent(response.content)
        } catch (error) {
            const currentSession = activeSessionRef.current
            if (fileContentRequestIdRef.current === requestId && currentSession?.id === requestSessionId && currentSession?.profileId === requestProfileId) {
                clearEditorState()
                showFeedback('error', `${copy.browserErrorTitle}: ${error instanceof Error ? error.message : copy.browserErrorTitle}`)
            }
        } finally {
            const currentSession = activeSessionRef.current
            if (fileContentRequestIdRef.current === requestId && currentSession?.id === requestSessionId && currentSession?.profileId === requestProfileId) {
                setIsEditorLoading(false)
            }
        }
    }

    function handleBrowseEntry(entry: HostAccessFileItem) {
        setSelectedEntryPath(entry.path)
    }

    function handleBrowserBackgroundClick(event: ReactMouseEvent<HTMLElement>, itemSelector: string) {
        const target = event.target
        if (!(target instanceof HTMLElement)) {
            return
        }

        if (!target.closest(itemSelector)) {
            setSelectedEntryPath(null)
        }
    }

    function handleBrowserBackgroundContextMenu(event: ReactMouseEvent<HTMLElement>, itemSelector: string) {
        if (editorPath) {
            return
        }
        const target = event.target
        if (!(target instanceof HTMLElement)) {
            return
        }

        if (!target.closest(itemSelector)) {
            openBrowserContextMenu(event, null)
        }
    }

    function handleBrowseEntryOpen(entry: HostAccessFileItem) {
        if (entry.item_type === 'directory') {
            navigateBrowser(entry.path)
            return
        }

        if (!entry.text_editable) {
            showFeedback('info', copy.filePreviewEmpty)
            return
        }

        void openBrowserFile(entry.path)
    }

    function handleToggleBrowserDisplayMode() {
        setBrowserDisplayMode((current) => (current === 'list' ? 'grid' : 'list'))
    }

    function handleToggleHiddenFiles() {
        setShowHiddenFiles((current) => !current)
    }

    function handlePathInputChange(nextValue: string) {
        setPathInputValue(nextValue)
        const normalizedCandidate = nextValue.trim()
        if (!normalizedCandidate.startsWith('/')) {
            return
        }

        const nextPath = normalizeDirectory(normalizedCandidate)
        if (nextPath === browserPath) {
            return
        }

        if (pathSuggestions.includes(nextPath)) {
            navigateBrowser(nextPath)
        }
    }

    function handleNavigateBack() {
        if (browserHistoryIndex <= 0) {
            return
        }
        const nextIndex = browserHistoryIndex - 1
        setBrowserHistoryIndex(nextIndex)
        navigateBrowser(browserHistory[nextIndex], { recordHistory: false })
    }

    function handleNavigateForward() {
        if (browserHistoryIndex >= browserHistory.length - 1) {
            return
        }
        const nextIndex = browserHistoryIndex + 1
        setBrowserHistoryIndex(nextIndex)
        navigateBrowser(browserHistory[nextIndex], { recordHistory: false })
    }

    function handleBrowseUp() {
        const nextPath = parentDirectory(browserPath)
        if (nextPath !== browserPath) {
            navigateBrowser(nextPath)
        }
    }

    function handleRefreshBrowser() {
        setBrowserRefreshNonce((current) => current + 1)
    }

    function handleApplyPathInput() {
        const normalizedPath = pathInputValue.trim()
        if (!normalizedPath.startsWith('/')) {
            setPathInputValue(browserPath)
            showFeedback('error', copy.invalidPath)
            return
        }

        const nextPath = normalizeDirectory(normalizedPath)
        if (nextPath === browserPath) {
            setPathInputValue(browserPath)
            return
        }

        navigateBrowser(nextPath)
    }

    useEffect(() => {
        if (!selectedBrowserEntry) {
            return
        }
        if (showHiddenFiles || !selectedBrowserEntry.name.startsWith('.')) {
            return
        }
        setSelectedEntryPath(null)
    }, [selectedBrowserEntry, showHiddenFiles])

    function openBrowserActionDialog(nextState: BrowserDialogState) {
        setBrowserDialogState(nextState)
        if (!nextState) {
            setBrowserDialogName('')
            setBrowserPropertiesForm(null)
            return
        }
        if (nextState.type === 'rename') {
            setBrowserDialogName(nextState.item.name)
            setBrowserPropertiesForm(null)
            return
        }
        if (nextState.type === 'properties') {
            setBrowserDialogName(nextState.item.name)
            setBrowserPropertiesForm(createPropertiesForm(nextState.item))
            return
        }
        setBrowserDialogName('')
        setBrowserPropertiesForm(null)
    }

    async function handleConfirmBrowserAction() {
        if (!browserDialogState) {
            return
        }

        if (browserDialogState.type === 'properties') {
            if (!browserPropertiesForm) {
                return
            }

            setIsFileActionSubmitting(true)
            try {
                const response = await requestJson<HostAccessAttributesMutationResponse>(buildFileApiUrl('/api/host-access/files/attributes'), {
                    method: 'PUT',
                    body: JSON.stringify({
                        source_path: browserDialogState.item.path,
                        owner: browserPropertiesForm.owner.trim(),
                        group: browserPropertiesForm.group.trim(),
                        owner_permissions: browserPropertiesForm.ownerPermissions,
                        group_permissions: browserPropertiesForm.groupPermissions,
                        other_permissions: browserPropertiesForm.otherPermissions,
                    }),
                })
                setSelectedEntryPath(response.path)
                if (editorPath === browserDialogState.item.path) {
                    setEditorPath(response.path)
                }
                setBrowserMetadata((current) => (current && current.path === response.metadata.path ? response.metadata : current))
                setBrowserDialogState(null)
                setBrowserDialogName('')
                setBrowserPropertiesForm(null)
                handleRefreshBrowser()
            } catch (error) {
                showFeedback('error', `${copy.browserErrorTitle}: ${error instanceof Error ? error.message : copy.browserErrorTitle}`)
            } finally {
                setIsFileActionSubmitting(false)
            }
            return
        }

        const trimmedName = browserDialogName.trim()
        if (browserDialogState.type !== 'delete' && !trimmedName) {
            return
        }

        const duplicateTarget = browserEntries.find((entry) => {
            if (browserDialogState.type === 'rename' && entry.path === browserDialogState.item.path) {
                return false
            }
            return entry.name.localeCompare(trimmedName, undefined, { sensitivity: 'accent' }) === 0
        })
        if ((browserDialogState.type === 'create-folder' || browserDialogState.type === 'create-file' || browserDialogState.type === 'rename') && duplicateTarget) {
            showFeedback('error', copy.nameExists)
            return
        }

        setIsFileActionSubmitting(true)
        try {
            if (browserDialogState.type === 'create-folder' || browserDialogState.type === 'create-file') {
                const endpoint = browserDialogState.type === 'create-folder' ? '/api/host-access/files/folders' : '/api/host-access/files/items'
                await requestJson<HostAccessMutationResponse>(buildFileApiUrl(endpoint), {
                    method: 'POST',
                    body: JSON.stringify({ parent_path: browserDialogState.parentPath ?? browserPath, name: trimmedName }),
                })
            }

            if (browserDialogState.type === 'rename') {
                const renamedPath = buildSiblingPath(browserDialogState.item.path, trimmedName)
                await requestJson<HostAccessMutationResponse>(buildFileApiUrl('/api/host-access/files/rename'), {
                    method: 'POST',
                    body: JSON.stringify({ source_path: browserDialogState.item.path, target_name: trimmedName }),
                })
                setSelectedEntryPath(renamedPath)
                if (editorPath === browserDialogState.item.path) {
                    setEditorPath(renamedPath)
                }
            }

            if (browserDialogState.type === 'delete') {
                await requestJson<HostAccessMutationResponse>(buildFileApiUrl('/api/host-access/files/item'), {
                    method: 'DELETE',
                    body: JSON.stringify({ path: browserDialogState.item.path }),
                })
                const deletedCurrentDirectory = browserDialogState.item.path === browserPath
                if (selectedEntryPath === browserDialogState.item.path) {
                    setSelectedEntryPath(null)
                }
                if (editorPath === browserDialogState.item.path) {
                    setEditorPath(null)
                    setEditorContent('')
                    setEditorInitialContent('')
                }
                setBrowserDialogState(null)
                setBrowserDialogName('')
                setBrowserPropertiesForm(null)
                if (deletedCurrentDirectory) {
                    navigateBrowser(parentDirectory(browserDialogState.item.path))
                    return
                }
            }

            setBrowserDialogState(null)
            setBrowserDialogName('')
            setBrowserPropertiesForm(null)
            handleRefreshBrowser()
        } catch (error) {
            showFeedback('error', `${copy.browserErrorTitle}: ${error instanceof Error ? error.message : copy.browserErrorTitle}`)
        } finally {
            setIsFileActionSubmitting(false)
        }
    }

    async function handleUploadChange(event: ChangeEvent<HTMLInputElement>) {
        const file = event.target.files?.[0]
        if (!file) {
            return
        }

        setIsFileActionSubmitting(true)
        try {
            const contentBase64 = await encodeFileToBase64(file)
            await requestJson<HostAccessMutationResponse>(buildFileApiUrl('/api/host-access/files/upload'), {
                method: 'POST',
                body: JSON.stringify({ parent_path: browserPath, file_name: file.name, content_base64: contentBase64 }),
            })
            handleRefreshBrowser()
        } catch (error) {
            showFeedback('error', `${copy.browserErrorTitle}: ${error instanceof Error ? error.message : copy.browserErrorTitle}`)
        } finally {
            event.target.value = ''
            setIsFileActionSubmitting(false)
        }
    }

    async function handleSaveEditor() {
        if (!editorPath) {
            return
        }

        setIsFileActionSubmitting(true)
        try {
            await requestJson<HostAccessMutationResponse>(buildFileApiUrl('/api/host-access/files/content'), {
                method: 'PUT',
                body: JSON.stringify({ path: editorPath, content: editorContent }),
            })
            clearEditorState()
            handleRefreshBrowser()
        } catch (error) {
            showFeedback('error', `${copy.browserErrorTitle}: ${error instanceof Error ? error.message : copy.browserErrorTitle}`)
        } finally {
            setIsFileActionSubmitting(false)
        }
    }

    async function handleDownloadBrowserItem(item: HostAccessFileItem) {
        setIsFileActionSubmitting(true)
        try {
            const response = await fetch(buildFileApiUrl('/api/host-access/files/download', { path: item.path }), {
                method: 'GET',
                credentials: 'include',
            })

            if (!response.ok) {
                let message = `HTTP ${response.status}`
                try {
                    const payload = (await response.json()) as { details?: string; message?: string }
                    message = payload.details ?? payload.message ?? message
                } catch {
                }
                throw new Error(message)
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
            showFeedback('error', `${copy.browserErrorTitle}: ${error instanceof Error ? error.message : copy.browserErrorTitle}`)
        } finally {
            setIsFileActionSubmitting(false)
        }
    }

    async function handlePasteBrowserItem(destinationPath: string) {
        if (!browserClipboard) {
            return
        }

        setIsFileActionSubmitting(true)
        try {
            await requestJson<HostAccessMutationResponse>(buildFileApiUrl(browserClipboard.mode === 'cut' ? '/api/host-access/files/move' : '/api/host-access/files/copy'), {
                method: 'POST',
                body: JSON.stringify({ source_path: browserClipboard.path, destination_path: destinationPath }),
            })
            if (browserClipboard.mode === 'cut') {
                setBrowserClipboard(null)
            }
            closeBrowserContextMenu()
            handleRefreshBrowser()
        } catch (error) {
            showFeedback('error', `${copy.browserErrorTitle}: ${error instanceof Error ? error.message : copy.browserErrorTitle}`)
        } finally {
            setIsFileActionSubmitting(false)
        }
    }

    async function handleBrowserContextAction(action: 'copy' | 'cut' | 'paste' | 'download' | 'rename' | 'delete' | 'create-folder' | 'create-file' | 'properties' | 'edit') {
        const contextItem = browserContextMenu?.item ?? null
        const contextTarget = contextItem ?? browserMetadata
        const destinationPath = resolveContextTargetDirectory(contextItem)

        if (action === 'copy' || action === 'cut') {
            if (!contextItem) {
                return
            }
            setBrowserClipboard({ path: contextItem.path, name: contextItem.name, itemType: contextItem.item_type, mode: action })
            closeBrowserContextMenu()
            return
        }

        if (action === 'paste') {
            await handlePasteBrowserItem(destinationPath)
            return
        }

        if (action === 'download') {
            if (!contextItem || contextItem.item_type !== 'file') {
                return
            }
            closeBrowserContextMenu()
            await handleDownloadBrowserItem(contextItem)
            return
        }

        if (action === 'edit') {
            if (!contextItem) {
                return
            }
            closeBrowserContextMenu()
            handleBrowseEntryOpen(contextItem)
            return
        }

        if (action === 'properties') {
            if (!contextTarget) {
                return
            }
            closeBrowserContextMenu()
            openBrowserActionDialog({ type: 'properties', item: contextTarget })
            return
        }

        if (action === 'rename') {
            if (!contextItem) {
                return
            }
            closeBrowserContextMenu()
            openBrowserActionDialog({ type: 'rename', item: contextItem })
            return
        }

        if (action === 'delete') {
            if (!contextTarget) {
                return
            }
            closeBrowserContextMenu()
            openBrowserActionDialog({ type: 'delete', item: contextTarget })
            return
        }

        closeBrowserContextMenu()
        openBrowserActionDialog({ type: action, parentPath: destinationPath })
    }

    const accessFields = (
        <div className="terminal-access-form">
            <div className="terminal-access-field" style={{ marginBottom: 0 }}>
                <Typography className="terminal-access-field-label">{copy.connectionNameLabel}</Typography>
                <TextField
                    disabled={formBusy}
                    onChange={(event) => updateAccessForm('name', event.target.value)}
                    placeholder={copy.connectionNameLabel}
                    size="small"
                    sx={terminalFieldSx}
                    value={accessForm.name}
                />
            </div>
            <div className="terminal-access-grid terminal-access-grid-top">
                <div className="terminal-access-field">
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 0.35 }}>
                        <Typography className="terminal-access-field-label" sx={{ mb: '0 !important' }}>{copy.host}</Typography>
                        {accessForm.host === localHostIp ? (
                            <Chip color="success" label={copy.localHostOption} size="small" sx={{ height: 18, fontWeight: 700, '& .MuiChip-label': { px: 0.75, fontSize: 11, lineHeight: 1.2 } }} />
                        ) : null}
                    </Box>
                    <TextField
                        disabled={formBusy}
                        error={Boolean(accessErrors.host)}
                        inputRef={(element) => {
                            accessFieldRefs.current.host = element
                        }}
                        onChange={(event) => {
                            const value = event.target.value
                            updateAccessForm('host', value)
                            setAccessForm((current) => ({ ...current, isLocal: value === localHostIp }))
                        }}
                        placeholder="example.com"
                        size="small"
                        slotProps={{
                            input: {
                                endAdornment: accessForm.host !== localHostIp ? (
                                    <InputAdornment position="end">
                                        <Tooltip title={`${copy.localHostOption}: ${localHostIp}`}>
                                            <IconButton
                                                aria-label={copy.localHostOption}
                                                disabled={formBusy}
                                                edge="end"
                                                onClick={() => setAccessForm((current) => ({ ...current, host: localHostIp, isLocal: true }))}
                                                size="small"
                                                tabIndex={-1}
                                            >
                                                <LocalHostIcon />
                                            </IconButton>
                                        </Tooltip>
                                    </InputAdornment>
                                ) : undefined,
                            },
                        }}
                        sx={terminalFieldSx}
                        value={accessForm.host}
                    />
                </div>
                <div className="terminal-access-field">
                    <Typography className="terminal-access-field-label">{copy.username}</Typography>
                    <TextField
                        disabled={formBusy}
                        error={Boolean(accessErrors.username)}
                        inputRef={(element) => {
                            accessFieldRefs.current.username = element
                        }}
                        onChange={(event) => updateAccessForm('username', event.target.value)}
                        placeholder={copy.username}
                        size="small"
                        sx={terminalFieldSx}
                        value={accessForm.username}
                    />
                </div>
            </div>

            <div className="terminal-access-grid terminal-access-grid-top">
                <div className="terminal-access-field">
                    <Typography className="terminal-access-field-label">{copy.port}</Typography>
                    <TextField
                        disabled={formBusy}
                        error={Boolean(accessErrors.port)}
                        inputRef={(element) => {
                            accessFieldRefs.current.port = element
                        }}
                        onChange={(event) => updateAccessForm('port', event.target.value)}
                        placeholder="22"
                        size="small"
                        sx={terminalFieldSx}
                        value={accessForm.port}
                    />
                </div>
                <div className="terminal-access-field">
                    <Typography className="terminal-access-field-label">{copy.authMethodLabel}</Typography>
                    <TextField
                        disabled={formBusy}
                        onChange={(event) => updateAccessForm('authMethod', event.target.value as AuthMethod)}
                        select
                        size="small"
                        slotProps={{ select: { MenuProps: selectMenuProps } }}
                        sx={terminalFieldSx}
                        value={accessForm.authMethod}
                    >
                        <MenuItem sx={terminalMenuItemSx} value="password">{copy.authPassword}</MenuItem>
                        <MenuItem sx={terminalMenuItemSx} value="key">{copy.authKey}</MenuItem>
                    </TextField>
                </div>
            </div>

            <div className="terminal-access-credential-stack">
                {accessForm.authMethod === 'password' ? (
                    <div className="terminal-access-field">
                        <Typography className="terminal-access-field-label">{copy.password}</Typography>
                        <TextField
                            disabled={formBusy}
                            error={Boolean(accessErrors.password)}
                            inputRef={(element) => {
                                accessFieldRefs.current.password = element
                            }}
                            onChange={(event) => updateAccessForm('password', event.target.value)}
                            placeholder={accessForm.hasExistingPassword && !accessForm.password ? '••••••••' : copy.password}
                            size="small"
                            slotProps={{
                                input: {
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <IconButton
                                                aria-label={passwordVisible ? copy.hidePassword : copy.showPassword}
                                                disabled={accessForm.hasExistingPassword && !accessForm.password}
                                                edge="end"
                                                onClick={() => setPasswordVisible((current) => !current)}
                                                size="small"
                                                tabIndex={-1}
                                            >
                                                {passwordVisible ? <VisibilityOffIcon /> : <VisibilityOnIcon />}
                                            </IconButton>
                                        </InputAdornment>
                                    ),
                                },
                            }}
                            sx={terminalFieldSx}
                            type={passwordVisible ? 'text' : 'password'}
                            value={accessForm.password}
                        />
                    </div>
                ) : (
                    <>
                        <div className="terminal-access-field">
                            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
                                <Typography className="terminal-access-field-label">{copy.privateKey}</Typography>
                                <>
                                    <input
                                        ref={accessPrivateKeyUploadInputRef}
                                        type="file"
                                        accept=".key,.pem,.ppk,.txt,*/*"
                                        onChange={(event) => void handlePrivateKeyFileSelected(event)}
                                        style={{ display: 'none' }}
                                    />
                                    <Button disabled={formBusy} onClick={() => accessPrivateKeyUploadInputRef.current?.click()} size="small" variant="outlined">
                                        {copy.privateKeyUploadAction}
                                    </Button>
                                </>
                            </Stack>
                            <TextField
                                disabled={formBusy}
                                error={Boolean(accessErrors.privateKey)}
                                inputRef={(element) => {
                                    accessFieldRefs.current.privateKey = element
                                }}
                                multiline
                                onChange={(event) => updateAccessForm('privateKey', event.target.value)}
                                placeholder={accessForm.hasExistingKey && !accessForm.privateKey ? copy.keepExistingKey : copy.privateKey}
                                rows={5}
                                size="small"
                                sx={terminalFieldSx}
                                value={accessForm.privateKey}
                            />
                        </div>
                        <div className="terminal-access-field terminal-access-key-passphrase-row">
                            <Typography className="terminal-access-field-label">{copy.passphrase}</Typography>
                            <TextField
                                disabled={formBusy}
                                onChange={(event) => updateAccessForm('passphrase', event.target.value)}
                                placeholder={copy.passphrase}
                                size="small"
                                sx={terminalFieldSx}
                                type="password"
                                value={accessForm.passphrase}
                            />
                        </div>
                    </>
                )}
            </div>

            <div className="terminal-access-remember-row">
                <FormControlLabel
                    control={<Checkbox checked={accessForm.remember} disabled={formBusy} onChange={(event) => updateAccessForm('remember', event.target.checked)} />}
                    label={copy.remember}
                    sx={{ m: 0, '& .MuiFormControlLabel-label': { fontSize: 13.5, color: palette.subtleText } }}
                />
            </div>
        </div>
    )

    const savedProfilesTable = (
        <Box sx={{ width: '100%', minWidth: 0, overflowX: 'hidden', border: `1px solid ${palette.border}` }}>
            <Box sx={{ width: '100%', minWidth: 0 }}>
                <Box
                    className="terminal-connections-table-head"
                    sx={{
                        display: 'grid',
                        width: '100%',
                        minWidth: 0,
                        gridTemplateColumns: 'minmax(0, 1.18fr) minmax(0, .52fr) minmax(0, .68fr) minmax(40px, .22fr) minmax(120px, .5fr)',
                        alignItems: 'center',
                        minHeight: 52,
                        px: 1,
                        gap: 0.75,
                        borderBottom: `1px solid ${palette.border}`,
                        background: isDarkMode ? alpha(palette.cardBg, 0.98) : alpha('#ffffff', 0.92),
                    }}
                >
                    {[copy.connectionNameLabel, copy.username, copy.authMethodLabel, copy.port, copy.actionsLabel].map((column, index) => (
                        <Typography
                            key={column}
                            sx={{
                                fontSize: 13,
                                fontWeight: 700,
                                color: palette.subtleText,
                                textAlign: index === 4 ? 'right' : 'left',
                            }}
                        >
                            {column}
                        </Typography>
                    ))}
                </Box>

                {isRefreshingProfiles ? (
                    Array.from({ length: 4 }).map((_, i) => (
                        <Box
                            key={i}
                            sx={{
                                display: 'grid',
                                gridTemplateColumns: 'minmax(0, 1.18fr) minmax(0, .52fr) minmax(0, .68fr) minmax(40px, .22fr) minmax(120px, .5fr)',
                                alignItems: 'center',
                                gap: 0.75,
                                px: 1,
                                py: 1.35,
                                borderBottom: `1px solid ${palette.border}`,
                            }}
                        >
                            <Stack spacing={0.5}>
                                <Skeleton variant="text" width="55%" height={18} />
                                <Skeleton variant="text" width="38%" height={14} />
                            </Stack>
                            <Skeleton variant="text" width="60%" height={18} />
                            <Skeleton variant="text" width="50%" height={18} />
                            <Skeleton variant="text" width="70%" height={18} />
                            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.5 }}>
                                <Skeleton variant="circular" width={28} height={28} />
                                <Skeleton variant="circular" width={28} height={28} />
                                <Skeleton variant="circular" width={28} height={28} />
                                <Skeleton variant="circular" width={28} height={28} />
                            </Box>
                        </Box>
                    ))
                ) : savedProfiles.length === 0 ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 180, px: 3 }}>
                        <Typography sx={{ fontSize: 16, fontWeight: 700, color: palette.text }}>{copy.savedProfilesEmpty}</Typography>
                    </Box>
                ) : filteredSavedProfiles.length === 0 ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 180, px: 3 }}>
                        <Typography sx={{ fontSize: 16, fontWeight: 700, color: palette.text }}>{copy.noSavedProfilesResults}</Typography>
                    </Box>
                ) : filteredSavedProfiles.map((profile) => (
                    <Box
                        key={profile.profile_id}
                        className="terminal-connections-table-row"
                        sx={{
                            display: 'grid',
                            width: '100%',
                            minWidth: 0,
                            gridTemplateColumns: 'minmax(0, 1.18fr) minmax(0, .52fr) minmax(0, .68fr) minmax(40px, .22fr) minmax(120px, .5fr)',
                            alignItems: 'center',
                            gap: 0.75,
                            px: 1,
                            py: 1.35,
                            borderBottom: `1px solid ${palette.border}`,
                            backgroundColor: palette.cardBg,
                            '&:hover': {
                                backgroundColor: alpha(palette.accent, isDarkMode ? 0.08 : 0.05),
                            },
                        }}
                    >
                        <Stack spacing={0.45} sx={{ minWidth: 0 }}>
                            <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                                <Typography sx={{ fontSize: 14, fontWeight: 600, color: palette.text, wordBreak: 'break-all' }}>{profile.name || profile.host}</Typography>
                                {profile.is_local ? <Chip color="success" label={copy.localLabel} size="small" sx={{ height: 18, fontWeight: 700, '& .MuiChip-label': { px: 0.75, fontSize: 11, lineHeight: 1.2 } }} /> : null}
                            </Stack>
                            {profile.name ? (
                                <Typography sx={{ fontSize: 12.5, color: palette.subtleText, wordBreak: 'break-all' }}>{profile.host}</Typography>
                            ) : null}
                        </Stack>
                        <Typography sx={{ minWidth: 0, fontSize: 13.5, color: palette.text, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{profile.username}</Typography>
                        <Typography sx={{ minWidth: 0, fontSize: 13.5, color: palette.subtleText, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{profile.auth_method === 'password' ? copy.authMethodPasswordHint : copy.authMethodKeyHint}</Typography>
                        <Typography sx={{ minWidth: 0, fontSize: 13.5, color: palette.subtleText }}>{profile.port}</Typography>
                        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                            <Box className="terminal-connections-row-actions">
                                <Tooltip title={copy.connectionTestTitle}>
                                    <span>
                                        <IconButton aria-label={copy.connectionTestTitle} className="terminal-connections-row-action-button terminal-connections-row-action-button-info" disabled={formBusy || isRefreshingProfiles || isDisconnecting || activatingProfileId !== null || testingProfileId === profile.profile_id} onClick={() => void handleTestSavedProfile(profile.profile_id)} size="small">
                                            {testingProfileId === profile.profile_id ? <CircularProgress size={14} color="inherit" /> : <TestActionIcon />}
                                        </IconButton>
                                    </span>
                                </Tooltip>
                                <Tooltip title={copy.editAction}>
                                    <span>
                                        <IconButton aria-label={copy.editAction} className="terminal-connections-row-action-button" disabled={formBusy || isRefreshingProfiles || isDisconnecting || activatingProfileId !== null} onClick={() => openEditHostDialog(profile)} size="small">
                                            <EditActionIcon />
                                        </IconButton>
                                    </span>
                                </Tooltip>
                                <Tooltip title={copy.savedLogin}>
                                    <span>
                                        <IconButton aria-label={copy.savedLogin} className="terminal-connections-row-action-button terminal-connections-row-action-button-primary" disabled={formBusy || isRefreshingProfiles || isDisconnecting || (activatingProfileId !== null && activatingProfileId !== profile.profile_id)} onClick={() => void handleActivateSavedProfile(profile.profile_id)} size="small">
                                            {activatingProfileId === profile.profile_id ? <CircularProgress size={14} color="inherit" /> : <ConnectActionIcon />}
                                        </IconButton>
                                    </span>
                                </Tooltip>
                                <Tooltip title={copy.deleteProfile}>
                                    <span>
                                        <IconButton aria-label={copy.deleteProfile} className="terminal-connections-row-action-button terminal-connections-row-action-button-danger" disabled={formBusy || isRefreshingProfiles || isDisconnecting || activatingProfileId !== null} onClick={() => setPendingDeleteProfile(profile)} size="small">
                                            <DeleteActionIcon />
                                        </IconButton>
                                    </span>
                                </Tooltip>
                            </Box>
                        </Box>
                    </Box>
                ))}
            </Box>
        </Box>
    )

    const quickConnectProfiles = filteredSavedProfiles.slice(0, 6)

    const quickConnectList = savedProfiles.length === 0 ? (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 120, px: 2 }}>
            <Typography sx={{ fontSize: 14, fontWeight: 600, color: palette.subtleText }}>{copy.savedProfilesEmpty}</Typography>
        </Box>
    ) : filteredSavedProfiles.length === 0 ? (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 120, px: 2 }}>
            <Typography sx={{ fontSize: 14, fontWeight: 600, color: palette.subtleText }}>{copy.noSavedProfilesResults}</Typography>
        </Box>
    ) : (
        <Stack spacing={1} sx={{ maxHeight: 248, overflowY: 'auto', pr: 0.5 }}>
            {quickConnectProfiles.map((profile) => (
                <Box
                    key={profile.profile_id}
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 1,
                        px: 1.25,
                        py: 1,
                        border: `1px solid ${palette.border}`,
                        borderRadius: '2px',
                        backgroundColor: palette.cardBg,
                    }}
                >
                    <Stack spacing={0.25} sx={{ minWidth: 0, flex: '1 1 auto', overflow: 'hidden' }}>
                        <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                            <Typography sx={{ fontSize: 13.5, fontWeight: 700, color: palette.text, wordBreak: 'break-all' }}>{profile.name || profile.host}</Typography>
                            {profile.is_local ? <Chip color="success" label={copy.localLabel} size="small" sx={{ height: 18, fontWeight: 700, '& .MuiChip-label': { px: 0.75, fontSize: 11, lineHeight: 1.2 } }} /> : null}
                        </Stack>
                        <Typography sx={{ fontSize: 12.5, color: palette.subtleText, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{profile.host} · {profile.username}</Typography>
                    </Stack>
                    <Button
                        disabled={formBusy || isRefreshingProfiles || isDisconnecting || (activatingProfileId !== null && activatingProfileId !== profile.profile_id)}
                        onClick={() => {
                            closeCreateSessionMenu()
                            void handleActivateSavedProfile(profile.profile_id)
                        }}
                        size="small"
                        sx={{ flex: '0 0 auto', minWidth: 68, fontWeight: 700 }}
                        variant="outlined"
                    >
                        {copy.savedLogin}
                    </Button>
                </Box>
            ))}
        </Stack>
    )

    const savedProfilesToolbar = (
        <Box className="terminal-connections-toolbar">
            <TextField
                className="terminal-connections-toolbar-field terminal-connections-toolbar-search"
                disabled={isDisconnecting || activatingProfileId !== null}
                onChange={(event) => setProfileSearchValue(event.target.value)}
                placeholder={copy.searchConnectionsPlaceholder}
                size="small"
                value={profileSearchValue}
                sx={{
                    '& .MuiOutlinedInput-root': {
                        backgroundColor: palette.cardBg,
                        '& fieldset': { borderColor: palette.border },
                        '&:hover fieldset': { borderColor: palette.border },
                        '&.Mui-focused fieldset': { borderColor: palette.accent },
                    },
                    '& .MuiInputBase-input': { color: palette.text },
                    '& .MuiInputBase-input::placeholder': { color: palette.subtleText, opacity: 1 },
                }}
            />
            <Button className="terminal-connections-toolbar-button" disabled={isDisconnecting || activatingProfileId !== null} onClick={() => openAddHostDialog('add-host')} variant="contained" sx={{ borderRadius: 0, boxShadow: 'none', textTransform: 'none', fontWeight: 600 }}>
                {copy.addHostAction}
            </Button>
            <Tooltip title={copy.refresh}>
                <span>
                    <IconButton className="terminal-connections-toolbar-icon-button" disabled={isDisconnecting || activatingProfileId !== null} onClick={() => void refreshSavedProfiles()} size="small" sx={isRefreshingProfiles ? { animation: 'spin 0.75s linear infinite', '@keyframes spin': { from: { transform: 'rotate(0deg)' }, to: { transform: 'rotate(360deg)' } } } : undefined}>
                        <RefreshActionIcon />
                    </IconButton>
                </span>
            </Tooltip>
        </Box>
    )

    return (
        <Box
            sx={{
                display: 'flex',
                flexDirection: 'column',
                flex: '1 1 auto',
                height: '100%',
                position: 'relative',
                minHeight: 0,
                mx: { xs: -1, md: -3 },
                my: { xs: -1.25, md: -2.25 },
                px: { xs: 2, md: 3 },
                pt: { xs: 2.1, md: 2.6 },
                pb: { xs: 1.25, md: 1.5 },
                backgroundColor: palette.pageBg,
                color: palette.text,
                overflowY: 'hidden',
                overflowX: 'hidden',
                '& .MuiCard-root': {
                    background: `${palette.cardBg} !important`,
                    borderColor: `${palette.border} !important`,
                    color: `${palette.text} !important`,
                    borderRadius: '2px !important',
                },
                '& .MuiPaper-root': {
                    backgroundColor: `${palette.cardBg} !important`,
                    color: `${palette.text} !important`,
                    borderRadius: '2px !important',
                },
                '& .MuiButton-root': {
                    borderRadius: '2px',
                    textTransform: 'none',
                    boxShadow: 'none',
                },
                '& .MuiOutlinedInput-root': {
                    backgroundColor: `${palette.cardBg} !important`,
                },
                '& .MuiChip-root': {
                    borderRadius: '2px !important',
                },
            }}
        >
            <Stack spacing={0.75} useFlexGap sx={{ width: '100%', height: '100%', minHeight: 0, pb: 0 }}>
                {!status?.enabled ? <Alert severity="info">{copy.noAuthAlert}</Alert> : null}

                <PageDescriptionHeader
                    title={t('nav.terminal.label')}
                    description={copy.description}
                    titleColor={palette.text}
                    descriptionColor={palette.subtleText}
                    sx={{ mt: { xs: 0.25, md: 0.45 } }}
                    actions={
                        status?.enabled ? (
                            <Stack
                                direction="row"
                                spacing={1}
                                className="terminal-workspace-header-actions"
                                sx={{
                                    width: '100%',
                                    flexWrap: 'wrap',
                                    alignItems: 'center',
                                    justifyContent: 'flex-end',
                                }}
                            >
                                <div className="terminal-view-nav" role="tablist" aria-label="workspace view selector">
                                    {([
                                        ['terminal', copy.viewTerminal],
                                        ['files', copy.viewFiles],
                                    ] as Array<[WorkspaceView, string]>).map(([view, label]) => {
                                        const disabled = view === 'files' ? !filesViewEnabled : !accessReady
                                        return (
                                            <button
                                                key={view}
                                                className={`terminal-view-nav-button ${workspaceView === view ? 'terminal-view-nav-button-active' : ''}`}
                                                disabled={disabled}
                                                onClick={() => {
                                                    if (disabled) {
                                                        return
                                                    }
                                                    setWorkspaceView(view)
                                                }}
                                                type="button"
                                            >
                                                {label}
                                            </button>
                                        )
                                    })}
                                </div>
                                <Button className="terminal-workspace-host-button" disabled={isDisconnecting} onClick={openHostSelector} variant="contained">
                                    {copy.hostSelectorTitle}
                                </Button>
                            </Stack>
                        ) : null
                    }
                />

                {!accessBootstrapped ? null : !accessReady ? (
                    <Card
                        elevation={0}
                        sx={{
                            ...surfaceCardSx,
                            display: 'flex',
                            flexDirection: 'column',
                            flex: '1 1 auto',
                            minHeight: 0,
                        }}
                    >
                        <CardContent sx={{ p: 0, display: 'flex', flex: '1 1 auto', minHeight: 0, width: '100%', '&:last-child': { pb: 0 } }}>
                            <div className="terminal-workspace-shell" ref={terminalWorkspaceShellRef}>
                                <div className="terminal-workspace-grid terminal-workspace-grid-terminal">
                                    <div className="terminal-shell-pane">
                                        <div className="terminal-session-strip">
                                            <div className="terminal-session-tabs">
                                                <button aria-label={copy.newConnectionTitle} className="terminal-session-add terminal-session-add-icon" onClick={handleCreateSession} type="button">
                                                    <span className="terminal-session-add-glyph">+</span>
                                                </button>
                                            </div>
                                        </div>

                                        <div className={`terminal-shell-surface ${isDarkMode ? '' : 'terminal-shell-surface-light'}`} style={{ background: isDarkMode ? `linear-gradient(180deg, ${alpha('#0f172a', 0.96)} 0%, ${alpha('#111827', 0.98)} 100%)` : 'linear-gradient(180deg, #f8fafc 0%, #eff4fa 100%)' }}>
                                            <div className="terminal-shell-toolbar">
                                                <div className="terminal-shell-toolbar-left">
                                                    <span className="terminal-window-dot" style={{ backgroundColor: '#fb7185' }} />
                                                    <span className="terminal-window-dot" style={{ backgroundColor: '#fbbf24' }} />
                                                    <span className="terminal-window-dot" style={{ backgroundColor: '#34d399' }} />
                                                    <span className="terminal-shell-title">{copy.emptyTerminalShellTitle}</span>
                                                </div>
                                            </div>

                                            <div className="terminal-shell-body">
                                                <div className="terminal-shell-transcript">
                                                    <div className="terminal-shell-empty terminal-shell-empty-connected-look">
                                                        <Stack spacing={1.5} sx={{ alignItems: 'center', textAlign: 'center', maxWidth: 440 }}>
                                                            <Box sx={{ width: 88, height: 88, borderRadius: '24px', display: 'grid', placeItems: 'center', color: isDarkMode ? '#cbd5e1' : '#94a3b8', background: isDarkMode ? 'rgba(148, 163, 184, 0.08)' : 'rgba(255, 255, 255, 0.72)', boxShadow: isDarkMode ? 'inset 0 0 0 1px rgba(148, 163, 184, 0.12)' : '0 18px 36px rgba(148, 163, 184, 0.18)' }}>
                                                                <EmptyTerminalIcon />
                                                            </Box>
                                                            <Typography sx={{ fontSize: 22, fontWeight: 800, color: isDarkMode ? '#e2e8f0' : '#334155' }}>
                                                                {copy.emptyTerminalTitle}
                                                            </Typography>
                                                            <Typography sx={{ fontSize: 14, lineHeight: 1.7, color: isDarkMode ? '#94a3b8' : '#64748b' }}>
                                                                {copy.emptyTerminalHint}
                                                            </Typography>
                                                        </Stack>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                ) : (
                    <Card
                        elevation={0}
                        sx={{
                            ...surfaceCardSx,
                            display: 'flex',
                            flexDirection: 'column',
                            flex: '1 1 auto',
                            minHeight: 0,
                        }}
                    >
                        <CardContent sx={{ p: 0, display: 'flex', flex: '1 1 auto', minHeight: 0, width: '100%', '&:last-child': { pb: 0 } }}>
                            <div className="terminal-workspace-shell" ref={terminalWorkspaceShellRef}>
                                <div className="terminal-workspace-grid terminal-workspace-grid-terminal">
                                    <div className="terminal-shell-pane">
                                        <div className="terminal-session-strip">
                                            <div className="terminal-session-tabs">
                                                {sessions.map((session) => {
                                                    const active = session.id === activeSession?.id
                                                    const tone = getStatusTone(session.status, palette)
                                                    return (
                                                        <div
                                                            key={session.id}
                                                            className={`terminal-session-tab ${active ? 'terminal-session-tab-active' : ''}`}
                                                            style={{
                                                                borderColor: active ? (isDarkMode ? 'rgba(96, 165, 250, 0.78)' : alpha(palette.terminalTabActive, 0.24)) : palette.border,
                                                                backgroundColor: active ? (isDarkMode ? 'rgba(37, 99, 235, 0.42)' : alpha(palette.terminalTabActive, 0.08)) : palette.terminalTab,
                                                                color: active ? (isDarkMode ? '#eff6ff' : '#1e3a8a') : palette.text,
                                                                boxShadow: active && isDarkMode ? 'inset 0 0 0 1px rgba(147, 197, 253, 0.34)' : 'none',
                                                            }}
                                                        >
                                                            <button className="terminal-session-tab-toggle" onClick={() => setActiveSessionId(session.id)} type="button">
                                                                <span className="terminal-session-tab-main">
                                                                    <span className="terminal-session-tab-title">{session.title}</span>
                                                                </span>
                                                                <span className="terminal-session-tab-status" style={{ backgroundColor: tone }} />
                                                            </button>
                                                            {active ? (
                                                                <button className="terminal-session-tab-close" onClick={() => handleCloseSession(session.id)} type="button">
                                                                    ×
                                                                </button>
                                                            ) : null}
                                                        </div>
                                                    )
                                                })}
                                                <button aria-label={copy.newConnectionTitle} className="terminal-session-add terminal-session-add-icon" onClick={handleCreateSession} type="button">
                                                    <span className="terminal-session-add-glyph">+</span>
                                                </button>
                                            </div>
                                        </div>

                                        {activeSession ? (
                                            <div className={`terminal-shell-surface ${isTerminalOverlayFullscreen ? 'terminal-shell-surface-overlay-fullscreen' : ''} ${isDarkMode ? '' : 'terminal-shell-surface-light'}`} ref={terminalShellRef} style={{ background: isDarkMode ? `linear-gradient(180deg, ${alpha(palette.terminalBg, 0.94)} 0%, ${alpha('#020617', 0.98)} 100%)` : 'linear-gradient(180deg, #f8fafc 0%, #eef3f9 100%)' }}>
                                                <div className="terminal-shell-toolbar">
                                                    <div className="terminal-shell-toolbar-left">
                                                        <span className="terminal-window-dot" style={{ backgroundColor: '#fb7185' }} />
                                                        <span className="terminal-window-dot" style={{ backgroundColor: '#fbbf24' }} />
                                                        <span className="terminal-window-dot" style={{ backgroundColor: '#34d399' }} />
                                                        <span className="terminal-shell-title">{activeSession.user}@{activeSession.host || copy.localServerTitle}</span>
                                                    </div>
                                                    <div className="terminal-shell-toolbar-right">
                                                        <Button onClick={() => void handleLogout()} size="small" variant="outlined">
                                                            {copy.disconnect}
                                                        </Button>
                                                        <Button aria-label={isTerminalFullscreen ? copy.exitFullscreen : copy.enterFullscreen} className="terminal-shell-toolbar-icon-button" onClick={() => void handleToggleTerminalFullscreen()} size="small" type="button" variant="outlined">
                                                            <span className="terminal-session-toolbar-glyph">{isTerminalFullscreen ? '⤡' : '⤢'}</span>
                                                        </Button>
                                                    </div>
                                                </div>

                                                <div className={`terminal-shell-body ${workspaceView === 'files' ? 'terminal-shell-body-files' : ''}`}>
                                                    {workspaceView === 'files' ? (
                                                        <div className="terminal-files-pane terminal-files-shell terminal-files-pane-embedded" style={{ ...terminalFilesThemeVars, borderLeftColor: palette.border }}>
                                                            <div className="terminal-files-toolbar-row">
                                                                <div className="terminal-files-toolbar-group">
                                                                    <button className="terminal-files-toolbar-button" disabled={browserHistoryIndex <= 0} onClick={handleNavigateBack} title={copy.browseBack} type="button">
                                                                        <span className="terminal-files-toolbar-glyph terminal-files-toolbar-glyph-back" />
                                                                    </button>
                                                                    <button className="terminal-files-toolbar-button" disabled={browserHistoryIndex >= browserHistory.length - 1} onClick={handleNavigateForward} title={copy.browseForward} type="button">
                                                                        <span className="terminal-files-toolbar-glyph terminal-files-toolbar-glyph-forward" />
                                                                    </button>
                                                                    <button className="terminal-files-toolbar-button" disabled={browserPath === '/'} onClick={handleBrowseUp} title={copy.browseUp} type="button">
                                                                        <span className="terminal-files-toolbar-glyph terminal-files-toolbar-glyph-up" />
                                                                    </button>
                                                                    <button className="terminal-files-toolbar-button terminal-files-toolbar-button-primary" disabled={browserLoading} onClick={handleRefreshBrowser} title={copy.refresh} type="button">
                                                                        <span className="terminal-files-toolbar-glyph terminal-files-toolbar-glyph-refresh" />
                                                                    </button>
                                                                </div>

                                                                <div className="terminal-files-toolbar-paths">
                                                                    <TextField className="terminal-files-path-input" onBlur={() => setPathInputValue(browserPath)} onChange={(event) => handlePathInputChange(event.target.value)} onKeyDown={(event) => {
                                                                        if (event.key === 'Enter') {
                                                                            event.preventDefault()
                                                                            handleApplyPathInput()
                                                                        }
                                                                    }} placeholder={copy.pathPlaceholder} size="small" slotProps={{ htmlInput: { list: 'terminal-path-suggestions' } }} value={pathInputValue} />
                                                                    <datalist id="terminal-path-suggestions">
                                                                        {pathSuggestions.map((suggestion) => (
                                                                            <option key={suggestion} value={suggestion} />
                                                                        ))}
                                                                    </datalist>
                                                                    <TextField className="terminal-files-search-input" onChange={(event) => setDirectorySearch(event.target.value)} placeholder={copy.searchPlaceholder} size="small" slotProps={{ input: { endAdornment: <span className="terminal-files-toolbar-glyph terminal-files-toolbar-glyph-search" /> } }} value={directorySearch} />
                                                                </div>

                                                                <div className="terminal-files-toolbar-group terminal-files-toolbar-group-actions">
                                                                    <button className="terminal-files-toolbar-button terminal-files-toolbar-button-primary" disabled={isFileActionSubmitting} onClick={() => openBrowserActionDialog({ type: 'create-folder' })} title={copy.createFolder} type="button">
                                                                        <FolderCreateIcon />
                                                                    </button>
                                                                    <button className="terminal-files-toolbar-button terminal-files-toolbar-button-primary" disabled={isFileActionSubmitting} onClick={() => openBrowserActionDialog({ type: 'create-file' })} title={copy.createFile} type="button">
                                                                        <FileCreateIcon />
                                                                    </button>
                                                                    <button className="terminal-files-toolbar-button terminal-files-toolbar-button-primary" disabled={isFileActionSubmitting} onClick={() => uploadInputRef.current?.click()} title={copy.uploadFile} type="button">
                                                                        <UploadFileIcon />
                                                                    </button>
                                                                    <input ref={uploadInputRef} hidden type="file" onChange={(event) => void handleUploadChange(event)} />
                                                                </div>
                                                            </div>

                                                            <div className="terminal-files-layout">
                                                                <div className="terminal-files-browser-panel" onClick={(event) => handleBrowserBackgroundClick(event, '.terminal-files-list-row, .terminal-files-grid-card')} onContextMenu={(event) => handleBrowserBackgroundContextMenu(event, '.terminal-files-list-row, .terminal-files-grid-card')}>
                                                                    {browserLoading ? <div className="terminal-files-progress" /> : null}
                                                                    {isEditorLoading ? (
                                                                        <div className="terminal-files-empty">
                                                                            <Typography sx={{ fontSize: 13.5, color: palette.subtleText }}>{copy.editorLoading}</Typography>
                                                                        </div>
                                                                    ) : editorPath ? (
                                                                        <div className="terminal-files-browser-editor">
                                                                            <div className="terminal-files-browser-editor-header">
                                                                                <div className="terminal-files-browser-editor-header-main">
                                                                                    <div className="terminal-files-browser-editor-title terminal-files-truncate">{editorPath}</div>
                                                                                    <div className="terminal-files-editor-actions terminal-files-editor-actions-header">
                                                                                        <button className="terminal-files-editor-action terminal-files-editor-action-close" onClick={clearEditorState} title={copy.closeEditor} type="button">
                                                                                            <ToolbarGlyph kind="close" />
                                                                                        </button>
                                                                                        <button className="terminal-files-editor-action terminal-files-editor-action-save" disabled={!editorDirty || isFileActionSubmitting} onClick={() => void handleSaveEditor()} title={copy.saveFile} type="button">
                                                                                            <ToolbarGlyph kind="save" />
                                                                                        </button>
                                                                                    </div>
                                                                                </div>
                                                                            </div>
                                                                            <div className="terminal-files-browser-editor-body">
                                                                                <TextField className="terminal-files-editor-textarea" fullWidth multiline onChange={(event) => setEditorContent(event.target.value)} slotProps={{ htmlInput: { wrap: 'off', spellCheck: false } }} sx={editorTextareaSx} value={editorContent} />
                                                                            </div>
                                                                        </div>
                                                                    ) : filteredBrowserEntries.length ? (
                                                                        <div className="terminal-files-list-view">
                                                                            {browserDisplayMode === 'list' ? (
                                                                                <>
                                                                                    <div className="terminal-files-list-header terminal-files-list-row-frame">
                                                                                        <div>{copy.nameLabel}</div>
                                                                                        <div>{copy.modeLabel}</div>
                                                                                        <div>{copy.ownerLabel}</div>
                                                                                        <div>{copy.groupLabel}</div>
                                                                                        <div>{copy.sizeLabel}</div>
                                                                                        <div>{copy.modifiedLabel}</div>
                                                                                        <div>{copy.createdLabel}</div>
                                                                                    </div>
                                                                                    <div className="terminal-files-list-body" onClick={(event) => handleBrowserBackgroundClick(event, '.terminal-files-list-row')} onContextMenu={(event) => handleBrowserBackgroundContextMenu(event, '.terminal-files-list-row')}>
                                                                                        {filteredBrowserEntries.map((entry) => {
                                                                                            const selected = selectedEntryPath === entry.path
                                                                                            return (
                                                                                                <button key={entry.path} className={`terminal-files-list-row terminal-files-list-row-frame ${selected ? 'terminal-files-list-row-selected' : ''}`} onClick={() => handleBrowseEntry(entry)} onContextMenu={(event) => openBrowserContextMenu(event, entry)} onDoubleClick={() => handleBrowseEntryOpen(entry)} type="button">
                                                                                                    <div className="terminal-files-list-name">
                                                                                                        <FileItemGlyph kind={getVisualKind(entry)} variant="list" active={selected && entry.item_type === 'directory'} />
                                                                                                        <div className="terminal-files-list-name-content">
                                                                                                            <span className="terminal-files-truncate">{entry.name}</span>
                                                                                                            <span className="terminal-files-list-kind">{getBrowserEntryCategoryLabel(entry, locale)}</span>
                                                                                                        </div>
                                                                                                    </div>
                                                                                                    <div>{entry.mode || '—'}</div>
                                                                                                    <div>{formatBrowserIdentity(entry.owner)}</div>
                                                                                                    <div>{formatBrowserIdentity(entry.group)}</div>
                                                                                                    <div>{entry.item_type === 'file' ? formatFileSize(entry.size) : '—'}</div>
                                                                                                    <div>{formatBrowserTimestamp(entry.modified_at, locale)}</div>
                                                                                                    <div>{formatBrowserTimestamp(entry.created_at, locale)}</div>
                                                                                                </button>
                                                                                            )
                                                                                        })}
                                                                                    </div>
                                                                                </>
                                                                            ) : (
                                                                                <div className="terminal-files-grid-body" onClick={(event) => handleBrowserBackgroundClick(event, '.terminal-files-grid-card')} onContextMenu={(event) => handleBrowserBackgroundContextMenu(event, '.terminal-files-grid-card')}>
                                                                                    {filteredBrowserEntries.map((entry) => {
                                                                                        const selected = selectedEntryPath === entry.path
                                                                                        return (
                                                                                            <button key={entry.path} className="terminal-files-grid-card" onClick={() => handleBrowseEntry(entry)} onContextMenu={(event) => openBrowserContextMenu(event, entry)} onDoubleClick={() => handleBrowseEntryOpen(entry)} type="button">
                                                                                                <div className={`terminal-files-grid-card-hitbox ${selected ? 'terminal-files-grid-card-hitbox-selected' : ''}`}>
                                                                                                    <FileItemGlyph kind={getVisualKind(entry)} variant="card" active={selected && entry.item_type === 'directory'} />
                                                                                                    <div className="terminal-files-grid-card-body">
                                                                                                        <div className="terminal-files-grid-card-title">{entry.name}</div>
                                                                                                        <div className="terminal-files-grid-card-kind">{getBrowserEntryCategoryLabel(entry, locale)}</div>
                                                                                                    </div>
                                                                                                </div>
                                                                                            </button>
                                                                                        )
                                                                                    })}
                                                                                </div>
                                                                            )}
                                                                        </div>
                                                                    ) : browserLoading ? (
                                                                        <div className="terminal-files-list-view">
                                                                            <div className="terminal-files-list-header terminal-files-list-row-frame">
                                                                                <div>{copy.nameLabel}</div>
                                                                                <div>{copy.modeLabel}</div>
                                                                                <div>{copy.ownerLabel}</div>
                                                                                <div>{copy.groupLabel}</div>
                                                                                <div>{copy.sizeLabel}</div>
                                                                                <div>{copy.modifiedLabel}</div>
                                                                                <div>{copy.createdLabel}</div>
                                                                            </div>
                                                                            <div className="terminal-files-list-body">
                                                                                {Array.from({ length: 8 }).map((_, i) => (
                                                                                    <div key={i} className="terminal-files-list-row terminal-files-list-row-frame" style={{ pointerEvents: 'none' }}>
                                                                                        <div className="terminal-files-list-name">
                                                                                            <Skeleton variant="circular" width={18} height={18} sx={{ flexShrink: 0 }} />
                                                                                            <Skeleton variant="text" width={i % 3 === 0 ? 140 : i % 3 === 1 ? 100 : 80} height={14} />
                                                                                        </div>
                                                                                        <Skeleton variant="text" width="55%" height={14} />
                                                                                        <Skeleton variant="text" width="45%" height={14} />
                                                                                        <Skeleton variant="text" width="45%" height={14} />
                                                                                        <Skeleton variant="text" width="35%" height={14} />
                                                                                        <Skeleton variant="text" width="65%" height={14} />
                                                                                        <Skeleton variant="text" width="65%" height={14} />
                                                                                    </div>
                                                                                ))}
                                                                            </div>
                                                                        </div>
                                                                    ) : (
                                                                        <div className="terminal-files-empty">
                                                                            <Typography sx={{ fontSize: 13.5, color: palette.subtleText }}>{copy.fileEmpty}</Typography>
                                                                        </div>
                                                                    )}
                                                                </div>

                                                                <div className="terminal-files-inspector-panel">
                                                                    <div className="terminal-files-inspector-header terminal-files-inspector-header-classic">
                                                                        <div className="terminal-files-inspector-header-main">
                                                                            <div className="terminal-files-inspector-header-copy">
                                                                                <div className="terminal-files-inspector-header-title terminal-files-truncate">{inspectorEntry?.name || copy.inspectorTitle}</div>
                                                                                {inspectorEntry ? <div className="terminal-files-inspector-header-meta">{`${getBrowserCategoryLabel(locale)}: ${getBrowserEntryCategoryLabel(inspectorEntry, locale)}`}</div> : null}
                                                                            </div>
                                                                            <div className="terminal-files-inspector-header-actions">
                                                                                <IconButton className="terminal-files-toolbar-button terminal-files-toolbar-button-small terminal-files-toolbar-button-danger" disabled={!canDeleteSelectedItem} onClick={() => activeBrowserEntry ? openBrowserActionDialog({ type: 'delete', item: activeBrowserEntry }) : undefined} size="small" title={copy.deleteAction}>
                                                                                    <ToolbarGlyph kind="trash" />
                                                                                </IconButton>
                                                                                <IconButton className="terminal-files-toolbar-button terminal-files-toolbar-button-small" disabled={!canShowInspectorProperties} onClick={handleShowInspectorProperties} size="small" title={copy.propertiesAction}>
                                                                                    <ToolbarGlyph kind="properties" />
                                                                                </IconButton>
                                                                                <IconButton className="terminal-files-toolbar-button terminal-files-toolbar-button-small" disabled={!canEditSelectedItem} onClick={() => selectedBrowserEntry ? handleBrowseEntryOpen(selectedBrowserEntry) : undefined} size="small" title={copy.editAction}>
                                                                                    <ToolbarGlyph kind="edit" />
                                                                                </IconButton>
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                    <div ref={browserInspectorBodyRef} className="terminal-files-inspector-body terminal-files-inspector-body-classic">
                                                                        {inspectorEntry ? (
                                                                            <div className="terminal-files-inspector-rows terminal-files-inspector-rows-classic">
                                                                                <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{getBrowserCategoryLabel(locale)}</Typography><Typography className="terminal-files-inspector-value">{getBrowserEntryCategoryLabel(inspectorEntry, locale)}</Typography></div>
                                                                                <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{copy.modeLabel}</Typography><Typography className="terminal-files-inspector-value">{inspectorEntry.mode || '—'}</Typography></div>
                                                                                <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{copy.ownerLabel}</Typography><Typography className="terminal-files-inspector-value">{formatBrowserIdentity(inspectorEntry.owner)}</Typography></div>
                                                                                <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{copy.groupLabel}</Typography><Typography className="terminal-files-inspector-value">{formatBrowserIdentity(inspectorEntry.group)}</Typography></div>
                                                                                <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{copy.sizeLabel}</Typography><Typography className="terminal-files-inspector-value">{inspectorEntry.item_type === 'file' ? formatFileSize(inspectorEntry.size) : '—'}</Typography></div>
                                                                                <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{copy.modifiedLabel}</Typography><Typography className="terminal-files-inspector-value">{formatBrowserTimestamp(inspectorEntry.modified_at, locale)}</Typography></div>
                                                                                <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{copy.createdLabel}</Typography><Typography className="terminal-files-inspector-value">{formatBrowserTimestamp(inspectorEntry.created_at, locale)}</Typography></div>
                                                                                <div className="terminal-files-inspector-row"><Typography className="terminal-files-inspector-label">{copy.pathPlaceholder}</Typography><Typography className="terminal-files-inspector-value terminal-files-break-value">{inspectorEntry.path}</Typography></div>
                                                                            </div>
                                                                        ) : (
                                                                            <div className="terminal-files-empty">
                                                                                <Typography sx={{ fontSize: 13.5, color: palette.subtleText }}>{copy.fileEmpty}</Typography>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    ) : (
                                                        <>
                                                            <div className="terminal-shell-transcript" style={{ position: 'relative' }}>
                                                                <div className="terminal-xterm-host" ref={terminalHostRef} />
                                                                {activeSession.status === 'idle' ? (
                                                                    <Box sx={{
                                                                        position: 'absolute', inset: 0,
                                                                        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                                                                        gap: 1.5,
                                                                        backgroundColor: palette.cardBg,
                                                                        zIndex: 2,
                                                                    }}>
                                                                        <CircularProgress size={28} />
                                                                        <Typography sx={{ fontSize: 13, color: palette.subtleText }}>{copy.connectingAction}</Typography>
                                                                    </Box>
                                                                ) : null}
                                                            </div>
                                                            {activeSession.status === 'ended' ? (
                                                                <div className="terminal-inline-reconnect-row">
                                                                    <span className="terminal-line terminal-line-meta">{copy.promptReconnect}</span>
                                                                    <Button onClick={handleReconnect} size="small" variant="outlined">
                                                                        {copy.reconnect}
                                                                    </Button>
                                                                </div>
                                                            ) : null}
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="terminal-shell-empty">
                                                <Typography sx={{ fontSize: 13.5, color: palette.subtleText }}>{copy.sessionEmpty}</Typography>
                                            </div>
                                        )}

                                        {workspaceView === 'files' ? (
                                            <div className="terminal-files-footer">
                                                <div className="terminal-files-footer-stats">
                                                    {`${visibleDirectoryCount} ${copy.directoryLabel}, ${visibleFileCount} ${copy.filesLabel} (${formatFileSize(visibleFileSize)})`}
                                                </div>
                                                <div className="terminal-files-footer-actions">
                                                    <button className={`terminal-files-footer-button ${showHiddenFiles ? 'terminal-files-footer-button-active' : ''}`} onClick={handleToggleHiddenFiles} title={showHiddenFiles ? copy.hideHiddenFiles : copy.showHiddenFiles} type="button">
                                                        {showHiddenFiles ? <HiddenFilesOffIcon /> : <HiddenFilesIcon />}
                                                    </button>
                                                    <button className={`terminal-files-footer-button ${browserDisplayMode === 'grid' ? 'terminal-files-footer-button-active' : ''}`} onClick={handleToggleBrowserDisplayMode} title={copy.toggleView} type="button">
                                                        {browserDisplayMode === 'list' ? <GridViewIcon /> : <ListViewIcon />}
                                                    </button>
                                                </div>
                                            </div>
                                        ) : null}

                                        <Dialog
                                            container={terminalWorkspaceShellRef.current}
                                            disablePortal
                                            open={browserDialogState !== null}
                                            onClose={() => setBrowserDialogState(null)}
                                            sx={{
                                                position: 'absolute',
                                                inset: 0,
                                                '& .MuiDialog-paper': {
                                                    borderRadius: '2px',
                                                    backgroundColor: palette.cardBg,
                                                    color: palette.text,
                                                    border: `1px solid ${palette.border}`,
                                                    minWidth: { xs: 'min(96vw, 420px)', sm: browserDialogState?.type === 'properties' ? 560 : 360 },
                                                },
                                                '& .MuiBackdrop-root': {
                                                    position: 'absolute',
                                                },
                                            }}
                                        >
                                            <DialogTitle sx={{ px: 2.5, py: 2, backgroundColor: palette.cardBg, borderBottom: `1px solid ${palette.border}` }}>
                                                {browserDialogState?.type === 'create-folder'
                                                    ? copy.createFolderTitle
                                                    : browserDialogState?.type === 'create-file'
                                                        ? copy.createFileTitle
                                                        : browserDialogState?.type === 'rename'
                                                            ? copy.renameTitle
                                                            : browserDialogState?.type === 'properties'
                                                                ? copy.propertiesTitle
                                                                : copy.deleteTitle}
                                            </DialogTitle>
                                            <DialogContent dividers sx={{ px: 2.5, py: 2, backgroundColor: palette.cardBg, '&.MuiDialogContent-dividers': { borderTop: 'none', borderBottomColor: palette.border } }}>
                                                {browserDialogState?.type === 'delete' ? (
                                                    <Stack spacing={1.25}>
                                                        <Box sx={{ border: `1px solid ${alpha(palette.danger, 0.28)}`, borderRadius: '2px', backgroundColor: alpha(palette.danger, isDarkMode ? 0.2 : 0.08), boxShadow: `inset 3px 0 0 ${palette.danger}`, px: 1.5, py: 1.25 }}>
                                                            <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.2, color: palette.danger }}>{copy.deleteTargetLabel}</Typography>
                                                            <Typography sx={{ mt: 0.5, fontSize: 14, fontWeight: 600, color: palette.text, wordBreak: 'break-all' }}>{browserDialogState.item.name}</Typography>
                                                        </Box>
                                                        <Typography sx={{ fontSize: 14, lineHeight: 1.65, color: palette.text }}>
                                                            {copy.deletePrompt}
                                                        </Typography>
                                                    </Stack>
                                                ) : browserDialogState?.type === 'properties' && browserPropertiesForm ? (
                                                    <Stack spacing={2.25}>
                                                        <TextField
                                                            disabled
                                                            fullWidth
                                                            label={copy.nameLabel}
                                                            sx={browserDialogFieldSx}
                                                            value={browserDialogState.item.name}
                                                        />
                                                        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                                                            <TextField
                                                                autoFocus
                                                                fullWidth
                                                                label={copy.ownerLabel}
                                                                onChange={(event) => setBrowserPropertiesForm((current) => (current ? { ...current, owner: event.target.value } : current))}
                                                                sx={browserDialogFieldSx}
                                                                value={browserPropertiesForm.owner}
                                                            />
                                                            <TextField
                                                                fullWidth
                                                                label={copy.groupLabel}
                                                                onChange={(event) => setBrowserPropertiesForm((current) => (current ? { ...current, group: event.target.value } : current))}
                                                                sx={browserDialogFieldSx}
                                                                value={browserPropertiesForm.group}
                                                            />
                                                        </Stack>
                                                        <Box sx={{ border: `1px solid ${palette.border}`, borderRadius: '2px', overflow: 'hidden' }}>
                                                            <Box sx={{ px: 1.5, py: 1.25, borderBottom: `1px solid ${palette.border}`, backgroundColor: alpha(palette.pageBg, 0.4) }}>
                                                                <Typography sx={{ fontSize: 13, fontWeight: 700 }}>{copy.permissionsTitle}</Typography>
                                                                <Typography sx={{ mt: 0.5, fontSize: 12, color: palette.subtleText }}>{`${copy.modePreviewLabel}: ${buildModePreview(browserDialogState.item.item_type, browserPropertiesForm)}`}</Typography>
                                                            </Box>
                                                            {([
                                                                ['ownerPermissions', copy.permissionsOwner],
                                                                ['groupPermissions', copy.permissionsGroup],
                                                                ['otherPermissions', copy.permissionsOther],
                                                            ] as const).map(([field, label], rowIndex) => (
                                                                <Box
                                                                    key={field}
                                                                    sx={{
                                                                        display: 'grid',
                                                                        gridTemplateColumns: 'minmax(96px, 1fr) repeat(3, minmax(78px, 92px))',
                                                                        alignItems: 'center',
                                                                        px: 1.5,
                                                                        py: 1,
                                                                        borderTop: rowIndex === 0 ? 'none' : `1px solid ${palette.border}`,
                                                                        gap: 1,
                                                                    }}
                                                                >
                                                                    <Typography sx={{ fontSize: 13.5, fontWeight: 600 }}>{label}</Typography>
                                                                    {([
                                                                        ['read', copy.permissionsRead],
                                                                        ['write', copy.permissionsWrite],
                                                                        ['execute', copy.permissionsExecute],
                                                                    ] as const).map(([permissionKey, permissionLabel]) => (
                                                                        <FormControlLabel
                                                                            key={permissionKey}
                                                                            control={
                                                                                <Checkbox
                                                                                    checked={browserPropertiesForm[field][permissionKey]}
                                                                                    onChange={(event) => {
                                                                                        const checked = event.target.checked
                                                                                        setBrowserPropertiesForm((current) => (
                                                                                            current
                                                                                                ? {
                                                                                                    ...current,
                                                                                                    [field]: {
                                                                                                        ...current[field],
                                                                                                        [permissionKey]: checked,
                                                                                                    },
                                                                                                }
                                                                                                : current
                                                                                        ))
                                                                                    }}
                                                                                />
                                                                            }
                                                                            label={permissionLabel}
                                                                            sx={{ m: 0, '& .MuiFormControlLabel-label': { fontSize: 12.5 } }}
                                                                        />
                                                                    ))}
                                                                </Box>
                                                            ))}
                                                        </Box>
                                                    </Stack>
                                                ) : (
                                                    <TextField
                                                        autoFocus
                                                        fullWidth
                                                        label={copy.nameLabel}
                                                        onChange={(event) => setBrowserDialogName(event.target.value)}
                                                        onKeyDown={(event) => {
                                                            if (event.key === 'Enter') {
                                                                event.preventDefault()
                                                                void handleConfirmBrowserAction()
                                                            }
                                                        }}
                                                        sx={browserDialogFieldSx}
                                                        value={browserDialogName}
                                                    />
                                                )}
                                            </DialogContent>
                                            <DialogActions sx={{ px: 2.5, py: 2, borderTop: `1px solid ${palette.border}`, backgroundColor: palette.cardBg }}>
                                                <Button onClick={() => openBrowserActionDialog(null)}>{copy.cancel}</Button>
                                                <Button
                                                    color={browserDialogState?.type === 'delete' ? 'error' : 'primary'}
                                                    disabled={
                                                        isFileActionSubmitting
                                                        || (browserDialogState?.type === 'properties'
                                                            ? !browserPropertiesForm
                                                            : browserDialogState?.type !== 'delete' && !browserDialogName.trim())
                                                    }
                                                    onClick={() => void handleConfirmBrowserAction()}
                                                    variant="contained"
                                                >
                                                    {browserDialogState?.type === 'rename'
                                                        ? copy.renameConfirm
                                                        : browserDialogState?.type === 'delete'
                                                            ? copy.deleteConfirm
                                                            : browserDialogState?.type === 'properties'
                                                                ? copy.propertiesSave
                                                                : copy.createConfirm}
                                                </Button>
                                            </DialogActions>
                                        </Dialog>

                                        <Menu
                                            open={browserContextMenu !== null}
                                            onClose={closeBrowserContextMenu}
                                            anchorReference="anchorPosition"
                                            anchorPosition={browserContextMenu ? { top: browserContextMenu.mouseY, left: browserContextMenu.mouseX } : undefined}
                                            slotProps={{
                                                paper: {
                                                    sx: {
                                                        border: `1px solid ${palette.border}`,
                                                        borderRadius: '2px',
                                                        backgroundColor: palette.cardBg,
                                                        color: palette.text,
                                                        minWidth: 180,
                                                        boxShadow: isDarkMode ? '0 12px 28px rgba(2, 6, 23, 0.5)' : '0 10px 24px rgba(15, 23, 42, 0.14)',
                                                        '& .MuiMenuItem-root': {
                                                            fontSize: 13.5,
                                                            color: palette.text,
                                                            minHeight: 36,
                                                        },
                                                        '& .MuiMenuItem-root.Mui-disabled': {
                                                            color: palette.subtleText,
                                                            opacity: 0.55,
                                                        },
                                                    },
                                                },
                                            }}
                                        >
                                            {browserContextMenu?.item ? (
                                                <>
                                                    <MenuItem disabled={isFileActionSubmitting} onClick={() => { void handleBrowserContextAction('copy') }}>{copy.copyAction}</MenuItem>
                                                    <MenuItem disabled={isFileActionSubmitting || browserContextMenu.item.path === '/' || browserContextMenu.item.path === browserPath} onClick={() => { void handleBrowserContextAction('cut') }}>{copy.cutAction}</MenuItem>
                                                    <MenuItem disabled={browserContextMenu.item.item_type !== 'file' || isFileActionSubmitting} onClick={() => { void handleBrowserContextAction('download') }}>{copy.downloadAction}</MenuItem>
                                                    <MenuItem disabled={isFileActionSubmitting} onClick={() => { void handleBrowserContextAction('rename') }}>{copy.renameAction}</MenuItem>
                                                    <MenuItem disabled={isFileActionSubmitting || (browserContextMenu.item.path === '/' && browserContextMenu.item.item_type === 'directory')} onClick={() => { void handleBrowserContextAction('delete') }}>{copy.deleteAction}</MenuItem>
                                                    <MenuItem disabled={isFileActionSubmitting} onClick={() => { void handleBrowserContextAction('properties') }}>{copy.propertiesAction}</MenuItem>
                                                    <MenuItem disabled={!browserContextMenu.item.text_editable || browserContextMenu.item.item_type !== 'file' || isFileActionSubmitting} onClick={() => { void handleBrowserContextAction('edit') }}>{copy.editAction}</MenuItem>
                                                </>
                                            ) : (
                                                <>
                                                    <MenuItem disabled={!browserClipboard || isFileActionSubmitting} onClick={() => { void handleBrowserContextAction('paste') }}>{copy.pasteAction}</MenuItem>
                                                    <MenuItem disabled={isFileActionSubmitting} onClick={() => { void handleBrowserContextAction('create-folder') }}>{copy.createFolder}</MenuItem>
                                                    <MenuItem disabled={isFileActionSubmitting} onClick={() => { void handleBrowserContextAction('create-file') }}>{copy.createFile}</MenuItem>
                                                    <MenuItem disabled={!browserMetadata || isFileActionSubmitting} onClick={() => { void handleBrowserContextAction('properties') }}>{copy.propertiesAction}</MenuItem>
                                                </>
                                            )}
                                        </Menu>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                )}

                <Menu
                    anchorEl={createSessionAnchorEl}
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
                    disableAutoFocusItem
                    onClose={closeCreateSessionMenu}
                    open={Boolean(createSessionAnchorEl)}
                    slotProps={{
                        paper: {
                            sx: {
                                mt: 1,
                                width: 'min(420px, calc(100vw - 32px))',
                                borderRadius: '2px',
                                border: `1px solid ${palette.border}`,
                                backgroundColor: palette.cardBg,
                                boxShadow: palette.shadow,
                                overflow: 'hidden',
                            },
                        },
                    }}
                    transformOrigin={{ vertical: 'top', horizontal: 'left' }}
                >
                    <Box sx={{ p: 1.25, display: 'grid', gap: 1 }}>
                        <Box sx={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: 0.75 }}>
                            <Button onClick={() => openAddHostDialog('new-connection')} sx={{ minHeight: 56, py: 0.75, borderRadius: '2px', borderColor: palette.border, color: palette.text, fontWeight: 700, flexDirection: 'column', gap: 0.35 }} variant="outlined">
                                <Typography component="span" sx={{ fontSize: 22, lineHeight: 1, fontWeight: 300 }}>+</Typography>
                                <Typography component="span" sx={{ fontSize: 15, fontWeight: 700 }}>{copy.quickConnectNewHost}</Typography>
                            </Button>
                        </Box>
                        <Box sx={{ pt: 1, borderTop: `1px solid ${palette.border}`, display: 'grid', gap: 0.9 }}>
                            <TextField
                                className="terminal-connections-toolbar-field"
                                disabled={isDisconnecting || activatingProfileId !== null}
                                onChange={(event) => setProfileSearchValue(event.target.value)}
                                placeholder={copy.searchConnectionsPlaceholder}
                                size="small"
                                value={profileSearchValue}
                                sx={{
                                    '& .MuiOutlinedInput-root': {
                                        bgcolor: isDarkMode ? '#111827' : '#fff',
                                        boxShadow: isDarkMode ? 'none' : '0 1px 2px rgba(15, 23, 42, 0.04)',
                                    },
                                    '& .MuiInputBase-input': {
                                        color: isDarkMode ? '#e5edf5' : '#334155',
                                    },
                                    '& .MuiInputBase-input::placeholder': {
                                        color: isDarkMode ? '#64748b' : '#94a3b8',
                                        opacity: 1,
                                    },
                                    '& .MuiOutlinedInput-notchedOutline': {
                                        borderColor: isDarkMode ? 'rgba(71, 85, 105, 0.8)' : 'rgba(203, 213, 225, 0.9)',
                                    },
                                }}
                            />
                            {quickConnectList}
                        </Box>
                    </Box>
                </Menu>

                <TerminalScopedOverlay open={isHostSelectorOpen} onClose={() => setIsHostSelectorOpen(false)}>
                    <Card elevation={0} sx={{ ...surfaceCardSx, width: 'min(960px, calc(100vw - 32px))', maxHeight: 'min(calc(100dvh - 72px), 820px)', display: 'flex', flexDirection: 'column', overflow: 'hidden', mx: 'auto', my: 'auto' }}>
                        <DialogTitle sx={{ px: 2.25, py: 1.5, backgroundColor: palette.cardBg, borderBottom: `1px solid ${palette.border}` }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
                                <Typography sx={{ fontSize: 18, fontWeight: 800, color: palette.text }}>{copy.savedProfilesTitle}</Typography>
                                <IconButton aria-label={copy.cancel} className="terminal-connections-dialog-close" onClick={() => setIsHostSelectorOpen(false)} size="small">
                                    <CloseActionIcon />
                                </IconButton>
                            </Box>
                        </DialogTitle>
                        <DialogContent dividers sx={{ px: { xs: 1.5, sm: 2 }, py: { xs: 1, sm: 1.5 }, backgroundColor: palette.cardBg, flex: '1 1 auto', minHeight: 0, overflowY: 'auto', overflowX: 'hidden', '&.MuiDialogContent-dividers': { borderTop: 'none', borderBottomColor: palette.border } }}>
                            <Stack spacing={1.5} sx={{ minHeight: 0 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5, flexWrap: 'wrap' }}>
                                    <Typography sx={{ fontSize: 14, fontWeight: 600, color: palette.subtleText }}>{copy.savedProfilesSubtitle}</Typography>
                                    {savedProfilesToolbar}
                                </Box>
                                {savedProfilesTable}
                            </Stack>
                        </DialogContent>
                    </Card>
                </TerminalScopedOverlay>

                <TerminalScopedOverlay centered open={activatingProfileId !== null} onClose={() => undefined}>
                    <Box sx={{
                        display: 'flex', alignItems: 'center', gap: 1.5,
                        backgroundColor: palette.cardBg,
                        border: `1px solid ${palette.border}`,
                        borderRadius: '999px',
                        px: 2.5, py: 1.25,
                        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.18)',
                        mx: 'auto', width: 'fit-content',
                    }}>
                        <CircularProgress size={16} thickness={4} />
                        <Typography sx={{ fontSize: 13.5, fontWeight: 600, color: palette.text, whiteSpace: 'nowrap' }}>{copy.connectingAction}</Typography>
                    </Box>
                </TerminalScopedOverlay>

                <TerminalScopedOverlay centered open={isDisconnecting} onClose={() => undefined}>
                    <Box sx={{
                        display: 'flex', alignItems: 'center', gap: 1.5,
                        backgroundColor: palette.cardBg,
                        border: `1px solid ${palette.border}`,
                        borderRadius: '999px',
                        px: 2.5, py: 1.25,
                        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.18)',
                        mx: 'auto', width: 'fit-content',
                    }}>
                        <CircularProgress size={16} thickness={4} />
                        <Typography sx={{ fontSize: 13.5, fontWeight: 600, color: palette.text, whiteSpace: 'nowrap' }}>{copy.disconnectingAction}</Typography>
                    </Box>
                </TerminalScopedOverlay>

                <TerminalScopedOverlay
                    open={isAccessDialogOpen}
                    onClose={() => {
                        if (!formBusy) {
                            setIsAccessDialogOpen(false)
                            if (accessDialogMode === 'add-host') setIsHostSelectorOpen(true)
                        }
                    }}
                >
                    <Card elevation={0} sx={{ ...surfaceCardSx, width: 'min(960px, calc(100vw - 32px))', maxHeight: 'min(calc(100dvh - 96px), 680px)', display: 'flex', flexDirection: 'column', overflow: 'hidden', mx: 'auto', my: 'auto' }}>
                        <DialogTitle sx={{ px: 2.25, py: 1.5, backgroundColor: palette.cardBg, borderBottom: `1px solid ${palette.border}` }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
                                <Typography sx={{ fontSize: 18, fontWeight: 800, color: palette.text }}>
                                    {accessDialogMode === 'edit' ? copy.editAction : accessDialogMode === 'new-connection' ? copy.newConnectionTitle : copy.addHostAction}
                                </Typography>
                                <IconButton aria-label={copy.cancel} className="terminal-connections-dialog-close" disabled={formBusy} onClick={() => { setIsAccessDialogOpen(false); if (accessDialogMode === 'add-host') setIsHostSelectorOpen(true) }} size="small">
                                    <CloseActionIcon />
                                </IconButton>
                            </Box>
                        </DialogTitle>
                        <DialogContent dividers sx={{ px: { xs: 1.5, sm: 2 }, py: { xs: 1, sm: 1.5 }, backgroundColor: palette.cardBg, flex: '1 1 auto', minHeight: 0, overflowY: 'auto', overscrollBehavior: 'contain', WebkitOverflowScrolling: 'touch', '&.MuiDialogContent-dividers': { borderTop: 'none', borderBottomColor: palette.border } }}>
                            {accessFields}
                        </DialogContent>
                        <DialogActions sx={{ px: 2.25, py: 1.5, borderTop: `1px solid ${palette.border}`, backgroundColor: palette.cardBg, justifyContent: 'space-between', gap: 1, flexWrap: 'wrap' }}>
                            <Button onClick={() => { setIsAccessDialogOpen(false); if (accessDialogMode === 'add-host') setIsHostSelectorOpen(true) }} disabled={formBusy}>{copy.cancel}</Button>
                            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                                <Button disabled={formBusy} onClick={() => void handleConnectionTest()} startIcon={isTestingConnection ? <CircularProgress color="inherit" size={16} /> : null} sx={{ minWidth: 148, fontWeight: 700 }} variant="outlined">
                                    {copy.connectionTestTitle}
                                </Button>
                                <Button disabled={formBusy} onClick={() => void handleAccessSubmit()} startIcon={isSubmittingAccess ? <CircularProgress color="inherit" size={16} /> : null} sx={{ minWidth: 148, fontWeight: 700 }} variant="contained">
                                    {copy.accessSubmit}
                                </Button>
                            </Stack>
                        </DialogActions>
                    </Card>
                </TerminalScopedOverlay>

                <TerminalScopedOverlay open={pendingDeleteProfile !== null} onClose={() => setPendingDeleteProfile(null)}>
                    <Card elevation={0} sx={{ ...surfaceCardSx, width: { xs: 'min(92vw, 440px)', sm: 440 }, mx: 'auto' }}>
                        <DialogTitle sx={{ px: 2.5, py: 2, backgroundColor: palette.cardBg, borderBottom: `1px solid ${palette.border}` }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
                                <Typography sx={{ fontSize: 18, fontWeight: 800, color: palette.text }}>
                                    {copy.deleteProfileTitle}
                                </Typography>
                                <IconButton aria-label={copy.cancel} className="terminal-connections-dialog-close" onClick={() => setPendingDeleteProfile(null)} size="small">
                                    <CloseActionIcon />
                                </IconButton>
                            </Box>
                        </DialogTitle>
                        <DialogContent dividers sx={{ px: 2.5, py: 2, backgroundColor: palette.cardBg, '&.MuiDialogContent-dividers': { borderTop: 'none', borderBottomColor: palette.border } }}>
                            <Typography sx={{ fontSize: 14, lineHeight: 1.65, color: palette.text }}>
                                {copy.deleteProfilePrompt}
                            </Typography>
                            {pendingDeleteProfile ? (
                                <Typography sx={{ mt: 1.25, fontSize: 13, fontWeight: 700, color: palette.subtleText }}>
                                    {pendingDeleteProfile.host} / {pendingDeleteProfile.username}
                                </Typography>
                            ) : null}
                        </DialogContent>
                        <DialogActions sx={{ px: 2.5, py: 2, borderTop: `1px solid ${palette.border}`, backgroundColor: palette.cardBg }}>
                            <Button onClick={() => setPendingDeleteProfile(null)}>{copy.cancel}</Button>
                            <Button color="error" onClick={() => void handleConfirmDeleteProfile()} variant="contained">
                                {copy.confirmDelete}
                            </Button>
                        </DialogActions>
                    </Card>
                </TerminalScopedOverlay>

            </Stack>

            <SurfaceFeedbackToast
                open={Boolean(feedback)}
                severity={feedback?.severity ?? 'info'}
                message={feedback?.message ?? ''}
                onClose={(_, reason?: SnackbarCloseReason) => {
                    if (reason === 'clickaway') {
                        return
                    }
                    setFeedback(null)
                }}
            />
        </Box>
    )
}
