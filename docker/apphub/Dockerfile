# modify time: 202312081739, you can modify here to trigger Docker Build action


FROM python:3.10-slim-bullseye
LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="0.0.6"

WORKDIR  /websoft9

ENV websoft9_repo="https://github.com/Websoft9/websoft9"
ENV websoft9_artifact="https://w9artifact.blob.core.windows.net/release/websoft9"
ENV library_repo="https://github.com/Websoft9/docker-library"
ENV source_github_pages="https://websoft9.github.io/websoft9"

RUN apt update && apt install -y --no-install-recommends curl git jq cron iproute2 supervisor rsync wget unzip zip && \
    git clone --depth=1 $library_repo && \
    mv docker-library w9library && \
    rm -rf w9library/.github && \
    unzip media.zip

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
