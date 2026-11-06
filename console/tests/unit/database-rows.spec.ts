import { expect, test } from '@playwright/test'

import {
    buildDatabaseRows,
    formatDatabaseNames,
    formatDatabaseRoles,
    formatDatabaseTypeLabel,
} from '../../src/features/my-apps/my-app-database-rows'
import type { AppDatabaseComponent } from '../../src/features/my-apps/use-app-databases'

/**
 * The flat database table (方案 A) shows one line per usable connection. The
 * conversion from the API payload is pure, so the rules that matter can be
 * asserted here: one row per account, a row without accounts still visible, and
 * unknown values kept as `null` instead of a placeholder.
 */

function component(overrides: Partial<AppDatabaseComponent> = {}): AppDatabaseComponent {
    return {
        id: 'rds',
        driver: 'mysql',
        service: 'mysql',
        mode: 'internal',
        host: 'wordpress_ab12-mysql',
        port: 3306,
        port_from_dictionary: true,
        names: ['wordpress'],
        accounts: [],
        auth: 'none',
        unknown_fields: [],
        tools: [],
        ...overrides,
    }
}

const t = (key: string) => key.replace('myAppsDetailPage.tabs.database.', '')

test.describe('database table rows', () => {
    test('one row per account, each with the shared address and names', () => {
        const rows = buildDatabaseRows([
            component({
                accounts: [
                    { user: 'root', usage: ['administration'], password: 'secret' },
                    { user: 'wordpress', usage: ['application'], password: null },
                ],
                auth: 'password',
            }),
        ])

        expect(rows).toHaveLength(2)
        expect(rows.map((row) => row.user)).toEqual(['root', 'wordpress'])
        expect(rows.every((row) => row.host === 'wordpress_ab12-mysql')).toBe(true)
        expect(rows.every((row) => row.port === 3306)).toBe(true)
        expect(rows.every((row) => row.names.join() === 'wordpress')).toBe(true)
        expect(rows[1].password).toBeNull()
    })

    test('a component without accounts still gets one row', () => {
        const rows = buildDatabaseRows([component({ names: ['graylog'], auth: 'none' })])

        expect(rows).toHaveLength(1)
        expect(rows[0].user).toBeNull()
        expect(rows[0].auth).toBe('none')
        expect(rows[0].names).toEqual(['graylog'])
    })

    test('unknown authentication is not turned into "no authentication"', () => {
        const rows = buildDatabaseRows([component({ auth: 'unknown' })])

        expect(rows[0].auth).toBe('unknown')
    })

    test('rows of one component share the leading cells', () => {
        const rows = buildDatabaseRows([
            component({
                accounts: [
                    { user: 'root', usage: ['administration'], password: 'secret' },
                    { user: 'wordpress', usage: ['application'], password: 'secret' },
                ],
                auth: 'password',
            }),
        ])

        expect(rows.map((row) => row.groupStart)).toEqual([true, false])
        expect(rows.map((row) => row.groupSize)).toEqual([2, 2])
    })

    test('an unresolved component does not name its inherited default account', () => {
        const rows = buildDatabaseRows([
            component({
                driver: 'redis',
                names: [],
                accounts: [{ user: 'default', usage: [], password: null }],
                auth: 'unknown',
            }),
        ])

        expect(rows[0].user).toBeNull()
        expect(rows[0].password).toBeNull()
    })

    test('every component keeps its own row set', () => {
        const rows = buildDatabaseRows([
            component({ id: 'postgres', driver: 'postgresql', host: 'db', port: 5432, names: ['dify'] }),
            component({ id: 'redis', driver: 'redis', host: 'redis', port: 6379, names: ['0', '1'] }),
        ])

        expect(rows.map((row) => row.componentId)).toEqual(['postgres', 'redis'])
        expect(rows[1].names).toEqual(['0', '1'])
    })
})

test.describe('database value formatting', () => {
    test('host and port stay separate and are never invented', () => {
        const [row] = buildDatabaseRows([component({ host: 'db', port: 5432 })])
        expect(row.host).toBe('db')
        expect(row.port).toBe(5432)

        const [withoutHost] = buildDatabaseRows([component({ host: null, port: 3306 })])
        expect(withoutHost.host).toBeNull()
        expect(withoutHost.port).toBe(3306)

        const [withoutPort] = buildDatabaseRows([component({ host: 'db', port: null })])
        expect(withoutPort.host).toBe('db')
        expect(withoutPort.port).toBeNull()
    })

    test('driver keys become product names', () => {
        expect(formatDatabaseTypeLabel('postgresql')).toBe('PostgreSQL')
        expect(formatDatabaseTypeLabel('mariadb')).toBe('MariaDB')
        expect(formatDatabaseTypeLabel('something-new')).toBe('something-new')
    })

    test('redis logical databases are labelled so a bare number is not read as a name', () => {
        expect(formatDatabaseNames('redis', ['0', '1'])).toEqual(['db 0', 'db 1'])
        expect(formatDatabaseNames('postgresql', ['dify', 'dify_plugin'])).toEqual(['dify', 'dify_plugin'])
        expect(formatDatabaseNames('redis', [])).toEqual([])
    })

    test('roles are translated and multiple usages are joined', () => {
        expect(formatDatabaseRoles(['application'], t)).toBe('roles.application')
        expect(formatDatabaseRoles(['initialization', 'administration'], t)).toBe(
            'roles.initialization / roles.administration',
        )
    })

    test('a declaration without roles yields nothing to render', () => {
        // The page drops the second line entirely instead of printing a
        // "not declared" placeholder under every account name.
        expect(formatDatabaseRoles([], t)).toBe('')
        expect(formatDatabaseRoles(['unknown-usage'], t)).toBe('')
    })
})
