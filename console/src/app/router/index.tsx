import { lazy } from 'react'
import { Navigate, createBrowserRouter, type RouteObject } from 'react-router-dom'

import { AppRouteBoundary } from './app-route-boundary'
import { ShellPlaceholderPage } from '../pages/shell-placeholder-page'
import { AppShell } from '../shell/app-shell'
import { shellNavigationItems, type ShellPageKey } from '../shell/shell-navigation'
import { IntegrationWorkspacePage } from '../../features/integrations/integration-workspace-page'
import { ProductAuthPage } from '../../features/product-auth/product-auth-page'
import { ProductAuthRouteGuard } from '../../features/product-auth/product-auth-route-guard'

const AppStorePage = lazy(() => import('../../features/app-store/app-store-page').then((module) => ({ default: module.AppStorePage })))
const MyAppDetailPage = lazy(() => import('../../features/my-apps/my-app-detail-page').then((module) => ({ default: module.MyAppDetailPage })))
const MyAppsPage = lazy(() => import('../../features/my-apps/my-apps-page').then((module) => ({ default: module.MyAppsPage })))
const IntegrationsPage = lazy(() => import('../../features/integrations/integrations-page').then((module) => ({ default: module.IntegrationsPage })))
const SettingsPage = lazy(() => import('../../features/settings/settings-page').then((module) => ({ default: module.SettingsPage })))
const FilesPage = lazy(() => import('../../features/files/files-page').then((module) => ({ default: module.FilesPage })))
const LogsPage = lazy(() => import('../../features/logs/logs-page').then((module) => ({ default: module.LogsPage })))
const OverviewPage = lazy(() => import('../../features/overview/overview-page').then((module) => ({ default: module.OverviewPage })))
const ServicesPage = lazy(() => import('../../features/services/services-page').then((module) => ({ default: module.ServicesPage })))
const TerminalPage = lazy(() => import('../../features/terminal/terminal-page').then((module) => ({ default: module.TerminalPage })))
const UsersPage = lazy(() => import('../../features/users/users-page').then((module) => ({ default: module.UsersPage })))
const ApplicationsDeployPage = lazy(() => import('../../features/applications/applications-deploy-page').then((module) => ({ default: module.ApplicationsDeployPage })))
const ApplicationsCustomInstallPage = lazy(() => import('../../features/applications/applications-custom-install-page').then((module) => ({ default: module.ApplicationsCustomInstallPage })))

export function createAppRouter() {
    const shellRoutes: RouteObject[] = shellNavigationItems.map((navItem) => {
        const item: { segment: string; pageKey: ShellPageKey } = navItem

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

        if (item.segment === 'applications') {
            return {
                path: item.segment,
                element: <Navigate replace to="/myapps" />,
            }
        }

        if (item.segment === 'myapps') {
            return {
                path: item.segment,
                element: <MyAppsPage />,
                children: [
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

        if (item.segment === 'users') {
            return {
                path: item.segment,
                element: <ProductAuthRouteGuard routeSegment={item.segment}><UsersPage /></ProductAuthRouteGuard>,
            }
        }

        if (item.segment === 'files') {
            return {
                path: item.segment,
                element: <ProductAuthRouteGuard routeSegment={item.segment}><FilesPage /></ProductAuthRouteGuard>,
            }
        }

        if (item.segment === 'terminal') {
            return {
                path: item.segment,
                element: <ProductAuthRouteGuard routeSegment={item.segment}><TerminalPage /></ProductAuthRouteGuard>,
            }
        }

        if (item.segment === 'logs') {
            return {
                path: item.segment,
                element: <ProductAuthRouteGuard routeSegment={item.segment}><LogsPage /></ProductAuthRouteGuard>,
            }
        }

        if (item.segment === 'services') {
            return {
                path: item.segment,
                element: <ProductAuthRouteGuard routeSegment={item.segment}><ServicesPage /></ProductAuthRouteGuard>,
            }
        }

        if (item.segment === 'dashboard') {
            return {
                path: item.segment,
                element: <ProductAuthRouteGuard routeSegment={item.segment}><OverviewPage /></ProductAuthRouteGuard>,
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
                    path: 'auth/setup',
                    element: <ProductAuthPage mode="setup" />,
                },
                {
                    path: 'auth/login',
                    element: <ProductAuthPage mode="login" />,
                },
                {
                    element: (
                        <ProductAuthRouteGuard requireAuthentication routeSegment="__shell__">
                            <AppShell />
                        </ProductAuthRouteGuard>
                    ),
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
                            path: 'appstore',
                            element: <AppStorePage lockedInstallSource="marketplace" hideInstallSourceSelector />,
                        },
                        {
                            path: 'applications/deploy',
                            element: <ApplicationsDeployPage />,
                        },
                        {
                            path: 'applications/custom-install',
                            element: <ApplicationsCustomInstallPage />,
                        },
                        ...shellRoutes,
                    ],
                },
            ],
        },
    ])
}
