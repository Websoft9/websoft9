import os, io, sys, platform, shutil, time, subprocess, json, datetime
import socket
from api.utils import shell_execute, network, docker
from api.model.app import App
import dotenv
from dotenv import load_dotenv, find_dotenv
from pathlib import Path

# 获取所有app的信息
def get_my_app(app_name=None):
    #{"name":"id",...}
    ip = socket.gethostbyname(socket.gethostname())
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
            load_dotenv(find_dotenv(Path.cwd().joinpath(path)))
            http_port = os.getenv('APP_HTTP_PORT')
            db_port = os.getenv('APP_DB_PORT')
            # get port and url
            if http_port != None:
                port = int(http_port)
                url = "http://"+ip+":"+str(port)
            elif db_port != None:
                port = int(db_port)
                url = "http://" + ip + ":" + str(port)
            else:
                port = 0
                url = "-"
            # get user_name
            user_name = os.getenv('APP_USER')
            if user_name == None:
                user_name = "-"
            # get password
            password = os.getenv('POWER_PASSWORD')
            if password == None:
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
    shell_execute.execute_command_output_all(cmd)
    ret = get_my_app(app_name)
    return ret

