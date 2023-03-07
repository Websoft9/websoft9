import os, io, sys, platform, shutil, time, json, datetime
from api.utils import shell_execute

# 根据.env文件提供的port，找出能正常启动的最小port
def get_start_port(port):
    use_port = port
    while True:
        cmd = "netstat -ntlp | grep -v only"
        output = shell_execute.execute_command_output_all(cmd)
        if output["result"].find(use_port)==-1:
            break
        else:
            use_port = str(int(use_port)+1)

    return use_port
