# API Reference

AppHub exposes a REST API at `/api` through the product gateway.

**Base URL**: `http://<server>:9000/api`

## Authentication

All API endpoints, including Swagger and OpenAPI, require a product-side operator session. Sign in to Websoft9 first, then open the API reference in the same browser session. The platform gateway validates the session before forwarding requests to AppHub.

AppHub also supports `x-api-key` and a gateway-only internal trust key for service-to-service calls. Neither credential is returned by the public API.

## API Modules

| Module | Prefix | Description |
|--------|--------|-------------|
| Apps | `/api/apps` | Application catalog, install, lifecycle |
| Auth | `/api/auth` | User authentication and token management |
| Backup | `/api/backup` | Backup jobs, schedules, restore |
| Compose | `/api/compose` | Custom Docker Compose app management |
| Files | `/api/files` | File browser operations |
| Host Access | `/api/host-access` | SSH/SFTP credential management |
| Integrations | `/api/integrations` | Gitea, Portainer, NPM session management |
| Logs | `/api/logs` | System and application log retrieval |
| Overview | `/api/overview` | Dashboard metrics and host info |
| Proxy | `/api/proxy` | NPM proxy host and certificate management |
| Services | `/api/services` | Core service status and control |
| Settings | `/api/settings` | Platform configuration |
| AppStore Sync | `/api/appstore` | Application catalog synchronization |
| Setup Wizard | `/api/setup` | Initial product setup wizard |

## Common Response Format

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

## Error Response

```json
{
  "code": -1,
  "message": "error description",
  "data": null
}
```

## API Documentation (Swagger)

After signing in to Websoft9, interactive API docs are available at:
- Swagger UI: `http://<server>:9000/api/docs`
- ReDoc: `http://<server>:9000/api/redoc`
- OpenAPI JSON: `http://<server>:9000/api/openapi.json`
