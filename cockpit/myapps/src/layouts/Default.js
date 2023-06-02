// @flow
import React, { useEffect, Suspense } from 'react';
import { useSelector } from 'react-redux';
import { Outlet } from 'react-router-dom';

// utils
import { changeBodyAttribute } from '../utils';

const loading = () => <div className=""></div>;

type DefaultLayoutProps = {};

const DefaultLayout = (props: DefaultLayoutProps): React$Element<any> => {
    const { layoutColor } = useSelector((state) => ({
        layoutColor: state.Layout.layoutColor,
    }));

    useEffect(() => {
        changeBodyAttribute('data-layout-color', layoutColor);
    }, [layoutColor]);

    useEffect(() => {
        if (document.body) document.body.classList.add('authentication-bg');

        return () => {
            if (document.body) document.body.classList.remove('authentication-bg');
        };
    }, []);

    return (
        <Suspense fallback={loading()}>
            <Outlet />
        </Suspense>
    );
};
export default DefaultLayout;
