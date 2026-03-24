# Story 3.1: Cockpit Menu Customization

Status: ready-for-dev

## Story

As a Websoft9 system administrator,
I want to customize the Cockpit menu interface,
so that only Websoft9-relevant functionality is displayed, providing a cleaner and more professional user experience.

## Acceptance Criteria

1. **Menu Grouping & Ordering**: Adjust the structure and display order of Cockpit's top menu and sidebar menu items
2. **Language Simplification**: Remove unnecessary language options, keeping only essential languages (English, Chinese)
3. **Help Menu Customization**: Point the top-right help menu to Websoft9 documentation instead of Cockpit default docs
4. **Menu Item Hiding**: Hide irrelevant Cockpit default menu items (e.g., machines, kdump, selinux)
5. **Configuration Persistence**: All menu configurations persist via override.json files and survive container restarts

## Tasks / Subtasks

- [ ] Task 1: Analyze and optimize menu grouping and ordering (AC: #1)
  - [ ] Review existing `menu_override/*.override.json` files
  - [ ] Determine which menu items Websoft9 needs to keep and their priority order
  - [ ] Adjust `order` fields in `systemd.override.json`
  - [ ] Configure tool menu grouping structure

- [ ] Task 2: Simplify language support (AC: #2)
  - [ ] Edit `locales` section in `shell.override.json`
  - [ ] Keep only English (default) and Chinese (zh-cn)
  - [ ] Remove 20+ unnecessary language options

- [ ] Task 3: Customize help documentation links (AC: #3)
  - [ ] Edit `shell.override.json` file
  - [ ] Locate the `docs` array in the JSON structure
  - [ ] Update the documentation link to point to Websoft9 official support docs
  - [ ] Example configuration:
    ```json
    "docs": [
      {
        "label": "Documentation",
        "url": "https://support.websoft9.com/en/docs/"
      }
    ]
    ```
  - [ ] Verify link displays correctly in top-right help menu (click "?" icon)

- [ ] Task 4: Hide irrelevant menu items (AC: #4)
  - [ ] Configure override.json files, set `"menu": null` to hide unnecessary modules
  - [ ] Confirm hidden: machines, kdump, selinux, session-recording, packagekit, sosreport, subscriptions, updates
  - [ ] Keep essential modules: systemd (services, logs), users, storaged, networkmanager, apps

- [ ] Task 5: Build and test configuration (AC: #5)
  - [ ] Update Dockerfile to ensure override files copy correctly to `/etc/cockpit/`
  - [ ] Rebuild Cockpit image
  - [ ] Start container and test menu display
  - [ ] Verify configuration persists after container restart

## Dev Notes

### Architecture Patterns and Constraints

**Cockpit Override Mechanism**:
- Cockpit uses `/etc/cockpit/*.override.json` files to override default menu configurations
- Override file format follows Cockpit manifest specification
- **Sidebar Menu Structure**: Divided into two groups
  - `"menu"` field → **System** group (e.g., Overview, Terminal)
  - `"tools"` field → **Tools** group (e.g., Logs, Accounts)
- Setting `"menu": null` hides the module's System menu item
- Setting `"tools": null` hides the module's Tools menu item
- Setting `"locales": { "language-code": null }` removes language options
- `docs` array customizes help links
- `order` field controls menu item display order within each group (lower values appear first)

**Docker Image Integration**:
- Override files embedded in image via Dockerfile `COPY` instruction
- File path: `build/menu_override/*.override.json` → `/etc/cockpit/`
- Configuration baked into image at build time, takes effect at runtime

**Version Compatibility**:
- Currently using Cockpit 297 (Debian Bullseye default version)
- Override functionality available in Cockpit 297
- Future Cockpit version upgrades may affect override behavior

### Project Structure Notes

**Related File Paths**:
```
cockpit/menu_override/           # Source configuration directory
├── shell.override.json          # Top menu and language config
├── systemd.override.json        # Services and Logs menu
├── users.override.json          # User management menu
├── networkmanager.override.json # Network management
├── storaged.override.json       # Storage management
├── apps.override.json           # Application management
├── machines.override.json       # Virtual machine management (hide)
├── kdump.override.json          # Kernel crash (hide)
├── selinux.override.json        # SELinux (hide)
├── session-recording.override.json  # Session recording (hide)
├── packagekit.override.json     # Package management (hide)
├── sosreport.override.json      # SOS report (hide)
├── subscriptions.override.json  # Subscription management (hide)
└── updates.override.json        # Update management (hide)

build/Dockerfile        # Cockpit image build file
build/menu_override/    # Another copy of override files (sync with cockpit/menu_override/)
```

**Important Notes**:
- `cockpit/menu_override/` and `build/menu_override/` must stay in sync
- Dockerfile uses `build/menu_override/` path
- Image rebuild required for changes to take effect

### Technical Specifications

**Help Menu Customization**:
The help menu (top-right "?" icon) is controlled by the `docs` array in `shell.override.json`:
```json
{
  "docs": [
    {
      "label": "Documentation",        // Menu item text
      "url": "https://support.websoft9.com/en/docs/"  // Target URL
    }
  ]
}
```
- Multiple help links can be added by including more objects in the array
- The "?" icon appears in the top-right corner of Cockpit interface
- Clicking opens a dropdown menu with the configured documentation links

**Menu Override JSON Structure Examples**:

```json
// Cockpit Sidebar Structure:
// - System group: Controlled by "menu" field in each module's override.json
// - Tools group: Controlled by "tools" field in each module's override.json

// shell.override.json - Top menu configuration
{
  "locales": {
    "zh-cn": {},      // Keep Chinese
    "es-es": null,    // Remove Spanish
    "fr-fr": null     // Remove French
  },
  "docs": [
    {
      "label": "Documentation",
      "url": "https://support.websoft9.com/en/docs/"
    }
  ]
}

// systemd.override.json - System and Tools menu configuration
{
  "tools": {                    // Tools group configuration
    "services": null,           // Hide Services from Tools group
    "logs": {
      "label": "Logs",
      "order": 20               // Display order in Tools group
    }
  },
  "menu": {                     // System group configuration
    "services": null,           // Hide Services from System group
    "logs": null,               // Hide Logs from System group
    "index": {
      "label": "Overview",
      "order": -2               // Display order in System group (negative = top)
    },
    "terminal": {
      "label": "Terminal"
    }
  }
}

// machines.override.json - Hide virtual machines menu
{
  "menu": null  // null means hide this menu item
}
```

**Test Commands**:

```bash
# Build image
cd build
docker build -t websoft9dev/cockpit-base:297-custom .

# Test run
docker run -d --name test-cockpit \
  --privileged \
  -v /run/systemd:/run/systemd:ro \
  -p 9091:9090 \
  websoft9dev/cockpit-base:297-custom

# Browser test
# http://localhost:9091
# Username: websoft9 / Password: websoft9

# Cleanup
docker stop test-cockpit && docker rm test-cockpit
```

### References

- [Source: cockpit/README.md#Override the default menus] - 说明了 menu_override 的用途和 shell.override.json 的作用
- [Source: build/README.md#配置文件] - Dockerfile 中如何集成 override 配置
- [Source: build/Dockerfile#L90] - `COPY build/menu_override/*.override.json /etc/cockpit/` 复制配置的指令
- [Source: build/menu_override/shell.override.json] - 帮助菜单和多语言配置示例
- [Source: cockpit/test/menu_override.sh] - 测试脚本展示了 override 文件的部署路径
- [Cockpit Manifest Documentation](https://cockpit-project.org/guide/latest/packages.html) - Cockpit 官方文档关于 manifest 和 override 机制
- [Cockpit Menu Override Guide](https://cockpit-project.org/guide/latest/cockpit-manifest.html) - Cockpit 菜单覆盖配置指南

### Design Decisions

**Why Menu Customization Is Needed**:
1. **Simplify Interface**: Cockpit includes many generic Linux management features that are redundant for Websoft9 users
2. **Brand Consistency**: Help documentation should point to Websoft9 docs, not Cockpit official docs
3. **I18n Simplification**: Websoft9 primarily serves English and Chinese users, 20+ languages not needed
4. **User Experience**: Streamlined menu structure helps users find needed features faster

**Core Modules to Keep**:
- **systemd**: Service management and log viewing are core functions
- **users**: User and account management
- **storaged**: Disk and storage management
- **networkmanager**: Network configuration
- **apps**: Application integration (if Websoft9 has Cockpit plugins)

**Modules to Hide** (not relevant to Websoft9):
- machines (virtual machine management)
- kdump (kernel crash dumps)
- selinux (SELinux management)
- session-recording (session recording)
- packagekit (system package management)
- sosreport (diagnostic reports)
- subscriptions (subscription management)
- updates (system updates)

### Potential Issues and Solutions

**Issue 1**: How to keep two override file directories in sync?
- **Solution**: Consider adding sync task in Makefile, or keep only one source and reference directly in Dockerfile

**Issue 2**: Cockpit version upgrades may affect override behavior
- **Solution**: Thoroughly test before upgrades, monitor Cockpit changelog for manifest changes

**Issue 3**: Some users may need hidden features
- **Solution**: Document that advanced users can restore features via custom image builds

## Dev Agent Record

### Agent Model Used

_To be filled by developer_

### Debug Log References

_To be recorded during implementation_

### Completion Notes List

_To be summarized after completion_

### File List

_To be listed by developer: files modified_
