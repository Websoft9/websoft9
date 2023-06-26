import os
import io
import sys
import platform
import shutil
import time
import subprocess
import requests
import json
import datetime
import socket
import re
from threading import Thread
from api.utils import shell_execute, docker, const
from api.model.app import App
from api.model.response import Response
from api.model.config import Config
from api.model.status_reason import StatusReason
from api.utils.common_log import myLogger
from redis import Redis
from rq import Queue, Worker, Connection
from rq.registry import StartedJobRegistry, FinishedJobRegistry, DeferredJobRegistry, FailedJobRegistry, ScheduledJobRegistry, CanceledJobRegistry
from api.exception.command_exception import CommandException
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_SCHEDULER_PAUSED, EVENT_SCHEDULER_RESUMED,EVENT_SCHEDULER_STARTED,EVENT_SCHEDULER_SHUTDOWN

# 指定 Redis 容器的主机名和端口
redis_conn = Redis(host='websoft9-redis', port=6379)

# 使用指定的 Redis 连接创建 RQ 队列
q = Queue(connection=redis_conn, default_timeout=3600)

def auto_update():
    myLogger.info_logger("auto update")
    shell_execute.execute_command_output_all("wget https://websoft9.github.io/StackHub/install/update_appstore.sh && bash update_appstore.sh 1>/dev/null 2>&1")

scheduler = BackgroundScheduler()
scheduler.add_job(auto_update, 'cron', hour=1)
scheduler.start()

# 获取github文件内容
def get_github_content(repo, path):
    url = 'https://websoft9.github.io/{repo}/{path}'
    url = url.format(repo=repo, path=path)
    response = requests.get(url)
    response.encoding = 'utf-8'
    contents = response.text
    return contents

def AppAutoUpdate(auto_update):

    myLogger.info_logger(scheduler.state)
    myLogger.info_logger(scheduler.get_jobs())
    if auto_update == "true" or auto_update == "True":
        scheduler.resume()
        return "true"
    elif auto_update == "false" or auto_update == "False":
        scheduler.pause()
        return "false"
    elif auto_update == None or auto_update == "" or auto_update == "undefine":
        state = scheduler.state
        if state == 1:
          return "true"
        else:
          return "false"

# 更新软件商店
def AppStoreUpdate():
    local_path = '/data/library/install/version.json'
    local_version = "0"
    try:
        op = shell_execute.execute_command_output_all("cat " + local_path)['result']
        local_version = json.loads(op)['VERSION']
    except:
        local_version = "0.0.1"

    repo = 'docker-library'
    version_contents = get_github_content(repo, 'install/version.json')
    version = json.loads(version_contents)['VERSION']

    if compared_version(local_version, version) == -1:
        content = []
        change_log_contents = get_github_content(repo, 'CHANGELOG.md')
        change_log = change_log_contents.split('## ')[1].split('\n')
        for change in change_log[1:]:
            if change != '':
                content.append(change)
        shell_execute.execute_command_output_all("rm -rf /tmp/update_appstore.sh")
        shell_execute.execute_command_output_all("cd /tmp && wget https://websoft9.github.io/StackHub/install/update_appstore.sh")
        shell_execute.execute_command_output_all("bash /tmp/update_appstore.sh 1>/dev/null 2>&1")
        
        return content
    else:
        return None

# 获取 update info
def get_update_list():
    local_path = '/data/apps/stackhub/install/version.json'
    repo = 'StackHub'
    local_version = "0"
    try:
        op = shell_execute.execute_command_output_all("cat " + local_path)['result']
        local_version = json.loads(op)['VERSION']
    except:
        local_version = "0.0.1"
    version_contents = get_github_content(repo, 'install/version.json')
    version = json.loads(version_contents)['VERSION']
    ret = {}
    ret['current_version'] = local_version
    if compared_version(local_version, version) == -1:
        content = []
        change_log_contents = get_github_content(repo, 'CHANGELOG.md')
        change_log = change_log_contents.split('## ')[1].split('\n')
        date = change_log[0].split()[-1]
        for change in change_log[1:]:
            if change != '':
                content.append(change)
        
        ret2= {}
        ret2['latest_version'] = version
        ret2['date'] = date
        ret2['content'] = content
        ret['Update_content']=ret2
        return ret
    else:
        ret['Update_content']=None
        return ret

def conbine_list(installing_list, installed_list):
    app_list = installing_list + installed_list
    result_list = []
    appid_list = []
    for app in app_list:
        app_id = app['app_id']
        if app_id in appid_list:
            continue
        else:
            appid_list.append(app_id)
            result_list.append(app)
    return result_list


