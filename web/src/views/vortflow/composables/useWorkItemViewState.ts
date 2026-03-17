import { computed, nextTick, ref, watch } from "vue";
import { message } from "@/components/vort";
import { useVortFlowStore } from "@/stores";
import { SYSTEM_VIEWS } from "./useVortFlowViews";
import type { ColumnFilterValue } from "@/components/vort-biz/pro-table/ColumnFilterPopover.vue";
import type { ColumnSettingItem } from "../components/ColumnSettingsDialog.vue";
import type { Ref, ComputedRef } from "vue";

export interface ViewSnapshot {
    keyword: string;
    owner: string;
    status: string;
    columnFilters: Record<string, ColumnFilterValue | null>;
    sortField: string;
    sortOrder: "ascend" | "descend" | null;
    columns: Array<{ key: string; visible: boolean }>;
}

export interface UseWorkItemViewStateOptions {
    workItemType: string;
    currentViewId: ComputedRef<string>;
    keyword: Ref<string>;
    owner: Ref<string>;
    status: Ref<string>;
    columnFilters: Record<string, ColumnFilterValue | null>;
    columnSortField: Ref<string>;
    columnSortOrder: Ref<"ascend" | "descend" | null>;
    columnSettings: Ref<ColumnSettingItem[]>;
    applyOrderedColumnSettings: (
        current: ColumnSettingItem[],
        saved: Array<{ key: string; visible: boolean }>,
    ) => ColumnSettingItem[];
}

