import os, io, sys, platform, shutil, time, json, datetime
from api.utils import shell_execute
from api.utils import network

from dotenv import load_dotenv, find_dotenv
import dotenv
from pathlib import Path

def create_app_directory(app_name):
    # 判断/data/apps/app_name是否已经存在，如果已经存在，方法结束
    print("checking dir...")
    path = "/data/apps/"+app_name
    isexsits = os.path.exists(path)
    if isexsits:
        return
    # 将apps复制到/data目录
    if not os.path.exists("/data"):
        os.makedirs("/data")
        os.makedirs("/data/apps")

    if not os.path.exists("/tmp/docker-library"):
        shell_execute.execute_command_output_all("git clone https://ghproxy.com/https://github.com/Websoft9/docker-library.git /tmp/docker-library")

    shell_execute.execute_command_output_all("cp -r /tmp/docker-library/apps/"+app_name+" /data/apps")

def check_app_compose(app_name):
    print("checking port...")
    path = "/data/apps/" + app_name + "/.env"
    load_dotenv(find_dotenv(Path.cwd().joinpath(path)))
    http_port = os.getenv('APP_HTTP_PORT')
    db_port = os.getenv('APP_DB_PORT')
    #1.判断/data/apps/app_name/.env中的port是否占用，没有被占用，方法结束（network.py的get_start_port方法）
    if http_port != None:
        print("modify http port...")
        http_port = network.get_start_port(http_port)
        dotenv.set_key(path, "APP_HTTP_PORT", http_port)
    if db_port != None:
        print("modify db port")
        db_port = network.get_start_port(db_port)
        dotenv.set_key(path, "APP_DB_PORT", db_port)
    print("port check complete")
    return





