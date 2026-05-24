export const shellNavigationItems = [
    {
        segment: 'dashboard',
        pageKey: 'dashboard',
    },
    {
        segment: 'applications',
        pageKey: 'applications',
    },
    {
        segment: 'myapps',
        pageKey: 'myApps',
    },
    {
        segment: 'containers',
        pageKey: 'containers',
    },
    {
        segment: 'gateway',
        pageKey: 'gateway',
    },
    {
        segment: 'repository',
        pageKey: 'repository',
    },
    {
        segment: 'files',
        pageKey: 'files',
    },
    {
        segment: 'terminal',
        pageKey: 'terminal',
    },
    {
        segment: 'services',
        pageKey: 'services',
    },
    {
        segment: 'logs',
        pageKey: 'logs',
    },
    {
        segment: 'users',
        pageKey: 'users',
    },
    {
        segment: 'settings',
        pageKey: 'settings',
    },
] as const

export type ShellPageKey = (typeof shellNavigationItems)[number]['pageKey']