git clone --depth=1 https://github.com/Websoft9/websoft9.git
rm -rf /etc/cockpit/*.override.json
cp -r websoft9/cockpit/menu_override/* /etc/cockpit