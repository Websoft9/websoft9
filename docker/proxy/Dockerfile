# modify time: 20240118, you can modify here to trigger Docker Build action
# from Dockerfile: https://github.com/NginxProxyManager/nginx-proxy-manager/blob/develop/docker/Dockerfile
# from image: https://hub.docker.com/r/jc21/nginx-proxy-manager

FROM jc21/nginx-proxy-manager:2.10.4

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="2.10.4"

RUN apt-get update && apt-get install --no-install-recommends -y curl jq && rm -rf /var/lib/apt/lists/*
COPY ./config/initproxy.conf /etc/
COPY ./s6/w9init/setuser.sh /app/setuser.sh
COPY ./s6/w9init/migration.sh /app/migration.sh
COPY ./s6/w9init/setproxy.sh /app/setproxy.sh
RUN chmod +x /app/setuser.sh /app/migration.sh /app/setproxy.sh

RUN export add_ip_data="const ipDataFile={[CLOUDFRONT_URL]:'ip-ranges.json',[CLOUDFARE_V4_URL]:'ips-v4',[CLOUDFARE_V6_URL]:'ips-v6'}[url];logger.info(ipDataFile);if(ipDataFile){return fs.readFile(__dirname+'/../lib/ipData/'+ipDataFile,'utf8',(error,data)=>{if(error){logger.error('fetch '+ipDataFile+' error');reject(error);return}logger.info('fetch '+ipDataFile+' success');resolve(data)})}" && \
    sed -i "s#url);#&${add_ip_data}#g" /app/internal/ip_ranges.js && \
    mkdir -p /app/lib/ipData && cd /app/lib/ipData && \
    curl -O https://ip-ranges.amazonaws.com/ip-ranges.json && \
    curl -O https://www.cloudflare.com/ips-v4 && \
    curl -O https://www.cloudflare.com/ips-v6

CMD ["/bin/sh", "-c", "/app/migration.sh && /app/setuser.sh && /app/setproxy.sh && tail -f /dev/null"]
