<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ProTable, TableCell } from "@/components/vort-biz";
import { message } from "@openvort/vort-ui";
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
import type { ColumnFilterValue } from "@/components/vort-biz/pro-table/ColumnFilterPopover.vue";
import ViewSelector from "./components/ViewSelector.vue";
import ViewManageDialog from "./components/ViewManageDialog.vue";
import ViewCreateDialog from "./components/ViewCreateDialog.vue";
import ColumnSettingsDialog from "./components/ColumnSettingsDialog.vue";
import NewTagDialog from "./components/NewTagDialog.vue";
import { useVortFlowStore } from "@/stores";
import { useVortFlowViews, SYSTEM_VIEWS } from "./composables/useVortFlowViews";
import { useWorkItemExport } from "./composables/useWorkItemExport";
import { useWorkItemColumns } from "./composables/useWorkItemColumns";
import { useWorkItemViewState } from "./composables/useWorkItemViewState";
import { useWorkItemDataSource } from "./composables/useWorkItemDataSource";
import { useWorkItemColumnFilters } from "./composables/useWorkItemColumnFilters";
import { useWorkItemMetadata } from "./composables/useWorkItemMetadata";
import { useWorkItemCrud } from "./composables/useWorkItemCrud";
import { useWorkItemDetailPanel } from "./composables/useWorkItemDetailPanel";
import { useWorkItemFieldEditors } from "./composables/useWorkItemFieldEditors";
import { useWorkItemCommon } from "./work-item/useWorkItemCommon";
import { useWorkItemInlineEdit } from "./work-item/useWorkItemInlineEdit";
import { useWorkItemDraft } from "./work-item/useWorkItemDraft";
import type {
    WorkItemType,
    Priority,
    WorkItemTableProps,
    ViewFilters,
    NewBugForm,
    RowItem,
    StatusOption,
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
    if (currentWorkItemType.value) vortFlowStore.setViewId(currentWorkItemType.value, viewId);
};
const viewManageOpen = ref(false);
const viewCreateOpen = ref(false);

const { views: mergedViews, activeViewFilters: builtInViewFilters } = currentWorkItemType.value
    ? useVortFlowViews(currentWorkItemType.value)
    : { views: computed(() => SYSTEM_VIEWS), activeViewFilters: computed(() => ({})) };

// --- Common & Draft ---

const {
    memberOptions, ownerGroups, getStatusOptionsByType, priorityOptions,
    getAvatarBg, getAvatarLabel, getMemberAvatarUrl,
    loadMemberOptions, getMemberIdByName, getMemberNameById,
    getWorkItemTypeIconClass, getWorkItemTypeIcon,
    mapBackendStateToStatus, mapBackendPriority, formatCnTime, formatDate,
    toBackendPriorityLevel, toTaskEstimateHours, getBackendStatesByDisplayStatus,
    bugStatusFilterOptions, demandStatusFilterOptions, taskStatusFilterOptions, loadStatusOptions,
} = useWorkItemCommon();

const { saveDraft, loadDraft, clearDraft } = useWorkItemDraft();

// --- Filters & helpers ---

const keyword = ref("");
const owner = ref<string[]>([]);
const type = ref<WorkItemType | "">(props.type ?? "");
const status = ref<string[]>([]);
const totalCount = ref(0);

const resolveActiveType = (): WorkItemType => {
    if (props.type) return props.type;
    if (type.value === "需求" || type.value === "任务" || type.value === "缺陷") return type.value;
    return "缺陷";
};

const allStatusFilterOptions: StatusOption[] = Array.from(
    new Map(
        [...demandStatusFilterOptions, ...taskStatusFilterOptions, ...bugStatusFilterOptions].map((item) => [item.value, item])
    ).values()
);
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

const getActiveProjectId = (): string => props.projectId || vortFlowStore.selectedProjectId || "";

const onAvatarError = (e: Event) => {
    const el = e.target as HTMLImageElement | null;
    if (el) el.style.display = "none";
};

// --- Metadata ---

