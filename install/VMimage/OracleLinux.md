# Oracle Linux

## Requirement

- OS disk automaticlly resize
- User can user password or key both for create VM or reset password
- OS start methond on Cloud: BIOS/UEFI
- Disk partition: LVM/?
- Softwares: cloud-init, agent of Cloud provider
- Other config: https://github.com/Websoft9/mcloud/blob/master/ansible/roles/desktop/tasks/image.yml
- Applicaitons: Desktop, Docker/Podman, Java

## Upgrade

You can use [leapp](https://docs.oracle.com/en/learn/ol-linux-leapp) to upgrade major version, e.g Oracle Linux8 > Oracle Linux9
