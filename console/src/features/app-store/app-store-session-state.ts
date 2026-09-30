/**
 * Remembers the App Store surface across in-app navigation.
 *
 * The shell unmounts a page as soon as the operator switches menus, so an open app detail or install
 * form -- and every value typed into it -- lived only in component state and was lost on the way
 * back. Keeping the intent in module scope lets the page reopen exactly what was left behind.
 *
 * Deliberately in memory only, with nothing written to storage: a browser reload is an explicit
 * request for a fresh start, so a refreshed page comes back empty instead of resurrecting a dialog.
 * This mirrors how the My Apps detail overlay remembers itself.
 */
export type AppStoreSessionState = {
    appKey: string
    isInstallMode: boolean
    installName: string
    selectedVersion: string
    installSettings: Record<string, string>
    selectedInstallProfile: string | null
    profileInstallSettings: Record<string, Record<string, string>>
    wildcardDomain: string
    isDomainEnabled: boolean
    customDomains: string[]
}

let sessionState: AppStoreSessionState | null = null

export function readAppStoreSessionState(): AppStoreSessionState | null {
    return sessionState
}

export function writeAppStoreSessionState(state: AppStoreSessionState | null): void {
    sessionState = state
}
