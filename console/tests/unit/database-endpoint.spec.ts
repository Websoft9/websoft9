import { expect, test } from '@playwright/test'

import { formatDatabaseEndpoint, resolveEndpointFromCandidates } from '../../src/features/my-apps/database-endpoint'

/**
 * The access tab shows the address other containers use next to the published host port. That
 * address comes from the container itself — name plus the private port the host port maps to —
 * because an application that *is* the database never declares ``database[]``.
 */

test('the endpoint is formatted as host:port', () => {
    expect(formatDatabaseEndpoint({ host: 'mysql_w8tab', port: 3306 })).toBe('mysql_w8tab:3306')
    expect(formatDatabaseEndpoint(null)).toBeNull()
})

test('a database server resolves through its container port mapping', () => {
    const endpoint = resolveEndpointFromCandidates(
        [{ container_name: 'mysql_w8tab', forward_port: 3306, published_ports: ['9001:3306'] }],
        ['9001'],
    )

    expect(endpoint).toEqual({ host: 'mysql_w8tab', port: 3306 })
})

test('the mapping wins over the first exposed port when several containers exist', () => {
    const endpoint = resolveEndpointFromCandidates(
        [
            { container_name: 'app-web', forward_port: 80, published_ports: ['9000:80'] },
            { container_name: 'app-db', forward_port: 5432, published_ports: ['9001:5432'] },
        ],
        ['9001'],
    )

    expect(endpoint).toEqual({ host: 'app-db', port: 5432 })
})

test('a single unmapped container is still usable', () => {
    expect(resolveEndpointFromCandidates([{ container_name: 'redis_x1', forward_port: 6379 }], ['6380'])).toEqual({
        host: 'redis_x1',
        port: 6379,
    })
})

test('no candidate means no endpoint', () => {
    expect(resolveEndpointFromCandidates(undefined, ['9001'])).toBeNull()
    expect(resolveEndpointFromCandidates([], ['9001'])).toBeNull()
    expect(
        resolveEndpointFromCandidates(
            [
                { container_name: 'a', forward_port: 1, published_ports: [] },
                { container_name: 'b', forward_port: 2, published_ports: [] },
            ],
            ['9001'],
        ),
    ).toBeNull()
})
