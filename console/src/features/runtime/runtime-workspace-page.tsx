import {
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    IconButton,
    MenuItem,
    Stack,
    SvgIcon,
    TextField,
    Typography,
} from '@mui/material'
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useAppColorMode } from '../../app/providers/color-mode'
import { PageDescriptionHeader } from '../../shared/design-system/page-description-header'

type RuntimeWorkspaceItem = {
    key: string
    language: string
    versions: string[]
    runtimeApp: string
    startupCommand: string
    projectPathPlaceholder: string
    defaultPort: string
    description: string
}

type ScopeRect = {
    top: number
    left: number
    width: number
    height: number
}

type RuntimeProjectForm = {
    name: string
    path: string
    version: string
    port: string
    startupCommand: string
    remark: string
}

function AppStoreActionIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M7 4h10l1 4h2v2h-1l-1 9H6L5 10H4V8h2l1-4Zm1.58 4h6.84l-.5-2H9.08l-.5 2ZM8 12v5h2v-5H8Zm6 0v5h2v-5h-2Z" /></SvgIcon>
}

function MyAppsActionIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm0 4v10h12V8H6Zm2 2h4v4H8v-4Z" /></SvgIcon>
}

function CreateProjectIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M19 11h-6V5h-2v6H5v2h6v6h2v-6h6v-2Z" /></SvgIcon>
}

function CloseIcon() {
    return <SvgIcon viewBox="0 0 24 24"><path d="M18.3 5.71 12 12l6.3 6.29-1.42 1.42L10.59 13.4 4.29 19.7 2.88 18.3 9.17 12 2.88 5.71 4.29 4.3l6.3 6.29 6.29-6.3 1.42 1.42Z" /></SvgIcon>
}

function RuntimeScopedOverlay({ open, scopeRect, onClose, darkMode, children }: { open: boolean; scopeRect: ScopeRect | null; onClose: () => void; darkMode: boolean; children: React.ReactNode }) {
    useEffect(() => {
        if (!open) {
            return
        }

        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                onClose()
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => {
            window.removeEventListener('keydown', handleKeyDown)
        }
    }, [onClose, open])

    if (!open || !scopeRect || typeof document === 'undefined') {
        return null
    }

    const availableHeight = Math.max(Math.round(scopeRect.height) - 32, 320)

    return createPortal(
        <Box
            sx={{
                position: 'fixed',
                top: scopeRect.top,
                left: scopeRect.left,
                width: scopeRect.width,
                height: scopeRect.height,
                zIndex: 1400,
            }}
        >
            <Box
                onClick={onClose}
                sx={{
                    position: 'absolute',
                    inset: 0,
                    backgroundColor: darkMode ? 'rgba(2, 6, 23, 0.62)' : 'rgba(15, 23, 42, 0.18)',
                }}
            />
            <Box
                sx={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    px: { xs: 1.5, md: 1.5 },
                    py: { xs: 1.5, md: 2.5 },
                    pointerEvents: 'none',
                }}
            >
                <Box
                    role="dialog"
                    aria-modal="true"
                    onClick={(event) => {
                        event.stopPropagation()
                    }}
                    sx={{
                        pointerEvents: 'auto',
                        width: { xs: 'min(100%, 860px)', md: 'min(860px, calc(100% - 16px))' },
                        maxWidth: '860px',
                        maxHeight: `${availableHeight}px`,
                        display: 'flex',
                        flexDirection: 'column',
                        backgroundColor: darkMode ? '#182235' : '#fff',
                        color: darkMode ? '#e5edf5' : '#0f172a',
                        borderRadius: '2px',
                        boxShadow: darkMode ? '0 24px 64px rgba(2, 6, 23, 0.62)' : '0 16px 40px rgba(15, 23, 42, 0.16)',
                        border: darkMode ? '1px solid rgba(148, 163, 184, 0.2)' : undefined,
                        overflow: 'hidden',
                    }}
                >
                    {children}
                </Box>
            </Box>
        </Box>,
        document.body,
    )
}

