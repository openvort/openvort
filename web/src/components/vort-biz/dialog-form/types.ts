import type { Component } from "vue";

/**
 * DialogForm 组件 Props
 */
export interface DialogFormProps {
    // ========== 核心属性 ==========
    /** 表单组件（必需） */
    component: Component;
    /** 传递给表单组件的参数 */
    params?: Record<string, unknown>;

    // ========== 模式切换 ==========
    /** 是否使用抽屉模式，默认 false（Dialog 模式） */
    isDrawer?: boolean;

    // ========== 通用属性 ==========
    /** 标题 */
    title?: string;
    /** 宽度，默认 Dialog:520px, Drawer:378px */
    width?: string | number;
    /** 是否显示关闭按钮，默认 true */
    closable?: boolean;
    /** 点击遮罩是否允许关闭，默认 true */
    maskClosable?: boolean;
    /** 关闭时是否销毁内容，默认 false */
    destroyOnClose?: boolean;
    /** z-index */
    zIndex?: number;

    // ========== Dialog 特有属性 ==========
    /** 垂直居中展示（仅 Dialog 模式） */
    centered?: boolean;

    // ========== Drawer 特有属性 ==========
    /** 抽屉方向（仅 Drawer 模式），默认 right */
    placement?: "left" | "right" | "top" | "bottom";
}

/**
 * DialogForm 组件 Emits
 */
export interface DialogFormEmits {
    /** 表单提交成功后触发 */
    ok: [];
    /** 取消/关闭时触发 */
    cancel: [];
    /** 关闭动画结束后触发 */
    afterClose: [];
}

/**
 * 表单组件需要接收的 Props
 * 表单组件应该实现这个接口
 */
export interface FormComponentProps {
    /** 传递的参数 */
    params: Record<string, unknown>;
    /** 成功回调，关闭弹窗并触发 ok 事件 */
    okHandler?: () => void;
    /** 取消回调，仅关闭弹窗 */
    cancelHandler?: () => void;
}