const {
    apiProjects, apiIterations, apiRepos, apiTagDefinitions,
    baseTagOptions, dynamicTagOptions, dynamicIterationOptions, dynamicVersionOptions,
    branchOptionsMap, branchLoadingMap, remoteTemplates,
    getDescriptionTemplate, getRepoNameById, getBranchOptions,
    loadRepoOptions, loadIterationOptions, loadBranchOptions, loadTagDefinitions,
    collectTagOptions, collectEnumOptions, loadApiMetadata, loadDescriptionTemplates,
} = useWorkItemMetadata({ useApi: computed(() => props.useApi), getActiveProjectId });

const currentProjectName = computed(() => {
    if (!props.projectId) return "";
    return apiProjects.value.find(p => p.id === props.projectId)?.name || "";
});

// --- Column filter state ---

const columnFilters = reactive<Record<string, ColumnFilterValue | null>>({});
const columnSortField = ref<string>("");
const columnSortOrder = ref<"ascend" | "descend" | null>(null);
const tableRef = ref<any>(null);

const {
    statusFilterConfig, dateFilterConfig, tagsFilterConfig,
    ownerFilterConfig, collaboratorsFilterConfig,
    iterationFilterConfig, versionFilterConfig,
    priorityFilterConfig, creatorFilterConfig, typeFilterConfig,
    handleColumnSort, handleColumnFilter,
} = useWorkItemColumnFilters({
    currentStatusFilterOptions, dynamicTagOptions, baseTagOptions,
    dynamicIterationOptions, dynamicVersionOptions,
    memberOptions, getMemberAvatarUrl, getAvatarBg, getAvatarLabel, priorityOptions,
    columnFilters, columnSortField, columnSortOrder, tableRef,
});

// --- Column settings & View state ---

const {
    columnSettingsOpen, columnSettings, columns, columnSettingsForDialog,
    loadColumnSettingsFromStore, handleColumnSettingsSave, handleColumnWidthChange, applyOrderedColumnSettings,
} = useWorkItemColumns({ workItemType: props.type || "" });

const {
    viewDirty, isSystemView, saveViewDialogOpen, saveViewDropdownOpen, saveViewWrapperRef,
    currentViewStateForCreate, resetViewBaseline, collectCurrentViewState,
    handleUpdateCurrentView, handleSaveAsNew, handleSaveAsNewView, applyViewState,
} = useWorkItemViewState({
    workItemType: props.type || "", currentViewId, keyword, owner, status,
    columnFilters, columnSortField, columnSortOrder, columnSettings, applyOrderedColumnSettings,
});

const handleCreateViewFromDialog = async (data: { name: string; scope: "personal" | "shared" }) => {
    const { filters, cols } = collectCurrentViewState();
    const maxOrder = vortFlowStore.customViews.reduce((max, v) => Math.max(max, v.order), -1);
    await vortFlowStore.addCustomView({
        name: data.name, work_item_type: props.type || "缺陷", scope: data.scope,
        visible: true, filters, columns: cols, order: maxOrder + 1,
    });
    viewCreateOpen.value = false;
};

// --- Shared reactive state ---

const itemRowsById = reactive<Record<string, RowItem>>({});
const itemChildrenMap = reactive<Record<string, RowItem[]>>({});
const expandedItemIds = reactive<Record<string, boolean>>({});
const expandingItemIds = reactive<Record<string, boolean>>({});
const pinnedRowsByType = reactive<Record<WorkItemType, RowItem[]>>({ 需求: [], 任务: [], 缺陷: [] });
const priorityModel = reactive<Record<string, Priority>>({});
const tagsModel = reactive<Record<string, string[]>>({});
const planTimeModel = reactive<Record<string, any>>({});
const collaboratorsModel = reactive<Record<string, string[]>>({});

// --- Data source ---

const {
    mapBackendItemToRow, findItemRowById, findItemRowByIdentifier,
    loadItemById, loadChildItems, request, postProcessTableRows, prependPinnedRow,
} = useWorkItemDataSource({
    useApi: computed(() => props.useApi), propType: props.type || "",
    propProjectId: computed(() => props.projectId || ""),
    propIterationId: computed(() => props.iterationId || ""),
    propViewFilters: computed(() => ({ ...builtInViewFilters.value, ...(props.viewFilters || {}) })),
    type, owner, status, columnFilters, columnSortField, columnSortOrder, totalCount,
    apiProjects, pinnedRowsByType, expandedItemIds, expandingItemIds, itemRowsById, itemChildrenMap,
    getMemberIdByName, getMemberNameById, loadMemberOptions,
    mapBackendStateToStatus, mapBackendPriority, getBackendStatesByDisplayStatus, formatCnTime, formatDate,
    collectTagOptions, collectEnumOptions,
});

