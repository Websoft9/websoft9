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
