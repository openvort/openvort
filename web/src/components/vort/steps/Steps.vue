<script setup lang="ts">
import { computed } from "vue";
import { CheckOutlined, CloseOutlined } from "@/components/vort/icons";

defineOptions({ name: "VortSteps" });

/** Vort Steps - 步骤条组件 */

export type StepStatus = "wait" | "process" | "finish" | "error";
export type StepsDirection = "horizontal" | "vertical";
export type StepsSize = "default" | "small";
export type StepsType = "default" | "navigation" | "dot" | "inline";

export interface StepItem {
    /** 标题 */
    title: string;
    /** 副标题 */
    subTitle?: string;
    /** 描述 */
    description?: string;
    /** 状态 */
    status?: StepStatus;
    /** 禁用点击 */
    disabled?: boolean;
    /** 图标（可选，用于自定义图标） */
    icon?: string;
}

interface Props {
    /** 当前步骤，从 0 开始 */
    current?: number;
    /** 步骤条方向 */
    direction?: StepsDirection;
    /** 起始序号，默认从 0 开始 */
    initial?: number;
    /** 尺寸 */
    size?: StepsSize;
    /** 当前步骤的状态 */
    status?: StepStatus;
    /** 步骤类型 */
    type?: StepsType;
    /** 配置式步骤项 */
    items?: StepItem[];
    /** 点击切换步骤 */
    clickable?: boolean;
    /** 自定义类名 */
    class?: string;
    /** 标签放置位置（仅在 dot 类型时生效） */
    labelPlacement?: "horizontal" | "vertical";
    /** 导航步骤条是否显示百分比（navigation 类型专用） */
    percent?: number;
}

const props = withDefaults(defineProps<Props>(), {
    current: 0,
    direction: "horizontal",
    initial: 0,
    size: "default",
    status: "process",
    type: "default",
    clickable: false,
    labelPlacement: "horizontal"
});

const emit = defineEmits<{
    "update:current": [current: number];
    change: [current: number];
}>();

// 计算每个步骤的实际状态
const getStepStatus = (index: number, step: StepItem): StepStatus => {
    if (step.status) return step.status;
    if (index < props.current) return "finish";
    if (index === props.current) return props.status;
    return "wait";
};

// 处理步骤点击
const handleStepClick = (index: number, step: StepItem) => {
    if (!props.clickable || step.disabled) return;
    emit("update:current", index);
    emit("change", index);
};

// 容器样式
const containerClasses = computed(() => {
    const classes = ["vort-steps", `vort-steps-${props.direction}`, `vort-steps-${props.type}`];
    if (props.size === "small") classes.push("vort-steps-small");
    if (props.type === "dot" && props.labelPlacement === "vertical") classes.push("vort-steps-label-vertical");
    if (props.class) classes.push(props.class);
    return classes;
});

// 获取步骤项样式
const getStepClasses = (index: number, step: StepItem) => {
    const status = getStepStatus(index, step);
    const isLast = index === (props.items?.length ?? 0) - 1;
    const classes = ["vort-steps-item", `vort-steps-item-${status}`];
    if (step.disabled) classes.push("vort-steps-item-disabled");
    if (props.clickable && !step.disabled) classes.push("vort-steps-item-clickable");
    if (isLast) classes.push("vort-steps-item-last");
    return classes;
};
</script>

<template>
    <div :class="containerClasses">
        <div v-for="(step, index) in items" :key="index" :class="getStepClasses(index, step)" @click="handleStepClick(index, step)">
            <!-- 连接线（仅用于垂直方向和点状步骤条） -->
            <div v-if="(direction === 'vertical' || type === 'dot') && type !== 'inline'" class="vort-steps-item-tail"></div>

            <!-- 导航箭头（navigation 类型专用） -->
            <div v-if="type === 'navigation'" class="vort-steps-item-arrow"></div>

            <!-- 图标容器 -->
            <div class="vort-steps-item-icon">
                <span class="vort-steps-icon">
                    <!-- 点状类型 -->
                    <template v-if="type === 'dot'">
                        <span class="vort-steps-icon-dot"></span>
                    </template>
                    <!-- 内联类型不显示图标 -->
                    <template v-else-if="type === 'inline'">
                        <!-- 内联类型不需要图标 -->
                    </template>
                    <!-- 默认类型和导航类型 -->
                    <template v-else>
                        <template v-if="getStepStatus(index, step) === 'finish'">
                            <CheckOutlined class="vort-steps-finish-icon" />
                        </template>
                        <template v-else-if="getStepStatus(index, step) === 'error'">
                            <CloseOutlined class="vort-steps-error-icon" />
                        </template>
                        <template v-else>
                            <span class="vort-steps-icon-number">{{ index + initial + 1 }}</span>
                        </template>
                    </template>
                </span>
            </div>

            <!-- 内容容器 -->
            <div class="vort-steps-item-content">
                <div class="vort-steps-item-title">
                    {{ step.title }}
                    <span v-if="step.subTitle && type !== 'inline'" class="vort-steps-item-subtitle">{{ step.subTitle }}</span>
                </div>
                <div v-if="step.description && type !== 'inline'" class="vort-steps-item-description">
                    {{ step.description }}
                </div>
            </div>

            <!-- 导航类型底部进度条 -->
            <div v-if="type === 'navigation'" class="vort-steps-item-progress"></div>
        </div>
    </div>
