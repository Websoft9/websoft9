import { Box } from '@mui/material'
import { useEffect, useMemo, useState } from 'react'

import defaultImageEn from '../../../../pluings/plugin-myapps/src/assets/images/default_en.png'
import defaultImageZh from '../../../../pluings/plugin-myapps/src/assets/images/default_zh.png'

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

export function LegacyMyAppLogo({ appName, appId, locale = 'en', size = 80, marginY = 2.5, title }: LegacyMyAppLogoProps) {
    const fallbackImage = locale.startsWith('zh') ? defaultImageZh : defaultImageEn
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