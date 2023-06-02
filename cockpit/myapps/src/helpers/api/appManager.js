import { APICore } from './apiCore';

const api = new APICore();

//App 安装
function AppInstall(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppInstall';
    return api.get(`${baseUrl}`, params);
}

//App 列表查询
function AppList(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppList';
    return api.get(`${baseUrl}`, params);
}

//App 卸载
function AppUninstall(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppUninstall';
    return api.get(`${baseUrl}`, params);
}

//App 停止
function AppStop(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppStop';
    return api.get(`${baseUrl}`, params);
}

//App 启动
function AppStart(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppStart';
    return api.get(`${baseUrl}`, params);
}

//App 重启
function AppRestart(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppRestart';
    return api.get(`${baseUrl}`, params);
}

//App 状态查询
function AppStatus(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppStatus';
    return api.get(`${baseUrl}`, params);
}

//查询APP对应的域名
function AppDomainList(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppDomainList';
    return api.get(`${baseUrl}`, params);
}

//删除APP绑定的域名
function AppDomainDelete(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppDomainDelete';
    return api.get(`${baseUrl}`, params);
}

//修改APP绑定的域名
function AppDomainUpdate(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppDomainUpdate';
    return api.get(`${baseUrl}`, params);
}

//APP绑定域名
function AppDomainAdd(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppDomainAdd';
    return api.get(`${baseUrl}`, params);
}

//设定默认域名
function AppDomainSet(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppDomainSet';
    return api.get(`${baseUrl}`, params);
}

export { AppInstall, AppList, AppUninstall, AppStop, AppStart, AppRestart, AppStatus, AppDomainList, AppDomainDelete, AppDomainUpdate, AppDomainAdd, AppDomainSet };

