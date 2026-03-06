<script setup lang="ts">
import { computed, useSlots } from "vue";

defineOptions({ name: "VortBadge" });

/** Vort Badge - 徽标组件 */

// 预设状态颜色
type PresetStatusColor = "success" | "processing" | "default" | "error" | "warning";

// 预设颜色
type PresetColor = "pink" | "red" | "yellow" | "orange" | "cyan" | "green" | "blue" | "purple" | "geekblue" | "magenta" | "volcano" | "gold" | "lime";

interface Props {
    /** 展示的数字，为 0 时默认不显示 */
    count?: number | string;
    /** 当数值为 0 时，是否展示 Badge */
    showZero?: boolean;
    /** 展示封顶的数字值 */
    overflowCount?: number;
    /** 不展示数字，只有一个小红点 */
    dot?: boolean;
    /** 设置 Badge 为状态点 */
    status?: PresetStatusColor;
    /** 自定义小圆点的颜色（当设置 status 或 dot 时有效） */
    color?: PresetColor | string;
    /** 在设置了 status 或 color 的前提下有效，设置状态点的文本 */
    text?: string;
    /** 设置状态点的位置偏移 [x, y] */
    offset?: [number, number];
    /** 设置鼠标放在状态点上时显示的文字 */
    title?: string;
    /** 徽标大小 */
    size?: "default" | "small";
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    showZero: false,
    overflowCount: 99,
    dot: false,
    size: "default"
});

// 定义插槽类型
defineSlots<{
    /** 默认插槽，徽标依附的内容 */
    default?: () => unknown;
    /** 自定义 count 显示内容 */
    count?: () => unknown;
}>();

const slots = useSlots();

// 预设状态颜色映射
const presetStatusColorMap: Record<PresetStatusColor, string> = {
    success: "#52c41a",
    processing: "var(--vort-primary, #1456f0)",
    default: "#d9d9d9",
    error: "#ff4d4f",
    warning: "#faad14"
};

// 预设颜色映射
const presetColorMap: Record<PresetColor, string> = {
    pink: "#eb2f96",
    red: "#f5222d",
    yellow: "#fadb14",
    orange: "#fa8c16",
    cyan: "#13c2c2",
    green: "#52c41a",
    blue: "#1677ff",
    purple: "#722ed1",
    geekblue: "#2f54eb",
    magenta: "#eb2f96",
    volcano: "#fa541c",
    gold: "#faad14",
    lime: "#a0d911"
};

// 检查是否是预设状态颜色
const isPresetStatusColor = (color: string | undefined): color is PresetStatusColor => {
    return color !== undefined && Object.keys(presetStatusColorMap).includes(color);
};

// 检查是否是预设颜色
const isPresetColor = (color: string | undefined): color is PresetColor => {
    return color !== undefined && Object.keys(presetColorMap).includes(color);
};

// 获取实际颜色值
const getColorValue = (color: string | undefined) => {
    if (!color) return undefined;
    if (isPresetColor(color)) return presetColorMap[color];
    return color;
};

// 计算显示的数字
const displayCount = computed(() => {
    if (props.dot) return "";
    if (slots.count) return "";

    const count = typeof props.count === "string" ? props.count : props.count;
    if (count === undefined || count === null) return "";

    if (typeof count === "number") {
        if (count === 0 && !props.showZero) return "";
        if (count > props.overflowCount) return `${props.overflowCount}+`;
        return String(count);
    }

    return count;
});

// 是否显示徽标
const showBadge = computed(() => {
    if (props.dot) return true;
    if (slots.count) return true;
    if (props.count === undefined || props.count === null) return false;
    if (props.count === 0 && !props.showZero) return false;
    return true;
});

// 是否是状态点模式（无子元素时，status 或 color 生效）
const isStatusMode = computed(() => {
    return !slots.default && (props.status || props.color);
});

// 是否是独立模式（无子元素）
const isStandalone = computed(() => {
    return !slots.default;
});

// 徽标样式
const badgeStyle = computed(() => {
    const style: Record<string, string> = {};

    // 颜色
    if (props.color) {
        style.backgroundColor = getColorValue(props.color) || props.color;
    } else if (props.status) {
        style.backgroundColor = presetStatusColorMap[props.status];
    }

    // 偏移
    if (props.offset && !isStandalone.value) {
        style.right = `${-props.offset[0]}px`;
        style.marginTop = `${props.offset[1]}px`;
    }

    return style;
});

