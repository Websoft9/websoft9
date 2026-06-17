#!/bin/bash
# install.sh — Websoft9 生命周期统一入口（§9）
# 职责：参数解析、模式分发、统一日志入口、统一退出码。
# 不直接实现迁移细节、卷复制细节、环境识别细节（下沉到 lib/*.sh）。
#
# 命令面（§9.2）：
#   install    面向 empty，全新安装现代运行时
#   upgrade    自动分流 modern(迭代升级) / legacy(跨代迁移)
#   uninstall  按环境分流卸载（modern / legacy）
#   detect     输出环境识别结果与关键观察信号
#   backup     显式生成备份点（modern / legacy）
#
# 参数面（§9.3）：
#   通用:   --channel --version --path --proxy
#   入口:   --console-port
#   安全:   --mode --force --dry-run --yes --keep-data

set -o pipefail

# 定位脚本目录与 lib
W9_SCRIPT="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
W9_ROOT_DIR="$(dirname "$W9_SCRIPT")"
W9_LIB_DIR="${W9_ROOT_DIR}/lib"
export W9_LIB_DIR

# 加载库
# 说明：以下 source 块在发布构建时（install/build-bundle.sh）会被内联，
#       生成自包含单文件 install.sh；两处标记之间的内容会被整体替换。
# >>> WEBSOFT9_LIB_SOURCING >>>
# shellcheck source=lib/common.sh
. "${W9_LIB_DIR}/common.sh"
. "${W9_LIB_DIR}/detect.sh"
. "${W9_LIB_DIR}/backup.sh"
. "${W9_LIB_DIR}/validate.sh"
. "${W9_LIB_DIR}/install-fresh.sh"
. "${W9_LIB_DIR}/upgrade-modern.sh"
. "${W9_LIB_DIR}/upgrade-legacy.sh"
. "${W9_LIB_DIR}/uninstall.sh"
# <<< WEBSOFT9_LIB_SOURCING <<<

usage() {
  cat <<EOF
Websoft9 生命周期工具

用法:
  install.sh <command> [options]

命令:
  install      全新安装（仅 empty 环境）
  upgrade      升级（modern 自动迭代升级 / legacy 自动跨代迁移）
  uninstall    卸载（modern / legacy 分流）
  detect       输出环境识别结果与关键信号
  backup       显式生成备份点

通用参数:
  --channel <release|rc|dev>   发布通道（默认 release）
  --version <tag>              镜像标签（IMAGE_TAG，默认 latest）
  --path <dir>                 安装目录（默认 ${DEFAULT_INSTALL_PATH}）
  --proxy <url>                下载代理（预留）

入口参数:
  --console-port <port>        控制台入口端口（默认 ${DEFAULT_CONSOLE_PORT}）

安全参数:
  --mode <stop|standard|purge> 卸载模式（默认 standard）
  --force                      放宽非破坏性检查（不绕过 mixed 停止规则）
  --dry-run                    仅前置检查与计划，不做破坏性操作
  --yes                        对破坏性操作进行确认
  --keep-data <true|false>     卸载/失败清理是否保留数据（默认 true）
  --remove-legacy-controlplane 卸载时显式清理旧 Cockpit/systemd 遗留

镜像参数:
  --image-repo <repo>          镜像仓库（IMAGE_REPO，默认 ${DEFAULT_IMAGE_REPO}）
  --network <name>             网络名（NETWORK_NAME，默认 ${DEFAULT_NETWORK_NAME}）
EOF
}

# ---- 参数默认值 ----
CMD=""
OPT_CHANNEL="release"
OPT_VERSION="$DEFAULT_IMAGE_TAG"
OPT_PATH="$DEFAULT_INSTALL_PATH"
OPT_PROXY=""
OPT_CONSOLE_PORT="$DEFAULT_CONSOLE_PORT"
OPT_MODE="standard"
OPT_FORCE="0"
OPT_YES="0"
OPT_KEEP_DATA="1"
OPT_REMOVE_CONTROLPLANE="0"
OPT_IMAGE_REPO="$DEFAULT_IMAGE_REPO"
OPT_NETWORK="$DEFAULT_NETWORK_NAME"
OPT_VOLUMES_ROOT="$DEFAULT_DOCKER_VOLUMES_ROOT"

