import { createTheme } from '@mui/material/styles'

export function createAppTheme(mode: 'light' | 'dark') {
    return createTheme({
        cssVariables: true,
        palette: {
            mode,
            primary: {
                main: '#1767d1',
            },
            secondary: {
                main: '#0f8c72',
            },
            background: mode === 'dark'
                ? {
                    default: '#161c24',
                    paper: '#1f2937',
                }
                : {
                    default: '#f5f7fb',
                    paper: '#ffffff',
                },
        },
        shape: {
            borderRadius: 16,
        },
        typography: {
            fontFamily: ['Segoe UI', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'].join(','),
            h3: {
                fontWeight: 700,
                letterSpacing: '-0.03em',
            },
        },
    })
}
