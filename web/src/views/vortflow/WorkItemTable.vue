<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ProTable, TableCell } from "@/components/vort-biz";
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
import { useVortFlowStore } from "@/stores";
import type { CustomView } from "@/stores/modules/vortflow";
import { useVortFlowViews, SYSTEM_VIEWS } from "./composables/useVortFlowViews";
import { useWorkItemExport } from "./composables/useWorkItemExport";
import { useWorkItemColumns } from "./composables/useWorkItemColumns";
import { useWorkItemViewState } from "./composables/useWorkItemViewState";
import { useWorkItemDataSource } from "./composables/useWorkItemDataSource";
import { useWorkItemCommon } from "./work-item/useWorkItemCommon";
import { useWorkItemInlineEdit } from "./work-item/useWorkItemInlineEdit";
import { useWorkItemDraft } from "./work-item/useWorkItemDraft";
import {
    getVortflowStories,
    getVortflowProjects, createVortflowStory, createVortflowTask, createVortflowBug,
    copyVortflowStory, copyVortflowTask, copyVortflowBug,
    deleteVortflowStory, deleteVortflowTask, deleteVortflowBug,
    updateVortflowStory, updateVortflowTask, updateVortflowBug,
    addVortflowIterationStory, addVortflowIterationTask, addVortflowIterationBug,
    removeVortflowIterationStory, removeVortflowIterationTask, removeVortflowIterationBug,
    addVortflowVersionStory, removeVortflowVersionStory,
    addVortflowVersionBug, removeVortflowVersionBug,
    getVortgitRepos, getVortgitRepoBranches,
    getVortflowTags,
    getVortflowIterations,
    getVortflowDescriptionTemplates,
    convertWorkItem,
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

const { views: mergedViews, activeViewFilters: builtInViewFilters } = currentWorkItemType.value
    ? useVortFlowViews(currentWorkItemType.value)
    : { views: computed(() => SYSTEM_VIEWS), activeViewFilters: computed(() => ({})) };

const handleCreateViewFromDialog = async (data: { name: string; scope: "personal" | "shared" }) => {
    const { filters, cols } = collectCurrentViewState();
    const maxOrder = vortFlowStore.customViews.reduce((max, v) => Math.max(max, v.order), -1);
    await vortFlowStore.addCustomView({
        name: data.name,
        work_item_type: props.type || "缺陷",
        scope: data.scope,
        visible: true,
        filters,
        columns: cols,
        order: maxOrder + 1,
    });
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
    loadStatusOptions,
} = useWorkItemCommon();

const { saveDraft, loadDraft, clearDraft } = useWorkItemDraft();
const createDraftData = ref<NewBugForm | null>(null);

const keyword = ref("");
const owner = ref<string[]>([]);
const type = ref<WorkItemType | "">(props.type ?? "");
const status = ref<string[]>([]);
const totalCount = ref(0);
const cacheDescDraftBeforeClose = () => {
    const comp = detailComponentRef.value;
    if (comp?.detailDescEditing && detailSelectedWorkNo.value) {
        detailDescDraftCache[detailSelectedWorkNo.value] = comp.detailDescDraft;
    }
};

const createBugDrawerOpen = computed({
    get: () => {
        const action = route.query.action as string;
        return action === "create" || action === "detail";
    },
    set: (val: boolean) => {
        if (!val) {
            cacheDescDraftBeforeClose();
            if (createBugDrawerMode.value === "create") {
                const formData = createWorkItemRef.value?.getFormData?.();
                const descTemplate = createWorkItemRef.value?.getDescriptionTemplateForCurrentType?.() ?? "";
                if (formData) {
                    const workItemType = (props.type || formData.type || "缺陷") as WorkItemType;
                    saveDraft(workItemType, formData, createParentItemId.value, descTemplate);
                }
            }
            router.replace({ query: { ...route.query, action: undefined, id: undefined, parentId: undefined, tab: undefined } });
        }
    }
});
const createBugDrawerMode = ref<"create" | "detail">("create");
const detailActiveTab = ref("detail");
const detailSelectedWorkNo = ref("");
const detailDescEditing = ref(false);
const detailDescDraft = ref("");
const detailDescDraftCache = reactive<Record<string, string>>({});
const detailBottomTab = ref<"comments" | "logs">("comments");
const detailCommentDraft = ref("");
const detailCommentsMap = reactive<Record<string, DetailComment[]>>({});
const detailLogsMap = reactive<Record<string, DetailLog[]>>({});
const createWorkItemRef = ref<{
    submit: () => NewBugForm | null;
    reset: () => void;
    cancel: () => void;
    getFormData: () => NewBugForm;
    getDescriptionTemplateForCurrentType: () => string;
} | null>(null);
const createBugAttachments = ref<CreateBugAttachment[]>([]);
const createAttachmentInputRef = ref<HTMLInputElement | null>(null);

const currentProjectName = computed(() => {
    if (!props.projectId) return "";
    return apiProjects.value.find(p => p.id === props.projectId)?.name || "";
});


const FALLBACK_TEMPLATES: Record<WorkItemType, string> = {
    "需求": "",
    "任务": "",
    "缺陷": "",
};

const remoteTemplates = ref<Record<string, string>>({});

const getDescriptionTemplate = (type: WorkItemType): string => {
    if (remoteTemplates.value[type] !== undefined && remoteTemplates.value[type] !== "") {
        return remoteTemplates.value[type];
    }
    return FALLBACK_TEMPLATES[type] ?? "";
};

const onAvatarError = (e: Event) => {
    const el = e.target as HTMLImageElement | null;
    if (el) el.style.display = "none";
};

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
    description: getDescriptionTemplate(props.type ?? "缺陷")
});
const createBugForm = reactive<NewBugForm>(createInitialBugForm());
const apiProjects = ref<Array<{ id: string; name: string }>>([]);
const apiIterations = ref<Array<{ id: string; name: string }>>([]);
const apiRepos = ref<Array<{ id: string; name: string }>>([]);
const apiStories = ref<Array<{ id: string; title: string }>>([]);
const branchOptionsMap = reactive<Record<string, Array<{ name: string }>>>({});
const branchLoadingMap = reactive<Record<string, boolean>>({});
const estimateEditingFor = ref<string | null>(null);
const estimateDraftMap = reactive<Record<string, number | null>>({});
const estimateInputRef = ref<any>(null);
const progressEditingFor = ref<string | null>(null);
const progressDraftMap = reactive<Record<string, number | null>>({});
const progressInputRef = ref<any>(null);
const projectPickerOpenMap = reactive<Record<string, boolean>>({});
const iterationPickerOpenMap = reactive<Record<string, boolean>>({});
const repoPickerOpenMap = reactive<Record<string, boolean>>({});
const branchPickerOpenMap = reactive<Record<string, boolean>>({});
const startAtPickerOpenMap = reactive<Record<string, boolean>>({});
const endAtPickerOpenMap = reactive<Record<string, boolean>>({});
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
    "收集中": "#94a3b8",
    "意向": "#64748b",
    "设计中": "#6366f1",
    "开发中": "#3b82f6",
    "测试完成": "#7c3aed",
    "已完成": "#059669",
    "待办的": "#64748b",
    "进行中": "#3b82f6",
    "延期处理": "#0284c7",
    "延期修复": "#3b82f6",
    "设计如此": "#d97706",
    "再次打开": "#ef4444",
    "无法复现": "#d97706",
    "暂时搁置": "#6b7280",
    "暂搁置": "#64748b",
    "开发完成": "#0891b2",
    "待发布": "#d97706",
    "发布完成": "#059669",
};

const statusFilterConfig = computed<ColumnFilterConfig>(() => ({
    type: "enum",
    options: currentStatusFilterOptions.value.map(o => ({
        label: o.label,
        value: o.value,
        dotColor: o.iconColor || STATUS_DOT_COLOR_MAP[o.label] || "#9ca3af",
    })),
}));

