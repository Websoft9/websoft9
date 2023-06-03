import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import MuiAlert from '@mui/material/Alert';
import Snackbar from '@mui/material/Snackbar';
import Typography from '@mui/material/Typography';
import classNames from 'classnames';
import cockpit from 'cockpit';
import { default as React, useEffect, useState } from 'react';
import { Alert, Badge, Button, Card, Col, Form, Modal, Row } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import FormInput from '../../components/FormInput';
import Spinner from '../../components/Spinner';
import { AppDomainAdd, AppDomainDelete, AppDomainList, AppDomainSet, AppDomainUpdate } from '../../helpers';

const _ = cockpit.gettext;

const MyMuiAlert = React.forwardRef(function Alert(props, ref) {
    return <MuiAlert elevation={6} ref={ref} variant="filled" {...props} />;
});

//删除绑定的域名
const RemoveDomain = (props): React$Element<React$FragmentType> => {
    const navigate = useNavigate(); //用于页面跳转
    const [disable, setDisable] = useState(false);//用于按钮禁用
    const [showAlert, setShowAlert] = useState(false); //用于是否显示错误提示
    const [alertMessage, setAlertMessage] = useState("");//用于显示错误提示消息

    function closeAllModals() {
        //关闭所有弹窗
        props.onClose();
        props.onDataChange();
    }

    return (
        <Modal show={props.showConform} onHide={props.onClose} size="lg"
            scrollable="true" backdrop="static" style={{ backgroundColor: "rgba(0,0,0,0.8)" }}>
            <Modal.Header onHide={props.onClose} className={classNames('modal-colored-header', 'bg-warning')}>
                <h4>{_("Delete domain binding")}</h4>
            </Modal.Header>
            <Modal.Body className="row" >
                <span style={{ margin: "10px 0px" }}>{_("Are you sure you want to delete the domain for:")} {props.deleteRowData.domainValue} ? </span>
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
                        const response = await AppDomainDelete({ app_id: props.deleteRowData.app_id, domain: props.deleteRowData.domainValue });
                        if (response.data.Error) {
                            setShowAlert(true);
                            setAlertMessage(response.data.Error.Message);
                        }
                        else { //删除成功
                            setDisable(false);
                            closeAllModals();
                        }
                    }
                    catch (error) {
                        navigate("/error-500");
                    }
                    finally {
                        setDisable(false);
                    }
                }}>
                    {disable && <Spinner className="spinner-border-sm me-1" tag="span" color="white" />} {_("Delete")}
                </Button>
            </Modal.Footer>
        </Modal >
    );
}

