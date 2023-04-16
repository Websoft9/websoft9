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
from rq.registry import StartedJobRegistry, FinishedJobRegistry, DeferredJobRegistry, FailedJobRegistry, ScheduledJobRegistry, CanceledJobRegistry
from api.exception.command_exception import CommandException

# 指定 Redis 容器的主机名和端口
redis_conn = Redis(host='websoft9-redis', port=6379)

# 使用指定的 Redis 连接创建 RQ 队列
q = Queue(connection=redis_conn,default_timeout=3600)

def AppList():
    myLogger.info_logger("Install app ...")
    ret = {}
    ret['ResponseData'] = {}
    app_id = app_name + "_" + customer_name
    ret['ResponseData'] = get_my_app()

# 获取所有app的信息
def get_my_app(app_id):
    myLogger.info_logger("Search all of apps ...")
    cmd = "docker compose ls -a --format json"
    output = shell_execute.execute_command_output_all(cmd)
    output_list = json.loads(output["result"])
    installed_list, has_add = get_apps_from_compose(output_list)
    installing_list = get_apps_from_queue()
    app_list = installed_list + installing_list
    find = False
    if app_id != None:
        for app in app_list:
            if app_id == app.app_id:
                ret = app
                find = True
                break
        if not find:
            raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "This App doesn't exist!", "")
    else:
        ret = app_list

    return ret

# 获取具体某个app的信息
def get_app_status(app_id):
    code, message = docker.check_app_id(app_id)
    customer_app_name = app_id.split('_')[1]
    if code == None:
        app = get_my_app(customer_app_name)
        # 将app_list 过滤出app_id的app，并缩减信息，使其符合文档的要求
        ret = {}
        ret['app_id'] = app.app_id
        app['status'] = app.status
        app['status_reason'] = app.status_reason
    else:
        raise CommandException(code, message, '')

    return ret


def install_app(app_name, customer_name, app_version):
    myLogger.info_logger("Install app ...")
    ret = {}
    ret['ResponseData'] = {}
    app_id = app_name + "_" + customer_name
    ret['ResponseData']['app_id'] = app_id

    code, message = check_app(app_name, customer_name, app_version)
    if code == None:
        q.enqueue(install_app_delay, app_name, customer_name, app_version, job_id=app_id)
    else:
        ret['Error'] = get_error_info(code, message, "")

    return ret

def start_app(app_id):
    code, message = docker.check_app_id(app_id)
    if code == None:
        app_name = split_app_id(app_id)
        info, flag = app_exits_in_docker(app_id)
        if flag:
            app_path = info.split()[-1].rsplit('/', 1)[0]
            cmd = "docker compose -f " + app_path + "/docker-compose.yml start"
            shell_execute.execute_command_output_all(cmd)
        else:
            raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, '')

def stop_app(app_id):
    code, message = docker.check_app_id(app_id)
    if code == None:
        app_name = split_app_id(app_id)
        info, flag = app_exits_in_docker(app_id)
        if flag:
            app_path = info.split()[-1].rsplit('/', 1)[0]
            cmd = "docker compose -f " + app_path + "/docker-compose.yml stop"
            shell_execute.execute_command_output_all(cmd)
        else:
            raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, "")


def restart_app(app_id):
    code, message = docker.check_app_id(app_id)
    if code == None:
        app_name = split_app_id(app_id)
        info, flag = app_exits_in_docker(app_id)
        if flag:
            app_path = info.split()[-1].rsplit('/', 1)[0]
            cmd = "docker compose -f " + app_path + "/docker-compose.yml restart"
            shell_execute.execute_command_output_all(cmd)
        else:
            raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, "")


def delete_app_failedjob(app_id):
    myLogger.info_logger("delete_app_failedjob")


def uninstall_app(app_id):
    code, message = docker.check_appid_include_rq(app_id)
    if code == None:
        app_name = split_app_id(app_id)
        info, code_exist = app_exits_in_docker(app_id)
        if code_exist:
            app_path = info.split()[-1].rsplit('/', 1)[0]
            cmd = "docker compose -f " + app_path + "/docker-compose.yml down -v"
            lib_path = '/data/library/apps/' + app_name
            if app_path != lib_path:
                cmd = cmd + " && sudo rm -rf " + app_path
            shell_execute.execute_command_output_all(cmd)
        else:
            delete_app_failedjob(app_id)
    else:
        raise CommandException(code, message, "")
    return ret

