import {
    Alert,
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    DialogActions,
    DialogContent,
    DialogTitle,
    InputAdornment,
    IconButton,
    Snackbar,
    Stack,
    SvgIcon,
    TextField,
    MenuItem,
    Tooltip,
    Typography,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'

import { useAppColorMode } from '../../app/providers/color-mode'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { SurfaceStateCard } from '../../shared/design-system/standard-surfaces'
import { useProductAuth } from '../product-auth/product-auth-provider'
import './users-page.css'

type ProductAuthUser = {
    id: string
    username: string
    display_name: string
    email: string | null
    locale: string
    disabled: boolean
    deleted: boolean
    reset_password_eligible: boolean
    delete_eligible: boolean
    created_at: string
}

type ProductAuthUsersResponse = {
    users: ProductAuthUser[]
}

type UserDialogState =
    | { type: 'create' }
    | { type: 'edit'; user: ProductAuthUser }
    | { type: 'delete'; user: ProductAuthUser }
    | null

type ContentScopeRect = {
    top: number
    left: number
    width: number
    height: number
}

type UsersScopedOverlayProps = {
    open: boolean
    scopeRect: ContentScopeRect | null
    onClose: () => void
    darkMode: boolean
    maxWidth?: number
    children: ReactNode
}

type UserFieldErrors = Partial<Record<'username' | 'displayName' | 'email' | 'locale' | 'password' | 'confirmPassword', string>>

type UsersRouteState = {
    openCurrentUserEditor?: boolean
    profileDialogNonce?: number
}

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
    const response = await fetch(input, {
        credentials: 'include',
        headers: {
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

async function fetchUsers() {
    return requestJson<ProductAuthUsersResponse>('/api/auth/users', { method: 'GET' })
}

function RefreshIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M17.65 6.35A7.95 7.95 0 0 0 12 4a8 8 0 1 0 7.75 10h-2.08A6 6 0 1 1 12 6c1.3 0 2.5.42 3.47 1.13L13 10h7V3l-2.35 3.35Z" />
        </SvgIcon>
    )
}

function EditIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25Zm2.92 2.33H5v-.92l9.06-9.06.92.92-9.06 9.06ZM20.71 7.04a1 1 0 0 0 0-1.42l-2.34-2.33a1 1 0 0 0-1.41 0l-1.13 1.12 3.75 3.75 1.13-1.12Z" />
        </SvgIcon>
    )
}

function DisableUserIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M12 2a10 10 0 1 0 10 10A10.01 10.01 0 0 0 12 2Zm0 2a7.94 7.94 0 0 1 5.66 2.34L6.34 17.66A8 8 0 0 1 12 4Zm0 16a7.94 7.94 0 0 1-5.66-2.34L17.66 6.34A8 8 0 0 1 12 20Z" />
        </SvgIcon>
    )
}

function EnableUserIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="m9.55 18.2-5.2-5.2 1.41-1.41 3.79 3.79 8.69-8.68 1.41 1.41-10.1 10.09Z" />
        </SvgIcon>
    )
}

function DeleteIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M9 3h6l1 2h5v2H3V5h5l1-2Zm1 6h2v8h-2V9Zm4 0h2v8h-2V9ZM6 9h2v8H6V9Zm1 12a2 2 0 0 1-2-2V8h14v11a2 2 0 0 1-2 2H7Z" />
        </SvgIcon>
    )
}

function UsersScopedOverlay({ open, scopeRect, onClose, darkMode, maxWidth = 600, children }: UsersScopedOverlayProps) {
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

    if (!open || !scopeRect || typeof document === 'undefined') {
        return null
    }

    const availableHeight = Math.max(Math.round(scopeRect.height) - 32, 240)

    return createPortal(
        <Box
            className={darkMode ? 'app-shell-root--dark' : undefined}
            sx={{
                position: 'fixed',
                top: scopeRect.top,
                left: scopeRect.left,
                width: scopeRect.width,
                height: scopeRect.height,
                zIndex: 1400,
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
                    alignItems: 'center',
                    justifyContent: 'center',
                    px: { xs: 1.5, md: 1.5 },
                    py: { xs: 1.5, md: 2 },
                    pointerEvents: 'none',
                }}
            >
                <Box
                    role="dialog"
                    aria-modal="true"
                    onClick={(event) => event.stopPropagation()}
                    sx={{
                        pointerEvents: 'auto',
                        width: { xs: 'min(100%, 600px)', md: `min(${maxWidth}px, calc(100% - 16px))` },
                        maxWidth: `${maxWidth}px`,
                        maxHeight: `${availableHeight}px`,
                        display: 'flex',
                        flexDirection: 'column',
                        backgroundColor: darkMode ? '#111827' : '#fff',
                        borderRadius: '2px',
                        color: darkMode ? '#e5edf5' : '#0f172a',
                        border: darkMode ? '1px solid rgba(148, 163, 184, 0.2)' : undefined,
                        boxShadow: darkMode ? '0 24px 64px rgba(2, 6, 23, 0.62)' : '0 16px 40px rgba(15, 23, 42, 0.16)',
                        overflow: 'hidden',
                    }}
                >
                    {children}
                </Box>
            </Box>
        </Box>,
        document.body,
    )
}

function UserDialogHeroIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M12 12a4.25 4.25 0 1 0 0-8.5 4.25 4.25 0 0 0 0 8.5Zm0 2c-4.05 0-7.5 2.17-7.5 5.25 0 .41.34.75.75.75h13.5a.75.75 0 0 0 .75-.75C19.5 16.17 16.05 14 12 14Z" />
        </SvgIcon>
    )
}

function CloseIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M18.3 5.71 12 12l6.3 6.29-1.42 1.42L10.59 13.4 4.29 19.7l-1.41-1.42L9.17 12 2.88 5.71 4.29 4.29l6.3 6.3 6.29-6.3 1.42 1.42Z" />
        </SvgIcon>
    )
}

function EyeIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="M12 5c5.23 0 9.27 4.11 10.75 6.2a1.33 1.33 0 0 1 0 1.6C21.27 14.89 17.23 19 12 19S2.73 14.89 1.25 12.8a1.33 1.33 0 0 1 0-1.6C2.73 9.11 6.77 5 12 5Zm0 2C8.21 7 5.1 9.84 3.39 12 5.1 14.16 8.21 17 12 17s6.9-2.84 8.61-5C18.9 9.84 15.79 7 12 7Zm0 2.25A2.75 2.75 0 1 1 9.25 12 2.75 2.75 0 0 1 12 9.25Zm0 2A.75.75 0 1 0 12.75 12 .75.75 0 0 0 12 11.25Z" />
        </SvgIcon>
    )
}

function EyeOffIcon() {
    return (
        <SvgIcon viewBox="0 0 24 24">
            <path d="m4.71 3.29 16 16-1.42 1.42-2.43-2.43A11.65 11.65 0 0 1 12 19c-5.23 0-9.27-4.11-10.75-6.2a1.33 1.33 0 0 1 0-1.6A18.48 18.48 0 0 1 6.4 6.6L3.29 4.71 4.71 3.29Zm8.08 8.08-1.58-1.58a.75.75 0 1 0-1.42.63l2.37 2.37a.75.75 0 0 0 .63-1.42ZM7.96 8.16C6.14 9.09 4.55 10.45 3.39 12 5.1 14.16 8.21 17 12 17c1.16 0 2.26-.27 3.27-.73l-1.71-1.71a4.75 4.75 0 0 1-6.12-6.12L7.96 8.16ZM12 7c3.79 0 6.9 2.84 8.61 5a14.8 14.8 0 0 1-2.35 2.31l-1.43-1.43c.72-.63 1.33-1.28 1.78-1.88C18.9 9.84 15.79 7 12 7c-.73 0-1.43.1-2.1.29L8.19 5.58A9.8 9.8 0 0 1 12 7Z" />
        </SvgIcon>
    )
}

