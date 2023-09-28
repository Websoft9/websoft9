# Cockpit

Cockpit is used for backend service gatway, we have not modify Cockpit core, just improve the installation and modify config for Websoft9

## Install

```
# default install
wget https://websoft9.github.io/websoft9/install/install_cockpit.sh && bash install_cockpit.sh

# define Cockpit port and install
wget https://websoft9.github.io/websoft9/install/install_cockpit.sh && bash install_cockpit.sh --port 9099
```

## Development

Developer should improve these codes:  

- Install and Upgrade Cockpit: */install/install_cockpit.sh*  

- Override the default menus: */cockpit/menu_override*  
  > shell.override.json is used for Top menu of Cockpit。Override function until Cockpit 297

- Cockipt configuration file: */cockpit/cockpit.conf*  