// --- CRUD ---

const createWorkItemRef = ref<{
    submit: () => NewBugForm | null;
    reset: () => void;
    cancel: () => void;
    getFormData: () => NewBugForm;
    getDescriptionTemplateForCurrentType: () => string;
} | null>(null);

const {
    selectedRowKeys, selectedRows, createParentItemId, createProjectId,
    createDraftData, createBugAttachments, createBugForm, createParentRecord,
    createInitialBugForm, resetCreateBugForm, rowSelection, clearSelection,
    syncRecordUpdateToApi, syncRecordStatusToApi, deleteOne, handleBatchDelete,
    handleCreateSuccess: crudCreateSuccess, handleCopyWorkItem: crudCopyWorkItem,
    handleDetailUpdate: crudDetailUpdate, handleUnlinkChild: crudUnlinkChild,
} = useWorkItemCrud({
    useApi: computed(() => props.useApi), propType: props.type || "",
    getDescriptionTemplate, getMemberIdByName, getBackendStatesByDisplayStatus, formatCnTime,
    mapBackendItemToRow, prependPinnedRow, findItemRowById,
    apiProjects, apiIterations, dynamicVersionOptions,
    itemRowsById, itemChildrenMap, expandedItemIds, tableRef, createWorkItemRef,
    saveDraft, loadDraft, clearDraft,
});

// --- Inline edit ---

const {
    priorityPickerOpenMap, tagPickerOpenMap, statusPickerOpenMap,
    ownerPickerOpenMap, collaboratorsPickerOpenMap,
    getInteractiveCellKey, isCellBackgroundClick, openCellPickerOnBackgroundClick,
    getRowPriority, selectPriority, getRowStatus, selectRowStatus,
    getRowOwner, selectRowOwner, getRowCollaborators, setRowCollaborators,
    getRowTags, setRowTags, rowTagOptions,
    getRowPlanTimeText, getRowOverdueInfo, onPlanTimeChange, onPlanTimeOpenChange,
    getRowPlanTime, togglePlanTimeMenu,
    getTagColor, tagColorPalette, openCreateTagDialog, handleCancelCreateTag, handleConfirmCreateTag,
    newTagName, newTagColor, newTagDialogOpen, openPlanTimeFor, planTimePickerOpen,
} = useWorkItemInlineEdit({
    useApi: computed(() => props.useApi), syncRecordUpdateToApi, syncRecordStatusToApi,
    getMemberIdByName, mapBackendPriority, toBackendPriorityLevel, toTaskEstimateHours,
    getBackendStatesByDisplayStatus: (t, s) => getBackendStatesByDisplayStatus(t as WorkItemType, s) || [],
    dynamicTagOptions, baseTagOptions, tagDefinitions: apiTagDefinitions,
    priorityModel, tagsModel, collaboratorsModel, planTimeModel, normalizeDateValue,
});

// --- Field editors ---

const {
    estimateEditingFor, estimateDraftMap, estimateInputRef, openEstimateEditor, selectRowEstimateHours,
    progressEditingFor, progressDraftMap, progressInputRef, isProgressReadonly, openProgressEditor, selectRowProgress,
    projectPickerOpenMap, selectRowProject, iterationPickerOpenMap, selectRowIteration,
    repoPickerOpenMap, openRepoPicker, selectRowRepo,
    branchPickerOpenMap, openBranchPicker, selectRowBranch,
    startAtPickerOpenMap, endAtPickerOpenMap, selectRowDateField,
} = useWorkItemFieldEditors({
    syncRecordUpdateToApi, getInteractiveCellKey, isCellBackgroundClick, openCellPickerOnBackgroundClick,
    normalizeDateValue, apiProjects, apiIterations, getRepoNameById, loadRepoOptions, loadBranchOptions,
});

// --- Detail panel ---

