# Readme

From official Nginx Proxy Manager image, and:

- Initialize username and password through environment variables
- Keep only NPM-owned runtime assets here, such as the stream multiplexer and NPM custom http snippets
- Leave product-origin routing, platform TLS ownership, and reserved Websoft9 prefixes under `docker/product/gateway/`
- Leave user application domain proxying under NPM-managed `proxy_host` configs instead of the platform default host