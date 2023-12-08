# modify time: 202312081709, you can modify here to trigger Docker Build action

FROM python:3.10-slim-bullseye
LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="0.0.6"

WORKDIR  /websoft9

ENV websoft9_repo="https://github.com/Websoft9/websoft9"
ENV websoft9_artifact="https://w9artifact.blob.core.windows.net/release/websoft9"
ENV library_repo="https://github.com/Websoft9/docker-library"
ENV source_github_pages="https://websoft9.github.io/websoft9"

RUN apt update && apt install -y --no-install-recommends curl git jq cron iproute2 supervisor rsync wget unzip zip && \
    # Prepare library
    git clone --depth=1 $library_repo \
    mv docker-library w9library && \
    rm -rf w9library/.github && \
    # Prepare media
    if [ ! -f ./media.zip ]; then \
      wget $websoft9_artifact/plugin/media/media-latest.zip -O ./media.zip && \
      unzip media.zip \
    fi \
    mv media* w9media \
    git clone --depth=1 https://github.com/swagger-api/swagger-ui.git && \
    wget https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js && \
    cp redoc.standalone.js swagger-ui/dist && \
    git clone --depth=1 $websoft9_repo ./w9source && \
    cp -r ./w9media ./media && \
    cp -r ./w9library ./library && \
    cp -r ./w9source/apphub ./apphub && \
    cp -r ./swagger-ui/dist ./apphub/swagger-ui && \
    cp -r ./w9source/apphub/src/config ./config && \
    cp -r ./w9source/docker/apphub/script ./script && \
    curl -o ./script/update_zip.sh $source_github_pages/scripts/update_zip.sh && \
    pip install --no-cache-dir --upgrade -r apphub/requirements.txt && \
    pip install -e ./apphub && \
    # Clean cache and install files
    rm -rf apphub/docs apphub/tests library.zip media.zip redoc.standalone.js swagger-ui w9library w9media w9source && \
    apt clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /usr/share/man /usr/share/doc /usr/share/doc-base

# supervisor
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +r /etc/supervisor/conf.d/supervisord.conf

# cron
COPY config/cron /etc/cron.d/cron
RUN echo "" >> /etc/cron.d/cron && crontab /etc/cron.d/cron

# chmod for all .sh script
RUN find /websoft9/script -name "*.sh" -exec chmod +x {} \;

VOLUME /websoft9/apphub/logs 
VOLUME /websoft9/apphub/src/config

EXPOSE 8080
ENTRYPOINT ["/websoft9/script/entrypoint.sh"]
