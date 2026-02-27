<script setup lang="ts">
import { computed, provide, useSlots } from "vue";

defineOptions({ name: "VortTimeline" });

/** Vort Timeline - 时间轴组件 */

export type TimelineMode = "left" | "right" | "alternate";

interface Props {
    /** 通过设置 mode 可以改变时间轴和内容的相对位置 */
    mode?: TimelineMode;
    /** 指定最后一个幽灵节点是否存在或内容 */
    pending?: boolean | string;
    /** 是否倒序排列 */
    reverse?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    mode: "left",
    pending: false,
    reverse: false
});

const slots = useSlots();

// 提供给子组件的上下文
provide(
    "timelineMode",
    computed(() => props.mode)
);

// 组合样式
const classes = computed(() => {
    const arr = ["vort-timeline", `vort-timeline-${props.mode}`];
    if (props.reverse) arr.push("vort-timeline-reverse");
    if (props.pending) arr.push("vort-timeline-pending");
    if (props.class) arr.push(props.class);
    return arr;
});

// 是否有 pending 内容
const hasPending = computed(() => props.pending !== false);
const pendingText = computed(() => (typeof props.pending === "string" ? props.pending : ""));
</script>

<template>
    <ul :class="classes">
        <slot />

        <!-- Pending 始终放在 DOM 最后：
             - 正序时：显示在最下面（最新位置），不需要 tail
             - 倒序时：因为 column-reverse，显示在最上面，需要 tail 连接到下面的项
        -->
        <template v-if="hasPending">
            <li class="vort-timeline-item vort-timeline-item-pending" :class="{ 'vort-timeline-item-pending-reverse': reverse }">
                <!-- 倒序时需要 tail 连接到下面的项 -->
                <div v-if="reverse" class="vort-timeline-item-tail" />
                <div class="vort-timeline-item-head vort-timeline-item-head-pending">
                    <slot name="pendingDot">
                        <span class="vort-timeline-item-head-pending-dot" />
                    </slot>
                </div>
                <div class="vort-timeline-item-content">
                    <slot name="pending">{{ pendingText }}</slot>
                </div>
            </li>
        </template>
    </ul>
</template>

<style scoped>
.vort-timeline {
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 14px;
    line-height: 1.5714;
}

/* 倒序 */
.vort-timeline-reverse {
    display: flex;
    flex-direction: column-reverse;
}

/* ==================== 倒序模式下的 tail 和间距处理 ==================== */

/* 倒序：DOM 第一个是视觉上最后一个，隐藏 tail 和底部间距 */
.vort-timeline-reverse :deep(.vort-timeline-item:first-child .vort-timeline-item-tail) {
    display: none;
}

.vort-timeline-reverse :deep(.vort-timeline-item:first-child) {
    padding-bottom: 0;
}

/* 倒序：DOM 最后一个是视觉上第一个，需要底部间距（排除 pending） */
.vort-timeline-reverse :deep(.vort-timeline-item:last-child:not(.vort-timeline-item-pending)) {
    padding-bottom: 20px;
}

/* ==================== 有 pending 时的虚线处理 ==================== */

/* 正序 + 有 pending：倒数第二个（pending 前一个）需要虚线连接到 pending */
.vort-timeline-pending:not(.vort-timeline-reverse) :deep(.vort-timeline-item:nth-last-child(2) .vort-timeline-item-tail) {
    border-inline-start-style: dashed;
}

/* 倒序 + 有 pending：pending 自身的 tail 显示为虚线 */
.vort-timeline-item-pending-reverse > .vort-timeline-item-tail {
    position: absolute;
    inset-block-start: 10px;
    inset-inline-start: 4px;
    height: calc(100% - 10px);
    border-inline-start: 2px dashed rgba(5, 5, 5, 0.06);
}

/* 右侧模式 + 倒序 pending tail */
.vort-timeline-right .vort-timeline-item-pending-reverse > .vort-timeline-item-tail {
    inset-inline-start: auto;
    inset-inline-end: 4px;
}

/* 交替模式 + 倒序 pending tail */
.vort-timeline-alternate .vort-timeline-item-pending-reverse > .vort-timeline-item-tail {
    inset-inline-start: 50%;
}

/* ==================== 左侧模式（默认） ==================== */
.vort-timeline-left :deep(.vort-timeline-item-label) {
    display: none;
}

