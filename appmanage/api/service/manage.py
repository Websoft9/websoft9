import os
import io
import sys
import platform
import shutil
import time
import subprocess
import json
import datetime
import socket
import re
from threading import Thread
from api.utils import shell_execute, docker, const
from api.model.app import App
from api.model.response import Response
from api.model.running_info import RunningInfo
from api.model.status_reason import StatusReason
from api.utils.common_log import myLogger
from redis import Redis
from rq import Queue, Worker, Connection
from rq.registry import StartedJobRegistry, FinishedJobRegistry, DeferredJobRegistry, FailedJobRegistry, \
    ScheduledJobRegistry

# 指定 Redis 容器的主机名和端口
redis_conn = Redis(host='websoft9-redis', port=6379)

# 使用指定的 Redis 连接创建 RQ 队列
q = Queue(connection=redis_conn)


# 获取所有app的信息
def get_my_app():
    # get all info
    cmd = "docker compose ls -a --format json"
    output = shell_execute.execute_command_output_all(cmd)
    if int(output["code"]) == 0:
        output_list = json.loads(output["result"])
        installed_list, has_add = get_apps_from_compose(output_list)
        installing_list = get_apps_from_queue()         # ------------待改------------
        app_list = installed_list + installing_list
    return app_list


# 获取具体某个app的信息
def get_app_detail(app_id):
    ret = {}
    ret['code'] = const.RETURN_FAIL
    ret['message'] = 'App query failed!'
    ret['data'] = None

    if docker.check_app_id(app_id):
        # get all info
        app_name = split_app_id(app_id)
        info, code = if_app_exits(app_id)
        if code:
            cmd = "docker compose ls -a --format json"
            output = shell_execute.execute_command_output_all(cmd)
            if int(output["code"]) == 0:
                output_list = json.loads(output["result"])
                app_list, has_add = get_apps_from_compose(output_list)
                flag = 0
                app_info = None
                for app in app_list:
                    if app["app_id"] == app_id:
                        app_info = app
                        flag = 1
                        break
                if flag == 1:
                    ret['code'] = const.RETURN_SUCCESS
                    ret['message'] = "The app query is successful."
                    ret['data'] = app_info
                else:
                    ret['message'] = 'This app is not currently installed.'
        else:
            ret['message'] = 'This app is not currently installed.'
    else:
        ret['message'] = "AppID is not legal!"
    return ret


# 查询某个正在安装的app的 具体状态：waiting（等待安装）pulling（拉取镜像）initializing（初始化）running（正常运行）
def install_app_process(app_id):
    ret = {}
    ret['code'] = const.RETURN_FAIL
    ret['message'] = ""
    ret['status'] = ""
    app_name = split_app_id(app_id)
    if docker.check_app_id(app_id):
        info, code = if_app_exits(app_id)
        if code:
            var_path = "/data/apps/" + app_name + "/variables.json"
            real_name = docker.read_var(var_path, 'name')
            app_status = docker.get_process_perc(app_name, real_name)
            ret["code"] = const.RETURN_SUCCESS
            ret['message'] = "This app is installing."
            ret['status'] = app_status
        else:
            ret['message'] = "This app is not currently installed."
    else:
        ret['message'] = "AppID is not legal!"

    ret = ret.dict()
    return ret


def install_app(app_name, customer_name, app_version):
    myLogger.info_logger("Install app ...")
    ret = {}
    ret['ResponseData'] = {}
    app_id = app_name + "_" + customer_name
    ret['ResponseData']['app_id'] = app_id

    code, message, detail = check_app(app_name, customer_name, app_version)

    q.enqueue(install_app_delay, app_name, customer_app_name, app_version, job_id=app_id, timeout=3600)

    ret = ret.dict()
    return ret


def start_app(app_id):
    ret = Response(code=const.RETURN_FAIL, message="")
    if docker.check_app_id(app_id):
        app_name = split_app_id(app_id)
        info, code = if_app_exits(app_id)
        if code:
            app_path = info.split()[-1].rsplit('/', 1)[0]
            docker.check_app_compose(app_path + '/.env')
            cmd = "docker compose -f " + app_path + "/docker-compose.yml start"
            output = shell_execute.execute_command_output_all(cmd)
            if int(output["code"]) == 0:
                ret.code = const.RETURN_SUCCESS
                ret.message = "The app starts successfully."
            else:
                ret.message = "The app failed to start!"
        else:
            ret.message = "This app is not currently installed."
    else:
        ret.message = "AppID is not legal!"
    ret = ret.dict()
    return ret


