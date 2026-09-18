import { Alert, Button } from '@mui/material'
import { useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { PRODUCT_AUTH_UNAUTHORIZED_EVENT, useProductAuth } from '../../features/product-auth/product-auth-provider'
import { useUpgradeInProgress } from '../upgrade-status'

const CONNECTION_FAILURE_EVENT = 'websoft9:connection-failure'
const CONNECTION_UNAVAILABLE_EVENT = 'websoft9:connection-unavailable'
const CONNECTION_RESTORED_EVENT = 'websoft9:connection-restored'
const HEALTH_CHECK_PATH = '/api/healthz'
const HEARTBEAT_INTERVAL_MS = 10_000
const RETRY_INTERVAL_MS = 2_000
const FAILURE_THRESHOLD = 2
const API_REQUEST_TIMEOUT_MS = 30_000

type FetchInput = RequestInfo | URL

const ConnectionStatusContext = createContext(false)

export function useConnectionUnavailable() {
    return useContext(ConnectionStatusContext)
}

function getRequestPath(input: FetchInput): string | null {
    try {
        const url = input instanceof Request ? input.url : input instanceof URL ? input.href : input
        return new URL(url, window.location.href).pathname
    } catch {
        return null
    }
}

function isApiRequest(input: FetchInput) {
    const pathname = getRequestPath(input)
    return pathname?.startsWith('/api/') ?? false
}

function isExpectedAuthenticationRequest(input: FetchInput) {
    const pathname = getRequestPath(input)
    return pathname === '/api/auth/login' || pathname === '/api/auth/initialize'
}

function isConnectionFailure(response: Response) {
    return [500, 502, 503, 504].includes(response.status)
}

export function ConnectionProvider({ children }: { children: ReactNode }) {
    const { t } = useTranslation('shell')
    const { refresh, status } = useProductAuth()
    const queryClient = useQueryClient()
    // An upgrade recreates the platform container on purpose; the mask explains it, so the
    // connection banner must not pile a second "service unavailable" report on top.
    const upgradeInProgress = useUpgradeInProgress()
    const [isUnavailable, setIsUnavailable] = useState(false)
    const originalFetchRef = useRef<typeof window.fetch | null>(null)
    const unavailableRef = useRef(false)
    const heartbeatFailuresRef = useRef(0)
    const isConfirmingUnavailableRef = useRef(false)

    useEffect(() => {
        unavailableRef.current = isUnavailable
    }, [isUnavailable])

    useEffect(() => {
        if (originalFetchRef.current) {
            return
        }

        const originalFetch = window.fetch.bind(window)
        originalFetchRef.current = originalFetch
        window.fetch = async (input: FetchInput, init?: RequestInit) => {
            const isApi = isApiRequest(input)
            const timeoutController = isApi ? new AbortController() : null
            const timeoutId = timeoutController
                ? window.setTimeout(() => timeoutController.abort(), API_REQUEST_TIMEOUT_MS)
                : undefined
            const requestInit = timeoutController
                ? {
                    ...init,
                    signal: init?.signal
                        ? AbortSignal.any([init.signal, timeoutController.signal])
                        : timeoutController.signal,
                }
                : init
            try {
                const response = await originalFetch(input, requestInit)
                if (isApi && !isExpectedAuthenticationRequest(input)) {
                    if (response.status === 401) {
                        window.dispatchEvent(new CustomEvent(PRODUCT_AUTH_UNAUTHORIZED_EVENT))
                    } else if (isConnectionFailure(response)) {
                        window.dispatchEvent(new CustomEvent(CONNECTION_FAILURE_EVENT))
                    }
                }
                return response
            } catch (error) {
                const isAbortError = typeof error === 'object' && error !== null && (error as { name?: string }).name === 'AbortError'
                const timedOut = timeoutController?.signal.aborted ?? false
                if (isApi && (!isAbortError || timedOut)) {
                    window.dispatchEvent(new CustomEvent(CONNECTION_FAILURE_EVENT))
                }
                throw error
            } finally {
                if (timeoutId !== undefined) {
                    window.clearTimeout(timeoutId)
                }
            }
        }

        return () => {
            window.fetch = originalFetch
            originalFetchRef.current = null
        }
    }, [])

    useEffect(() => {
        function markUnavailable() {
            if (status?.authenticated) {
                setIsUnavailable(true)
            }
        }

        function markRestored() {
            heartbeatFailuresRef.current = 0
            setIsUnavailable(false)
            void queryClient.invalidateQueries()
        }

        async function confirmUnavailable() {
            if (!status?.authenticated || !originalFetchRef.current || isConfirmingUnavailableRef.current) {
                return
            }

            isConfirmingUnavailableRef.current = true
            try {
                const response = await originalFetchRef.current(HEALTH_CHECK_PATH, {
                    credentials: 'include',
                    cache: 'no-store',
                })
                if (response.status === 401) {
                    window.dispatchEvent(new CustomEvent(PRODUCT_AUTH_UNAUTHORIZED_EVENT))
                    return
                }
                if (response.ok) {
                    heartbeatFailuresRef.current = 0
                    if (unavailableRef.current) {
                        markRestored()
                    }
                    return
                }
            } catch {
                // Treat an unreachable health endpoint as a confirmed connection failure.
            } finally {
                isConfirmingUnavailableRef.current = false
            }

            markUnavailable()
        }

        const handleConnectionFailure = () => void confirmUnavailable()
        window.addEventListener(CONNECTION_FAILURE_EVENT, handleConnectionFailure)
        window.addEventListener(CONNECTION_UNAVAILABLE_EVENT, markUnavailable)
        window.addEventListener(CONNECTION_RESTORED_EVENT, markRestored)
        window.addEventListener('offline', markUnavailable)
        return () => {
            window.removeEventListener(CONNECTION_FAILURE_EVENT, handleConnectionFailure)
            window.removeEventListener(CONNECTION_UNAVAILABLE_EVENT, markUnavailable)
            window.removeEventListener(CONNECTION_RESTORED_EVENT, markRestored)
            window.removeEventListener('offline', markUnavailable)
        }
    }, [queryClient, status?.authenticated])

    useEffect(() => {
        if (!status?.authenticated || !originalFetchRef.current) {
            return
        }

        let cancelled = false
        let timer: number | undefined
        const originalFetch = originalFetchRef.current

        const schedule = (delay: number) => {
            timer = window.setTimeout(checkHealth, delay)
        }

        const checkHealth = async () => {
            if (cancelled || document.visibilityState !== 'visible') {
                schedule(HEARTBEAT_INTERVAL_MS)
                return
            }

            try {
                const response = await originalFetch(HEALTH_CHECK_PATH, {
                    credentials: 'include',
                    cache: 'no-store',
                })
                if (!response.ok) {
                    throw new Error(`Health check failed: ${response.status}`)
                }
                heartbeatFailuresRef.current = 0
                if (unavailableRef.current) {
                    const authStatus = await refresh()
                    if (!authStatus.authenticated) {
                        window.dispatchEvent(new CustomEvent(PRODUCT_AUTH_UNAUTHORIZED_EVENT))
                        return
                    }
                    window.dispatchEvent(new CustomEvent(CONNECTION_RESTORED_EVENT))
                }
                schedule(HEARTBEAT_INTERVAL_MS)
            } catch {
                heartbeatFailuresRef.current += 1
                if (heartbeatFailuresRef.current >= FAILURE_THRESHOLD) {
                    window.dispatchEvent(new CustomEvent(CONNECTION_UNAVAILABLE_EVENT))
                    schedule(RETRY_INTERVAL_MS)
                    return
                }
                schedule(HEARTBEAT_INTERVAL_MS)
            }
        }

        const handleOnline = () => {
            heartbeatFailuresRef.current = FAILURE_THRESHOLD
            void checkHealth()
        }
        const handleVisibilityChange = () => {
            if (document.visibilityState === 'visible') {
                void checkHealth()
            }
        }

        window.addEventListener('online', handleOnline)
        document.addEventListener('visibilitychange', handleVisibilityChange)
        schedule(HEARTBEAT_INTERVAL_MS)
        return () => {
            cancelled = true
            if (timer !== undefined) {
                window.clearTimeout(timer)
            }
            window.removeEventListener('online', handleOnline)
            document.removeEventListener('visibilitychange', handleVisibilityChange)
        }
    }, [refresh, status?.authenticated])

    return (
        <ConnectionStatusContext.Provider value={isUnavailable}>
            {children}
            {isUnavailable && !upgradeInProgress ? (
                <Alert
                    severity="warning"
                    role="status"
                    action={(
                        <Button
                            color="inherit"
                            onClick={() => window.dispatchEvent(new Event('online'))}
                            size="small"
                            sx={{ fontWeight: 700 }}
                        >
                            {t('connection.retry')}
                        </Button>
                    )}
                    sx={{
                        position: 'fixed',
                        top: 0,
                        right: 0,
                        left: 0,
                        zIndex: (theme) => theme.zIndex.modal + 1,
                        alignItems: 'center',
                        borderRadius: 0,
                        border: 0,
                        borderBottom: '1px solid #f2c779',
                        backgroundColor: '#fff7e6',
                        color: '#7a3e00',
                        '& .MuiAlert-icon': {
                            color: '#b45309',
                        },
                        '& .MuiAlert-message': {
                            flex: 1,
                            py: 0.25,
                        },
                    }}
                >
                    <strong>{t('connection.unavailableTitle')}</strong>{' '}
                    {t('connection.unavailableDetail')}
                </Alert>
            ) : null}
        </ConnectionStatusContext.Provider>
    )
}
