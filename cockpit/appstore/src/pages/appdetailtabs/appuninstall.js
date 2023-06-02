import classNames from 'classnames';
import cockpit from 'cockpit';
import React, { forwardRef, useImperativeHandle, useState } from 'react';
import { Alert, Button, Col, Modal, Row } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import Spinner from '../../components/Spinner';
import { AppStart, AppStop, AppUninstall } from '../../helpers';

const _ = cockpit.gettext;

//卸载应用时的确定/取消弹窗
const UninstallConform = (props) => {
    const navigate = useNavigate(); //用于页面跳转
    const [disable, setDisable] = useState(false);//用于按钮禁用
    const [showAlert, setShowAlert] = useState(false); //用于是否显示错误提示
    const [alertMessage, setAlertMessage] = useState("");//用于显示错误提示消息

    function closeAllModals() {
        //关闭弹窗
        props.onClose();
        props.onCloseFatherModal();

        //更新主页APP的数据
        props.onDataChange();
    }

    return (
        <Modal show={props.showConform} onHide={props.onClose} size="lg"
            scrollable="true" backdrop="static" style={{ backgroundColor: "rgba(0,0,0,0.8)" }}>
            <Modal.Header onHide={props.onClose} closeButton className={classNames('modal-colored-header', 'bg-warning')}>
                <h4>{_("Uninstall")} {props.app.customer_name}</h4>
            </Modal.Header>
            <Modal.Body className="row" >
                <span style={{ margin: "10px 0px" }}>{_("This will immediately uninstall")} {props.app.customer_name} {_("and remove all its data.")}</span>
                <div>
                    {showAlert && <Alert variant="danger" className="my-2">
                        {alertMessage}
                    </Alert>}
                </div>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="light" onClick={props.onClose}>
                    {_("Close")}
                </Button>{" "}
                <Button disabled={disable} variant="warning" onClick={async () => {
                    try {
                        setDisable(true);
                        //调用卸载应用接口
                        const response = await AppUninstall({ app_id: props.app.app_id });
                        if (response.data.Error) {
                            setShowAlert(true);
                            setAlertMessage(response.data.Error.Message);
                        }
                        else {
                            closeAllModals(); //关闭弹窗并更新数据
                        }
                    }
                    catch (error) {
                        navigate("/error-500");
                    }
                }}>
                    {disable && <Spinner className="spinner-border-sm me-1" tag="span" color="white" />} {_("Uninstall")}
                </Button>
            </Modal.Footer>
        </Modal >
    );
}

//卸载应用选项卡
const Uninstall = forwardRef((props, ref): React$Element<React$FragmentType> => {
    const [showUninstallConform, setShowUninstallConform] = useState(false);//用于确认卸载弹窗的标识
    const [disable, setDisable] = useState(false);//用于按钮禁用
    const navigate = useNavigate(); //用于页面跳转

    //用于显示确定/取消卸载应用的弹窗
    const handleClick = () => {
        setShowUninstallConform(true);
    };
    //用于关闭确定/取消卸载应用的弹窗
    const handleClose = () => {
        setShowUninstallConform(false);
    };

    //设置按钮禁用
    const setButtonDisable = () => {
        setDisable(true);
    };

    //设置按钮启用
    const setButtonEnable = () => {
        setDisable(false);
    };

    //提供给父组件调用的方法，用于在父组件中调用子组件的方法
    useImperativeHandle(ref, () => ({
        setButtonDisable,
        setButtonEnable,
    }));

    return (
        <>
            <Row className="mb-2">
                <Col sm={12}>
                    <label className="me-1" style={{ fontWeight: "bolder", marginBottom: "5px" }}>{_("Start / Stop")}</label>
                    <p>
                        {_("Apps can be stopped to conserve server resources instead of uninstalling.")}
                    </p>
                    {props.data.status === "running" ?
                        <Button variant="secondary" className="float-end" disabled={disable} onClick={async () => {
                            try {
                                props.disabledButton();
                                setDisable(true);
                                //调用应用停止接口
                                const response = await AppStop({ app_id: props.data.app_id });
                                if (response.data.Error) {
                                    navigate("/error")
                                }
                                else {
                                    props.onDataChange(props.data.app_id);
                                }
                            }
                            catch (error) {
                                navigate("/error-500");
                            }
                            finally {
                                setDisable(false);
                                props.enableButton();
                            }
                        }}>
                            {disable && <Spinner className="spinner-border-sm me-1" tag="span" color="white" />} {_("Stop")}
                        </Button>
                        :
                        <Button variant="primary" className="float-end" disabled={disable}
                            onClick={async () => {
                                props.disabledButton();
                                setDisable(true);
                                try {
                                    const response = await AppStart({ app_id: props.data.app_id });
                                    if (response.data.Error) {
                                        navigate("/error")
                                    }
                                    else {
                                        props.onDataChange(props.data.app_id);
                                    }
                                }
                                catch (error) {
                                    navigate("/error-500");
                                }
                                finally {
                                    props.enableButton();
                                    setDisable(false);
                                }
                            }}>
                            {disable && <Spinner className="spinner-border-sm me-1" tag="span" color="white" />} {_("Start")}
                        </Button>
                    }
                </Col>
            </Row>
            <hr></hr>
            <Row className="mb-2">
                <Col sm={12}>
                    <label className="me-1" style={{ fontWeight: "bolder", marginBottom: "5px" }}>{_("Uninstall")}</label>
                    <p>
                        {_("This will uninstall the app immediately and remove all its data.The app will be inaccessible.")}
                    </p>
                    <Button variant="warning" className="float-end" onClick={() => { handleClick() }} >
                        {_("Uninstall")}
                    </Button>
                </Col>
            </Row>
            {showUninstallConform && <UninstallConform showConform={showUninstallConform} onClose={handleClose}
                app={props.data} onDataChange={props.onDataChange} onCloseFatherModal={props.onCloseFatherModal} />}
        </>
    );
});

export default Uninstall;