# 获取所有app的信息
def get_my_app(app_id):
    installed_list = get_apps_from_compose()
    installing_list = get_apps_from_queue()

    app_list = conbine_list(installing_list, installed_list)
    find = False
    ret = {}
    if app_id != None:
        for app in app_list:
            if app_id == app['app_id']:
                ret = app
                find = True
                break
        if not find:
            raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "This App doesn't exist!", "")
    else:
        ret = app_list
    myLogger.info_logger("app list result ok")
    return ret


# 获取具体某个app的信息
def get_app_status(app_id):
    code, message = docker.check_app_id(app_id)
    if code == None:
        app = get_my_app(app_id)
        # 将app_list 过滤出app_id的app，并缩减信息，使其符合文档的要求
        ret = {}
        ret['app_id'] = app['app_id']
        ret['status'] = app['status']
        ret['status_reason'] = app['status_reason']
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
    info, flag = app_exits_in_docker(app_id)
    if flag:
        app_path = info.split()[-1].rsplit('/', 1)[0]
        cmd = "docker compose -f " + app_path + "/docker-compose.yml start"
        shell_execute.execute_command_output_all(cmd)
    else:
        raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")


def stop_app(app_id):
    info, flag = app_exits_in_docker(app_id)
    if flag:
        app_path = info.split()[-1].rsplit('/', 1)[0]
        cmd = "docker compose -f " + app_path + "/docker-compose.yml stop"
        shell_execute.execute_command_output_all(cmd)
    else:
        raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")


def restart_app(app_id):
    code, message = docker.check_app_id(app_id)
    if code == None:
        info, flag = app_exits_in_docker(app_id)
        if flag:
            app_path = info.split()[-1].rsplit('/', 1)[0]
            cmd = "docker compose -f " + app_path + "/docker-compose.yml restart"
            shell_execute.execute_command_output_all(cmd)
        else:
            raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, "")


def delete_app_failedjob(job_id):
    myLogger.info_logger("delete_app_failedjob")
    failed = FailedJobRegistry(queue=q)
    failed.remove(job_id, delete_job=True)


def delete_app(app_id):
    try:
        app_name = app_id.split('_')[0]
        customer_name = app_id.split('_')[1]
        app_path = ""
        info, code_exist = app_exits_in_docker(app_id)
        if code_exist:
            app_path = info.split()[-1].rsplit('/', 1)[0]
            cmd = "docker compose -f " + app_path + "/docker-compose.yml down -v"
            lib_path = '/data/library/apps/' + app_name
            if app_path != lib_path:
                cmd = cmd + " && sudo rm -rf " + app_path
            try:
                myLogger.info_logger("Intall fail, down app and delete files")
                shell_execute.execute_command_output_all(cmd)
            except Exception:
                myLogger.info_logger("Delete app compose exception")
            # 强制删除失败又无法通过docker compose down 删除的容器
            try:
                myLogger.info_logger("IF delete fail, force to delete containers")
                force_cmd = "docker rm -f $(docker ps -f name=^" + customer_name + " -aq)"
                shell_execute.execute_command_output_all(force_cmd)
            except Exception:
                myLogger.info_logger("force delete app compose exception")

        else:
            if check_app_rq(app_id):
                delete_app_failedjob(app_id)
            else:
                raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "AppID is not exist", "")
        cmd = " sudo rm -rf /data/apps/" + customer_name
        shell_execute.execute_command_output_all(cmd)
    except CommandException as ce:
        myLogger.info_logger("Delete app compose exception")


def uninstall_app(app_id):
    app_name = app_id.split('_')[0]
    customer_name = app_id.split('_')[1]
    app_path = ""
    info, code_exist = app_exits_in_docker(app_id)
    if code_exist:
        app_path = info.split()[-1].rsplit('/', 1)[0]
        cmd = "docker compose -f " + app_path + "/docker-compose.yml down -v"
        lib_path = '/data/library/apps/' + app_name
        if app_path != lib_path:
            cmd = cmd + " && sudo rm -rf " + app_path
        shell_execute.execute_command_output_all(cmd)
    else:
        if check_app_rq(app_id):
            delete_app_failedjob(app_id)
        else:
            raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "AppID is not exist", "")
    # Force to delete docker compose
    try:
        cmd = " sudo rm -rf /data/apps/" + customer_name
        shell_execute.execute_command_output_all(cmd)
    except CommandException as ce:
        myLogger.info_logger("Delete app compose exception")
    # Delete proxy config when uninstall app
    app_proxy_delete(app_id)


