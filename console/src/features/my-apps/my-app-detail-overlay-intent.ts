let rememberedMyAppsDetailRoute: string | null = null
let activeMyAppsDetailAppId: string | null = null
let pendingComposeReturnAppId: string | null = null

export function rememberMyAppsDetailRoute(route: string | null) {
    rememberedMyAppsDetailRoute = route
}

export function getRememberedMyAppsDetailRoute() {
    return rememberedMyAppsDetailRoute
}

export function markPendingComposeReturn(appId: string | null) {
    pendingComposeReturnAppId = appId
}

export function consumePendingComposeReturn(appId: string | undefined) {
    if (!appId || pendingComposeReturnAppId !== appId) {
        return false
    }

    pendingComposeReturnAppId = null
    return true
}

export function markMyAppsDetailOverlayIntent(appId: string) {
    activeMyAppsDetailAppId = appId
}

export function hasMyAppsDetailOverlayIntent(appId: string | undefined) {
    return Boolean(appId) && activeMyAppsDetailAppId === appId
}

export function canOpenMyAppsDetailOverlay(appId: string | undefined, currentPathname: string) {
    if (hasMyAppsDetailOverlayIntent(appId)) {
        return true
    }

    const rememberedRoute = rememberedMyAppsDetailRoute
    const rememberedPathname = rememberedRoute?.split('?')[0] ?? null
    if (!rememberedPathname || rememberedPathname !== currentPathname) {
        return false
    }
    return true
}

export function clearMyAppsDetailOverlayIntent(appId?: string) {
    if (!appId || activeMyAppsDetailAppId === appId) {
        activeMyAppsDetailAppId = null
    }
}