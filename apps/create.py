#!/usr/bin/env python2
#!/usr/bin/env python3
#coding: utf-8

import os, io, sys, platform, shutil, urllib3, time, json


def ReadLists(filename):
    if os.path.getsize(filename) == 0:
        print("\n清单中没有项目！")
        sys.exit()
    else:
        with open("./"+filename,mode='r',newline='') as f:
          templists=list(f)
          rlist=[]
          for templist in templists:
              rlist.append(templist.replace('\n',''))
          return rlist
      
mylists=ReadLists("add")

# 批量处理，创建项目文件夹，issue
for mylist in mylists:
    print("处理 "+mylist+" ...\n")
    os.system("cp -R roles/Template roles/" + mylist)
    os.system("echo '' > add")

print("\n执行完成，并清空列表")
