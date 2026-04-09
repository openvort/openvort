<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, nextTick } from "vue";
import dayjs from "dayjs";
import type { GanttBarData } from "./gantt.types";

const props = defineProps<{
    bar: GanttBarData;
    left: number;
    width: number;
    scrollLeft: number;
    previewLeft?: number;
    previewWidth?: number;
    previewProgress?: number;
    isDragging?: boolean;
    rowHeight: number;
    xToDate?: (x: number) => Date;
    dateToX?: (date: Date) => number;
}>();

const emit = defineEmits<{
    moveStart: [e: PointerEvent];
    resizeLeftStart: [e: PointerEvent];
    resizeRightStart: [e: PointerEvent];
    progressDragStart: [e: PointerEvent];
    clickCreate: [e: MouseEvent];
    clearDate: [type: "start" | "end" | "both"];
}>();

const textRef = ref<HTMLElement | null>(null);
const barRef = ref<HTMLElement | null>(null);
const textOverflow = ref(false);
const hovered = ref(false);

const actualLeft = computed(() => props.previewLeft ?? props.left);
const actualWidth = computed(() => props.previewWidth ?? props.width);
const actualProgress = computed(() => props.previewProgress ?? props.bar.progress);

const stickyOffset = computed(() => {
    const hiddenLeft = props.scrollLeft - actualLeft.value;
    if (hiddenLeft <= 0) return 0;
    return Math.min(hiddenLeft, actualWidth.value);
});

const visibleBarWidth = computed(() => actualWidth.value - stickyOffset.value);

const isBarInViewport = computed(() => actualLeft.value + actualWidth.value > props.scrollLeft);

const showProgress = computed(() =>
    (props.bar.row.type === "需求" || props.bar.row.type === "任务") && props.bar.progress !== undefined
);

const progressWidth = computed(() => {
    if (!showProgress.value) return 0;
    return (actualProgress.value / 100) * actualWidth.value;
});

const barLabel = computed(() => {
    const { row } = props.bar;
    const start = row.planStartDate || row.planTime?.[0] || "";
    const end = row.planEndDate || row.planTime?.[1] || "";
    const startStr = start ? dayjs(start).format("YYYY-MM-DD") : "";
    const endStr = end ? dayjs(end).format("YYYY-MM-DD") : "";
    return `${startStr}  ${row.title}  ${endStr}`;
});

const displayTitle = computed(() => props.bar.row.title);

const tooltipText = computed(() => {
    const { row } = props.bar;
    const start = row.planStartDate || row.planTime?.[0] || "";
    const end = row.planEndDate || row.planTime?.[1] || "";
    const lines = [row.title];
    if (start) lines.push(`开始: ${dayjs(start).format("YYYY-MM-DD")}`);
    if (end) lines.push(`截止: ${dayjs(end).format("YYYY-MM-DD")}`);
    if (showProgress.value) lines.push(`进度: ${actualProgress.value}%`);
    return lines.join("\n");
});

const barColors = computed(() => {
    const hex = props.bar.statusColor;
    return {
        '--bar-bg': `${hex}30`,
        '--bar-fill': hex,
    };
});

function checkTextOverflow() {
    if (!textRef.value || !barRef.value) return;
    textOverflow.value = textRef.value.scrollWidth > actualWidth.value - 16;
}

let resizeObs: ResizeObserver | null = null;
onMounted(() => {
    nextTick(checkTextOverflow);
    if (barRef.value) {
        resizeObs = new ResizeObserver(checkTextOverflow);
        resizeObs.observe(barRef.value);
    }
});
onBeforeUnmount(() => { resizeObs?.disconnect(); });

const hoverPreview = ref<{
    left: number;
    width: number;
    startLabel: string;
    endLabel: string;
} | null>(null);

