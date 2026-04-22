import { createTheme } from '@mui/material/styles'

export const appTheme = createTheme({
    colorSchemes: {
        light: true,
    },
    cssVariables: true,
    palette: {
        primary: {
            main: '#1767d1',
        },
        secondary: {
            main: '#0f8c72',
        },
        background: {
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
