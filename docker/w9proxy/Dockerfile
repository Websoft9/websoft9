FROM jc21/nginx-proxy-manager:2.10.3

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="2.10.3"

RUN apk add --no-cache curl
COPY user.sh /user.sh
COPY initproxy.conf /data/nginx/proxy_host
RUN chmod +x /user.sh
CMD ["/user.sh"]