import { computed, ref, type Ref } from "vue";
import dayjs from "dayjs";
import isoWeek from "dayjs/plugin/isoWeek";
import type { RowItem } from "@/components/vort-biz/work-item/WorkItemTable.types";
import type {
    GanttZoomLevel,
    GanttBarData,
    GanttColumnTick,
    GanttHeaderGroup,
    GanttTimelineConfig,
} from "./gantt.types";
import { STATUS_DOT_COLOR_MAP } from "../composables/useWorkItemColumnFilters";

dayjs.extend(isoWeek);

const DEFAULT_STATUS_COLOR = "#9ca3af";

const COLUMN_WIDTHS: Record<GanttZoomLevel, number> = {
    day: 40,
    week: 120,
    month: 160,
    quarter: 200,
};

const BUFFER_UNITS: Record<GanttZoomLevel, number> = {
    day: 30,
    week: 8,
    month: 3,
    quarter: 2,
};

function parseDate(val: string | undefined | null): Date | null {
    if (!val) return null;
    const d = dayjs(val);
    return d.isValid() ? d.toDate() : null;
}

export function useGanttTimeline(rows: Ref<RowItem[]>) {
    const zoomLevel = ref<GanttZoomLevel>("day");
    const scrollLeft = ref(0);
    const containerWidth = ref(800);

    const barDataList = computed<GanttBarData[]>(() => {
        return rows.value.map((row) => {
            const start = parseDate(row.planStartDate || row.planTime?.[0]);
            const end = parseDate(row.planEndDate || row.planTime?.[1]);
            return {
                row,
                startDate: start,
                endDate: end,
                progress: row.progress ?? 0,
                statusColor: STATUS_DOT_COLOR_MAP[row.status] || DEFAULT_STATUS_COLOR,
                hasTime: !!(start && end),
            };
        });
    });

    const timeRange = computed(() => {
        const now = dayjs();
        let minDate = now;
        let maxDate = now;
        let hasData = false;

        for (const bar of barDataList.value) {
            if (bar.startDate) {
                const d = dayjs(bar.startDate);
                if (!hasData || d.isBefore(minDate)) minDate = d;
                hasData = true;
            }
            if (bar.endDate) {
                const d = dayjs(bar.endDate);
                if (!hasData || d.isAfter(maxDate)) maxDate = d;
                hasData = true;
            }
        }

        const zoom = zoomLevel.value;
        const buf = BUFFER_UNITS[zoom];

        const unitMap: Record<GanttZoomLevel, dayjs.ManipulateType> = {
            day: "day",
            week: "week",
            month: "month",
            quarter: "month",
        };
        const unit = unitMap[zoom];
        const amount = zoom === "quarter" ? buf * 3 : buf;

        return {
            start: minDate.subtract(amount, unit).startOf(zoom === "quarter" ? "month" : unit),
            end: maxDate.add(amount, unit).endOf(zoom === "quarter" ? "month" : unit),
        };
    });

    const timelineConfig = computed<GanttTimelineConfig>(() => {
        const zoom = zoomLevel.value;
        const colWidth = COLUMN_WIDTHS[zoom];
        const { start, end } = timeRange.value;

        const ticks: GanttColumnTick[] = [];
        const headerGroups: GanttHeaderGroup[] = [];

        if (zoom === "day") {
            let cursor = start.startOf("day");
            const endDay = end.endOf("day");
            let currentMonth = "";
            let monthSpan = 0;

            while (cursor.isBefore(endDay) || cursor.isSame(endDay, "day")) {
                const monthLabel = cursor.format("M月");
                const day = cursor.day();
                const isWeekend = day === 0 || day === 6;

                ticks.push({
                    label: String(cursor.date()),
                    startDate: cursor.toDate(),
                    endDate: cursor.endOf("day").toDate(),
                    width: colWidth,
                    isToday: cursor.isSame(dayjs(), "day"),
                    isWeekend,
                });

                if (monthLabel !== currentMonth) {
                    if (currentMonth) {
                        headerGroups.push({ label: currentMonth, span: monthSpan, width: monthSpan * colWidth });
                    }
                    currentMonth = monthLabel;
                    monthSpan = 1;
                } else {
                    monthSpan++;
                }

                cursor = cursor.add(1, "day");
            }
            if (currentMonth) {
                headerGroups.push({ label: currentMonth, span: monthSpan, width: monthSpan * colWidth });
            }
        } else if (zoom === "week") {
            let cursor = start.startOf("isoWeek");
            const endWeek = end.endOf("isoWeek");
            let currentMonth = "";
            let monthSpan = 0;

            while (cursor.isBefore(endWeek)) {
                const weekEnd = cursor.endOf("isoWeek");
                const weekNum = cursor.isoWeek();
                const monthLabel = `${cursor.format("M月")}, ${cursor.format("YYYY")}`;

                ticks.push({
                    label: `${cursor.date()} | 第${weekNum}周`,
                    startDate: cursor.toDate(),
                    endDate: weekEnd.toDate(),
                    width: colWidth,
                    isToday: dayjs().isSame(cursor, "isoWeek"),
                });

                if (monthLabel !== currentMonth) {
                    if (currentMonth) {
                        headerGroups.push({ label: currentMonth, span: monthSpan, width: monthSpan * colWidth });
                    }
                    currentMonth = monthLabel;
                    monthSpan = 1;
                } else {
                    monthSpan++;
                }

                cursor = cursor.add(1, "week");
            }
            if (currentMonth) {
                headerGroups.push({ label: currentMonth, span: monthSpan, width: monthSpan * colWidth });
            }
        } else if (zoom === "month") {
            let cursor = start.startOf("month");
            const endMonth = end.endOf("month");
            let currentYear = "";
            let yearSpan = 0;

            while (cursor.isBefore(endMonth)) {
                const yearLabel = cursor.format("YYYY");

                ticks.push({
                    label: cursor.format("M月"),
                    startDate: cursor.toDate(),
                    endDate: cursor.endOf("month").toDate(),
                    width: colWidth,
                });

                if (yearLabel !== currentYear) {
                    if (currentYear) {
                        headerGroups.push({ label: currentYear, span: yearSpan, width: yearSpan * colWidth });
                    }
                    currentYear = yearLabel;
                    yearSpan = 1;
                } else {
                    yearSpan++;
                }

                cursor = cursor.add(1, "month");
            }
            if (currentYear) {
                headerGroups.push({ label: currentYear, span: yearSpan, width: yearSpan * colWidth });
            }
        } else {
            let cursor = start.startOf("month");
            const monthInQuarter = cursor.month() % 3;
            cursor = cursor.subtract(monthInQuarter, "month");
            const endQuarter = end.endOf("month");
            let currentYear = "";
            let yearSpan = 0;

            while (cursor.isBefore(endQuarter)) {
                const q = Math.floor(cursor.month() / 3) + 1;
                const yearLabel = cursor.format("YYYY");

                ticks.push({
                    label: `第${q}季`,
                    startDate: cursor.toDate(),
                    endDate: cursor.add(2, "month").endOf("month").toDate(),
                    width: colWidth,
                });

                if (yearLabel !== currentYear) {
                    if (currentYear) {
                        headerGroups.push({ label: currentYear, span: yearSpan, width: yearSpan * colWidth });
                    }
                    currentYear = yearLabel;
                    yearSpan = 1;
                } else {
                    yearSpan++;
                }

                cursor = cursor.add(3, "month");
            }
            if (currentYear) {
                headerGroups.push({ label: currentYear, span: yearSpan, width: yearSpan * colWidth });
            }
        }

        const totalWidth = ticks.reduce((sum, t) => sum + t.width, 0);

        return {
            zoomLevel: zoom,
            columnWidth: colWidth,
            headerGroups,
            ticks,
            totalWidth,
            startDate: start.toDate(),
            endDate: end.toDate(),
        };
    });

    function dateToX(date: Date): number {
        const config = timelineConfig.value;
        const { ticks } = config;
        if (!ticks.length) return 0;

        const targetMs = date.getTime();
        let x = 0;

        for (const tick of ticks) {
            const tickStart = tick.startDate.getTime();
            const tickEnd = tick.endDate.getTime();

            if (targetMs <= tickStart) return x;
            if (targetMs >= tickEnd) {
                x += tick.width;
                continue;
            }

            const ratio = (targetMs - tickStart) / (tickEnd - tickStart);
            return x + ratio * tick.width;
        }
        return x;
    }

    function xToDate(x: number): Date {
        const config = timelineConfig.value;
        const { ticks } = config;
        if (!ticks.length) return new Date();

        let accX = 0;
        for (const tick of ticks) {
            if (x <= accX + tick.width) {
                const ratio = (x - accX) / tick.width;
                const tickStart = tick.startDate.getTime();
                const tickEnd = tick.endDate.getTime();
                return new Date(tickStart + ratio * (tickEnd - tickStart));
            }
            accX += tick.width;
        }
        return ticks[ticks.length - 1]!.endDate;
    }

    function getBarPosition(bar: GanttBarData): { left: number; width: number } | null {
        if (!bar.startDate || !bar.endDate) return null;
        const left = dateToX(bar.startDate);
        const endOfDay = dayjs(bar.endDate).endOf("day").toDate();
        const right = dateToX(endOfDay);
        const colWidth = COLUMN_WIDTHS[zoomLevel.value];
        return { left, width: Math.max(right - left, 20) };
    }

    function getTodayX(): number | null {
        const todayStart = dayjs().startOf("day");
        const todayMid = todayStart.add(12, "hour").toDate();
        const config = timelineConfig.value;
        if (todayStart.toDate() < config.startDate || todayStart.toDate() > config.endDate) return null;
        return dateToX(todayMid);
    }

    function getOutOfRangeInfo(bar: GanttBarData, viewStart: number, viewEnd: number) {
        if (!bar.hasTime || !bar.startDate || !bar.endDate) return null;
        const pos = getBarPosition(bar);
        if (!pos) return null;

        const barRight = pos.left + pos.width;
        const isLeftOut = barRight < viewStart;
        const isRightOut = pos.left > viewEnd;

        if (!isLeftOut && !isRightOut) return null;

        const startStr = dayjs(bar.startDate).format("YYYY-MM-DD");
        const endStr = dayjs(bar.endDate).format("YYYY-MM-DD");

        return {
            direction: isLeftOut ? "left" as const : "right" as const,
            text: `${startStr}至${endStr}`,
            scrollToX: pos.left - 50,
        };
    }

    function scrollToToday() {
        const x = getTodayX();
        if (x !== null) {
            scrollLeft.value = Math.max(0, x - containerWidth.value / 3);
        }
    }

    function scrollToDate(date: Date) {
        const x = dateToX(date);
        scrollLeft.value = Math.max(0, x - containerWidth.value / 3);
    }

    return {
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
    };
}
