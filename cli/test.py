import model,re

fileop=model.FileOp('c2/.env')
securityop=model.SecurityOp()
netop=model.NetOp()


env_dict = fileop.fileToDict()
env_str = fileop.fileToString()
port_list = []

for key in list(env_dict.keys()):
    if env_dict[key] in ["", "True", "False"]:
        del env_dict[key]

for key,value in env_dict.items():
    # replace password
    if re.match('\w*PASSWORD',key,re.I) != None:
        env_str = env_str.replace(key+"="+value, key+"="+securityop.randomPass())
        
    # replace port
    if re.match('\w*PORT',key,re.I) != None:
        port = int(value)
        while port in port_list or not netop.checkPort(port):
            port = port + 1
        port_list.append(port)
        print(port_list)
        env_str = env_str.replace(key+"="+value, key+"="+netop.setPort(int(port)))
    
    # replace app_container 
    if re.match('\w*APP_CONTAINER_NAME',key,re.I) != None:
        env_str = env_str.replace(key+"="+value, key+"="+"hello")
        
    # replace app_container 
    if re.match('\w*APP_NETWORK',key,re.I) != None:
        env_str = env_str.replace(key+"="+value, key+"="+"hello")

fileop.stringToFile(env_str)

print(env_str)

