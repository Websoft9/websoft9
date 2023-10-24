# modify time: 202310241540, you can modify here to trigger Docker Build action

FROM python:3.10-bullseye AS buildstage
LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="0.0.6-rc2"

ENV LIBRARY_VERSION=v0.5.8
ENV MEDIA_VERSION=0.0.3
ENV websoft9_repo="https://github.com/Websoft9/websoft9"
ENV docker_library_repo="https://github.com/Websoft9/docker-library"
ENV media_repo="https://github.com/Websoft9/media"

# Prepare source files
RUN wget $docker_library_repo/archive/refs/tags/$LIBRARY_VERSION.zip -O ./library.zip && \
    unzip library.zip && \
    mv docker-library-* w9library && \
    rm -rf w9library/.github && \

    wget $media_repo/archive/refs/tags/$MEDIA_VERSION.zip -O ./media.zip && \
    unzip media.zip && \
    mv media-* w9media && \
    rm -rf w9media/.github && \

    # Prepare  Media and master data from Contentful
    git clone --depth=1 https://github.com/swagger-api/swagger-ui.git && \
    wget https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js && \ 
    cp redoc.standalone.js swagger-ui/dist && \ 

    git clone --depth=1 $websoft9_repo

FROM python:3.10-slim-bullseye
WORKDIR  /websoft9

COPY --from=buildstage /w9media ./media
COPY --from=buildstage /w9library ./library
COPY --from=buildstage /websoft9/apphub ./apphub
COPY --from=buildstage /swagger-ui/dist ./apphub/swagger-ui

RUN apt update && apt install curl git jq iproute2 supervisor -y

RUN pip install --no-cache-dir --upgrade -r apphub/requirements.txt
RUN pip install -e ./apphub

# supervisor
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +r /etc/supervisor/conf.d/supervisord.conf
COPY config/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME /websoft9/apphub/logs 
VOLUME /websoft9/apphub/src/config

# Clean cache and install files
RUN rm -rf apphub/docs apphub/tests library.zip plugin-appstore && \
    apt clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /usr/share/man /usr/share/doc /usr/share/doc-base

EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]