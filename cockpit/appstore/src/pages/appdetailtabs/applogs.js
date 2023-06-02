import cockpit from "cockpit";
import { default as React, useEffect, useRef, useState } from 'react';
import ScrollToBottom from 'react-scroll-to-bottom';

const AppLogs = (props): React$Element<React$FragmentType> => {
    const [appLogs, setAppLog] = useState("");

    const messagesEndRef = useRef(null);

    useEffect(() => {
        messagesEndRef.current.scrollIntoView({ behavior: "auto" });
    }, []);

    const getAppLog = () => {
        cockpit.spawn(["docker", "compose", "--project-name", props.projectName.customer_name, "logs", "--tail", "200"]).then(content => {
            setAppLog(content);
        }).catch(exception => {

        });
    };

    useEffect(() => {
        const timer = setInterval(getAppLog, 1000);
        return () => clearInterval(timer);
    }, [getAppLog]);


    return (
        <ScrollToBottom>
            <div style={{ "height": "600px", "width": "100%" }}>
                <pre style={{ "white-space": "pre-wrap", "word-wrap": "break-word" }}>
                    {appLogs}
                </pre>
                <div ref={messagesEndRef} />
            </div>
        </ScrollToBottom>
    );
}

export default AppLogs;