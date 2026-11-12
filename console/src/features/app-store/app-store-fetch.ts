export class AppStoreAssetsUnavailableError extends Error {
    readonly statusCode = 503
}

export async function fetchAppStoreJson<T>(url: string, errorMessage: string): Promise<T> {
    const response = await fetch(url, { headers: { Accept: 'application/json' } })
    if (!response.ok) {
        if (response.status === 503) {
            let payload: unknown
            try {
                payload = JSON.parse(await response.text())
            } catch (error) {
                if (!(error instanceof SyntaxError)) {
                    throw error
                }
            }
            if (typeof payload === 'object' && payload !== null
                && 'message' in payload && payload.message === 'App Store Assets Unavailable') {
                throw new AppStoreAssetsUnavailableError(errorMessage)
            }
        }
        const error: Error & { statusCode?: number } = new Error(`${errorMessage}: ${response.status}`)
        error.statusCode = response.status
        throw error
    }
    return await response.json() as T
}

export async function fetchAppStoreWithFallback<T>(
    apiUrl: string,
    errorMessage: string,
    loadStatic: () => Promise<T>,
): Promise<T> {
    try {
        return await fetchAppStoreJson<T>(apiUrl, errorMessage)
    } catch (error) {
        if (error instanceof AppStoreAssetsUnavailableError) {
            throw error
        }
        return loadStatic()
    }
}
