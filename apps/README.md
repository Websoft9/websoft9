# APPS

## Install App

```
ansible-playbook -i hosts application.yml -e appname=wordpress
ansible-playbook -i hosts application.yml -c local -e appname=wordpress
```

## DevOps

You can add new app role from template just one command
```
echo "appname" > add
```
