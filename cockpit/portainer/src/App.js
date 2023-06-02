import axios from 'axios';
import 'bootstrap/dist/css/bootstrap.min.css';
import { useEffect, useState } from 'react';
import Spinner from 'react-bootstrap/Spinner';
import './App.css';

function App() {
  const [portainerJWT, setPortainerJWT] = useState(null);
  const [portainerHomePage, setPortainerHomePage] = useState(null);

  const getData = async () => {
    try {
      const response = await axios.get('../appstore/config.json'); //从项目下读取配置文件
      if (response.status === 200) {
        let config = response.data.PORTAINER;
        const { PORTAINER_USERNAME, PORTAINER_PASSWORD, PORTAINER_AUTH_URL, PORTAINER_HOME_PAGE } = config;
        setPortainerHomePage(PORTAINER_HOME_PAGE);

        //调用portainer的登录API，模拟登录
        const authResponse = await axios.post(PORTAINER_AUTH_URL, {
          username: PORTAINER_USERNAME,
          password: PORTAINER_PASSWORD
        });
        if (authResponse.status === 200) {
          let jwt = "\"" + authResponse.data.jwt + "\"";
          setPortainerJWT(jwt);
          window.localStorage.setItem('portainer\.JWT', jwt); //关键是将通过API登录后获取的jwt，存储到本地localStorage
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
        portainerJWT && portainerHomePage ? (
          <div class='myPortainer' key='container'>
            <iframe title='portainer' src={portainerHomePage} />
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