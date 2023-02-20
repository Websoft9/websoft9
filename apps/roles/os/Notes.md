## 可视化

Linux 可视化可以从 Desktop 和 Web GUI 两个方案考量。不同的操作系统发行版加上可视化的翅膀后，可以形成20个镜像商品

### Desktop

* Desktop: KDE, GNOME, 深度等
* Server: VNCServer,XDRP Server（依赖VNCServer）
* 客户端：VNC和Windows远程桌面客户端

最好可以支持两种客户端

### Web-GUI

Cockpit 是红帽开发的网页版图像化服务管理工具，优点是无需中间层，且可以管理多种服务。  

Cockpit 安装已经移到 role_common


## 上传OS

目前有如下 Linux 发行版有分发的价值：

* Oracle Linux
* 深度

上传的自定义镜像OS，除了满足云平台要求之外，还需额外安装云平添的 Cloud Agent，例如：阿里云的安骑士。

## 待研究

1. 安装tigerVNC 之后，默认生成了 vncserver@.server模板，本Ansible role 中的service模板是修改后的内容
2. 所有的启动设置之前，都可以加上一个连词号（-），表示"抑制错误"，即发生错误的时候，不影响其他命令的执行

## 上架版本

|云平台&桌面名称|  GNOME  |   KDE  |  Xfce  |  Mate  | 
|  -------------- |  --------------  | --------------  | --------------  | --------------  |
|阿里云CentOS|  √  |√|√|√|
|阿里云Ubuntu|√|-|√|-|
|阿里云OracleLinux7.8|√|√|√|-|
|腾讯云CentOS|√|√|-|-|
|腾讯云Ubuntu|√|-|√|-|
|华为云CentOS|√|√|||
|华为云Ubuntu|||||
|Azure CentOS|√|√|√|√|
|Azure Ubuntu|-|-|√|-|
|AWS Amazonlinux|-|-|√|√|
|AWS Ubuntu|√|-|√|-|

## 常见问题

#### 阿里云上 OracleLinux 无法通过控制台下发秘钥对？

确保安骑士服务启动，且安骑士版本是阿里云版本

#### Oracle Linux 如何安装 epel 等软件包？

Oracle Linux 提供了非常快捷等安装方式（[参考](https://yum.oracle.com/getting-started.html#installing-software-from-oracle-linux-yum-server)）  
例如：yum install oracle-epel-release-el8

