export const shellNavigationItems = [
    {
        segment: 'app-store',
        pageKey: 'appStore',
    },
    {
        segment: 'my-apps',
        pageKey: 'myApps',
    },
    {
        segment: 'operations',
        pageKey: 'operations',
    },
    {
        segment: 'integrations',
        pageKey: 'integrations',
    },
    {
        segment: 'settings',
        pageKey: 'settings',
    },
] as const

export type ShellPageKey = (typeof shellNavigationItems)[number]['pageKey']