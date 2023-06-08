import React, { useCallback, useEffect, useRef, useState } from "react";
import Spinner from 'react-bootstrap/Spinner';

// 把handleIframe函数提取成一个自定义hook，并使用useCallback来缓存它
const useHandleIframe = () => {
    return useCallback((iframe) => {
        var iframeWindow = iframe.contentWindow;

        var pageWrapper = iframeWindow.document.getElementById("page-wrapper");
        if (pageWrapper) {
            var sideview = pageWrapper.querySelector("#sideview");
            if (sideview) {
                pageWrapper.removeChild(sideview);
            }

            var pageHeaders = pageWrapper.querySelectorAll("page-header");
            for (var i = 0; i < pageHeaders.length; i++) {
                var pageHeader = pageHeaders[i];
                var parent = pageHeader.parentNode;
                parent.removeChild(pageHeader);
            }

            var rdWidgetHeaders = pageWrapper.querySelectorAll("rd-widget-header");
            for (var i = 0; i < rdWidgetHeaders.length; i++) {
                var rdWidgetHeade = rdWidgetHeaders[i];
                var parent = rdWidgetHeade.parentNode;
                parent.removeChild(rdWidgetHeade);
            }

            pageWrapper.style.setProperty("padding-left", "0px");
            pageWrapper.removeAttribute("ng-class");
            pageWrapper.className = "";

            iframe.style.display = "block";
        }
    }, []);
};

const AppTerminal = (props): React$Element<React$FragmentType> => {
    const iframeRef = useRef(null);
    const [loading, setLoading] = useState(true);
    const endpointsId = props.endpointsId;
    const containerId = props.containerId;

    // 使用自定义hook来获取handleIframe函数
    const handleIframe = useHandleIframe();

    useEffect(() => {
        if (iframeRef.current) {
            // 创建一个MutationObserver来监听iframe中的内容的变化
            const observer = new MutationObserver(() => {
                // 当变化发生时，执行handleIframe函数
                handleIframe(iframeRef.current);
                setLoading(false);
            });
            // 设置观察选项，观察子节点和属性的变化
            const config = { childList: true, attributes: true };
            // 判断iframe的contentDocument是否不为null
            if (iframeRef.current.contentDocument) {
                // 开始观察iframe中的文档根节点
                observer.observe(iframeRef.current.contentDocument.documentElement, config);
            }
            return () => {
                // 停止观察
                observer.disconnect();
            };
        }
    }, [iframeRef.current, handleIframe]);

    return (
        <>
            {
                loading && (
                    <div className="d-flex align-items-center justify-content-center m-5">
                        <Spinner animation="border" variant="secondary" />
                    </div>
                )
            }
            <div class="myProtainerTerminal" key="myProtainerTerminal" >
                <iframe
                    id="myIframe"
                    title="myProtainerTerminal"
                    src={`/portainer/#!/${endpointsId}/docker/containers/${containerId}/exec`}
                    style={{ display: "none" }}
                    ref={iframeRef}
                    sandbox='allow-scripts allow-modal allow-same-origin'
                    loading='eager'
                />
            </div >
        </>
    );
};

export default AppTerminal;
