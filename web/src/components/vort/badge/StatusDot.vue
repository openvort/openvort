<script setup lang="ts">
import { computed } from "vue";

defineOptions({ name: "VortStatusDot" });

/**
 * Vort StatusDot - 状态点组件
 *
 * 用于表示状态的小圆点。
 *
 * - 支持预设状态颜色：success、processing、default、error、warning
 * - 支持自定义颜色
 * - 支持发光动画效果（pulse 参数）
 * - 可选配文字说明
 */

// 预设状态颜色
type PresetStatusColor = "success" | "processing" | "default" | "error" | "warning";

// 预设颜色
type PresetColor = "pink" | "red" | "yellow" | "orange" | "cyan" | "green" | "blue" | "purple" | "geekblue" | "magenta" | "volcano" | "gold" | "lime";

interface Props {
    /** 设置状态点的状态 */
    status?: PresetStatusColor;
    /** 自定义小圆点的颜色 */
    color?: PresetColor | string;
    /** 状态点的文本说明 */
    text?: string;
    /** 是否开启发光动画效果 */
    pulse?: boolean;
    /** 状态点大小 */
    size?: "small" | "default" | "large";
    /** 设置鼠标放在状态点上时显示的文字 */
    title?: string;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    status: "default",
    pulse: false,
    size: "default"
});

// 预设状态颜色映射
const presetStatusColorMap: Record<PresetStatusColor, string> = {
    success: "#52c41a",
    processing: "var(--vort-primary)",
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

// 计算实际显示的颜色
const dotColor = computed(() => {
    if (props.color) {
        return getColorValue(props.color) || props.color;
    }
    return presetStatusColorMap[props.status];
});

// 状态点样式
const dotStyle = computed(() => {
    return {
        backgroundColor: dotColor.value,
        "--dot-color": dotColor.value
    };
});

// 状态点大小类名
const sizeClasses = computed(() => {
    switch (props.size) {
        case "small":
            return "vort-status-dot-sm";
        case "large":
            return "vort-status-dot-lg";
        default:
            return "";
    }
});
</script>

<template>
    <span :class="['vort-status-dot-wrapper', props.class]">
        <span class="vort-status-dot" :class="[sizeClasses, { 'vort-status-dot-pulse': pulse }]" :style="dotStyle" :title="title" />
        <span v-if="text" class="vort-status-dot-text">{{ text }}</span>
    </span>
</template>

<style scoped>
.vort-status-dot-wrapper {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    line-height: inherit;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

.vort-status-dot {
    position: relative;
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    vertical-align: middle;
    flex-shrink: 0;
}

/* 小尺寸 */
.vort-status-dot-sm {
    width: 4px;
    height: 4px;
}

/* 大尺寸 */
.vort-status-dot-lg {
    width: 8px;
    height: 8px;
}

/* 发光动画效果 */
.vort-status-dot-pulse {
    overflow: visible;
}

.vort-status-dot-pulse::after {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 100%;
    height: 100%;
    border: 1px solid var(--dot-color);
    border-radius: 50%;
    animation: vort-status-dot-pulse 1.2s infinite ease-in-out;
    content: "";
}

.vort-status-dot-text {
    font-size: 14px;
    color: var(--vort-text);
}

@keyframes vort-status-dot-pulse {
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
