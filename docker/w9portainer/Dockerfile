# step1: build entrypoint execute program init_portainer by golang
FROM golang:latest AS builder
WORKDIR /
COPY init_portainer.go /
COPY init_endpoint.go /
RUN go build -o init_portainer /init_portainer.go
RUN go build -o init_endpoint /init_endpoint.go
RUN chmod +x /init_portainer /init_endpoint

# step2: copy build go program to portainer
FROM portainer/portainer-ce:2.19.0
COPY --from=builder /init_portainer /
COPY --from=builder /init_endpoint /