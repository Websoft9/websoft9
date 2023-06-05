import axios from 'axios';
import cockpit from "cockpit";
import React, { useEffect, useState } from 'react';
import { Badge, Button, Card, Col, Row, Table } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';

const _ = cockpit.gettext;

const AppContainer = (props): React$Element<React$FragmentType> => {
    const navigate = useNavigate(); //用于页面跳转
    const [containersInfo, setContainersInfo] = useState([]);
    const customer_name = props.data.customer_name;
    const [endpointsId, setEndpointsId] = useState(null);

    //通过Portainer的接口获取容器数据
    const getContainersData = async () => {
        try {
            let jwt = window.localStorage.getItem("portainer.JWT2"); //获取存储在本地的JWT数据 
            let id = null;

            //如果获取不到jwt，则模拟登录并写入新的jwt
            if (jwt === null) {
                const response = await axios.get('./config.json'); //从项目下读取配置文件
                if (response.status === 200) {
                    let config = response.data.PORTAINER;
                    const { PORTAINER_USERNAME, PORTAINER_PASSWORD, PORTAINER_AUTH_URL, PORTAINER_HOME_PAGE } = config;

                    //调用portainer的登录API，模拟登录
                    const authResponse = await axios.post(PORTAINER_AUTH_URL, {
                        username: PORTAINER_USERNAME,
                        password: PORTAINER_PASSWORD
                    });
                    if (authResponse.status === 200) {
                        jwt = "\"" + authResponse.data.jwt + "\"";
                        //jwt = authResponse.data.jwt
                        window.localStorage.setItem('portainer\.JWT2', jwt); //关键是将通过API登录后获取的jwt，存储到本地localStorage
                    } else {
                        console.error('Error:', authResponse);
                    }
                }
                else {
                    console.error('Error:', response);
                }
            }

            //从portainer接口获取endpoints
            const endpointsData = await axios.get('/portainer/api/endpoints', {
                headers: {
                    'Authorization': 'Bearer ' + jwt.replace(/"/g, '')
                }
            });
            if (endpointsData.status === 200) {
                //先判断是否获取了“本地”endpoint
                if (endpointsData.data.length == 0) { //没有“本地”endpoint
                    //调用添加"本地"环境的接口
                    const addEndpoint = await axios.post('/portainer/api/endpoints', {},
                        {
                            params: {
                                Name: "websoft9-local",
                                EndpointCreationType: 1
                            },
                            headers: {
                                'Authorization': 'Bearer ' + jwt.replace(/"/g, '')
                            }
                        }
                    );
                    if (addEndpoint.status === 200) {
                        id = addEndpoint.data?.Id;
                        setEndpointsId(id);
                    }
                    else {
                        console.error('Error:', addEndpoint);
                    }
                }
                else {
                    //应该可能会返回“远程”的endpoint，这里只获取“本地”endpoint,条件为URL包含'/var/run/docker.sock'
                    id = endpointsData.data.find(({ URL }) => URL.includes('/var/run/docker.sock')).Id;
                    setEndpointsId(id);
                }

                //调用接口获取
                const containersData = await axios.get(`/portainer/api/endpoints/${id}/docker/containers/json`, {
                    headers: {
                        'Authorization': 'Bearer ' + jwt.replace(/"/g, '')
                    },
                    params: {
                        all: true,
                        filters: JSON.stringify({ "label": [`com.docker.compose.project=${customer_name}`] })
                    }
                })
                if (containersData.status === 200) {
                    setContainersInfo(containersData.data);
                }
                else {
                    console.error('Error:', containersData);
                }
            }
            else {
                console.error('Error:', endpointsData);
            }
        }
        catch (error) {
            console.error('Error:', error);
            //navigate("/error-500");
        }
    }

    useEffect(() => {
        getContainersData();
    }, []);

    return (
        <Row>
            <Col xs={12}>
                <Card>
                    <Card.Header>
                        <Row className="align-items-center">
                            <Col xs={12} md={10}>
                                <label className="me-2 fs-5 d-block">{_("Container")}</label>
                                <span className="me-2 fs-6">
                                    {cockpit.format(_("This application consists of the following containers, and the one named $0 is the main container."), customer_name)}
                                </span>
                            </Col>
                            <Col xs={12} md={2}>
                                <a href={`/portainer/#!/${endpointsId}/docker/stacks/${customer_name}?type=2&regular=false&external=true&orphaned=false`}
                                    target="_blank" className="me-2">
                                    <Button variant="primary" size="sm" className="float-end">{_("More")}</Button>
                                </a>
                            </Col>
                        </Row>
                    </Card.Header>
                    <Card.Body>
                        <Table className="mb-0">
                            <thead>
                                <tr>
                                    <th>{_("Name")}</th>
                                    <th>{_("State")}</th>
                                    <th style={{ textAlign: 'center' }}>{_("Actions")}</th>
                                    <th>{_("Image")}</th>
                                    <th>{_("Created")}</th>
                                    <th>{_("Ip Address")}</th>
                                    <th>{_("Published Ports")}</th>
                                </tr>
                            </thead>
                            <tbody>
                                {containersInfo.map((container, index) => {
                                    return (
                                        <tr key={index}>
                                            <td>{container.Names?.[0]?.replace(/^\/|\/$/g, '')}</td>
                                            <td>
                                                <Badge className={`${container.State === 'running' ? 'bg-success' : container.State === 'exited' ? 'bg-danger' : 'info'}`}>
                                                    {container.State}
                                                </Badge>
                                            </td>
                                            <td style={{ textAlign: 'center' }}>
                                                <a href={`/portainer/#!/${endpointsId}/docker/containers/${container.Id}/logs`}
                                                    target="_blank" title='Logs'>
                                                    <i className="dripicons-document-remove noti-icon"></i>{' '}
                                                </a>
                                                {
                                                    container.State === "running" && (
                                                        <a href={`/portainer/#!/${endpointsId}/docker/containers/${container.Id}/stats`}
                                                            target="_blank" title='Stats'>
                                                            <i className="dripicons-pulse noti-icon"></i>{' '}
                                                        </a>
                                                    )
                                                }

                                            </td>
                                            <td>{container.Image}</td>
                                            <td>{new Date(container.Created * 1000).toLocaleString()}</td>
                                            <td>{container.NetworkSettings.Networks[container.HostConfig.NetworkMode].IPAddress}</td>
                                            <td>{container.Ports.find(port => port.IP && /^(\d{1,3}\.){3}\d{1,3}$/.test(port.IP))?.PublicPort}:{container.Ports.find(port => port.IP && /^(\d{1,3}\.){3}\d{1,3}$/.test(port.IP))?.PrivatePort}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </Table>
                    </Card.Body>
                </Card>
            </Col>
        </Row >
    );
}

export default AppContainer;