<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{
    minLeft?: number;
    maxLeft?: number;
}>();

const emit = defineEmits<{
    drag: [deltaX: number];
    dragEnd: [];
}>();

const isDragging = ref(false);
let startX = 0;

function onPointerDown(e: PointerEvent) {
    e.preventDefault();
    isDragging.value = true;
    startX = e.clientX;
    const target = e.currentTarget as HTMLElement;
    target.setPointerCapture(e.pointerId);
}

function onPointerMove(e: PointerEvent) {
    if (!isDragging.value) return;
    const delta = e.clientX - startX;
    startX = e.clientX;
    emit("drag", delta);
}

function onPointerUp(_e: PointerEvent) {
    if (!isDragging.value) return;
    isDragging.value = false;
    emit("dragEnd");
}
</script>

<template>
    <div
        class="gantt-divider"
        :class="{ 'is-dragging': isDragging }"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
    >
        <div class="gantt-divider-line" />
    </div>
</template>

<style scoped>
.gantt-divider {
    width: 6px;
    flex-shrink: 0;
    cursor: col-resize;
    position: relative;
    z-index: 12;
    display: flex;
    align-items: stretch;
    justify-content: center;
    user-select: none;
    touch-action: none;
    margin-left: -3px;
    margin-right: -3px;
}

.gantt-divider:hover .gantt-divider-line,
.gantt-divider.is-dragging .gantt-divider-line {
    background: var(--vort-primary, #1456f0);
    width: 3px;
}

.gantt-divider-line {
    width: 1px;
    background: #e5e7eb;
    transition: all 0.15s;
}
</style>