function onEmptyMouseMove(e: MouseEvent) {
    if (!props.xToDate || !props.dateToX) return;
    const el = e.currentTarget as HTMLElement;
    const absoluteX = e.clientX - el.getBoundingClientRect().left;
    const hoverDate = dayjs(props.xToDate(absoluteX));
    const startDate = hoverDate.subtract(1, "day").startOf("day");
    const endDate = hoverDate.add(1, "day");

    const left = props.dateToX(startDate.toDate());
    const rightEnd = props.dateToX(endDate.endOf("day").toDate());

    hoverPreview.value = {
        left,
        width: rightEnd - left,
        startLabel: startDate.format("YYYY-MM-DD"),
        endLabel: endDate.format("YYYY-MM-DD"),
    };
}
</script>

<template>
    <VortDropdown v-if="bar.hasTime" trigger="contextMenu">
        <div
            ref="barRef"
            class="gantt-bar"
            :class="{ 'is-dragging': isDragging }"
            :style="{
                left: `${actualLeft}px`,
                width: `${actualWidth}px`,
                height: '26px',
                ...barColors,
            }"
            :title="tooltipText"
            @mouseenter="hovered = true"
            @mouseleave="hovered = false"
            @pointerdown="emit('moveStart', $event)"
        >
            <!-- Progress fill -->
            <div
                v-if="showProgress && actualProgress > 0"
                class="gantt-bar-progress"
                :style="{ width: `${progressWidth}px`, borderRadius: actualProgress >= 100 ? '4px' : `${Math.min(4, progressWidth / 2)}px 0 0 ${Math.min(4, progressWidth / 2)}px` }"
            />

            <!-- Text inside bar -->
            <span
                v-if="!textOverflow"
                ref="textRef"
                class="gantt-bar-text inside"
                :style="stickyOffset > 0 ? {
                    transform: `translateX(${stickyOffset}px)`,
                    maxWidth: `${visibleBarWidth - 16}px`,
                } : undefined"
            >
                {{ displayTitle }}
            </span>

            <!-- Text after bar (hidden when bar is fully off-screen to avoid overlap with OOR labels) -->
            <span
                v-else-if="isBarInViewport"
                ref="textRef"
                class="gantt-bar-text outside"
                :style="{ left: `${actualWidth + 6}px` }"
            >
                {{ displayTitle }}
            </span>

            <!-- Left resize handle -->
            <div
                class="gantt-bar-handle-zone left"
                @pointerdown="emit('resizeLeftStart', $event)"
            >
                <svg
                    class="gantt-bar-handle"
                    :class="{ visible: hovered || isDragging }"
                    width="3" height="12" viewBox="0 0 3 12"
                >
                    <rect x="0" y="0" width="3" height="12" rx="1.5" ry="1.5" fill="#aaa" />
                </svg>
            </div>

            <!-- Right resize handle -->
            <div
                class="gantt-bar-handle-zone right"
                @pointerdown="emit('resizeRightStart', $event)"
            >
                <svg
                    class="gantt-bar-handle"
                    :class="{ visible: hovered || isDragging }"
                    width="3" height="12" viewBox="0 0 3 12"
                >
                    <rect x="0" y="0" width="3" height="12" rx="1.5" ry="1.5" fill="#aaa" />
                </svg>
            </div>

            <!-- Progress drag handle (SVG pentagon cursor) -->
            <svg
                v-if="showProgress"
                class="gantt-bar-progress-handle"
                :class="{ visible: hovered || isDragging }"
                :style="{ left: `${progressWidth - 6}px` }"
                width="12" height="14" viewBox="0 0 12 14"
                @pointerdown="emit('progressDragStart', $event)"
            >
                <path
                    d="M6 0 L1 3 L1 11 Q1 13 3 13 L9 13 Q11 13 11 11 L11 3 L6 0 Z"
                    stroke="#d8d8d8" fill="#fff"
                />
            </svg>
            <span
                v-if="showProgress && (hovered || isDragging)"
                class="gantt-bar-progress-label"
                :style="{ left: `${progressWidth}px` }"
            >{{ actualProgress }}%</span>
        </div>

        <template #overlay>
            <VortDropdownMenuItem @click="emit('clearDate', 'start')">删除开始日期</VortDropdownMenuItem>
            <VortDropdownMenuItem @click="emit('clearDate', 'end')">删除结尾日期</VortDropdownMenuItem>
            <VortDropdownMenuSeparator />
            <VortDropdownMenuItem danger @click="emit('clearDate', 'both')">删除两个日期</VortDropdownMenuItem>
        </template>
    </VortDropdown>

    <!-- No-time placeholder -->
    <div
        v-else
        class="gantt-bar-empty"
        :style="{ height: `${rowHeight}px` }"
        @mousemove="onEmptyMouseMove"
        @mouseleave="hoverPreview = null"
        @click="emit('clickCreate', $event)"
    >
        <div
            v-if="hoverPreview"
            class="gantt-bar-create-preview"
            :style="{
                left: `${hoverPreview.left}px`,
                width: `${hoverPreview.width}px`,
            }"
        >
            <span class="gantt-bar-create-date is-left">{{ hoverPreview.startLabel }}</span>
            <span class="gantt-bar-create-text">点击创建</span>
            <span class="gantt-bar-create-date is-right">{{ hoverPreview.endLabel }}</span>
        </div>
    </div>
