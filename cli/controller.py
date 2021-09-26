import model, os

path_repo = "./data/application.list"
path_project = ""

# for Git clone HA
github_url = ("https://github.com", "https://github.com.cnpmjs.org", "https://hub.fastgit.org")

class Print:
    
    def __init__(self):
        pass
    
    def printRepo():
        model.FileOp.printJson(path_repo)


class Github:
    
    def __init__(self):
        pass
    
    def gitClone(name: str):
        cmd = "git clone --depth=1 " + model.SmoothUrl.res(github_url) + "/websoft9/docker-" + name + " repo/docker-"+name
        print(cmd)
        os.system(cmd)