def check_app(app_name, customer_name, app_version):
    message = ""
    code = None
    app_id = app_name + "_" + customer_name
    if app_name == None:
        code = const.ERROR_CLIENT_PARAM_BLANK
        message = "app_name is null"
    elif customer_name == None:
        code = const.ERROR_CLIENT_PARAM_BLANK
        message = "customer_name is null"
    elif len(customer_name) < 2:
        code = const.ERROR_CLIENT_PARAM_BLANK
        message = "customer_name must be longer than 2 chars"
    elif app_version == None:
        code = const.ERROR_CLIENT_PARAM_BLANK
        message = "app_version is null"
    elif app_version == "undefined" or app_version == "":
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
    elif check_app_docker(app_id):
        code = const.ERROR_CLIENT_PARAM_REPEAT
        message = "Repeat installation: " + customer_name
    elif check_app_rq(app_id):
        code = const.ERROR_CLIENT_PARAM_REPEAT
        message = "Repeat installation: " + customer_name

    return code, message


def prepare_app(app_name, customer_name):
    library_path = "/data/library/apps/" + app_name
    install_path = "/data/apps/" + customer_name
    shell_execute.execute_command_output_all("cp -r " + library_path + " " + install_path)


def install_app_delay(app_name, customer_name, app_version):
    myLogger.info_logger("-------RQ install start --------")
    job_id = app_name + "_" + customer_name

    try:
        # 因为这个时候还没有复制文件夹，是从/data/library里面文件读取json来检查的，应该是app_name,而不是customer_name
        resource_flag = docker.check_vm_resource(app_name)

        if resource_flag == True:

            myLogger.info_logger("job check ok, continue to install app")
            env_path = "/data/apps/" + customer_name + "/.env"
            # prepare_app(app_name, customer_name)
            docker.check_app_compose(app_name, customer_name)
            myLogger.info_logger("start JobID=" + job_id)
            docker.modify_env(env_path, 'APP_NAME', customer_name)
            docker.modify_env(env_path, "APP_VERSION", app_version)
            docker.check_app_url(customer_name)
            cmd = "cd /data/apps/" + customer_name + " && sudo docker compose pull && sudo docker compose up -d"
            output = shell_execute.execute_command_output_all(cmd)
            myLogger.info_logger("-------Install result--------")
            myLogger.info_logger(output["code"])
            myLogger.info_logger(output["result"])
            try:
                shell_execute.execute_command_output_all("bash /data/apps/" + customer_name + "/src/after_up.sh")
            except Exception as e:
                myLogger.info_logger(str(e))
        else:
            error_info = "##websoft9##" + const.ERROR_SERVER_RESOURCE + "##websoft9##" + "Insufficient system resources (cpu, memory, disk space)" + "##websoft9##" + "Insufficient system resources (cpu, memory, disk space)"
            myLogger.info_logger(error_info)
            raise Exception(error_info)
    except CommandException as ce:
        myLogger.info_logger(customer_name + " install failed(docker)!")
        delete_app(job_id)
        error_info = "##websoft9##" + ce.code + "##websoft9##" + ce.message + "##websoft9##" + ce.detail
        myLogger.info_logger(error_info)
        raise Exception(error_info)
    except Exception as e:
        myLogger.info_logger(customer_name + " install failed(system)!")
        delete_app(job_id)
        error_info = "##websoft9##" + const.ERROR_SERVER_SYSTEM + "##websoft9##" + 'system original error' + "##websoft9##" + str(
            e)
        myLogger.info_logger(error_info)
        raise Exception(error_info)


def app_exits_in_docker(app_id):
    customer_name = app_id.split('_')[1]
    app_name = app_id.split('_')[0]
    flag = False
    info = ""
    cmd = "docker compose ls -a | grep \'/" + customer_name + "/\'"
    try:
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
            myLogger.info_logger("APP in docker")
    except CommandException as ce:
        myLogger.info_logger("APP not in docker")

    return info, flag


def split_app_id(app_id):
    return app_id.split("_")[1]


def get_createtime(official_app, app_path, customer_name):
    data_time = ""
    try:
        if official_app:
            cmd = "docker ps -f name=" + customer_name + " --format {{.RunningFor}}  | head -n 1"
            result = shell_execute.execute_command_output_all(cmd)["result"].rstrip('\n')
            data_time = result
        else:
            cmd_all = "cd " + app_path + " && docker compose ps -a --format json"
            output = shell_execute.execute_command_output_all(cmd_all)
            container_name = json.loads(output["result"])[0]["Name"]
            cmd = "docker ps -f name=" + container_name + " --format {{.RunningFor}}  | head -n 1"
            result = shell_execute.execute_command_output_all(cmd)["result"].rstrip('\n')
            data_time = result

    except Exception as e:
        myLogger.info_logger(str(e))
    myLogger.info_logger("get_createtime get success" + data_time)
    return data_time


