import os, io, sys, platform, shutil, time, json, datetime
import re
from api.utils import shell_execute
from api.utils import network

from dotenv import load_dotenv, find_dotenv
import dotenv
from pathlib import Path

def get_process_perc(app_name):
    
    process_now = "0%"

    return process_now

def check_vm_resource():
    # 服务器剩余资源是否足够安装，如cpu，内存，硬盘

    return true

def check_app_directory(app_name):
    # 判断/data/apps/app_name是否已经存在，如果已经存在，方法结束
    print("checking dir...")
    path = "/data/apps/"+app_name
    isexsits = os.path.exists(path)
    return isexsits

def check_app_compose(app_name):
    print("checking port...")
    path = "/data/apps/" + app_name + "/.env"
    http_port_env, http_port = read_env(path, "APP_HTTP_PORT")
    db_port_env, db_port = read_env(path, "APP_DB.*_PORT")
    #1.判断/data/apps/app_name/.env中的port是否占用，没有被占用，方法结束（network.py的get_start_port方法）
    if http_port != "":
        print("check http port...")
        http_port = network.get_start_port(http_port)
        modify_env(path, http_port_env, http_port)
    if db_port != "":
        print("check db port...")
        db_port = network.get_start_port(db_port)
        modify_env(path, db_port_env, db_port)
    print("port check complete")
    return

def read_env(path, key):
    output = shell_execute.execute_command_output_all("cat " + path + "|grep "+ key+ "|head -1")
    code = output["code"]
    env = ""    #the name of environment var
    ret = ""    #the value of environment var
    if int(code) == 0 and output["result"] != "":
        ret = output["result"]
        env = ret.split("=")[0]
        ret = ret.split("=")[1]
        ret = re.sub("'","",ret)
        ret = re.sub("\n","",ret)
    return env, ret

def modify_env(path, env_name, value):
    file_data = ""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if env_name in line:
                line = line.replace(line, env_name + "=" + value+"\n")
            file_data += line
    with open(path, "w", encoding="utf-8") as f:
        f.write(file_data)