const {
    detailSelectedWorkNo, detailDescEditing, detailDescDraft,
    detailRecordSnapshot, detailComponentRef, detailParentRecord, detailChildRecords,
    detailCurrentRecord, cacheDescDraftBeforeClose, prepareDetailView,
    handleOpenRelated: detailOpenRelated, syncDetailRelations,
} = useWorkItemDetailPanel({
    useApi: computed(() => props.useApi), syncRecordUpdateToApi,
    loadItemById, loadChildItems, getRowPriority, getRowTags, planTimeModel,
});

// --- Export ---

const { handleExportCsv, handleExportExcel, handleExportJson } = useWorkItemExport({ selectedRows, itemRowsById });

// --- Page state ---

const importDialogOpen = ref(false);
const importRecordDialogOpen = ref(false);
const batchPropertyEditorOpen = ref(false);
const refreshKey = ref(0);
const mountedReady = ref(false);
const initialLoading = ref(true);

const queryParams = computed(() => ({
    keyword: keyword.value, owner: owner.value,
    type: props.type || type.value, status: status.value, _rk: refreshKey.value,
}));
const refreshTable = () => { refreshKey.value++; };
const onReset = () => { keyword.value = ""; owner.value = []; type.value = props.type ?? ""; status.value = []; };

watch(() => props.projectId, () => { loadRepoOptions(); tableRef.value?.refresh?.(); });
watch(() => props.viewFilters, () => { if (mountedReady.value) tableRef.value?.refresh?.(); }, { deep: true });
watch(builtInViewFilters, () => { if (mountedReady.value) tableRef.value?.refresh?.(); }, { deep: true });

const rowKeyGetter = (record: RowItem) => record.backendId || record.workNo;

// --- Drawer state ---

const createBugDrawerMode = ref<"create" | "detail">("create");

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

const handleCancelCreateBug = () => {
    createBugDrawerOpen.value = false;
    createParentItemId.value = "";
    createProjectId.value = "";
};

// --- Page-level CRUD wrappers (bridge composable + drawer state) ---