</template>

<style scoped>
/* ========== 容器 ========== */
.vort-steps {
    display: flex;
    width: 100%;
    font-size: 14px;
    box-sizing: border-box;
}

/* ========== 步骤项 ========== */
.vort-steps-item {
    position: relative;
    flex: 1;
    overflow: hidden;
}

.vort-steps-item-last {
    flex: none;
}

.vort-steps-item-last .vort-steps-item-tail {
    display: none;
}

/* ========== 水平方向 ========== */
.vort-steps-horizontal {
    flex-direction: row;
}

.vort-steps-horizontal .vort-steps-item {
    display: inline-flex;
    align-items: flex-start;
}

/* ========== 水平连接线（通过 title::after 实现） ========== */
.vort-steps-horizontal.vort-steps-default .vort-steps-item {
    margin-right: 16px; /* 线条右侧间隔 */
}

.vort-steps-horizontal.vort-steps-default .vort-steps-item-last {
    margin-right: 0;
}

.vort-steps-horizontal.vort-steps-default .vort-steps-item-title::after {
    position: absolute;
    top: 16px;
    inset-inline-start: 100%;
    display: block;
    width: 9999px;
    height: 1px;
    background: var(--vort-border);
    content: "";
    transition: background 0.3s;
}

.vort-steps-horizontal.vort-steps-default .vort-steps-item-finish .vort-steps-item-title::after {
    background: var(--vort-primary);
}

.vort-steps-horizontal.vort-steps-default .vort-steps-item-last .vort-steps-item-title::after {
    display: none;
}

/* ========== 图标 ========== */
.vort-steps-item-icon {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    margin-right: 8px;
}

.vort-steps-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    font-size: 16px;
    font-weight: 500;
    border: 1px solid var(--vort-border);
    border-radius: 50%;
    background: var(--vort-bg-elevated, #fff);
    color: var(--vort-text-tertiary);
    transition: all 0.3s;
}

.vort-steps-icon-number {
    line-height: 1;
}

/* 完成状态 */
.vort-steps-item-finish .vort-steps-icon {
    background: var(--vort-primary);
    border-color: var(--vort-primary);
    color: #fff;
}

.vort-steps-finish-icon,
.vort-steps-error-icon {
    width: 14px;
    height: 14px;
}

/* 进行中状态 */
.vort-steps-item-process .vort-steps-icon {
    background: var(--vort-primary);
    border-color: var(--vort-primary);
    color: #fff;
}

