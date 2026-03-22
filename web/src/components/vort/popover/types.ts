/**
 * Popover 组件类型定义
 */

/** 气泡框位置 */
export type PopoverPlacement =
    | "top"
    | "topLeft"
    | "topRight"
    | "bottom"
    | "bottomLeft"
    | "bottomRight"
    | "left"
    | "leftTop"
    | "leftBottom"
    | "right"
    | "rightTop"
    | "rightBottom";

/** 触发方式 */
export type PopoverTrigger = "click" | "hover" | "focus" | "contextMenu" | "manual";

/** Popover 组件 Props */
export interface PopoverProps {
    /** 卡片标题 */
    title?: string;
    /** 卡片内容 */
    content?: string;
    /** 气泡框位置 */
    placement?: PopoverPlacement;
    /** 触发方式 */
    trigger?: PopoverTrigger;
    /** 是否显示箭头 */
    arrow?: boolean;
    /** 控制浮层显示（受控模式） */
    open?: boolean;
    /** 是否禁用 */
    disabled?: boolean;
    /** 鼠标移入后延时多少才显示 (ms)，trigger="hover" 时有效 */
    mouseEnterDelay?: number;
    /** 鼠标移出后延时多少才隐藏 (ms)，trigger="hover" 时有效 */
    mouseLeaveDelay?: number;
    /** 菜单渲染父节点 */
    getPopupContainer?: () => HTMLElement;
    /** 浮层额外类名 */
    overlayClass?: string;
    /** 浮层额外样式 */
    overlayStyle?: Record<string, string>;
    /** 自定义类名 */
    class?: string;
}

/** Popover 组件 Emits */
export interface PopoverEmits {
    /** open 状态变化事件 */
    (e: "openChange", open: boolean): void;
    /** v-model:open 更新事件 */
    (e: "update:open", open: boolean): void;
}

/** Popover 组件暴露的方法 */
export interface PopoverExpose {
    /** 显示 popover */
    show: () => void;
    /** 隐藏 popover */
    hide: () => void;
}
