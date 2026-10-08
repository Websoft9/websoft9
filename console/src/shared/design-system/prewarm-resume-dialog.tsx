import { Button, DialogActions, DialogContent, DialogTitle, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'

import { SurfaceDialog } from './standard-surfaces'
import { getSurfacePalette } from './surface-theme'

type PrewarmResumeDialogProps = {
    open: boolean
    subject: string
    scopeRect: { top: number; left: number; width: number; height: number } | null
    darkMode: boolean
    onClose: () => void
    onConfirm: () => void
}

export function PrewarmResumeDialog({ open, subject, scopeRect, darkMode, onClose, onConfirm }: PrewarmResumeDialogProps) {
    const { t } = useTranslation('shell')
    const palette = getSurfacePalette(darkMode)

    return (
        <SurfaceDialog
            open={open && Boolean(scopeRect)}
            onClose={onClose}
            scope="content"
            scopeRect={scopeRect}
            contentStrategy="viewport-fixed"
            darkMode={darkMode}
            aria-labelledby="prewarm-resume-title"
            aria-describedby="prewarm-resume-description"
            sx={{ zIndex: 1501, '& .MuiDialog-container': { alignItems: 'flex-start', px: 0, py: 2 } }}
            paperSx={{ width: 'min(480px, calc(100% - 24px))', maxWidth: 480 }}
        >
            <DialogTitle id="prewarm-resume-title" sx={{ px: 2.25, py: 1.5, fontSize: 16, fontWeight: 700, borderBottom: `1px solid ${palette.border}` }}>
                {t('scheduledTasks.prewarmResumeTitle')}
            </DialogTitle>
            <DialogContent sx={{ px: 2.25, py: 2 }}>
                <Typography id="prewarm-resume-description" sx={{ m: 0, fontSize: 14, lineHeight: 1.7, color: palette.subtleText }}>
                    {t('scheduledTasks.prewarmResumeDescription', { subject })}
                </Typography>
            </DialogContent>
            <DialogActions sx={{ px: 2.25, py: 1.25, borderTop: `1px solid ${palette.border}` }}>
                <Button
                    onClick={onClose}
                    variant="contained"
                    color="inherit"
                    sx={{ minWidth: 68, borderRadius: 0, boxShadow: 'none', border: `1px solid ${palette.border}`, backgroundColor: palette.actionBg, color: palette.subtleText, '&:hover': { backgroundColor: palette.actionHover, color: palette.text, boxShadow: 'none' } }}
                >
                    {t('scheduledTasks.actions.cancel')}
                </Button>
                <Button
                    onClick={onConfirm}
                    variant="contained"
                    sx={{ minWidth: 68, borderRadius: 0, boxShadow: 'none', border: '1px solid #ffbc00', backgroundColor: '#ffbc00', color: '#313a46', '&:hover': { backgroundColor: '#e0a700', borderColor: '#e0a700', boxShadow: 'none' } }}
                >
                    {t('scheduledTasks.prewarm.resume')}
                </Button>
            </DialogActions>
        </SurfaceDialog>
    )
}