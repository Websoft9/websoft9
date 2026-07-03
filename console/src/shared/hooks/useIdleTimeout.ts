import { useEffect, useRef } from 'react'

const DEFAULT_IDLE_TIMEOUT_MS = 30 * 60 * 1000 // 30 minutes

/**
 * Calls `onIdle` after the user has been idle (no mouse, keyboard, touch, or scroll events)
 * for the specified duration. The timer resets on any user interaction.
 */
export function useIdleTimeout(
    onIdle: () => void,
    { timeoutMs = DEFAULT_IDLE_TIMEOUT_MS, enabled = true }: { timeoutMs?: number; enabled?: boolean } = {},
) {
    const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const onIdleRef = useRef(onIdle)

    // Keep the callback ref up to date without restarting the timer
    onIdleRef.current = onIdle

    useEffect(() => {
        if (!enabled) {
            return
        }

        function resetTimer() {
            if (idleTimerRef.current) {
                clearTimeout(idleTimerRef.current)
            }

            idleTimerRef.current = setTimeout(() => {
                onIdleRef.current()
            }, timeoutMs)
        }

        const events: Array<keyof WindowEventMap> = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll']

        for (const event of events) {
            window.addEventListener(event, resetTimer, { passive: true })
        }

        // Start the initial timer
        resetTimer()

        return () => {
            if (idleTimerRef.current) {
                clearTimeout(idleTimerRef.current)
            }

            for (const event of events) {
                window.removeEventListener(event, resetTimer)
            }
        }
    }, [timeoutMs, enabled])
}
