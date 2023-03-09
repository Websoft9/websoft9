import os, io, sys, platform, shutil, time, subprocess, json, datetime
import socket
from threading import Thread
from api.utils import shell_execute, network, docker, const
from api.model.app import App
from api.model.response import Response

# 获取所有app的信息
def get_my_app(app_name=None):
    #{"name":"id",...}
    ret = Response(code=const.RETURN_FAIL, message="app查询失败")

    # get all info
    cmd = "sudo docker compose ls -a"
    output = shell_execute.execute_command_output_all(cmd)
    if int(output["code"]) == 0:
        output_list = output["result"].split()
        list = []
        output_list = output_list[4:]
        num = int(len(output_list) / 3)
        list = set_app_info(output_list, num)
        flag = 0
        if app_name != None:
            for app in list:
                if app["name"] == app_name:
                    list.clear()
                    list.append(app)
                    flag = 1
                    break
        if app_name == None or flag == 1:
            ret = Response(code=const.RETURN_SUCCESS, message="app查询成功", data=list)
    ret = ret.dict()
    return ret

def set_app_info(output_list, num):
    ip_result = shell_execute.execute_command_output_all("curl ifconfig.me")
    ip = ip_result["result"]
    list = []
    for i in range(0, num):
        name = output_list[3 * i]  # name
        image_url = "https://libs.websoft9.com/Websoft9/logo/product/" + name + "-websoft9.png"
        # get trade_mark
        trade_mark = ""
        var_path = "/data/apps/" + name + "/variables.json"
        try:
            f = open(var_path, 'r', encoding='utf-8')
            var = json.load(f)
            try:
                trade_mark = var["trademark"]
            except KeyError:
                pass
        except FileNotFoundError:
            pass
        id = 0  # id
        case = output_list[3 * i + 1].split("(")[0]  # case
        if (case.startswith("r")):
            case_code = const.RETURN_RUNNING  # case_code
        else:
            case = "stop"
            case_code = const.RETURN_STOP
        volume = output_list[3 * i + 2]  # volume
        j = 2
        while not volume.startswith("/"):
            volume = output_list[3 * i + j]
            j = j + 1
        # get env info
        path = "/data/apps/" + name + "/.env"
        http_port_env, http_port = docker.read_env(path, "APP_HTTP_PORT")
        db_port_env, db_port = docker.read_env(path, "APP_DB.*_PORT")
        # get port and url
        port = 0
        url = "-"
        if http_port != "":
            port = int(http_port)
            url = "http://" + ip + ":" + str(port)
        elif db_port != "":
            port = int(db_port)

        # get user_name
        username_env, user_name = docker.read_env(path, "APP_USER")
        if user_name == "":
            user_name = "-"
        # get password
        password_env, password = docker.read_env(path, "POWER_PASSWORD")
        if password == "":
            password = "-"

        app = App(id=id, name=name, status_code=case_code, status=case, port=port, volume=volume, url=url,
                  image_url=image_url, trade_mark=trade_mark, user_name=user_name, password=password)
        list.append(app.dict())
    return list

def install_app(app_name):
    # check directory
    if docker.check_app_directory(app_name):
        # check port
        docker.check_app_compose(app_name)
        cmd = "cd /data/apps/"+app_name+" && sudo docker compose up -d"
        t1 = Thread(target=shell_execute.execute_command_output_all, args=(cmd,))
        t1.start()
        ret = Response(code=const.RETURN_SUCCESS, message="应用正在启动中，请过几分钟再查询")
        ret = ret.dict()
    else:
        ret = Response(code=const.RETURN_FAIL , message="目前不支持安装此App")
        ret = ret.dict()
    return ret

def if_app_exits(app_name):
    cmd = "docker compose ls -a | grep \'"+app_name+"\\b\'"
    output = shell_execute.execute_command_output_all(cmd)
    if int(output["code"]) == -1:
        return False
    else:
        return True

def start_app(app_name):
    ret = Response(code=const.RETURN_FAIL, message="")
    if if_app_exits(app_name):
        docker.check_app_compose(app_name)
        cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml start"
        output = shell_execute.execute_command_output_all(cmd)
        if int(output["code"]) == 0:
            ret.code = const.RETURN_SUCCESS
            ret.message = "应用启动成功"
        else:
            ret.message = "应用启动失败"
    else:
        ret.message = "应用不存在"
    ret = ret.dict()
    return ret

def stop_app(app_name):
    ret = Response(code=const.RETURN_FAIL, message="")
    if if_app_exits(app_name):
        cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml stop"
        output = shell_execute.execute_command_output_all(cmd)
        if int(output["code"]) == 0:
            ret.code = const.RETURN_SUCCESS
            ret.message = "应用停止成功"
        else:
            ret.message = "应用停止失败"
    else:
        ret.message = "应用不存在"
    ret = ret.dict()
    return ret

def restart_app(app_name):
    ret = Response(code=const.RETURN_FAIL, message="")
    if if_app_exits(app_name):
        cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml restart"
        output = shell_execute.execute_command_output_all(cmd)
        if int(output["code"]) == 0:
            ret.code = const.RETURN_SUCCESS
            ret.message = "应用重启成功"
        else:
            ret.message = "应用重启失败"
    else:
        ret.message = "应用不存在"
    ret = ret.dict()
    return ret

def delete_app(app_name):
    ret = Response(code=const.RETURN_FAIL, message="")
    if_stopped = stop_app(app_name)
    if if_stopped["code"] == 0:
        cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml down"
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
