<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick, useSlots, type Component } from "vue";
import { ExclamationCircleFilled } from "@/components/vort/icons";
import { getVortPopupContainer, type FloatingPlacement, useZIndex } from "@/components/vort/composables";
import { useLocale } from "../locale";

defineOptions({ name: "VortPopconfirm" });

// 使用 z-index 上下文，在 Dialog/Drawer 内时自动获得更高的层级
const zIndex = useZIndex("popconfirm");

/** Vort Popconfirm - 气泡确认框组件 */

type ButtonType = "primary" | "default" | "dashed" | "text" | "link";

interface Props {
    /** 确认框标题 */
    title?: string;
    /** 确认框描述 */
    description?: string;
    /** 确认按钮文字 */
    okText?: string;
    /** 取消按钮文字 */
    cancelText?: string;
    /** 确认按钮类型 */
    okType?: ButtonType;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义图标 */
    icon?: Component;
    /** 是否显示取消按钮 */
    showCancel?: boolean;
    /** 气泡框位置 */
    placement?: FloatingPlacement;
    /** 是否显示箭头 */
    arrow?: boolean;
    /** 控制浮层显示（受控模式） */
    open?: boolean;
    /** 菜单渲染父节点。默认渲染到 body 上，如果你遇到菜单滚动定位问题，试试修改为滚动的区域，并相对其定位 */
    getPopupContainer?: () => HTMLElement;
    /** 自定义类名 */
    class?: string;
    /** 弹窗宽度 */
    width?: number | string;
    /** 确认按钮 loading 状态 */
    loading?: boolean;
    /** 是否显示默认按钮区域（自定义内容模式下可隐藏） */
    showButtons?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    title: "",
    description: "",
    okText: undefined,
    cancelText: undefined,
    okType: "primary",
    disabled: false,
    showCancel: true,
    placement: "top",
    arrow: true,
    loading: false,
    showButtons: true
});

// 国际化
const { t } = useLocale("Popconfirm");
const okTextValue = computed(() => props.okText ?? t("ok_text"));
const cancelTextValue = computed(() => props.cancelText ?? t("cancel_text"));

const slots = useSlots();

const emit = defineEmits<{
    confirm: [e: MouseEvent];
    cancel: [e: MouseEvent];
    openChange: [open: boolean];
    "update:open": [open: boolean];
    afterOpen: [];
}>();

// 是否使用自定义内容模式
const hasContentSlot = computed(() => !!slots.content);

// 计算弹窗宽度样式
const popWidthStyle = computed(() => {
    if (!props.width) return undefined;
    return typeof props.width === "number" ? `${props.width}px` : props.width;
});

// 状态
const visible = ref(false);
const shouldRenderTeleport = ref(false); // 控制 Teleport 是否渲染，避免产生 <!--v-if--> 注释
const triggerRef = ref<HTMLElement | null>(null);
const popoverRef = ref<HTMLElement | null>(null);
const position = ref({ top: 0, left: 0 });
const arrowPosition = ref({ top: "", left: "", right: "", bottom: "" });
const actualPlacement = ref(props.placement);
const popupContainer = computed(() => props.getPopupContainer?.() ?? getVortPopupContainer());

// 同步外部 open 状态
watch(
    () => props.open,
    (val) => {
        if (val !== undefined) {
            if (val) {
                shouldRenderTeleport.value = true;
            }
            visible.value = val;
        }
    },
    { immediate: true }
);