function normalizeLocaleValue(value: string | null | undefined) {
    return value === 'zh-CN' ? 'zh-CN' : 'en'
}

function validateUsername(value: string, usernames: string[], t: ReturnType<typeof useTranslation<'shell'>>['t']): string | undefined {
    const normalized = value.trim().toLowerCase()
    if (!normalized) {
        return t('usersPage.validation.usernameRequired')
    }
    if (normalized.length < 3) {
        return t('usersPage.validation.usernameMinLength')
    }
    if (normalized.length > 64) {
        return t('usersPage.validation.usernameMaxLength')
    }
    if (usernames.includes(normalized)) {
        return t('usersPage.validation.usernameTaken')
    }
    return undefined
}

function validateDisplayName(value: string, t: ReturnType<typeof useTranslation<'shell'>>['t']): string | undefined {
    const normalized = value.trim()
    if (!normalized) {
        return t('usersPage.validation.fullNameRequired')
    }
    if (normalized.length > 128) {
        return t('usersPage.validation.fullNameMaxLength')
    }
    return undefined
}

function validatePassword(value: string, required: boolean, t: ReturnType<typeof useTranslation<'shell'>>['t']): string | undefined {
    if (!value) {
        return required ? t('usersPage.validation.passwordRequired') : undefined
    }
    if (value.length < 8) {
        return t('usersPage.validation.passwordComplexity')
    }
    if (value.length > 256) {
        return t('usersPage.validation.passwordMaxLength')
    }
    if (!/[A-Z]/.test(value) || !/[a-z]/.test(value) || !/\d/.test(value) || !/[^A-Za-z0-9]/.test(value)) {
        return t('usersPage.validation.passwordComplexity')
    }
    return undefined
}

function validateEmail(value: string, t: ReturnType<typeof useTranslation<'shell'>>['t']): string | undefined {
    const normalized = value.trim()
    if (!normalized) {
        return undefined
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(normalized)) {
        return t('usersPage.validation.emailInvalid')
    }
    return undefined
}

function validateLocale(value: string, t: ReturnType<typeof useTranslation<'shell'>>['t']): string | undefined {
    if (!['en', 'zh-CN'].includes(value)) {
        return t('usersPage.validation.languageRequired')
    }
    return undefined
}

function mapUserRequestError(message: string, t: ReturnType<typeof useTranslation<'shell'>>['t']): { feedback?: string; fieldErrors?: UserFieldErrors } {
    switch (message) {
        case 'Username is already in use':
            return { fieldErrors: { username: t('usersPage.validation.usernameTaken') } }
        case 'Username must be at least 3 characters after trimming':
            return { fieldErrors: { username: t('usersPage.validation.usernameMinLength') } }
        case 'Display name cannot be empty':
            return { fieldErrors: { displayName: t('usersPage.validation.fullNameRequired') } }
        case 'Password must be at least 8 characters and include uppercase, lowercase, number, and special character':
            return { fieldErrors: { password: t('usersPage.validation.passwordComplexity') } }
        case 'Locale must be one of: en, zh-CN':
            return { fieldErrors: { locale: t('usersPage.validation.languageRequired') } }
        default:
            return { feedback: t('usersPage.feedback.genericError') }
    }
}