/* 等待状态 */
.vort-steps-item-wait .vort-steps-icon {
    background: var(--vort-bg-elevated, #fff);
    border-color: var(--vort-border);
    color: var(--vort-text-tertiary);
}

/* 错误状态 */
.vort-steps-item-error .vort-steps-icon {
    background: var(--vort-error);
    border-color: var(--vort-error);
    color: #fff;
}

/* ========== 内容 ========== */
.vort-steps-item-content {
    display: inline-block;
    vertical-align: top;
}

.vort-steps-item-title {
    position: relative;
    display: inline-flex;
    align-items: center;
    padding-right: 16px;
    font-size: 16px;
    font-weight: 500;
    line-height: 32px;
    color: var(--vort-text);
    white-space: nowrap;
}

.vort-steps-item-wait .vort-steps-item-title {
    color: var(--vort-text-tertiary);
}

.vort-steps-item-finish .vort-steps-item-title {
    color: var(--vort-text);
}

.vort-steps-item-error .vort-steps-item-title {
    color: var(--vort-error);
}

.vort-steps-item-subtitle {
    display: inline;
    margin-left: 8px;
    font-size: 14px;
    font-weight: 400;
    color: var(--vort-text-tertiary);
}

.vort-steps-item-description {
    max-width: 140px;
    font-size: 14px;
    color: var(--vort-text-secondary);
    white-space: normal;
    word-break: break-word;
}

.vort-steps-item-wait .vort-steps-item-description {
    color: var(--vort-text-tertiary);
}

.vort-steps-item-error .vort-steps-item-description {
    color: var(--vort-error);
}

/* ========== 垂直方向 ========== */
.vort-steps-vertical {
    flex-direction: column;
}

.vort-steps-vertical .vort-steps-item {
    display: flex;
    flex: none;
    overflow: visible;
}

.vort-steps-vertical .vort-steps-item-tail {
    position: absolute;
    top: 38px;
    bottom: 4px;
    left: 15px;
    width: 1px;
}

.vort-steps-vertical .vort-steps-item-tail::after {
    content: "";
    display: block;
    width: 1px;
    height: 100%;
    background: var(--vort-border);
    transition: background 0.3s;
}

.vort-steps-vertical .vort-steps-item-finish .vort-steps-item-tail::after {
    background: var(--vort-primary);
}

.vort-steps-vertical .vort-steps-item-content {
    min-height: 48px;
    padding-bottom: 20px;
}

.vort-steps-vertical .vort-steps-item-last .vort-steps-item-content {
    padding-bottom: 0;
}

.vort-steps-vertical .vort-steps-item-description {
    max-width: none;
}

/* ========== 迷你版/小尺寸 ========== */
.vort-steps-small .vort-steps-item-icon {
    width: 24px;
    height: 24px;
    margin-right: 8px;
}

.vort-steps-small .vort-steps-icon {
    width: 24px;
    height: 24px;
    font-size: 12px;
}

.vort-steps-small .vort-steps-item-title {
    font-size: 14px;
    line-height: 24px;
    padding-right: 12px;
}

.vort-steps-small .vort-steps-item-description {
    font-size: 12px;
}

.vort-steps-small.vort-steps-horizontal.vort-steps-default .vort-steps-item {
    padding-right: 12px;
}

.vort-steps-small.vort-steps-horizontal.vort-steps-default .vort-steps-item-last {
    padding-right: 0;
}

.vort-steps-small.vort-steps-horizontal.vort-steps-default .vort-steps-item-title::after {
    top: 12px;
}

.vort-steps-small.vort-steps-vertical .vort-steps-item-tail {
    left: 11px;
    top: 30px;
    bottom: 4px;
}

/* ========== 点状步骤条 (Dot Style) ========== */
.vort-steps-dot .vort-steps-item-icon {
    width: 16px;
    height: 32px;
    margin-right: 0;
    display: flex;
    align-items: center;
    justify-content: center;
}

.vort-steps-dot .vort-steps-icon {
    width: 8px;
    height: 8px;
    min-width: 8px;
    min-height: 8px;
    border: none;
    background: var(--vort-border);
    border-radius: 50%;
    transition: all 0.3s ease;
}

.vort-steps-dot .vort-steps-icon-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: inherit;
}

/* 点状 - 完成状态 */
.vort-steps-dot .vort-steps-item-finish .vort-steps-icon {
    background: var(--vort-primary);
}

/* 点状 - 进行中状态（大圆点效果） */
.vort-steps-dot .vort-steps-item-process .vort-steps-icon {
    width: 10px;
    height: 10px;
    background: var(--vort-primary);
    box-shadow: 0 0 0 3px var(--vort-primary-bg, rgba(22, 119, 255, 0.1));
}

/* 点状 - 等待状态 */
.vort-steps-dot .vort-steps-item-wait .vort-steps-icon {
    background: var(--vort-border);
}

/* 点状 - 错误状态 */
.vort-steps-dot .vort-steps-item-error .vort-steps-icon {
    background: var(--vort-error);
    box-shadow: 0 0 0 3px rgba(255, 77, 79, 0.1);
}

/* 点状水平方向 */
.vort-steps-dot.vort-steps-horizontal .vort-steps-item {
    flex-direction: column;
    align-items: flex-start;
    overflow: visible;
}

.vort-steps-dot.vort-steps-horizontal .vort-steps-item-icon {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    margin: 0 0 12px 0;
    height: auto;
}

