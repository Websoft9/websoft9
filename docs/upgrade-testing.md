# 平台升级测试手册（模拟升级成功 / 失败）

本文面向开发与测试人员，说明如何在**标准安装的开发环境**里制造真实的「升级成功」「升级失败并回滚」现场，以及如何复位。

> 仅用于测试环境。升级会真实重建平台容器，期间控制台与应用访问会中断约 10–20 秒。

## 0. 关键路径与概念

| 对象 | 位置 / 名称 | 说明 |
|------|-------------|------|
| 升级状态 | `/opt/websoft9/data/upgrade/state.json` | 状态机：`idle / downloading / ready / applying / completed / degraded / rolled_back / rollback_failed / apply_interrupted` |
| 升级日志 | `/opt/websoft9/data/upgrade/logs/<run_id>.log` | Runner 写入，重试时按尝试追加（`===== attempt at … =====`） |
| 升级物料 | `/opt/websoft9/data/upgrade/staging/<run_id>/` | `docker-compose.yml`、`runner-upgrade.sh`、`task.env` |
| 回滚备份 | `/opt/websoft9/data/upgrade/backups/<run_id>/` | 升级前的 `.env` 与 `docker-compose.yml` |
| 执行器容器 | `websoft9-upgrade-<run_id 前 12 位>` | 真实执行升级；失败后保留用于诊断 |
| 当前版本标记 | 容器内 `/websoft9/version.json` | 决定页面「当前版本」与是否出现「可更新」 |
| 通道最新版本 | `data/upgrade/latest-version.json` | 每日检查缓存（24h） |

页面升级入口出现的条件是 `latest > current`。本开发环境的 artifact dev 通道为 `2.4.3`，因此需要把版本标记临时降到 `2.4.2`。

## 1. 一次性准备：让页面出现「可更新」

```bash
# 记录真实版本标记
docker exec websoft9-dev cat /websoft9/version.json      # {"version":"2.4.3","channel":"dev"}

# 降为 2.4.2，页面随即出现「可更新 / 下载更新」
printf '{\n  "version": "2.4.2",\n  "channel": "dev"\n}\n' > /tmp/w9-version-2.4.2.json
docker cp /tmp/w9-version-2.4.2.json websoft9-dev:/websoft9/version.json
```

连续测试时建议把本地代码与版本标记挂载进容器，避免真实回滚重建容器后代码被镜像内容覆盖：

```yaml
# /opt/websoft9/docker-compose.yml → services.product.volumes 临时追加
      - /root/workspace/websoft9/apphub/src:/websoft9/apphub/src
      - /root/workspace/websoft9/console/dist:/etc/websoft9/console
      - /tmp/w9-version-2.4.2.json:/websoft9/version.json
```

```bash
docker compose -p websoft9-dev --env-file /opt/websoft9/.env -f /opt/websoft9/docker-compose.yml up -d
docker exec websoft9-dev bash /websoft9/script/platform-service-control.sh restart apphub-api
```

不需要挂载时，也可以在每次回滚后重新部署：

```bash
docker cp console/dist/. websoft9-dev:/etc/websoft9/console/
docker cp apphub/src/services/upgrade_manager.py websoft9-dev:/websoft9/apphub/src/services/upgrade_manager.py
docker exec websoft9-dev bash /websoft9/script/platform-service-control.sh restart apphub-api
```

## 2. 模拟「升级成功」

物料是真实发布的版本，直接走正常流程：

1. 页面点「下载更新」，等待状态变为 `ready`；
2. 点「立即升级」→「开始升级」。

```bash
# 观察
tail -f /opt/websoft9/data/upgrade/logs/<run_id>.log
docker ps -a --filter name=websoft9-upgrade --format '{{.Names}} {{.Status}}'
```

预期：遮罩依次显示「准备升级环境 → 重建平台容器 → 校验服务健康」，总耗时 1–2 分钟；结束后 `state=completed`，页面提示「平台已升级到 X」并自动刷新。

## 3. 模拟「升级失败（含真实回滚）」

关键是**先真实 prepare，再破坏 staging 中的 compose**，让 `docker compose up` 真实失败。

```bash
# 1) 页面点「下载更新」，等 state=ready
RUN_ID=$(python3 -c "import json;print(json.load(open('/opt/websoft9/data/upgrade/state.json'))['run_id'])")
ls /opt/websoft9/data/upgrade/staging/$RUN_ID        # docker-compose.yml runner-upgrade.sh task.env

# 2) 追加一个引用不存在镜像的服务 → 重建必然失败
cd /opt/websoft9/data/upgrade/staging/$RUN_ID
python3 - <<'PY'
from pathlib import Path
p = Path('docker-compose.yml')
text = p.read_text()
marker = "networks:\n  websoft9:"
injection = """  broken-service:
    image: websoft9dev/websoft9:realfail-missing-tag
    restart: "no"
    networks:
      - websoft9

"""
p.write_text(text.replace(marker, injection + marker, 1))
PY

# 3) 页面点「立即升级」→ 真实失败 → 真实回滚
```

预期：`state=rolled_back`、`reason=container_recreate_failed`，页面出现失败横幅（结论 + 原因 + 查看日志 / 重试 / 获取支持）。点横幅里的「重试」会复用同一份 staging 再次真实执行，无需重新下载。

其他可复现的失败类型：

| 目标状态 | 制造方式 |
|----------|----------|
| `rolled_back`（重建失败） | 见上：staging compose 引用不存在的镜像 |
| `rolled_back`（健康检查超时） | staging compose 覆盖容器 `healthcheck` 为永不通过的命令（等待 300s 超时） |
| `apply_interrupted`（执行器提前退出） | 把 `task.env` 的 `TARGET_IMAGE_DIGEST` 改成错误的 sha256（Runner 在镜像校验处立即退出） |
| `degraded` | 升级后用 `platform-healthcheck.sh --strict` 判定部分服务未就绪（如手动停掉某个内部服务） |
| `download_failed` | 修改 `latest-version.json` 的版本指向不存在的发布物，或断网后点「下载更新」 |

