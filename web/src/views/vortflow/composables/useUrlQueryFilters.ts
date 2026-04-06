import { computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useVortFlowStore } from "@/stores";
import type { ViewFilters } from "@/components/vort-biz/work-item/WorkItemTable.types";

/**
 * Reads URL query params (project_id, assignee_id, status) and converts them
 * to ViewFilters for WorkItemTable. Sets the store project if needed.
 *
 * Supported query params:
 * - project_id: auto-selects the project in the store
 * - assignee_id: filters to items assigned to this member
 * - status: display-level filter (e.g. "incomplete")
 */
export function useUrlQueryFilters() {
    const route = useRoute();
    const router = useRouter();
    const store = useVortFlowStore();

    const urlFilters = computed<ViewFilters>(() => {
        const q = route.query;
        const filters: ViewFilters = {};
        if (q.assignee_id && typeof q.assignee_id === "string") {
            filters.owner = q.assignee_id;
        }
        if (q.status && typeof q.status === "string") {
            filters.status = q.status;
        }
        return filters;
    });

    onMounted(async () => {
        const qProjectId = route.query.project_id;
        if (qProjectId && typeof qProjectId === "string") {
            await store.loadProjects();
            const exists = store.projects.some(p => p.id === qProjectId);
            if (exists && store.selectedProjectId !== qProjectId) {
                store.setProjectId(qProjectId);
            }
            router.replace({ query: { ...route.query, project_id: undefined } });
        }
    });

    return { urlFilters };
}
