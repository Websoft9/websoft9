import axios from 'axios';
import { Navigate } from "react-router-dom";

// 定义一个全局变量来存储 config.json 的内容
let credentials;

async function getCredentials() {
    // 如果 credentials 不存在，就从 config.json 中获取它
    if (!credentials) {
        const response = await fetch('../myapps/config.json');
        const data = await response.json();
        const userName = data.APPMANAGE.APPMANAGE_USERNAME;
        const uerPassword = data.APPMANAGE.APPMANAGE_PASSWORD;
        credentials = btoa(userName + ":" + uerPassword);
    }
    // 返回 credentials
    return credentials;
}

// 设置 axios 的默认配置
axios.defaults.headers.post['Content-Type'] = 'application/json';
axios.defaults.headers.get['Content-Type'] = 'application/json';
axios.defaults.headers.common['Cache-Control'] = 'no-cache';
axios.defaults.headers.common['Pragma'] = 'no-cache';
axios.defaults.headers.common['Expires'] = '0';

// 拦截响应以捕获错误
axios.interceptors.response.use(
    (response) => {
        return response;
    },
    (error) => {
        // 任何不在 2xx 范围内的状态码都会触发这个函数
        let message;

        if (error && error.response && error.response.status === 404) {
            <Navigate to="/error-404" />
        } else if (error && error.response && error.response.status === 500) {
            <Navigate to="/error-500" />
        } else {
            message = error.response && error.response.data ? error.response.data['message'] : error.message || error;
            return Promise.reject(message);
        }
    }
);

class APICore {
    /**
    * Fetches data from given url
    */
    get = async (url, params) => {
        // 等待获取凭证并设置授权头
        axios.defaults.headers.common['Authorization'] = 'Basic ' + await getCredentials();
        let response;
        if (params) {
            var queryString = params
                ? Object.keys(params)
                    .map((key) => key + '=' + params[key])
                    .join('&')
                : '';
            response = axios.get(`${url}?${queryString}`, params);
        } else {
            response = axios.get(`${url}`, params);
        }
        return response;
    };

    /**
    * post given data to url
    */
    create = async (url, data) => {
        // 等待获取凭证并设置授权头
        axios.defaults.headers.common['Authorization'] = 'Basic ' + await getCredentials();
        return axios.post(url, data);
    };
}

export { APICore };