const dateFilterConfig: ColumnFilterConfig = { type: "date" };

const tagsFilterConfig = computed<ColumnFilterConfig>(() => ({
    type: "enum",
    options: (dynamicTagOptions.value.length ? dynamicTagOptions.value : baseTagOptions.value).map(t => ({
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
            label: m.name || m.id,
            value: m.name || m.id,
            avatarUrl: getMemberAvatarUrl(m.name || ""),
            avatarLabel: getAvatarLabel(m.name || m.id || ""),
            avatarBg: getAvatarBg(m.name || m.id || ""),
        })),
    ],
    sortLabels: ["A → Z", "Z → A"] as [string, string],
}));

const collaboratorsFilterConfig = computed<ColumnFilterConfig>(() => ({
    type: "enum",
    options: memberOptions.value.map(m => ({
        label: m.name || m.id,
        value: m.name || m.id,
        avatarUrl: getMemberAvatarUrl(m.name || ""),
        avatarLabel: getAvatarLabel(m.name || m.id || ""),
        avatarBg: getAvatarBg(m.name || m.id || ""),
    })),
    sortLabels: ["A → Z", "Z → A"] as [string, string],
}));

const iterationFilterConfig = computed<ColumnFilterConfig>(() => ({
    type: "enum",
    options: dynamicIterationOptions.value.map(o => ({ label: o.name, value: o.name })),
}));

const versionFilterConfig = computed<ColumnFilterConfig>(() => ({
    type: "enum",
    options: dynamicVersionOptions.value.map(o => ({ label: o.name, value: o.name })),
}));

const PRIORITY_DOT_COLOR_MAP: Record<string, string> = {
    "紧急": "#ef4444",
    "高": "#f59e0b",
    "中": "#3b82f6",
    "低": "#10b981",
    "无优先级": "#9ca3af",
};

const priorityFilterConfig = computed<ColumnFilterConfig>(() => ({
    type: "enum",
    options: priorityOptions.map(o => ({
        label: o.label,
        value: o.value,
        dotColor: PRIORITY_DOT_COLOR_MAP[o.label] || "#9ca3af",
    })),
    sortLabels: ["低 → 紧急", "紧急 → 低"] as [string, string],
}));

const creatorFilterConfig = computed<ColumnFilterConfig>(() => ({
    type: "enum",
    options: memberOptions.value.map(m => ({
        label: m.name || m.id,
        value: m.name || m.id,
        avatarUrl: getMemberAvatarUrl(m.name || ""),
        avatarLabel: getAvatarLabel(m.name || m.id || ""),
        avatarBg: getAvatarBg(m.name || m.id || ""),
    })),
    sortLabels: ["A → Z", "Z → A"] as [string, string],
}));

const TYPE_DOT_COLOR_MAP: Record<string, string> = {
    "需求": "#3b82f6",
    "任务": "#10b981",
    "缺陷": "#ef4444",
};

