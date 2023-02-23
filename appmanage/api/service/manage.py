import os, io, sys, platform, shutil, time, subprocess, json, datetime

from api.utils import shell_execute, network, docker

# 获取所有app的信息
def get_my_app():

    my_cmd = "sudo docker compose ls"
    output = shell_execute.execute_command_output_all(my_cmd)
    ret = read_output(output)
    return ret

def install_app(app_name):
    path = "/data/apps/" + app_name
    isexsits = os.path.exists(path)
    ret = ""
    if not isexsits:
        ret = "app文件不存在，无法安装！"
    else:
        # check port
        docker.check_app_compose(app_name)
        cmd = "cd /data/apps/"+app_name+" && sudo docker compose up -d"
        shell_execute.execute_command_output_all(cmd)
        ret = get_app_status(app_name)
    return ret

def get_app_status(app_name):
    cmd = "sudo docker compose ls | grep "+app_name
    output = shell_execute.execute_command_output_all(cmd)
    ret = read_output(output)
    return ret

def read_output(output):
    if int(output["code"]) == 0:
        output_list = output["result"].split()
        print(output_list)
        ret = {}
        list = []
        num = int(len(output_list)/3)
        start = 1
        if num != 1:
            output_list = output_list[4:]
            num = num-1
        for i in range(0 ,num):
            app = {}
            app['name'] = output_list[3*i]
            app['status_code'] = output_list[3*i+1].split("(")[0]
            app['status'] = output_list[3*i+2]
            list.append(app)
        ret["code"] = 0
        ret["message"] = "app查询成功"
        ret["data"] = list
    else:
        ret = {}
        ret["code"] = -1
        ret["message"] = "app查询失败"
        ret["data"] = None
    return ret