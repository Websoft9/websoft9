# modify time: 202403261345, you can modify here to trigger Docker Build action
# Dockerfile refer to: https://github.com/go-gitea/gitea/blob/main/Dockerfile
FROM gitea/gitea:1.21.9

LABEL maintainer="Websoft9<help@websoft9.com>"
LABEL version="1.21.9-test"
COPY ./src/s6/user /etc/s6/user
RUN chmod -R 755 /etc/s6/user
