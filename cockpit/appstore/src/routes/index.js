import React, { Suspense } from 'react';
import { Navigate, useRoutes } from 'react-router-dom';
import Root from './Root';

// All layouts/containers
import DefaultLayout from '../layouts/Default';
import DetachedLayout from '../layouts/Detached';

// pages
const AppStore = React.lazy(() => import('../pages/appstore'));
const ErrorPageNotFound = React.lazy(() => import('../pages/error/PageNotFound'));
const ServerError = React.lazy(() => import('../pages/error/ServerError'));
const CustomError = React.lazy(() => import('../pages/error/CustomError'));

const loading = () => <div className=""></div>;

type LoadComponentProps = {
    component: React.LazyExoticComponent<() => JSX.Element>,
};

const LoadComponent = ({ component: Component }: LoadComponentProps) => (
    <Suspense fallback={loading()}>
        <Component />
    </Suspense>
);

const AllRoutes = () => {
    return useRoutes([
        { path: '/', element: <Root /> },
        {
            path: '/',
            element: <DefaultLayout />,
            children: [
                {
                    path: 'error-404',
                    element: <LoadComponent component={ErrorPageNotFound} />,
                },
                {
                    path: 'error-500',
                    element: <LoadComponent component={ServerError} />,
                },
                {
                    path: "error",
                    element: <LoadComponent component={CustomError} />,
                }
            ],
        },
        {
            path: '/',
            element: <DetachedLayout />,
            children: [
                {
                    path: 'appstore',
                    element: <LoadComponent component={AppStore} />,
                },
            ],
        },
        {
            path: "*", // 通配符路径，匹配任何没有匹配到的路径
            element: <Navigate to="/error-404" />, // 使用Redirect组件，重定向到error-404页面
        }
    ]);
};

export { AllRoutes };
