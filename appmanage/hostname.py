from websoft9.appmanage.api.utils.log import myLogger
from api.utils import shell_execute

shell_execute.execute_command_output_all("sed -i '/websoft9-appmanage/d' /etc/hosts")
shell_execute.execute_command_output_all("echo $(docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' websoft9-appmanage) websoft9-appmanage >> /etc/hosts")