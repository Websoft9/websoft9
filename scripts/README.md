## build

docker build -t art:1.0 .
```
[root@VM-74-236-centos ~]# docker build -t art:2.0 .
Sending build context to Docker daemon  451.1kB
Step 1/8 : FROM ansible/ansible:centos7
 ---> 0731001e75a9
Step 2/8 : LABEL Description="DevOps for ansible runtime" Vendor="Websoft9" Version="1.0.0"
 ---> Using cache
 ---> 616caba41119
Step 3/8 : WORKDIR "/ansible"
 ---> Using cache
 ---> 6cd79046e09f
Step 4/8 : RUN yum install ansible -y
 ---> Using cache
 ---> cba6486307e6
Step 5/8 : RUN git clone https://github.com/Websoft9/role_common
 ---> Using cache
 ---> 82b608d88aad
Step 6/8 : RUN ansible-playbook role_common/tests/test.yml
 ---> Using cache
 ---> 5269d440e608
Step 7/8 : RUN git clone https://github.com/Websoft9/role_template
 ---> Using cache
 ---> e9b640674655
Step 8/8 : VOLUME "/ansible"
 ---> Using cache
 ---> 99f4472fd521
Successfully built 99f4472fd521
Successfully tagged art:2.0

[root@VM-74-236-centos ~]# docker image list
REPOSITORY        TAG       IMAGE ID       CREATED          SIZE
art               1.0       2735478ce859   37 minutes ago   1.27GB
art               2.0       99f4472fd521   37 minutes ago   1.27GB

```

## Excute

### Get project from volumes


```
docker run -d --name art -v /root/role_mysql:/ansible/role_mysql art:2.0

[root@VM-74-236-centos ~]# docker ps
CONTAINER ID   IMAGE     COMMAND            CREATED         STATUS         PORTS     NAMES
f8ec36905530   art:2.0   "/usr/sbin/init"   9 minutes ago   Up 9 minutes             art

container:
[root@f8ec36905530 ansible]# ansible-playbook role_mysql/tests/test.yml 

Please choose the number for MySQL version [ 1/2/3/4...] 

 1: MySQL 5.5
 2: MySQL 5.6
 3: MySQL 5.7
 4: MySQL 8.0
 [3]: 

```

### Get project and edit in Container

```
docker run -d --name art -v /root/role_mysql:/ansible/role_mysql art:2.0

[root@VM-74-236-centos ~]# docker ps
CONTAINER ID   IMAGE     COMMAND            CREATED         STATUS         PORTS     NAMES
f8ec36905530   art:2.0   "/usr/sbin/init"   9 minutes ago   Up 9 minutes             art

[root@f8ec36905530 ansible]# vim role_template/tasks/main.yml 
- name: Install this role on {{ansible_os_family}}
  include: "{{ansible_os_family}}.yml"

- name: Test you add task
  shell: echo "Your ansible runtime is OK"

[root@f8ec36905530 ansible]# ansible-playbook role_template/tests/test.yml 

PLAY [localhost] *************************************************************************************************************************************************************************************************************************************************************

TASK [Gathering Facts] *******************************************************************************************************************************************************************************************************************************************************
ok: [localhost]

TASK [role_template : Install this role on RedHat] ***************************************************************************************************************************************************************************************************************************

TASK [role_template : Test you add task] *************************************************************************************************************************************************************************************************************************************
changed: [localhost]

PLAY RECAP *******************************************************************************************************************************************************************************************************************************************************************
localhost                  : ok=2    changed=1    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0   

[root@f8ec36905530 ansible]# 


```