def check_app(app_name, customer_name, app_version):
    message = ""
    code = None
    app_id = app_name + "-" + customer_name
    if app_name == None:
        code = const.ERROR_CLIENT_PARAM_BLANK
        message = "app_name is null"
    elif customer_name == None:
        code = const.ERROR_CLIENT_PARAM_BLANK
        message = "customer_name is null"
    elif app_version == None:
        code = const.ERROR_CLIENT_PARAM_BLANK
        message = "app_version is null"
    elif not docker.check_app_websoft9(app_name):
        code = const.ERROR_CLIENT_PARAM_NOTEXIST
        message = "It is not support to install " + app_name
    elif re.match('^[a-z0-9]+$', customer_name) == None:
        code = const.ERROR_CLIENT_PARAM_Format
        message = "APP name can only be composed of numbers and lowercase letters"
    elif docker.check_directory("/data/apps/" + customer_name):
        code = const.ERROR_CLIENT_PARAM_REPEAT
        message = "Repeat installation: " + customer_name
    elif not docker.check_vm_resource(app_name):
        code = const.ERROR_SERVER_RESOURCE
        message = "Insufficient system resources (cpu, memory, disk space)"
    elif check_app_rq(app_id):
        code = const.ERROR_CLIENT_PARAM_REPEAT
        message = "Repeat installation: " + customer_name

    return code, message

def prepare_app(app_name, customer_name):
    library_path = "/data/library/apps/" + app_name
    install_path = "/data/apps/" + customer_name
    shell_execute.execute_command_output_all("cp -r " + library_path + " " + install_path)

def install_app_delay(app_name, customer_name, app_version):
    job_id = app_name + "_" + customer_name

    try:

        code, message = check_app(app_name, customer_name, app_version)
        if code == None:
            
            myLogger.info_logger("job check ok, continue to install app")
            prepare_app(app_name, customer_name)

            myLogger.info_logger("start JobID=" + job_id)
            # modify env
            env_path = "/data/apps/" + customer_name + "/.env"
            docker.modify_env(env_path, 'APP_NAME', customer_name)
            docker.modify_env(env_path, "APP_VERSION", app_version)
            # check port
            docker.check_app_compose(env_path)

            cmd = "cd /data/apps/" + customer_name + " && sudo docker compose pull && sudo docker compose up -d"
            output = shell_execute.execute_command_output_all(cmd)
            myLogger.info_logger("-------Install result--------")
            myLogger.info_logger(output["code"])
            myLogger.info_logger(output["result"])
        else:
            myLogger.info_logger("job check failed, stop to install app")
            raise CommandException(code, message, "")
    except CommandException as ce:
        uninstall_app(job_id)
        raise CommandException(ce.code, ce.message, ce.detail)
    except Exception as e:
        myLogger.info_logger(customer_name + "install failed!")
        myLogger.error_logger(e)
        uninstall_app(job_id)
        raise CommandException(const.ERROR_SERVER_SYSTEM, "system original error", str(e))


