# Changelog

All notable changes to Websoft9 are documented in this file.

The format is based on Keep a Changelog, and this project aims to follow Semantic Versioning.

## [3.0.0] - 2026-06-15

### Fixed
- Updated the fallback `daemon.json` Docker registry mirrors to improve image pull success rate.

## [0.8.29] - 2023-11-04

### Changed
- Updated Gitea, My Apps, and App Store.
- Updated AppHub domains.
- Updated the AppHub docs Nginx config.

## [0.8.28] - 2023-11-01

### Changed
- Improved the Dockerfile to reduce image size.
- Hid Websoft9 containers from the default surface.

### Fixed
- Fixed `update_zip.sh` behavior.

## [0.8.27] - 2023-10-31

### Added
- Introduced the new Websoft9 init flow.

## [0.8.26] - 2023-09-27

### Changed
- Renamed appmanage to AppHub.

## [0.8.20] - 2023-08-23

### Fixed
- Fixed the appmanage config files error.

## [0.8.19] - 2023-08-23

### Added
- Added the new App Store preview push flow.

### Fixed
- Fixed known bugs across the current release line.

## [0.8.18] - 2023-08-17

### Fixed
- Fixed the appmanage volumes behavior.

## [0.8.15] - 2023-08-17

### Fixed
- Fixed the service menu bug.

## [0.8.14] - 2023-08-16

### Fixed
- Fixed the My Apps plugin refresh bug.

## [0.8.13] - 2023-08-15

### Changed
- Updated plugins.

### Fixed
- Fixed the session data persistence bug.

## [0.8.12] - 2023-08-12

### Changed
- Changed the navigator plugin install flow.
- Updated plugins.

## [0.8.11] - 2023-08-03

### Added
- Added initial apps: NocoBase and Affine.

### Changed
- Optimized interface calls.
- Moved the library artifacts directory to `websoft9/plugin/library`.

## [0.8.10] - 2023-08-01

### Changed
- Improved `update.sh`.
- Added docs to the published artifacts.
- Improved the server hostname handling.

## [0.8.8] - 2023-07-27

### Fixed
- Fixed the update search API bug.

## [0.8.5] - 2023-07-26

### Added
- Added documentation.

## [0.8.4] - 2023-07-26

### Added
- Added the App Store search API.

## [0.8.2] - 2023-07-24

### Added
- Added installation from published artifacts.
- Added an extra `version.json` into the published artifacts.

## [0.7.2] - 2023-06-25

### Changed
- 升级了 appmanage 自动更新接口。

## [0.7.1] - 2023-06-21

### Changed
- 将自动更新时间频率调整为一天。

### Fixed
- 修复了 appmanage 的 `version` 文件意外删除问题。
- 修复了更新脚本在 `version` 文件不存在时的错误。

## [0.7.0] - 2023-06-20

### Added
- 新增 App Store 更新功能。
- 新增 settings（设置）功能。

### Changed
- 优化了 My Apps 功能。

## [0.6.0] - 2023-06-17

### Added
- 新增自动更新软件商店功能。

### Changed
- 上架 WordPress。
- 下架 Moodle。
- 调整 Redmine。
- 升级 DiscuzQ 和 Zabbix。

## [0.4.0] - 2023-06-15

### Changed
- 下线 ownCloud 测试。

## [0.3.0] - 2023-06-06

### Changed
- 将 appmanage Docker 镜像更新到 `0.3.0`。

### Fixed
- 修复了 PrestaShop 无法访问的问题。
- 修复了 Odoo 无法安装的问题。

## [0.2.0] - 2023-06-03

### Changed
- 将 appmanage Docker 镜像更新到 `0.2.0`。

### Fixed
- 修复了 Portainer 插件自动登录问题。
- 修复了 My Apps 插件首次使用时获取容器的问题。

## [0.1.0] - 2023-05-26

### Added
- 发布 Stackhub 预览版并提供基础能力。