</template>

<style scoped>
.gantt-bar {
    position: absolute;
    top: 11px;
    border-radius: 4px;
    cursor: grab;
    display: flex;
    align-items: center;
    overflow: visible;
    z-index: 2;
    transition: box-shadow 0.15s;
    background: var(--bar-bg, #e5e7eb);
}

.gantt-bar:hover {
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
    z-index: 3;
}

.gantt-bar.is-dragging {
    opacity: 0.85;
    z-index: 10;
    cursor: grabbing;
    transition: none;
}

.gantt-bar.is-dragging .gantt-bar-progress {
    transition: none;
}

.gantt-bar .gantt-bar-progress {
    background: var(--bar-fill, #9ca3af);
}

.gantt-bar .gantt-bar-text {
    color: #374151;
}

.gantt-bar-progress {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    max-width: 100%;
    transition: width 0.1s;
    pointer-events: none;
    overflow: hidden;
}

.gantt-bar-text {
    font-size: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    pointer-events: none;
    line-height: 1;
}

.gantt-bar-text.inside {
    position: relative;
    z-index: 1;
    padding: 0 8px;
    max-width: 100%;
}

.gantt-bar-text.outside {
    position: absolute;
    z-index: 1;
    color: #374151;
    max-width: 200px;
}

.gantt-bar-handle-zone {
    position: absolute;
    top: 0;
    width: 10px;
    height: 100%;
    cursor: ew-resize;
    z-index: 5;
    display: flex;
    align-items: center;
    justify-content: center;
}

.gantt-bar-handle-zone.left {
    left: 0;
}

.gantt-bar-handle-zone.right {
    right: 0;
}

.gantt-bar-handle {
    opacity: 0;
    transition: opacity 0.15s;
    flex-shrink: 0;
}

.gantt-bar-handle.visible {
    opacity: 1;
}

.gantt-bar-progress-handle {
    position: absolute;
    bottom: -15px;
    cursor: ew-resize;
    z-index: 6;
    opacity: 0;
    transition: opacity 0.15s;
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.1));
}

.gantt-bar-progress-handle:hover path {
    stroke: #bbb;
}

.gantt-bar-progress-handle.visible {
    opacity: 1;
}

.gantt-bar-progress-label {
    position: absolute;
    top: -18px;
    transform: translateX(-50%);
    font-size: 11px;
    color: #6b7280;
    white-space: nowrap;
    background: #fff;
    padding: 1px 4px;
    border-radius: 3px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    pointer-events: none;
}

.gantt-bar-empty {
    position: relative;
    width: 100%;
    cursor: pointer;
}

.gantt-bar-create-preview {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    align-items: center;
    justify-content: center;
    height: 28px;
    background: rgba(191, 219, 254, 0.5);
    border-radius: 4px;
    pointer-events: none;
}

.gantt-bar-create-text {
    font-size: 12px;
    color: var(--vort-primary, #1456f0);
    white-space: nowrap;
}

.gantt-bar-create-date {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    font-size: 11px;
    color: #9ca3af;
    white-space: nowrap;
}

.gantt-bar-create-date.is-left {
    right: calc(100% + 6px);
}

.gantt-bar-create-date.is-right {
    left: calc(100% + 6px);
}
</style>
