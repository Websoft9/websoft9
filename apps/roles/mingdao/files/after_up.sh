#!/bin/bash

/bin/rm -f /usr/local/MDPrivateDeployment/first  
/bin/bash /usr/local/MDPrivateDeployment/service.sh stopall  
/bin/bash /usr/local/MDPrivateDeployment/service.sh start
