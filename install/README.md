# Websoft9 Install

This directory contains the current installation scripts and their implementation baseline.

It does not define the final lifecycle standard for the product.

For the ongoing redesign of install, upgrade, uninstall, and legacy-to-modern migration, use [docs/platform-lifecycle/platform-lifecycle-governance_cn.md](../docs/platform-lifecycle/platform-lifecycle-governance_cn.md).

## 1. Current Implementation Boundary

The current scripts reflect the repository's present implementation, not the long-term target design.

Current scope is limited to:

1. Single-container installation
2. Single-container same-model upgrade
3. Single-container uninstall
4. Standalone Docker installation helper

Current scripts do not yet define the final standard for:

1. Legacy Cockpit multi-container to current single-container one-click upgrade
2. Long-term iterative upgrade policy for future versions
3. Unified lifecycle governance across install, upgrade, uninstall, and rollback

## 2. Current Scripts

| Script | Current role |
|---|---|
| `install.sh` | Unified install and upgrade entry for same-model upgrade and legacy-to-modern migration |
| `uninstall.sh` | Current single-container uninstall implementation |
| `install_docker.sh` | Current Docker and Compose installation helper |
| `install_podman.sh` | Experimental or alternative runtime helper |

## 3. Current Usage Baseline

These commands describe the current implementation baseline only.

```bash
# Default install
curl -fsSL https://artifact.websoft9.com/websoft9/release/install.sh | bash

# Install with parameters
bash install.sh --channel release --version latest --console_port 9000

# Upgrade or migration
curl -fsSL https://artifact.websoft9.com/websoft9/release/install.sh | bash -s -- --mode upgrade

# Same-model upgrade only
bash install.sh --mode upgrade --version 3.0.0

# Uninstall and remove runtime
curl -fsSL https://artifact.websoft9.com/websoft9/release/platform/uninstall.sh | sudo bash

# Uninstall and keep data
sudo bash uninstall.sh --keep-data

# Uninstall and purge images
sudo bash uninstall.sh --purge
```

## 4. Current Known Limits

1. Upgrade detection is still implementation-oriented, not lifecycle-oriented
2. Legacy environment recognition is not yet the final design
3. Asset migration rules are not yet the final design
4. Rollback policy is not yet the final design
5. New install and modern-to-modern upgrade support non-root execution only when Docker and Docker Compose are already available and the current user can access Docker
6. Legacy Cockpit-based migration upgrade still requires root because it manipulates systemd and old host-level control surfaces

## 5. Supported OS Baseline

Supported operating systems should be documented with the install surface, not embedded in release metadata.

Current baseline:

| Distribution | Supported versions |
|---|---|
| Fedora | 40, 39 |
| Red Hat Enterprise Linux | 9 |
| CentOS | 8 |
| Oracle Linux | 9, 8, 7 |
| Rocky Linux | 9 |
| CentOS Stream | 9, 8 |
| Debian | 12, 11 |
| Ubuntu | 24.04, 22.04 |
| OpenEuler | 24 |

## 6. Planning Reference

Before changing or replacing these scripts, align with the lifecycle redesign in [docs/platform-lifecycle/platform-lifecycle-governance_cn.md](../docs/platform-lifecycle/platform-lifecycle-governance_cn.md).
