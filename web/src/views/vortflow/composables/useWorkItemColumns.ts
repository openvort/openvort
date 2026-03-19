import { computed, ref } from "vue";
import type { ProTableColumn } from "@/components/vort-biz";
import type { ColumnSettingItem } from "../components/ColumnSettingsDialog.vue";
import type { RowItem } from "@/components/vort-biz/work-item/WorkItemTable.types";
import { useVortFlowStore } from "@/stores";

export interface UseWorkItemColumnsOptions {
    workItemType: string;
}

const ALL_COLUMN_DEFS: Array<ProTableColumn<RowItem> & { key: string }> = [
    { key: "workNo", title: "工作编号", dataIndex: "workNo", width: 130, sorter: true, align: "left", fixed: "left", slot: "workNo" },
    { key: "title", title: "标题", dataIndex: "title", width: 228, ellipsis: true, align: "left", fixed: "left", slot: "title" },
    { key: "status", title: "状态", dataIndex: "status", width: 120, slot: "status", align: "left" },
    { key: "owner", title: "负责人", dataIndex: "owner", width: 160, align: "left", slot: "owner" },
    { key: "priority", title: "优先级", dataIndex: "priority", width: 120, slot: "priority", align: "left" },
    { key: "tags", title: "标签", dataIndex: "tags", width: 180, slot: "tags", align: "left" },
    { key: "createdAt", title: "创建时间", dataIndex: "createdAt", width: 150, align: "left", slot: "createdAt" },
    { key: "collaborators", title: "协作者", dataIndex: "collaborators", width: 140, slot: "collaborators", align: "left" },
    { key: "type", title: "工作项类型", dataIndex: "type", width: 120, align: "left", slot: "type" },
    { key: "planTime", title: "计划时间", dataIndex: "planTime", width: 260, align: "left", slot: "planTime" },
    { key: "creator", title: "创建人", dataIndex: "creator", width: 160, align: "left", slot: "creator" },
    { key: "updatedAt", title: "更新时间", dataIndex: "updatedAt", width: 150, align: "left", slot: "updatedAt" },
    { key: "iteration", title: "迭代", dataIndex: "iteration", width: 140, align: "left", slot: "iteration" },
    { key: "version", title: "版本", dataIndex: "version", width: 120, align: "left", slot: "version" },
    { key: "estimateHours", title: "预估工时", dataIndex: "estimateHours", width: 100, sorter: true, align: "left", slot: "estimateHours" },
    { key: "repo", title: "关联仓库", dataIndex: "repo", width: 140, align: "left", slot: "repo" },
    { key: "milestone", title: "关联里程碑", dataIndex: "milestone", width: 140, align: "left", slot: "milestone" },
    { key: "branch", title: "关联分支", dataIndex: "branch", width: 140, align: "left", slot: "branch" },
    { key: "project", title: "关联项目", dataIndex: "projectName", width: 140, sorter: true, align: "left", slot: "project" },
    { key: "startAt", title: "实际开始时间", dataIndex: "startAt", width: 150, align: "left", slot: "startAt" },
    { key: "endAt", title: "实际结束时间", dataIndex: "endAt", width: 150, align: "left", slot: "endAt" },
];

const DEFAULT_VISIBLE_KEYS = new Set([
    "workNo", "title", "status", "owner", "priority", "tags",
    "createdAt", "collaborators", "type", "planTime", "creator",
]);

