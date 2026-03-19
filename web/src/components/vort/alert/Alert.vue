<script setup lang="ts">
import { computed, ref, useSlots, type SlotsType } from "vue";
import { CheckCircleFilled, InfoCircleFilled, ExclamationCircleFilled, CloseCircleFilled, CloseOutlined } from "@/components/vort/icons";

defineOptions({ name: "VortAlert" });

/** Vort Alert - 警告提示组件 */

type AlertType = "success" | "info" | "warning" | "error";

interface Props {
    /** 指定警告提示的样式 */
    type?: AlertType;
    /** 警告提示内容（正文） */
    message?: string;
    /** 警告提示的辅助性文字介绍 */
    description?: string;
    /** 是否显示关闭按钮 */
    closable?: boolean;
    /** 自定义关闭按钮 */
    closeText?: string;
    /** 是否显示辅助图标 */
    showIcon?: boolean;
    /** 是否用作顶部公告 */
    banner?: boolean;
    /** 自定义类名 */
    class?: string;
}

interface AlertProps extends Props {}

const props = withDefaults(defineProps<AlertProps>(), {
    type: "info",
    closable: false,
    showIcon: false,
    banner: false
});

const emit = defineEmits<{
    /** 关闭时触发 */
    close: [e: MouseEvent];
    /** 关闭动画结束后触发 */
    afterClose: [];
}>();

// 定义插槽类型
defineSlots<{
    /** 自定义图标 */
    icon?: () => unknown;
    /** 自定义消息内容 */
    message?: () => unknown;
    /** 自定义描述内容 */
    description?: () => unknown;
    /** 自定义关闭图标 */
    closeIcon?: () => unknown;
    /** 操作区域 */
    action?: () => unknown;
}>();

// 是否可见
const visible = ref(true);

// 图标组件映射
const iconComponents = {
    success: CheckCircleFilled,
    info: InfoCircleFilled,
    warning: ExclamationCircleFilled,
    error: CloseCircleFilled
};

// 当前图标组件
const IconComponent = computed(() => iconComponents[props.type]);

// 是否有描述（检查 prop 和 slot）
const slotApi = useSlots();
const hasDescription = computed((): boolean => !!props.description || typeof slotApi.description === "function");

// 是否显示图标 - banner 模式默认显示
const shouldShowIcon = computed(() => props.showIcon || props.banner);

// ========== 类名计算 ==========

const alertClasses = computed(() => {
    const classes = ["vort-alert", `vort-alert-${props.type}`];
    if (hasDescription.value) classes.push("vort-alert-with-description");
    if (props.banner) classes.push("vort-alert-banner");
    if (props.class) classes.push(props.class);
    return classes;
});

// 处理关闭
const handleClose = (e: MouseEvent) => {
    emit("close", e);
    visible.value = false;
};

// Ant Design 风格动画曲线
const antdEasing = "cubic-bezier(0.645, 0.045, 0.355, 1)";

// 关闭动画钩子 - 参考 Ant Design 实现
const onBeforeLeave = (el: Element) => {
    const element = el as HTMLElement;
    element.style.maxHeight = `${element.offsetHeight}px`;
    element.style.opacity = "1";
};

const onLeave = (el: Element) => {
    const element = el as HTMLElement;
    element.offsetHeight;
    element.style.transition = `max-height 0.3s ${antdEasing}, opacity 0.3s ${antdEasing}, padding 0.3s ${antdEasing}, margin 0.3s ${antdEasing}, border-width 0.3s ${antdEasing}`;
    element.style.overflow = "hidden";
    element.style.maxHeight = "0";
    element.style.opacity = "0";
    element.style.paddingTop = "0";
    element.style.paddingBottom = "0";
    element.style.marginTop = "0";
    element.style.marginBottom = "0";
    element.style.borderTopWidth = "0";
    element.style.borderBottomWidth = "0";
};

const onAfterLeave = () => {
    emit("afterClose");
};
</script>

