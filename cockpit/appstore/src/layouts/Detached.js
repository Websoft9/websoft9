// @flow
import React, { Suspense, useCallback, useEffect } from 'react';
import { Container } from 'react-bootstrap';
import { useDispatch, useSelector } from 'react-redux';
import { Outlet } from 'react-router-dom';

// actions
import { changeSidebarType } from '../redux/actions';

// constants
import * as layoutConstants from '../constants/layout';

// components

// utils
import { changeBodyAttribute } from '../utils/';

// code splitting and lazy loading
// https://blog.logrocket.com/lazy-loading-components-in-react-16-6-6cea535c0b52
const Topbar = React.lazy(() => import('./Topbar'));

const loading = () => <div className="text-center"></div>;


type VerticalLayoutProps = {
    children?: any,
};

type VerticalLayoutState = {
    isMenuOpened?: boolean,
};


const DetachedLayout = ({ children }: VerticalLayoutProps, state: VerticalLayoutState): React$Element<any> => {
    const dispatch = useDispatch();
    const { layoutColor, } = useSelector((state) => ({
        layoutColor: state.Layout.layoutColor,
        layoutWidth: state.Layout.layoutWidth,
    }));

    /*
     * layout defaults
     */
    useEffect(() => {
        changeBodyAttribute('data-layout', layoutConstants.LAYOUT_DETACHED);
        changeBodyAttribute('data-layout-mode', layoutConstants.LAYOUT_WIDTH_FLUID);
    }, []);

    useEffect(() => {
        changeBodyAttribute('data-layout-color', layoutColor);
    }, [layoutColor]);


    const updateDimensions = useCallback(() => {
        // activate the condensed sidebar if smaller devices like ipad or tablet
        if (window.innerWidth >= 768 && window.innerWidth <= 1028) {
            dispatch(changeSidebarType(layoutConstants.LEFT_SIDEBAR_TYPE_CONDENSED));
        } else if (window.innerWidth > 1028) {
            dispatch(changeSidebarType(layoutConstants.LEFT_SIDEBAR_TYPE_FIXED));
        }
    }, [dispatch]);

    useEffect(() => {
        window.addEventListener('resize', updateDimensions);

        return () => {
            window.removeEventListener('resize', updateDimensions);
        };
    }, [dispatch, updateDimensions]);

    return (
        <>
            <Suspense fallback={loading()}>
                <Topbar navCssClasses="topnav-navbar" topbarDark={true} />
            </Suspense>
            <Container fluid style={{ marginTop: "100px" }}>
                <div className="wrapper">
                    <div className="content-page">
                        <div className="content">
                            <Outlet />
                        </div>
                    </div>
                </div>
            </Container>
        </>
    );
};

export default DetachedLayout;
