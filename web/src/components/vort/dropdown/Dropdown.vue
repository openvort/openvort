<script lang="ts">
/** Vort Dropdown - 下拉菜单组件 */
export type DropdownTrigger = "hover" | "click" | "contextMenu";
export type DropdownPlacement =
    | "bottom"
    | "bottomLeft"
    | "bottomRight"
    | "top"
    | "topLeft"
    | "topRight"
    | "left"
    | "leftTop"
    | "leftBottom"
    | "right"
    | "rightTop"
    | "rightBottom";

interface Props {
    /** 菜单是否显示（受控模式） */
    open?: boolean;
    /** 菜单是否默认显示（非受控模式） */
    defaultOpen?: boolean;
    /** 触发下拉的行为，支持数组 */
    trigger?: DropdownTrigger | DropdownTrigger[];
    /** 菜单弹出位置 */
    placement?: DropdownPlacement;
    /** 菜单是否禁用 */
    disabled?: boolean;
    /** 下拉根元素的类名 */
    overlayClassName?: string;
    /** 下拉根元素的样式 */
    overlayStyle?: Record<string, string>;
    /** 是否显示箭头 */
    arrow?: boolean | { pointAtCenter: boolean };
    /**
     * 关闭后是否销毁 Dropdown 内容（默认：true，保持当前行为）
     *
     * 说明：当你在 dropdown overlay 内嵌了 Dialog/Drawer 等 Teleport 组件时，
     * 如果关闭 dropdown 时销毁 overlay，会导致弹窗组件实例被卸载，弹窗也会同步关闭。
     * 此时可以设置 destroyOnHidden=false，让 dropdown 关闭时仅隐藏、不销毁内容。
     */
    destroyOnHidden?: boolean;
    /**
     * 关闭后是否销毁 Dropdown（兼容旧命名）
     *
     * @deprecated 请使用 destroyOnHidden
     */
    destroyPopupOnHide?: boolean;
    /** 下拉框和触发元素之间的距离 */
    offset?: number;
    /** 菜单渲染父节点。默认渲染到 body 上，如果你遇到菜单滚动定位问题，试试修改为滚动的区域，并相对其定位 */
    getPopupContainer?: () => HTMLElement;
    /** 触发元素的自定义类名 */
    class?: string;
    /** 鼠标移入后延迟多少时间显示 Dropdown，单位：毫秒（仅 hover 触发时有效） */
    mouseEnterDelay?: number;
    /** 鼠标移出后延迟多少时间关闭 Dropdown，单位：毫秒（仅 hover 触发时有效） */
    mouseLeaveDelay?: number;
}

export type { Props as DropdownProps };
</script>

<script setup lang="ts">
import { computed, ref, onBeforeUnmount, watch, nextTick } from "vue";
import { DropdownMenuRoot, DropdownMenuTrigger, DropdownMenuPortal, DropdownMenuContent, DropdownMenuArrow } from "reka-ui";
import { getVortPopupContainer, useZIndex } from "@/components/vort/composables";
import "./dropdown.css";

defineOptions({ name: "VortDropdown" });

const props = withDefaults(defineProps<Props>(), {
    open: undefined,
    defaultOpen: false,
    trigger: "hover",
    placement: "bottomLeft",
    disabled: false,
    overlayClassName: "",
    overlayStyle: () => ({}),
    arrow: false,
    destroyOnHidden: true,
    offset: 4,
    mouseEnterDelay: 100,
    mouseLeaveDelay: 100
});

const shouldDestroyOnHidden = computed(() => props.destroyOnHidden ?? props.destroyPopupOnHide ?? true);
const popupContainer = computed(() => props.getPopupContainer?.() ?? getVortPopupContainer());

const emit = defineEmits<{
    /** 菜单显示状态改变时调用 */
    "update:open": [open: boolean];
    /** 菜单显示状态改变时调用（兼容 ant-design 事件命名） */
    openChange: [open: boolean];
}>();

// ============ 内部状态 ============
const triggerRef = ref<HTMLElement | null>(null);
const contentRef = ref<HTMLElement | null>(null);
const isHovered = ref(false);
const enterTimeoutId = ref<ReturnType<typeof setTimeout> | null>(null);
const leaveTimeoutId = ref<ReturnType<typeof setTimeout> | null>(null);
const shouldRenderPortal = ref(false); // 控制 Portal 是否渲染，避免产生 <!--v-if--> 注释
const isAfterClosedHidden = ref(false); // destroyOnHidden=false 时，关闭后强制隐藏 wrapper，避免遮挡点击区域
const hideTimeoutId = ref<ReturnType<typeof setTimeout> | null>(null);
const isTriggerClicking = ref(false); // 标记是否正在点击 trigger，用于 hover 模式下阻止点击关闭

