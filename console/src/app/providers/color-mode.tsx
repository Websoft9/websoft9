import { createContext, useContext, type ReactNode } from 'react'

export const SHELL_MODE_STORAGE_KEY = 'websoft9:shell-color-mode'

export type AppColorMode = 'light' | 'dark'

type ColorModeContextValue = {
    colorMode: AppColorMode
    setColorMode: (mode: AppColorMode | ((currentMode: AppColorMode) => AppColorMode)) => void
}

const ColorModeContext = createContext<ColorModeContextValue | null>(null)

export function ColorModeProvider({ value, children }: { value: ColorModeContextValue; children: ReactNode }) {
    return <ColorModeContext.Provider value={value}>{children}</ColorModeContext.Provider>
}

export function useAppColorMode() {
    const context = useContext(ColorModeContext)

    if (!context) {
        throw new Error('useAppColorMode must be used within ColorModeProvider')
    }

    return context
}