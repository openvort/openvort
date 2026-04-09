import { ref, type Ref } from "vue";
import dayjs from "dayjs";
import type { GanttDragState, GanttBarData } from "./gantt.types";

export interface UseGanttDragOptions {
    xToDate: (x: number) => Date;
    dateToX: (date: Date) => number;
    scrollContainer?: Ref<HTMLElement | null>;
    onTimeChange: (rowId: string, startDate: string, endDate: string) => void;
    onProgressChange: (rowId: string, progress: number) => void;
    onCreateTime: (rowId: string, startDate: string, endDate: string) => void;
}

function snapToDay(date: Date): string {
    return dayjs(date).format("YYYY-MM-DD");
}

function endOfDay(date: Date): Date {
    return dayjs(date).endOf("day").toDate();
}

export function useGanttDrag(options: UseGanttDragOptions) {
    const { xToDate, dateToX, scrollContainer, onTimeChange, onProgressChange, onCreateTime } = options;
    const dragState = ref<GanttDragState | null>(null);
    const dragPreview = ref<{ left: number; width: number; progress?: number } | null>(null);

    function startResizeLeft(e: PointerEvent, bar: GanttBarData) {
        if (e.button !== 0 || !bar.startDate || !bar.endDate) return;
        e.preventDefault();
        e.stopPropagation();
        const target = e.currentTarget as HTMLElement;
        target.setPointerCapture(e.pointerId);

        dragState.value = {
            type: "resize-left",
            rowId: bar.row.backendId || bar.row.workNo,
            startX: e.clientX,
            initialStartDate: bar.startDate,
            initialEndDate: bar.endDate,
            initialProgress: bar.progress,
        };

        const left = dateToX(bar.startDate);
        const right = dateToX(endOfDay(bar.endDate));
        dragPreview.value = { left, width: right - left };
    }

    function startResizeRight(e: PointerEvent, bar: GanttBarData) {
        if (e.button !== 0 || !bar.startDate || !bar.endDate) return;
        e.preventDefault();
        e.stopPropagation();
        const target = e.currentTarget as HTMLElement;
        target.setPointerCapture(e.pointerId);

        dragState.value = {
            type: "resize-right",
            rowId: bar.row.backendId || bar.row.workNo,
            startX: e.clientX,
            initialStartDate: bar.startDate,
            initialEndDate: bar.endDate,
            initialProgress: bar.progress,
        };

        const left = dateToX(bar.startDate);
        const right = dateToX(endOfDay(bar.endDate));
        dragPreview.value = { left, width: right - left };
    }

    function startMove(e: PointerEvent, bar: GanttBarData) {
        if (e.button !== 0 || !bar.startDate || !bar.endDate) return;
        e.preventDefault();
        e.stopPropagation();
        const target = e.currentTarget as HTMLElement;
        target.setPointerCapture(e.pointerId);

        dragState.value = {
            type: "move",
            rowId: bar.row.backendId || bar.row.workNo,
            startX: e.clientX,
            initialStartDate: bar.startDate,
            initialEndDate: bar.endDate,
            initialProgress: bar.progress,
        };

        const left = dateToX(bar.startDate);
        const right = dateToX(endOfDay(bar.endDate));
        dragPreview.value = { left, width: right - left };
    }

    function startProgressDrag(e: PointerEvent, bar: GanttBarData) {
        if (e.button !== 0 || !bar.startDate || !bar.endDate) return;
        e.preventDefault();
        e.stopPropagation();
        const target = e.currentTarget as HTMLElement;
        target.setPointerCapture(e.pointerId);

        dragState.value = {
            type: "progress",
            rowId: bar.row.backendId || bar.row.workNo,
            startX: e.clientX,
            initialStartDate: bar.startDate,
            initialEndDate: bar.endDate,
            initialProgress: bar.progress,
        };

        const left = dateToX(bar.startDate);
        const right = dateToX(endOfDay(bar.endDate));
        dragPreview.value = { left, width: right - left, progress: bar.progress };
    }

    function snapStartX(x: number): number {
        return dateToX(dayjs(xToDate(x)).add(1, "ms").startOf("day").toDate());
    }

    function snapEndX(x: number): number {
        return dateToX(endOfDay(xToDate(x)));
    }

    function onPointerMove(e: PointerEvent) {
        const state = dragState.value;
        if (!state) return;

        const deltaX = e.clientX - state.startX;
        const initialLeft = dateToX(state.initialStartDate);
        const initialRight = dateToX(endOfDay(state.initialEndDate));
        const barWidth = initialRight - initialLeft;

        if (state.type === "move") {
            const newStart = dayjs(xToDate(initialLeft + deltaX)).add(1, "ms").startOf("day");
            const durationDays = dayjs(state.initialEndDate).diff(dayjs(state.initialStartDate), "day");
            const newEnd = newStart.add(durationDays, "day");
            const snappedLeft = dateToX(newStart.toDate());
            const snappedRight = dateToX(endOfDay(newEnd.toDate()));
            dragPreview.value = { left: snappedLeft, width: snappedRight - snappedLeft };
        } else if (state.type === "resize-left") {
            const snappedLeft = Math.min(snapStartX(initialLeft + deltaX), initialRight - 4);
            dragPreview.value = { left: snappedLeft, width: initialRight - snappedLeft };
        } else if (state.type === "resize-right") {
            const snappedRight = Math.max(snapEndX(initialRight + deltaX), initialLeft + 4);
            dragPreview.value = { left: initialLeft, width: snappedRight - initialLeft };
        } else if (state.type === "progress") {
            const progressX = initialLeft + (barWidth * state.initialProgress) / 100 + deltaX;
            const clampedX = Math.max(initialLeft, Math.min(progressX, initialRight));
            const newProgress = barWidth > 0 ? Math.round(((clampedX - initialLeft) / barWidth) * 100) : 0;
            dragPreview.value = { left: initialLeft, width: barWidth, progress: newProgress };
        }
    }

    function onPointerUp(_e: PointerEvent) {
        const state = dragState.value;
        const preview = dragPreview.value;
        if (!state || !preview) {
            dragState.value = null;
            dragPreview.value = null;
            return;
        }

        if (state.type === "move") {
            const newStart = dayjs(xToDate(preview.left)).add(1, "ms").startOf("day");
            const durationDays = dayjs(state.initialEndDate).diff(dayjs(state.initialStartDate), "day");
            const newEnd = newStart.add(durationDays, "day");
            onTimeChange(state.rowId, newStart.format("YYYY-MM-DD"), newEnd.format("YYYY-MM-DD"));
        } else if (state.type === "resize-left") {
            const newStart = dayjs(xToDate(preview.left)).add(1, "ms").startOf("day");
            onTimeChange(state.rowId, newStart.format("YYYY-MM-DD"), snapToDay(state.initialEndDate));
        } else if (state.type === "resize-right") {
            const newEnd = xToDate(preview.left + preview.width);
            onTimeChange(state.rowId, snapToDay(state.initialStartDate), snapToDay(newEnd));
        } else if (state.type === "progress" && preview.progress !== undefined) {
            onProgressChange(state.rowId, preview.progress);
        }

        const scrollEl = scrollContainer?.value;
        const savedScroll = scrollEl?.scrollLeft;
        const barLeft = preview.left;
        const barRight = preview.left + preview.width;

        dragState.value = null;
        dragPreview.value = null;

        if (scrollEl && savedScroll !== undefined) {
            const viewEnd = savedScroll + scrollEl.clientWidth;
            const isVisible = barRight > savedScroll && barLeft < viewEnd;
            requestAnimationFrame(() => {
                scrollEl.scrollLeft = isVisible
                    ? savedScroll
                    : Math.max(0, barLeft - 50);
            });
        }
    }

    function handleClickCreate(bar: GanttBarData, e: MouseEvent, timelineEl: HTMLElement) {
        const rect = timelineEl.getBoundingClientRect();
        const clickX = e.clientX - rect.left + timelineEl.scrollLeft;
        const clickDate = dayjs(xToDate(clickX));
        const startDate = clickDate.format("YYYY-MM-DD");
        const endDate = clickDate.add(7, "day").format("YYYY-MM-DD");
        const rowId = bar.row.backendId || bar.row.workNo;
        onCreateTime(rowId, startDate, endDate);
    }

    return {
        dragState,
        dragPreview,
        startMove,
        startResizeLeft,
        startResizeRight,
        startProgressDrag,
        onPointerMove,
        onPointerUp,
        handleClickCreate,
    };
}
