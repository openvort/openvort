<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from "vue";

defineOptions({ name: "VortScrollbar" });

/** Vort Scrollbar - 自定义滚动条组件 */

interface Props {
    /** 滚动条高度 */
    height?: string | number;
    /** 滚动条最大高度 */
    maxHeight?: string | number;
    /** 是否使用原生滚动条样式 */
    native?: boolean;
    /** 包裹容器的自定义样式 */
    wrapStyle?: string | Record<string, string>;
    /** 包裹容器的自定义类名 */
    wrapClass?: string;
    /** 视图的自定义样式 */
    viewStyle?: string | Record<string, string>;
    /** 视图的自定义类名 */
    viewClass?: string;
    /** 不响应容器尺寸变化，如果容器尺寸不会发生变化，最好设置它可以优化性能 */
    noresize?: boolean;
    /** 视图的元素标签 */
    tag?: string;
    /** 滚动条总是显示 */
    always?: boolean;
    /** 滚动条最小尺寸 */
    minSize?: number;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    native: false,
    tag: "div",
    always: false,
    minSize: 20
});

const emit = defineEmits<{
    /** 滚动时触发 */
    scroll: [params: { scrollTop: number; scrollLeft: number }];
}>();

// DOM 引用
const scrollbarRef = ref<HTMLElement | null>(null);
const wrapRef = ref<HTMLElement | null>(null);
const resizeRef = ref<HTMLElement | null>(null);

// 滚动条状态
const sizeWidth = ref("0");
const sizeHeight = ref("0");
const moveX = ref(0);
const moveY = ref(0);
const ratioX = ref(1);
const ratioY = ref(1);

// 滚动条显示状态
const visible = ref(false);
let cursorDown = false;
let cursorLeave = false;

// 拖拽状态
const barState = ref({
    X: 0,
    Y: 0
});

// 计算样式
const wrapStyleComputed = computed(() => {
    const style: Record<string, string> = {};

    if (props.height) {
        style.height = typeof props.height === "number" ? `${props.height}px` : props.height;
    }

    if (props.maxHeight) {
        style.maxHeight = typeof props.maxHeight === "number" ? `${props.maxHeight}px` : props.maxHeight;
    }

    if (typeof props.wrapStyle === "string") {
        // 解析字符串样式
        const styleStr = props.wrapStyle;
        if (styleStr) {
            styleStr.split(";").forEach((item) => {
                const [key, value] = item.split(":").map((s) => s.trim());
                if (key && value) {
                    style[key] = value;
                }
            });
        }
    } else if (props.wrapStyle) {
        Object.assign(style, props.wrapStyle);
    }

    return style;
});

const viewStyleComputed = computed(() => {
    if (typeof props.viewStyle === "string") {
        const style: Record<string, string> = {};
        const styleStr = props.viewStyle;
        if (styleStr) {
            styleStr.split(";").forEach((item) => {
                const [key, value] = item.split(":").map((s) => s.trim());
                if (key && value) {
                    style[key] = value;
                }
            });
        }
        return style;
    }
    return props.viewStyle || {};
});

// 计算滚动条尺寸
const calculateSize = () => {
    if (!wrapRef.value) return;

    const wrap = wrapRef.value;

    // 计算垂直滚动条
    const heightPercentage = (wrap.clientHeight * 100) / wrap.scrollHeight;
    const widthPercentage = (wrap.clientWidth * 100) / wrap.scrollWidth;

    sizeHeight.value = heightPercentage < 100 ? `${Math.max(heightPercentage, (props.minSize / wrap.clientHeight) * 100)}%` : "";
    sizeWidth.value = widthPercentage < 100 ? `${Math.max(widthPercentage, (props.minSize / wrap.clientWidth) * 100)}%` : "";

    // 计算比例
    ratioY.value =
        parseFloat(sizeHeight.value) / 100 !== 0
            ? (wrap.clientHeight - parseFloat(sizeHeight.value) * 0.01 * wrap.clientHeight) / (wrap.scrollHeight - wrap.clientHeight)
            : 1;
    ratioX.value =
        parseFloat(sizeWidth.value) / 100 !== 0
            ? (wrap.clientWidth - parseFloat(sizeWidth.value) * 0.01 * wrap.clientWidth) / (wrap.scrollWidth - wrap.clientWidth)
            : 1;
};

// 处理滚动事件
const handleScroll = () => {
    if (!wrapRef.value) return;

    const wrap = wrapRef.value;
    const { scrollTop, scrollLeft } = wrap;

    moveY.value = scrollTop * ratioY.value;
    moveX.value = scrollLeft * ratioX.value;

    emit("scroll", { scrollTop, scrollLeft });
};

// 滚动到指定位置
const scrollTo = (options: ScrollToOptions | number, yCoord?: number) => {
    if (!wrapRef.value) return;

    if (typeof options === "number") {
        wrapRef.value.scrollTo(options, yCoord ?? 0);
    } else {
        wrapRef.value.scrollTo(options);
    }
};

