import { computed, type ComputedRef, type Ref } from "vue";
import type { ColumnFilterConfig, ColumnFilterValue } from "@/components/vort-biz/pro-table/ColumnFilterPopover.vue";
import type { MemberOption, StatusOption } from "@/components/vort-biz/work-item/WorkItemTable.types";
import type { Priority } from "@/components/vort-biz/work-item/WorkItemTable.types";

export const STATUS_DOT_COLOR_MAP: Record<string, string> = {
    "待确认": "#9ca3af",
    "修复中": "#3b82f6",
    "已修复": "#3b82f6",
    "已关闭": "#374151",
    "已取消": "#ef4444",
    "收集中": "#94a3b8",
    "意向": "#64748b",
    "设计中": "#6366f1",
    "设计完成": "#0284c7",
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

export const PRIORITY_DOT_COLOR_MAP: Record<string, string> = {
    "紧急": "#ef4444",
    "高": "#f59e0b",
    "中": "#3b82f6",
    "低": "#10b981",
    "无优先级": "#9ca3af",
};

export const TYPE_DOT_COLOR_MAP: Record<string, string> = {
    "需求": "#3b82f6",
    "任务": "#10b981",
    "缺陷": "#ef4444",
};

export interface UseWorkItemColumnFiltersOptions {
    currentStatusFilterOptions: ComputedRef<StatusOption[]>;
    dynamicTagOptions: Ref<string[]>;
    baseTagOptions: ComputedRef<string[]>;
    dynamicIterationOptions: Ref<Array<{ id: string; name: string }>>;
    dynamicVersionOptions: Ref<Array<{ id: string; name: string }>>;
    memberOptions: Ref<MemberOption[]>;
    getMemberAvatarUrl: (name: string) => string;
    getAvatarBg: (name: string) => string;
    getAvatarLabel: (name: string) => string;
    priorityOptions: Array<{ label: string; value: Priority }>;
    columnFilters: Record<string, ColumnFilterValue | null>;
    columnSortField: Ref<string>;
    columnSortOrder: Ref<"ascend" | "descend" | null>;
    tableRef: Ref<any>;
}

export function useWorkItemColumnFilters(options: UseWorkItemColumnFiltersOptions) {
    const {
        currentStatusFilterOptions,
        dynamicTagOptions,
        baseTagOptions,
        dynamicIterationOptions,
        dynamicVersionOptions,
        memberOptions,
        getMemberAvatarUrl,
        getAvatarBg,
        getAvatarLabel,
        priorityOptions,
        columnFilters,
        columnSortField,
        columnSortOrder,
        tableRef,
    } = options;

    const statusFilterConfig = computed<ColumnFilterConfig>(() => ({
        type: "enum",
        options: currentStatusFilterOptions.value.map(o => ({
            label: o.label,
            value: o.value,
            icon: o.icon,
            iconClass: o.iconClass,
        })),
    }));

    const dateFilterConfig: ColumnFilterConfig = { type: "date" };

    const tagsFilterConfig = computed<ColumnFilterConfig>(() => ({
        type: "enum",
        searchable: true,
        options: (dynamicTagOptions.value.length ? dynamicTagOptions.value : baseTagOptions.value).map(t => ({
            label: t,
            value: t,
        })),
        sortLabels: ["A → Z", "Z → A"] as [string, string],
    }));

    const buildMemberFilterOptions = (includeUnassigned = false) => {
        const items = memberOptions.value.map(m => ({
            label: m.name || m.id,
            value: m.name || m.id,
            avatarUrl: getMemberAvatarUrl(m.name || ""),
            avatarLabel: getAvatarLabel(m.name || m.id || ""),
            avatarBg: getAvatarBg(m.name || m.id || ""),
        }));
        if (includeUnassigned) return [{ label: "未指派", value: "__unassigned__" }, ...items];
        return items;
    };

    const ownerFilterConfig = computed<ColumnFilterConfig>(() => ({
        type: "enum",
        searchable: true,
        options: buildMemberFilterOptions(true),
        sortLabels: ["A → Z", "Z → A"] as [string, string],
    }));

    const collaboratorsFilterConfig = computed<ColumnFilterConfig>(() => ({
        type: "enum",
        searchable: true,
        options: buildMemberFilterOptions(false),
        sortLabels: ["A → Z", "Z → A"] as [string, string],
    }));

    const iterationFilterConfig = computed<ColumnFilterConfig>(() => ({
        type: "enum",
        searchable: true,
        options: dynamicIterationOptions.value.map(o => ({ label: o.name, value: o.name })),
    }));

    const versionFilterConfig = computed<ColumnFilterConfig>(() => ({
        type: "enum",
        searchable: true,
        options: dynamicVersionOptions.value.map(o => ({ label: o.name, value: o.name })),
    }));

    const priorityFilterConfig = computed<ColumnFilterConfig>(() => ({
        type: "enum",
        options: priorityOptions.map(o => ({
            label: o.label,
            value: o.value,
            dotColor: PRIORITY_DOT_COLOR_MAP[o.label] || "#9ca3af",
        })),
        sortLabels: ["紧急 → 低", "低 → 紧急"] as [string, string],
    }));

    const creatorFilterConfig = computed<ColumnFilterConfig>(() => ({
        type: "enum",
        searchable: true,
        options: buildMemberFilterOptions(false),
        sortLabels: ["A → Z", "Z → A"] as [string, string],
    }));

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
        if (tableRef.value) tableRef.value.current = 1;
        tableRef.value?.refresh?.();
    };

    const handleColumnFilter = (field: string, value: ColumnFilterValue | null) => {
        if (value) columnFilters[field] = value;
        else delete columnFilters[field];
        if (tableRef.value) tableRef.value.current = 1;
        tableRef.value?.refresh?.();
    };

    return {
        statusFilterConfig,
        dateFilterConfig,
        tagsFilterConfig,
        ownerFilterConfig,
        collaboratorsFilterConfig,
        iterationFilterConfig,
        versionFilterConfig,
        priorityFilterConfig,
        creatorFilterConfig,
        typeFilterConfig,
        handleColumnSort,
        handleColumnFilter,
    };
}
