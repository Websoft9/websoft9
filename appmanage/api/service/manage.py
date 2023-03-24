import os
import io
import sys
import platform
import shutil
import time
import subprocess
import json
import datetime
import socket
import re
from threading import Thread
from api.utils import shell_execute, network, docker, const
from api.model.app import App
from api.model.response import Response
from api.utils import lock

# 获取所有app的信息
def get_my_app():

    ret = Response(code=const.RETURN_FAIL, message="app查询失败")

    # get all info
    cmd = "docker compose ls -a --format json"
    output = shell_execute.execute_command_output_all(cmd)
    if int(output["code"]) == 0:
        output_list = json.loads(output["result"])
        list = []
        list = set_app_info(output_list)
        ret = Response(code=const.RETURN_SUCCESS, message="app查询成功", data=list)
    ret = ret.dict()
    return ret

# 获取具体某个app的信息
def get_app_detail(app_id):

    ret = Response(code=const.RETURN_FAIL, message="app查询失败")

    # get all info
    cmd = "docker compose ls -a --format json"
    output = shell_execute.execute_command_output_all(cmd)
    if int(output["code"]) == 0:
        output_list = json.loads(output["result"])
        list = []
        list = set_app_info(output_list)
        flag = 0
        for app in list:
            if app["app_id"] == app_id:
                list.clear()
                list.append(app)
                flag = 1
                break
        if flag == 1:
            ret = Response(code=const.RETURN_SUCCESS, message="app查询成功", data=list)
    ret = ret.dict()
    return ret

# 查询某个正在安装的app的 具体状态：waiting（等待安装）pulling（拉取镜像）initing（初始化）running（正常运行）
def install_app_process(app_id):
    app_name = split_app_id(app_id)
    real_name = docker.read_var(app_name, 'name')
    if docker.check_app_directory(app_name):
        percentage = docker.get_process_perc(app_name, real_name)
        ret = Response(code=const.RETURN_SUCCESS, message=percentage)
        ret = ret.dict()
    else:
        ret = Response(code=const.RETURN_FAIL, message="目前没有安装此App")
        ret = ret.dict()
    return ret

def install_app(app_name, customer_app_name, app_version):
    ret = Response(code=const.RETURN_FAIL, message=" ")
    ret.code, ret.message = check_app(app_name, customer_app_name, app_version)
    if ret.code == const.RETURN_SUCCESS:
        ret.code, ret.message = prepare_app(app_name, customer_app_name)
        if ret.code == const.RETURN_SUCCESS:
            t1 = Thread(target=install_app_job, args=(customer_app_name, app_version,))
            t1.start()
            ret.message="应用正在启动中，请过几分钟再查询"
    ret = ret.dict()
    return ret

def start_app(app_id):
    ret = Response(code=const.RETURN_FAIL, message="")
    app_name = split_app_id(app_id)
    if if_app_exits(app_id, app_name):
        docker.check_app_compose(app_name)
        cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml start"
        output = shell_execute.execute_command_output_all(cmd)
        if int(output["code"]) == 0:
            ret.code = const.RETURN_SUCCESS
            ret.message = "应用启动成功"
        else:
            ret.message = "应用启动失败"
    else:
        ret.message = "app应用没有安装"
    ret = ret.dict()
    return ret


def stop_app(app_id):
    ret = Response(code=const.RETURN_FAIL, message="")
    app_name = split_app_id(app_id)
    if if_app_exits(app_id, app_name):
        cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml stop"
        output = shell_execute.execute_command_output_all(cmd)
        if int(output["code"]) == 0:
            ret.code = const.RETURN_SUCCESS
            ret.message = "应用停止成功"
        else:
            ret.message = "应用停止失败"
    else:
        ret.message = "app应用没有安装"
    ret = ret.dict()
    return ret


def restart_app(app_id):
    ret = Response(code=const.RETURN_FAIL, message="")
    app_name = split_app_id(app_id)
    if if_app_exits(app_id, app_name):
        cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml restart"
        output = shell_execute.execute_command_output_all(cmd)
        if int(output["code"]) == 0:
            ret.code = const.RETURN_SUCCESS
            ret.message = "应用重启成功"
        else:
            ret.message = "应用重启失败"
    else:
        ret.message = "app应用没有安装"
    ret = ret.dict()
    return ret


def uninstall_app(app_id):
    ret = Response(code=const.RETURN_FAIL, message="")
    if_stopped = stop_app(app_id)   # stop_app
    app_name = split_app_id(app_id)
    real_name = app_id.split("_")[0]
    if if_stopped["code"] == 0:
        cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml down -v"
        if real_name != app_name:
            cmd = cmd + " && sudo rm -rf /data/apps/" + app_name
        output = shell_execute.execute_command_output_all(cmd)
        if int(output["code"]) == 0:
            ret.code = 0
            ret.message = "应用删除成功"
        else:
            ret.message = "应用删除失败"
    else:
        ret.message = if_stopped["message"]
    ret = ret.dict()
    return ret
def check_app(app_name, customer_app_name, app_version):
    message = " "
    code = const.RETURN_FAIL
    install_path = "/data/apps/" + customer_app_name
    if app_name==None or customer_app_name==None or app_version==None:
        message = "请将APP信息填写完整"
    elif not docker.check_app_directory(app_name):
        message = "不支持安装该APP"
    elif re.match('^[a-z0-9]+$', customer_app_name)==None:
        message = "应用名称必须为小写字母和数字"
    elif docker.check_app_directory(install_path):
        message = "APP名称已经使用，请指定其他名称重新安装。"
    elif not docker.check_vm_resource(app_name):
        message = "系统资源(内存、CPU、磁盘)不足，继续安装可能导致应用无法运行或服务器异常！"
    else:
        code = const.RETURN_SUCCESS
    return code, message


