def get_release_url():
    preview = db.AppSearchPreview().get("preview")
    myLogger.info_logger(preview)
    if preview == "false":
        return const.ARTIFACT_URL
    else:
        return const.ARTIFACT_URL_DEV

def appstore_update():
    myLogger.info_logger("appstore update start...")
    # 当点击appstore升级时，是无条件升级，不需要做版本的判定
    release_url = get_release_url()
    download_url = release_url + "/plugin/appstore/appstore-latest.zip"
    cmd = "cd /opt && rm -rf /opt/appstore* && wget -q " + download_url + " && unzip  -q  appstore-latest.zip "
    shell_execute.execute_command_output_all(cmd)

    shell_execute.execute_command_output_all("rm -rf /usr/share/cockpit/appstore && cp -r /opt/appstore /usr/share/cockpit")
    shell_execute.execute_command_output_all("rm -rf /opt/appstore*")

    library_url = release_url + "/plugin/library/library-latest.zip"
    library_cmd = "cd /opt && rm -rf /opt/library* && wget -q  " + library_url + " && unzip  -q  library-latest.zip "
    shell_execute.execute_command_output_all(library_cmd)
    shell_execute.execute_command_output_all("rm -rf /data/library && cp -r /opt/library /data")
    shell_execute.execute_command_output_all("rm -rf /opt/library*")        
    myLogger.info_logger("auto update success...")

def AppStoreUpdate():
    core_support = AppStoreCore()
    release_url = get_release_url()
    if core_support == "-1":
        raise CommandException(const.ERRORMESSAGE_SERVER_VERSION_NEEDUPGRADE, "You must upgrade websoft9 core", "You must upgrade websoft9 core")
    elif core_support == "1":
        raise CommandException(const.ERRORMESSAGE_SERVER_VERSION_NOTSUPPORT, "core not support,can not upgrade", "core not support,can not upgrade")
    local_path = '/usr/share/cockpit/appstore/appstore.json'
    local_version = "0"
    try:
        op = shell_execute.execute_command_output_all("cat " + local_path)['result']
        local_version = json.loads(op)['Version']
    except:
        local_version = "0.0.0"

    version_cmd = "wget -O appstore.json  " + release_url + "/plugin/appstore/appstore.json  && cat appstore.json"
    latest = shell_execute.execute_command_output_all(version_cmd)['result']
    version = json.loads(latest)['Version']
    if local_version < version:
        appstore_update()
    else:
        myLogger.info_logger("You click update appstore, but not need to update")



def AppPreviewUpdate(preview):
    myLogger.info_logger("AppPreviewUpdate")
    if preview == "true" or preview == "True":
        db.AppUpdatePreview(preview)
        return "true"
    elif preview == "false" or preview == "False":
        db.AppUpdatePreview(preview)
        return "false"
    elif preview == None or preview == "" or preview == "undefine":
        return db.AppSearchPreview().get("preview")
    else:
        raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "preview is true,false,blank", "preview is true,false,blank")

#检查内核VERSION 是否支持Appstore的更新
def AppStoreCore():
    release_url = get_release_url()
    version_cmd = "wget -O appstore.json " + release_url + "/plugin/appstore/appstore.json && cat appstore.json"
    latest = shell_execute.execute_command_output_all(version_cmd)['result']
    most_version = json.loads(latest)['Requires at most']
    least_version = json.loads(latest)['Requires at least']
    now = shell_execute.execute_command_output_all("cat /data/apps/websoft9/version.json")['result']
    now_version = json.loads(now)['VERSION']
    version_str = "now_version:" + now_version + " least_version:" + least_version + " most_version:" + most_version
    myLogger.info_logger(version_str)
    if now_version >= least_version and now_version <= most_version:
        return "0"
    elif now_version < least_version:
        return "-1"
    elif now_version > most_version:
        return "1"
    return "0"

# 获取 核心更新日志
def get_update_list(url: str=None):
    local_path = '/data/apps/websoft9/version.json'
    artifact_url = const.ARTIFACT_URL
    if url:
        artifact_url = url
    
    try:
        op = shell_execute.execute_command_output_all("cat " + local_path)['result']
        local_version = json.loads(op)['VERSION']
    except:
        local_version = "0.0.0"
    version_cmd = f"wget -O version.json {artifact_url}/version.json  && cat version.json"
    latest = shell_execute.execute_command_output_all(version_cmd)['result']
    version = json.loads(latest)['VERSION']
    ret = {}
    ret['local_version'] = local_version
    ret['target_version'] = version
    content = []
    date = ""

    if compared_version(local_version, version) == -1:
        ret['update'] = True
        cmd = f"wget -O CHANGELOG.md {artifact_url}/CHANGELOG.md  && head -n 20 CHANGELOG.md"
        change_log_contents = shell_execute.execute_command_output(cmd)
        change_log = change_log_contents.split('## ')[1].split('\n')
        date = change_log[0].split()[-1]
        for change in change_log[1:]:
            if change != '':
                content.append(change)
    else:
        ret['update'] = False
    ret['date'] = date
    ret['content'] = content
    return ret

# 获取 appstore 更新日志
def get_appstore_update_list():
    release_url = get_release_url()
    local_path = '/usr/share/cockpit/appstore/appstore.json'
    local_version = "0"
    try:
        op = shell_execute.execute_command_output_all("cat " + local_path)['result']
        local_version = json.loads(op)['Version']
    except:
        local_version = "0.0.0"
    
    
    version_cmd = "wget -O appstore.json -N  " + release_url + "/plugin/appstore/appstore.json && cat appstore.json"
    latest = shell_execute.execute_command_output_all(version_cmd)['result']
    version = json.loads(latest)['Version']
    ret = {}
    ret['local_version'] = local_version
    ret['target_version'] = version
    content = []
    date = ""
    core_compare = ""

    if compared_version(local_version, version) == -1:
        ret['update'] = True
        cmd = "wget -O CHANGELOG.md  " + release_url + "/plugin/appstore/CHANGELOG.md  && cat CHANGELOG.md" 
        change_log_contents = shell_execute.execute_command_output_all(cmd)['result']
        change_log = change_log_contents.split('## ')[1].split('\n')
        date = change_log[0].split()[-1]
        for change in change_log[1:]:
            if change != '':
                content.append(change)
        core_compare = AppStoreCore()
    else:
        ret['update'] = False
    ret['date'] = date
    ret['content'] = content
    ret['core_compare'] = core_compare
    return ret


def compared_version(ver1, ver2):
    list1 = str(ver1).split(".")
    list2 = str(ver2).split(".")
    # 循环次数为短的列表的len
    for i in range(len(list1)) if len(list1) < len(list2) else range(len(list2)):
        if int(list1[i]) == int(list2[i]):
            pass
        elif int(list1[i]) < int(list2[i]):
            return -1
        else:
            return 1
    # 循环结束，哪个列表长哪个版本号高
    if len(list1) == len(list2):
        return 0
    elif len(list1) < len(list2):
        return -1
    else:
        return 1