def get_apps_from_compose():
    myLogger.info_logger("Search all of apps ...")
    cmd = "docker compose ls -a --format json"
    output = shell_execute.execute_command_output_all(cmd)
    output_list = json.loads(output["result"])
    myLogger.info_logger(len(output_list))
    ip = "localhost"
    try:
        ip_result = shell_execute.execute_command_output_all("cat /data/apps/w9services/w9appmanage/public_ip")
        ip = ip_result["result"].rstrip('\n')
    except Exception:
        ip = "127.0.0.1"

    app_list = []
    for app_info in output_list:
        volume = app_info["ConfigFiles"]
        app_path = volume.rsplit('/', 1)[0]
        customer_name = volume.split('/')[-2]
        app_id = ""
        app_name = ""
        trade_mark = ""
        port = 0
        url = ""
        admin_url = ""
        image_url = ""
        user_name = ""
        password = ""
        official_app = False
        app_version = ""
        create_time = ""
        volume_data = ""
        config_path = app_path
        app_https = False
        app_replace_url = False
        default_domain = ""
        admin_path = ""
        admin_domain_url = ""
        if customer_name in ['w9appmanage', 'w9nginxproxymanager', 'w9redis', 'w9kopia',
                             'w9portainer'] or app_path == '/data/apps/w9services/' + customer_name:
            continue

        var_path = app_path + "/variables.json"
        official_app = check_if_official_app(var_path)

        status_show = app_info["Status"]
        status = app_info["Status"].split("(")[0]
        if status == "running" or status == "exited" or status == "restarting":
            if "exited" in status_show and "running" in status_show:
                if status == "exited":
                    cmd = "docker ps -a  -f name=" + customer_name + " --format {{.Names}}#{{.Status}}|grep Exited"
                    result = shell_execute.execute_command_output_all(cmd)["result"].rstrip('\n')
                    container = result.split("#Exited")[0]
                    if container != customer_name:
                        status = "running"
            if "restarting" in status_show:
                about_time = get_createtime(official_app, app_path, customer_name)
                if "seconds" in about_time:
                    status = "restarting"
                else:
                    status = "failed"
        elif status == "created":
            status = "failed"
        else:
            continue

        if official_app:
            app_name = docker.read_var(var_path, 'name')
            app_id = app_name + "_" + customer_name  # app_id
            # get trade_mark
            trade_mark = docker.read_var(var_path, 'trademark')
            image_url = get_Image_url(app_name)
            # get env info
            path = app_path + "/.env"
            env_map = docker.get_map(path)

            try:
                myLogger.info_logger("get domain for APP_URL")
                domain = env_map.get("APP_URL")
                if "appname.example.com" in domain or ip in domain:
                    default_domain = ""
                else:
                    default_domain = domain
            except Exception:
                myLogger.info_logger("domain exception")
            try:
                app_version = env_map.get("APP_VERSION")
                volume_data = "/data/apps/" + customer_name + "/data"
                user_name = env_map.get("APP_USER", "")
                password = env_map.get("POWER_PASSWORD", "")
                admin_path = env_map.get("APP_ADMIN_PATH")
                if admin_path:
                    myLogger.info_logger(admin_path)
                    admin_path = admin_path.replace("\"", "")
                else:
                    admin_path = ""

                if default_domain != "" and admin_path != "":
                    admin_domain_url = "http://" + default_domain + admin_path
            except Exception:
                myLogger.info_logger("APP_USER POWER_PASSWORD exception")
            try:
                replace = env_map.get("APP_URL_REPLACE", "false")
                myLogger.info_logger("replace=" + replace)
                if replace == "true":
                    app_replace_url = True
                https = env_map.get("APP_HTTPS_ACCESS", "false")
                if https == "true":
                    app_https = True
            except Exception:
                myLogger.info_logger("APP_HTTPS_ACCESS exception")

            try:
                http_port = env_map.get("APP_HTTP_PORT", "0")
                if http_port:
                    port = int(http_port)
            except Exception:
                pass
            if port != 0:
                try:
                    if app_https:
                        easy_url = "https://" + ip + ":" + str(port)
                    else:
                        easy_url = "http://" + ip + ":" + str(port)
                    url = easy_url
                    admin_url = get_admin_url(customer_name, url)
                except Exception:
                    pass
            else:
                try:
                    db_port = list(docker.read_env(path, "APP_DB.*_PORT").values())[0]
                    port = int(db_port)
                except Exception:
                    pass
        else:
            app_name = customer_name
            app_id = customer_name + "_" + customer_name
        create_time = get_createtime(official_app, app_path, customer_name)
        if status in ['running', 'exited']:
            config = Config(port=port, compose_file=volume, url=url, admin_url=admin_url,
                            admin_domain_url=admin_domain_url,
                            admin_path=admin_path, admin_username=user_name, admin_password=password,
                            default_domain=default_domain)
        else:
            config = None
        if status == "failed":
            status_reason = StatusReason(Code=const.ERROR_SERVER_SYSTEM, Message="system original error",
                                         Detail="unknown error")
        else:
            status_reason = None
        app = App(app_id=app_id, app_name=app_name, customer_name=customer_name, trade_mark=trade_mark,
                  app_version=app_version, create_time=create_time, volume_data=volume_data, config_path=config_path,
                  status=status, status_reason=status_reason, official_app=official_app, image_url=image_url,
                  app_https=app_https, app_replace_url=app_replace_url, config=config)

        app_list.append(app.dict())
    return app_list


