import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const consoleRoot = path.resolve(scriptDir, '..')
const resourcesFile = path.join(consoleRoot, 'src/shared/i18n/resources.ts')

function loadShellResources() {
    const source = fs.readFileSync(resourcesFile, 'utf8')
    const executableSource = source
        .replace('function normalizeLocaleNamespaces(resources: Record<string, Record<string, any>>) {', 'function normalizeLocaleNamespaces(resources) {')
        .replace('export const shellResources =', 'const shellResources =')
        .replace(/\s+as const/g, '')
    const sandbox = { module: { exports: {} }, exports: {} }
    vm.runInNewContext(`${executableSource}\nmodule.exports = shellResources`, sandbox, { filename: resourcesFile })
    return sandbox.module.exports
}

function normalizeLocaleNamespaces(resources) {
    return Object.fromEntries(
        Object.entries(resources).map(([locale, namespaces]) => {
            const shellNamespace = namespaces.shell ?? {}
            const extraNamespaces = Object.fromEntries(Object.entries(namespaces).filter(([name]) => name !== 'shell'))

            return [
                locale,
                {
                    ...extraNamespaces,
                    shell: {
                        ...extraNamespaces,
                        ...shellNamespace,
                    },
                },
            ]
        }),
    )
}

function collectObjectKeys(value, prefix = '') {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
        return []
    }

    return Object.entries(value).flatMap(([key, child]) => {
        const nextPrefix = prefix ? `${prefix}.${key}` : key
        const nestedKeys = collectObjectKeys(child, nextPrefix)
        return nestedKeys.length ? nestedKeys : [nextPrefix]
    })
}

function getByPath(root, dottedPath) {
    return dottedPath.split('.').reduce((current, segment) => current?.[segment], root)
}

function scanFileForChinese(relativePath) {
    const filePath = path.join(consoleRoot, relativePath)
    const content = fs.readFileSync(filePath, 'utf8')
    const lines = content.split(/\r?\n/)
    const findings = []

    lines.forEach((line, index) => {
        if (/[\u4e00-\u9fff]/.test(line)) {
            findings.push(`${relativePath}:${index + 1}: ${line.trim()}`)
        }
    })

    return findings
}

const shellResources = normalizeLocaleNamespaces(loadShellResources())
const guardedResourcePairs = [
    {
        label: 'myAppsDetailPage.accessPanel',
        enPath: 'shell.myAppsDetailPage.accessPanel',
        zhPath: 'shell.myAppsDetailPage.accessPanel',
    },
    {
        label: 'myAppsDetailPage.tabs.database',
        enPath: 'shell.myAppsDetailPage.tabs.database',
        zhPath: 'shell.myAppsDetailPage.tabs.database',
    },
    {
        label: 'myAppsDetailPage.tabs.monitor',
        enPath: 'shell.myAppsDetailPage.tabs.monitor',
        zhPath: 'shell.myAppsDetailPage.tabs.monitor',
    },
    {
        label: 'myAppsDetailPage.tabs.compose',
        enPath: 'shell.myAppsDetailPage.tabs.compose',
        zhPath: 'shell.myAppsDetailPage.tabs.compose',
    },
    {
        label: 'myAppsDetailPage.tabs.uninstall',
        enPath: 'shell.myAppsDetailPage.tabs.uninstall',
        zhPath: 'shell.myAppsDetailPage.tabs.uninstall',
    },
    {
        label: 'servicesPage.hero',
        enPath: 'shell.servicesPage.hero',
        zhPath: 'shell.servicesPage.hero',
    },
    {
        label: 'usersPage.hero',
        enPath: 'shell.usersPage.hero',
        zhPath: 'shell.usersPage.hero',
    },
    {
        label: 'settingsPage.hero',
        enPath: 'shell.settingsPage.hero',
        zhPath: 'shell.settingsPage.hero',
    },
    {
        label: 'filesPage.feedback',
        enPath: 'shell.filesPage.feedback',
        zhPath: 'shell.filesPage.feedback',
    },
]

const missingInChinese = []
const missingInEnglish = []

guardedResourcePairs.forEach(({ label, enPath, zhPath }) => {
    const englishRoot = getByPath(shellResources.en, enPath)
    const chineseRoot = getByPath(shellResources['zh-CN'], zhPath)
    const englishKeys = new Set(collectObjectKeys(englishRoot, label))
    const chineseKeys = new Set(collectObjectKeys(chineseRoot, label))

    missingInChinese.push(...[...englishKeys].filter((key) => !chineseKeys.has(key)))
    missingInEnglish.push(...[...chineseKeys].filter((key) => !englishKeys.has(key)))
})

missingInChinese.sort()
missingInEnglish.sort()

const guardedFiles = [
    'src/features/my-apps/my-app-access-panel.tsx',
    'src/features/my-apps/volume-file-manager-dialog.tsx',
    'src/features/services/services-page.tsx',
    'src/features/users/users-page.tsx',
    'src/features/settings/settings-page.tsx',
]

const hardcodedChineseFindings = guardedFiles.flatMap(scanFileForChinese)

if (!missingInChinese.length && !missingInEnglish.length && !hardcodedChineseFindings.length) {
    console.log('i18n check passed')
    process.exit(0)
}

if (missingInChinese.length) {
    console.error('Missing keys in zh-CN:')
    missingInChinese.forEach((key) => console.error(`  - ${key}`))
}

if (missingInEnglish.length) {
    console.error('Missing keys in en:')
    missingInEnglish.forEach((key) => console.error(`  - ${key}`))
}

if (hardcodedChineseFindings.length) {
    console.error('Hardcoded Chinese detected in guarded feature files:')
    hardcodedChineseFindings.forEach((entry) => console.error(`  - ${entry}`))
}

process.exit(1)