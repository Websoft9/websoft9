export type IntegrationStatus = 'loading' | 'available' | 'unavailable' | 'configuration-error' | 'session-error'

export type IntegrationKey = 'gitea' | 'portainer' | 'npm'

export type IntegrationDefinition = {
    authMarkers: string[]
    authPaths: string[]
    diagnosticsPath: string
    entrySegment: 'repository' | 'containers' | 'gateway'
    key: IntegrationKey
    pageKey: IntegrationKey
    probePath: string
    workspacePath: string
    directPath: string
}

export const integrationDefinitions: IntegrationDefinition[] = [
    {
        authMarkers: ['/user/login', 'name="user_name"', 'content="Gitea"'],
        authPaths: ['/user/login'],
        diagnosticsPath: '/w9git/',
        entrySegment: 'repository',
        key: 'gitea',
        pageKey: 'gitea',
        probePath: '/w9git/',
        workspacePath: '/w9git/',
        directPath: '/w9git/',
    },
    {
        authMarkers: ['#/auth', '/api/auth', 'Portainer'],
        authPaths: ['/api/auth'],
        diagnosticsPath: '/w9deployment/api/auth',
        entrySegment: 'containers',
        key: 'portainer',
        pageKey: 'portainer',
        probePath: '/w9deployment/',
        workspacePath: '/w9deployment/',
        directPath: '/w9deployment/',
    },
    {
        authMarkers: ['/login', 'nginx-proxy-manager', 'Authorization'],
        authPaths: ['/login'],
        diagnosticsPath: '/w9proxy/',
        entrySegment: 'gateway',
        key: 'npm',
        pageKey: 'npm',
        probePath: '/w9proxy/',
        workspacePath: '/w9proxy/',
        directPath: '/w9proxy/',
    },
] as const

export function getIntegrationDefinition(key: string | undefined) {
    return integrationDefinitions.find((definition) => definition.key === key)
}

export function getIntegrationDefinitionByEntrySegment(segment: string | undefined) {
    return integrationDefinitions.find((definition) => definition.entrySegment === segment)
}

export function classifyIntegrationStatus(response: Response) {
    if (response.ok) {
        return 'available' satisfies IntegrationStatus
    }

    if (response.status === 401 || response.status === 403) {
        return 'session-error' satisfies IntegrationStatus
    }

    if (response.status === 400 || response.status === 404) {
        return 'configuration-error' satisfies IntegrationStatus
    }

    return 'unavailable' satisfies IntegrationStatus
}