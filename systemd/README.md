# Systemd

This is the Websoft9 system service that run some proxy services on the host machine for Websoft9 to solve the problem that the API cannot handle.

- Copy credentials from one other containers to apphub container

## Test it

```
export install_path="/data/websoft9/source"
chmod +x $install_path/systemd/send_credentials.sh
cp $install_path/systemd/websoft9.service /lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable websoft9.service  
sudo systemctl start websoft9
```