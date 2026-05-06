import {
    Alert,
    Box,
    Button,
    CircularProgress,
    IconButton,
    LinearProgress,
    Paper,
    Snackbar,
    Stack,
    TextField,
    Typography,
} from '@mui/material'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { useProductAuth } from '../product-auth/product-auth-provider'
import './files-page.css'

type FileManagerVolume = {
    volume_name: string
    driver: string
    app_id?: string | null
    owner?: string | null
}

type FileManagerItem = {
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

type FileManagerVolumesResponse = {
    volumes: FileManagerVolume[]
}

type FileManagerDirectoryResponse = {
    volume_name: string
    current_path: string
    metadata?: FileManagerMetadataResponse
    items: FileManagerItem[]
}

type FileManagerTextFileResponse = {
    volume_name: string
    path: string
    content: string
}

type FileManagerMetadataResponse = {
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

type DialogState =
    | { type: 'create-folder'; parentPath: string }
    | { type: 'create-file'; parentPath: string }
    | { type: 'rename'; item: FileManagerItem }
    | { type: 'delete'; item: FileManagerItem }
    | { type: 'delete-volume'; volume: FileManagerVolume }
    | { type: 'overwrite-upload'; fileName: string; contentBase64: string }
    | null

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

function formatSize(size: number, t: (key: string, options?: Record<string, unknown>) => string): string {
    if (size < 1024) {
        return t('filesPage.table.sizeBytes', { count: size })
    }

    const units = ['KB', 'MB', 'GB']
    let value = size / 1024
    let unitIndex = 0
    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024
        unitIndex += 1
    }
    return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`
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

            const encoded = result.includes(',') ? result.split(',')[1] : result
            resolve(encoded)
        }
        reader.readAsDataURL(file)
    })
}

function formatDate(value: string | null | undefined, formatter: Intl.DateTimeFormat): string {
    if (!value) {
        return '—'
    }

    return formatter.format(new Date(value))
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

function normalizeActionErrorMessage(
    message: string,
    t: (key: string, options?: Record<string, unknown>) => string,
    name?: string,
): string {
    const normalized = message.toLowerCase()
    if (normalized.includes('already exists') || normalized.includes('file exists') || normalized.includes('exists')) {
        return t('filesPage.feedback.nameExists', { name: name ?? '' })
    }

    if (normalized.includes('requested file does not exist') || normalized.includes('requested path does not exist')) {
        return t('filesPage.feedback.missingEntry', { name: name ?? '' })
    }

    return message
}

const VIRTUAL_VOLUMES_ROOT_PATH = '/volumes'
const DOCKER_VOLUMES_ROOT_SENTINEL = '__docker_volumes_root__'

function buildVirtualPath(volumeName: string, path: string): string {
    if (!volumeName) {
        return path === '/' ? VIRTUAL_VOLUMES_ROOT_PATH : `${VIRTUAL_VOLUMES_ROOT_PATH}${path}`
    }

    const volumeBasePath = `${VIRTUAL_VOLUMES_ROOT_PATH}/${volumeName}`
    return path === '/' ? volumeBasePath : `${volumeBasePath}${path}`
}

function buildSiblingPath(path: string, nextName: string): string {
    const parent = parentPath(path)
    return parent === '/' ? `/${nextName}` : `${parent}/${nextName}`
}

function parseBrowserPath(input: string, knownVolumes: string[]): NavigationLocation | null {
    const trimmed = input.trim()
    if (!trimmed.startsWith(VIRTUAL_VOLUMES_ROOT_PATH)) {
        return null
    }

    const suffix = trimmed.slice(VIRTUAL_VOLUMES_ROOT_PATH.length)
    const normalizedSuffix = suffix ? `/${suffix.replace(/^\/+/, '').replace(/\/+$/, '')}`.replace(/\/+/g, '/') : '/'
    if (normalizedSuffix === '/' || normalizedSuffix === '/.') {
        return { volumeName: '', path: '/' }
    }

    const parts = normalizedSuffix.split('/').filter(Boolean)
    if (!parts.length || parts.includes('..')) {
        return null
    }

    const [first, second, ...rest] = parts
    if (knownVolumes.includes(first)) {
        const relativeSegments = second === '_data' ? rest : [second, ...rest].filter(Boolean)
        return {
            volumeName: first,
            path: relativeSegments.length ? `/${relativeSegments.join('/')}` : '/',
        }
    }

    return { volumeName: '', path: normalizedSuffix }
}

function ToolbarGlyph({ kind }: { kind: 'back' | 'forward' | 'up' | 'refresh' | 'folder' | 'file' | 'upload' | 'download' | 'rename' | 'trash' | 'edit' | 'search' | 'save' | 'close' }) {
    if (kind === 'search') {
        return (
            <svg aria-hidden="true" className="files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <circle cx="10" cy="10" r="5.5" fill="none" stroke="currentColor" strokeWidth="2" />
                <path d="M14.5 14.5L20 20" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
            </svg>
        )
    }

    if (kind === 'back') {
        return (
            <svg aria-hidden="true" className="files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <path d="M14.5 6L8.5 12L14.5 18" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" />
            </svg>
        )
    }

    if (kind === 'forward') {
        return (
            <svg aria-hidden="true" className="files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <path d="M9.5 6L15.5 12L9.5 18" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" />
            </svg>
        )
    }

    if (kind === 'up') {
        return (
            <svg aria-hidden="true" className="files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <path d="M7 14L12 9L17 14" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" />
            </svg>
        )
    }

    if (kind === 'refresh') {
        return (
            <svg aria-hidden="true" className="files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <path d="M18 8.5V5.5H15" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                <path d="M18 5.5C16.5 4 14.4 3 12 3C7.6 3 4 6.6 4 11" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                <path d="M6 15.5V18.5H9" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                <path d="M6 18.5C7.5 20 9.6 21 12 21C16.4 21 20 17.4 20 13" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
            </svg>
        )
    }

    if (kind === 'download') {
        return (
            <svg aria-hidden="true" className="files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <path d="M12 4V14" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" />
                <path d="M8 10L12 14L16 10" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" />
                <path d="M5 19H19" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
            </svg>
        )
    }

    if (kind === 'rename') {
        return (
            <svg aria-hidden="true" className="files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <path d="M4 17.5V20H6.5L16.8 9.7L14.3 7.2L4 17.5Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="2" />
                <path d="M13.6 7.9L16.1 10.4" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
                <path d="M14.9 6.6L16.1 5.4C16.8 4.7 18 4.7 18.7 5.4L18.8 5.5C19.5 6.2 19.5 7.4 18.8 8.1L17.6 9.3" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
            </svg>
        )
    }

    if (kind === 'save') {
        return (
            <svg aria-hidden="true" className="files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <path d="M6 4H16L19 7V20H5V5C5 4.4 5.4 4 6 4Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="2" />
                <path d="M8 4V9H15V4" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="2" />
                <path d="M8 15H16" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
            </svg>
        )
    }

    if (kind === 'close') {
        return (
            <svg aria-hidden="true" className="files-toolbar-glyph-svg" viewBox="0 0 24 24">
                <path d="M7 7L17 17" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
                <path d="M17 7L7 17" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.2" />
            </svg>
        )
    }

    return <span className={`files-toolbar-glyph files-toolbar-glyph-${kind}`} aria-hidden="true" />
}

function FooterGlyph({ kind }: { kind: 'grid' | 'list' | 'hidden' }) {
    return <span className={`files-footer-glyph files-footer-glyph-${kind}`} aria-hidden="true" />
}

type InspectorState =
    | { mode: 'root' }
    | { mode: 'root-item'; item: FileManagerItem }
    | { mode: 'volume'; volume: FileManagerVolume }
    | { mode: 'item'; item: FileManagerItem }

type NavigationLocation = {
    volumeName: string
    path: string
}

function isSameLocation(left: NavigationLocation, right: NavigationLocation): boolean {
    return left.volumeName === right.volumeName && left.path === right.path
}

export function FilesPage() {
    const { t, i18n } = useTranslation('shell')
    const { status } = useProductAuth()
    const queryClient = useQueryClient()
    const [selectedVolume, setSelectedVolume] = useState('')
    const [selectedRootVolume, setSelectedRootVolume] = useState<FileManagerVolume | null>(null)
    const [selectedRootEntry, setSelectedRootEntry] = useState<FileManagerItem | null>(null)
    const [currentPath, setCurrentPath] = useState('/')
    const [selectedItem, setSelectedItem] = useState<FileManagerItem | null>(null)
    const [editorPath, setEditorPath] = useState<string | null>(null)
    const [editorContent, setEditorContent] = useState('')
    const [editorInitialContent, setEditorInitialContent] = useState('')
    const [dialogState, setDialogState] = useState<DialogState>(null)
    const [dialogValue, setDialogValue] = useState('')
    const [directorySearch, setDirectorySearch] = useState('')
    const [pathInputValue, setPathInputValue] = useState(VIRTUAL_VOLUMES_ROOT_PATH)
    const [pathSuggestions, setPathSuggestions] = useState<string[]>([])
    const [feedback, setFeedback] = useState<{ severity: 'success' | 'error' | 'info'; message: string } | null>(null)
    const [isActionSubmitting, setIsActionSubmitting] = useState(false)
    const [isEditorLoading, setIsEditorLoading] = useState(false)
    const [navigationHistory, setNavigationHistory] = useState<NavigationLocation[]>([{ volumeName: '', path: '/' }])
    const [navigationIndex, setNavigationIndex] = useState(0)
    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
    const [showHiddenFiles, setShowHiddenFiles] = useState(false)
    const uploadInputRef = useRef<HTMLInputElement | null>(null)

    const locale = i18n.resolvedLanguage === 'zh-CN' ? 'zh-CN' : 'en-US'
    const dateFormatter = useMemo(
        () =>
            new Intl.DateTimeFormat(locale, {
                dateStyle: 'medium',
                timeStyle: 'short',
            }),
        [locale],
    )

    const {
        data: volumeData,
        error: volumeError,
        isLoading: isVolumeLoading,
        isFetching: isVolumeFetching,
        refetch: refetchVolumes,
    } = useQuery<FileManagerVolumesResponse, Error>({
        queryKey: ['file-manager-volumes'],
        queryFn: () => requestJson<FileManagerVolumesResponse>('/api/files/volumes', { method: 'GET' }),
        enabled: Boolean(status?.enabled && status?.authenticated),
        staleTime: 10_000,
    })

    const volumes = volumeData?.volumes ?? []

    const {
        data: rootDirectoryData,
        error: rootDirectoryError,
        isLoading: isRootDirectoryLoading,
        isFetching: isRootDirectoryFetching,
        refetch: refetchRootDirectory,
    } = useQuery<FileManagerDirectoryResponse, Error>({
        queryKey: ['file-manager-root-tree', currentPath],
        queryFn: () =>
            currentPath === '/'
                ? requestJson<FileManagerDirectoryResponse>('/api/files/root-tree', { method: 'GET' })
                : requestJson<FileManagerDirectoryResponse>(
                    `/api/files/tree?volume_id=${encodeURIComponent(DOCKER_VOLUMES_ROOT_SENTINEL)}&path=${encodeURIComponent(currentPath)}`,
                    { method: 'GET' },
                ),
        enabled: Boolean(status?.enabled && status?.authenticated && !selectedVolume),
        staleTime: 0,
    })

    useEffect(() => {
        if (!volumes.length) {
            setSelectedVolume('')
            setSelectedRootVolume(null)
            return
        }

        if (selectedVolume && !volumes.some((volume) => volume.volume_name === selectedVolume)) {
            setSelectedVolume('')
            setCurrentPath('/')
        }

        if (selectedRootVolume && !volumes.some((volume) => volume.volume_name === selectedRootVolume.volume_name)) {
            setSelectedRootVolume(null)
        }
    }, [selectedRootVolume, selectedVolume, volumes])

    const {
        data: directoryData,
        error: directoryError,
        isLoading: isDirectoryLoading,
        isFetching: isDirectoryFetching,
        refetch: refetchDirectory,
    } = useQuery<FileManagerDirectoryResponse, Error>({
        queryKey: ['file-manager-tree', selectedVolume, currentPath],
        queryFn: () =>
            requestJson<FileManagerDirectoryResponse>(
                `/api/files/tree?volume_id=${encodeURIComponent(selectedVolume)}&path=${encodeURIComponent(currentPath)}`,
                { method: 'GET' },
            ),
        enabled: Boolean(status?.enabled && status?.authenticated && selectedVolume),
        staleTime: 0,
    })

    useEffect(() => {
        setSelectedItem(null)
        setEditorPath(null)
        setEditorContent('')
        setEditorInitialContent('')
        setDirectorySearch('')
        if (selectedVolume || currentPath !== '/') {
            setSelectedRootEntry(null)
        }
    }, [selectedVolume, currentPath])

    const isVolumeRoot = !selectedVolume
    const isRootHome = !selectedVolume && currentPath === '/'
    const rootItems = rootDirectoryData?.items ?? []
    const volumeItems = directoryData?.items ?? []
    const items = selectedVolume ? volumeItems : isRootHome ? [] : rootItems
    const currentDirectoryEntries = selectedVolume ? volumeItems : rootItems
    const isEditing = editorPath !== null
    const editorDirty = editorPath !== null && editorContent !== editorInitialContent
    const selectedItemPath = selectedItem?.path ?? selectedRootEntry?.path ?? editorPath ?? null
    const browserPathLabel = buildVirtualPath(selectedVolume, currentPath)
    const activeVolumeId = selectedVolume || DOCKER_VOLUMES_ROOT_SENTINEL

    useEffect(() => {
        setPathInputValue(browserPathLabel)
    }, [browserPathLabel])

    useEffect(() => {
        const normalizedInput = pathInputValue.trim()
        const volumeNames = volumes.map((volume) => volume.volume_name)
        if (!normalizedInput.startsWith(VIRTUAL_VOLUMES_ROOT_PATH)) {
            setPathSuggestions([])
            return
        }

        const normalizedPath = normalizedInput.replace(/\/+$/, '') || VIRTUAL_VOLUMES_ROOT_PATH
        const lastSlashIndex = normalizedPath.lastIndexOf('/')
        const parentAbsolutePath =
            normalizedInput.endsWith('/') || normalizedPath === VIRTUAL_VOLUMES_ROOT_PATH
                ? normalizedPath
                : normalizedPath.slice(0, lastSlashIndex)
        const partialName =
            normalizedInput.endsWith('/') || normalizedPath === VIRTUAL_VOLUMES_ROOT_PATH
                ? ''
                : normalizedPath.slice(lastSlashIndex + 1).toLowerCase()
        const parsedParentPath = parseBrowserPath(parentAbsolutePath, volumeNames)
        if (!parsedParentPath) {
            setPathSuggestions([])
            return
        }

        let cancelled = false
        const timeoutId = window.setTimeout(() => {
            void (async () => {
                try {
                    const suggestionEntries = isSameLocation(parsedParentPath, { volumeName: selectedVolume, path: currentPath })
                        ? currentDirectoryEntries
                        : (
                            await requestJson<FileManagerDirectoryResponse>(
                                `/api/files/tree?volume_id=${encodeURIComponent(parsedParentPath.volumeName || DOCKER_VOLUMES_ROOT_SENTINEL)}&path=${encodeURIComponent(parsedParentPath.path)}`,
                                { method: 'GET' },
                            )
                        ).items

                    if (cancelled) {
                        return
                    }

                    setPathSuggestions(
                        suggestionEntries
                            .filter((item) => item.item_type === 'directory')
                            .filter((item) => !partialName || item.name.toLowerCase().includes(partialName))
                            .map((item) => buildVirtualPath(parsedParentPath.volumeName, item.path))
                            .slice(0, 12),
                    )
                } catch {
                    if (!cancelled) {
                        setPathSuggestions([])
                    }
                }
            })()
        }, 120)

        return () => {
            cancelled = true
            window.clearTimeout(timeoutId)
        }
    }, [currentDirectoryEntries, currentPath, pathInputValue, selectedVolume, volumes])

    useEffect(() => {
        if (!selectedItem) {
            return
        }

        const itemStillExists = items.some((item) => item.path === selectedItem.path)
        if (!itemStillExists) {
            setSelectedItem(null)
            if (editorPath === selectedItem.path) {
                setEditorPath(null)
                setEditorContent('')
                setEditorInitialContent('')
            }
        }
    }, [editorPath, items, selectedItem])

    const filteredRootEntries = useMemo(() => {
        const normalized = directorySearch.trim().toLowerCase()
        const visibleItems = showHiddenFiles ? rootItems : rootItems.filter((item) => !item.name.startsWith('.'))
        const matchedItems = !normalized
            ? visibleItems
            : visibleItems.filter(
                (item) =>
                    item.name.toLowerCase().includes(normalized) ||
                    item.path.toLowerCase().includes(normalized) ||
                    (item.owner ?? '').toLowerCase().includes(normalized),
            )

        return [...matchedItems].sort((left, right) => {
            if (left.item_type !== right.item_type) {
                return left.item_type === 'directory' ? -1 : 1
            }

            return left.name.localeCompare(right.name, undefined, { sensitivity: 'base' })
        })
    }, [directorySearch, rootItems, showHiddenFiles])

    const filteredItemEntries = useMemo(() => {
        const normalized = directorySearch.trim().toLowerCase()
        const visibleItems = showHiddenFiles ? items : items.filter((item) => !item.name.startsWith('.'))
        const matchedItems = !normalized
            ? visibleItems
            : visibleItems.filter((item) => item.name.toLowerCase().includes(normalized) || item.path.toLowerCase().includes(normalized))

        return [...matchedItems].sort((left, right) => {
            if (left.item_type !== right.item_type) {
                return left.item_type === 'directory' ? -1 : 1
            }

            return left.name.localeCompare(right.name, undefined, { sensitivity: 'base' })
        })
    }, [directorySearch, items, showHiddenFiles])

    useEffect(() => {
        if (!selectedRootEntry) {
            return
        }

        const entryStillExists = isRootHome && rootItems.some((item) => item.path === selectedRootEntry.path)
        if (!entryStillExists) {
            setSelectedRootEntry(null)
            setSelectedRootVolume(null)
        }
    }, [isRootHome, rootItems, selectedRootEntry])

    const inspectorState: InspectorState = selectedItem
        ? { mode: 'item', item: selectedItem }
        : selectedVolume
            ? {
                mode: 'volume',
                volume:
                    volumes.find((volume) => volume.volume_name === selectedVolume) ?? {
                        volume_name: selectedVolume,
                        driver: 'local',
                    },
            }
            : selectedRootEntry
                ? { mode: 'root-item', item: selectedRootEntry }
                : { mode: 'root' }

    const metadataVolumeId =
        inspectorState.mode === 'item'
            ? activeVolumeId
            : inspectorState.mode === 'volume'
                ? selectedVolume || inspectorState.volume.volume_name
                : inspectorState.mode === 'root-item'
                    ? DOCKER_VOLUMES_ROOT_SENTINEL
                    : !isRootHome
                        ? DOCKER_VOLUMES_ROOT_SENTINEL
                        : ''
    const metadataPath =
        inspectorState.mode === 'item'
            ? inspectorState.item.path
            : inspectorState.mode === 'volume'
                ? selectedVolume
                    ? currentPath
                    : '/'
                : inspectorState.mode === 'root-item'
                    ? inspectorState.item.path
                    : !isRootHome
                        ? currentPath
                        : ''

    const fetchMetadata = (volumeId: string, path: string) =>
        requestJson<FileManagerMetadataResponse>(
            `/api/files/metadata?volume_id=${encodeURIComponent(volumeId)}&path=${encodeURIComponent(path)}`,
            { method: 'GET' },
        )

    function prefetchMetadata(volumeId: string, path: string) {
        if (!status?.enabled || !status?.authenticated || !volumeId) {
            return
        }

        void queryClient.prefetchQuery({
            queryKey: ['file-manager-metadata', volumeId, path],
            queryFn: () => fetchMetadata(volumeId, path),
            staleTime: 15_000,
        })
    }

    async function refreshMetadata(volumeId: string, path: string) {
        if (!status?.enabled || !status?.authenticated || !volumeId) {
            return
        }

        await queryClient.fetchQuery({
            queryKey: ['file-manager-metadata', volumeId, path],
            queryFn: () => fetchMetadata(volumeId, path),
            staleTime: 0,
        })
    }

    const { data: metadataResponse } = useQuery<FileManagerMetadataResponse, Error>({
        queryKey: ['file-manager-metadata', metadataVolumeId, metadataPath],
        queryFn: () => fetchMetadata(metadataVolumeId, metadataPath),
        enabled: Boolean(status?.enabled && status?.authenticated && metadataVolumeId),
        staleTime: 15_000,
    })

    function applyLocation(nextLocation: NavigationLocation, recordHistory = true) {
        setSelectedVolume(nextLocation.volumeName)
        setCurrentPath(nextLocation.path)

        if (nextLocation.volumeName) {
            const matchedVolume = volumes.find((volume) => volume.volume_name === nextLocation.volumeName) ?? null
            setSelectedRootVolume(matchedVolume)
        } else if (nextLocation.path === '/') {
            setSelectedRootVolume(null)
        } else {
            setSelectedRootVolume(null)
        }

        if (!recordHistory) {
            return
        }

        setNavigationHistory((previous) => {
            const current = previous[navigationIndex] ?? { volumeName: '', path: '/' }
            if (isSameLocation(current, nextLocation)) {
                return previous
            }

            const nextHistory = previous.slice(0, navigationIndex + 1)
            nextHistory.push(nextLocation)
            setNavigationIndex(nextHistory.length - 1)
            return nextHistory
        })
    }

    function clearEditorState(clearSelection = true) {
        setEditorPath(null)
        setEditorContent('')
        setEditorInitialContent('')
        if (clearSelection) {
            setSelectedItem(null)
            setSelectedRootEntry(null)
            setSelectedRootVolume(null)
        }
    }

    async function loadEditorFile(volumeId: string, item: FileManagerItem) {
        if (!item.text_editable) {
            setEditorPath(null)
            setEditorContent('')
            setEditorInitialContent('')
            setFeedback({ severity: 'info', message: t('filesPage.feedback.inlinePreviewUnavailable', { name: item.name }) })
            return
        }

        setIsEditorLoading(true)
        try {
            const response = await requestJson<FileManagerTextFileResponse>(
                `/api/files/content?volume_id=${encodeURIComponent(volumeId)}&path=${encodeURIComponent(item.path)}`,
                { method: 'GET' },
            )
            setEditorPath(response.path)
            setEditorContent(response.content)
            setEditorInitialContent(response.content)
        } catch (error) {
            setEditorPath(null)
            setEditorContent('')
            setEditorInitialContent('')
            setFeedback({
                severity: 'error',
                message:
                    error instanceof Error
                        ? normalizeActionErrorMessage(error.message, t, item.name)
                        : t('filesPage.feedback.genericError'),
            })
        } finally {
            setIsEditorLoading(false)
        }
    }

    async function openRootEntry(item: FileManagerItem, matchedVolume: FileManagerVolume | null = null) {
        setSelectedRootEntry(item)
        setSelectedRootVolume(matchedVolume)

        if (item.item_type === 'directory') {
            applyLocation({ volumeName: '', path: item.path })
            return
        }

        await loadEditorFile(DOCKER_VOLUMES_ROOT_SENTINEL, item)
    }

    async function openFile(item: FileManagerItem) {
        setSelectedItem(item)
        if (item.item_type === 'directory') {
            applyLocation({ volumeName: selectedVolume, path: item.path })
            return
        }

        await loadEditorFile(activeVolumeId, item)
    }

    async function handleSaveEditor() {
        if (!editorPath) {
            return
        }

        setIsActionSubmitting(true)
        try {
            await requestJson('/api/files/content', {
                method: 'PUT',
                body: JSON.stringify({ volume_id: activeVolumeId, path: editorPath, content: editorContent }),
            })
            clearEditorState(true)
            setFeedback({ severity: 'success', message: t('filesPage.feedback.saveSuccess') })
            if (selectedVolume) {
                await refetchDirectory()
            } else {
                await refetchRootDirectory()
            }
        } catch (error) {
            setFeedback({ severity: 'error', message: error instanceof Error ? error.message : t('filesPage.feedback.genericError') })
        } finally {
            setIsActionSubmitting(false)
        }
    }

    async function handleDownloadItem(item: FileManagerItem, volumeId: string) {
        setIsActionSubmitting(true)
        try {
            const response = await fetch(`/api/files/download?volume_id=${encodeURIComponent(volumeId)}&path=${encodeURIComponent(item.path)}`, {
                method: 'GET',
                credentials: 'include',
            })

            if (!response.ok) {
                let message = `HTTP ${response.status}`
                try {
                    const payload = (await response.json()) as { details?: string; message?: string }
                    message = payload.details ?? payload.message ?? message
                } catch {
                    // Keep the HTTP fallback when the download endpoint returns binary or empty payloads.
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
            setFeedback({ severity: 'error', message: error instanceof Error ? error.message : t('filesPage.feedback.genericError') })
        } finally {
            setIsActionSubmitting(false)
        }
    }

    function openActionDialog(nextState: DialogState) {
        setDialogState(nextState)
        if (!nextState) {
            setDialogValue('')
            return
        }
        if (nextState.type === 'rename') {
            setDialogValue(nextState.item.name)
            return
        }
        setDialogValue('')
    }

    async function submitDialogAction() {
        if (!dialogState) {
            return
        }

        const trimmedValue = dialogValue.trim()
        const duplicateTarget = currentDirectoryEntries.find((item) => {
            if (dialogState.type === 'rename' && item.path === dialogState.item.path) {
                return false
            }

            return item.name.localeCompare(trimmedValue, undefined, { sensitivity: 'accent' }) === 0
        })

        if ((dialogState.type === 'create-folder' || dialogState.type === 'create-file' || dialogState.type === 'rename') && trimmedValue && duplicateTarget) {
            setFeedback({ severity: 'error', message: t('filesPage.feedback.nameExists', { name: trimmedValue }) })
            return
        }

        const actionVolumeId =
            dialogState.type === 'create-folder' || dialogState.type === 'create-file'
                ? activeVolumeId
                : dialogState.type === 'delete-volume'
                    ? dialogState.volume.volume_name
                    : selectedVolume || selectedRootVolume?.volume_name || DOCKER_VOLUMES_ROOT_SENTINEL
        if (!actionVolumeId) {
            return
        }

        setIsActionSubmitting(true)
        try {
            if (dialogState.type === 'create-folder') {
                await requestJson('/api/files/folders', {
                    method: 'POST',
                    body: JSON.stringify({ volume_id: actionVolumeId, parent_path: dialogState.parentPath, name: trimmedValue }),
                })
                setFeedback({ severity: 'success', message: t('filesPage.feedback.createFolderSuccess', { name: trimmedValue }) })
            }

            if (dialogState.type === 'create-file') {
                await requestJson('/api/files/items', {
                    method: 'POST',
                    body: JSON.stringify({ volume_id: actionVolumeId, parent_path: dialogState.parentPath, name: trimmedValue }),
                })
                setFeedback({ severity: 'success', message: t('filesPage.feedback.createFileSuccess', { name: trimmedValue }) })
            }

            if (dialogState.type === 'rename') {
                const renamedPath = buildSiblingPath(dialogState.item.path, trimmedValue)
                await requestJson('/api/files/rename', {
                    method: 'POST',
                    body: JSON.stringify({ volume_id: actionVolumeId, source_path: dialogState.item.path, target_name: trimmedValue }),
                })
                setFeedback({ severity: 'success', message: t('filesPage.feedback.renameSuccess', { name: trimmedValue }) })
                if (selectedItem?.path === dialogState.item.path) {
                    setSelectedItem({ ...dialogState.item, name: trimmedValue, path: renamedPath })
                }
                if (selectedRootEntry?.path === dialogState.item.path) {
                    setSelectedRootEntry({ ...dialogState.item, name: trimmedValue, path: renamedPath })
                }
                if (editorPath === dialogState.item.path) {
                    setEditorPath(renamedPath)
                }
            }

            if (dialogState.type === 'delete') {
                await requestJson('/api/files/item', {
                    method: 'DELETE',
                    body: JSON.stringify({ volume_id: actionVolumeId, path: dialogState.item.path }),
                })
                setFeedback({ severity: 'success', message: t('filesPage.feedback.deleteSuccess', { name: dialogState.item.name }) })
                if (selectedItem?.path === dialogState.item.path) {
                    setSelectedItem(null)
                }
                if (selectedRootEntry?.path === dialogState.item.path) {
                    setSelectedRootEntry(null)
                }
                if (editorPath === dialogState.item.path) {
                    setEditorPath(null)
                    setEditorContent('')
                    setEditorInitialContent('')
                }
            }

            if (dialogState.type === 'delete-volume') {
                await requestJson('/api/files/item', {
                    method: 'DELETE',
                    body: JSON.stringify({ volume_id: dialogState.volume.volume_name, path: '/' }),
                })
                setFeedback({ severity: 'success', message: t('filesPage.feedback.deleteSuccess', { name: dialogState.volume.volume_name }) })
                if (selectedRootVolume?.volume_name === dialogState.volume.volume_name) {
                    setSelectedRootVolume(null)
                }
            }

            openActionDialog(null)
            if (dialogState.type === 'delete-volume') {
                await refetchVolumes()
            } else {
                if (selectedVolume) {
                    await refetchDirectory()
                } else {
                    await refetchRootDirectory()
                }
            }
        } catch (error) {
            setFeedback({
                severity: 'error',
                message:
                    error instanceof Error
                        ? normalizeActionErrorMessage(error.message, t, dialogValue.trim())
                        : t('filesPage.feedback.genericError'),
            })
        } finally {
            setIsActionSubmitting(false)
        }
    }

    async function handleUploadChange(event: ChangeEvent<HTMLInputElement>) {
        const file = event.target.files?.[0]
        const actionVolumeId = activeVolumeId
        const actionParentPath = currentPath
        if (!file || !actionVolumeId) {
            return
        }

        const duplicateEntry = currentDirectoryEntries.find((item) => item.name === file.name)
        const contentBase64 = await fileToBase64(file)
        if (duplicateEntry) {
            if (duplicateEntry.item_type !== 'file') {
                setFeedback({ severity: 'error', message: t('filesPage.feedback.nameExists', { name: file.name }) })
                if (uploadInputRef.current) {
                    uploadInputRef.current.value = ''
                }
                return
            }

            openActionDialog({ type: 'overwrite-upload', fileName: file.name, contentBase64 })
            return
        }

        setIsActionSubmitting(true)
        try {
            await requestJson('/api/files/upload', {
                method: 'POST',
                body: JSON.stringify({
                    volume_id: actionVolumeId,
                    parent_path: actionParentPath,
                    file_name: file.name,
                    content_base64: contentBase64,
                }),
            })
            setFeedback({ severity: 'success', message: t('filesPage.feedback.uploadSuccess', { name: file.name }) })
            if (selectedVolume) {
                await refetchDirectory()
            } else {
                await refetchRootDirectory()
            }
        } catch (error) {
            setFeedback({
                severity: 'error',
                message:
                    error instanceof Error
                        ? normalizeActionErrorMessage(error.message, t, file.name)
                        : t('filesPage.feedback.genericError'),
            })
        } finally {
            if (uploadInputRef.current) {
                uploadInputRef.current.value = ''
            }
            setIsActionSubmitting(false)
        }
    }

    function handleNavigateBack() {
        if (navigationIndex <= 0) {
            return
        }

        const nextIndex = navigationIndex - 1
        setNavigationIndex(nextIndex)
        applyLocation(navigationHistory[nextIndex], false)
    }

    function handleNavigateForward() {
        if (navigationIndex >= navigationHistory.length - 1) {
            return
        }

        const nextIndex = navigationIndex + 1
        setNavigationIndex(nextIndex)
        applyLocation(navigationHistory[nextIndex], false)
    }

    function handleNavigateUp() {
        if (!selectedVolume && currentPath === '/') {
            return
        }

        if (selectedVolume && currentPath === '/') {
            applyLocation({ volumeName: '', path: '/' })
            return
        }

        applyLocation({ volumeName: selectedVolume, path: parentPath(currentPath) })
    }

    function handleApplyPathInput() {
        const parsed = parseBrowserPath(pathInputValue, volumes.map((volume) => volume.volume_name))
        if (!parsed) {
            setPathInputValue(browserPathLabel)
            setFeedback({ severity: 'error', message: t('filesPage.feedback.invalidPath') })
            return
        }

        if (isSameLocation(parsed, { volumeName: selectedVolume, path: currentPath })) {
            setPathInputValue(browserPathLabel)
            return
        }

        applyLocation(parsed)
    }

    function handleRefresh() {
        if (isVolumeRoot) {
            void (async () => {
                await queryClient.invalidateQueries({ queryKey: ['file-manager-root-tree'] })
                void queryClient.invalidateQueries({ queryKey: ['file-manager-volumes'] })
                void refetchVolumes()
                await refetchRootDirectory()

                if (currentPath !== '/') {
                    await refreshMetadata(DOCKER_VOLUMES_ROOT_SENTINEL, currentPath)
                    return
                }

                if (!selectedRootVolume) {
                    return
                }

                if (selectedRootVolume) {
                    await refreshMetadata(selectedRootVolume.volume_name, '/')
                    return
                }
            })()
            return
        }

        void (async () => {
            await refetchDirectory()
            if (metadataVolumeId) {
                await refreshMetadata(metadataVolumeId, metadataPath)
            }
        })()
    }

    const dialogTitle =
        dialogState?.type === 'create-folder'
            ? t('filesPage.dialogs.createFolderTitle')
            : dialogState?.type === 'create-file'
                ? t('filesPage.dialogs.createFileTitle')
                : dialogState?.type === 'rename'
                    ? t('filesPage.dialogs.renameTitle')
                    : dialogState?.type === 'overwrite-upload'
                        ? t('filesPage.dialogs.overwriteTitle')
                        : dialogState?.type === 'delete' || dialogState?.type === 'delete-volume'
                            ? t('filesPage.dialogs.deleteTitle')
                            : ''

    const dialogConfirmLabel =
        dialogState?.type === 'create-folder'
            ? t('filesPage.actions.createFolder')
            : dialogState?.type === 'create-file'
                ? t('filesPage.actions.createFile')
                : dialogState?.type === 'rename'
                    ? t('filesPage.actions.rename')
                    : dialogState?.type === 'overwrite-upload'
                        ? t('filesPage.actions.overwrite')
                        : t('filesPage.actions.delete')

    let inspectorTitle = '—'
    let inspectorMode = '—'
    let inspectorOwner = '—'
    let inspectorGroup = '—'
    let inspectorSize = '—'
    let inspectorAccessed = '—'
    let inspectorModified = '—'
    let inspectorCreated = '—'
    const inspectorItem = inspectorState.mode === 'item' ? inspectorState.item : null
    const currentDirectoryName = currentPath === '/' ? selectedVolume : currentPath.split('/').filter(Boolean).at(-1) ?? selectedVolume
    const selectedVolumeEntry = !selectedVolume && inspectorState.mode === 'volume' ? inspectorState.volume : null
    const canDeleteRootVolume = false
    const canDeleteSelectedItem = (inspectorState.mode === 'item' || Boolean(selectedVolumeEntry) || Boolean(inspectorState.mode === 'root-item')) && !isEditing
    const canRenameSelectedItem = (inspectorState.mode === 'item' || inspectorState.mode === 'root-item') && !isEditing
    const editableInspectorItem =
        inspectorState.mode === 'item' || inspectorState.mode === 'root-item'
            ? inspectorState.item
            : null
    const canEditSelectedItem = Boolean(editableInspectorItem && editableInspectorItem.item_type === 'file' && editableInspectorItem.text_editable) && !isEditing
    const canDownloadSelectedItem = Boolean(editableInspectorItem && editableInspectorItem.item_type === 'file') && !isEditing
    const inspectorRootItem = inspectorState.mode === 'root-item' ? inspectorState.item : null
    const visibleDirectoryCount = filteredItemEntries.filter((item) => item.item_type === 'directory').length
    const visibleFileCount = filteredItemEntries.filter((item) => item.item_type === 'file').length
    const visibleFileSize = filteredItemEntries.filter((item) => item.item_type === 'file').reduce((total, item) => total + item.size, 0)
    const inspectorItemImmediateSize = inspectorItem ? formatSize(inspectorItem.size, t) : '—'
    const showInspectorPlaceholder = false

    if (rootDirectoryData?.metadata) {
        inspectorTitle = rootDirectoryData.metadata.name
        inspectorMode = rootDirectoryData.metadata.mode ?? '—'
        inspectorOwner = formatIdentity(rootDirectoryData.metadata.owner)
        inspectorGroup = formatIdentity(rootDirectoryData.metadata.group)
        inspectorSize = formatSize(rootDirectoryData.metadata.size, t)
        inspectorAccessed = formatDate(rootDirectoryData.metadata.accessed_at, dateFormatter)
        inspectorModified = formatDate(rootDirectoryData.metadata.modified_at, dateFormatter)
        inspectorCreated = formatDate(rootDirectoryData.metadata.created_at, dateFormatter)
    }

    if (directoryData?.metadata && selectedVolume && !inspectorItem) {
        inspectorTitle = directoryData.metadata.name
        inspectorMode = directoryData.metadata.mode ?? inspectorMode
        inspectorOwner = formatIdentity(directoryData.metadata.owner) ?? inspectorOwner
        inspectorGroup = formatIdentity(directoryData.metadata.group) ?? inspectorGroup
        inspectorSize = formatSize(directoryData.metadata.size, t)
        inspectorAccessed = formatDate(directoryData.metadata.accessed_at, dateFormatter)
        inspectorModified = formatDate(directoryData.metadata.modified_at, dateFormatter)
        inspectorCreated = formatDate(directoryData.metadata.created_at, dateFormatter)
    }

    if (inspectorRootItem) {
        inspectorTitle = inspectorRootItem.name
        inspectorMode = inspectorRootItem.mode ?? inspectorMode
        inspectorOwner = formatIdentity(inspectorRootItem.owner) ?? inspectorOwner
        inspectorGroup = formatIdentity(inspectorRootItem.group) ?? inspectorGroup
        inspectorSize = formatSize(inspectorRootItem.size, t)
        inspectorAccessed = formatDate(inspectorRootItem.accessed_at, dateFormatter)
        inspectorModified = formatDate(inspectorRootItem.modified_at, dateFormatter)
        inspectorCreated = formatDate(inspectorRootItem.created_at, dateFormatter)
    }

    if (metadataResponse) {
        inspectorTitle = metadataResponse.name
        inspectorMode = metadataResponse.mode ?? '—'
        inspectorOwner = formatIdentity(metadataResponse.owner)
        inspectorGroup = formatIdentity(metadataResponse.group)
        inspectorSize = formatSize(metadataResponse.size, t)
        inspectorAccessed = formatDate(metadataResponse.accessed_at, dateFormatter)
        inspectorModified = formatDate(metadataResponse.modified_at, dateFormatter)
        inspectorCreated = formatDate(metadataResponse.created_at, dateFormatter)
    }

    if (inspectorState.mode === 'volume' && !metadataResponse) {
        inspectorTitle = inspectorState.volume.volume_name
        inspectorOwner = formatIdentity(inspectorState.volume.owner)
        if (selectedRootEntry && selectedRootVolume?.volume_name === inspectorState.volume.volume_name) {
            inspectorMode = selectedRootEntry.mode ?? inspectorMode
            inspectorGroup = formatIdentity(selectedRootEntry.group) ?? inspectorGroup
            inspectorAccessed = formatDate(selectedRootEntry.accessed_at, dateFormatter)
            inspectorModified = formatDate(selectedRootEntry.modified_at, dateFormatter)
            inspectorCreated = formatDate(selectedRootEntry.created_at, dateFormatter)
        }
    }

    if ((selectedVolume || currentPath !== '/') && !inspectorItem && !inspectorRootItem) {
        inspectorTitle = currentDirectoryName
    }

    if (inspectorItem) {
        inspectorTitle = inspectorItem.name
        inspectorMode = inspectorItem.mode ?? inspectorMode
        inspectorOwner = formatIdentity(inspectorItem.owner) ?? inspectorOwner
        inspectorGroup = formatIdentity(inspectorItem.group) ?? inspectorGroup
        inspectorSize = inspectorItemImmediateSize !== '—' ? inspectorItemImmediateSize : inspectorSize
        inspectorAccessed = formatDate(inspectorItem.accessed_at, dateFormatter)
        inspectorModified = formatDate(inspectorItem.modified_at, dateFormatter)
        inspectorCreated = formatDate(inspectorItem.created_at, dateFormatter)
    }

    const inspectorRows = [
        { label: t('filesPage.metadata.mode'), value: inspectorMode },
        { label: t('filesPage.metadata.owner'), value: inspectorOwner },
        { label: t('filesPage.metadata.group'), value: inspectorGroup },
        { label: t('filesPage.table.size'), value: inspectorSize },
        { label: t('filesPage.metadata.accessed'), value: inspectorAccessed },
        { label: t('filesPage.metadata.modified'), value: inspectorModified },
        { label: t('filesPage.metadata.created'), value: inspectorCreated },
    ]

    return (
        <Box className="files-page" sx={{ px: { xs: 0.25, md: 0.5 }, py: { xs: 0.5, md: 0.75 } }}>
            <Stack spacing={0.5} className="files-shell">
                {!status?.enabled ? <Alert severity="info">{t('filesPage.states.authDisabled')}</Alert> : null}

                <Paper className="files-shell-toolbar" elevation={0}>
                    <div className="files-toolbar-row files-toolbar-row-classic files-toolbar-row-shell">
                        <div className="files-toolbar-group">
                            <IconButton className="files-toolbar-button" disabled={navigationIndex <= 0} onClick={handleNavigateBack} size="small" title={t('filesPage.actions.back')}>
                                <ToolbarGlyph kind="back" />
                            </IconButton>
                            <IconButton className="files-toolbar-button" disabled={navigationIndex >= navigationHistory.length - 1} onClick={handleNavigateForward} size="small" title={t('filesPage.actions.forward')}>
                                <ToolbarGlyph kind="forward" />
                            </IconButton>
                            <IconButton className="files-toolbar-button" disabled={navigationIndex <= 0 && !selectedVolume} onClick={handleNavigateUp} size="small" title={t('filesPage.actions.up')}>
                                <ToolbarGlyph kind="up" />
                            </IconButton>
                            <IconButton className="files-toolbar-button files-toolbar-button-primary" disabled={(isVolumeRoot ? isRootDirectoryFetching : isDirectoryFetching) || isVolumeLoading} onClick={handleRefresh} size="small" title={t('filesPage.states.retry')}>
                                <ToolbarGlyph kind="refresh" />
                            </IconButton>
                        </div>

                        <div className="files-toolbar-paths">
                            <TextField
                                size="small"
                                value={pathInputValue}
                                onChange={(event) => setPathInputValue(event.target.value)}
                                onBlur={() => setPathInputValue(browserPathLabel)}
                                onKeyDown={(event) => {
                                    if (event.key === 'Enter') {
                                        event.preventDefault()
                                        handleApplyPathInput()
                                    }
                                }}
                                className="files-path-input files-path-input-classic"
                                placeholder={t('filesPage.filters.pathLabel')}
                                slotProps={{ htmlInput: { list: 'files-path-suggestions' } }}
                            />
                            <datalist id="files-path-suggestions">
                                {pathSuggestions.map((suggestion) => (
                                    <option key={suggestion} value={suggestion} />
                                ))}
                            </datalist>
                            <TextField
                                size="small"
                                value={directorySearch}
                                onChange={(event) => setDirectorySearch(event.target.value)}
                                className="files-search-input files-search-input-classic"
                                placeholder={t('filesPage.filters.searchPlaceholder')}
                                slotProps={{ input: { endAdornment: <ToolbarGlyph kind="search" /> } }}
                            />
                        </div>

                        <div className="files-toolbar-group files-toolbar-group-actions">
                            <IconButton className="files-toolbar-button files-toolbar-button-primary" disabled={isActionSubmitting} onClick={() => openActionDialog({ type: 'create-folder', parentPath: currentPath })} size="small" title={t('filesPage.actions.createFolder')}>
                                <ToolbarGlyph kind="folder" />
                            </IconButton>
                            <IconButton className="files-toolbar-button files-toolbar-button-primary" disabled={isActionSubmitting} onClick={() => openActionDialog({ type: 'create-file', parentPath: currentPath })} size="small" title={t('filesPage.actions.createFile')}>
                                <ToolbarGlyph kind="file" />
                            </IconButton>
                            <IconButton className="files-toolbar-button files-toolbar-button-primary" disabled={isActionSubmitting} onClick={() => uploadInputRef.current?.click()} size="small" title={t('filesPage.actions.upload')}>
                                <ToolbarGlyph kind="upload" />
                            </IconButton>
                            <input ref={uploadInputRef} hidden type="file" onChange={handleUploadChange} />
                        </div>
                    </div>
                </Paper>

                <div className="files-layout files-layout-classic">
                    <Paper className="files-panel files-browser-panel" elevation={0}>
                        {isVolumeRoot ? isRootDirectoryFetching || isVolumeFetching ? <LinearProgress /> : null : isDirectoryFetching ? <LinearProgress /> : null}

                        {isEditorLoading ? (
                            <div className="files-loading">
                                <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                                    <CircularProgress size={18} />
                                    <Typography variant="body2">{t('filesPage.editor.loading')}</Typography>
                                </Stack>
                            </div>
                        ) : editorPath ? (
                            <div className="files-browser-editor">
                                <div className="files-browser-editor-header">
                                    <div className="files-browser-editor-header-main">
                                        <div className="files-browser-editor-title files-truncate">
                                            {t('filesPage.editor.editing')} - {buildVirtualPath(selectedVolume, editorPath)}
                                        </div>
                                        <div className="files-editor-actions files-editor-actions-header">
                                            <button
                                                type="button"
                                                className="files-editor-action files-editor-action-close"
                                                onClick={() => {
                                                    clearEditorState(true)
                                                }}
                                                title={t('filesPage.actions.close')}
                                            >
                                                <ToolbarGlyph kind="close" />
                                            </button>
                                            <button
                                                type="button"
                                                className="files-editor-action files-editor-action-save"
                                                onClick={() => void handleSaveEditor()}
                                                disabled={!editorDirty || isActionSubmitting}
                                                title={t('filesPage.actions.save')}
                                            >
                                                <ToolbarGlyph kind="save" />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                                <div className="files-browser-editor-body">
                                    <TextField
                                        className="files-editor-textarea"
                                        fullWidth
                                        multiline
                                        placeholder={selectedItemPath ?? undefined}
                                        value={editorContent}
                                        slotProps={{ htmlInput: { wrap: 'off', spellCheck: false } }}
                                        onChange={(event) => setEditorContent(event.target.value)}
                                    />
                                </div>
                            </div>
                        ) : isVolumeLoading || (isVolumeRoot && isRootDirectoryLoading) ? (
                            <div className="files-loading">
                                <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                                    <CircularProgress size={18} />
                                    <Typography variant="body2">{t('filesPage.states.loadingVolumes')}</Typography>
                                </Stack>
                            </div>
                        ) : volumeError ? (
                            <div className="files-empty">
                                <Alert severity="error">{volumeError.message}</Alert>
                            </div>
                        ) : isVolumeRoot && rootDirectoryError ? (
                            <div className="files-empty">
                                <Alert severity="error">{rootDirectoryError.message}</Alert>
                            </div>
                        ) : !isVolumeRoot && isDirectoryLoading ? (
                            <div className="files-loading">
                                <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                                    <CircularProgress size={18} />
                                    <Typography variant="body2">{t('filesPage.states.loadingDirectory')}</Typography>
                                </Stack>
                            </div>
                        ) : !isVolumeRoot && directoryError ? (
                            <div className="files-empty">
                                <Alert severity="error">{directoryError.message}</Alert>
                            </div>
                        ) : (isRootHome ? filteredRootEntries.length : filteredItemEntries.length) === 0 ? (
                            <div className="files-empty">
                                <Typography color="text.secondary" variant="body2">
                                    {directorySearch ? t('filesPage.states.noSearchResults') : t('filesPage.states.empty')}
                                </Typography>
                            </div>
                        ) : viewMode === 'list' ? (
                            <div className="files-list-view">
                                <div className="files-list-body">
                                    <div className="files-list-header files-list-row-frame">
                                        <div>{t('filesPage.table.name')}</div>
                                        <div>{t('filesPage.metadata.mode')}</div>
                                        <div>{t('filesPage.metadata.owner')}</div>
                                        <div>{t('filesPage.metadata.group')}</div>
                                        <div>{t('filesPage.table.size')}</div>
                                        <div>{t('filesPage.metadata.modified')}</div>
                                        <div>{t('filesPage.metadata.created')}</div>
                                    </div>
                                    {isRootHome
                                        ? filteredRootEntries.map((item) => {
                                            const isSelected = selectedRootEntry?.path === item.path
                                            return (
                                                <button
                                                    key={item.path}
                                                    type="button"
                                                    className={`files-list-row files-list-row-frame ${isSelected ? 'files-list-row-selected' : ''}`}
                                                    onClick={() => {
                                                        setSelectedRootEntry(item)
                                                        setSelectedRootVolume(null)
                                                    }}
                                                    onDoubleClick={() => void openRootEntry(item)}
                                                >
                                                    <div className="files-list-name">
                                                        <span className={item.item_type === 'directory' ? 'files-list-folder-dot' : 'files-list-file-dot'} />
                                                        <span className="files-truncate">{item.name}</span>
                                                    </div>
                                                    <div>{item.mode ?? '—'}</div>
                                                    <div>{item.owner ?? '—'}</div>
                                                    <div>{item.group ?? '—'}</div>
                                                    <div>{item.item_type === 'file' ? formatSize(item.size, t) : '—'}</div>
                                                    <div>{formatDate(item.modified_at, dateFormatter)}</div>
                                                    <div>{formatDate(item.created_at, dateFormatter)}</div>
                                                </button>
                                            )
                                        })
                                        : filteredItemEntries.map((item) => {
                                            const isSelected = selectedItem?.path === item.path
                                            return (
                                                <button
                                                    key={item.path}
                                                    type="button"
                                                    className={`files-list-row files-list-row-frame ${isSelected ? 'files-list-row-selected' : ''}`}
                                                    onClick={() => {
                                                        setSelectedItem(item)
                                                    }}
                                                    onDoubleClick={() => void openFile(item)}
                                                >
                                                    <div className="files-list-name">
                                                        <span className={item.item_type === 'directory' ? 'files-list-folder-dot' : 'files-list-file-dot'} />
                                                        <span className="files-truncate">{item.name}</span>
                                                    </div>
                                                    <div>{item.mode ?? '—'}</div>
                                                    <div>{item.owner ?? '—'}</div>
                                                    <div>{item.group ?? '—'}</div>
                                                    <div>{item.item_type === 'file' ? formatSize(item.size, t) : '—'}</div>
                                                    <div>{formatDate(item.modified_at, dateFormatter)}</div>
                                                    <div>{formatDate(item.created_at, dateFormatter)}</div>
                                                </button>
                                            )
                                        })}
                                </div>
                            </div>
                        ) : (
                            <div className="files-card-grid files-card-grid-classic files-card-grid-overview">
                                {isRootHome
                                    ? filteredRootEntries.map((item) => {
                                        const isSelected = selectedRootEntry?.path === item.path
                                        return (
                                            <button
                                                key={item.path}
                                                type="button"
                                                className="files-card files-card-classic"
                                                onClick={() => {
                                                    setSelectedRootEntry(item)
                                                    setSelectedRootVolume(null)
                                                }}
                                                onDoubleClick={() => void openRootEntry(item)}
                                            >
                                                <div className={`files-card-hitbox ${isSelected ? 'files-card-hitbox-selected' : ''}`}>
                                                    <div className={`files-card-visual files-card-visual-${item.item_type}`} />
                                                    <div className="files-card-body">
                                                        <div className="files-card-title">{item.name}</div>
                                                    </div>
                                                </div>
                                            </button>
                                        )
                                    })
                                    : filteredItemEntries.map((item) => {
                                        const isSelected = selectedItem?.path === item.path
                                        return (
                                            <button
                                                key={item.path}
                                                type="button"
                                                className="files-card files-card-classic"
                                                onClick={() => {
                                                    setSelectedItem(item)
                                                    prefetchMetadata(activeVolumeId, item.path)
                                                }}
                                                onDoubleClick={() => void openFile(item)}
                                                onFocus={() => prefetchMetadata(activeVolumeId, item.path)}
                                                onMouseEnter={() => prefetchMetadata(activeVolumeId, item.path)}
                                            >
                                                <div className={`files-card-hitbox ${isSelected ? 'files-card-hitbox-selected' : ''}`}>
                                                    <div className={`files-card-visual files-card-visual-${item.item_type}`} />
                                                    <div className="files-card-body">
                                                        <div className="files-card-title">{item.name}</div>
                                                    </div>
                                                </div>
                                            </button>
                                        )
                                    })}
                            </div>
                        )}
                    </Paper>

                    <Paper className="files-panel files-editor-panel" elevation={0}>
                        <div className="files-editor-header files-editor-header-classic">
                            <div className="files-inspector-header-main">
                                <div className="files-inspector-header-title files-truncate">{showInspectorPlaceholder ? t('filesPage.inspector.emptyTitle') : inspectorTitle}</div>
                                <div className="files-inspector-header-actions">
                                    <IconButton className="files-toolbar-button" disabled={!canRenameSelectedItem || isActionSubmitting} onClick={() => {
                                        if (inspectorState.mode === 'item' || inspectorState.mode === 'root-item') {
                                            openActionDialog({ type: 'rename', item: inspectorState.item })
                                        }
                                    }} size="small" title={t('filesPage.actions.rename')}>
                                        <ToolbarGlyph kind="rename" />
                                    </IconButton>
                                    <IconButton className="files-toolbar-button" disabled={!canDownloadSelectedItem || isActionSubmitting} onClick={() => {
                                        if (inspectorState.mode === 'item') {
                                            void handleDownloadItem(inspectorState.item, activeVolumeId)
                                        }
                                        if (inspectorState.mode === 'root-item') {
                                            void handleDownloadItem(inspectorState.item, DOCKER_VOLUMES_ROOT_SENTINEL)
                                        }
                                    }} size="small" title={t('filesPage.actions.download')}>
                                        <ToolbarGlyph kind="download" />
                                    </IconButton>
                                    <IconButton className="files-toolbar-button files-toolbar-button-danger" disabled={!canDeleteSelectedItem || isActionSubmitting} onClick={() => {
                                        if (inspectorState.mode === 'item') {
                                            openActionDialog({ type: 'delete', item: inspectorState.item })
                                            return
                                        }
                                        if (inspectorState.mode === 'root-item') {
                                            openActionDialog({ type: 'delete', item: inspectorState.item })
                                            return
                                        }
                                        if (canDeleteRootVolume && selectedRootVolume) {
                                            openActionDialog({ type: 'delete-volume', volume: selectedRootVolume })
                                            return
                                        }
                                        if (selectedVolumeEntry) {
                                            openActionDialog({ type: 'delete-volume', volume: selectedVolumeEntry })
                                        }
                                    }} size="small" title={t('filesPage.actions.delete')}>
                                        <ToolbarGlyph kind="trash" />
                                    </IconButton>
                                    <IconButton className="files-toolbar-button" disabled={!canEditSelectedItem || isActionSubmitting} onClick={() => {
                                        if (!canEditSelectedItem || !editableInspectorItem) {
                                            return
                                        }
                                        if (inspectorState.mode === 'root-item') {
                                            void openRootEntry(editableInspectorItem)
                                            return
                                        }
                                        void openFile(editableInspectorItem)
                                    }} size="small" title={t('filesPage.actions.edit')}>
                                        <ToolbarGlyph kind="edit" />
                                    </IconButton>
                                </div>
                            </div>
                        </div>

                        <div className="files-editor-body files-editor-body-classic">
                            <div className="files-inspector-card files-inspector-card-classic">
                                {showInspectorPlaceholder ? (
                                    <div className="files-inspector-empty">
                                        <Typography className="files-inspector-empty-title">{t('filesPage.inspector.emptyTitle')}</Typography>
                                        <Typography className="files-inspector-empty-body">{t('filesPage.inspector.emptyBody')}</Typography>
                                    </div>
                                ) : (
                                    <div className="files-inspector-rows files-inspector-rows-classic">
                                        {inspectorRows.map((row) => (
                                            <div key={row.label} className="files-inspector-row">
                                                <Typography className="files-inspector-label">{row.label}</Typography>
                                                <Typography className="files-inspector-value">{row.value}</Typography>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </Paper>
                </div>

                <Paper className="files-footer-panel" elevation={0}>
                    <div className="files-footer-bar">
                        <div className="files-footer-stats">
                            {isVolumeRoot
                                ? `${filteredRootEntries.filter((item) => item.item_type === 'directory').length} ${t('filesPage.footer.directories')}, ${filteredRootEntries.filter((item) => item.item_type === 'file').length} ${t('filesPage.footer.files')}`
                                : `${visibleDirectoryCount} ${t('filesPage.footer.directories')}, ${visibleFileCount} ${t('filesPage.footer.files')} (${formatSize(visibleFileSize, t)})`}
                        </div>
                        <div className="files-footer-actions">
                            <button
                                type="button"
                                className={`files-footer-button ${viewMode === 'list' ? 'files-footer-button-active' : ''}`}
                                onClick={() => setViewMode((current) => (current === 'grid' ? 'list' : 'grid'))}
                                title={t('filesPage.footer.listView')}
                            >
                                <FooterGlyph kind={viewMode === 'list' ? 'list' : 'grid'} />
                            </button>
                            <button
                                type="button"
                                className={`files-footer-toggle ${showHiddenFiles ? 'files-footer-toggle-active' : ''}`}
                                onClick={() => setShowHiddenFiles((current) => !current)}
                                title={t('filesPage.footer.showHidden')}
                            >
                                <FooterGlyph kind="hidden" />
                            </button>
                        </div>
                    </div>
                </Paper>
            </Stack>

            <Snackbar autoHideDuration={3000} onClose={() => setFeedback(null)} open={feedback !== null} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
                {feedback ? (
                    <Alert onClose={() => setFeedback(null)} severity={feedback.severity}>
                        {feedback.message}
                    </Alert>
                ) : (
                    <span />
                )}
            </Snackbar>

            {dialogState ? (
                <div className="files-local-dialog-backdrop" role="presentation" onClick={() => {
                    if (!isActionSubmitting) {
                        openActionDialog(null)
                    }
                }}>
                    <Paper
                        aria-modal="false"
                        className="files-local-dialog"
                        elevation={4}
                        role="dialog"
                        onClick={(event) => {
                            event.stopPropagation()
                        }}
                    >
                        <div className="files-local-dialog-header">
                            <Typography className="files-local-dialog-title">{dialogTitle}</Typography>
                        </div>
                        <div className="files-local-dialog-content">
                            {dialogState.type === 'delete' || dialogState.type === 'delete-volume' ? (
                                <Typography className="files-local-dialog-body" variant="body2">
                                    {dialogState.type === 'delete'
                                        ? t(selectedVolume ? 'filesPage.dialogs.deleteBody' : 'filesPage.dialogs.deleteRootBody', {
                                            name: dialogState.item.name,
                                        })
                                        : t('filesPage.dialogs.deleteVolumeBody', { name: dialogState.volume.volume_name })}
                                </Typography>
                            ) : dialogState.type === 'overwrite-upload' ? (
                                <Typography className="files-local-dialog-body" variant="body2">
                                    {t('filesPage.dialogs.overwriteBody', { name: dialogState.fileName })}
                                </Typography>
                            ) : (
                                <TextField
                                    autoFocus
                                    fullWidth
                                    label={t('filesPage.dialogs.nameField')}
                                    margin="dense"
                                    value={dialogValue}
                                    onChange={(event) => setDialogValue(event.target.value)}
                                />
                            )}
                        </div>
                        <div className="files-local-dialog-actions">
                            <Button disabled={isActionSubmitting} onClick={() => openActionDialog(null)}>{t('filesPage.dialogs.cancel')}</Button>
                            <Button
                                onClick={() => {
                                    if (dialogState.type === 'overwrite-upload') {
                                        setIsActionSubmitting(true)
                                        void requestJson('/api/files/upload', {
                                            method: 'POST',
                                            body: JSON.stringify({
                                                volume_id: activeVolumeId,
                                                parent_path: currentPath,
                                                file_name: dialogState.fileName,
                                                content_base64: dialogState.contentBase64,
                                            }),
                                        })
                                            .then(async () => {
                                                setFeedback({ severity: 'success', message: t('filesPage.feedback.uploadSuccess', { name: dialogState.fileName }) })
                                                openActionDialog(null)
                                                if (selectedVolume) {
                                                    await refetchDirectory()
                                                } else {
                                                    await refetchRootDirectory()
                                                }
                                            })
                                            .catch((error: unknown) => {
                                                setFeedback({
                                                    severity: 'error',
                                                    message:
                                                        error instanceof Error
                                                            ? normalizeActionErrorMessage(error.message, t, dialogState.fileName)
                                                            : t('filesPage.feedback.genericError'),
                                                })
                                            })
                                            .finally(() => {
                                                if (uploadInputRef.current) {
                                                    uploadInputRef.current.value = ''
                                                }
                                                setIsActionSubmitting(false)
                                            })
                                        return
                                    }

                                    void submitDialogAction()
                                }}
                                color={dialogState.type === 'delete' || dialogState.type === 'delete-volume' ? 'error' : 'primary'}
                                variant="contained"
                                disabled={isActionSubmitting || (!dialogState || dialogState.type === 'delete' || dialogState.type === 'delete-volume' || dialogState.type === 'overwrite-upload' ? false : !dialogValue.trim())}
                            >
                                {dialogConfirmLabel}
                            </Button>
                        </div>
                    </Paper>
                </div>
            ) : null}
        </Box>
    )
}