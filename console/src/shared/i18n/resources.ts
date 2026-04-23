export const shellResources = {
    en: {
        shell: {
            brand: {
                logoAriaLabel: 'Websoft9 logo placeholder',
                title: 'Websoft9',
            },
            hero: {
                kicker: 'Story 1.2 baseline',
                title: 'One shell for product-wide routing and bilingual entry.',
                description:
                    'The console now owns its routing surface, locale resources, and shell composition so upcoming stories can attach feature pages without pulling language state from Cockpit.',
            },
            navigation: {
                sections: {
                    system: 'System',
                    tools: 'Tools',
                },
            },
            localeSwitcher: {
                label: 'Language',
            },
            user: {
                name: 'Administrator',
                role: 'Websoft9 User',
                menu: {
                    profile: 'Profile',
                    preferences: 'Preferences',
                    signOut: 'Sign out',
                },
            },
            locales: {
                en: 'English',
                'zh-CN': '中文',
            },
            nav: {
                dashboard: {
                    label: 'Overview',
                },
                appStore: {
                    label: 'App Store',
                },
                myApps: {
                    label: 'My Apps',
                },
                containers: {
                    label: 'Containers',
                },
                gateway: {
                    label: 'Gateway',
                },
                repository: {
                    label: 'Repository',
                },
                files: {
                    label: 'Files',
                },
                terminal: {
                    label: 'Terminal',
                },
                services: {
                    label: 'Services',
                },
                logs: {
                    label: 'Logs',
                },
                users: {
                    label: 'Users',
                },
                settings: {
                    label: 'Settings',
                },
            },
            pages: {
                dashboard: {
                    eyebrow: 'Shell route placeholder',
                    title: 'Overview shell entry',
                    description:
                        'This route reserves the top-level product overview, summary metrics, and quick operator feedback inside the shared console shell.',
                    nodeName: 'dev',
                    nodeSummary: 'Running Ubuntu 24.04.3 LTS',
                    primaryAction: 'Restart',
                    healthTitle: 'Health',
                    healthBody: 'Software updates are currently being applied in the background.',
                    lastLoginLabel: 'Last successful login',
                    lastLoginValue: 'Apr 22 15:57 from web console',
                    historyLink: 'View login history',
                    usageTitle: 'Usage',
                    cpuLabel: 'CPU',
                    cpuValue: '10% 12 CPU',
                    memoryLabel: 'Memory',
                    memoryValue: '7.3 / 23 GiB',
                    metricsLink: 'View metrics and history',
                    systemInfoTitle: 'System Information',
                    modelLabel: 'Model',
                    modelValue: 'QEMU Standard PC (Q35 + ICH9, 2009)',
                    machineIdLabel: 'Machine ID',
                    machineIdValue: 'c5411fd8d2a7455287fb1c693aa3ed7c',
                    uptimeLabel: 'Uptime',
                    uptimeValue: '1 month',
                    hardwareLink: 'View hardware details',
                    configTitle: 'Configuration',
                    hostnameLabel: 'Hostname',
                    hostnameValue: 'dev',
                    timeLabel: 'System Time',
                    timeValue: '2026-04-23 00:30',
                    domainLabel: 'Domain',
                    domainValue: 'Join Domain',
                    securityLabel: 'Secure Shell Keys',
                    securityValue: 'Show fingerprints',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'Dashboard summaries, product status cards, and shortcut actions can attach here without changing the shared shell structure.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'The shell now exposes a standard backend-style overview entry above the rest of the product navigation.',
                },
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
                services: {
                    eyebrow: 'Shell route placeholder',
                    title: 'Services shell entry',
                    description:
                        'This route reserves the shared surface for core service status, health, and operational controls managed by Websoft9.',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'Core service inventory, status views, and service-level controls can land here without taking over the dedicated repository, containers, or gateway workspaces.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'The route tree now separates product-owned runtime surfaces from third-party workspaces instead of grouping everything under a generic operations bucket.',
                },
                logs: {
                    eyebrow: 'Shell route placeholder',
                    title: 'Logs shell entry',
                    description:
                        'This route reserves the shared surface for product logs, runtime diagnostics, and drill-down visibility.',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'Platform log streams and focused troubleshooting flows can mount here without colliding with the integration workspaces.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'The shell now exposes logs as its own first-class backend surface instead of hiding it behind a broader operations label.',
                },
                users: {
                    eyebrow: 'Shell route placeholder',
                    title: 'Users shell entry',
                    description:
                        'This route reserves the shared surface for administrators, users, and access-control management owned by Websoft9.',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'User onboarding, account management, and permission surfaces can attach here on the same shared shell boundary.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'The information architecture now matches a more standard backend console by giving user management its own menu entry.',
                },
                containers: {
                    eyebrow: 'Embedded workspace entry',
                    title: 'Containers workspace entry',
                    description:
                        'Portainer is exposed as a first-class container-management surface under the Websoft9 shell instead of being buried inside a generic operations or integrations bucket.',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'Container-management continuity, failure handling, and later native entry points can keep building on this stable route without moving user mental models again.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'This primary route reuses the Epic 2 workspace framework while restoring the original container-focused entry shape.',
                },
                gateway: {
                    eyebrow: 'Embedded workspace entry',
                    title: 'Gateway workspace entry',
                    description:
                        'Nginx Proxy Manager is exposed as a dedicated gateway-management surface under the Websoft9 shell.',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'Gateway continuity, degraded-state handling, and later native proxy flows can evolve here without passing through a generic integration catalog first.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'This route keeps the product-owned path and shared Epic 2 state contract while aligning navigation with the historical gateway mental model.',
                },
                repository: {
                    eyebrow: 'Embedded workspace entry',
                    title: 'Repository workspace entry',
                    description:
                        'Gitea is exposed as a dedicated repository-management surface under the Websoft9 shell.',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'Repository continuity and later native repository affordances can keep attaching to this route without reintroducing scattered legacy links.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'This route keeps the product-owned workspace and shared Epic 2 recovery model while restoring the original repository entry shape.',
                },
                files: {
                    eyebrow: 'Shell route placeholder',
                    title: 'Files shell entry',
                    description:
                        'This route reserves the shared surface for file browsing, transfer, and product-owned storage workflows inside the Websoft9 shell.',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'File browsing, uploads, downloads, and future file-level actions can attach here without borrowing space from the embedded repository or gateway workspaces.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'The shell now keeps file-centric workflows as their own top-level surface instead of forcing them into a generic utility bucket.',
                },
                terminal: {
                    eyebrow: 'Shell route placeholder',
                    title: 'Terminal shell entry',
                    description:
                        'This route reserves the shared surface for terminal access, command execution, and future operator flows inside the Websoft9 shell.',
                    nextStepTitle: 'What lands here next',
                    nextStepBody:
                        'Terminal continuity, session launch, and future shell-assisted operations can attach here without mixing with repository or container management surfaces.',
                    systemTitle: 'Current system state',
                    systemBody:
                        'The route tree now preserves a dedicated terminal mental model instead of hiding shell access behind a broader tools grouping.',
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
            appStorePage: {
                filters: {
                    searchPlaceholder: 'Enter an app name to search, such as WordPress, MySQL, GitLab ...',
                    allMainCategories: 'All',
                    allSubCategories: 'All',
                },
                results: {
                    sectionTitle: 'All',
                    title: '{{count}} apps',
                    helper: 'Keyword and category filters update the current visible app list immediately.',
                },
                states: {
                    loading: 'Loading App Store data...',
                    retry: 'Retry',
                    errorTitle: 'App Store data is temporarily unavailable',
                    errorDetail: 'The current available-app request failed with status {{statusCode}}. Retry after checking the AppHub API path.',
                    emptyTitle: 'No apps match the current filters',
                    emptyDetail: 'Adjust the keyword or category filter to widen the visible App Store results.',
                },
                card: {
                    imageFallbackAlt: 'App logo',
                    summaryFallback: 'Base app metadata is available, but this app does not currently expose a summary field.',
                    versionLabel: 'Version',
                    webAppLabel: 'Web App',
                    webAppYes: 'Yes',
                    webAppNo: 'No',
                    requirementLabel: 'Requirements',
                    requirementValue: '{{cpu}} CPU / {{memory}} GB / {{storage}} GB',
                    settingsLabel: 'Settings',
                    websiteAction: 'Website',
                },
                detail: {
                    versionLine: 'Version: {{version}}',
                    requirementLine: 'Minimum requirements: {{cpu}} vCPU, {{memory}} GB memory, {{storage}} GB storage',
                    categoriesLabel: 'Categories:',
                    overviewTitle: 'Overview',
                    descriptionTitle: 'Details',
                },
                install: {
                    versionLine: 'Version: {{version}}',
                    appIdLabel: 'Application name',
                    appIdHelper: 'Only letters and numbers from 2 to 20 are allowed. No special characters.',
                    versionLabel: 'Application version',
                    httpPortLabel: 'Application HTTP port',
                    httpsPortLabel: 'Application HTTPS port',
                    databasePortLabel: 'Database port',
                    dynamicPortLabel: '{{name}} port',
                    dynamicSettingLabel: '{{name}}',
                    setGlobalDomain: 'Set global domain',
                    addDomain: 'Add Domain',
                    customDomainLabel: 'Domain',
                    customDomainPlaceholder: 'Please enter a custom domain name.',
                    disableDomain: 'Disable',
                    enableDomain: 'Enable',
                    validation: {
                        appId: 'Please enter a custom application name between 2 and 20 characters.Cannot start with a number.',
                        customDomain: 'Please enter a custom domain name.',
                    },
                    submitting: 'Installing...',
                    feedback: {
                        success: 'The application has started installing. You can continue tracking it in My Apps.',
                        error: 'Installation failed. Please retry after checking the current configuration.',
                    },
                },
                actions: {
                    close: 'Close',
                    closeIcon: 'x',
                    install: 'Install',
                    delete: 'Delete',
                },
            },
            integrations: {
                hero: {
                    eyebrow: 'Embedded workspace baseline',
                    title: 'Stable product-owned entry cards for every integration surface.',
                    description:
                        'Gitea, Portainer, and NPM now have dedicated workspace routes, shared state vocabulary, and product-owned entry cards inside the shell.',
                    refresh: 'Refresh integration states',
                },
                card: {
                    workspaceTitle: 'Workspace contract',
                    statusTitle: 'Current probe result',
                    openWorkspace: 'Open workspace',
                    openDirect: 'Open routed path',
                },
                workspace: {
                    backToCatalog: 'Back to integrations',
                    bootstrappingSession: 'Preparing sign-in',
                    bootstrappingSessionDetail: 'Websoft9 is establishing the integration session before opening the embedded workspace.',
                    diagnosticsPath: 'Diagnostics path: {{path}}',
                    diagnosticsTitle: 'Diagnostics entry',
                    lastResolvedUrl: 'Last resolved probe URL: {{url}}',
                    openDirect: 'Open routed path in new tab',
                    recoveryTitle: 'Recovery and diagnostics',
                    retryProbe: 'Retry probe',
                    sessionBootstrapFailed: 'Sign-in bridge failed',
                    sessionBootstrapFailedDetail: 'Websoft9 could not establish the embedded sign-in session. Use diagnostics or open the service directly.',
                },
                states: {
                    loading: {
                        label: 'Loading',
                        summary: 'The shell is checking whether the product-owned integration path is responding.',
                        detail: 'Waiting for the first product-origin probe result.',
                        detailWithCode: 'Waiting for the first product-origin probe result.',
                        recovery: 'Wait for the initial probe or retry after the product gateway is ready.',
                    },
                    available: {
                        label: 'Available',
                        summary: 'The product-owned workspace path is responding and can host the embedded integration.',
                        detail: 'The routed workspace responded successfully through the product-owned origin.',
                        detailWithCode: 'The routed workspace responded with HTTP {{statusCode}} through the product-owned origin.',
                        recovery: 'If the embedded page still looks wrong, open the routed path in a new tab to compare behavior.',
                    },
                    unavailable: {
                        label: 'Unavailable',
                        summary: 'The workspace path did not respond cleanly. This usually means the service or gateway is not ready.',
                        detail: 'The product-owned route probe could not get a healthy response from the integration path.',
                        detailWithCode: 'The product-owned route probe returned HTTP {{statusCode}} instead of a healthy response.',
                        recovery: 'Check the product runtime, gateway health, and integration process availability before retrying.',
                    },
                    'configuration-error': {
                        label: 'Configuration Error',
                        summary: 'The routed workspace path responded with a configuration-like failure instead of a healthy page.',
                        detail: 'The routed workspace is reachable, but its response suggests a binding, route, or session bootstrap problem.',
                        detailWithCode: 'The routed workspace returned HTTP {{statusCode}}, which suggests a binding, route, or session bootstrap problem.',
                        recovery: 'Verify the reserved route, upstream service binding, and any session bootstrap requirements for this integration.',
                    },
                    'session-error': {
                        label: 'Session Continuity Error',
                        summary: 'The product-owned route resolved to an authentication surface instead of a continued embedded workspace session.',
                        detail: 'The integration path is reachable, but the response looks like a login or bootstrap restart instead of a continuous workspace.',
                        detailWithCode: 'The integration path returned HTTP {{statusCode}}, but the resolved response still looks like a login or bootstrap restart.',
                        recovery: 'Verify the delegated login, upstream cookies, and route-specific bootstrap flow before retrying the workspace.',
                    },
                },
                catalog: {
                    gitea: {
                        title: 'Gitea',
                        description: 'Repository and source-management workspace carried by the Websoft9 shell.',
                        workspaceBody:
                            'This workspace keeps repository operations under a product-owned route so later stories can add session continuity and degraded-state handling without changing the shell boundary.',
                    },
                    portainer: {
                        title: 'Portainer',
                        description: 'Container-management workspace mounted under the product-owned integrations surface.',
                        workspaceBody:
                            'This route anchors embedded container-management continuity while keeping failure handling and diagnostics owned by Websoft9.',
                    },
                    npm: {
                        title: 'Nginx Proxy Manager',
                        description: 'Proxy-management workspace aligned to the product-owned route boundary.',
                        workspaceBody:
                            'This route preserves proxy-management continuity in the shell while leaving application-domain ownership separate from platform-origin routing.',
                    },
                },
            },
        },
    },
    'zh-CN': {
        shell: {
            brand: {
                logoAriaLabel: 'Websoft9 标志占位',
                title: 'Websoft9',
            },
            hero: {
                kicker: 'Story 1.2 基线',
                title: '为全产品路由和双语入口建立统一壳层。',
                description:
                    '现在 console 自主管理路由表面、locale 资源和壳层组合，后续故事可以直接挂接功能页面，而不必再从 Cockpit 注入语言状态。',
            },
            navigation: {
                sections: {
                    system: '系统',
                    tools: '工具',
                },
            },
            localeSwitcher: {
                label: '语言',
            },
            user: {
                name: '管理员',
                role: 'Websoft9 用户',
                menu: {
                    profile: '个人资料',
                    preferences: '偏好设置',
                    signOut: '退出登录',
                },
            },
            locales: {
                en: 'English',
                'zh-CN': '中文',
            },
            nav: {
                dashboard: {
                    label: '概览',
                },
                appStore: {
                    label: '应用商店',
                },
                myApps: {
                    label: '我的应用',
                },
                containers: {
                    label: '容器',
                },
                gateway: {
                    label: '网关',
                },
                repository: {
                    label: '仓库',
                },
                files: {
                    label: '文件',
                },
                terminal: {
                    label: '终端',
                },
                services: {
                    label: '服务',
                },
                logs: {
                    label: '日志',
                },
                users: {
                    label: '用户',
                },
                settings: {
                    label: '设置',
                },
            },
            pages: {
                dashboard: {
                    eyebrow: '壳层路由占位',
                    title: '概览壳层入口',
                    description:
                        '这个路由为产品总览、摘要指标和运维快捷反馈提供共享壳层下的顶部入口。',
                    nodeName: 'dev',
                    nodeSummary: '运行中 Ubuntu 24.04.3 LTS',
                    primaryAction: '重启',
                    healthTitle: '健康',
                    healthBody: '正在检查软件包更新。',
                    lastLoginLabel: '最后成功的登录',
                    lastLoginValue: '4月22日 15:57 来自 web console',
                    historyLink: '查看登录历史记录',
                    usageTitle: '占用率',
                    cpuLabel: 'CPU',
                    cpuValue: '10% 12 CPU',
                    memoryLabel: '内存',
                    memoryValue: '7.3 / 23 GiB',
                    metricsLink: '查看指标和历史记录',
                    systemInfoTitle: '系统信息',
                    modelLabel: '型号',
                    modelValue: 'QEMU Standard PC (Q35 + ICH9, 2009)',
                    machineIdLabel: '机器编号',
                    machineIdValue: 'c5411fd8d2a7455287fb1c693aa3ed7c',
                    uptimeLabel: '运行时间',
                    uptimeValue: '上个月',
                    hardwareLink: '查看硬件详细信息',
                    configTitle: '配置',
                    hostnameLabel: '主机名',
                    hostnameValue: 'dev',
                    timeLabel: '系统时间',
                    timeValue: '2026年4月23日 00:30',
                    domainLabel: '域',
                    domainValue: '加入域',
                    securityLabel: '安全 shell 密钥',
                    securityValue: '显示指纹',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '仪表盘摘要、产品状态卡片和快捷动作都可以挂到这里，而不需要改变共享壳层结构。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '壳层现在在其它产品导航之前提供了一个更接近标准后台的概览入口。',
                },
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
                services: {
                    eyebrow: '壳层路由占位',
                    title: '服务壳层入口',
                    description:
                        '这个路由为 Websoft9 自有核心服务状态、健康情况和服务级操作预留稳定表面。',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '核心服务清单、状态视图和服务级控制都可以挂到这里，而不必侵入已经拥有独立入口的仓库、容器和网关工作区。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '路由树现在把产品自有运行时表面和第三方工作区拆开，而不是继续塞进一个泛化的“运维”分组。',
                },
                logs: {
                    eyebrow: '壳层路由占位',
                    title: '日志壳层入口',
                    description:
                        '这个路由为产品日志、运行时诊断和逐层排障可见性预留稳定表面。',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '平台日志流和聚焦诊断流程可以挂到这里，而不必和集成工作区混在一起。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '壳层现在把日志提升为独立后台表面，而不是隐藏在更宽泛的运维标签后面。',
                },
                users: {
                    eyebrow: '壳层路由占位',
                    title: '用户壳层入口',
                    description:
                        '这个路由为 Websoft9 自有的管理员、用户与访问控制管理预留稳定表面。',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '用户初始化、账号管理和权限表面都可以继续挂在这个共享壳层边界上。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '当前信息架构更接近标准后台，把用户管理提升为独立菜单入口。',
                },
                containers: {
                    eyebrow: '嵌入式工作区入口',
                    title: '容器工作区入口',
                    description:
                        'Portainer 现在以一级容器管理表面暴露在 Websoft9 壳层中，而不是继续埋在泛化的运维或集成分组里。',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '容器管理连续性、失败处理，以及后续更原生的入口能力都可以继续挂在这条稳定路由下，而不必再次移动用户心智。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '这个一级路由复用了 Epic 2 的工作区框架，同时把用户入口恢复到原先围绕容器工作的认知方式。',
                },
                gateway: {
                    eyebrow: '嵌入式工作区入口',
                    title: '网关工作区入口',
                    description:
                        'Nginx Proxy Manager 现在以独立网关管理表面暴露在 Websoft9 壳层中。',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '网关连续性、降级处理，以及后续更原生的代理管理能力都可以在这里演进，而不需要先经过集成目录。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '这条路由继续保留产品自有路径和 Epic 2 共享状态契约，同时让导航重新对齐旧版的网关心智。',
                },
                repository: {
                    eyebrow: '嵌入式工作区入口',
                    title: '仓库工作区入口',
                    description:
                        'Gitea 现在以独立仓库管理表面暴露在 Websoft9 壳层中。',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '仓库连续性以及后续更原生的仓库能力都可以继续挂在这条路由下，而不必回到分散的旧链接方式。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '这条路由保留了产品自有工作区和 Epic 2 共享恢复模型，同时把用户入口恢复到原先围绕仓库工作的认知方式。',
                },
                files: {
                    eyebrow: '壳层路由占位',
                    title: '文件壳层入口',
                    description:
                        '这个路由为文件浏览、传输和产品自有存储工作流预留共享壳层表面。',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '文件浏览、上传、下载，以及后续文件级操作都可以挂在这里，而不必借用仓库或网关工作区的表面。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '壳层现在把文件相关工作流提升为独立一级表面，而不是继续塞进泛化的工具分组。',
                },
                terminal: {
                    eyebrow: '壳层路由占位',
                    title: '终端壳层入口',
                    description:
                        '这个路由为终端访问、命令执行和后续运维工作流预留共享壳层表面。',
                    nextStepTitle: '后续功能将落在这里',
                    nextStepBody:
                        '终端连续性、会话启动以及后续 shell 辅助运维能力都可以附着在这里，而不会和仓库或容器管理表面混在一起。',
                    systemTitle: '当前系统状态',
                    systemBody:
                        '当前路由树保留了独立终端心智模型，而不是把 shell 入口继续隐藏在更宽泛的工具语义之后。',
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
            appStorePage: {
                filters: {
                    searchPlaceholder: '请输入要搜索的应用名称,例如:WordPress,MySQL,GitLab ...',
                    allMainCategories: '全部',
                    allSubCategories: '全部',
                },
                results: {
                    sectionTitle: '全部',
                    title: '{{count}} 个应用',
                    helper: '关键字和分类筛选会立即更新当前可见的应用列表。',
                },
                states: {
                    loading: '正在加载应用商店数据……',
                    retry: '重试',
                    errorTitle: '应用商店数据暂时不可用',
                    errorDetail: '当前 available-app 请求失败，状态码为 {{statusCode}}。请检查 AppHub API 路径后重试。',
                    emptyTitle: '当前筛选条件下没有匹配应用',
                    emptyDetail: '请调整关键字或分类筛选条件，以扩大当前可见结果。',
                },
                card: {
                    imageFallbackAlt: '应用 Logo',
                    summaryFallback: '当前应用已有基础元数据，但暂未提供 summary 字段。',
                    versionLabel: '版本',
                    webAppLabel: 'Web 应用',
                    webAppYes: '是',
                    webAppNo: '否',
                    requirementLabel: '资源要求',
                    requirementValue: '{{cpu}} CPU / {{memory}} GB / {{storage}} GB',
                    settingsLabel: '设置项',
                    websiteAction: '官网',
                },
                detail: {
                    versionLine: '版本: {{version}}',
                    requirementLine: '最低配置要求: {{cpu}} vCPU, {{memory}} GB memory, {{storage}} GB storage',
                    categoriesLabel: '类别:',
                    overviewTitle: '概览',
                    descriptionTitle: '详情',
                },
                install: {
                    versionLine: '版本: {{version}}',
                    appIdLabel: '应用名称',
                    appIdHelper: '只允许使用2-20位的字母和数字,不允许使用特殊字符.',
                    versionLabel: '应用版本',
                    httpPortLabel: '应用 HTTP 端口',
                    httpsPortLabel: '应用 HTTPS 端口',
                    databasePortLabel: '数据库端口',
                    dynamicPortLabel: '{{name}} 端口',
                    dynamicSettingLabel: '{{name}}',
                    setGlobalDomain: '设置全局域名',
                    addDomain: '添加域名',
                    customDomainLabel: '域名',
                    customDomainPlaceholder: '请输入自定义域名。',
                    disableDomain: '禁用',
                    enableDomain: '启用',
                    validation: {
                        appId: '请输入一个2-20位的自定义应用名称.不允许以数字开头.',
                        customDomain: '请输入自定义域名',
                    },
                    submitting: '安装中...',
                    feedback: {
                        success: '应用已经开始安装, 你可以到我的应用中继续跟踪。',
                        error: '安装失败, 请检查当前配置后重试。',
                    },
                },
                actions: {
                    close: '关闭',
                    closeIcon: 'x',
                    install: '安装',
                    delete: '删除',
                },
            },
            integrations: {
                hero: {
                    eyebrow: '嵌入式工作区基线',
                    title: '为每个集成表面建立稳定的产品自有入口卡片。',
                    description:
                        'Gitea、Portainer 和 NPM 现在都在壳层内拥有独立工作区路由、共享状态词汇和产品自有入口卡片。',
                    refresh: '刷新集成状态',
                },
                card: {
                    workspaceTitle: '工作区契约',
                    statusTitle: '当前探测结果',
                    openWorkspace: '打开工作区',
                    openDirect: '打开路由路径',
                },
                workspace: {
                    backToCatalog: '返回集成目录',
                    bootstrappingSession: '正在准备登录',
                    bootstrappingSessionDetail: 'Websoft9 正在先建立集成服务会话，再打开嵌入工作区。',
                    diagnosticsPath: '诊断路径：{{path}}',
                    diagnosticsTitle: '诊断入口',
                    lastResolvedUrl: '最近一次探测落点 URL：{{url}}',
                    openDirect: '在新标签页打开路由路径',
                    recoveryTitle: '恢复与诊断',
                    retryProbe: '重试探测',
                    sessionBootstrapFailed: '登录桥接失败',
                    sessionBootstrapFailedDetail: 'Websoft9 未能建立嵌入登录会话。请使用诊断信息或直接打开服务。',
                },
                states: {
                    loading: {
                        label: '加载中',
                        summary: '壳层正在检查产品自有集成路径是否有响应。',
                        detail: '正在等待第一次产品 origin 探测结果。',
                        detailWithCode: '正在等待第一次产品 origin 探测结果。',
                        recovery: '等待首次探测完成，或在产品 gateway 就绪后重试。',
                    },
                    available: {
                        label: '可用',
                        summary: '产品自有工作区路径已有响应，可以承载嵌入式集成。',
                        detail: '该路由工作区已通过产品自有 origin 成功响应。',
                        detailWithCode: '该路由工作区已通过产品自有 origin 返回 HTTP {{statusCode}}。',
                        recovery: '如果嵌入页面表现异常，可在新标签页打开该路由路径进行对比。',
                    },
                    unavailable: {
                        label: '不可用',
                        summary: '工作区路径没有正常响应，通常表示服务或 gateway 尚未就绪。',
                        detail: '产品自有路由探测未能从该集成路径获得健康响应。',
                        detailWithCode: '产品自有路由探测返回了 HTTP {{statusCode}}，而不是健康响应。',
                        recovery: '重试前先检查产品运行时、gateway 健康状态以及集成进程可用性。',
                    },
                    'configuration-error': {
                        label: '配置错误',
                        summary: '路由工作区路径返回了更像配置类故障的响应，而不是健康页面。',
                        detail: '该路由工作区可以访问，但响应更像是绑定、路由或会话引导问题。',
                        detailWithCode: '该路由工作区返回了 HTTP {{statusCode}}，通常意味着绑定、路由或会话引导存在问题。',
                        recovery: '请检查保留路由、上游服务绑定，以及该集成所需的会话引导条件。',
                    },
                    'session-error': {
                        label: '会话连续性错误',
                        summary: '产品自有路由最终落到了认证界面，而不是连续的嵌入式工作区会话。',
                        detail: '该集成路径可以访问，但响应看起来像登录页或会话引导重启，而不是连续工作区。',
                        detailWithCode: '该集成路径返回了 HTTP {{statusCode}}，但最终响应仍然更像登录页或会话引导重启。',
                        recovery: '请检查委派登录、上游 cookie，以及该路由对应的会话引导流程，再重试工作区。',
                    },
                },
                catalog: {
                    gitea: {
                        title: 'Gitea',
                        description: '由 Websoft9 壳层承载的仓库与源码管理工作区。',
                        workspaceBody:
                            '这个工作区让仓库操作继续挂在产品自有路由下，后续故事可以在不改变壳层边界的前提下补上会话连续性和降级处理。',
                    },
                    portainer: {
                        title: 'Portainer',
                        description: '挂载在产品自有集成表面下的容器管理工作区。',
                        workspaceBody:
                            '这个路由为嵌入式容器管理连续性提供锚点，同时让失败处理与诊断继续由 Websoft9 自己拥有。',
                    },
                    npm: {
                        title: 'Nginx Proxy Manager',
                        description: '与产品自有路由边界对齐的代理管理工作区。',
                        workspaceBody:
                            '这个路由在壳层内保留代理管理连续性，同时继续将应用域名访问职责与平台 origin 路由职责分离。',
                    },
                },
            },
        },
    },
} as const