<script setup lang="ts">
import type { GanttTimelineConfig } from "./gantt.types";

defineProps<{
    config: GanttTimelineConfig;
}>();
</script>

<template>
    <div class="gantt-header" :style="{ width: `${config.totalWidth}px` }">
        <div class="gantt-header-top">
            <div
                v-for="(group, i) in config.headerGroups"
                :key="i"
                class="gantt-header-group"
                :style="{ width: `${group.width}px` }"
            >
                {{ group.label }}
            </div>
        </div>
        <div class="gantt-header-bottom">
            <div
                v-for="(tick, i) in config.ticks"
                :key="i"
                class="gantt-header-tick"
                :class="{
                    'is-today': tick.isToday,
                    'is-weekend': tick.isWeekend,
                }"
                :style="{ width: `${tick.width}px` }"
            >
                {{ tick.label }}
            </div>
        </div>
    </div>
</template>

<style scoped>
.gantt-header {
    flex-shrink: 0;
    user-select: none;
}

.gantt-header-top {
    display: flex;
    height: 24px;
    border-bottom: 1px solid #f0f0f0;
}

.gantt-header-group {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    color: #6b7280;
    font-weight: 500;
    border-right: 1px solid #f0f0f0;
    flex-shrink: 0;
}

.gantt-header-bottom {
    display: flex;
    height: 24px;
}

.gantt-header-tick {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    color: #9ca3af;
    border-right: 1px solid #f0f0f0;
    flex-shrink: 0;
    box-sizing: border-box;
}

.gantt-header-tick.is-today {
    background: var(--vort-primary, #1456f0);
    color: #fff;
    font-weight: 600;
}

.gantt-header-tick.is-weekend {
    background: #f9fafb;
}
</style>
