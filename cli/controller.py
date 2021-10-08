import model, os, sys, subprocess
from model import GitOp

path_repo = "./data/application.list"
path_project = ""

# for Git clone HA
github_url = ("https://github.com", "https://github.com.cnpmjs.org", "https://hub.fastgit.org")

class Print:
    
    def __init__(self):
        pass
    
    def printRepo():
        model.FileOp.printJson(path_repo)


class Create:
    
    def __init__(self, app_name: str, project_name: str):
        
        self.folder = None
        self.app_name = app_name
        self.project_name = project_name
        
        if self.project_name != None:
            self.folder = self.project_name
        else:
            self.folder = self.app_name
    
    def downRepo(self):
        '''download repository'''
        
        geturl = model.SmoothUrl()
        gitop = model.GitOp()
        
        cmd = "git clone --depth=1 " + geturl.res(github_url) + "/websoft9/docker-" + self.app_name + " " + self.folder
        if os.path.exists("./"+self.folder):
            print(os.path.abspath(self.folder)+" folder already exists")
            sys.exit(0)
        else:
            gitop.gitClone(cmd)
            
    def setEnv(self):
        '''set the usable port for application'''
        fileop=model.FileOp()
        print(fileop.fileToJson('./drupal/.env'))
        pass
            
    def upRepo(self):
        '''docker-compose up repository'''
        
        cmd = "docker-compose up -d"
        print(cmd)
        os.chdir(self.folder)
        os.system(cmd)
        
    def printResult(self):
        pass
    

