import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import MuiAlert from '@mui/material/Alert';
import Snackbar from '@mui/material/Snackbar';
import Typography from '@mui/material/Typography';
import axios from 'axios';
import 'bootstrap/dist/css/bootstrap.min.css';
import classNames from 'classnames';
import cockpit from 'cockpit';
import React, { useEffect, useState } from 'react';
import { Button, Card, Col, Form, Modal, Row } from 'react-bootstrap';
import "./App.css";
import Spinner from './Spinner';

const _ = cockpit.gettext;

const Alert = React.forwardRef(function Alert(props, ref) {
  return <MuiAlert elevation={6} ref={ref} variant="filled" {...props} />;
});


function App() {
  const [showUpdateLog, setShowUpdateLog] = useState(false); //用于更新弹窗
  const [currentVersion, setCurrentVersion] = useState(""); //用于存储当前版本
  const [updateContent, setUpdateContent] = useState(null); //用于存储更新数据
  const [showAlert, setShowAlert] = useState(false); //用于是否显示错误提示
  const [alertMessage, setAlertMessage] = useState("");//用于显示错误提示消息
  const [disable, setDisable] = useState(false);//用于更新按钮禁用
  const [showMask, setShowMask] = useState(false); //用于设置遮罩层
  const [alertType, setAlertType] = useState("");  //用于确定弹窗的类型：error\success

  let credentials;

  //获取接口调用的credentials
  async function getCredentials() {
    if (!credentials) {
      const response = await fetch('../myapps/config.json');
      const data = await response.json();
      if (data) {
        const userName = data.APPMANAGE.APPMANAGE_USERNAME;
        const uerPassword = data.APPMANAGE.APPMANAGE_PASSWORD;
        credentials = btoa(userName + ":" + uerPassword);
      }
    }
    return credentials;
  }

  const checkeUpdate = async (init) => {
    try {
      axios.defaults.headers.common['Authorization'] = 'Basic ' + await getCredentials();
      const response = await axios.get("/AppManage/AppUpdateList"); //调用获取更新内容接口
      if (response.data.Error) {
        setShowAlert(true);
        setAlertType("error")
        setAlertMessage(response.data.Error.Message);
      }
      else {
        const data = response.data.ResponseData.Compare_content;
        setCurrentVersion(data.current_version);
        setUpdateContent(data.Update_content);
        if (!init) {
          setShowUpdateLog(true);
          setDisable(false);
        }
      }
    }
    catch (error) {
      setShowAlert(true);
      setAlertType("error")
      setAlertMessage(error);
    }
  };

  const systemUpdate = async () => {
    setShowMask(true);
    setShowUpdateLog(false);
    //调用更新脚本
    var script = "curl https://websoft9.github.io/StackHub/install/update.sh | bash";
    cockpit.script(script).then(() => {
      setShowMask(false);
      setShowAlert(true);
      setAlertType("success")
      setAlertMessage("更新成功");

    }).catch(exception => {
      setShowAlert(true);
      setAlertType("error")
      setAlertMessage(exception.toString());
      setShowMask(false);
    });
  }

  const updateLogClose = () => {
    setShowUpdateLog(!showUpdateLog);
  };

  const handleClose = (event, reason) => {
    if (reason === 'clickaway') {
      return;
    }
    setShowAlert(false);
    setAlertMessage("");
  };

  useEffect(() => {
    checkeUpdate(true);
  }, []);

  return (
    <>
      {
        showMask && (
          <div className="card-disabled" style={{ zIndex: 999 }}>
            <Spinner className='dis_mid' />
          </div>
        )
      }
      <Row style={{ padding: "30px" }}>
        <Col xs={12}>
          <Card>
            <Card.Header>
              <label className="me-2 fs-5 d-block">{_("System Setting")}</label>
            </Card.Header>
            <Card.Body>
              <Accordion expanded={true} className='mb-2'>
                <AccordionSummary
                  aria-controls="panel1a-content"
                  id="panel1a-header"
                >
                  <Typography>
                    <label className="me-2 fs-5 d-block">{_("App Store Updates")}</label>
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography>
                    <Form>
                      <Form.Check
                        checked
                        type="switch"
                        id="store-switch"
                        label={_("Enable automatic updates")}
                      />
                    </Form>
                  </Typography>
                </AccordionDetails>
              </Accordion>
              <Accordion expanded={true} className='mb-2'>
                <AccordionSummary
                  aria-controls="panel1a-content"
                  id="panel1a-header"
                >
                  <Typography>
                    <label className="me-2 fs-5 d-block">{_("System Updates")}</label>
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography>
                    <Row className="mb-2 align-items-center">
                      <Col xs={12} md={12} className="d-flex">
                        <Form>
                          <Form.Check
                            checked
                            type="switch"
                            id="system-switch"
                            label={_("Enable automatic updates")}
                          />
                        </Form>
                      </Col>
                    </Row>

                    <Row className="mb-2 align-items-center">
                      <Col xs={6} md={6} className="d-flex">
                        {_("Current Version")}{" : "}<span style={{ color: "#0b5ed7" }}>{currentVersion}</span>
                      </Col>
                      <Col xs={6} md={6} className="d-flex">
                        <Button variant="primary" size="sm" className="me-2" disabled={disable}
                          onClick={() => { setDisable(true); checkeUpdate(false); }} >
                          {disable && <Spinner className="spinner-border-sm me-1" tag="span" color="white" />}  {_("Check for updates")}
                        </Button>
                      </Col>
                    </Row>
                  </Typography>
                </AccordionDetails>
              </Accordion>
            </Card.Body>
          </Card>
        </Col>
      </Row >
      {
        showUpdateLog && <Modal show={showUpdateLog} onHide={updateLogClose} size="lg"
          scrollable="true" backdrop="static" >
          <Modal.Header onHide={updateLogClose} closeButton className={classNames('modal-colored-header', 'bg-primary')} style={{ color: "#fff" }}>
            <h4>{_("Update Log")}</h4>
          </Modal.Header>
          <Modal.Body className="row" >
            <p>{_("Latest Version")}{" : "}{updateContent.latest_version}</p>
            <p>{_("Update Time")}{" : "}{updateContent.date}</p>
            <p>{_("Update Content")}{" : "}</p>
            {updateContent.content.map((item, index) => (
              <p key={index}>{index + 1}{" : "}{item}</p>
            ))}
          </Modal.Body>
          <Modal.Footer>
            <Button variant="light" onClick={updateLogClose}>
              {_("Close")}
            </Button>
            <Button variant='primary' className='bg-primary' onClick={systemUpdate}>
              {_("Update")}
            </Button>
          </Modal.Footer>
        </Modal >
      }
      {
        showAlert &&
        <Snackbar open={showAlert} autoHideDuration={5000} onClose={handleClose} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
          <Alert onClose={handleClose} severity={alertType} sx={{ width: '100%' }}>
            {alertMessage}
          </Alert>
        </Snackbar>
      }
    </>
  );
}

export default App;
