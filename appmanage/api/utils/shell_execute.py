#!/usr/bin/python3
import os, io, sys, platform, shutil, time, subprocess, json, datetime
from api.utils.common_log import myLogger
from api.exception.command_exception import CommandException
from api.utils import const

def execute_command_output(cmd_str):
    print(cmd_str)
    out_str = subprocess.getoutput(cmd_str)
    print(out_str)
    return out_str

# cmd_str: 执行的command命令 times：如果不成功的重复次数
def execute_command_output_all(cmd_str, max_time = 2):
    
    myLogger.info_logger("Start to execute cmd: " + cmd_str)
    execute_time = 0
    while execute_time < max_time:

        process = subprocess.run(f'nsenter -m -u -i -n -p -t 1 sh -c "{cmd_str}"', capture_output=True, check=False, text=True, shell=True)
        
        if process.returncode == 0 and 'Fail' not in process.stdout and 'fail' not in process.stdout and 'Error' not in process.stdout and 'error' not in process.stdout:
            myLogger.info_logger("success to excute cmd ")
            return {"code": "0", "result": process.stdout,}
        else:
            execute_time = execute_time + 1
            if execute_time > 2:
               myLogger.info_logger("failed to excute cmd ")
               myLogger.info_logger(process.stdout)
               raise CommandException(const.ERROR_SERVER_COMMAND,"Docker returns the original error",process.stdout)

def convert_command(cmd_str):
    convert_cmd = ""
    if cmd_str == "":
       convert_cmd=cmd_str
    else:
       convert_cmd="nsenter -m -u -i -n -p -t 1 sh -c " + "'"+cmd_str+"'"

    return convert_cmd
