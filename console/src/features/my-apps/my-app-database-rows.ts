import type { AppDatabaseComponent } from './use-app-databases'

/**
 * Pure view-model for the "Data → Database" table.
 *
 * The API returns one component per declared database instance. The flat table
 * (`方案 A`) shows one line per usable connection, so the component is flattened
 * here and every value stays as the backend resolved it: unknown values are
 * `null`, never a placeholder.
 */

export type AppDatabaseRow = {
    key: string
    componentId: string
    driver: string
    mode: AppDatabaseComponent['mode']
    host: string | null
    port: number | null
    names: string[]
    user: string | null
    usage: string[]
    password: string | null
    auth: AppDatabaseComponent['auth']
    /** True for the first row of a component; its cells span the whole group. */
    groupStart: boolean
    groupSize: number
}

const driverLabels: Record<string, string> = {
    mysql: 'MySQL',
    mariadb: 'MariaDB',
    postgresql: 'PostgreSQL',
    mongodb: 'MongoDB',
    redis: 'Redis',
    clickhouse: 'ClickHouse',
    couchdb: 'CouchDB',
    elasticsearch: 'Elasticsearch',
    opensearch: 'OpenSearch',
    meilisearch: 'Meilisearch',
    chroma: 'Chroma',
    weaviate: 'Weaviate',
    solr: 'Solr',
}

const roleKeys: Record<string, string> = {
    application: 'myAppsDetailPage.tabs.database.roles.application',
    initialization: 'myAppsDetailPage.tabs.database.roles.initialization',
    administration: 'myAppsDetailPage.tabs.database.roles.administration',
}

export function formatDatabaseTypeLabel(driver: string) {
    return driverLabels[driver] ?? driver
}

/**
 * Redis has no database names, only numbered logical databases (`db 0`,
 * `db 1`). Without the prefix a bare `0` reads like a broken cell.
 */
export function formatDatabaseNames(driver: string, names: string[]) {
    return driver === 'redis' ? names.map((name) => `db ${name}`) : names
}

/**
 * Account roles are optional metadata. When the declaration omits them there is
 * nothing to show, so the caller renders no second line at all instead of
 * filling the cell with "not declared".
 */
export function formatDatabaseRoles(usage: string[], t: (key: string, options?: Record<string, unknown>) => string) {
    const labels = usage.filter((value) => roleKeys[value]).map((value) => t(roleKeys[value]))
    return labels.join(' / ')
}

/**
 * One row per account. A component without accounts still gets a row so its
 * address and database names remain visible; the password cell then explains
 * whether the instance has no authentication or the accounts are unknown.
 */
export function buildDatabaseRows(components: AppDatabaseComponent[]): AppDatabaseRow[] {
    const rows: AppDatabaseRow[] = []

    for (const component of components) {
        const base = {
            componentId: component.id,
            driver: component.driver,
            mode: component.mode,
            host: component.host,
            port: component.port,
            names: component.names,
            auth: component.auth,
        }

        const accounts = component.accounts.length === 0 ? [null] : component.accounts
        accounts.forEach((account, index) => {
            rows.push({
                ...base,
                key: account ? `${component.id}-${account.user}` : `${component.id}-none`,
                // Nothing is known about the credentials when the source does not
                // resolve, so the cells stay empty instead of naming a default.
                user: component.auth === 'unknown' ? null : (account?.user ?? null),
                usage: component.auth === 'unknown' ? [] : (account?.usage ?? []),
                password: component.auth === 'unknown' ? null : (account?.password ?? null),
                groupStart: index === 0,
                groupSize: accounts.length,
            })
        })
    }

    return rows
}
