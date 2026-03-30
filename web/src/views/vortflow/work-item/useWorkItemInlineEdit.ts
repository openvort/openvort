import { computed, nextTick, reactive, ref, unref, type Ref } from "vue";
import { message } from "@openvort/vort-ui";
import type {
    Priority,
    Status,
    DateRange,
    RowItem,
} from "@/components/vort-biz/work-item/WorkItemTable.types";

export interface UseWorkItemInlineEditOptions {
    useApi: Ref<boolean> | boolean;
    syncRecordUpdateToApi: (record: RowItem, patch: any) => Promise<void>;
    syncRecordStatusToApi: (record: RowItem, status: Status) => Promise<void>;
    getMemberIdByName: (name: string) => string;
    mapBackendPriority: any;
    toBackendPriorityLevel: (p: Priority) => number;
    toTaskEstimateHours: (p: Priority) => number;
    getBackendStatesByDisplayStatus: (type: string, status: Status) => string[];
    dynamicTagOptions: Ref<string[]>;
    baseTagOptions: Ref<string[]> | string[];
    tagDefinitions?: Ref<Array<{ name: string; color: string }>>;
    priorityModel: Record<string, Priority>;
    tagsModel: Record<string, string[]>;
    collaboratorsModel: Record<string, string[]>;
    planTimeModel: Record<string, any>;
    normalizeDateValue: (value: unknown) => string;
}

