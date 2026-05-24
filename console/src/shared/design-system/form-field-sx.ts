import type { SurfacePalette } from './surface-theme'

type SurfaceFieldOptions = {
    minHeight?: number | string
    borderRadius?: number | string
    helperErrorColor?: string
    placeholderColor?: string
}

export function getSurfaceFieldSx(
    palette: Pick<SurfacePalette, 'panelBg' | 'panelSoft' | 'text' | 'subtleText' | 'placeholderText' | 'borderStrong' | 'accent' | 'danger'>,
    options: SurfaceFieldOptions = {},
) {
    const {
        minHeight = 'var(--ds-form-height)',
        borderRadius = 'var(--ds-radius-field)',
        helperErrorColor = palette.danger,
        placeholderColor = palette.placeholderText,
    } = options

    return {
        '& .MuiOutlinedInput-root': {
            minHeight,
            borderRadius,
            backgroundColor: palette.panelBg,
            '& .MuiOutlinedInput-notchedOutline': {
                borderColor: palette.borderStrong,
            },
            '&:hover .MuiOutlinedInput-notchedOutline': {
                borderColor: palette.borderStrong,
            },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                borderColor: palette.accent,
            },
            '&.Mui-focused': {
                boxShadow: 'var(--ds-focus-ring)',
            },
            '&.Mui-error .MuiOutlinedInput-notchedOutline': {
                borderColor: helperErrorColor,
            },
            '&.Mui-disabled': {
                backgroundColor: palette.panelSoft,
            },
        },
        '& .MuiInputLabel-root': {
            color: palette.subtleText,
        },
        '& .MuiInputLabel-root.Mui-focused': {
            color: palette.subtleText,
        },
        '& .MuiInputBase-input, & .MuiSelect-select': {
            fontSize: 14,
            fontWeight: 400,
            color: palette.text,
            WebkitTextFillColor: palette.text,
        },
        '& .MuiInputBase-input::placeholder': {
            fontSize: 14,
            fontWeight: 400,
            color: placeholderColor,
            WebkitTextFillColor: placeholderColor,
            opacity: 1,
        },
        '& .MuiInputBase-input::-webkit-input-placeholder': {
            color: placeholderColor,
            WebkitTextFillColor: placeholderColor,
            opacity: 1,
        },
        '& .MuiInputBase-input::-moz-placeholder': {
            color: placeholderColor,
            opacity: 1,
        },
        '& .MuiInputBase-input.Mui-disabled': {
            WebkitTextFillColor: palette.text,
            color: palette.text,
            opacity: 1,
        },
        '& .MuiFormHelperText-root': {
            color: palette.subtleText,
            mx: 0,
            mt: 0.75,
        },
        '& .MuiFormHelperText-root.Mui-error': {
            color: helperErrorColor,
        },
    } as const
}