// 内部打开状态
const internalOpen = ref(props.defaultOpen);

// ============ 右键菜单位置状态 ============
// 记录右键点击时的鼠标位置，用于将弹窗定位到鼠标位置
const contextMenuPosition = ref<{ x: number; y: number } | null>(null);

// 使用 z-index 上下文，在 Dialog/Drawer 内时自动获得更高的层级
const zIndex = useZIndex("popup");

// 计算实际的 open 状态（支持受控和非受控模式）
const isOpen = computed({
    get: () => (props.open !== undefined ? props.open : internalOpen.value),
    set: (val) => {
        if (val) {
            shouldRenderPortal.value = true; // 打开时先渲染 Portal
        }
        if (props.open === undefined) {
            internalOpen.value = val;
        }
        emit("update:open", val);
        emit("openChange", val);
    }
});

// 打开时立即取消隐藏；关闭时允许播放关闭动画，动画结束后再隐藏 wrapper
watch(
    isOpen,
    (open) => {
        if (hideTimeoutId.value) {
            clearTimeout(hideTimeoutId.value);
            hideTimeoutId.value = null;
        }
        if (open) {
            isAfterClosedHidden.value = false;
            return;
        }
        // destroyOnHidden=true 时会在动画结束后卸载 Portal，不需要额外隐藏
        if (!shouldDestroyOnHidden.value) {
            isAfterClosedHidden.value = false;
            // 兜底：极少数情况下 animationend 可能不触发（如用户关闭动画），延迟隐藏避免遮挡
            hideTimeoutId.value = setTimeout(() => {
                if (!isOpen.value) {
                    isAfterClosedHidden.value = true;
                }
            }, 200);
        }
    },
    { immediate: true }
);

// 处理关闭动画完成后移除 Portal 和清理右键菜单状态
const handleAnimationEnd = () => {
    if (!isOpen.value) {
        if (shouldDestroyOnHidden.value) {
            shouldRenderPortal.value = false;
        } else {
            isAfterClosedHidden.value = true;
        }
        // 动画结束后再停止 Observer 和清除位置，避免关闭动画期间弹窗跳位
        stopContextMenuPositionWatch();
        contextMenuPosition.value = null;
    }
};

// 解析触发方式
const triggers = computed(() => {
    const t = props.trigger;
    return Array.isArray(t) ? t : [t];
});

const hasHoverTrigger = computed(() => triggers.value.includes("hover"));
const hasClickTrigger = computed(() => triggers.value.includes("click"));
const hasContextMenuTrigger = computed(() => triggers.value.includes("contextMenu"));

// ============ 位置映射 ============
// Ant Design placement -> Radix side/align
const placementMap: Record<DropdownPlacement, { side: "top" | "bottom" | "left" | "right"; align: "start" | "center" | "end" }> = {
    bottom: { side: "bottom", align: "center" },
    bottomLeft: { side: "bottom", align: "start" },
    bottomRight: { side: "bottom", align: "end" },
    top: { side: "top", align: "center" },
    topLeft: { side: "top", align: "start" },
    topRight: { side: "top", align: "end" },
    left: { side: "left", align: "center" },
    leftTop: { side: "left", align: "start" },
    leftBottom: { side: "left", align: "end" },
    right: { side: "right", align: "center" },
    rightTop: { side: "right", align: "start" },
    rightBottom: { side: "right", align: "end" }
};

const placement = computed(() => placementMap[props.placement]);

// ============ 箭头配置 ============
const showArrow = computed(() => !!props.arrow);

// ============ 样式类（简洁的类名切换） ============
const contentClasses = computed(() => {
    const classes = ["vort-dropdown"];
    if (props.overlayClassName) classes.push(props.overlayClassName);
    return classes;
});

const triggerClasses = computed(() => {
    const classes = ["vort-dropdown-trigger"];
    if (props.disabled) classes.push("vort-dropdown-trigger-disabled");
    if (props.class) classes.push(props.class);
    return classes;
});

// ============ 事件处理 ============

// 清除所有延迟定时器
const clearAllTimers = () => {
    if (enterTimeoutId.value) {
        clearTimeout(enterTimeoutId.value);
        enterTimeoutId.value = null;
    }
    if (leaveTimeoutId.value) {
        clearTimeout(leaveTimeoutId.value);
        leaveTimeoutId.value = null;
    }
};

