
import os, io, sys, platform, shutil, urllib3, json, time, subprocess
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Type, Union

import urllib.parse
import urllib.request

class SmoothUrl:
    ''' get url '''
    
    def __init__(self):
        pass
    
    def res(url_list: Tuple):
        
        for item in url_list:
            req = urllib.request.Request(item)
            try:
                urllib.request.urlopen(item,timeout=3).read()
                return item
            except urllib.error.URLError as e:
                print(e.reason)
                continue
        
        return None


class Github:
    '''Github operation'''
    
    def __init__(self):
        pass
    
    def gitClone():
        pass
    
    


class FileOp:
    '''File operation'''
    
    def __init__(self):
        pass
    
    def printJson(path: str):
        with open(path,newline='') as file:
            print(file.read())