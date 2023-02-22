import os, io, sys, platform, shutil, time, json, datetime
from api.utils import shell_execute

# 根据依赖文件提供的port，判断是否启动
def get_start_port(port):
    print("目前检查"+port+"是否被占用")
    use_port = port
    output = "ok"
    while True:
        cmd = "netstat -anp|grep "+use_port
        output = shell_execute.execute_CommandReturn(cmd)
        if output == "":
            break
        else:
            use_port = use_port+1

    return use_port

        
        
    
