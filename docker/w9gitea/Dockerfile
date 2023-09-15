# step1: build hook-api exe
FROM docker.io/library/golang:1.21-alpine3.18 as build-hook
WORKDIR /
COPY hook.go /
RUN go build -o hook /hook.go

# step2: from gitea image clone library, copy hook, s6 run script ...
FROM gitea/gitea:1.20.4
RUN cd / && git clone --depth=1 https://github.com/Websoft9/docker-library.git \
    && mv docker-library library
COPY --from=build-hook /hook /usr/local/bin/hook
COPY init.sh /usr/local/bin/init.sh
COPY ./hook /etc/s6/hook
COPY ./init /etc/s6/init
RUN chmod -R 755 /etc/s6/hook /usr/local/bin/init.sh