`apply_interrupted` 示例：

```bash
RUN_ID=$(python3 -c "import json;print(json.load(open('/opt/websoft9/data/upgrade/state.json'))['run_id'])")
sed -i 's/^TARGET_IMAGE_DIGEST=.*/TARGET_IMAGE_DIGEST=sha256:0000000000000000000000000000000000000000000000000000000000000000/' \
  /opt/websoft9/data/upgrade/staging/$RUN_ID/task.env
# 然后在页面点「立即升级」
```

## 4. 只验证界面：直接注入状态

不真正执行升级，只让页面呈现某种结果（用于 UI 走查）：

```bash
S=/opt/websoft9/data/upgrade/state.json
now=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# 升级失败（已回滚）
printf '{"run_id":"demo-1","state":"rolled_back","target_version":"2.4.3","detail":"previous deployment restored after container_recreate_failed","reason":"container_recreate_failed","updated_at":"%s"}' "$now" > $S

# 回滚未完成
printf '{"run_id":"demo-1","state":"rollback_failed","target_version":"2.4.3","detail":"failed to recreate the previous deployment","reason":"rollback_health_check_timeout","updated_at":"%s"}' "$now" > $S

# 升级被中断
printf '{"run_id":"demo-1","state":"apply_interrupted","target_version":"2.4.3","detail":"upgrade runner: target image digest does not match task","reason":"runner_exit","exit_code":1,"updated_at":"%s"}' "$now" > $S

# 部分服务未启动
printf '{"run_id":"demo-1","state":"degraded","target_version":"2.4.3","detail":"upgraded to 2.4.3 with degraded services: nginx-proxy-manager-bootstrap","reason":"health_check_degraded","updated_at":"%s"}' "$now" > $S

# 已就绪（显示“立即升级”）
printf '{"run_id":"demo-1","state":"ready","target_version":"2.4.3","detail":"Upgrade is prepared","log_path":"/opt/websoft9/data/upgrade/logs/demo-1.log","updated_at":"%s"}' "$now" > $S
```

注入状态只影响页面呈现，没有真实日志与备份，因此「查看日志」可能提示暂无内容。角色说明：

| `reason` | 页面原因文案 |
|----------|--------------|
| `download_failed` / `download_interrupted` | 升级包下载失败，平台未做任何更改 |
| `container_recreate_failed` / `health_check_timeout` / `strict_health_check_failed` | 新版本容器未能正常启动 |
| `rollback_*` | 回滚未完成，平台可能处于中间状态 |
| `runner_exit` / `apply_interrupted` | 升级过程中断 |
| `health_check_degraded` | 升级已完成，但部分服务未正常启动 |

## 5. 观察与排查

```bash
# 当前状态（容器内直连 apphub，绕过网关鉴权）
docker exec websoft9-dev sh -c 'curl -s http://127.0.0.1:8080/api/settings/upgrade/status'

# 运行中的执行器与其输出
docker ps -a --filter name=websoft9-upgrade --format '{{.Names}} {{.Status}}'
docker logs --tail 50 websoft9-upgrade-<run_id 前 12 位>

# 升级日志（按尝试追加）
tail -n 40 /opt/websoft9/data/upgrade/logs/$RUN_ID.log
```

日志行格式：`[YYYY-MM-DD HH:MM:SS] 消息`，失败行以 `error:`、告警以 `warning:` 开头。

## 6. 测试后复位

```bash
# 1) 状态、物料、备份、日志
cp -p /tmp/real-fail-backup/state.bak /opt/websoft9/data/upgrade/state.json   # 若有基线备份
rm -rf /opt/websoft9/data/upgrade/staging/* /opt/websoft9/data/upgrade/backups/*
rm -f  /opt/websoft9/data/upgrade/logs/*.log

# 2) 执行器容器与回滚锚点镜像
docker rm -f $(docker ps -aq --filter name=websoft9-upgrade) 2>/dev/null || true
docker rmi websoft9dev/websoft9:rollback 2>/dev/null || true

# 3) 版本标记与编排文件（移除临时挂载后再重建容器）
docker cp <真实 version.json> websoft9-dev:/websoft9/version.json
diff -q /opt/websoft9/docker-compose.yml /tmp/real-fail-backup/compose.bak
grep -E '^(IMAGE_REPO|IMAGE_TAG)=' /opt/websoft9/.env     # 应为 IMAGE_TAG=<原标签>

# 4) 平台自检
docker ps --filter name=websoft9-dev --format '{{.Names}} {{.Status}}'
docker exec websoft9-dev /websoft9/script/platform-healthcheck.sh --strict
```

## 7. 注意事项

1. **真实回滚会重建平台容器**（10–20 秒中断）：用 `docker cp` 部署的代码会被镜像自带版本覆盖，连续测试请使用第 1 节的挂载方案。
2. **版本标记会被回滚重置**回镜像内的版本，需要继续测试时再降一次或用挂载。
3. **runner 会改写 `.env` 与 `docker-compose.yml`**：若测试被中断（例如手动 kill 执行器），请用 `/tmp/real-fail-backup/{env,compose}.bak` 还原并执行 `docker compose up -d`。
4. **失败现场会保留执行器容器与 `websoft9:rollback` 镜像锚点**，用于诊断与再次重试；复位时按第 6 节清理。
5. 重试使用同一 `run_id`，日志按尝试追加，因此同一文件里可能出现多次 `upgrade started`。
