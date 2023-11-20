import uuid

appInstalling = {}              # app installing
appInstallingError = {}         # app install error

# Add app to appInstalling
def start_app_installation(app_id, app_name):
    app_uuid = str(uuid.uuid4())
    app = {
        "app_id": app_id,
        "app_name": app_name,
        "app_official": True,
        "status": 3,  # installing
    }
    appInstalling[app_uuid] = app
    return app_uuid

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

