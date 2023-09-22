# Cockpit

Cockpit is used for backend service gatway, we have not modify Cockpit core, just improve the installation and modify config for Websoft9

## Install

```
wget https://websoft9.github.io/websoft9/install/install_cockpit.sh && bash install_cockpit.sh
```

## Development

Developer should improve these codes:  

- Install and Upgrade Cockpit: */install/install_cockpit.sh*  
- Override the default menus: */cockpit/menu_override*  
- Cockipt configuration file: */cockpit/cockpit.conf*  

> shell.override.json is used for Top menu of Cockpit