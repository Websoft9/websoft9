import { Button, Modal } from "@patternfly/react-core";
import cockpit from "cockpit";
import PropTypes from "prop-types";
import React from "react";
import { Terminal as Term } from "xterm";
import { CanvasAddon } from 'xterm-addon-canvas';
import "../assets/scss/custom/terminal/console.css";
import { ContextMenu } from "./cockpit-components-context-menu";

const _ = cockpit.gettext;

const theme_core = {
    yellow: "#b58900",
    brightRed: "#cb4b16",
    red: "#dc322f",
    magenta: "#d33682",
    brightMagenta: "#6c71c4",
    blue: "#268bd2",
    cyan: "#2aa198",
    green: "#859900"
};

const themes = {
    "black-theme": {
        background: "#000000",
        foreground: "#ffffff"
    },
    "dark-theme": Object.assign({}, theme_core, {
        background: "#002b36",
        foreground: "#fdf6e3",
        cursor: "#eee8d5",
        selection: "#ffffff77",
        brightBlack: "#002b36",
        black: "#073642",
        brightGreen: "#586e75",
        brightYellow: "#657b83",
        brightBlue: "#839496",
        brightCyan: "#93a1a1",
        white: "#eee8d5",
        brightWhite: "#fdf6e3"
    }),
    "light-theme": Object.assign({}, theme_core, {
        background: "#fdf6e3",
        foreground: "#002b36",
        cursor: "#073642",
        selection: "#00000044",
        brightWhite: "#002b36",
        white: "#073642",
        brightCyan: "#586e75",
        brightBlue: "#657b83",
        brightYellow: "#839496",
        brightGreen: "#93a1a1",
        black: "#eee8d5",
        brightBlack: "#fdf6e3"
    }),
    "white-theme": {
        background: "#ffffff",
        foreground: "#000000",
        selection: "#00000044",
        cursor: "#000000",
    },
};

export class Terminal extends React.Component {
    constructor(props) {
        super(props);
        this.onChannelMessage = this.onChannelMessage.bind(this);
        this.onChannelClose = this.onChannelClose.bind(this);
        this.connectChannel = this.connectChannel.bind(this);
        this.disconnectChannel = this.disconnectChannel.bind(this);
        this.reset = this.reset.bind(this);
        this.focus = this.focus.bind(this);
        this.onWindowResize = this.onWindowResize.bind(this);
        this.resizeTerminal = this.resizeTerminal.bind(this);
        this.onFocusIn = this.onFocusIn.bind(this);
        this.onFocusOut = this.onFocusOut.bind(this);
        this.setText = this.setText.bind(this);
        this.getText = this.getText.bind(this);
        this.setTerminalTheme = this.setTerminalTheme.bind(this);

        const term = new Term({
            cols: props.cols || 80,
            rows: props.rows || 25,
            screenKeys: true,
            cursorBlink: true,
            fontSize: props.fontSize || 16,
            fontFamily: 'Menlo, Monaco, Consolas, monospace',
            screenReaderMode: true,
            showPastingModal: false,
        });

        this.terminalRef = React.createRef();

        term.onData(function (data) {
            if (this.props.channel.valid) {
                this.props.channel.send(data);
            }
        }.bind(this));

        if (props.onTitleChanged)
            term.onTitleChange(props.onTitleChanged);

        this.terminal = term;
        this.state = {
            showPastingModal: false,
            cols: props.cols || 80,
            rows: props.rows || 25
        };
    }

    componentDidMount() {
        this.terminal.open(this.terminalRef.current);
        this.terminal.loadAddon(new CanvasAddon());

        this.connectChannel();

        if (!this.props.rows) {
            window.addEventListener('resize', this.onWindowResize);
            this.onWindowResize();
        }
        this.setTerminalTheme(this.props.theme || 'black-theme');
        this.terminal.focus();
    }

    resizeTerminal(cols, rows) {
        this.terminal.resize(cols, rows);
        this.props.channel.control({
            window: {
                rows,
                cols
            }
        });
    }

    componentDidUpdate(prevProps, prevState) {
        if (prevProps.fontSize !== this.props.fontSize) {
            this.terminal.options.fontSize = this.props.fontSize;

            // After font size is changed, resize needs to be triggered
            const dimensions = this.calculateDimensions();
            if (dimensions.cols !== this.state.cols || dimensions.rows !== this.state.rows) {
                this.onWindowResize();
            } else {
                // When font size changes but dimensions are the same, we need to force `resize`
                this.resizeTerminal(dimensions.cols - 1, dimensions.rows);
            }
        }

        if (prevState.cols !== this.state.cols || prevState.rows !== this.state.rows)
            this.resizeTerminal(this.state.cols, this.state.rows);

        if (prevProps.theme !== this.props.theme)
            this.setTerminalTheme(this.props.theme);

        if (prevProps.channel !== this.props.channel) {
            this.terminal.reset();
            this.disconnectChannel(prevProps.channel);
            this.connectChannel();
            this.props.channel.control({
                window: {
                    rows: this.state.rows,
                    cols: this.state.cols
                }
            });
        }
        this.terminal.focus();
    }

