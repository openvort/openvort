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

export interface VortDropdownContext {
    close: () => void;
}
</script>

<script setup lang="ts">
import { computed, ref, onBeforeUnmount, onMounted, watch, nextTick, provide } from "vue";
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
    "update:open": [open: boolean];
    openChange: [open: boolean];
}>();

// ============ 内部状态 ============
const triggerRef = ref<HTMLElement | null>(null);
const contentRef = ref<HTMLElement | null>(null);
const isHovered = ref(false);
const enterTimeoutId = ref<ReturnType<typeof setTimeout> | null>(null);
const leaveTimeoutId = ref<ReturnType<typeof setTimeout> | null>(null);
const shouldRenderPortal = ref(false);
const isAfterClosedHidden = ref(false);
const hideTimeoutId = ref<ReturnType<typeof setTimeout> | null>(null);
const isTriggerClicking = ref(false);

const internalOpen = ref(props.defaultOpen);

// ============ 右键菜单位置状态 ============
const contextMenuPosition = ref<{ x: number; y: number } | null>(null);

const zIndex = useZIndex("popup");

// ============ 定位状态 ============
const contentPosition = ref({ top: 0, left: 0 });
const actualSide = ref<"top" | "bottom" | "left" | "right">("bottom");

const isOpen = computed({
    get: () => (props.open !== undefined ? props.open : internalOpen.value),
    set: (val) => {
        if (val) {
            shouldRenderPortal.value = true;
        }
        if (props.open === undefined) {
            internalOpen.value = val;
        }
        emit("update:open", val);
        emit("openChange", val);
    }
});

watch(
    isOpen,
    (open) => {
        if (hideTimeoutId.value) {
            clearTimeout(hideTimeoutId.value);
            hideTimeoutId.value = null;
        }
        if (open) {
            isAfterClosedHidden.value = false;
            nextTick(updatePosition);
            return;
        }
        if (!shouldDestroyOnHidden.value) {
            isAfterClosedHidden.value = false;
            hideTimeoutId.value = setTimeout(() => {
                if (!isOpen.value) {
                    isAfterClosedHidden.value = true;
                }
            }, 200);
        }
    },
    { immediate: true }
);

// ============ 提供上下文给子组件 ============
provide<VortDropdownContext>("vortDropdownContext", {
    close: () => {
        isOpen.value = false;
    }
});

// ============ 位置计算 ============
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

const updatePosition = () => {
    // 右键菜单模式：使用鼠标位置
    if (contextMenuPosition.value) {
        contentPosition.value = { top: contextMenuPosition.value.y, left: contextMenuPosition.value.x };
        actualSide.value = "bottom";
        return;
    }

    if (!triggerRef.value || !contentRef.value) return;

    const triggerRect = triggerRef.value.getBoundingClientRect();
    const contentEl = contentRef.value;
    const contentWidth = contentEl.offsetWidth;
    const contentHeight = contentEl.offsetHeight;
    const { side, align } = placementMap[props.placement];
    const gap = props.offset;

    let top = 0;
    let left = 0;
    let resolvedSide = side;

    // 根据 side 计算主轴
    if (side === "bottom") {
        top = triggerRect.bottom + gap;
    } else if (side === "top") {
        top = triggerRect.top - contentHeight - gap;
    } else if (side === "left") {
        left = triggerRect.left - contentWidth - gap;
    } else {
        left = triggerRect.right + gap;
    }

    // 根据 align 计算交叉轴
    if (side === "bottom" || side === "top") {
        if (align === "start") left = triggerRect.left;
        else if (align === "center") left = triggerRect.left + (triggerRect.width - contentWidth) / 2;
        else left = triggerRect.right - contentWidth;
    } else {
        if (align === "start") top = triggerRect.top;
        else if (align === "center") top = triggerRect.top + (triggerRect.height - contentHeight) / 2;
        else top = triggerRect.bottom - contentHeight;
    }

    // 碰撞检测 - 翻转
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const padding = 8;

    if (resolvedSide === "bottom" && top + contentHeight > vh - padding) {
        const flipped = triggerRect.top - contentHeight - gap;
        if (flipped >= padding) {
            top = flipped;
            resolvedSide = "top";
        }
    } else if (resolvedSide === "top" && top < padding) {
        const flipped = triggerRect.bottom + gap;
        if (flipped + contentHeight <= vh - padding) {
            top = flipped;
            resolvedSide = "bottom";
        }
    } else if (resolvedSide === "left" && left < padding) {
        const flipped = triggerRect.right + gap;
        if (flipped + contentWidth <= vw - padding) {
            left = flipped;
            resolvedSide = "right";
        }
    } else if (resolvedSide === "right" && left + contentWidth > vw - padding) {
        const flipped = triggerRect.left - contentWidth - gap;
        if (flipped >= padding) {
            left = flipped;
            resolvedSide = "left";
        }
    }

    // 确保不超出左右边界
    left = Math.max(padding, Math.min(left, vw - contentWidth - padding));
    top = Math.max(padding, Math.min(top, vh - contentHeight - padding));

    contentPosition.value = { top, left };
    actualSide.value = resolvedSide;
};

