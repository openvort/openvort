<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue";
import { X } from "lucide-vue-next";
import { getVortTeleportTo, useZIndexProviderValue } from "@/components/vort/composables";
import { Button } from "@/components/vort/button";
import { useLocale } from "../locale";

defineOptions({ name: "VortDialog" });

/** Vort Dialog - 对话框组件 */

type DialogWidth = "small" | "default" | "large" | number | string;

interface Props {
    /** 对话框是否可见（v-model） */
    open?: boolean;
    /** 标题 */
    title?: string;
    /** 对话框宽度 */
    width?: DialogWidth;
    /** 是否显示右上角关闭按钮 */
    closable?: boolean;
    /** 点击蒙层是否允许关闭 */
    maskClosable?: boolean;
    /** 是否支持键盘 ESC 关闭 */
    keyboard?: boolean;
    /** 是否显示遮罩 */
    mask?: boolean;
    /** 垂直居中展示 */
    centered?: boolean;
    /** 确定按钮文字 */
    okText?: string;
    /** 取消按钮文字 */
    cancelText?: string;
    /** 确定按钮 loading */
    confirmLoading?: boolean;
    /** 是否显示底部按钮区域 */
    footer?: boolean;
    /** z-index */
    zIndex?: number;
    /** 自定义类名 */
    class?: string;
    /** 对话框外层容器类名 */
    wrapClass?: string;
    /** body 区域是否无内边距 */
    bodyNoPadding?: boolean;
    /** 内容区域背景色（仅 body 区域），默认白色 */
    contentBg?: string;
}

const props = withDefaults(defineProps<Props>(), {
    open: false,
    title: "",
    width: "default",
    closable: true,
    maskClosable: true,
    keyboard: true,
    mask: true,
    centered: false,
    okText: undefined,
    cancelText: undefined,
    confirmLoading: false,
    footer: true,
    zIndex: 1000,
    bodyNoPadding: false,
    contentBg: "#fff"
});

// 国际化
const { t } = useLocale("Modal");
const okTextValue = computed(() => props.okText ?? t("ok_text"));
const cancelTextValue = computed(() => props.cancelText ?? t("cancel_text"));

// 提供 z-index 上下文给子组件（如 Select、Dropdown 等）
// 这样子组件的弹出层会自动获得比 Dialog 更高的 z-index
useZIndexProviderValue(() => props.zIndex);

const emit = defineEmits<{
    "update:open": [value: boolean];
    ok: [];
    cancel: [];
    afterClose: [];
}>();

// 状态
const visible = ref(false);
const shouldRenderTeleport = ref(false); // 控制 Teleport 是否渲染，避免产生 <!--v-if--> 注释
const animationState = ref<"" | "enter" | "leave">("");
const dialogRef = ref<HTMLDivElement | null>(null);
const wrapRef = ref<HTMLDivElement | null>(null);
const transformOriginStyle = ref("");
const teleportTo = computed(() => getVortTeleportTo());

// 全局鼠标位置追踪（使用视口坐标 clientX/clientY）
let mousePosition: { x: number; y: number } | null = null;

// 获取点击位置
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

// 只在 document 上监听 click 获取位置
if (typeof window !== "undefined") {
    document.documentElement.addEventListener("click", getClickPosition, true);
}

// 计算 transform-origin
const setTransformOrigin = () => {
    if (!dialogRef.value || !mousePosition) {
        transformOriginStyle.value = "";
        return;
    }

    const dialogNode = dialogRef.value;
    const rect = dialogNode.getBoundingClientRect();

    // 计算点击位置相对于对话框的偏移（都是视口坐标系）
    const left = mousePosition.x - rect.left;
    const top = mousePosition.y - rect.top;

    transformOriginStyle.value = `${left}px ${top}px`;
};

// 宽度计算
const dialogWidth = computed(() => {
    const { width } = props;
    if (typeof width === "number") {
        return `${width}px`;
    }
    if (width === "small") return "416px";
    if (width === "large") return "800px";
    if (width === "default") return "520px";
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
const handleMaskClick = () => {
    if (props.maskClosable) {
        close();
    }
};

// wrap 点击（点击对话框外部区域）
const handleWrapClick = (e: MouseEvent) => {
    // 只有点击 wrap 本身（不是对话框内部）才关闭
    if (e.target === wrapRef.value && props.maskClosable) {
        close();
    }
};

// ESC 键关闭
const handleKeydown = (e: KeyboardEvent) => {
    if (e.key === "Escape" && props.keyboard && props.open) {
        close();
    }
};

// 动画结束回调
const handleAnimationEnd = () => {
    if (animationState.value === "leave") {
        visible.value = false;
        animationState.value = "";
        document.body.style.overflow = "";
        shouldRenderTeleport.value = false; // 动画结束后移除 Teleport
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
            // 打开对话框
            shouldRenderTeleport.value = true; // 先渲染 Teleport
            visible.value = true;
            document.body.style.overflow = "hidden";

            await nextTick();

            // 等待浏览器渲染完成后再计算位置和触发动画
            requestAnimationFrame(() => {
                // 设置 transform-origin
                setTransformOrigin();
                // 触发进入动画
                animationState.value = "enter";
            });
        } else if (oldVal && !newVal) {
            // 关闭对话框 - 触发离开动画
            animationState.value = "leave";
        }
    },
    { immediate: true }
);

onMounted(() => {
    document.addEventListener("keydown", handleKeydown);
});

onUnmounted(() => {
    document.removeEventListener("keydown", handleKeydown);
    document.body.style.overflow = "";
});
</script>

<template>
    <Teleport v-if="shouldRenderTeleport" :to="teleportTo">
        <div v-if="visible" class="vort-dialog-root" :class="wrapClass" :style="{ zIndex }">
            <!-- 遮罩层 -->
            <Transition name="vort-mask">
                <div v-if="mask" v-show="open" class="vort-dialog-mask" @click="handleMaskClick" />
            </Transition>

            <!-- 对话框容器 -->
            <div ref="wrapRef" class="vort-dialog-wrap" :class="{ 'vort-dialog-centered': centered }" @click="handleWrapClick">
                <div
                    ref="dialogRef"
                    :class="['vort-dialog', props.class]"
                    :style="{
                        width: dialogWidth,
                        transformOrigin: transformOriginStyle || undefined
                    }"
                    :data-state="animationState"
                    role="dialog"
                    aria-modal="true"
                    @animationend="handleAnimationEnd"
                >
                    <div class="vort-dialog-content">
                        <!-- 关闭按钮 -->
                        <Button v-if="closable" type="text" icon class="vort-dialog-close" aria-label="关闭" @click="close">
                            <X class="vort-dialog-close-icon" />
                        </Button>

                        <!-- 头部 -->
                        <div v-if="title || $slots.title" class="vort-dialog-header">
                            <slot name="title">
                                <span class="vort-dialog-title">{{ title }}</span>
                            </slot>
                        </div>

                        <!-- 内容区 -->
                        <div class="vort-dialog-body" :class="{ 'vort-dialog-body-no-padding': bodyNoPadding }" :style="{ background: contentBg }">
                            <slot />
                        </div>

                        <!-- 底部按钮区 -->
                        <div v-if="footer" class="vort-dialog-footer">
                            <slot name="footer">
                                <Button @click="handleCancel">{{ cancelTextValue }}</Button>
                                <Button type="primary" :loading="confirmLoading" @click="handleOk">{{ okTextValue }}</Button>
                            </slot>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </Teleport>
