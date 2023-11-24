# User Guide

## FAQ

#### user can not sudo?

```
# add user to sudo/admin group (select one command)
usermod -aG wheel username
usermod -aG sudo username

# sudo not need to input password

```

#### Can not login when I reinstall my Instance?

Need to clear all cookie at you browser

#### How to update Media and library?

--channel dev | release

```
docker exec -it websoft9-apphub bash
bash /websoft9/script/update_zip.sh --channel dev --package_name "media-latest.zip" --sync_to "/websoft9/media"
bash /websoft9/script/update_zip.sh --channel dev --package_name "library-latest.zip" --sync_to "/websoft9/library"
```
