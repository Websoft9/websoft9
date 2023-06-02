import cockpit from "cockpit";
import React from 'react';
import { Card, Col, Row, Table } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';

const _ = cockpit.gettext;

const AppOverview = (props): React$Element<React$FragmentType> => {
    const navigate = useNavigate(); //用于页面跳转

    return (
        <Row>
            <Col xs={12}>
                <Card>
                    <Card.Header>
                        <label className="me-2 fs-5 d-block">应用概览</label>
                    </Card.Header>
                    <Card.Body>
                        <Table responsive className="mb-0" bordered={false} style={{ display: 'flex' }}>
                            <tbody>
                                <tr>
                                    <td style={{ fontWeight: "bold" }}>应用名称：</td>
                                    <td>{props.data?.app_name}</td>
                                </tr>
                                <tr>
                                    <td style={{ fontWeight: "bold" }}>应用版本：</td>
                                    <td>{props.data?.app_version}</td>
                                </tr>
                                <tr>
                                    <td style={{ fontWeight: "bold" }}>应用端口：</td>
                                    <td>{props.data?.config?.port}</td>
                                </tr>
                                <tr>
                                    <td style={{ fontWeight: "bold" }}>创建时间：</td>
                                    <td>{props.data?.create_time}</td>
                                </tr>
                                <tr>
                                    <td style={{ fontWeight: "bold" }}>配置目录： </td>
                                    <td>{props.data?.config_path}</td>
                                </tr>
                                <tr>
                                    <td style={{ fontWeight: "bold" }}>数据目录：</td>
                                    <td>{props.data?.volume_data}</td>
                                </tr>
                            </tbody>
                        </Table>
                        {/* <Table responsive className="mb-0" bordered={false}>
                            <tbody>
                                <tr>
                                    <td style={{ width: '10%', fontWeight: "bold" }}>应用名称：</td>
                                    <td>{props.data?.app_name}</td>
                                    <td style={{ width: '10%', fontWeight: "bold" }}>应用版本：</td>
                                    <td>{props.data?.app_version}</td>
                                </tr>
                                <tr>
                                    <td style={{ width: '10%', fontWeight: "bold" }}>应用端口：</td>
                                    <td>{props.data?.config?.port}</td>
                                    <td style={{ width: '10%', fontWeight: "bold" }}>创建时间：</td>
                                    <td>{props.data?.create_time}</td>
                                </tr>
                                <tr>
                                    <td style={{ width: '10%', fontWeight: "bold" }}>配置目录： </td>
                                    <td>{props.data?.config_path}</td>
                                    <td style={{ width: '10%', fontWeight: "bold" }}>数据目录：</td>
                                    <td>{props.data?.volume_data}</td>
                                </tr>
                            </tbody>
                        </Table> */}
                    </Card.Body>
                </Card>
            </Col>
        </Row>
    );
}

export default AppOverview;