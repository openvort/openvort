/**
 * Tooltip 组件类型定义
 */

/** 气泡框位置 */
export type TooltipPlacement =
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
export type TooltipTrigger = "click" | "hover" | "focus" | "contextMenu" | "manual";

/** Tooltip 组件 Props */
export interface TooltipProps {
    /** 提示文字 */
    title?: string;
    /** 气泡框位置 */
    placement?: TooltipPlacement;
    /** 触发方式 */
    trigger?: TooltipTrigger;
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
    /** 背景颜色 */
    color?: string;
    /** 是否使用暗色主题 */
    dark?: boolean;
    /** 菜单渲染父节点 */
    getPopupContainer?: () => HTMLElement;
    /** 浮层额外类名 */
    overlayClass?: string;
    /** 浮层额外样式 */
    overlayStyle?: Record<string, string>;
    /** 自定义类名 */
    class?: string;
}

/** Tooltip 组件 Emits */
export interface TooltipEmits {
    /** open 状态变化事件 */
    (e: "openChange", open: boolean): void;
    /** v-model:open 更新事件 */
    (e: "update:open", open: boolean): void;
}

/** Tooltip 组件暴露的方法 */
export interface TooltipExpose {
    /** 显示 tooltip */
    show: () => void;
    /** 隐藏 tooltip */
    hide: () => void;
    /** 更新位置 */
    updatePosition: () => void;
}