def prepare_app(app_name, customer_app_name):
    library_path = "/data/apps/docker-library/" + app_name
    install_path = "/data/apps/" + customer_app_name
    message = " "
    code = const.RETURN_SUCCESS
    output = shell_execute.execute_command_output_all("cp -r " + library_path + " " + install_path)
    if int(output["code"]) != 0:
        message = "创建" + customer_app_name + "目录失败"
        code = const.RETURN_FAIL
    return code, message

def install_app_job(customer_app_name, app_version):
    file_path = "/data/apps/running_apps.txt"
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(customer_app_name + "\n")
    # modify env
    env_path = "/data/apps/" + customer_app_name + "/.env"
    docker.modify_env(env_path, 'APP_NAME', customer_app_name)
    docker.modify_env(env_path, "APP_VERSION", app_version)
    # check port
    docker.check_app_compose(customer_app_name)
    # modify running_apps.txt
    cmd = "cd /data/apps/" + customer_app_name + " && sudo docker compose up -d"
    shell_execute.execute_command_output_all(cmd)
    file_data = ""
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if re.match("^" + customer_app_name + "$", line):
                line = line.replace(line, "")
            file_data += line
    with open("test.txt", "w", encoding="utf-8") as f:
        f.write(file_data)


def if_app_exits(app_id, app_name):
    cmd = "docker compose ls -a | grep \'"+app_name+"\\b\'"
    output = shell_execute.execute_command_output_all(cmd)
    if int(output["code"]) == -1:
        return False
    else:
        real_name = docker.read_var(app_name, "name")
        real_id = real_name + "_" + app_name
        if app_id == real_id:
            return True
        else:
            return False

def split_app_id(app_id):
    return app_id.split("_")[1]

def set_app_info(output_list):
    ip_result = shell_execute.execute_command_output_all("curl ifconfig.me")
    ip = ip_result["result"]
    app_list = []
    has_add = []
    for app_info in output_list:
        volume = app_info["ConfigFiles"]  # volume
        app_name = volume.split('/')[3]
        real_name = docker.read_var(app_name, 'name')
        image_url = get_Image_url(real_name)
        # get trade_mark
        trade_mark = docker.read_var(app_name, 'trademark')
        app_id = real_name + "_" + app_name  # app_id
        case = app_info["Status"].split("(")[0]  # case
        if case == "running":
            case_code = const.RETURN_RUNNING  # case_code
        elif case == "exited":
            case = "stop"
            case_code = const.RETURN_STOP
        elif case == "created":
            case_code = const.RETURN_READY
            case = "installing"
        else:
            case_code = const.RETURN_ERROR
        # get env info
        path = "/data/apps/" + app_name + "/.env"
        port = 0
        url = "-"
        admin_url = "-"
        # get port and url
        try:
            http_port = list(docker.read_env(
                path, "APP_HTTP_PORT").values())[0]
            port = int(http_port)
            easy_url = "http://" + ip + ":" + str(port)
            url = get_url(real_name, easy_url)
            admin_url = get_admin_url(real_name, url)
        except IndexError:
            try:
                db_port = list(docker.read_env(
                    path, "APP_DB.*_PORT").values())[0]
                port = int(db_port)
            except IndexError:
                pass
        # get user_name
        user_name = "-"
        try:
            user_name = list(docker.read_env(path, "APP_USER").values())[0]
        except IndexError:
            pass
        # get password
        password = "-"
        try:
            password = list(docker.read_env(
                path, "POWER_PASSWORD").values())[0]
        except IndexError:
            pass

        has_add.append(app_name)
        app = App(app_id=app_id, name=real_name, customer_name=app_name, status_code=case_code, status=case, port=port, volume=volume, url=url,
                  image_url=image_url, admin_url=admin_url, trade_mark=trade_mark, user_name=user_name, password=password)
        app_list.append(app.dict())

    file_path = "/data/apps/running_apps.txt"
    if os.path.exists(file_path) and os.path.getsize(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            for running_app_name in f:
                running_app_name = re.sub("\n", "", running_app_name)
                if running_app_name not in has_add and running_app_name != "":
                    trade_mark = docker.read_var(running_app_name, 'trademark')
                    real_name = docker.read_var(running_app_name, 'name')
                    image_url = get_Image_url(real_name)
                    app = App(app_id=real_name + "_" + running_app_name, name=real_name, customer_name=running_app_name, status_code=const.RETURN_READY, status="installing", port=0, volume="-",
                              url="-", image_url=image_url, admin_url="-", trade_mark=trade_mark, user_name="-", password="-")
                    app_list.append(app.dict())
    return app_list

def get_Image_url(app_name):

    image_url = "/static/" + app_name + "-websoft9.png"

    return image_url

def get_url(app_name, easy_url):

    url = easy_url
    if app_name == "joomla":
        url = easy_url + "/administrator"
    elif app_name == "other":
        url = easy_url + "/administrator"
    else:
        url = easy_url
    return url


def get_admin_url(app_name, url):

    admin_url = "-"
    if app_name == "wordpress":
        admin_url = url + "/wp-admin"
    elif app_name == "other":
        admin_url = url + "/admin"
    else:
        admin_url = "-"
    return admin_url
