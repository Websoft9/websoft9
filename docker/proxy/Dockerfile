FROM jc21/nginx-proxy-manager:2.10.4

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="2.10.4"

RUN apt-get update && apt-get install -y curl supervisor jq
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY config/user.sh /user.sh
COPY config/entrypoint.sh /entrypoint.sh
COPY ./config/initproxy.conf /data/nginx/proxy_host/
RUN chmod +x /user.sh /entrypoint.sh
ENTRYPOINT ["/init"]