#!/usr/bin/python3
import os, io, sys, platform, shutil, time, subprocess, json, datetime

# 执行Shell命令，处理报错和超时，并有返回值
def execute_Command(cmd_str, timeout=60, timeinner=3, retry=True):
    print(cmd_str)
    time_out = 0
    status = False

    while time_out < timeout:
        out_str = subprocess.getstatusoutput(cmd_str)
        print(out_str)
        if out_str[0] == 0 and out_str[1].find('ERROR') == -1 and out_str[1].find('error') == -1:
            status = True
            print('\nExecute successfully')
            break
        elif retry:
            print('\nTry again')
            time.sleep(timeinner)
            time_out = time_out + timeinner
        else:
            time_out = timeout

    if not status:
        print('\n此次任务执行有异常，请仔细排查')

# 执行Shell命令，处理报错和超时，并有返回值
def execute_CommandReturn(cmd_str, timeout=30, timeinner=3):
    print(cmd_str)
    time_out = 0

    while time_out < timeout:
        out_str = subprocess.getstatusoutput(cmd_str)
        print(out_str)
        if out_str[0] == 0 and out_str[1].find('ERROR') == -1 and out_str[1].find('error') == -1:
            # 去掉\n和"
            # 返回值是元组，不能修改，需要赋值给变量
            temp_str = out_str[1]
            temp_str = temp_str.strip('\n')
            temp_str = temp_str.strip('"')
            time_out = timeout
            return temp_str
        else:
            time.sleep(timeinner)
            time_out = time_out + timeinner
    print('\n此次任务执行失败，请根据下面错误原因排查：')
    print(out_str)

def execute_command_output(cmd_str):
    print(cmd_str)
    out_str = subprocess.getoutput(cmd_str)
    print(out_str)
    return out_str

# cmd_str: 执行的command命令 times：如果不成功的重复次数
def execute_command_output_all(cmd_str, max_time = 3):
    
    print("start to excute cmd: " + cmd_str)
    excutetime = 0
    while excutetime < max_time:
        process = subprocess.run(convert_command(cmd_str), shell=True, stdout=subprocess.PIPE, universal_newlines=True)
        if process.returncode == 0:
            return {"code": "0", "result": process.stdout,}
        else:
            excutetime = excutetime + 1    

    return {"code": "-1", "result": "command excute failed, please check your command!"}

def convert_command(cmd_str):
    convert_cmd = ""
    if cmd_str == "":
       convert_cmd=cmd_str
    else:
       convert_cmd='echo "'+cmd_str+'" > /data/pipe/appmanage'

    return convert_cmd