// 设置滚动位置
const setScrollTop = (value: number) => {
    if (!wrapRef.value) return;
    wrapRef.value.scrollTop = value;
};

const setScrollLeft = (value: number) => {
    if (!wrapRef.value) return;
    wrapRef.value.scrollLeft = value;
};

// 更新滚动条状态
const update = () => {
    calculateSize();
};

// 鼠标进入显示滚动条
const handleMouseEnter = () => {
    cursorLeave = false;
    visible.value = true;
    calculateSize();
};

// 鼠标离开隐藏滚动条
const handleMouseLeave = () => {
    cursorLeave = true;
    if (!cursorDown) {
        visible.value = false;
    }
};

// 垂直滚动条拖拽
const handleThumbMouseDownY = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    cursorDown = true;
    document.addEventListener("mousemove", handleThumbMoveY);
    document.addEventListener("mouseup", handleThumbMouseUp);

    barState.value.Y = e.clientY - (e.currentTarget as HTMLElement).getBoundingClientRect().top;
};

const handleThumbMoveY = (e: MouseEvent) => {
    if (!wrapRef.value || !scrollbarRef.value) return;

    const wrap = wrapRef.value;
    const scrollbar = scrollbarRef.value;

    // 计算滑块在轨道上的偏移量
    const offset = e.clientY - scrollbar.getBoundingClientRect().top - barState.value.Y;
    const thumbHeight = (parseFloat(sizeHeight.value) / 100) * wrap.clientHeight;
    const maxOffset = wrap.clientHeight - thumbHeight;

    // 将滑块偏移量转换为滚动距离
    // offset / maxOffset = scrollTop / maxScrollTop
    const maxScrollTop = wrap.scrollHeight - wrap.clientHeight;
    const scrollTop = (Math.min(Math.max(0, offset), maxOffset) / maxOffset) * maxScrollTop;

    wrap.scrollTop = scrollTop;
};

// 水平滚动条拖拽
const handleThumbMouseDownX = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    cursorDown = true;
    document.addEventListener("mousemove", handleThumbMoveX);
    document.addEventListener("mouseup", handleThumbMouseUp);

    barState.value.X = e.clientX - (e.currentTarget as HTMLElement).getBoundingClientRect().left;
};

const handleThumbMoveX = (e: MouseEvent) => {
    if (!wrapRef.value || !scrollbarRef.value) return;

    const wrap = wrapRef.value;
    const scrollbar = scrollbarRef.value;

    // 计算滑块在轨道上的偏移量
    const offset = e.clientX - scrollbar.getBoundingClientRect().left - barState.value.X;
    const thumbWidth = (parseFloat(sizeWidth.value) / 100) * wrap.clientWidth;
    const maxOffset = wrap.clientWidth - thumbWidth;

    // 将滑块偏移量转换为滚动距离
    // offset / maxOffset = scrollLeft / maxScrollLeft
    const maxScrollLeft = wrap.scrollWidth - wrap.clientWidth;
    const scrollLeft = (Math.min(Math.max(0, offset), maxOffset) / maxOffset) * maxScrollLeft;

    wrap.scrollLeft = scrollLeft;
};

// 鼠标释放
const handleThumbMouseUp = () => {
    cursorDown = false;
    document.removeEventListener("mousemove", handleThumbMoveY);
    document.removeEventListener("mousemove", handleThumbMoveX);
    document.removeEventListener("mouseup", handleThumbMouseUp);

    if (cursorLeave) {
        visible.value = false;
    }
};

// 点击轨道跳转
const handleTrackClickY = (e: MouseEvent) => {
    if (!wrapRef.value) return;

    const target = e.target as HTMLElement;
    if (target.classList.contains("vort-scrollbar__thumb")) return;

    const wrap = wrapRef.value;
    const track = target.getBoundingClientRect();
    const thumbHeight = (parseFloat(sizeHeight.value) / 100) * wrap.clientHeight;
    const offset = e.clientY - track.top - thumbHeight / 2;
    const maxOffset = wrap.clientHeight - thumbHeight;

    const maxScrollTop = wrap.scrollHeight - wrap.clientHeight;
    const scrollTop = (Math.min(Math.max(0, offset), maxOffset) / maxOffset) * maxScrollTop;
    wrap.scrollTop = scrollTop;
};

const handleTrackClickX = (e: MouseEvent) => {
    if (!wrapRef.value) return;

    const target = e.target as HTMLElement;
    if (target.classList.contains("vort-scrollbar__thumb")) return;

    const wrap = wrapRef.value;
    const track = target.getBoundingClientRect();
    const thumbWidth = (parseFloat(sizeWidth.value) / 100) * wrap.clientWidth;
    const offset = e.clientX - track.left - thumbWidth / 2;
    const maxOffset = wrap.clientWidth - thumbWidth;

    const maxScrollLeft = wrap.scrollWidth - wrap.clientWidth;
    const scrollLeft = (Math.min(Math.max(0, offset), maxOffset) / maxOffset) * maxScrollLeft;
    wrap.scrollLeft = scrollLeft;
};

// ResizeObserver
let resizeObserver: ResizeObserver | null = null;