def app_exits_in_docker(app_id):
    customer_name = app_id.split('_')[1]
    app_name = app_id.split('_')[0]
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
            if name == app_name:
                flag = True
        elif app_name == customer_name:
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
        customer_name = volume.split('/')[-2]
        app_id = ""  # app_id
        app_name = ""
        trade_mark = ""
        port = 0
        url = ""
        admin_url = ""
        image_url = ""
        user_name = ""
        password = ""
        official_app = False

        if customer_name in ['appmanage', 'nginxproxymanager',
                             'redis'] and app_path == '/data/apps/stackhub/docker/' + customer_name:
            continue
        # get code
        status = app_info["Status"].split("(")[0]
        if status == "running" or status == "exited" or status == "restarting":
            myLogger.info_logger("ok")
        elif status == "created":
            status = "failed"
        else:
            continue

        var_path = app_path + "/variables.json"
        official_app = check_if_official_app(var_path)
        if official_app:
            app_name = docker.read_var(var_path, 'name')
            app_id = app_name + "_" + customer_name  # app_id
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
                    db_port = list(docker.read_env(path, "APP_DB.*_PORT").values())[0]
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
                password = list(docker.read_env(path, "POWER_PASSWORD").values())[0]
            except IndexError:
                pass

        has_add.append(customer_name)

        running_info = RunningInfo(port=port, compose_file=volume, url=url, admin_url=admin_url,
                                   user_name=user_name, password=password, default_domain="", set_domain="")
        status_reason = StatusReason(Code="", Message="", Detail="")

        app = App(app_id=app_id, name=app_name, customer_name=customer_name, trade_mark=trade_mark, status=status,
                  status_reason=status_reason, official_app=official_app, image_url=image_url,
                  running_info=running_info)
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

def check_app_rq(app_id):
    
    myLogger.info_logger("check_app_rq")

    started = StartedJobRegistry(queue=q)
    failed = FailedJobRegistry(queue=q)
    run_job_ids = started.get_job_ids()
    failed_job_ids = failed.get_job_ids()
    queue_job_ids = q.job_ids
    myLogger.info_logger(queue_job_ids)
    myLogger.info_logger(run_job_ids)
    myLogger.info_logger(failed_job_ids)
    if queue_job_ids and app_id  in queue_job_ids:
        return True 
    if failed_job_ids and app_id in failed_job_ids:
        return True  
    if run_job_ids and app_id in run_job_ids:
        return True 

    return False

def get_apps_from_queue():
    myLogger.info_logger("get queque apps...")
    # 获取 StartedJobRegistry 实例
    started = StartedJobRegistry(queue=q)
    finish = FinishedJobRegistry(queue=q)
    deferred = DeferredJobRegistry(queue=q)
    failed = FailedJobRegistry(queue=q)
    scheduled = ScheduledJobRegistry(queue=q)
    cancel = CanceledJobRegistry(queue=q)

    # 获取正在执行的作业 ID 列表
    run_job_ids = started.get_job_ids()
    finish_job_ids = finish.get_job_ids()
    wait_job_ids = deferred.get_job_ids()
    failed_jobs = failed.get_job_ids()
    scheduled_jobs = scheduled.get_job_ids()
    cancel_jobs = cancel.get_job_ids()

    myLogger.info_logger(q.jobs)
    myLogger.info_logger(run_job_ids)
    myLogger.info_logger(failed_jobs)
    myLogger.info_logger(cancel_jobs)
    myLogger.info_logger(wait_job_ids)
    myLogger.info_logger(finish_job_ids)
    myLogger.info_logger(scheduled_jobs)

    installing_list = []
    for job_id in run_job_ids:
        app = get_installing_app(job_id, 'installing', '""', "", "")
        installing_list.append(app)
    for job in q.jobs:
        app = get_installing_app(job.id, 'installing', "", "", "")
        installing_list.append(app)
    for job_id in failed_jobs:
        job = q.fetch_job(job_id)
        app = get_installing_app(job_id, 'failed', "", "", "")
        installing_list.append(app)

    return installing_list

def get_installing_app(id, status, code, message, detail):
    app_name = id.split('_')[0]
    customer_name = id.split('_')[1]
    var_path = "/data/apps/" + customer_name + "/variables.json"
    trade_mark = docker.read_var(var_path, 'trademark')
    app_name = docker.read_var(var_path, 'name')
    image_url = get_Image_url(app_name)
    running_info = RunningInfo(port=0, compose_file="", url="", admin_url="",
                               user_name="", password="", default_domain="", set_domain="")
    status_reason = StatusReason(Code=code, Message=message, Detail=detail)
    app = App(app_id=app_name + "_" + customer_name, name=app_name, customer_name=customer_name, trade_mark=trade_mark,
              status=status, status_reason=status_reason, official_app=True, image_url=image_url,
              running_info=running_info)
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
