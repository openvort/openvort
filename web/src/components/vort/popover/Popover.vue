<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from "vue";
import { getVortPopupContainer, type FloatingPlacement, type FloatingTrigger, useZIndex } from "@/components/vort/composables";

defineOptions({ name: "VortPopover" });

// 使用 z-index 上下文，在 Dialog/Drawer 内时自动获得更高的层级
const zIndex = useZIndex("popover");

/** Vort Popover - 气泡卡片组件 */

interface Props {
    /** 卡片标题 */
    title?: string;
    /** 卡片内容 */
    content?: string;
    /** 气泡框位置 */
    placement?: FloatingPlacement;
    /** 触发方式 */
    trigger?: FloatingTrigger;
    /** 是否显示箭头 */
    arrow?: boolean;
    /** 控制浮层显示（受控模式） */
    open?: boolean;
    /** 是否禁用 */
    disabled?: boolean;
    /** 鼠标移入后延时多少才显示 (ms)，trigger="hover" 时有效 */
    mouseEnterDelay?: number;
    /** 鼠标移出后延时多少才隐藏 (ms)，trigger="hover" 时有效 */
    mouseLeaveDelay?: number;
    /** 菜单渲染父节点。默认渲染到 body 上，如果你遇到菜单滚动定位问题，试试修改为滚动的区域，并相对其定位 */
    getPopupContainer?: () => HTMLElement;
    /** 浮层额外类名 */
    overlayClass?: string;
    /** 浮层额外样式 */
    overlayStyle?: Record<string, string>;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    title: "",
    content: "",
    placement: "top",
    trigger: "hover",
    arrow: true,
    disabled: false,
    mouseEnterDelay: 100,
    mouseLeaveDelay: 100
});

const emit = defineEmits<{
    openChange: [open: boolean];
    "update:open": [open: boolean];
}>();

// 状态
const visible = ref(false);
const shouldRenderTeleport = ref(false); // 控制 Teleport 是否渲染，避免产生 <!--v-if--> 注释
const triggerRef = ref<HTMLElement | null>(null);
const floatingRef = ref<HTMLElement | null>(null);
const position = ref({ top: 0, left: 0 });
const arrowPosition = ref({ top: "", left: "", right: "", bottom: "" });
const actualPlacement = ref<FloatingPlacement>(props.placement);
const popupContainer = computed(() => props.getPopupContainer?.() ?? getVortPopupContainer());

// hover 延迟定时器
let enterTimer: ReturnType<typeof setTimeout> | null = null;
let leaveTimer: ReturnType<typeof setTimeout> | null = null;
let resizeObserver: ResizeObserver | null = null;

// 防止刚打开时被同一个点击事件关闭
let canCloseByClickOutside = true;

// 同步外部 open 状态
watch(
    () => props.open,
    (val) => {
        if (val !== undefined) {
            if (val) {
                shouldRenderTeleport.value = true;
            }
            visible.value = val;
            if (val) {
                // 防止同一个点击事件触发 clickOutside
                canCloseByClickOutside = false;
                nextTick(() => {
                    updatePosition();
                    setTimeout(() => {
                        canCloseByClickOutside = true;
                    }, 0);
                });
            }
        }
    },
    { immediate: true }
);

