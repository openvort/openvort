import { computed, reactive, ref, unref, type ComputedRef, type Ref } from "vue";
import { message } from "@openvort/vort-ui";
import {
    createVortflowStory, createVortflowTask, createVortflowBug,
    copyVortflowStory, copyVortflowTask, copyVortflowBug,
    deleteVortflowStory, deleteVortflowTask, deleteVortflowBug,
    updateVortflowStory, updateVortflowTask, updateVortflowBug,
    addVortflowIterationStory, addVortflowIterationTask, addVortflowIterationBug,
    removeVortflowIterationStory, removeVortflowIterationTask, removeVortflowIterationBug,
    addVortflowVersionStory, removeVortflowVersionStory,
    addVortflowVersionBug, removeVortflowVersionBug,
    convertWorkItem,
    batchArchiveWorkItems,
} from "@/api";
import type {
    WorkItemType,
    Priority,
    Status,
    NewBugForm,
    RowItem,
    CreateBugAttachment,
} from "@/components/vort-biz/work-item/WorkItemTable.types";

const _TYPE_TO_BACKEND: Record<string, string> = { "需求": "story", "任务": "task", "缺陷": "bug" };

export interface UseWorkItemCrudOptions {
    useApi: ComputedRef<boolean> | Ref<boolean>;
    propType: string;
    getDescriptionTemplate: (type: WorkItemType) => string;
    getMemberIdByName: (name: string) => string;
    getBackendStatesByDisplayStatus: (type: WorkItemType, status: Status | string) => string[] | undefined;
    formatCnTime: (date: Date) => string;
    mapBackendItemToRow: (item: any, type: WorkItemType, index: number) => RowItem;
    prependPinnedRow: (type: WorkItemType, row: RowItem) => void;
    pinnedRowsByType: Record<WorkItemType, RowItem[]>;
    findItemRowById: (id: string | undefined) => RowItem | null;
    apiProjects: Ref<Array<{ id: string; name: string }>>;
    apiIterations: Ref<Array<{ id: string; name: string }>>;
    dynamicVersionOptions: Ref<Array<{ id: string; name: string }>>;
    itemRowsById: Record<string, RowItem>;
    itemChildrenMap: Record<string, RowItem[]>;
    expandedItemIds: Record<string, boolean>;
    tableRef: Ref<any>;
    createWorkItemRef: Ref<any>;
    saveDraft: (type: WorkItemType, data: NewBugForm, parentId: string, descTemplate: string) => void;
    loadDraft: (type: WorkItemType, parentId: string) => NewBugForm | null;
    clearDraft: (type: WorkItemType) => void;
}