    render() {
        return (
            <>
                <Modal title={_("Paste error")}
                    position="top"
                    variant="small"
                    isOpen={this.state.showPastingModal}
                    onClose={() => this.setState({ showPastingModal: false })}
                    actions={[
                        <Button key="cancel" variant="secondary" onClick={() => this.setState({ showPastingModal: false })}>
                            {_("Close")}
                        </Button>
                    ]}>
                    {_("Your browser does not allow paste from the context menu. You can use Shift+Insert.")}
                </Modal>
                <div ref={this.terminalRef}
                    key={this.terminal}
                    className="console-ct"
                    onFocus={this.onFocusIn}
                    onContextMenu={this.contextMenu}
                    onBlur={this.onFocusOut} />
                <ContextMenu parentId={this.props.parentId} setText={this.setText} getText={this.getText} />
            </>
        );
    }

    componentWillUnmount() {
        this.disconnectChannel();
        this.terminal.dispose();
        window.removeEventListener('resize', this.onWindowResize);
        this.onFocusOut();
    }

    setText() {
        try {
            navigator.clipboard.readText()
                .then(text => this.props.channel.send(text))
                .catch(e => this.setState({ showPastingModal: true }))
                .finally(() => this.terminal.focus());
        } catch (error) {
            this.setState({ showPastingModal: true });
        }
    }

    getText() {
        try {
            navigator.clipboard.writeText(this.terminal.getSelection())
                .catch(e => console.error('Text could not be copied, use Ctrl+Insert ', e ? e.toString() : ""))
                .finally(() => this.terminal.focus());
        } catch (error) {
            console.error('Text could not be copied, use Ctrl+Insert:', error.toString());
        }
    }

    onChannelMessage(event, data) {
        this.terminal.write(data);
    }

    onChannelClose(event, options) {
        const term = this.terminal;
        term.write('\x1b[31m' + (options.problem || 'disconnected') + '\x1b[m\r\n');
        term.cursorHidden = true;
        term.refresh(term.rows, term.rows);
    }

    connectChannel() {
        const channel = this.props.channel;
        if (channel?.valid) {
            //channel.send("docker exec -it mysql55 bash||sh\n");

            channel.addEventListener('message', this.onChannelMessage.bind(this));
            channel.addEventListener('close', this.onChannelClose.bind(this));

            //用于打开终端时默认执行一条命令，进入容器内部
            channel.send(this.props.runCmd);
            this.reset();//调用一次重置
        }
    }

    disconnectChannel(channel) {
        if (channel === undefined)
            channel = this.props.channel;
        if (channel) {
            channel.removeEventListener('message', this.onChannelMessage);
            channel.removeEventListener('close', this.onChannelClose);
        }
        channel.close();
    }

    reset() {
        this.terminal.reset();
        this.props.channel.send(String.fromCharCode(12)); // Send SIGWINCH to show prompt on attaching
    }

    focus() {
        if (this.terminal)
            this.terminal.focus();
    }

    calculateDimensions() {
        const padding = 10; // Leave a bit of space around terminal
        const realHeight = this.terminal._core._renderService.dimensions.css.cell.height;
        const realWidth = this.terminal._core._renderService.dimensions.css.cell.width;
        if (realHeight && realWidth && realWidth !== 0 && realHeight !== 0)
            return {
                rows: Math.floor((this.terminalRef.current.parentElement.clientHeight - padding) / realHeight),
                cols: Math.floor((this.terminalRef.current.parentElement.clientWidth - padding - 12) / realWidth) // Remove 12px for scrollbar
            };

        return { rows: this.state.rows, cols: this.state.cols };
    }

    onWindowResize() {
        this.setState(this.calculateDimensions());
    }

    setTerminalTheme(theme) {
        this.terminal.options.theme = themes[theme];
    }

    onBeforeUnload(event) {
        // Firefox requires this when the page is in an iframe
        event.preventDefault();

        // see "an almost cross-browser solution" at
        // https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeunload_event
        event.returnValue = '';
        return '';
    }

    onFocusIn() {
        window.addEventListener('beforeunload', this.onBeforeUnload);
    }

    onFocusOut() {
        window.removeEventListener('beforeunload', this.onBeforeUnload);
    }
}

Terminal.propTypes = {
    cols: PropTypes.number,
    rows: PropTypes.number,
    channel: PropTypes.object.isRequired,
    onTitleChanged: PropTypes.func,
    theme: PropTypes.string,
    parentId: PropTypes.string.isRequired
};