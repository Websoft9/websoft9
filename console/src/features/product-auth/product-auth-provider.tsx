import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { i18n, normalizeSupportedLocale } from '../../shared/i18n/i18n'

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
    const [status, setStatus] = useState<ProductAuthStatus | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)

    const refresh = useCallback(async () => {
        const nextStatus = await requestJson<ProductAuthStatus>('/api/auth/status', { method: 'GET' })
        setStatus(nextStatus)
        setErrorMessage(null)
        return nextStatus
    }, [])

    useEffect(() => {
        let active = true

        void requestJson<ProductAuthStatus>('/api/auth/status', { method: 'GET' })
            .then((payload) => {
                if (!active) {
                    return
                }
                setStatus(payload)
                setErrorMessage(null)
            })
            .catch((error: unknown) => {
                if (!active) {
                    return
                }
                setErrorMessage(error instanceof Error ? error.message : 'Failed to load authentication state')
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
    }, [])

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
            setStatus(nextStatus)
            setErrorMessage(null)
            return nextStatus
        } catch (error) {
            const nextMessage = error instanceof Error ? error.message : 'Failed to initialize operator account'
            setErrorMessage(nextMessage)
            throw error
        } finally {
            setIsSubmitting(false)
        }
    }, [])

    const login = useCallback(async (payload: { username: string; password: string }) => {
        setIsSubmitting(true)
        try {
            const nextStatus = await requestJson<ProductAuthStatus>('/api/auth/login', {
                method: 'POST',
                body: JSON.stringify(payload),
            })
            setStatus(nextStatus)
            setErrorMessage(null)
            return nextStatus
        } catch (error) {
            const nextMessage = error instanceof Error ? error.message : 'Failed to sign in'
            setErrorMessage(nextMessage)
            throw error
        } finally {
            setIsSubmitting(false)
        }
    }, [])

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