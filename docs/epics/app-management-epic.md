# Epic: Application Management

**Related PRD:** [FR-APP-001]
**Owner:** Product Manager  
**Status:** In Development  
**Priority:** P0 (Required)  
**Estimated Effort:** 4-5 weeks

---

## 1. Epic Overview

### 1.1 Business Objectives

Provide complete containerized application lifecycle management capabilities, supporting the entire workflow from application catalog browsing, one-click installation, to operations management.

### 1.2 Core Value

- Users can quickly browse and install 200+ open-source applications
- Standardized deployment through docker-compose
- Integrated Portainer for visual container management
- Real-time application status monitoring and log viewing
- Simplified operations (start, stop, restart, uninstall)

### 1.3 Acceptance Criteria

✅ Application catalog supports category browsing (Chinese/English)  
✅ Application installation success rate > 95%  
✅ Average installation time < 2 minutes  
✅ Application status change response < 3 seconds  
✅ Uninstall cleans all related resources  
✅ Real-time log viewing with no delay (< 500ms)  

---

## 2. Technical Specifications

### 2.1 Architecture Design

#### System Architecture

```
User Request → AppHub API → App Manager Service
                              ↓
                        Portainer API
                              ↓
                        Docker Engine
```

#### Data Flow

```
Application Catalog (media.json) → Parse Metadata → API Response
Install Request → Generate docker-compose → Portainer Stack → Docker Deployment
```

### 2.2 API Endpoints

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/v1/apps/catalog/{locale}` | GET | Get application catalog (locale: zh/en) | API Key |
| `/api/v1/apps/available/{locale}` | GET | Get available apps (not installed) | API Key |
| `/api/v1/apps` | GET | Get installed applications | API Key |
| `/api/v1/apps/{app_id}` | GET | Get application details | API Key |
| `/api/v1/apps/install` | POST | Install application (async background) | API Key |
| `/api/v1/apps/{app_id}/start` | POST | Start application | API Key |
| `/api/v1/apps/{app_id}/stop` | POST | Stop application | API Key |
| `/api/v1/apps/{app_id}/restart` | POST | Restart application | API Key |
| `/api/v1/apps/{app_id}/redeploy` | PUT | Redeploy application (pull images, streaming logs) | API Key |
| `/api/v1/apps/{app_id}/uninstall` | DELETE | Uninstall application (supports data cleanup) | API Key |
| `/api/v1/apps/{app_id}/remove` | DELETE | Remove empty app (status: inactive) | API Key |
| `/api/v1/apps/{app_id}/error/remove` | DELETE | Remove error app (status: error) | API Key |

#### Example: Install Application

**Request:**
```http
POST /api/v1/apps/install
X-API-Key: <key>
Content-Type: application/json

{
  "app_name": "wordpress",
  "app_id": "wordpress001",
  "endpointId": 1,
  "domain": "myblog.example.com",
  "env": {
    "MYSQL_ROOT_PASSWORD": "secret123",
    "WORDPRESS_DB_NAME": "wp_db"
  }
}
```

**Response:**
```json
{
  "code": 200,
  "message": "App installed successfully",
  "data": {
    "app_id": "wordpress001",
    "app_name": "wordpress",
    "status": "running",
    "domain": "myblog.example.com",
    "created_at": "2026-01-05T10:30:00Z"
  }
}
```

### 2.3 Data Models

#### Application Metadata (media.json)

```python
class AppCatalog(BaseModel):
    key: str                           # Unique application identifier
    name: str                          # Application name
    trademark: str                     # Trademark name
    category: str                      # Category
    description: str                   # Description
    compose_file: str                  # docker-compose.yml path
    logo_url: str                      # Logo URL
    requirements: Dict[str, Any]       # System requirements
    default_port: int                  # Default port
```

#### Installed Application (from Portainer)

```python
class InstalledApp(BaseModel):
    app_id: str                        # Stack ID
    app_name: str                      # Application name
    status: str                        # running, stopped, error
    created_at: datetime
    containers: List[Dict]             # Container list
    env_vars: Dict[str, str]           # Environment variables
```

### 2.4 Core Service Design

#### app_manager.py

```python
class AppManager:
    def __init__(self):
        self.portainer = PortainerAPI()
        self.media = self.load_media_catalog()
    
    def get_catalog_apps(self, locale: str) -> List[AppCatalog]:
        """Get application catalog"""
        pass
    
    def get_available_apps(self, locale: str) -> List[Dict]:
        """Get available apps (not installed)"""
        installed = self.get_apps()
        all_apps = self.get_catalog_apps(locale)
        return [app for app in all_apps if app.key not in installed]
    
    def install_app(self, app_install: AppInstall) -> Dict:
        """
        Application installation workflow:
        1. Validate application exists
        2. Generate docker-compose.yml
        3. Create Stack through Portainer
        4. Wait for container startup
        5. Return installation result
        """
        pass
    
    def start_app(self, app_id: str) -> Dict:
        """Start application - Call Portainer Stack Start"""
        pass
    
    def stop_app(self, app_id: str) -> Dict:
        """Stop application - Call Portainer Stack Stop"""
        pass
    
    def uninstall_app(self, app_id: str, remove_volumes: bool = False) -> Dict:
        """
        Uninstall application:
        1. Stop all containers
        2. Delete containers
        3. Delete networks
        4. Optionally delete volumes
        """
        pass