def check_if_official_app(var_path):
    if docker.check_directory(var_path):
        if docker.read_var(var_path, 'name') != "" and docker.read_var(var_path, 'trademark') != "" and docker.read_var(
                var_path, 'requirements') != "":
            requirements = docker.read_var(var_path, 'requirements')
            try:
                cpu = requirements['cpu']
                mem = requirements['memory']
                disk = requirements['disk']
                return True
            except KeyError:
                return False
    else:
        return False


def check_app_docker(app_id):
    customer_name = app_id.split('_')[1]
    app_name = app_id.split('_')[0]
    flag = False
    cmd = "docker compose ls -a | grep \'/" + customer_name + "/\'"
    try:
        shell_execute.execute_command_output_all(cmd)
        flag = True
        myLogger.info_logger("APP in docker")
    except CommandException as ce:
        myLogger.info_logger("APP not in docker")

    return flag


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
    if queue_job_ids and app_id in queue_job_ids:
        myLogger.info_logger("App in RQ")
        return True
    if failed_job_ids and app_id in failed_job_ids:
        myLogger.info_logger("App in RQ")
        return True
    if run_job_ids and app_id in run_job_ids:
        myLogger.info_logger("App in RQ")
        return True
    myLogger.info_logger("App not in RQ")
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
        app = get_rq_app(job_id, 'installing', "", "", "")
        installing_list.append(app)
    for job in q.jobs:
        app = get_rq_app(job.id, 'installing', "", "", "")
        installing_list.append(app)
    for job_id in failed_jobs:
        job = q.fetch_job(job_id)
        exc_info = job.exc_info
        code = exc_info.split('##websoft9##')[1]
        message = exc_info.split('##websoft9##')[2]
        detail = exc_info.split('##websoft9##')[3]
        app = get_rq_app(job_id, 'failed', code, message, detail)
        installing_list.append(app)

    return installing_list


def get_rq_app(id, status, code, message, detail):
    app_name = id.split('_')[0]
    customer_name = id.split('_')[1]
    # 当app还在RQ时，可能文件夹还没创建，无法获取trade_mark
    trade_mark = ""
    app_version = ""
    create_time = ""
    volume_data = ""
    config_path = ""
    image_url = get_Image_url(app_name)
    config = None
    if status == "installing":
        status_reason = None
    else:
        status_reason = StatusReason(Code=code, Message=message, Detail=detail)

    app = App(app_id=id, app_name=app_name, customer_name=customer_name, trade_mark=trade_mark,
              app_version=app_version, create_time=create_time, volume_data=volume_data, config_path=config_path,
              status=status, status_reason=status_reason, official_app=True, image_url=image_url,
              app_https=False, app_replace_url=False, config=config)
    return app.dict()


def get_Image_url(app_name):
    image_url = "static/images/" + app_name + "-websoft9.png"
    return image_url


def get_url(app_name, easy_url):
    url = easy_url
    return url


def get_admin_url(customer_name, url):
    admin_url = ""
    path = "/data/apps/" + customer_name + "/.env"
    try:
        admin_path = list(docker.read_env(path, "APP_ADMIN_PATH").values())[0]
        admin_path = admin_path.replace("\"", "")
        admin_url = url + admin_path
    except IndexError:
        pass
    return admin_url


def get_error_info(code, message, detail):
    error = {}
    error['Code'] = code
    error['Message'] = message
    error['Detail'] = detail
    return error


def app_domain_list(app_id):
    code, message = docker.check_app_id(app_id)
    if code == None:
        info, flag = app_exits_in_docker(app_id)
        if flag:
            myLogger.info_logger("Check app_id ok[app_domain_list]")
        else:
            raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, "")

    domains = get_all_domains(app_id)

    myLogger.info_logger(domains)

    ret = {}
    ret['domains'] = domains

    default_domain = ""
    if domains != None and len(domains) > 0:
        customer_name = app_id.split('_')[1]
        app_url = shell_execute.execute_command_output_all("cat /data/apps/" + customer_name + "/.env")["result"]
        if "APP_URL" in app_url:
            url = shell_execute.execute_command_output_all("cat /data/apps/" + customer_name + "/.env |grep APP_URL=")[
                "result"].rstrip('\n')
            default_domain = url.split('=')[1]
    ret['default_domain'] = default_domain
    myLogger.info_logger(ret)
    return ret


