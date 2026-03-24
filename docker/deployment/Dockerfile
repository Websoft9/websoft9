# modify time: 202503231200, you can modify here to trigger Docker Build action
# CVE fix: upgrade to 2.39.1 to resolve CVE-2026-33186 (grpc) and CVE-2026-1229 (circl)
# step1: Build entrypoint execute program init_portainer by golang

FROM golang:latest AS builder
WORKDIR /
COPY init_portainer.go /
# CGO_ENABLED=0 can not depend on any dynamic library
RUN CGO_ENABLED=0 go build -o init_portainer /init_portainer.go
RUN chmod +x /init_portainer


# step2: Copy build go program to portainer
# Dockerfile refer to: https://github.com/portainer/portainer/blob/develop/build/linux/Dockerfile
FROM portainer/portainer-ce:2.39.1
LABEL maintainer="websoft9<help@websoft9.com>"
LABEL version="2.39.1-rc1"
COPY --from=builder /init_portainer /

ENTRYPOINT ["/init_portainer"]
