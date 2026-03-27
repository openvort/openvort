<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick, reactive } from "vue";
import { CloseOutlined } from "@/components/vort/icons";
import { getVortTeleportTo, useZIndexProviderValue, useOverlayStack } from "@/components/vort/composables";
import { useLocale } from "../locale";

defineOptions({ name: "VortDrawer" });

/** Vort Drawer - 抽屉组件 */

type DrawerPlacement = "top" | "right" | "bottom" | "left";

interface Props {
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

const props = withDefaults(defineProps<Props>(), {
    open: false,
    placement: "right",
    width: 378,
    height: 378,
    mask: true,
    maskClosable: true,
    closable: true,
    zIndex: 1000,
    footer: false,
    push: 180,
    keyboard: true,
    destroyOnClose: false,
    contentBg: "#fff"
});

// 提供 z-index 上下文给子组件（如 Select、Dropdown 等）
// 这样子组件的弹出层会自动获得比 Drawer 更高的 z-index
useZIndexProviderValue(() => props.zIndex);

const overlay = useOverlayStack();

// 国际化
const { t } = useLocale("Drawer");

const emit = defineEmits<{
    "update:open": [value: boolean];
    close: [];
    afterOpenChange: [open: boolean];
}>();

// ==================== 全局抽屉栈管理 ====================
// 使用全局响应式对象来管理所有打开的抽屉
interface DrawerInstance {
    id: symbol;
    placement: DrawerPlacement;
    zIndex: number;
    setChildOpen: (hasChild: boolean) => void;
}

// 全局抽屉栈 - 使用 reactive 确保响应性
const globalDrawerStack = reactive<DrawerInstance[]>(
    (window as unknown as { __vortDrawerStack__?: DrawerInstance[] }).__vortDrawerStack__ ||
        ((window as unknown as { __vortDrawerStack__?: DrawerInstance[] }).__vortDrawerStack__ = [])
);

// 当前抽屉实例的唯一标识
const drawerId = Symbol("drawer");

// 是否有子抽屉打开（用于触发偏移动画）
const hasChildOpen = ref(false);

// 设置子抽屉状态的方法
const setChildOpen = (value: boolean) => {
    hasChildOpen.value = value;
};

// 注册到全局栈
const registerToStack = () => {
    // 通知前一个抽屉有新的子抽屉打开
    if (globalDrawerStack.length > 0) {
        const parentDrawer = globalDrawerStack[globalDrawerStack.length - 1];
        parentDrawer?.setChildOpen(true);
    }

    // 注册当前抽屉
    globalDrawerStack.push({
        id: drawerId,
        placement: props.placement,
        zIndex: props.zIndex,
        setChildOpen
    });
};

// 从全局栈移除
const unregisterFromStack = () => {
    const index = globalDrawerStack.findIndex((d) => d.id === drawerId);
    if (index > -1) {
        globalDrawerStack.splice(index, 1);

        // 通知父抽屉子抽屉已关闭
        if (index > 0) {
            const parentDrawer = globalDrawerStack[index - 1];
            // 检查是否还有其他子抽屉
            const hasOtherChild = globalDrawerStack.length > index;
            parentDrawer?.setChildOpen(hasOtherChild);
        }
    }
};

// ==================== 状态管理 ====================
const isVisible = ref(false);
const shouldRenderTeleport = ref(false); // 控制 Teleport 是否渲染，避免产生 <!--v-if--> 注释
const isAnimating = ref(false);
// 控制抽屉面板显示（用于触发进入动画）
const showPanel = ref(false);
const teleportTo = computed(() => getVortTeleportTo());

// 计算尺寸
const sizeValue = computed(() => {
    const isHorizontal = props.placement === "left" || props.placement === "right";
    const size = isHorizontal ? props.width : props.height;
    return typeof size === "number" ? `${size}px` : size;
});

// 计算偏移距离
const pushDistance = computed(() => {
    if (props.push === false) return 0;
    return props.push;
});

// 计算 transform 偏移
const pushTransform = computed(() => {
    if (!hasChildOpen.value || !pushDistance.value) return "";

    switch (props.placement) {
        case "right":
            return `translateX(-${pushDistance.value}px)`;
        case "left":
            return `translateX(${pushDistance.value}px)`;
        case "top":
            return `translateY(${pushDistance.value}px)`;
        case "bottom":
            return `translateY(-${pushDistance.value}px)`;
        default:
            return "";
    }
});

// 计算抽屉样式
const drawerStyle = computed(() => {
    const style: Record<string, string> = {
        zIndex: String(props.zIndex + globalDrawerStack.findIndex((d) => d.id === drawerId))
    };

    // 尺寸
    if (props.placement === "left" || props.placement === "right") {
        style.width = sizeValue.value;
    } else {
        style.height = sizeValue.value;
    }

    // 嵌套偏移
    if (pushTransform.value) {
        style.transform = pushTransform.value;
    }

    return style;
});

// 计算遮罩样式
const maskStyle = computed(() => ({
    zIndex: String(props.zIndex + globalDrawerStack.findIndex((d) => d.id === drawerId) - 1)
}));

// 内容区样式（兼容原有 bodyStyle；bodyStyle 优先级更高）
const drawerBodyStyle = computed(() => ({
    background: props.contentBg,
    ...(props.bodyStyle || {})
}));

// ==================== 事件处理 ====================
// 关闭抽屉
const handleClose = () => {
    emit("update:open", false);
    emit("close");
};

// 点击遮罩
const handleMaskClick = () => {
    if (props.maskClosable) {
        handleClose();
    }
};

// 动画结束回调
const handleAfterEnter = () => {
    isAnimating.value = false;
    emit("afterOpenChange", true);
};

const handleAfterLeave = () => {
    isVisible.value = false;
    isAnimating.value = false;
    shouldRenderTeleport.value = false; // 动画结束后移除 Teleport
    emit("afterOpenChange", false);

    // 如果没有其他抽屉，恢复 body 滚动
    if (globalDrawerStack.length === 0) {
        document.body.style.overflow = "";
    }
};

// ==================== 生命周期 ====================
watch(
    () => props.open,
    async (newVal, oldVal) => {
        if (newVal) {
            // 打开抽屉
            shouldRenderTeleport.value = true; // 先渲染 Teleport
            isVisible.value = true;
            isAnimating.value = true;
            document.body.style.overflow = "hidden";

            // 等待 DOM 更新后再显示面板，确保触发进入动画
            await nextTick();
            requestAnimationFrame(() => {
                showPanel.value = true;
                registerToStack();
                overlay.push(() => {
                    if (props.keyboard) handleClose();
                });
            });
        } else if (oldVal && !newVal) {
            // 关闭抽屉
            isAnimating.value = true;
            showPanel.value = false;
            // 关键：父抽屉可能被业务逻辑“联动关闭”（父先关、子后关）。
            // 此时子抽屉关闭时无法再回调到父抽屉 setChildOpen(false)，会导致父抽屉下次打开仍残留 push 偏移。
            // 在关闭父抽屉时强制清理 hasChildOpen，避免右侧空隙（translateX push）残留。
            hasChildOpen.value = false;
            unregisterFromStack();
            overlay.pop();
        }
    }
);

onMounted(() => {
    if (props.open) {
        shouldRenderTeleport.value = true;
        isVisible.value = true;
        document.body.style.overflow = "hidden";
        requestAnimationFrame(() => {
            showPanel.value = true;
            registerToStack();
            overlay.push(() => {
                if (props.keyboard) handleClose();
            });
        });
    }
});

onUnmounted(() => {
    overlay.pop();
    unregisterFromStack();

    // 恢复滚动
    if (globalDrawerStack.length === 0) {
        document.body.style.overflow = "";
    }
});
</script>

<template>
    <Teleport v-if="shouldRenderTeleport" :to="teleportTo">
        <div v-if="isVisible || (open && !destroyOnClose)" v-show="isVisible" :class="['vort-drawer-root', props.class]">
            <!-- 遮罩 -->
            <Transition name="vort-drawer-mask">
                <div v-if="mask" v-show="showPanel" class="vort-drawer-mask" :style="maskStyle" @click="handleMaskClick" />
            </Transition>