# 第一个非选项参数作为命令
if [ $# -eq 0 ]; then usage; exit "$EXIT_USAGE"; fi
CMD="$1"; shift

# ---- 解析选项 ----
while [ $# -gt 0 ]; do
  case "$1" in
    --channel)        OPT_CHANNEL="$2"; shift 2 ;;
    --version)        OPT_VERSION="$2"; shift 2 ;;
    --path)           OPT_PATH="$2"; shift 2 ;;
    --proxy)          OPT_PROXY="$2"; shift 2 ;;
    --console-port)   OPT_CONSOLE_PORT="$2"; shift 2 ;;
    --mode)           OPT_MODE="$2"; shift 2 ;;
    --force)          OPT_FORCE="1"; shift ;;
    --dry-run)        W9_DRY_RUN="1"; export W9_DRY_RUN; shift ;;
    --yes)            OPT_YES="1"; shift ;;
    --keep-data)
      case "$2" in
        true|TRUE|1)  OPT_KEEP_DATA="1" ;;
        false|FALSE|0) OPT_KEEP_DATA="0" ;;
        *) die "$EXIT_USAGE" "--keep-data 仅接受 true/false" ;;
      esac
      shift 2 ;;
    --remove-legacy-controlplane) OPT_REMOVE_CONTROLPLANE="1"; shift ;;
    --image-repo)     OPT_IMAGE_REPO="$2"; shift 2 ;;
    --network)        OPT_NETWORK="$2"; shift 2 ;;
    -h|--help)        usage; exit "$EXIT_OK" ;;
    *) die "$EXIT_USAGE" "未知参数: $1" ;;
  esac
done

# 通道与版本：dev/rc 通道在未显式指定 version 时回落到 latest
[ -z "$OPT_VERSION" ] && OPT_VERSION="$DEFAULT_IMAGE_TAG"

# 导出通道与制品分发根，供物料/依赖下载（单文件 install.sh 真实安装场景）
# 制品分发根可用环境变量 W9_ARTIFACT_BASE 覆盖（默认 https://artifact.websoft9.com/websoft9）。
export W9_CHANNEL="$OPT_CHANNEL"

# ---- 命令分发 ----
case "$CMD" in
  detect)
    log_info "环境识别信号："
    detect_print_signals
    env_kind="$(detect_environment)"
    log_info "环境识别结果: ${env_kind}"
    echo "$env_kind"
    ;;

  install)
    env_kind="$(detect_environment)"
    log_info "环境识别结果: ${env_kind}"
    case "$env_kind" in
      empty)
        run_install "$OPT_CONSOLE_PORT" "$OPT_PATH" "$OPT_IMAGE_REPO" "$OPT_VERSION" "$OPT_NETWORK" "$OPT_VOLUMES_ROOT"
        ;;
      modern)
        die "$EXIT_ENV_GUARD" "检测到 modern 环境，请使用 upgrade 而非 install" ;;
      legacy)
        die "$EXIT_ENV_GUARD" "检测到 legacy 环境，请使用 upgrade 进行跨代迁移" ;;
      *)
        die "$EXIT_ENV_GUARD" "环境为 ${env_kind}，install 仅面向 empty" ;;
    esac
    ;;

  upgrade)
    env_kind="$(detect_environment)"
    log_info "环境识别结果: ${env_kind}"
    case "$env_kind" in
      modern)
        run_upgrade_modern "$OPT_CONSOLE_PORT" "$OPT_PATH" "$OPT_IMAGE_REPO" "$OPT_VERSION" "$OPT_NETWORK" "$OPT_VOLUMES_ROOT"
        ;;
      legacy)
        run_upgrade_legacy "$OPT_CONSOLE_PORT" "$OPT_PATH" "$OPT_IMAGE_REPO" "$OPT_VERSION" "$OPT_NETWORK" "$OPT_VOLUMES_ROOT"
        ;;
      empty)
        die "$EXIT_ENV_GUARD" "环境为 empty，请先使用 install" ;;
      mixed|*)
        die "$EXIT_ENV_GUARD" "环境为 ${env_kind}，不自动升级，请先人工治理（见 §12）" ;;
    esac
    ;;

  uninstall)
    env_kind="$(detect_environment)"
    log_info "环境识别结果: ${env_kind}"
    run_uninstall "$env_kind" "$OPT_MODE" "$OPT_PATH" "$OPT_KEEP_DATA" "$OPT_YES" "$OPT_REMOVE_CONTROLPLANE"
    ;;

  backup)
    env_kind="$(detect_environment)"
    log_info "环境识别结果: ${env_kind}"
    case "$env_kind" in
      modern)
        bdir="$(backup_new_dir modern)"
        backup_modern_pre_upgrade "$OPT_PATH" "$bdir"
        log_info "现代备份点: $bdir"
        ;;
      legacy)
        bdir="$(backup_new_dir legacy)"
        backup_legacy_pre_migration "$bdir"
        log_info "旧版备份点: $bdir"
        ;;
      *)
        die "$EXIT_ENV_GUARD" "环境为 ${env_kind}，无可备份的标准运行时" ;;
    esac
    ;;

  -h|--help|help)
    usage ;;

  *)
    usage
    die "$EXIT_USAGE" "未知命令: $CMD" ;;
esac

exit "$EXIT_OK"
