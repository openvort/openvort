import { ref, computed, onMounted, onUnmounted, nextTick, type Ref } from "vue";

/**
 * 浮层定位方向
 */
export type FloatingPlacement =
    | "top"
    | "topLeft"
    | "topRight"
    | "bottom"
    | "bottomLeft"
    | "bottomRight"
    | "left"
    | "leftTop"
    | "leftBottom"
    | "right"
    | "rightTop"
    | "rightBottom";

/**
 * 触发方式
 */
export type FloatingTrigger = "click" | "hover" | "focus" | "contextMenu" | "manual";

/**
 * useFloating 配置选项
 */
export interface UseFloatingOptions {
    /** 初始显示状态 */
    defaultOpen?: boolean;
    /** 受控的显示状态 */
    open?: Ref<boolean | undefined>;
    /** 定位方向 */
    placement?: FloatingPlacement;
    /** 触发方式 */
    trigger?: FloatingTrigger;
    /** 是否禁用 */
    disabled?: boolean;
    /** 显示/隐藏延迟 (hover 模式下) */
    mouseEnterDelay?: number;
    mouseLeaveDelay?: number;
    /** 间距（箭头尖端到触发元素的距离） */
    gap?: number;
    /** 箭头高度 */
    arrowHeight?: number;
    /** 状态变化回调 */
    onOpenChange?: (open: boolean) => void;
}

/**
 * 浮层定位 Composable
 *
 * 从 Popconfirm 抽取的通用浮层定位逻辑，支持：
 * - 12 种定位方向
 * - 边界检测和自动翻转
 * - 箭头定位
 * - 动画 transform-origin 计算
 * - 点击外部关闭
 * - 滚动/resize 自动更新位置
 */
export function useFloating(options: UseFloatingOptions = {}) {
    const {
        defaultOpen = false,
        open: controlledOpen,
        placement: initialPlacement = "top",
        trigger = "click",
        disabled = false,
        mouseEnterDelay = 100,
        mouseLeaveDelay = 100,
        gap = 8,
        arrowHeight = 6,
        onOpenChange
    } = options;

    // 状态
    const visible = ref(defaultOpen);
    const triggerRef = ref<HTMLElement | null>(null);
    const floatingRef = ref<HTMLElement | null>(null);
    const position = ref({ top: 0, left: 0 });
    const arrowPosition = ref({ top: "", left: "", right: "", bottom: "" });
    const actualPlacement = ref<FloatingPlacement>(initialPlacement);

    // hover 延迟定时器
    let enterTimer: ReturnType<typeof setTimeout> | null = null;
    let leaveTimer: ReturnType<typeof setTimeout> | null = null;

    // 受控模式同步
    const isControlled = computed(() => controlledOpen?.value !== undefined);

    const isOpen = computed(() => {
        if (isControlled.value) {
            return controlledOpen!.value;
        }
        return visible.value;
    });

    // 计算位置
    const updatePosition = async () => {
        await nextTick();
        if (!triggerRef.value || !floatingRef.value) return;

        const triggerRect = triggerRef.value.getBoundingClientRect();
        const floatingWidth = floatingRef.value.offsetWidth;
        const floatingHeight = floatingRef.value.offsetHeight;
        // 使用 fixed 定位时不需要 scroll 偏移，因为 getBoundingClientRect 已经是相对视口的
        const totalGap = gap + arrowHeight;

        let top = 0;
        let left = 0;
        let placement = initialPlacement;

        // 根据 placement 计算位置
        const calcPosition = (p: FloatingPlacement) => {
            let t = 0;
            let l = 0;

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

            return { top: t, left: l };
        };

        // 计算初始位置
        const pos = calcPosition(placement);
        top = pos.top;
        left = pos.left;

        // 边界检测和自动翻转
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

        // 确保不超出左右边界
        left = Math.max(8, Math.min(left, viewportWidth - floatingWidth - 8));

        actualPlacement.value = placement;
        position.value = { top, left };

        // 更新箭头位置
        updateArrowPosition(placement, triggerRect, floatingWidth, floatingHeight);
    };

    // 更新箭头位置
    const updateArrowPosition = (placement: FloatingPlacement, triggerRect: DOMRect, floatingWidth: number, floatingHeight: number) => {
        const arrowOffset = arrowHeight;
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
        if (disabled) return;
        visible.value = true;
        onOpenChange?.(true);
        nextTick(updatePosition);
    };

    const hide = () => {
        visible.value = false;
        onOpenChange?.(false);
    };

    const toggle = () => {
        if (isOpen.value) {
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

    // 触发器事件处理
    const triggerHandlers = computed(() => {
        const handlers: Record<string, (e: Event) => void> = {};

        if (trigger === "click") {
            handlers.onClick = () => toggle();
        } else if (trigger === "hover") {
            handlers.onMouseenter = () => {
                clearTimers();
                enterTimer = setTimeout(show, mouseEnterDelay);
            };
            handlers.onMouseleave = () => {
                clearTimers();
                leaveTimer = setTimeout(hide, mouseLeaveDelay);
            };
        } else if (trigger === "focus") {
            handlers.onFocus = () => show();
            handlers.onBlur = () => hide();
        } else if (trigger === "contextMenu") {
            handlers.onContextmenu = (e: Event) => {
                e.preventDefault();
                toggle();
            };
        }

        return handlers;
    });

    // 浮层事件处理 (hover 模式下保持显示)
    const floatingHandlers = computed(() => {
        if (trigger !== "hover") return {};

        return {
            onMouseenter: () => {
                clearTimers();
            },
            onMouseleave: () => {
                clearTimers();
                leaveTimer = setTimeout(hide, mouseLeaveDelay);
            }
        };
    });

    // 点击外部关闭
    const handleClickOutside = (e: MouseEvent) => {
        if (!isOpen.value) return;
        if (trigger !== "click" && trigger !== "contextMenu") return;

        const target = e.target as Node;
        if (triggerRef.value?.contains(target) || floatingRef.value?.contains(target)) {
            return;
        }
        hide();
    };

    // 滚动/resize 时更新位置
    const handleScroll = () => {
        if (isOpen.value) {
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
    });

    return {
        // Refs
        triggerRef,
        floatingRef,

        // 状态
        isOpen,
        visible,
        position,
        arrowPosition,
        actualPlacement,

        // 计算属性
        arrowDirectionClass,
        transformOrigin,

        // 方法
        show,
        hide,
        toggle,
        updatePosition,

        // 事件处理器
        triggerHandlers,
        floatingHandlers
    };
}

export type UseFloatingReturn = ReturnType<typeof useFloating>;
