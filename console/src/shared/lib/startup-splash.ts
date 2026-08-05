const STARTUP_SPLASH_ID = 'startup-splash'

export function dismissStartupSplash() {
    const splash = document.getElementById(STARTUP_SPLASH_ID)
    if (!splash || splash.classList.contains('is-hidden')) {
        return
    }

    splash.classList.add('is-hidden')
    window.setTimeout(() => splash.remove(), 160)
}