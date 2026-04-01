import { computed, reactive, ref, type Ref } from "vue";
import { message } from "@openvort/vort-ui";
import type {
    WorkItemType,
    Priority,
    DateRange,
    RowItem,
    NewBugForm,
    DetailComment,
    DetailLog,
} from "@/components/vort-biz/work-item/WorkItemTable.types";

export interface UseWorkItemDetailPanelOptions {
    useApi: Ref<boolean> | boolean;
    syncRecordUpdateToApi: (record: RowItem, patch: any) => Promise<void>;
    loadItemById: (id: string | undefined, type: WorkItemType | string) => Promise<RowItem | null>;
    loadChildItems: (parentId: string, type: string, projectId?: string) => Promise<RowItem[]>;
    getRowPriority: (record: RowItem, text?: Priority) => Priority;
    getRowTags: (record: RowItem, text?: string[]) => string[];
    planTimeModel: Record<string, any>;
}

export function useWorkItemDetailPanel(options: UseWorkItemDetailPanelOptions) {
    const {
        syncRecordUpdateToApi,
        loadItemById,
        loadChildItems,
        getRowPriority,
        getRowTags,
        planTimeModel,
    } = options;

    const detailActiveTab = ref("detail");
    const detailSelectedWorkNo = ref("");
    const detailDescEditing = ref(false);
    const detailDescDraft = ref("");
    const detailDescDraftCache = reactive<Record<string, string>>({});
    const detailBottomTab = ref<"comments" | "logs">("comments");
    const detailCommentDraft = ref("");
    const detailCommentsMap = reactive<Record<string, DetailComment[]>>({});
    const detailLogsMap = reactive<Record<string, DetailLog[]>>({});
    const detailRecordSnapshot = ref<RowItem | null>(null);
    const detailComponentRef = ref<any>(null);
    const detailParentRecord = ref<RowItem | null>(null);
    const detailChildRecords = ref<RowItem[]>([]);

    const detailCurrentUser = "当前用户";

    const detailCurrentRecord = computed<RowItem | null>(() => {
        if (!detailSelectedWorkNo.value) return null;
        if (detailRecordSnapshot.value?.workNo === detailSelectedWorkNo.value) {
            return detailRecordSnapshot.value;
        }
        return detailRecordSnapshot.value || null;
    });

    const detailComments = computed<DetailComment[]>(() => {
        const workNo = detailSelectedWorkNo.value;
        if (!workNo) return [];
        return detailCommentsMap[workNo] || [];
    });

    const detailLogs = computed<DetailLog[]>(() => {
        const workNo = detailSelectedWorkNo.value;
        if (!workNo) return [];
        return detailLogsMap[workNo] || [];
    });

    const ensureDetailPanelsData = (record: RowItem) => {
        if (!detailCommentsMap[record.workNo]) {
            detailCommentsMap[record.workNo] = [];
        }
        if (!detailLogsMap[record.workNo]) {
            detailLogsMap[record.workNo] = [];
        }
    };

    const appendDetailLog = (action: string) => {
        const workNo = detailSelectedWorkNo.value;
        if (!workNo) return;
        if (!detailLogsMap[workNo]) detailLogsMap[workNo] = [];
        detailLogsMap[workNo].unshift({
            id: `${workNo}-l-${Date.now()}`,
            actor: detailCurrentUser,
            createdAt: "刚刚",
            action,
        });
    };

    const submitDetailComment = () => {
        const workNo = detailSelectedWorkNo.value;
        const content = detailCommentDraft.value.trim();
        if (!workNo || !content) {
            message.warning("请先输入评论内容");
            return;
        }
        if (!detailCommentsMap[workNo]) detailCommentsMap[workNo] = [];
        detailCommentsMap[workNo].unshift({
            id: `${workNo}-c-${Date.now()}`,
            author: detailCurrentUser,
            createdAt: "刚刚",
            content,
        });
        detailCommentDraft.value = "";
        appendDetailLog("发布评论");
        message.success("评论已发布");
    };

    const openDetailDescEditor = () => {
        if (!detailCurrentRecord.value) return;
        detailDescDraft.value = detailCurrentRecord.value.description || "";
        detailDescEditing.value = true;
    };

    const cancelDetailDescEditor = () => {
        detailDescEditing.value = false;
        detailDescDraft.value = "";
        if (detailSelectedWorkNo.value) delete detailDescDraftCache[detailSelectedWorkNo.value];
    };

    const saveDetailDescEditor = async () => {
        if (!detailCurrentRecord.value) return;
        const record = detailCurrentRecord.value;
        const prev = record.description || "";
        const next = detailDescDraft.value || "";
        record.description = next;
        try {
            await syncRecordUpdateToApi(record, { description: next });
        } catch (error: any) {
            record.description = prev;
            message.error(error?.message || "描述同步失败");
            return;
        }
        detailDescEditing.value = false;
        if (detailSelectedWorkNo.value) delete detailDescDraftCache[detailSelectedWorkNo.value];
        appendDetailLog("更新描述");
        message.success("描述已保存");
    };

    const syncDetailRelations = async (record: RowItem) => {
        if (record.type !== "需求" && record.type !== "任务") {
            detailParentRecord.value = null;
            detailChildRecords.value = [];
            return;
        }
        detailParentRecord.value = await loadItemById(record.parentId, record.type);
        if (record.backendId && record.childrenCount) {
            detailChildRecords.value = await loadChildItems(record.backendId, record.type, record.projectId);
        } else {
            detailChildRecords.value = [];
        }
    };

    const cacheDescDraftBeforeClose = () => {
        const comp = detailComponentRef.value;
        if (comp?.detailDescEditing && detailSelectedWorkNo.value) {
            detailDescDraftCache[detailSelectedWorkNo.value] = comp.detailDescDraft;
        }
    };

    const prepareDetailView = async (record: RowItem) => {
        detailSelectedWorkNo.value = record.workNo;
        detailRecordSnapshot.value = record;
        detailActiveTab.value = "detail";
        detailBottomTab.value = "comments";
        detailCommentDraft.value = "";
        const cachedDraft = detailDescDraftCache[record.workNo];
        if (cachedDraft !== undefined) {
            detailDescEditing.value = true;
            detailDescDraft.value = cachedDraft;
            delete detailDescDraftCache[record.workNo];
        } else {
            detailDescEditing.value = false;
            detailDescDraft.value = "";
        }
        ensureDetailPanelsData(record);
        await syncDetailRelations(record);

        return {
            priority: getRowPriority(record, record.priority),
            tags: getRowTags(record, record.tags),
            planTime: planTimeModel[record.workNo] || record.planTime,
        };
    };

    const handleOpenRelated = async (partial: any, openDetail: (record: RowItem) => void) => {
        if (partial?.workNo) {
            openDetail(partial as RowItem);
            return;
        }
        const id = partial?.backendId || partial?.id;
        const itemType = partial?.type as WorkItemType;
        if (!id || !itemType) return;
        const full = await loadItemById(id, itemType);
        if (full) openDetail(full);
    };

    return {
        detailActiveTab,
        detailSelectedWorkNo,
        detailDescEditing,
        detailDescDraft,
        detailDescDraftCache,
        detailBottomTab,
        detailCommentDraft,
        detailCommentsMap,
        detailLogsMap,
        detailRecordSnapshot,
        detailComponentRef,
        detailParentRecord,
        detailChildRecords,
        detailCurrentRecord,
        detailComments,
        detailLogs,
        ensureDetailPanelsData,
        appendDetailLog,
        submitDetailComment,
        openDetailDescEditor,
        cancelDetailDescEditor,
        saveDetailDescEditor,
        syncDetailRelations,
        cacheDescDraftBeforeClose,
        prepareDetailView,
        handleOpenRelated,
    };
}
