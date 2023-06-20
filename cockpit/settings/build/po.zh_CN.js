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
    "System Setting": [
        null,
        "系统设置"
    ],
    "Setting": [
        null,
        "设置"
    ],
    "Enable automatic updates": [
        null,
        "开启自动更新"
    ],
    "App Store Updates": [
        null,
        "应用商店更新"
    ],
    "System Updates": [
        null,
        "系统更新"
    ],
    "Current Version": [
        null,
        "当前版本"
    ],
    "Check for updates": [
        null,
        "检查更新"
    ],
    "Latest Version": [
        null,
        "最新版本"
    ],
    "Update Time": [
        null,
        "更新时间"
    ],
    "Update Content": [
        null,
        "更新内容"
    ],
    "Update": [
        null,
        "立即更新"
    ]
}));

