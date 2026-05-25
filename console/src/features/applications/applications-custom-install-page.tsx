import { Box, Button, Paper, Snackbar, Alert, Tab, Tabs, TextField, Typography, IconButton } from '@mui/material'
import { yaml as yamlLanguage } from '@codemirror/lang-yaml'
import { linter, lintGutter } from '@codemirror/lint'
import CodeMirror from '@uiw/react-codemirror'
import * as jsyaml from 'js-yaml'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAppColorMode } from '../../app/providers/color-mode'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'
import { getSurfaceFieldSx } from '../../shared/design-system/form-field-sx'
import { getSurfacePalette } from '../../shared/design-system/surface-theme'
import { SurfaceDialog } from '../../shared/design-system/standard-surfaces'
import { MAX_FILE_SIZE, MAX_FILE_SIZE_LABEL } from '../../shared/config/ui-limits'

// ── yaml linter (reused across renders) ──────────────────────────────────────

const yamlLinter = linter((view) => {
    const text = view.state.doc.toString()
    if (!text.trim()) return []
    try {
        jsyaml.load(text)
        return []
    } catch (e) {
        if (e instanceof jsyaml.YAMLException && e.mark != null) {
            const from = Math.min(e.mark.position, view.state.doc.length)
            const to = Math.min(from + 1, view.state.doc.length)
            return [{ from, to, severity: 'error' as const, message: e.reason || String(e.message) }]
        }
        return []
    }
})

// ── icons ─────────────────────────────────────────────────────────────────────

function UploadCloudIcon() {
    return (
        <Box
            component="svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeLinejoin="round"
            sx={{ width: 40, height: 40, color: '#94a3b8' }}
        >
            <polyline points="16 16 12 12 8 16" />
            <line x1="12" y1="12" x2="12" y2="21" />
            <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
        </Box>
    )
}

function TrashIcon() {
    return (
        <Box
            component="svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.6}
            strokeLinecap="round"
            strokeLinejoin="round"
            sx={{ width: 15, height: 15 }}
        >
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6l-1 14H6L5 6" />
            <path d="M10 11v6M14 11v6" />
            <path d="M9 6V4h6v2" />
        </Box>
    )
}

function FileIcon() {
    return (
        <Box
            component="svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.6}
            strokeLinecap="round"
            strokeLinejoin="round"
            sx={{ width: 13, height: 13, flexShrink: 0 }}
        >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
        </Box>
    )
}

function BackIcon() {
    return (
        <Box
            component="svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            sx={{ width: 15, height: 15 }}
        >
            <polyline points="15 18 9 12 15 6" />
        </Box>
    )
}

function RestoreIcon() {
    return (
        <Box
            component="svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
            sx={{ width: 15, height: 15 }}
        >
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
            <path d="M3 3v5h5" />
        </Box>
    )
}

function CheckCircleIcon() {
    return (
        <Box
            component="svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
            sx={{ width: 15, height: 15 }}
        >
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
        </Box>
    )
}

function DeployIcon() {
    return (
        <Box
            component="svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
            sx={{ width: 15, height: 15 }}
        >
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" />
            <polygon points="10 8 16 12 10 16 10 8" />
        </Box>
    )
}

// ── types ────────────────────────────────────────────────────────────────────

type EnvRow = { id: number; key: string; value: string }
type ConfigFile = { id: number; name: string; mountPath: string; content: string }

const MOUNT_BASE = './src/'

const DEFAULT_ENV_ROWS = (): EnvRow[] => [
    { id: uid(), key: 'APP_ENV', value: 'production' },
    { id: uid(), key: 'APP_KEY', value: 'changeme_please' },
]

const DEFAULT_CONFIG_FILES = (): ConfigFile[] => [
    {
        id: uid(),
        name: 'nginx.conf',
        mountPath: `${MOUNT_BASE}nginx.conf`,
        content: `server {
    listen 80;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        index index.html index.htm;
    }
}
`,
    },
]

const DEFAULT_COMPOSE = `services:
  web:
    image: nginx:latest
    ports:
      - "8080:80"
    environment:
      - APP_ENV=\${APP_ENV}
      - APP_KEY=\${APP_KEY}
    volumes:
      - web-data:/usr/share/nginx/html
      - ./src/nginx.conf:/etc/nginx/conf.d/default.conf
    restart: unless-stopped

volumes:
  web-data:
`