def stop_app(app_id):
    ret = Response(code=const.RETURN_FAIL, message="")
    if docker.check_app_id(app_id):
        app_name = split_app_id(app_id)
        info, code = if_app_exits(app_id)
        if code:
            app_path = info.split()[-1].rsplit('/', 1)[0]
            cmd = "docker compose -f " + app_path + "/docker-compose.yml stop"
            output = shell_execute.execute_command_output_all(cmd)
            if int(output["code"]) == 0:
                ret.code = const.RETURN_SUCCESS
                ret.message = "The app stopped successfully."
            else:
                ret.message = "App stop failed!"
        else:
            ret.message = "This app is not currently installed."
    else:
        ret.message = 'AppID is not legal!'
    ret = ret.dict()
    return ret


def restart_app(app_id):
    ret = Response(code=const.RETURN_FAIL, message="")
    if docker.check_app_id(app_id):
        app_name = split_app_id(app_id)
        info, code = if_app_exits(app_id)
        if code:
            app_path = info.split()[-1].rsplit('/', 1)[0]
            cmd = "docker compose -f " + app_path + "/docker-compose.yml restart"
            output = shell_execute.execute_command_output_all(cmd)
            if int(output["code"]) == 0:
                ret.code = const.RETURN_SUCCESS
                ret.message = "The app restarts successfully."
            else:
                ret.message = "App restart failed!"
        else:
            ret.message = "This app is not currently installed."
    else:
        ret.message = 'AppID is not legal!'
    ret = ret.dict()
    return ret


def uninstall_app(app_id, delete_image, delete_data):
    ret = Response(code=const.RETURN_FAIL, message="")
    if docker.check_app_id(app_id):
        app_name = split_app_id(app_id)
        if_stopped = stop_app(app_id)  # stop_app
        if if_stopped["code"] == 0:
            info, code = if_app_exits(app_id)
            app_path = info.split()[-1].rsplit('/', 1)[0]
            cmd = "docker compose -f " + app_path + "/docker-compose.yml down -v"
            lib_path = '/data/library/apps/' + app_name
            if app_path != lib_path:
                cmd = cmd + " && sudo rm -rf " + app_path
            output = shell_execute.execute_command_output_all(cmd)
            if int(output["code"]) == 0:
                ret.code = 0
                ret.message = "The app is deleted successfully"
            else:
                ret.message = "App deletion failed!"
        else:
            ret.message = if_stopped["message"]
    else:
        ret.message = 'AppID is not legal!'
    ret = ret.dict()
    return ret


def check_app(app_name, customer_app_name, app_version):
    message = " "
    code = None
    app_id = app_name + "-" + customer_app_name
    if not docker.check_app_websoft9(app_name):
        code = 'Param.AppName.NotExis'
        message = "不支持安装指定的App"
    elif re.match('^[a-z0-9]+$', customer_app_name) == None:
        code = 'Param.CustomerAppName.FormatError'
        message = "用户自定义APP名称只能是数字和小写字母组成"
    elif docker.check_directory("/data/apps/" + customer_app_name):
        code = 'Param.CustomerAppName.Repeat'
        message = "已经安装了此应用，请重新指定APP名称"
    elif not docker.check_vm_resource(app_name):
        code = 'Requirement.NotEnough'
        message = "系统资源（cpu，内存，磁盘空间）不足"
    elif check_app_wait(app_id):
        code = 'Param.CustomerAppName.Wait'
        message = "同名应用已经在安装等待中，请重新指定APP名称"
    return code, message


def prepare_app(app_name, customer_app_name):
    library_path = "/data/library/apps/" + app_name
    install_path = "/data/apps/" + customer_app_name
    message = " "
    code = const.RETURN_SUCCESS
    output = shell_execute.execute_command_output_all("cp -r " + library_path + " " + install_path)
    if int(output["code"]) != 0:
        message = "creating" + customer_app_name + "directory failed!"
        code = const.RETURN_FAIL
    return code, message