// ============ 动画结束处理 ============
const handleAnimationEnd = () => {
    if (!isOpen.value) {
        if (shouldDestroyOnHidden.value) {
            shouldRenderPortal.value = false;
        } else {
            isAfterClosedHidden.value = true;
        }
        contextMenuPosition.value = null;
    }
};

// ============ 触发方式 ============
const triggers = computed(() => {
    const t = props.trigger;
    return Array.isArray(t) ? t : [t];
});

const hasHoverTrigger = computed(() => triggers.value.includes("hover"));
const hasClickTrigger = computed(() => triggers.value.includes("click"));
const hasContextMenuTrigger = computed(() => triggers.value.includes("contextMenu"));

const showArrow = computed(() => !!props.arrow);

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

const contentStyle = computed(() => ({
    ...props.overlayStyle,
    position: "fixed" as const,
    top: `${contentPosition.value.top}px`,
    left: `${contentPosition.value.left}px`,
    zIndex: zIndex.value
}));

// ============ 事件处理 ============
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

const handleMouseEnter = () => {
    if (!hasHoverTrigger.value || props.disabled) return;
    if (leaveTimeoutId.value) {
        clearTimeout(leaveTimeoutId.value);
        leaveTimeoutId.value = null;
    }
    isHovered.value = true;
    enterTimeoutId.value = setTimeout(() => {
        if (isHovered.value) {
            isOpen.value = true;
        }
    }, props.mouseEnterDelay);
};

const handleMouseLeave = () => {
    if (!hasHoverTrigger.value || props.disabled) return;
    if (enterTimeoutId.value) {
        clearTimeout(enterTimeoutId.value);
        enterTimeoutId.value = null;
    }
    isHovered.value = false;
    leaveTimeoutId.value = setTimeout(() => {
        if (!isHovered.value) {
            isOpen.value = false;
        }
    }, props.mouseLeaveDelay);
};

