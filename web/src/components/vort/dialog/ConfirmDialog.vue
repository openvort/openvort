<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue";
import { InfoCircleFilled, CheckCircleFilled, CloseCircleFilled, ExclamationCircleFilled } from "@/components/vort/icons";
import { Button } from "@/components/vort/button";
import { getVortTeleportTo, useOverlayStack } from "@/components/vort/composables";
import { useLocale } from "@/components/vort/locale/useLocale";

defineOptions({ name: "VortConfirmDialog" });

const { t: modalT } = useLocale("Modal");

/** Vort ConfirmDialog - 确认对话框组件 */

export type ConfirmDialogType = "info" | "success" | "error" | "warning" | "confirm";

interface Props {
    /** 对话框是否可见 */
    open?: boolean;
    /** 对话框类型 */
    type?: ConfirmDialogType;
    /** 标题 */
    title?: string;
    /** 内容 */
    content?: string;
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
    /** 确定按钮 loading */
    confirmLoading?: boolean;
    /** 确定按钮类型 */
    okType?: "primary" | "danger";
    /** z-index */
    zIndex?: number;
    /** 垂直居中展示 */
    centered?: boolean;
    /** 鼠标点击位置（用于动画起点） */
    mousePosition?: { x: number; y: number } | null;
    /** 内容区域背景色（仅 body 区域），默认白色 */
    contentBg?: string;
}

const props = withDefaults(defineProps<Props>(), {
    open: false,
    type: "confirm",
    title: "",
    content: "",
    width: 416,
    closable: false,
    maskClosable: false,
    keyboard: true,
    okText: undefined,
    cancelText: undefined,
    confirmLoading: false,
    okType: "primary",
    zIndex: 1000,
    centered: true,
    mousePosition: null,
    contentBg: "#fff"
});

const resolvedOkText = computed(() => props.okText ?? modalT("ok_text"));
const resolvedCancelText = computed(() => props.cancelText ?? modalT("cancel_text"));

const emit = defineEmits<{
    "update:open": [value: boolean];
    ok: [];
    cancel: [];
    afterClose: [];
}>();

const overlay = useOverlayStack();

// 状态
const visible = ref(false);
const shouldRenderTeleport = ref(false);
const animationState = ref<"" | "enter" | "leave">("");
const dialogRef = ref<HTMLDivElement | null>(null);
const wrapRef = ref<HTMLDivElement | null>(null);
const transformOriginStyle = ref("");
const teleportTo = computed(() => getVortTeleportTo());

// 计算 transform-origin
const setTransformOrigin = () => {
    if (!dialogRef.value || !props.mousePosition) {
        transformOriginStyle.value = "";
        return;
    }

    const dialogNode = dialogRef.value;
    const rect = dialogNode.getBoundingClientRect();

    // 计算点击位置相对于对话框的偏移（都是视口坐标系）
    const left = props.mousePosition.x - rect.left;
    const top = props.mousePosition.y - rect.top;

    transformOriginStyle.value = `${left}px ${top}px`;
};

// 图标组件映射
const iconComponents = {
    info: InfoCircleFilled,
    success: CheckCircleFilled,
    error: CloseCircleFilled,
    warning: ExclamationCircleFilled,
    confirm: ExclamationCircleFilled
};

// 图标颜色映射
const iconColors = {
    info: "var(--vort-primary)",
    success: "#52c41a",
    error: "#ff4d4f",
    warning: "#faad14",
    confirm: "#faad14"
};

// 计算当前图标组件
const IconComponent = computed(() => iconComponents[props.type]);

// 计算当前图标颜色
const iconColor = computed(() => iconColors[props.type]);

// 是否只显示一个按钮（info/success/error/warning 类型）
const isSingleButton = computed(() => ["info", "success", "error", "warning"].includes(props.type));

// 宽度计算
const dialogWidth = computed(() => {
    const { width } = props;
    if (typeof width === "number") {
        return `${width}px`;
    }
    return width;
});

// 关闭对话框
const close = () => {
    emit("update:open", false);
    emit("cancel");
};

// 确定按钮点击
const handleOk = () => {
    emit("ok");
};

// 取消按钮点击
const handleCancel = () => {
    close();
};

// 遮罩点击
const handleWrapClick = (e: MouseEvent) => {
    if (e.target === wrapRef.value && props.maskClosable) {
        close();
    }
};

// 动画结束回调
const handleAnimationEnd = () => {
    if (animationState.value === "leave") {
        visible.value = false;
        animationState.value = "";
        document.body.style.overflow = "";
        shouldRenderTeleport.value = false;
        emit("afterClose");
    } else if (animationState.value === "enter") {
        animationState.value = "";
    }
};

// 监听 open 属性变化
watch(
    () => props.open,
    async (newVal, oldVal) => {
        if (newVal) {
            shouldRenderTeleport.value = true;
            visible.value = true;
            document.body.style.overflow = "hidden";

            overlay.push(() => {
                if (props.keyboard) close();
            });

            await nextTick();

            // 等待浏览器渲染完成后再计算位置和触发动画
            requestAnimationFrame(() => {
                // 设置 transform-origin
                setTransformOrigin();
                // 触发进入动画
                animationState.value = "enter";
            });
        } else if (oldVal && !newVal) {
            overlay.pop();
            animationState.value = "leave";
        }
    },
    { immediate: true }
);

onUnmounted(() => {
    overlay.pop();
    document.body.style.overflow = "";
});
</script>

