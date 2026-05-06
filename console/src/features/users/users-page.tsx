import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Paper,
    Snackbar,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField,
    Typography,
    MenuItem,
} from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useProductAuth } from '../product-auth/product-auth-provider'
import './users-page.css'

type ProductAuthUser = {
    id: string
    username: string
    display_name: string
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

export function UsersPage() {
    const { t, i18n } = useTranslation('shell')
    const { refresh, status } = useProductAuth()
    const [feedback, setFeedback] = useState<{ severity: 'success' | 'error'; message: string } | null>(null)
    const [searchValue, setSearchValue] = useState('')
    const [activeDialog, setActiveDialog] = useState<UserDialogState>(null)
    const [createDraft, setCreateDraft] = useState({ username: '', displayName: '', locale: i18n.resolvedLanguage ?? 'en', password: '', confirmPassword: '' })
    const [editDraft, setEditDraft] = useState({ displayName: '', password: '', confirmPassword: '' })
    const [isSubmitting, setIsSubmitting] = useState(false)

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

    const activeEditUser = activeDialog?.type === 'edit' ? activeDialog.user : null
    const createPasswordMismatch =
        Boolean(createDraft.password || createDraft.confirmPassword) && createDraft.password !== createDraft.confirmPassword
    const editPasswordMismatch = Boolean(editDraft.password || editDraft.confirmPassword) && editDraft.password !== editDraft.confirmPassword
    const hasEditChanges = activeEditUser
        ? editDraft.displayName.trim() !== activeEditUser.display_name || editDraft.password.trim().length > 0
        : false

    function openCreateDialog() {
        setCreateDraft({ username: '', displayName: '', locale: i18n.resolvedLanguage ?? 'en', password: '', confirmPassword: '' })
        setActiveDialog({ type: 'create' })
    }

    function openEditDialog(user: ProductAuthUser) {
        setEditDraft({ displayName: user.display_name, password: '', confirmPassword: '' })
        setActiveDialog({ type: 'edit', user })
    }

    async function handleCreateUser() {
        setIsSubmitting(true)
        setFeedback(null)

        try {
            const createdUser = await requestJson<ProductAuthUser>('/api/auth/users', {
                method: 'POST',
                body: JSON.stringify({
                    username: createDraft.username,
                    display_name: createDraft.displayName,
                    locale: createDraft.locale,
                    password: createDraft.password,
                }),
            })
            await Promise.all([refetch(), refresh()])
            setActiveDialog(null)
            setCreateDraft({ username: '', displayName: '', locale: i18n.resolvedLanguage ?? 'en', password: '', confirmPassword: '' })
            setFeedback({ severity: 'success', message: t('usersPage.feedback.createSuccess', { username: createdUser.username }) })
        } catch (submitError) {
            setFeedback({
                severity: 'error',
                message: submitError instanceof Error ? submitError.message : t('usersPage.feedback.genericError'),
            })
        } finally {
            setIsSubmitting(false)
        }
    }

    async function handleEditUser() {
        if (!activeEditUser) {
            return
        }

        setIsSubmitting(true)
        setFeedback(null)

        try {
            if (editDraft.displayName.trim() !== activeEditUser.display_name) {
                await requestJson<ProductAuthUser>(`/api/auth/users/${activeEditUser.id}`, {
                    method: 'PUT',
                    body: JSON.stringify({
                        display_name: editDraft.displayName,
                        locale: activeEditUser.locale,
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
            setEditDraft({ displayName: '', password: '', confirmPassword: '' })
            setFeedback({ severity: 'success', message: t('usersPage.feedback.editSuccess', { username: activeEditUser.username }) })
        } catch (submitError) {
            setFeedback({
                severity: 'error',
                message: submitError instanceof Error ? submitError.message : t('usersPage.feedback.genericError'),
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
        <Box className="users-page" sx={{ px: { xs: 0.5, md: 1 }, py: { xs: 1, md: 1.5 } }}>
            <Stack spacing={2.5}>
                <Box className="users-header">
                    <Typography className="users-page-title" component="h1">
                        {t('usersPage.hero.title')}
                    </Typography>

                    <Box className="users-toolbar">
                        <TextField
                            className="users-toolbar-field users-toolbar-search"
                            onChange={(event) => setSearchValue(event.target.value)}
                            placeholder={t('usersPage.filters.searchPlaceholder')}
                            size="small"
                            value={searchValue}
                        />
                        {currentUserIsSystem ? (
                            <Button className="users-toolbar-button" onClick={openCreateDialog} variant="contained">
                                {t('usersPage.create.submit')}
                            </Button>
                        ) : null}
                    </Box>
                </Box>

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

                <Paper className="users-panel" elevation={0}>
                    <Box className="users-table-meta">
                        {isFetching && !isLoading ? t('usersPage.states.refreshing') : t('usersPage.list.meta', { count: filteredUsers.length })}
                    </Box>

                    {isLoading ? (
                        <Box className="users-loading">
                            <CircularProgress size={18} />
                            <Typography color="text.secondary" variant="body2">
                                {t('usersPage.states.loading')}
                            </Typography>
                        </Box>
                    ) : null}

                    {!isLoading && users.length === 0 ? (
                        <Box className="users-empty-state">
                            <Alert severity="info" variant="outlined">
                                {t('usersPage.states.empty')}
                            </Alert>
                        </Box>
                    ) : null}

                    {!isLoading && users.length > 0 && filteredUsers.length === 0 ? (
                        <Box className="users-empty-state">
                            <Alert severity="info" variant="outlined">
                                {t('usersPage.states.noResults')}
                            </Alert>
                        </Box>
                    ) : null}

                    {!isLoading && filteredUsers.length > 0 ? (
                        <TableContainer>
                            <Table className="users-table">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>{t('usersPage.columns.username')}</TableCell>
                                        <TableCell>{t('usersPage.columns.displayName')}</TableCell>
                                        <TableCell>{t('usersPage.columns.language')}</TableCell>
                                        <TableCell>{t('usersPage.columns.status')}</TableCell>
                                        <TableCell>{t('usersPage.columns.createdAt')}</TableCell>
                                        <TableCell align="right">{t('usersPage.columns.actions')}</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {filteredUsers.map((user) => {
                                        const isCurrentUser = currentUserId === user.id
                                        const canEditUser = currentUserIsSystem || isCurrentUser
                                        const canDeleteUser = currentUserIsSystem && user.delete_eligible
                                        const canToggleUser = currentUserIsSystem && user.delete_eligible && !isCurrentUser
                                        return (
                                            <TableRow key={user.id}>
                                                <TableCell>
                                                    <Stack className="users-identity-cell" spacing={0.75}>
                                                        <Typography className="users-linkish">{user.username}</Typography>
                                                        <Box className="users-inline-tags">
                                                            {isCurrentUser ? <Chip label={t('usersPage.badges.current')} size="small" /> : null}
                                                            {!user.delete_eligible ? (
                                                                <Chip color="warning" label={t('usersPage.badges.initialized')} size="small" variant="outlined" />
                                                            ) : null}
                                                        </Box>
                                                    </Stack>
                                                </TableCell>
                                                <TableCell>{user.display_name}</TableCell>
                                                <TableCell>{formatUserLocale(user.locale)}</TableCell>
                                                <TableCell>
                                                    <Chip
                                                        color={user.disabled ? 'default' : 'success'}
                                                        label={user.disabled ? t('usersPage.status.disabled') : t('usersPage.status.enabled')}
                                                        size="small"
                                                        variant={user.disabled ? 'outlined' : 'filled'}
                                                    />
                                                </TableCell>
                                                <TableCell>{dateFormatter.format(new Date(user.created_at))}</TableCell>
                                                <TableCell align="right">
                                                    {canEditUser || canDeleteUser || canToggleUser ? (
                                                        <Box className="users-row-actions">
                                                            {canEditUser ? (
                                                                <Button disabled={isSubmitting} onClick={() => openEditDialog(user)} size="small" variant="outlined">
                                                                    {t('usersPage.actions.edit')}
                                                                </Button>
                                                            ) : null}
                                                            {canToggleUser ? (
                                                                <Button disabled={isSubmitting} onClick={() => void handleToggleUserEnabled(user)} size="small" variant="outlined">
                                                                    {user.disabled ? t('usersPage.actions.enable') : t('usersPage.actions.disable')}
                                                                </Button>
                                                            ) : null}
                                                            {canDeleteUser ? (
                                                                <Button
                                                                    color="error"
                                                                    disabled={isSubmitting}
                                                                    onClick={() => setActiveDialog({ type: 'delete', user })}
                                                                    size="small"
                                                                    variant="outlined"
                                                                >
                                                                    {t('usersPage.actions.delete')}
                                                                </Button>
                                                            ) : null}
                                                        </Box>
                                                    ) : null}
                                                </TableCell>
                                            </TableRow>
                                        )
                                    })}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    ) : null}
                </Paper>
            </Stack>

            <Dialog
                fullWidth
                maxWidth="sm"
                onClose={() => {
                    if (!isSubmitting) {
                        setActiveDialog(null)
                    }
                }}
                open={activeDialog?.type === 'create'}
            >
                <DialogTitle>{t('usersPage.dialogs.createTitle')}</DialogTitle>
                <DialogContent>
                    <Stack spacing={2} sx={{ pt: 1 }}>
                        <TextField
                            autoFocus
                            label={t('auth.fields.username')}
                            onChange={(event) => setCreateDraft((current) => ({ ...current, username: event.target.value }))}
                            value={createDraft.username}
                        />
                        <TextField
                            label={t('auth.fields.displayName')}
                            onChange={(event) => setCreateDraft((current) => ({ ...current, displayName: event.target.value }))}
                            value={createDraft.displayName}
                        />
                        <TextField
                            select
                            label={t('usersPage.fields.language')}
                            onChange={(event) => setCreateDraft((current) => ({ ...current, locale: event.target.value }))}
                            value={createDraft.locale}
                        >
                            {localeOptions.map((option) => (
                                <MenuItem key={option.value} value={option.value}>
                                    {option.label}
                                </MenuItem>
                            ))}
                        </TextField>
                        <TextField
                            helperText={t('usersPage.fields.passwordHelper')}
                            label={t('auth.fields.password')}
                            onChange={(event) => setCreateDraft((current) => ({ ...current, password: event.target.value }))}
                            error={createPasswordMismatch}
                            type="password"
                            value={createDraft.password}
                        />
                        <TextField
                            helperText={createPasswordMismatch ? t('usersPage.fields.passwordMismatch') : ' '}
                            label={t('usersPage.fields.confirmPassword')}
                            onChange={(event) => setCreateDraft((current) => ({ ...current, confirmPassword: event.target.value }))}
                            error={createPasswordMismatch}
                            type="password"
                            value={createDraft.confirmPassword}
                        />
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setActiveDialog(null)}>{t('usersPage.dialogs.cancel')}</Button>
                    <Button
                        disabled={
                            isSubmitting ||
                            !createDraft.username.trim() ||
                            !createDraft.displayName.trim() ||
                            !createDraft.password.trim() ||
                            !createDraft.confirmPassword.trim() ||
                            createPasswordMismatch
                        }
                        onClick={() => void handleCreateUser()}
                        variant="contained"
                    >
                        {isSubmitting ? t('usersPage.create.submitting') : t('usersPage.dialogs.confirmCreate')}
                    </Button>
                </DialogActions>
            </Dialog>

            <Dialog
                fullWidth
                maxWidth="sm"
                onClose={() => {
                    if (!isSubmitting) {
                        setActiveDialog(null)
                    }
                }}
                open={activeDialog?.type === 'edit'}
            >
                <DialogTitle>{t('usersPage.dialogs.editTitle')}</DialogTitle>
                <DialogContent>
                    <Stack spacing={2} sx={{ pt: 1 }}>
                        <TextField
                            disabled
                            helperText={t('usersPage.fields.usernameReadonly')}
                            label={t('auth.fields.username')}
                            value={activeEditUser?.username ?? ''}
                        />
                        <TextField
                            label={t('auth.fields.displayName')}
                            onChange={(event) => setEditDraft((current) => ({ ...current, displayName: event.target.value }))}
                            value={editDraft.displayName}
                        />
                        <TextField
                            helperText={t('usersPage.fields.passwordOptional')}
                            label={t('usersPage.fields.newPassword')}
                            onChange={(event) => setEditDraft((current) => ({ ...current, password: event.target.value }))}
                            error={editPasswordMismatch}
                            type="password"
                            value={editDraft.password}
                        />
                        <TextField
                            helperText={editPasswordMismatch ? t('usersPage.fields.passwordMismatch') : ' '}
                            label={t('usersPage.fields.confirmPassword')}
                            onChange={(event) => setEditDraft((current) => ({ ...current, confirmPassword: event.target.value }))}
                            error={editPasswordMismatch}
                            type="password"
                            value={editDraft.confirmPassword}
                        />
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setActiveDialog(null)}>{t('usersPage.dialogs.cancel')}</Button>
                    <Button disabled={isSubmitting || !hasEditChanges || editPasswordMismatch} onClick={() => void handleEditUser()} variant="contained">
                        {isSubmitting ? t('usersPage.dialogs.saving') : t('usersPage.dialogs.confirmEdit')}
                    </Button>
                </DialogActions>
            </Dialog>

            <Dialog
                fullWidth
                maxWidth="xs"
                onClose={() => {
                    if (!isSubmitting) {
                        setActiveDialog(null)
                    }
                }}
                open={activeDialog?.type === 'delete'}
            >
                <DialogTitle>{t('usersPage.dialogs.deleteTitle')}</DialogTitle>
                <DialogContent>
                    <Typography color="text.secondary" sx={{ pt: 1 }} variant="body2">
                        {activeDialog?.type === 'delete' ? t('usersPage.dialogs.deleteBody', { username: activeDialog.user.username }) : ''}
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setActiveDialog(null)}>{t('usersPage.dialogs.cancel')}</Button>
                    <Button color="error" disabled={isSubmitting} onClick={() => void handleDeleteUser()} variant="contained">
                        {isSubmitting ? t('usersPage.dialogs.deleting') : t('usersPage.dialogs.confirmDelete')}
                    </Button>
                </DialogActions>
            </Dialog>

            <Snackbar open={Boolean(feedback)} autoHideDuration={3000} onClose={() => setFeedback(null)} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
                <Alert onClose={() => setFeedback(null)} severity={feedback?.severity ?? 'info'} variant="filled" elevation={6} sx={{ width: '100%' }}>
                    {feedback?.message}
                </Alert>
            </Snackbar>
        </Box>
    )
}