#!/usr/bin/python3
import subprocess

from api.utils.log import myLogger
from api.exception.command_exception import CommandException
from api.utils import const


# This fuction is for running shell commands on container
# cmd_str e.g: "ls -a"
# return string limit: 4000 chars? to do
def execute_command_output(cmd_str):
    print(cmd_str)
    out_str = subprocess.getoutput(cmd_str)
    print(out_str)
    return out_str


# This fuction is for running shell commands on host machine
# cmd_str e.g: "ls -a"
# return string limit: 4000 chars
def execute_command_output_all(cmd_str):
    
    myLogger.info_logger("Start to execute cmd: " + cmd_str)

    process = subprocess.run(f'nsenter -m -u -i -n -p -t 1 sh -c "{cmd_str}"', capture_output=True, bufsize=65536, check=False, text=True, shell=True)
        
    if process.returncode == 0 and 'Fail' not in process.stdout and 'fail' not in process.stdout and 'Error' not in process.stdout and 'error' not in process.stdout:

       return {"code": "0", "result": process.stdout}
    else:
       myLogger.info_logger("Failed to execute cmd, output failed result")
       myLogger.info_logger(process)
       raise CommandException(const.ERROR_SERVER_COMMAND, "Docker returns the original error", process.stderr)



# This fuction is convert container commands to host machine commands
def convert_command(cmd_str):
    convert_cmd = ""
    if cmd_str == "":
       convert_cmd=cmd_str
    else:
       convert_cmd="nsenter -m -u -i -n -p -t 1 sh -c " + "'"+cmd_str+"'"

    return convert_cmd