export function useWorkItemViewState(options: UseWorkItemViewStateOptions) {
    const {
        workItemType,
        currentViewId,
        keyword,
        owner,
        status,
        columnFilters,
        columnSortField,
        columnSortOrder,
        columnSettings,
        applyOrderedColumnSettings,
    } = options;

    const vortFlowStore = useVortFlowStore();
    const viewBaseline = ref<ViewSnapshot | null>(null);

    const takeViewSnapshot = (): ViewSnapshot => ({
        keyword: keyword.value,
        owner: owner.value,
        status: status.value,
        columnFilters: { ...columnFilters },
        sortField: columnSortField.value,
        sortOrder: columnSortOrder.value,
        columns: columnSettings.value.map(s => ({ key: s.key, visible: s.visible })),
    });

    const resetViewBaseline = () => {
        viewBaseline.value = takeViewSnapshot();
    };

    const isSystemView = computed(() => {
        return SYSTEM_VIEWS.some(v => v.id === currentViewId.value);
    });

    const currentCustomView = computed(() => {
        if (isSystemView.value) return null;
        return vortFlowStore.customViews.find(v => v.id === currentViewId.value) ?? null;
    });

    const viewDirty = computed(() => {
        const base = viewBaseline.value;
        if (!base) return false;
        if (keyword.value !== base.keyword) return true;
        if (owner.value !== base.owner) return true;
        if (status.value !== base.status) return true;
        if (columnSortField.value !== base.sortField) return true;
        if (columnSortOrder.value !== base.sortOrder) return true;
        const currentFilterKeys = Object.keys(columnFilters);
        const baseFilterKeys = Object.keys(base.columnFilters);
        if (currentFilterKeys.length !== baseFilterKeys.length) return true;
        for (const k of currentFilterKeys) {
            if (JSON.stringify(columnFilters[k]) !== JSON.stringify(base.columnFilters[k])) return true;
        }
        const curCols = columnSettings.value.map(s => `${s.key}:${s.visible}`).join(",");
        const baseCols = base.columns.map(s => `${s.key}:${s.visible}`).join(",");
        if (curCols !== baseCols) return true;
        return false;
    });

    const saveViewDialogOpen = ref(false);
    const saveViewDropdownOpen = ref(false);
    const saveViewWrapperRef = ref<HTMLElement | null>(null);

    const onDocClickForSaveView = (e: MouseEvent) => {
        if (saveViewWrapperRef.value && !saveViewWrapperRef.value.contains(e.target as Node)) {
            saveViewDropdownOpen.value = false;
        }
    };

    watch(saveViewDropdownOpen, (open) => {
        if (open) {
            document.addEventListener("click", onDocClickForSaveView, true);
        } else {
            document.removeEventListener("click", onDocClickForSaveView, true);
        }
    });

    const collectCurrentViewState = () => {
        const filters: Record<string, any> = {};
        if (keyword.value) filters.keyword = keyword.value;
        if (owner.value) filters.owner = owner.value;
        if (status.value) filters.status = status.value;
        if (columnSortField.value) {
            filters.sortField = columnSortField.value;
            filters.sortOrder = columnSortOrder.value;
        }
        const cfKeys = Object.keys(columnFilters);
        if (cfKeys.length > 0) {
            filters.columnFilters = { ...columnFilters };
        }
        const cols = columnSettings.value.map(s => ({ key: s.key, visible: s.visible }));
        return { filters, cols };
    };

    const currentViewStateForCreate = computed(() => collectCurrentViewState());

    const handleUpdateCurrentView = async () => {
        saveViewDropdownOpen.value = false;
        const cv = currentCustomView.value;
        if (!cv) {
            message.warning("系统视图不可更新，请存为新视图");
            return;
        }
        const { filters, cols } = collectCurrentViewState();
        await vortFlowStore.updateCustomView(cv.id, { filters, columns: cols });
        message.success("视图已更新");
        resetViewBaseline();
    };

    const handleSaveAsNew = () => {
        saveViewDropdownOpen.value = false;
        saveViewDialogOpen.value = true;
    };

    const handleSaveAsNewView = async (data: { name: string; scope: "personal" | "shared" }) => {
        const { filters, cols } = collectCurrentViewState();
        const maxOrder = vortFlowStore.customViews.reduce((max, v) => Math.max(max, v.order), -1);
        const res = await vortFlowStore.addCustomView({
            name: data.name,
            work_item_type: workItemType || "缺陷",
            scope: data.scope,
            visible: true,
            filters,
            columns: cols,
            order: maxOrder + 1,
        });
        if (res?.id) {
            const cwt = workItemType as "需求" | "任务" | "缺陷" | null;
            if (cwt) vortFlowStore.setViewId(cwt, res.id);
        }
        saveViewDialogOpen.value = false;
        message.success("视图已创建");
        resetViewBaseline();
    };

    watch(currentViewId, () => {
        keyword.value = "";
        owner.value = "";
        status.value = "";
        columnSortField.value = "";
        columnSortOrder.value = null;
        for (const k of Object.keys(columnFilters)) {
            delete columnFilters[k];
        }
        const cv = vortFlowStore.customViews.find(v => v.id === currentViewId.value);
        if (cv?.filters) {
            const f = cv.filters;
            if (f.keyword) keyword.value = f.keyword;
            if (f.owner) owner.value = f.owner;
            if (f.status) status.value = f.status;
            if (f.sortField) columnSortField.value = f.sortField;
            if (f.sortOrder) columnSortOrder.value = f.sortOrder;
            if (f.columnFilters) {
                for (const [k, v] of Object.entries(f.columnFilters as Record<string, ColumnFilterValue>)) {
                    columnFilters[k] = v;
                }
            }
        }
        if (cv?.columns?.length) {
            columnSettings.value = applyOrderedColumnSettings(
                columnSettings.value,
                cv.columns.map((c: any) => ({ key: c.key, visible: c.visible })),
            );
        }
        nextTick(() => resetViewBaseline());
    });

    return {
        viewBaseline,
        viewDirty,
        isSystemView,
        currentCustomView,
        saveViewDialogOpen,
        saveViewDropdownOpen,
        saveViewWrapperRef,
        currentViewStateForCreate,
        takeViewSnapshot,
        resetViewBaseline,
        collectCurrentViewState,
        handleUpdateCurrentView,
        handleSaveAsNew,
        handleSaveAsNewView,
    };
}
