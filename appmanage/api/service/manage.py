import os, io, sys, platform, shutil, time, subprocess, json, datetime

from api.utils import shell_execute

# 获取我的信息的所有信息
def get_my_app():

    my_cmd = my_app()

    apps_info = shell_execute.execute_CommandReturn(my_cmd)

    return apps_info

# 生成创建 App 的命令
def my_app():

    my_app_cmd = ''
    my_app_cmd = "sudo su && docker compose ls"

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