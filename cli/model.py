
import os, io, sys, platform, psutil, json, secrets, string
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type, Union

import urllib.request


class SmoothUrl:
    ''' Get the best smooth url for Git or Download'''
    
    def __init__(self):
        pass
    
    def res(self, url_list: Tuple):
        
        for item in url_list:
            try:
                urllib.request.urlopen(item,timeout=3).read()
                print("Smooth URL is: " + item)
                return item
            except:
                continue
        
        print("Necessary resource URL can not reachable, system exit!")
        sys.exit(0)
        

class GitOp:
    '''Git operation'''
    
    def __init__(self):
        pass
    
    def gitClone(self, cmd: str):
        '''git clone'''
        try:
            print("Command is： "+cmd)
            os.system(cmd)
        except:
            print("Git clone failed, try again and check your URL can be accessed")
            sys.exit(0)

class FileOp:
    '''File operation'''
    
    def __init__(self):
        pass
    
    def printJson(self, path: str):
        '''output file content'''
        
        with open(path,newline='') as file:
            print(file.read())
    
    def fileToJson(self, path: str, remark: Optional[str] = "#", separate: Optional[str] = "="):
        ''' convert file to Json '''
        
        dict = {}
        with open(path) as fh:
            for line in fh:
                if line == "\n":
                    continue
                
                if line.find(remark) != 0:
                    item, value = line.strip().split(separate, -1)
                    dict[item] = value
                else:
                    continue
        fh.close()        
        return dict
            

class NetOp:
    '''Network and port manage'''
     
    def __init__(self):
        pass
     
    def checkPort(self, port: int):
        '''check the target port's status'''
        search_key = "port="+str(port)
        if str(psutil.net_connections()).find(search_key) != -1:
            print(str(port)+" is used")
            return False
        else:
            print(str(port)+" is free")
            return True
     
    def setPort(self, port: int):
        '''set usable port'''
        while self.checkPort(port) == False:
            port=port+1
         
        print(port)
        return port

class SecurityOp:
    '''Password and security operation'''
    
    def __int__(self):
        pass
    
    def randomPass(self, length: Optional[int] = 16):
        '''set strong password'''
        
        alphabet = string.ascii_letters + string.digits
        while True:
            password = ''.join(secrets.choice(alphabet) for i in range(length))
            if (any(c.islower() for c in password)
                    and any(c.isupper() for c in password)
                    and sum(c.isdigit() for c in password) >= 3):
                break
        print(password)