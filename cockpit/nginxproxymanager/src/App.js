import axios from 'axios';
import 'bootstrap/dist/css/bootstrap.min.css';
import { useEffect, useState } from 'react';
import Spinner from 'react-bootstrap/Spinner';
import './App.css';

function App() {
  const [nginxproxymanagerTokens, setNginxproxymanagerTokens] = useState(null);
  const [nginxproxymanagerHomePage, setNginxproxymanagerHomePage] = useState(null);

  const getData = async () => {
    try {
      const response = await axios.get('../myapps/config.json'); //从项目下读取配置文件
      if (response.status === 200) {
        const config = response.data.NGINXPROXYMANAGER;
        const { NGINXPROXYMANAGER_USERNAME, NGINXPROXYMANAGER_PASSWORD, NGINXPROXYMANAGER_AUTH_URL, NGINXPROXYMANAGER_HOME_PAGE, NGINXPROXYMANAGER_NIKENAME } = config;
        setNginxproxymanagerHomePage(NGINXPROXYMANAGER_HOME_PAGE);

        //调用nginxproxymanager的登录API，模拟登录
        const authResponse = await axios.post(NGINXPROXYMANAGER_AUTH_URL, {
          identity: NGINXPROXYMANAGER_USERNAME,
          secret: NGINXPROXYMANAGER_PASSWORD
        });
        if (authResponse.status === 200) {
          const tokens = authResponse.data.token;
          setNginxproxymanagerTokens(tokens);
          const nginx_proxy_manager_tokens = [{ "t": tokens, "n": NGINXPROXYMANAGER_NIKENAME }];
          window.localStorage.setItem('nginx-proxy-manager-tokens', JSON.stringify(nginx_proxy_manager_tokens)); //关键是将通过API登录后获取的tokens，存储到本地localStorage
        } else {
          console.log('Error:', authResponse);
        }
      }
      else {
        console.log('Error:', response);
      }
    } catch (error) {
      console.log('Error:', error);
    }
  }

  useEffect(() => {
    getData();
  }, []);

  return (
    <>
      {
        nginxproxymanagerTokens && nginxproxymanagerHomePage ? (
          <div className='myNginx' key='container'>
            <iframe title='nginxproxymanager' src={nginxproxymanagerHomePage} />
          </div>
        ) : (
          <div className="d-flex align-items-center justify-content-center m-5">
            <Spinner animation="border" variant="secondary" />
          </div>
        )
      }
    </>
  );
}

export default App;