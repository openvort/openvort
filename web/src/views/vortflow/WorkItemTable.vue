<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ProTable, TableCell, type ProTableColumn, type ProTableRequestParams, type ProTableResponse } from "@/components/vort-biz";
import { message } from "@/components/vort";
import VortEditor from "@/components/vort-biz/editor/VortEditor.vue";
import MarkdownView from "@/components/vort-biz/editor/MarkdownView.vue";
import { Pencil } from "lucide-vue-next";
import WorkItemMemberPicker from "@/components/vort-biz/work-item/WorkItemMemberPicker.vue";
import WorkItemPriority from "@/components/vort-biz/work-item/WorkItemPriority.vue";
import WorkItemStatus from "@/components/vort-biz/work-item/WorkItemStatus.vue";
import WorkItemTagPicker from "@/components/vort-biz/work-item/WorkItemTagPicker.vue";
import WorkItemFilters from "@/components/vort-biz/work-item/WorkItemFilters.vue";
import WorkItemDetail from "./work-item/WorkItemDetail.vue";
import WorkItemCreate from "./work-item/WorkItemCreate.vue";
import MoreActionsDropdown from "./components/MoreActionsDropdown.vue";
import BatchPropertyEditor from "./components/BatchPropertyEditor.vue";
import ImportDialog from "./components/ImportDialog.vue";
import ImportRecordDialog from "./components/ImportRecordDialog.vue";
import ColumnFilterPopover from "@/components/vort-biz/pro-table/ColumnFilterPopover.vue";
import type { ColumnFilterConfig, ColumnFilterValue } from "@/components/vort-biz/pro-table/ColumnFilterPopover.vue";
import ViewSelector from "./components/ViewSelector.vue";
import ViewManageDialog from "./components/ViewManageDialog.vue";
import ViewCreateDialog from "./components/ViewCreateDialog.vue";
import ColumnSettingsDialog from "./components/ColumnSettingsDialog.vue";
import type { ColumnSettingItem } from "./components/ColumnSettingsDialog.vue";
import { useVortFlowStore } from "@/stores";
import type { CustomView } from "@/stores/modules/vortflow";
import { useVortFlowViews, SYSTEM_VIEWS } from "./composables/useVortFlowViews";
import { useWorkItemCommon } from "./work-item/useWorkItemCommon";
import {
    getVortflowStory, getVortflowStories, getVortflowTask, getVortflowTasks, getVortflowBugs,
    getVortflowProjects, createVortflowStory, createVortflowTask, createVortflowBug,
    deleteVortflowStory, deleteVortflowTask, deleteVortflowBug,
    updateVortflowStory, updateVortflowTask, updateVortflowBug
} from "@/api";
import type {
    WorkItemType,
    Priority,
    Status,
    DateRange,
    WorkItemTableProps,
    ViewFilters,
    NewBugForm,
    RowItem,
    DetailComment,
    DetailLog,
    CreateBugAttachment,
    StatusOption
} from "@/components/vort-biz/work-item/WorkItemTable.types";

const props = withDefaults(defineProps<WorkItemTableProps>(), {
    pageTitle: "缺陷",
    createButtonText: "+ 新建缺陷",
    createDrawerTitle: "新建缺陷",
    detailDrawerTitle: "缺陷详情",
    descriptionPlaceholder: "请填写缺陷描述",
    useApi: true,
    projectId: "",
    viewFilters: () => ({}),
});

const route = useRoute();
const router = useRouter();
const vortFlowStore = useVortFlowStore();

const currentWorkItemType = computed(() => (props.type as "需求" | "任务" | "缺陷") || null);

const currentViewId = computed(() => {
    if (!currentWorkItemType.value) return "all";
    return vortFlowStore.getViewId(currentWorkItemType.value);
});

const onViewChange = (viewId: string) => {
    if (currentWorkItemType.value) {
        vortFlowStore.setViewId(currentWorkItemType.value, viewId);
    }
};

const viewManageOpen = ref(false);
const viewCreateOpen = ref(false);

const { views: mergedViews } = currentWorkItemType.value
    ? useVortFlowViews(currentWorkItemType.value)
    : { views: computed(() => SYSTEM_VIEWS) };

const handleCreateViewFromDialog = (data: { name: string; scope: "personal" | "shared" }) => {
    const maxOrder = vortFlowStore.customViews.reduce((max, v) => Math.max(max, v.order), -1);
    const newView: CustomView = {
        id: `custom_${Date.now()}`,
        name: data.name,
        scope: data.scope,
        visible: true,
        filters: {},
        order: maxOrder + 1,
    };
    vortFlowStore.addCustomView(newView);
    viewCreateOpen.value = false;
};

const {
    memberOptions,
    ownerGroups,
    getStatusOptionsByType,
    getStatusOption,
    priorityOptions,
    priorityLabelMap,
    priorityClassMap,
    getAvatarBg,
    getAvatarLabel,
    getMemberAvatarUrl,
    loadMemberOptions,
    getMemberIdByName,
    getMemberNameById,
    getWorkItemTypeIconClass,
    getWorkItemTypeIconSymbol,
    mapBackendStateToStatus,
    mapBackendPriority,
    formatCnTime,
    formatDate,
    toBackendPriorityLevel,
    toTaskEstimateHours,
    getBackendStatesByDisplayStatus,
    bugStatusFilterOptions,
    demandStatusFilterOptions,
    taskStatusFilterOptions,
} = useWorkItemCommon();

const keyword = ref("");
const owner = ref("");
const type = ref<WorkItemType | "">(props.type ?? "");
const status = ref("");
const openPlanTimeFor = ref<string | null>(null);
const planTimePickerOpen = ref(false);
const planTimePrevValue = ref<DateRange>([]);
const planTimeCommitted = ref(false);
const priorityPickerOpenMap = reactive<Record<string, boolean>>({});
const tagPickerOpenMap = reactive<Record<string, boolean>>({});
const statusPickerOpenMap = reactive<Record<string, boolean>>({});
const ownerPickerOpenMap = reactive<Record<string, boolean>>({});
const collaboratorsPickerOpenMap = reactive<Record<string, boolean>>({});
const totalCount = ref(0);
const createBugDrawerOpen = computed({
    get: () => {
        const action = route.query.action as string;
        return action === "create" || action === "detail";
    },
    set: (val: boolean) => {
        if (!val) {
            router.replace({ query: { ...route.query, action: undefined, id: undefined, parentId: undefined } });
        }
    }
});
const createBugDrawerMode = ref<"create" | "detail">("create");
const detailActiveTab = ref("detail");
const detailSelectedWorkNo = ref("");
const detailDescEditing = ref(false);
const detailDescDraft = ref("");
const detailBottomTab = ref<"comments" | "logs">("comments");
const detailCommentDraft = ref("");
const detailCommentsMap = reactive<Record<string, DetailComment[]>>({});
const detailLogsMap = reactive<Record<string, DetailLog[]>>({});
const createWorkItemRef = ref<{
    submit: () => NewBugForm | null;
    reset: () => void;
    cancel: () => void;
} | null>(null);
const createBugAttachments = ref<CreateBugAttachment[]>([]);
const createAttachmentInputRef = ref<HTMLInputElement | null>(null);

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
    openMap: Record<string, boolean>
) => {
    if (!isCellBackgroundClick(event)) return;
    openMap[getInteractiveCellKey(record)] = true;
};

const defaultDescriptionTemplate = [
    "环境：请填写",
    "",
    "账号：请填写",
    "",
    "密码：请填写",
    "",
    "前置条件：请填写",
    "",
    "操作步骤：",
    "步骤1：",
    "步骤2：",
    "",
    "实际结果：请填写",
    "",
    "预期结果：请填写",
].join("\n");

const createInitialBugForm = (): NewBugForm => ({
    title: "",
    owner: "",
    collaborators: [],
    type: props.type ?? "缺陷",
    planTime: [],
    project: "VortMall",
    projectId: "",
    iteration: "",
    version: "",
    parentId: "",
    priority: "",
    tags: [],
    repo: "",
    branch: "",
    startAt: "",
    endAt: "",
    remark: "",
    description: defaultDescriptionTemplate
});
const createBugForm = reactive<NewBugForm>(createInitialBugForm());
const apiProjects = ref<Array<{ id: string; name: string }>>([]);
const apiStories = ref<Array<{ id: string; title: string }>>([]);
const itemRowsById = reactive<Record<string, RowItem>>({});
const itemChildrenMap = reactive<Record<string, RowItem[]>>({});
const expandedItemIds = reactive<Record<string, boolean>>({});
const expandingItemIds = reactive<Record<string, boolean>>({});
const createParentItemId = ref("");
const createProjectId = ref("");
const selectedRowKeys = ref<Array<string | number>>([]);
const selectedRows = ref<RowItem[]>([]);
const pinnedRowsByType = reactive<Record<WorkItemType, RowItem[]>>({
    需求: [],
    任务: [],
    缺陷: [],
});

const createBugProjectOptions = ["VortMall", "OpenVort", "VortFlow"];

const allStatusFilterOptions: StatusOption[] = Array.from(
    new Map(
        [...demandStatusFilterOptions, ...taskStatusFilterOptions, ...bugStatusFilterOptions].map((item) => [item.value, item])
    ).values()
);

