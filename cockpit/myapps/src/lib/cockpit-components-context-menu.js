import cockpit from "cockpit";
import PropTypes from "prop-types";
import React from "react";
import "../assets/scss/custom/terminal/context-menu.css";

const _ = cockpit.gettext;

export const ContextMenu = ({ parentId, getText, setText }) => {
    const [visible, setVisible] = React.useState(false);
    const [event, setEvent] = React.useState(null);
    const root = React.useRef(null);

    React.useEffect(() => {
        const _handleContextMenu = (event) => {
            event.preventDefault();

            setVisible(true);
            setEvent(event);
        };

        const _handleClick = (event) => {
            if (event && event.button === 0) {
                const wasOutside = !(event.target.contains === root.current);

                if (wasOutside)
                    setVisible(false);
            }
        };

        const parent = document.getElementById(parentId);
        parent.addEventListener('contextmenu', _handleContextMenu);
        document.addEventListener('click', _handleClick);

        return () => {
            parent.removeEventListener('contextmenu', _handleContextMenu);
            document.removeEventListener('click', _handleClick);
        };
    }, [parentId]);

    React.useEffect(() => {
        if (!event)
            return;

        const clickX = event.clientX;
        const clickY = event.clientY;
        const screenW = window.innerWidth;
        const screenH = window.innerHeight;
        const rootW = root.current.offsetWidth;
        const rootH = root.current.offsetHeight;

        const right = (screenW - clickX) > rootW;
        const left = !right;
        const top = (screenH - clickY) > rootH;
        const bottom = !top;

        if (right) {
            root.current.style.left = `${clickX + 5}px`;
        }

        if (left) {
            root.current.style.left = `${clickX - rootW - 5}px`;
        }

        if (top) {
            root.current.style.top = `${clickY + 5}px`;
        }

        if (bottom) {
            root.current.style.top = `${clickY - rootH - 5}px`;
        }
    }, [event]);

    return visible &&
        <div ref={root} className="contextMenu">
            <button className="contextMenuOption" onClick={getText}>
                <div className="contextMenuName"> {_("Copy")} </div>
                <div className="contextMenuShortcut">{_("Ctrl+Insert")}</div>
            </button>
            <button className="contextMenuOption" onClick={setText}>
                <div className="contextMenuName"> {_("Paste")} </div>
                <div className="contextMenuShortcut">{_("Shift+Insert")}</div>
            </button>
        </div>;
};

ContextMenu.propTypes = {
    getText: PropTypes.func.isRequired,
    setText: PropTypes.func.isRequired,
    parentId: PropTypes.string.isRequired
};