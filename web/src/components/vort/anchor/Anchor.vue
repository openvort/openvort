<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, provide, watch, nextTick } from "vue";

defineOptions({ name: "VortAnchor" });

/** Vort Anchor - 锚点组件 */

type AnchorDirection = "vertical" | "horizontal";

interface Props {
    /** 滚动容器，CSS 选择器或 HTMLElement */
    container?: string | HTMLElement;
    /** 设置锚点滚动的偏移量 */
    offset?: number;
    /** 触发锚点的元素边界值 */
    bound?: number;
    /** 容器滚动持续时间（毫秒） */
    duration?: number;
    /** 是否显示标记 */
    marker?: boolean;
    /** 锚点类型 */
    type?: "default" | "underline";
    /** 锚点方向 */
    direction?: AnchorDirection;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    offset: 0,
    bound: 15,
    duration: 300,
    marker: true,
    type: "default",
    direction: "vertical"
});

const emit = defineEmits<{
    /** 锚点链接变化时触发 */
    change: [href: string, prevHref: string];
    /** 点击锚点链接时触发 */
    click: [e: MouseEvent, href: string];
}>();

// 当前激活的锚点
const activeLink = ref<string>("");
// 锚点链接列表
const links = ref<string[]>([]);
// 滚动容器
const scrollContainer = ref<HTMLElement | Window | null>(null);
// 标记位置和尺寸
const markerTop = ref(0);
const markerLeft = ref(0);
const markerWidth = ref(40);
// 锚点容器 ref
const anchorRef = ref<HTMLElement | null>(null);
// 点击滚动的目标锚点（用于点击时立即更新标记）
let clickTarget = "";

// 注册锚点链接
const registerLink = (href: string) => {
    if (!links.value.includes(href)) {
        links.value.push(href);
    }
};

// 取消注册锚点链接
const unregisterLink = (href: string) => {
    const index = links.value.indexOf(href);
    if (index > -1) {
        links.value.splice(index, 1);
    }
};

// 提供给子组件的上下文
provide("anchor", {
    activeLink,
    registerLink,
    unregisterLink,
    handleClick: handleLinkClick,
    direction: computed(() => props.direction)
});

// 获取滚动容器
const getContainer = (): HTMLElement | Window => {
    if (props.container) {
        if (typeof props.container === "string") {
            const container = document.querySelector(props.container);
            return container instanceof HTMLElement ? container : window;
        }
        return props.container;
    }
    return window;
};

// 获取元素距离视口顶部的距离
const getOffsetTop = (element: HTMLElement, container: HTMLElement | Window): number => {
    const rect = element.getBoundingClientRect();
    if (container === window) {
        return rect.top + window.scrollY;
    }
    const containerRect = (container as HTMLElement).getBoundingClientRect();
    return rect.top - containerRect.top + (container as HTMLElement).scrollTop;
};

// 获取当前激活的锚点
const getCurrentAnchor = (): string => {
    const container = scrollContainer.value;
    if (!container) return "";

    const scrollTop = container === window ? window.scrollY : (container as HTMLElement).scrollTop;

    let currentLink = "";
    let minDistance = Infinity;

    for (const href of links.value) {
        const targetId = href.startsWith("#") ? href.slice(1) : href;
        const targetElement = document.getElementById(targetId);

        if (targetElement) {
            const top = getOffsetTop(targetElement, container);
            const distance = top - scrollTop - props.offset - props.bound;

            // 找到最接近顶部且在视口内或刚超过的元素
            if (distance <= 0 && Math.abs(distance) < minDistance) {
                minDistance = Math.abs(distance);
                currentLink = href;
            }
        }
    }

    // 如果没有找到，返回第一个在视口内的链接
    if (!currentLink && links.value.length > 0) {
        for (const href of links.value) {
            const targetId = href.startsWith("#") ? href.slice(1) : href;
            const targetElement = document.getElementById(targetId);

            if (targetElement) {
                const top = getOffsetTop(targetElement, container);
                const distance = top - scrollTop - props.offset;

                if (distance >= -props.bound) {
                    currentLink = href;
                    break;
                }
            }
        }
    }

    return currentLink;
};

// 标记线尺寸
const MARKER_HEIGHT = 20;

// 更新标记位置（同步更新，不使用 nextTick）
const updateMarkerPosition = () => {
    if (!anchorRef.value || !activeLink.value || !props.marker) return;

    const activeItem = anchorRef.value.querySelector(`[data-href="${activeLink.value}"]`) as HTMLElement;

    if (!activeItem) return;

    // 使用 getBoundingClientRect 计算相对位置
    const anchorRect = anchorRef.value.getBoundingClientRect();
    const linkEl = activeItem.querySelector("a") as HTMLElement;

    if (props.direction === "vertical") {
        // 垂直方向：标记线垂直居中于链接文字
        if (linkEl) {
            const linkRect = linkEl.getBoundingClientRect();
            markerTop.value = linkRect.top - anchorRect.top + (linkRect.height - MARKER_HEIGHT) / 2;
        } else {
            const itemRect = activeItem.getBoundingClientRect();
            markerTop.value = itemRect.top - anchorRect.top + (itemRect.height - MARKER_HEIGHT) / 2;
        }
    } else {
        // 水平方向：标记线对齐链接文字，宽度跟随文字
        if (linkEl) {
            const linkRect = linkEl.getBoundingClientRect();
            markerLeft.value = linkRect.left - anchorRect.left;
            markerWidth.value = linkRect.width;
        } else {
            const itemRect = activeItem.getBoundingClientRect();
            markerLeft.value = itemRect.left - anchorRect.left;
            markerWidth.value = itemRect.width;
        }
    }
};

