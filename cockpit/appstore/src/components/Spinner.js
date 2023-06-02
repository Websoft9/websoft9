// @flow
import React from 'react';
import classNames from 'classnames';

type SpinnerProps = {
    tag?: string,
    className?: string,
    size?: 'lg' | 'md' | 'sm',
    type?: 'bordered' | 'grow',
    color?: string,
    children?: any,
};

/**
 * Spinner
 */
const Spinner = (props: SpinnerProps): React$Element<any> => {
    const children = props.children || null;
    const Tag = props.tag || 'div';
    const color = props.color || 'secondary';
    const size = props.size || '';

    return (
        <Tag
            role="status"
            className={classNames(
                {
                    'spinner-border': props.type === 'bordered',
                    'spinner-grow': props.type === 'grow',
                },
                [`text-${color}`],
                { [`avatar-${size}`]: size },
                props.className
            )}>
            {children}
        </Tag>
    );
};

Spinner.defaultProps = {
    tag: 'div',
    type: 'bordered',
};

export default Spinner;
