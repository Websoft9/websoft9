FROM gitea/gitea:1.20.4
LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="1.20.4"

COPY init.sh /usr/local/bin/init.sh
COPY ./init /etc/s6/init
RUN chmod -R 755 /etc/s6/init /usr/local/bin/init.sh