// 处理滚动 - 实时响应
const handleScroll = () => {
    // 如果有点击目标，优先使用点击目标
    if (clickTarget) return;

    const currentAnchor = getCurrentAnchor();
    if (currentAnchor && currentAnchor !== activeLink.value) {
        const prevHref = activeLink.value;
        activeLink.value = currentAnchor;
        emit("change", currentAnchor, prevHref);
        updateMarkerPosition();
    }
};

// 缓动函数
const easeInOutCubic = (t: number): number => {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
};

// 滚动到指定位置
const scrollTo = (href: string) => {
    const targetId = href.startsWith("#") ? href.slice(1) : href;
    const targetElement = document.getElementById(targetId);
    const container = scrollContainer.value;

    if (!targetElement || !container) return;

    // 立即更新激活状态和标记位置
    const prevHref = activeLink.value;
    clickTarget = href;
    activeLink.value = href;
    if (prevHref !== href) {
        emit("change", href, prevHref);
    }
    updateMarkerPosition();

    const startTime = Date.now();
    const startTop = container === window ? window.scrollY : (container as HTMLElement).scrollTop;
    const targetTop = getOffsetTop(targetElement, container) - props.offset;
    const distance = targetTop - startTop;

    const animate = () => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / props.duration, 1);
        const easeProgress = easeInOutCubic(progress);
        const currentTop = startTop + distance * easeProgress;

        if (container === window) {
            window.scrollTo(0, currentTop);
        } else {
            (container as HTMLElement).scrollTop = currentTop;
        }

        if (progress < 1) {
            requestAnimationFrame(animate);
        } else {
            // 滚动完成，清除点击目标
            clickTarget = "";
        }
    };

    requestAnimationFrame(animate);
};

// 点击锚点链接
function handleLinkClick(e: MouseEvent, href: string) {
    emit("click", e, href);
    scrollTo(href);
}

// 监听容器变化
watch(
    () => props.container,
    () => {
        if (scrollContainer.value) {
            scrollContainer.value.removeEventListener("scroll", handleScroll);
        }
        scrollContainer.value = getContainer();
        scrollContainer.value.addEventListener("scroll", handleScroll, { passive: true });
    },
    { immediate: false }
);

// 监听激活链接变化，更新标记位置
watch(activeLink, () => {
    updateMarkerPosition();
});

onMounted(() => {
    scrollContainer.value = getContainer();
    scrollContainer.value.addEventListener("scroll", handleScroll, { passive: true });

    // 初始化时获取当前激活锚点
    nextTick(() => {
        const hash = window.location.hash;
        if (hash && links.value.includes(hash)) {
            activeLink.value = hash;
        } else {
            activeLink.value = getCurrentAnchor();
        }
        updateMarkerPosition();
    });
});

onUnmounted(() => {
    if (scrollContainer.value) {
        scrollContainer.value.removeEventListener("scroll", handleScroll);
    }
});

// 暴露方法
defineExpose({
    /** 手动滚动到指定锚点 */
    scrollTo
});

// 组合样式
const classes = computed(() => {
    const arr = ["vort-anchor", `vort-anchor--${props.direction}`];
    if (props.type === "underline") arr.push("vort-anchor--underline");
    if (props.class) arr.push(props.class);
    return arr;
});
</script>

<template>
    <div ref="anchorRef" :class="classes">
        <!-- 标记线 -->
        <div
            v-if="marker && activeLink && type === 'default'"
            class="vort-anchor__marker"
            :style="
                direction === 'vertical' ? { transform: `translateY(${markerTop}px)` } : { transform: `translateX(${markerLeft}px)`, width: `${markerWidth}px` }
            "
        />
        <!-- 下划线标记 -->
        <div
            v-if="marker && activeLink && type === 'underline'"
            class="vort-anchor__underline-marker"
            :style="{ transform: `translateX(${markerLeft}px)`, width: `${markerWidth}px` }"
        />
        <!-- 锚点内容 -->
        <div class="vort-anchor__content">
            <slot />
        </div>
    </div>
</template>

<style scoped>
.vort-anchor {
    position: relative;
    font-size: 14px;
}

/* 垂直方向 */
.vort-anchor--vertical {
    padding-left: 2px;
}

.vort-anchor--vertical .vort-anchor__marker {
    position: absolute;
    left: 0;
    top: 0;
    width: 2px;
    height: 20px;
    background: var(--vort-primary);
    border-radius: 1px;
    transition: transform 0.15s cubic-bezier(0.4, 0, 0.2, 1);
}

.vort-anchor--vertical .vort-anchor__content {
    padding-left: 14px;
    border-left: 1px solid var(--vort-border-secondary);
}

/* 水平方向 */
.vort-anchor--horizontal {
    display: inline-flex;
}

.vort-anchor--horizontal .vort-anchor__content {
    display: flex;
    gap: 24px;
}

.vort-anchor--horizontal .vort-anchor__marker {
    position: absolute;
    bottom: 0;
    left: 0;
    height: 2px;
    background: var(--vort-primary);
    border-radius: 1px;
    transition:
        transform 0.15s cubic-bezier(0.4, 0, 0.2, 1),
        width 0.15s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 下划线类型 */
.vort-anchor--underline {
    border-bottom: 1px solid var(--vort-border-secondary);
}

.vort-anchor--underline .vort-anchor__underline-marker {
    position: absolute;
    bottom: -1px;
    left: 0;
    height: 2px;
    background: var(--vort-primary);
    border-radius: 1px;
    transition:
        transform 0.15s cubic-bezier(0.4, 0, 0.2, 1),
        width 0.15s cubic-bezier(0.4, 0, 0.2, 1);
}
</style>
