import CssBaseline from '@mui/material/CssBaseline'
import { ThemeProvider } from '@mui/material/styles'
import { QueryClientProvider } from '@tanstack/react-query'
import { I18nextProvider } from 'react-i18next'
import { RouterProvider, type RouterProviderProps } from 'react-router-dom'

import { ProductAuthProvider } from '../../features/product-auth/product-auth-provider'
import { i18n } from '../../shared/i18n/i18n'
import { queryClient } from '../../shared/lib/query-client'
import { appTheme } from '../../shared/theme/theme'

type AppProvidersProps = {
    router: RouterProviderProps['router']
}

export function AppProviders({ router }: AppProvidersProps) {
    return (
        <ThemeProvider theme={appTheme}>
            <CssBaseline />
            <I18nextProvider i18n={i18n}>
                <QueryClientProvider client={queryClient}>
                    <ProductAuthProvider>
                        <RouterProvider router={router} />
                    </ProductAuthProvider>
                </QueryClientProvider>
            </I18nextProvider>
        </ThemeProvider>
    )
}
