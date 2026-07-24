import { lazy, type ComponentType, type LazyExoticComponent } from 'react'
import { Navigate, createBrowserRouter, type RouteObject } from 'react-router-dom'

import { AppRouteBoundary } from './app-route-boundary'
import { ShellPlaceholderPage } from '../pages/shell-placeholder-page'
import { AppShell } from '../shell/app-shell'
import { shellNavigationItems, type ShellPageKey } from '../shell/shell-navigation'
import { IntegrationWorkspacePage } from '../../features/integrations/integration-workspace-page'
import { ProductAuthPage } from '../../features/product-auth/product-auth-page'
import { ProductAuthRouteGuard } from '../../features/product-auth/product-auth-route-guard'
import { BrandPreviewPage } from '../../features/settings/brand-preview-page'
import { queryClient } from '../../shared/lib/query-client'

type PreloadableLazyComponent = LazyExoticComponent<ComponentType<any>> & {
    preload: () => Promise<unknown>
}

function lazyPage<TModule extends Record<string, unknown>>(
    loader: () => Promise<TModule>,
    exportName: keyof TModule,
): PreloadableLazyComponent {
    const load = () => loader().then((module) => ({ default: module[exportName] as ComponentType<any> }))
    const component = lazy(load) as PreloadableLazyComponent
    component.preload = load
    return component
}

const AppStorePage = lazyPage(() => import('../../features/app-store/app-store-page'), 'AppStorePage')
const MyAppDetailPage = lazyPage(() => import('../../features/my-apps/my-app-detail-page'), 'MyAppDetailPage')
const MyAppsPage = lazyPage(() => import('../../features/my-apps/my-apps-page'), 'MyAppsPage')
const IntegrationsPage = lazyPage(() => import('../../features/integrations/integrations-page'), 'IntegrationsPage')
const SettingsPage = lazyPage(() => import('../../features/settings/settings-page'), 'SettingsPage')
const FilesPage = lazyPage(() => import('../../features/files/files-page'), 'FilesPage')
const LogsPage = lazyPage(() => import('../../features/logs/logs-page'), 'LogsPage')
const OverviewPage = lazyPage(() => import('../../features/overview/overview-page'), 'OverviewPage')
const ServicesPage = lazyPage(() => import('../../features/services/services-page'), 'ServicesPage')
const TerminalPage = lazyPage(() => import('../../features/terminal/terminal-page'), 'TerminalPage')
const UsersPage = lazyPage(() => import('../../features/users/users-page'), 'UsersPage')
const ApplicationsDeployPage = lazyPage(() => import('../../features/applications/applications-deploy-page'), 'ApplicationsDeployPage')
const ApplicationsCustomInstallPage = lazyPage(() => import('../../features/applications/applications-custom-install-page'), 'ApplicationsCustomInstallPage')
const SetupWizardPage = lazyPage(() => import('../../features/setup-wizard/setup-wizard-page'), 'SetupWizardPage')

async function prefetchOverviewSummary() {
    await queryClient.prefetchQuery({
        queryKey: ['overview-summary'],
        queryFn: async () => {
            const response = await fetch('/api/overview', {
                credentials: 'include',
                headers: {
                    Accept: 'application/json',
                },
            })

            const payload = (await response.json().catch(() => null)) as { details?: string; message?: string } | null
            if (!response.ok) {
                throw new Error(payload?.details ?? payload?.message ?? `HTTP ${response.status}`)
            }

            return payload
        },
        staleTime: 10_000,
    })
}

function preloadInitialRoute(pathname: string) {
    const preloaders: Array<() => Promise<unknown>> = []

    if (pathname === '/' || pathname === '/dashboard') {
        preloaders.push(OverviewPage.preload)
        preloaders.push(prefetchOverviewSummary)
    } else if (pathname === '/appstore') {
        preloaders.push(AppStorePage.preload)
    } else if (pathname === '/myapps') {
        preloaders.push(MyAppsPage.preload)
    } else if (/^\/myapps\//.test(pathname)) {
        preloaders.push(MyAppsPage.preload, MyAppDetailPage.preload)
    } else if (pathname === '/settings') {
        preloaders.push(SettingsPage.preload)
    } else if (pathname === '/users') {
        preloaders.push(UsersPage.preload)
    } else if (pathname === '/files') {
        preloaders.push(FilesPage.preload)
    } else if (pathname === '/terminal') {
        preloaders.push(TerminalPage.preload)
    } else if (pathname === '/logs') {
        preloaders.push(LogsPage.preload)
    } else if (pathname === '/services') {
        preloaders.push(ServicesPage.preload)
    } else if (pathname === '/applications/deploy') {
        preloaders.push(ApplicationsDeployPage.preload)
    } else if (pathname === '/applications/custom-install') {
        preloaders.push(ApplicationsCustomInstallPage.preload)
    } else if (pathname === '/integrations') {
        preloaders.push(IntegrationsPage.preload)
    } else if (pathname === '/setup') {
        preloaders.push(SetupWizardPage.preload)
    }

    for (const preload of preloaders) {
        void preload()
    }
}

if (typeof window !== 'undefined') {
    preloadInitialRoute(window.location.pathname)
}

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
                    path: 'setup',
                    element: <SetupWizardPage />,
                },
                {
                    path: 'settings/brand-preview',
                    element: <BrandPreviewPage />,
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