export function useWorkItemInlineEdit(options: UseWorkItemInlineEditOptions) {
    const {
        syncRecordUpdateToApi,
        syncRecordStatusToApi,
        getMemberIdByName,
        toBackendPriorityLevel,
        toTaskEstimateHours,
        dynamicTagOptions,
        baseTagOptions,
        priorityModel,
        tagsModel,
        collaboratorsModel,
        planTimeModel,
        normalizeDateValue,
    } = options;

    // --- Picker open state maps ---
    const priorityPickerOpenMap = reactive<Record<string, boolean>>({});
    const tagPickerOpenMap = reactive<Record<string, boolean>>({});
    const statusPickerOpenMap = reactive<Record<string, boolean>>({});
    const ownerPickerOpenMap = reactive<Record<string, boolean>>({});
    const collaboratorsPickerOpenMap = reactive<Record<string, boolean>>({});

    // --- Plan time state ---
    const openPlanTimeFor = ref<string | null>(null);
    const planTimePickerOpen = ref(false);
    const planTimePrevValue = ref<DateRange>([]);
    const planTimeCommitted = ref(false);

    // --- Tag creation state ---
    const newTagDialogOpen = ref(false);
    const newTagName = ref("");
    const newTagColor = ref<string>("");
    const newTagTargetRecord = ref<RowItem | null>(null);
    const newTagTargetText = ref<string[] | undefined>(undefined);

    // --- Cell interaction helpers ---
    const getInteractiveCellKey = (record: RowItem) =>
        String(record.workNo || record.backendId || "");

    const isCellBackgroundClick = (event: Event) => {
        const target = event.target as HTMLElement | null;
        const currentTarget = event.currentTarget as HTMLElement | null;
        return !!target && !!currentTarget && target === currentTarget;
    };

    const openCellPickerOnBackgroundClick = (
        record: RowItem,
        event: Event,
        openMap: Record<string, boolean>,
    ) => {
        if (!isCellBackgroundClick(event)) return;
        openMap[getInteractiveCellKey(record)] = true;
    };

    // --- Priority ---
    const getRowPriority = (record: RowItem, text?: Priority): Priority => {
        return priorityModel[record.workNo] || text || record.priority;
    };

    const selectPriority = async (record: RowItem, value: Priority) => {
        const workNo = record.workNo;
        const prev = getRowPriority(record, record.priority);
        priorityModel[workNo] = value;
        record.priority = value;
        try {
            if (record.type === "缺陷") {
                await syncRecordUpdateToApi(record, { severity: toBackendPriorityLevel(value) });
            } else if (record.type === "任务") {
                await syncRecordUpdateToApi(record, { estimate_hours: toTaskEstimateHours(value) });
            } else {
                await syncRecordUpdateToApi(record, { priority: toBackendPriorityLevel(value) });
            }
        } catch (error: any) {
            priorityModel[workNo] = prev;
            record.priority = prev;
            message.error(error?.message || "优先级同步失败");
            return;
        }
    };

    // --- Status ---
    const getRowStatus = (record: RowItem, text?: Status): Status => {
        return text || record.status;
    };

    const selectRowStatus = async (record: RowItem, value: Status) => {
        const prev = record.status;
        record.status = value;
        if (prev !== value) {
            try {
                await syncRecordStatusToApi(record, value);
            } catch (error: any) {
                record.status = prev;
                message.error(error?.message || "状态同步失败");
                return;
            }
        }
    };

    // --- Owner ---
    const getRowOwner = (record: RowItem, text?: string): string => {
        return text || record.owner || "未指派";
    };

    const selectRowOwner = async (record: RowItem, value: string) => {
        const prev = record.owner;
        const nextOwner = value || "未指派";
        record.owner = nextOwner;
        if (prev !== nextOwner) {
            const memberId = value ? getMemberIdByName(value) : "";
            if (value && !memberId) {
                record.owner = prev;
                message.error("未找到负责人对应的成员ID，无法同步");
                return;
            }
            try {
                if (record.type === "需求") {
                    await syncRecordUpdateToApi(record, { pm_id: memberId || null });
                } else {
                    await syncRecordUpdateToApi(record, { assignee_id: memberId || null });
                }
            } catch (error: any) {
                record.owner = prev;
                message.error(error?.message || "负责人同步失败");
                return;
            }
        }
    };

    // --- Collaborators ---
    const getRowCollaborators = (record: RowItem, text?: string[]): string[] => {
        return collaboratorsModel[record.workNo] || text || record.collaborators || [];
    };

    const setRowCollaborators = async (record: RowItem, nextCollaborators: string[]) => {
        const prev = [...getRowCollaborators(record, record.collaborators)];
        collaboratorsModel[record.workNo] = [...nextCollaborators];
        record.collaborators = [...nextCollaborators];
        try {
            await syncRecordUpdateToApi(record, { collaborators: nextCollaborators });
        } catch (error: any) {
            collaboratorsModel[record.workNo] = prev;
            record.collaborators = prev;
            message.error(error?.message || "协作者同步失败");
        }
    };

    // --- Tags ---
    const tagColorPalette = ["#ef4444", "#d946ef", "#eab308", "#22c55e", "#3b82f6", "#f97316", "#14b8a6", "#8b5cf6"];
    const tagColorOverrides = reactive<Record<string, string>>({});

    const getTagColor = (name: string): string => {
        if (tagColorOverrides[name]) return tagColorOverrides[name]!;
        const defs = options.tagDefinitions?.value;
        if (defs) {
            const match = defs.find(t => t.name === name);
            if (match) return match.color;
        }
        let hash = 0;
        for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
        return tagColorPalette[hash % tagColorPalette.length]!;
    };

    const getRowTags = (record: RowItem, text?: string[]): string[] => {
        return tagsModel[record.workNo] || text || [];
    };

    const rowTagOptions = computed(() => dynamicTagOptions.value.length ? dynamicTagOptions.value : unref(baseTagOptions));

    const setRowTags = async (record: RowItem, nextTags: string[]) => {
        const prev = [...getRowTags(record, record.tags)];
        tagsModel[record.workNo] = [...nextTags];
        record.tags = [...nextTags];
        try {
            await syncRecordUpdateToApi(record, { tags: nextTags });
        } catch (error: any) {
            tagsModel[record.workNo] = prev;
            record.tags = prev;
            message.error(error?.message || "标签同步失败");
        }
    };

    const openCreateTagDialog = (record?: RowItem | null, text?: string[]) => {
        newTagName.value = "";
        newTagColor.value = tagColorPalette[0] || "#3b82f6";
        newTagTargetRecord.value = record || null;
        newTagTargetText.value = text;
        newTagDialogOpen.value = true;
    };

    const handleCancelCreateTag = () => {
        newTagDialogOpen.value = false;
    };

    const handleConfirmCreateTag = async () => {
        const name = newTagName.value.trim();
        if (!name) {
            message.error("请输入标签名称");
            return;
        }
        const existing = new Set<string>([...unref(baseTagOptions), ...dynamicTagOptions.value]);
        if (existing.has(name)) {
            message.error("该标签已存在");
            return;
        }
        dynamicTagOptions.value = [...dynamicTagOptions.value, name];
        if (newTagColor.value) {
            tagColorOverrides[name] = newTagColor.value;
        }
        if (newTagTargetRecord.value) {
            const currentTags = getRowTags(newTagTargetRecord.value, newTagTargetText.value);
            if (!currentTags.includes(name)) {
                await setRowTags(newTagTargetRecord.value, [...currentTags, name]);
            }
        }
        newTagDialogOpen.value = false;
    };

    // --- Plan time ---
    const onPlanTimeChange = async (record: RowItem, value?: any) => {
        const workNo = record.workNo;
        if (!value || value.length !== 2) return;
        const start = normalizeDateValue(value[0]);
        const end = normalizeDateValue(value[1]);
        if (!start || !end) return;
        planTimeCommitted.value = true;
        const prev = [...planTimePrevValue.value] as DateRange;
        planTimeModel[workNo] = [start, end];
        record.planTime = [start, end];
        openPlanTimeFor.value = null;
        try {
            if (record.type === "缺陷") {
                message.warning("缺陷暂不支持计划时间同步到后端");
            } else {
                await syncRecordUpdateToApi(record, { deadline: end });
            }
        } catch (error: any) {
            planTimeModel[workNo] = prev;
            record.planTime = prev;
            message.error(error?.message || "计划时间同步失败");
        }
    };

    const onPlanTimeOpenChange = (record: RowItem, open: boolean) => {
        if (!open && openPlanTimeFor.value === record.workNo && !planTimeCommitted.value) {
            const workNo = record.workNo;
            planTimeModel[workNo] = [...planTimePrevValue.value];
            record.planTime = [...planTimePrevValue.value];
            openPlanTimeFor.value = null;
        }
    };

    const getRowPlanTime = (record: RowItem, text?: DateRange): DateRange => {
        return planTimeModel[record.workNo] || text || record.planTime;
    };

    const DONE_STATUSES = new Set(["已关闭", "已完成", "已修复", "发布完成", "测试完成", "开发完成"]);

    const getRowPlanTimeText = (record: RowItem, text?: DateRange): string => {
        const value = getRowPlanTime(record, text);
        const start = normalizeDateValue(value[0]);
        const end = normalizeDateValue(value[1]);
        if (!start && !end) return "-";
        const currentYear = String(new Date().getFullYear());
        const stripYear = (d: string) => d.slice(5);
        if (!end) {
            return (start.startsWith(currentYear) ? stripYear(start) : start) + " 开始";
        }
        if (!start) return "~" + (end.startsWith(currentYear) ? stripYear(end) : end);
        const startYear = start.slice(0, 4);
        const endYear = end.slice(0, 4);
        if (startYear === endYear) {
            const isCurrentYear = startYear === currentYear;
            return `${isCurrentYear ? stripYear(start) : start}~${stripYear(end)}`;
        }
        return `${start}~${end}`;
    };

    const getRowOverdueInfo = (record: RowItem, text?: DateRange): { days: number; completed: boolean } | null => {
        const value = getRowPlanTime(record, text);
        const end = normalizeDateValue(value[1]);
        if (!end) return null;
        const endDate = new Date(end + "T00:00:00");
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const diffMs = today.getTime() - endDate.getTime();
        const diffDays = Math.floor(diffMs / 86400000);
        if (diffDays <= 0) return null;
        return { days: diffDays, completed: DONE_STATUSES.has(record.status) };
    };

    const togglePlanTimeMenu = (workNo: string, record?: RowItem, text?: DateRange) => {
        const willOpen = openPlanTimeFor.value !== workNo;
        if (willOpen) {
            const value = record ? getRowPlanTime(record, text) : undefined;
            const start = normalizeDateValue(value?.[0]);
            const end = normalizeDateValue(value?.[1]);
            if (start && end) {
                planTimeModel[workNo] = [start, end];
            }
            planTimePrevValue.value = planTimeModel[workNo] ? [...planTimeModel[workNo]] : [];
            planTimeCommitted.value = false;
            planTimePickerOpen.value = false;
            openPlanTimeFor.value = workNo;
            nextTick(() => {
                planTimePickerOpen.value = true;
            });
        } else {
            planTimePickerOpen.value = false;
            openPlanTimeFor.value = null;
        }
    };

    return {
        priorityPickerOpenMap,
        tagPickerOpenMap,
        statusPickerOpenMap,
        ownerPickerOpenMap,
        collaboratorsPickerOpenMap,

        getInteractiveCellKey,
        isCellBackgroundClick,
        openCellPickerOnBackgroundClick,

        getRowPriority,
        selectPriority,
        getRowStatus,
        selectRowStatus,
        getRowOwner,
        selectRowOwner,
        getRowCollaborators,
        setRowCollaborators,
        getRowTags,
        setRowTags,
        rowTagOptions,
        getRowPlanTimeText,
        getRowOverdueInfo,
        onPlanTimeChange,
        onPlanTimeOpenChange,
        getRowPlanTime,
        togglePlanTimeMenu,

        getTagColor,
        tagColorPalette,
        openCreateTagDialog,
        handleCancelCreateTag,
        handleConfirmCreateTag,
        newTagName,
        newTagColor,
        newTagDialogOpen,

        openPlanTimeFor,
        planTimePickerOpen,
        planTimePrevValue,
        planTimeCommitted,
    };
}
