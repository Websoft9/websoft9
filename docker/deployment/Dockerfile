# step1: build entrypoint execute program init_portainer by golang
FROM golang:latest AS builder
WORKDIR /
COPY init_portainer.go /
RUN go build -o init_portainer /init_portainer.go
RUN chmod +x /init_portainer

# step2: copy build go program to portainer
FROM portainer/portainer-ce:2.19.0
LABEL maintainer="websoft9<help@websoft9.com>"
LABEL version="2.19.0"
COPY --from=builder /init_portainer /
ENTRYPOINT ["/init_portainer"]