const handleContentMouseEnter = () => {
    if (!hasHoverTrigger.value) return;
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

const handleTriggerClick = (e: MouseEvent) => {
    if (props.disabled) return;

    if (hasHoverTrigger.value && !hasClickTrigger.value) {
        isTriggerClicking.value = true;
        nextTick(() => {
            isTriggerClicking.value = false;
        });
        return;
    }

    if (hasClickTrigger.value) {
        e.preventDefault();
        contextMenuPosition.value = null;
        isOpen.value = !isOpen.value;
    }

    if (hasContextMenuTrigger.value && !hasClickTrigger.value) {
        e.preventDefault();
        e.stopPropagation();
    }
};

const handleContextMenu = (e: MouseEvent) => {
    if (!hasContextMenuTrigger.value || props.disabled) return;
    e.preventDefault();
    contextMenuPosition.value = { x: e.clientX, y: e.clientY };
    if (isOpen.value) {
        nextTick(updatePosition);
        return;
    }
    isOpen.value = true;
};

// ============ 键盘导航 ============
const getMenuItems = (): HTMLElement[] => {
    if (!contentRef.value) return [];
    return Array.from(
        contentRef.value.querySelectorAll<HTMLElement>('[role="menuitem"]:not([data-disabled]), [role="menuitemcheckbox"]:not([data-disabled]), [role="menuitemradio"]:not([data-disabled])')
    );
};

const handleContentKeydown = (e: KeyboardEvent) => {
    const items = getMenuItems();
    if (!items.length) return;

    const currentIndex = items.indexOf(document.activeElement as HTMLElement);

    switch (e.key) {
        case "ArrowDown": {
            e.preventDefault();
            const next = currentIndex < items.length - 1 ? currentIndex + 1 : 0;
            items[next]?.focus();
            break;
        }
        case "ArrowUp": {
            e.preventDefault();
            const prev = currentIndex > 0 ? currentIndex - 1 : items.length - 1;
            items[prev]?.focus();
            break;
        }
        case "Home":
            e.preventDefault();
            items[0]?.focus();
            break;
        case "End":
            e.preventDefault();
            items[items.length - 1]?.focus();
            break;
        case "Escape":
            e.preventDefault();
            isOpen.value = false;
            triggerRef.value?.focus();
            break;
    }
};

// ============ 点击外部关闭（不拦截事件，不使用遮罩层） ============
const handleDocumentMouseDown = (e: MouseEvent) => {
    if (!isOpen.value) return;
    const target = e.target as Node;
    if (triggerRef.value?.contains(target) || contentRef.value?.contains(target)) return;
    isOpen.value = false;
};

// ============ 滚动/resize 更新位置 ============
const handleScrollOrResize = () => {
    if (isOpen.value) updatePosition();
};

// ============ 生命周期 ============
onMounted(() => {
    document.addEventListener("mousedown", handleDocumentMouseDown);
    window.addEventListener("scroll", handleScrollOrResize, true);
    window.addEventListener("resize", handleScrollOrResize);
});

onBeforeUnmount(() => {
    document.removeEventListener("mousedown", handleDocumentMouseDown);
    window.removeEventListener("scroll", handleScrollOrResize, true);
    window.removeEventListener("resize", handleScrollOrResize);
    clearAllTimers();
    if (hideTimeoutId.value) {
        clearTimeout(hideTimeoutId.value);
        hideTimeoutId.value = null;
    }
});

// ============ 暴露方法 ============
defineExpose({
    open: () => {
        if (!props.disabled) {
            isOpen.value = true;
        }
    },
    close: () => {
        isOpen.value = false;
    }
});
</script>

<template>
    <span ref="triggerRef" :class="triggerClasses" @click="handleTriggerClick" @contextmenu="handleContextMenu" @mouseenter="handleMouseEnter" @mouseleave="handleMouseLeave">
        <slot />
    </span>

    <Teleport v-if="shouldRenderPortal" :to="popupContainer">
        <div
            v-show="!isAfterClosedHidden"
            ref="contentRef"
            :class="contentClasses"
            :style="contentStyle"
            :data-state="isOpen ? 'open' : 'closed'"
            :data-side="actualSide"
            data-slot="dropdown-content"
            role="menu"
            tabindex="-1"
            @mouseenter="handleContentMouseEnter"
            @mouseleave="handleContentMouseLeave"
            @animationend="handleAnimationEnd"
            @keydown="handleContentKeydown"
        >
            <slot name="overlay" />

            <div
                v-if="showArrow"
                class="vort-dropdown-arrow"
                :style="{
                    position: 'absolute',
                    [actualSide === 'bottom' ? 'top' : actualSide === 'top' ? 'bottom' : actualSide === 'left' ? 'right' : 'left']: '-6px',
                    left: actualSide === 'bottom' || actualSide === 'top' ? '50%' : undefined,
                    top: actualSide === 'left' || actualSide === 'right' ? '50%' : undefined,
                    transform: 'translate(-50%, 0)'
                }"
            >
                <svg width="12" height="6" viewBox="0 0 12 6" fill="#fff">
                    <path
                        :d="actualSide === 'bottom' ? 'M0 6L6 0L12 6' : actualSide === 'top' ? 'M0 0L6 6L12 0' : actualSide === 'left' ? 'M0 0L6 6L0 12' : 'M6 0L0 6L6 12'"
                    />
                </svg>
            </div>
        </div>
    </Teleport>
</template>