export function UsersPage() {
    const { colorMode } = useAppColorMode()
    const isDarkMode = colorMode === 'dark'
    const { t, i18n } = useTranslation('shell')
    const location = useLocation()
    const navigate = useNavigate()
    const { refresh, status } = useProductAuth()
    const pageShellRef = useRef<HTMLDivElement | null>(null)
    const createUsernameInputRef = useRef<HTMLInputElement | null>(null)
    const createDisplayNameInputRef = useRef<HTMLInputElement | null>(null)
    const createPasswordInputRef = useRef<HTMLInputElement | null>(null)
    const createConfirmPasswordInputRef = useRef<HTMLInputElement | null>(null)
    const editDisplayNameInputRef = useRef<HTMLInputElement | null>(null)
    const editPasswordInputRef = useRef<HTMLInputElement | null>(null)
    const editConfirmPasswordInputRef = useRef<HTMLInputElement | null>(null)
    const [feedback, setFeedback] = useState<{ severity: 'success' | 'error'; message: string } | null>(null)
    const [searchValue, setSearchValue] = useState('')
    const [activeDialog, setActiveDialog] = useState<UserDialogState>(null)
    const [createDraft, setCreateDraft] = useState({ username: '', displayName: '', email: '', locale: normalizeLocaleValue(i18n.resolvedLanguage), disabled: false, password: '', confirmPassword: '' })
    const [editDraft, setEditDraft] = useState({ displayName: '', email: '', locale: normalizeLocaleValue(i18n.resolvedLanguage), disabled: false, password: '', confirmPassword: '' })
    const [createTouched, setCreateTouched] = useState<Partial<Record<keyof UserFieldErrors, boolean>>>({})
    const [editTouched, setEditTouched] = useState<Partial<Record<keyof UserFieldErrors, boolean>>>({})
    const [createFieldErrors, setCreateFieldErrors] = useState<UserFieldErrors>({})
    const [editFieldErrors, setEditFieldErrors] = useState<UserFieldErrors>({})
    const [showCreatePassword, setShowCreatePassword] = useState(false)
    const [showCreateConfirmPassword, setShowCreateConfirmPassword] = useState(false)
    const [showEditPassword, setShowEditPassword] = useState(false)
    const [showEditConfirmPassword, setShowEditConfirmPassword] = useState(false)
    const [isSubmitting, setIsSubmitting] = useState(false)

    const palette = {
        pageBg: isDarkMode ? '#0f172a' : '#ffffff',
        cardBg: isDarkMode ? '#111827' : '#ffffff',
        tableHead: isDarkMode ? '#162033' : '#f8fafc',
        text: isDarkMode ? '#f8fafc' : '#0f172a',
        subtleText: isDarkMode ? '#94a3b8' : '#64748b',
        actionText: isDarkMode ? '#f8fafc' : '#475569',
        border: isDarkMode ? 'rgba(71, 85, 105, 0.65)' : 'rgba(226, 232, 240, 0.95)',
        borderStrong: isDarkMode ? 'rgba(148, 163, 184, 0.2)' : 'rgba(203, 213, 225, 0.9)',
        idleBg: isDarkMode ? '#111827' : '#ffffff',
        idleHover: isDarkMode ? '#162033' : '#f8fafc',
        buttonHover: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(145, 158, 171, 0.12)',
    } as const

    const surfaceCardSx = {
        borderRadius: '2px',
        border: `1px solid ${palette.border}`,
        background: palette.cardBg,
        boxShadow: isDarkMode ? '0 12px 28px rgba(2, 6, 23, 0.28)' : '0 8px 24px rgba(15, 23, 42, 0.05)',
    } as const

    const topActionButtonSx = {
        borderRadius: 0,
        textTransform: 'none',
        px: 1.25,
        color: palette.actionText,
        fontWeight: 600,
        backgroundColor: 'transparent',
        '&:hover': {
            backgroundColor: palette.buttonHover,
        },
    } as const
    const [contentScopeRect, setContentScopeRect] = useState<ContentScopeRect | null>(null)

    const { data, error, isLoading, isFetching, refetch } = useQuery<ProductAuthUsersResponse, Error>({
        queryKey: ['product-auth-users'],
        queryFn: fetchUsers,
        enabled: Boolean(status?.enabled && status?.authenticated),
        staleTime: 5_000,
    })

    const users = data?.users ?? []
    const currentUserId = status?.current_user?.id ?? null
    const locale = i18n.resolvedLanguage === 'zh-CN' ? 'zh-CN' : 'en-US'
    const dateFormatter = useMemo(
        () =>
            new Intl.DateTimeFormat(locale, {
                dateStyle: 'medium',
                timeStyle: 'short',
            }),
        [locale],
    )

    const filteredUsers = useMemo(() => {
        const normalizedQuery = searchValue.trim().toLowerCase()
        if (!normalizedQuery) {
            return users
        }

        return users.filter((user) => {
            return user.username.toLowerCase().includes(normalizedQuery) || user.display_name.toLowerCase().includes(normalizedQuery)
        })
    }, [searchValue, users])
    const currentUserIsSystem = users.find((user) => user.id === currentUserId)?.delete_eligible === false
    const localeOptions = [
        { value: 'en', label: t('usersPage.locales.en') },
        { value: 'zh-CN', label: t('usersPage.locales.zh-CN') },
    ]
    const knownUsernames = useMemo(() => users.map((user) => user.username.trim().toLowerCase()), [users])

    const activeEditUser = activeDialog?.type === 'edit' ? activeDialog.user : null
    const showLoadingCard = isLoading && !data
    const showRefreshRow = isFetching && Boolean(data)
    const canManageStatusForEdit = Boolean(activeEditUser && currentUserIsSystem && activeEditUser.delete_eligible && activeEditUser.id !== currentUserId)
    const hasEditChanges = activeEditUser
        ? editDraft.displayName.trim() !== activeEditUser.display_name ||
        editDraft.email.trim() !== (activeEditUser.email ?? '') ||
        editDraft.locale !== activeEditUser.locale ||
        (canManageStatusForEdit && editDraft.disabled !== activeEditUser.disabled) ||
        editDraft.password.trim().length > 0
        : false

    const statusOptions = [
        { value: 'enabled', label: t('usersPage.status.enabled') },
        { value: 'disabled', label: t('usersPage.status.disabled') },
    ]
    const dialogSelectMenuProps = useMemo(
        () => ({
            disablePortal: true,
            slotProps: {
                paper: {
                    sx: {
                        borderRadius: 0,
                        mt: 0.5,
                        zIndex: 1501,
                        backgroundColor: isDarkMode ? '#111827' : '#ffffff',
                        color: isDarkMode ? '#e5edf5' : '#0f172a',
                    },
                },
            },
        }),
        [isDarkMode],
    )

    const dialogSectionSx = {
        px: { xs: 2, md: 2.5 },
        py: { xs: 1.75, md: 2 },
        flexShrink: 0,
        backgroundColor: isDarkMode ? '#111827' : '#ffffff',
    } as const

    const dialogContentSx = {
        px: 0,
        py: 0,
        backgroundColor: isDarkMode ? '#111827' : '#ffffff',
        '&.MuiDialogContent-dividers': {
            borderTopColor: isDarkMode ? 'rgba(71, 85, 105, 0.65)' : 'rgba(226, 232, 240, 0.9)',
            borderBottomColor: isDarkMode ? 'rgba(71, 85, 105, 0.65)' : 'rgba(226, 232, 240, 0.9)',
        },
    } as const

    const dialogActionsSx = {
        px: 2.5,
        py: 2,
        flexShrink: 0,
        borderTop: `1px solid ${isDarkMode ? 'rgba(71, 85, 105, 0.65)' : 'rgba(226, 232, 240, 0.9)'}`,
        backgroundColor: isDarkMode ? '#111827' : '#ffffff',
    } as const

    const computedCreateErrors = useMemo<UserFieldErrors>(() => {
        const errors: UserFieldErrors = {}
        const usernameError = validateUsername(createDraft.username, knownUsernames, t)
        const displayNameError = validateDisplayName(createDraft.displayName, t)
        const emailError = validateEmail(createDraft.email, t)
        const localeError = validateLocale(createDraft.locale, t)
        const passwordError = validatePassword(createDraft.password, true, t)
        const confirmPasswordError =
            !createDraft.confirmPassword
                ? t('usersPage.validation.confirmPasswordRequired')
                : createDraft.password !== createDraft.confirmPassword
                    ? t('usersPage.fields.passwordMismatch')
                    : undefined

        if (usernameError) {
            errors.username = usernameError
        }
        if (displayNameError) {
            errors.displayName = displayNameError
        }
        if (emailError) {
            errors.email = emailError
        }
        if (localeError) {
            errors.locale = localeError
        }
        if (passwordError) {
            errors.password = passwordError
        }
        if (confirmPasswordError) {
            errors.confirmPassword = confirmPasswordError
        }
        return errors
    }, [createDraft.confirmPassword, createDraft.displayName, createDraft.email, createDraft.locale, createDraft.password, createDraft.username, knownUsernames, t])

    const computedEditErrors = useMemo<UserFieldErrors>(() => {
        const errors: UserFieldErrors = {}
        const displayNameError = validateDisplayName(editDraft.displayName, t)
        const emailError = validateEmail(editDraft.email, t)
        const localeError = validateLocale(editDraft.locale, t)
        const passwordError = validatePassword(editDraft.password, false, t)
        const confirmPasswordError =
            editDraft.password || editDraft.confirmPassword
                ? !editDraft.confirmPassword
                    ? t('usersPage.validation.confirmPasswordRequired')
                    : editDraft.password !== editDraft.confirmPassword
                        ? t('usersPage.fields.passwordMismatch')
                        : undefined
                : undefined

        if (displayNameError) {
            errors.displayName = displayNameError
        }
        if (emailError) {
            errors.email = emailError
        }
        if (localeError) {
            errors.locale = localeError
        }
        if (passwordError) {
            errors.password = passwordError
        }
        if (confirmPasswordError) {
            errors.confirmPassword = confirmPasswordError
        }
        return errors
    }, [editDraft.confirmPassword, editDraft.displayName, editDraft.email, editDraft.locale, editDraft.password, t])

    const createFormInvalid = Object.keys(computedCreateErrors).length > 0
    const editFormInvalid = Object.keys(computedEditErrors).length > 0

    useLayoutEffect(() => {
        const shellElement = pageShellRef.current
        const mainElement = shellElement?.closest('main')
        if (!shellElement || !(mainElement instanceof HTMLElement)) {
            return
        }

        const updateScopeRect = () => {
            const rect = mainElement.getBoundingClientRect()
            setContentScopeRect({
                top: rect.top,
                left: rect.left,
                width: rect.width,
                height: rect.height,
            })
        }

        updateScopeRect()

        const resizeObserver = new ResizeObserver(() => updateScopeRect())
        resizeObserver.observe(mainElement)
        window.addEventListener('resize', updateScopeRect)

        return () => {
            resizeObserver.disconnect()
            window.removeEventListener('resize', updateScopeRect)
        }
    }, [])

    useEffect(() => {
        setCreateFieldErrors(computedCreateErrors)
    }, [computedCreateErrors])

    useEffect(() => {
        setEditFieldErrors(computedEditErrors)
    }, [computedEditErrors])

    useEffect(() => {
        const routeState = (location.state ?? null) as UsersRouteState | null
        if (!routeState?.openCurrentUserEditor || !currentUserId || activeDialog) {
            return
        }

        const currentUser = users.find((user) => user.id === currentUserId)
        if (!currentUser) {
            return
        }

        openEditDialog(currentUser)
        navigate(location.pathname, { replace: true, state: null })
    }, [activeDialog, currentUserId, location.pathname, location.state, navigate, users])

    function focusCreateField(field: keyof UserFieldErrors) {
        const refMap = {
            username: createUsernameInputRef,
            displayName: createDisplayNameInputRef,
            email: createDisplayNameInputRef,
            password: createPasswordInputRef,
            confirmPassword: createConfirmPasswordInputRef,
            locale: createDisplayNameInputRef,
        }
        refMap[field]?.current?.focus()
    }

    function focusEditField(field: keyof UserFieldErrors) {
        const refMap = {
            username: editDisplayNameInputRef,
            displayName: editDisplayNameInputRef,
            email: editDisplayNameInputRef,
            password: editPasswordInputRef,
            confirmPassword: editConfirmPasswordInputRef,
            locale: editDisplayNameInputRef,
        }
        refMap[field]?.current?.focus()
    }

    function openCreateDialog() {
        setCreateDraft({ username: '', displayName: '', email: '', locale: normalizeLocaleValue(i18n.resolvedLanguage), disabled: false, password: '', confirmPassword: '' })
        setCreateTouched({})
        setCreateFieldErrors({})
        setShowCreatePassword(false)
        setShowCreateConfirmPassword(false)
        setActiveDialog({ type: 'create' })
    }

    function openEditDialog(user: ProductAuthUser) {
        setEditDraft({ displayName: user.display_name, email: user.email ?? '', locale: normalizeLocaleValue(user.locale), disabled: user.disabled, password: '', confirmPassword: '' })
        setEditTouched({})
        setEditFieldErrors({})
        setShowEditPassword(false)
        setShowEditConfirmPassword(false)
        setActiveDialog({ type: 'edit', user })
    }

    async function handleCreateUser() {
        setCreateTouched({ username: true, displayName: true, email: true, locale: true, password: true, confirmPassword: true })
        setCreateFieldErrors(computedCreateErrors)
        const firstCreateErrorField = (['username', 'displayName', 'email', 'locale', 'password', 'confirmPassword'] as Array<keyof UserFieldErrors>).find((field) => computedCreateErrors[field])
        if (firstCreateErrorField) {
            focusCreateField(firstCreateErrorField)
            return
        }

        setIsSubmitting(true)
        setFeedback(null)

        try {
            const createdUser = await requestJson<ProductAuthUser>('/api/auth/users', {
                method: 'POST',
                body: JSON.stringify({
                    username: createDraft.username.trim().toLowerCase(),
                    display_name: createDraft.displayName.trim(),
                    email: createDraft.email.trim() || null,
                    locale: createDraft.locale,
                    disabled: createDraft.disabled,
                    password: createDraft.password,
                }),
            })
            await Promise.all([refetch(), refresh()])
            setActiveDialog(null)
            setCreateDraft({ username: '', displayName: '', email: '', locale: normalizeLocaleValue(i18n.resolvedLanguage), disabled: false, password: '', confirmPassword: '' })
            setFeedback({ severity: 'success', message: t('usersPage.feedback.createSuccess', { username: createdUser.username }) })
        } catch (submitError) {
            const mappedError = mapUserRequestError(submitError instanceof Error ? submitError.message : '', t)
            if (mappedError.fieldErrors) {
                setCreateTouched({ username: true, displayName: true, email: true, locale: true, password: true, confirmPassword: true })
                setCreateFieldErrors((current) => ({ ...current, ...mappedError.fieldErrors }))
                const firstField = (['username', 'displayName', 'email', 'locale', 'password', 'confirmPassword'] as Array<keyof UserFieldErrors>).find((field) => mappedError.fieldErrors?.[field])
                if (firstField) {
                    focusCreateField(firstField)
                    return
                }
            }
            setFeedback({
                severity: 'error',
                message: mappedError.feedback ?? t('usersPage.feedback.genericError'),
            })
        } finally {
            setIsSubmitting(false)
        }
    }

    async function handleEditUser() {
        if (!activeEditUser) {
            return
        }

        setEditTouched({ displayName: true, email: true, locale: true, password: true, confirmPassword: true })
        setEditFieldErrors(computedEditErrors)
        const firstEditErrorField = (['displayName', 'email', 'locale', 'password', 'confirmPassword'] as Array<keyof UserFieldErrors>).find((field) => computedEditErrors[field])
        if (firstEditErrorField) {
            focusEditField(firstEditErrorField)
            return
        }

        setIsSubmitting(true)
        setFeedback(null)

        try {
            if (
                editDraft.displayName.trim() !== activeEditUser.display_name ||
                editDraft.email.trim() !== (activeEditUser.email ?? '') ||
                editDraft.locale !== activeEditUser.locale ||
                (canManageStatusForEdit && editDraft.disabled !== activeEditUser.disabled)
            ) {
                await requestJson<ProductAuthUser>(`/api/auth/users/${activeEditUser.id}`, {
                    method: 'PUT',
                    body: JSON.stringify({
                        display_name: editDraft.displayName.trim(),
                        email: editDraft.email.trim() || null,
                        locale: editDraft.locale,
                        ...(canManageStatusForEdit ? { disabled: editDraft.disabled } : {}),
                    }),
                })
            }

            if (editDraft.password.trim()) {
                await requestJson<ProductAuthUser>(`/api/auth/users/${activeEditUser.id}/reset-password`, {
                    method: 'POST',
                    body: JSON.stringify({ password: editDraft.password }),
                })
            }

            await Promise.all([refetch(), refresh()])
            setActiveDialog(null)
            setEditDraft({ displayName: '', email: '', locale: normalizeLocaleValue(i18n.resolvedLanguage), disabled: false, password: '', confirmPassword: '' })
            setFeedback({ severity: 'success', message: t('usersPage.feedback.editSuccess', { username: activeEditUser.username }) })
        } catch (submitError) {
            const mappedError = mapUserRequestError(submitError instanceof Error ? submitError.message : '', t)
            if (mappedError.fieldErrors) {
                setEditTouched({ displayName: true, email: true, locale: true, password: true, confirmPassword: true })
                setEditFieldErrors((current) => ({ ...current, ...mappedError.fieldErrors }))
                const firstField = (['displayName', 'email', 'locale', 'password', 'confirmPassword'] as Array<keyof UserFieldErrors>).find((field) => mappedError.fieldErrors?.[field])
                if (firstField) {
                    focusEditField(firstField)
                    return
                }
            }
            setFeedback({
                severity: 'error',
                message: mappedError.feedback ?? t('usersPage.feedback.genericError'),
            })
        } finally {
            setIsSubmitting(false)
        }
    }

    async function handleDeleteUser() {
        if (!activeDialog || activeDialog.type !== 'delete') {
            return
        }

        setIsSubmitting(true)
        setFeedback(null)

        try {
            await requestJson<ProductAuthUser>(`/api/auth/users/${activeDialog.user.id}`, { method: 'DELETE' })
            await Promise.all([refetch(), refresh()])
            setActiveDialog(null)
            setFeedback({ severity: 'success', message: t('usersPage.feedback.deleteSuccess', { username: activeDialog.user.username }) })
        } catch (submitError) {
            setFeedback({
                severity: 'error',
                message: submitError instanceof Error ? submitError.message : t('usersPage.feedback.genericError'),
            })
        } finally {
            setIsSubmitting(false)
        }
    }

    async function handleToggleUserEnabled(user: ProductAuthUser) {
        setIsSubmitting(true)
        setFeedback(null)

        try {
            await requestJson<ProductAuthUser>(`/api/auth/users/${user.id}/${user.disabled ? 'enable' : 'disable'}`, {
                method: 'POST',
            })
            await Promise.all([refetch(), refresh()])
            setFeedback({
                severity: 'success',
                message: user.disabled
                    ? t('usersPage.feedback.enableSuccess', { username: user.username })
                    : t('usersPage.feedback.disableSuccess', { username: user.username }),
            })
        } catch (submitError) {
            setFeedback({
                severity: 'error',
                message: submitError instanceof Error ? submitError.message : t('usersPage.feedback.genericError'),
            })
        } finally {
            setIsSubmitting(false)
        }
    }

    function formatUserLocale(value: string) {
        return value === 'zh-CN' ? t('usersPage.locales.zh-CN') : t('usersPage.locales.en')
    }

    return (
        <Box
            className="users-page-shell"
            ref={pageShellRef}
            sx={{
                minHeight: 0,
                position: 'relative',
                mx: { xs: -1, md: -3 },
                my: { xs: -1.25, md: -2.25 },
                px: { xs: 2, md: 3 },
                py: { xs: 1.25, md: 1.5 },
                backgroundColor: palette.pageBg,
                overflowY: 'visible',
                overflowX: 'hidden',
            }}
        >
            <Stack spacing={2} sx={{ height: '100%', minHeight: 0 }}>
                {!status?.enabled ? (
                    <Alert severity="info" variant="outlined">
                        {t('usersPage.states.authDisabled')}
                    </Alert>
                ) : null}

                {error ? (
                    <Alert
                        action={
                            <Button color="inherit" onClick={() => void refetch()} size="small">
                                {t('usersPage.states.retry')}
                            </Button>
                        }
                        severity="warning"
                        variant="outlined"
                    >
                        {t('usersPage.states.loadError', { statusCode: error.message.replace(/^.*HTTP\s/, '') || 'unknown' })}
                    </Alert>
                ) : null}

                <PageDescriptionHeader title={t('nav.users.label')} description={t('usersPage.hero.description')} descriptionColor={palette.subtleText} />

                <Box className="users-page-grid">
                    <Card elevation={0} sx={surfaceCardSx}>
                        <CardContent sx={{ pt: 3, pb: 2 }}>
                            <Stack spacing={1.5} sx={{ minHeight: 0 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 1.5, flexWrap: 'wrap' }}>
                                    <Box className="users-toolbar">
                                        <TextField
                                            className="users-toolbar-field users-toolbar-search"
                                            onChange={(event) => setSearchValue(event.target.value)}
                                            placeholder={t('usersPage.filters.searchPlaceholder')}
                                            size="small"
                                            value={searchValue}
                                        />
                                        {currentUserIsSystem ? (
                                            <Button className="users-toolbar-button" onClick={openCreateDialog} variant="contained" sx={{ borderRadius: 0, boxShadow: 'none', textTransform: 'none', fontWeight: 600 }}>
                                                {t('usersPage.create.submit')}
                                            </Button>
                                        ) : null}
                                        <IconButton className="users-toolbar-icon-button" onClick={() => void refetch()} disabled={isFetching} size="small" title={t('usersPage.actions.refresh')} sx={topActionButtonSx}>
                                            {isFetching ? <CircularProgress size={14} color="inherit" /> : <RefreshIcon />}
                                        </IconButton>
                                    </Box>
                                </Box>

                                {showLoadingCard ? <SurfaceStateCard detail={t('usersPage.states.loading')} loading darkMode={isDarkMode} /> : null}

                                {!showLoadingCard ? (
                                    <Box sx={{ overflowX: 'auto', border: `1px solid ${palette.border}` }}>
                                        <Box sx={{ minWidth: 1200 }}>
                                            <Box
                                                sx={{
                                                    display: 'grid',
                                                    gridTemplateColumns: '1.1fr 1fr 1.2fr .75fr .78fr .9fr 1fr',
                                                    alignItems: 'center',
                                                    minHeight: 52,
                                                    px: 1.25,
                                                    borderBottom: `1px solid ${palette.border}`,
                                                    background: palette.tableHead,
                                                }}
                                            >
                                                {[
                                                    t('usersPage.columns.username'),
                                                    t('usersPage.columns.displayName'),
                                                    t('usersPage.fields.email'),
                                                    t('usersPage.columns.language'),
                                                    t('usersPage.columns.status'),
                                                    t('usersPage.columns.createdAt'),
                                                    t('usersPage.columns.actions'),
                                                ].map((column, index) => (
                                                    <Typography
                                                        key={column}
                                                        sx={{
                                                            fontSize: 13,
                                                            fontWeight: 700,
                                                            color: palette.subtleText,
                                                            textAlign: index === 6 ? 'right' : 'left',
                                                        }}
                                                    >
                                                        {column}
                                                    </Typography>
                                                ))}
                                            </Box>

                                            {showRefreshRow ? (
                                                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1.25, minHeight: 140, px: 3, color: palette.subtleText }}>
                                                    <CircularProgress size={18} />
                                                    <Typography sx={{ fontSize: 14, color: palette.subtleText }}>
                                                        {t('usersPage.states.refreshing')}
                                                    </Typography>
                                                </Box>
                                            ) : null}

                                            {!showRefreshRow && users.length === 0 ? (
                                                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 180, px: 3 }}>
                                                    <Typography sx={{ fontSize: 16, fontWeight: 700, color: palette.text }}>{t('usersPage.states.empty')}</Typography>
                                                </Box>
                                            ) : null}

                                            {!showRefreshRow && users.length > 0 && filteredUsers.length === 0 ? (
                                                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 180, px: 3 }}>
                                                    <Typography sx={{ fontSize: 16, fontWeight: 700, color: palette.text }}>{t('usersPage.states.noResults')}</Typography>
                                                </Box>
                                            ) : null}

                                            {!showRefreshRow
                                                ? filteredUsers.map((user) => {
                                                    const isCurrentUser = currentUserId === user.id
                                                    const canEditUser = currentUserIsSystem || isCurrentUser
                                                    const canDeleteUser = currentUserIsSystem && user.delete_eligible
                                                    const canToggleUser = currentUserIsSystem && user.delete_eligible && !isCurrentUser
                                                    return (
                                                        <Box
                                                            key={user.id}
                                                            sx={{
                                                                display: 'grid',
                                                                gridTemplateColumns: '1.1fr 1fr 1.2fr .75fr .78fr .9fr 1fr',
                                                                alignItems: 'center',
                                                                gap: 1.25,
                                                                px: 1.25,
                                                                py: 1.35,
                                                                borderBottom: `1px solid ${palette.borderStrong}`,
                                                                backgroundColor: palette.idleBg,
                                                                '&:hover': {
                                                                    backgroundColor: palette.idleHover,
                                                                },
                                                            }}
                                                        >
                                                            <Stack className="users-identity-cell" spacing={0.75} sx={{ minWidth: 0 }}>
                                                                <Typography className="users-linkish">{user.username}</Typography>
                                                                <Box className="users-inline-tags">
                                                                    {isCurrentUser ? <Chip label={t('usersPage.badges.current')} size="small" sx={{ borderRadius: 0 }} /> : null}
                                                                    {!user.delete_eligible ? (
                                                                        <Chip color="warning" label={t('usersPage.badges.initialized')} size="small" variant="outlined" sx={{ borderRadius: 0 }} />
                                                                    ) : null}
                                                                </Box>
                                                            </Stack>
                                                            <Typography sx={{ fontSize: 13.5, lineHeight: 1.6, color: palette.text }}>{user.display_name}</Typography>
                                                            <Typography sx={{ fontSize: 13, color: palette.subtleText, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={user.email ?? ''}>{user.email ?? '—'}</Typography>
                                                            <Typography sx={{ fontSize: 13.5, color: palette.subtleText }}>{formatUserLocale(user.locale)}</Typography>
                                                            <Box>
                                                                <Chip
                                                                    className={`users-status-chip ${user.disabled ? 'users-status-chip-disabled' : 'users-status-chip-enabled'}`}
                                                                    label={user.disabled ? t('usersPage.status.disabled') : t('usersPage.status.enabled')}
                                                                    size="small"
                                                                    variant="filled"
                                                                />
                                                            </Box>
                                                            <Typography sx={{ fontSize: 13, color: palette.subtleText }}>{dateFormatter.format(new Date(user.created_at))}</Typography>
                                                            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                                                                {canEditUser || canDeleteUser || canToggleUser ? (
                                                                    <Box className="users-row-actions">
                                                                        {canEditUser ? (
                                                                            <Tooltip title={t('usersPage.actions.edit')}>
                                                                                <span>
                                                                                    <IconButton aria-label={t('usersPage.actions.edit')} className="users-row-action-button" disabled={isSubmitting} onClick={() => openEditDialog(user)} size="small">
                                                                                        <EditIcon />
                                                                                    </IconButton>
                                                                                </span>
                                                                            </Tooltip>
                                                                        ) : null}
                                                                        {canToggleUser ? (
                                                                            <Tooltip title={user.disabled ? t('usersPage.actions.enable') : t('usersPage.actions.disable')}>
                                                                                <span>
                                                                                    <IconButton
                                                                                        aria-label={user.disabled ? t('usersPage.actions.enable') : t('usersPage.actions.disable')}
                                                                                        className={`users-row-action-button ${user.disabled ? 'users-row-action-button-success' : 'users-row-action-button-warning'}`}
                                                                                        disabled={isSubmitting}
                                                                                        onClick={() => void handleToggleUserEnabled(user)}
                                                                                        size="small"
                                                                                    >
                                                                                        {user.disabled ? <EnableUserIcon /> : <DisableUserIcon />}
                                                                                    </IconButton>
                                                                                </span>
                                                                            </Tooltip>
                                                                        ) : null}
                                                                        {canDeleteUser ? (
                                                                            <Tooltip title={t('usersPage.actions.delete')}>
                                                                                <span>
                                                                                    <IconButton
                                                                                        aria-label={t('usersPage.actions.delete')}
                                                                                        className="users-row-action-button users-row-action-button-danger"
                                                                                        disabled={isSubmitting}
                                                                                        onClick={() => setActiveDialog({ type: 'delete', user })}
                                                                                        size="small"
                                                                                    >
                                                                                        <DeleteIcon />
                                                                                    </IconButton>
                                                                                </span>
                                                                            </Tooltip>
                                                                        ) : null}
                                                                    </Box>
                                                                ) : null}
                                                            </Box>
                                                        </Box>
                                                    )
                                                })
                                                : null}
                                        </Box>
                                    </Box>
                                ) : null}
                            </Stack>
                        </CardContent>
                    </Card>
                </Box>
            </Stack>

            <UsersScopedOverlay
                open={activeDialog?.type === 'create'}
                onClose={() => {
                    if (!isSubmitting) {
                        setActiveDialog(null)
                    }
                }}
                darkMode={isDarkMode}
                scopeRect={contentScopeRect}
                maxWidth={720}
            >
                <DialogTitle sx={dialogSectionSx}>
                    <Box className="users-dialog-hero">
                        <Box className="users-dialog-hero-icon-shell">
                            <Box className="users-dialog-hero-icon">
                                <UserDialogHeroIcon />
                            </Box>
                        </Box>
                        <Box className="users-dialog-title-stack">
                            <Typography className="users-dialog-title">{t('usersPage.dialogs.createTitle')}</Typography>
                            <Typography className="users-dialog-description">{t('usersPage.dialogs.createDescription')}</Typography>
                        </Box>
                        <IconButton aria-label={t('usersPage.dialogs.cancel')} className="users-dialog-close-button" disabled={isSubmitting} onClick={() => setActiveDialog(null)} size="small">
                            <CloseIcon />
                        </IconButton>
                    </Box>
                </DialogTitle>
                <DialogContent dividers sx={dialogContentSx}>
                    <Box className="users-dialog-form-grid">
                        <Box>
                            <Typography className="users-dialog-field-label">{t('auth.fields.username')}</Typography>
                            <TextField
                                autoFocus
                                fullWidth
                                className="users-dialog-field"
                                error={Boolean(createTouched.username && createFieldErrors.username)}
                                helperText={createTouched.username ? (createFieldErrors.username ?? ' ') : ' '}
                                inputRef={createUsernameInputRef}
                                onBlur={() => setCreateTouched((current) => ({ ...current, username: true }))}
                                onChange={(event) => setCreateDraft((current) => ({ ...current, username: event.target.value }))}
                                placeholder={t('auth.fields.username')}
                                value={createDraft.username}
                            />
                        </Box>
                        <Box>
                            <Typography className="users-dialog-field-label">{t('usersPage.columns.displayName')}</Typography>
                            <TextField
                                fullWidth
                                className="users-dialog-field"
                                error={Boolean(createTouched.displayName && createFieldErrors.displayName)}
                                helperText={createTouched.displayName ? (createFieldErrors.displayName ?? ' ') : ' '}
                                inputRef={createDisplayNameInputRef}
                                onBlur={() => setCreateTouched((current) => ({ ...current, displayName: true }))}
                                onChange={(event) => setCreateDraft((current) => ({ ...current, displayName: event.target.value }))}
                                placeholder={t('usersPage.columns.displayName')}
                                value={createDraft.displayName}
                            />
                        </Box>
                        <Box>
                            <Typography className="users-dialog-field-label">{t('usersPage.fields.email')}</Typography>
                            <TextField
                                fullWidth
                                className="users-dialog-field"
                                error={Boolean(createTouched.email && createFieldErrors.email)}
                                helperText={createTouched.email ? (createFieldErrors.email ?? ' ') : ' '}
                                onBlur={() => setCreateTouched((current) => ({ ...current, email: true }))}
                                onChange={(event) => setCreateDraft((current) => ({ ...current, email: event.target.value }))}
                                placeholder="user@example.com"
                                type="email"
                                value={createDraft.email}
                            />
                        </Box>
                        <Box className="users-dialog-field-grid users-dialog-field-grid-halves">
                            <Box>
                                <Typography className="users-dialog-field-label">{t('usersPage.fields.language')}</Typography>
                                <TextField
                                    select
                                    fullWidth
                                    className="users-dialog-field"
                                    error={Boolean(createTouched.locale && createFieldErrors.locale)}
                                    helperText={createTouched.locale ? (createFieldErrors.locale ?? ' ') : ' '}
                                    onBlur={() => setCreateTouched((current) => ({ ...current, locale: true }))}
                                    onChange={(event) => setCreateDraft((current) => ({ ...current, locale: event.target.value }))}
                                    slotProps={{
                                        select: {
                                            MenuProps: dialogSelectMenuProps,
                                        },
                                    }}
                                    value={createDraft.locale}
                                >
                                    {localeOptions.map((option) => (
                                        <MenuItem key={option.value} value={option.value}>
                                            {option.label}
                                        </MenuItem>
                                    ))}
                                </TextField>
                            </Box>
                            <Box>
                                <Typography className="users-dialog-field-label">{t('usersPage.fields.status')}</Typography>
                                <TextField
                                    select
                                    fullWidth
                                    className="users-dialog-field"
                                    slotProps={{
                                        select: {
                                            MenuProps: dialogSelectMenuProps,
                                        },
                                    }}
                                    onChange={(event) => setCreateDraft((current) => ({ ...current, disabled: event.target.value === 'disabled' }))}
                                    value={createDraft.disabled ? 'disabled' : 'enabled'}
                                >
                                    {statusOptions.map((option) => (
                                        <MenuItem key={option.value} value={option.value}>
                                            {option.label}
                                        </MenuItem>
                                    ))}
                                </TextField>
                            </Box>
                        </Box>
                        <Box>
                            <Typography className="users-dialog-field-label">{t('auth.fields.password')}</Typography>
                            <TextField
                                fullWidth
                                className="users-dialog-field"
                                error={Boolean(createTouched.password && createFieldErrors.password)}
                                helperText={createTouched.password ? (createFieldErrors.password ?? t('usersPage.fields.passwordHelper')) : t('usersPage.fields.passwordHelper')}
                                inputRef={createPasswordInputRef}
                                onBlur={() => setCreateTouched((current) => ({ ...current, password: true }))}
                                onChange={(event) => setCreateDraft((current) => ({ ...current, password: event.target.value }))}
                                type={showCreatePassword ? 'text' : 'password'}
                                value={createDraft.password}
                                slotProps={{
                                    input: {
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <IconButton aria-label={showCreatePassword ? t('auth.actions.hidePassword') : t('auth.actions.showPassword')} edge="end" onClick={() => setShowCreatePassword((current) => !current)}>
                                                    {showCreatePassword ? <EyeOffIcon /> : <EyeIcon />}
                                                </IconButton>
                                            </InputAdornment>
                                        ),
                                    },
                                }}
                            />
                        </Box>
                        <Box>
                            <Typography className="users-dialog-field-label">{t('usersPage.fields.confirmPassword')}</Typography>
                            <TextField
                                fullWidth
                                className="users-dialog-field"
                                error={Boolean(createTouched.confirmPassword && createFieldErrors.confirmPassword)}
                                helperText={createTouched.confirmPassword ? (createFieldErrors.confirmPassword ?? ' ') : ' '}
                                inputRef={createConfirmPasswordInputRef}
                                onBlur={() => setCreateTouched((current) => ({ ...current, confirmPassword: true }))}
                                onChange={(event) => setCreateDraft((current) => ({ ...current, confirmPassword: event.target.value }))}
                                type={showCreateConfirmPassword ? 'text' : 'password'}
                                value={createDraft.confirmPassword}
                                slotProps={{
                                    input: {
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <IconButton aria-label={showCreateConfirmPassword ? t('auth.actions.hidePassword') : t('auth.actions.showPassword')} edge="end" onClick={() => setShowCreateConfirmPassword((current) => !current)}>
                                                    {showCreateConfirmPassword ? <EyeOffIcon /> : <EyeIcon />}
                                                </IconButton>
                                            </InputAdornment>
                                        ),
                                    },
                                }}
                            />
                        </Box>
                    </Box>
                </DialogContent>
                <DialogActions sx={dialogActionsSx}>
                    <Button onClick={() => setActiveDialog(null)}>{t('usersPage.dialogs.cancel')}</Button>
                    <Button
                        disabled={isSubmitting || createFormInvalid}
                        onClick={() => void handleCreateUser()}
                        variant="contained"
                        sx={{ borderRadius: 0 }}
                    >
                        {isSubmitting ? t('usersPage.create.submitting') : t('usersPage.dialogs.confirmCreate')}
                    </Button>
                </DialogActions>
            </UsersScopedOverlay>

            <UsersScopedOverlay
                open={activeDialog?.type === 'edit'}
                onClose={() => {
                    if (!isSubmitting) {
                        setActiveDialog(null)
                    }
                }}
                darkMode={isDarkMode}
                scopeRect={contentScopeRect}
                maxWidth={720}
            >
                <DialogTitle sx={dialogSectionSx}>
                    <Box className="users-dialog-hero">
                        <Box className="users-dialog-hero-icon-shell">
                            <Box className="users-dialog-hero-icon users-dialog-hero-icon-accent">
                                <Typography component="span" className="users-dialog-hero-initial">
                                    {(activeEditUser?.username ?? '?').trim().slice(0, 1).toUpperCase()}
                                </Typography>
                            </Box>
                        </Box>
                        <Box className="users-dialog-title-stack">
                            <Typography className="users-dialog-title">{t('usersPage.dialogs.editTitle')}</Typography>
                            <Typography className="users-dialog-description">{t('usersPage.dialogs.editDescription', { username: activeEditUser?.username ?? '' })}</Typography>
                        </Box>
                        <IconButton aria-label={t('usersPage.dialogs.cancel')} className="users-dialog-close-button" disabled={isSubmitting} onClick={() => setActiveDialog(null)} size="small">
                            <CloseIcon />
                        </IconButton>
                    </Box>
                </DialogTitle>
                <DialogContent dividers sx={dialogContentSx}>
                    <Box className="users-dialog-form-grid">
                        <Box>
                            <Typography className="users-dialog-field-label">{t('auth.fields.username')}</Typography>
                            <TextField
                                disabled
                                fullWidth
                                className="users-dialog-field users-dialog-field-readonly"
                                helperText={t('usersPage.fields.usernameReadonly')}
                                value={activeEditUser?.username ?? ''}
                            />
                        </Box>
                        <Box>
                            <Typography className="users-dialog-field-label">{t('usersPage.columns.displayName')}</Typography>
                            <TextField
                                fullWidth
                                className="users-dialog-field"
                                error={Boolean(editTouched.displayName && editFieldErrors.displayName)}
                                helperText={editTouched.displayName ? (editFieldErrors.displayName ?? ' ') : ' '}
                                inputRef={editDisplayNameInputRef}
                                onBlur={() => setEditTouched((current) => ({ ...current, displayName: true }))}
                                onChange={(event) => setEditDraft((current) => ({ ...current, displayName: event.target.value }))}
                                value={editDraft.displayName}
                            />
                        </Box>
                        <Box>
                            <Typography className="users-dialog-field-label">{t('usersPage.fields.email')}</Typography>
                            <TextField
                                fullWidth
                                className="users-dialog-field"
                                error={Boolean(editTouched.email && editFieldErrors.email)}
                                helperText={editTouched.email ? (editFieldErrors.email ?? ' ') : ' '}
                                onBlur={() => setEditTouched((current) => ({ ...current, email: true }))}
                                onChange={(event) => setEditDraft((current) => ({ ...current, email: event.target.value }))}
                                placeholder="user@example.com"
                                type="email"
                                value={editDraft.email}
                            />
                        </Box>
                        <Box className="users-dialog-field-grid users-dialog-field-grid-halves">
                            <Box>
                                <Typography className="users-dialog-field-label">{t('usersPage.fields.language')}</Typography>
                                <TextField
                                    select
                                    fullWidth
                                    className="users-dialog-field"
                                    error={Boolean(editTouched.locale && editFieldErrors.locale)}
                                    helperText={editTouched.locale ? (editFieldErrors.locale ?? ' ') : ' '}
                                    onBlur={() => setEditTouched((current) => ({ ...current, locale: true }))}
                                    onChange={(event) => setEditDraft((current) => ({ ...current, locale: event.target.value }))}
                                    slotProps={{
                                        select: {
                                            MenuProps: dialogSelectMenuProps,
                                        },
                                    }}
                                    value={editDraft.locale}
                                >
                                    {localeOptions.map((option) => (
                                        <MenuItem key={option.value} value={option.value}>
                                            {option.label}
                                        </MenuItem>
                                    ))}
                                </TextField>
                            </Box>
                            <Box>
                                <Typography className="users-dialog-field-label">{t('usersPage.fields.status')}</Typography>
                                <TextField
                                    select
                                    disabled={!canManageStatusForEdit}
                                    fullWidth
                                    className="users-dialog-field"
                                    helperText={!canManageStatusForEdit ? t('usersPage.fields.statusReadonly') : ' '}
                                    onChange={(event) => setEditDraft((current) => ({ ...current, disabled: event.target.value === 'disabled' }))}
                                    slotProps={{
                                        select: {
                                            MenuProps: dialogSelectMenuProps,
                                        },
                                    }}
                                    value={editDraft.disabled ? 'disabled' : 'enabled'}
                                >
                                    {statusOptions.map((option) => (
                                        <MenuItem key={option.value} value={option.value}>
                                            {option.label}
                                        </MenuItem>
                                    ))}
                                </TextField>
                            </Box>
                        </Box>
                        <Box>
                            <Typography className="users-dialog-field-label">{t('usersPage.fields.newPassword')}</Typography>
                            <TextField
                                fullWidth
                                className="users-dialog-field"
                                error={Boolean(editTouched.password && editFieldErrors.password)}
                                helperText={editTouched.password ? (editFieldErrors.password ?? t('usersPage.fields.passwordOptional')) : t('usersPage.fields.passwordOptional')}
                                inputRef={editPasswordInputRef}
                                onBlur={() => setEditTouched((current) => ({ ...current, password: true }))}
                                onChange={(event) => setEditDraft((current) => ({ ...current, password: event.target.value }))}
                                type={showEditPassword ? 'text' : 'password'}
                                value={editDraft.password}
                                slotProps={{
                                    input: {
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <IconButton aria-label={showEditPassword ? t('auth.actions.hidePassword') : t('auth.actions.showPassword')} edge="end" onClick={() => setShowEditPassword((current) => !current)}>
                                                    {showEditPassword ? <EyeOffIcon /> : <EyeIcon />}
                                                </IconButton>
                                            </InputAdornment>
                                        ),
                                    },
                                }}
                            />
                        </Box>
                        <Box>
                            <Typography className="users-dialog-field-label">{t('usersPage.fields.confirmPassword')}</Typography>
                            <TextField
                                fullWidth
                                className="users-dialog-field"
                                error={Boolean(editTouched.confirmPassword && editFieldErrors.confirmPassword)}
                                helperText={editTouched.confirmPassword ? (editFieldErrors.confirmPassword ?? ' ') : ' '}
                                inputRef={editConfirmPasswordInputRef}
                                onBlur={() => setEditTouched((current) => ({ ...current, confirmPassword: true }))}
                                onChange={(event) => setEditDraft((current) => ({ ...current, confirmPassword: event.target.value }))}
                                type={showEditConfirmPassword ? 'text' : 'password'}
                                value={editDraft.confirmPassword}
                                slotProps={{
                                    input: {
                                        endAdornment: (
                                            <InputAdornment position="end">
                                                <IconButton aria-label={showEditConfirmPassword ? t('auth.actions.hidePassword') : t('auth.actions.showPassword')} edge="end" onClick={() => setShowEditConfirmPassword((current) => !current)}>
                                                    {showEditConfirmPassword ? <EyeOffIcon /> : <EyeIcon />}
                                                </IconButton>
                                            </InputAdornment>
                                        ),
                                    },
                                }}
                            />
                        </Box>
                    </Box>
                </DialogContent>
                <DialogActions sx={dialogActionsSx}>
                    <Button onClick={() => setActiveDialog(null)}>{t('usersPage.dialogs.cancel')}</Button>
                    <Button disabled={isSubmitting || !hasEditChanges || editFormInvalid} onClick={() => void handleEditUser()} variant="contained" sx={{ borderRadius: 0 }}>
                        {isSubmitting ? t('usersPage.dialogs.saving') : t('usersPage.dialogs.confirmEdit')}
                    </Button>
                </DialogActions>
            </UsersScopedOverlay>

            <UsersScopedOverlay
                open={activeDialog?.type === 'delete'}
                onClose={() => {
                    if (!isSubmitting) {
                        setActiveDialog(null)
                    }
                }}
                darkMode={isDarkMode}
                scopeRect={contentScopeRect}
                maxWidth={480}
            >
                <DialogTitle sx={dialogSectionSx}>
                    <Box className="users-dialog-title-stack">
                        <Typography className="users-dialog-title">{t('usersPage.dialogs.deleteTitle')}</Typography>
                        <Typography className="users-dialog-description">{activeDialog?.type === 'delete' ? t('usersPage.dialogs.deleteDescription', { username: activeDialog.user.username }) : ''}</Typography>
                    </Box>
                </DialogTitle>
                <DialogContent dividers sx={dialogContentSx}>
                    <Box className="users-dialog-form-grid">
                        <Alert severity="warning" variant="outlined">
                            {activeDialog?.type === 'delete' ? t('usersPage.dialogs.deleteBody', { username: activeDialog.user.username }) : ''}
                        </Alert>
                    </Box>
                </DialogContent>
                <DialogActions sx={dialogActionsSx}>
                    <Button onClick={() => setActiveDialog(null)}>{t('usersPage.dialogs.cancel')}</Button>
                    <Button color="error" disabled={isSubmitting} onClick={() => void handleDeleteUser()} variant="contained" sx={{ borderRadius: 0 }}>
                        {isSubmitting ? t('usersPage.dialogs.deleting') : t('usersPage.dialogs.confirmDelete')}
                    </Button>
                </DialogActions>
            </UsersScopedOverlay>

            <Snackbar open={Boolean(feedback)} autoHideDuration={3000} onClose={() => setFeedback(null)} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
                <Alert onClose={() => setFeedback(null)} severity={feedback?.severity ?? 'info'} variant="filled" elevation={6} sx={{ width: '100%' }}>
                    {feedback?.message}
                </Alert>
            </Snackbar>
        </Box>
    )
}