import { createApp, ref, h, type App } from "vue";
import ConfirmDialog, { type ConfirmDialogType } from "./ConfirmDialog.vue";
import { isServer } from "@/components/vort/composables";

export { default as Dialog } from "./Dialog.vue";
export { default as ConfirmDialog } from "./ConfirmDialog.vue";

// 导出类型
export type { DialogProps, DialogEmits, DialogWidth, ConfirmDialogProps, ConfirmDialogEmits } from "./types";
export type { ConfirmDialogType } from "./types";

/** Vort Dialog - 对话框函数式调用 */

// 全局鼠标位置追踪
let mousePosition: { x: number; y: number } | null = null;

const getClickPosition = (e: MouseEvent) => {
    mousePosition = {
        x: e.clientX,
        y: e.clientY
    };
    // 100ms 后清除，避免影响其他弹窗
    setTimeout(() => {
        mousePosition = null;
    }, 100);
};

// 在 document 上监听 click 获取位置（仅客户端）
if (!isServer) {
    document.documentElement.addEventListener("click", getClickPosition, true);
}

// 空的对话框实例（用于 SSR 环境）
const noopInstance: DialogInstance = {
    close: () => {},
    update: () => {}
};

// 确认对话框配置接口
export interface DialogConfig {
    /** 标题 */
    title?: string;
    /** 内容 */
    content?: string;
    /** 内容区域背景色（仅 body 区域），默认白色 */
    contentBg?: string;
    /** 对话框宽度 */
    width?: number | string;
    /** 是否显示右上角关闭按钮 */
    closable?: boolean;
    /** 点击蒙层是否允许关闭 */
    maskClosable?: boolean;
    /** 是否支持键盘 ESC 关闭 */
    keyboard?: boolean;
    /** 确定按钮文字 */
    okText?: string;
    /** 取消按钮文字 */
    cancelText?: string;
    /** 确定按钮类型 */
    okType?: "primary" | "danger";
    /** z-index */
    zIndex?: number;
    /** 垂直居中展示 */
    centered?: boolean;
    /** 点击确定回调，返回 Promise 时会显示加载状态 */
    onOk?: () => void | Promise<void>;
    /** 点击取消回调 */
    onCancel?: () => void;
    /** 完全关闭后回调 */
    afterClose?: () => void;
}

// 对话框实例接口
export interface DialogInstance {
    /** 关闭对话框 */
    close: () => void;
    /** 更新对话框配置 */
    update: (config: Partial<DialogConfig>) => void;
}

// 内部状态
interface DialogState {
    app: App | null;
    container: HTMLDivElement | null;
    open: ReturnType<typeof ref<boolean>>;
    confirmLoading: ReturnType<typeof ref<boolean>>;
    config: DialogConfig;
}

// 创建对话框
const createDialog = (type: ConfirmDialogType, config: DialogConfig): DialogInstance => {
    // SSR 环境下不执行，返回空实例
    if (isServer) {
        return noopInstance;
    }

    // 创建容器
    const container = document.createElement("div");
    container.className = "vort-confirm-dialog-container";
    document.body.appendChild(container);

    // 捕获当前鼠标位置（在创建时立即获取）
    const clickPosition = mousePosition ? { ...mousePosition } : null;

    // 响应式状态
    const open = ref(true);
    const confirmLoading = ref(false);
    let currentConfig = { ...config };

    // 销毁对话框
    const destroy = () => {
        open.value = false;
    };

    // 完全关闭后清理
    const cleanup = () => {
        if (state.app) {
            state.app.unmount();
            state.app = null;
        }
        if (state.container && document.body.contains(state.container)) {
            document.body.removeChild(state.container);
            state.container = null;
        }
        currentConfig.afterClose?.();
    };

    // 处理确定按钮
    const handleOk = async () => {
        if (currentConfig.onOk) {
            const result = currentConfig.onOk();
            if (result instanceof Promise) {
                confirmLoading.value = true;
                try {
                    await result;
                    destroy();
                } catch {
                    // Promise 被 reject 时不关闭
                } finally {
                    confirmLoading.value = false;
                }
            } else {
                destroy();
            }
        } else {
            destroy();
        }
    };

    // 处理取消按钮
    const handleCancel = () => {
        currentConfig.onCancel?.();
        destroy();
    };

    // 状态对象
    const state: DialogState = {
        app: null,
        container,
        open,
        confirmLoading,
        config: currentConfig
    };

    // 创建 Vue 应用
    state.app = createApp({
        setup() {
            return () =>
                h(ConfirmDialog, {
                    open: open.value,
                    type,
                    title: currentConfig.title,
                    content: currentConfig.content,
                    contentBg: currentConfig.contentBg,
                    width: currentConfig.width,
                    closable: currentConfig.closable,
                    maskClosable: currentConfig.maskClosable,
                    keyboard: currentConfig.keyboard,
                    okText: currentConfig.okText,
                    cancelText: currentConfig.cancelText,
                    okType: currentConfig.okType,
                    confirmLoading: confirmLoading.value,
                    zIndex: currentConfig.zIndex,
                    centered: currentConfig.centered,
                    mousePosition: clickPosition,
                    "onUpdate:open": (value: boolean) => {
                        open.value = value;
                        if (!value) {
                            handleCancel();
                        }
                    },
                    onOk: handleOk,
                    onCancel: handleCancel,
                    onAfterClose: cleanup
                });
        }
    });

    state.app.mount(container);

    // 返回实例
    return {
        close: destroy,
        update: (newConfig: Partial<DialogConfig>) => {
            currentConfig = { ...currentConfig, ...newConfig };
            // 触发重新渲染
            if (state.app) {
                state.app.unmount();
                state.app = createApp({
                    setup() {
                        return () =>
                            h(ConfirmDialog, {
                                open: open.value,
                                type,
                                title: currentConfig.title,
                                content: currentConfig.content,
                                contentBg: currentConfig.contentBg,
                                width: currentConfig.width,
                                closable: currentConfig.closable,
                                maskClosable: currentConfig.maskClosable,
                                keyboard: currentConfig.keyboard,
                                okText: currentConfig.okText,
                                cancelText: currentConfig.cancelText,
                                okType: currentConfig.okType,
                                confirmLoading: confirmLoading.value,
                                zIndex: currentConfig.zIndex,
                                centered: currentConfig.centered,
                                mousePosition: clickPosition,
                                "onUpdate:open": (value: boolean) => {
                                    open.value = value;
                                    if (!value) {
                                        handleCancel();
                                    }
                                },
                                onOk: handleOk,
                                onCancel: handleCancel,
                                onAfterClose: cleanup
                            });
                    }
                });
                state.app.mount(container);
            }
        }
    };
};

// Dialog API
export const dialog = {
    /**
     * 信息提示对话框
     * @param config 配置项
     */
    info: (config: DialogConfig): DialogInstance => createDialog("info", config),

    /**
     * 成功提示对话框
     * @param config 配置项
     */
    success: (config: DialogConfig): DialogInstance => createDialog("success", config),

    /**
     * 错误提示对话框
     * @param config 配置项
     */
    error: (config: DialogConfig): DialogInstance => createDialog("error", config),

    /**
     * 警告提示对话框
     * @param config 配置项
     */
    warning: (config: DialogConfig): DialogInstance => createDialog("warning", config),

    /**
     * 确认对话框
     * @param config 配置项
     */
    confirm: (config: DialogConfig): DialogInstance => createDialog("confirm", config)
};
