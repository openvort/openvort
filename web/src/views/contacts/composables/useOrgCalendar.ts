import { ref } from "vue";
import {
    getOrgCalendar, createOrgCalendarEntry, deleteOrgCalendarEntry,
    syncHolidays, getWorkSettings, updateWorkSettings,
} from "@/api";
import { message } from "@/components/vort";
import type { CalendarEntry, WorkSettingsData } from "../types";

export function useOrgCalendar() {
    const calendarEntries = ref<CalendarEntry[]>([]);
    const loadingCalendar = ref(false);
    const calendarYear = ref(new Date().getFullYear());
    const syncingHolidays = ref(false);
    const workSettings = ref<WorkSettingsData | null>(null);

    const calendarDialogOpen = ref(false);
    const calendarForm = ref({ date: "", day_type: "holiday", name: "" });
    const savingCalendar = ref(false);

    const editingWorkSettings = ref(false);
    const savingWorkSettings = ref(false);
    const workSettingsForm = ref({
        timezone: "",
        work_start: "",
        work_end: "",
        lunch_start: "",
        lunch_end: "",
        work_days: [] as number[],
    });

    const weekDayOptions = [
        { label: "周一", value: 1 },
        { label: "周二", value: 2 },
        { label: "周三", value: 3 },
        { label: "周四", value: 4 },
        { label: "周五", value: 5 },
        { label: "周六", value: 6 },
        { label: "周日", value: 7 },
    ];

    const dayTypeOptions = [
        { label: "放假", value: "holiday" },
        { label: "调休上班", value: "workday" },
    ];

    const dayTypeLabel = (val: string) => dayTypeOptions.find(o => o.value === val)?.label || val;
    const dayTypeColor = (val: string) => val === "holiday" ? "red" : "blue";

    async function loadCalendar() {
        loadingCalendar.value = true;
        try {
            const res: any = await getOrgCalendar(calendarYear.value);
            calendarEntries.value = res?.entries || [];
        } catch { /* ignore */ }
        finally { loadingCalendar.value = false; }
    }

    async function loadWorkSettings() {
        try {
            const res: any = await getWorkSettings();
            workSettings.value = res;
        } catch { /* ignore */ }
    }

    function startEditWorkSettings() {
        if (!workSettings.value) return;
        workSettingsForm.value = {
            timezone: workSettings.value.timezone,
            work_start: workSettings.value.work_start,
            work_end: workSettings.value.work_end,
            lunch_start: workSettings.value.lunch_start,
            lunch_end: workSettings.value.lunch_end,
            work_days: workSettings.value.work_days.split(",").map(Number),
        };
        editingWorkSettings.value = true;
    }

    function cancelEditWorkSettings() {
        editingWorkSettings.value = false;
    }

    async function handleSaveWorkSettings() {
        savingWorkSettings.value = true;
        try {
            const res: any = await updateWorkSettings({
                timezone: workSettingsForm.value.timezone,
                work_start: workSettingsForm.value.work_start,
                work_end: workSettingsForm.value.work_end,
                lunch_start: workSettingsForm.value.lunch_start,
                lunch_end: workSettingsForm.value.lunch_end,
                work_days: workSettingsForm.value.work_days.sort((a, b) => a - b).join(","),
            });
            if (res?.success) {
                message.success("工时设置已保存");
                editingWorkSettings.value = false;
                await loadWorkSettings();
            } else { message.error(res?.error || "保存失败"); }
        } catch { message.error("保存失败"); }
        finally { savingWorkSettings.value = false; }
    }

    async function handleSyncHolidays() {
        syncingHolidays.value = true;
        try {
            const res: any = await syncHolidays(calendarYear.value);
            if (res?.success) {
                message.success(`同步完成：新增 ${res.created} 条，跳过 ${res.skipped} 条`);
                await loadCalendar();
            } else { message.error(res?.error || "同步失败"); }
        } catch { message.error("同步失败"); }
        finally { syncingHolidays.value = false; }
    }

    function openCalendarDialog() {
        calendarForm.value = { date: "", day_type: "holiday", name: "" };
        calendarDialogOpen.value = true;
    }

    async function handleSaveCalendar() {
        if (!calendarForm.value.date) {
            message.error("请选择日期");
            return;
        }
        savingCalendar.value = true;
        try {
            const res: any = await createOrgCalendarEntry(calendarForm.value);
            if (res?.success) {
                message.success("已添加");
                calendarDialogOpen.value = false;
                await loadCalendar();
            } else { message.error(res?.error || "添加失败"); }
        } catch { message.error("添加失败"); }
        finally { savingCalendar.value = false; }
    }

    async function handleDeleteCalendar(id: number) {
        try {
            const res: any = await deleteOrgCalendarEntry(id);
            if (res?.success) {
                message.success("已删除");
                await loadCalendar();
            } else { message.error("删除失败"); }
        } catch { message.error("删除失败"); }
    }

    return {
        calendarEntries, loadingCalendar, calendarYear, syncingHolidays,
        workSettings, editingWorkSettings, savingWorkSettings, workSettingsForm,
        calendarDialogOpen, calendarForm, savingCalendar,
        weekDayOptions, dayTypeOptions, dayTypeLabel, dayTypeColor,
        loadCalendar, loadWorkSettings,
        startEditWorkSettings, cancelEditWorkSettings, handleSaveWorkSettings,
        handleSyncHolidays,
        openCalendarDialog, handleSaveCalendar, handleDeleteCalendar,
    };
}
