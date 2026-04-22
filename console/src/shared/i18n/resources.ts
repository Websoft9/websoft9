export const shellResources = {
    en: {
        shell: {
            brand: {
                kicker: 'Websoft9 Platform',
                title: 'Unified Console',
            },
            hero: {
                kicker: 'Story 1.2 baseline',
                title: 'One shell for product-wide routing and bilingual entry.',
                description:
                    'The console now owns its routing surface, locale resources, and shell composition so upcoming stories can attach feature pages without pulling language state from Cockpit.',
            },
            navigation: {
                title: 'Product navigation',
                description:
                    'These placeholders map to the target information architecture and prove the shared shell boundary.',
            },
            locales: {
                en: 'English',
                'zh-CN': '中文',
            },
            nav: {
                appStore: {
                    label: 'App Store',
                    hint: 'Browse and install products',
                },
                myApps: {
                    label: 'My Apps',
                    hint: 'Monitor installed applications',
                },
                operations: {
                    label: 'Operations',
                    hint: 'Tasks, backups, and runtime tools',
                },
                integrations: {
                    label: 'Integrations',
                    hint: 'Embedded product workspaces',
                },
                settings: {
                    label: 'Settings',
                    hint: 'Product configuration and access',
                },
            },
            pages: {
                appStore: {
                    eyebrow: 'Shell route placeholder',
                    title: 'App Store shell entry',
                    description:
                        'This route anchors the future store listing, filters, and installation flow inside the shared console shell.',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'Store browsing, product detail, and installation stories can attach to this route without rebuilding the app root.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'The shell confirms shared routing, theme, query client, and i18n can all render through the same application boundary.',
                },
                myApps: {
                    eyebrow: 'Shell route placeholder',
                    title: 'My Apps shell entry',
                    description:
                        'This route reserves the shared surface for installed applications, lifecycle actions, and detail drill-down.',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'Application inventory and detail stories can reuse the same shell nav and locale resources.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'Routing currently proves the top-level product boundary and keeps feature work out of the entry bootstrap layer.',
                },
                operations: {
                    eyebrow: 'Shell route placeholder',
                    title: 'Operations shell entry',
                    description:
                        'This route marks the future home for tasks, backups, terminal access, file management, and runtime visibility.',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'Operational tools can be added under one route cluster without inventing a second shell pattern.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'The route tree now reflects the target product IA rather than the temporary bootstrap page from Story 1.1.',
                },
                integrations: {
                    eyebrow: 'Shell route placeholder',
                    title: 'Integrations shell entry',
                    description:
                        'This route prepares the embedded workspaces for products like Gitea, Portainer, and NPM.',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'Integration stories can bind session continuity and degraded states to this route segment later.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'Bilingual shell text already flows through the same resource pipeline that later integrations can reuse.',
                },
                settings: {
                    eyebrow: 'Shell route placeholder',
                    title: 'Settings shell entry',
                    description:
                        'This route reserves the stable shell area for product settings, user management, and system preferences.',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'Admin initialization, settings, and sensitive configuration flows can mount here on the same provider stack.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'Language switching is product-owned and no longer depends on Cockpit locale globals or po.js assets.',
                },
            },
        },
    },
    'zh-CN': {
        shell: {
            brand: {
                kicker: 'Websoft9 平台',
                title: '统一控制台',
            },
            hero: {
                kicker: 'Story 1.2 基线',
                title: '为全产品路由和双语入口建立统一壳层。',
                description:
                    '现在 console 自主管理路由表面、locale 资源和壳层组合，后续故事可以直接挂接功能页面，而不必再从 Cockpit 注入语言状态。',
            },
            navigation: {
                title: '产品导航',
                description: '这些占位入口与目标信息架构对齐，用来证明共享壳层边界已经建立。',
            },
            locales: {
                en: 'English',
                'zh-CN': '中文',
            },
            nav: {
                appStore: {
                    label: '应用商店',
                    hint: '浏览并安装产品',
                },
                myApps: {
                    label: '我的应用',
                    hint: '查看已安装应用',
                },
                operations: {
                    label: '运维',
                    hint: '任务、备份与运行工具',
                },
                integrations: {
                    label: '集成',
                    hint: '嵌入式产品工作区',
                },
                settings: {
                    label: '设置',
                    hint: '产品配置与访问控制',
                },
            },
            pages: {
                appStore: {
                    eyebrow: '壳层路由占位',
                    title: '应用商店壳层入口',
                    description:
                        '这个路由为未来的商店列表、筛选和安装流程提供共享壳层下的稳定入口。',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '应用商店浏览、详情和安装任务可以直接附着到这个路由，而不必重建应用根节点。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '这个壳层已经证明共享路由、主题、查询客户端和 i18n 可以通过同一个应用边界一起渲染。',
                },
                myApps: {
                    eyebrow: '壳层路由占位',
                    title: '我的应用壳层入口',
                    description:
                        '这个路由为已安装应用列表、生命周期动作和详情页预留了共享壳层表面。',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '应用库存与详情故事可以复用同一套壳层导航和 locale 资源。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '当前路由树已经体现目标产品边界，不再停留在 Story 1.1 的临时启动页。',
                },
                operations: {
                    eyebrow: '壳层路由占位',
                    title: '运维壳层入口',
                    description:
                        '这个路由标记了未来任务、备份、终端、文件管理和运行时可见性的聚合入口。',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '运维工具后续都可以挂到同一条路由簇下，而不必再发明第二套壳层模式。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '路由树现在围绕目标信息架构组织，而不是继续沿用 Story 1.1 的启动占位页。',
                },
                integrations: {
                    eyebrow: '壳层路由占位',
                    title: '集成壳层入口',
                    description:
                        '这个路由为 Gitea、Portainer 和 NPM 等嵌入式产品工作区预留了稳定挂载点。',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '集成故事之后可以把会话连续性和降级处理绑定到这一路由段。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '双语壳层文案已经走通同一套资源管线，后续集成页面可以直接复用。',
                },
                settings: {
                    eyebrow: '壳层路由占位',
                    title: '设置壳层入口',
                    description:
                        '这个路由为产品设置、用户管理和系统偏好提供了稳定的壳层区域。',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '管理员初始化、设置和敏感配置流程可以继续挂到这套 provider 栈之上。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '语言切换现在由产品自身控制，不再依赖 Cockpit locale 全局变量或 po.js 资源。',
                },
            },
        },
    },
} as const