onMounted(() => {
    nextTick(() => {
        calculateSize();
    });

    if (!props.noresize && wrapRef.value) {
        resizeObserver = new ResizeObserver(() => {
            calculateSize();
        });
        resizeObserver.observe(wrapRef.value);

        if (resizeRef.value) {
            resizeObserver.observe(resizeRef.value);
        }
    }
});

onUnmounted(() => {
    if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
    }
    document.removeEventListener("mousemove", handleThumbMoveY);
    document.removeEventListener("mousemove", handleThumbMoveX);
    document.removeEventListener("mouseup", handleThumbMouseUp);
});

// 暴露方法
defineExpose({
    /** 处理滚动事件 */
    handleScroll,
    /** 滚动到指定位置 */
    scrollTo,
    /** 设置滚动条到顶部的距离 */
    setScrollTop,
    /** 设置滚动条到左边的距离 */
    setScrollLeft,
    /** 手动更新滚动条状态 */
    update,
    /** 滚动条包裹的 ref 对象 */
    wrapRef
});
</script>

<template>
    <div ref="scrollbarRef" :class="['vort-scrollbar', props.class]" @mouseenter="handleMouseEnter" @mouseleave="handleMouseLeave">
        <div
            ref="wrapRef"
            :class="['vort-scrollbar__wrap', { 'vort-scrollbar__wrap--native': native }, wrapClass]"
            :style="wrapStyleComputed"
            @scroll="handleScroll"
        >
            <component :is="tag" ref="resizeRef" :class="['vort-scrollbar__view', viewClass]" :style="viewStyleComputed">
                <slot />
            </component>
        </div>

        <!-- 自定义滚动条 -->
        <template v-if="!native">
            <!-- 垂直滚动条 -->
            <Transition name="vort-scrollbar-fade">
                <div v-show="(always || visible) && sizeHeight" class="vort-scrollbar__bar vort-scrollbar__bar--vertical" @click="handleTrackClickY">
                    <div
                        class="vort-scrollbar__thumb"
                        :style="{
                            height: sizeHeight,
                            transform: `translateY(${moveY}px)`
                        }"
                        @mousedown="handleThumbMouseDownY"
                    />
                </div>
            </Transition>

            <!-- 水平滚动条 -->
            <Transition name="vort-scrollbar-fade">
                <div v-show="(always || visible) && sizeWidth" class="vort-scrollbar__bar vort-scrollbar__bar--horizontal" @click="handleTrackClickX">
                    <div
                        class="vort-scrollbar__thumb"
                        :style="{
                            width: sizeWidth,
                            transform: `translateX(${moveX}px)`
                        }"
                        @mousedown="handleThumbMouseDownX"
                    />
                </div>
            </Transition>
        </template>
    </div>
</template>

<style scoped>
.vort-scrollbar {
    position: relative;
    overflow: hidden;
    height: 100%;
}

.vort-scrollbar__wrap {
    overflow: auto;
    height: 100%;
    scrollbar-width: none; /* Firefox */
    -ms-overflow-style: none; /* IE/Edge */
}

.vort-scrollbar__wrap::-webkit-scrollbar {
    display: none; /* Chrome/Safari/Opera */
}

.vort-scrollbar__wrap--native {
    scrollbar-width: auto;
    -ms-overflow-style: auto;
}

.vort-scrollbar__wrap--native::-webkit-scrollbar {
    display: block;
}

.vort-scrollbar__view {
    width: 100%;
    box-sizing: border-box;
}

/* 滚动条轨道 */
.vort-scrollbar__bar {
    position: absolute;
    z-index: 1;
    border-radius: var(--vort-border-radius-sm, 4px);
}

/* 垂直滚动条 */
.vort-scrollbar__bar--vertical {
    top: 0;
    right: 2px;
    bottom: 0;
    width: 6px;
}

/* 水平滚动条 */
.vort-scrollbar__bar--horizontal {
    left: 0;
    right: 0;
    bottom: 2px;
    height: 6px;
}

/* 滚动条滑块 */
.vort-scrollbar__thumb {
    position: relative;
    display: block;
    border-radius: var(--vort-border-radius-sm, 4px);
    background-color: rgba(0, 0, 0, 0.15);
    cursor: pointer;
    transition: background-color 0.2s;
}

.vort-scrollbar__thumb:hover {
    background-color: rgba(0, 0, 0, 0.3);
}

.vort-scrollbar__thumb:active {
    background-color: rgba(0, 0, 0, 0.4);
}

.vort-scrollbar__bar--vertical .vort-scrollbar__thumb {
    width: 100%;
    min-height: 20px;
}

.vort-scrollbar__bar--horizontal .vort-scrollbar__thumb {
    height: 100%;
    min-width: 20px;
}

/* 淡入淡出动画 */
.vort-scrollbar-fade-enter-active,
.vort-scrollbar-fade-leave-active {
    transition: opacity 0.2s ease;
}

.vort-scrollbar-fade-enter-from,
.vort-scrollbar-fade-leave-to {
    opacity: 0;
}
</style>
