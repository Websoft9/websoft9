// @flow

/**
 * Changes the body attribute
 */
const changeBodyAttribute = (attribute: string, value: string): void => {
    if (document.body) document.body.setAttribute(attribute, value);
};

export { changeBodyAttribute };
