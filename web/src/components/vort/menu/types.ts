/**
 * Vort Menu 类型定义
 * 参考 Ant Design 5.x Menu 组件
 */

/** 菜单模式 */
export type MenuMode = "vertical" | "horizontal" | "inline";

/** 菜单主题 */
export type MenuTheme = "light" | "dark";

/** 菜单项类型 */
export type MenuItemType = "item" | "group" | "submenu" | "divider";

/** 菜单项基础接口 */
export interface MenuItemBase {
    /** 唯一标识 */
    key: string;
    /** 菜单项类型 */
    type?: MenuItemType;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义类名 */
    class?: string;
    /** 自定义样式 */
    style?: Record<string, string>;
}

/** 菜单项 */
export interface MenuItem extends MenuItemBase {
    type?: "item";
    /** 菜单标题 */
    label?: string;
    /** 菜单图标 */
    icon?: string;
    /** 是否危险项（红色） */
    danger?: boolean;
}

/** 子菜单 */
export interface SubMenuItem extends MenuItemBase {
    type: "submenu";
    /** 子菜单标题 */
    label?: string;
    /** 子菜单图标 */
    icon?: string;
    /** 子菜单项 */
    children?: MenuItemConfig[];
    /** 弹出菜单的类名 */
    popupClassName?: string;
    /** 弹出菜单的偏移 */
    popupOffset?: [number, number];
}

/** 菜单分组 */
export interface MenuItemGroup extends MenuItemBase {
    type: "group";
    /** 分组标题 */
    label?: string;
    /** 分组内菜单项 */
    children?: MenuItemConfig[];
}

/** 分割线 */
export interface MenuDividerItem extends MenuItemBase {
    type: "divider";
    /** 是否虚线 */
    dashed?: boolean;
}

/** 菜单项配置联合类型 */
export type MenuItemConfig = MenuItem | SubMenuItem | MenuItemGroup | MenuDividerItem;

/** 菜单上下文 */
export interface MenuContext {
    /** 当前模式 */
    mode: MenuMode;
    /** 当前主题 */
    theme: MenuTheme;
    /** 当前选中的菜单项 key 数组 */
    selectedKeys: string[];
    /** 当前展开的 SubMenu 菜单项 key 数组 */
    openKeys: string[];
    /** 是否内联折叠 */
    inlineCollapsed: boolean;
    /** 缩进宽度 */
    inlineIndent: number;
    /** 层级 */
    level: number;
    /** 注册菜单项 */
    registerItem: (key: string) => void;
    /** 取消注册菜单项 */
    unregisterItem: (key: string) => void;
    /** 选择菜单项 */
    selectItem: (key: string) => void;
    /** 切换子菜单展开状态 */
    toggleSubMenu: (key: string) => void;
    /** 设置展开的子菜单 */
    setOpenKeys: (keys: string[]) => void;
}

/** SubMenu 上下文 */
export interface SubMenuContext {
    /** 父级 key */
    parentKey: string;
    /** 是否展开 */
    isOpen: boolean;
}