def app_proxy_delete(app_id):
    customer_name = app_id.split('_')[1]
    proxy_host = None
    token = get_token()
    url = "http://172.17.0.1:9092/api/nginx/proxy-hosts"
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)

    for proxy in response.json():
        portainer_name = proxy["forward_host"]
        if customer_name == portainer_name:
            proxy_id = proxy["id"]
            token = get_token()
            url = "http://172.17.0.1:9092/api/nginx/proxy-hosts/" + str(proxy_id)
            headers = {
                'Authorization': token,
                'Content-Type': 'application/json'
            }
            response = requests.delete(url, headers=headers)


def app_domain_delete(app_id, domain):
    code, message = docker.check_app_id(app_id)
    if code == None:
        info, flag = app_exits_in_docker(app_id)
        if flag:
            myLogger.info_logger("Check app_id ok[app_domain_delete]")
        else:
            raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, "")

    if domain is None or domain == "undefined":
        raise CommandException(const.ERROR_CLIENT_PARAM_BLANK, "Domains is blank", "")

    old_all_domains = get_all_domains(app_id)
    if domain not in old_all_domains:
        myLogger.info_logger("delete domain is not binded")
        raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "Domain is not bind.", "")

    myLogger.info_logger("Start to delete " + domain)
    proxy = get_proxy_domain(app_id, domain)
    if proxy != None:
        myLogger.info_logger(proxy)
        myLogger.info_logger("before update")
        domains_old = proxy["domain_names"]
        myLogger.info_logger(domains_old)

        domains_old.remove(domain)
        myLogger.info_logger("after update")
        myLogger.info_logger(domains_old)
        if len(domains_old) == 0:
            proxy_id = proxy["id"]
            token = get_token()
            url = "http://172.17.0.1:9092/api/nginx/proxy-hosts/" + str(proxy_id)
            headers = {
                'Authorization': token,
                'Content-Type': 'application/json'
            }
            response = requests.delete(url, headers=headers)
            try:
                if response.json().get("error"):
                    raise CommandException(const.ERROR_CONFIG_NGINX, response.json().get("error").get("message"), "")
            except Exception:
                myLogger.info_logger(response.json())
            set_domain("", app_id)
        else:
            proxy_id = proxy["id"]
            token = get_token()
            url = "http://172.17.0.1:9092/api/nginx/proxy-hosts/" + str(proxy_id)
            headers = {
                'Authorization': token,
                'Content-Type': 'application/json'
            }
            port = get_container_port(app_id.split('_')[1])
            host = app_id.split('_')[1]
            data = {
                "domain_names": domains_old,
                "forward_scheme": "http",
                "forward_host": host,
                "forward_port": port,
                "access_list_id": "0",
                "certificate_id": 0,
                "meta": {
                    "letsencrypt_agree": False,
                    "dns_challenge": False
                },
                "advanced_config": "",
                "locations": [],
                "block_exploits": False,
                "caching_enabled": False,
                "allow_websocket_upgrade": False,
                "http2_support": False,
                "hsts_enabled": False,
                "hsts_subdomains": False,
                "ssl_forced": False
            }

            response = requests.put(url, data=json.dumps(data), headers=headers)
            if response.json().get("error"):
                raise CommandException(const.ERROR_CONFIG_NGINX, response.json().get("error").get("message"), "")
            domain_set = app_domain_list(app_id)
            default_domain = domain_set['default_domain']
            # 如果被删除的域名是默认域名，删除后去剩下域名的第一个
            if default_domain == domain:
                set_domain(domains_old[0], app_id)

    else:
        raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "Delete domain is not bind", "")


def app_domain_update(app_id, domain_old, domain_new):
    myLogger.info_logger("app_domain_update")
    domain_list = []
    domain_list.append(domain_old)
    domain_list.append(domain_new)

    check_domains(domain_list)

    code, message = docker.check_app_id(app_id)
    if code == None:
        info, flag = app_exits_in_docker(app_id)
        if flag:
            myLogger.info_logger("Check app_id ok")
        else:
            raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, "")
    proxy = get_proxy_domain(app_id, domain_old)
    if proxy != None:
        domains_old = proxy["domain_names"]
        index = domains_old.index(domain_old)
        domains_old[index] = domain_new
        proxy_id = proxy["id"]
        token = get_token()
        url = "http://172.17.0.1:9092/api/nginx/proxy-hosts/" + str(proxy_id)
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }
        port = get_container_port(app_id.split('_')[1])
        host = app_id.split('_')[1]
        data = {
            "domain_names": domains_old,
            "forward_scheme": "http",
            "forward_host": host,
            "forward_port": port,
            "access_list_id": "0",
            "certificate_id": 0,
            "meta": {
                "letsencrypt_agree": False,
                "dns_challenge": False
            },
            "advanced_config": "",
            "locations": [],
            "block_exploits": False,
            "caching_enabled": False,
            "allow_websocket_upgrade": False,
            "http2_support": False,
            "hsts_enabled": False,
            "hsts_subdomains": False,
            "ssl_forced": False
        }

        response = requests.put(url, data=json.dumps(data), headers=headers)
        if response.json().get("error"):
            raise CommandException(const.ERROR_CONFIG_NGINX, response.json().get("error").get("message"), "")
        domain_set = app_domain_list(app_id)
        default_domain = domain_set['default_domain']
        myLogger.info_logger("default_domain=" + default_domain + ",domain_old=" + domain_old)
        # 如果被修改的域名是默认域名，修改后也设置为默认域名
        if default_domain == domain_old:
            set_domain(domain_new, app_id)
    else:
        raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "edit domain is not exist", "")


