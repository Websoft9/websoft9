# 模板说明

## 快速使用

以此模板创建项目之后，依次参考如下步骤完成后续设置

1. 依次替换文件（夹）和关键词 **RabbitMQ** 和 **rabbitmq**
2. 依次完成如下文件的改写
   ```
   /rabbitmq.yml
   /requirements.yml
   /vars/main.yml
   ```
3. 完成对应的role的编写
4. 改写文档
5. 日志填写

## 模板说明

### 架构

Playbook 主体结构
  - vars：主变量
  - roles：用于存放role目录
  - rabbitmq.yml : 项目主入口文件
  - docs：用于存放文档
  - .github：用于存放 GitHub Actions 配置
  - ansible.cfg 


### 注意事项

1. 尽量少用应用模块，例如Docker模块，MySQL模块
2. 文件删除请直接使用 Shell 命令
3. 每一行代码必须考虑非root用户运行的权限问题
4. 使用公共模块完成依赖安装
5. 软件的安装与配置逻辑上做出分离