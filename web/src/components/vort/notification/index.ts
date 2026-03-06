import { createApp, ref, h, type App } from "vue";
import NotificationItem, { type NotificationType, type NotificationPlacement } from "./NotificationItem.vue";
import { getVortPopupContainer, isServer } from "@/components/vort/composables";

/** Vort Notification - 全局通知提醒 */

// 通知配置接口
export interface NotificationConfig {
    /** 通知标题（必填） */
    message: string;
    /** 通知内容描述 */
    description?: string;
    /** 自动关闭延时（毫秒），默认 4500，设为 0 时不自动关闭 */
    duration?: number;
    /** 是否显示关闭按钮，默认 true */
    closable?: boolean;
    /** 弹出位置，默认 topRight */
    placement?: NotificationPlacement;
    /** 关闭时的回调 */
    onClose?: () => void;
    /** 唯一标识 */
    key?: string;
}

// 通知实例接口
export interface NotificationInstance {
    /** 关闭通知 */
    close: () => void;
}

// 全局配置接口
export interface NotificationGlobalConfig {
    /** 默认自动关闭延时（毫秒） */
    duration?: number;
    /** 弹出位置 */
    placement?: NotificationPlacement;
    /** 消息从顶部弹出时，距离顶部的位置 */
    top?: number;
    /** 消息从底部弹出时，距离底部的位置 */
    bottom?: number;
    /** 最大显示数量，超过时会自动关闭最早的通知 */
    maxCount?: number;
}

// 内部通知数据结构
interface NotificationData {
    id: string;
    type: NotificationType;
    message: string;
    description?: string;
    duration: number;
    closable: boolean;
    placement: NotificationPlacement;
    onClose?: () => void;
}

// 全局配置
let globalConfig: NotificationGlobalConfig = {
    duration: 4500,
    placement: "topRight",
    top: 24,
    bottom: 24,
    maxCount: undefined
};

// 通知层级：高于 popup(1050) / tooltip(1070)，避免被下拉菜单遮挡
const NOTIFICATION_Z_INDEX = 1090;

// 各位置的通知列表
const notificationLists: Record<NotificationPlacement, { value: NotificationData[] }> = {
    top: ref<NotificationData[]>([]),
    topLeft: ref<NotificationData[]>([]),
    topRight: ref<NotificationData[]>([]),
    bottom: ref<NotificationData[]>([]),
    bottomLeft: ref<NotificationData[]>([]),
    bottomRight: ref<NotificationData[]>([])
};

// 各位置的容器实例
const containers: Record<NotificationPlacement, { app: App | null; el: HTMLDivElement | null }> = {
    top: { app: null, el: null },
    topLeft: { app: null, el: null },
    topRight: { app: null, el: null },
    bottom: { app: null, el: null },
    bottomLeft: { app: null, el: null },
    bottomRight: { app: null, el: null }
};

// 生成唯一 ID
let notificationId = 0;
const generateId = () => `vort-notification-${++notificationId}`;

// 获取位置样式
const getPlacementStyle = (placement: NotificationPlacement): string => {
    const isTop = placement.startsWith("top") || placement === "top";
    const isCenter = placement === "top" || placement === "bottom";
    const isRight = placement.endsWith("Right");

    const topValue = isTop ? `${globalConfig.top}px` : "auto";
    const bottomValue = isTop ? "auto" : `${globalConfig.bottom}px`;
    const flexDirection = isTop ? "column" : "column-reverse";

    // 居中位置
    if (isCenter) {
        return `
            position: fixed;
            top: ${topValue};
            bottom: ${bottomValue};
            left: 50%;
            transform: translateX(-50%);
            z-index: ${NOTIFICATION_Z_INDEX};
            pointer-events: none;
            display: flex;
            flex-direction: ${flexDirection};
            align-items: center;
            padding: 0 16px;
        `;
    }

    // 角落位置
    const leftValue = isRight ? "auto" : "0";
    const rightValue = isRight ? "0" : "auto";
    const alignItems = isRight ? "flex-end" : "flex-start";

    return `
        position: fixed;
        top: ${topValue};
        bottom: ${bottomValue};
        left: ${leftValue};
        right: ${rightValue};
        z-index: ${NOTIFICATION_Z_INDEX};
        pointer-events: none;
        display: flex;
        flex-direction: ${flexDirection};
        align-items: ${alignItems};
        padding: 0 16px;
    `;
};