            <!-- 抽屉主体 -->
            <Transition :name="`vort-drawer-panel-${placement}`" @after-enter="handleAfterEnter" @after-leave="handleAfterLeave">
                <div v-show="showPanel" :class="['vort-drawer', `vort-drawer-${placement}`]" :style="drawerStyle" role="dialog" aria-modal="true">
                    <!-- 头部 -->
                    <div v-if="title || closable || $slots.title" class="vort-drawer-header">
                        <div class="vort-drawer-title">
                            <slot name="title">{{ title }}</slot>
                        </div>
                        <button v-if="closable" type="button" class="vort-drawer-close" :aria-label="t('close')" @click="handleClose">
                            <CloseOutlined />
                        </button>
                    </div>

                    <!-- 内容 -->
                    <div class="vort-drawer-body" :style="drawerBodyStyle">
                        <slot />
                    </div>

                    <!-- 底部 -->
                    <div v-if="footer || $slots.footer" class="vort-drawer-footer">
                        <slot name="footer" />
                    </div>
                </div>
            </Transition>
        </div>
    </Teleport>
</template>

<style scoped>
/* 根容器 */
.vort-drawer-root {
    position: fixed;
    inset: 0;
    z-index: 1000;
    pointer-events: none;
}

/* 遮罩 */
.vort-drawer-mask {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    pointer-events: auto;
}

/* 遮罩动画 */
.vort-drawer-mask-enter-active,
.vort-drawer-mask-leave-active {
    transition: opacity 0.3s cubic-bezier(0.7, 0.3, 0.1, 1);
}

.vort-drawer-mask-enter-from,
.vort-drawer-mask-leave-to {
    opacity: 0;
}

/* 抽屉主体 */
.vort-drawer {
    position: fixed;
    background: #fff;
    /* border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px)); */
    box-shadow:
        -6px 0 16px 0 rgba(0, 0, 0, 0.08),
        -3px 0 6px -4px rgba(0, 0, 0, 0.12),
        -9px 0 28px 8px rgba(0, 0, 0, 0.05);
    display: flex;
    flex-direction: column;
    pointer-events: auto;
    /* 嵌套偏移动画 */
    transition: transform 0.3s cubic-bezier(0.7, 0.3, 0.1, 1);
}

/* 方向定位 */
.vort-drawer-right {
    top: 0;
    right: 0;
    bottom: 0;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
}

.vort-drawer-left {
    top: 0;
    left: 0;
    bottom: 0;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    box-shadow:
        6px 0 16px 0 rgba(0, 0, 0, 0.08),
        3px 0 6px -4px rgba(0, 0, 0, 0.12),
        9px 0 28px 8px rgba(0, 0, 0, 0.05);
}

.vort-drawer-top {
    top: 0;
    left: 0;
    right: 0;
    border-top-left-radius: 0;
    border-top-right-radius: 0;
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
}

.vort-drawer-bottom {
    bottom: 0;
    left: 0;
    right: 0;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
    box-shadow:
        0 -6px 16px 0 rgba(0, 0, 0, 0.08),
        0 -3px 6px -4px rgba(0, 0, 0, 0.12),
        0 -9px 28px 8px rgba(0, 0, 0, 0.05);
}

/* 头部 */
.vort-drawer-header {
    flex-shrink: 0;
    padding: 16px 24px;
    border-bottom: 1px solid var(--vort-border-secondary, #f0f0f0);
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.vort-drawer-title {
    flex: 1;
    font-size: 16px;
    font-weight: 600;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
    line-height: 1.5;
}

.vort-drawer-close {
    flex-shrink: 0;
    width: 22px;
    height: 22px;
    padding: 0;
    border: none;
    background: transparent;
    color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45));
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--vort-border-radius-sm, 4px);
    transition: all 0.2s;
    margin-left: 12px;
}