// 状态点样式
const statusDotStyle = computed(() => {
    const style: Record<string, string> = {};

    if (props.color) {
        style.backgroundColor = getColorValue(props.color) || props.color;
    } else if (props.status) {
        style.backgroundColor = presetStatusColorMap[props.status];
    }

    return style;
});

// ========== 类名计算 ==========

const badgeClasses = computed(() => {
    const classes: string[] = ["vort-badge-count"];
    if (props.size === "small") classes.push("vort-badge-count-small");
    if (props.dot) classes.push("vort-badge-dot");
    if (!props.color && !props.status) classes.push("vort-badge-count-default");
    return classes;
});

const wrapperClasses = computed(() => {
    const classes = ["vort-badge"];
    if (props.class) classes.push(props.class);
    return classes;
});

const statusWrapperClasses = computed(() => {
    const classes = ["vort-badge", "vort-badge-status"];
    if (props.class) classes.push(props.class);
    return classes;
});

const standaloneWrapperClasses = computed(() => {
    const classes = ["vort-badge", "vort-badge-standalone"];
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <!-- 状态点模式（无子元素，有 status 或 color） -->
    <span v-if="isStatusMode" :class="statusWrapperClasses">
        <span class="vort-badge-status-dot" :class="{ 'vort-badge-status-processing': status === 'processing' }" :style="statusDotStyle" :title="title" />
        <span v-if="text" class="vort-badge-status-text">{{ text }}</span>
    </span>

    <!-- 独立模式（无子元素，只有数字） -->
    <span v-else-if="isStandalone && showBadge" :class="standaloneWrapperClasses">
        <sup :class="badgeClasses" :style="badgeStyle" :title="title">
            <slot name="count">{{ displayCount }}</slot>
        </sup>
    </span>

    <!-- 正常模式（有子元素） -->
    <span v-else :class="wrapperClasses">
        <slot />
        <sup v-if="showBadge" :class="badgeClasses" :style="badgeStyle" :title="title">
            <slot name="count">{{ displayCount }}</slot>
        </sup>
    </span>
</template>

<style scoped>
.vort-badge {
    position: relative;
    display: inline-block;
    line-height: 1;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

.vort-badge-count {
    position: absolute;
    top: 0;
    right: 0;
    transform: translate(50%, -50%);
    transform-origin: 100% 0%;
    z-index: auto;
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    font-size: 12px;
    font-weight: 400;
    line-height: 20px;
    white-space: nowrap;
    text-align: center;
    border-radius: 10px;
    box-shadow: 0 0 0 1px #fff;
    color: #fff;
}

.vort-badge-count-default {
    background-color: #ff4d4f;
}

.vort-badge-count-small {
    min-width: 14px;
    height: 14px;
    padding: 0 4px;
    font-size: 10px;
    line-height: 14px;
    border-radius: 7px;
}

.vort-badge-dot {
    min-width: 6px;
    width: 6px;
    height: 6px;
    padding: 0;
    font-size: 0;
    border-radius: 50%;
}

/* 独立模式（无子元素） */
.vort-badge-standalone .vort-badge-count {
    position: relative;
    top: auto;
    right: auto;
    transform: none;
    display: block;
}

/* 状态点模式 */
.vort-badge-status {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    line-height: inherit;
}

.vort-badge-status-dot {
    position: relative;
    top: -1px;
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    vertical-align: middle;
}

.vort-badge-status-processing {
    overflow: visible;
}

.vort-badge-status-processing::after {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 100%;
    height: 100%;
    border: 1px solid currentColor;
    border-radius: 50%;
    animation: vort-badge-status-processing 1.2s infinite ease-in-out;
    content: "";
}

.vort-badge-status-text {
    font-size: var(--vort-font-size-sm, 14px);
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

@keyframes vort-badge-status-processing {
    0% {
        transform: translate(-50%, -50%) scale(0.8);
        opacity: 0.5;
    }
    100% {
        transform: translate(-50%, -50%) scale(2.4);
        opacity: 0;
    }
}
</style>
