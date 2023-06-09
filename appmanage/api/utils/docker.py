import os, io, sys, platform, shutil, time, json, datetime, psutil
import re, docker, requests
from api.utils import shell_execute
from dotenv import load_dotenv, find_dotenv
import dotenv
from pathlib import Path
from api.utils.common_log import myLogger
from api.utils import shell_execute, const
from api.exception.command_exception import CommandException
from api.service import manage


# 已经是running的app怎么知道它已经能够访问，如页面能进入，如mysql能被客户端连接
def if_app_access(app_name):
    return True


def if_app_exits(app_name):
    cmd = "docker compose ls -a"
    output = shell_execute.execute_command_output_all(cmd)
    if int(output["code"]) == 0:
        pattern = app_name + '$'
        info_list = output['result'].split()
        is_exist = False
        for info in info_list:
            if re.match(pattern, info) != None:
                is_exist = True
                break
        return is_exist
    else:
        return True


def if_app_running(app_name):
    cmd = "docker compose ls -a"
    output = shell_execute.execute_command_output_all(cmd)
    if int(output["code"]) == 0:
        app_list = output['result'].split("\n")
        pattern = app_name + '\s*'
        if_running = False
        for app in app_list:
            if re.match(pattern, app) != None and re.match('running', app) != None:
                if_running = True
                break
        return if_running
    else:
        return False


def check_appid_exist(app_id):
    myLogger.info_logger("Checking check_appid_exist ...")
    appList = manage.get_my_app()
    find = False
    for app in appList:
        if app_id == app.app_id:
            find = True
            break
    myLogger.info_logger("Check complete.")
    return find


def check_appid_include_rq(app_id):
    message = ""
    code = None
    if app_id == None or app_id == "undefine":
        code = const.ERROR_CLIENT_PARAM_BLANK
        message = "AppID is null"
    elif re.match('^[a-z0-9]+_[a-z0-9]+$', app_id) == None:
        code = const.ERROR_CLIENT_PARAM_Format
        message = "App_id format error"
    elif not check_appid_exist(app_id):
        code = const.ERROR_CLIENT_PARAM_NOTEXIST
        message = "AppID is not exist"
    return code, message


def check_app_id(app_id):
    message = ""
    code = None
    if app_id == None:
        code = const.ERROR_CLIENT_PARAM_BLANK
        message = "AppID is null"
    elif re.match('^[a-z0-9]+_[a-z0-9]+$', app_id) == None:
        code = const.ERROR_CLIENT_PARAM_Format
        message = "APP name can only be composed of numbers and lowercase letters"
    myLogger.info_logger(code)
    return code, message


def check_vm_resource(app_name):
    myLogger.info_logger("Checking virtual memory resource ...")
    var_path = "/data/library/apps/" + app_name + "/variables.json"
    requirements_var = read_var(var_path, 'requirements')
    need_cpu_count = int(requirements_var['cpu'])
    cpu_count = int(shell_execute.execute_command_output_all("cat /proc/cpuinfo | grep \'core id\'| wc -l")["result"])
    if cpu_count < need_cpu_count:
        myLogger.info_logger("Check complete: The number of CPU cores is insufficient!")
        return False
    need_mem_total = int(requirements_var['memory'])
    mem_free = float(psutil.virtual_memory().available) / 1024 / 1024 / 1024
    if mem_free < need_mem_total * 1.2:
        myLogger.info_logger("Check complete: The total amount of memory is insufficient!")
        return False
    need_disk = int(requirements_var['disk'])
    disk_free = float(psutil.disk_usage('/').free) / 1024 / 1024 / 1024
    if round(disk_free) < need_disk + 2:
        myLogger.info_logger("Check complete: There are not enough disks left!")
        return False
    myLogger.info_logger("Check complete.")
    return True


def check_app_websoft9(app_name):
    # websoft9's support applist
    myLogger.info_logger("Checking dir...")
    path = "/data/library/apps/" + app_name
    is_exists = check_directory(path)
    return is_exists


def check_directory(path):
    try:
        shell_execute.execute_command_output_all("ls " + path)
        return True
    except CommandException as ce:
        return False


