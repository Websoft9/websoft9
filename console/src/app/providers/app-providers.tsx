import CssBaseline from '@mui/material/CssBaseline'
import { ThemeProvider } from '@mui/material/styles'
import { QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { I18nextProvider } from 'react-i18next'
import { RouterProvider, type RouterProviderProps } from 'react-router-dom'

import { ColorModeProvider, SHELL_MODE_STORAGE_KEY, type AppColorMode } from './color-mode'
import { ProductAuthProvider } from '../../features/product-auth/product-auth-provider'
import { i18n } from '../../shared/i18n/i18n'
import { queryClient } from '../../shared/lib/query-client'
import { createAppTheme } from '../../shared/theme/theme'

type AppProvidersProps = {
    router: RouterProviderProps['router']
}

export function AppProviders({ router }: AppProvidersProps) {
    const [colorMode, setColorMode] = useState<AppColorMode>(() => {
        if (typeof window === 'undefined') {
            return 'light'
        }

        const storedValue = window.localStorage.getItem(SHELL_MODE_STORAGE_KEY)
        return storedValue === 'dark' ? 'dark' : 'light'
    })

    const theme = useMemo(() => createAppTheme(colorMode), [colorMode])

    useEffect(() => {
        if (typeof window === 'undefined') {
            return
        }

        window.localStorage.setItem(SHELL_MODE_STORAGE_KEY, colorMode)
        document.documentElement.style.colorScheme = colorMode
    }, [colorMode])

    return (
        <ColorModeProvider value={{ colorMode, setColorMode }}>
            <ThemeProvider theme={theme}>
                <CssBaseline />
                <I18nextProvider i18n={i18n}>
                    <QueryClientProvider client={queryClient}>
                        <ProductAuthProvider>
                            <RouterProvider router={router} />
                        </ProductAuthProvider>
                    </QueryClientProvider>
                </I18nextProvider>
            </ThemeProvider>
        </ColorModeProvider>
    )
}