// 计算位置
const updatePosition = async () => {
    await nextTick();
    if (!triggerRef.value || !floatingRef.value) return;

    const triggerRect = triggerRef.value.getBoundingClientRect();
    const floatingWidth = floatingRef.value.offsetWidth;
    const floatingHeight = floatingRef.value.offsetHeight;
    const gap = 8;
    const arrowHeight = 6;
    const totalGap = gap + arrowHeight;

    // 判断是否使用自定义容器
    const container = popupContainer.value;
    const useCustomContainer = container && container !== document.body;

    let scrollTop = 0;
    let scrollLeft = 0;
    let containerRect: DOMRect | null = null;

    if (useCustomContainer) {
        containerRect = container.getBoundingClientRect();
        scrollTop = container.scrollTop;
        scrollLeft = container.scrollLeft;
    } else {
        scrollTop = window.scrollY;
        scrollLeft = window.scrollX;
    }

    let top = 0;
    let left = 0;
    let placement = props.placement;

    // 根据 placement 计算位置
    const calcPosition = (p: FloatingPlacement) => {
        let t = 0;
        let l = 0;

        if (useCustomContainer && containerRect) {
            const offsetTop = triggerRect.top - containerRect.top + scrollTop;
            const offsetLeft = triggerRect.left - containerRect.left + scrollLeft;

            switch (p) {
                case "top":
                    t = offsetTop - floatingHeight - totalGap;
                    l = offsetLeft + (triggerRect.width - floatingWidth) / 2;
                    break;
                case "topLeft":
                    t = offsetTop - floatingHeight - totalGap;
                    l = offsetLeft;
                    break;
                case "topRight":
                    t = offsetTop - floatingHeight - totalGap;
                    l = offsetLeft + triggerRect.width - floatingWidth;
                    break;
                case "bottom":
                    t = offsetTop + triggerRect.height + totalGap;
                    l = offsetLeft + (triggerRect.width - floatingWidth) / 2;
                    break;
                case "bottomLeft":
                    t = offsetTop + triggerRect.height + totalGap;
                    l = offsetLeft;
                    break;
                case "bottomRight":
                    t = offsetTop + triggerRect.height + totalGap;
                    l = offsetLeft + triggerRect.width - floatingWidth;
                    break;
                case "left":
                    t = offsetTop + (triggerRect.height - floatingHeight) / 2;
                    l = offsetLeft - floatingWidth - totalGap;
                    break;
                case "leftTop":
                    t = offsetTop;
                    l = offsetLeft - floatingWidth - totalGap;
                    break;
                case "leftBottom":
                    t = offsetTop + triggerRect.height - floatingHeight;
                    l = offsetLeft - floatingWidth - totalGap;
                    break;
                case "right":
                    t = offsetTop + (triggerRect.height - floatingHeight) / 2;
                    l = offsetLeft + triggerRect.width + totalGap;
                    break;
                case "rightTop":
                    t = offsetTop;
                    l = offsetLeft + triggerRect.width + totalGap;
                    break;
                case "rightBottom":
                    t = offsetTop + triggerRect.height - floatingHeight;
                    l = offsetLeft + triggerRect.width + totalGap;
                    break;
            }
        } else {
            switch (p) {
                case "top":
                    t = triggerRect.top - floatingHeight - totalGap;
                    l = triggerRect.left + (triggerRect.width - floatingWidth) / 2;
                    break;
                case "topLeft":
                    t = triggerRect.top - floatingHeight - totalGap;
                    l = triggerRect.left;
                    break;
                case "topRight":
                    t = triggerRect.top - floatingHeight - totalGap;
                    l = triggerRect.right - floatingWidth;
                    break;
                case "bottom":
                    t = triggerRect.bottom + totalGap;
                    l = triggerRect.left + (triggerRect.width - floatingWidth) / 2;
                    break;
                case "bottomLeft":
                    t = triggerRect.bottom + totalGap;
                    l = triggerRect.left;
                    break;
                case "bottomRight":
                    t = triggerRect.bottom + totalGap;
                    l = triggerRect.right - floatingWidth;
                    break;
                case "left":
                    t = triggerRect.top + (triggerRect.height - floatingHeight) / 2;
                    l = triggerRect.left - floatingWidth - totalGap;
                    break;
                case "leftTop":
                    t = triggerRect.top;
                    l = triggerRect.left - floatingWidth - totalGap;
                    break;
                case "leftBottom":
                    t = triggerRect.bottom - floatingHeight;
                    l = triggerRect.left - floatingWidth - totalGap;
                    break;
                case "right":
                    t = triggerRect.top + (triggerRect.height - floatingHeight) / 2;
                    l = triggerRect.right + totalGap;
                    break;
                case "rightTop":
                    t = triggerRect.top;
                    l = triggerRect.right + totalGap;
                    break;
                case "rightBottom":
                    t = triggerRect.bottom - floatingHeight;
                    l = triggerRect.right + totalGap;
                    break;
            }
        }

        return { top: t, left: l };
    };

    // 计算初始位置
    const pos = calcPosition(placement);
    top = pos.top;
    left = pos.left;

    // 边界检测和自动翻转
    if (useCustomContainer && containerRect) {
        const containerWidth = container!.clientWidth;
        const containerHeight = container!.clientHeight;

        if (placement.startsWith("top") && top < scrollTop) {
            placement = placement.replace("top", "bottom") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        } else if (placement.startsWith("bottom") && top + floatingHeight > scrollTop + containerHeight) {
            placement = placement.replace("bottom", "top") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        } else if (placement.startsWith("left") && left < scrollLeft) {
            placement = placement.replace("left", "right") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        } else if (placement.startsWith("right") && left + floatingWidth > scrollLeft + containerWidth) {
            placement = placement.replace("right", "left") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        }

        left = Math.max(scrollLeft + 8, Math.min(left, scrollLeft + containerWidth - floatingWidth - 8));
    } else {
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        if (placement.startsWith("top") && triggerRect.top - floatingHeight - totalGap < 0) {
            placement = placement.replace("top", "bottom") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        } else if (placement.startsWith("bottom") && triggerRect.bottom + floatingHeight + totalGap > viewportHeight) {
            placement = placement.replace("bottom", "top") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        } else if (placement.startsWith("left") && triggerRect.left - floatingWidth - totalGap < 0) {
            placement = placement.replace("left", "right") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        } else if (placement.startsWith("right") && triggerRect.right + floatingWidth + totalGap > viewportWidth) {
            placement = placement.replace("right", "left") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        }

        left = Math.max(8, Math.min(left, viewportWidth - floatingWidth - 8));
    }

    actualPlacement.value = placement;
    position.value = { top, left };

    // 更新箭头位置
    updateArrowPosition(placement, triggerRect, floatingWidth, floatingHeight);
};

