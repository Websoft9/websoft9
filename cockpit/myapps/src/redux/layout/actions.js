// @flow
import { LayoutActionTypes } from './constants';

type LayoutAction = { type: string, payload?: string | null };

export const changeLayout = (layout: string): LayoutAction => ({
    type: LayoutActionTypes.CHANGE_LAYOUT,
    payload: layout,
});

export const changeLayoutColor = (color: string): LayoutAction => ({
    type: LayoutActionTypes.CHANGE_LAYOUT_COLOR,
    payload: color,
});

export const changeLayoutWidth = (width: string): LayoutAction => ({
    type: LayoutActionTypes.CHANGE_LAYOUT_WIDTH,
    payload: width,
});

export const changeSidebarTheme = (theme: string): LayoutAction => ({
    type: LayoutActionTypes.CHANGE_SIDEBAR_THEME,
    payload: theme,
});

export const changeSidebarType = (sidebarType: string): LayoutAction => ({
    type: LayoutActionTypes.CHANGE_SIDEBAR_TYPE,
    payload: sidebarType,
});

export const showRightSidebar = (): LayoutAction => ({
    type: LayoutActionTypes.SHOW_RIGHT_SIDEBAR,
    payload: null,
});

export const hideRightSidebar = (): LayoutAction => ({
    type: LayoutActionTypes.HIDE_RIGHT_SIDEBAR,
    payload: null,
});
