import { Chip, CircularProgress } from '@mui/material'

/**
 * Image prewarm states share one visual language across the App Store and Scheduled Tasks. Both
 * surfaces previously styled their own chips, so the same state could render with different colors
 * and text contrast depending on where it appeared.
 */
export type PrewarmStatusState = 'queued' | 'running' | 'success' | 'failed' | 'cancelled'

const STATE_BACKGROUND: Record<PrewarmStatusState, string> = {
    queued: '#0277bd',
    running: '#0277bd',
    success: '#2e7d32',
    failed: '#d32f2f',
    cancelled: '#64748b',
}

type PrewarmStatusChipProps = {
    state: PrewarmStatusState
    label: string
    /** Chip height in pixels. The App Store field uses 22, the Scheduled Tasks table uses 20. */
    height?: number
    fontSize?: number
}

export function PrewarmStatusChip({ state, label, height = 20, fontSize = 11 }: PrewarmStatusChipProps) {
    const running = state === 'running'
    return (
        <Chip
            className="prewarm-status-chip"
            icon={running ? <CircularProgress size={height <= 20 ? 10 : 11} sx={{ color: '#ffffff' }} /> : undefined}
            label={label}
            size="small"
            sx={{
                height,
                borderRadius: '2px',
                fontWeight: 600,
                flexShrink: 0,
                color: '#ffffff',
                // `-webkit-text-fill-color` is inherited and wins over `color`, so a container that
                // sets it (the version field does) would otherwise render this label dark.
                WebkitTextFillColor: '#ffffff',
                backgroundColor: STATE_BACKGROUND[state] ?? STATE_BACKGROUND.queued,
                '& .MuiChip-icon': {
                    ml: 0.75,
                    mr: -0.25,
                    color: '#ffffff',
                },
                '& .MuiChip-label': { px: 0.75, fontSize },
            }}
        />
    )
}