// 计算位置
const updatePosition = async () => {
    await nextTick();
    if (!triggerRef.value || !popoverRef.value) return;

    const triggerRect = triggerRef.value.getBoundingClientRect();
    // 使用 offsetWidth/offsetHeight 获取未被 transform 影响的原始尺寸
    const popoverWidth = popoverRef.value.offsetWidth;
    const popoverHeight = popoverRef.value.offsetHeight;
    const gap = 8; // 间距（箭头尖端到触发元素的距离）
    const arrowHeight = 6; // 箭头露出高度
    const totalGap = gap + arrowHeight; // 总间距

    // 判断是否使用自定义容器
    const container = popupContainer.value;
    const useCustomContainer = container && container !== document.body;

    let scrollTop = 0;
    let scrollLeft = 0;
    let containerRect: DOMRect | null = null;

    if (useCustomContainer) {
        // 使用自定义容器，需要计算相对容器的偏移
        containerRect = container.getBoundingClientRect();
        scrollTop = container.scrollTop;
        scrollLeft = container.scrollLeft;
    } else {
        // 使用 body，使用 window 的滚动
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
            // 相对自定义容器定位
            const offsetTop = triggerRect.top - containerRect.top + scrollTop;
            const offsetLeft = triggerRect.left - containerRect.left + scrollLeft;

            switch (p) {
                case "top":
                    t = offsetTop - popoverHeight - totalGap;
                    l = offsetLeft + (triggerRect.width - popoverWidth) / 2;
                    break;
                case "topLeft":
                    t = offsetTop - popoverHeight - totalGap;
                    l = offsetLeft;
                    break;
                case "topRight":
                    t = offsetTop - popoverHeight - totalGap;
                    l = offsetLeft + triggerRect.width - popoverWidth;
                    break;
                case "bottom":
                    t = offsetTop + triggerRect.height + totalGap;
                    l = offsetLeft + (triggerRect.width - popoverWidth) / 2;
                    break;
                case "bottomLeft":
                    t = offsetTop + triggerRect.height + totalGap;
                    l = offsetLeft;
                    break;
                case "bottomRight":
                    t = offsetTop + triggerRect.height + totalGap;
                    l = offsetLeft + triggerRect.width - popoverWidth;
                    break;
                case "left":
                    t = offsetTop + (triggerRect.height - popoverHeight) / 2;
                    l = offsetLeft - popoverWidth - totalGap;
                    break;
                case "leftTop":
                    t = offsetTop;
                    l = offsetLeft - popoverWidth - totalGap;
                    break;
                case "leftBottom":
                    t = offsetTop + triggerRect.height - popoverHeight;
                    l = offsetLeft - popoverWidth - totalGap;
                    break;
                case "right":
                    t = offsetTop + (triggerRect.height - popoverHeight) / 2;
                    l = offsetLeft + triggerRect.width + totalGap;
                    break;
                case "rightTop":
                    t = offsetTop;
                    l = offsetLeft + triggerRect.width + totalGap;
                    break;
                case "rightBottom":
                    t = offsetTop + triggerRect.height - popoverHeight;
                    l = offsetLeft + triggerRect.width + totalGap;
                    break;
            }
        } else {
            // 相对 body 定位（使用 fixed，所以直接用 viewport 坐标）
            switch (p) {
                case "top":
                    t = triggerRect.top - popoverHeight - totalGap;
                    l = triggerRect.left + (triggerRect.width - popoverWidth) / 2;
                    break;
                case "topLeft":
                    t = triggerRect.top - popoverHeight - totalGap;
                    l = triggerRect.left;
                    break;
                case "topRight":
                    t = triggerRect.top - popoverHeight - totalGap;
                    l = triggerRect.right - popoverWidth;
                    break;
                case "bottom":
                    t = triggerRect.bottom + totalGap;
                    l = triggerRect.left + (triggerRect.width - popoverWidth) / 2;
                    break;
                case "bottomLeft":
                    t = triggerRect.bottom + totalGap;
                    l = triggerRect.left;
                    break;
                case "bottomRight":
                    t = triggerRect.bottom + totalGap;
                    l = triggerRect.right - popoverWidth;
                    break;
                case "left":
                    t = triggerRect.top + (triggerRect.height - popoverHeight) / 2;
                    l = triggerRect.left - popoverWidth - totalGap;
                    break;
                case "leftTop":
                    t = triggerRect.top;
                    l = triggerRect.left - popoverWidth - totalGap;
                    break;
                case "leftBottom":
                    t = triggerRect.bottom - popoverHeight;
                    l = triggerRect.left - popoverWidth - totalGap;
                    break;
                case "right":
                    t = triggerRect.top + (triggerRect.height - popoverHeight) / 2;
                    l = triggerRect.right + totalGap;
                    break;
                case "rightTop":
                    t = triggerRect.top;
                    l = triggerRect.right + totalGap;
                    break;
                case "rightBottom":
                    t = triggerRect.bottom - popoverHeight;
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
        // 自定义容器的边界
        const containerWidth = container!.clientWidth;
        const containerHeight = container!.clientHeight;

        if (placement.startsWith("top") && top < scrollTop) {
            placement = placement.replace("top", "bottom") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        } else if (placement.startsWith("bottom") && top + popoverHeight > scrollTop + containerHeight) {
            placement = placement.replace("bottom", "top") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        } else if (placement.startsWith("left") && left < scrollLeft) {
            placement = placement.replace("left", "right") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        } else if (placement.startsWith("right") && left + popoverWidth > scrollLeft + containerWidth) {
            placement = placement.replace("right", "left") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        }

        // 确保不超出容器边界
        left = Math.max(scrollLeft + 8, Math.min(left, scrollLeft + containerWidth - popoverWidth - 8));
        top = Math.max(scrollTop + 8, Math.min(top, scrollTop + containerHeight - popoverHeight - 8));
    } else {
        // body 容器的边界
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        if (placement.startsWith("top") && triggerRect.top - popoverHeight - totalGap < 0) {
            placement = placement.replace("top", "bottom") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        } else if (placement.startsWith("bottom") && triggerRect.bottom + popoverHeight + totalGap > viewportHeight) {
            placement = placement.replace("bottom", "top") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        } else if (placement.startsWith("left") && triggerRect.left - popoverWidth - totalGap < 0) {
            placement = placement.replace("left", "right") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        } else if (placement.startsWith("right") && triggerRect.right + popoverWidth + totalGap > viewportWidth) {
            placement = placement.replace("right", "left") as FloatingPlacement;
            const newPos = calcPosition(placement);
            top = newPos.top;
            left = newPos.left;
        }

        // 确保不超出边界
        left = Math.max(8, Math.min(left, viewportWidth - popoverWidth - 8));
        top = Math.max(8, Math.min(top, viewportHeight - popoverHeight - 8));
    }

    actualPlacement.value = placement;
    position.value = { top, left };

    // 计算箭头位置
    updateArrowPosition(placement, triggerRect, popoverWidth, popoverHeight, top, left, useCustomContainer, containerRect, scrollTop, scrollLeft);
};

// 更新箭头位置
// 注意：CSS 中使用了 translateX(-50%) 或 translateY(-50%) 来居中箭头
// 所以定位使用 left/top（px），值代表箭头中心点在弹层内的坐标
const updateArrowPosition = (
    placement: FloatingPlacement,
    triggerRect: DOMRect,
    popoverWidth: number,
    popoverHeight: number,
    top: number,
    left: number,
    useCustomContainer: boolean,
    containerRect: DOMRect | null,
    scrollTop: number,
    scrollLeft: number
) => {
    const arrowOffset = 6; // 箭头露出高度
    const reset = { top: "", left: "", right: "", bottom: "" };

    const clamp = (val: number, min: number, max: number) => {
        if (Number.isNaN(val)) return min;
        if (max < min) return min;
        return Math.min(Math.max(val, min), max);
    };

    // 触发点中心在「定位坐标系」中的坐标（body: viewport；自定义容器: 容器内容区）
    const triggerCenterX =
        useCustomContainer && containerRect
            ? triggerRect.left - containerRect.left + scrollLeft + triggerRect.width / 2
            : triggerRect.left + triggerRect.width / 2;
    const triggerCenterY =
        useCustomContainer && containerRect
            ? triggerRect.top - containerRect.top + scrollTop + triggerRect.height / 2
            : triggerRect.top + triggerRect.height / 2;

    // 箭头中心在「弹层内部」的坐标
    const arrowX = clamp(triggerCenterX - left, 16, popoverWidth - 16);
    const arrowY = clamp(triggerCenterY - top, 16, popoverHeight - 16);

    if (placement.startsWith("top")) {
        arrowPosition.value = {
            ...reset,
            bottom: `-${arrowOffset}px`,
            left: `${arrowX}px`
        };
    } else if (placement.startsWith("bottom")) {
        arrowPosition.value = {
            ...reset,
            top: `-${arrowOffset}px`,
            left: `${arrowX}px`
        };
    } else if (placement.startsWith("left")) {
        arrowPosition.value = {
            ...reset,
            right: `-${arrowOffset}px`,
            top: `${arrowY}px`
        };
    } else if (placement.startsWith("right")) {
        arrowPosition.value = {
            ...reset,
            left: `-${arrowOffset}px`,
            top: `${arrowY}px`
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

// 动画 transform-origin（从箭头方向展开）
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
    nextTick(() => {
        updatePosition();
        // 触发 afterOpen 回调供外部聚焦等操作
        emit("afterOpen");
    });
};

const hide = () => {
    if (props.loading) return; // loading 时禁止关闭
    visible.value = false;
    emit("update:open", false);
    emit("openChange", false);
    // 注意：shouldRenderTeleport 会在 Transition 的 afterLeave 回调中设为 false
};

// Transition 离开动画完成后移除 Teleport，避免产生 <!--v-if--> 注释
const handleAfterLeave = () => {
    shouldRenderTeleport.value = false;
};

// 事件处理
const handleTriggerClick = () => {
    if (visible.value) {
        hide();
    } else {
        show();
    }
};

const handleConfirm = (e: MouseEvent) => {
    hide();
    emit("confirm", e);
};

const handleCancel = (e: MouseEvent) => {
    hide();
    emit("cancel", e);
};

// 点击外部关闭
const handleClickOutside = (e: MouseEvent) => {
    if (!visible.value || props.loading) return;
    const target = e.target as Node;
    if (triggerRef.value?.contains(target) || popoverRef.value?.contains(target)) {
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
});

// 按钮样式
const okButtonClasses = computed(() => {
    const base = "vort-popconfirm-btn";
    return props.okType === "primary" ? `${base} vort-popconfirm-btn-primary` : base;
});

// 暴露方法供外部调用
defineExpose({
    show,
    hide,
    updatePosition,
    visible
});
</script>

<template>
    <span ref="triggerRef" class="vort-popconfirm-trigger" @click="handleTriggerClick">
        <slot />
    </span>

    <Teleport v-if="shouldRenderTeleport" :to="popupContainer">
        <Transition name="vort-popconfirm" appear @after-leave="handleAfterLeave">
            <div
                v-if="visible"
                ref="popoverRef"
                :class="['vort-popconfirm', props.class]"
                :style="{
                    top: `${position.top}px`,
                    left: `${position.left}px`,
                    width: popWidthStyle,
                    zIndex: zIndex,
                    '--transform-origin': transformOrigin
                }"
                @click.stop
            >
                <!-- 箭头 -->
                <div
                    v-if="arrow"
                    class="vort-popconfirm-arrow"
                    :class="arrowDirectionClass"
                    :style="{
                        top: arrowPosition.top || undefined,
                        bottom: arrowPosition.bottom || undefined,
                        left: arrowPosition.left || undefined,
                        right: arrowPosition.right || undefined
                    }"
                />

                <!-- 自定义内容模式 -->
                <div v-if="hasContentSlot" class="vort-popconfirm-inner">
                    <slot name="content" :hide="hide" :loading="loading" />

                    <!-- 可选按钮区域 -->
                    <div v-if="showButtons" class="vort-popconfirm-buttons">
                        <button v-if="showCancel" class="vort-popconfirm-btn" :disabled="loading" @click="handleCancel">
                            <slot name="cancelText">{{ cancelTextValue }}</slot>
                        </button>
                        <button :class="[okButtonClasses, { 'is-loading': loading }]" :disabled="loading" @click="handleConfirm">
                            <span v-if="loading" class="vort-popconfirm-btn-loading" />
                            <slot name="okText">{{ okTextValue }}</slot>
                        </button>
                    </div>
                </div>

                <!-- 默认模式：icon + title + description + buttons -->
                <div v-else class="vort-popconfirm-inner">
                    <div class="vort-popconfirm-message">
                        <span class="vort-popconfirm-icon">
                            <slot name="icon">
                                <component :is="icon" v-if="icon" />
                                <ExclamationCircleFilled v-else />
                            </slot>
                        </span>
                        <div class="vort-popconfirm-message-text">
                            <div v-if="title || $slots.title" class="vort-popconfirm-title">
                                <slot name="title">{{ title }}</slot>
                            </div>
                            <div v-if="description || $slots.description" class="vort-popconfirm-description">
                                <slot name="description">{{ description }}</slot>
                            </div>
                        </div>
                    </div>

                    <div v-if="showButtons" class="vort-popconfirm-buttons">
                        <button v-if="showCancel" class="vort-popconfirm-btn" :disabled="loading" @click="handleCancel">
                            <slot name="cancelText">{{ cancelTextValue }}</slot>
                        </button>
                        <button :class="[okButtonClasses, { 'is-loading': loading }]" :disabled="loading" @click="handleConfirm">
                            <span v-if="loading" class="vort-popconfirm-btn-loading" />
                            <slot name="okText">{{ okTextValue }}</slot>
                        </button>
                    </div>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>

<style scoped>
.vort-popconfirm-trigger {
    display: inline-flex;
    cursor: pointer;
}

.vort-popconfirm {
    position: absolute;
    min-width: 180px;
    max-width: 420px;
    padding: 12px;
    background: #fff;
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 4px));
    pointer-events: auto;
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
    overflow: visible;
}