export function RuntimeWorkspacePage() {
    const navigate = useNavigate()
    const { i18n } = useTranslation('shell')
    const { colorMode } = useAppColorMode()
    const isChinese = (i18n.resolvedLanguage ?? i18n.language ?? 'en').toLowerCase().startsWith('zh')
    const isDarkMode = colorMode === 'dark'
    const scopeRef = useRef<HTMLDivElement | null>(null)

    const runtimeOptions = useMemo<RuntimeWorkspaceItem[]>(() => {
        return [
            {
                key: 'php',
                language: 'PHP',
                versions: ['8.4', '8.3', '8.2'],
                runtimeApp: 'PHP Runtime / Nginx / MySQL',
                startupCommand: 'php-fpm -F',
                projectPathPlaceholder: '/data/www/php-app',
                defaultPort: '9000',
                description: isChinese ? '站点 / CMS / Laravel' : 'Sites / CMS / Laravel',
            },
            {
                key: 'java',
                language: 'Java',
                versions: ['22', '21', '17'],
                runtimeApp: 'OpenJDK / Tomcat / Maven',
                startupCommand: 'java -jar app.jar',
                projectPathPlaceholder: '/data/www/java-app',
                defaultPort: '8080',
                description: isChinese ? 'Spring Boot / WAR' : 'Spring Boot / WAR',
            },
            {
                key: 'node',
                language: 'Node.js',
                versions: ['22', '20', '18'],
                runtimeApp: 'Node.js / PM2 / Nginx',
                startupCommand: 'pnpm start',
                projectPathPlaceholder: '/data/www/node-app',
                defaultPort: '3000',
                description: isChinese ? 'Next.js / NestJS' : 'Next.js / NestJS',
            },
            {
                key: 'go',
                language: 'Go',
                versions: ['1.24', '1.23', '1.22'],
                runtimeApp: 'Go Runtime / Nginx',
                startupCommand: './app',
                projectPathPlaceholder: '/data/www/go-app',
                defaultPort: '8080',
                description: isChinese ? 'Gin / Fiber / API' : 'Gin / Fiber / API',
            },
            {
                key: 'python',
                language: 'Python',
                versions: ['3.12', '3.11', '3.10'],
                runtimeApp: 'Python Runtime / Gunicorn / Nginx',
                startupCommand: 'gunicorn app:app',
                projectPathPlaceholder: '/data/www/python-app',
                defaultPort: '8000',
                description: isChinese ? 'Django / Flask / FastAPI' : 'Django / Flask / FastAPI',
            },
            {
                key: 'dotnet',
                language: '.NET',
                versions: ['9.0', '8.0', '6.0'],
                runtimeApp: '.NET Runtime / ASP.NET / Nginx',
                startupCommand: 'dotnet app.dll',
                projectPathPlaceholder: '/data/www/dotnet-app',
                defaultPort: '5000',
                description: isChinese ? 'ASP.NET Core / API' : 'ASP.NET Core / API',
            },
        ]
    }, [isChinese])

    const [selectedKey, setSelectedKey] = useState(runtimeOptions[0]?.key ?? 'php')
    const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
    const [dialogScopeRect, setDialogScopeRect] = useState<ScopeRect | null>(null)
    const selectedRuntime = runtimeOptions.find((item) => item.key === selectedKey) ?? runtimeOptions[0]

    const [form, setForm] = useState<RuntimeProjectForm>(() => ({
        name: '',
        path: runtimeOptions[0]?.projectPathPlaceholder ?? '/data/www/app',
        version: runtimeOptions[0]?.versions[0] ?? '',
        port: runtimeOptions[0]?.defaultPort ?? '8080',
        startupCommand: runtimeOptions[0]?.startupCommand ?? '',
        remark: '',
    }))

    useEffect(() => {
        setForm((currentValue) => ({
            ...currentValue,
            version: selectedRuntime.versions[0] ?? currentValue.version,
            port: selectedRuntime.defaultPort,
            startupCommand: selectedRuntime.startupCommand,
            path: currentValue.name.trim() ? currentValue.path : selectedRuntime.projectPathPlaceholder,
        }))
    }, [selectedRuntime])

    useEffect(() => {
        if (!isCreateDialogOpen) {
            return
        }

        const updateScopeRect = () => {
            const rect = scopeRef.current?.getBoundingClientRect()
            if (!rect) {
                return
            }

            setDialogScopeRect({
                top: rect.top,
                left: rect.left,
                width: rect.width,
                height: rect.height,
            })
        }

        updateScopeRect()
        window.addEventListener('resize', updateScopeRect)
        window.addEventListener('scroll', updateScopeRect, true)

        return () => {
            window.removeEventListener('resize', updateScopeRect)
            window.removeEventListener('scroll', updateScopeRect, true)
        }
    }, [isCreateDialogOpen])

    const copy = isChinese
        ? {
            pageTitle: '运行环境',
            pageDescription: '选择运行环境模板并准备源码部署。',
            openStore: '应用商店',
            openApps: '我的应用',
            create: '开始部署',
            dialogTitle: '创建项目',
            dialogSubtitle: '按照当前运行时模板填写项目目录、版本和启动方式。',
            formTitle: '项目配置',
            runtimeTitle: '运行时模板',
            runtimeApp: '运行环境应用',
            projectName: '项目名称',
            projectPath: '项目目录',
            projectVersion: '运行时版本',
            mappedPort: '外部映射端口',
            startupCommand: '启动命令',
            remark: '备注',
            cancel: '取消',
            submit: '创建项目',
            namePlaceholder: '例如：php-demo',
            remarkPlaceholder: '例如：用于站点发布或 API 服务',
            versionLabel: '推荐版本',
            projectSummary: '当前所选运行时',
            summaryTitle: '部署摘要',
            summaryDescription: '确认本次部署会使用的运行环境、版本、端口和默认启动方式。',
            stepsTitle: '部署流程',
            steps: [
                '选择语言运行时并确认推荐版本。',
                '填写项目名称、目录、端口和启动命令。',
                '创建后由平台准备运行环境，应用会自动出现在“我的应用”。',
            ],
            manageHintTitle: '部署后的管理位置',
            manageHintBody: '运行环境页只负责发起部署。状态、访问入口、日志和后续操作统一在“我的应用”中查看。',
        }
        : {
            pageTitle: 'Runtime environment',
            pageDescription: 'Choose a runtime template and prepare source deployment.',
            openStore: 'App Store',
            openApps: 'My Apps',
            create: 'Start deployment',
            dialogTitle: 'Create project',
            dialogSubtitle: 'Fill in the project path, version, and startup method from the active runtime template.',
            formTitle: 'Project settings',
            runtimeTitle: 'Runtime template',
            runtimeApp: 'Runtime app',
            projectName: 'Project name',
            projectPath: 'Project path',
            projectVersion: 'Runtime version',
            mappedPort: 'Mapped port',
            startupCommand: 'Startup command',
            remark: 'Remark',
            cancel: 'Cancel',
            submit: 'Create project',
            namePlaceholder: 'For example: php-demo',
            remarkPlaceholder: 'For example: website publishing or API service',
            versionLabel: 'Recommended versions',
            projectSummary: 'Current runtime',
            summaryTitle: 'Deployment summary',
            summaryDescription: 'Confirm the runtime, version, port, and default startup command used for this deployment.',
            stepsTitle: 'Deployment flow',
            steps: [
                'Choose the runtime template and recommended version.',
                'Fill in the project name, path, port, and startup command.',
                'After creation, the platform prepares the runtime and the deployed app appears in My Apps.',
            ],
            manageHintTitle: 'Where deployment is managed later',
            manageHintBody: 'This page only starts deployments. Runtime status, access entry, logs, and follow-up operations are managed in My Apps.',
        }

    const palette = {
        pageBg: isDarkMode ? '#0f172a' : '#ffffff',
        cardBg: isDarkMode ? '#111827' : '#ffffff',
        dialogBg: isDarkMode ? '#182235' : '#ffffff',
        cardSoft: isDarkMode ? '#0b1220' : '#f8fafc',
        tableHead: isDarkMode ? '#162033' : '#f8fafc',
        text: isDarkMode ? '#f8fafc' : '#0f172a',
        subtleText: isDarkMode ? '#94a3b8' : '#64748b',
        actionText: isDarkMode ? '#f8fafc' : '#475569',
        border: isDarkMode ? 'rgba(71, 85, 105, 0.65)' : 'rgba(226, 232, 240, 0.95)',
        borderStrong: isDarkMode ? 'rgba(148, 163, 184, 0.2)' : 'rgba(203, 213, 225, 0.9)',
        activeBg: isDarkMode ? '#1d4ed8' : '#eff6ff',
        activeText: '#eff6ff',
        activeSubtleText: isDarkMode ? '#dbeafe' : '#2563eb',
        idleBg: isDarkMode ? '#111827' : '#ffffff',
        idleHover: isDarkMode ? '#162033' : '#f8fafc',
        idleText: isDarkMode ? '#e5edf5' : '#334155',
        buttonHover: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(145, 158, 171, 0.12)',
    } as const

    const surfaceCardSx = {
        borderRadius: '2px',
        border: `1px solid ${palette.border}`,
        background: palette.cardBg,
        boxShadow: isDarkMode ? '0 12px 28px rgba(2, 6, 23, 0.28)' : '0 8px 24px rgba(15, 23, 42, 0.05)',
    } as const

    const installCardSx = {
        borderRadius: '2px',
        border: `1px solid ${palette.borderStrong}`,
        background: isDarkMode ? 'linear-gradient(180deg, #162033 0%, #111827 100%)' : 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
        boxShadow: isDarkMode ? '0 12px 28px rgba(2, 6, 23, 0.3)' : '0 8px 24px rgba(15, 23, 42, 0.06)',
    } as const

    const topActionButtonSx = {
        borderRadius: 0,
        textTransform: 'none',
        px: 1.25,
        color: palette.actionText,
        fontWeight: 600,
        backgroundColor: 'transparent',
        '&:hover': {
            backgroundColor: palette.buttonHover,
        },
    } as const

    const handleOpenCreateDialog = () => {
        const rect = scopeRef.current?.getBoundingClientRect()
        if (rect) {
            setDialogScopeRect({ top: rect.top, left: rect.left, width: rect.width, height: rect.height })
        }
        setIsCreateDialogOpen(true)
    }

    return (
        <Box
            ref={scopeRef}
            sx={{
                minHeight: 'calc(100vh - var(--shell-topbar-height) - var(--shell-footer-height, 40px) - 20px)',
                position: 'relative',
                mx: { xs: -1, md: -3 },
                my: { xs: -1.25, md: -2.25 },
                px: { xs: 2, md: 3 },
                py: { xs: 1.25, md: 1.5 },
                backgroundColor: palette.pageBg,
                overflowY: 'auto',
                overflowX: 'hidden',
            }}
        >
            <Stack spacing={2}>
                <PageDescriptionHeader
                    title={copy.pageTitle}
                    description={copy.pageDescription}
                    titleColor={palette.text}
                    descriptionColor={palette.subtleText}
                    actions={(
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                            <Button variant="text" onClick={() => navigate('/appstore')} startIcon={<AppStoreActionIcon />} sx={topActionButtonSx}>
                                {copy.openStore}
                            </Button>
                            <Button variant="text" onClick={() => navigate('/myapps')} startIcon={<MyAppsActionIcon />} sx={topActionButtonSx}>
                                {copy.openApps}
                            </Button>
                        </Box>
                    )}
                />

                <Card elevation={0} sx={surfaceCardSx}>
                    <CardContent sx={{ pb: '16px !important' }}>
                        <Stack spacing={1.5}>
                            <Stack spacing={1}>
                                <Box sx={{ display: 'grid', gap: 1, gridTemplateColumns: { xs: 'repeat(2, minmax(0, 1fr))', md: 'repeat(3, minmax(0, 1fr))', xl: 'repeat(6, minmax(0, 1fr))' } }}>
                                    {runtimeOptions.map((runtime) => {
                                        const active = runtime.key === selectedKey
                                        return (
                                            <Button
                                                key={runtime.key}
                                                onClick={() => setSelectedKey(runtime.key)}
                                                sx={{
                                                    minWidth: 0,
                                                    height: 76,
                                                    px: 1.5,
                                                    py: 1.25,
                                                    borderRadius: 0,
                                                    border: `1px solid ${active ? palette.activeBg : palette.border}`,
                                                    textTransform: 'none',
                                                    alignItems: 'flex-start',
                                                    justifyContent: 'flex-start',
                                                    color: active ? palette.activeText : palette.idleText,
                                                    backgroundColor: active ? palette.activeBg : palette.idleBg,
                                                    boxShadow: active ? (isDarkMode ? '0 12px 28px rgba(37, 99, 235, 0.24)' : 'inset 0 0 0 1px rgba(37, 99, 235, 0.18)') : 'none',
                                                    '&:hover': {
                                                        backgroundColor: active ? (isDarkMode ? '#2563eb' : '#dbeafe') : palette.idleHover,
                                                    },
                                                }}
                                            >
                                                <Stack spacing={0.4} sx={{ alignItems: 'flex-start' }}>
                                                    <Typography sx={{ fontSize: 15, fontWeight: 700, color: 'inherit' }}>{runtime.language}</Typography>
                                                    <Typography sx={{ fontSize: 12.5, lineHeight: 1.45, color: active ? palette.activeSubtleText : palette.subtleText }}>{runtime.description}</Typography>
                                                </Stack>
                                            </Button>
                                        )
                                    })}
                                </Box>
                            </Stack>
                        </Stack>
                    </CardContent>
                </Card>

                <Card elevation={0} sx={surfaceCardSx}>
                    <CardContent>
                        <Stack spacing={2}>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1.5, flexWrap: 'wrap' }}>
                                <Box>
                                    <Typography sx={{ fontSize: 16, fontWeight: 700, color: palette.text }}>{copy.summaryTitle}</Typography>
                                    <Typography sx={{ mt: 0.35, fontSize: 13, color: palette.subtleText }}>{copy.summaryDescription}</Typography>
                                </Box>
                                <Button variant="contained" startIcon={<CreateProjectIcon />} onClick={handleOpenCreateDialog} sx={{ borderRadius: 0, textTransform: 'none', boxShadow: 'none', fontWeight: 600 }}>
                                    {copy.create}
                                </Button>
                            </Box>

                            <Box
                                sx={{
                                    display: 'grid',
                                    gap: 1,
                                    gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))', xl: 'repeat(4, minmax(0, 1fr))' },
                                }}
                            >
                                {[
                                    { label: copy.runtimeTitle, value: selectedRuntime.language },
                                    { label: copy.versionLabel, value: selectedRuntime.versions.join(' / ') },
                                    { label: copy.mappedPort, value: selectedRuntime.defaultPort },
                                    { label: copy.startupCommand, value: selectedRuntime.startupCommand },
                                ].map((item) => (
                                    <Box key={item.label} sx={{ border: `1px solid ${palette.border}`, backgroundColor: palette.cardSoft, px: 1.5, py: 1.25 }}>
                                        <Typography sx={{ fontSize: 12.5, fontWeight: 700, color: palette.subtleText }}>{item.label}</Typography>
                                        <Typography sx={{ mt: 0.45, fontSize: 14, lineHeight: 1.6, color: palette.text }}>{item.value}</Typography>
                                    </Box>
                                ))}
                            </Box>

                            <Box sx={{ display: 'grid', gap: 1.25, gridTemplateColumns: { xs: '1fr', md: '1.15fr .85fr' } }}>
                                <Card elevation={0} sx={installCardSx}>
                                    <CardContent>
                                        <Stack spacing={1.25}>
                                            <Typography sx={{ fontSize: 15, fontWeight: 700, color: palette.text }}>{copy.stepsTitle}</Typography>
                                            <Stack spacing={1}>
                                                {copy.steps.map((step, index) => (
                                                    <Box key={step} sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                                                        <Chip label={index + 1} size="small" sx={{ borderRadius: 0, fontWeight: 700, minWidth: 28, backgroundColor: palette.activeBg, color: palette.activeText }} />
                                                        <Typography sx={{ fontSize: 14, lineHeight: 1.7, color: palette.subtleText }}>{step}</Typography>
                                                    </Box>
                                                ))}
                                            </Stack>
                                        </Stack>
                                    </CardContent>
                                </Card>

                                <Card elevation={0} sx={surfaceCardSx}>
                                    <CardContent>
                                        <Stack spacing={1.25}>
                                            <Typography sx={{ fontSize: 15, fontWeight: 700, color: palette.text }}>{copy.manageHintTitle}</Typography>
                                            <Typography sx={{ fontSize: 14, lineHeight: 1.7, color: palette.subtleText }}>{copy.manageHintBody}</Typography>
                                            <Button variant="text" onClick={() => navigate('/myapps')} startIcon={<MyAppsActionIcon />} sx={{ ...topActionButtonSx, justifyContent: 'flex-start', px: 0 }}>
                                                {copy.openApps}
                                            </Button>
                                        </Stack>
                                    </CardContent>
                                </Card>
                            </Box>
                        </Stack>
                    </CardContent>
                </Card>
            </Stack>

            <RuntimeScopedOverlay
                open={isCreateDialogOpen}
                scopeRect={dialogScopeRect}
                darkMode={isDarkMode}
                onClose={() => {
                    setIsCreateDialogOpen(false)
                }}
            >
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 2.5, py: 2, borderBottom: `1px solid ${palette.border}`, backgroundColor: palette.dialogBg }}>
                    <Box>
                        <Typography sx={{ fontSize: 18, fontWeight: 700, color: palette.text }}>{copy.dialogTitle}</Typography>
                        <Typography sx={{ mt: 0.5, fontSize: 13, lineHeight: 1.6, color: palette.subtleText }}>{copy.dialogSubtitle}</Typography>
                    </Box>
                    <IconButton onClick={() => setIsCreateDialogOpen(false)} sx={{ borderRadius: 0, color: palette.subtleText }}>
                        <CloseIcon />
                    </IconButton>
                </Box>
                <Box sx={{ px: 2.5, py: 2.5, overflowY: 'auto', backgroundColor: palette.dialogBg }}>
                    <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1fr) minmax(320px, 360px)' } }}>
                        <Card sx={installCardSx}>
                            <CardContent>
                                <Stack spacing={1.5}>
                                    <Typography sx={{ fontSize: 16, fontWeight: 700, color: palette.text }}>{copy.formTitle}</Typography>
                                    <TextField
                                        label={copy.projectName}
                                        value={form.name}
                                        onChange={(event) => {
                                            const value = event.target.value
                                            setForm((currentValue) => ({
                                                ...currentValue,
                                                name: value,
                                                path: value.trim() ? `/data/www/${value.trim()}` : selectedRuntime.projectPathPlaceholder,
                                            }))
                                        }}
                                        placeholder={copy.namePlaceholder}
                                        size="small"
                                        fullWidth
                                        sx={{
                                            '& .MuiOutlinedInput-root': { borderRadius: '4px', backgroundColor: palette.cardBg },
                                            '& .MuiInputBase-input': { color: palette.text },
                                            '& .MuiInputLabel-root': { color: palette.subtleText },
                                        }}
                                    />
                                    <TextField
                                        label={copy.projectPath}
                                        value={form.path}
                                        onChange={(event) => {
                                            setForm((currentValue) => ({ ...currentValue, path: event.target.value }))
                                        }}
                                        size="small"
                                        fullWidth
                                        sx={{
                                            '& .MuiOutlinedInput-root': { borderRadius: '4px', backgroundColor: palette.cardBg },
                                            '& .MuiInputBase-input': { color: palette.text },
                                            '& .MuiInputLabel-root': { color: palette.subtleText },
                                        }}
                                    />
                                    <Box sx={{ display: 'grid', gap: 1.5, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
                                        <TextField
                                            select
                                            label={copy.projectVersion}
                                            value={form.version}
                                            onChange={(event) => {
                                                setForm((currentValue) => ({ ...currentValue, version: event.target.value }))
                                            }}
                                            size="small"
                                            fullWidth
                                            sx={{
                                                '& .MuiOutlinedInput-root': { borderRadius: '4px', backgroundColor: palette.cardBg },
                                                '& .MuiSelect-select': { color: palette.text },
                                                '& .MuiInputLabel-root': { color: palette.subtleText },
                                            }}
                                        >
                                            {selectedRuntime.versions.map((version) => (
                                                <MenuItem key={version} value={version}>{version}</MenuItem>
                                            ))}
                                        </TextField>
                                        <TextField
                                            label={copy.mappedPort}
                                            value={form.port}
                                            onChange={(event) => {
                                                setForm((currentValue) => ({ ...currentValue, port: event.target.value }))
                                            }}
                                            size="small"
                                            fullWidth
                                            sx={{
                                                '& .MuiOutlinedInput-root': { borderRadius: '4px', backgroundColor: palette.cardBg },
                                                '& .MuiInputBase-input': { color: palette.text },
                                                '& .MuiInputLabel-root': { color: palette.subtleText },
                                            }}
                                        />
                                    </Box>
                                    <TextField
                                        label={copy.startupCommand}
                                        value={form.startupCommand}
                                        onChange={(event) => {
                                            setForm((currentValue) => ({ ...currentValue, startupCommand: event.target.value }))
                                        }}
                                        size="small"
                                        fullWidth
                                        sx={{
                                            '& .MuiOutlinedInput-root': { borderRadius: '4px', backgroundColor: palette.cardBg },
                                            '& .MuiInputBase-input': { color: palette.text },
                                            '& .MuiInputLabel-root': { color: palette.subtleText },
                                        }}
                                    />
                                    <TextField
                                        label={copy.remark}
                                        value={form.remark}
                                        onChange={(event) => {
                                            setForm((currentValue) => ({ ...currentValue, remark: event.target.value }))
                                        }}
                                        placeholder={copy.remarkPlaceholder}
                                        size="small"
                                        fullWidth
                                        multiline
                                        minRows={3}
                                        sx={{
                                            '& .MuiOutlinedInput-root': { borderRadius: '4px', backgroundColor: palette.cardBg },
                                            '& .MuiInputBase-input': { color: palette.text },
                                            '& .MuiInputLabel-root': { color: palette.subtleText },
                                        }}
                                    />
                                </Stack>
                            </CardContent>
                        </Card>

                        <Card sx={installCardSx}>
                            <CardContent>
                                <Stack spacing={1.5}>
                                    <Typography sx={{ fontSize: 16, fontWeight: 700, color: palette.text }}>{copy.runtimeTitle}</Typography>
                                    <Stack spacing={0.5}>
                                        <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: palette.subtleText }}>{copy.runtimeApp}</Typography>
                                        <Typography sx={{ fontSize: 14, fontWeight: 600, color: palette.text }}>{selectedRuntime.runtimeApp}</Typography>
                                    </Stack>
                                    <Stack spacing={0.5}>
                                        <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: palette.subtleText }}>{copy.versionLabel}</Typography>
                                        <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                                            {selectedRuntime.versions.map((version) => (
                                                <Chip key={version} label={version} size="small" sx={{ borderRadius: 0, backgroundColor: palette.cardSoft, color: palette.idleText, border: `1px solid ${palette.border}` }} />
                                            ))}
                                        </Box>
                                    </Stack>
                                    <Stack spacing={0.5}>
                                        <Typography sx={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: palette.subtleText }}>{copy.startupCommand}</Typography>
                                        <Box sx={{ px: 1.25, py: 1, border: `1px solid ${palette.border}`, backgroundColor: palette.cardSoft, fontSize: 13, color: palette.idleText }}>{selectedRuntime.startupCommand}</Box>
                                    </Stack>
                                </Stack>
                            </CardContent>
                        </Card>
                    </Box>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, px: 2.5, py: 1.75, borderTop: `1px solid ${palette.border}`, backgroundColor: palette.dialogBg }}>
                    <Button variant="text" onClick={() => setIsCreateDialogOpen(false)} sx={{ borderRadius: 0, textTransform: 'none', color: palette.subtleText }}>
                        {copy.cancel}
                    </Button>
                    <Button variant="contained" startIcon={<CreateProjectIcon />} sx={{ borderRadius: 0, textTransform: 'none', boxShadow: 'none', fontWeight: 600 }}>
                        {copy.submit}
                    </Button>
                </Box>
            </RuntimeScopedOverlay>
        </Box>
    )
}
