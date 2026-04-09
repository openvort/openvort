import type { RowItem } from "@/components/vort-biz/work-item/WorkItemTable.types";

export type GanttZoomLevel = "day" | "week" | "month" | "quarter";

export interface GanttBarData {
    row: RowItem;
    startDate: Date | null;
    endDate: Date | null;
    progress: number;
    statusColor: string;
    hasTime: boolean;
}

export interface GanttColumnTick {
    label: string;
    startDate: Date;
    endDate: Date;
    width: number;
    isToday?: boolean;
    isWeekend?: boolean;
}

export interface GanttHeaderGroup {
    label: string;
    span: number;
    width: number;
}

export interface GanttTimelineConfig {
    zoomLevel: GanttZoomLevel;
    columnWidth: number;
    headerGroups: GanttHeaderGroup[];
    ticks: GanttColumnTick[];
    totalWidth: number;
    startDate: Date;
    endDate: Date;
}

export interface GanttDragState {
    type: "move" | "resize-left" | "resize-right" | "progress";
    rowId: string;
    startX: number;
    initialStartDate: Date;
    initialEndDate: Date;
    initialProgress: number;
}