// 更新箭头位置
const updateArrowPosition = (placement: FloatingPlacement, triggerRect: DOMRect, floatingWidth: number, floatingHeight: number) => {
    const arrowOffset = 6;
    const reset = { top: "", left: "", right: "", bottom: "" };

    const getHorizontalOffset = () => Math.min(Math.max(triggerRect.width / 2, 16), floatingWidth - 16);
    const getVerticalOffset = () => Math.min(Math.max(triggerRect.height / 2, 16), floatingHeight - 16);

    if (placement.startsWith("top")) {
        arrowPosition.value = {
            ...reset,
            bottom: `-${arrowOffset}px`,
            left: placement === "top" ? "50%" : placement === "topLeft" ? `${getHorizontalOffset()}px` : `${floatingWidth - getHorizontalOffset()}px`
        };
    } else if (placement.startsWith("bottom")) {
        arrowPosition.value = {
            ...reset,
            top: `-${arrowOffset}px`,
            left: placement === "bottom" ? "50%" : placement === "bottomLeft" ? `${getHorizontalOffset()}px` : `${floatingWidth - getHorizontalOffset()}px`
        };
    } else if (placement.startsWith("left")) {
        arrowPosition.value = {
            ...reset,
            right: `-${arrowOffset}px`,
            top: placement === "left" ? "50%" : placement === "leftTop" ? `${getVerticalOffset()}px` : `${floatingHeight - getVerticalOffset()}px`
        };
    } else if (placement.startsWith("right")) {
        arrowPosition.value = {
            ...reset,
            left: `-${arrowOffset}px`,
            top: placement === "right" ? "50%" : placement === "rightTop" ? `${getVerticalOffset()}px` : `${floatingHeight - getVerticalOffset()}px`
        };
    }
};

// 箭头方向 class
const arrowDirectionClass = computed(() => {
    const p = actualPlacement.value;
    if (p.startsWith("top")) return "arrow-bottom";
    if (p.startsWith("bottom")) return "arrow-top";
    if (p.startsWith("left")) return "arrow-right";
    if (p.startsWith("right")) return "arrow-left";
    return "";
});

// 动画 transform-origin
const transformOrigin = computed(() => {
    const p = actualPlacement.value;
    if (p === "top") return "center bottom";
    if (p === "topLeft") return "left bottom";
    if (p === "topRight") return "right bottom";
    if (p === "bottom") return "center top";
    if (p === "bottomLeft") return "left top";
    if (p === "bottomRight") return "right top";
    if (p === "left") return "right center";
    if (p === "leftTop") return "right top";
    if (p === "leftBottom") return "right bottom";
    if (p === "right") return "left center";
    if (p === "rightTop") return "left top";
    if (p === "rightBottom") return "left bottom";
    return "center center";
});

// 打开/关闭
const show = () => {
    if (props.disabled) return;
    shouldRenderTeleport.value = true; // 先渲染 Teleport
    visible.value = true;
    emit("update:open", true);
    emit("openChange", true);
    // 防止同一个点击事件触发 clickOutside
    canCloseByClickOutside = false;
    nextTick(() => {
        updatePosition();
        // 下一个宏任务才允许点击外部关闭
        setTimeout(() => {
            canCloseByClickOutside = true;
        }, 0);
    });
};

