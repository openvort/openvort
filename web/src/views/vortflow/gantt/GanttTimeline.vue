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
    canUndo?: boolean;
    canRedo?: boolean;
}>();

const emit = defineEmits<{
    timeChange: [rowId: string, startDate: string, endDate: string];
    progressChange: [rowId: string, progress: number];
    createTime: [rowId: string, startDate: string, endDate: string];
    clearDate: [rowId: string, type: "start" | "end" | "both"];
    iconTimeChange: [rowId: string, field: "testTime" | "draftTime" | "releaseTime", date: string];
    clearIconTime: [rowId: string, field: "testTime" | "draftTime" | "releaseTime"];
    "update:zoomLevel": [level: GanttZoomLevel];
    undo: [];
    redo: [];
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
    iconDragPreviewX,
    startMove,
    startResizeLeft,
    startResizeRight,
    startProgressDrag,
    startIconDrag,
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
    onIconTimeChange: (rowId, field, date) => emit("iconTimeChange", rowId, field, date),
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

function onKeydown(e: KeyboardEvent) {
    const mod = e.metaKey || e.ctrlKey;
    if (!mod || e.key.toLowerCase() !== "z") return;
    e.preventDefault();
    if (e.shiftKey) {
        emit("redo");
    } else {
        emit("undo");
    }
}

onMounted(() => {
    window.addEventListener("keydown", onKeydown);
});

onBeforeUnmount(() => {
    resizeObs?.disconnect();
    window.removeEventListener("keydown", onKeydown);
});

const zoomOptions: { value: GanttZoomLevel; label: string }[] = [
    { value: "day", label: "日" },
    { value: "week", label: "周" },
    { value: "month", label: "月" },
    { value: "quarter", label: "季" },
];

function getBarRowId(bar: GanttBarData) {
    return bar.row.backendId || bar.row.workNo;
}

const iconDragTypeMap: Record<string, string> = { testTime: "icon-test", draftTime: "icon-draft", releaseTime: "icon-release" };

function getIconX(bar: GanttBarData, field: "testTime" | "draftTime" | "releaseTime"): number | null {
    const rowId = getBarRowId(bar);
    if (dragState.value?.rowId === rowId
        && dragState.value.type === iconDragTypeMap[field]
        && iconDragPreviewX.value !== null) {
        return iconDragPreviewX.value;
    }
    const dateStr = bar.row[field];
    if (!dateStr) return null;
    return dateToX(dayjs(dateStr + "T12:00:00").toDate());
}

function isIconInsideBar(bar: GanttBarData, field: "testTime" | "draftTime" | "releaseTime"): boolean {
    const ix = getIconX(bar, field);
    if (ix === null) return false;
    const rowId = getBarRowId(bar);
    const pos = getBarPosition(bar);
    if (!pos) return false;
    const left = (dragState.value?.rowId === rowId ? dragPreview.value?.left : undefined) ?? pos.left;
    const width = (dragState.value?.rowId === rowId ? dragPreview.value?.width : undefined) ?? pos.width;
    return ix >= left && ix <= left + width;
}

const iconLabelMap: Record<string, string> = { testTime: "提测时间", draftTime: "出稿时间", releaseTime: "发布时间" };

function getIconTooltip(bar: GanttBarData, field: "testTime" | "draftTime" | "releaseTime"): string {
    const label = iconLabelMap[field];
    const rowId = getBarRowId(bar);
    if (dragState.value?.rowId === rowId
        && dragState.value.type === iconDragTypeMap[field]
        && iconDragPreviewX.value !== null) {
        const d = dayjs(xToDate(iconDragPreviewX.value)).format("YYYY-MM-DD");
        return `${label}: ${d}`;
    }
    const dateStr = bar.row[field];
    return dateStr ? `${label}: ${dateStr}` : label;
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
                        @add-icon-time="(field: 'testTime' | 'draftTime' | 'releaseTime', date: string) => emit('iconTimeChange', getBarRowId(bar), field, date)"
                    />

                    <!-- Test time icon (需求 only) -->
                    <VortDropdown
                        v-if="bar.row.type === '需求' && getIconX(bar, 'testTime') !== null"
                        trigger="contextMenu"
                    >
                        <svg
                            class="gantt-icon-marker gantt-icon-test"
                            :class="{
                                'is-dragging': dragState?.rowId === getBarRowId(bar) && dragState?.type === 'icon-test',
                                'is-inside': isIconInsideBar(bar, 'testTime'),
                            }"
                            :style="{ left: `${getIconX(bar, 'testTime')! - 7}px` }"
                            width="14" height="14" viewBox="0 0 1024 1024"
                            @pointerdown="startIconDrag($event, bar, 'testTime')"
                        >
                            <title>{{ getIconTooltip(bar, 'testTime') }}</title>
                            <path d="M590.1 243.7L573.6 161.1H202.1v701.8h82.6V573.9h231.1l16.6 82.6h288.9V243.7z" fill="currentColor"/>
                        </svg>
                        <template #overlay>
                            <VortDropdownMenuItem danger @click="emit('clearIconTime', getBarRowId(bar), 'testTime')">删除提测时间</VortDropdownMenuItem>
                        </template>
                    </VortDropdown>

                    <!-- Draft time icon (需求 only) -->
                    <VortDropdown
                        v-if="bar.row.type === '需求' && getIconX(bar, 'draftTime') !== null"
                        trigger="contextMenu"
                    >
                        <svg
                            class="gantt-icon-marker gantt-icon-draft"
                            :class="{
                                'is-dragging': dragState?.rowId === getBarRowId(bar) && dragState?.type === 'icon-draft',
                                'is-inside': isIconInsideBar(bar, 'draftTime'),
                            }"
                            :style="{ left: `${getIconX(bar, 'draftTime')! - 6}px` }"
                            width="12" height="12" viewBox="0 0 1024 1024"
                            @pointerdown="startIconDrag($event, bar, 'draftTime')"
                        >
                            <title>{{ getIconTooltip(bar, 'draftTime') }}</title>
                            <path d="M962.048 301.568c29.184-29.184 29.184-75.776 0-104.96l-141.824-141.824c-28.672-29.184-75.776-29.184-104.96 0l-144.384 144.384 246.784 247.296 144.384-144.896z" fill="currentColor"/>
                            <path d="M137.216 632.832c-14.848 14.848-26.112 33.792-32.768 53.76L43.52 909.824c-8.192 26.624 6.656 54.784 33.28 63.488 9.728 3.072 20.48 3.072 30.208 0l223.232-60.928c20.48-6.656 38.912-17.408 54.272-32.768L440.32 823.808l-246.784-247.296-56.32 56.32zM312.832 71.168c-31.232-31.744-82.944-31.744-114.688 0l-0.512 0.512-133.632 133.632c-31.744 31.744-31.744 82.944 0 114.688L127.488 384l117.76-118.272c15.872-15.872 41.472-15.872 57.344 0 15.872 15.872 15.872 41.472 0 57.344L184.832 440.32l57.344 57.344L312.32 427.52c15.36-15.872 40.96-16.384 56.832-0.512l0.512 0.512c15.872 15.872 15.872 41.472 0 57.344l-69.632 70.144 57.344 57.344 117.248-117.76c15.872-15.872 41.472-15.872 57.344 0s15.872 41.472 0 57.344l-118.784 116.736L471.04 727.04l0.512-0.512 69.12-69.632c15.872-15.872 41.472-15.872 57.344 0s15.872 41.472 0 57.344L528.384 783.36l-0.512 0.512 57.344 57.344 117.248-117.248c15.872-15.872 41.472-15.872 57.344 0 15.872 15.872 15.872 41.472 0 57.344l-117.76 116.736 68.608 68.608c31.744 31.744 82.944 31.744 114.688 0.512l0.512-0.512 134.144-134.144c31.744-31.744 31.744-82.944 0-114.688L312.832 71.168z" fill="currentColor"/>
                        </svg>
                        <template #overlay>
                            <VortDropdownMenuItem danger @click="emit('clearIconTime', getBarRowId(bar), 'draftTime')">删除出稿时间</VortDropdownMenuItem>
                        </template>
                    </VortDropdown>

                    <!-- Release time icon (需求 only) -->
                    <VortDropdown
                        v-if="bar.row.type === '需求' && getIconX(bar, 'releaseTime') !== null"
                        trigger="contextMenu"
                    >
                        <svg
                            class="gantt-icon-marker gantt-icon-release"
                            :class="{
                                'is-dragging': dragState?.rowId === getBarRowId(bar) && dragState?.type === 'icon-release',
                                'is-inside': isIconInsideBar(bar, 'releaseTime'),
                            }"
                            :style="{ left: `${getIconX(bar, 'releaseTime')! - 6}px` }"
                            width="12" height="12" viewBox="0 0 1024 1024"
                            @pointerdown="startIconDrag($event, bar, 'releaseTime')"
                        >
                            <title>{{ getIconTooltip(bar, 'releaseTime') }}</title>
                            <path d="M920.1 91.8c-15.4-7.7-30.9-7.7-38.6 0L108.5 475.5c-15.5 0-23.2 15.4-23.2 30.7 0 15.4 7.7 30.7 15.5 30.7l185.5 115.1c15.5 7.7 30.9 7.7 46.4-7.7l409.7-368.3 15.5 7.7-371 391.3c-7.7 7.7-7.7 15.4-7.7 23v168.8c0 15.4 7.7 30.7 23.2 38.4 15.5 7.7 30.9 0 38.7-7.7l92.7-92.1 185.5 122.8c7.7 7.7 15.5 7.7 23.2 7.7h15.5c15.4-7.7 23.2-15.4 23.2-30.7l154.6-767.4c0-23-0-38.4-15.5-46z" fill="currentColor"/>
                        </svg>
                        <template #overlay>
                            <VortDropdownMenuItem danger @click="emit('clearIconTime', getBarRowId(bar), 'releaseTime')">删除发布时间</VortDropdownMenuItem>
                        </template>
                    </VortDropdown>

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
            <div class="gantt-footer-left">
                <button
                    class="gantt-undo-btn"
                    :class="{ disabled: !canUndo }"
                    :disabled="!canUndo"
                    title="撤销 (Ctrl+Z)"
                    @click="emit('undo')"
                >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="1 4 1 10 7 10" />
                        <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
                    </svg>
                    <span>撤销</span>
                </button>
                <button
                    class="gantt-undo-btn"
                    :class="{ disabled: !canRedo }"
                    :disabled="!canRedo"
                    title="重做 (Ctrl+Shift+Z)"
                    @click="emit('redo')"
                >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="23 4 23 10 17 10" />
                        <path d="M20.49 15a9 9 0 1 1-2.13-9.36L23 10" />
                    </svg>
                    <span>重做</span>
                </button>
            </div>
            <div class="gantt-footer-right">
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
}

