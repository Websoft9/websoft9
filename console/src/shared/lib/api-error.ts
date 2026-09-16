const PLATFORM_UNAVAILABLE_STATUS_PATTERN = /\b(?:500|502|503|504)\b/
const PLATFORM_UNAVAILABLE_MESSAGE_PATTERN = /(?:failed to fetch|networkerror|network request failed|load failed|request timed out|timeout)/i

export function isPlatformUnavailableError(error: unknown) {
    if (!(error instanceof Error)) {
        return false
    }

    const statusCode = (error as Error & { statusCode?: number; status?: number }).statusCode
        ?? (error as Error & { status?: number }).status
    if (statusCode === 500 || statusCode === 502 || statusCode === 503 || statusCode === 504) {
        return true
    }

    return PLATFORM_UNAVAILABLE_STATUS_PATTERN.test(error.message) || PLATFORM_UNAVAILABLE_MESSAGE_PATTERN.test(error.message)
}