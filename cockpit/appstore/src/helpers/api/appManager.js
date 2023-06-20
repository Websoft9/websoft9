import { APICore } from './apiCore';

const api = new APICore();

//App 安装
function AppInstall(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppInstall';
    return api.get(`${baseUrl}`, params);
}


//更新应用列表
function AppStoreUpdate(params: any): Promise<any> {
    const baseUrl = '/AppManage/AppStoreUpdate';
    return api.get(`${baseUrl}`, params);
}

export { AppInstall, AppStoreUpdate };