const handleCreateBug = async () => {
    await loadApiMetadata(props.type === "任务");
    if (apiProjects.value.length > 0) {
        const names = new Set(apiProjects.value.map((x) => x.name));
        if (!createBugForm.project || !names.has(createBugForm.project)) {
            createBugForm.project = apiProjects.value[0]!.name;
        }
    }
    createBugDrawerMode.value = "create";
    createParentItemId.value = "";
    createProjectId.value = props.projectId || "";
    resetCreateBugForm();
    const workItemType = (props.type || "缺陷") as WorkItemType;
    createDraftData.value = loadDraft(workItemType, "");
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

const handleCancelCreateWorkItem = () => {
    if (createWorkItemRef.value) { createWorkItemRef.value.cancel(); return; }
    handleCancelCreateBug();
};

const handleCreateSuccess = async (formData: NewBugForm, keepCreating = false) => {
    const success = await crudCreateSuccess(formData, keepCreating);
    if (success && !keepCreating) handleCancelCreateBug();
};

const handleSubmitCreateBug = async (keepCreating = false) => {
    const formData = createWorkItemRef.value?.submit();
    if (!formData) return;
    await handleCreateSuccess(formData, keepCreating);
};

const handleOpenBugDetail = async (record: RowItem) => {
    const info = await prepareDetailView(record);
    const base = createInitialBugForm();
    createBugDrawerMode.value = "detail";
    Object.assign(createBugForm, {
        ...base, title: record.title, owner: record.owner === "未指派" ? "" : record.owner,
        type: record.type, planTime: [...info.planTime], priority: info.priority,
        tags: [...info.tags], description: record.description || base.description,
    });
    const typeToTab: Record<string, string> = { "需求": "story", "任务": "task", "缺陷": "bug" };
    router.replace({ query: { ...route.query, action: "detail", id: record.backendId || record.workNo, tab: typeToTab[record.type] || typeToTab[props.type] } });
};

const handleDetailUpdate = async (data: Partial<RowItem>) => {
    if (!detailCurrentRecord.value) return;
    const result = await crudDetailUpdate(detailCurrentRecord.value, data);
    if (result === "close") handleCancelCreateBug();
};

const handleDetailDelete = async () => {
    const rec = detailCurrentRecord.value;
    if (!rec) return;
    try { await deleteOne(rec); message.success("删除成功"); handleCancelCreateBug(); tableRef.value?.refresh?.(); }
    catch { message.error("删除失败"); }
};

const handleCopyWorkItem = async () => {
    const success = await crudCopyWorkItem(detailCurrentRecord.value);
    if (success) createBugDrawerOpen.value = false;
};

const handleUnlinkChild = async (child: RowItem) => {
    await crudUnlinkChild(child, detailCurrentRecord.value, syncDetailRelations);
};

const handleOpenRelated = async (partial: any) => {
    await detailOpenRelated(partial, handleOpenBugDetail);
};

// --- Tree expand ---

const toggleItemExpand = async (record: RowItem) => {
    if ((record.type !== "需求" && record.type !== "任务") || !record.childrenCount || !record.backendId) return;
    const itemId = String(record.backendId);
    if (expandingItemIds[itemId]) return;
    if (expandedItemIds[itemId]) { expandedItemIds[itemId] = false; return; }
    if (!itemChildrenMap[itemId]) {
        expandingItemIds[itemId] = true;
        try { await loadChildItems(itemId, record.type, record.projectId); }
        finally { expandingItemIds[itemId] = false; }
    }
    expandedItemIds[itemId] = true;
};

// --- Tag rendering ---

const getCollapsedTags = (tags: string[], resolvedWidth?: string | number): { visible: string[]; hidden: number } => {
    const width = typeof resolvedWidth === "number" ? resolvedWidth
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

const getTagRenderInfo = (record: RowItem, text: string[] | undefined, resolvedWidth?: string | number) =>
    getCollapsedTags(getRowTags(record, text), resolvedWidth);

// --- Lifecycle ---

onMounted(async () => {
    const queryProject = route.query.project as string;
    if (queryProject && queryProject !== vortFlowStore.selectedProjectId) {
        vortFlowStore.setProjectId(queryProject);
    }
    const hasCachedColumns = !!vortFlowStore.getColumnSettings(props.type || "");
    if (hasCachedColumns) { columnSettings.value = loadColumnSettingsFromStore(); resetViewBaseline(); }

    await loadMemberOptions();
    await Promise.all([
        loadApiMetadata(false), loadRepoOptions(), loadIterationOptions(), loadTagDefinitions(),
        loadStatusOptions(), vortFlowStore.loadColumnSettings(props.type || ""),
        vortFlowStore.loadViews(), loadDescriptionTemplates(),
    ]);
    columnSettings.value = loadColumnSettingsFromStore();
    applyViewState();
    mountedReady.value = true;
    initialLoading.value = false;
    refreshTable();

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
            if (targetPath) { router.replace({ path: targetPath, query: { action: "detail", id, tab: urlTab } }); }
            return;
        }
        let record = findItemRowByIdentifier(id) || await loadItemById(id, props.type);
        if (!record && !urlType) {
            const otherTypes = (["需求", "任务", "缺陷"] as WorkItemType[]).filter(t => t !== props.type);
            for (const t of otherTypes) { record = await loadItemById(id, t); if (record) break; }
        }
        if (record) { handleOpenBugDetail(record); }
        else { router.replace({ query: { ...route.query, action: undefined, id: undefined, parentId: undefined, tab: undefined } }); }
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
                :loading="initialLoading"
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
                                <component :is="getWorkItemTypeIcon(record.type)" :size="12" />
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
                                <span v-if="getRowOverdueInfo(record, text)" class="plan-time-overdue" :class="getRowOverdueInfo(record, text)!.completed ? 'is-done' : ''">
                                    {{ getRowOverdueInfo(record, text)!.completed ? `逾期${getRowOverdueInfo(record, text)!.days}天完成` : `逾期${getRowOverdueInfo(record, text)!.days}天` }}
                                </span>
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
                    @unlink-child="handleUnlinkChild"
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

        <NewTagDialog
            v-model:open="newTagDialogOpen"
            v-model:tag-name="newTagName"
            v-model:tag-color="newTagColor"
            :color-palette="tagColorPalette"
            @cancel="handleCancelCreateTag"
            @confirm="handleConfirmCreateTag"
        />

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

.plan-time-overdue {
    margin-left: 6px;
    font-size: 12px;
    font-weight: 500;
    color: #dc2626;
    white-space: nowrap;
}
.plan-time-overdue.is-done {
    color: #d97706;
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