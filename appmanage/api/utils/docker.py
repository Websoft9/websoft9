import os, io, sys, platform, shutil, time, json, datetime
import re, docker, requests
from api.utils import shell_execute
from dotenv import load_dotenv, find_dotenv
import dotenv
from pathlib import Path
from api.utils.common_log import myLogger


def pull_images(app_name):
    # 备用方法
    # 为了防止安装前，用户服务器已经有了镜像。导致安装时镜像不重新拉取，镜像是老的（根据docker-compose.yml 和 .env 获取）
    myLogger.info_logger("Pull images complete ...")


def delete_images(app_id):
    # 备用方法
    # 卸载APP时同时删除dockercompose里面对应的镜像（根据docker-compose.yml 和 .env 获取）
    myLogger.info_logger("Delete images complete ...")


def get_process_perc(app_name, real_name):
    
    process_now = "pulling"

    if if_app_exits(app_name):
        process_now = "creating"

    if if_app_running(app_name):
        process_now = "initing"
        if if_app_access(app_name):
          process_now = "running"
        
    return process_now

# 已经是running的app怎么知道它已经能够访问，如页面能进入，如mysql能被客户端连接
def if_app_access(app_name):
    return True
    
def if_app_exits(app_name):
    cmd = "docker compose ls -a | grep \'" + app_name + "\\b\'"
    output = shell_execute.execute_command_output_all(cmd)
    if int(output["code"]) == -1:
        return False
    else:
        return True

def if_app_running(app_name):
    cmd = "docker compose ls -a |grep running | grep \'" + app_name + "\\b\'"
    output = shell_execute.execute_command_output_all(cmd)
    if int(output["code"]) == -1:
        return False
    else:
        return True
    
def check_app_id(app_id):
    myLogger.info_logger("Checking app id ...")
    if app_id == None:
        myLogger.info_logger("Check complete: AppID is none!")
        return False
    if re.match('^[a-zA-Z0-9]+_[a-z0-9]+$', app_id) == None:
        myLogger.info_logger("Check complete: AppID is not compliant")
        return False
    myLogger.info_logger("Check complete.")
    return True


def check_vm_resource(app_name):
    myLogger.info_logger("Checking virtual memory resource ...")
    var_path = "/data/library/apps/" + app_name + "/variables.json"
    requirements_var = read_var(var_path, 'requirements')
    need_cpu_count = int(requirements_var['cpu'])
    cpu_count = int(shell_execute.execute_command_output_all("cat /proc/cpuinfo | grep \'core id\'| wc -l")["result"])
    if cpu_count < need_cpu_count:
        myLogger.info_logger("Check complete: The number of CPU cores is insufficient!")
        return False
    need_mem_total = int(requirements_var['memory'])
    mem = shell_execute.execute_command_output_all("free -m | grep Mem")["result"].split()
    mem_total = float(mem[1]) / 1024
    if mem_total < need_mem_total:
        myLogger.info_logger("Check complete: The total amount of memory is insufficient!")
        return False
    mem_free = float(mem[3]) / 1024
    if need_mem_total > 4 and mem_free < 4:
        myLogger.info_logger("Check complete: There is not enough memory left!")
        return False
    need_disk = int(requirements_var['disk'])
    disk_free = float(
        shell_execute.execute_command_output_all("df -m --output=avail /")["result"].split("\n")[1]) / 1024
    if disk_free < need_disk - 17:
        myLogger.info_logger("Check complete: There are not enough disks left!")
        return False
    myLogger.info_logger("Check complete.")
    return True


def check_app_directory(app_name):
    # websoft9's support applist
    myLogger.info_logger("Checking dir...")
    path = "/data/library/apps/" + app_name
    is_exists = check_directory(path)
    return is_exists


def check_directory(path):
    output = shell_execute.execute_command_output_all("ls " + path)
    if int(output["code"]) == 0:
        return True
    else:
        return False


def check_app_compose(path):
    myLogger.info_logger("Checking port...")
    port_dic = read_env(path, "APP_.*_PORT")
    # 1.判断/data/apps/app_name/.env中的port是否占用，没有被占用，方法结束（get_start_port方法）
    for port_name in port_dic:
        port_value = get_start_port(port_dic[port_name])
        modify_env(path, port_name, port_value)
    myLogger.info_logger("Port check complete")
    return


def check_app_url(customer_app_name):
    myLogger.info_logger("Checking app url...")

    # 如果app的.env文件中含有HTTP_URL项目,需要如此设置 HTTP_URL=ip:port
    env_path = "/data/apps/" + customer_app_name + "/.env"
    if read_env(env_path, "HTTP_URL") != {}:
        ip = shell_execute.execute_command_output_all("curl ifconfig.me")["result"]
        http_port = list(read_env(path, "APP_HTTP_PORT").values())[0]
        url = ip + ":" + http_port
        modify_env(path, "HTTP_URL", url)

    myLogger.info_logger("App url check complete")
    return


def read_env(path, key):
    myLogger.info_logger("Read " + path)
    output = shell_execute.execute_command_output_all("cat " + path + "|grep " + key)
    code = output["code"]
    env_dic = {}
    if int(code) == 0 and output["result"] != "":
        ret = output["result"]
        env_list = ret.split()
        for env in env_list:
            env_dic[env.split("=")[0]] = env.split("=")[1]
    myLogger.info_logger("Read " + path + ": " + str(env_dic))
    return env_dic


def modify_env(path, env_name, value):
    myLogger.info_logger("Modify " + path + "...")
    output = shell_execute.execute_command_output_all("sed -n \'/^" + env_name + "/=\' " + path)
    if int(output["code"]) == 0 and output["result"] != "":
        line_num = output["result"].split("\n")[0]
        s = env_name + "=" + value
        output = shell_execute.execute_command_output_all("sed -i \'" + line_num + "c " + s + "\' " + path)
        if int(output["code"]) == 0:
            myLogger.info_logger("Modify " + path + ": Change " + env_name + " to " + value)


def read_var(var_path, var_name):
    value = ""
    myLogger.info_logger("Read " + var_path)
    output = shell_execute.execute_command_output_all("cat " + var_path)
    if int(output["code"]) == 0:
        var = json.loads(output["result"])
        try:
            value = var[var_name]
        except KeyError:
            myLogger.warning_logger("Read " + var_path + ": No key " + var_name)
    else:
        myLogger.warning_logger(var_path + " not found")
    return value


def get_start_port(port):
    use_port = port
    while True:
        cmd = "netstat -ntlp | grep -v only"
        output = shell_execute.execute_command_output_all(cmd)
        if output["result"].find(use_port) == -1:
            break
        else:
            use_port = str(int(use_port) + 1)

    return use_port
