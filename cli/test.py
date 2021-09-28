import json

with open("./joomla/.env_all","r") as file:
    jsonData = json.dump(file, tempfile)