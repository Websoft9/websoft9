# Systemd

This is the Websoft9 system service that run some proxy services on the host machine for Websoft9 to solve the problem that the API cannot handle.

- Copy credentials from one other containers to apphub container

## Test it

```
export install_path="/data/websoft9/source"
sudo cp -r $install_path/systemd/script/* "$systemd_path"
sudo cp -f "$install_path/systemd/websoft9.service" /lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable websoft9.service  
sudo systemctl start websoft9
```

## Develop it

* [systemd.exec — Execution environment configuration](https://www.freedesktop.org/software/systemd/man/systemd.exec.html)
* [systemd.unit — Unit configuration](https://www.freedesktop.org/software/systemd/man/systemd.unit.html)
* [systemd.service — Service unit configuration](https://www.freedesktop.org/software/systemd/man/systemd.service.html)