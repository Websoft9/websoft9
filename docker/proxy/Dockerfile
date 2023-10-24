# modify time: 202310240910, you can modify here to trigger Docker Build action
# Dockerfile refer to:https://github.com/NginxProxyManager/nginx-proxy-manager/blob/develop/docker/Dockerfile
FROM jc21/nginx-proxy-manager:2.10.4

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="2.10.4"

RUN apt-get update && apt-get install -y curl  jq
COPY ./config/initproxy.conf /data/nginx/proxy_host/

COPY ./s6/init_user/init_user.sh /app/init_user.sh
RUN chmod +x /app/init_user.sh
CMD ["/bin/sh", "-c", "/app/init_user.sh && tail -f /dev/null"]