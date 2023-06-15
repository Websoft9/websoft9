// @flow
import classNames from 'classnames';
import cockpit from 'cockpit';
import React from 'react';
import { Link } from 'react-router-dom';
// images
import logoSM from '../assets/images/logo-sm.svg';
import logo from '../assets/images/logo.svg';
import logoEn from '../assets/images/websoft9.svg';

const _ = cockpit.gettext;
const language = cockpit.language;//获取cockpit的当前语言环境

type TopbarProps = {
    hideLogo?: boolean,
    navCssClasses?: string,
    openLeftMenuCallBack?: () => void,
    topbarDark?: boolean,
};

const Topbar = ({ hideLogo, navCssClasses, openLeftMenuCallBack, topbarDark }: TopbarProps): React$Element<any> => {
    const navbarCssClasses = navCssClasses || '';
    const containerCssClasses = !hideLogo ? 'container-fluid' : '';

    return (
        <>
            <div className={classNames('navbar-custom', navbarCssClasses)}>
                <div className={containerCssClasses}>
                    {!hideLogo && (
                        <Link to="/" className="topnav-logo">
                            <span className="topnav-logo-lg">
                                {
                                    language === "zh_CN" ? <img src={logo} alt="logo" width="99" /> : <img src={logoEn} alt="logo" width="99" />
                                }
                            </span>
                            <span className="topnav-logo-sm">
                                <img src={logoSM} alt="logo" width="24px" height="24" />
                            </span>
                        </Link>
                    )}
                    <ul style={{
                        display: "flex", justifyContent: "flex-end", flexDirection: "row",
                        alignItems: "center", minHeight: "70px", fontSize: "16px", listStyle: "none",
                        marginBottom: "0px"
                    }}>
                        {/* <li style={{ margin: "0 10px" }}>
                            <a href='/myapps' style={{ color: "#428bca" }} target="_parent" >
                                <i className="dripicons-view-apps"></i>{' '}{_("My Apps")}
                            </a>
                        </li>
                        <li style={{ margin: "0 10px" }}>
                            <a href='/appstore' style={{ color: "#428bca" }} target="_parent">
                                <i className="dripicons-cloud-download"></i>{' '}{_("App Store")}
                            </a>
                        </li> */}
                        <li>
                            <button onClick={() => {

                            }}
                                className="nav-link dropdown-toggle end-bar-toggle arrow-none btn btn-link shadow-none" style={{ color: "#428bca", fontSize: "16px" }}>
                                更新应用列表
                            </button>
                        </li>
                    </ul>
                </div>
            </div>
        </>
    );
};

export default Topbar;