// Hover 触发逻辑
const handleMouseEnter = () => {
    if (!hasHoverTrigger.value || props.disabled) return;
    // 清除离开定时器
    if (leaveTimeoutId.value) {
        clearTimeout(leaveTimeoutId.value);
        leaveTimeoutId.value = null;
    }
    isHovered.value = true;
    // 延迟显示，防止鼠标快速经过时触发
    enterTimeoutId.value = setTimeout(() => {
        if (isHovered.value) {
            isOpen.value = true;
        }
    }, props.mouseEnterDelay);
};

const handleMouseLeave = () => {
    if (!hasHoverTrigger.value || props.disabled) return;
    // 清除进入定时器
    if (enterTimeoutId.value) {
        clearTimeout(enterTimeoutId.value);
        enterTimeoutId.value = null;
    }
    isHovered.value = false;
    // 延迟关闭，给用户时间移动到菜单内容上
    leaveTimeoutId.value = setTimeout(() => {
        if (!isHovered.value) {
            isOpen.value = false;
        }
    }, props.mouseLeaveDelay);
};

const handleContentMouseEnter = () => {
    if (!hasHoverTrigger.value) return;
    // 清除离开定时器
    if (leaveTimeoutId.value) {
        clearTimeout(leaveTimeoutId.value);
        leaveTimeoutId.value = null;
    }
    isHovered.value = true;
};

const handleContentMouseLeave = () => {
    if (!hasHoverTrigger.value) return;
    isHovered.value = false;
    leaveTimeoutId.value = setTimeout(() => {
        if (!isHovered.value) {
            isOpen.value = false;
        }
    }, props.mouseLeaveDelay);
};

// Click 触发逻辑
const handleTriggerClick = (e: MouseEvent) => {
    if (props.disabled) return;

    // hover 模式下，点击 trigger 不应该关闭菜单
    // 设置标志，在 handleOpenChange 中检查
    if (hasHoverTrigger.value && !hasClickTrigger.value) {
        isTriggerClicking.value = true;
        // 使用 nextTick 重置标志，确保 handleOpenChange 能检测到
        nextTick(() => {
            isTriggerClicking.value = false;
        });
        return;
    }

    // 只有明确设置了 click 触发时才响应左键点击
    if (hasClickTrigger.value) {
        e.preventDefault();
        // 非右键模式触发时，清除右键位置
        contextMenuPosition.value = null;
        isOpen.value = !isOpen.value;
    }
    // 如果只有 contextMenu 触发，阻止左键打开
    if (hasContextMenuTrigger.value && !hasClickTrigger.value) {
        e.preventDefault();
        e.stopPropagation();
    }
};

// ============ 右键菜单位置控制 ============
// 使用 MutationObserver 监听 wrapper 的 style 变化，持续覆盖 popper 的位置计算
let contextMenuObserver: MutationObserver | null = null;

// 设置右键菜单弹窗位置的辅助函数
const applyContextMenuPosition = (wrapper: HTMLElement, x: number, y: number) => {
    // 检查当前位置是否已正确
    const currentLeft = wrapper.style.left;
    const currentTop = wrapper.style.top;
    const currentTransform = wrapper.style.transform;

    if (currentLeft === `${x}px` && currentTop === `${y}px` && currentTransform === "none") {
        return; // 位置已正确，无需更新
    }

    wrapper.style.position = "fixed";
    wrapper.style.left = `${x}px`;
    wrapper.style.top = `${y}px`;
    wrapper.style.transform = "none";
};

// 开始监听 wrapper 的 style 变化
const startContextMenuPositionWatch = () => {
    if (!contentRef.value || !contextMenuPosition.value) return;

    const refValue = contentRef.value as unknown as { $el?: HTMLElement };
    const contentEl = refValue.$el || (contentRef.value as unknown as HTMLElement);
    const wrapper = contentEl?.closest?.("[data-reka-popper-content-wrapper]") as HTMLElement | null;

    if (!wrapper) return;

    const { x, y } = contextMenuPosition.value;

    // 先立即设置一次位置
    applyContextMenuPosition(wrapper, x, y);

    // 停止之前的观察器
    stopContextMenuPositionWatch();

    // 创建 MutationObserver 监听 style 变化
    contextMenuObserver = new MutationObserver(() => {
        if (contextMenuPosition.value) {
            applyContextMenuPosition(wrapper, contextMenuPosition.value.x, contextMenuPosition.value.y);
        }
    });

    contextMenuObserver.observe(wrapper, {
        attributes: true,
        attributeFilter: ["style"]
    });
};