.vort-steps-dot.vort-steps-horizontal .vort-steps-item-tail {
    display: block;
    position: absolute;
    top: 3px;
    left: 16px;
    width: calc(100% - 24px);
    height: 3px;
    margin: 0;
    padding: 0;
}

.vort-steps-dot.vort-steps-horizontal .vort-steps-item-tail::after {
    content: "";
    display: block;
    width: 100%;
    height: 1px;
    background: var(--vort-border);
    transition: background 0.3s;
}

.vort-steps-dot.vort-steps-horizontal .vort-steps-item-finish .vort-steps-item-tail::after {
    background: var(--vort-primary);
}

.vort-steps-dot.vort-steps-horizontal .vort-steps-item-content {
    width: 100%;
}

.vort-steps-dot.vort-steps-horizontal .vort-steps-item-title {
    line-height: 1.5;
    padding-right: 8px;
}

.vort-steps-dot.vort-steps-horizontal .vort-steps-item-title::after {
    display: none;
}

/* 点状 - 垂直方向标签 */
.vort-steps-dot.vort-steps-label-vertical .vort-steps-item {
    align-items: center;
    text-align: center;
}

.vort-steps-dot.vort-steps-label-vertical .vort-steps-item-icon {
    margin: 0 auto 12px;
    justify-content: center;
}

.vort-steps-dot.vort-steps-label-vertical .vort-steps-item-content {
    text-align: center;
}

.vort-steps-dot.vort-steps-label-vertical .vort-steps-item-title {
    padding-right: 0;
}

/* 点状垂直方向 */
.vort-steps-dot.vort-steps-vertical .vort-steps-item {
    flex-direction: row;
    align-items: flex-start;
}

.vort-steps-dot.vort-steps-vertical .vort-steps-item-icon {
    margin: 10px 12px 0 0;
    height: 8px;
}

.vort-steps-dot.vort-steps-vertical .vort-steps-item-tail {
    left: 7px;
    top: 24px;
    bottom: -3px;
    width: 1px;
}

.vort-steps-dot.vort-steps-vertical .vort-steps-item-content {
    min-height: 48px;
    padding-bottom: 20px;
}

/* 点状小尺寸 */
.vort-steps-dot.vort-steps-small .vort-steps-icon {
    width: 6px;
    height: 6px;
}

.vort-steps-dot.vort-steps-small .vort-steps-item-process .vort-steps-icon {
    width: 8px;
    height: 8px;
}

.vort-steps-dot.vort-steps-small .vort-steps-item-title {
    font-size: 12px;
    line-height: 1.5;
}

.vort-steps-dot.vort-steps-small .vort-steps-item-description {
    font-size: 12px;
}

/* ========== 导航步骤条 (Navigation Style) ========== */
.vort-steps-navigation {
    padding: 0;
    background: var(--vort-bg-elevated, #fff);
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px));
    overflow: hidden;
    box-shadow:
        0 1px 2px 0 rgba(0, 0, 0, 0.03),
        0 1px 6px -1px rgba(0, 0, 0, 0.02),
        0 2px 4px 0 rgba(0, 0, 0, 0.02);
}

.vort-steps-navigation .vort-steps-item {
    display: flex;
    align-items: center;
    padding: 12px 16px 12px 24px;
    overflow: visible;
    transition: background 0.3s;
}

.vort-steps-navigation .vort-steps-item:first-child {
    padding-left: 24px;
}

/* 导航 - 连接线隐藏 */
.vort-steps-navigation .vort-steps-item-tail {
    display: none;
}

.vort-steps-navigation .vort-steps-item-title::after {
    display: none !important;
}

/* 导航 - 底部进度条 */
.vort-steps-navigation .vort-steps-item-progress {
    position: absolute;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 3px;
    background: transparent;
    transition: all 0.3s;
}

.vort-steps-navigation .vort-steps-item-process .vort-steps-item-progress,
.vort-steps-navigation .vort-steps-item-finish .vort-steps-item-progress {
    background: var(--vort-primary);
}

.vort-steps-navigation .vort-steps-item-error .vort-steps-item-progress {
    background: var(--vort-error);
}

/* 导航 - 箭头 */
.vort-steps-navigation .vort-steps-item-arrow {
    position: absolute;
    top: 50%;
    right: 16px;
    width: 0;
    height: 0;
    border-style: solid;
    border-width: 6px 0 6px 8px;
    border-color: transparent transparent transparent var(--vort-border);
    transform: translateY(-50%);
    transition: border-color 0.3s;
}

.vort-steps-navigation .vort-steps-item-last .vort-steps-item-arrow {
    display: none;
}

