import classnames from "classnames";
import cockpit from 'cockpit';
import React, { useEffect, useRef, useState } from 'react';
import { Button, Col, Modal, Nav, OverlayTrigger, Row, Tab, Tooltip } from 'react-bootstrap';
import { Link, useNavigate } from 'react-router-dom';
import DefaultImg from '../assets/images/default.png';
import Spinner from '../components/Spinner';
import { AppRestart, AppStart, AppStop } from '../helpers';
import AppAccess from './appdetailtabs/appaccess';
import AppContainer from './appdetailtabs/appcontainer';
import AppOverview from './appdetailtabs/appoverview';
import Uninstall from './appdetailtabs/appuninstall';

const _ = cockpit.gettext;

const AppDetailModal = (props): React$Element<React$FragmentType> => {
    const [restartDisable, setRestartDisable] = useState(false);//用于重启按钮的按钮禁用
    const [buttonDisable, setButtonDisable] = useState(false); //用于启动/停止按钮禁用
    const [currentApp, setCurrentApp] = useState(props.current_app);
    const [startAppLoading, setStartAppLoading] = useState(false); //用户显示启动应用的加载状态
    const [stopAppLoading, setStopAppLoading] = useState(false); //用户显示停止时应用的加载状态
    const [restartAppLoading, setRestartAppLoading] = useState(false); //用户显示重启时应用的加载状态
    const navigate = useNavigate(); //用于页面跳转
    const childRef = useRef();

    //设置卸载页面的按钮禁用
    const setUninstallButtonDisable = () => {
        // 通过ref调用子组件的方法
        childRef.current.setButtonDisable();
    };

    //设置卸载页面的按钮启用
    const setUninstallButtonEnable = () => {
        // 通过ref调用子组件的方法
        childRef.current.setButtonEnable();
    };

    //设置启动/停止按钮禁用,用于传递给卸载页面
    const setAppdetailButtonDisable = () => {
        setButtonDisable(true);
        setRestartDisable(true);
    };
    //设置启动/停止按钮启用,用于传递给卸载页面
    const setAppdetailButtonEnable = () => {
        setButtonDisable(false);
        setRestartDisable(false);
    };

    useEffect(() => {
        setCurrentApp(props.current_app);
    }, [props.current_app]);

    const tabContents = [
        {
            id: '1',
            title: _("Overview"),
            icon: 'mdi dripicons-home',
            text: <AppOverview data={currentApp} />,
        },
        {
            id: '2',
            title: _("Access"),
            icon: 'mdi dripicons-web',
            text: <AppAccess data={currentApp} />,
        },
        {
            id: '3',
            title: _("Container"),
            icon: 'mdi dripicons-stack',
            text: <AppContainer data={currentApp} />,
        },
        {
            id: '4',
            title: _("Uninstall"),
            icon: 'mdi mdi-cog-outline',
            text: <Uninstall data={currentApp} ref={childRef} disabledButton={setAppdetailButtonDisable} enableButton={setAppdetailButtonEnable}
                onDataChange={props.onDataChange} onCloseFatherModal={props.onClose} />,
        },
    ];

    return (
        currentApp && <Modal show={props.showFlag} backdrop="static" onHide={props.onClose} size="lg" scrollable="true" dialogClassName="modal-full-width" >
            <Modal.Header onHide={props.onClose} closeButton>
                <div style={{ padding: "10px", display: "flex", width: "100%", alignItems: "center" }}>
                    <div className='appstore-item-content-icon col-same-height'>
                        <img
                            src={currentApp.image_url}
                            alt=""
                            className="app-icon"
                            onError={(e) => (e.target.src = DefaultImg)}
                        />
                    </div>
                    <div className='col-same-height'>
                        <h4 className="appstore-item-content-title" style={{ marginTop: "5px" }}>
                            {currentApp.customer_name}
                        </h4>
                        <h5 className="appstore-item-content-title" style={{ marginTop: "5px" }}>
                            {currentApp.status}
                        </h5>
                    </div>
                    <div className='col-same-height' style={{ flexGrow: 1, display: "flex", justifyContent: "flex-end", alignItems: "center" }}>
                        {
                            currentApp.status === "exited" &&
                            <OverlayTrigger
                                key="bottom1"
                                placement="bottom"
                                overlay={
                                    <Tooltip id="tooltip-bottom">
                                        {_("Start App")}
                                    </Tooltip>
                                }>
                                <Button variant="primary" disabled={buttonDisable}
                                    style={{ padding: "5px 10px", borderRadius: "3px", marginRight: "10px" }}
                                    onClick={async () => {
                                        setUninstallButtonDisable();
                                        setStartAppLoading(true);
                                        setRestartDisable(true);
                                        try {
                                            const response = await AppStart({ app_id: currentApp.app_id });
                                            if (response.data.Error) {
                                                navigate("/error")
                                            }
                                            else {
                                                props.onDataChange();
                                            }
                                        }
                                        catch (error) {
                                            navigate("/error-500");
                                        }
                                        finally {
                                            setUninstallButtonEnable();
                                            setStartAppLoading(false);
                                            setRestartDisable(false);
                                        }
                                    }}
                                >
                                    {
                                        startAppLoading ?
                                            <Spinner className="spinner-border-sm noti-icon" color="light" />
                                            :
                                            <i className="dripicons-media-play noti-icon"></i>
                                    }
                                </Button>
                            </OverlayTrigger>
                        }
                        {
                            currentApp.status === "running" &&
                            <OverlayTrigger
                                key="bottom2"
                                placement="bottom"
                                overlay={
                                    <Tooltip id="tooltip-bottom">
                                        {_("Stop App")}
                                    </Tooltip>
                                }>
                                <Button variant="primary" disabled={buttonDisable}
                                    style={{ padding: "5px 10px", borderRadius: "3px", marginRight: "10px" }}
                                    onClick={async () => {
                                        setUninstallButtonDisable();
                                        setStopAppLoading(true);
                                        setRestartDisable(true);
                                        try {
                                            const response = await AppStop({ app_id: currentApp.app_id });
                                            if (response.data.Error) {
                                                navigate("/error");
                                            }
                                            else {
                                                props.onDataChange();
                                            }
                                        }
                                        catch (error) {
                                            navigate("/error-500");
                                        }
                                        finally {
                                            setUninstallButtonEnable();
                                            setStopAppLoading(false);
                                            setRestartDisable(false);
                                        }
                                    }}
                                >
                                    {
                                        stopAppLoading ?
                                            <Spinner className="spinner-border-sm noti-icon" color="light" />
                                            :
                                            <i className="dripicons-power noti-icon"></i>
                                    }
                                </Button>
                            </OverlayTrigger>
                        }
                        <OverlayTrigger
                            key="bottom3"
                            placement="bottom"
                            overlay={
                                <Tooltip id="tooltip-bottom">
                                    {_("Restart App")}
                                </Tooltip>
                            }>
                            <Button disabled={restartDisable}
                                style={{ padding: "5px 10px", borderRadius: "3px", marginRight: "10px" }}
                                onClick={async () => {
                                    try {
                                        setUninstallButtonDisable();
                                        setRestartAppLoading(true);
                                        setButtonDisable(true);
                                        const response = await AppRestart({ app_id: currentApp.app_id });
                                        if (response.data.Error) {
                                            navigate("/error");
                                        }
                                        else {
                                            props.onDataChange();
                                        }
                                    }
                                    catch (error) {
                                        navigate("/error-500");
                                    }
                                    finally {
                                        setUninstallButtonEnable();
                                        setRestartAppLoading(false);
                                        setButtonDisable(false);
                                    }
                                }}
                            >
                                {
                                    restartAppLoading ?
                                        <Spinner className="spinner-border-sm noti-icon" color="light" />
                                        :
                                        <i className="dripicons-clockwise noti-icon"></i>
                                }
                            </Button>
                        </OverlayTrigger>
                        {
                            currentApp.status === "running" &&
                            <OverlayTrigger
                                key="bottom4"
                                placement="bottom"
                                overlay={
                                    <Tooltip id="tooltip-bottom">
                                        {_("Terminal")}
                                    </Tooltip>
                                }>
                                <Link to={{ pathname: '/terminal', search: `?id=${currentApp.customer_name}` }}
                                    style={{ color: "#fff", backgroundColor: "#727cf5", padding: "5px 10px", borderRadius: "3px", borderColor: "#727cf5", marginRight: "10px" }}
                                    target="_blank">
                                    <i className="dripicons-code noti-icon"></i>{' '}
                                </Link>
                            </OverlayTrigger>
                        }
                        {
                            <OverlayTrigger
                                key="bottom5"
                                placement="bottom"
                                overlay={
                                    <Tooltip id="tooltip-bottom">
                                        {_("Documentation")}
                                    </Tooltip>
                                }>
                                <a href={'https://support.websoft9.com/docs/' + currentApp.app_name}
                                    style={{ color: "#fff", backgroundColor: "#727cf5", padding: "5px 10px", borderRadius: "3px", borderColor: "#727cf5", marginRight: "10px" }}
                                    target="_blank">
                                    <i className="dripicons-document noti-icon"></i>{' '}
                                </a>
                            </OverlayTrigger>
                        }
                    </div>
                </div>
            </Modal.Header>
            <Modal.Body className="row">
                <Tab.Container defaultActiveKey={_("Overview")}>
                    <Col sm={2} className="mb-2 mb-sm-0">
                        <Nav variant="pills" className="flex-column">
                            {tabContents.map((tab, index) => {
                                const renderElement = () => {
                                    return (
                                        <Nav.Item key={index}>
                                            <Nav.Link as={Link} to="#" eventKey={tab.title}>
                                                <i
                                                    className={classnames(
                                                        tab.icon,
                                                        'd-md-none',
                                                        'd-block',
                                                        'me-1'
                                                    )}></i>
                                                <span className="d-none d-md-block">{tab.title}</span>
                                            </Nav.Link>
                                        </Nav.Item>
                                    );
                                }
                                if (tab.title === "Terminal") {
                                    if (currentApp.status === "running") {
                                        return renderElement();
                                    }
                                } else {
                                    return renderElement();
                                }
                            })}
                        </Nav>
                    </Col>
                    <Col sm={10}>
                        <Tab.Content style={{ height: "100%" }}>
                            {tabContents.map((tab, index) => {
                                return (
                                    <Tab.Pane eventKey={tab.title} id={tab.id} key={index} style={{ height: "100%" }}>
                                        <Row style={{ height: "100%" }}>
                                            <Col sm="12" style={{ height: tab.title === "Terminal" ? "600px" : "" }}>
                                                {tab.text}
                                            </Col>
                                        </Row>
                                    </Tab.Pane>
                                );
                            })}
                        </Tab.Content>
                    </Col>
                </Tab.Container>
            </Modal.Body>
        </Modal >
    );
}

export default AppDetailModal;