def install_app_delay(app_name, customer_app_name, app_version):
    try:
        code, message = check_app(app_name, customer_app_name, app_version)
        if code == const.RETURN_SUCCESS:
            code, message = prepare_app(app_name, customer_app_name)
            if code == const.RETURN_SUCCESS:
                myLogger.info_logger("start job=" + customer_app_name)
                # modify env
                env_path = "/data/apps/" + customer_app_name + "/.env"
                docker.modify_env(env_path, 'APP_NAME', customer_app_name)
                docker.modify_env(env_path, "APP_VERSION", app_version)
                # check port
                docker.check_app_compose(env_path)

                cmd = "cd /data/apps/" + customer_app_name + " && sudo docker compose pull && sudo docker compose up -d"
                output = shell_execute.execute_command_output_all(cmd)
                myLogger.info_logger("install output")
                myLogger.info_logger(output["code"])
                myLogger.info_logger(output["result"])
                if int(output["code"]) != 0 or "error" in output["result"] or "fail" in output["result"]:
                    raise Exception("installfailed!")
                else:
                    return "success"
            else:
                raise Exception("prepare_app failed")
        else:
            raise Exception("resource check failed")
    except Exception as e:
        myLogger.info_logger(customer_app_name + "install failed!")
        myLogger.error_logger(e)
        job_id = app_name + "_" + customer_app_name
        try:
            uninstall_app(job_id)
        except Exception as e:
            myLogger.error_logger(e)
        raise Exception(e)


def if_app_exits(app_id):
    app_name = app_id.split('_')[1]
    real_name = app_id.split('_')[0]
    flag = False
    info = ""
    cmd = "docker compose ls -a | grep \'/" + app_name + "/\'"
    output = shell_execute.execute_command_output_all(cmd)
    if int(output["code"]) == 0:
        info = output["result"]
        app_path = info.split()[-1].rsplit('/', 1)[0]
        is_official = check_if_official_app(app_path + '/variables.json')
        if is_official:
            name = docker.read_var(app_path + '/variables.json', 'name')
            if name == real_name:
                flag = True
        elif real_name == app_name:
            flag = True
    myLogger.info_logger("APP info: " + info)
    return info, flag


def split_app_id(app_id):
    return app_id.split("_")[1]


def get_apps_from_compose(output_list):
    ip_result = shell_execute.execute_command_output_all("curl ifconfig.me")
    ip = ip_result["result"]
    app_list = []
    has_add = []
    for app_info in output_list:
        volume = app_info["ConfigFiles"]  # volume
        app_path = volume.rsplit('/', 1)[0]
        customer_app_name = volume.split('/')[-2]
        app_id = customer_app_name + "_" + customer_app_name  # app_id
        app_name = ""
        trade_mark = ""
        port = 0
        url = ""
        admin_url = ""
        image_url = ""
        user_name = ""
        password = ""
        official_app = False

        if customer_app_name in ['appmanage', 'nginxproxymanager',
                                 'redis'] and app_path == '/data/apps/stackhub/docker/' + customer_app_name:
            continue
        # get code
        case = app_info["Status"].split("(")[0]  # case
        if case == "running":
            case_code = const.APP_RUNNING  # case_code
        elif case == "exited":
            case = "stop"
            case_code = const.APP_STOP
        elif case == "created":
            case_code = const.APP_READY
            case = "installing"
        else:
            case_code = const.APP_ERROR

        var_path = app_path + "/variables.json"
        official_app = check_if_official_app(var_path)
        if official_app:
            app_name = docker.read_var(var_path, 'name')
            app_id = app_name + "_" + customer_app_name  # app_id
            # get trade_mark
            trade_mark = docker.read_var(var_path, 'trademark')
            image_url = get_Image_url(app_name)
            # get env info
            path = app_path + "/.env"
            # get port and url
            try:
                http_port = list(docker.read_env(
                    path, "APP_HTTP_PORT").values())[0]
                port = int(http_port)
                easy_url = "http://" + ip + ":" + str(port)
                url = get_url(app_name, easy_url)
                admin_url = get_admin_url(app_name, url)
            except IndexError:
                try:
                    db_port = list(docker.read_env(
                        path, "APP_DB.*_PORT").values())[0]
                    port = int(db_port)
                except IndexError:
                    pass
            # get user_name
            try:
                user_name = list(docker.read_env(path, "APP_USER").values())[0]
            except IndexError:
                pass
            # get password
            try:
                password = list(docker.read_env(
                    path, "POWER_PASSWORD").values())[0]
            except IndexError:
                pass

        has_add.append(customer_app_name)

        running_info = RunningInfo(port=port, compose_file=volume, url=url, image_url=image_url, admin_url=admin_url,
                                   user_name=user_name, password=password, default_domain="", set_domain="")
        status_reason = StatusReason(Code="", Message="", Detail="")

        app = App(app_id=app_id, name=app_name, customer_name=customer_app_name, trade_mark=trade_mark, status=case,
                  official_app=official_app, running_info=running_info, status_reason=status_reason)
        app_list.append(app.dict())
    return app_list, has_add


