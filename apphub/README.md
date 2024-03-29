
## apphub cli
```
Usage: apphub [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  genkey     Generate a new API key
  getconfig  Get a config value
  setconfig  Set a config value
```

# 项目结构
## src
- src
  - main.py                                                         # 主程序入口
  - api                                                             # API路由和端点相关的代码(对外发布的API)
    - v1                                                            # 版本1的API路由和端点代码
        - routers                                                   # 版本1的所有路由器
            - app.py                                                # 应用相关的路由和端点代码
                - @router.get("/apps/")                             # 获取所有应用的列表
                - @router.post("/apps/install")                     # 安装新的应用
                - @router.post("/apps/{app_id}/start")              # 启动指定ID的应用
                - @router.post("/apps/{app_id}/stop")               # 停止指定ID的应用
                - @router.post("/apps/{app_id}/restart")            # 重启指定ID的应用
                - @router.post("/apps/{app_id}/redeploy")           # 重新部署指定ID的应用
                - @router.delete("/apps/{app_id}/uninstall")        # 卸载指定ID的应用
            - settings.py                                           # 配置相关的路由和端点代码
                - @router.get("/settings")                          # 获取当前的设置
                - @router.put("/settings")                          # 更新当前的设置
            - proxy.py
                - @router.get("/proxy/{app_id}")                    # 获取指定应用的代理信息
                - @router.post("/proxy/{app_id}")                   # 为指定的应用创建一个新的代理
                - @router.put("/proxy/{app_id}")                    # 更新指定应用的代理信息
                - @router.delete("/proxy/{app_id}")                 # 删除指定应用的代理
    - v2                                                            # 版本2的API路由和端点代码
  - config                                                          # 项目的配置代码，例如环境变量、常量等
    - system.ini                                                    # 系统级别的配置
    - config.ini                                                    # 应用级别的配置
 - core                                                             # 项目的核心代码
    - api_key.py                                                    # 处理API密钥的模块
    - config.py
        - config.get_value()                                        # 获取配置值
        - config.set_value()                                        # 设置配置值
        - config.remove_value()                                     # 删除配置值
        - config.remove_section()                                   # 删除配置的一个区块
    - logger.py                                                     # 日志处理模块
        -logger.access()                                            # 记录访问日志
        -logger.error()                                             # 记录错误日志
  - external                                                        # 与外部系统交互的代码（第三方API）
    - gitea_api.py                                                  # Gitea交互的API调用代码

    - nginx_proxy_manager_api.py                                    # Nginx Proxy Manager交互的API调用代码
        - get_token()                                               # 获取访问Nginx Proxy Manager API的令牌
        - get_proxy_hosts()                                         # 获取所有的代理主机列表
        - create_proxy_host()                                       # 创建一个新的代理主机
        - update_proxy_host()                                       # 更新一个已存在的代理主机
        - delete_proxy_host()                                       # 删除一个已存在的代理主机
    - portainer_api.py                                              # Portainer交互的API调用代码

  - schemas                                                         # 存放Pydantic模型定义，用于请求和响应的数据验证
    - appInstall.py                                                 # 定义与应用安装相关的请求和响应模型
    - proxy.py                                          
  - services                                                        # 存放服务层的代码，处理业务逻辑
    - app_manager.py                                                # 处理应用管理相关的业务逻辑，如应用的查询、创建、卸载、启动、停止、重启、重建等
        - get_app()                                                 # 查询应用
        - install_app()                                             # 创建新的应用
        - uninstall_app()                                           # 卸载已存在的应用
        - start_app()                                               # 启动已存在的应用
        - stop_app()                                                # 停止已运行的应用
        - restart_app()                                             # 重启已存在的应用
        - rebuild_app()                                             # 重建已存在的应用
    - gitea_manager.py                                              # 处理与Gitea相关的业务逻辑，如仓库的创建、删除、更新等
        - get_repo()                                                # 查询仓库
        - create_repo()                                             # 创建新的仓库
        - update_repo()                                             # 更新已存在的仓库
        - delete_repo()                                             # 删除已存在的仓库
    - portainer_manager.py                                          # 处理与Portainer相关的业务逻辑，如Stack的创建、删除、启动、停止、重启，重建等
        - get_stack()                                               # 查询Stack
        - create_stack()                                            # 创建新的Stack
        - delete_stack()                                            # 删除已存在的Stack
        - start_stack()                                             # 启动已存在的Stack
        - stop_stack()                                              # 停止已运行的Stack
        - restart_stack()                                           # 重启已存在的Stack
        - rebuild_stack()                                           # 重建已存在的Stack
    - proxy_manager.py                                              # 处理代理管理相关的业务逻辑，如代理的查询、创建、删除、更新等
        - get_proxy()                                               # 查询代理
        - create_proxy()                                            # 创建新的代理
        - update_proxy()                                            # 更新已存在的代理
        - delete_proxy()                                            # 删除已存在的代理
    - settings_manager.py                                           # 处理设置管理相关的业务逻辑，如设置的读取和更新等
        - get_settings()                                            # 获取设置
        - update_settings()                                         # 更新设置
  - utils                                                           # 存放工具函数和工具类
