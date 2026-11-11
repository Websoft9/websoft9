export type DatabaseEndpoint = {
    host: string
    port: number
}

type PortCandidate = {
    container_name?: string
    forward_port?: number
    published_ports?: string[]
}

/**
 * Resolve the address other containers use for a service-style application.
 *
 * The access tab shows two addresses: the host port published by Compose and the address other
 * containers connect to. The latter is the container name plus the private port the published
 * host port maps to. Container metadata is the only correct source here: applications that *are*
 * the database (MySQL, Redis, MongoDB) never declare ``database[]``, which describes an
 * application that *uses* a database.
 */
export function resolveEndpointFromCandidates(
    candidates: PortCandidate[] | undefined | null,
    hostPorts: string[],
): DatabaseEndpoint | null {
    if (!Array.isArray(candidates) || candidates.length === 0) return null

    const usable = candidates.filter(
        (candidate): candidate is PortCandidate & { container_name: string; forward_port: number } =>
            typeof candidate.container_name === 'string' &&
            candidate.container_name.trim() !== '' &&
            typeof candidate.forward_port === 'number',
    )
    if (usable.length === 0) return null

    for (const hostPort of hostPorts) {
        const wanted = hostPort.trim()
        if (!wanted) continue
        for (const candidate of usable) {
            const pair = (candidate.published_ports ?? []).find((entry) => entry.split(':')[0] === wanted)
            if (!pair) continue
            const privatePort = Number(pair.split(':')[1])
            if (Number.isFinite(privatePort) && privatePort > 0) {
                return { host: candidate.container_name, port: privatePort }
            }
        }
    }

    // A single container with a single port: nothing to disambiguate.
    const unique = new Map(usable.map((candidate) => [candidate.container_name, candidate]))
    if (unique.size === 1) {
        const [candidate] = [...unique.values()]
        return { host: candidate.container_name, port: candidate.forward_port }
    }
    return null
}

/** `host:port` for the container network, or `null` when the endpoint is unknown. */
export function formatDatabaseEndpoint(endpoint: DatabaseEndpoint | null): string | null {
    if (!endpoint) return null
    return `${endpoint.host}:${endpoint.port}`
}
