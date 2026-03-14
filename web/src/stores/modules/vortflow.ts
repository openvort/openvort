import { defineStore } from "pinia";
import { ref, computed } from "vue";
import {
    getVortflowProjects,
    getVortflowViews, createVortflowView, updateVortflowView, deleteVortflowView,
    getVortflowColumnSettings, saveVortflowColumnSettings,
} from "@/api";

export interface VortFlowProject {
    id: string;
    name: string;
    description?: string;
    owner_id?: string;
    created_at?: string;
    story_count?: number;
    task_count?: number;
    bug_count?: number;
}

export interface CustomView {
    id: string;
    name: string;
    scope: "personal" | "shared";
    visible: boolean;
    filters: Record<string, any>;
    columns: Array<{ key: string; visible: boolean }>;
    order: number;
    work_item_type?: string;
    owner_id?: string;
}

export interface PersistedColumnSetting {
    key: string;
    visible: boolean;
}

export const useVortFlowStore = defineStore(
    "vortflow",
    () => {
        const selectedProjectId = ref<string>("");
        const viewIdByType = ref<Record<string, string>>({});
        const projects = ref<VortFlowProject[]>([]);
        const projectsLoaded = ref(false);
        const customViews = ref<CustomView[]>([]);
        const viewsLoaded = ref(false);
        const columnSettingsByType = ref<Record<string, PersistedColumnSetting[]>>({});
        const columnSettingsLoaded = ref(false);

        const selectedProject = computed(() => {
            if (!selectedProjectId.value) return null;
            return projects.value.find(p => p.id === selectedProjectId.value) ?? null;
        });

        const setProjectId = (id: string) => {
            selectedProjectId.value = id;
        };

        const getViewId = (type: string): string => {
            return viewIdByType.value[type] || "all";
        };

        const setViewId = (type: string, viewId: string) => {
            viewIdByType.value = { ...viewIdByType.value, [type]: viewId };
        };

        // ---- Views (API-backed) ----

        const loadViews = async (workItemType?: string) => {
            try {
                const res: any = await getVortflowViews(workItemType);
                const items = (res?.items || []) as any[];
                customViews.value = items.map((v: any) => ({
                    id: v.id,
                    name: v.name,
                    scope: v.scope || "personal",
                    visible: true,
                    filters: v.filters || {},
                    columns: v.columns || [],
                    order: v.order ?? 0,
                    work_item_type: v.work_item_type,
                    owner_id: v.owner_id,
                }));
                viewsLoaded.value = true;
            } catch {
                customViews.value = [];
            }
        };

        const addCustomView = async (view: Omit<CustomView, "id"> & { work_item_type: string }) => {
            try {
                const res: any = await createVortflowView({
                    name: view.name,
                    work_item_type: view.work_item_type,
                    scope: view.scope,
                    filters: view.filters,
                    columns: view.columns || [],
                });
                if (res?.id) {
                    customViews.value.push({
                        id: res.id,
                        name: res.name,
                        scope: res.scope || "personal",
                        visible: true,
                        filters: res.filters || {},
                        columns: res.columns || [],
                        order: res.order ?? 0,
                        work_item_type: res.work_item_type,
                        owner_id: res.owner_id,
                    });
                }
                return res;
            } catch {
                return null;
            }
        };

        const updateCustomViewApi = async (id: string, data: Partial<Omit<CustomView, "id">>) => {
            try {
                await updateVortflowView(id, {
                    name: data.name,
                    filters: data.filters,
                    columns: data.columns,
                    view_order: data.order,
                });
                const idx = customViews.value.findIndex(v => v.id === id);
                if (idx !== -1) {
                    customViews.value[idx] = { ...customViews.value[idx]!, ...data };
                }
            } catch { /* silent */ }
        };

        const deleteCustomViewApi = async (id: string) => {
            try {
                await deleteVortflowView(id);
                customViews.value = customViews.value.filter(v => v.id !== id);
            } catch { /* silent */ }
        };

        const reorderViews = (ids: string[]) => {
            const map = new Map(customViews.value.map(v => [v.id, v]));
            const reordered: CustomView[] = [];
            for (let i = 0; i < ids.length; i++) {
                const view = map.get(ids[i]!);
                if (view) reordered.push({ ...view, order: i });
            }
            for (const v of customViews.value) {
                if (!ids.includes(v.id)) reordered.push(v);
            }
            customViews.value = reordered;
        };

        const toggleViewVisibility = (id: string, visible: boolean) => {
            const idx = customViews.value.findIndex(v => v.id === id);
            if (idx !== -1) {
                customViews.value[idx] = { ...customViews.value[idx]!, visible };
            }
        };

        // ---- Column Settings (API-backed) ----

        const loadColumnSettings = async (workItemType?: string) => {
            try {
                const res: any = await getVortflowColumnSettings(workItemType);
                if (res && typeof res === "object") {
                    for (const [type, cols] of Object.entries(res)) {
                        columnSettingsByType.value[type] = cols as PersistedColumnSetting[];
                    }
                }
                columnSettingsLoaded.value = true;
            } catch { /* silent */ }
        };

        const getColumnSettings = (type: string): PersistedColumnSetting[] | null => {
            return columnSettingsByType.value[type] || null;
        };

        const setColumnSettings = async (type: string, settings: PersistedColumnSetting[]) => {
            columnSettingsByType.value = {
                ...columnSettingsByType.value,
                [type]: settings,
            };
            try {
                await saveVortflowColumnSettings({ work_item_type: type, columns: settings });
            } catch { /* silent */ }
        };

        // ---- Projects ----

        const loadProjects = async () => {
            try {
                const res: any = await getVortflowProjects();
                projects.value = (res?.items || []).map((p: any) => ({
                    id: p.id,
                    name: p.name,
                    description: p.description || "",
                    owner_id: p.owner_id,
                    created_at: p.created_at,
                    story_count: p.story_count ?? 0,
                    task_count: p.task_count ?? 0,
                    bug_count: p.bug_count ?? 0,
                }));
                projectsLoaded.value = true;
            } catch {
                projects.value = [];
            }
        };

        return {
            selectedProjectId, viewIdByType, projects, projectsLoaded,
            customViews, viewsLoaded, columnSettingsByType, columnSettingsLoaded,
            selectedProject,
            setProjectId, getViewId, setViewId, loadProjects,
            loadViews, addCustomView,
            updateCustomView: updateCustomViewApi,
            deleteCustomView: deleteCustomViewApi,
            reorderViews, toggleViewVisibility,
            loadColumnSettings, getColumnSettings, setColumnSettings,
        };
    },
    {
        persist: {
            pick: ["selectedProjectId", "viewIdByType"],
        },
    }
);