export function useWorkItemColumns(options: UseWorkItemColumnsOptions) {
    const { workItemType } = options;
    const vortFlowStore = useVortFlowStore();

    const columnSettingsOpen = ref(false);

    const buildDefaultColumnSettings = (): ColumnSettingItem[] =>
        ALL_COLUMN_DEFS.map(c => ({
            key: c.key,
            title: c.title || c.key,
            fixed: c.key === "workNo" || c.key === "title",
            visible: DEFAULT_VISIBLE_KEYS.has(c.key),
        }));

    const loadColumnSettingsFromStore = (): ColumnSettingItem[] => {
        if (!workItemType) return buildDefaultColumnSettings();
        const persisted = vortFlowStore.getColumnSettings(workItemType);
        if (!persisted || persisted.length === 0) return buildDefaultColumnSettings();
        const defaults = buildDefaultColumnSettings();
        const defaultMap = new Map(defaults.map(c => [c.key, c]));
        const result: ColumnSettingItem[] = [];
        const seen = new Set<string>();
        for (const p of persisted) {
            const def = defaultMap.get(p.key);
            if (def) {
                result.push({ ...def, visible: p.visible });
                seen.add(p.key);
            }
        }
        for (const d of defaults) {
            if (!seen.has(d.key)) result.push(d);
        }
        return result;
    };

    const columnSettings = ref<ColumnSettingItem[]>(loadColumnSettingsFromStore());

    const handleColumnSettingsSave = (settings: ColumnSettingItem[]) => {
        columnSettings.value = settings;
        if (workItemType) {
            const existing = vortFlowStore.getColumnSettings(workItemType);
            const widthMap = new Map<string, number>();
            if (existing) {
                for (const p of existing) {
                    if (p.width) widthMap.set(p.key, p.width);
                }
            }
            vortFlowStore.setColumnSettings(
                workItemType,
                settings.map(s => {
                    const w = widthMap.get(s.key);
                    return w ? { key: s.key, visible: s.visible, width: w } : { key: s.key, visible: s.visible };
                }),
            );
        }
    };

    const handleColumnWidthChange = (widths: Record<string, number>) => {
        if (!workItemType) return;
        const existing = vortFlowStore.getColumnSettings(workItemType);
        if (!existing || existing.length === 0) return;
        const updated = existing.map(p => {
            const w = widths[p.key];
            return w ? { ...p, width: w } : p;
        });
        vortFlowStore.setColumnSettings(workItemType, updated);
    };

    const applyOrderedColumnSettings = (
        current: ColumnSettingItem[],
        saved: Array<{ key: string; visible: boolean }>,
    ): ColumnSettingItem[] => {
        if (!saved?.length) return current;
        const currentMap = new Map(current.map((item) => [item.key, item]));
        const next: ColumnSettingItem[] = [];
        const seen = new Set<string>();

        for (const item of saved) {
            const currentItem = currentMap.get(item.key);
            if (!currentItem) continue;
            next.push({ ...currentItem, visible: item.visible });
            seen.add(item.key);
        }

        for (const item of current) {
            if (seen.has(item.key)) continue;
            next.push(item);
        }

        return next;
    };

    const columns = computed<ProTableColumn<RowItem>[]>(() => {
        const orderedKeys = columnSettings.value.filter(s => s.visible).map(s => s.key);
        const colMap = new Map(ALL_COLUMN_DEFS.map(c => [c.key, c]));
        const persisted = vortFlowStore.getColumnSettings(workItemType || "");
        const widthMap = new Map<string, number>();
        if (persisted) {
            for (const p of persisted) {
                if (p.width) widthMap.set(p.key, p.width);
            }
        }
        return orderedKeys.map(k => {
            const def = colMap.get(k);
            if (!def) return null;
            const savedWidth = widthMap.get(k);
            return savedWidth ? { ...def, width: savedWidth } : def;
        }).filter(Boolean) as ProTableColumn<RowItem>[];
    });

    const columnSettingsForDialog = computed<ColumnSettingItem[]>(() => columnSettings.value);

    return {
        ALL_COLUMN_DEFS,
        DEFAULT_VISIBLE_KEYS,
        columnSettingsOpen,
        columnSettings,
        columns,
        columnSettingsForDialog,
        buildDefaultColumnSettings,
        loadColumnSettingsFromStore,
        handleColumnSettingsSave,
        handleColumnWidthChange,
        applyOrderedColumnSettings,
    };
}