.vort-drawer-close:hover {
    color: var(--vort-text-secondary, rgba(0, 0, 0, 0.65));
    background: rgba(0, 0, 0, 0.06);
}

.vort-drawer-close:active {
    background: rgba(0, 0, 0, 0.1);
}

/* 内容 */
.vort-drawer-body {
    flex: 1;
    padding: 24px;
    overflow-y: auto;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
    font-size: 14px;
    line-height: 1.5714;
}

/* 底部 */
.vort-drawer-footer {
    flex-shrink: 0;
    padding: 10px 16px;
    border-top: 1px solid var(--vort-border-secondary, #f0f0f0);
}

/* ==================== 抽屉滑入/滑出动画 ==================== */
/* Right */
.vort-drawer-panel-right-enter-active,
.vort-drawer-panel-right-leave-active {
    transition: transform 0.3s cubic-bezier(0.7, 0.3, 0.1, 1);
}

.vort-drawer-panel-right-enter-from,
.vort-drawer-panel-right-leave-to {
    transform: translateX(100%) !important;
}

/* Left */
.vort-drawer-panel-left-enter-active,
.vort-drawer-panel-left-leave-active {
    transition: transform 0.3s cubic-bezier(0.7, 0.3, 0.1, 1);
}

.vort-drawer-panel-left-enter-from,
.vort-drawer-panel-left-leave-to {
    transform: translateX(-100%) !important;
}

/* Top */
.vort-drawer-panel-top-enter-active,
.vort-drawer-panel-top-leave-active {
    transition: transform 0.3s cubic-bezier(0.7, 0.3, 0.1, 1);
}

.vort-drawer-panel-top-enter-from,
.vort-drawer-panel-top-leave-to {
    transform: translateY(-100%) !important;
}

/* Bottom */
.vort-drawer-panel-bottom-enter-active,
.vort-drawer-panel-bottom-leave-active {
    transition: transform 0.3s cubic-bezier(0.7, 0.3, 0.1, 1);
}

.vort-drawer-panel-bottom-enter-from,
.vort-drawer-panel-bottom-leave-to {
    transform: translateY(100%) !important;
}

/* 响应式：小屏幕时左右抽屉最大宽度 100% */
@media (max-width: 576px) {
    .vort-drawer-left,
    .vort-drawer-right {
        max-width: 100% !important;
    }
}
</style>
