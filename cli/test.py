import model,re

env = {}
fileop=model.FileOp()
env = fileop.fileToJson('c2/.env')

for key,value in env.items():
    if re.match(pattern,key,re.I) != None:
        print(value)

