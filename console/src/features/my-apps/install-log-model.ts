import type { MyApp, MyAppLogStage } from './use-my-apps'

export const INSTALL_STAGE_TITLES = ['Initializing installation', 'Pulling docker image', 'Starting the services', 'Configuring the domain']
export const INSTALL_STAGE_KEYS = ['initializing', 'pulling', 'starting', 'domain']

type PullEntry = {
    status?: unknown
    message?: unknown
    details?: unknown
    id?: unknown
    image?: unknown
    event?: unknown
    progressDetail?: { current?: unknown; total?: unknown; units?: unknown } | null
}

function humanSize(bytes: number) {
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let unitIndex = 0
    while (bytes >= 1024 && unitIndex < units.length - 1) {
        bytes /= 1024
        unitIndex++
    }
    return `${unitIndex ? bytes.toFixed(1) : Math.round(bytes)} ${units[unitIndex]}`
}

export function formatInstallLogLine(value: unknown): string {
    if (typeof value === 'string') return value
    if (typeof value === 'number' || typeof value === 'boolean') return String(value)
    if (!value || typeof value !== 'object') return ''
    const entry = value as PullEntry
    const parts: string[] = []
    if (typeof entry.status === 'string' && (typeof entry.message !== 'string' || !entry.message.startsWith(entry.status))) parts.push(entry.status)
    if (typeof entry.message === 'string') parts.push(entry.message)
    if (typeof entry.details === 'string' && !parts.includes(entry.details)) parts.push(entry.details)
    if (typeof entry.id === 'string' && !parts.some((part) => part.includes(`#${entry.id}`))) parts.push(`#${entry.id}`)
    const current = entry.progressDetail?.current
    const total = entry.progressDetail?.total
    if (typeof current === 'number' && Number.isFinite(current) && current >= 0) {
        if (entry.status === 'Downloading' && typeof total === 'number' && Number.isFinite(total) && total > 0) {
            const percent = Math.min(100, Math.max(0, Math.floor(current * 100 / total)))
            parts.push(`${percent}% (${humanSize(current)}/${humanSize(total)})`)
        } else {
            const units = typeof entry.progressDetail?.units === 'string' ? entry.progressDetail.units : ''
            parts.push(`(${current}${units})`)
        }
    }
    if (parts.length) return parts.join(' ')
    try { return JSON.stringify(value) } catch { return String(value) }
}

export type InstallLogRow = { key: string; stageIndex: number; image: string; text: string }

export function buildInstallLogRows(stages: MyAppLogStage[]): InstallLogRow[] {
    const rows: InstallLogRow[] = []
    const layerRows = new Map<string, number>()
    stages.forEach((stage, stageIndex) => {
        let image = ''
        for (const value of stage.sub_logs ?? []) {
            if (value == null || value === '') continue
            const entry = typeof value === 'object' ? value as PullEntry : null
            if (typeof entry?.image === 'string') image = entry.image
            if (entry?.event === 'image-pull-started' || entry?.event === 'image-pull-completed') continue
            const isLayer = typeof entry?.id === 'string' && /^(Downloading|Extracting|Pulling fs layer|Download complete|Pull complete|Already exists|Waiting|Verifying Checksum)$/.test(String(entry.status))
            const key = isLayer ? `${stageIndex}:${image}:${entry.id}` : `${stageIndex}:entry:${rows.length}`
            const row = { key, stageIndex, image, text: formatInstallLogLine(value) }
            const previousIndex = isLayer ? layerRows.get(key) : undefined
            if (previousIndex !== undefined) rows[previousIndex] = row
            else {
                if (isLayer) layerRows.set(key, rows.length)
                rows.push(row)
            }
        }
    })
    return rows
}

export function getInstallSteps(app: MyApp) {
    const stages = app.logs ?? []
    const observed = stages.map(stage => INSTALL_STAGE_TITLES.indexOf(stage.title)).filter(index => index >= 0)
    const current = observed.length ? observed[observed.length - 1] : 0
    const interrupted = app.status === 4 || app.status === 6 || Boolean(app.error)
    const completed = !interrupted && (app.status === 1 || app.status === 2 || stages.some(stage => stage.title === 'Installation complete'))
    const accessConfigured = observed.includes(3) || (app.proxy_enabled && Boolean(app.domain_names?.length))
    return INSTALL_STAGE_KEYS.map((key, index) => ({
        key,
        state: index === 3 && completed && !accessConfigured ? 'skipped'
            : completed || index < current ? 'done'
                : index === current ? interrupted ? 'interrupted' : 'active' : 'pending',
    }))
}

