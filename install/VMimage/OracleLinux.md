# Oracle Linux

## How to create VM image?

You should download [Oracle Linux image](https://yum.oracle.com/oracle-linux-templates.html) from official website, don't try to build image from ISO manual setup by KVM/VMVare/VirtualBox

## Cloud image requirements

- Kernel: Unbreakable Enterprise Kernel (UEK)/Red Hat Compatible Kernel(RHCK)
- OS disk automaticlly resize
- User can user password or key both for create VM or reset password
- OS start methond on Cloud: BIOS/UEFI
- Disk partition: LVM/?
- File system type: FAT32、EXT2、EXT3、EXT4、UFS?
- Softwares: cloud-init, agent of Cloud provider, virtio, NVMe, 
- Other config: https://github.com/Websoft9/mcloud/blob/master/ansible/roles/desktop/tasks/image.yml
- Applicaitons: Desktop, Docker/Podman, Java

## Upgrade Oracle Linux

You can use [leapp](https://docs.oracle.com/en/learn/ol-linux-leapp) to upgrade major version, e.g Oracle Linux8 > Oracle Linux9

## Test your Cloud private image

Some Cloud provider have tools for your image testing:  

- [阿里云 sersi](https://help.aliyun.com/zh/ecs/user-guide/check-whether-an-image-meets-the-import-requirements)