/* ==================== 右侧模式 ==================== */
.vort-timeline-right :deep(.vort-timeline-item-tail) {
    inset-inline-start: auto;
    inset-inline-end: 4px;
}

.vort-timeline-right :deep(.vort-timeline-item-head) {
    inset-inline-start: auto;
    inset-inline-end: 0;
}

.vort-timeline-right :deep(.vort-timeline-item-content) {
    margin-inline-start: 0;
    margin-inline-end: 26px;
    text-align: end;
}

.vort-timeline-right :deep(.vort-timeline-item-label) {
    display: none;
}

/* ==================== 交替模式 ==================== */
.vort-timeline-alternate :deep(.vort-timeline-item-tail) {
    inset-inline-start: 50%;
}

.vort-timeline-alternate :deep(.vort-timeline-item-head) {
    inset-inline-start: 50%;
    margin-inline-start: -4px;
}

/* 奇数项：内容在左边 */
.vort-timeline-alternate :deep(.vort-timeline-item:nth-child(odd) .vort-timeline-item-content) {
    margin-inline-start: 0;
    margin-inline-end: calc(50% + 12px);
    text-align: end;
}

/* 偶数项：内容在右边 */
.vort-timeline-alternate :deep(.vort-timeline-item:nth-child(even) .vort-timeline-item-content) {
    margin-inline-start: calc(50% + 12px);
    margin-inline-end: 0;
    text-align: start;
}

/* 标签样式 - 奇数项标签在右边 */
.vort-timeline-alternate :deep(.vort-timeline-item:nth-child(odd) .vort-timeline-item-label) {
    display: block;
    inset-inline-start: calc(50% + 12px);
    width: calc(50% - 12px);
    text-align: start;
}

/* 标签样式 - 偶数项标签在左边 */
.vort-timeline-alternate :deep(.vort-timeline-item:nth-child(even) .vort-timeline-item-label) {
    display: block;
    inset-inline-start: 0;
    inset-inline-end: calc(50% + 12px);
    width: calc(50% - 12px);
    text-align: end;
}

/* ==================== Pending 状态 ==================== */
.vort-timeline-item-head-pending {
    position: absolute;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 10px;
    height: 10px;
    background: transparent !important;
    border: none !important;
}

.vort-timeline-item-head-pending-dot {
    display: block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--vort-primary);
    animation: vortTimelinePendingPulse 1.5s ease-in-out infinite;
}

/* Pending 项基础样式 */
.vort-timeline-item-pending {
    position: relative;
    padding-bottom: 0;
    font-size: 14px;
    line-height: 1.5714;
    list-style: none;
}

/* 倒序时 pending 需要底部间距（因为有 tail 向下延伸） */
.vort-timeline-item-pending-reverse {
    padding-bottom: 20px;
}

/* Pending 项的内容 */
.vort-timeline-item-pending > .vort-timeline-item-content {
    position: relative;
    inset-block-start: -7px;
    margin-inline-start: 26px;
    margin-inline-end: 0;
    word-break: break-word;
    color: var(--vort-text);
}

/* Pending 在右侧模式下 */
.vort-timeline-right .vort-timeline-item-pending > .vort-timeline-item-head-pending {
    inset-inline-start: auto;
    inset-inline-end: 0;
}

.vort-timeline-right .vort-timeline-item-pending > .vort-timeline-item-content {
    margin-inline-start: 0;
    margin-inline-end: 26px;
    text-align: end;
}

/* Pending 在交替模式下 */
.vort-timeline-alternate .vort-timeline-item-pending > .vort-timeline-item-head-pending {
    inset-inline-start: 50%;
    margin-inline-start: -4px;
}

.vort-timeline-alternate .vort-timeline-item-pending:nth-child(odd) > .vort-timeline-item-content {
    margin-inline-start: 0;
    margin-inline-end: calc(50% + 12px);
    text-align: end;
}

.vort-timeline-alternate .vort-timeline-item-pending:nth-child(even) > .vort-timeline-item-content {
    margin-inline-start: calc(50% + 12px);
    margin-inline-end: 0;
    text-align: start;
}

@keyframes vortTimelinePendingPulse {
    0%,
    100% {
        opacity: 1;
        transform: scale(1);
    }
    50% {
        opacity: 0.5;
        transform: scale(0.8);
    }
}
</style>