def app_domain_add(app_id, domain):
    temp_domains = []
    temp_domains.append(domain)
    check_domains(temp_domains)

    code, message = docker.check_app_id(app_id)
    if code == None:
        info, flag = app_exits_in_docker(app_id)
        if flag:
            myLogger.info_logger("Check app_id ok")
        else:
            raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, "")

    old_domains = get_all_domains(app_id)
    if domain in old_domains:
        raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "Domain is in use", "")

    proxy = get_proxy(app_id)
    if proxy != None:
        domains_old = proxy["domain_names"]
        domain_list = domains_old
        domain_list.append(domain)

        proxy_id = proxy["id"]
        token = get_token()
        url = "http://172.17.0.1:9092/api/nginx/proxy-hosts/" + str(proxy_id)
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }
        port = get_container_port(app_id.split('_')[1])
        host = app_id.split('_')[1]
        data = {
            "domain_names": domain_list,
            "forward_scheme": "http",
            "forward_host": host,
            "forward_port": port,
            "access_list_id": "0",
            "certificate_id": 0,
            "meta": {
                "letsencrypt_agree": False,
                "dns_challenge": False
            },
            "advanced_config": "",
            "locations": [],
            "block_exploits": False,
            "caching_enabled": False,
            "allow_websocket_upgrade": False,
            "http2_support": False,
            "hsts_enabled": False,
            "hsts_subdomains": False,
            "ssl_forced": False
        }
        response = requests.put(url, data=json.dumps(data), headers=headers)
        if response.json().get("error"):
            raise CommandException(const.ERROR_CONFIG_NGINX, response.json().get("error").get("message"), "")
    else:
        # 追加
        token = get_token()
        url = "http://172.17.0.1:9092/api/nginx/proxy-hosts"
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }
        port = get_container_port(app_id.split('_')[1])
        host = app_id.split('_')[1]

        data = {
            "domain_names": temp_domains,
            "forward_scheme": "http",
            "forward_host": host,
            "forward_port": port,
            "access_list_id": "0",
            "certificate_id": 0,
            "meta": {
                "letsencrypt_agree": False,
                "dns_challenge": False
            },
            "advanced_config": "",
            "locations": [],
            "block_exploits": False,
            "caching_enabled": False,
            "allow_websocket_upgrade": False,
            "http2_support": False,
            "hsts_enabled": False,
            "hsts_subdomains": False,
            "ssl_forced": False
        }

        response = requests.post(url, data=json.dumps(data), headers=headers)

        if response.json().get("error"):
            raise CommandException(const.ERROR_CONFIG_NGINX, response.json().get("error").get("message"), "")
        set_domain(domain, app_id)

    return domain


def check_domains(domains):
    myLogger.info_logger(domains)
    if domains is None or len(domains) == 0:
        raise CommandException(const.ERROR_CLIENT_PARAM_BLANK, "Domains is blank", "")
    else:
        for domain in domains:
            if is_valid_domain(domain):
                if check_real_domain(domain) == False:
                    raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "Domain and server not match", "")
            else:
                raise CommandException(const.ERROR_CLIENT_PARAM_Format, "Domains format error", "")


def is_valid_domain(domain):
    if domain.startswith("http"):
        return False

    return True


def check_real_domain(domain):
    domain_real = True
    try:
        cmd = "ping -c 1 " + domain + "  | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | uniq"
        domain_ip = shell_execute.execute_command_output_all(cmd)["result"].rstrip('\n')

        ip_result = shell_execute.execute_command_output_all("cat /data/apps/w9services/w9appmanage/public_ip")
        ip_save = ip_result["result"].rstrip('\n')

        if domain_ip == ip_save:
            myLogger.info_logger("Domain check ok!")
        else:
            domain_real = False
    except CommandException as ce:
        domain_real = False

    return domain_real


def get_token():
    url = 'http://172.17.0.1:9092/api/tokens'
    headers = {'Content-type': 'application/json'}
    cmd = "cat /usr/share/cockpit/myapps/config.json | jq -r '.NGINXPROXYMANAGER.NGINXPROXYMANAGER_PASSWORD'"
    password = shell_execute.execute_command_output_all(cmd)["result"].rstrip('\n')
    myLogger.info_logger(password)
    param = {
        "identity": "help@websoft9.com",
        "scope": "user",
        "secret": password
    }
    response = requests.post(url, data=json.dumps(param), headers=headers)

    token = "Bearer " + response.json()["token"]
    return token