const hide = () => {
    visible.value = false;
    emit("update:open", false);
    emit("openChange", false);
};

// Transition 离开动画完成后移除 Teleport
const handleAfterLeave = () => {
    shouldRenderTeleport.value = false;
};

const toggle = () => {
    if (visible.value) {
        hide();
    } else {
        show();
    }
};

// 清除定时器
const clearTimers = () => {
    if (enterTimer) {
        clearTimeout(enterTimer);
        enterTimer = null;
    }
    if (leaveTimer) {
        clearTimeout(leaveTimer);
        leaveTimer = null;
    }
};

// 监听浮层尺寸变化（例如图片异步加载）后自动重算位置
const stopResizeObserver = () => {
    if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
    }
};

const setupResizeObserver = () => {
    if (typeof window === "undefined" || typeof ResizeObserver === "undefined") return;
    if (!floatingRef.value) return;

    stopResizeObserver();

    resizeObserver = new ResizeObserver(() => {
        if (visible.value) {
            updatePosition();
        }
    });

    resizeObserver.observe(floatingRef.value);
};

// 事件处理
const handleTriggerClick = () => {
    if (props.trigger === "click") {
        toggle();
    }
};

const handleTriggerMouseEnter = () => {
    if (props.trigger !== "hover") return;
    clearTimers();
    enterTimer = setTimeout(show, props.mouseEnterDelay);
};

const handleTriggerMouseLeave = () => {
    if (props.trigger !== "hover") return;
    clearTimers();
    leaveTimer = setTimeout(hide, props.mouseLeaveDelay);
};

const handleTriggerFocus = () => {
    if (props.trigger === "focus") {
        show();
    }
};

const handleTriggerBlur = () => {
    if (props.trigger === "focus") {
        hide();
    }
};

const handleTriggerContextMenu = (e: MouseEvent) => {
    if (props.trigger === "contextMenu") {
        e.preventDefault();
        toggle();
    }
};

const handleFloatingMouseEnter = () => {
    if (props.trigger !== "hover") return;
    clearTimers();
};

const handleFloatingMouseLeave = () => {
    if (props.trigger !== "hover") return;
    clearTimers();
    leaveTimer = setTimeout(hide, props.mouseLeaveDelay);
};

// 点击外部关闭
const handleClickOutside = (e: MouseEvent) => {
    if (!visible.value) return;
    if (!canCloseByClickOutside) return;
    if (props.trigger !== "click" && props.trigger !== "contextMenu") return;

    const target = e.target as Node;
    if (triggerRef.value?.contains(target) || floatingRef.value?.contains(target)) {
        return;
    }
    hide();
};

// 滚动/resize 时更新位置
const handleScroll = () => {
    if (visible.value) {
        updatePosition();
    }
};

onMounted(() => {
    document.addEventListener("click", handleClickOutside);
    window.addEventListener("scroll", handleScroll, true);
    window.addEventListener("resize", handleScroll);
});

onUnmounted(() => {
    document.removeEventListener("click", handleClickOutside);
    window.removeEventListener("scroll", handleScroll, true);
    window.removeEventListener("resize", handleScroll);
    clearTimers();
    stopResizeObserver();
});

watch(visible, async (val) => {
    if (val) {
        await nextTick();
        setupResizeObserver();
    } else {
        stopResizeObserver();
    }
});

// 浮层样式
const floatingStyle = computed(() => ({
    top: `${position.value.top}px`,
    left: `${position.value.left}px`,
    zIndex: zIndex.value,
    "--transform-origin": transformOrigin.value,
    ...props.overlayStyle
}));

// 暴露方法供外部调用
defineExpose({
    show,
    hide
});
</script>

