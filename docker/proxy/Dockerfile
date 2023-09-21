FROM jc21/nginx-proxy-manager:2.10.4

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="2.10.4"

RUN apt-get update && apt-get install -y curl
COPY user.sh /user.sh
COPY initproxy.conf /data/nginx/proxy_host
RUN chmod +x /user.sh
#  There is ENTRYPOINT in jc21/nginx-proxy-manager, no CMD
CMD ["/user.sh"]