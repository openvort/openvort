<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { CheckCircleFilled, InfoCircleFilled, ExclamationCircleFilled, CloseCircleFilled, CloseOutlined } from "@/components/vort/icons";
import LoadingOutlined from "@/components/vort/icons/LoadingOutlined.vue";

/** Vort NotificationItem - 通知项组件（内部组件） */

export type NotificationType = "success" | "info" | "warning" | "error" | "loading";
export type NotificationPlacement = "top" | "topLeft" | "topRight" | "bottom" | "bottomLeft" | "bottomRight";

interface Props {
    /** 通知 ID */
    id: string;
    /** 通知类型 */
    type?: NotificationType;
    /** 通知标题 */
    message: string;
    /** 通知内容描述 */
    description?: string;
    /** 自动关闭延时（毫秒），设为 0 时不自动关闭 */
    duration?: number;
    /** 是否显示关闭按钮 */
    closable?: boolean;
    /** 弹出位置 */
    placement?: NotificationPlacement;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    type: "info",
    duration: 4500,
    closable: true,
    placement: "topRight"
});

const emit = defineEmits<{
    /** 通知关闭时触发 */
    close: [id: string];
}>();

// 是否可见
const visible = ref(false);
// 是否正在关闭
const closing = ref(false);

// 图标组件映射
const iconComponents = {
    success: CheckCircleFilled,
    info: InfoCircleFilled,
    warning: ExclamationCircleFilled,
    error: CloseCircleFilled,
    loading: LoadingOutlined
};

// 当前图标组件
const IconComponent = computed(() => iconComponents[props.type]);

// 动画方向
const isRight = computed(() => props.placement.includes("Right"));
const isCenter = computed(() => props.placement === "top" || props.placement === "bottom");
const isTop = computed(() => props.placement === "top" || props.placement === "topLeft" || props.placement === "topRight");

// 定时器
let timer: ReturnType<typeof setTimeout> | null = null;

// 关闭通知
const close = () => {
    if (closing.value) return;
    closing.value = true;

    // 动画结束后通知父组件
    setTimeout(() => {
        emit("close", props.id);
    }, 300);
};

// 鼠标进入时暂停自动关闭
const handleMouseEnter = () => {
    if (timer) {
        clearTimeout(timer);
        timer = null;
    }
};

// 鼠标离开时恢复自动关闭
const handleMouseLeave = () => {
    if (props.duration > 0) {
        timer = setTimeout(() => {
            close();
        }, props.duration);
    }
};

// 组件挂载时
onMounted(() => {
    // 触发进入动画
    requestAnimationFrame(() => {
        visible.value = true;
    });

    // 设置自动关闭定时器
    if (props.duration > 0) {
        timer = setTimeout(() => {
            close();
        }, props.duration);
    }
});

// 组件卸载时清除定时器
onUnmounted(() => {
    if (timer) {
        clearTimeout(timer);
        timer = null;
    }
});

// 暴露方法
defineExpose({
    close
});
</script>

<template>
    <div
        :class="[
            'vort-notification-item',
            `vort-notification-${type}`,
            `vort-notification-placement-${placement}`,
            {
                'is-visible': visible,
                'is-closing': closing,
                'is-right': isRight,
                'is-left': !isRight && !isCenter,
                'is-center': isCenter,
                'is-top': isTop,
                'is-bottom': !isTop
            },
            props.class
        ]"
        @mouseenter="handleMouseEnter"
        @mouseleave="handleMouseLeave"
    >
        <div class="vort-notification-content">
            <!-- 图标 -->
            <span class="vort-notification-icon">
                <component :is="IconComponent" :class="{ 'is-spinning': type === 'loading' }" />
            </span>

            <!-- 内容 -->
            <div class="vort-notification-body">
                <!-- 标题 -->
                <div class="vort-notification-message">{{ message }}</div>
                <!-- 描述 -->
                <div v-if="description" class="vort-notification-description">{{ description }}</div>
            </div>

            <!-- 关闭按钮 -->
            <button v-if="closable" class="vort-notification-close" @click="close">
                <CloseOutlined />
            </button>
        </div>
    </div>
</template>

<style scoped>
.vort-notification-item {
    position: relative;
    width: 384px;
    max-width: calc(100vw - 32px);
    padding: 16px;
    margin-bottom: 16px;
    background: #fff;
    border-radius: var(--vort-border-radius-lg, 8px);
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
    pointer-events: all;
    transition: all 0.3s cubic-bezier(0.08, 0.82, 0.17, 1);
}

/* ==================== 动画状态 ==================== */
/* 左右滑动（角落位置） */
.vort-notification-item.is-right {
    opacity: 0;
    transform: translateX(100%);
}

.vort-notification-item.is-left {
    opacity: 0;
    transform: translateX(-100%);
}

/* 上下滑动（居中位置） */
.vort-notification-item.is-center.is-top {
    opacity: 0;
    transform: translateY(-100%);
}

.vort-notification-item.is-center.is-bottom {
    opacity: 0;
    transform: translateY(100%);
}

/* 进入动画 */
.vort-notification-item.is-visible {
    opacity: 1;
    transform: translate(0, 0);
}

/* 离开动画 - 左右 */
.vort-notification-item.is-closing.is-right {
    opacity: 0;
    transform: translateX(100%);
}

.vort-notification-item.is-closing.is-left {
    opacity: 0;
    transform: translateX(-100%);
}

/* 离开动画 - 上下 */
.vort-notification-item.is-closing.is-center.is-top {
    opacity: 0;
    transform: translateY(-100%);
}

.vort-notification-item.is-closing.is-center.is-bottom {
    opacity: 0;
    transform: translateY(100%);
}

/* ==================== 内容布局 ==================== */
.vort-notification-content {
    display: flex;
    gap: 12px;
}

/* 图标 */
.vort-notification-icon {
    flex-shrink: 0;
    line-height: 1;
    font-size: 20px;
    margin-top: 2px;
}

.vort-notification-icon :deep(svg) {
    width: 1em;
    height: 1em;
}

/* 图标颜色 */
.vort-notification-success .vort-notification-icon {
    color: var(--vort-success);
}

.vort-notification-info .vort-notification-icon {
    color: var(--vort-primary);
}

.vort-notification-warning .vort-notification-icon {
    color: var(--vort-warning);
}

.vort-notification-error .vort-notification-icon {
    color: var(--vort-error);
}

.vort-notification-loading .vort-notification-icon {
    color: var(--vort-primary);
}

/* Loading 旋转动画 */
.vort-notification-icon .is-spinning {
    animation: vort-notification-spin 1s linear infinite;
}

@keyframes vort-notification-spin {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}

/* 内容区域 */
.vort-notification-body {
    flex: 1;
    min-width: 0;
}

.vort-notification-message {
    font-size: 14px;
    font-weight: 500;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
    line-height: 1.5;
}

.vort-notification-description {
    margin-top: 4px;
    font-size: 14px;
    color: var(--vort-text-secondary, rgba(0, 0, 0, 0.65));
    line-height: 1.5;
}

/* 关闭按钮 */
.vort-notification-close {
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border: none;
    background: transparent;
    color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45));
    cursor: pointer;
    transition: color 0.2s;
}

.vort-notification-close:hover {
    color: var(--vort-text-secondary, rgba(0, 0, 0, 0.65));
}

.vort-notification-close :deep(svg) {
    width: 14px;
    height: 14px;
}
</style>