.gantt-icon-marker {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    cursor: ew-resize;
    z-index: 5;
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.1));
    transition: filter 0.1s, color 0.15s;
}

.gantt-icon-test {
    color: #1296db;
}

.gantt-icon-draft {
    color: #3366FF;
}

.gantt-icon-release {
    color: #3299FE;
}

.gantt-icon-marker.is-inside {
    color: #fff;
    filter: drop-shadow(0 1px 3px rgba(0, 0, 0, 0.3));
}

.gantt-icon-marker:hover {
    filter: drop-shadow(0 1px 4px rgba(0, 0, 0, 0.35));
}

.gantt-icon-marker.is-dragging {
    z-index: 12;
    cursor: grabbing;
    filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.4));
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
    justify-content: space-between;
    padding: 8px 12px;
    border-top: 1px solid #e5e7eb;
    flex-shrink: 0;
    background: #fff;
    position: sticky;
    bottom: 0;
    z-index: 10;
}

.gantt-footer-left,
.gantt-footer-right {
    display: flex;
    align-items: center;
    gap: 8px;
}

.gantt-undo-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: #374151;
    background: #fff;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 4px 10px;
    cursor: pointer;
    transition: all 0.15s;
}

.gantt-undo-btn:hover:not(.disabled) {
    border-color: var(--vort-primary, #1456f0);
    color: var(--vort-primary, #1456f0);
}

.gantt-undo-btn.disabled {
    color: #c9cdd4;
    border-color: #e5e7eb;
    cursor: not-allowed;
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
