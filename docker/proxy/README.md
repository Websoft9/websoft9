# Readme

From official Nginx Proxy Manager image, and:

- Initialize username and password through environment variables
- Keep only NPM-owned proxy runtime assets in this legacy image
- Leave user application domain proxying under NPM-managed `proxy_host` configs