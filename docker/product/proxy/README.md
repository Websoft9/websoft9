# Readme

From official Nginx Proxy Manager image, and:

- Copy the initproxy.conf file to the nginx directory to initialize the custom configuration
- Initialize username and password through environment variables
- Add landing page designed by [figma](https://www.figma.com/)
- Reserve the product-origin platform gateway prefixes in `config/platform-gateway-boundary.conf`
- Keep product entry and internal-service routes in `config/platform-gateway-routes.conf`
- Leave user application domain proxying under NPM-managed `proxy_host` configs instead of the platform default host