</template>

<style scoped>
.vort-dialog-root {
    position: fixed;
    inset: 0;
    z-index: v-bind(zIndex);
}

/* 遮罩层 */
.vort-dialog-mask {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 0;
    pointer-events: auto;
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
.vort-dialog-wrap {
    position: fixed;
    inset: 0;
    overflow: auto;
    outline: 0;
    z-index: 1;
    pointer-events: none;
}

/* 对话框主体 */
.vort-dialog {
    position: relative;
    top: 100px;
    margin: 0 auto;
    pointer-events: auto;
    max-width: calc(100vw - 32px);
}

/* 内容容器（包裹 header/body/footer，统一处理圆角和阴影） */
.vort-dialog-content {
    position: relative;
    background: #fff;
    background-clip: padding-box;
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px));
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
    overflow: hidden;
}

/* 居中模式 */
.vort-dialog-centered {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100%;
    padding: 16px;
}

.vort-dialog-centered .vort-dialog {
    top: 0;
    margin: 0;
}

/* 缩放动画 */
.vort-dialog[data-state="enter"] {
    animation: vortDialogZoomIn 0.3s cubic-bezier(0.08, 0.82, 0.17, 1) forwards;
}

.vort-dialog[data-state="leave"] {
    animation: vortDialogZoomOut 0.2s cubic-bezier(0.78, 0.14, 0.15, 0.86) forwards;
}

@keyframes vortDialogZoomIn {
    0% {
        opacity: 0;
        transform: scale(0.2);
    }

    100% {
        opacity: 1;
        transform: scale(1);
    }
}

@keyframes vortDialogZoomOut {
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
.vort-dialog-close {
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
}

.vort-dialog-close-icon {
    width: 16px;
    height: 16px;
    background: transparent;
    border: none;
    border-radius: var(--vort-border-radius-sm, 4px);
    color: rgba(0, 0, 0, 0.45);
    cursor: pointer;
    transition: all 0.2s;
}

.vort-dialog-close:hover {
    color: rgba(0, 0, 0, 0.88);
    background: rgba(0, 0, 0, 0.06);
}

.vort-dialog-close:active {
    background: rgba(0, 0, 0, 0.1);
}

/* 头部 */
.vort-dialog-header {
    padding: 16px 24px;
    border-bottom: 1px solid rgba(5, 5, 5, 0.06);
}

.vort-dialog-title {
    font-size: 16px;
    font-weight: 600;
    color: rgba(0, 0, 0, 0.88);
    line-height: 1.5;
    word-wrap: break-word;
}

/* 内容区 */
.vort-dialog-body {
    padding: 24px;
    font-size: 14px;
    color: rgba(0, 0, 0, 0.88);
    line-height: 1.5714;
    word-wrap: break-word;
}

.vort-dialog-body-no-padding {
    padding: 0;
}

/* 底部按钮区 */
.vort-dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid rgba(5, 5, 5, 0.06);
}

/* 响应式：小屏幕时对话框宽度 100% */
@media (max-width: 576px) {
    .vort-dialog {
        width: 100% !important;
        max-width: 100%;
        margin: 0;
    }

    .vort-dialog-content {
        border-radius: 0;
    }

    .vort-dialog-wrap:not(.vort-dialog-centered) .vort-dialog {
        top: 0;
        height: 100%;
    }

    .vort-dialog-wrap:not(.vort-dialog-centered) .vort-dialog-content {
        height: 100%;
        display: flex;
        flex-direction: column;
    }

    .vort-dialog-wrap:not(.vort-dialog-centered) .vort-dialog-body {
        flex: 1;
        overflow-y: auto;
    }

    .vort-dialog-centered {
        padding: 0;
    }

    .vort-dialog-centered .vort-dialog {
        height: 100%;
    }

    .vort-dialog-centered .vort-dialog-content {
        height: 100%;
        display: flex;
        flex-direction: column;
    }

    .vort-dialog-centered .vort-dialog-body {
        flex: 1;
        overflow-y: auto;
    }
}
</style>
