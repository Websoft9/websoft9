# modify time: 202504300834, you can modify here to trigger Docker Build action
# from Dockerfile: https://github.com/NginxProxyManager/nginx-proxy-manager/blob/develop/docker/Dockerfile
# from image: https://hub.docker.com/r/jc21/nginx-proxy-manager

FROM jc21/nginx-proxy-manager:2.11.3

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="2.11.3"

COPY README.md /data/nginx/README.md
RUN mkdir /data/nginx/custom
RUN mkdir -p /etc/websoft9
COPY ./config/http.conf /data/nginx/custom/http.conf
COPY ./config/landing/ /etc/websoft9/landing
COPY ./config/initproxy.conf /etc/websoft9/initproxy.conf
COPY ./init_nginx.sh /app/init_nginx.sh
RUN chmod +x /app/init_nginx.sh

# 修复nginx启动加载ip_ranges失败的问题
RUN export add_ip_data="const ipDataFile={[CLOUDFRONT_URL]:'ip-ranges.json',[CLOUDFARE_V4_URL]:'ips-v4',[CLOUDFARE_V6_URL]:'ips-v6'}[url];logger.info(ipDataFile);if(ipDataFile){return fs.readFile(__dirname+'/../lib/ipData/'+ipDataFile,'utf8',(error,data)=>{if(error){logger.error('fetch '+ipDataFile+' error');reject(error);return}logger.info('fetch '+ipDataFile+' success');resolve(data)})}" && \
    sed -i "s#url);#&${add_ip_data}#g" /app/internal/ip_ranges.js && \
    mkdir -p /app/lib/ipData && cd /app/lib/ipData && \
    curl -O https://ip-ranges.amazonaws.com/ip-ranges.json && \
    curl -O https://www.cloudflare.com/ips-v4 && \
    curl -O https://www.cloudflare.com/ips-v6


# 为所有nginx的代理统一加入websockets支持
RUN proxy_line=("proxy_set_header Upgrade \$http_upgrade;" "proxy_set_header Connection upgrade;") && \
    proxy_path="/etc/nginx/conf.d/include/proxy.conf" && \
    length=${#proxy_line[@]} && \
    for ((i=0; i<$length; i++)); do \
    if ! grep -Fxq "${proxy_line[$i]}" $proxy_path; then \
    echo "${proxy_line[$i]}" >> $proxy_path; \
    fi; \
    done

ENTRYPOINT [ "/app/init_nginx.sh" ]
