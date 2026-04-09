<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from "vue";
import dayjs from "dayjs";
import type { RowItem } from "@/components/vort-biz/work-item/WorkItemTable.types";
import type { GanttZoomLevel, GanttBarData } from "./gantt.types";
import GanttHeader from "./GanttHeader.vue";
import GanttBar from "./GanttBar.vue";
import { useGanttTimeline } from "./useGanttTimeline";
import { useGanttDrag } from "./useGanttDrag";

const props = defineProps<{
    rows: RowItem[];
    rowTops: number[];
    rowHeights: number[];
    bodyHeight: number;
    tableHeaderHeight: number;
    rowHeight: number;
    zoomLevel: GanttZoomLevel;
}>();

const emit = defineEmits<{
    timeChange: [rowId: string, startDate: string, endDate: string];
    progressChange: [rowId: string, progress: number];
    createTime: [rowId: string, startDate: string, endDate: string];
    clearDate: [rowId: string, type: "start" | "end" | "both"];
    "update:zoomLevel": [level: GanttZoomLevel];
}>();

const rowsRef = computed(() => props.rows);
const bodyScrollRef = ref<HTMLElement | null>(null);

const {
    zoomLevel,
    scrollLeft,
    containerWidth,
    barDataList,
    timelineConfig,
    dateToX,
    xToDate,
    getBarPosition,
    getTodayX,
    getOutOfRangeInfo,
    scrollToToday,
    scrollToDate,
} = useGanttTimeline(rowsRef);

watch(() => props.zoomLevel, (v) => { zoomLevel.value = v; }, { immediate: true });
watch(zoomLevel, (v) => {
    emit("update:zoomLevel", v);
    nextTick(() => {
        scrollToToday();
        if (bodyScrollRef.value) {
            bodyScrollRef.value.scrollLeft = scrollLeft.value;
        }
    });
});

const {
    dragState,
    dragPreview,
    startMove,
    startResizeLeft,
    startResizeRight,
    startProgressDrag,
    onPointerMove,
    onPointerUp,
    handleClickCreate,
} = useGanttDrag({
    xToDate,
    dateToX,
    scrollContainer: bodyScrollRef,
    onTimeChange: (rowId, start, end) => emit("timeChange", rowId, start, end),
    onProgressChange: (rowId, progress) => emit("progressChange", rowId, progress),
    onCreateTime: (rowId, start, end) => emit("createTime", rowId, start, end),
});

const todayX = computed(() => getTodayX());

const viewRange = computed(() => ({
    start: scrollLeft.value,
    end: scrollLeft.value + containerWidth.value,
}));

function getRowOutOfRange(bar: GanttBarData) {
    return getOutOfRangeInfo(bar, viewRange.value.start, viewRange.value.end);
}

function onBodyScroll() {
    const el = bodyScrollRef.value;
    if (!el) return;
    scrollLeft.value = el.scrollLeft;
}

function handleOutOfRangeClick(bar: GanttBarData) {
    const info = getRowOutOfRange(bar);
    if (!info || !bodyScrollRef.value) return;
    bodyScrollRef.value.scrollLeft = Math.max(0, info.scrollToX);
}

function doScrollToToday() {
    scrollToToday();
    nextTick(() => {
        if (bodyScrollRef.value) {
            bodyScrollRef.value.scrollLeft = scrollLeft.value;
        }
    });
}

let resizeObs: ResizeObserver | null = null;

onMounted(() => {
    if (bodyScrollRef.value) {
        resizeObs = new ResizeObserver(() => {
            if (bodyScrollRef.value) containerWidth.value = bodyScrollRef.value.clientWidth;
        });
        resizeObs.observe(bodyScrollRef.value);
    }
    requestAnimationFrame(() => {
        if (bodyScrollRef.value) {
            containerWidth.value = bodyScrollRef.value.clientWidth;
        }
        scrollToToday();
        if (bodyScrollRef.value) {
            bodyScrollRef.value.scrollLeft = scrollLeft.value;
        }
    });
});

onBeforeUnmount(() => { resizeObs?.disconnect(); });

const zoomOptions: { value: GanttZoomLevel; label: string }[] = [
    { value: "day", label: "日" },
    { value: "week", label: "周" },
    { value: "month", label: "月" },
    { value: "quarter", label: "季" },
];

function getBarRowId(bar: GanttBarData) {
    return bar.row.backendId || bar.row.workNo;
}

defineExpose({ scrollToToday: doScrollToToday });
</script>