const typeFilterConfig = computed<ColumnFilterConfig>(() => ({
    type: "enum",
    options: (["需求", "任务", "缺陷"] as const).map(t => ({
        label: t,
        value: t,
        dotColor: TYPE_DOT_COLOR_MAP[t],
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

const {
    handleExportCsv,
    handleExportExcel,
    handleExportJson,
} = useWorkItemExport({ selectedRows, itemRowsById });

const priorityModel = reactive<Record<string, Priority>>({});
const tagsModel = reactive<Record<string, string[]>>({});
const apiTagDefinitions = ref<Array<{ id: string; name: string; color: string }>>([]);
const baseTagOptions = computed(() => apiTagDefinitions.value.map(t => t.name));
const dynamicTagOptions = ref<string[]>([]);

const loadTagDefinitions = async () => {
    try {
        const res: any = await getVortflowTags();
        apiTagDefinitions.value = (res?.items || []).map((t: any) => ({
            id: t.id,
            name: t.name,
            color: t.color,
        }));
    } catch {
        apiTagDefinitions.value = [];
    }
};
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

const getActiveProjectId = (): string => {
    return props.projectId || vortFlowStore.selectedProjectId || "";
};

const getRepoNameById = (repoId?: string): string => {
    if (!repoId) return "";
    return apiRepos.value.find((item) => item.id === repoId)?.name || "";
};

const getBranchOptions = (repoId?: string) => {
    if (!repoId) return [];
    return branchOptionsMap[repoId] || [];
};

const loadRepoOptions = async () => {
    if (!props.useApi) return;
    const projectId = getActiveProjectId();
    if (!projectId) {
        apiRepos.value = [];
        return;
    }
    try {
        const res: any = await getVortgitRepos({
            project_id: projectId,
            page: 1,
            page_size: 100,
        });
        apiRepos.value = ((res?.items || []) as any[])
            .map((item) => ({
                id: String(item.id || ""),
                name: String(item.name || item.full_name || item.id || ""),
            }))
            .filter((item) => item.id && item.name);
    } catch {
        apiRepos.value = [];
    }
};

const loadIterationOptions = async () => {
    if (!props.useApi) return;
    try {
        const res: any = await getVortflowIterations({ page_size: 200 });
        apiIterations.value = ((res?.items || []) as any[])
            .map((i: any) => ({ id: String(i.id || ""), name: String(i.name || "") }))
            .filter((i) => i.id && i.name);
    } catch {
        apiIterations.value = [];
    }
};

const loadBranchOptions = async (repoId?: string) => {
    if (!props.useApi || !repoId) return;
    if (branchOptionsMap[repoId]?.length) return;
    branchLoadingMap[repoId] = true;
    try {
        const res: any = await getVortgitRepoBranches(repoId);
        branchOptionsMap[repoId] = ((res?.items || []) as any[])
            .map((item) => ({ name: String(item.name || "") }))
            .filter((item) => item.name);
    } catch {
        branchOptionsMap[repoId] = [];
    } finally {
        branchLoadingMap[repoId] = false;
    }
};

const collectTagOptions = (rows: RowItem[]) => {
    const set = new Set<string>(baseTagOptions.value);
    for (const row of rows) {
        for (const tag of row.tags || []) {
            if (tag) set.add(tag);
        }
    }
    dynamicTagOptions.value = [...set];
};

const dynamicIterationOptions = ref<Array<{ id: string; name: string }>>([]);
const dynamicVersionOptions = ref<Array<{ id: string; name: string }>>([]);

const collectEnumOptions = (rows: RowItem[]) => {
    const iterMap = new Map<string, string>();
    const verMap = new Map<string, string>();
    for (const row of rows) {
        if (row.iterationId && row.iteration) iterMap.set(row.iterationId, row.iteration);
        if (row.versionId && row.version) verMap.set(row.versionId, row.version);
    }
    dynamicIterationOptions.value = [...iterMap.entries()].map(([id, name]) => ({ id, name }));
    dynamicVersionOptions.value = [...verMap.entries()].map(([id, name]) => ({ id, name }));
};

const detailCurrentUser = "当前用户";
const formatFileSize = (size: number): string => {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

const {
    columnSettingsOpen,
    columnSettings,
    columns,
    columnSettingsForDialog,
    loadColumnSettingsFromStore,
    handleColumnSettingsSave,
    handleColumnWidthChange,
    applyOrderedColumnSettings,
} = useWorkItemColumns({ workItemType: props.type || "" });

const {
    viewDirty,
    isSystemView,
    currentCustomView,
    saveViewDialogOpen,
    saveViewDropdownOpen,
    saveViewWrapperRef,
    currentViewStateForCreate,
    resetViewBaseline,
    collectCurrentViewState,
    handleUpdateCurrentView,
    handleSaveAsNew,
    handleSaveAsNewView,
} = useWorkItemViewState({
    workItemType: props.type || "",
    currentViewId,
    keyword,
    owner,
    status,
    columnFilters,
    columnSortField,
    columnSortOrder,
    columnSettings,
    applyOrderedColumnSettings,
});

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
        project_id?: string | null;
        actual_hours?: number;
        start_at?: string;
        end_at?: string;
        repo_id?: string | null;
        branch?: string;
        progress?: number;
        attachments?: { name: string; url: string; size: number }[];
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
            assignee_id: patch.assignee_id === undefined ? undefined : (patch.assignee_id || undefined),
            tags: patch.tags,
            collaborators: patch.collaborators,
            deadline: patch.deadline,
            pm_id: patch.pm_id,
            project_id: patch.project_id,
            start_at: patch.start_at,
            end_at: patch.end_at,
            repo_id: patch.repo_id,
            branch: patch.branch,
            progress: patch.progress,
            attachments: patch.attachments,
        });
        record.updatedAt = formatCnTime(new Date());
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
            actual_hours: patch.actual_hours,
            start_at: patch.start_at,
            end_at: patch.end_at,
            repo_id: patch.repo_id,
            branch: patch.branch,
            project_id: patch.project_id,
            progress: patch.progress,
            attachments: patch.attachments,
        });
        record.updatedAt = formatCnTime(new Date());
        return;
    }
    await updateVortflowBug(id, {
        title: patch.title,
        description: patch.description,
        severity: patch.severity,
        state: patch.state,
        assignee_id: patch.assignee_id === undefined ? undefined : (patch.assignee_id || undefined),
        estimate_hours: patch.estimate_hours,
        actual_hours: patch.actual_hours,
        tags: patch.tags,
        collaborators: patch.collaborators,
        deadline: patch.deadline,
        start_at: patch.start_at,
        end_at: patch.end_at,
        repo_id: patch.repo_id,
        branch: patch.branch,
        project_id: patch.project_id,
        attachments: patch.attachments,
    });
    record.updatedAt = formatCnTime(new Date());
};

const syncRecordStatusToApi = async (record: RowItem, displayStatus: Status) => {
    if (!props.useApi) return;
    const targetStates = getBackendStatesByDisplayStatus(record.type, displayStatus) || [];
    if (!targetStates.length) {
        throw new Error("当前状态不支持同步到后端");
    }
    await syncRecordUpdateToApi(record, { state: targetStates[0] });
};

const {
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
} = useWorkItemInlineEdit({
    useApi: computed(() => props.useApi),
    syncRecordUpdateToApi,
    syncRecordStatusToApi,
    getMemberIdByName,
    mapBackendPriority,
    toBackendPriorityLevel,
    toTaskEstimateHours,
    getBackendStatesByDisplayStatus: (typeValue, statusValue) =>
        getBackendStatesByDisplayStatus(typeValue as WorkItemType, statusValue) || [],
    dynamicTagOptions,
    baseTagOptions,
    tagDefinitions: apiTagDefinitions,
    priorityModel,
    tagsModel,
    collaboratorsModel,
    planTimeModel,
    normalizeDateValue,
});

const openRepoPicker = async (record: RowItem, event: Event) => {
    const shouldOpen = isCellBackgroundClick(event);
    openCellPickerOnBackgroundClick(record, event, repoPickerOpenMap);
    if (shouldOpen) {
        await loadRepoOptions();
    }
};

const selectRowEstimateHours = async (record: RowItem, value?: number | null) => {
    const key = getInteractiveCellKey(record);
    const prevEstimate = record.estimateHours;
    const prevRemain = record.remainHours;
    const nextValue = value == null || value === undefined ? undefined : Number(value);
    record.estimateHours = nextValue;
    if (record.loggedHours != null && nextValue != null) {
        record.remainHours = Math.max(0, Number(nextValue) - Number(record.loggedHours || 0));
    } else if (nextValue == null) {
        record.remainHours = undefined;
    }
    estimateEditingFor.value = null;
    try {
        await syncRecordUpdateToApi(record, { estimate_hours: nextValue });
    } catch (error: any) {
        record.estimateHours = prevEstimate;
        record.remainHours = prevRemain;
        estimateDraftMap[key] = prevEstimate == null ? null : Number(prevEstimate);
        message.error(error?.message || "预估工时同步失败");
    }
};

const openEstimateEditor = (record: RowItem) => {
    const key = getInteractiveCellKey(record);
    estimateDraftMap[key] = record.estimateHours == null || record.estimateHours === ""
        ? null
        : Number(record.estimateHours);
    estimateEditingFor.value = key;
    nextTick(() => estimateInputRef.value?.focus());
};

const isProgressReadonly = (record: RowItem) => {
    if ((record.childrenCount || 0) > 0) return true;
    if (record.type === "需求" && (record.taskCount || 0) > 0) return true;
    return false;
};

const selectRowProgress = async (record: RowItem, value?: number | null) => {
    const key = getInteractiveCellKey(record);
    const prevProgress = record.progress;
    const nextValue = value == null ? 0 : Math.max(0, Math.min(100, Math.round(Number(value))));
    record.progress = nextValue;
    progressEditingFor.value = null;
    try {
        await syncRecordUpdateToApi(record, { progress: nextValue });
    } catch (error: any) {
        record.progress = prevProgress;
        progressDraftMap[key] = prevProgress ?? 0;
        message.error(error?.message || "进度同步失败");
    }
};

const openProgressEditor = (record: RowItem) => {
    if (isProgressReadonly(record)) return;
    const key = getInteractiveCellKey(record);
    progressDraftMap[key] = record.progress ?? 0;
    progressEditingFor.value = key;
    nextTick(() => progressInputRef.value?.focus());
};

const selectRowProject = async (record: RowItem, projectId?: string) => {
    const key = getInteractiveCellKey(record);
    const prevProjectId = record.projectId || "";
    const prevProjectName = record.projectName || "";
    const nextProjectId = String(projectId || "");
    const nextProjectName = apiProjects.value.find(p => p.id === nextProjectId)?.name || "";
    record.projectId = nextProjectId;
    record.projectName = nextProjectName;
    projectPickerOpenMap[key] = false;
    try {
        await syncRecordUpdateToApi(record, { project_id: nextProjectId || null });
    } catch (error: any) {
        record.projectId = prevProjectId;
        record.projectName = prevProjectName;
        message.error(error?.message || "项目同步失败");
    }
};

const selectRowIteration = async (record: RowItem, iterationId?: string) => {
    const key = getInteractiveCellKey(record);
    const itemId = getRecordBackendId(record);
    if (!itemId) return;
    const prevIterationId = record.iterationId || "";
    const prevIteration = record.iteration || "";
    const nextIterationId = String(iterationId || "");
    const nextIteration = apiIterations.value.find(i => i.id === nextIterationId)?.name || "";
    record.iterationId = nextIterationId;
    record.iteration = nextIteration;
    record._prevIteration = nextIterationId;
    iterationPickerOpenMap[key] = false;
    try {
        if (prevIterationId && prevIterationId !== nextIterationId) {
            if (record.type === "需求") await removeVortflowIterationStory(prevIterationId, itemId);
            else if (record.type === "任务") await removeVortflowIterationTask(prevIterationId, itemId);
            else if (record.type === "缺陷") await removeVortflowIterationBug(prevIterationId, itemId);
        }
        if (nextIterationId && nextIterationId !== prevIterationId) {
            if (record.type === "需求") await addVortflowIterationStory(nextIterationId, { story_id: itemId });
            else if (record.type === "任务") await addVortflowIterationTask(nextIterationId, { task_id: itemId });
            else if (record.type === "缺陷") await addVortflowIterationBug(nextIterationId, { bug_id: itemId });
        }
    } catch (error: any) {
        record.iterationId = prevIterationId;
        record.iteration = prevIteration;
        record._prevIteration = prevIterationId;
        message.error(error?.message || "迭代同步失败");
    }
};

const selectRowRepo = async (record: RowItem, repoId?: string) => {
    const prevRepoId = record.repoId || "";
    const prevRepo = record.repo || "";
    const prevBranch = record.branch || "";
    const nextRepoId = String(repoId || "");
    const nextRepo = getRepoNameById(nextRepoId);
    record.repoId = nextRepoId;
    record.repo = nextRepo;
    if (prevRepoId !== nextRepoId) {
        record.branch = "";
    }
    repoPickerOpenMap[getInteractiveCellKey(record)] = false;
    try {
        await syncRecordUpdateToApi(record, {
            repo_id: nextRepoId || null,
            branch: prevRepoId !== nextRepoId ? "" : record.branch || "",
        });
        if (nextRepoId) {
            await loadBranchOptions(nextRepoId);
        }
    } catch (error: any) {
        record.repoId = prevRepoId;
        record.repo = prevRepo;
        record.branch = prevBranch;
        message.error(error?.message || "关联仓库同步失败");
    }
};

const openBranchPicker = async (record: RowItem, event: Event) => {
    if (!record.repoId) {
        message.warning("请先选择关联仓库");
        return;
    }
    const shouldOpen = isCellBackgroundClick(event);
    openCellPickerOnBackgroundClick(record, event, branchPickerOpenMap);
    if (shouldOpen) {
        await loadBranchOptions(record.repoId);
    }
};

const selectRowBranch = async (record: RowItem, branch?: string) => {
    const prevBranch = record.branch || "";
    const nextBranch = String(branch || "");
    record.branch = nextBranch;
    branchPickerOpenMap[getInteractiveCellKey(record)] = false;
    try {
        await syncRecordUpdateToApi(record, { branch: nextBranch });
    } catch (error: any) {
        record.branch = prevBranch;
        message.error(error?.message || "关联分支同步失败");
    }
};

const selectRowDateField = async (record: RowItem, field: "startAt" | "endAt", value?: string) => {
    const prev = record[field] || "";
    const next = normalizeDateValue(value || "");
    record[field] = next;
    const cellKey = getInteractiveCellKey(record);
    if (field === "startAt") startAtPickerOpenMap[cellKey] = false;
    else endAtPickerOpenMap[cellKey] = false;
    try {
        await syncRecordUpdateToApi(record, {
            [field === "startAt" ? "start_at" : "end_at"]: next || "",
        });
    } catch (error: any) {
        record[field] = prev;
        message.error(error?.message || `${field === "startAt" ? "实际开始时间" : "实际结束时间"}同步失败`);
    }
};

const {
    mapBackendItemToRow,
    findItemRowById,
    findItemRowByIdentifier,
    loadItemById,
    loadChildItems,
    request,
    postProcessTableRows,
    prependPinnedRow,
} = useWorkItemDataSource({
    useApi: computed(() => props.useApi),
    propType: props.type || "",
    propProjectId: computed(() => props.projectId || ""),
    propIterationId: computed(() => props.iterationId || ""),
    propViewFilters: computed(() => ({
        ...builtInViewFilters.value,
        ...(props.viewFilters || {}),
    })),
    type,
    owner,
    status,
    columnFilters,
    columnSortField,
    columnSortOrder,
    totalCount,
    apiProjects,
    pinnedRowsByType,
    expandedItemIds,
    expandingItemIds,
    itemRowsById,
    itemChildrenMap,
    getMemberIdByName,
    getMemberNameById,
    loadMemberOptions,
    mapBackendStateToStatus,
    mapBackendPriority,
    getBackendStatesByDisplayStatus,
    formatCnTime,
    formatDate,
    collectTagOptions,
    collectEnumOptions,
});

const tableRef = ref<any>(null);
const refreshKey = ref(0);

const queryParams = computed(() => ({
    keyword: keyword.value,
    owner: owner.value,
    type: props.type || type.value,
    status: status.value,
    _rk: refreshKey.value,
}));

const refreshTable = () => {
    refreshKey.value++;
};

const onReset = () => {
    keyword.value = "";
    owner.value = [];
    type.value = props.type ?? "";
    status.value = [];
};

watch(() => props.projectId, () => {
    loadRepoOptions();
    tableRef.value?.refresh?.();
});

watch(() => props.viewFilters, () => {
    tableRef.value?.refresh?.();
}, { deep: true });

watch(builtInViewFilters, () => {
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
    tableRef.value?.clearSelection?.();
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
    refreshTable();
};

const resetCreateBugForm = () => {
    Object.assign(createBugForm, createInitialBugForm());
    createBugAttachments.value = [];
};

const handleCreateBug = async () => {
    await loadApiMetadata(props.type === "任务");
    createBugDrawerMode.value = "create";
    createParentItemId.value = "";
    createProjectId.value = props.projectId || "";
    resetCreateBugForm();
    const workItemType = (props.type || "缺陷") as WorkItemType;
    const draft = loadDraft(workItemType, "");
    createDraftData.value = draft;
    createBugForm.type = props.type ?? createBugForm.type;
    router.replace({ query: { ...route.query, action: "create", parentId: undefined } });
};

const handleCreateChild = async (record: RowItem) => {
    if ((record.type !== "需求" && record.type !== "任务") || !record.backendId) return;
    await loadApiMetadata(record.type === "任务");
    createBugDrawerMode.value = "create";
    createParentItemId.value = String(record.backendId);
    createProjectId.value = record.projectId || "";
    createDraftData.value = null;
    resetCreateBugForm();
    router.replace({ query: { ...route.query, action: "create", parentId: String(record.backendId), id: undefined } });
};

const handleCancelCreateBug = () => {
    createBugDrawerOpen.value = false;
    createParentItemId.value = "";
    createProjectId.value = "";
};

const handleDetailDelete = async () => {
    const rec = detailCurrentRecord.value;
    if (!rec) return;
    try {
        await deleteOne(rec);
        message.success("删除成功");
        handleCancelCreateBug();
        tableRef.value?.refresh?.();
    } catch {
        message.error("删除失败");
    }
};

const handleCancelCreateWorkItem = () => {
    if (createWorkItemRef.value) {
        createWorkItemRef.value.cancel();
        return;
    }
    handleCancelCreateBug();
};

const handleCopyWorkItem = async () => {
    const rec = detailCurrentRecord.value;
    if (!rec?.backendId || !props.useApi) return;
    try {
        const type = rec.type as WorkItemType;
        if (type === "需求") await copyVortflowStory(rec.backendId);
        else if (type === "任务") await copyVortflowTask(rec.backendId);
        else await copyVortflowBug(rec.backendId);
        message.success("复制成功");
        createBugDrawerOpen.value = false;
        tableRef.value?.refresh?.();
    } catch {
        message.error("复制失败");
    }
};

const _TYPE_TO_BACKEND: Record<string, string> = { "需求": "story", "任务": "task", "缺陷": "bug" };

const handleDetailUpdate = async (data: Partial<RowItem>) => {
    if (!detailCurrentRecord.value) return;
    const rec = detailCurrentRecord.value;

    if (data.type && props.useApi && rec.backendId) {
        const fromBackend = _TYPE_TO_BACKEND[rec.type];
        const toBackend = _TYPE_TO_BACKEND[data.type];
        if (fromBackend && toBackend && fromBackend !== toBackend) {
            try {
                const res: any = await convertWorkItem({ from_type: fromBackend, id: rec.backendId, to_type: toBackend });
                if (res?.error) { message.error(res.error); return; }
                message.success(res?.message || "类型转换成功");
                handleCancelCreateBug();
                tableRef.value?.refresh?.();
            } catch {
                message.error("类型转换失败");
            }
            return;
        }
    }

    Object.assign(rec, data);

    if (!props.useApi || !rec.backendId) return;

    if (data.title !== undefined) {
        await syncRecordUpdateToApi(rec, { title: data.title });
    }
    if (data.status !== undefined) {
        await syncRecordStatusToApi(rec, data.status);
    }
    if (data.owner !== undefined || data.collaborators !== undefined) {
        const ownerId = data.owner ? getMemberIdByName(data.owner) || data.owner : undefined;
        const collabIds = data.collaborators?.map(n => getMemberIdByName(n) || n);
        const patch: any = {};
        if (ownerId !== undefined) patch.assignee_id = ownerId || null;
        if (collabIds) patch.collaborators = collabIds;
        await syncRecordUpdateToApi(rec, patch);
    }
    if (data.description !== undefined) {
        await syncRecordUpdateToApi(rec, { description: data.description });
    }
    if (data.planTime !== undefined) {
        const pt = data.planTime;
        const deadline = (pt && pt[1]) ? pt[1] : undefined;
        await syncRecordUpdateToApi(rec, { deadline: deadline || undefined });
    }
    if (data.progress !== undefined) {
        await syncRecordUpdateToApi(rec, { progress: data.progress });
    }
    if (data.estimateHours !== undefined) {
        const value = data.estimateHours === "" || data.estimateHours == null
            ? undefined
            : Number(data.estimateHours);
        await syncRecordUpdateToApi(rec, { estimate_hours: value });
    }
    if (data.startAt !== undefined) {
        await syncRecordUpdateToApi(rec, { start_at: data.startAt || "" });
    }
    if (data.endAt !== undefined) {
        await syncRecordUpdateToApi(rec, { end_at: data.endAt || "" });
    }
    if (data.repoId !== undefined || data.branch !== undefined) {
        await syncRecordUpdateToApi(rec, {
            repo_id: (data.repoId ?? rec.repoId ?? "") || null,
            branch: data.branch ?? rec.branch ?? "",
        });
    }
    if (data.projectName !== undefined && data.projectId !== undefined) {
        const itemId = getRecordBackendId(rec);
        if (itemId) {
            await syncRecordUpdateToApi(rec, { project_id: data.projectId || null });
        }
    }
    if (data.iterationId !== undefined || data.iteration !== undefined) {
        const itemId = getRecordBackendId(rec);
        if (itemId) {
            const prevIter = rec._prevIteration || "";
            const nextIter = data.iterationId ?? rec.iterationId ?? "";
            if (prevIter && prevIter !== nextIter) {
                if (rec.type === "需求") await removeVortflowIterationStory(prevIter, itemId).catch(() => {});
                else if (rec.type === "任务") await removeVortflowIterationTask(prevIter, itemId).catch(() => {});
                else if (rec.type === "缺陷") await removeVortflowIterationBug(prevIter, itemId).catch(() => {});
            }
            if (nextIter && nextIter !== prevIter) {
                if (rec.type === "需求") await addVortflowIterationStory(nextIter, { story_id: itemId }).catch(() => {});
                else if (rec.type === "任务") await addVortflowIterationTask(nextIter, { task_id: itemId }).catch(() => {});
                else if (rec.type === "缺陷") await addVortflowIterationBug(nextIter, { bug_id: itemId }).catch(() => {});
            }
            rec._prevIteration = nextIter;
        }
    }
    if (data.versionId !== undefined || data.version !== undefined) {
        const itemId = getRecordBackendId(rec);
        if (itemId) {
            const prevVer = rec._prevVersion || "";
            const nextVer = data.versionId ?? rec.versionId ?? "";
            if (prevVer && prevVer !== nextVer) {
                if (rec.type === "需求") await removeVortflowVersionStory(prevVer, itemId).catch(() => {});
                else if (rec.type === "缺陷") await removeVortflowVersionBug(prevVer, itemId).catch(() => {});
            }
            if (nextVer && nextVer !== prevVer) {
                if (rec.type === "需求") await addVortflowVersionStory(nextVer, { story_id: itemId }).catch(() => {});
                else if (rec.type === "缺陷") await addVortflowVersionBug(nextVer, { bug_id: itemId }).catch(() => {});
            }
            rec._prevVersion = nextVer;
        }
    }
    if (data.attachments !== undefined) {
        await syncRecordUpdateToApi(rec, { attachments: data.attachments });
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
                    description: formData.description || getDescriptionTemplate("需求"),
                    priority: formData.priority === "urgent" ? 1 : formData.priority === "high" ? 2 : formData.priority === "medium" ? 3 : 4,
                    parent_id: formData.parentId || undefined,
                    tags: [...formData.tags],
                    collaborators: [...formData.collaborators],
                    attachments: [...(formData.attachments || [])],
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
                    project_id: formData.projectId || createProjectId.value || resolveCreateProjectId() || undefined,
                    story_id: formData.storyId || undefined,
                    parent_id: formData.parentId || undefined,
                    title,
                    description: formData.description || getDescriptionTemplate("任务"),
                    task_type: "develop",
                    assignee_id: ownerId,
                    tags: [...formData.tags],
                    collaborators: [...formData.collaborators],
                    attachments: [...(formData.attachments || [])],
                    deadline: formData.planTime?.[1] || undefined,
                });
            } else {
                createdItem = await createVortflowBug({
                    project_id: formData.projectId || createProjectId.value || resolveCreateProjectId() || undefined,
                    story_id: formData.storyId || undefined,
                    title,
                    description: formData.description || getDescriptionTemplate("缺陷"),
                    severity: formData.priority === "urgent" ? 1 : formData.priority === "high" ? 2 : formData.priority === "medium" ? 3 : 4,
                    assignee_id: ownerId,
                    tags: [...formData.tags],
                    collaborators: [...formData.collaborators],
                    attachments: [...(formData.attachments || [])],
                    deadline: formData.planTime?.[1] || undefined,
                });
            }
            if (createdItem) {
                const createdId = String(createdItem.id || "");
                // Link to iteration if specified
                if (createdId && formData.iteration && formData.iteration !== "__unplanned__") {
                    try {
                        if (type === "需求") {
                            await addVortflowIterationStory(formData.iteration, { story_id: createdId });
                        } else if (type === "任务") {
                            await addVortflowIterationTask(formData.iteration, { task_id: createdId });
                        } else if (type === "缺陷") {
                            await addVortflowIterationBug(formData.iteration, { bug_id: createdId });
                        }
                    } catch { /* iteration link failed silently */ }
                }
                if (createdId && formData.version) {
                    try {
                        if (type === "需求") {
                            await addVortflowVersionStory(formData.version, { story_id: createdId });
                        } else if (type === "缺陷") {
                            await addVortflowVersionBug(formData.version, { bug_id: createdId });
                        }
                    } catch { /* version link failed silently */ }
                }
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
            clearDraft((props.type || formData.type || "缺陷") as WorkItemType);
            createDraftData.value = null;
            if (keepCreating) {
                createWorkItemRef.value?.reset();
            } else {
                createWorkItemRef.value?.reset();
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
const detailComponentRef = ref<any>(null);

const handleOpenBugDetail = async (record: RowItem) => {
    detailSelectedWorkNo.value = record.workNo;
    detailRecordSnapshot.value = record;
    detailActiveTab.value = "detail";
    detailBottomTab.value = "comments";
    detailCommentDraft.value = "";
    const cachedDraft = detailDescDraftCache[record.workNo];
    if (cachedDraft !== undefined) {
        detailDescEditing.value = true;
        detailDescDraft.value = cachedDraft;
        delete detailDescDraftCache[record.workNo];
    } else {
        detailDescEditing.value = false;
        detailDescDraft.value = "";
    }
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

    const typeToTab: Record<string, string> = { "需求": "story", "任务": "task", "缺陷": "bug" };
    router.replace({ query: { ...route.query, action: "detail", id: record.backendId || record.workNo, tab: typeToTab[record.type] || typeToTab[props.type] } });
};

const handleOpenRelated = async (partial: any) => {
    if (partial?.workNo) {
        handleOpenBugDetail(partial as RowItem);
        return;
    }
    const id = partial?.backendId || partial?.id;
    const itemType = partial?.type as WorkItemType;
    if (!id || !itemType) return;
    const full = await loadItemById(id, itemType);
    if (full) handleOpenBugDetail(full);
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
    if (detailSelectedWorkNo.value) delete detailDescDraftCache[detailSelectedWorkNo.value];
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
    if (detailSelectedWorkNo.value) delete detailDescDraftCache[detailSelectedWorkNo.value];
    appendDetailLog("更新描述");
    message.success("描述已保存");
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
    const queryProject = route.query.project as string;
    if (queryProject && queryProject !== vortFlowStore.selectedProjectId) {
        vortFlowStore.setProjectId(queryProject);
    }

    const hasCachedColumns = !!vortFlowStore.getColumnSettings(props.type || "");
    if (hasCachedColumns) {
        columnSettings.value = loadColumnSettingsFromStore();
        resetViewBaseline();
    }

    await loadMemberOptions();
    await Promise.all([
        loadApiMetadata(false),
        loadRepoOptions(),
        loadIterationOptions(),
        loadTagDefinitions(),
        loadStatusOptions(),
        vortFlowStore.loadColumnSettings(props.type || ""),
        vortFlowStore.loadViews(props.type || ""),
        getVortflowDescriptionTemplates().then((res: any) => {
            if (res?.items) remoteTemplates.value = res.items;
        }).catch(() => {}),
    ]);
    columnSettings.value = loadColumnSettingsFromStore();
    resetViewBaseline();
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
        const urlTab = route.query.tab as string;
        const tabTypeMap: Record<string, WorkItemType> = { story: "需求", task: "任务", bug: "缺陷" };
        const tabRouteMap: Record<string, string> = { story: "/vortflow/stories", task: "/vortflow/tasks", bug: "/vortflow/bugs" };
        const urlType = tabTypeMap[urlTab];
        if (urlType && urlType !== props.type) {
            const targetPath = tabRouteMap[urlTab];
            if (targetPath) {
                router.replace({ path: targetPath, query: { action: "detail", id, tab: urlTab } });
            }
            return;
        }

        let record = findItemRowByIdentifier(id) || await loadItemById(id, props.type);
        if (!record && !urlType) {
            const otherTypes = (["需求", "任务", "缺陷"] as WorkItemType[]).filter(t => t !== props.type);
            for (const t of otherTypes) {
                record = await loadItemById(id, t);
                if (record) break;
            }
        }
        if (record) {
            handleOpenBugDetail(record);
        } else {
            router.replace({ query: { ...route.query, action: undefined, id: undefined, parentId: undefined, tab: undefined } });
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
            <template v-if="currentWorkItemType && viewDirty" #after-filters>
                <div class="save-view-wrapper" ref="saveViewWrapperRef">
                    <button
                        type="button"
                        class="save-view-btn"
                        @click="saveViewDropdownOpen = !saveViewDropdownOpen"
                    >
                        保存视图
                        <svg
                            class="save-view-arrow"
                            :class="{ open: saveViewDropdownOpen }"
                            width="12" height="12" viewBox="0 0 12 12" fill="none"
                        >
                            <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </button>
                    <Transition name="dropdown">
                        <div v-if="saveViewDropdownOpen" class="save-view-dropdown">
                            <button
                                type="button"
                                class="save-view-option"
                                :disabled="isSystemView"
                                @click="handleUpdateCurrentView"
                            >
                                更新当前视图
                            </button>
                            <button
                                type="button"
                                class="save-view-option"
                                @click="handleSaveAsNew"
                            >
                                存为新视图
                            </button>
                        </div>
                    </Transition>
                </div>
            </template>
            <template #extra-actions>
                <AiAssistButton
                    :prompt="`我想在项目「${currentProjectName}」中创建一个${resolveActiveType()}，请引导我完成。`"
                />
                <MoreActionsDropdown
                    @import="importDialogOpen = true"
                    @import-records="importRecordDialogOpen = true"
                    @export-csv="handleExportCsv"
                    @export-excel="handleExportExcel"
                    @export-json="handleExportJson"
                    @batch-ops="batchPropertyEditorOpen = true"
                />
                <vort-tooltip title="表头显示设置">
                    <button type="button" class="column-settings-btn" @click="columnSettingsOpen = true">
                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
                    </button>
                </vort-tooltip>
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
            <ProTable
                ref="tableRef"
                :columns="columns"
                :request="request"
                :immediate="false"
                :post-process-data="postProcessTableRows"
                :params="queryParams"
                :row-key="rowKeyGetter"
                :row-selection="rowSelection"
                :pagination="{ pageSize: vortFlowStore.tablePageSize, showSizeChanger: true, showQuickJumper: true, pageSizeOptions: [10, 20, 50] }"
                @pagination-change="({ pageSize: ps }) => { vortFlowStore.tablePageSize = ps; }"
                :toolbar="false"
                bordered
                @column-width-change="handleColumnWidthChange"
            >
                <template #header-status="{ column }">
                    <ColumnFilterPopover field="status" :title="column.title || ''" :config="statusFilterConfig" :sort-order="columnSortField === 'status' ? columnSortOrder : null" :filter-value="columnFilters['status']" @sort="(o) => handleColumnSort('status', o)" @filter="(v) => handleColumnFilter('status', v)">{{ column.title }}</ColumnFilterPopover>
                </template>

                <template #header-priority="{ column }">
                    <ColumnFilterPopover field="priority" :title="column.title || ''" :config="priorityFilterConfig" :sort-order="columnSortField === 'priority' ? columnSortOrder : null" :filter-value="columnFilters['priority']" @sort="(o) => handleColumnSort('priority', o)" @filter="(v) => handleColumnFilter('priority', v)">{{ column.title }}</ColumnFilterPopover>
                </template>

                <template #header-createdAt="{ column }">
                    <ColumnFilterPopover field="createdAt" :title="column.title || ''" :config="dateFilterConfig" :sort-order="columnSortField === 'createdAt' ? columnSortOrder : null" :filter-value="columnFilters['createdAt']" @sort="(o) => handleColumnSort('createdAt', o)" @filter="(v) => handleColumnFilter('createdAt', v)">{{ column.title }}</ColumnFilterPopover>
                </template>

                <template #header-tags="{ column }">
                    <ColumnFilterPopover field="tags" :title="column.title || ''" :config="tagsFilterConfig" :sort-order="columnSortField === 'tags' ? columnSortOrder : null" :filter-value="columnFilters['tags']" @sort="(o) => handleColumnSort('tags', o)" @filter="(v) => handleColumnFilter('tags', v)">{{ column.title }}</ColumnFilterPopover>
                </template>

                <template #header-planTime="{ column }">
                    <ColumnFilterPopover field="planTime" :title="column.title || ''" :config="dateFilterConfig" :sort-order="columnSortField === 'planTime' ? columnSortOrder : null" :filter-value="columnFilters['planTime']" @sort="(o) => handleColumnSort('planTime', o)" @filter="(v) => handleColumnFilter('planTime', v)">{{ column.title }}</ColumnFilterPopover>
                </template>

                <template #header-owner="{ column }">
                    <ColumnFilterPopover field="owner" :title="column.title || ''" :config="ownerFilterConfig" :sort-order="columnSortField === 'owner' ? columnSortOrder : null" :filter-value="columnFilters['owner']" @sort="(o) => handleColumnSort('owner', o)" @filter="(v) => handleColumnFilter('owner', v)">{{ column.title }}</ColumnFilterPopover>
                </template>

                <template #header-collaborators="{ column }">
                    <ColumnFilterPopover field="collaborators" :title="column.title || ''" :config="collaboratorsFilterConfig" :sort-order="columnSortField === 'collaborators' ? columnSortOrder : null" :filter-value="columnFilters['collaborators']" @sort="(o) => handleColumnSort('collaborators', o)" @filter="(v) => handleColumnFilter('collaborators', v)">{{ column.title }}</ColumnFilterPopover>
                </template>

                <template #header-updatedAt="{ column }">
                    <ColumnFilterPopover field="updatedAt" :title="column.title || ''" :config="dateFilterConfig" :sort-order="columnSortField === 'updatedAt' ? columnSortOrder : null" :filter-value="columnFilters['updatedAt']" @sort="(o) => handleColumnSort('updatedAt', o)" @filter="(v) => handleColumnFilter('updatedAt', v)">{{ column.title }}</ColumnFilterPopover>
                </template>

                <template #header-iteration="{ column }">
                    <ColumnFilterPopover field="iteration" :title="column.title || ''" :config="iterationFilterConfig" :sort-order="columnSortField === 'iteration' ? columnSortOrder : null" :filter-value="columnFilters['iteration']" @sort="(o) => handleColumnSort('iteration', o)" @filter="(v) => handleColumnFilter('iteration', v)">{{ column.title }}</ColumnFilterPopover>
                </template>

                <template #header-version="{ column }">
                    <ColumnFilterPopover field="version" :title="column.title || ''" :config="versionFilterConfig" :sort-order="columnSortField === 'version' ? columnSortOrder : null" :filter-value="columnFilters['version']" @sort="(o) => handleColumnSort('version', o)" @filter="(v) => handleColumnFilter('version', v)">{{ column.title }}</ColumnFilterPopover>
                </template>

                <template #header-startAt="{ column }">
                    <ColumnFilterPopover field="startAt" :title="column.title || ''" :config="dateFilterConfig" :sort-order="columnSortField === 'startAt' ? columnSortOrder : null" :filter-value="columnFilters['startAt']" @sort="(o) => handleColumnSort('startAt', o)" @filter="(v) => handleColumnFilter('startAt', v)">{{ column.title }}</ColumnFilterPopover>
                </template>

                <template #header-endAt="{ column }">
                    <ColumnFilterPopover field="endAt" :title="column.title || ''" :config="dateFilterConfig" :sort-order="columnSortField === 'endAt' ? columnSortOrder : null" :filter-value="columnFilters['endAt']" @sort="(o) => handleColumnSort('endAt', o)" @filter="(v) => handleColumnFilter('endAt', v)">{{ column.title }}</ColumnFilterPopover>
                </template>

                <template #header-creator="{ column }">
                    <ColumnFilterPopover field="creator" :title="column.title || ''" :config="creatorFilterConfig" :sort-order="columnSortField === 'creator' ? columnSortOrder : null" :filter-value="columnFilters['creator']" @sort="(o) => handleColumnSort('creator', o)" @filter="(v) => handleColumnFilter('creator', v)">{{ column.title }}</ColumnFilterPopover>
                </template>

                <template #header-type="{ column }">
                    <ColumnFilterPopover field="type" :title="column.title || ''" :config="typeFilterConfig" :sort-order="columnSortField === 'type' ? columnSortOrder : null" :filter-value="columnFilters['type']" @sort="(o) => handleColumnSort('type', o)" @filter="(v) => handleColumnFilter('type', v)">{{ column.title }}</ColumnFilterPopover>
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
                                        class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center shrink-0 overflow-hidden relative"
                                        :style="{ backgroundColor: getAvatarBg(getRowOwner(record, text)) }"
                                    >
                                        {{ getAvatarLabel(getRowOwner(record, text)) }}
                                        <img v-if="getMemberAvatarUrl(getRowOwner(record, text))" :src="getMemberAvatarUrl(getRowOwner(record, text))" class="absolute inset-0 w-full h-full object-cover" @error="onAvatarError" />
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
                                            class="-ml-1 first:ml-0 w-6 h-6 rounded-full border border-white text-white text-[11px] flex items-center justify-center overflow-hidden relative"
                                            :style="{ backgroundColor: getAvatarBg(name) }"
                                            :title="name"
                                        >
                                            {{ getAvatarLabel(name) }}
                                            <img v-if="getMemberAvatarUrl(name)" :src="getMemberAvatarUrl(name)" class="absolute inset-0 w-full h-full object-cover" @error="onAvatarError" />
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

                <template #updatedAt="{ text }">
                    <TableCell>
                        <span class="text-sm text-gray-500">{{ text }}</span>
                    </TableCell>
                </template>

                <template #iteration="{ text, record }">
                    <TableCell @click.stop="iterationPickerOpenMap[getInteractiveCellKey(record)] = true">
                        <div class="cell-select-plain text-sm text-gray-700">
                            <vort-select
                                :model-value="record.iterationId || undefined"
                                :open="iterationPickerOpenMap[getInteractiveCellKey(record)]"
                                placeholder="-"
                                allow-clear
                                size="small"
                                :bordered="false"
                                @update:open="iterationPickerOpenMap[getInteractiveCellKey(record)] = $event"
                                @change="(val: any) => selectRowIteration(record, val)"
                            >
                                <vort-select-option v-for="iter in apiIterations" :key="iter.id" :value="iter.id">{{ iter.name }}</vort-select-option>
                            </vort-select>
                        </div>
                    </TableCell>
                </template>

                <template #version="{ text }">
                    <TableCell>
                        <span v-if="text" class="text-sm text-gray-700">{{ text }}</span>
                        <span v-else class="text-sm text-gray-300">-</span>
                    </TableCell>
                </template>

                <template #progress="{ record }">
                    <TableCell @click.stop="openProgressEditor(record)">
                        <template v-if="record.type === '需求' || record.type === '任务'">
                            <div class="progress-cell">
                                <div class="progress-bar">
                                    <div
                                        class="progress-fill"
                                        :style="{ width: (record.progress || 0) + '%' }"
                                    />
                                </div>
                                <template v-if="!isProgressReadonly(record) && progressEditingFor === getInteractiveCellKey(record)">
                                    <vort-input-number
                                        ref="progressInputRef"
                                        v-model="progressDraftMap[getInteractiveCellKey(record)]"
                                        :min="0"
                                        :max="100"
                                        :step="5"
                                        size="small"
                                        style="width:64px"
                                        @click.stop
                                        @blur="selectRowProgress(record, progressDraftMap[getInteractiveCellKey(record)])"
                                        @keyup.enter="selectRowProgress(record, progressDraftMap[getInteractiveCellKey(record)])"
                                    />
                                </template>
                                <span v-else class="progress-text" :class="{ 'cursor-pointer': !isProgressReadonly(record) }">{{ record.progress || 0 }}%</span>
                            </div>
                        </template>
                        <span v-else class="text-sm text-gray-300">-</span>
                    </TableCell>
                </template>

                <template #estimateHours="{ text, record }">
                    <TableCell @click.stop="openEstimateEditor(record)">
                        <div class="min-h-8 flex items-center">
                            <vort-input-number
                                v-if="estimateEditingFor === getInteractiveCellKey(record)"
                                ref="estimateInputRef"
                                v-model="estimateDraftMap[getInteractiveCellKey(record)]"
                                :min="0"
                                :step="0.5"
                                size="small"
                                style="width:88px"
                                @click.stop
                                @blur="selectRowEstimateHours(record, estimateDraftMap[getInteractiveCellKey(record)])"
                                @keyup.enter="selectRowEstimateHours(record, estimateDraftMap[getInteractiveCellKey(record)])"
                            />
                            <span
                                v-else-if="text != null && text !== ''"
                                class="text-sm text-blue-600 cursor-pointer"
                            >
                                {{ text }}h
                            </span>
                            <span v-else class="text-sm text-blue-400 cursor-pointer">-</span>
                        </div>
                    </TableCell>
                </template>


                <template #project="{ text, record }">
                    <TableCell @click.stop="projectPickerOpenMap[getInteractiveCellKey(record)] = true">
                        <vort-select
                            :model-value="record.projectId || undefined"
                            :open="projectPickerOpenMap[getInteractiveCellKey(record)]"
                            placeholder="-"
                            allow-clear
                            size="small"
                            :bordered="false"
                            class="w-full"
                            @update:open="projectPickerOpenMap[getInteractiveCellKey(record)] = $event"
                            @change="(val: string) => selectRowProject(record, val)"
                        >
                            <vort-select-option v-for="p in apiProjects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                        </vort-select>
                    </TableCell>
                </template>

                <template #startAt="{ text, record }">
                    <TableCell @click.stop="startAtPickerOpenMap[getInteractiveCellKey(record)] = true">
                        <div class="relative inline-block min-w-[120px]" @click.stop>
                            <span
                                v-if="!startAtPickerOpenMap[getInteractiveCellKey(record)]"
                                class="text-sm text-blue-600 cursor-pointer"
                            >
                                {{ text || "-" }}
                            </span>
                            <vort-date-picker
                                v-else
                                v-model="record.startAt"
                                v-model:open="startAtPickerOpenMap[getInteractiveCellKey(record)]"
                                value-format="YYYY-MM-DD"
                                format="YYYY-MM-DD"
                                allow-clear
                                size="small"
                                class="w-[128px]"
                                @change="(value: any) => selectRowDateField(record, 'startAt', value || '')"
                            />
                        </div>
                    </TableCell>
                </template>

                <template #endAt="{ text, record }">
                    <TableCell @click.stop="endAtPickerOpenMap[getInteractiveCellKey(record)] = true">
                        <div class="relative inline-block min-w-[120px]" @click.stop>
                            <span
                                v-if="!endAtPickerOpenMap[getInteractiveCellKey(record)]"
                                class="text-sm text-blue-600 cursor-pointer"
                            >
                                {{ text || "-" }}
                            </span>
                            <vort-date-picker
                                v-else
                                v-model="record.endAt"
                                v-model:open="endAtPickerOpenMap[getInteractiveCellKey(record)]"
                                value-format="YYYY-MM-DD"
                                format="YYYY-MM-DD"
                                allow-clear
                                size="small"
                                class="w-[128px]"
                                @change="(value: any) => selectRowDateField(record, 'endAt', value || '')"
                            />
                        </div>
                    </TableCell>
                </template>

                <template #repo="{ text, record }">
                    <TableCell @click="openRepoPicker(record, $event)">
                        <vort-select
                            :model-value="record.repoId || ''"
                            :open="repoPickerOpenMap[getInteractiveCellKey(record)]"
                            placeholder="未设置"
                            allow-clear
                            :bordered="false"
                            size="small"
                            class="w-full min-w-0"
                            @update:open="(open: boolean) => { repoPickerOpenMap[getInteractiveCellKey(record)] = open; if (open) loadRepoOptions(); }"
                            @change="(value: string | number | (string | number)[] | undefined) => selectRowRepo(record, String(value || ''))"
                        >
                            <vort-select-option v-for="item in apiRepos" :key="item.id" :value="item.id">{{ item.name }}</vort-select-option>
                        </vort-select>
                    </TableCell>
                </template>

                <template #branch="{ text, record }">
                    <TableCell @click="openBranchPicker(record, $event)">
                        <vort-select
                            :model-value="record.branch || ''"
                            :open="branchPickerOpenMap[getInteractiveCellKey(record)]"
                            :placeholder="record.repoId ? (branchLoadingMap[record.repoId] ? '分支加载中' : '未设置') : '请先选择仓库'"
                            allow-clear
                            :disabled="!record.repoId"
                            :bordered="false"
                            size="small"
                            class="w-full min-w-0"
                            @update:open="(open: boolean) => { branchPickerOpenMap[getInteractiveCellKey(record)] = open; if (open) loadBranchOptions(record.repoId); }"
                            @change="(value: string | number | (string | number)[] | undefined) => selectRowBranch(record, String(value || ''))"
                        >
                            <vort-select-option v-for="item in getBranchOptions(record.repoId)" :key="item.name" :value="item.name">{{ item.name }}</vort-select-option>
                        </vort-select>
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
                    ref="detailComponentRef"
                    :work-no="detailCurrentRecord.workNo"
                    :initial-data="detailCurrentRecord"
                    :parent-record="detailParentRecord"
                    :child-records="detailChildRecords"
                    :initial-desc-editing="detailDescEditing"
                    :initial-desc-draft="detailDescDraft"
                    @close="handleCancelCreateBug"
                    @update="handleDetailUpdate"
                    @delete="handleDetailDelete"
                    @copy="handleCopyWorkItem"
                    @open-related="handleOpenRelated"
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
                    :iteration-id="props.iterationId"
                    :initial-draft="createDraftData"
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

        <ImportDialog v-model:open="importDialogOpen" :project-id="props.projectId" @done="tableRef?.refresh?.()" />
        <ImportRecordDialog v-model:open="importRecordDialogOpen" />
        <BatchPropertyEditor
            v-model:open="batchPropertyEditorOpen"
            :selected-rows="selectedRows"
            :work-item-type="(props.type || '缺陷') as WorkItemType"
            :status-options="currentStatusFilterOptions"
            @done="() => { clearSelection(); refreshTable(); }"
        />
        <ViewManageDialog
            v-model:open="viewManageOpen"
            :work-item-type="type"
            :current-filters="currentViewStateForCreate.filters"
            :current-columns="currentViewStateForCreate.cols"
        />
        <ViewCreateDialog v-model:open="viewCreateOpen" @create="handleCreateViewFromDialog" />
        <ViewCreateDialog v-model:open="saveViewDialogOpen" @create="handleSaveAsNewView" />
        <ColumnSettingsDialog
            v-model:open="columnSettingsOpen"
            :all-columns="columnSettingsForDialog"
            @save="handleColumnSettingsSave"
        />
    </div>
</template>

<style scoped>
@reference "../../assets/styles/index.css";

.progress-cell {
    @apply flex items-center gap-2;
}
.progress-bar {
    @apply flex-1 h-2 rounded-full overflow-hidden;
    background-color: var(--vort-bg-secondary, #f0f0f0);
    min-width: 60px;
}
.progress-fill {
    @apply h-full rounded-full transition-all duration-200;
    background-color: #22c55e;
}
.progress-text {
    @apply text-sm text-gray-600 whitespace-nowrap;
    min-width: 36px;
}

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

.column-settings-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #fff;
    cursor: pointer;
    color: #666;
    transition: all 0.2s;
}
.column-settings-btn:hover {
    border-color: var(--vort-primary, #1456f0);
    color: var(--vort-primary, #1456f0);
    background: var(--vort-primary-bg, rgba(20, 86, 240, 0.04));
}

.save-view-wrapper {
    position: relative;
}

.save-view-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    height: 32px;
    padding: 0 10px;
    border: 1px solid var(--vort-primary, #1456f0);
    border-radius: 6px;
    background: #fff;
    color: var(--vort-primary, #1456f0);
    font-size: 13px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s;
}
.save-view-btn:hover {
    background: var(--vort-primary-bg, rgba(20, 86, 240, 0.04));
}

.save-view-arrow {
    transition: transform 0.2s;
}
.save-view-arrow.open {
    transform: rotate(180deg);
}

.save-view-dropdown {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    min-width: 150px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12);
    padding: 4px;
    z-index: 50;
}

.save-view-option {
    display: block;
    width: 100%;
    padding: 8px 12px;
    border: none;
    background: transparent;
    text-align: left;
    font-size: 14px;
    color: #1e293b;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.15s;
    white-space: nowrap;
}
.save-view-option:hover:not(:disabled) {
    background: rgba(0, 0, 0, 0.04);
}
.save-view-option:disabled {
    color: #c0c4cc;
    cursor: not-allowed;
}

.dropdown-enter-active,
.dropdown-leave-active {
    transition: opacity 0.15s, transform 0.15s;
}
.dropdown-enter-from,
.dropdown-leave-to {
    opacity: 0;
    transform: translateY(-4px);
}

.cell-select-plain {
    width: 100%;
}

</style>

<style>
.cell-select-plain .vort-select-suffix {
    display: none !important;
}
.cell-select-plain .vort-select-value {
    color: inherit !important;
    font-size: inherit !important;
}
.cell-select-plain .vort-select-placeholder {
    color: #d1d5db !important;
    font-size: inherit !important;
}
</style>