import os, io, sys, platform, shutil, time, subprocess, json, datetime

from api.utils import shell_execute

# 获取所有app的信息
def get_my_app():

    my_cmd = my_app()

    output = shell_execute.execute_command_output_all(my_cmd)
    if int(output["code"]) == 0:
        output_list = output["result"].split()
        print(output_list)
        list = []
        num = int(len(output_list)/3)
        for i in range(1,num):
            app = {}
            app['name'] = output_list[3*i+1]
            app['status_code'] = output_list[3*i+2].split("(")[0]
            app['status'] = output_list[3*i+3]
            list.append(app)
        return list

    return -1


# 生成创建 App 的命令
def my_app():

    my_app_cmd = ''
    my_app_cmd = "sudo docker compose ls"

    return my_app_cmd


# 生成创建 App 的命令
def create_app(app_name):
    print(app_name)

    create_cmd = ''
    create_cmd = "sudo su && cd /data/apps/" + app_name + " && docker compose up -d"

    return create_cmd


# 生成启动 App 的命令
def start_app(app_name):
    print(app_name)

    start_cmd = ''
    start_cmd = "sudo su && docker compose start" + app_name

    return start_cmd


# 生成停止 App 的命令
def stop_app(app_name):
    print(app_name)

    stop_cmd = ''
    stop_cmd = "sudo su && docker compose stop" + app_name

    return stop_cmd
