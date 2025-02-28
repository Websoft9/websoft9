import uuid

appInstalling = {}              # app installing
appInstallingError = {}         # app install error

MAX_SUB_LOGS = 30  # 每个阶段的最大子日志数量

# Add app to appInstalling
def start_app_installation(app_id, app_name):
    app_uuid = str(uuid.uuid4())
    app = {
        "app_id": app_id,
        "app_name": app_name,
        "app_official": True,
        "status": 3,  # installing
        "logs": []
    }
    appInstalling[app_uuid] = app
    return app_uuid

# Add logs to appInstalling
def add_installing_logs(app_uuid, stage, log):
    if app_uuid in appInstalling:
        app = appInstalling[app_uuid]
        # 查找对应阶段的日志
        stage_log = next((item for item in app["logs"] if item["title"] == stage), None)
        if not stage_log:
            stage_log = {
                "title": stage,
                "sub_logs": []
            }
            app["logs"].append(stage_log)
        if len(stage_log["sub_logs"]) >= MAX_SUB_LOGS:
            stage_log["sub_logs"].pop(0)  # 删除最旧的子日志
        stage_log["sub_logs"].append(log)  # 添加新的子日志


# Remove logs from appInstalling
def remove_installation_logs(app_uuid):
    if app_uuid in appInstalling:
        app = appInstalling[app_uuid]
        for stage_log in app["logs"]:
            stage_log["sub_logs"] = []

# Add app to appInstallingError
def modify_app_information(app_uuid, error):
    # If the app is in appInstalling, remove it
    if app_uuid in appInstalling:
        app = appInstalling.pop(app_uuid)
        app["status"] = 4  # error
        app["error"] = error
        appInstallingError[app_uuid] = app
    # If the app is not in appInstalling but in appInstallingError, modify it
    elif app_uuid in appInstallingError:
        app = appInstallingError[app_uuid]
        app["status"] = 4  # error
        app["error"] = error

# Remove app from appInstalling
def remove_app_installation(app_uuid):
    if app_uuid in appInstalling:
        appInstalling.pop(app_uuid)

# Remove app from appInstallingError
def remove_app_from_errors(app_uuid):
    if app_uuid in appInstallingError:
        appInstallingError.pop(app_uuid)

# Remove app from  appInstallingError by app_id
def remove_app_from_errors_by_app_id(app_id):
    app_uuids_to_remove = [app_uuid for app_uuid, app in appInstallingError.items() if app["app_id"] == app_id]
    for app_uuid in app_uuids_to_remove:
        appInstallingError.pop(app_uuid)