const importDialogOpen = ref(false);
const importRecordDialogOpen = ref(false);
const batchPropertyEditorOpen = ref(false);
const columnFilters = reactive<Record<string, ColumnFilterValue | null>>({});
const columnSortField = ref<string>("");
const columnSortOrder = ref<"ascend" | "descend" | null>(null);

const STATUS_DOT_COLOR_MAP: Record<string, string> = {
    "待确认": "#9ca3af",
    "修复中": "#3b82f6",
    "已修复": "#3b82f6",
    "已关闭": "#374151",
    "已取消": "#ef4444",
    "意向": "#64748b",
    "设计中": "#6366f1",
    "开发中": "#3b82f6",
    "测试完成": "#7c3aed",
    "已完成": "#059669",
    "待办的": "#64748b",
    "进行中": "#3b82f6",
    "延期处理": "#0284c7",
    "设计如此": "#d97706",
    "再次打开": "#ef4444",
    "无法复现": "#d97706",
    "暂时搁置": "#6b7280",
    "开发完成": "#0891b2",
    "待发布": "#d97706",
    "发布完成": "#059669",
};

const statusFilterConfig = computed<ColumnFilterConfig>(() => ({
    type: "enum",
    options: currentStatusFilterOptions.value.map(o => ({
        label: o.label,
        value: o.value,
        dotColor: STATUS_DOT_COLOR_MAP[o.label] || "#9ca3af",
    })),
}));

const dateFilterConfig: ColumnFilterConfig = { type: "date" };

const tagsFilterConfig = computed<ColumnFilterConfig>(() => ({
    type: "enum",
    options: (dynamicTagOptions.value.length ? dynamicTagOptions.value : baseTagOptions).map(t => ({
        label: t,
        value: t,
    })),
    sortLabels: ["A → Z", "Z → A"] as [string, string],
}));

const ownerFilterConfig = computed<ColumnFilterConfig>(() => ({
    type: "enum",
    options: [
        { label: "未指派", value: "__unassigned__" },
        ...memberOptions.value.map(m => ({
            label: m.label || m.value,
            value: m.value,
        })),
    ],
}));

const collaboratorsFilterConfig = computed<ColumnFilterConfig>(() => ({
    type: "enum",
    options: memberOptions.value.map(m => ({
        label: m.label || m.value,
        value: m.value,
    })),
}));

const handleColumnSort = (field: string, order: "ascend" | "descend" | null) => {
    columnSortField.value = order ? field : "";
    columnSortOrder.value = order;
    tableRef.value?.refresh?.();
};

const handleColumnFilter = (field: string, value: ColumnFilterValue | null) => {
    if (value) columnFilters[field] = value;
    else delete columnFilters[field];
    tableRef.value?.refresh?.();
};

const getExportData = (): RowItem[] => {
    if (selectedRows.value.length > 0) return selectedRows.value;
    return Object.values(itemRowsById);
};

