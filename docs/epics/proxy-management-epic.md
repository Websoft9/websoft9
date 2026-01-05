# Epic: 反向代理管理

**关联 PRD:** [FR-PROXY-001](../prd.md#22-反向代理与-ssl-管理)  
**负责人:** Product Manager  
**状态:** In Development  
**优先级:** P0 (必需)  
**预估工作量:** 3-4 周

---

## 1. Epic 概述

### 1.1 业务目标

通过 Nginx Proxy Manager 提供应用的反向代理配置和自动化 SSL 证书管理，实现域名访问和 HTTPS 加密。

### 1.2 核心价值

- 应用可通过自定义域名访问
- 自动申请和续期 Let's Encrypt SSL 证书
- 支持强制 HTTPS 跳转
- 提供访问控制（IP 白名单/黑名单）
- 支持自定义 SSL 证书上传
- HTTP 基本认证保护

### 1.3 验收标准

✅ 代理主机创建时间 < 30秒  
✅ Let's Encrypt 证书自动申请成功率 > 95%  
✅ SSL 证书自动续期（过期前 30 天）  
✅ SSL Labs 评级 A 或以上  
✅ 代理配置变更生效时间 < 5秒  
✅ 支持通配符域名证书

---

## 2. 技术规范

### 2.1 架构设计

#### 系统架构

```
用户域名请求 → Nginx Proxy Manager → 后端应用容器
                       ↓
                Let's Encrypt (ACME)
```

#### 代理流程

```
域名解析 → NPM 反向代理 → Docker Network → 应用容器:端口
            ↓
    SSL 证书验证 & 加密
```

### 2.2 API 端点

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/api/v1/proxy/{app_id}` | GET | 获取应用代理配置 | API Key |
| `/api/v1/proxy/{app_id}` | POST | 创建代理主机 | API Key |
| `/api/v1/proxy/{app_id}` | PUT | 更新代理配置 | API Key |
| `/api/v1/proxy/{app_id}` | DELETE | 删除代理 | API Key |
| `/api/v1/proxy/certificates` | GET | 获取 SSL 证书列表 | API Key |
| `/api/v1/proxy/certificates` | POST | 上传自定义证书 | API Key |

#### 示例：创建代理主机

**请求:**
```http
POST /api/v1/proxy/wordpress001
X-API-Key: <key>
Content-Type: application/json

{
  "domain_names": ["myblog.example.com", "www.myblog.example.com"],
  "forward_host": "wordpress001_app_1",
  "forward_port": 80,
  "forward_scheme": "http",
  "ssl_enabled": true,
  "ssl_forced": true,
  "letsencrypt_email": "admin@example.com",
  "access_list_id": null,
  "enable_websocket": false,
  "http2_support": true,
  "hsts_enabled": true,
  "hsts_subdomains": true
}
```

**响应:**
```json
{
  "code": 200,
  "message": "Proxy host created successfully",
  "data": {
    "proxy_id": "123",
    "domain_names": ["myblog.example.com", "www.myblog.example.com"],
    "ssl_status": "pending",
    "certificate_expires_at": null,
    "created_at": "2026-01-05T10:30:00Z"
  }
}
```

### 2.3 数据模型

#### NPM 代理主机配置

```python
class ProxyHost(BaseModel):
    proxy_id: int                      # NPM Proxy Host ID
    app_id: str                        # 关联的应用 ID
    domain_names: List[str]            # 域名列表
    forward_host: str                  # 转发目标主机
    forward_port: int                  # 转发目标端口
    forward_scheme: str                # http 或 https
    ssl_enabled: bool                  # 是否启用 SSL
    ssl_forced: bool                   # 强制 HTTPS
    certificate_id: Optional[int]      # SSL 证书 ID
    access_list_id: Optional[int]      # 访问控制列表 ID
    enable_websocket: bool             # WebSocket 支持
    http2_support: bool                # HTTP/2 支持
    hsts_enabled: bool                 # HSTS 启用
```

#### SSL 证书

```python
class SSLCertificate(BaseModel):
    id: int
    provider: str                      # letsencrypt, custom, other
    domain_names: List[str]
    expires_at: datetime
    is_valid: bool
    meta: Dict[str, Any]               # 证书元数据
```

### 2.4 核心服务设计

#### nginx_proxy_manager.py

```python
class NginxProxyManagerAPI:
    def __init__(self):
        self.base_url = "http://nginx-proxy-manager:81/api"
        self.token = self.get_token()
    
    def get_token(self) -> str:
        """获取 NPM API Token"""
        response = requests.post(
            f"{self.base_url}/tokens",
            json={
                "identity": os.getenv("NPM_USER"),
                "secret": os.getenv("NPM_PASSWORD")
            }
        )
        return response.json()["token"]
    
    def create_proxy_host(self, config: Dict) -> Dict:
        """
        创建代理主机:
        1. 验证域名格式
        2. 检查域名是否已被使用
        3. 创建 Proxy Host
        4. 如果启用 SSL，申请 Let's Encrypt 证书
        5. 返回代理配置
        """
        url = f"{self.base_url}/nginx/proxy-hosts"
        headers = {"Authorization": f"Bearer {self.token}"}
        
        payload = {
            "domain_names": config["domain_names"],
            "forward_host": config["forward_host"],
            "forward_port": config["forward_port"],
            "forward_scheme": config["forward_scheme"],
            "certificate_id": config.get("certificate_id"),
            "ssl_forced": config.get("ssl_forced", False),
            "meta": {
                "letsencrypt_agree": True,
                "letsencrypt_email": config.get("letsencrypt_email"),
                "dns_challenge": False
            }
        }
        
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    
    def update_proxy_host(self, proxy_id: int, config: Dict) -> Dict:
        """更新代理配置"""
        url = f"{self.base_url}/nginx/proxy-hosts/{proxy_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        response = requests.put(url, json=config, headers=headers)
        return response.json()
    
    def delete_proxy_host(self, proxy_id: int) -> None:
        """删除代理主机"""
        url = f"{self.base_url}/nginx/proxy-hosts/{proxy_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        requests.delete(url, headers=headers)
    
    def request_letsencrypt_cert(self, proxy_id: int, email: str, 
                                  domains: List[str]) -> Dict:
        """申请 Let's Encrypt 证书"""
        url = f"{self.base_url}/nginx/certificates"
        headers = {"Authorization": f"Bearer {self.token}"}
        
        payload = {
            "provider": "letsencrypt",
            "domain_names": domains,
            "meta": {
                "letsencrypt_email": email,
                "letsencrypt_agree": True
            }
        }
        
        response = requests.post(url, json=payload, headers=headers)
        cert = response.json()
        
        # 将证书关联到代理主机
        self.update_proxy_host(proxy_id, {"certificate_id": cert["id"]})
        return cert
```

### 2.5 Let's Encrypt 证书自动续期

```python
class CertificateRenewalService:
    def __init__(self):
        self.npm_api = NginxProxyManagerAPI()
    
    async def auto_renew_certificates(self):
        """
        定时任务：自动续期证书
        - 每天检查一次
        - 过期前 30 天自动续期
        """
        certificates = self.npm_api.get_certificates()
        
        for cert in certificates:
            if cert["provider"] != "letsencrypt":
                continue
            
            days_until_expiry = (cert["expires_at"] - datetime.now()).days
            
            if days_until_expiry <= 30:
                logger.info(f"Renewing certificate for {cert['domain_names']}")
                try:
                    self.npm_api.renew_certificate(cert["id"])
                    logger.info(f"Certificate renewed: {cert['id']}")
                except Exception as e:
                    logger.error(f"Certificate renewal failed: {e}")
```

### 2.6 配置

```yaml
# config/proxy.yaml
nginx_proxy_manager:
  url: "http://nginx-proxy-manager:81"
  api_url: "http://nginx-proxy-manager:81/api"
  admin_email: "${NPM_ADMIN_EMAIL}"
  admin_password: "${NPM_ADMIN_PASSWORD}"
  
  ssl:
    provider: "letsencrypt"
    auto_renew: true
    renew_before_days: 30
    challenge_type: "http-01"  # http-01 或 dns-01
  
  defaults:
    forward_scheme: "http"
    ssl_forced: true
    http2_support: true
    hsts_enabled: true
    hsts_max_age: 31536000
    websocket_support: false
```

---

## 3. Stories 拆分

### Story 1: NPM API 集成

**优先级:** P0  
**工作量:** 3 天

**任务:**
- 实现 NPM Token 认证
- 封装代理主机 CRUD 接口
- 错误处理和重试机制
- 编写 API 集成测试

### Story 2: 代理主机管理

**优先级:** P0  
**工作量:** 3 天

**任务:**
- 实现创建代理主机端点
- 域名格式验证
- 代理配置持久化
- 编写功能测试

### Story 3: Let's Encrypt 证书申请

**优先级:** P0  
**工作量:** 4 天

**任务:**
- 集成 Let's Encrypt ACME 流程
- HTTP-01 挑战验证
- 证书申请失败处理
- 编写证书申请测试

### Story 4: SSL 证书自动续期

**优先级:** P1  
**工作量:** 2 天

**任务:**
- 实现定时检查任务
- 证书过期监控
- 自动续期逻辑
- 续期失败告警
- 编写续期测试

### Story 5: 自定义 SSL 证书上传

**优先级:** P1  
**工作量:** 2 天

**任务:**
- 证书文件上传接口
- 证书格式验证（PEM）
- 私钥安全存储
- 编写上传测试

### Story 6: 访问控制列表

**优先级:** P2  
**工作量:** 2 天

**任务:**
- IP 白名单/黑名单配置
- HTTP 基本认证
- 访问控制规则验证
- 编写访问控制测试

---

## 4. 依赖关系

### 技术依赖

- **Nginx Proxy Manager** 2.10+
- **Let's Encrypt** ACME v2
- **FastAPI** 0.104+
- **Certbot** (内置于 NPM)

### 模块依赖

- **应用管理模块** - 获取应用容器信息
- **配置模块** - 读取代理配置
- **日志模块** - 记录证书操作

### 外部依赖

- **DNS 解析** - 域名必须正确解析到服务器
- **80/443 端口开放** - Let's Encrypt HTTP-01 验证

---

## 5. 风险与挑战

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| Let's Encrypt 速率限制 | 高 | 使用 DNS-01 挑战，避免重复申请 |
| 证书申请失败 | 高 | 详细错误日志，DNS 预检查 |
| 域名未解析到服务器 | 中 | 安装前 DNS 验证提示 |
| NPM API 变更 | 中 | API 版本锁定，变更监控 |
| 证书续期失败 | 高 | 提前 30 天续期，失败告警 |

---

## 6. 测试策略

### 单元测试

- 域名格式验证
- 代理配置生成
- Token 认证逻辑
- API 响应解析

### 集成测试

- 完整代理创建流程
- Let's Encrypt 证书申请（测试环境）
- 证书续期模拟
- 代理删除清理

### 手动测试

- 真实域名 SSL 证书申请
- SSL Labs 评分验证
- 浏览器 HTTPS 访问
- 强制 HTTPS 跳转验证

---

## 7. 监控指标

```python
# Prometheus 指标
proxy_host_total                       # 代理主机总数
proxy_host_create_success_total        # 创建成功数
proxy_host_create_failed_total         # 创建失败数
ssl_certificate_total                  # SSL 证书总数
ssl_certificate_expiring_soon          # 即将过期证书数
ssl_certificate_renew_success_total    # 续期成功数
ssl_certificate_renew_failed_total     # 续期失败数
proxy_api_request_duration_seconds     # API 响应时间
```

---

## 附录

### A. 错误码定义

| 错误码 | HTTP | 说明 |
|--------|------|------|
| PROXY_DOMAIN_INVALID | 400 | 域名格式无效 |
| PROXY_DOMAIN_CONFLICT | 409 | 域名已被使用 |
| PROXY_NOT_FOUND | 404 | 代理配置不存在 |
| SSL_CERT_REQUEST_FAILED | 500 | SSL 证书申请失败 |
| SSL_CERT_INVALID | 400 | SSL 证书格式无效 |
| NPM_API_ERROR | 502 | NPM API 错误 |
| DNS_RESOLUTION_FAILED | 400 | 域名未解析到服务器 |

### B. Let's Encrypt 速率限制

- **每域名证书:** 50 张/周
- **重复证书:** 5 张/周
- **失败验证:** 5 次/账户/小时
- **新账户:** 10 个/IP/3小时

### C. 相关文档

- [PRD - 反向代理与 SSL 管理](../prd.md#22-反向代理与-ssl-管理)
- [Nginx Proxy Manager 文档](https://nginxproxymanager.com/guide/)
- [Let's Encrypt 文档](https://letsencrypt.org/docs/)

---

**文档维护:** PM Agent  
**最后更新:** 2026-01-05
