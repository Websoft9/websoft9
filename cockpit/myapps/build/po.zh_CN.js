(function (root, data) {
    var loaded, module;

    /* Load into AMD if desired */
    if (typeof define === 'function' && define.amd) {
        define(data);
        loaded = true;
    }

    /* Load into Cockpit locale */
    if (typeof cockpit === 'object') {
        cockpit.locale(data)
        loaded = true;
    }

    if (!loaded)
        root.po = data;

    /* The syntax of this line is important  by po2json */
}(this, {
    "": {
        'plural-forms': function (n) {
            var nplurals, plural;
            nplurals = 1; plural = 0;
            return plural;
        },
        "language": "zh_CN",
        "x-generator": "Weblate 3.10.3"
    },
    "$0 day": [
        "$0 days",
        "$0 天"
    ],
    "$0 hour": [
        "$0 hours",
        "$0 小时"
    ],
    "$0 minute": [
        "$0 minutes",
        "$0 分钟"
    ],
    "$0 month": [
        "$0 months",
        "$0 月"
    ],
    "$0 week": [
        "$0 weeks",
        "$0 周"
    ],
    "$0 year": [
        "$0 years",
        "$0 年"
    ],
    "1 day": [
        null,
        "1 天"
    ],
    "1 hour": [
        null,
        "1 小时"
    ],
    "1 week": [
        null,
        "1 周"
    ],
    "5 minutes": [
        null,
        "5 分钟"
    ],
    "App Store": [
        null,
        "应用商店"
    ],
    "My Apps": [
        null,
        "我的应用"
    ],
    "All": [
        null,
        "全部"
    ],
    "developers": [
        null,
        "文档"
    ],
    "Version": [
        null,
        "版本"
    ],
    "Requires at least": [
        null,
        "最低配置要求"
    ],
    "Name": [
        null,
        "名称"
    ],
    "Close": [
        null,
        "关闭"
    ],
    "Install": [
        null,
        "安装"
    ],
    "Other Apps": [
        null,
        "其他应用"
    ],
    "Websoft9's Apps": [
        null,
        "微聚云应用"
    ],
    "Refresh": [
        null,
        "刷新"
    ],
    "All States": [
        null,
        "所有状态"
    ],
    "Domain": [
        null,
        "域名"
    ],
    "Access": [
        null,
        "访问"
    ],
    "Backups": [
        null,
        "备份"
    ],
    "Uninstall": [
        null,
        "卸载"
    ],
    "Updates": [
        null,
        "更新"
    ],
    "Please enter a custom application name between 2 and 20 characters.": [
        null,
        "请输入一个2-20位的自定义应用名称."
    ],
    "Only letters and numbers from 2 to 20 are allowed. No special characters.": [
        null,
        "只允许使用2-20位的字母和数字,不允许使用特殊字符."
    ],
    "Start App": [
        null,
        "启动应用"
    ],
    "Stop App": [
        null,
        "停止应用"
    ],
    "Start": [
        null,
        "启动"
    ],
    "Stop": [
        null,
        "停止"
    ],
    "Restart App": [
        null,
        "重启应用"
    ],
    "Documentation": [
        null,
        "文档"
    ],
    "This will immediately uninstall": [
        null,
        "这将马上卸载"
    ],
    "and remove all its data.": [
        null,
        "并且删除所有数据."
    ],
    "Start / Stop": [
        null,
        "启动 / 停止"
    ],
    "This will uninstall the app immediately and remove all its data.The app will be inaccessible.": [
        null,
        "这将立即卸载应用程序并删除其所有数据,该应用程序将无法访问."
    ],
    "Apps can be stopped to conserve server resources instead of uninstalling.": [
        null,
        "可以停止应用程序以节省服务器资源,而不是卸载."
    ],
    "This is the error message for": [
        null,
        "错误消息:"
    ],
    "Code: ": [
        null,
        "错误代码:"
    ],
    "Message: ": [
        null,
        "错误消息:"
    ],
    "Detail: ": [
        null,
        "错误详情:"
    ],
    "Support": [
        null,
        "支持"
    ],
    "Remove": [
        null,
        "删除"
    ],
    "This will immediately remove": [
        null,
        "这将立马删除"
    ],
    "Domain Binding": [
        null,
        "域名绑定"
    ],
    "Add": [
        null,
        "添加"
    ],
    "More": [
        null,
        "更多"
    ],
    "save": [
        null,
        "保存"
    ],
    "cancel": [
        null,
        "取消"
    ],
    "edit": [
        null,
        "编辑"
    ],
    "delete": [
        null,
        "删除"
    ],
    "Delete": [
        null,
        "删除"
    ],
    "default": [
        null,
        "默认"
    ],
    "set as default": [
        null,
        "设为默认"
    ],
    "Domain name cannot be empty": [
        null,
        "域名不能为空"
    ],
    "Please enter the correct domain name and cannot start with http or https!": [
        null,
        "请输入正确的域名,并且不能以http或者https开始！"
    ],
    "Are you sure you want to delete the domain for:": [
        null,
        "你确定删除绑定的域名："
    ],
    "Success": [
        null,
        "执行成功"
    ],
    "Delete domain binding": [
        null,
        "删除绑定域名"
    ],
    "saving...": [
        null,
        "保存中..."
    ],
    "Portainer": [
        null,
        "容器"
    ],
    "Container": [
        null,
        "容器"
    ],
    "Nginx": [
        null,
        "域名"
    ],
    "BackUp": [
        null,
        "备份"
    ],
    "Navigator": [
        null,
        "文件"
    ],
    "Search for apps like WordPress, MySQL, GitLab, …": [
        null,
        "请输入要搜索的应用名称,例如:WordPress,MySQL,GitLab, …"
    ],
    "App Overview": [
        null,
        "应用预览"
    ],
    "App Name": [
        null,
        "应用名称"
    ],
    "App Version": [
        null,
        "应用版本"
    ],
    "App Port": [
        null,
        "应用端口"
    ],
    "Created Time": [
        null,
        "创建时间"
    ],
    "Config Path": [
        null,
        "配置目录"
    ],
    "Data Path": [
        null,
        "数据目录"
    ],
    "Domain Access": [
        null,
        "域名访问"
    ],
    "Domain access for better application performance.HTTPS and custom configurations available.": [
        null,
        "域名访问以获得更好的应用程序性能,HTTPS和自定义配置可点击"
    ],
    "Add Domain": [
        null,
        "添加域名"
    ]
}));