<template>
    <Transition name="vort-alert" @before-leave="onBeforeLeave" @leave="onLeave" @after-leave="onAfterLeave">
        <div v-if="visible" :class="alertClasses" role="alert">
            <!-- 图标 -->
            <span v-if="shouldShowIcon" class="vort-alert-icon">
                <slot name="icon">
                    <component :is="IconComponent" />
                </slot>
            </span>

            <!-- 内容区域 -->
            <div class="vort-alert-content">
                <!-- 消息 -->
                <div class="vort-alert-message">
                    <slot name="message">{{ message }}</slot>
                </div>

                <!-- 描述 -->
                <div v-if="hasDescription || $slots.description" class="vort-alert-description">
                    <slot name="description">{{ description }}</slot>
                </div>
            </div>

            <!-- 操作区域 -->
            <div v-if="$slots.action" class="vort-alert-action">
                <slot name="action" />
            </div>

            <!-- 关闭按钮 -->
            <button v-if="closable" class="vort-alert-close" @click="handleClose" aria-label="关闭">
                <slot name="closeIcon">
                    <template v-if="closeText">
                        <span class="vort-alert-close-text">{{ closeText }}</span>
                    </template>
                    <template v-else>
                        <CloseOutlined />
                    </template>
                </slot>
            </button>
        </div>
    </Transition>
</template>

<style scoped>
/* ========================================
   基础样式
   ======================================== */
.vort-alert {
    position: relative;
    display: flex;
    align-items: center;
    width: 100%;
    padding: 8px 12px;
    border-radius: var(--vort-radius, 8px);
    border: 1px solid transparent;
    transition: all var(--vort-duration-slow, 300ms);
}

/* 有描述时顶部对齐，增加内边距 */
.vort-alert-with-description {
    align-items: flex-start;
    padding: 20px 24px;
}

/* Banner 模式 */
.vort-alert-banner {
    border-radius: 0;
    border: 0;
    border-bottom: 1px solid transparent;
}

/* ========================================
   类型样式 - Success
   ======================================== */
.vort-alert-success {
    background: var(--vort-success-bg, #f6ffed);
    border-color: var(--vort-success-border, #b7eb8f);
}

.vort-alert-success .vort-alert-icon {
    color: var(--vort-success, #52c41a);
}

/* ========================================
   类型样式 - Info
   ======================================== */
.vort-alert-info {
    background: var(--vort-info-bg, #e6f4ff);
    border-color: var(--vort-info-border, #91caff);
}

.vort-alert-info .vort-alert-icon {
    color: var(--vort-primary, #1456f0);
}

/* ========================================
   类型样式 - Warning
   ======================================== */
.vort-alert-warning {
    background: var(--vort-warning-bg, #fffbe6);
    border-color: var(--vort-warning-border, #ffe58f);
}

.vort-alert-warning .vort-alert-icon {
    color: var(--vort-warning, #faad14);
}

/* ========================================
   类型样式 - Error
   ======================================== */
.vort-alert-error {
    background: var(--vort-error-bg, #fff2f0);
    border-color: var(--vort-error-border, #ffccc7);
}

.vort-alert-error .vort-alert-icon {
    color: var(--vort-error, #ff4d4f);
}

/* ========================================
   图标
   ======================================== */
.vort-alert-icon {
    flex-shrink: 0;
    margin-right: 8px;
    font-size: 14px;
    line-height: 1;
}

.vort-alert-with-description .vort-alert-icon {
    margin-right: 12px;
    font-size: 24px;
}

/* ========================================
   内容区域
   ======================================== */
.vort-alert-content {
    flex: 1;
    min-width: 0;
}

.vort-alert-message {
    font-size: 14px;
    line-height: 1.5714;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

.vort-alert-with-description .vort-alert-message {
    font-size: 16px;
    font-weight: 500;
}

.vort-alert-description {
    margin-top: 8px;
    font-size: 14px;
    line-height: 1.5714;
    color: var(--vort-text-secondary, rgba(0, 0, 0, 0.65));
}

/* ========================================
   操作区域
   ======================================== */
.vort-alert-action {
    flex-shrink: 0;
    margin-left: 16px;
}

/* ========================================
   关闭按钮
   ======================================== */
.vort-alert-close {
    position: absolute;
    top: 12px;
    right: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border: none;
    background: transparent;
    font-size: 14px;
    color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45));
    cursor: pointer;
    transition: color var(--vort-duration-fast, 100ms);
}

.vort-alert-close:hover {
    color: var(--vort-text-secondary, rgba(0, 0, 0, 0.65));
}

.vort-alert-with-description .vort-alert-close {
    top: 16px;
}

.vort-alert-close-text {
    font-size: 14px;
}
</style>
