# modify time: 202310261640, you can modify here to trigger Docker Build action
# from Dockerfile: https://github.com/NginxProxyManager/nginx-proxy-manager/blob/develop/docker/Dockerfile
# from image: https://hub.docker.com/r/jc21/nginx-proxy-manager

FROM jc21/nginx-proxy-manager:2.10.4

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="2.10.4"

RUN apt-get update && apt-get install --no-install-recommends -y curl jq && rm -rf /var/lib/apt/lists/*
COPY ./config/initproxy.conf /etc/

COPY ./s6/w9init/setuser.sh /app/setuser.sh
COPY ./s6/w9init/migration.sh /app/migration.sh

RUN chmod +x /app/setuser.sh /app/migration.sh

CMD ["/bin/sh", "-c", "/app/migration.sh && /app/setuser.sh && tail -f /dev/null"]