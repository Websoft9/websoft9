#### go code below

package main

#1 wait and get credential
#2 portainer api login 
#3 add local if not exist
```
name: local
url: /var/run/docker.sock
```


curl -X POST -H "Content-Type: application/json" -d '{"username":"admin", "Password":"'$new_password'"}' http://$portainer_ip:9000/api/users/admin/init
curl "http://$appmanage_ip:5000/AppUpdateUser?user_name=admin&password=$new_password"



#### other place

- add it to Dockerfile 
- docker compose health check

```
healthcheck:
test: ["CMD", "/healthcheck"]
interval: 1m30s
timeout: 10s
retries: 3
```
