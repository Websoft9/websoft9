import os, io, sys, platform, shutil, time, subprocess, json, datetime
import socket
from threading import Thread
from api.utils import shell_execute, network, docker
from api.model.app import App

# 获取所有app的信息
def get_my_app(app_name=None):
    #{"name":"id",...}
    ip_result = shell_execute.execute_command_output_all("curl ifconfig.me")
    ip = ip_result["result"]
    ret = {}
    ret["code"] = -1
    ret["message"] = "app查询失败"
    ret["data"] = None

    # get all info
    cmd = "sudo docker compose ls"
    output = shell_execute.execute_command_output_all(cmd)
    if int(output["code"]) == 0:
        output_list = output["result"].split()
        list = []
        output_list = output_list[4:]
        num = int(len(output_list) / 3)
        for i in range(0, num):
            name = output_list[3 * i]   #name
            id = 0  #id
            status = output_list[3 * i + 1].split("(")[0]   #status
            status_code = 0     #status_code
            volume = output_list[3 * i+2]     #volume
            # get env info
            path = "/data/apps/" + name + "/.env"
            http_port_env, http_port = docker.read_env(path, "APP_HTTP_PORT")
            db_port_env, db_port = docker.read_env(path, "APP_DB.*_PORT")
            print(name+": "+ db_port)
            # get port and url
            port = 0
            url = "-"
            if http_port != "":
                port = int(http_port)
                url = "http://"+ip+":"+str(port)
            elif db_port != "":
                port = int(db_port)
                url = "http://" + ip + ":" + str(port)

            # get user_name
            username_env, user_name = docker.read_env(path, "APP_USER")
            if user_name == "":
                user_name = "-"
            # get password
            password_env, password = docker.read_env(path, "POWER_PASSWORD")
            if password == "":
                password = "-"

            app = App(id=id, name=name, status_code=status_code, status=status, port=port, volume=volume, url=url, user_name=user_name, password=password)
            list.append(app.dict())
        flag = 0
        if app_name != None:
            for app in list:
                if app["name"] == app_name:
                    list.clear()
                    list.append(app)
                    flag = 1
                    break
        if app_name == None or flag == 1:
            ret["code"] = 0
            ret["message"] = "app查询成功"
            ret["data"] = list

    return ret

def install_app(app_name):
    # check directory
    docker.create_app_directory(app_name)
    # check port
    docker.check_app_compose(app_name)
    cmd = "cd /data/apps/"+app_name+" && sudo docker compose up -d"
    t1 = Thread(target=shell_execute.execute_command_output_all, args=(cmd,))
    t1.start()
    ret = {}
    ret["code"] = 0
    ret["message"] = "应用正在启动中，请过几分钟再查询"
    ret["data"] = ""
    return ret

def if_app_exits(app_name):
    cmd = "docker compose ls -a | grep \'"+app_name+"\\b\'"
    output = shell_execute.execute_command_output_all(cmd)
    if int(output["code"]) == -1:
        return False
    else:
        return True

def start_app(app_name):
    ret = {}
    ret["code"] = -1
    if if_app_exits(app_name):
        cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml start"
        output = shell_execute.execute_command_output_all(cmd)
        if int(output["code"]) == 0:
            ret["code"] = 0
            ret["message"] = "应用启动成功"
        else:
            ret["message"] = "应用启动失败"
    else:
        ret["message"] = "应用不存在"
    return ret

def stop_app(app_name):
    ret = {}
    ret["code"] = -1
    if if_app_exits(app_name):
        cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml stop"
        output = shell_execute.execute_command_output_all(cmd)
        if int(output["code"]) == 0:
            ret["code"] = 0
            ret["message"] = "应用停止成功"
        else:
            ret["message"] = "应用停止失败"
    else:
        ret["message"] = "应用不存在"
    return ret

def restart_app(app_name):
    ret = {}
    ret["code"] = -1
    if if_app_exits(app_name):
        cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml restart"
        output = shell_execute.execute_command_output_all(cmd)
        if int(output["code"]) == 0:
            ret["code"] = 0
            ret["message"] = "应用重启成功"
        else:
            ret["message"] = "应用重启失败"
    else:
        ret["message"] = "应用不存在"
    return ret

def delete_app(app_name):
    ret = {}
    ret["code"] = -1
    if_stopped = stop_app(app_name)
    if if_stopped["code"] == 0:
        cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml down"
        output = shell_execute.execute_command_output_all(cmd)
        if int(output["code"]) == 0:
            ret["code"] = 0
            ret["message"] = "应用删除成功"
        else:
            ret["message"] = "应用删除失败"
    else:
        ret["message"] = if_stopped["message"]
    return ret
