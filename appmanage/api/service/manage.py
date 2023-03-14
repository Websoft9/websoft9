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
        output_list = output["result"].split("\n")
        list = []
        output_list = output_list[1:-1]
        list = set_app_info(output_list)
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

def set_app_info(output_list):
    ip_result = shell_execute.execute_command_output_all("curl ifconfig.me")
    ip = ip_result["result"]
    app_list = []
    id_dic = get_id_dic()
    for app_info in output_list:
        app_name = app_info.split()[0]  # app_name
        image_url = "https://libs.websoft9.com/Websoft9/logo/product/" + app_name + "-websoft9.png"
        # get trade_mark
        trade_mark = get_trade_mark(app_name)
        id = 0  # id
        id = "0"  # id
        case = app_info.split()[1].split("(")[0]  # case
        if case == "running":
            case_code = const.RETURN_RUNNING  # case_code
            try:
                id = id_dic[app_name]
            except KeyError:
                pass
        elif case == "exited":
            case = "stop"
            case_code = const.RETURN_STOP
        elif case == "installing":
            case_code = const.RETURN_READY
        else:
            case_code = const.RETURN_ERROR
        volume = app_info.split()[-1]  # volume
        # get env info
        path = "/data/apps/" + app_name + "/.env"
        port = 0
        url = "-"
        admin_url = "-"
        # get port and url
        try:
            http_port = list(docker.read_env(path, "APP_HTTP_PORT").values())[0]
            port = int(http_port)
            easy_url = "http://" + ip + ":" + str(port)
            url = get_url(app_name, easy_url)
            admin_url = get_admin_url(app_name, url)
        except IndexError:
            try:
                db_port = list(docker.read_env(path, "APP_DB.*_PORT").values())[0]
                port = int(db_port)
            except IndexError:
                pass
        # get user_name
        user_name = "-"
        try:
            user_name = list(docker.read_env(path, "APP_USER").values())[0]
        except IndexError:
            pass
        # get password
        password = "-"
        try:
            password = list(docker.read_env(path, "POWER_PASSWORD").values())[0]
        except IndexError:
            pass

        app = App(id=id, name=app_name, status_code=case_code, status=case, port=port, volume=volume, url=url,
                  image_url=image_url, admin_url=admin_url, trade_mark=trade_mark, user_name=user_name, password=password)
        app_list.append(app.dict())

    file_path = "/data/apps/running_apps.txt"
    if os.path.exists(file_path) and os.path.getsize(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            for running_app_name in f:
                image_url = "https://libs.websoft9.com/Websoft9/logo/product/" + running_app_name + "-websoft9.png"
                trade_mark = get_trade_mark(app_name)
                app = App(id="0", name=running_app_name, status_code=const.RETURN_READY, status="installing", port=0, volume="-",
                          url="-",image_url=image_url, admin_url="-", trade_mark=trade_mark, user_name="-",password="-")
                app_list.append(app.dict())
    return app_list

def get_id_dic():
    output = shell_execute.execute_command_output_all("docker ps")
    id_dic = {}
    if int(output["code"]) == 0:
        id_op = output["result"].split("\n")
        id_op = id_op[1:-1]
        for i in id_op:
            id_name = i.split()[-1]
            id = i.split()[0]
            id_dic[id_name] = id
    return id_dic

def get_trade_mark(app_name):

    trade_mark = ""
    var_path = "/data/apps/" + app_name + "/variables.json"
    try:
        f = open(var_path, 'r', encoding='utf-8')
        var = json.load(f)
        try:
            trade_mark = var["trademark"]
        except KeyError:
            pass
    except FileNotFoundError:
        pass
    return trade_mark

def get_url(app_name,easy_url):
    
    url = easy_url
    if app_name == "joomla":
        url = easy_url + "/administrator"
    elif app_name == "other":
        url = easy_url + "/administrator"
    else:
        url = easy_url
    return url

def get_admin_url(app_name,url):
    
    admin_url = "-"
    if app_name == "wordpress":
        admin_url = url + "/wp-admin"
    elif app_name == "other":
        admin_url = url + "/admin"
    else:
        admin_url = "-"
    return admin_url

def install_app_process(app_name):

    if docker.check_app_directory(app_name):
        percentage = docker.get_process_perc(app_name)
        ret = Response(code=const.RETURN_SUCCESS, message=percentage)
        ret = ret.dict()
    else:
        ret = Response(code=const.RETURN_FAIL , message="目前没有安装此App")
        ret = ret.dict()
    return ret

def install_app(app_name, customer_app_name, app_version):
    
    runnging_file_path = "/data/apps/running_apps.txt"
    unique_app_path = "/data/apps/"
    
    # 防止app名重复
    if os.path.exists(unique_app_path)
           ret = Response(code=const.RETURN_FAIL , message="APP名称已经使用，请指定其他名称重新安装。")
           ret = ret.dict()
           return ret
    
    if os.path.exists(runnging_file_path) and os.path.getsize(runnging_file_path):
        ret = Response(code=const.RETURN_SUCCESS, message="已有应用正在启动，请稍后再试")
        ret = ret.dict()

    elif docker.check_app_directory(app_name):
        
        if app_name != customer_app_name:
            output = shell_execute.execute_command_output_all("cp -r /data/apps/" + app_name + " /data/apps/" + customer_app_name)
            if int(output["code"]) != 0:
                ret.code = const.RETURN_FAIL
                ret.message = "创建" + customer_app_name + "目录失败."
                ret = ret.dict()
                return ret
  
        # check port
        docker.check_app_compose(customer_app_name)
        if app_version != None:
            path = "/data/apps/"+customer_app_name+"/.env"
            docker.modify_env(path, "APP_VERSION", app_version)
        t1 = Thread(target=record_and_install_app, args=(customer_app_name,))
        t1.start()
        ret = Response(code=const.RETURN_SUCCESS, message="应用正在启动中，请过几分钟再查询")
        ret = ret.dict()
    else:
        ret = Response(code=const.RETURN_FAIL , message="目前不支持安装此App")
        ret = ret.dict()
    return ret

def record_and_install_app(app_name):
    # modify running_apps.txt
    file_path = "/data/apps/running_apps.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(app_name)
    cmd = "cd /data/apps/" + app_name + " && sudo docker compose up -d"
    shell_execute.execute_command_output_all(cmd)
    with open(file_path, "a+", encoding="utf-8") as f:
        f.truncate(0)

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

def delete_app(app_name, delete_flag):
    ret = Response(code=const.RETURN_FAIL, message="")
    if_stopped = stop_app(app_name)
    if if_stopped["code"] == 0:
        if delete_flag == 0:
            cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml down"
        elif delete_flag == 1:
            cmd = "docker compose -f /data/apps/"+app_name+"/docker-compose.yml down -v"
        else:
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