const downloadFile = (content: string, filename: string, type: string) => {
    const bom = type.includes("csv") ? "\uFEFF" : "";
    const blob = new Blob([bom + content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
};

const handleExportCsv = () => {
    const rows = getExportData();
    if (!rows.length) { message.warning("暂无数据可导出"); return; }
    const headers = ["工作编号", "标题", "类型", "状态", "优先级", "负责人", "创建人", "标签", "协作者", "创建时间", "计划开始", "计划结束"];
    const csvRows = rows.map(r => [
        r.workNo || "", (r.title || "").replace(/"/g, '""'), r.type || "",
        r.status || "", r.priority || "", r.owner || "", r.creator || "",
        (r.tags || []).join(";"), (r.collaborators || []).join(";"),
        r.createdAt || "", r.planTime?.[0] || "", r.planTime?.[1] || "",
    ].map(v => `"${v}"`).join(","));
    downloadFile([headers.join(","), ...csvRows].join("\n"), `工作项导出_${new Date().toISOString().slice(0, 10)}.csv`, "text/csv;charset=utf-8");
    message.success(`已导出 ${rows.length} 条数据`);
};

const handleExportExcel = () => {
    handleExportCsv();
    message.info("已导出为 CSV 格式，可使用 Excel 打开");
};

const handleExportJson = () => {
    const rows = getExportData();
    if (!rows.length) { message.warning("暂无数据可导出"); return; }
    const data = rows.map(r => ({
        workNo: r.workNo, title: r.title, type: r.type, status: r.status,
        priority: r.priority, owner: r.owner, creator: r.creator,
        tags: r.tags, collaborators: r.collaborators, createdAt: r.createdAt,
        planTimeStart: r.planTime?.[0] || "", planTimeEnd: r.planTime?.[1] || "",
        description: r.description || "",
    }));
    downloadFile(JSON.stringify(data, null, 2), `工作项导出_${new Date().toISOString().slice(0, 10)}.json`, "application/json;charset=utf-8");
    message.success(`已导出 ${rows.length} 条数据`);
};

const priorityModel = reactive<Record<string, Priority>>({});
const tagsModel = reactive<Record<string, string[]>>({});
const baseTagOptions = ["客户需求", "演示站", "运营需求", "待开会确认", "已发布", "高优先", "稳定性", "UI优化", "S1", "S2", "S3", "S4", "develop", "test"];
const dynamicTagOptions = ref<string[]>([]);
const newTagDialogOpen = ref(false);
const newTagName = ref("");
const newTagColor = ref<string>("");
const newTagTargetRecord = ref<RowItem | null>(null);
const newTagTargetText = ref<string[] | undefined>(undefined);
const planTimeModel = reactive<Record<string, any>>({});
const collaboratorsModel = reactive<Record<string, string[]>>({});

const resolveActiveType = (): WorkItemType => {
    if (props.type) return props.type;
    if (type.value === "需求" || type.value === "任务" || type.value === "缺陷") return type.value;
    return "缺陷";
};
const currentStatusFilterOptions = computed(() => getStatusOptionsByType(resolveActiveType()));

const normalizeDateValue = (value: unknown): string => {
    if (value instanceof Date) return formatDate(value);
    if (typeof value === "string") {
        const direct = value.trim();
        if (/^\d{4}-\d{2}-\d{2}$/.test(direct)) return direct;
        const parsed = new Date(direct);
        if (!Number.isNaN(parsed.getTime())) return formatDate(parsed);
    }
    return "";
};

const collectTagOptions = (rows: RowItem[]) => {
    const set = new Set<string>(baseTagOptions);
    for (const row of rows) {
        for (const tag of row.tags || []) {
            if (tag) set.add(tag);
        }
    }
    dynamicTagOptions.value = [...set];
};

const detailCurrentUser = "当前用户";
const formatFileSize = (size: number): string => {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

const columnSettingsOpen = ref(false);

const ALL_COLUMN_DEFS: Array<ProTableColumn<RowItem> & { key: string }> = [
    { key: "workNo", title: "工作编号", dataIndex: "workNo", width: 130, sorter: true, align: "left", fixed: "left", slot: "workNo" },
    { key: "title", title: "标题", dataIndex: "title", width: 228, ellipsis: true, align: "left", fixed: "left", slot: "title" },
    { key: "status", title: "状态", dataIndex: "status", width: 120, slot: "status", align: "left" },
    { key: "owner", title: "负责人", dataIndex: "owner", width: 160, sorter: true, align: "left", slot: "owner" },
    { key: "priority", title: "优先级", dataIndex: "priority", width: 120, slot: "priority", align: "left" },
    { key: "tags", title: "标签", dataIndex: "tags", width: 180, slot: "tags", align: "left" },
    { key: "createdAt", title: "创建时间", dataIndex: "createdAt", width: 150, sorter: true, align: "left", slot: "createdAt" },
    { key: "collaborators", title: "协作者", dataIndex: "collaborators", width: 140, slot: "collaborators", align: "left" },
    { key: "type", title: "工作项类型", dataIndex: "type", width: 120, sorter: true, align: "left", slot: "type" },
    { key: "planTime", title: "计划时间", dataIndex: "planTime", width: 260, sorter: true, align: "left", slot: "planTime" },
    { key: "creator", title: "创建人", dataIndex: "creator", width: 160, sorter: true, align: "left", slot: "creator" },
    { key: "updatedAt", title: "更新时间", dataIndex: "updatedAt", width: 150, sorter: true, align: "left" },
    { key: "iteration", title: "迭代", dataIndex: "iteration", width: 140, align: "left" },
    { key: "version", title: "版本", dataIndex: "version", width: 120, align: "left" },
    { key: "estimateHours", title: "预估工时", dataIndex: "estimateHours", width: 100, align: "left" },
];

const DEFAULT_VISIBLE_KEYS = new Set([
    "workNo", "title", "status", "owner", "priority", "tags",
    "createdAt", "collaborators", "type", "planTime", "creator",
]);

const columnSettings = ref<ColumnSettingItem[]>(
    ALL_COLUMN_DEFS.map(c => ({
        key: c.key,
        title: c.title || c.key,
        fixed: c.key === "workNo" || c.key === "title",
        visible: DEFAULT_VISIBLE_KEYS.has(c.key),
    }))
);

const handleColumnSettingsSave = (settings: ColumnSettingItem[]) => {
    columnSettings.value = settings;
};

const columns = computed<ProTableColumn<RowItem>[]>(() => {
    const visibleKeys = new Set(columnSettings.value.filter(s => s.visible).map(s => s.key));
    const orderedKeys = columnSettings.value.filter(s => s.visible).map(s => s.key);
    const colMap = new Map(ALL_COLUMN_DEFS.map(c => [c.key, c]));
    return orderedKeys.map(k => colMap.get(k)!).filter(Boolean);
});

const columnSettingsForDialog = computed<ColumnSettingItem[]>(() => columnSettings.value);

const getRecordBackendId = (record: RowItem): string => String(record.backendId || "").trim();

const syncRecordUpdateToApi = async (
    record: RowItem,
    patch: {
        title?: string;
        description?: string;
        state?: string;
        priority?: number;
        severity?: number;
        assignee_id?: string | null;
        estimate_hours?: number;
        tags?: string[];
        collaborators?: string[];
        deadline?: string;
        pm_id?: string | null;
    }
) => {
    if (!props.useApi) return;
    const id = getRecordBackendId(record);
    if (!id) return;
    if (record.type === "需求") {
        await updateVortflowStory(id, {
            title: patch.title,
            description: patch.description,
            state: patch.state,
            priority: patch.priority,
            tags: patch.tags,
            collaborators: patch.collaborators,
            deadline: patch.deadline,
            pm_id: patch.pm_id,
        });
        return;
    }
    if (record.type === "任务") {
        await updateVortflowTask(id, {
            title: patch.title,
            description: patch.description,
            state: patch.state,
            assignee_id: patch.assignee_id === undefined ? undefined : (patch.assignee_id || undefined),
            estimate_hours: patch.estimate_hours,
            tags: patch.tags,
            collaborators: patch.collaborators,
            deadline: patch.deadline,
        });
        return;
    }
    await updateVortflowBug(id, {
        title: patch.title,
        description: patch.description,
        severity: patch.severity,
        state: patch.state,
        assignee_id: patch.assignee_id === undefined ? undefined : (patch.assignee_id || undefined),
        tags: patch.tags,
        collaborators: patch.collaborators,
    });
};

const syncRecordStatusToApi = async (record: RowItem, displayStatus: Status) => {
    if (!props.useApi) return;
    const targetStates = getBackendStatesByDisplayStatus(record.type, displayStatus) || [];
    if (!targetStates.length) {
        throw new Error("当前状态不支持同步到后端");
    }
    await syncRecordUpdateToApi(record, { state: targetStates[0] });
};

const prependPinnedRow = (typeValue: WorkItemType, row: RowItem) => {
    const list = pinnedRowsByType[typeValue] || [];
    const rowId = row.backendId || row.workNo;
    pinnedRowsByType[typeValue] = [row, ...list.filter((x) => (x.backendId || x.workNo) !== rowId)];
};

const cacheItemRows = (rows: RowItem[]) => {
    for (const row of rows) {
        if (!row.backendId) continue;
        itemRowsById[row.backendId] = row;
    }
};

const findItemRowById = (itemId?: string): RowItem | null => {
    if (!itemId) return null;
    return itemRowsById[itemId] || null;
};

const loadItemById = async (itemId: string | undefined, itemType: WorkItemType): Promise<RowItem | null> => {
    if (!itemId) return null;
    const cached = findItemRowById(itemId);
    if (cached) return cached;
    try {
        const res: any = itemType === "任务"
            ? await getVortflowTask(itemId)
            : await getVortflowStory(itemId);
        if (!res?.id) return null;
        const row = mapBackendItemToRow(res, itemType, 0);
        itemRowsById[itemId] = row;
        return row;
    } catch {
        return null;
    }
};

const loadChildItems = async (parentId: string, itemType: WorkItemType, projectId?: string): Promise<RowItem[]> => {
    if (!parentId || itemType === "缺陷") return [];
    const res: any = itemType === "任务"
        ? await getVortflowTasks({
            parent_id: parentId,
            page: 1,
            page_size: 100,
        })
        : await getVortflowStories({
            parent_id: parentId,
            project_id: projectId,
            page: 1,
            page_size: 100,
        });
    const rows = ((res?.items || []) as any[]).map((item, index) => {
        const row = mapBackendItemToRow(item, itemType, index);
        row.isChild = true;
        return row;
    });
    cacheItemRows(rows);
    itemChildrenMap[parentId] = rows;
    return rows;
};

const mapBackendItemToRow = (item: any, typeValue: WorkItemType, index: number): RowItem => {
    const created = item?.created_at ? new Date(item.created_at) : new Date();
    const createdAt = formatCnTime(created);
    const deadline = item?.deadline ? String(item.deadline).split("T")[0] : "";
    const backendId = String(item?.id || index + 1);
    const workNo = `#${backendId.replace(/-/g, "").slice(0, 6).toUpperCase().padEnd(6, "X")}`;
    const ownerSourceId = String(item?.assignee_id || item?.pm_id || item?.developer_id || "").trim();
    const ownerSourceName = getMemberNameById(ownerSourceId);
    const ownerName = ownerSourceName || (ownerSourceId ? ownerSourceId : "未指派");

    const creatorSourceId = String(item?.submitter_id || item?.creator_id || item?.reporter_id || "").trim();
    const creatorName = getMemberNameById(creatorSourceId) || (creatorSourceId || "");

    const collaboratorsFromBackend = Array.isArray(item?.collaborators)
        ? (item.collaborators as any[]).map((x) => {
            const id = String(x || "").trim();
            return getMemberNameById(id) || id;
        }).filter(Boolean)
        : [];

    const tags: string[] = Array.isArray(item?.tags)
        ? (item.tags as any[]).map((x) => String(x || "").trim()).filter(Boolean)
        : [];

    const planDate = deadline || formatDate(created);
    return {
        backendId,
        workNo,
        title: String(item?.title || ""),
        parentId: item?.parent_id ? String(item.parent_id) : "",
        parentTitle: "",
        childrenCount: Number(item?.children_count || 0),
        isChild: Boolean(item?.parent_id),
        priority: mapBackendPriority(item, typeValue),
        tags,
        status: mapBackendStateToStatus(typeValue, String(item?.state || "")),
        createdAt,
        collaborators: collaboratorsFromBackend,
        type: typeValue,
        planTime: [planDate, planDate],
        description: item?.description || "",
        ownerId: ownerSourceId,
        owner: ownerName,
        creator: creatorName,
        projectId: item?.project_id ? String(item.project_id) : "",
        projectName: "",
    };
};

const createOwnerMatcher = (ownerValue: string) => {
    const normalizedOwner = String(ownerValue || "").trim();
    const ownerMemberId = normalizedOwner && normalizedOwner !== "未指派" ? getMemberIdByName(normalizedOwner) : "";
    const matchOwner = (row: RowItem) => {
        if (!normalizedOwner) return true;
        if (normalizedOwner === "未指派") return !String(row.ownerId || "").trim();
        if (ownerMemberId) return String(row.ownerId || "").trim() === ownerMemberId;
        return row.owner === normalizedOwner;
    };
    return { ownerMemberId, matchOwner };
};

const getVisibleChildRows = (rows: RowItem[], ownerValue = owner.value, statusValue = status.value) => {
    const currentType = String(props.type ?? type.value ?? "").trim();
    if (!props.useApi || (currentType !== "需求" && currentType !== "任务")) return rows;
    const { matchOwner } = createOwnerMatcher(ownerValue);
    const flattenedRows: RowItem[] = [];
    for (const row of rows) {
        flattenedRows.push(row);
        const itemId = String(row.backendId || "").trim();
        if (!itemId || !expandedItemIds[itemId]) continue;
        const children = (itemChildrenMap[itemId] || [])
            .filter((child) => !statusValue || child.status === statusValue)
            .filter(matchOwner)
            .map((child) => ({ ...child, isChild: true }));
        flattenedRows.push(...children);
    }
    return flattenedRows;
};

const postProcessTableRows = (rows: RowItem[]) => getVisibleChildRows(rows);

const SORT_FIELD_MAP: Record<string, string> = {
    createdAt: "created_at",
    priority: "priority",
    title: "title",
    status: "state",
    planTime: "deadline",
    owner: "assignee_id",
    creator: "creator_id",
};

const SORT_FIELD_OVERRIDES: Record<string, Record<string, string>> = {
    "需求": { owner: "pm_id", creator: "submitter_id" },
    "缺陷": { creator: "reporter_id" },
};

const applyColumnFilters = (rows: RowItem[]): RowItem[] => {
    const filters = columnFilters;
    if (!Object.keys(filters).length) return rows;

    return rows.filter(row => {
        for (const [field, fv] of Object.entries(filters)) {
            if (!fv) continue;
            if (field === "status") {
                const vals = fv.value as string[];
                if (vals?.length && !vals.includes(row.status)) return false;
            } else if (field === "tags") {
                const vals = fv.value as string[];
                if (vals?.length) {
                    const rowTags: string[] = row.tags || [];
                    if (!vals.some(v => rowTags.includes(v))) return false;
                }
            } else if (field === "createdAt" || field === "planTime") {
                const rowVal = field === "createdAt" ? row.createdAt : (row.planStartDate || row.planEndDate || "");
                if (!rowVal) return false;
                const rowDate = new Date(rowVal).getTime();
                if (isNaN(rowDate)) return false;
                const { operator, value } = fv;
                if (operator === "between") {
                    const [start, end] = value as [string, string];
                    if (start && rowDate < new Date(start).getTime()) return false;
                    if (end && rowDate > new Date(end + "T23:59:59").getTime()) return false;
                } else {
                    const target = new Date(value).getTime();
                    if (isNaN(target)) continue;
                    if (operator === "gt" && rowDate <= target) return false;
                    if (operator === "lt" && rowDate >= target) return false;
                    if (operator === "gte" && rowDate < target) return false;
                    if (operator === "lte" && rowDate > target) return false;
                    if (operator === "eq" && new Date(rowVal).toDateString() !== new Date(value).toDateString()) return false;
                }
            }
        }
        return true;
    });
};

const applyColumnSort = (rows: RowItem[]): RowItem[] => {
    const field = columnSortField.value;
    const order = columnSortOrder.value;
    if (!field || !order) return rows;

    const sorted = [...rows];
    const dir = order === "ascend" ? 1 : -1;

    sorted.sort((a, b) => {
        let va: any;
        let vb: any;
        if (field === "status") {
            va = a.status || "";
            vb = b.status || "";
        } else if (field === "tags") {
            va = (a.tags || []).join(",");
            vb = (b.tags || []).join(",");
        } else if (field === "createdAt") {
            va = a.createdAt || "";
            vb = b.createdAt || "";
        } else if (field === "planTime") {
            va = a.planStartDate || a.planEndDate || "";
            vb = b.planStartDate || b.planEndDate || "";
        } else {
            return 0;
        }
        if (va < vb) return -1 * dir;
        if (va > vb) return 1 * dir;
        return 0;
    });
    return sorted;
};

const request = async (params: ProTableRequestParams): Promise<ProTableResponse<RowItem>> => {
    const kw = String(params.keyword ?? "").trim().toLowerCase();
    const ownerValue = String(params.owner ?? "").trim();
    const { ownerMemberId, matchOwner } = createOwnerMatcher(ownerValue);
    const typeValue = String(props.type ?? params.type ?? "").trim();
    const statusValue = String(params.status ?? "").trim();
    const current = Number(params.current || 1);
    const pageSize = Number(params.pageSize || 20);

    const effectiveSortField = columnSortField.value || params.sortField || "";
    const effectiveSortOrder = columnSortOrder.value || params.sortOrder || null;
    const typeOverrides = SORT_FIELD_OVERRIDES[typeValue];
    let backendSortBy = (typeOverrides && typeOverrides[effectiveSortField]) || SORT_FIELD_MAP[effectiveSortField] || "";
    if (backendSortBy === "priority" && typeValue === "缺陷") backendSortBy = "severity";
    const backendSortOrder = effectiveSortOrder === "ascend" ? "asc" : effectiveSortOrder === "descend" ? "desc" : "";

    if (props.useApi && (typeValue === "需求" || typeValue === "任务" || typeValue === "缺陷")) {
        const workType = typeValue as WorkItemType;
        const backendStates = statusValue ? getBackendStatesByDisplayStatus(workType, statusValue) : undefined;
        if (statusValue && (!backendStates || backendStates.length === 0)) {
            totalCount.value = 0;
            return { data: [], total: 0, current, pageSize };
        }
        const projectIdParam = props.projectId || undefined;
        const vf = props.viewFilters || {};
        const viewOwner = vf.owner || undefined;
        const viewCreator = vf.creator || undefined;
        const viewParticipant = vf.participant || undefined;
        const effectiveAssignee = ownerMemberId || viewOwner || undefined;
        const sortParams = backendSortBy ? { sort_by: backendSortBy, sort_order: backendSortOrder } : {};
        const requestByState = async (state?: string, page = current, size = pageSize) => {
            if (workType === "需求") {
                return getVortflowStories({
                    keyword: kw, state, parent_id: "root",
                    project_id: projectIdParam,
                    pm_id: ownerMemberId || viewOwner || undefined,
                    submitter_id: viewCreator,
                    participant_id: viewParticipant,
                    ...sortParams,
                    page, page_size: size
                });
            }
            if (workType === "任务") {
                return getVortflowTasks({
                    keyword: kw,
                    parent_id: "root",
                    state,
                    assignee_id: effectiveAssignee,
                    project_id: projectIdParam,
                    creator_id: viewCreator,
                    participant_id: viewParticipant,
                    ...sortParams,
                    page,
                    page_size: size
                });
            }
            return getVortflowBugs({
                keyword: kw,
                state,
                assignee_id: effectiveAssignee,
                project_id: projectIdParam,
                reporter_id: viewCreator,
                participant_id: viewParticipant,
                ...sortParams,
                page,
                page_size: size
            });
        };
        const fetchAllItemsByState = async (state?: string): Promise<any[]> => {
            const batchSize = 100;
            const firstRes: any = await requestByState(state, 1, batchSize);
            const allItems: any[] = [...((firstRes as any)?.items || [])];
            const total = Number((firstRes as any)?.total || allItems.length);
            const totalPages = Math.max(1, Math.ceil(total / batchSize));
            for (let page = 2; page <= totalPages; page++) {
                const pageRes: any = await requestByState(state, page, batchSize);
                const pageItems = ((pageRes as any)?.items || []);
                if (!pageItems.length) break;
                allItems.push(...pageItems);
            }
            return allItems;
        };
        const buildRowsFromItems = (items: any[]): RowItem[] => {
            const rows = items.map((item: any, idx: number) => mapBackendItemToRow(item, workType, idx));
            if (workType === "需求" || workType === "任务") {
                cacheItemRows(rows);
            }
            return rows;
        };

        let rows: RowItem[] = [];
        let totalFromApi = 0;

        if (backendStates && backendStates.length > 1) {
            // Multi-state display filters need full merged querying across all pages.
            const merged = new Map<string, any>();
            const itemGroups = await Promise.all(backendStates.map((state) => fetchAllItemsByState(state)));
            for (const items of itemGroups) {
                for (const item of items) {
                    const id = String(item?.id || "");
                    if (!id || merged.has(id)) continue;
                    merged.set(id, item);
                }
            }
            const mergedItems = [...merged.values()];
            const allRows = buildRowsFromItems(mergedItems)
                .filter((x) => !statusValue || x.status === statusValue)
                .filter(matchOwner);
            totalFromApi = allRows.length;
            const start = (current - 1) * pageSize;
            rows = allRows.slice(start, start + pageSize);
        } else {
            const backendState = backendStates?.[0];
            if (ownerValue && (workType === "需求" || ownerValue === "未指派" || !ownerMemberId)) {
                const allItems = await fetchAllItemsByState(backendState);
                const allRows = buildRowsFromItems(allItems)
                    .filter((x) => !statusValue || x.status === statusValue)
                    .filter(matchOwner);
                totalFromApi = allRows.length;
                const start = (current - 1) * pageSize;
                rows = allRows.slice(start, start + pageSize);
            } else {
                const res: any = await requestByState(backendState, current, pageSize);
                rows = buildRowsFromItems((res as any)?.items || []);
                if (statusValue) rows = rows.filter((x) => x.status === statusValue);
                if (ownerValue) rows = rows.filter(matchOwner);
                totalFromApi = Number((res as any)?.total || rows.length);
            }
        }

        if (current === 1) {
            let pinnedRows = pinnedRowsByType[workType] || [];
            if (statusValue) pinnedRows = pinnedRows.filter((x) => x.status === statusValue);
            if (ownerValue) pinnedRows = pinnedRows.filter(matchOwner);
            const pinnedIds = new Set(pinnedRows.map((x) => x.backendId || x.workNo));
            rows = [...pinnedRows, ...rows.filter((x) => !pinnedIds.has(x.backendId || x.workNo))];
            rows = rows.slice(0, pageSize);
        }
        const isIncompleteView = vf.status === "incomplete";
        if (isIncompleteView) {
            const completedStatuses: Set<string> = new Set(["已完成", "已关闭", "已取消", "发布完成"]);
            rows = rows.filter((x) => !completedStatuses.has(x.status));
            totalFromApi = rows.length;
        }
        rows = applyColumnFilters(rows);
        rows = applyColumnSort(rows);
        totalFromApi = rows.length;
        collectTagOptions(workType === "需求" || workType === "任务" ? getVisibleChildRows(rows, ownerValue, statusValue) : rows);
        totalCount.value = totalFromApi;
        return { data: rows, total: totalFromApi, current, pageSize };
    }

    totalCount.value = 0;
    return { data: [], total: 0, current, pageSize };
};

const tableRef = ref<any>(null);

const queryParams = computed(() => ({
    keyword: keyword.value,
    owner: owner.value,
    type: props.type || type.value,
    status: status.value
}));

const onReset = () => {
    keyword.value = "";
    owner.value = "";
    type.value = props.type ?? "";
    status.value = "";
    tableRef.value?.refresh?.();
};

watch(() => props.projectId, () => {
    tableRef.value?.refresh?.();
});

watch(() => props.viewFilters, () => {
    tableRef.value?.refresh?.();
}, { deep: true });

const rowKeyGetter = (record: RowItem) => record.backendId || record.workNo;

const rowSelection = computed(() => ({
    selectedRowKeys: selectedRowKeys.value,
    onChange: (keys: Array<string | number>, rows: RowItem[]) => {
        selectedRowKeys.value = keys;
        selectedRows.value = rows;
    },
}));

const clearSelection = () => {
    selectedRowKeys.value = [];
    selectedRows.value = [];
};

const deleteOne = async (record: RowItem) => {
    const id = record.backendId;
    if (!id) throw new Error("缺少记录ID");
    const itemType = (props.type || record.type) as WorkItemType;
    if (itemType === "需求") await deleteVortflowStory(id);
    else if (itemType === "任务") await deleteVortflowTask(id);
    else await deleteVortflowBug(id);
};

const handleBatchDelete = async () => {
    if (!selectedRows.value.length) return;
    const rows = [...selectedRows.value];
    const results = await Promise.allSettled(rows.map((row) => deleteOne(row)));
    const failed = results.filter((r) => r.status === "rejected").length;
    if (failed === 0) message.success(`已删除 ${rows.length} 条`);
    else if (failed === rows.length) message.error("批量删除失败");
    else message.warning(`已删除 ${rows.length - failed} 条，失败 ${failed} 条`);
    clearSelection();
    tableRef.value?.refresh?.();
};

const resetCreateBugForm = () => {
    Object.assign(createBugForm, createInitialBugForm());
    createBugAttachments.value = [];
};

const handleCreateBug = async () => {
    await loadApiMetadata(props.type === "任务");
    createBugDrawerMode.value = "create";
    createParentItemId.value = "";
    createProjectId.value = "";
    resetCreateBugForm();
    createBugForm.type = props.type ?? createBugForm.type;
    router.replace({ query: { ...route.query, action: "create", parentId: undefined } });
};

const handleCreateChild = async (record: RowItem) => {
    if ((record.type !== "需求" && record.type !== "任务") || !record.backendId) return;
    await loadApiMetadata(record.type === "任务");
    createBugDrawerMode.value = "create";
    createParentItemId.value = String(record.backendId);
    createProjectId.value = record.projectId || "";
    resetCreateBugForm();
    router.replace({ query: { ...route.query, action: "create", parentId: String(record.backendId), id: undefined } });
};

const handleCancelCreateBug = () => {
    createBugDrawerOpen.value = false;
    createParentItemId.value = "";
    createProjectId.value = "";
};

const handleCancelCreateWorkItem = () => {
    if (createWorkItemRef.value) {
        createWorkItemRef.value.cancel();
        return;
    }
    handleCancelCreateBug();
};

const handleDetailUpdate = (data: Partial<RowItem>) => {
    if (detailCurrentRecord.value) {
        Object.assign(detailCurrentRecord.value, data);
        tableRef.value?.refresh?.();
    }
};

const toggleItemExpand = async (record: RowItem) => {
    if ((record.type !== "需求" && record.type !== "任务") || !record.childrenCount || !record.backendId) return;
    const itemId = String(record.backendId);
    if (expandingItemIds[itemId]) return;
    if (expandedItemIds[itemId]) {
        expandedItemIds[itemId] = false;
        return;
    }
    if (!itemChildrenMap[itemId]) {
        expandingItemIds[itemId] = true;
        try {
            await loadChildItems(itemId, record.type, record.projectId);
        } finally {
            expandingItemIds[itemId] = false;
        }
    }
    expandedItemIds[itemId] = true;
};

const detailParentRecord = ref<RowItem | null>(null);
const detailChildRecords = ref<RowItem[]>([]);
const createParentRecord = computed<RowItem | null>(() => findItemRowById(createParentItemId.value));

const syncDetailRelations = async (record: RowItem) => {
    if (record.type !== "需求" && record.type !== "任务") {
        detailParentRecord.value = null;
        detailChildRecords.value = [];
        return;
    }
    detailParentRecord.value = await loadItemById(record.parentId, record.type);
    if (record.backendId && record.childrenCount) {
        detailChildRecords.value = await loadChildItems(record.backendId, record.type, record.projectId);
    } else {
        detailChildRecords.value = [];
    }
};

const handleCreateSuccess = async (formData: NewBugForm, keepCreating = false) => {
    if (createBugDrawerMode.value !== "create") {
        createBugDrawerOpen.value = false;
        return;
    }

    const title = formData.title.trim();
    if (!title) {
        message.warning("请填写标题");
        return;
    }

    if (props.useApi) {
        const type = (props.type || formData.type || "缺陷") as WorkItemType;
        try {
            let createdItem: any = null;
            const ownerId = getMemberIdByName(formData.owner) || undefined;
            if (type === "需求") {
                const defaultProject = formData.projectId || createProjectId.value || resolveCreateProjectId();
                createdItem = await createVortflowStory({
                    project_id: defaultProject,
                    title,
                    description: formData.description || defaultDescriptionTemplate,
                    priority: formData.priority === "urgent" ? 1 : formData.priority === "high" ? 2 : formData.priority === "medium" ? 3 : 4,
                    parent_id: formData.parentId || undefined,
                    tags: [...formData.tags],
                    collaborators: [...formData.collaborators],
                    deadline: formData.planTime?.[1] || undefined,
                });
                if (createdItem?.id && ownerId) {
                    try {
                        createdItem = await updateVortflowStory(String(createdItem.id), { pm_id: ownerId });
                    } catch {
                        createdItem = { ...createdItem, pm_id: ownerId };
                    }
                }
            } else if (type === "任务") {
                createdItem = await createVortflowTask({
                    story_id: formData.storyId || undefined,
                    parent_id: formData.parentId || undefined,
                    title,
                    description: formData.description || "",
                    task_type: "develop",
                    assignee_id: ownerId,
                    tags: [...formData.tags],
                    collaborators: [...formData.collaborators],
                    deadline: formData.planTime?.[1] || undefined,
                });
            } else {
                createdItem = await createVortflowBug({
                    story_id: formData.storyId || undefined,
                    title,
                    description: formData.description || defaultDescriptionTemplate,
                    severity: formData.priority === "urgent" ? 1 : formData.priority === "high" ? 2 : formData.priority === "medium" ? 3 : 4,
                    assignee_id: ownerId,
                    tags: [...formData.tags],
                    collaborators: [...formData.collaborators],
                });
            }
            if (createdItem) {
                const pinnedRow = mapBackendItemToRow(createdItem, type, 0);
                if ((type === "需求" || type === "任务") && formData.parentId) {
                    const parentId = formData.parentId;
                    const existingChildren = itemChildrenMap[parentId] || [];
                    itemChildrenMap[parentId] = [{ ...pinnedRow, isChild: true }, ...existingChildren];
                    const parentRow = itemRowsById[parentId];
                    if (parentRow) {
                        parentRow.childrenCount = (parentRow.childrenCount || 0) + 1;
                    }
                    expandedItemIds[parentId] = true;
                } else {
                    prependPinnedRow(type, pinnedRow);
                }
            }
            tableRef.value?.refresh?.();
            message.success("新建成功");
            if (keepCreating) {
                createWorkItemRef.value?.reset();
            } else {
                handleCancelCreateBug();
            }
            return;
        } catch (error: any) {
            message.error(error?.message || "新建失败");
            return;
        }
    }
};

const handleSubmitCreateBug = async (keepCreating = false) => {
    const formData = createWorkItemRef.value?.submit();
    if (!formData) return;
    await handleCreateSuccess(formData, keepCreating);
};

const openCreateAttachmentDialog = () => {
    createAttachmentInputRef.value?.click();
};

const onCreateAttachmentChange = (event: Event) => {
    const target = event.target as HTMLInputElement;
    const files = target.files;
    if (!files || files.length === 0) return;

    const next = [...createBugAttachments.value];
    for (const file of Array.from(files)) {
        const exists = next.some((x) => x.name === file.name && x.size === file.size);
        if (exists) continue;
        next.push({
            id: `${file.name}-${file.size}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            name: file.name,
            size: file.size
        });
    }
    createBugAttachments.value = next;
    target.value = "";
};

const removeCreateAttachment = (id: string) => {
    createBugAttachments.value = createBugAttachments.value.filter((x) => x.id !== id);
};

const detailRecordSnapshot = ref<RowItem | null>(null);

const handleOpenBugDetail = async (record: RowItem) => {
    detailSelectedWorkNo.value = record.workNo;
    detailRecordSnapshot.value = record;
    detailActiveTab.value = "detail";
    detailBottomTab.value = "comments";
    detailCommentDraft.value = "";
    detailDescEditing.value = false;
    detailDescDraft.value = "";
    ensureDetailPanelsData(record);
    await syncDetailRelations(record);

    const currentPriority = getRowPriority(record, record.priority);
    const currentTags = getRowTags(record, record.tags);
    const currentPlanTime = planTimeModel[record.workNo] || record.planTime;
    const base = createInitialBugForm();

    createBugDrawerMode.value = "detail";
    Object.assign(createBugForm, {
        ...base,
        title: record.title,
        owner: record.owner === "未指派" ? "" : record.owner,
        type: record.type,
        planTime: [...currentPlanTime],
        priority: currentPriority,
        tags: [...currentTags],
        description: record.description || base.description
    });

    router.replace({ query: { ...route.query, action: "detail", id: record.workNo } });
};

const detailCurrentRecord = computed<RowItem | null>(() => {
    if (!detailSelectedWorkNo.value) return null;
    if (detailRecordSnapshot.value?.workNo === detailSelectedWorkNo.value) {
        return detailRecordSnapshot.value;
    }
    return detailRecordSnapshot.value || null;
});

const detailComments = computed<DetailComment[]>(() => {
    const workNo = detailSelectedWorkNo.value;
    if (!workNo) return [];
    return detailCommentsMap[workNo] || [];
});

const detailLogs = computed<DetailLog[]>(() => {
    const workNo = detailSelectedWorkNo.value;
    if (!workNo) return [];
    return detailLogsMap[workNo] || [];
});

const ensureDetailPanelsData = (record: RowItem) => {
    if (!detailCommentsMap[record.workNo]) {
        detailCommentsMap[record.workNo] = [];
    }
    if (!detailLogsMap[record.workNo]) {
        detailLogsMap[record.workNo] = [];
    }
};

const appendDetailLog = (action: string) => {
    const workNo = detailSelectedWorkNo.value;
    if (!workNo) return;
    if (!detailLogsMap[workNo]) detailLogsMap[workNo] = [];
    detailLogsMap[workNo].unshift({
        id: `${workNo}-l-${Date.now()}`,
        actor: detailCurrentUser,
        createdAt: "刚刚",
        action
    });
};

const submitDetailComment = () => {
    const workNo = detailSelectedWorkNo.value;
    const content = detailCommentDraft.value.trim();
    if (!workNo || !content) {
        message.warning("请先输入评论内容");
        return;
    }
    if (!detailCommentsMap[workNo]) detailCommentsMap[workNo] = [];
    detailCommentsMap[workNo].unshift({
        id: `${workNo}-c-${Date.now()}`,
        author: detailCurrentUser,
        createdAt: "刚刚",
        content
    });
    detailCommentDraft.value = "";
    appendDetailLog("发布评论");
    message.success("评论已发布");
};

const openDetailDescEditor = () => {
    if (!detailCurrentRecord.value) return;
    detailDescDraft.value = detailCurrentRecord.value.description || "";
    detailDescEditing.value = true;
};

const cancelDetailDescEditor = () => {
    detailDescEditing.value = false;
    detailDescDraft.value = "";
};

const saveDetailDescEditor = async () => {
    if (!detailCurrentRecord.value) return;
    const record = detailCurrentRecord.value;
    const prev = record.description || "";
    const next = detailDescDraft.value || "";
    record.description = next;
    try {
        await syncRecordUpdateToApi(record, { description: next });
    } catch (error: any) {
        record.description = prev;
        message.error(error?.message || "描述同步失败");
        return;
    }
    detailDescEditing.value = false;
    appendDetailLog("更新描述");
    message.success("描述已保存");
};

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

const tagColorPalette = ["#ef4444", "#d946ef", "#eab308", "#22c55e", "#3b82f6", "#f97316", "#14b8a6", "#8b5cf6"];
const tagColorOverrides = reactive<Record<string, string>>({});

const getTagColor = (name: string): string => {
    if (tagColorOverrides[name]) return tagColorOverrides[name]!;
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
    return tagColorPalette[hash % tagColorPalette.length]!;
};

const getRowTags = (record: RowItem, text?: string[]): string[] => {
    return tagsModel[record.workNo] || text || [];
};

const rowTagOptions = computed(() => dynamicTagOptions.value.length ? dynamicTagOptions.value : baseTagOptions);

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
    const existing = new Set<string>([...baseTagOptions, ...dynamicTagOptions.value]);
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

const getRowPlanTimeText = (record: RowItem, text?: DateRange): string => {
    const value = getRowPlanTime(record, text);
    const start = normalizeDateValue(value[0]) || "-";
    const end = normalizeDateValue(value[1]) || "-";
    return `${start} ~ ${end}`;
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

const getCollapsedTags = (tags: string[], resolvedWidth?: string | number): { visible: string[]; hidden: number } => {
    const width = typeof resolvedWidth === "number"
        ? resolvedWidth
        : (typeof resolvedWidth === "string" ? Number.parseFloat(resolvedWidth) : 180);
    const cellWidth = Number.isFinite(width) ? width : 180;
    const available = Math.max(48, cellWidth - 14);
    const moreReserve = 34;
    const gap = 4;
    let used = 0;
    const visible: string[] = [];
    const chipWidth = (text: string) => Math.max(36, text.length * 13 + 14);

    for (let i = 0; i < tags.length; i++) {
        const w = chipWidth(tags[i]!);
        const remaining = tags.length - i - 1;
        const nextUsed = used + (visible.length > 0 ? gap : 0) + w;
        const limit = remaining > 0 ? available - moreReserve : available;
        if (nextUsed > limit) break;
        visible.push(tags[i]!);
        used = nextUsed;
    }
    return { visible, hidden: Math.max(0, tags.length - visible.length) };
};

const getTagRenderInfo = (record: RowItem, text: string[] | undefined, resolvedWidth?: string | number) => {
    return getCollapsedTags(getRowTags(record, text), resolvedWidth);
};

const createProjectOptions = computed(() => {
    if (props.useApi && apiProjects.value.length > 0) {
        return apiProjects.value.map((x) => x.name);
    }
    return createBugProjectOptions;
});

const resolveCreateProjectId = (): string => {
    if (!apiProjects.value.length) return "";
    const selected = createBugForm.project?.trim();
    if (!selected) return apiProjects.value[0]?.id || "";
    const match = apiProjects.value.find((x) => x.name === selected || x.id === selected);
    return match?.id || apiProjects.value[0]?.id || "";
};

const loadApiMetadata = async (withStories = false) => {
    if (!props.useApi) return;
    const tasks: Promise<any>[] = [getVortflowProjects()];
    if (withStories) {
        tasks.push(getVortflowStories({ page: 1, page_size: 100 }));
    }
    const results = await Promise.allSettled(tasks);
    const projectsRes = results[0];
    const storiesRes = withStories ? results[1] : undefined;
    if (projectsRes && projectsRes.status === "fulfilled") {
        apiProjects.value = ((projectsRes.value as any)?.items || []).map((x: any) => ({ id: String(x.id), name: String(x.name || x.id) }));
        if (apiProjects.value.length > 0) {
            const names = new Set(apiProjects.value.map((x) => x.name));
            if (!createBugForm.project || !names.has(createBugForm.project)) {
                createBugForm.project = apiProjects.value[0]!.name;
            }
        }
    }
    if (storiesRes && storiesRes.status === "fulfilled") {
        apiStories.value = ((storiesRes.value as any)?.items || []).map((x: any) => ({ id: String(x.id), title: String(x.title || x.id) }));
    }
};

onMounted(async () => {
    await loadMemberOptions();
    await loadApiMetadata(false);
    tableRef.value?.refresh?.();

    const action = route.query.action as string;
    const id = route.query.id as string;
    const parentId = route.query.parentId as string;
    if (action === "create") {
        await handleCreateBug();
        if (parentId) {
            createParentItemId.value = parentId;
            createProjectId.value = findItemRowById(parentId)?.projectId || "";
        }
    } else if (action === "detail" && id) {
        const cached = findItemRowById(id);
        if (cached) {
            handleOpenBugDetail(cached);
        }
    }
});
</script>

<template>
    <div class="space-y-4">
        <WorkItemFilters
            v-model:keyword="keyword"
            v-model:owner="owner"
            v-model:type="type"
            v-model:status="status"
            :page-title="props.pageTitle"
            :create-button-text="props.createButtonText"
            :total-count="totalCount"
            :member-options="memberOptions"
            :owner-groups="ownerGroups"
            :status-options="currentStatusFilterOptions"
            :show-type-filter="!props.type"
            @search="tableRef?.refresh?.()"
            @reset="onReset"
            @create="handleCreateBug"
        >
            <template v-if="currentWorkItemType" #before-count>
                <ViewSelector
                    :views="mergedViews"
                    :selected-id="currentViewId"
                    @update:selected-id="onViewChange"
                    @create-view="viewCreateOpen = true"
                    @manage-views="viewManageOpen = true"
                />
            </template>
            <template #extra-actions>
                <MoreActionsDropdown
                    @import="importDialogOpen = true"
                    @import-records="importRecordDialogOpen = true"
                    @export-csv="handleExportCsv"
                    @export-excel="handleExportExcel"
                    @export-json="handleExportJson"
                    @batch-ops="batchPropertyEditorOpen = true"
                />
            </template>
        </WorkItemFilters>

        <div class="bg-white rounded-xl p-4 relative">
            <div v-if="selectedRows.length > 0" class="mb-3 flex items-center gap-3 text-sm">
                <span class="text-blue-500 font-medium">已选择 {{ selectedRows.length }} 个工作项</span>
                <VortButton variant="text" @click="batchPropertyEditorOpen = true">修改属性</VortButton>
                <vort-popconfirm title="确认批量删除选中记录？" @confirm="handleBatchDelete">
                    <VortButton variant="text" danger>删除</VortButton>
                </vort-popconfirm>
                <VortButton variant="link" @click="clearSelection">取消选择</VortButton>
            </div>
            <vort-tooltip title="表头显示设置">
                <button
                    type="button"
                    class="absolute top-4 right-4 w-7 h-7 flex items-center justify-center rounded border border-gray-200 text-gray-400 hover:text-blue-500 hover:border-blue-300 transition-colors z-10"
                    @click="columnSettingsOpen = true"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
            </vort-tooltip>
            <ProTable
                ref="tableRef"
                :columns="columns"
                :request="request"
                :post-process-data="postProcessTableRows"
                :params="queryParams"
                :row-key="rowKeyGetter"
                :row-selection="rowSelection"
                :pagination="{ pageSize: 20, showSizeChanger: true, showQuickJumper: true, pageSizeOptions: [10, 20, 50] }"
                :toolbar="false"
                bordered
            >
                <template #header-status="{ column }">
                    <span>{{ column.title }}</span>
                    <ColumnFilterPopover
                        field="status"
                        :title="column.title || ''"
                        :config="statusFilterConfig"
                        :sort-order="columnSortField === 'status' ? columnSortOrder : null"
                        :filter-value="columnFilters['status']"
                        @sort="(o) => handleColumnSort('status', o)"
                        @filter="(v) => handleColumnFilter('status', v)"
                    />
                </template>

                <template #header-createdAt="{ column }">
                    <span>{{ column.title }}</span>
                    <ColumnFilterPopover
                        field="createdAt"
                        :title="column.title || ''"
                        :config="dateFilterConfig"
                        :sort-order="columnSortField === 'createdAt' ? columnSortOrder : null"
                        :filter-value="columnFilters['createdAt']"
                        @sort="(o) => handleColumnSort('createdAt', o)"
                        @filter="(v) => handleColumnFilter('createdAt', v)"
                    />
                </template>

                <template #header-tags="{ column }">
                    <span>{{ column.title }}</span>
                    <ColumnFilterPopover
                        field="tags"
                        :title="column.title || ''"
                        :config="tagsFilterConfig"
                        :sort-order="columnSortField === 'tags' ? columnSortOrder : null"
                        :filter-value="columnFilters['tags']"
                        @sort="(o) => handleColumnSort('tags', o)"
                        @filter="(v) => handleColumnFilter('tags', v)"
                    />
                </template>

                <template #header-planTime="{ column }">
                    <span>{{ column.title }}</span>
                    <ColumnFilterPopover
                        field="planTime"
                        :title="column.title || ''"
                        :config="dateFilterConfig"
                        :sort-order="columnSortField === 'planTime' ? columnSortOrder : null"
                        :filter-value="columnFilters['planTime']"
                        @sort="(o) => handleColumnSort('planTime', o)"
                        @filter="(v) => handleColumnFilter('planTime', v)"
                    />
                </template>

                <template #header-owner="{ column }">
                    <span>{{ column.title }}</span>
                    <ColumnFilterPopover
                        field="owner"
                        :title="column.title || ''"
                        :config="ownerFilterConfig"
                        :sort-order="columnSortField === 'owner' ? columnSortOrder : null"
                        :filter-value="columnFilters['owner']"
                        @sort="(o) => handleColumnSort('owner', o)"
                        @filter="(v) => handleColumnFilter('owner', v)"
                    />
                </template>

                <template #header-collaborators="{ column }">
                    <span>{{ column.title }}</span>
                    <ColumnFilterPopover
                        field="collaborators"
                        :title="column.title || ''"
                        :config="collaboratorsFilterConfig"
                        :sort-order="columnSortField === 'collaborators' ? columnSortOrder : null"
                        :filter-value="columnFilters['collaborators']"
                        @sort="(o) => handleColumnSort('collaborators', o)"
                        @filter="(v) => handleColumnFilter('collaborators', v)"
                    />
                </template>

                <template #workNo="{ text }">
                    <TableCell>
                        <span class="text-sm text-gray-700">{{ text }}</span>
                    </TableCell>
                </template>

                <template #title="{ text, record }">
                    <TableCell @click="handleOpenBugDetail(record)">
                        <VortButton class="title-link-cell" :title="text" variant="link" @click.stop="handleOpenBugDetail(record)">
                            <span
                                v-if="record.childrenCount"
                                class="story-expand-toggle"
                                :class="{
                                    expanded: expandedItemIds[String(record.backendId || '')],
                                    loading: expandingItemIds[String(record.backendId || '')]
                                }"
                                @click.stop="toggleItemExpand(record)"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" aria-hidden="true" role="img" class="flex-shrink-0 iconify iconify--gitee icon-caret-down" width="1em" height="1em" preserveAspectRatio="xMidYMid meet" viewBox="0 0 16 16"><g fill="none" fill-rule="evenodd"><path d="M0 0h16v16H0z"></path><path fill="currentColor" fill-rule="nonzero" d="m10.835 7.638-2.388 2.666a.628.628 0 01-.441.196.57.57 0 01-.426-.195L5.192 7.638c-.188-.19-.24-.478-.147-.725s.313-.413.556-.413h4.793c.243 0 .462.162.556.411.093.25.058.537-.115.727z"></path></g></svg>
                            </span>
                            <span v-else-if="record.isChild" class="story-child-indent"></span>
                            <span v-else class="story-expand-placeholder"></span>
                            
                            <span class="work-type-icon" :class="getWorkItemTypeIconClass(record.type)">
                                {{ getWorkItemTypeIconSymbol(record.type) }}
                            </span>

                            <span class="title-link-text" :class="{ 'story-child-text': record.isChild }">{{ text }}</span>
                        </VortButton>
                    </TableCell>
                </template>

                <template #priority="{ text, record }">
                    <TableCell @click="openCellPickerOnBackgroundClick(record, $event, priorityPickerOpenMap)">
                        <WorkItemPriority
                            v-model:open="priorityPickerOpenMap[getInteractiveCellKey(record)]"
                            :model-value="getRowPriority(record, text)"
                            @change="(value) => selectPriority(record, value)"
                        />
                    </TableCell>
                </template>

                <template #tags="{ text, record, resolvedWidth }">
                    <TableCell @click="openCellPickerOnBackgroundClick(record, $event, tagPickerOpenMap)">
                        <WorkItemTagPicker
                            v-model:open="tagPickerOpenMap[getInteractiveCellKey(record)]"
                            :model-value="getRowTags(record, text)"
                            :options="rowTagOptions"
                            :get-tag-color="getTagColor"
                            :bordered="false"
                            @update:model-value="(value) => setRowTags(record, value)"
                        >
                            <template #trigger>
                                <div class="flex items-center gap-1 flex-nowrap whitespace-nowrap overflow-hidden">
                                    <template v-for="tag in getTagRenderInfo(record, text, resolvedWidth).visible" :key="record.workNo + '-' + tag">
                                        <span
                                            class="px-1.5 py-0.5 rounded text-xs text-white inline-block"
                                            :style="{ backgroundColor: getTagColor(tag) }"
                                        >
                                            {{ tag }}
                                        </span>
                                    </template>
                                    <span v-if="getTagRenderInfo(record, text, resolvedWidth).hidden > 0" class="text-gray-400 font-medium text-sm">
                                        +{{ getTagRenderInfo(record, text, resolvedWidth).hidden }}
                                    </span>
                                </div>
                            </template>
                            <template #footer>
                                <div class="mt-1 px-3 py-2 text-left">
                                    <button
                                        type="button"
                                        class="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
                                        @click.stop="openCreateTagDialog(record, text)"
                                    >
                                        <span class="text-base leading-none">+</span>
                                        <span>新建标签</span>
                                    </button>
                                </div>
                            </template>
                        </WorkItemTagPicker>
                    </TableCell>
                </template>

                <template #status="{ text, record }">
                    <TableCell @click="openCellPickerOnBackgroundClick(record, $event, statusPickerOpenMap)">
                        <WorkItemStatus
                            v-model:open="statusPickerOpenMap[getInteractiveCellKey(record)]"
                            :model-value="getRowStatus(record, text)"
                            :options="getStatusOptionsByType(record.type || resolveActiveType())"
                            @change="(value) => selectRowStatus(record, value)"
                        />
                    </TableCell>
                </template>

                <template #owner="{ text, record }">
                    <TableCell @click="openCellPickerOnBackgroundClick(record, $event, ownerPickerOpenMap)">
                        <WorkItemMemberPicker
                            v-model:open="ownerPickerOpenMap[getInteractiveCellKey(record)]"
                            mode="owner"
                            :owner="getRowOwner(record, text)"
                            :groups="ownerGroups"
                            :dropdown-max-height="420"
                            :bordered="false"
                            :get-avatar-bg="getAvatarBg"
                            :get-avatar-label="getAvatarLabel"
                            :get-avatar-url="getMemberAvatarUrl"
                            @update:owner="(value) => selectRowOwner(record, value)"
                        >
                            <template #trigger>
                                <div
                                    class="h-8 max-w-[150px] px-2 rounded-md bg-transparent flex items-center gap-2 cursor-pointer"
                                >
                                    <span
                                        class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center shrink-0 overflow-hidden"
                                        :style="{ backgroundColor: getAvatarBg(getRowOwner(record, text)) }"
                                    >
                                        <img v-if="getMemberAvatarUrl(getRowOwner(record, text))" :src="getMemberAvatarUrl(getRowOwner(record, text))" class="w-full h-full object-cover" />
                                        <template v-else>{{ getAvatarLabel(getRowOwner(record, text)) }}</template>
                                    </span>
                                    <span class="text-sm text-gray-700 truncate">{{ getRowOwner(record, text) }}</span>
                                </div>
                            </template>
                        </WorkItemMemberPicker>
                    </TableCell>
                </template>

                <template #creator="{ text }">
                    <TableCell>
                        <div class="h-8 max-w-[150px] px-2 rounded-md bg-transparent flex items-center gap-2">
                            <span
                                class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center shrink-0"
                                :style="{ backgroundColor: getAvatarBg(text) }"
                            >
                                {{ getAvatarLabel(text) }}
                            </span>
                            <span class="text-sm text-gray-700 truncate">{{ text }}</span>
                        </div>
                    </TableCell>
                </template>

                <template #collaborators="{ text, record }">
                    <TableCell @click="openCellPickerOnBackgroundClick(record, $event, collaboratorsPickerOpenMap)">
                        <WorkItemMemberPicker
                            v-model:open="collaboratorsPickerOpenMap[getInteractiveCellKey(record)]"
                            mode="collaborators"
                            :collaborators="getRowCollaborators(record, text)"
                            :groups="ownerGroups"
                            :dropdown-max-height="260"
                            :bordered="false"
                            :get-avatar-bg="getAvatarBg"
                            :get-avatar-label="getAvatarLabel"
                            :get-avatar-url="getMemberAvatarUrl"
                            @update:collaborators="(value) => setRowCollaborators(record, value)"
                        >
                            <template #trigger>
                                <div
                                    class="h-8 px-1 rounded-md bg-transparent flex items-center cursor-pointer"
                                >
                                    <div class="flex items-center">
                                        <div
                                            v-for="(name, idx) in getRowCollaborators(record, text)"
                                            :key="record.workNo + '-c-' + name + idx"
                                            class="-ml-1 first:ml-0 w-6 h-6 rounded-full border border-white text-white text-[11px] flex items-center justify-center overflow-hidden"
                                            :style="{ backgroundColor: getAvatarBg(name) }"
                                            :title="name"
                                        >
                                            <img v-if="getMemberAvatarUrl(name)" :src="getMemberAvatarUrl(name)" class="w-full h-full object-cover" />
                                            <template v-else>{{ getAvatarLabel(name) }}</template>
                                        </div>
                                    </div>
                                </div>
                            </template>
                        </WorkItemMemberPicker>
                    </TableCell>
                </template>

                <template #planTime="{ text, record }">
                    <TableCell @click.stop="togglePlanTimeMenu(record.workNo, record, text)">
                        <div class="relative inline-block" @click.stop>
                            <span
                                v-if="openPlanTimeFor !== record.workNo"
                                class="plan-time-display text-sm text-gray-700 cursor-pointer"
                                @click.stop="togglePlanTimeMenu(record.workNo, record, text)"
                            >
                                {{ getRowPlanTimeText(record, text) }}
                            </span>
                            <vort-range-picker
                                v-else
                                v-model="planTimeModel[record.workNo]"
                                format="YYYY-MM-DD"
                                separator="~"
                                :open="planTimePickerOpen"
                                :allow-clear="false"
                                :placeholder="['开始', '结束']"
                                class="plan-time-picker"
                                @change="(value: any) => onPlanTimeChange(record, value || text)"
                                @open-change="(open: boolean) => onPlanTimeOpenChange(record, open)"
                                @click.stop
                            />
                        </div>
                    </TableCell>
                </template>

                <template #createdAt="{ text }">
                    <TableCell>
                        <span class="text-sm text-gray-700">{{ text }}</span>
                    </TableCell>
                </template>

                <template #type="{ text }">
                    <TableCell>
                        <span class="text-sm text-gray-700">{{ text }}</span>
                    </TableCell>
                </template>
            </ProTable>
        </div>

        <vort-drawer
            v-model:open="createBugDrawerOpen"
            :title="createBugDrawerMode === 'create' ? props.createDrawerTitle : props.detailDrawerTitle"
            :width="1180"
            :body-style="{ padding: '16px 20px 20px' }"
        >
            <template v-if="createBugDrawerMode === 'detail'">
                <WorkItemDetail
                    v-if="detailCurrentRecord"
                    :work-no="detailCurrentRecord.workNo"
                    :initial-data="detailCurrentRecord"
                    :parent-record="detailParentRecord"
                    :child-records="detailChildRecords"
                    @close="handleCancelCreateBug"
                    @update="handleDetailUpdate"
                    @open-related="handleOpenBugDetail"
                    @create-child="handleCreateChild"
                />
            </template>
            <template v-else>
                <WorkItemCreate
                    ref="createWorkItemRef"
                    :type="props.type"
                    :title="props.createDrawerTitle"
                    :use-api="props.useApi"
                    :project-id="createProjectId"
                    :parent-id="createParentItemId"
                    :parent-record="createParentRecord"
                    @close="handleCancelCreateBug"
                    @success="handleCreateSuccess"
                />
            </template>
            <template #footer>
                <div v-if="createBugDrawerMode === 'create'" class="create-bug-footer">
                    <VortButton variant="primary" @click="handleSubmitCreateBug()">新建</VortButton>
                    <VortButton @click="handleSubmitCreateBug(true)">新建并继续</VortButton>
                    <VortButton @click="handleCancelCreateWorkItem">取消</VortButton>
                </div>
            </template>
        </vort-drawer>

        <VortDialog
            :open="newTagDialogOpen"
            title="新建标签"
            :width="520"
            @update:open="(val) => (newTagDialogOpen = val)"
        >
            <div class="space-y-5 mt-2">
                <div>
                    <div class="text-sm text-gray-700 mb-1">名称</div>
                    <VortInput v-model="newTagName" placeholder="请输入标签名称" />
                </div>
                <div>
                    <div class="text-sm text-gray-700 mb-2">颜色</div>
                    <div class="grid grid-cols-8 gap-2">
                        <button
                            v-for="color in tagColorPalette"
                            :key="color"
                            type="button"
                            class="w-8 h-8 rounded-sm border-2 flex items-center justify-center transition"
                            :class="newTagColor === color ? 'border-blue-500 shadow-sm' : 'border-transparent'"
                            :style="{ backgroundColor: color }"
                            @click="newTagColor = color"
                        >
                            <span v-if="newTagColor === color" class="text-white text-xs">✓</span>
                        </button>
                    </div>
                </div>
            </div>
            <template #footer>
                <VortButton @click="handleCancelCreateTag">取消</VortButton>
                <VortButton variant="primary" class="ml-2" @click="handleConfirmCreateTag">确定</VortButton>
            </template>
        </VortDialog>

        <ImportDialog v-model:open="importDialogOpen" @done="tableRef?.refresh?.()" />
        <ImportRecordDialog v-model:open="importRecordDialogOpen" />
        <BatchPropertyEditor
            v-model:open="batchPropertyEditorOpen"
            :selected-rows="selectedRows"
            :work-item-type="(props.type || '缺陷') as WorkItemType"
            :status-options="currentStatusFilterOptions"
            @done="() => { clearSelection(); tableRef?.refresh?.(); }"
        />
        <ViewManageDialog v-model:open="viewManageOpen" />
        <ViewCreateDialog v-model:open="viewCreateOpen" @create="handleCreateViewFromDialog" />
        <ColumnSettingsDialog
            v-model:open="columnSettingsOpen"
            :all-columns="columnSettingsForDialog"
            @save="handleColumnSettingsSave"
        />
    </div>
</template>

<style scoped>
@reference "../../assets/styles/index.css";

.title-link-cell {
    @apply flex items-center justify-start gap-2 cursor-pointer max-w-full !p-0 !h-auto !bg-transparent;
}

.title-link-text {
    @apply truncate text-blue-600 hover:underline;
}

.story-expand-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45));
    transition: transform 0.2s ease, color 0.2s ease;
    flex-shrink: 0;
}

.story-expand-toggle svg {
    width: 18px;
    height: 18px;
    transform: rotate(-90deg);
    transition: transform 0.2s ease;
}

.story-expand-toggle.expanded svg {
    transform: rotate(0deg);
}

.story-expand-toggle.expanded {
    transform: none;
}

.story-expand-toggle.loading {
    pointer-events: none;
}

.story-expand-toggle.loading svg {
    animation: story-expand-spin 0.8s linear infinite;
}

.story-expand-placeholder {
    display: inline-block;
    width: 20px;
    flex-shrink: 0;
}

.story-child-indent {
    display: inline-block;
    width: 44px;
    flex-shrink: 0;
}

@keyframes story-expand-spin {
    from {
        transform: rotate(-90deg);
    }
    to {
        transform: rotate(270deg);
    }
}

.work-type-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    border-radius: 3px;
    font-size: 12px;
    color: #fff;
    flex-shrink: 0;
}

.work-type-icon-demand {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
}

.work-type-icon-task {
    background: linear-gradient(135deg, #0ea5e9 0%, #06b6d4 100%);
}

.work-type-icon-bug {
    background: linear-gradient(135deg, #ef4444 0%, #f97316 100%);
}

.story-child-text {
    padding-left: 0;
}

.story-children-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    margin-left: 6px;
    border-radius: 999px;
    background: rgba(99, 102, 241, 0.12);
    color: #4f46e5;
    font-size: 12px;
    line-height: 20px;
}

:deep(.plan-time-picker) {
    max-width: 260px;
    border-color: transparent !important;
    .vort-rangepicker-prefix,.vort-rangepicker-suffix{
        display: none;
    }
    .vort-rangepicker-separator{
    padding: 0 4px;
    }
    .vort-rangepicker-input{
    font-size: 13px;

    }
}

.create-bug-footer {
    display: flex;
    gap: 12px;
}

</style>