const AppAccess = (props): React$Element<React$FragmentType> => {
    const navigate = useNavigate(); //用于页面跳转
    const [domains, setDomains] = useState([]); // 定义域名数组
    const [loading, setLoading] = useState(false); // 定义执行操作时的加载转态

    const [showAlert, setShowAlert] = useState(false); //用于是否显示错误提示
    const [alertMessage, setAlertMessage] = useState("");  //用于显示错误提示消息
    const [alertType, setAlertType] = useState("");  //用于确定弹窗的类型：error\success
    const [showRemoveDomain, setShowRemoveDomain] = useState(false); //用于显示状态为failed时显示确定删除的弹窗
    const [deleteRowData, setDeleteRowData] = useState(null); //用于保存将要删除的行数据
    const [inputDomainValue, setInputDomainValue] = useState("");//用户保存用户输入的域名

    const [isExpandedForDomain, setIsExpandedForDomain] = React.useState(true); //用于保存“域名绑定”的折叠状态
    const [isExpandedForNoDomain, setIsExpandedForNoDomain] = React.useState(true);//用于保存“无域名访问”的折叠状态
    const [isExpandedForAccount, setIsExpandedForAccount] = React.useState(false);//用于保存“无域名访问”的折叠状态

    const getDomains = async () => {
        try {
            const response = await AppDomainList({ app_id: props.data.app_id });
            if (response.data.Error) {
                setShowAlert(true);
                setAlertType("error")
                setAlertMessage(response.data.Error.Message);
            }
            else {
                let responseData = response.data.ResponseData.Domain_set;
                let defaultdomain = responseData.default_domain; //获取返回的默认域名数据

                let resturnDomains = responseData.domains.map(domain => {
                    return {
                        app_id: props.data.app_id,
                        domainValue: domain,
                        newDomainValue: domain,
                        isEditable: false,
                        isFromAPI: true,
                        isDefaultDomain: domain === defaultdomain ? true : false
                    };
                });
                //排序：将默认域名放前面
                resturnDomains.sort((a, b) => {
                    return b.isDefaultDomain - a.isDefaultDomain;
                });
                setDomains(resturnDomains);
            }
        }
        catch (error) {
            navigate("/error-500");
        }
    }

    useEffect(() => {
        getDomains();
    }, []);

    //添加域名
    const addRow = () => {
        if (domains.length < 10) {
            // 限制最多只能有10个domain
            setDomains([
                ...domains,
                {
                    app_id: props.data.app_id,
                    domainValue: "",
                    newDomainValue: "",
                    isEditable: true,
                    isFromAPI: false,
                    isDefaultDomain: false
                },
            ]);
        }
    }

    //删除域名
    const deleteRow = async (row, index) => {
        if (!row.isFromAPI) { //如果是点“添加”产生的记录行，则直接删除，不需要调用接口
            const newRows = [...domains]; // 复制状态数组
            newRows.splice(index, 1); // 删除指定索引的对象
            setDomains(newRows); // 更新状态数组
        }
        else { //表示记录是从接口获取的，删除时需要调用接口删除
            setShowRemoveDomain(true);
            setDeleteRowData(row);
        }
    }

    //编辑
    const editRow = (index) => {
        const newRows = [...domains]; // 复制状态数组
        newRows[index].isEditable = !newRows[index].isEditable; // 切换isEditable属性
        setDomains(newRows); // 更新状态数组
    }

    //取消编辑
    const cancelEditRow = (index) => {
        const newRows = [...domains]; // 复制状态数组
        newRows[index].newDomainValue = newRows[index].domainValue; // 用户有修改但是取消编辑，需要将数据还原
        newRows[index].isEditable = !newRows[index].isEditable; // 切换isEditable属性
        setDomains(newRows); // 更新状态数组
    }

    //设为默认域名
    const setDefaultDomain = async (index) => {
        const defaultDomain = domains[index].newDomainValue; //获取域名
        setLoading(true);
        try {  //调用设定默认域名接口
            const response = await AppDomainSet({ app_id: props.data.app_id, domain: defaultDomain });
            if (response.data.Error) {
                setShowAlert(true);
                setAlertType("error")
                setAlertMessage(response.data.Error.Message);
            }
            else {
                setShowAlert(true);
                setAlertType("success")
                setAlertMessage("设置成功!");
                getDomains();
            }
        }
        catch (error) {
            navigate("/error-500");
        }
        finally {
            setLoading(false);
        }
    }

    //保存
    const saveRow = async (row, index) => {
        const input = document.getElementsByName(`domain-${index}`)[0]; // 获取搜索框元素
        const value = input.value; // 获取搜索框的值
        const regex = /^(?!https?:\/\/)([\da-z\.-]+\.)*([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/; // 定义一个正则表达式，用来验证域名的格式
        if (value) {
            if (regex.test(value)) {
                if (row.isFromAPI) { //如果取到isFromAPI为true,表示要修改数据
                    if (row.domainValue != row.newDomainValue) { //如果修改前的数据不等于修改后的数据，则调用修改接口
                        setLoading(true);
                        try {
                            const response = await AppDomainUpdate({ app_id: props.data.app_id, domain_old: row.domainValue, domain_new: value });
                            if (response.data.Error) {
                                setShowAlert(true);
                                setAlertType("error")
                                setAlertMessage(response.data.Error.Message);
                            }
                            else {
                                setShowAlert(true);
                                setAlertType("success")
                                setAlertMessage("Success");
                                getDomains();
                            }
                        }
                        catch (error) {
                            navigate("/error-500");
                        }
                        finally {
                            setLoading(false);
                        }
                    }
                    else {
                        const newRows = [...domains]; // 复制状态数组
                        newRows[index].isEditable = !newRows[index].isEditable; // 切换isEditable属性
                        setDomains(newRows); // 更新状态数组
                    }
                }
                else { //如果取到isFromAPI为false,表示是绑定数据 
                    try {
                        setLoading(true);
                        const response = await AppDomainAdd({ app_id: props.data.app_id, domains: value });
                        if (response.data.Error) {
                            setShowAlert(true);
                            setAlertType("error")
                            setAlertMessage(response.data.Error.Message);
                        }
                        else {
                            setShowAlert(true);
                            setAlertType("success")
                            setAlertMessage("Success");
                            getDomains();
                        }
                    }
                    catch (error) {
                        navigate("/error-500");
                    }
                    finally {
                        setLoading(false);
                    }
                }
            } else {
                setShowAlert(true);
                setAlertType("error")
                setAlertMessage(_("Please enter the correct domain name and cannot start with http or https!"));
            }
        }
        else {
            // 如果搜索框的值为空
            setShowAlert(true);
            setAlertType("error")
            setAlertMessage(_("Domain name cannot be empty"));
        }
    }

    //处理输入
    function handleChange(index, e) {
        const newRows = [...domains]; // 复制状态数组
        newRows[index].newDomainValue = e.target.value; // 修改inputValue属性
        setDomains(newRows); // 更新状态数组
    }

    const handleAlertClose = (event, reason) => {
        if (reason === 'clickaway') {
            return;
        }
        setShowAlert(false);
        setAlertMessage("");
    };

    //用于取消删除域名弹窗
    const cancelRemoveDomain = () => {
        setShowRemoveDomain(false);
    };

    const [isOpen, setIsOpen] = useState(false);
    const toggle = () => setIsOpen(!isOpen);

    const handleChangefordomin = (event, newExpanded) => {
        setIsExpandedForDomain(newExpanded);
    };

    const handleChangefornodomin = (event, newExpanded) => {
        setIsExpandedForNoDomain(newExpanded);
    };

    const handleChangeforaccount = (event, newExpanded) => {
        setIsExpandedForAccount(newExpanded);
    };

    return (
        <>
            <Card>
                {loading && (
                    <div className="card-disabled" style={{ zIndex: 999 }}>
                        <div className="card-portlets-loader"></div>
                    </div>
                )}
                <Card.Body>
                    <Accordion defaultExpanded={true} onChange={handleChangefordomin} className='mb-2'>
                        <AccordionSummary
                            expandIcon={<ExpandMoreIcon />}
                            aria-controls="panel1a-content"
                            id="panel1a-header"
                        >
                            <Typography>
                                <label className="me-2 fs-5 d-block">{_("Domain Access")}</label>
                                <span className="me-2 fs-6" style={{ display: isExpandedForDomain ? 'inline' : 'none' }}>
                                    {_("Domain access for better application performance. HTTPS and custom configurations available")}
                                    <a href="/nginx" target="_parent">
                                        {_("More")}
                                    </a>
                                </span>
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            <Typography>
                                <Card>
                                    <Card.Header>
                                        <Row className="mb-2 align-items-center">
                                            <Col xs={12} md={12} className="d-flex justify-content-end">
                                                <Button variant="primary" size="sm" className="me-2" onClick={() => addRow()}>{_("Add Domain")}</Button>
                                                {
                                                    props.data?.config?.admin_domain_url && (
                                                        <a href={props.data?.config?.admin_domain_url} target="_blank" className="me-2">
                                                            <Button variant="primary" size="sm">访问后台</Button>
                                                        </a>
                                                    )
                                                }
                                                <Button size="sm" className="me-2" variant="primary"
                                                    onClick={async () => {
                                                        setLoading(true);
                                                        await getDomains();
                                                        setLoading(false);
                                                    }} > {_("Refresh")}
                                                </Button>
                                            </Col>
                                        </Row>
                                    </Card.Header>
                                    <Card.Body>
                                        {domains.map((row, index) => (
                                            <Row className="mb-2" key={index}>
                                                <Col xs={12} className="d-flex justify-content-between">
                                                    <Col>
                                                        <FormInput className="mb-2 mb-md-0" type="text"
                                                            name={`domain-${index}`}
                                                            value={row.newDomainValue}
                                                            disabled={!row.isEditable}
                                                            onChange={(e) => handleChange(index, e)} />
                                                    </Col>
                                                    <Col className='col-auto ms-auto'>
                                                        <Button variant="link text-danger" style={{ padding: "5px" }} onClick={() => deleteRow(row, index)}>
                                                            {_("delete")}
                                                        </Button>
                                                        {row.isEditable && row.isFromAPI && (
                                                            <>
                                                                <Button variant="link text-success" style={{ padding: "5px" }} onClick={() => saveRow(row, index)}>
                                                                    {_("save")}
                                                                </Button>
                                                                <Button variant="link text-success" style={{ padding: "5px" }} onClick={() => cancelEditRow(index)}>
                                                                    {_("cancel")}
                                                                </Button>
                                                            </>
                                                        )}
                                                        {row.isEditable && !row.isFromAPI && (

                                                            <Button variant="link text-success" style={{ padding: "5px" }} onClick={() => saveRow(row, index)}>
                                                                {_("save")}
                                                            </Button>
                                                        )}
                                                        {!row.isEditable && (
                                                            <>
                                                                <Button variant="link text-primary" style={{ padding: "5px" }} onClick={() => editRow(index)}>
                                                                    {_("edit")}
                                                                </Button>
                                                                <a href={'http://' + row.domainValue} target="_blank">
                                                                    <Button variant="link text-primary" style={{ padding: "5px" }}>{_("access")}</Button>
                                                                </a>
                                                                {
                                                                    row.isDefaultDomain ? (
                                                                        <Badge className="ms-2 bg-success"> {_("default")} </Badge>
                                                                    ) : (
                                                                        <Button variant="link text-primary" onClick={() => setDefaultDomain(index)}>
                                                                            {_("set as default")}
                                                                        </Button>
                                                                    )
                                                                }
                                                            </>
                                                        )}
                                                    </Col>
                                                </Col>
                                            </Row>
                                        ))}
                                    </Card.Body>
                                    {/* <Card.Footer>
                                        <Row className="mb-2 mt-2">
                                            <Col sm={12}>
                                                <span>
                                                    如要需要进行Https设置,或者更多自定义配置，请点击更多
                                                </span>
                                                <a href="/nginx" target="_parent" className="me-2 float-end">
                                                    <Button variant="primary" size="sm">{_("More")}</Button>
                                                </a>
                                            </Col>
                                        </Row>
                                    </Card.Footer> */}
                                </Card >
                            </Typography>
                        </AccordionDetails>
                    </Accordion>
                    {
                        (props.data?.config?.url && ((props.data?.config?.default_domain && !props.data?.app_replace_url) || (!props.data?.config?.default_domain))) &&
                        <Accordion defaultExpanded={true} onChange={handleChangefornodomin} className='mb-2'>
                            <AccordionSummary
                                expandIcon={<ExpandMoreIcon />}
                                aria-controls="panel2a-content"
                                id="panel2a-header"
                            >
                                <Typography>
                                    <label className="me-2 fs-5 d-block">无域名访问</label>
                                    <span className="me-2 fs-6" style={{ display: isExpandedForNoDomain ? 'inline' : 'none' }}>没有域名可以通过IP+端口的方式临时访问应用</span>
                                </Typography>
                            </AccordionSummary>
                            <AccordionDetails>
                                <Typography>
                                    <Card>
                                        <Card.Body>
                                            {
                                                props.data?.config?.url &&
                                                (
                                                    <div>
                                                        <label className="me-2 fs-5">前台:</label>
                                                        <a href={props.data?.config?.url} target="_blank" className="me-2">
                                                            {props.data?.config?.url}
                                                        </a>
                                                    </div>
                                                )
                                            }
                                            {
                                                props.data?.config?.admin_url &&
                                                (
                                                    <div>
                                                        <label className="me-2 fs-5">后台:</label>
                                                        <a href={props.data?.config?.admin_url} target="_blank" className="me-2">
                                                            {props.data?.config?.admin_url}
                                                        </a>
                                                    </div>
                                                )
                                            }
                                        </Card.Body>
                                    </Card>
                                </Typography>
                            </AccordionDetails>
                        </Accordion>
                    }
                    {
                        props.data?.config?.admin_username &&
                        <Accordion className='mb-2' onChange={handleChangeforaccount}>
                            <AccordionSummary
                                expandIcon={<ExpandMoreIcon />}
                                aria-controls="panel3a-content"
                                id="panel3a-header"
                            >
                                <Typography>
                                    <label className="me-2 fs-5 d-block">初始账号</label>
                                    <span className="me-2 fs-6" style={{ display: isExpandedForAccount ? 'inline' : 'none' }}>
                                        此应用程序是使用管理员帐户预先设置的，请立即更改管理员密码。初始凭据为：
                                    </span>
                                </Typography>
                            </AccordionSummary>
                            <AccordionDetails>
                                <Typography>
                                    <Card>
                                        <Card.Body>
                                            {/* <p>
                                                This app is pre-setup with an admin account,Please change the admin password immediately. The initial credentials are:
                                            </p> */}
                                            <Form.Group as={Row} className="mb-3">
                                                <Form.Label htmlFor="username" column md={2} className='fs-5'>
                                                    UserName
                                                </Form.Label>
                                                <Col md={4}>
                                                    <Form.Control
                                                        type="text"
                                                        name="username"
                                                        id="username"
                                                        defaultValue={props.data?.config?.admin_username}
                                                        readOnly
                                                    />
                                                </Col>
                                            </Form.Group>

                                            <Form.Group as={Row} className="mb-3">
                                                <Form.Label htmlFor="password" column md={2} className='fs-5'>
                                                    Password
                                                </Form.Label>
                                                <Col md={4}>
                                                    <FormInput
                                                        type="password"
                                                        name="password"
                                                        containerClass={'mb-3'}
                                                        value={props.data?.config?.admin_password}
                                                        readOnly
                                                    />
                                                </Col>
                                            </Form.Group>
                                        </Card.Body>
                                    </Card>
                                </Typography>
                            </AccordionDetails>
                        </Accordion>
                    }
                </Card.Body>
            </Card >
            {
                showRemoveDomain &&
                <RemoveDomain showConform={showRemoveDomain} onClose={cancelRemoveDomain} deleteRowData={deleteRowData} onDataChange={getDomains} />
            }
            {
                showAlert &&
                <Snackbar open={showAlert} autoHideDuration={5000} onClose={handleAlertClose} anchorOrigin={{ vertical: 'top', horizontal: 'center' }}>
                    <MyMuiAlert onClose={handleAlertClose} severity={alertType} sx={{ width: '100%' }}>
                        {alertMessage}
                    </MyMuiAlert>
                </Snackbar>
            }
        </>
    );
}

export default AppAccess;