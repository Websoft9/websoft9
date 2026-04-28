import { Box } from '@mui/material'
import { useEffect, useMemo, useState } from 'react'

type LegacyMyAppLogoProps = {
    appName?: string | null
    appId?: string | null
    locale?: string
    size?: number
    marginY?: number
    title?: string | null
}

function buildPrimaryLogoSource(appName?: string | null, appId?: string | null) {
    const preferredValue = appName?.trim() || appId?.trim()
    if (!preferredValue) return null
    return `/media/logos/${preferredValue.toLowerCase()}-websoft9.png`
}

function buildFallbackLogoDataUri(locale: string) {
    const isChinese = locale.startsWith('zh')
    const background = isChinese ? '#f3ead6' : '#e8eef7'
    const accent = isChinese ? '#a35a1f' : '#2550a3'
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240" viewBox="0 0 240 240"><rect width="240" height="240" rx="36" fill="${background}"/><circle cx="120" cy="78" r="28" fill="${accent}" fill-opacity="0.14"/><text x="120" y="118" text-anchor="middle" font-family="Arial, sans-serif" font-size="26" font-weight="700" fill="${accent}">Websoft9</text><text x="120" y="154" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" fill="${accent}">${isChinese ? '应用' : 'App'}</text></svg>`
    return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
}

export function LegacyMyAppLogo({ appName, appId, locale = 'en', size = 80, marginY = 2.5, title }: LegacyMyAppLogoProps) {
    const fallbackImage = useMemo(() => buildFallbackLogoDataUri(locale), [locale])
    const primarySource = useMemo(() => buildPrimaryLogoSource(appName, appId), [appId, appName])
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