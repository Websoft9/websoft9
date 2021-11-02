
import os, io, sys, platform, psutil, json, secrets, string, docker
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
    
    def __init__(self, path: str):
        self.path = path
    
    def printFile(self):
        '''output file content'''
        with open(self.path,newline='') as file:
            print(file.read())
            
    def fileToString(self):
        '''read file content'''
        with open(self.path,'r') as file:
            return file.read()
        
    def stringToFile(self, content: Optional[str] = ""):
        '''string content to file'''
        with open(self.path,'w+') as file:
            return file.write(content)
        file.close()
    
    def fileToDict(self, remark: Optional[str] = "#", separate: Optional[str] = "="):
        ''' convert file to Json '''
        dict = {}
        with open(self.path) as fh:
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
            return True

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
        return password
    
class DockerComposeOp:
    '''Docker Compose operation'''
    
    def __init__(self, command: str, **parameter):
        
        self.cmd = "docker-compose "+ command
        
        for key, value in parameter.items():
            self.cmd = self.cmd + " --" + key + " " + value
        
        try:
            os.chdir(self.parameter[project-directory])
        except:
            print("Not found project directory")
            sys.exit(0)
    
    def execute(self):
        '''docker-compose command executing'''
        try:
            os.system(self.cmd)
        except:
            print("This operation execute failed")
            sys.exit(0)

class DockerOp:
    ''' Docker operation '''
    def __init__(self, status: Optional[str] = 'all'):
        self.client = docker.from_env()
        self.status = status
    
    def lsContainer(self):
        container_list = []
        
        for container in self.client.containers.list(self.status):
            container_list.append(container.name)
        return container_list

    def getProject(self):
        project_dict = {}

        for name in self.lsContainer():
            project_dict[self.client.containers.get(name).labels['com.docker.compose.project']] = self.client.containers.get(name).labels['com.docker.compose.project.working_dir']
        
        return project_dict
    
    def lsProject(self):
        '''list all project and path'''
        for key, value in self.getProject().items():
            print(key,value)