def check_if_official_app(var_path):
    if docker.check_directory(var_path):
        if docker.read_var(var_path, 'name') != "" and docker.read_var(var_path, 'trademark') != "" and docker.read_var(
                var_path, 'requirements') != "":
            requirements = docker.read_var(var_path, 'requirements')
            try:
                cpu = requirements['cpu']
                mem = requirements['memory']
                return True
            except:
                return False
    else:
        return False


def check_app_wait(app_id):
    myLogger.info_logger("check_app_wait")
    deferred = DeferredJobRegistry(queue=q)
    wait_job_ids = deferred.get_job_ids()
    if app_id in wait_job_ids:
        return True
    else:
        return False


def get_apps_from_queue():
    myLogger.info_logger("get queque apps...")
    # 获取 StartedJobRegistry 实例
    registry = StartedJobRegistry(queue=q)
    finish = FinishedJobRegistry(queue=q)
    deferred = DeferredJobRegistry(queue=q)
    failed = FailedJobRegistry(queue=q)
    scheduled = ScheduledJobRegistry(queue=q)

    # 获取正在执行的作业 ID 列表
    run_job_ids = registry.get_job_ids()
    finish_job_ids = finish.get_job_ids()
    wait_job_ids = deferred.get_job_ids()
    failed_jobs = failed.get_job_ids()
    scheduled_jobs = scheduled.get_job_ids()

    myLogger.info_logger(q.jobs)
    myLogger.info_logger(wait_job_ids)
    myLogger.info_logger(run_job_ids)
    myLogger.info_logger(finish_job_ids)
    myLogger.info_logger(failed_jobs)
    myLogger.info_logger(scheduled_jobs)

    myLogger.info_logger("----------------------------------------")

    installing_list = []
    for job in run_job_ids:
        app = get_installing_app(job, const.APP_READY, 'installing')
        installing_list.append(app)
    for job in q.jobs:
        app = get_installing_app(job.id, const.APP_WAIT, 'waiting')
        installing_list.append(app)
    for job_id in finish_job_ids:
        job = q.fetch_job(job_id)
        if job.result == "fail":
            app = get_installing_app(job_id, const.APP_ERROR, 'error')
            installing_list.append(app)

    return installing_list


def get_installing_app(id, status_code, status):
    app_name = id.split('_')[0]
    customer_app_name = id.split('_')[1]
    var_path = "/data/apps/" + customer_app_name + "/variables.json"
    trade_mark = docker.read_var(var_path, 'trademark')
    app_name = docker.read_var(var_path, 'name')
    image_url = get_Image_url(app_name)
    running_info = RunningInfo(port=0, compose_file="", url="", image_url=image_url, admin_url="",
                               user_name="", password="", default_domain="", set_domain="")
    status_reason = StatusReason(Code="", Message="", Detail="")
    app = App(app_id=app_name + "_" + customer_app_name, name=app_name, customer_name=customer_app_name,
              trade_mark=trade_mark, status=status, official_app=True, running_info=running_info, status_reason=status_reason)
    return app


def get_Image_url(app_name):
    image_url = "static/images/" + app_name + "-websoft9.png"
    return image_url


def get_url(app_name, easy_url):
    url = easy_url
    if app_name == "joomla":
        url = easy_url + "/administrator"
    elif app_name == "other":
        url = easy_url + "/administrator"
    else:
        url = easy_url
    return url


def get_admin_url(app_name, url):
    admin_url = ""
    if app_name == "wordpress":
        admin_url = url + "/wp-admin"
    elif app_name == "other":
        admin_url = url + "/admin"
    else:
        admin_url = ""
    return admin_url


def get_error_info(code, message, detail):
    error = {}
    error['Code'] = code
    error['Message'] = message
    error['Detail'] = detail
    return error
