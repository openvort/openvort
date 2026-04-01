import { computed, reactive, ref, unref, type ComputedRef, type Ref } from "vue";
import {
    getVortflowProjects,
    getVortflowStories,
    getVortgitRepos,
    getVortgitRepoBranches,
    getVortflowTags,
    getVortflowIterations,
    getVortflowDescriptionTemplates,
} from "@/api";
import type { WorkItemType, RowItem } from "@/components/vort-biz/work-item/WorkItemTable.types";

const FALLBACK_TEMPLATES: Record<WorkItemType, string> = {
    "需求": "",
    "任务": "",
    "缺陷": "",
};

export interface UseWorkItemMetadataOptions {
    useApi: ComputedRef<boolean> | Ref<boolean>;
    getActiveProjectId: () => string;
}

export function useWorkItemMetadata(options: UseWorkItemMetadataOptions) {
    const { useApi, getActiveProjectId } = options;

    const apiProjects = ref<Array<{ id: string; name: string }>>([]);
    const apiIterations = ref<Array<{ id: string; name: string }>>([]);
    const apiRepos = ref<Array<{ id: string; name: string }>>([]);
    const apiStories = ref<Array<{ id: string; title: string }>>([]);
    const apiTagDefinitions = ref<Array<{ id: string; name: string; color: string }>>([]);
    const baseTagOptions = computed(() => apiTagDefinitions.value.map(t => t.name));
    const dynamicTagOptions = ref<string[]>([]);
    const dynamicIterationOptions = ref<Array<{ id: string; name: string }>>([]);
    const dynamicVersionOptions = ref<Array<{ id: string; name: string }>>([]);
    const branchOptionsMap = reactive<Record<string, Array<{ name: string }>>>({});
    const branchLoadingMap = reactive<Record<string, boolean>>({});
    const remoteTemplates = ref<Record<string, string>>({});

    const getDescriptionTemplate = (type: WorkItemType): string => {
        if (remoteTemplates.value[type] !== undefined && remoteTemplates.value[type] !== "") {
            return remoteTemplates.value[type];
        }
        return FALLBACK_TEMPLATES[type] ?? "";
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
        if (!unref(useApi)) return;
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
        if (!unref(useApi)) return;
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
        if (!unref(useApi) || !repoId) return;
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

    const collectTagOptions = (rows: RowItem[]) => {
        const set = new Set<string>(baseTagOptions.value);
        for (const row of rows) {
            for (const tag of row.tags || []) {
                if (tag) set.add(tag);
            }
        }
        dynamicTagOptions.value = [...set];
    };

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

    const loadApiMetadata = async (withStories = false) => {
        if (!unref(useApi)) return;
        const tasks: Promise<any>[] = [getVortflowProjects()];
        if (withStories) {
            tasks.push(getVortflowStories({ page: 1, page_size: 100 }));
        }
        const results = await Promise.allSettled(tasks);
        const projectsRes = results[0];
        const storiesRes = withStories ? results[1] : undefined;
        if (projectsRes && projectsRes.status === "fulfilled") {
            apiProjects.value = ((projectsRes.value as any)?.items || []).map((x: any) => ({
                id: String(x.id),
                name: String(x.name || x.id),
            }));
        }
        if (storiesRes && storiesRes.status === "fulfilled") {
            apiStories.value = ((storiesRes.value as any)?.items || []).map((x: any) => ({
                id: String(x.id),
                title: String(x.title || x.id),
            }));
        }
    };

    const loadDescriptionTemplates = async () => {
        try {
            const res: any = await getVortflowDescriptionTemplates();
            if (res?.items) remoteTemplates.value = res.items;
        } catch { /* ignore */ }
    };

    return {
        apiProjects,
        apiIterations,
        apiRepos,
        apiStories,
        apiTagDefinitions,
        baseTagOptions,
        dynamicTagOptions,
        dynamicIterationOptions,
        dynamicVersionOptions,
        branchOptionsMap,
        branchLoadingMap,
        remoteTemplates,
        getDescriptionTemplate,
        getRepoNameById,
        getBranchOptions,
        loadRepoOptions,
        loadIterationOptions,
        loadBranchOptions,
        loadTagDefinitions,
        collectTagOptions,
        collectEnumOptions,
        loadApiMetadata,
        loadDescriptionTemplates,
    };
}
