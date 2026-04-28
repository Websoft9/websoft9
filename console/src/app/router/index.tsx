import { Navigate, Outlet, createBrowserRouter, type RouteObject } from 'react-router-dom'

import { AppRouteBoundary } from './app-route-boundary'
import { ShellPlaceholderPage } from '../pages/shell-placeholder-page'
import { AppShell } from '../shell/app-shell'
import { shellNavigationItems } from '../shell/shell-navigation'
import { AppStorePage } from '../../features/app-store/app-store-page'
import { MyAppDetailPage } from '../../features/my-apps/my-app-detail-page'
import { MyAppsPage } from '../../features/my-apps/my-apps-page'
import { IntegrationsPage } from '../../features/integrations/integrations-page'
import { IntegrationWorkspacePage } from '../../features/integrations/integration-workspace-page'
import { ProductAuthPage } from '../../features/product-auth/product-auth-page'
import { ProductAuthRouteGuard } from '../../features/product-auth/product-auth-route-guard'
import { SettingsPage } from '../../features/settings/settings-page'

export function createAppRouter() {
    const shellRoutes: RouteObject[] = shellNavigationItems.map((item) => {
        if (item.segment === 'containers') {
            return {
                path: item.segment,
                element: <IntegrationWorkspacePage integrationKey="portainer" shellPersistent />,
            }
        }

        if (item.segment === 'gateway') {
            return {
                path: item.segment,
                element: <IntegrationWorkspacePage integrationKey="npm" shellPersistent />,
            }
        }

        if (item.segment === 'repository') {
            return {
                path: item.segment,
                element: <IntegrationWorkspacePage integrationKey="gitea" shellPersistent />,
            }
        }

        if (item.segment === 'appstore') {
            return {
                path: item.segment,
                element: <AppStorePage />,
            }
        }

        if (item.segment === 'myapps') {
            return {
                path: item.segment,
                element: <Outlet />,
                children: [
                    {
                        index: true,
                        element: <MyAppsPage />,
                    },
                    {
                        path: ':appId',
                        element: <MyAppDetailPage />,
                    },
                ],
            }
        }

        if (item.segment === 'settings') {
            return {
                path: item.segment,
                element: <SettingsPage />,
            }
        }

        const pageElement = <ShellPlaceholderPage pageKey={item.pageKey} />

        return {
            path: item.segment,
            element: <ProductAuthRouteGuard routeSegment={item.segment}>{pageElement}</ProductAuthRouteGuard>,
        }
    })

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
                            element: <Navigate replace to="dashboard" />,
                        },
                        {
                            path: 'integrations',
                            element: <IntegrationsPage />,
                        },
                        {
                            path: 'integrations/:integrationKey',
                            element: <IntegrationWorkspacePage showCatalogLink />,
                        },
                        {
                            path: 'auth/setup',
                            element: <ProductAuthPage mode="setup" />,
                        },
                        {
                            path: 'auth/login',
                            element: <ProductAuthPage mode="login" />,
                        },
                        ...shellRoutes,
                    ],
                },
            ],
        },
    ])
}
