<script setup lang="ts">
import { computed } from "vue";

defineOptions({ name: "VortBadgeRibbon" });

/** Vort BadgeRibbon - 缎带徽标组件 */

// 预设颜色
type PresetColor = "pink" | "red" | "yellow" | "orange" | "cyan" | "green" | "blue" | "purple" | "geekblue" | "magenta" | "volcano" | "gold" | "lime";

interface Props {
    /** 缎带中填入的内容 */
    text?: string;
    /** 自定义缎带的颜色 */
    color?: PresetColor | string;
    /** 设置缎带的位置 */
    placement?: "start" | "end";
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    placement: "end"
});

// 定义插槽类型
defineSlots<{
    /** 默认插槽，缎带包裹的内容 */
    default?: () => unknown;
    /** 缎带中填入的内容 */
    text?: () => unknown;
}>();

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

// 缎带样式
const ribbonStyle = computed(() => {
    const style: Record<string, string> = {};

    if (props.color) {
        style.backgroundColor = getColorValue(props.color) || props.color;
    }

    return style;
});

// 缎带角样式
const cornerStyle = computed(() => {
    const style: Record<string, string> = {};

    if (props.color) {
        const colorValue = getColorValue(props.color) || props.color;
        // 使用较深的颜色作为角的颜色
        style.color = colorValue;
    }

    return style;
});

// 缎带类名
const ribbonClasses = computed(() => {
    const classes: string[] = ["vort-ribbon"];

    if (props.placement === "start") {
        classes.push("vort-ribbon-start");
    } else {
        classes.push("vort-ribbon-end");
    }

    if (!props.color) {
        classes.push("vort-ribbon-default");
    }

    return classes;
});
</script>

<template>
    <div :class="['vort-ribbon-wrapper', props.class]">
        <slot />
        <div :class="ribbonClasses" :style="ribbonStyle">
            <span class="vort-ribbon-text">
                <slot name="text">{{ text }}</slot>
            </span>
            <span class="vort-ribbon-corner" :style="cornerStyle" />
        </div>
    </div>
</template>

<style scoped>
.vort-ribbon-wrapper {
    position: relative;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

.vort-ribbon {
    position: absolute;
    top: 8px;
    padding: 0 8px;
    font-size: 14px;
    line-height: 22px;
    white-space: nowrap;
    color: #fff;
    border-radius: var(--vort-border-radius-sm, 2px);
}

.vort-ribbon-default {
    background-color: var(--vort-primary);
}

.vort-ribbon-end {
    right: -8px;
    border-bottom-right-radius: 0;
}

.vort-ribbon-start {
    left: -8px;
    border-bottom-left-radius: 0;
}

.vort-ribbon-text {
    display: inline-block;
}

.vort-ribbon-corner {
    position: absolute;
    bottom: 0;
    width: 8px;
    height: 8px;
    background-color: currentColor;
    transform: scaleY(0.75);
    transform-origin: top;
    filter: brightness(0.75);
}

.vort-ribbon-default .vort-ribbon-corner {
    color: var(--vort-primary);
}

.vort-ribbon-end .vort-ribbon-corner {
    right: 0;
    border-bottom-right-radius: var(--vort-border-radius-sm, 4px);
    transform: translateY(100%) scaleY(0.75);
    clip-path: polygon(100% 0, 100% 100%, 0 100%);
}

.vort-ribbon-start .vort-ribbon-corner {
    left: 0;
    border-bottom-left-radius: var(--vort-border-radius-sm, 4px);
    transform: translateY(100%) scaleY(0.75);
    clip-path: polygon(0 0, 100% 100%, 0 100%);
}
</style>
