import { Box } from '@mui/material'
import { useEffect, useMemo, useState } from 'react'

type LegacyMyAppLogoProps = {
    appName?: string | null
    appId?: string | null
    logoUrl?: string | null
    locale?: string
    size?: number
    marginY?: number
    title?: string | null
}

function getDefaultImagePath(locale: string) {
    return locale.startsWith('zh') ? '/default.png' : '/default-en.png'
}

export function LegacyMyAppLogo({ appName, appId, logoUrl, locale = 'en', size = 80, marginY = 2.5, title }: LegacyMyAppLogoProps) {
    const fallbackImage = useMemo(() => getDefaultImagePath(locale), [locale])
    const primarySource = useMemo(() => logoUrl?.trim() || null, [logoUrl])
    const [imageFailed, setImageFailed] = useState(false)
    const src = !imageFailed && primarySource ? primarySource : fallbackImage

    useEffect(() => {
        setImageFailed(false)
    }, [primarySource])

    return (
        <Box
            component="img"
            src={src}
            alt={appName || appId || 'app'}
            title={title ?? appName ?? appId ?? undefined}
            referrerPolicy="no-referrer"
            onError={() => {
                setImageFailed(true)
            }}
            sx={{
                minHeight: size,
                maxHeight: size,
                minWidth: size,
                maxWidth: '100%',
                objectFit: 'contain',
                display: 'block',
                mx: 'auto',
                my: marginY,
            }}
        />
    )
}