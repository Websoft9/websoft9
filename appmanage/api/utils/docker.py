import os, io, sys, platform, shutil, time, json, datetime
from api.utils import shell_execute
from api.utils import network

from dotenv import load_dotenv, find_dotenv
from pathlib import Path

def copy_dir(src_path, target_path):
    if os.path.isdir(src_path) and os.path.isdir(target_path):
        filelist_src = os.listdir(src_path)
        for file in filelist_src:
            path = os.path.join(os.path.abspath(src_path), file)
            if os.path.isdir(path):
                path1 = os.path.join(os.path.abspath(target_path), file)
                if not os.path.exists(path1):
                    os.mkdir(path1)
                copy_dir(path, path1)
            else:
                with open(path, 'rb') as read_stream:
                    contents = read_stream.read()
                    path1 = os.path.join(target_path, file)
                    with open(path1, 'wb') as write_stream:
                        write_stream.write(contents)
        return True

    else:
        return False

def create_app_directory(app_name):
    #1.判断/data/apps/app_name是否已经存在，如果已经存在，方法结束
    path = "/data/apps/"+app_name
    isexsits = os.path.exists(path)
    if isexsits:
        return
    #2. git clone https://github.com/Websoft9/docker-library.git项目，将apps复制到/data目录，如果data目录没有，创建
    shell_execute.execute_command_output_all("git clone https://github.com/Websoft9/docker-library.git")
    if not os.path.exists("/data"):
        os.makedirs("/data")
    copy_dir("docker-library","/data")

def check_app_compose(app_name):
    path = "/data/apps/" + app_name + ".env"
    load_dotenv(find_dotenv(Path.cwd().joinpath(path)))
    port = os.getenv('APP_HTTP_PORT')
    #1.判断/data/apps/app_name/.env中的port是否占用，没有被占用，方法结束（network.py的get_start_port方法）
    use_port = network.get_start_port(port)
    return use_port





