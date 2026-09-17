export type PortSuggestion = {
    key: string
    port: number | null
}

export type PortCheckResult = {
    port: number
    available: boolean
    reason: string | null
}

export type PortCheckStatus = 'checking' | 'available' | 'occupied' | 'failed' | 'invalid'

export function isPortSettingKey(key: string) {
    const normalizedKey = key.toUpperCase()
    return normalizedKey.includes('PORT_SET') && normalizedKey !== 'W9_DB_PORT_SET'
}

export async function fetchPortSuggestions(keys: string[]): Promise<PortSuggestion[]> {
    const response = await fetch('/api/ports/suggest', {
        method: 'POST',
        credentials: 'include',
        headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ports: keys.map((key) => ({ key })) }),
    })

    if (!response.ok) {
        throw new Error(`Failed to suggest free ports: ${response.status}`)
    }

    const payload = (await response.json()) as { suggestions?: PortSuggestion[] }
    return payload.suggestions ?? []
}

export async function checkPortAvailability(port: number): Promise<PortCheckResult> {
    const response = await fetch(`/api/ports/check?ports=${port}`, {
        credentials: 'include',
        headers: {
            Accept: 'application/json',
        },
    })

    if (!response.ok) {
        throw new Error(`Failed to check port ${port}: ${response.status}`)
    }

    const payload = (await response.json()) as { results?: PortCheckResult[] }
    const result = payload.results?.find((item) => item.port === port)
    if (!result) {
        throw new Error(`Missing port check result for ${port}`)
    }
    return result
}
