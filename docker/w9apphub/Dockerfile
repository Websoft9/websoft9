FROM python:3.10-bullseye AS buildstage
LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="0.0.1"


ENV LIBRARY_VERSION=v0.5.4

# Prepare library
RUN wget https://github.com/Websoft9/docker-library/archive/refs/tags/$LIBRARY_VERSION.zip -O ./library.zip && \
    unzip library.zip && \
    mv docker-library-* library && \
    mkdir credentials && \
    echo "This folder stored the credentials of other services that apphub will connect" > credentials/readme  && \
    # Prepare  Media and master data from Contentful 
    git clone --depth=1 https://github.com/Websoft9/plugin-appstore && \
    mv -f plugin-appstore/data ./media && \
    git clone --depth=1 https://github.com/Websoft9/websoft9


FROM python:3.10-slim-bullseye
WORKDIR  /websoft9

COPY --from=buildstage /media/data ./media
COPY --from=buildstage /library ./library
COPY --from=buildstage /websoft9/appmanage_new ./apphub


RUN apt update && apt install git -y && \
    mkdir credentials && \
    echo "This folder stored the credentials of other services that integrated with apphub" > credentials/readme

RUN pip install --upgrade pip && pip install -r apphub/requirements.txt

# supervisor
RUN pip install supervisor
COPY config/supervisord.conf /usr/local/supervisord.conf
RUN chmod +r /usr/local/supervisord.conf


COPY config/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME /usr/websoft9/apphub/logs 
VOLUME /usr/websoft9/apphub/src/conf
VOLUME /usr/websoft9/media

# Clean cache and install files
RUN rm -rf apphub/docs apphub/tests library.zip plugin-appstore

EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]