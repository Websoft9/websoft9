
## Ansible facts for OS distribution
```
# AmazonLinux2
"ansible_distribution": "Amazon",
"ansible_distribution_file_parsed": true,
"ansible_distribution_file_path": "/etc/system-release",
"ansible_distribution_file_variety": "Amazon",
"ansible_distribution_major_version": "2",
"ansible_distribution_release": "NA",
"ansible_distribution_version": "2",

# Ubuntu
"ansible_distribution": "Ubuntu",
"ansible_distribution_file_parsed": true,
"ansible_distribution_file_path": "/etc/os-release",
"ansible_distribution_file_variety": "Debian",
"ansible_distribution_major_version": "18",
"ansible_distribution_release": "bionic",
"ansible_distribution_version": "18.04",

# CentOS
"ansible_distribution": "CentOS",
"ansible_distribution_file_parsed": true,
"ansible_distribution_file_path": "/etc/redhat-release",
"ansible_distribution_file_variety": "RedHat",
"ansible_distribution_major_version": "7",
"ansible_distribution_release": "core",
"ansible_distribution_version": "7.6"

# OracleLinux
"ansible_distribution": "OracleLinux",
"ansible_distribution_file_parsed": true,
"ansible_distribution_file_path": "/etc/oracle-release",
"ansible_distribution_file_search_string": "Oracle Linux",
"ansible_distribution_file_variety": "OracleLinux",
"ansible_distribution_major_version": "7",
"ansible_distribution_release": "NA",
"ansible_distribution_version": "7.7",
```

## Cockpit

Cockpit 建议采用 `yum install cockpit*` 这种批量安装方式，确保安装所有与之相关的包