// 创建通知容器
const createContainer = (placement: NotificationPlacement) => {
    if (containers[placement].el) return;

    const containerEl = document.createElement("div");
    containerEl.className = `vort-notification-container vort-notification-${placement}`;
    containerEl.style.cssText = getPlacementStyle(placement);
    // 使用 getVortPopupContainer 获取正确的挂载点，以继承 ConfigProvider 的 CSS 变量
    const mountTarget = getVortPopupContainer();
    mountTarget.appendChild(containerEl);

    const notificationList = notificationLists[placement]!;

    // 创建 Vue 应用渲染通知列表
    const containerApp = createApp({
        setup() {
            const handleClose = (id: string) => {
                const index = notificationList.value.findIndex((n) => n.id === id);
                if (index > -1) {
                    const notification = notificationList.value[index]!;
                    notification.onClose?.();
                    notificationList.value.splice(index, 1);
                }

                // 如果没有通知了，移除容器
                if (notificationList.value.length === 0) {
                    destroyContainer(placement);
                }
            };

            return () =>
                notificationList.value.map((n) =>
                    h(NotificationItem, {
                        key: n.id,
                        id: n.id,
                        type: n.type,
                        message: n.message,
                        description: n.description,
                        duration: n.duration,
                        closable: n.closable,
                        placement: n.placement,
                        onClose: handleClose
                    })
                );
        }
    });

    containerApp.mount(containerEl);

    containers[placement] = { app: containerApp, el: containerEl };
};

// 销毁通知容器
const destroyContainer = (placement: NotificationPlacement) => {
    const container = containers[placement];
    if (container.app) {
        container.app.unmount();
        container.app = null;
    }
    if (container.el) {
        // 从父元素中移除（可能是 vort-teleport-container 或 body）
        container.el.parentElement?.removeChild(container.el);
        container.el = null;
    }
};

// 空的通知实例（用于 SSR 环境）
const noopInstance: NotificationInstance = { close: () => {} };

// 添加通知
const addNotification = (type: NotificationType, config: NotificationConfig): NotificationInstance => {
    // SSR 环境下不执行，返回空实例
    if (isServer) {
        return noopInstance;
    }

    const placement = config.placement ?? globalConfig.placement ?? "topRight";
    const id = config.key || generateId();
    const duration = config.duration ?? globalConfig.duration ?? 4500;
    const notificationList = notificationLists[placement]!;

    // 检查是否有相同 key 的通知，如果有则更新
    const existingIndex = notificationList.value.findIndex((n) => config.key && n.id === config.key);

    if (existingIndex > -1) {
        // 更新已有通知
        notificationList.value[existingIndex] = {
            ...notificationList.value[existingIndex]!,
            type,
            message: config.message,
            description: config.description,
            duration,
            closable: config.closable ?? true,
            placement,
            onClose: config.onClose
        };
    } else {
        // 确保容器存在
        createContainer(placement);

        // 检查最大数量限制
        if (globalConfig.maxCount && notificationList.value.length >= globalConfig.maxCount) {
            // 移除最早的通知
            const oldest = notificationList.value.shift();
            oldest?.onClose?.();
        }

        // 添加新通知
        notificationList.value.push({
            id,
            type,
            message: config.message,
            description: config.description,
            duration,
            closable: config.closable ?? true,
            placement,
            onClose: config.onClose
        });
    }

    // 返回通知实例
    return {
        close: () => {
            const index = notificationList.value.findIndex((n) => n.id === id);
            if (index > -1) {
                const n = notificationList.value[index]!;
                n.onClose?.();
                notificationList.value.splice(index, 1);

                if (notificationList.value.length === 0) {
                    destroyContainer(placement);
                }
            }
        }
    };
};

// Notification API
export const notification = {
    /**
     * 成功通知
     * @param config 通知配置
     */
    success: (config: NotificationConfig): NotificationInstance => addNotification("success", config),

    /**
     * 信息通知
     * @param config 通知配置
     */
    info: (config: NotificationConfig): NotificationInstance => addNotification("info", config),

    /**
     * 警告通知
     * @param config 通知配置
     */
    warning: (config: NotificationConfig): NotificationInstance => addNotification("warning", config),

    /**
     * 错误通知
     * @param config 通知配置
     */
    error: (config: NotificationConfig): NotificationInstance => addNotification("error", config),

    /**
     * 打开通知（通用方法）
     * @param config 通知配置，可指定 type
     */
    open: (config: NotificationConfig & { type?: NotificationType }): NotificationInstance => addNotification(config.type ?? "info", config),

    /**
     * 全局配置
     * @param config 全局配置项
     */
    config: (config: NotificationGlobalConfig) => {
        globalConfig = { ...globalConfig, ...config };

        // 更新已存在的容器位置
        const placements: NotificationPlacement[] = ["top", "topLeft", "topRight", "bottom", "bottomLeft", "bottomRight"];
        placements.forEach((placement) => {
            if (containers[placement].el) {
                containers[placement].el!.style.cssText = getPlacementStyle(placement);
            }
        });
    },

    /**
     * 销毁所有通知
     */
    destroy: () => {
        const placements: NotificationPlacement[] = ["top", "topLeft", "topRight", "bottom", "bottomLeft", "bottomRight"];
        placements.forEach((placement) => {
            notificationLists[placement].value = [];
            destroyContainer(placement);
        });
    }
};

// 导出类型
export type { NotificationType, NotificationPlacement };
