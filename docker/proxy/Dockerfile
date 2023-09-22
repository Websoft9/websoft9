FROM jc21/nginx-proxy-manager:2.10.4

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="2.10.4"

RUN apt-get update && apt-get install -y curl  jq
COPY ./config/initproxy.conf /data/nginx/proxy_host/
COPY ./s6/user /etc/s6-overlay/s6-rc.d/user

RUN chmod -R 755 /etc/s6-overlay/s6-rc.d/user