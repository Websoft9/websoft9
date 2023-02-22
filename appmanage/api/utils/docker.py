import os, io, sys, platform, shutil, time, json, datetime

def create_app_directory(app_name):
  
    #1.判断/data/apps/app_name是否已经存在，如果已经存在，方法结束

    #2. git clone https://github.com/Websoft9/docker-library.git项目，将apps复制到/data目录，如果data目录没有，创建

def check_app_compose(app_name):
  
    #1.判断/data/apps/app_name/.env中的port是否占用，没有被占用，方法结束（network.py的get_start_port方法）
