# modify time: 202504301144, you can modify here to trigger Docker Build action
# from Dockerfile: https://github.com/NginxProxyManager/nginx-proxy-manager/blob/develop/docker/Dockerfile
# from image: https://hub.docker.com/r/jc21/nginx-proxy-manager

# Build ModSecurity module and Nginx dynamic module
FROM jc21/nginx-proxy-manager:2.12.6 AS builder

WORKDIR /tmp

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget git g++ apt-utils autoconf automake build-essential \
    libcurl4-openssl-dev libgeoip1 libgeoip-dev liblmdb-dev libpcre2-dev \
    libtool libxml2-dev libyajl-dev pkgconf zlib1g-dev

# Build ModSecurity from source code
WORKDIR /tmp/modsecurity
RUN git clone --depth 1 -b v3/master --single-branch https://github.com/SpiderLabs/ModSecurity .
RUN git submodule init && git submodule update
RUN ./build.sh
RUN ./configure --with-pcre2 --prefix=/usr/local
RUN make -j$(nproc)
RUN make install

# Get OpenResty version
RUN OPENRESTY_VERSION=$(nginx -v 2>&1 | grep -oP 'openresty/\K[0-9.]+')
WORKDIR /tmp
# Clone ModSecurity-nginx source code and compile Nginx dynamic module
RUN git clone --depth 1 https://github.com/SpiderLabs/ModSecurity-nginx.git && \
    wget https://openresty.org/download/openresty-${OPENRESTY_VERSION}.tar.gz && \
    tar -zxvf openresty-${OPENRESTY_VERSION}.tar.gz && \
    cd /tmp/openresty-${OPENRESTY_VERSION}/bundle && \
    NGINX_DIR=$(find . -type d -name "nginx-*" | head -1) && \
    cd "$NGINX_DIR" && \
    ./configure --with-compat --add-dynamic-module=/tmp/ModSecurity-nginx && \
    make modules && \
    mkdir -p /output && \
    cp objs/ngx_http_modsecurity_module.so /output/ngx_http_modsecurity_module.so


# Build final image
FROM jc21/nginx-proxy-manager:2.12.6

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="2.12.6"

COPY README.md /data/nginx/README.md
RUN mkdir /data/nginx/custom
RUN mkdir -p /etc/websoft9
COPY ./config/http.conf /data/nginx/custom/http.conf
COPY ./config/landing/ /etc/websoft9/landing
COPY ./config/initproxy.conf /etc/websoft9/initproxy.conf
COPY ./init_nginx.sh /app/init_nginx.sh
RUN chmod +x /app/init_nginx.sh


# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libcurl4 libgeoip1 libxml2 libpcre2-8-0 libyajl2 zlib1g && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy ModSecurity library files
COPY --from=builder /usr/local/lib/libmodsecurity.so* /usr/local/lib/
RUN ldconfig
# Copy Nginx dynamic module
COPY --from=builder /output/ngx_http_modsecurity_module.so /etc/nginx/modules/ngx_http_modsecurity_module.so


# Modify Nginx configuration to load ModSecurity module
RUN mkdir -p /etc/modsec/rules
RUN mkdir -p /etc/modsec/log
RUN sed -i '1iload_module /etc/nginx/modules/ngx_http_modsecurity_module.so;' /etc/nginx/nginx.conf && \
    sed -i '/http {/a \    include /etc/modsec/nginx_modsecurity.conf;' /etc/nginx/nginx.conf
RUN touch /etc/modsec/nginx_modsecurity.conf
RUN echo $'# Enable ModSecurity\nmodsecurity on;\nmodsecurity_rules_file /etc/modsec/modsec_includes.conf;' > /etc/modsec/nginx_modsecurity.conf

# Install rule sets
COPY ./config/unicode.mapping /etc/modsec/unicode.mapping
COPY ./config/modsec_includes.conf /etc/modsec/modsec_includes.conf
COPY ./config/crs-setup.conf /etc/modsec/crs-setup.conf
COPY ./config/modsecurity.conf /etc/modsec/modsecurity.conf
COPY ./config/rules/* /etc/modsec/rules/

VOLUME [ "/etc/modsec" ]

# Fix nginx startup issue with ip_ranges loading failure
RUN export add_ip_data="const ipDataFile={[CLOUDFRONT_URL]:'ip-ranges.json',[CLOUDFARE_V4_URL]:'ips-v4',[CLOUDFARE_V6_URL]:'ips-v6'}[url];logger.info(ipDataFile);if(ipDataFile){return fs.readFile(__dirname+'/../lib/ipData/'+ipDataFile,'utf8',(error,data)=>{if(error){logger.error('fetch '+ipDataFile+' error');reject(error);return}logger.info('fetch '+ipDataFile+' success');resolve(data)})}" && \
    sed -i "s#url);#&${add_ip_data}#g" /app/internal/ip_ranges.js && \
    mkdir -p /app/lib/ipData && cd /app/lib/ipData && \
    curl -O https://ip-ranges.amazonaws.com/ip-ranges.json && \
    curl -O https://www.cloudflare.com/ips-v4 && \
    curl -O https://www.cloudflare.com/ips-v6

# Add unified websockets support for all nginx proxies
RUN proxy_line=("proxy_set_header Upgrade \$http_upgrade;" "proxy_set_header Connection upgrade;") && \
    proxy_path="/etc/nginx/conf.d/include/proxy.conf" && \
    length=${#proxy_line[@]} && \
    for ((i=0; i<$length; i++)); do \
    if ! grep -Fxq "${proxy_line[$i]}" $proxy_path; then \
    echo "${proxy_line[$i]}" >> $proxy_path; \
    fi; \
    done

WORKDIR /app
ENTRYPOINT ["/app/init_nginx.sh"]