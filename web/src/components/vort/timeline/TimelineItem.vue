<script setup lang="ts">
import { computed, inject, type ComputedRef } from "vue";
import type { TimelineMode } from "./Timeline.vue";

defineOptions({ name: "VortTimelineItem" });

/** Vort TimelineItem - 时间轴节点组件 */

export type TimelineItemColor = "blue" | "green" | "red" | "gray" | string;
export type TimelineItemPosition = "left" | "right";

interface Props {
    /** 指定圆圈颜色 */
    color?: TimelineItemColor;
    /** 设置标签 */
    label?: string;
    /** 自定义时间轴点的位置（仅在 alternate 模式下有效） */
    position?: TimelineItemPosition;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    color: "blue"
});

const slots = defineSlots<{
    default?: () => any;
    dot?: () => any;
    label?: () => any;
}>();

// 获取父组件的 mode
const timelineMode = inject<ComputedRef<TimelineMode>>("timelineMode");

// 判断是否为预设颜色
const isPresetColor = computed(() => ["blue", "green", "red", "gray"].includes(props.color));

// 圆点样式（自定义颜色）
const dotStyle = computed(() => {
    if (!isPresetColor.value) {
        return {
            color: props.color,
            borderColor: props.color
        };
    }
    return {};
});

// 组合样式
const classes = computed(() => {
    const arr = ["vort-timeline-item"];
    if (isPresetColor.value) arr.push(`vort-timeline-item-${props.color}`);
    if (props.class) arr.push(props.class);
    return arr;
});

const headClasses = computed(() => {
    const arr = ["vort-timeline-item-head"];
    if (isPresetColor.value) arr.push(`vort-timeline-item-head-${props.color}`);
    if (slots.dot) arr.push("vort-timeline-item-head-custom");
    return arr;
});

// 是否有标签
const hasLabel = computed(() => props.label || slots.label);
</script>

<template>
    <li :class="classes">
        <div v-if="hasLabel" class="vort-timeline-item-label">
            <slot name="label">{{ label }}</slot>
        </div>
        <div class="vort-timeline-item-tail" />
        <div :class="headClasses" :style="dotStyle">
            <slot name="dot" />
        </div>
        <div class="vort-timeline-item-content">
            <slot />
        </div>
    </li>
</template>

<style scoped>
.vort-timeline-item {
    position: relative;
    padding-bottom: 20px;
    font-size: 14px;
    line-height: 1.5714;
    list-style: none;
}

.vort-timeline-item:last-child {
    padding-bottom: 0;
}

/* 尾巴（连接线） */
.vort-timeline-item-tail {
    position: absolute;
    inset-block-start: 10px;
    inset-inline-start: 4px;
    height: calc(100% - 10px);
    border-inline-start: 2px solid rgba(5, 5, 5, 0.06);
}

.vort-timeline-item:last-child .vort-timeline-item-tail {
    display: none;
}

/* 圆点 - 参考 Ant Design: 10px, border 3px */
.vort-timeline-item-head {
    position: absolute;
    width: 10px;
    height: 10px;
    background-color: #fff;
    border: 3px solid transparent;
    border-radius: 50%;
}

/* 预设颜色 */
.vort-timeline-item-head-blue {
    color: var(--vort-primary);
    border-color: var(--vort-primary);
}

.vort-timeline-item-head-green {
    color: var(--vort-success);
    border-color: var(--vort-success);
}

.vort-timeline-item-head-red {
    color: var(--vort-error);
    border-color: var(--vort-error);
}

.vort-timeline-item-head-gray {
    color: rgba(0, 0, 0, 0.25);
    border-color: rgba(0, 0, 0, 0.25);
}

/* 自定义图标 */
.vort-timeline-item-head-custom {
    width: auto;
    height: auto;
    margin-top: 0;
    padding: 0;
    line-height: 1;
    text-align: center;
    border: 0;
    border-radius: 0;
    background: transparent;
    /* 使内部 SVG 图标居中 */
    display: flex;
    align-items: center;
    justify-content: center;
    transform: translate(-50%, 0);
    inset-inline-start: 5px;
}

/* 内容 */
.vort-timeline-item-content {
    position: relative;
    inset-block-start: -7px;
    margin-inline-start: 26px;
    margin-inline-end: 0;
    word-break: break-word;
    color: var(--vort-text);
}

/* 标签 */
.vort-timeline-item-label {
    position: absolute;
    inset-block-start: -7px;
    width: calc(50% - 12px);
    text-align: end;
    color: var(--vort-text-secondary);
    font-size: 14px;
}
</style>
