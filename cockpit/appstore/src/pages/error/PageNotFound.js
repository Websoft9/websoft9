// @flow
import cockpit from "cockpit";
import React from 'react';
import { Card, Col, Row } from 'react-bootstrap';
import { Link } from 'react-router-dom';

// images
import Logo from '../../assets/images/logo.svg';
import logoEn from '../../assets/images/websoft9.svg';

const language = cockpit.language;//获取cockpit的当前语言环境

const ErrorPageNotFound = (): React$Element<React$FragmentType> => {
    return (
        <>
            <div className="account-pages pt-2 pt-sm-5 pb-4 pb-sm-5">
                <div className="container">
                    <Row className="justify-content-center">
                        <Col md={8} lg={6} xl={5} xxl={4}>
                            <Card>
                                {/* logo */}
                                <Card.Header className="pt-4 pb-4 text-center bg-primary">
                                    <Link to="/">
                                        <span>
                                            {
                                                language === "zh_CN" ? <img src={Logo} alt="" height="18" /> : <img src={logoEn} alt="" height="18" />
                                            }
                                        </span>
                                    </Link>
                                </Card.Header>

                                <Card.Body className="p-4">
                                    <div className="text-center">
                                        <h1 className="text-error">
                                            4<i className="mdi mdi-emoticon-sad"></i>4
                                        </h1>
                                        <h4 className="text-uppercase text-danger mt-3">Page Not Found</h4>
                                        <p className="text-muted mt-3">
                                            It's looking like you may have taken a wrong turn. Don't worry... it happens
                                            to the best of us. Here's a little tip that might help you get back on
                                            track.
                                        </p>

                                        <Link className="btn btn-info mt-3" to="/">
                                            <i className="mdi mdi-reply"></i> Return Home
                                        </Link>
                                    </div>
                                </Card.Body>
                            </Card>
                        </Col>
                    </Row>
                </div>
            </div>
        </>
    );
};

export default ErrorPageNotFound;
