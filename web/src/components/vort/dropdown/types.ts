/**
 * Dropdown 组件类型定义
 */

// ==================== Dropdown 主组件 ====================

/** 下拉菜单触发方式 */
export type DropdownTrigger = "hover" | "click" | "contextMenu";

/** 下拉菜单弹出位置 */
export type DropdownPlacement =
    | "bottom"
    | "bottomLeft"
    | "bottomRight"
    | "top"
    | "topLeft"
    | "topRight"
    | "left"
    | "leftTop"
    | "leftBottom"
    | "right"
    | "rightTop"
    | "rightBottom";

/** Dropdown 组件 Props */
export interface DropdownProps {
    /** 菜单是否显示（受控模式） */
    open?: boolean;
    /** 菜单是否默认显示（非受控模式） */
    defaultOpen?: boolean;
    /** 触发下拉的行为，支持数组 */
    trigger?: DropdownTrigger | DropdownTrigger[];
    /** 菜单弹出位置 */
    placement?: DropdownPlacement;
    /** 菜单是否禁用 */
    disabled?: boolean;
    /** 下拉根元素的类名 */
    overlayClassName?: string;
    /** 下拉根元素的样式 */
    overlayStyle?: Record<string, string>;
    /** 是否显示箭头 */
    arrow?: boolean | { pointAtCenter: boolean };
    /** 关闭后是否销毁 Dropdown 内容（默认：true） */
    destroyOnHidden?: boolean;
    /**
     * @deprecated 请使用 destroyOnHidden
     */
    destroyPopupOnHide?: boolean;
    /** 下拉框和触发元素之间的距离 */
    offset?: number;
    /** 菜单渲染父节点 */
    getPopupContainer?: () => HTMLElement;
    /** 触发元素的自定义类名 */
    class?: string;
    /** 鼠标移入后延迟多少时间显示 Dropdown，单位：毫秒（仅 hover 触发时有效） */
    mouseEnterDelay?: number;
    /** 鼠标移出后延迟多少时间关闭 Dropdown，单位：毫秒（仅 hover 触发时有效） */
    mouseLeaveDelay?: number;
}

/** Dropdown 组件 Emits */
export interface DropdownEmits {
    /** 菜单显示状态改变时调用 */
    (e: "update:open", open: boolean): void;
    /** 菜单显示状态改变时调用（兼容 ant-design 事件命名） */
    (e: "openChange", open: boolean): void;
}

/** Dropdown 组件暴露的方法 */
export interface DropdownExpose {
    /** 打开下拉菜单 */
    open: () => void;
    /** 关闭下拉菜单 */
    close: () => void;
}

// ==================== DropdownButton 组件 ====================

/** 下拉按钮类型 */
export type DropdownButtonType = "primary" | "default" | "dashed";

/** 下拉按钮尺寸 */
export type DropdownButtonSize = "large" | "middle" | "small";

/** 下拉按钮触发方式 */
export type DropdownButtonTrigger = "hover" | "click";

/** 下拉按钮弹出位置 */
export type DropdownButtonPlacement = "bottom" | "bottomLeft" | "bottomRight" | "top" | "topLeft" | "topRight";

/** DropdownButton 组件 Props */
export interface DropdownButtonProps {
    /** 下拉菜单是否显示（受控模式） */
    open?: boolean;
    /** 按钮类型 */
    type?: DropdownButtonType;
    /** 按钮尺寸 */
    size?: DropdownButtonSize;
    /** 是否为危险按钮 */
    danger?: boolean;
    /** 左侧按钮是否禁用 */
    disabled?: boolean;
    /** 整个按钮组是否禁用（包括下拉触发按钮） */
    buttonsDisabled?: boolean;
    /** 是否加载中 */
    loading?: boolean;
    /** 触发下拉的行为 */
    trigger?: DropdownButtonTrigger | DropdownButtonTrigger[];
    /** 菜单弹出位置 */
    placement?: DropdownButtonPlacement;
    /** 下拉菜单的 class */
    overlayClassName?: string;
    /** 下拉菜单的 style */
    overlayStyle?: Record<string, string>;
    /** 是否显示箭头 */
    arrow?: boolean | { pointAtCenter: boolean };
    /** 关闭后是否销毁 Dropdown 内容 */
    destroyOnHidden?: boolean;
    /** 下拉框距触发元素的距离 */
    offset?: number;
    /** 菜单渲染父节点 */
    getPopupContainer?: () => HTMLElement;
    /** 鼠标移入后延迟多少时间显示 Dropdown，单位：毫秒 */
    mouseEnterDelay?: number;
    /** 鼠标移出后延迟多少时间关闭 Dropdown，单位：毫秒 */
    mouseLeaveDelay?: number;
}

/** DropdownButton 组件 Emits */
export interface DropdownButtonEmits {
    /** 左侧按钮点击事件 */
    (e: "click", event: MouseEvent): void;
    /** 下拉菜单显示状态改变时调用 */
    (e: "update:open", open: boolean): void;
    /** 下拉菜单显示状态改变时调用 */
    (e: "openChange", open: boolean): void;
}

// ==================== DropdownMenuItem 组件 ====================

/** DropdownMenuItem 组件 Props */
export interface DropdownMenuItemProps {
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否为危险项（红色） */
    danger?: boolean;
    /** 菜单图标 */
    icon?: string;
    /** 自定义类名 */
    class?: string;
}

/** DropdownMenuItem 组件 Emits */
export interface DropdownMenuItemEmits {
    /** 点击菜单项时触发 */
    (e: "click", event: Event): void;
}

// ==================== DropdownMenuLabel 组件 ====================

/** DropdownMenuLabel 组件 Props */
export interface DropdownMenuLabelProps {
    /** 自定义类名 */
    class?: string;
}

// ==================== DropdownMenuGroup 组件 ====================

/** DropdownMenuGroup 组件 Props */
export interface DropdownMenuGroupProps {
    /** 自定义类名 */
    class?: string;
}

// ==================== DropdownMenuSub 组件 ====================

/** DropdownMenuSub 组件 Props */
export interface DropdownMenuSubProps {
    /** 子菜单标题 */
    title?: string;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义类名 */
    class?: string;
}

// ==================== DropdownMenuCheckboxItem 组件 ====================

/** DropdownMenuCheckboxItem 组件 Props */
export interface DropdownMenuCheckboxItemProps {
    /** 选中状态 */
    checked?: boolean;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义类名 */
    class?: string;
}

/** DropdownMenuCheckboxItem 组件 Emits */
export interface DropdownMenuCheckboxItemEmits {
    /** 选中状态改变时触发 */
    (e: "update:checked", checked: boolean): void;
}

// ==================== DropdownMenuRadioGroup 组件 ====================

/** DropdownMenuRadioGroup 组件 Props */
export interface DropdownMenuRadioGroupProps {
    /** 选中的值 */
    modelValue?: string;
    /** 自定义类名 */
    class?: string;
}

/** DropdownMenuRadioGroup 组件 Emits */
export interface DropdownMenuRadioGroupEmits {
    /** 选中值改变时触发 */
    (e: "update:modelValue", value: string): void;
}

// ==================== DropdownMenuRadioItem 组件 ====================

/** DropdownMenuRadioItem 组件 Props */
export interface DropdownMenuRadioItemProps {
    /** 选项值 */
    value: string;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义类名 */
    class?: string;
}
