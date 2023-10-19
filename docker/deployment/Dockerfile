# modify time: 202310191713, you can modify here to trigger Docker Build action
# step1: Build entrypoint execute program init_portainer by golang

FROM golang:latest AS builder
WORKDIR /
COPY init_portainer.go /
RUN go build -o init_portainer /init_portainer.go
RUN chmod +x /init_portainer

COPY environment.go /
RUN go build -o environment /environment.go
RUN chmod +x /environment

# step2: Copy build go program to portainer
# Dockerfile refer to: https://github.com/portainer/portainer/blob/develop/build/linux/Dockerfile
FROM portainer/portainer-ce:2.19.0
LABEL maintainer="websoft9<help@websoft9.com>"
LABEL version="2.19.0"
COPY --from=builder /init_portainer /
COPY --from=builder /environment /

ENTRYPOINT ["/init_portainer"]
