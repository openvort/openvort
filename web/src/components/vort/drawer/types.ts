/**
 * Drawer 组件类型定义
 */

/** 抽屉方向 */
export type DrawerPlacement = "top" | "right" | "bottom" | "left";

/** Drawer 组件 Props */
export interface DrawerProps {
    /** 是否显示 */
    open?: boolean;
    /** 标题 */
    title?: string;
    /** 抽屉方向 */
    placement?: DrawerPlacement;
    /** 宽度（仅 left/right） */
    width?: number | string;
    /** 高度（仅 top/bottom） */
    height?: number | string;
    /** 是否显示遮罩 */
    mask?: boolean;
    /** 点击遮罩是否允许关闭 */
    maskClosable?: boolean;
    /** 是否显示关闭按钮 */
    closable?: boolean;
    /** z-index */
    zIndex?: number;
    /** 自定义类名 */
    class?: string;
    /** 底部内容 */
    footer?: boolean;
    /** body 样式 */
    bodyStyle?: Record<string, string>;
    /** 内容区域背景色（仅 body 区域），默认白色 */
    contentBg?: string;
    /** 嵌套抽屉偏移距离 */
    push?: number | false;
    /** 是否支持键盘 ESC 关闭 */
    keyboard?: boolean;
    /** 销毁时是否卸载子组件 */
    destroyOnClose?: boolean;
}

/** Drawer 组件 Emits */
export interface DrawerEmits {
    /** 打开状态变化 */
    (e: "update:open", value: boolean): void;
    /** 关闭事件 */
    (e: "close"): void;
    /** 打开/关闭动画结束后回调 */
    (e: "afterOpenChange", open: boolean): void;
}
