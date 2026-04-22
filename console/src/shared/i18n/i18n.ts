import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { shellResources } from './resources'

export const supportedLocales = ['en', 'zh-CN'] as const

export type SupportedLocale = (typeof supportedLocales)[number]

const defaultLocale: SupportedLocale = 'en'
const localePreferenceKey = 'websoft9.console.locale'

function isSupportedLocale(value: string | null): value is SupportedLocale {
    return value !== null && supportedLocales.includes(value as SupportedLocale)
}

function getStoredLocale(): SupportedLocale | null {
    if (typeof window === 'undefined') {
        return null
    }

    const storedLocale = window.localStorage.getItem(localePreferenceKey)

    return isSupportedLocale(storedLocale) ? storedLocale : null
}

function persistLocale(locale: string) {
    if (typeof window === 'undefined' || !isSupportedLocale(locale)) {
        return
    }

    window.localStorage.setItem(localePreferenceKey, locale)
}

function resolveInitialLocale(): SupportedLocale {
    const storedLocale = getStoredLocale()

    if (storedLocale) {
        return storedLocale
    }

    if (typeof navigator === 'undefined') {
        return defaultLocale
    }

    return navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en'
}

if (!i18n.isInitialized) {
    void i18n.use(initReactI18next).init({
        fallbackLng: defaultLocale,
        resources: shellResources,
        supportedLngs: [...supportedLocales],
        lng: resolveInitialLocale(),
        defaultNS: 'shell',
        ns: ['shell'],
        interpolation: {
            escapeValue: false,
        },
        react: {
            useSuspense: false,
        },
    })
}

i18n.on('languageChanged', persistLocale)

export { i18n }