<template>
    <Teleport v-if="shouldRenderTeleport" :to="teleportTo">
        <div v-if="visible" class="vort-confirm-dialog-root" :style="{ zIndex }">
            <!-- 遮罩层 -->
            <Transition name="vort-mask">
                <div v-show="open" class="vort-confirm-dialog-mask" />
            </Transition>

            <!-- 对话框容器 -->
            <div ref="wrapRef" class="vort-confirm-dialog-wrap" :class="{ 'vort-confirm-dialog-centered': centered }" @click="handleWrapClick">
                <!-- 对话框主体 -->
                <div
                    ref="dialogRef"
                    class="vort-confirm-dialog"
                    :style="{
                        width: dialogWidth,
                        transformOrigin: transformOriginStyle || undefined
                    }"
                    :data-state="animationState"
                    role="dialog"
                    aria-modal="true"
                    @animationend="handleAnimationEnd"
                >
                    <!-- 关闭按钮 -->
                    <button v-if="closable" class="vort-confirm-dialog-close" type="button" :aria-label="modalT('close')" @click="close">
                        <svg class="vort-confirm-dialog-close-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M18 6L6 18M6 6l12 12" />
                        </svg>
                    </button>

                    <!-- 内容区域 -->
                    <div class="vort-confirm-dialog-body" :style="{ background: contentBg }">
                        <!-- 图标 -->
                        <span class="vort-confirm-dialog-icon" :style="{ color: iconColor }">
                            <component :is="IconComponent" />
                        </span>

                        <!-- 文本内容 -->
                        <div class="vort-confirm-dialog-content">
                            <span v-if="title" class="vort-confirm-dialog-title">{{ title }}</span>
                            <div v-if="content" class="vort-confirm-dialog-message">{{ content }}</div>
                        </div>
                    </div>

                    <!-- 底部按钮区 -->
                    <div class="vort-confirm-dialog-footer">
                        <Button v-if="!isSingleButton" @click="handleCancel">
                            {{ resolvedCancelText }}
                        </Button>
                        <Button
                            :variant="okType === 'danger' ? undefined : 'primary'"
                            :danger="okType === 'danger'"
                            :loading="confirmLoading"
                            @click="handleOk"
                        >
                            {{ isSingleButton ? modalT("got_it") : resolvedOkText }}
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    </Teleport>
</template>

<style scoped>
.vort-confirm-dialog-root {
    position: fixed;
    inset: 0;
}

/* 遮罩层 */
.vort-confirm-dialog-mask {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 0;
}

/* 遮罩动画 */
.vort-mask-enter-active,
.vort-mask-leave-active {
    transition: opacity 0.3s;
}

.vort-mask-enter-from,
.vort-mask-leave-to {
    opacity: 0;
}

/* 对话框容器 */
.vort-confirm-dialog-wrap {
    position: fixed;
    inset: 0;
    overflow: auto;
    outline: 0;
    z-index: 1;
}

/* 居中模式 */
.vort-confirm-dialog-centered {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100%;
    padding: 16px;
}

/* 对话框主体 */
.vort-confirm-dialog {
    position: relative;
    background: #fff;
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px));
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
    pointer-events: auto;
    max-width: calc(100vw - 32px);
}

.vort-confirm-dialog-centered .vort-confirm-dialog {
    margin: 0;
}

/* 缩放动画 */
.vort-confirm-dialog[data-state="enter"] {
    animation: vortConfirmDialogZoomIn 0.3s cubic-bezier(0.08, 0.82, 0.17, 1) forwards;
}

.vort-confirm-dialog[data-state="leave"] {
    animation: vortConfirmDialogZoomOut 0.2s cubic-bezier(0.78, 0.14, 0.15, 0.86) forwards;
}

@keyframes vortConfirmDialogZoomIn {
    0% {
        opacity: 0;
        transform: scale(0.2);
    }

    100% {
        opacity: 1;
        transform: scale(1);
    }
}

@keyframes vortConfirmDialogZoomOut {
    0% {
        opacity: 1;
        transform: scale(1);
    }

    100% {
        opacity: 0;
        transform: scale(0.2);
    }
}

/* 关闭按钮 */
.vort-confirm-dialog-close {
    position: absolute;
    top: 16px;
    right: 16px;
    z-index: 10;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: var(--vort-border-radius-sm, 4px);
    color: rgba(0, 0, 0, 0.45);
    cursor: pointer;
}

.vort-confirm-dialog-close-icon {
    width: 16px;
    height: 16px;
    transition: all 0.2s;
}

.vort-confirm-dialog-close:hover {
    color: rgba(0, 0, 0, 0.88);
    background: rgba(0, 0, 0, 0.06);
}

.vort-confirm-dialog-close:active {
    background: rgba(0, 0, 0, 0.1);
}

/* 内容区域 */
.vort-confirm-dialog-body {
    display: flex;
    padding: 32px 32px 24px;
    border-top-left-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px));
    border-top-right-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px));
}

/* 图标 */
.vort-confirm-dialog-icon {
    flex-shrink: 0;
    margin-right: 16px;
    font-size: 22px;
    line-height: 1;
}

.vort-confirm-dialog-icon :deep(svg) {
    width: 22px;
    height: 22px;
}

/* 文本内容 */
.vort-confirm-dialog-content {
    flex: 1;
    min-width: 0;
}

.vort-confirm-dialog-title {
    display: block;
    font-size: 16px;
    font-weight: 600;
    color: rgba(0, 0, 0, 0.88);
    line-height: 1.5;
    word-wrap: break-word;
}

.vort-confirm-dialog-message {
    margin-top: 8px;
    font-size: 14px;
    color: rgba(0, 0, 0, 0.65);
    line-height: 1.5714;
    word-wrap: break-word;
}

/* 底部按钮区 */
.vort-confirm-dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 0 32px 24px;
    margin-top: 0;
}
</style>