export function getInstallError(app: MyApp) {
    const raw = String(app.error ?? '')
    const image = raw.match(/Unable to pull image ['"]([^'"]+)['"]/)?.[1]
    const category = image ? 'image'
        : /port is already allocated|address already in use|port\s+\d+\s+is already in use/i.test(raw) ? 'port'
            : /no space left on device|disk quota exceeded/i.test(raw) ? 'disk'
                : /permission denied|operation not permitted/i.test(raw) ? 'permission'
                    : /timeout|timed out|connection refused|network is unreachable/i.test(raw) ? 'network'
                        : /yaml:|invalid compose|invalid configuration|mapping values are not allowed/i.test(raw) ? 'configuration' : 'unknown'
    const port = raw.match(/(?:0\.0\.0\.0:|127\.0\.0\.1:|port\s+)(\d+)/i)?.[1]
    const phase = [...(app.logs ?? [])].reverse().map(stage => INSTALL_STAGE_TITLES.indexOf(stage.title)).find(index => index >= 0)
    const sources = category === 'image' ? raw.split('\n').flatMap(line => {
        const match = line.match(/^\s*-\s*(.+?)\s*\[(.+?)\]:\s*(.*)$/)
        return match ? [{ label: match[1], reference: match[2], reason: match[3] }] : []
    }) : []
    return {
        category, raw, phase: phase === undefined ? undefined : INSTALL_STAGE_KEYS[phase], object: image ?? (category === 'port' ? port : undefined),
        sources,
    }
}

export function getInstallSourceSummary(source: { label: string; reference: string; reason: string }) {
    const firstComponent = source.reference.split('/')[0]
    const isMirror = /^mirror(?:\s|$)/.test(source.label)
    const hasRegistry = source.reference.includes('/') && (firstComponent.includes('.') || firstComponent.includes(':') || firstComponent === 'localhost')
    const registry = isMirror || hasRegistry ? firstComponent : 'docker.io'
    const nameKey = isMirror ? 'mirrorSource' : source.label === 'direct pull' ? 'originalSource' : undefined
    const result = /access denied|permission denied|unauthorized|authentication required/i.test(source.reason) ? 'denied'
        : /not found|does not exist/i.test(source.reason) ? 'missing'
            : /timeout|timed out/i.test(source.reason) ? 'timeout'
                : /EOF|internal server error|connection refused|unreachable/i.test(source.reason) ? 'connection' : 'failed'
    return { registry, nameKey, result }
}

export function formatInstallSourceReason(reason: string) {
    const wrapper = reason.trim().match(/^(?:Internal Server Error|Bad Gateway|Service Unavailable|Gateway Timeout|Bad Request|Not Found|Unauthorized|Forbidden)\s*(?:\(\s*"([\s\S]+)"\s*\)|:\s*([\s\S]+))$/i)
    return wrapper ? (wrapper[1] ?? wrapper[2]).trim() : reason
}

export function getInstallSourceGroups(sources: { label: string; reference: string; reason: string }[]) {
    const groups = new Map<string, { label: string; nameKey: string | undefined; sources: typeof sources }>()
    for (const source of sources) {
        const { nameKey } = getInstallSourceSummary(source)
        const key = nameKey ?? source.label
        const group = groups.get(key) ?? { label: source.label, nameKey, sources: [] }
        group.sources.push(source)
        groups.set(key, group)
    }
    return [...groups.values()]
}

export function getInstallExportText(app: MyApp, stageTitle: (title: string) => string) {
    if (app.status === 6) return ''
    if (app.error) return String(app.error)
    const stages = app.logs ?? []
    const rows = buildInstallLogRows(stages)
    return stages.flatMap((stage, stageIndex) => {
        const lines = rows.filter(row => row.stageIndex === stageIndex && row.text.trim()).map(row => `${row.image ? `[${row.image}] ` : ''}${row.text}`)
        return lines.length ? [[stageTitle(stage.title), ...lines].join('\n')] : []
    }).join('\n\n')
}