# 所有常量统一定义区

# 接口返回值定义
# 成功
RETURN_SUCCESS = 0
# 失败
RETURN_FAIL = -1

# 应用状态定义
# 应用启动中 installing
APP_READY = 0
# 应用正在运行 running
APP_RUNNING = 1
# 应用已经停止 stop
APP_STOP = 2
# 应用等待安装 waiting
APP_WAIT = 3
# 应用错误或不存在 容器一直restart
APP_ERROR = -1

# 应用正在运行状态定义 (pulling,creating,initing,running)
APP_RUNNING_STATE_PULLING = 10
APP_RUNNING_STATE_CREATing = 11
APP_RUNNING_STATE_INITING = 12
APP_RUNNING_STATE_RUNNING = 13



