# Epic: 系统设置管理

**关联 PRD:** [FR-SYS-001](../prd.md#23-系统管理)  
**负责人:** Product Manager  
**状态:** In Development  
**优先级:** P0 (必需)  
**预估工作量:** 2-3 周

---

## 1. Epic 概述

### 1.1 业务目标

提供系统级配置管理能力，包括 AppHub 配置、Portainer 配置、NPM 配置等核心组件的参数管理。

### 1.2 核心价值

- 统一的配置管理界面
- 配置变更实时生效
- 配置验证和校验
- 配置备份和恢复
- 敏感信息加密存储

### 1.3 验收标准

✅ 配置读取响应时间 < 100ms  
✅ 配置更新后立即生效（无需重启）  
✅ 敏感配置加密存储  
✅ 配置变更记录审计日志  
✅ 配置格式验证准确率 100%  
✅ 支持配置回滚

---

## 2. 技术规范

### 2.1 架构设计

#### 配置存储架构

```
应用配置 → config.ini (ConfigParser)
系统配置 → system.ini
环境变量 → .env 文件
敏感配置 → 加密存储 (Fernet)
```

#### 配置读取流程

```
API 请求 → Config Manager → 读取 INI 文件 → 解密敏感值 → 返回配置
```

### 2.2 API 端点

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/api/v1/settings` | GET | 获取所有配置 | API Key |
| `/api/v1/settings/{section}` | GET | 获取指定配置节 | API Key |
| `/api/v1/settings` | PUT | 批量更新配置 | API Key |
| `/api/v1/settings/{section}/{key}` | PUT | 更新单个配置 | API Key |
| `/api/v1/settings/{section}/{key}` | DELETE | 删除配置项 | API Key |
| `/api/v1/settings/validate` | POST | 验证配置格式 | API Key |
| `/api/v1/settings/backup` | POST | 备份配置 | API Key |
| `/api/v1/settings/restore` | POST | 恢复配置 | API Key |

#### 示例：获取配置

**请求:**
```http
GET /api/v1/settings
X-API-Key: <key>
```

**响应:**
```json
{
  "code": 200,
  "data": {
    "portainer": {
      "url": "http://portainer:9000",
      "username": "admin",
      "password": "******"  // 敏感信息脱敏
    },
    "nginx_proxy_manager": {
      "url": "http://nginx-proxy-manager:81",
      "admin_email": "admin@example.com",
      "admin_password": "******"
    },
    "gitea": {
      "url": "http://gitea:3000",
      "admin_username": "gitea_admin"
    },
    "apphub": {
      "media_url": "https://websoft9.github.io/docker-library/media.json",
      "cache_duration": 3600,
      "max_concurrent_installs": 3
    }
  }
}
```

#### 示例:更新配置

**请求:**
```http
PUT /api/v1/settings/portainer/password
X-API-Key: <key>
Content-Type: application/json

{
  "value": "new_secure_password_123"
}
```

**响应:**
```json
{
  "code": 200,
  "message": "Configuration updated successfully",
  "data": {
    "section": "portainer",
    "key": "password",
    "value": "******",
    "updated_at": "2026-01-05T10:30:00Z"
  }
}
```

### 2.3 数据模型

#### 配置文件结构（config.ini）

```ini
[portainer]
url = http://portainer:9000
username = admin
password = encrypted:gAAAAABh1234567890...  # Fernet 加密

[nginx_proxy_manager]
url = http://nginx-proxy-manager:81
admin_email = admin@example.com
admin_password = encrypted:gAAAAABh9876543210...

[gitea]
url = http://gitea:3000
admin_username = gitea_admin
admin_password = encrypted:gAAAAABh5555555555...

[apphub]
media_url = https://websoft9.github.io/docker-library/media.json
cache_duration = 3600
max_concurrent_installs = 3
log_level = INFO

[system]
timezone = Asia/Shanghai
language = zh_CN
```

#### Python 配置模型

```python
class ConfigItem(BaseModel):
    section: str
    key: str
    value: str
    is_sensitive: bool = False  # 是否为敏感配置
    data_type: str = "string"   # string, int, bool, list
    description: Optional[str]

class ConfigSection(BaseModel):
    name: str
    items: Dict[str, ConfigItem]
    description: Optional[str]
```

### 2.4 核心服务设计

#### config.py

```python
import configparser
from cryptography.fernet import Fernet
import os

class ConfigManager:
    def __init__(self, config_file="config/config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        
        # 加密密钥（从环境变量读取）
        self.cipher = Fernet(os.getenv("CONFIG_ENCRYPTION_KEY").encode())
    
    def get_value(self, section: str, key: str, 
                  decrypt: bool = True) -> str:
        """
        获取配置值
        - 自动解密以 'encrypted:' 开头的值
        """
        value = self.config.get(section, key)
        
        if decrypt and value.startswith("encrypted:"):
            encrypted_data = value.replace("encrypted:", "")
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        
        return value
    
    def set_value(self, section: str, key: str, value: str, 
                  encrypt: bool = False) -> None:
        """
        设置配置值
        - 敏感配置自动加密
        """
        if not self.config.has_section(section):
            self.config.add_section(section)
        
        if encrypt:
            encrypted_value = self.cipher.encrypt(value.encode()).decode()
            value = f"encrypted:{encrypted_value}"
        
        self.config.set(section, key, value)
        self._save_config()
        
        # 记录审计日志
        self._log_config_change(section, key, "update")
    
    def remove_value(self, section: str, key: str) -> None:
        """删除配置项"""
        if self.config.has_option(section, key):
            self.config.remove_option(section, key)
            self._save_config()
            self._log_config_change(section, key, "delete")
    
    def remove_section(self, section: str) -> None:
        """删除整个配置节"""
        if self.config.has_section(section):
            self.config.remove_section(section)
            self._save_config()
            self._log_config_change(section, None, "delete_section")
    
    def get_all_config(self, mask_sensitive: bool = True) -> Dict:
        """
        获取所有配置
        - mask_sensitive: 是否脱敏敏感信息
        """
        result = {}
        sensitive_keys = ["password", "secret", "token", "key"]
        
        for section in self.config.sections():
            result[section] = {}
            for key, value in self.config.items(section):
                # 敏感配置脱敏
                if mask_sensitive and any(sk in key.lower() for sk in sensitive_keys):
                    result[section][key] = "******"
                elif value.startswith("encrypted:"):
                    result[section][key] = "******"
                else:
                    result[section][key] = value
        
        return result
    
    def validate_config(self, section: str, key: str, 
                       value: str) -> Tuple[bool, str]:
        """
        验证配置值
        - URL 格式验证
        - 端口范围验证
        - 必填项验证
        """
        validators = {
            "url": self._validate_url,
            "port": self._validate_port,
            "email": self._validate_email,
            "int": self._validate_int,
        }
        
        # 根据 key 名称判断验证类型
        if "url" in key.lower():
            return validators["url"](value)
        elif "port" in key.lower():
            return validators["port"](value)
        elif "email" in key.lower():
            return validators["email"](value)
        
        return True, "Valid"
    
    def backup_config(self) -> str:
        """
        备份配置文件
        返回备份文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"config/backups/config_{timestamp}.ini"
        
        os.makedirs("config/backups", exist_ok=True)
        shutil.copy(self.config_file, backup_file)
        
        logger.info(f"Configuration backed up to {backup_file}")
        return backup_file
    
    def restore_config(self, backup_file: str) -> None:
        """恢复配置文件"""
        if not os.path.exists(backup_file):
            raise FileNotFoundError(f"Backup file not found: {backup_file}")
        
        # 备份当前配置
        self.backup_config()
        
        # 恢复
        shutil.copy(backup_file, self.config_file)
        self.config.read(self.config_file)
        
        logger.info(f"Configuration restored from {backup_file}")
    
    def _save_config(self) -> None:
        """保存配置到文件"""
        with open(self.config_file, 'w') as f:
            self.config.write(f)
    
    def _log_config_change(self, section: str, key: str, action: str) -> None:
        """记录配置变更审计日志"""
        logger.access(
            action="config_change",
            section=section,
            key=key,
            operation=action,
            timestamp=datetime.now().isoformat()
        )
```

### 2.5 配置加密

```python
from cryptography.fernet import Fernet

class ConfigEncryption:
    @staticmethod
    def generate_key() -> str:
        """生成新的加密密钥"""
        return Fernet.generate_key().decode()
    
    @staticmethod
    def encrypt_value(value: str, key: str) -> str:
        """加密配置值"""
        cipher = Fernet(key.encode())
        encrypted = cipher.encrypt(value.encode())
        return f"encrypted:{encrypted.decode()}"
    
    @staticmethod
    def decrypt_value(encrypted_value: str, key: str) -> str:
        """解密配置值"""
        cipher = Fernet(key.encode())
        encrypted_data = encrypted_value.replace("encrypted:", "")
        return cipher.decrypt(encrypted_data.encode()).decode()
```

### 2.6 配置验证规则

```python
class ConfigValidator:
    @staticmethod
    def _validate_url(url: str) -> Tuple[bool, str]:
        """验证 URL 格式"""
        import re
        pattern = r'^https?://[\w\-.]+(:\d+)?(/.*)?$'
        if re.match(pattern, url):
            return True, "Valid URL"
        return False, "Invalid URL format"
    
    @staticmethod
    def _validate_port(port: str) -> Tuple[bool, str]:
        """验证端口范围"""
        try:
            port_num = int(port)
            if 1 <= port_num <= 65535:
                return True, "Valid port"
            return False, "Port must be between 1 and 65535"
        except ValueError:
            return False, "Port must be a number"
    
    @staticmethod
    def _validate_email(email: str) -> Tuple[bool, str]:
        """验证邮箱格式"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(pattern, email):
            return True, "Valid email"
        return False, "Invalid email format"
```

---

## 3. Stories 拆分

### Story 1: 配置读取 API

**优先级:** P0  
**工作量:** 2 天

**任务:**
- 实现 `/settings` 获取端点
- ConfigManager 配置读取逻辑
- 敏感信息脱敏
- 编写读取测试

### Story 2: 配置更新 API

**优先级:** P0  
**工作量:** 3 天

**任务:**
- 实现配置更新端点
- 配置写入和持久化
- 配置验证逻辑
- 编写更新测试

### Story 3: 配置加密存储

**优先级:** P0  
**工作量:** 2 天

**任务:**
- 集成 Fernet 加密
- 敏感配置自动加密
- 解密逻辑实现
- 密钥管理方案
- 编写加密测试

### Story 4: 配置验证

**优先级:** P1  
**工作量:** 2 天

**任务:**
- URL/Email/Port 验证器
- 配置格式校验
- 必填项检查
- 编写验证测试

### Story 5: 配置备份恢复

**优先级:** P1  
**工作量:** 2 天

**任务:**
- 配置备份接口
- 备份文件管理
- 配置恢复逻辑
- 编写备份测试

### Story 6: 配置审计日志

**优先级:** P2  
**工作量:** 1 天

**任务:**
- 配置变更日志记录
- 审计日志格式定义
- 日志查询接口
- 编写日志测试

---

## 4. 依赖关系

### 技术依赖

- **Python ConfigParser** - INI 文件解析
- **Cryptography (Fernet)** - 配置加密
- **FastAPI** 0.104+

### 模块依赖

- **日志模块** - 记录配置变更
- **API Key 认证** - 接口安全

---

## 5. 风险与挑战

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 配置文件损坏 | 高 | 自动备份，校验和验证 |
| 加密密钥泄露 | 高 | 环境变量存储，定期轮换 |
| 配置错误导致系统不可用 | 高 | 配置验证，灰度更新 |
| 并发写入冲突 | 中 | 文件锁机制 |

---

## 6. 测试策略

### 单元测试
- 配置读取/写入
- 加密/解密逻辑
- 验证规则

### 集成测试
- 完整配置更新流程
- 配置备份恢复
- 配置验证场景

---

## 7. 监控指标

```python
config_read_total                      # 配置读取次数
config_update_total                    # 配置更新次数
config_validation_failed_total         # 配置验证失败次数
config_backup_total                    # 配置备份次数
```

---

## 附录

### A. 错误码定义

| 错误码 | HTTP | 说明 |
|--------|------|------|
| CONFIG_NOT_FOUND | 404 | 配置项不存在 |
| CONFIG_INVALID_FORMAT | 400 | 配置格式无效 |
| CONFIG_VALIDATION_FAILED | 400 | 配置验证失败 |
| CONFIG_BACKUP_FAILED | 500 | 配置备份失败 |

### B. 相关文档

- [PRD - 系统管理](../prd.md#23-系统管理)
- [配置管理最佳实践](../standards/config-management.md)

---

**文档维护:** PM Agent  
**最后更新:** 2026-01-05