<template>
    <span
        ref="triggerRef"
        class="vort-popover-trigger"
        @click="handleTriggerClick"
        @mouseenter="handleTriggerMouseEnter"
        @mouseleave="handleTriggerMouseLeave"
        @focus="handleTriggerFocus"
        @blur="handleTriggerBlur"
        @contextmenu="handleTriggerContextMenu"
    >
        <slot />
    </span>

    <Teleport v-if="shouldRenderTeleport" :to="popupContainer">
        <Transition name="vort-popover" appear @after-leave="handleAfterLeave">
            <div
                v-if="visible"
                ref="floatingRef"
                :class="['vort-popover', props.overlayClass]"
                :style="floatingStyle"
                @mouseenter="handleFloatingMouseEnter"
                @mouseleave="handleFloatingMouseLeave"
            >
                <!-- 箭头 -->
                <div
                    v-if="arrow"
                    class="vort-popover-arrow"
                    :class="arrowDirectionClass"
                    :style="{
                        top: arrowPosition.top || undefined,
                        bottom: arrowPosition.bottom || undefined,
                        left: arrowPosition.left || undefined,
                        right: arrowPosition.right || undefined
                    }"
                />

                <!-- 内容 -->
                <div class="vort-popover-inner">
                    <!-- 标题 -->
                    <div v-if="title || $slots.title" class="vort-popover-title">
                        <slot name="title">{{ title }}</slot>
                    </div>

                    <!-- 内容 -->
                    <div class="vort-popover-content">
                        <slot name="content">{{ content }}</slot>
                    </div>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>

<style scoped>
.vort-popover-trigger {
    display: inline-flex;
}

.vort-popover {
    position: absolute;
    max-width: 320px;
    padding: 12px;
    background: #fff;
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px));
    pointer-events: auto;
    min-height: 32px;
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
    overflow: visible;
}

/* 渲染到 body 时使用 fixed 定位 */
body > .vort-popover {
    position: fixed;
}

/* 动画 - 参考 Ant Design zoom-big */
.vort-popover-enter-active {
    animation: vortPopoverIn 0.2s cubic-bezier(0.08, 0.82, 0.17, 1);
    transform-origin: var(--transform-origin, center);
}

.vort-popover-leave-active {
    animation: vortPopoverOut 0.2s cubic-bezier(0.78, 0.14, 0.15, 0.86);
    transform-origin: var(--transform-origin, center);
}

@keyframes vortPopoverIn {
    0% {
        opacity: 0;
        transform: scale(0.8);
    }

    100% {
        opacity: 1;
        transform: scale(1);
    }
}

@keyframes vortPopoverOut {
    0% {
        opacity: 1;
        transform: scale(1);
    }

    100% {
        opacity: 0;
        transform: scale(0.8);
    }
}

/* 箭头 - 使用旋转正方形实现（参考 Ant Design） */
.vort-popover-arrow {
    position: absolute;
    z-index: 1;
    display: block;
    pointer-events: none;
    width: 16px;
    height: 8px;
}

.vort-popover-arrow::before {
    content: "";
    position: absolute;
    width: 8px;
    height: 8px;
    background: #fff;
    pointer-events: none;
    z-index: 1;
    border-radius: 0 0 2px 0;
}

/* 箭头在底部（弹窗在上方时） - 三角形指向下方 */
.vort-popover-arrow.arrow-bottom {
    transform: translateX(-50%);
    height: 8px;
}

.vort-popover-arrow.arrow-bottom::before {
    left: 50%;
    top: -2px;
    transform: translateX(-50%) rotate(45deg);
}

/* 箭头在顶部（弹窗在下方时） - 三角形指向上方 */
.vort-popover-arrow.arrow-top {
    transform: translateX(-50%);
    height: 8px;
}

.vort-popover-arrow.arrow-top::before {
    left: 50%;
    bottom: -2px;
    transform: translateX(-50%) rotate(-135deg);
}

/* 箭头在右侧（弹窗在左方时） - 三角形指向右方 */
.vort-popover-arrow.arrow-right {
    transform: translateY(-50%);
    width: 8px;
    height: 16px;
}

.vort-popover-arrow.arrow-right::before {
    top: 50%;
    left: -2px;
    transform: translateY(-50%) rotate(-45deg);
}

/* 箭头在左侧（弹窗在右方时） - 三角形指向左方 */
.vort-popover-arrow.arrow-left {
    transform: translateY(-50%);
    width: 8px;
    height: 16px;
}

.vort-popover-arrow.arrow-left::before {
    top: 50%;
    right: -2px;
    transform: translateY(-50%) rotate(135deg);
}

/* 内容 */
.vort-popover-inner {
    display: flex;
    flex-direction: column;
}

.vort-popover-title {
    font-size: 14px;
    font-weight: 600;
    color: rgba(0, 0, 0, 0.88);
    line-height: 1.5;
    margin-bottom: 8px;
    min-width: 176px;
}

.vort-popover-content {
    font-size: 14px;
    color: rgba(0, 0, 0, 0.88);
    line-height: 1.5;
}

/* 无标题时移除标题底部间距 */
.vort-popover-inner > .vort-popover-content:first-child {
    margin-top: 0;
}
</style>
