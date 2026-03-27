import { createApp, ref, h, type App, type ComponentPublicInstance } from "vue";
import MessageItem, { type MessageType } from "./MessageItem.vue";
import { getVortPopupContainer, isServer, Z_INDEX_BASE } from "@/components/vort/composables";

/** Vort Message - 全局提示 */

// 消息配置接口
export interface MessageConfig {
    /** 消息内容 */
    content: string;
    /** 自动关闭延时（毫秒），默认 3000，设为 0 时不自动关闭 */
    duration?: number;
    /** 关闭时的回调 */
    onClose?: () => void;
    /** 唯一标识 */
    key?: string;
}

// 消息实例接口
export interface MessageInstance {
    /** 关闭消息 */
    close: () => void;
}

// 全局配置接口
export interface MessageGlobalConfig {
    /** 默认自动关闭延时（毫秒） */
    duration?: number;
    /** 消息距离顶部的位置 */
    top?: number;
    /** 最大显示数量，超过时会自动关闭最早的消息 */
    maxCount?: number;
}

// 内部消息数据结构
interface MessageData {
    id: string;
    type: MessageType;
    content: string;
    duration: number;
    onClose?: () => void;
}

// 全局配置
let globalConfig: MessageGlobalConfig = {
    duration: 3000,
    top: 8,
    maxCount: undefined
};

// 消息列表
const messageList = ref<MessageData[]>([]);

// 消息容器实例
let containerApp: App | null = null;
let containerEl: HTMLDivElement | null = null;

// 生成唯一 ID
let messageId = 0;
const generateId = () => `vort-message-${++messageId}`;

// 创建消息容器
const createContainer = () => {
    if (containerEl) return;

    containerEl = document.createElement("div");
    containerEl.className = "vort-message-container";
    containerEl.style.cssText = `
        position: fixed;
        top: ${globalConfig.top}px;
        left: 0;
        right: 0;
        z-index: ${Z_INDEX_BASE.message};
        pointer-events: none;
        display: flex;
        flex-direction: column;
        align-items: center;
    `;
    // 使用 getVortPopupContainer 获取正确的挂载点，以继承 ConfigProvider 的 CSS 变量
    const mountTarget = getVortPopupContainer();
    mountTarget.appendChild(containerEl);

    // 创建 Vue 应用渲染消息列表
    containerApp = createApp({
        setup() {
            const handleClose = (id: string) => {
                const index = messageList.value.findIndex((m) => m.id === id);
                if (index > -1) {
                    const msg = messageList.value[index]!;
                    msg.onClose?.();
                    messageList.value.splice(index, 1);
                }

                // 如果没有消息了，移除容器
                if (messageList.value.length === 0) {
                    destroyContainer();
                }
            };

            return () =>
                messageList.value.map((msg) =>
                    h(MessageItem, {
                        key: msg.id,
                        id: msg.id,
                        type: msg.type,
                        content: msg.content,
                        duration: msg.duration,
                        onClose: handleClose
                    })
                );
        }
    });

    containerApp.mount(containerEl);
};

// 销毁消息容器
const destroyContainer = () => {
    if (containerApp) {
        containerApp.unmount();
        containerApp = null;
    }
    if (containerEl) {
        // 从父元素中移除（可能是 vort-teleport-container 或 body）
        containerEl.parentElement?.removeChild(containerEl);
        containerEl = null;
    }
};

// 空的消息实例（用于 SSR 环境）
const noopInstance: MessageInstance = { close: () => {} };

// 添加消息
const addMessage = (type: MessageType, config: string | MessageConfig): MessageInstance => {
    // SSR 环境下不执行，返回空实例
    if (isServer) {
        return noopInstance;
    }

    // 标准化配置
    const normalizedConfig: MessageConfig = typeof config === "string" ? { content: config } : config;

    const id = normalizedConfig.key || generateId();
    const duration = normalizedConfig.duration ?? globalConfig.duration ?? 3000;

    // 检查是否有相同 key 的消息，如果有则更新
    const existingIndex = messageList.value.findIndex((m) => normalizedConfig.key && m.id === normalizedConfig.key);

    if (existingIndex > -1) {
        // 更新已有消息
        messageList.value[existingIndex] = {
            ...messageList.value[existingIndex]!,
            type,
            content: normalizedConfig.content,
            duration,
            onClose: normalizedConfig.onClose
        };
    } else {
        // 确保容器存在
        createContainer();

        // 检查最大数量限制
        if (globalConfig.maxCount && messageList.value.length >= globalConfig.maxCount) {
            // 移除最早的消息
            const oldest = messageList.value.shift();
            oldest?.onClose?.();
        }

        // 添加新消息
        messageList.value.push({
            id,
            type,
            content: normalizedConfig.content,
            duration,
            onClose: normalizedConfig.onClose
        });
    }

    // 返回消息实例
    return {
        close: () => {
            const index = messageList.value.findIndex((m) => m.id === id);
            if (index > -1) {
                const msg = messageList.value[index]!;
                msg.onClose?.();
                messageList.value.splice(index, 1);

                if (messageList.value.length === 0) {
                    destroyContainer();
                }
            }
        }
    };
};

// Message API
export const message = {
    /**
     * 成功提示
     * @param config 消息内容或配置
     */
    success: (config: string | MessageConfig): MessageInstance => addMessage("success", config),

    /**
     * 信息提示
     * @param config 消息内容或配置
     */
    info: (config: string | MessageConfig): MessageInstance => addMessage("info", config),

    /**
     * 警告提示
     * @param config 消息内容或配置
     */
    warning: (config: string | MessageConfig): MessageInstance => addMessage("warning", config),

    /**
     * 错误提示
     * @param config 消息内容或配置
     */
    error: (config: string | MessageConfig): MessageInstance => addMessage("error", config),

    /**
     * 加载中提示
     * @param config 消息内容或配置
     */
    loading: (config: string | MessageConfig): MessageInstance => addMessage("loading", config),

    /**
     * 打开消息（通用方法）
     * @param type 消息类型
     * @param config 消息内容或配置
     */
    open: (type: MessageType, config: string | MessageConfig): MessageInstance => addMessage(type, config),

    /**
     * 全局配置
     * @param config 全局配置项
     */
    config: (config: MessageGlobalConfig) => {
        globalConfig = { ...globalConfig, ...config };

        // 如果容器已存在，更新 top 值
        if (containerEl && config.top !== undefined) {
            containerEl.style.top = `${config.top}px`;
        }
    },

    /**
     * 销毁所有消息
     */
    destroy: () => {
        messageList.value = [];
        destroyContainer();
    }
};

// 导出类型
export type { MessageType };
