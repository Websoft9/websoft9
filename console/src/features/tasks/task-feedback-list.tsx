import { Alert, Box, Button, Chip, CircularProgress, Paper, Stack, Typography } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'

export type TaskFeedbackItem = {
    key: string
    kind: string
    title: string
    status: 'running' | 'success' | 'failed'
    detail: string | null
    updated_at: string
    target_route: string
}

type TaskFeedbackListProps = {
    title: string
    description: string
    emptyTitle: string
    emptyDescription: string
    openLabel: string
    loading: boolean
    errorMessage?: string | null
    items: TaskFeedbackItem[]
    formatter: Intl.DateTimeFormat
}

function chipColorFromTaskStatus(status: TaskFeedbackItem['status']): 'success' | 'warning' | 'error' {
    if (status === 'success') {
        return 'success'
    }
    if (status === 'failed') {
        return 'error'
    }
    return 'warning'
}

export function TaskFeedbackList({
    title,
    description,
    emptyTitle,
    emptyDescription,
    openLabel,
    loading,
    errorMessage,
    items,
    formatter,
}: TaskFeedbackListProps) {
    return (
        <Paper
            elevation={0}
            sx={{
                p: { xs: 1.5, md: 2 },
                borderRadius: 3,
                border: '1px solid rgba(15, 23, 42, 0.08)',
                backgroundColor: '#ffffff',
                boxShadow: '0 10px 30px rgba(15, 23, 42, 0.04)',
                minHeight: 100,
            }}
        >
            <Stack spacing={2}>
                <Stack spacing={0.75}>
                    <Typography sx={{ fontSize: 18, fontWeight: 700 }}>{title}</Typography>
                    <Typography color="text.secondary" variant="body2">
                        {description}
                    </Typography>
                </Stack>

                {errorMessage ? <Alert severity="warning">{errorMessage}</Alert> : null}

                {loading ? (
                    <Stack sx={{ minHeight: 180, alignItems: 'center', justifyContent: 'center' }}>
                        <CircularProgress size={28} />
                    </Stack>
                ) : null}

                {!loading && !errorMessage && items.length === 0 ? (
                    <Box
                        sx={{
                            minHeight: 220,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            borderRadius: 2.5,
                            background: 'linear-gradient(180deg, rgba(248,250,252,0.9) 0%, rgba(255,255,255,1) 100%)',
                            border: '1px dashed rgba(15, 23, 42, 0.14)',
                            px: 2,
                        }}
                    >
                        <Stack spacing={0.75} sx={{ textAlign: 'center' }}>
                            <Typography sx={{ fontSize: 16, fontWeight: 600 }}>{emptyTitle}</Typography>
                            <Typography color="text.secondary" variant="body2">
                                {emptyDescription}
                            </Typography>
                        </Stack>
                    </Box>
                ) : null}

                {!loading && items.length > 0 ? (
                    <Stack spacing={1.25}>
                        {items.map((item) => (
                            <Box
                                key={item.key}
                                sx={{
                                    p: 1.4,
                                    borderRadius: 2.5,
                                    border: '1px solid rgba(15, 23, 42, 0.08)',
                                    background:
                                        item.status === 'failed'
                                            ? 'linear-gradient(180deg, rgba(254,242,242,0.98) 0%, rgba(255,255,255,1) 100%)'
                                            : item.status === 'running'
                                                ? 'linear-gradient(180deg, rgba(255,247,237,0.96) 0%, rgba(255,255,255,1) 100%)'
                                                : 'linear-gradient(180deg, rgba(240,253,244,0.98) 0%, rgba(255,255,255,1) 100%)',
                                }}
                            >
                                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25} sx={{ justifyContent: 'space-between' }}>
                                    <Stack spacing={0.75} sx={{ minWidth: 0 }}>
                                        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                                            <Typography sx={{ fontSize: 15, fontWeight: 700 }}>{item.title}</Typography>
                                            <Chip color={chipColorFromTaskStatus(item.status)} label={item.status} size="small" sx={{ fontWeight: 600 }} />
                                        </Stack>
                                        <Typography color="text.secondary" variant="body2">
                                            {item.detail || item.kind}
                                        </Typography>
                                        <Typography color="text.secondary" sx={{ fontSize: 12 }}>
                                            {formatter.format(new Date(item.updated_at))}
                                        </Typography>
                                    </Stack>
                                    <Button component={RouterLink} size="small" sx={{ borderRadius: 999, alignSelf: { xs: 'flex-start', sm: 'center' }, px: 1.5 }} to={item.target_route} variant="outlined">
                                        {openLabel}
                                    </Button>
                                </Stack>
                            </Box>
                        ))}
                    </Stack>
                ) : null}
            </Stack>
        </Paper>
    )
}
