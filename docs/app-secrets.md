# 应用安装密钥（`env.secrets`）

应用模板通过 `variables.json` 的 `env.secrets` 声明「启动前必须由平台生成」的密钥。Websoft9 在**创建实例时**生成这些值并写入实例 `.env`，此后重建、升级、恢复都不会重新生成。

上游约定见 `docker-library` 仓库的 `docs/app-secret-spec.md` 与 `docs/appstore-release-spec.md`；本文只描述消费端（Websoft9）的实现。

## 声明形态

```json
"env": {
  "secrets": [
    "JWT_SECRET",
    { "SECRET_KEY": "base64" },
    { "AIRFLOW__CORE__FERNET_KEY": "fernet" },
    { "ANON_KEY": "jwt:JWT_SECRET" }
  ]
}
```

| 声明 | 生成方式 | 说明 |
|---|---|---|
| `"KEY"` | 按 `.env` 默认值的形状生成 | 保留长度与字符类别（十六进制大小写、`sk-` 前缀、`-` 分段）；逗号分隔列表（如 Strapi `APP_KEYS`）逐项生成后重新拼接 |
| `{ "KEY": "base64" }` | 解码默认值得到 `N` 字节 → 生成 `N` 个随机字节 → 标准 Base64（含 `=`） | 没有统一最小长度，长度由模板决定 |
| `{ "KEY": "fernet" }` | 32 字节 → URL-safe Base64（44 字符，含 `=`） | 与 Fernet 密钥格式一致 |
| `{ "KEY": "jwt:<SECRET_KEY>" }` | 解码默认 JWT 的 header/payload，`iat` 设为当前时间并保持原有 `exp - iat` 时长，用 `<SECRET_KEY>` 的值做 HS256 签名 | 签名密钥可以是另一个声明项，生成顺序不依赖声明顺序 |

`W9_POWER_PASSWORD`、`W9_RCODE` 是平台隐式字段，不需要在 `env.secrets` 重复声明。

## 规则字典

`base64`/`fernet`/`jwt` 的机器参数来自 App Store 发布的共享字典 `metadata/secret-rules.json`：

- 与 `metadata/database-types.json` 同源，位于 `<docker_library.path>` 的上一级 `metadata/` 目录（可用 `WEBSOFT9_SECRET_RULES_PATH` 覆盖）。
- 运行时同步脚本按 library 清单的 `metadata.secretRules { path, sha256 }` 做内容寻址下载、SHA-256 校验和原子替换，并写入同步状态 `secretRulesSha256`；仅字典变化的增量（`appsDelta` 为空）同样会更新。
- **字典缺失或非法时安装直接失败**，不会回退到内置实现或普通随机串。

## 优先级与安全

- 显式用户设置 > 实例缓存 > 新生成；缓存按实例身份加锁、原子写入，安装重试复用同一组值。
- 缓存同时记录每项的规则，声明从 `"KEY"` 改成 `{ "KEY": "base64" }`（或反向）时会重新生成，不会复用旧值。
- 生成值保证不含 `$`、空格、`#`、换行，避免 Compose 插值与 `.env` 解析问题。
- 密码类值不写入日志、安装状态或 API 响应。

## 相关代码

- `apphub/src/services/install_secrets.py`：声明解析、两阶段生成、缓存与 `.env` 原子写入。
- `apphub/src/services/secret_rules.py`：字典校验与 `base64` / `fernet` / `jwt` 生成器。
- `docker/scripts/platform-sync-runtime-assets.py`：共享字典同步（`databaseTypes`、`secretRules`）。
- 测试：`apphub/tests/test_install_secrets.py`、`apphub/tests/test_install_secret_rules.py`、`apphub/tests/test_platform_sync_dictionary.py`。