/* 渲染到 body 时使用 fixed 定位 */
body > .vort-popconfirm {
    position: fixed;
}

/* 动画 - 参考 Ant Design zoom-big */
.vort-popconfirm-enter-active {
    animation: vortPopconfirmIn 0.2s cubic-bezier(0.08, 0.82, 0.17, 1);
    transform-origin: var(--transform-origin, center);
}

.vort-popconfirm-leave-active {
    animation: vortPopconfirmOut 0.2s cubic-bezier(0.78, 0.14, 0.15, 0.86);
    transform-origin: var(--transform-origin, center);
}

@keyframes vortPopconfirmIn {
    0% {
        opacity: 0;
        transform: scale(0.8);
    }

    100% {
        opacity: 1;
        transform: scale(1);
    }
}

@keyframes vortPopconfirmOut {
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
.vort-popconfirm-arrow {
    position: absolute;
    z-index: 1;
    display: block;
    pointer-events: none;
    width: 16px;
    height: 8px;
}

.vort-popconfirm-arrow::before {
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
.vort-popconfirm-arrow.arrow-bottom {
    transform: translateX(-50%);
    height: 8px;
}

.vort-popconfirm-arrow.arrow-bottom::before {
    left: 50%;
    top: -2px;
    transform: translateX(-50%) rotate(45deg);
}

/* 箭头在顶部（弹窗在下方时） - 三角形指向上方 */
.vort-popconfirm-arrow.arrow-top {
    transform: translateX(-50%);
    height: 8px;
}

.vort-popconfirm-arrow.arrow-top::before {
    left: 50%;
    bottom: -2px;
    transform: translateX(-50%) rotate(-135deg);
}

/* 箭头在右侧（弹窗在左方时） - 三角形指向右方 */
.vort-popconfirm-arrow.arrow-right {
    transform: translateY(-50%);
    width: 8px;
    height: 16px;
}

.vort-popconfirm-arrow.arrow-right::before {
    top: 50%;
    left: -2px;
    transform: translateY(-50%) rotate(-45deg);
}

/* 箭头在左侧（弹窗在右方时） - 三角形指向左方 */
.vort-popconfirm-arrow.arrow-left {
    transform: translateY(-50%);
    width: 8px;
    height: 16px;
}

.vort-popconfirm-arrow.arrow-left::before {
    top: 50%;
    right: -2px;
    transform: translateY(-50%) rotate(135deg);
}

/* 内容 */
.vort-popconfirm-inner {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.vort-popconfirm-message {
    display: flex;
    align-items: flex-start;
    gap: 8px;
}

.vort-popconfirm-icon {
    flex-shrink: 0;
    color: var(--vort-warning);
    line-height: 1;
    /* 使 icon 与 title 文字垂直居中对齐：(line-height 21px - icon 14px) / 2 ≈ 4px */
    margin-top: 4px;
}

.vort-popconfirm-icon :deep(svg) {
    width: 14px;
    height: 14px;
}

.vort-popconfirm-message-text {
    flex: 1;
    min-width: 0;
}

.vort-popconfirm-title {
    font-size: 14px;
    font-weight: 600;
    color: rgba(0, 0, 0, 0.88);
    line-height: 1.5;
}

.vort-popconfirm-description {
    margin-top: 4px;
    font-size: 14px;
    color: rgba(0, 0, 0, 0.65);
    line-height: 1.5;
}

/* 按钮 */
.vort-popconfirm-buttons {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 4px;
}

.vort-popconfirm-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 24px;
    padding: 0 8px;
    font-size: 12px;
    font-weight: 400;
    border-radius: var(--vort-border-radius-sm, 4px);
    cursor: pointer;
    transition: all 0.2s;
    background: #fff;
    border: 1px solid var(--vort-border);
    color: rgba(0, 0, 0, 0.88);
}

.vort-popconfirm-btn:hover {
    color: var(--vort-primary-hover);
    border-color: var(--vort-primary-hover);
}

.vort-popconfirm-btn:active {
    color: var(--vort-primary-active);
    border-color: var(--vort-primary-active);
}

.vort-popconfirm-btn-primary {
    background: var(--vort-primary);
    border-color: var(--vort-primary);
    color: #fff;
}

.vort-popconfirm-btn-primary:hover {
    background: var(--vort-primary-hover);
    border-color: var(--vort-primary-hover);
    color: #fff;
}

.vort-popconfirm-btn-primary:active {
    background: var(--vort-primary-active);
    border-color: var(--vort-primary-active);
    color: #fff;
}

.vort-popconfirm-btn:disabled {
    cursor: not-allowed;
    opacity: 0.65;
}

.vort-popconfirm-btn.is-loading {
    position: relative;
    pointer-events: none;
}

.vort-popconfirm-btn-loading {
    display: inline-block;
    width: 12px;
    height: 12px;
    margin-right: 4px;
    border: 1.5px solid currentColor;
    border-top-color: transparent;
    border-radius: 50%;
    animation: vort-popconfirm-spin 0.8s linear infinite;
}

@keyframes vort-popconfirm-spin {
    from {
        transform: rotate(0deg);
    }

    to {
        transform: rotate(360deg);
    }
}
</style>