// 停止监听
const stopContextMenuPositionWatch = () => {
    if (contextMenuObserver) {
        contextMenuObserver.disconnect();
        contextMenuObserver = null;
    }
};

// ContextMenu 触发逻辑
const handleContextMenu = (e: MouseEvent) => {
    if (!hasContextMenuTrigger.value || props.disabled) return;
    e.preventDefault();

    // 记录右键点击的鼠标位置
    contextMenuPosition.value = { x: e.clientX, y: e.clientY };

    // 如果已经打开，直接更新位置
    if (isOpen.value) {
        nextTick(() => {
            startContextMenuPositionWatch();
        });
        return;
    }

    // 首次打开
    isOpen.value = true;
};

// 监听 contentRef 变化，在右键菜单模式下开始位置监听
watch(contentRef, (newVal) => {
    if (newVal && contextMenuPosition.value) {
        // 使用 nextTick 确保 DOM 完成更新
        nextTick(() => {
            startContextMenuPositionWatch();
        });
    }
});

// Radix 的 open 变化回调
const handleOpenChange = (open: boolean) => {
    // 如果是 hover 模式，只通过 hover 控制打开，但允许通过点击菜单项关闭
    if (hasHoverTrigger.value && !hasClickTrigger.value) {
        // hover 模式下，点击 trigger 不应该关闭菜单
        if (!open && isTriggerClicking.value) {
            return;
        }
        // hover 模式下，允许关闭（如点击菜单项），但不通过此回调打开
        if (!open) {
            isOpen.value = false;
        }
        return;
    }
    // 如果只有 contextMenu 触发，不响应 radix 默认的点击打开行为
    if (hasContextMenuTrigger.value && !hasClickTrigger.value && !hasHoverTrigger.value) {
        // 只允许关闭操作，打开操作由 handleContextMenu 控制
        if (!open) {
            isOpen.value = false;
        }
        return;
    }
    isOpen.value = open;
};

// ============ 清理 ============
onBeforeUnmount(() => {
    clearAllTimers();
    stopContextMenuPositionWatch();
    if (hideTimeoutId.value) {
        clearTimeout(hideTimeoutId.value);
        hideTimeoutId.value = null;
    }
});

// ============ 暴露方法 ============
defineExpose({
    /** 打开下拉菜单 */
    open: () => {
        if (!props.disabled) {
            isOpen.value = true;
        }
    },
    /** 关闭下拉菜单 */
    close: () => {
        isOpen.value = false;
    }
});
</script>

<template>
    <DropdownMenuRoot :open="isOpen" :modal="false" @update:open="handleOpenChange">
        <DropdownMenuTrigger
            ref="triggerRef"
            as-child
            :disabled="disabled"
            @click="handleTriggerClick"
            @contextmenu="handleContextMenu"
            @mouseenter="handleMouseEnter"
            @mouseleave="handleMouseLeave"
        >
            <span :class="triggerClasses">
                <slot />
            </span>
        </DropdownMenuTrigger>

        <DropdownMenuPortal v-if="shouldRenderPortal" :to="popupContainer">
            <DropdownMenuContent
                ref="contentRef"
                data-slot="dropdown-content"
                :data-vort-hidden="isAfterClosedHidden ? '' : undefined"
                :class="contentClasses"
                :style="{ ...overlayStyle, '--vort-dropdown-z-index': zIndex }"
                :side="placement.side"
                :align="placement.align"
                :side-offset="offset"
                :collision-padding="8"
                :force-mount="!shouldDestroyOnHidden"
                @mouseenter="handleContentMouseEnter"
                @mouseleave="handleContentMouseLeave"
                @animationend="handleAnimationEnd"
            >
                <!-- 下拉内容 -->
                <slot name="overlay" />

                <!-- 箭头 -->
                <DropdownMenuArrow v-if="showArrow" class="vort-dropdown-arrow" :width="12" :height="6" :style="{ fill: '#fff' }" />
            </DropdownMenuContent>
        </DropdownMenuPortal>
    </DropdownMenuRoot>
</template>

<style>
/* 覆盖 reka-ui 的 popper wrapper z-index */
[data-reka-popper-content-wrapper]:has([data-slot="dropdown-content"]) {
    z-index: var(--vort-dropdown-z-index, 1050) !important;
}
</style>
