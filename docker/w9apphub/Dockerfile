# python:3.10-bullseye
# RUN apt update & apt install wget git curl unzip

FROM python:3.10-bullseye
LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="0.8.17"


ENV LIBRARY_VERSION=v0.5.4

WORKDIR  /usr/websoft9

# Prepare library
RUN wget https://github.com/Websoft9/docker-library/archive/refs/tags/$LIBRARY_VERSION.zip -O ./library.zip && \
    unzip library.zip && \
    mkdir credentials && \
    echo "This folder stored the credentials of other services that apphub will connect" > credentials/readme  && \
    # Prepare  Media and master data from Contentful 
    git clone --depth=1 https://github.com/Websoft9/plugin-appstore && \
    mv -f plugin-appstore/data ./media

# Copy source and install pip dpendencies
# Todo: add virtualenv for Python install
#COPY ../../appmanage_new ./apphub
#RUN pip install -r apphub/requirements.txt


# supervisor
RUN pip install supervisor
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +r /etc/supervisor/conf.d/supervisord.conf


COPY config/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME /usr/websoft9/apphub/logs
VOLUME /usr/websoft9/apphub/src/conf
VOLUME /usr/websoft9/media

# Clean cache and install files
RUN rm -rf apphub/docs apphub/tests library.zip plugin-appstore

EXPOSE 8080
ENTRYPOINT [/entrypoint.sh]