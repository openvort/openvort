<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { CheckCircleFilled, InfoCircleFilled, ExclamationCircleFilled, CloseCircleFilled } from "@/components/vort/icons";
import LoadingOutlined from "@/components/vort/icons/LoadingOutlined.vue";

/** Vort MessageItem - 消息项组件（内部组件） */

export type MessageType = "success" | "info" | "warning" | "error" | "loading";

interface Props {
    /** 消息 ID */
    id: string;
    /** 消息类型 */
    type?: MessageType;
    /** 消息内容 */
    content: string;
    /** 自动关闭延时（毫秒），设为 0 时不自动关闭 */
    duration?: number;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    type: "info",
    duration: 3000
});

const emit = defineEmits<{
    /** 消息关闭时触发 */
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

// 定时器
let timer: ReturnType<typeof setTimeout> | null = null;

// 关闭消息
const close = () => {
    if (closing.value) return;
    closing.value = true;

    // 动画结束后通知父组件
    setTimeout(() => {
        emit("close", props.id);
    }, 300);
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
    <div :class="['vort-message-item', `vort-message-${type}`, { 'is-visible': visible, 'is-closing': closing }, props.class]">
        <!-- 图标 -->
        <span class="vort-message-icon">
            <component :is="IconComponent" :class="{ 'is-spinning': type === 'loading' }" />
        </span>

        <!-- 内容 -->
        <span class="vort-message-content">{{ content }}</span>
    </div>
</template>

<style scoped>
.vort-message-item {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    margin: 8px 0;
    background: #fff;
    border-radius: var(--vort-border-radius-lg, 8px);
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
    font-size: 14px;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
    pointer-events: all;
    /* 初始状态 */
    opacity: 0;
    transform: translateY(-16px);
    transition: all 0.3s cubic-bezier(0.08, 0.82, 0.17, 1);
}

/* 进入动画 */
.vort-message-item.is-visible {
    opacity: 1;
    transform: translateY(0);
}

/* 离开动画 */
.vort-message-item.is-closing {
    opacity: 0;
    transform: translateY(-8px);
}

/* 图标 */
.vort-message-icon {
    flex-shrink: 0;
    line-height: 1;
    font-size: 16px;
}

.vort-message-icon :deep(svg) {
    width: 1em;
    height: 1em;
}

/* 图标颜色 */
.vort-message-success .vort-message-icon {
    color: var(--vort-success);
}

.vort-message-info .vort-message-icon {
    color: var(--vort-primary);
}

.vort-message-warning .vort-message-icon {
    color: var(--vort-warning);
}

.vort-message-error .vort-message-icon {
    color: var(--vort-error);
}

.vort-message-loading .vort-message-icon {
    color: var(--vort-primary);
}

/* Loading 旋转动画 */
.vort-message-icon .is-spinning {
    animation: vort-message-spin 1s linear infinite;
}

@keyframes vort-message-spin {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}

/* 内容 */
.vort-message-content {
    line-height: 1.5;
}
</style>
