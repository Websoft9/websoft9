import { Navigate, createBrowserRouter } from 'react-router-dom'

import { AppRouteBoundary } from './app-route-boundary'
import { ShellPlaceholderPage } from '../pages/shell-placeholder-page'
import { AppShell } from '../shell/app-shell'
import { shellNavigationItems } from '../shell/shell-navigation'

export function createAppRouter() {
    return createBrowserRouter([
        {
            path: '/',
            element: <AppRouteBoundary />,
            children: [
                {
                    element: <AppShell />,
                    children: [
                        {
                            index: true,
                            element: <Navigate replace to="app-store" />,
                        },
                        ...shellNavigationItems.map((item) => ({
                            path: item.segment,
                            element: <ShellPlaceholderPage pageKey={item.pageKey} />,
                        })),
                    ],
                },
            ],
        },
    ])
}