def check_app_compose(app_name, customer_name):
    myLogger.info_logger("Set port and random password ...")
    library_path = "/data/library/apps/" + app_name
    install_path = "/data/apps/" + customer_name
    port_dic = read_env(library_path + '/.env', "APP_.*_PORT=")
    # 1.判断/data/apps/app_name/.env中的port是否占用，没有被占用，方法结束（get_start_port方法）
    cmd1 = "docker container inspect $(docker ps -aq) | grep HostPort | awk \'{print $2}\' | sort -u"
    cmd2 = "netstat -tunlp | grep \"LISTEN\" | awk '{print $4}' | awk -F \":\" '{print $NF}' | sort -u"
    cmd3 = "grep -r \"APP_.*_PORT=\" /data/apps/*/.env | awk -F \"=\" '{print $2}' | sort -u"
    s1 = shell_execute.execute_command_output_all(cmd1)['result'].replace('\"', '')
    s2 = shell_execute.execute_command_output_all(cmd2)['result']
    try:
        s3 = ''
        s3 = shell_execute.execute_command_output_all(cmd3)['result']
    except:
        pass
    s = s1 + '\n' + s2 + '\n' + s3

    shell_execute.execute_command_output_all("cp -r " + library_path + " " + install_path)
    env_path = install_path + "/.env"
    get_map(env_path)
    for port_name in port_dic:
        port_value = get_start_port(s, port_dic[port_name])
        modify_env(install_path + '/.env', port_name, port_value)

    # set random password
    power_password = shell_execute.execute_command_output_all("cat /data/apps/" + customer_name + "/.env")["result"]
    if "POWER_PASSWORD" in power_password:
        try:
            shell_execute.execute_command_output_all("docker rm -f pwgen")
        except Exception:
            pass
        new_password = shell_execute.execute_command_output_all("docker run --name pwgen backplane/pwgen 15")[
                           "result"].rstrip('\n') + "!"
        modify_env(install_path + '/.env', 'POWER_PASSWORD', new_password)
        shell_execute.execute_command_output_all("docker rm -f pwgen")
    env_path = install_path + "/.env"
    get_map(env_path)
    myLogger.info_logger("Port check complete")
    return


def check_app_url(customer_app_name):
    myLogger.info_logger("Checking app url...")
    # 如果app的.env文件中含有HTTP_URL项目,需要如此设置 HTTP_URL=ip:port
    env_path = "/data/apps/" + customer_app_name + "/.env"
    env_map = get_map(env_path)
    if env_map.get("APP_URL_REPLACE") == "true":
        myLogger.info_logger(customer_app_name + "need to change app url...")
        app_url = list(read_env(env_path, "APP_URL=").values())[0]
        ip = "localhost"
        url = ""
        try:
            ip_result = shell_execute.execute_command_output_all("cat /data/apps/w9services/w9appmanage/public_ip")
            ip = ip_result["result"].rstrip('\n')
        except Exception:
            ip = "127.0.0.1"
        http_port = list(read_env(env_path, "APP_HTTP_PORT").values())[0]

        if ":" in app_url:
            url = ip + ":" + http_port
        else:
            url = ip
        cmd = "sed -i 's/APP_URL=.*/APP_URL=" + url + "/g' /data/apps/" + customer_app_name + "/.env"
        shell_execute.execute_command_output_all(cmd)

    myLogger.info_logger("App url check complete")
    return


def get_map(path):
    myLogger.info_logger("Read env_dic" + path)
    output = shell_execute.execute_command_output_all("cat " + path)
    code = output["code"]
    env_dic = {}
    if int(code) == 0:
        ret = output["result"]
        myLogger.info_logger(ret)
        env_list = ret.split("\n")
        for env in env_list:
            if "=" in env:
                env_dic[env.split("=")[0]] = env.split("=")[1]
    myLogger.info_logger(env_dic)
    return env_dic


def read_env(path, key):
    myLogger.info_logger("Read " + path)
    output = shell_execute.execute_command_output_all("cat " + path)
    code = output["code"]
    env_dic = {}
    if int(code) == 0:
        ret = output["result"]
        env_list = ret.split("\n")
        for env in env_list:
            if re.match(key, env) != None:
                env_dic[env.split("=")[0]] = env.split("=")[1]
    myLogger.info_logger("Read " + path + ": " + str(env_dic))
    return env_dic


def modify_env(path, env_name, value):
    myLogger.info_logger("Modify " + path + "...")
    output = shell_execute.execute_command_output_all("sed -n \'/^" + env_name + "/=\' " + path)
    if int(output["code"]) == 0 and output["result"] != "":
        line_num = output["result"].split("\n")[0]
        s = env_name + "=" + value
        output = shell_execute.execute_command_output_all("sed -i \'" + line_num + "c " + s + "\' " + path)
        if int(output["code"]) == 0:
            myLogger.info_logger("Modify " + path + ": Change " + env_name + " to " + value)


def read_var(var_path, var_name):
    value = ""
    myLogger.info_logger("Read " + var_path)
    output = shell_execute.execute_command_output_all("cat " + var_path)
    if int(output["code"]) == 0:
        var = json.loads(output["result"])
        try:
            value = var[var_name]
        except KeyError:
            myLogger.warning_logger("Read " + var_path + ": No key " + var_name)
    else:
        myLogger.warning_logger(var_path + " not found")
    return value


def get_start_port(s, port):
    use_port = port
    while True:
        if s.find(use_port) == -1:
            break
        else:
            use_port = str(int(use_port) + 1)

    return use_port