```

### 2.5 Portainer Integration

```python
class PortainerAPI:
    def __init__(self):
        self.base_url = "http://portainer:9000/api"
        self.token = self.authenticate()
    
    def create_stack(self, stack_name: str, compose_content: str, 
                     endpoint_id: int, env: Dict) -> Dict:
        """Create Stack"""
        url = f"{self.base_url}/stacks"
        payload = {
            "Name": stack_name,
            "StackFileContent": compose_content,
            "Env": [{"name": k, "value": v} for k, v in env.items()]
        }
        response = requests.post(url, json=payload, headers=self.headers)
        return response.json()
    
    def start_stack(self, stack_id: int, endpoint_id: int) -> Dict:
        """Start Stack"""
        url = f"{self.base_url}/stacks/{stack_id}/start"
        response = requests.post(url, params={"endpointId": endpoint_id})
        return response.json()
    
    def delete_stack(self, stack_id: int, endpoint_id: int) -> None:
        """Delete Stack"""
        url = f"{self.base_url}/stacks/{stack_id}"
        requests.delete(url, params={"endpointId": endpoint_id})
```

### 2.6 Configuration

```yaml
# config/app.yaml
app_management:
  media_url: "https://websoft9.github.io/docker-library/media.json"
  cache_duration: 3600  # Application catalog cache duration (seconds)
  
  portainer:
    url: "http://portainer:9000"
    username: "admin"
    password: "${PORTAINER_PASSWORD}"
  
  defaults:
    network_mode: "bridge"
    restart_policy: "unless-stopped"
    compose_version: "3.8"
  
  limits:
    max_concurrent_installs: 3
    install_timeout: 300  # 5 minutes
```

---

## 3. Story Breakdown

### Story 1: Application Catalog Browsing

**Priority:** P0  
**Effort:** 2 days

**Tasks:**
- Implement `/apps/catalog/{locale}` endpoint
- Load application metadata from media.json
- Support Chinese/English categories
- Add caching mechanism
- Write unit tests

### Story 2: Application Installation Workflow

**Priority:** P0  
**Effort:** 4 days

**Tasks:**
- Implement `/apps/install` endpoint
- Generate docker-compose files
- Portainer Stack creation logic
- Installation parameter validation
- Error handling and rollback
- Write integration tests

### Story 3: Application Lifecycle Management

**Priority:** P0  
**Effort:** 3 days

**Tasks:**
- Implement start/stop/restart endpoints
- Portainer API integration
- Status synchronization mechanism
- Write functional tests

### Story 4: Application Uninstallation

**Priority:** P0  
**Effort:** 2 days

**Tasks:**
- Implement `/apps/{app_id}/uninstall` endpoint
- Resource cleanup logic (containers, networks, volumes)
- Uninstall confirmation mechanism
- Write cleanup tests

### Story 5: Application Log Viewing

**Priority:** P1  
**Effort:** 2 days

**Tasks:**
- Implement `/apps/{app_id}/logs` endpoint
- Real-time log streaming
- Log filtering and search
- Write log tests

### Story 6: Installed Applications List

**Priority:** P0  
**Effort:** 2 days

**Tasks:**
- Implement `/apps` endpoint
- Fetch Stack list from Portainer
- Status aggregation and formatting
- Write query tests

---

## 4. Dependencies

### Technical Dependencies

- **Docker Engine** 20.10+
- **Portainer** 2.19+
- **FastAPI** 0.104+
- **Pydantic** 2.0+

### Module Dependencies

- **Configuration Module** - Read system configuration
- **Logging Module** - Record operation logs
- **API Key Authentication** - Interface security validation

### External Dependencies

- **media.json** - Application metadata (GitHub)
- **Docker Registry** - Image repository

---

## 5. Risks & Challenges

| Risk | Level | Mitigation |
|------|-------|------------|
| Portainer API changes | Medium | Version locking, API change monitoring |
| Application installation failures | High | Detailed error logs, automatic rollback |
| Concurrent installation conflicts | Medium | Queue mechanism, limit concurrency |
| Docker resource shortage | High | Pre-installation resource check, disk space alerts |
| Application catalog unavailable | Medium | Local cache, fallback solution |

---

## 6. Testing Strategy

### Unit Tests

- Application metadata parsing
- docker-compose generation logic
- Parameter validation rules
- API response formatting

### Integration Tests

- Complete installation workflow (select → install → run)
- Portainer API calls
- Error scenario handling
- Uninstall cleanup verification

### Performance Tests

- Application catalog load time < 2 seconds
- 3 concurrent installations
- 1000+ application catalog response time

### User Acceptance Tests

- Install WordPress and access
- Install GitLab and configure
- Batch install common application combinations

---

## 7. Monitoring Metrics

```python
# Prometheus metrics
app_install_total                      # Total application installations
app_install_success_total              # Successful installations
app_install_failed_total               # Failed installations
app_install_duration_seconds           # Installation duration
app_uninstall_total                    # Total uninstallations
app_running_total                      # Running applications
app_api_request_duration_seconds       # API response time
```

---

## Appendix

### A. Error Code Definitions

| Error Code | HTTP | Description |
|------------|------|-------------|
| APP_NOT_FOUND | 404 | Application not found |
| APP_ALREADY_INSTALLED | 409 | Application already installed |
| APP_INSTALL_FAILED | 500 | Installation failed |
| APP_START_FAILED | 500 | Start failed |
| APP_STOP_FAILED | 500 | Stop failed |
| APP_INVALID_CONFIG | 400 | Invalid configuration parameters |
| PORTAINER_API_ERROR | 502 | Portainer API error |
| DOCKER_RESOURCE_INSUFFICIENT | 507 | Insufficient Docker resources |

### B. Related Documentation

- [PRD - Application Management](../prd.md#21-应用管理)
- [Technical Architecture Documentation](../architecture.md)
- [Portainer API Documentation](https://docs.portainer.io/api/docs)

---

**Document Maintainer:** PM Agent  
**Last Updated:** 2026-01-05
