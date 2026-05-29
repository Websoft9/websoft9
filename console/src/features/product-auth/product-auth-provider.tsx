import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { i18n, normalizeSupportedLocale } from '../../shared/i18n/i18n'

const PRODUCT_AUTH_STATUS_STORAGE_KEY = 'websoft9:product-auth-status'

type ProductAuthUser = {
    id: string
    username: string
    display_name: string
    locale: string
    disabled: boolean
    deleted: boolean
    reset_password_eligible: boolean
    created_at: string
}

type ProductAuthStatus = {
    enabled: boolean
    initialization_required: boolean
    authenticated: boolean
    protected_modules: string[]
    current_user: ProductAuthUser | null
    storage_boundary?: {
        asset_group: string
        backup_scope: string
        separated_from_integrations: boolean
    }
}

type ProductAuthContextValue = {
    errorMessage: string | null
    isLoading: boolean
    isSubmitting: boolean
    status: ProductAuthStatus | null
    initialize: (payload: { username: string; password: string; displayName: string }) => Promise<ProductAuthStatus>
    login: (payload: { username: string; password: string }) => Promise<ProductAuthStatus>
    logout: () => Promise<void>
    refresh: () => Promise<ProductAuthStatus>
}

const ProductAuthContext = createContext<ProductAuthContextValue | null>(null)

type ProductAuthBootstrapState = {
    status: ProductAuthStatus | null
    isLoading: boolean
    hydratedFromSnapshot: boolean
}

function isAuthRoute(pathname: string) {
    return /^\/auth\/(login|setup)(?:[/?#]|$)/.test(pathname)
}

function readPersistedProductAuthStatus(): ProductAuthBootstrapState {
    if (typeof window === 'undefined') {
        return { status: null, isLoading: true, hydratedFromSnapshot: false }
    }

    try {
        const rawSnapshot = window.sessionStorage.getItem(PRODUCT_AUTH_STATUS_STORAGE_KEY)
        if (!rawSnapshot) {
            return { status: null, isLoading: true, hydratedFromSnapshot: false }
        }

        const snapshot = JSON.parse(rawSnapshot) as { status?: ProductAuthStatus } | null
        const status = snapshot?.status ?? null
        if (!status?.authenticated || isAuthRoute(window.location.pathname)) {
            return { status: null, isLoading: true, hydratedFromSnapshot: false }
        }

        return { status, isLoading: false, hydratedFromSnapshot: true }
    } catch {
        return { status: null, isLoading: true, hydratedFromSnapshot: false }
    }
}

function persistProductAuthStatus(status: ProductAuthStatus) {
    if (typeof window === 'undefined') {
        return
    }

    try {
        window.sessionStorage.setItem(
            PRODUCT_AUTH_STATUS_STORAGE_KEY,
            JSON.stringify({
                savedAt: Date.now(),
                status,
            }),
        )
    } catch {
        // Ignore storage failures and continue using in-memory auth state.
    }
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

export function ProductAuthProvider({ children }: { children: ReactNode }) {
    const bootstrapStateRef = useRef<ProductAuthBootstrapState>(readPersistedProductAuthStatus())
    const [status, setStatus] = useState<ProductAuthStatus | null>(bootstrapStateRef.current.status)
    const [isLoading, setIsLoading] = useState(bootstrapStateRef.current.isLoading)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)

    const applyStatus = useCallback((nextStatus: ProductAuthStatus) => {
        setStatus(nextStatus)
        persistProductAuthStatus(nextStatus)
    }, [])

    const refresh = useCallback(async () => {
        const nextStatus = await requestJson<ProductAuthStatus>('/api/auth/status', { method: 'GET' })
        applyStatus(nextStatus)
        setErrorMessage(null)
        return nextStatus
    }, [applyStatus])

    useEffect(() => {
        let active = true
        const hydratedFromSnapshot = bootstrapStateRef.current.hydratedFromSnapshot

        void requestJson<ProductAuthStatus>('/api/auth/status', { method: 'GET' })
            .then((payload) => {
                if (!active) {
                    return
                }
                applyStatus(payload)
                setErrorMessage(null)
            })
            .catch((error: unknown) => {
                if (!active) {
                    return
                }
                if (!hydratedFromSnapshot) {
                    setErrorMessage(error instanceof Error ? error.message : 'Failed to load authentication state')
                }
            })
            .finally(() => {
                if (!active) {
                    return
                }
                setIsLoading(false)
            })

        return () => {
            active = false
        }
    }, [applyStatus])

    useEffect(() => {
        const nextLocale = status?.current_user?.locale
        const normalizedLocale = normalizeSupportedLocale(nextLocale)
        if (!nextLocale || i18n.resolvedLanguage === normalizedLocale || i18n.language === normalizedLocale) {
            return
        }

        void i18n.changeLanguage(normalizedLocale)
    }, [status?.current_user?.locale])

    const initialize = useCallback(async (payload: { username: string; password: string; displayName: string }) => {
        setIsSubmitting(true)
        try {
            const nextStatus = await requestJson<ProductAuthStatus>('/api/auth/initialize', {
                method: 'POST',
                body: JSON.stringify({
                    username: payload.username,
                    password: payload.password,
                    display_name: payload.displayName,
                    locale: normalizeSupportedLocale(i18n.resolvedLanguage ?? i18n.language ?? 'en'),
                }),
            })
            applyStatus(nextStatus)
            setErrorMessage(null)
            return nextStatus
        } catch (error) {
            const nextMessage = error instanceof Error ? error.message : 'Failed to initialize operator account'
            setErrorMessage(nextMessage)
            throw error
        } finally {
            setIsSubmitting(false)
        }
    }, [applyStatus])

    const login = useCallback(async (payload: { username: string; password: string }) => {
        setIsSubmitting(true)
        try {
            const nextStatus = await requestJson<ProductAuthStatus>('/api/auth/login', {
                method: 'POST',
                body: JSON.stringify(payload),
            })
            applyStatus(nextStatus)
            setErrorMessage(null)
            return nextStatus
        } catch (error) {
            const nextMessage = error instanceof Error ? error.message : 'Failed to sign in'
            setErrorMessage(nextMessage)
            throw error
        } finally {
            setIsSubmitting(false)
        }
    }, [applyStatus])

    const logout = useCallback(async () => {
        setIsSubmitting(true)
        try {
            await requestJson<ProductAuthStatus>('/api/auth/logout', { method: 'POST' })
            await refresh()
        } finally {
            setIsSubmitting(false)
        }
    }, [refresh])

    const value = useMemo<ProductAuthContextValue>(
        () => ({
            errorMessage,
            isLoading,
            isSubmitting,
            status,
            initialize,
            login,
            logout,
            refresh,
        }),
        [errorMessage, initialize, isLoading, isSubmitting, login, logout, refresh, status],
    )

    return <ProductAuthContext.Provider value={value}>{children}</ProductAuthContext.Provider>
}

export function useProductAuth() {
    const context = useContext(ProductAuthContext)
    if (!context) {
        throw new Error('useProductAuth must be used inside ProductAuthProvider')
    }
    return context
}