export function useWorkItemCrud(options: UseWorkItemCrudOptions) {
    const {
        useApi,
        propType,
        getDescriptionTemplate,
        getMemberIdByName,
        getBackendStatesByDisplayStatus,
        formatCnTime,
        mapBackendItemToRow,
        prependPinnedRow,
        pinnedRowsByType,
        findItemRowById,
        apiProjects,
        apiIterations,
        dynamicVersionOptions,
        itemRowsById,
        itemChildrenMap,
        expandedItemIds,
        tableRef,
        createWorkItemRef,
        saveDraft,
        loadDraft,
        clearDraft,
    } = options;

    const removePinnedRow = (type: WorkItemType, backendId: string) => {
        const list = pinnedRowsByType[type];
        if (!list) return;
        pinnedRowsByType[type] = list.filter((r) => r.backendId !== backendId);
    };

    const selectedRowKeys = ref<Array<string | number>>([]);
    const selectedRows = ref<RowItem[]>([]);
    const createParentItemId = ref("");
    const createProjectId = ref("");
    const createDraftData = ref<NewBugForm | null>(null);
    const isCreating = ref(false);
    const createBugAttachments = ref<CreateBugAttachment[]>([]);
    const createAttachmentInputRef = ref<HTMLInputElement | null>(null);

    const createInitialBugForm = (): NewBugForm => ({
        title: "",
        owner: "",
        collaborators: [],
        type: (propType ?? "缺陷") as WorkItemType,
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
        description: getDescriptionTemplate((propType ?? "缺陷") as WorkItemType),
    });

    const createBugForm = reactive<NewBugForm>(createInitialBugForm());

    const resetCreateBugForm = () => {
        Object.assign(createBugForm, createInitialBugForm());
        createBugAttachments.value = [];
    };

    const resolveCreateProjectId = (): string => {
        if (!apiProjects.value.length) return "";
        const selected = createBugForm.project?.trim();
        if (!selected) return apiProjects.value[0]?.id || "";
        const match = apiProjects.value.find((x) => x.name === selected || x.id === selected);
        return match?.id || apiProjects.value[0]?.id || "";
    };

    const createParentRecord = computed<RowItem | null>(() => findItemRowById(createParentItemId.value));

    // --- Selection ---

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

    // --- API sync ---

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
            plan_start?: string;
            deadline?: string;
            pm_id?: string | null;
            project_id?: string | null;
            actual_hours?: number;
            start_at?: string;
            end_at?: string;
            test_time?: string;
            draft_time?: string;
            release_time?: string;
            repo_id?: string | null;
            branch?: string;
            progress?: number;
            attachments?: { name: string; url: string; size: number }[];
        }
    ) => {
        if (!unref(useApi)) return;
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
                plan_start: patch.plan_start,
                deadline: patch.deadline,
                pm_id: patch.pm_id,
                project_id: patch.project_id,
                start_at: patch.start_at,
                end_at: patch.end_at,
                test_time: patch.test_time,
                draft_time: patch.draft_time,
                release_time: patch.release_time,
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
                plan_start: patch.plan_start,
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
            plan_start: patch.plan_start,
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
        if (!unref(useApi)) return;
        const targetStates = getBackendStatesByDisplayStatus(record.type, displayStatus) || [];
        if (!targetStates.length) {
            throw new Error("当前状态不支持同步到后端");
        }
        await syncRecordUpdateToApi(record, { state: targetStates[0] });
    };

    // --- Delete ---

    const deleteOne = async (record: RowItem) => {
        const id = record.backendId;
        if (!id) throw new Error("缺少记录ID");
        const itemType = (propType || record.type) as WorkItemType;
        if (itemType === "需求") await deleteVortflowStory(id);
        else if (itemType === "任务") await deleteVortflowTask(id);
        else await deleteVortflowBug(id);
        removePinnedRow(itemType, id);
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
        tableRef.value?.refresh?.();
    };

    // --- Archive ---

    const _batchArchive = async (archived: boolean) => {
        if (!selectedRows.value.length) return;
        const rows = [...selectedRows.value];
        const backendType = _TYPE_TO_BACKEND[propType] || "story";
        const ids = rows.map((r) => r.backendId).filter(Boolean) as string[];
        if (!ids.length) return;
        try {
            await batchArchiveWorkItems({ ids, type: backendType, archived });
            message.success(archived ? `已归档 ${ids.length} 条` : `已取消归档 ${ids.length} 条`);
        } catch {
            message.error(archived ? "批量归档失败" : "批量取消归档失败");
        }
        clearSelection();
        tableRef.value?.refresh?.();
    };

    const handleBatchArchive = () => _batchArchive(true);
    const handleBatchUnarchive = () => _batchArchive(false);

    // --- Create ---

    const handleCreateSuccess = async (formData: NewBugForm, keepCreating = false) => {
        if (isCreating.value) return false;
        const title = formData.title.trim();
        if (!title) {
            message.warning("请填写标题");
            return;
        }

        if (unref(useApi)) {
            const type = (propType || formData.type || "缺陷") as WorkItemType;
            isCreating.value = true;
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
                        plan_start: formData.planTime?.[0] || undefined,
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
                        plan_start: formData.planTime?.[0] || undefined,
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
                        plan_start: formData.planTime?.[0] || undefined,
                        deadline: formData.planTime?.[1] || undefined,
                    });
                }
                if (createdItem) {
                    const createdId = String(createdItem.id || "");
                    if (createdId && formData.iteration && formData.iteration !== "__unplanned__") {
                        try {
                            if (type === "需求") await addVortflowIterationStory(formData.iteration, { story_id: createdId });
                            else if (type === "任务") await addVortflowIterationTask(formData.iteration, { task_id: createdId });
                            else if (type === "缺陷") await addVortflowIterationBug(formData.iteration, { bug_id: createdId });
                            createdItem.iteration_id = formData.iteration;
                            createdItem.iteration_name = apiIterations.value.find((i: any) => i.id === formData.iteration)?.name || "";
                        } catch { /* iteration link failed silently */ }
                    }
                    if (createdId && formData.version) {
                        try {
                            if (type === "需求") await addVortflowVersionStory(formData.version, { story_id: createdId });
                            else if (type === "缺陷") await addVortflowVersionBug(formData.version, { bug_id: createdId });
                            createdItem.version_id = formData.version;
                            createdItem.version_name = dynamicVersionOptions.value.find((v: any) => v.id === formData.version)?.name || "";
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
                clearDraft((propType || formData.type || "缺陷") as WorkItemType);
                createDraftData.value = null;
                if (keepCreating) {
                    createWorkItemRef.value?.reset();
                } else {
                    createWorkItemRef.value?.reset();
                }
                return true;
            } catch (error: any) {
                message.error(error?.message || "新建失败");
                return false;
            } finally {
                isCreating.value = false;
            }
        }
        return true;
    };

    const handleSubmitCreateBug = async (keepCreating = false) => {
        const formData = createWorkItemRef.value?.submit();
        if (!formData) return;
        await handleCreateSuccess(formData, keepCreating);
    };

    // --- Copy ---

    const handleCopyWorkItem = async (record: RowItem | null) => {
        if (!record?.backendId || !unref(useApi)) return;
        try {
            const type = record.type as WorkItemType;
            if (type === "需求") await copyVortflowStory(record.backendId);
            else if (type === "任务") await copyVortflowTask(record.backendId);
            else await copyVortflowBug(record.backendId);
            message.success("复制成功");
            tableRef.value?.refresh?.();
            return true;
        } catch {
            message.error("复制失败");
            return false;
        }
    };

    // --- Detail update (dispatches field changes to API) ---

    const handleDetailUpdate = async (record: RowItem, data: Partial<RowItem>) => {
        if (data.type && unref(useApi) && record.backendId) {
            const fromBackend = _TYPE_TO_BACKEND[record.type];
            const toBackend = _TYPE_TO_BACKEND[data.type];
            if (fromBackend && toBackend && fromBackend !== toBackend) {
                try {
                    const res: any = await convertWorkItem({ from_type: fromBackend, id: record.backendId, to_type: toBackend });
                    if (res?.error) { message.error(res.error); return; }
                    delete itemRowsById[record.backendId];
                    delete itemChildrenMap[record.backendId];
                    delete expandedItemIds[record.backendId];
                    removePinnedRow(record.type as WorkItemType, record.backendId);
                    message.success(res?.message || "类型转换成功");
                    tableRef.value?.refresh?.();
                    return "close";
                } catch {
                    message.error("类型转换失败");
                }
                return;
            }
        }

        Object.assign(record, data);

        if (!unref(useApi) || !record.backendId) return;

        if (data.title !== undefined) {
            await syncRecordUpdateToApi(record, { title: data.title });
        }
        if (data.priority !== undefined) {
            const pMap: Record<string, number> = { urgent: 1, high: 2, medium: 3, low: 4, none: 4 };
            const level = pMap[data.priority] ?? 4;
            if (record.type === "缺陷") {
                await syncRecordUpdateToApi(record, { severity: level });
            } else {
                await syncRecordUpdateToApi(record, { priority: level });
            }
        }
        if (data.status !== undefined) {
            await syncRecordStatusToApi(record, data.status);
        }
        if (data.owner !== undefined || data.collaborators !== undefined) {
            const ownerId = data.owner ? getMemberIdByName(data.owner) || data.owner : undefined;
            const collabIds = data.collaborators?.map(n => getMemberIdByName(n) || n);
            const patch: any = {};
            if (data.owner !== undefined) {
                record.ownerId = ownerId || "";
            }
            if (ownerId !== undefined) {
                if (record.type === "需求") patch.pm_id = ownerId || null;
                else patch.assignee_id = ownerId || null;
            }
            if (collabIds) patch.collaborators = collabIds;
            await syncRecordUpdateToApi(record, patch);
        }
        if (data.description !== undefined) {
            await syncRecordUpdateToApi(record, { description: data.description });
        }
        if (data.planTime !== undefined) {
            const pt = data.planTime;
            const planStart = (pt && pt[0]) ? pt[0] : "";
            const deadline = (pt && pt[1]) ? pt[1] : "";
            await syncRecordUpdateToApi(record, { plan_start: planStart, deadline });
        }
        if (data.progress !== undefined) {
            await syncRecordUpdateToApi(record, { progress: data.progress });
        }
        if (data.estimateHours !== undefined) {
            const value = data.estimateHours === "" || data.estimateHours == null
                ? undefined
                : Number(data.estimateHours);
            await syncRecordUpdateToApi(record, { estimate_hours: value });
        }
        if (data.startAt !== undefined) {
            await syncRecordUpdateToApi(record, { start_at: data.startAt || "" });
        }
        if (data.endAt !== undefined) {
            await syncRecordUpdateToApi(record, { end_at: data.endAt || "" });
        }
        if (data.testTime !== undefined) {
            await syncRecordUpdateToApi(record, { test_time: data.testTime || "" });
        }
        if (data.draftTime !== undefined) {
            await syncRecordUpdateToApi(record, { draft_time: data.draftTime || "" });
        }
        if (data.releaseTime !== undefined) {
            await syncRecordUpdateToApi(record, { release_time: data.releaseTime || "" });
        }
        if (data.repoId !== undefined || data.branch !== undefined) {
            await syncRecordUpdateToApi(record, {
                repo_id: (data.repoId ?? record.repoId ?? "") || null,
                branch: data.branch ?? record.branch ?? "",
            });
        }
        if (data.projectName !== undefined && data.projectId !== undefined) {
            const itemId = getRecordBackendId(record);
            if (itemId) {
                await syncRecordUpdateToApi(record, { project_id: data.projectId || null });
            }
        }
        if (data.iterationId !== undefined || data.iteration !== undefined) {
            const itemId = getRecordBackendId(record);
            if (itemId) {
                const prevIter = record._prevIteration || "";
                const nextIter = data.iterationId ?? record.iterationId ?? "";
                if (prevIter && prevIter !== nextIter) {
                    if (record.type === "需求") await removeVortflowIterationStory(prevIter, itemId).catch(() => {});
                    else if (record.type === "任务") await removeVortflowIterationTask(prevIter, itemId).catch(() => {});
                    else if (record.type === "缺陷") await removeVortflowIterationBug(prevIter, itemId).catch(() => {});
                }
                if (nextIter && nextIter !== prevIter) {
                    if (record.type === "需求") await addVortflowIterationStory(nextIter, { story_id: itemId }).catch(() => {});
                    else if (record.type === "任务") await addVortflowIterationTask(nextIter, { task_id: itemId }).catch(() => {});
                    else if (record.type === "缺陷") await addVortflowIterationBug(nextIter, { bug_id: itemId }).catch(() => {});
                }
                record._prevIteration = nextIter;
            }
        }
        if (data.versionId !== undefined || data.version !== undefined) {
            const itemId = getRecordBackendId(record);
            if (itemId) {
                const prevVer = record._prevVersion || "";
                const nextVer = data.versionId ?? record.versionId ?? "";
                if (prevVer && prevVer !== nextVer) {
                    if (record.type === "需求") await removeVortflowVersionStory(prevVer, itemId).catch(() => {});
                    else if (record.type === "缺陷") await removeVortflowVersionBug(prevVer, itemId).catch(() => {});
                }
                if (nextVer && nextVer !== prevVer) {
                    if (record.type === "需求") await addVortflowVersionStory(nextVer, { story_id: itemId }).catch(() => {});
                    else if (record.type === "缺陷") await addVortflowVersionBug(nextVer, { bug_id: itemId }).catch(() => {});
                }
                record._prevVersion = nextVer;
            }
        }
        if (data.attachments !== undefined) {
            await syncRecordUpdateToApi(record, { attachments: data.attachments });
        }
    };

    // --- Unlink child ---

    const handleUnlinkChild = async (child: RowItem, currentRecord: RowItem | null, syncRelations: (rec: RowItem) => Promise<void>) => {
        if (!child.backendId) return;
        try {
            const id = String(child.backendId);
            if (child.type === "需求") {
                await updateVortflowStory(id, { parent_id: null });
            } else if (child.type === "任务") {
                await updateVortflowTask(id, { parent_id: null });
            }
            message.success("已取消关联");
            if (currentRecord) await syncRelations(currentRecord);
            tableRef.value?.refresh?.();
        } catch {
            message.error("取消关联失败");
        }
    };

    // --- Attachment helpers ---

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
                size: file.size,
            });
        }
        createBugAttachments.value = next;
        target.value = "";
    };

    const removeCreateAttachment = (id: string) => {
        createBugAttachments.value = createBugAttachments.value.filter((x) => x.id !== id);
    };

    return {
        selectedRowKeys,
        selectedRows,
        createParentItemId,
        createProjectId,
        createDraftData,
        isCreating,
        createBugAttachments,
        createAttachmentInputRef,
        createBugForm,
        createParentRecord,
        createInitialBugForm,
        resetCreateBugForm,
        resolveCreateProjectId,
        rowSelection,
        clearSelection,
        getRecordBackendId,
        syncRecordUpdateToApi,
        syncRecordStatusToApi,
        deleteOne,
        handleBatchDelete,
        handleBatchArchive,
        handleBatchUnarchive,
        handleCreateSuccess,
        handleSubmitCreateBug,
        handleCopyWorkItem,
        handleDetailUpdate,
        handleUnlinkChild,
        openCreateAttachmentDialog,
        onCreateAttachmentChange,
        removeCreateAttachment,
    };
}