<template>
    <div
        class="gantt-timeline"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
    >
        <!-- Header -->
        <div class="gantt-timeline-header-wrap">
            <div class="gantt-timeline-header-scroll" :style="{ transform: `translateX(-${scrollLeft}px)` }">
                <GanttHeader :config="timelineConfig" />
            </div>
        </div>

        <!-- Body -->
        <div
            ref="bodyScrollRef"
            class="gantt-timeline-body"
            @scroll.passive="onBodyScroll"
        >
            <div
                class="gantt-timeline-canvas"
                :style="{ width: `${timelineConfig.totalWidth}px`, height: `${bodyHeight || rows.length * rowHeight}px` }"
            >
                <div
                    v-if="todayX !== null"
                    class="gantt-today-line"
                    :style="{ left: `${todayX}px` }"
                />

                <div class="gantt-grid-columns">
                    <div
                        v-for="(tick, i) in timelineConfig.ticks"
                        :key="i"
                        class="gantt-grid-col"
                        :class="{ 'is-weekend': tick.isWeekend }"
                        :style="{ width: `${tick.width}px` }"
                    />
                </div>

                <div
                    v-for="(bar, idx) in barDataList"
                    :key="getBarRowId(bar) || idx"
                    class="gantt-row"
                    :style="{ height: `${rowHeight}px`, top: `${idx * rowHeight}px` }"
                >
                        <GanttBar
                            :bar="bar"
                            :left="getBarPosition(bar)?.left ?? 0"
                            :width="getBarPosition(bar)?.width ?? 0"
                            :scroll-left="scrollLeft"
                            :preview-left="dragState?.rowId === getBarRowId(bar) ? dragPreview?.left : undefined"
                            :preview-width="dragState?.rowId === getBarRowId(bar) ? dragPreview?.width : undefined"
                            :preview-progress="dragState?.rowId === getBarRowId(bar) ? dragPreview?.progress : undefined"
                            :is-dragging="dragState?.rowId === getBarRowId(bar)"
                            :row-height="rowHeight"
                            :x-to-date="xToDate"
                            :date-to-x="dateToX"
                        @move-start="startMove($event, bar)"
                        @resize-left-start="startResizeLeft($event, bar)"
                        @resize-right-start="startResizeRight($event, bar)"
                        @progress-drag-start="startProgressDrag($event, bar)"
                        @click-create="handleClickCreate(bar, $event, bodyScrollRef!)"
                        @clear-date="(type: 'start' | 'end' | 'both') => emit('clearDate', getBarRowId(bar), type)"
                    />

                    <span
                        v-if="getRowOutOfRange(bar)"
                        class="gantt-oor-label"
                        :class="`gantt-oor-${getRowOutOfRange(bar)!.direction}`"
                        :style="getRowOutOfRange(bar)!.direction === 'left'
                            ? { left: `${scrollLeft + 4}px` }
                            : { left: `${scrollLeft + containerWidth - 180}px` }"
                        @click="handleOutOfRangeClick(bar)"
                    >{{ getRowOutOfRange(bar)!.text }}</span>
                </div>
            </div>
        </div>

        <!-- Bottom controls -->
        <div class="gantt-footer">
            <button class="gantt-today-btn" @click="doScrollToToday">今天</button>
            <div class="gantt-zoom-tabs">
                <button
                    v-for="opt in zoomOptions"
                    :key="opt.value"
                    class="gantt-zoom-tab"
                    :class="{ active: zoomLevel === opt.value }"
                    @click="zoomLevel = opt.value"
                >
                    {{ opt.label }}
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.gantt-timeline {
    display: flex;
    flex-direction: column;
    min-width: 0;
    flex: 1;
    position: relative;
    background: #fff;
}

.gantt-timeline::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    bottom: 0;
    width: 8px;
    //background: linear-gradient(to right, rgba(0, 0, 0, 0.06), transparent);
    pointer-events: none;
    z-index: 20;
}


.gantt-timeline-header-wrap {
    flex-shrink: 0;
    overflow: hidden;
    position: sticky;
    top: 0;
    z-index: 10;
    background: #fff;
    border-bottom: 1px solid #e5e7eb;
}

.gantt-timeline-header-scroll {
    display: inline-block;
    min-width: max-content;
    will-change: transform;
}

.gantt-timeline-body {
    overflow-x: auto;
    overflow-y: hidden;
    flex: 1;
    position: relative;
}

.gantt-timeline-canvas {
    position: relative;
}

.gantt-grid-columns {
    display: flex;
    position: absolute;
    top: 0;
    left: 0;
    bottom: 0;
    pointer-events: none;
}

.gantt-grid-col {
    height: 100%;
    flex-shrink: 0;
    box-sizing: border-box;
}

.gantt-grid-col.is-weekend {
    background: #f9fafb;
}

.gantt-today-line {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background: rgba(20, 86, 240, 0.3);
    z-index: 4;
    pointer-events: none;
}

.gantt-row {
    position: absolute;
    left: 0;
    right: 0;
    border-bottom: 1px solid #f5f5f5;
}

.gantt-oor-label {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    font-size: 12px;
    color: #9ca3af;
    white-space: nowrap;
    cursor: pointer;
    z-index: 6;
}

.gantt-oor-label:hover {
    color: var(--vort-primary, #1456f0);
}

.gantt-oor-label.gantt-oor-left::before {
    content: ">";
}

.gantt-oor-label.gantt-oor-right::before {
    content: "<";
}

.gantt-footer {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    border-top: 1px solid #e5e7eb;
    flex-shrink: 0;
    background: #fff;
    position: sticky;
    bottom: 0;
    z-index: 10;
}

.gantt-today-btn {
    font-size: 13px;
    color: #374151;
    background: #fff;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 4px 12px;
    cursor: pointer;
    transition: all 0.15s;
}

.gantt-today-btn:hover {
    border-color: var(--vort-primary, #1456f0);
    color: var(--vort-primary, #1456f0);
}

.gantt-zoom-tabs {
    display: flex;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    overflow: hidden;
}

.gantt-zoom-tab {
    font-size: 13px;
    color: #6b7280;
    background: #fff;
    border: none;
    border-right: 1px solid #d1d5db;
    padding: 4px 12px;
    cursor: pointer;
    transition: all 0.15s;
}

.gantt-zoom-tab:last-child {
    border-right: none;
}

.gantt-zoom-tab:hover {
    background: #f3f4f6;
}

.gantt-zoom-tab.active {
    background: var(--vort-primary, #1456f0);
    color: #fff;
}
</style>
