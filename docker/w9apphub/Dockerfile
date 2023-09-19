FROM python:3.10-slim
LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="0.0.1"

ENV LIBRARY_VERSION=v0.5.4


# RUN mkdir /usr/src/app/config
WORKDIR  /usr/websoft9

RUN apt update
RUN apt install -y supervisor wget git zip

RUN wget https://github.com/Websoft9/docker-library/archive/refs/tags/$LIBRARY_VERSION.zip -O /usr/websoft9/library.zip
RUN unzip library.zip
RUN mkdir credentials
RUN echo "This folder stored the credentials of other services that apphub will connect" > credentials/readme

# Media and master data from Contentful
RUN wget --depth=1 https://github.com/Websoft9/plugin-appstore
RUN mv -f plugin-appstore/data ./media

# Copy source and install pip dpendencies
# Todo: add virtualenv for Python install
COPY ../../appmanage_new ./apphub
RUN pip install -r apphub/requirements.txt


# supervisor
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +r /etc/supervisor/conf.d/supervisord.conf

# entrypoint
COPY config/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh


VOLUME /usr/websoft9/apphub/logs
VOLUME /usr/websoft9/apphub/src/conf
VOLUME /usr/websoft9/media

# Clean
RUN rm -rf apphub/docs apphub/tests library.zip plugin-appstore

# Expose the port in which the application will be deployed
EXPOSE 8080

ENTRYPOINT [/entrypoint.sh]
