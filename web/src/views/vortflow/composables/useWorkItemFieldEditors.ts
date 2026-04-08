import { nextTick, reactive, ref, type Ref } from "vue";
import { message } from "@openvort/vort-ui";
import {
    addVortflowIterationStory, addVortflowIterationTask, addVortflowIterationBug,
    removeVortflowIterationStory, removeVortflowIterationTask, removeVortflowIterationBug,
} from "@/api";
import type { RowItem } from "@/components/vort-biz/work-item/WorkItemTable.types";

export interface UseWorkItemFieldEditorsOptions {
    syncRecordUpdateToApi: (record: RowItem, patch: any) => Promise<void>;
    getInteractiveCellKey: (record: RowItem) => string;
    isCellBackgroundClick: (event: Event) => boolean;
    openCellPickerOnBackgroundClick: (record: RowItem, event: Event, openMap: Record<string, boolean>) => void;
    normalizeDateValue: (value: unknown) => string;
    apiProjects: Ref<Array<{ id: string; name: string }>>;
    apiIterations: Ref<Array<{ id: string; name: string }>>;
    getRepoNameById: (repoId?: string) => string;
    loadRepoOptions: () => Promise<void>;
    loadBranchOptions: (repoId?: string) => Promise<void>;
}

export function useWorkItemFieldEditors(options: UseWorkItemFieldEditorsOptions) {
    const {
        syncRecordUpdateToApi,
        getInteractiveCellKey,
        isCellBackgroundClick,
        openCellPickerOnBackgroundClick,
        normalizeDateValue,
        apiProjects,
        apiIterations,
        getRepoNameById,
        loadRepoOptions,
        loadBranchOptions,
    } = options;

    // --- Estimate hours ---
    const estimateEditingFor = ref<string | null>(null);
    const estimateDraftMap = reactive<Record<string, number | null>>({});
    const estimateInputRef = ref<any>(null);

    const openEstimateEditor = (record: RowItem) => {
        const key = getInteractiveCellKey(record);
        estimateDraftMap[key] = record.estimateHours == null || record.estimateHours === ""
            ? null
            : Number(record.estimateHours);
        estimateEditingFor.value = key;
        nextTick(() => estimateInputRef.value?.focus());
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

    // --- Progress ---
    const progressEditingFor = ref<string | null>(null);
    const progressDraftMap = reactive<Record<string, number | null>>({});
    const progressInputRef = ref<any>(null);

    const isProgressReadonly = (record: RowItem) => {
        if (record.type === "需求") return false;
        if ((record.childrenCount || 0) > 0) return true;
        return false;
    };

    const openProgressEditor = (record: RowItem) => {
        if (isProgressReadonly(record)) return;
        const key = getInteractiveCellKey(record);
        progressDraftMap[key] = record.progress ?? 0;
        progressEditingFor.value = key;
        nextTick(() => progressInputRef.value?.focus());
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

    // --- Project ---
    const projectPickerOpenMap = reactive<Record<string, boolean>>({});

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

    // --- Iteration ---
    const iterationPickerOpenMap = reactive<Record<string, boolean>>({});

    const selectRowIteration = async (record: RowItem, iterationId?: string) => {
        const key = getInteractiveCellKey(record);
        const itemId = String(record.backendId || "").trim();
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

    // --- Repo ---
    const repoPickerOpenMap = reactive<Record<string, boolean>>({});

    const openRepoPicker = async (record: RowItem, event: Event) => {
        const shouldOpen = isCellBackgroundClick(event);
        openCellPickerOnBackgroundClick(record, event, repoPickerOpenMap);
        if (shouldOpen) {
            await loadRepoOptions();
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

    // --- Branch ---
    const branchPickerOpenMap = reactive<Record<string, boolean>>({});

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

    // --- Date fields (startAt / endAt) ---
    const startAtPickerOpenMap = reactive<Record<string, boolean>>({});
    const endAtPickerOpenMap = reactive<Record<string, boolean>>({});

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

    return {
        estimateEditingFor,
        estimateDraftMap,
        estimateInputRef,
        openEstimateEditor,
        selectRowEstimateHours,
        progressEditingFor,
        progressDraftMap,
        progressInputRef,
        isProgressReadonly,
        openProgressEditor,
        selectRowProgress,
        projectPickerOpenMap,
        selectRowProject,
        iterationPickerOpenMap,
        selectRowIteration,
        repoPickerOpenMap,
        openRepoPicker,
        selectRowRepo,
        branchPickerOpenMap,
        openBranchPicker,
        selectRowBranch,
        startAtPickerOpenMap,
        endAtPickerOpenMap,
        selectRowDateField,
    };
}
