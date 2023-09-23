FROM gitea/gitea:1.20.4

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="1.20.4"
#COPY ./src/s6/user /etc/s6/user
#RUN chmod -R 755 /etc/s6/user
COPY ./src/init_user.sh /etc/init.d/init_user.sh
RUN chmod -R 755 /etc/init.d/init_user.sh