.vort-steps-navigation .vort-steps-item-finish .vort-steps-item-arrow {
    border-left-color: var(--vort-primary);
}

.vort-steps-navigation .vort-steps-item-process .vort-steps-item-arrow {
    border-left-color: var(--vort-primary);
}

/* 导航 - 悬停效果 */
.vort-steps-navigation .vort-steps-item-clickable:hover {
    background: #f5f5f5;
}

/* 导航 - 当前步骤背景 */
.vort-steps-navigation .vort-steps-item-process {
    background: var(--vort-primary-bg, rgba(22, 119, 255, 0.08));
}

/* 导航 - 标题样式 */
.vort-steps-navigation .vort-steps-item-title {
    padding-right: 24px;
}

/* 导航 - 小尺寸 */
.vort-steps-navigation.vort-steps-small .vort-steps-item {
    padding: 8px 12px 8px 16px;
}

.vort-steps-navigation.vort-steps-small .vort-steps-item-icon {
    width: 24px;
    height: 24px;
    margin-right: 8px;
}

.vort-steps-navigation.vort-steps-small .vort-steps-icon {
    width: 24px;
    height: 24px;
    font-size: 12px;
}

.vort-steps-navigation.vort-steps-small .vort-steps-item-title {
    font-size: 14px;
    line-height: 24px;
}

.vort-steps-navigation.vort-steps-small .vort-steps-item-progress {
    height: 2px;
}

.vort-steps-navigation.vort-steps-small .vort-steps-item-arrow {
    border-width: 5px 0 5px 6px;
}

/* ========== 内联步骤条 (Inline Style) ========== */
.vort-steps-inline {
    display: inline-flex;
    width: auto;
    background: #f5f5f5;
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px));
    padding: 4px;
}

.vort-steps-inline .vort-steps-item {
    flex: none;
    padding: 6px 20px;
    border-radius: var(--vort-border-radius, 6px);
    cursor: pointer;
    transition: all 0.3s;
}

.vort-steps-inline .vort-steps-item-process {
    background: var(--vort-bg-elevated, #fff);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
}

.vort-steps-inline .vort-steps-item-icon {
    display: none;
}

.vort-steps-inline .vort-steps-item-content {
    display: flex;
    align-items: center;
}

.vort-steps-inline .vort-steps-item-title {
    font-size: 14px;
    line-height: 22px;
    padding-right: 0;
}

.vort-steps-inline .vort-steps-item-title::after {
    display: none !important;
}

.vort-steps-inline .vort-steps-item-wait .vort-steps-item-title {
    color: var(--vort-text-secondary);
}

.vort-steps-inline .vort-steps-item-process .vort-steps-item-title {
    color: var(--vort-text);
    font-weight: 500;
}

.vort-steps-inline .vort-steps-item-finish .vort-steps-item-title {
    color: var(--vort-primary);
}

/* 内联小尺寸 */
.vort-steps-inline.vort-steps-small {
    padding: 3px;
}

.vort-steps-inline.vort-steps-small .vort-steps-item {
    padding: 4px 14px;
}

.vort-steps-inline.vort-steps-small .vort-steps-item-title {
    font-size: 12px;
    line-height: 20px;
}

/* ========== 禁用状态 ========== */
.vort-steps-item-disabled {
    cursor: not-allowed;
}

.vort-steps-item-disabled .vort-steps-icon {
    background: #fafafa !important;
    border-color: var(--vort-border) !important;
    color: var(--vort-text-quaternary) !important;
}

.vort-steps-item-disabled .vort-steps-item-title,
.vort-steps-item-disabled .vort-steps-item-description {
    color: var(--vort-text-quaternary) !important;
}

/* ========== 可点击状态 ========== */
.vort-steps-item-clickable {
    cursor: pointer;
}

.vort-steps-item-clickable:hover .vort-steps-item-title {
    color: var(--vort-primary);
}

.vort-steps-item-clickable.vort-steps-item-wait:hover .vort-steps-icon {
    border-color: var(--vort-primary);
    color: var(--vort-primary);
}

.vort-steps-dot .vort-steps-item-clickable.vort-steps-item-wait:hover .vort-steps-icon {
    background: var(--vort-primary);
    opacity: 0.6;
}

.vort-steps-navigation .vort-steps-item-clickable.vort-steps-item-wait:hover .vort-steps-icon {
    border-color: var(--vort-primary);
    color: var(--vort-primary);
}
</style>
