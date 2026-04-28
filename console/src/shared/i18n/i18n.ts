import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { shellResources } from './resources'

export const supportedLocales = ['en', 'zh-CN'] as const

export type SupportedLocale = (typeof supportedLocales)[number]

const defaultLocale: SupportedLocale = 'en'

export function normalizeSupportedLocale(locale: string | null | undefined): SupportedLocale {
    return locale?.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en'
}

function resolveInitialLocale(): SupportedLocale {
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

export { i18n }