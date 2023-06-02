function debug() {
    if (window.debugging == "all" || window.debugging?.includes("style")) {
        console.debug([`cockpit-dark-theme: ${document.documentElement.id}:`, ...arguments].join(" "));
    }
}

function changeDarkThemeClass(documentElement, dark_mode) {
    debug(`Setting cockpit theme to ${dark_mode ? "dark" : "light"}`);

    if (dark_mode) {
        documentElement.classList.add('pf-theme-dark');
    } else {
        documentElement.classList.remove('pf-theme-dark');
    }
}

function _setDarkMode(_style) {
    const style = _style || localStorage.getItem('shell:style') || 'auto';
    let dark_mode;
    // If a user set's an explicit theme, ignore system changes.
    if ((window.matchMedia?.('(prefers-color-scheme: dark)').matches && style === "auto") || style === "dark") {
        dark_mode = true;
    } else {
        dark_mode = false;
    }
    changeDarkThemeClass(document.documentElement, dark_mode);
}

window.addEventListener("storage", event => {
    if (event.key === "shell:style") {
        debug(`Storage element 'shell:style' changed from  ${event.oldValue} to ${event.newValue}`);

        _setDarkMode();
    }
});

// When changing the theme from the shell switcher the localstorage change will not fire for the same page (aka shell)
// so we need to listen for the event on the window object.
window.addEventListener("cockpit-style", event => {
    const style = event.detail.style;
    debug(`Event received from shell with 'cockpit-style'  ${style}`);

    _setDarkMode(style);
});

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    debug(`Operating system theme preference changed to ${window.matchMedia?.('(prefers-color-scheme: dark)').matches ? "dark" : "light"}`);
    _setDarkMode();
});

_setDarkMode();