let nextId = 1
function uid() {
    return nextId++
}

// ── name validation (same rules as app store) ────────────────────────────────
function normalizeInstallName(value: string) {
    return value.toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 20)
}
function isInstallNameValid(value: string) {
    return /^[a-z][a-z0-9]{1,19}$/.test(value)
}

// ── file size limit ───────────────────────────────────────────────────
// (edit src/shared/config/ui-limits.ts to change the limit)

// ── component ─────────────────────────────────────────────────────────────────

export function ApplicationsCustomInstallPage() {
    const { t } = useTranslation()
    const navigate = useNavigate()
    const { colorMode } = useAppColorMode()
    const isDark = colorMode === 'dark'
    const palette = getSurfacePalette(isDark)
    const fieldSx = getSurfaceFieldSx(palette)

    // app name
    const [appName, setAppName] = useState('')

    // compose yaml
    const [composeContent, setComposeContent] = useState(DEFAULT_COMPOSE)
    const yamlFileInputRef = useRef<HTMLInputElement>(null)

    // env vars
    const [envMode, setEnvMode] = useState<'kv' | 'text'>('kv')
    const [envRows, setEnvRows] = useState<EnvRow[]>(() => DEFAULT_ENV_ROWS())
    const [envText, setEnvText] = useState('')
    const envFileInputRef = useRef<HTMLInputElement>(null)

    // config files
    const [configFiles, setConfigFiles] = useState<ConfigFile[]>(() => DEFAULT_CONFIG_FILES())
    const configFileInputRef = useRef<HTMLInputElement>(null)
    const [dragOver, setDragOver] = useState(false)

    // reset confirm dialog
    const [showResetConfirm, setShowResetConfirm] = useState(false)

    // validate result snackbar
    const [validateSnack, setValidateSnack] = useState<{ ok: boolean; msg: string } | null>(null)
    const [isValidating, setIsValidating] = useState(false)
    const [isDeploying, setIsDeploying] = useState(false)

    // ── env helpers ──

    function addEnvRow() {
        setEnvRows((rows) => [...rows, { id: uid(), key: '', value: '' }])
    }

    function updateEnvRow(id: number, field: 'key' | 'value', val: string) {
        setEnvRows((rows) => rows.map((r) => (r.id === id ? { ...r, [field]: val } : r)))
    }

    function removeEnvRow(id: number) {
        setEnvRows((rows) => rows.filter((r) => r.id !== id))
    }

    function handleEnvFileImport(file: File | null) {
        if (!file) return
        if (file.size > MAX_FILE_SIZE) {
            setValidateSnack({ ok: false, msg: t('customInstallPage.fileTooLarge', { name: file.name, max: MAX_FILE_SIZE_LABEL }) })
            return
        }
        const reader = new FileReader()
        reader.onload = (e) => {
            const text = (e.target?.result as string) ?? ''
            if (envMode === 'text') {
                setEnvText(text)
            } else {
                const parsed: EnvRow[] = text
                    .split('\n')
                    .map((line) => line.trim())
                    .filter((line) => line && !line.startsWith('#'))
                    .map((line) => {
                        const eq = line.indexOf('=')
                        return { id: uid(), key: line.slice(0, eq).trim(), value: line.slice(eq + 1).trim() }
                    })
                if (parsed.length > 0) setEnvRows(parsed)
            }
        }
        reader.readAsText(file)
    }

    // ── yaml helpers ──

    function handleYamlFileImport(file: File | null) {
        if (!file) return
        if (file.size > MAX_FILE_SIZE) {
            setValidateSnack({ ok: false, msg: t('customInstallPage.fileTooLarge', { name: file.name, max: MAX_FILE_SIZE_LABEL }) })
            return
        }
        const reader = new FileReader()
        reader.onload = (e) => setComposeContent((e.target?.result as string) ?? '')
        reader.readAsText(file)
    }

    // ── config file helpers ──

    function addConfigFile(file: File) {
        if (file.size > MAX_FILE_SIZE) {
            setValidateSnack({ ok: false, msg: t('customInstallPage.fileTooLarge', { name: file.name, max: MAX_FILE_SIZE_LABEL }) })
            return
        }
        const reader = new FileReader()
        reader.onload = (e) => {
            const content = (e.target?.result as string) ?? ''
            setConfigFiles((prev) => [...prev, { id: uid(), name: file.name, mountPath: `${MOUNT_BASE}${file.name}`, content }])
        }
        reader.readAsText(file)
    }

    function removeConfigFile(id: number) {
        setConfigFiles((prev) => prev.filter((f) => f.id !== id))
    }

    function handleResetExample() {
        setShowResetConfirm(true)
    }

    function handleConfirmReset() {
        setShowResetConfirm(false)
        setAppName('')
        setComposeContent(DEFAULT_COMPOSE)
        setEnvMode('kv')
        setEnvRows(DEFAULT_ENV_ROWS())
        setEnvText('')
        setConfigFiles(DEFAULT_CONFIG_FILES())
    }

    async function handleValidate() {
        // Validate app name
        const normalizedName = normalizeInstallName(appName)
        if (!normalizedName) {
            setValidateSnack({ ok: false, msg: t('customInstallPage.appName.required') })
            return
        }
        if (!isInstallNameValid(normalizedName)) {
            setValidateSnack({ ok: false, msg: t('customInstallPage.appName.nameError') })
            return
        }
        const appId = normalizedName

        // Validate env: value present but key empty
        if (envMode === 'kv') {
            const badRows = envRows.filter((r) => r.value.trim() && !r.key.trim())
            if (badRows.length > 0) {
                setValidateSnack({ ok: false, msg: t('customInstallPage.validate.envKeyRequired') })
                return
            }
        }

        // Build env list from current mode
        const envEntries: { key: string; value: string }[] =
            envMode === 'kv'
                ? envRows.filter((r) => r.key.trim()).map((r) => ({ key: r.key.trim(), value: r.value }))
                : envText
                    .split('\n')
                    .map((line) => line.trim())
                    .filter((line) => line && !line.startsWith('#') && line.includes('='))
                    .map((line) => { const idx = line.indexOf('='); return { key: line.slice(0, idx).trim(), value: line.slice(idx + 1) } })
                    .filter((e) => e.key)

        // Build mounts — strip leading ./ so backend path validator accepts them
        const mounts = configFiles.map((f) => ({
            path: f.mountPath.replace(/^\.\//, ''),
            content: '',
        }))

        setIsValidating(true)
        try {
            const response = await fetch('/api/apps/install/compose/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ app_id: appId, compose_content: composeContent, env: envEntries, mounts }),
            })
            if (response.ok) {
                const data = await response.json() as { valid: boolean; services: string[]; details: string }
                setValidateSnack({ ok: true, msg: t('customInstallPage.validate.success', { services: data.services.join(', ') }) })
            } else {
                const err = await response.json() as { message?: string; details?: string }
                setValidateSnack({ ok: false, msg: err.details || err.message || t('customInstallPage.validate.failed') })
            }
        } catch (e) {
            setValidateSnack({ ok: false, msg: e instanceof Error ? e.message : String(e) })
        } finally {
            setIsValidating(false)
        }
    }

    async function handleDeploy() {
        const normalizedName = normalizeInstallName(appName)
        if (!normalizedName) {
            setValidateSnack({ ok: false, msg: t('customInstallPage.appName.required') })
            return
        }
        if (!isInstallNameValid(normalizedName)) {
            setValidateSnack({ ok: false, msg: t('customInstallPage.appName.nameError') })
            return
        }
        const appId = normalizedName

        // Build env list from current mode
        const envEntries: { key: string; value: string }[] =
            envMode === 'kv'
                ? envRows.filter((r) => r.key.trim()).map((r) => ({ key: r.key.trim(), value: r.value }))
                : envText
                    .split('\n')
                    .map((line) => line.trim())
                    .filter((line) => line && !line.startsWith('#') && line.includes('='))
                    .map((line) => { const idx = line.indexOf('='); return { key: line.slice(0, idx).trim(), value: line.slice(idx + 1) } })
                    .filter((e) => e.key)

        // Build mounts — strip leading ./ so backend path validator accepts them
        const mounts = configFiles.map((f) => ({
            path: f.mountPath.replace(/^\.\//, ''),
            content: f.content,
        }))

        setIsDeploying(true)
        try {
            const response = await fetch('/api/apps/install/compose', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ app_id: appId, compose_content: composeContent, env: envEntries, mounts }),
            })
            if (response.ok) {
                const data = await response.json() as { app_id?: string; tracking_id?: string }
                const nextSearchParams = new URLSearchParams()
                if (data.app_id) nextSearchParams.set('trackedAppId', data.app_id)
                if (data.tracking_id) nextSearchParams.set('trackingId', data.tracking_id)
                navigate(nextSearchParams.size > 0 ? `/myapps?${nextSearchParams.toString()}` : '/myapps', { replace: true })
            } else {
                const err = await response.json() as { message?: string; details?: string }
                setValidateSnack({ ok: false, msg: err.details || err.message || t('customInstallPage.deploy.failed') })
            }
        } catch (e) {
            setValidateSnack({ ok: false, msg: e instanceof Error ? e.message : String(e) })
        } finally {
            setIsDeploying(false)
        }
    }

    function handleConfigFileDrop(e: React.DragEvent) {
        e.preventDefault()
        setDragOver(false)
        const files = Array.from(e.dataTransfer.files)
        files.forEach(addConfigFile)
    }

    // ── layout values ──

    const cardBorder = `1px solid ${palette.border}`
    const sectionHeaderSx = {
        fontSize: 13,
        fontWeight: 800,
        letterSpacing: '0.02em',
        color: palette.text,
    }

    // shared column template used by both top row and content (6:4 ratio)
    const columnsTemplate = { xs: '1fr', md: '3fr 2fr' }

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, gap: 1.5 }}>
            {/* ── page header ── */}
            <PageDescriptionHeader
                title={t('applicationsHubPage.menu.customInstall')}
                description={t('customInstallPage.description')}
                descriptionColor={palette.subtleText}
                sx={{ mt: 0, mb: 0 }}
                actions={
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button
                            className="app-shell-page-pill"
                            color="inherit"
                            size="small"
                            startIcon={<BackIcon />}
                            onClick={() => navigate('/applications/deploy')}
                        >
                            {t('customInstallPage.backToDeploy')}
                        </Button>
                        <Button
                            className="app-shell-page-pill"
                            color="inherit"
                            size="small"
                            startIcon={<RestoreIcon />}
                            onClick={handleResetExample}
                        >
                            {t('customInstallPage.resetExample')}
                        </Button>
                    </Box>
                }
            />

            {/* ── app name row (uses same columnsTemplate to keep width aligned with content below) ── */}
            <Box sx={{ display: 'grid', gridTemplateColumns: columnsTemplate, gap: 1.5, alignItems: 'center' }}>
                {/* left: label + text field (aligned with editor column) */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Typography sx={{ fontSize: 13.5, fontWeight: 800, color: palette.text, whiteSpace: 'nowrap', flexShrink: 0 }}>
                        {t('customInstallPage.appName.label')}
                    </Typography>
                    <TextField
                        fullWidth
                        size="small"
                        placeholder={t('customInstallPage.appName.placeholder')}
                        value={appName}
                        onChange={(e) => {
                            const normalized = normalizeInstallName(e.target.value)
                            setAppName(normalized)
                        }}
                        sx={fieldSx}
                    />
                </Box>
                {/* right: validate + deploy at far right */}
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 1 }}>
                    <Button
                        size="small"
                        variant="outlined"
                        color="inherit"
                        startIcon={<CheckCircleIcon />}
                        onClick={handleValidate}
                        disabled={isValidating}
                        sx={{
                            fontSize: 12,
                            fontWeight: 700,
                            textTransform: 'none',
                            borderRadius: '2px',
                            borderColor: palette.borderStrong,
                            color: palette.subtleText,
                            minWidth: 96,
                            px: 2,
                            py: 0.45,
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {t('customInstallPage.actions.validate')}
                    </Button>
                    <Button
                        size="small"
                        variant="contained"
                        disableElevation
                        startIcon={<DeployIcon />}
                        onClick={handleDeploy}
                        disabled={isDeploying}
                        sx={{
                            fontSize: 12,
                            fontWeight: 700,
                            textTransform: 'none',
                            borderRadius: '2px',
                            backgroundColor: '#2563eb',
                            color: '#fff',
                            minWidth: 96,
                            px: 2,
                            py: 0.45,
                            whiteSpace: 'nowrap',
                            '&:hover': { backgroundColor: '#1d4ed8' },
                        }}
                    >
                        {t('customInstallPage.actions.deploy')}
                    </Button>
                </Box>
            </Box>

            {/* ── main two-column area ── */}
            <Box
                sx={{
                    flex: 1,
                    minHeight: 0,
                    display: 'grid',
                    gridTemplateColumns: columnsTemplate,
                    gridTemplateRows: '1fr',
                    gap: 1.5,
                    alignItems: 'stretch',
                }}
            >
                {/* ── LEFT: YAML editor ── */}
                <Paper
                    elevation={0}
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        border: cardBorder,
                        borderRadius: '2px',
                        backgroundColor: palette.panelBg,
                        overflow: 'hidden',
                    }}
                >
                    {/* card header */}
                    <Box
                        sx={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            px: 1.5,
                            py: 1,
                            borderBottom: cardBorder,
                        }}
                    >
                        <Typography sx={sectionHeaderSx}>{t('customInstallPage.compose.title')}</Typography>
                        <Button
                            size="small"
                            variant="outlined"
                            color="inherit"
                            onClick={() => yamlFileInputRef.current?.click()}
                            sx={{
                                fontSize: 12,
                                fontWeight: 700,
                                textTransform: 'none',
                                borderRadius: '2px',
                                borderColor: palette.borderStrong,
                                color: palette.subtleText,
                                px: 1.25,
                                py: 0.4,
                                minHeight: 0,
                            }}
                        >
                            {t('customInstallPage.compose.importYaml')}
                        </Button>
                        <input
                            ref={yamlFileInputRef}
                            type="file"
                            accept=".yml,.yaml,text/plain"
                            hidden
                            onChange={(e) => {
                                handleYamlFileImport(e.target.files?.[0] ?? null)
                                e.target.value = ''
                            }}
                        />
                    </Box>

                    {/* editor - absolute fill so CodeMirror height:100% resolves correctly */}
                    <Box sx={{ flex: 1, minHeight: 0, position: 'relative' }}>
                        <Box
                            sx={{
                                position: 'absolute',
                                top: 0, left: 0, right: 0, bottom: 0,
                                overflow: 'hidden',
                                '& .cm-editor': { height: '100%', fontSize: 13.5 },
                                '& .cm-scroller': {
                                    overflow: 'auto',
                                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace',
                                },
                                '& .cm-gutters': isDark ? {
                                    backgroundColor: '#0d1117',
                                    borderRight: '1px solid rgba(255,255,255,0.06)',
                                } : {},
                                '& .cm-content': isDark ? { caretColor: '#c9d1d9' } : {},
                            }}
                        >
                            <CodeMirror
                                value={composeContent}
                                height="100%"
                                style={{ height: '100%' }}
                                theme={isDark ? 'dark' : 'light'}
                                extensions={[yamlLanguage(), yamlLinter, lintGutter()]}
                                onChange={(value) => setComposeContent(value)}
                                basicSetup={{
                                    lineNumbers: true,
                                    foldGutter: true,
                                    highlightActiveLine: true,
                                    highlightActiveLineGutter: true,
                                }}
                            />
                        </Box>
                    </Box>
                </Paper>

                {/* ── RIGHT: env + config ── */}
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, minHeight: 0 }}>

                    {/* ─── ENV card ─── */}
                    <Paper
                        elevation={0}
                        sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            border: cardBorder,
                            borderRadius: '2px',
                            backgroundColor: palette.panelBg,
                            overflow: 'hidden',
                            flex: 1,
                            minHeight: 0,
                        }}
                    >
                        {/* env header */}
                        <Box
                            sx={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                px: 1.5,
                                py: 1,
                                borderBottom: cardBorder,
                                flexShrink: 0,
                            }}
                        >
                            <Typography sx={sectionHeaderSx}>{t('customInstallPage.env.title')}</Typography>
                            <Button
                                size="small"
                                variant="outlined"
                                color="inherit"
                                onClick={() => envFileInputRef.current?.click()}
                                sx={{
                                    fontSize: 12,
                                    fontWeight: 700,
                                    textTransform: 'none',
                                    borderRadius: '2px',
                                    borderColor: palette.borderStrong,
                                    color: palette.subtleText,
                                    px: 1.25,
                                    py: 0.4,
                                    minHeight: 0,
                                }}
                            >
                                {t('customInstallPage.env.importDotenv')}
                            </Button>
                            <input
                                ref={envFileInputRef}
                                type="file"
                                accept=".env,text/plain"
                                hidden
                                onChange={(e) => {
                                    handleEnvFileImport(e.target.files?.[0] ?? null)
                                    e.target.value = ''
                                }}
                            />
                        </Box>

                        {/* mode tabs */}
                        <Box sx={{ borderBottom: cardBorder, flexShrink: 0 }}>
                            <Tabs
                                value={envMode}
                                onChange={(_, v) => {
                                    const newMode = v as 'kv' | 'text'
                                    if (newMode === 'text' && envMode === 'kv') {
                                        const lines = envRows
                                            .filter((r) => r.key.trim())
                                            .map((r) => `${r.key.trim()}=${r.value}`)
                                        setEnvText(lines.join('\n'))
                                    } else if (newMode === 'kv' && envMode === 'text') {
                                        const parsed: EnvRow[] = envText
                                            .split('\n')
                                            .map((line) => line.trim())
                                            .filter((line) => line && !line.startsWith('#') && line.includes('='))
                                            .map((line) => { const idx = line.indexOf('='); return { id: uid(), key: line.slice(0, idx).trim(), value: line.slice(idx + 1) } })
                                            .filter((e) => e.key)
                                        if (parsed.length > 0) {
                                            setEnvRows([...parsed, { id: uid(), key: '', value: '' }])
                                        }
                                    }
                                    setEnvMode(newMode)
                                }}
                                sx={{
                                    minHeight: 36,
                                    px: 1,
                                    '& .MuiTab-root': {
                                        minHeight: 36,
                                        fontSize: 12.5,
                                        fontWeight: 700,
                                        textTransform: 'none',
                                        color: palette.subtleText,
                                        py: 0,
                                        px: 1.5,
                                    },
                                    '& .Mui-selected': { color: palette.text },
                                    '& .MuiTabs-indicator': { backgroundColor: '#2563eb', height: 2 },
                                }}
                            >
                                <Tab value="kv" label={t('customInstallPage.env.kvMode')} />
                                <Tab value="text" label={t('customInstallPage.env.textMode')} />
                            </Tabs>
                        </Box>

                        {/* env content */}
                        <Box sx={{ flex: 1, minHeight: 0, position: 'relative', overflow: 'hidden' }}>
                            {envMode === 'kv' ? (
                                <Box sx={{ position: 'absolute', inset: 0, overflow: 'auto', p: 1.25, display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                                    {envRows.map((row) => (
                                        <Box key={row.id} sx={{ display: 'grid', gridTemplateColumns: '1fr 16px 1fr auto', gap: 0.5, alignItems: 'center' }}>
                                            <TextField
                                                size="small"
                                                placeholder="KEY"
                                                value={row.key}
                                                onChange={(e) => updateEnvRow(row.id, 'key', e.target.value)}
                                                sx={{
                                                    '& .MuiOutlinedInput-root': {
                                                        fontSize: 12.5,
                                                        fontFamily: 'ui-monospace, SFMono-Regular, monospace',
                                                        borderRadius: '2px',
                                                        backgroundColor: palette.panelBg,
                                                        '& .MuiOutlinedInput-notchedOutline': { borderColor: palette.borderStrong },
                                                    },
                                                    '& .MuiInputBase-input': { py: 0.7, px: 1 },
                                                }}
                                            />
                                            <Typography sx={{ textAlign: 'center', fontSize: 13, color: palette.subtleText, fontWeight: 700 }}>=</Typography>
                                            <TextField
                                                size="small"
                                                placeholder="VALUE"
                                                value={row.value}
                                                onChange={(e) => updateEnvRow(row.id, 'value', e.target.value)}
                                                sx={{
                                                    '& .MuiOutlinedInput-root': {
                                                        fontSize: 12.5,
                                                        fontFamily: 'ui-monospace, SFMono-Regular, monospace',
                                                        borderRadius: '2px',
                                                        backgroundColor: palette.panelBg,
                                                        '& .MuiOutlinedInput-notchedOutline': { borderColor: palette.borderStrong },
                                                    },
                                                    '& .MuiInputBase-input': { py: 0.7, px: 1 },
                                                }}
                                            />
                                            <IconButton
                                                size="small"
                                                onClick={() => removeEnvRow(row.id)}
                                                sx={{ color: palette.subtleText, p: 0.4, '&:hover': { color: palette.danger } }}
                                            >
                                                <TrashIcon />
                                            </IconButton>
                                        </Box>
                                    ))}

                                    <Button
                                        size="small"
                                        variant="text"
                                        color="inherit"
                                        onClick={addEnvRow}
                                        sx={{
                                            alignSelf: 'flex-start',
                                            mt: 0.5,
                                            fontSize: 12.5,
                                            fontWeight: 700,
                                            textTransform: 'none',
                                            color: '#2563eb',
                                            px: 0.5,
                                        }}
                                    >
                                        + {t('customInstallPage.env.addRow')}
                                    </Button>
                                </Box>
                            ) : (
                                <Box
                                    sx={{
                                        position: 'absolute',
                                        inset: 0,
                                        overflow: 'hidden',
                                        '& .cm-editor': { height: '100%', fontSize: 13 },
                                        '& .cm-scroller': {
                                            overflow: 'auto',
                                            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace',
                                        },
                                    }}
                                >
                                    <CodeMirror
                                        value={envText}
                                        height="100%"
                                        style={{ height: '100%' }}
                                        theme={isDark ? 'dark' : 'light'}
                                        onChange={(value) => setEnvText(value)}
                                        basicSetup={{ lineNumbers: true, highlightActiveLine: true }}
                                    />
                                </Box>
                            )}
                        </Box>
                    </Paper>

                    {/* ─── Config files card ─── */}
                    <Paper
                        elevation={0}
                        sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            border: cardBorder,
                            borderRadius: '2px',
                            backgroundColor: palette.panelBg,
                            overflow: 'hidden',
                            flex: 1,
                            minHeight: 0,
                        }}
                    >
                        {/* config header */}
                        <Box
                            sx={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                px: 1.5,
                                py: 1,
                                borderBottom: cardBorder,
                                flexShrink: 0,
                            }}
                        >
                            <Typography sx={sectionHeaderSx}>{t('customInstallPage.configFiles.title')}</Typography>
                            <Typography sx={{ fontSize: 12, color: palette.subtleText }}>
                                {t('customInstallPage.configFiles.mountBase')}
                                <Box component="span" sx={{ fontFamily: 'ui-monospace, monospace', fontWeight: 700, color: palette.text }}>
                                    {MOUNT_BASE}
                                </Box>
                            </Typography>
                        </Box>

                        {/* drag-drop zone */}
                        <Box
                            sx={{
                                flex: 1,
                                minHeight: 0,
                                display: 'flex',
                                flexDirection: 'column',
                                p: 1.25,
                                gap: 1,
                                overflow: 'auto',
                            }}
                        >
                            <Box
                                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                                onDragLeave={() => setDragOver(false)}
                                onDrop={handleConfigFileDrop}
                                onClick={() => configFileInputRef.current?.click()}
                                sx={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: 0.75,
                                    p: 2,
                                    borderRadius: '4px',
                                    border: `1.5px dashed ${dragOver ? '#2563eb' : palette.borderStrong}`,
                                    backgroundColor: dragOver ? (isDark ? 'rgba(37,99,235,0.08)' : 'rgba(37,99,235,0.04)') : 'transparent',
                                    cursor: 'pointer',
                                    transition: 'border-color 0.15s, background-color 0.15s',
                                    '&:hover': { borderColor: '#2563eb' },
                                }}
                            >
                                <UploadCloudIcon />
                                <Typography sx={{ fontSize: 13, fontWeight: 700, color: palette.text }}>
                                    {t('customInstallPage.configFiles.dropZoneTitle')}
                                </Typography>
                                <Typography sx={{ fontSize: 12, color: palette.subtleText, textAlign: 'center', lineHeight: 1.6 }}>
                                    {t('customInstallPage.configFiles.dropZoneDetail')}
                                </Typography>
                            </Box>
                            <input
                                ref={configFileInputRef}
                                type="file"
                                multiple
                                hidden
                                onChange={(e) => {
                                    Array.from(e.target.files ?? []).forEach(addConfigFile)
                                    e.target.value = ''
                                }}
                            />

                            {/* uploaded file list */}
                            {configFiles.map((file) => (
                                <Box
                                    key={file.id}
                                    sx={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between',
                                        gap: 1,
                                        px: 1,
                                        py: 0.6,
                                        borderRadius: '2px',
                                        border: `1px solid ${palette.borderStrong}`,
                                        backgroundColor: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
                                    }}
                                >
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
                                        <Box sx={{ color: palette.subtleText }}>
                                            <FileIcon />
                                        </Box>
                                        <Typography
                                            sx={{
                                                fontSize: 12.5,
                                                fontFamily: 'ui-monospace, monospace',
                                                color: palette.text,
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis',
                                                whiteSpace: 'nowrap',
                                            }}
                                        >
                                            {file.name}
                                            <Box component="span" sx={{ color: palette.subtleText, ml: 0.5 }}>
                                                (+ {file.mountPath})
                                            </Box>
                                        </Typography>
                                    </Box>
                                    <IconButton
                                        size="small"
                                        onClick={() => removeConfigFile(file.id)}
                                        sx={{ flexShrink: 0, p: 0.25, color: palette.subtleText, '&:hover': { color: palette.danger } }}
                                    >
                                        <Box component="span" sx={{ fontSize: 14, lineHeight: 1 }}>×</Box>
                                    </IconButton>
                                </Box>
                            ))}
                        </Box>
                    </Paper>
                </Box>
            </Box>

            {/* ── reset confirm dialog (SurfaceDialog matches my-apps style) ── */}
            <SurfaceDialog
                darkMode={isDark}
                open={showResetConfirm}
                onClose={() => setShowResetConfirm(false)}
                paperSx={{
                    width: { xs: 'min(100%, 560px)', md: 'min(560px, calc(100% - 20px))' },
                    maxWidth: '560px',
                    backgroundColor: palette.dialogBg,
                    color: palette.text,
                    border: `1px solid ${palette.border}`,
                }}
            >
                <Box sx={{ px: { xs: 2, md: 2.5 }, py: { xs: 1.5, md: 1.75 }, borderBottom: `1px solid ${palette.border}`, display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Typography sx={{ flex: 1, fontSize: { xs: 16, md: 18 }, fontWeight: 600, lineHeight: 1.2, color: palette.text }}>
                        {t('customInstallPage.resetConfirm.title')}
                    </Typography>
                    <IconButton onClick={() => setShowResetConfirm(false)} size="small" sx={{ width: 40, height: 40, color: palette.subtleText, borderRadius: '999px', backgroundColor: 'transparent', '&:hover': { backgroundColor: 'transparent', color: palette.text, opacity: 0.84 } }}>
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" /></svg>
                    </IconButton>
                </Box>
                <Box sx={{ px: { xs: 2, md: 2.5 }, py: 2.25, borderBottom: `1px solid ${palette.border}` }}>
                    <Typography sx={{ m: 0, fontSize: 14, lineHeight: 1.75, color: palette.subtleText, fontWeight: 400 }}>
                        {t('customInstallPage.resetConfirm.message')}
                    </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.5, py: 2 }}>
                    <Button
                        onClick={() => setShowResetConfirm(false)}
                        variant="contained"
                        sx={{ minWidth: 68, backgroundColor: palette.actionBg, color: palette.subtleText, borderRadius: 0, boxShadow: 'none', '&:hover': { backgroundColor: palette.actionHover, boxShadow: 'none', color: palette.text } }}
                    >
                        {t('customInstallPage.resetConfirm.cancel')}
                    </Button>
                    <Button
                        onClick={handleConfirmReset}
                        variant="contained"
                        sx={{ minWidth: 68, borderRadius: 0, boxShadow: 'none' }}
                    >
                        {t('customInstallPage.resetConfirm.confirm')}
                    </Button>
                </Box>
            </SurfaceDialog>

            {/* ── validate result snackbar ── */}
            <Snackbar
                open={validateSnack !== null}
                autoHideDuration={6000}
                onClose={() => setValidateSnack(null)}
                anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
            >
                <Alert
                    onClose={() => setValidateSnack(null)}
                    severity={validateSnack?.ok ? 'success' : 'error'}
                    sx={{ fontSize: 13, fontWeight: 600 }}
                >
                    {validateSnack?.msg}
                </Alert>
            </Snackbar>
        </Box>
    )
}
