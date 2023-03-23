#!/usr/bin/python3
import os, io, sys, platform, shutil, time, subprocess, json, datetime
from api.utils.common_log import myLogger

def execute_command_output(cmd_str):
    print(cmd_str)
    out_str = subprocess.getoutput(cmd_str)
    print(out_str)
    return out_str

# cmd_str: 执行的command命令 times：如果不成功的重复次数
def execute_command_output_all(cmd_str, max_time = 3):
    
    myLogger.info_logger("Start to execute cmd: " + cmd_str)
    execute_time = 0
    while execute_time < max_time:
        process = subprocess.run(convert_command(cmd_str), shell=True, stdout=subprocess.PIPE, universal_newlines=True)
        if process.returncode == 0:
            return {"code": "0", "result": process.stdout,}
        else:
            execute_time = execute_time + 1

    myLogger.error_logger("Command execute failed   Commend: " + cmd_str)
    return {"code": "-1", "result": "command execute failed, please check your command!"}

def convert_command(cmd_str):
    convert_cmd = ""
    if cmd_str == "":
       convert_cmd=cmd_str
    else:
       convert_cmd='chroot /host ' + cmd_str

    return convert_cmd
