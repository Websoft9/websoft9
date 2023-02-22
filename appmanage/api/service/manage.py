import os, io, sys, platform, shutil, time, subprocess, json, datetime

from api.utils import shell_execute

# 获取所有app的信息
def get_my_app():

    my_cmd = "sudo docker compose ls"
    output = shell_execute.execute_command_output_all(my_cmd)
    if int(output["code"]) == 0:
        output_list = output["result"].split()
        print(output_list)
        ret = {}
        list = []
        num = int(len(output_list)/3)
        for i in range(1,num):
            app = {}
            app['name'] = output_list[3*i+1]
            app['status_code'] = output_list[3*i+2].split("(")[0]
            app['status'] = output_list[3*i+3]
            list.append(app)
        ret["code"] = 0
        ret["message"] = "app查询成功"
        ret["data"] = list
    else:
        ret["code"] = -1
        ret["message"] = "app查询失败"
        ret["data"] = None
    return ret
