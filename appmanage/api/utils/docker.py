import os, io, sys, platform, shutil, time, json, datetime
import re,docker,requests
from api.utils import shell_execute
from api.utils import network
import psutil as p
from dotenv import load_dotenv, find_dotenv
import dotenv
from pathlib import Path

def get_process_perc(app_name):
    
    process_now = "pulling"
    output = shell_execute.execute_command_output_all("sudo docker image list |grep  " + app_name)
    code = output["code"]
    if int(code) == 0 and output["result"] != "":
        process_now = "starting"
    
    output = shell_execute.execute_command_output_all("docker inspect " +  app_name + "|grep error")
    code = output["code"]
    if int(code) == 0 and output["result"] == "":
        process_now = "Initializing"
    
    return process_now

def check_vm_resource(app_name):
    # 服务器剩余资源是否足够安装，如cpu，内存，硬盘
    p.cpu_percent(None)  # 第一次返回的结果是0
    time.sleep(0.5)
    cpu_percent = p.cpu_percent(None)
    mem = p.virtual_memory()
    mem_total = float(mem.total) / 1024 / 1024 / 1024
    mem_free = float(mem.available) / 1024 / 1024 / 1024
    disk = p.disk_usage('/')
    disk_free = float(disk.free) / 1024 / 1024 / 1024
    if cpu_percent>70 or mem_free<1 or disk_free<5:
        return False
    # read variables.json
    memory = ""
    var_path = "/data/apps/" + app_name + "/variables.json"
    try:
        f = open(var_path, 'r', encoding='utf-8')
        var = json.load(f)
        try:
            trade_mark = var["memory"]
        except KeyError:
            return False
    except FileNotFoundError:
        return False
    if memory == "8" and mem_total<8 and mem_free<4:
        return False
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
    port_dic = read_env(path, "APP_.*_PORT")
    #1.判断/data/apps/app_name/.env中的port是否占用，没有被占用，方法结束（network.py的get_start_port方法）
    for port_name in port_dic:
        port_value = network.get_start_port(port_dic[port_name])
        modify_env(path, port_name, port_value)
    print("port check complete")
    return

def read_env(path, key):
    output = shell_execute.execute_command_output_all("cat " + path + "|grep "+ key)
    code = output["code"]
    env_dic = {}
    if int(code) == 0 and output["result"] != "":
        ret = output["result"]
        env_list = ret.split()
        for env in env_list:
            env_dic[env.split("=")[0]] = env.split("=")[1]
    return env_dic

def modify_env(path, env_name, value):
    file_data = ""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if re.match(env_name, line) != None:
                env_name = line.split("=")[0]
                line = line.replace(line, env_name + "=" + value+"\n")
            file_data += line
    with open(path, "w", encoding="utf-8") as f:
        f.write(file_data)
