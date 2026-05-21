export type SurfacePalette = {
    pageBg: string
    panelBg: string
    dialogBg: string
    panelSoft: string
    panelMuted: string
    panelHover: string
    text: string
    subtleText: string
    placeholderText: string
    border: string
    borderStrong: string
    divider: string
    actionBg: string
    actionHover: string
    accent: string
    accentSoft: string
    accentContrast: string
    warning: string
    warningSoft: string
    danger: string
    dangerSoft: string
    overlay: string
}

export function getSurfacePalette(darkMode: boolean): SurfacePalette {
    return darkMode
        ? {
            pageBg: '#0f172a',
            panelBg: '#111827',
            dialogBg: '#182235',
            panelSoft: '#162033',
            panelMuted: '#0f172a',
            panelHover: '#1f2937',
            text: '#e5edf5',
            subtleText: '#9fb0c3',
            placeholderText: '#64748b',
            border: 'rgba(255, 255, 255, 0.08)',
            borderStrong: 'rgba(148, 163, 184, 0.22)',
            divider: 'rgba(71, 85, 105, 0.52)',
            actionBg: '#1f2937',
            actionHover: '#334155',
            accent: '#93c5fd',
            accentSoft: 'rgba(96, 165, 250, 0.16)',
            accentContrast: '#0f172a',
            warning: '#fde68a',
            warningSoft: 'rgba(251, 191, 36, 0.16)',
            danger: '#fca5a5',
            dangerSoft: 'rgba(248, 113, 113, 0.14)',
            overlay: 'rgba(15, 23, 42, 0.18)',
        }
        : {
            pageBg: '#ffffff',
            panelBg: '#ffffff',
            dialogBg: '#ffffff',
            panelSoft: '#f8fafc',
            panelMuted: '#eef2f6',
            panelHover: '#eef2f7',
            text: '#111827',
            subtleText: '#64748b',
            placeholderText: '#94a3b8',
            border: 'rgba(15, 23, 42, 0.08)',
            borderStrong: 'rgba(203, 213, 225, 0.9)',
            divider: 'rgba(15, 23, 42, 0.08)',
            actionBg: '#eef2f7',
            actionHover: '#e2e8f0',
            accent: '#2563eb',
            accentSoft: 'rgba(59, 130, 246, 0.12)',
            accentContrast: '#ffffff',
            warning: '#92400e',
            warningSoft: 'rgba(245, 158, 11, 0.14)',
            danger: '#dc2626',
            dangerSoft: 'rgba(239, 68, 68, 0.1)',
            overlay: 'rgba(15, 23, 42, 0.18)',
        }
}