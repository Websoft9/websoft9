# step1: build hook-api exe
FROM docker.io/library/golang:1.21-alpine3.18 as build-hook
WORKDIR /

# 定义构建参数
ARG GITEA_VERSION=1.20.4

# step2: from gitea image clone library, copy hook, s6 run script ...
FROM gitea/gitea:${GITEA_VERSION}
COPY init.sh /usr/local/bin/init.sh
COPY ./init /etc/s6/init
RUN chmod -R 755 /etc/s6/init /usr/local/bin/init.sh