def get_proxy(app_id):
    customer_name = app_id.split('_')[1]
    proxy_host = None
    token = get_token()
    url = "http://172.17.0.1:9092/api/nginx/proxy-hosts"
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)

    for proxy in response.json():
        portainer_name = proxy["forward_host"]
        if customer_name == portainer_name:
            proxy_host = proxy
            break

    return proxy_host


def get_proxy_domain(app_id, domain):
    customer_name = app_id.split('_')[1]
    proxy_host = None
    token = get_token()
    url = "http://172.17.0.1:9092/api/nginx/proxy-hosts"
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)

    myLogger.info_logger(response.json())
    for proxy in response.json():
        portainer_name = proxy["forward_host"]
        domain_list = proxy["domain_names"]
        if customer_name == portainer_name:
            myLogger.info_logger("-------------------")
            if domain in domain_list:
                myLogger.info_logger("find the domain proxy")
                proxy_host = proxy
                break

    return proxy_host


def get_all_domains(app_id):
    customer_name = app_id.split('_')[1]
    domains = []
    token = get_token()
    url = "http://172.17.0.1:9092/api/nginx/proxy-hosts"
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)

    for proxy in response.json():
        portainer_name = proxy["forward_host"]
        if customer_name == portainer_name:
            for domain in proxy["domain_names"]:
                domains.append(domain)
    return domains


def app_domain_set(domain, app_id):
    temp_domains = []
    temp_domains.append(domain)
    check_domains(temp_domains)

    code, message = docker.check_app_id(app_id)
    if code == None:
        info, flag = app_exits_in_docker(app_id)
        if flag:
            myLogger.info_logger("Check app_id ok")
        else:
            raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, "")

    set_domain(domain, app_id)


def set_domain(domain, app_id):
    myLogger.info_logger("set_domain start")
    old_domains = get_all_domains(app_id)
    if domain != "":
        if domain not in old_domains:
            message = domain + " is not in use"
            raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, message, "")

    customer_name = app_id.split('_')[1]
    app_url = shell_execute.execute_command_output_all("cat /data/apps/" + customer_name + "/.env")["result"]

    if "APP_URL" in app_url:
        myLogger.info_logger("APP_URL is exist")
        if domain == "":
            ip_result = shell_execute.execute_command_output_all("cat /data/apps/w9services/w9appmanage/public_ip")
            domain = ip_result["result"].rstrip('\n')
            cmd = "sed -i 's/APP_URL=.*/APP_URL=" + domain + "/g' /data/apps/" + customer_name + "/.env"
            shell_execute.execute_command_output_all(cmd)
            if "APP_URL_REPLACE=true" in app_url:
                myLogger.info_logger("need up")
                shell_execute.execute_command_output_all("cd /data/apps/" + customer_name + " && docker compose up -d")
        else:
            cmd = "sed -i 's/APP_URL=.*/APP_URL=" + domain + "/g' /data/apps/" + customer_name + "/.env"
            shell_execute.execute_command_output_all(cmd)
            if "APP_URL_REPLACE=true" in app_url:
                myLogger.info_logger("need up")
                shell_execute.execute_command_output_all("cd /data/apps/" + customer_name + " && docker compose up -d")
    else:
        myLogger.info_logger("APP_URL is not exist")
        if domain == "":
            ip_result = shell_execute.execute_command_output_all("cat /data/apps/w9services/w9appmanage/public_ip")
            domain = ip_result["result"].rstrip('\n')

        cmd = "sed -i '/APP_NETWORK/a APP_URL=" + domain + "' /data/apps/" + customer_name + "/.env"
        shell_execute.execute_command_output_all(cmd)
    myLogger.info_logger("set_domain success")


def get_container_port(container_name):
    port = "80"
    cmd = "docker port " + container_name + " |grep ::"
    result = shell_execute.execute_command_output_all(cmd)["result"]
    myLogger.info_logger(result)
    port = result.split('/')[0]
    myLogger.info_logger(port)

    return port


def compared_version(ver1, ver2):
    list1 = str(ver1).split(".")
    list2 = str(ver2).split(".")
    # 循环次数为短的列表的len
    for i in range(len(list1)) if len(list1) < len(list2) else range(len(list2)):
        if int(list1[i]) == int(list2[i]):
            pass
        elif int(list1[i]) < int(list2[i]):
            return -1
        else:
            return 1
    # 循环结束，哪个列表长哪个版本号高
    if len(list1) == len(list2):
        return 0
    elif len(list1) < len(list2):
        return -1
    else:
        return 1
