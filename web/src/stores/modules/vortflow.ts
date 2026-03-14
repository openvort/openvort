import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { getVortflowProjects } from "@/api";

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

export const useVortFlowStore = defineStore(
    "vortflow",
    () => {
        const selectedProjectId = ref<string>("");
        // Per-type view selection: { "需求": "all", "任务": "my_assigned", "缺陷": "all" }
        const viewIdByType = ref<Record<string, string>>({});
        const projects = ref<VortFlowProject[]>([]);
        const projectsLoaded = ref(false);

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
            selectedProject,
            setProjectId, getViewId, setViewId, loadProjects,
        };
    },
    {
        persist: {
            pick: ["selectedProjectId", "viewIdByType"],
        },
    }
);
