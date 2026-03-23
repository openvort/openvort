<script setup lang="ts">
import { ref, computed, reactive, onMounted, watch, nextTick } from "vue";
import { message } from "@/components/vort";
import WorkItemMemberPicker from "@/components/vort-biz/work-item/WorkItemMemberPicker.vue";
import WorkItemStatus from "@/components/vort-biz/work-item/WorkItemStatus.vue";
import VortEditor from "@/components/vort-biz/editor/VortEditor.vue";
import MarkdownView from "@/components/vort-biz/editor/MarkdownView.vue";
import { Copy, SquarePen, FileText, Bot, Loader2, Bell } from "lucide-vue-next";
import { useInlineAi } from "@/hooks";
import { useWorkItemCommon } from "./useWorkItemCommon";
import WorkItemLinkPanel from "./WorkItemLinkPanel.vue";
import TestCaseLinkPanel from "./TestCaseLinkPanel.vue";
import NotifyDialog from "./NotifyDialog.vue";
import { getVortflowProjects, getVortflowIterations, getVortflowVersions, getVortgitRepos, getVortgitRepoBranches, getVortflowComments, createVortflowComment, getVortflowActivity } from "@/api";
import { useUserStore } from "@/stores";
import type { WorkItemType, Status, DateRange, RowItem, DetailComment, DetailLog } from "@/components/vort-biz/work-item/WorkItemTable.types";

interface Props {
    workNo: string;
    initialData?: RowItem;
    parentRecord?: RowItem | null;
    childRecords?: RowItem[];
    initialDescDraft?: string;
    initialDescEditing?: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
    close: [];
    update: [data: Partial<RowItem>];
    delete: [];
    openRelated: [record: RowItem];
    createChild: [record: RowItem];
}>();

const {
    ownerGroups,
    getStatusOptionsByType,
    getStatusOption,
    getAvatarBg,
    getAvatarLabel,
    getMemberAvatarUrl,
    loadMemberOptions,
    getMemberIdByName,
    getMemberNameById,
    getWorkItemTypeIconClass,
    getWorkItemTypeIconSymbol,
} = useWorkItemCommon();

const userStore = useUserStore();
const detailCurrentUser = computed(() => userStore.userInfo.name || "未知用户");
const loading = ref(false);
const record = ref<RowItem | null>(props.initialData || null);
const detailActiveTab = ref("detail");
const detailBottomTab = ref<"comments" | "logs">("comments");
const detailStatusDropdownOpen = ref(false);
const detailStatusKeyword = ref("");
const detailAssigneeDropdownOpen = ref(false);
const detailAssigneeKeyword = ref("");
const detailAssigneeGroupOpen = reactive<Record<string, boolean>>({});
const detailDescEditing = ref(props.initialDescEditing || false);
const detailDescDraft = ref(props.initialDescDraft ?? "");

defineExpose({ detailDescEditing, detailDescDraft });
const notifyDialogOpen = ref(false);
const detailCommentDraft = ref("");
const detailCommentsMap = reactive<Record<string, DetailComment[]>>({});
const detailLogsMap = reactive<Record<string, DetailLog[]>>({});

const detailCurrentRecord = computed(() => record.value);
const parentRecord = computed(() => props.parentRecord || null);
const childRecords = computed(() => props.childRecords || []);
const isHierarchyRecord = computed(() => record.value?.type === "需求" || record.value?.type === "任务");
const canCreateChild = computed(() => Boolean(record.value?.backendId) && isHierarchyRecord.value);
const linkEntityType = computed<"story" | "task" | "bug">(() => {
    const t = record.value?.type;
    if (t === "需求") return "story";
    if (t === "任务") return "task";
    return "bug";
});
const childItemLabel = computed(() => record.value?.type === "任务" ? "子任务" : "子需求");
const addChildLabel = computed(() => record.value?.type === "任务" ? "添加子任务" : "添加子需求");
const emptyChildText = computed(() => `暂无关联的${childItemLabel.value}`);

const handleCopyDetailLink = async () => {
    const link = window.location.href;
    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(link);
        } else {
            const input = document.createElement("input");
            input.value = link;
            document.body.appendChild(input);
            input.select();
            document.execCommand("copy");
            document.body.removeChild(input);
        }
        message.success("链接已复制");
    } catch {
        message.error("复制链接失败");
    }
};

const detailComments = computed(() => {
    if (!props.workNo) return [];
    return detailCommentsMap[props.workNo] || [];
});

const detailLogs = computed(() => {
    if (!props.workNo) return [];
    return detailLogsMap[props.workNo] || [];
});

const filteredDetailStatusOptions = computed(() => {
    const type = record.value?.type || "缺陷";
    const options = getStatusOptionsByType(type);
    const kw = detailStatusKeyword.value.trim().toLowerCase();
    if (!kw) return options;
    return options.filter((opt) => opt.label.toLowerCase().includes(kw));
});

const filteredDetailAssigneeGroups = computed(() => {
    const groups = ownerGroups.value;
    const kw = detailAssigneeKeyword.value.trim();
    if (!kw) return groups;
    return groups
        .map((g) => ({
            ...g,
            members: g.members.filter((m) => m.includes(kw))
        }))
        .filter((g) => g.members.length > 0);
});

const formatTimeAgo = (isoStr: string): string => {
    if (!isoStr) return "";
    const d = new Date(isoStr);
    const now = Date.now();
    const diff = now - d.getTime();
    if (diff < 60_000) return "刚刚";
    if (diff < 3600_000) return `${Math.floor(diff / 60_000)}分钟前`;
    if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}小时前`;
    const month = d.getMonth() + 1;
    const day = d.getDate();
    const h = String(d.getHours()).padStart(2, "0");
    const m = String(d.getMinutes()).padStart(2, "0");
    return `${month}月${day}日 ${h}:${m}`;
};

const FIELD_LABEL_MAP: Record<string, string> = {
    title: "名称", description: "描述", state: "状态", priority: "优先级",
    assignee_id: "负责人", pm_id: "负责人", estimate_hours: "预估工时",
    actual_hours: "实际工时", tags: "标签", collaborators: "协作者",
    deadline: "截止日期", project_id: "项目", start_at: "开始时间",
    end_at: "结束时间", repo_id: "关联仓库", branch: "关联分支",
    severity: "严重程度", task_type: "任务类型", parent_id: "父级",
};

const LONG_TEXT_FIELDS = new Set(["description"]);

const STATE_LABEL_MAP: Record<string, string> = {
    intake: "意向", review: "评审", rejected: "已取消",
    pm_refine: "需求细化", design: "设计中", breakdown: "任务拆解",
    dev_assign: "待分配", in_progress: "进行中", testing: "测试中",
    bugfix: "修复缺陷", done: "已完成",
    todo: "待办的", closed: "已关闭",
    open: "待确认", confirmed: "已确认",
    fixing: "修复中", resolved: "已修复", verified: "已验证",
};

const formatFieldValue = (key: string, value: any): string => {
    if (value == null || value === "") return "空";
    if (LONG_TEXT_FIELDS.has(key)) return "（已更新）";
    if (key === "assignee_id" || key === "pm_id") return getMemberNameById(String(value)) || String(value);
    if (key === "collaborators" && Array.isArray(value)) return value.map(v => getMemberNameById(String(v)) || String(v)).join("、") || "空";
    if (key === "tags" && Array.isArray(value)) return value.join("、") || "空";
    if (key === "state") return STATE_LABEL_MAP[String(value)] || String(value);
    if (key === "priority") {
        const m: Record<number, string> = { 1: "紧急", 2: "高", 3: "中", 4: "低" };
        return m[value] || String(value);
    }
    if (key === "severity") {
        const m: Record<number, string> = { 1: "致命", 2: "严重", 3: "一般", 4: "轻微" };
        return m[value] || String(value);
    }
    return String(value);
};

const formatActivityAction = (action: string, detailRaw: any): string => {
    let detail: Record<string, any> = {};
    if (typeof detailRaw === "string") {
        try { detail = JSON.parse(detailRaw); } catch { /* ignore */ }
    } else if (detailRaw && typeof detailRaw === "object") {
        detail = detailRaw;
    }
    if (action === "created") {
        const title = detail.title ? `「${detail.title}」` : "";
        return `创建了工作项${title}`;
    }
    if (action === "state_changed") {
        const fromLabel = STATE_LABEL_MAP[detail.from] || detail.from || "?";
        const toLabel = STATE_LABEL_MAP[detail.to] || detail.to || "?";
        return `将状态从"${fromLabel}"修改为"${toLabel}"`;
    }
    if (action === "updated") {
        const keys = Object.keys(detail);
        if (!keys.length) return "更新了工作项";
        const parts = keys.map(k => {
            const label = FIELD_LABEL_MAP[k] || k;
            const val = formatFieldValue(k, detail[k]);
            return `${label}→"${val}"`;
        });
        return `修改了${parts.join("、")}`;
    }
    if (action === "deleted") return `删除了工作项${detail.title ? `「${detail.title}」` : ""}`;
    if (action === "comment_added") return `添加了评论`;
    if (action === "link_added") return `添加了关联工作项`;
    if (action === "link_removed") return `移除了关联工作项`;
    return action;
};

const ensureDetailPanelsData = async () => {
    const entityId = record.value?.backendId;
    if (!entityId) {
        if (!detailCommentsMap[props.workNo]) detailCommentsMap[props.workNo] = [];
        if (!detailLogsMap[props.workNo]) detailLogsMap[props.workNo] = [];
        return;
    }
    const entityType = getEntityTypeKey();
    const [commentsRes, activityRes] = await Promise.allSettled([
        getVortflowComments(entityType, entityId),
        getVortflowActivity(entityType, entityId),
    ]);
    if (commentsRes.status === "fulfilled") {
        const items = ((commentsRes.value as any)?.items || []) as any[];
        detailCommentsMap[props.workNo] = items.map((c: any) => ({
            id: String(c.id),
            author: getMemberNameById(c.author_id) || c.author_id || "未知",
            createdAt: formatTimeAgo(c.created_at),
            content: c.content || "",
        }));
    } else {
        if (!detailCommentsMap[props.workNo]) detailCommentsMap[props.workNo] = [];
    }
    if (activityRes.status === "fulfilled") {
        const items = ((activityRes.value as any)?.items || []) as any[];
        detailLogsMap[props.workNo] = items.map((e: any) => ({
            id: String(e.id),
            actor: getMemberNameById(e.actor_id) || e.actor_id || "系统",
            createdAt: formatTimeAgo(e.created_at),
            action: formatActivityAction(e.action, e.detail),
        }));
    } else {
        if (!detailLogsMap[props.workNo]) detailLogsMap[props.workNo] = [];
    }
};

const appendDetailLog = (action: string) => {
    if (!detailLogsMap[props.workNo]) detailLogsMap[props.workNo] = [];
    const logs = detailLogsMap[props.workNo];
    if (!logs) return;
    logs.unshift({
        id: `${props.workNo}-l-${Date.now()}`,
        actor: detailCurrentUser.value,
        createdAt: "刚刚",
        action
    });
};

const toggleDetailStatusMenu = () => {
    detailStatusDropdownOpen.value = !detailStatusDropdownOpen.value;
    if (!detailStatusDropdownOpen.value) detailStatusKeyword.value = "";
};

const toggleDetailAssigneeMenu = () => {
    detailAssigneeDropdownOpen.value = !detailAssigneeDropdownOpen.value;
    if (!detailAssigneeDropdownOpen.value) detailAssigneeKeyword.value = "";
};

const toggleDetailAssigneeGroup = (group: string) => {
    detailAssigneeGroupOpen[group] = !detailAssigneeGroupOpen[group];
};

const selectDetailStatus = async (value: Status) => {
    if (!record.value) return;
    const prevStatus = record.value.status;
    record.value.status = value;
    detailStatusDropdownOpen.value = false;
    detailStatusKeyword.value = "";
    appendDetailLog(`将状态修改为"${value}"`);
    emit("update", { status: value });
};

const isDetailOwner = (member: string): boolean => {
    return record.value?.owner === member;
};

const isDetailCollaborator = (member: string): boolean => {
    return (record.value?.collaborators || []).includes(member);
};

const setDetailOwner = async (member: string) => {
    if (!record.value) return;
    const prev = record.value.owner;
    const nextOwner = member || "未指派";
    record.value.owner = nextOwner;
    detailAssigneeDropdownOpen.value = false;
    detailAssigneeKeyword.value = "";
    appendDetailLog(`将负责人修改为"${nextOwner}"`);
    emit("update", { owner: nextOwner });
};

const toggleDetailCollaborator = async (member: string) => {
    if (!record.value) return;
    const collaborators = [...record.value.collaborators];
    const idx = collaborators.indexOf(member);
    if (idx >= 0) {
        collaborators.splice(idx, 1);
        appendDetailLog(`取消协作者"${member}"`);
    } else {
        collaborators.push(member);
        appendDetailLog(`添加协作者"${member}"`);
    }
    record.value.collaborators = collaborators;
    emit("update", { collaborators });
};

const setDetailCollaborators = async (nextCollaborators: string[]) => {
    if (!record.value) return;
    const prev = [...record.value.collaborators];
    record.value.collaborators = [...nextCollaborators];
    try {
        emit("update", { collaborators: [...nextCollaborators] });
    } catch {
        record.value.collaborators = prev;
    }
};

const openDetailDescEditor = () => {
    detailDescDraft.value = record.value?.description || "";
    detailDescEditing.value = true;
};

const saveDetailDescEditor = () => {
    if (!record.value) return;
    record.value.description = detailDescDraft.value;
    detailDescEditing.value = false;
    appendDetailLog("更新了描述");
    emit("update", { description: detailDescDraft.value });
};

const cancelDetailDescEditor = () => {
    detailDescEditing.value = false;
    detailDescDraft.value = "";
    descAi.clear();
};

// ---- AI enrich description ----
const descAi = useInlineAi({ sessionName: "描述完善助手" });

const descAiPhaseLabel = computed(() => {
    switch (descAi.phase.value) {
        case "thinking": return "思考中";
        case "tool_running": return "正在查询项目信息";
        case "generating": return "生成中";
        default: return "处理中";
    }
});

const aiEnrichBtnLabel = computed(() => {
    const type = record.value?.type || "需求";
    return `AI 完善${type}描述`;
});

const extractImageRefs = (content: string): string[] => {
    const images: string[] = [];
    const mdImg = /!\[[^\]]*\]\([^)]+\)/g;
    let m: RegExpExecArray | null;
    while ((m = mdImg.exec(content)) !== null) images.push(m[0]);
    const htmlImg = /<img[^>]+>/gi;
    while ((m = htmlImg.exec(content)) !== null) images.push(m[0]);
    return images;
};

const getStructureByType = (type: string): string => {
    switch (type) {
        case "缺陷":
            return `- **问题描述**：清晰描述缺陷的具体现象
- **复现步骤**：列出重现该缺陷的详细操作步骤（1. 2. 3. ...）
- **预期结果**：正常情况下应该出现的结果
- **实际结果**：当前实际出现的错误现象
- **影响范围**：该缺陷影响的功能模块和严重程度`;
        case "任务":
            return `- **任务目标**：明确说明本任务要达成的目标
- **实现方案**：列出具体的实施步骤或技术方案
- **完成标准**：明确可验证的交付标准
- **依赖与注意事项**：前置依赖、风险点或需要注意的事项`;
        default:
            return `- **需求背景**：为什么需要做这个需求
- **用户故事**：作为___，我希望___，以便___
- **验收标准**：列出具体可验证的验收条件
- **技术要点**：关键的技术实现方向（如果能判断）`;
    }
};

const buildDescEnrichPrompt = () => {
    if (!record.value) return "";
    const title = record.value.title || "";
    const desc = detailDescDraft.value || record.value.description || "";
    const project = record.value.projectName || "";
    const type = record.value.type || "需求";

    const images = extractImageRefs(desc);
    const imagePart = images.length > 0
        ? `\n\n重要：原描述中包含 ${images.length} 张图片，你必须在输出中原样保留所有图片引用（不要修改图片语法或 URL），将它们放在最相关的段落位置：\n${images.map((img, i) => `${i + 1}. ${img}`).join("\n")}`
        : "";

    const descPart = desc.trim()
        ? `当前已有描述：\n${desc}\n\n请在此基础上完善和补充。`
        : "（暂无描述内容）";

    const structure = getStructureByType(type);

    return `请帮我完善以下${type}的描述内容。

${type}标题：${title}
所属项目：${project || "未设置"}
${descPart}

请生成一份结构清晰的${type}描述，可以包含以下结构（按需裁剪）：
${structure}

如果需要了解项目的业务背景，你可以查询项目信息或关联的代码仓库来获取更多上下文。${imagePart}
请直接输出 Markdown 格式的描述内容，不要包含${type}标题。`;
};

const startAiEnrichDesc = () => {
    if (!detailDescEditing.value) {
        openDetailDescEditor();
    }
    const prompt = buildDescEnrichPrompt();
    if (!prompt) return;
    descAi.run(prompt);
};

const applyAiDesc = () => {
    if (!descAi.text.value) return;
    detailDescDraft.value = descAi.text.value;
    descAi.clear();
};

// ---- AI supplement prompt builder ----
const buildSupplementPrompt = () => {
    if (!record.value) return "";
    const r = record.value;
    const fields = [
        `负责人：${r.owner || "未指派"}`,
        `计划时间：${r.planTime?.[0] && r.planTime?.[1] ? `${r.planTime[0]} ~ ${r.planTime[1]}` : "未设置"}`,
        `迭代：${r.iteration || "未设置"}`,
        `版本：${r.version || "未设置"}`,
        `预估工时：${r.estimateHours != null ? r.estimateHours + " 小时" : "未设置"}`,
    ].join("\n");

    return `请帮我补充${r.type}「${r.title}」(${r.workNo}) 的详细信息。

所属项目：${r.projectName || "未设置"}
当前字段：
${fields}

请根据${r.type}标题、描述和项目上下文，帮我合理补充以上尚未设置的字段。你可以：
1. 先查询项目信息了解团队成员、迭代计划、版本规划
2. 查看关联的代码仓库了解技术背景
3. 参考同项目其他${r.type}的设置

然后使用工具逐个更新这些字段。每个字段请先简要说明理由再操作。`;
};

const getEntityTypeKey = (): string => {
    const type = record.value?.type;
    if (type === "需求") return "story";
    if (type === "任务") return "task";
    return "bug";
};

const submitDetailComment = async () => {
    const content = detailCommentDraft.value.trim();
    if (!content) {
        message.warning("请先输入评论内容");
        return;
    }
    const entityId = record.value?.backendId;
    if (!entityId) return;
    try {
        const res: any = await createVortflowComment(getEntityTypeKey(), entityId, { content });
        if (!detailCommentsMap[props.workNo]) detailCommentsMap[props.workNo] = [];
        detailCommentsMap[props.workNo].unshift({
            id: String(res?.id || `${props.workNo}-c-${Date.now()}`),
            author: detailCurrentUser.value,
            createdAt: "刚刚",
            content,
        });
        detailCommentDraft.value = "";
        message.success("评论已发布");
    } catch (error: any) {
        message.error(error?.message || "评论发布失败");
    }
};

// ---- Editable field options ----
const apiProjects = ref<Array<{ id: string; name: string }>>([]);
const apiIterations = ref<Array<{ id: string; name: string }>>([]);
const apiVersions = ref<Array<{ id: string; name: string }>>([]);
const apiRepos = ref<Array<{ id: string; name: string }>>([]);
const apiBranches = ref<Array<{ name: string }>>([]);
const branchLoading = ref(false);

const formatDate = (value: Date) => {
    const y = value.getFullYear();
    const m = String(value.getMonth() + 1).padStart(2, "0");
    const d = String(value.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
};

const normalizeDateValue = (value: unknown): string => {
    if (value instanceof Date) return formatDate(value);
    if (typeof value === "string") {
        const direct = value.trim();
        if (!direct) return "";
        if (/^\d{4}-\d{2}-\d{2}$/.test(direct)) return direct;
        const parsed = new Date(direct);
        if (!Number.isNaN(parsed.getTime())) return formatDate(parsed);
    }
    return "";
};

const loadBranchOptions = async (repoId?: string) => {
    if (!repoId) {
        apiBranches.value = [];
        return;
    }
    branchLoading.value = true;
    try {
        const res: any = await getVortgitRepoBranches(repoId);
        apiBranches.value = ((res?.items || []) as any[])
            .map((item) => ({ name: String(item.name || "") }))
            .filter((item) => item.name);
    } catch {
        apiBranches.value = [];
    } finally {
        branchLoading.value = false;
    }
};

const loadFieldOptions = async () => {
    const projectId = record.value?.projectId || "";
    const [projRes, iterRes, verRes, repoRes] = await Promise.allSettled([
        getVortflowProjects(),
        projectId ? getVortflowIterations({ project_id: projectId, page: 1, page_size: 100 }) : Promise.resolve({ items: [] }),
        projectId ? getVortflowVersions({ project_id: projectId, page: 1, page_size: 100 }) : Promise.resolve({ items: [] }),
        projectId ? getVortgitRepos({ project_id: projectId, page: 1, page_size: 100 }) : Promise.resolve({ items: [] }),
    ]);
    if (projRes.status === "fulfilled") {
        apiProjects.value = ((projRes.value as any)?.items || []).map((p: any) => ({ id: String(p.id), name: String(p.name || p.id) }));
    }
    if (iterRes.status === "fulfilled") {
        apiIterations.value = ((iterRes.value as any)?.items || []).map((p: any) => ({ id: String(p.id), name: String(p.name || p.id) }));
    }
    if (verRes.status === "fulfilled") {
        apiVersions.value = ((verRes.value as any)?.items || []).map((p: any) => ({ id: String(p.id), name: String(p.name || p.id) }));
    }
    if (repoRes.status === "fulfilled") {
        apiRepos.value = ((repoRes.value as any)?.items || []).map((item: any) => ({
            id: String(item.id || ""),
            name: String(item.name || item.full_name || item.id || ""),
        })).filter((item: { id: string; name: string }) => item.id && item.name);
    }
    syncDetailLinkedLabels();
    syncDetailRepoLabel();
    await loadBranchOptions(record.value?.repoId || "");
};

const detailPlanTimeModel = computed<any>({
    get: () => {
        if (!record.value) return undefined;
        const pt = record.value.planTime;
        return pt && pt.length === 2 && pt[0] ? [pt[0], pt[1]] as DateRange : undefined;
    },
    set: (value) => {
        if (!record.value) return;
        if (Array.isArray(value) && value.length === 2) {
            record.value.planTime = [String(value[0] || ""), String(value[1] || "")] as DateRange;
        } else {
            record.value.planTime = ["", ""];
        }
        emit("update", { planTime: record.value.planTime });
        appendDetailLog("修改了计划时间");
    },
});

const detailProjectName = computed({
    get: () => record.value?.projectName || "",
    set: (val: string) => {
        if (!record.value) return;
        const match = apiProjects.value.find(p => p.name === val);
        record.value.projectName = val;
        if (match) record.value.projectId = match.id;
        emit("update", { projectName: val, projectId: match?.id });
        appendDetailLog(`修改项目为"${val}"`);
        loadProjectLinkedOptions(match?.id || "");
    },
});

const detailIteration = computed({
    get: () => record.value?.iterationId || "",
    set: (val: string) => {
        if (!record.value) return;
        const nextId = String(val || "");
        const name = apiIterations.value.find(i => i.id === nextId)?.name || "";
        record.value.iterationId = nextId;
        record.value.iteration = name;
        emit("update", { iterationId: nextId, iteration: name });
        const label = name || "未设置";
        appendDetailLog(`修改迭代为"${label}"`);
    },
});

const detailVersion = computed({
    get: () => record.value?.versionId || "",
    set: (val: string) => {
        if (!record.value) return;
        const nextId = String(val || "");
        const name = apiVersions.value.find(v => v.id === nextId)?.name || "";
        record.value.versionId = nextId;
        record.value.version = name;
        emit("update", { versionId: nextId, version: name });
        const label = name || "未设置";
        appendDetailLog(`修改版本为"${label}"`);
    },
});

const syncDetailLinkedLabels = () => {
    if (!record.value) return;
    if (record.value.iterationId && !record.value.iteration) {
        record.value.iteration = apiIterations.value.find((item) => item.id === record.value?.iterationId)?.name || "";
    }
    if (record.value.versionId && !record.value.version) {
        record.value.version = apiVersions.value.find((item) => item.id === record.value?.versionId)?.name || "";
    }
};

const syncDetailRepoLabel = () => {
    if (!record.value) return;
    if (record.value.repoId) {
        record.value.repo = apiRepos.value.find((item) => item.id === record.value?.repoId)?.name || record.value.repo || "";
    }
};

const detailEstimateHours = computed<number | undefined>({
    get: () => {
        if (!record.value?.estimateHours && record.value?.estimateHours !== 0) return undefined;
        return Number(record.value.estimateHours);
    },
    set: (value) => {
        if (!record.value) return;
        const next = value == null ? undefined : Number(value);
        record.value.estimateHours = next;
        if (record.value.loggedHours != null && next != null) {
            record.value.remainHours = Math.max(0, next - Number(record.value.loggedHours || 0));
        } else if (next == null) {
            record.value.remainHours = undefined;
        }
        emit("update", { estimateHours: next });
        appendDetailLog(`修改预估工时为"${next ?? "未设置"}h"`);
    },
});

const detailRepoId = computed({
    get: () => record.value?.repoId || "",
    set: (val: string) => {
        if (!record.value) return;
        const nextId = String(val || "");
        const nextRepo = apiRepos.value.find((item) => item.id === nextId)?.name || "";
        const repoChanged = nextId !== (record.value.repoId || "");
        record.value.repoId = nextId;
        record.value.repo = nextRepo;
        if (repoChanged) {
            record.value.branch = "";
        }
        emit("update", {
            repoId: nextId,
            repo: nextRepo,
            branch: repoChanged ? "" : record.value.branch || "",
        });
        appendDetailLog(`修改关联仓库为"${nextRepo || "未设置"}"`);
        loadBranchOptions(nextId);
    },
});

const detailBranch = computed({
    get: () => record.value?.branch || "",
    set: (val: string) => {
        if (!record.value) return;
        const nextBranch = String(val || "");
        record.value.branch = nextBranch;
        emit("update", { branch: nextBranch });
        appendDetailLog(`修改关联分支为"${nextBranch || "未设置"}"`);
    },
});

const detailActualTimeModel = computed<any>({
    get: () => {
        if (!record.value) return undefined;
        const s = record.value.startAt || "";
        const e = record.value.endAt || "";
        return s || e ? [s, e] as DateRange : undefined;
    },
    set: (value) => {
        if (!record.value) return;
        if (Array.isArray(value) && value.length === 2) {
            const startAt = normalizeDateValue(String(value[0] || ""));
            const endAt = normalizeDateValue(String(value[1] || ""));
            record.value.startAt = startAt;
            record.value.endAt = endAt;
            emit("update", { startAt, endAt });
        } else {
            record.value.startAt = "";
            record.value.endAt = "";
            emit("update", { startAt: "", endAt: "" });
        }
        appendDetailLog("修改了实际时间");
    },
});

const detailType = computed({
    get: () => record.value?.type || "缺陷",
    set: (val: string) => {
        if (!record.value || val === record.value.type) return;
        record.value.type = val as WorkItemType;
        emit("update", { type: val as WorkItemType });
        appendDetailLog(`修改类型为"${val}"`);
    },
});

const loadProjectLinkedOptions = async (projectId?: string) => {
    const pid = projectId || record.value?.projectId || "";
    if (!pid) return;
    const [iterRes, verRes, repoRes] = await Promise.allSettled([
        getVortflowIterations({ project_id: pid, page: 1, page_size: 100 }),
        getVortflowVersions({ project_id: pid, page: 1, page_size: 100 }),
        getVortgitRepos({ project_id: pid, page: 1, page_size: 100 }),
    ]);
    if (iterRes.status === "fulfilled") {
        apiIterations.value = ((iterRes.value as any)?.items || []).map((p: any) => ({ id: String(p.id), name: String(p.name || p.id) }));
    }
    if (verRes.status === "fulfilled") {
        apiVersions.value = ((verRes.value as any)?.items || []).map((p: any) => ({ id: String(p.id), name: String(p.name || p.id) }));
    }
    if (repoRes.status === "fulfilled") {
        apiRepos.value = ((repoRes.value as any)?.items || []).map((item: any) => ({
            id: String(item.id || ""),
            name: String(item.name || item.full_name || item.id || ""),
        })).filter((item: { id: string; name: string }) => item.id && item.name);
    }
    syncDetailLinkedLabels();
    syncDetailRepoLabel();
    await loadBranchOptions(record.value?.repoId || "");
};

// ---- Inline edit: click-to-edit pattern ----
type EditableField =
    | "title"
    | "planTime"
    | "iteration"
    | "type"
    | "project"
    | "version"
    | "estimateHours"
    | "repo"
    | "branch"
    | "actualTime";
const editingField = ref<EditableField | null>(null);
const startEditing = (field: EditableField) => {
    editingField.value = field;
};
const stopEditing = () => {
    editingField.value = null;
};
const isEditing = (field: EditableField) => editingField.value === field;

const titleDraft = ref("");
const titleInputRef = ref<HTMLInputElement | null>(null);
const startEditingTitle = () => {
    if (!record.value) return;
    titleDraft.value = record.value.title;
    startEditing("title");
    nextTick(() => titleInputRef.value?.focus());
};
const saveTitle = () => {
    if (!record.value) return;
    const trimmed = titleDraft.value.trim();
    if (trimmed && trimmed !== record.value.title) {
        record.value.title = trimmed;
        emit("update", { title: trimmed });
        appendDetailLog("修改了名称");
    }
    titleDraft.value = "";
    stopEditing();
};
const cancelTitleEdit = () => {
    titleDraft.value = "";
    stopEditing();
};
const handleTitleKeydown = (e: KeyboardEvent) => {
    if (e.key === "Enter") {
        e.preventDefault();
        saveTitle();
    } else if (e.key === "Escape") {
        cancelTitleEdit();
    }
};

const canEditProject = computed(() => !!record.value);
const canEditIteration = computed(() => !!record.value);
const canEditVersion = computed(() => !!record.value);
const canEditEstimateHours = computed(() => !!record.value);
const detailEstimateRef = ref<any>(null);
const startEditingEstimate = () => {
    if (!canEditEstimateHours.value) return;
    startEditing("estimateHours");
    nextTick(() => detailEstimateRef.value?.focus());
};

onMounted(async () => {
    await loadMemberOptions();
    await loadFieldOptions();
    detailAssigneeGroupOpen["全部成员"] = true;
    await ensureDetailPanelsData();
});

watch(() => props.initialData, (value) => {
    record.value = value || null;
    if (value) loadFieldOptions();
}, { immediate: true });
</script>

<template>
    <div class="bug-detail-drawer">
        <main class="bug-detail-main" v-if="record">
            <div class="bug-detail-meta-top">
                <span class="work-type-icon" :class="getWorkItemTypeIconClass(record.type)">
                    <svg v-if="record.type === '缺陷'" class="work-type-icon-svg" viewBox="0 0 24 24" aria-hidden="true">
                        <circle cx="12" cy="7.5" r="3.2" fill="white" />
                        <rect x="8" y="10.5" width="8" height="9" rx="3.8" fill="white" />
                        <rect x="11.2" y="10.8" width="1.6" height="8.6" rx="0.8" fill="#ef4444" />
                        <path d="M8.3 12.3H5.2M8.1 15.1H4.8M15.9 12.3H18.8M16.1 15.1H19.2" stroke="white" stroke-width="1.5" stroke-linecap="round" />
                        <path d="M10.2 4.8 8.7 3.3M13.8 4.8 15.3 3.3" stroke="white" stroke-width="1.5" stroke-linecap="round" />
                    </svg>
                    <template v-else>{{ getWorkItemTypeIconSymbol(record.type) }}</template>
                </span>
                <span class="bug-detail-no">{{ record.workNo }}</span>
                <button type="button" class="detail-copy-link-btn" @click="handleCopyDetailLink">
                    <Copy :size="14" />
                    复制链接
                </button>
                <AiAssistButton
                    :prompt="`我要对${record.type}「${record.title}」(${record.workNo}) 进一步操作，请告诉我可以做什么。`"
                    label="AI 助手"
                />
                <button type="button" class="detail-copy-link-btn" @click="notifyDialogOpen = true">
                    <Bell :size="14" />
                    通知
                </button>
                <WorkItemStatus
                    :model-value="record.status"
                    :options="filteredDetailStatusOptions"
                    :open="detailStatusDropdownOpen"
                    v-model:keyword="detailStatusKeyword"
                    @update:open="(open) => { detailStatusDropdownOpen = open; if (!open) detailStatusKeyword = ''; }"
                    @change="selectDetailStatus"
                >
                    <template #trigger>
                        <VortButton class="detail-status-trigger" variant="text" @click.stop="toggleDetailStatusMenu">
                            <span class="detail-status-content">
                                <span class="detail-status-icon" :class="getStatusOption(record.status, record.type).iconClass">
                                    {{ getStatusOption(record.status, record.type).icon }}
                                </span>
                                <span class="detail-status-text">{{ record.status }}</span>
                            </span>
                            <span class="status-arrow-simple" :class="{ open: detailStatusDropdownOpen }" />
                        </VortButton>
                    </template>
                </WorkItemStatus>
            </div>

            <div v-if="isHierarchyRecord && parentRecord" class="story-tree-header">
                <div class="story-parent-node" @click="emit('openRelated', parentRecord)">
                    <span class="work-type-icon-small" :class="getWorkItemTypeIconClass(parentRecord.type)">
                        {{ getWorkItemTypeIconSymbol(parentRecord.type) }}
                    </span>
                    <span class="parent-title">{{ parentRecord.title }}</span>
                </div>
                <div class="story-child-node">
                    <div class="tree-line"></div>
                    <input
                        v-if="isEditing('title')"
                        ref="titleInputRef"
                        v-model="titleDraft"
                        class="bug-detail-title-input"
                        style="margin-bottom: 0;"
                        @blur="saveTitle"
                        @keydown="handleTitleKeydown"
                    />
                    <h2 v-else class="bug-detail-title bug-detail-title-editable" style="margin-bottom: 0;" @click="startEditingTitle">{{ record.title }}</h2>
                </div>
            </div>
            <template v-else>
                <input
                    v-if="isEditing('title')"
                    ref="titleInputRef"
                    v-model="titleDraft"
                    class="bug-detail-title-input"
                    @blur="saveTitle"
                    @keydown="handleTitleKeydown"
                />
                <h2 v-else class="bug-detail-title bug-detail-title-editable" @click="startEditingTitle">{{ record.title }}</h2>
            </template>
            <p class="bug-detail-sub" :style="isHierarchyRecord && parentRecord ? 'margin-top: 8px;' : ''">
                {{ record.owner || "未指派" }}，创建于 {{ record.createdAt }}，最近更新于 {{ record.updatedAt || record.createdAt }}
            </p>
            <div class="bug-detail-tabs">
                <button :class="{ active: detailActiveTab === 'detail' }" @click="detailActiveTab = 'detail'">详情</button>
                <button :class="{ active: detailActiveTab === 'worklog' }" @click="detailActiveTab = 'worklog'">工作日志</button>
                <button :class="{ active: detailActiveTab === 'related' }" @click="detailActiveTab = 'related'">关联工作项</button>
                <button :class="{ active: detailActiveTab === 'test' }" @click="detailActiveTab = 'test'">关联测试用例</button>
                <button :class="{ active: detailActiveTab === 'docs' }" @click="detailActiveTab = 'docs'">关联文档</button>
            </div>

            <div class="bug-detail-panel" v-if="detailActiveTab === 'detail'">
                <div class="bug-detail-ai-bar">
                    <AiAssistButton
                        :prompt="buildSupplementPrompt()"
                        label="AI 一键补充"
                    />
                </div>
                <div class="bug-detail-top-grid">
                    <div class="bug-detail-left-col">
                        <div class="bug-detail-info-item bug-detail-info-item-row bug-detail-info-assignee" @click.stop>
                            <label>负责人 / 协作</label>
                            <WorkItemMemberPicker
                                mode="assignee"
                                :owner="record.owner === '未指派' ? '' : record.owner"
                                :collaborators="record.collaborators"
                                :groups="filteredDetailAssigneeGroups"
                                :open="detailAssigneeDropdownOpen"
                                v-model:keyword="detailAssigneeKeyword"
                                :dropdown-width="280"
                                :dropdown-max-height="320"
                                :bordered="false"
                                :collapsible="false"
                                :get-avatar-bg="getAvatarBg"
                                :get-avatar-label="getAvatarLabel"
                                :get-avatar-url="getMemberAvatarUrl"
                                @update:open="(open) => { detailAssigneeDropdownOpen = open; if (!open) detailAssigneeKeyword = ''; }"
                                @update:owner="setDetailOwner"
                                @update:collaborators="setDetailCollaborators"
                            >
                                <template #trigger>
                                    <VortButton
                                        class="detail-assignee-trigger"
                                        variant="text"
                                        :class="detailAssigneeDropdownOpen ? 'active' : ''"
                                        @click.stop="toggleDetailAssigneeMenu"
                                    >
                                        <div class="detail-assignee-split">
                                            <div class="detail-assignee-owner">
                                                <span
                                                    v-if="record.owner && record.owner !== '未指派'"
                                                    class="detail-assignee-avatar overflow-hidden"
                                                    :style="{ backgroundColor: getAvatarBg(record.owner) }"
                                                >
                                                    <img v-if="getMemberAvatarUrl(record.owner)" :src="getMemberAvatarUrl(record.owner)" class="w-full h-full object-cover" />
                                                    <template v-else>{{ getAvatarLabel(record.owner) }}</template>
                                                </span>
                                                <span class="detail-assignee-owner-name">
                                                    {{ record.owner || "未指派" }}
                                                </span>
                                            </div>
                                            <span class="detail-assignee-separator">/</span>
                                            <div class="detail-assignee-collaborators detail-collab-stack">
                                                <template v-if="record.collaborators.length > 0">
                                                    <span
                                                        v-for="name in record.collaborators"
                                                        :key="'detail-collab-' + name"
                                                        class="detail-assignee-avatar overflow-hidden"
                                                        :style="{ backgroundColor: getAvatarBg(name) }"
                                                        :title="name"
                                                    >
                                                        <img v-if="getMemberAvatarUrl(name)" :src="getMemberAvatarUrl(name)" class="w-full h-full object-cover" />
                                                        <template v-else>{{ getAvatarLabel(name) }}</template>
                                                    </span>
                                                </template>
                                                <span v-else class="detail-assignee-avatar detail-assignee-add">+</span>
                                            </div>
                                        </div>
                                    </VortButton>
                                </template>
                            </WorkItemMemberPicker>
                        </div>
                        <div class="bug-detail-info-item bug-detail-info-item-row">
                            <label>计划时间</label>
                            <div
                                class="detail-field-shell"
                                :class="{ 'is-editing': isEditing('planTime') }"
                                @mousedown.capture="startEditing('planTime')"
                            >
                                <vort-range-picker
                                    v-model="detailPlanTimeModel"
                                    value-format="YYYY-MM-DD"
                                    format="YYYY-MM-DD"
                                    separator="~"
                                    :placeholder="['未设置', '未设置']"
                                    class="detail-field-picker"
                                    @change="stopEditing"
                                    @open-change="(v: boolean) => { if (!v) stopEditing() }"
                                />
                            </div>
                        </div>
                        <div class="bug-detail-info-item bug-detail-info-item-row">
                            <label>迭代</label>
                            <div
                                class="detail-field-shell"
                                :class="{ 'is-editing': isEditing('iteration') }"
                                @mousedown.capture="canEditIteration && startEditing('iteration')"
                            >
                                <vort-select
                                    v-model="detailIteration"
                                    placeholder="未设置"
                                    allow-clear
                                    :disabled="!canEditIteration"
                                    :bordered="isEditing('iteration')"
                                    class="detail-field-select"
                                    @change="stopEditing"
                                    @blur="stopEditing"
                                >
                                    <vort-select-option v-for="item in apiIterations" :key="item.id" :value="item.id">{{ item.name }}</vort-select-option>
                                </vort-select>
                            </div>
                        </div>
                        <div class="bug-detail-info-item bug-detail-info-item-row">
                            <label>预估工时</label>
                            <div
                                class="detail-field-shell"
                                :class="{ 'is-editing': isEditing('estimateHours') }"
                                @mousedown.capture="startEditingEstimate"
                            >
                                <vort-input-number
                                    ref="detailEstimateRef"
                                    v-model="detailEstimateHours"
                                    placeholder="未设置"
                                    :disabled="!canEditEstimateHours"
                                    :min="0"
                                    :step="0.5"
                                    :bordered="isEditing('estimateHours')"
                                    class="detail-field-number"
                                    @blur="stopEditing"
                                />
                            </div>
                        </div>
                        <div class="bug-detail-info-item bug-detail-info-item-row">
                            <label>实际时间</label>
                            <div
                                class="detail-field-shell"
                                :class="{ 'is-editing': isEditing('actualTime') }"
                                @mousedown.capture="startEditing('actualTime')"
                            >
                                <vort-range-picker
                                    v-model="detailActualTimeModel"
                                    value-format="YYYY-MM-DD"
                                    format="YYYY-MM-DD"
                                    separator="~"
                                    :placeholder="['未设置', '未设置']"
                                    class="detail-field-picker"
                                    @change="stopEditing"
                                    @open-change="(v: boolean) => { if (!v) stopEditing() }"
                                />
                            </div>
                        </div>
                    </div>
                    <div class="bug-detail-right-col">
                        <div class="bug-detail-info-item bug-detail-info-item-row">
                            <label>类型</label>
                            <div
                                class="detail-field-shell"
                                :class="{ 'is-editing': isEditing('type') }"
                                @mousedown.capture="startEditing('type')"
                            >
                                <vort-select
                                    v-model="detailType"
                                    :bordered="isEditing('type')"
                                    class="detail-field-select"
                                    @change="stopEditing"
                                    @blur="stopEditing"
                                >
                                    <vort-select-option value="需求">需求</vort-select-option>
                                    <vort-select-option value="任务">任务</vort-select-option>
                                    <vort-select-option value="缺陷">缺陷</vort-select-option>
                                </vort-select>
                            </div>
                        </div>
                        <div class="bug-detail-info-item bug-detail-info-item-row">
                            <label>项目</label>
                            <div
                                class="detail-field-shell"
                                :class="{ 'is-editing': isEditing('project') }"
                                @mousedown.capture="canEditProject && startEditing('project')"
                            >
                                <vort-select
                                    v-model="detailProjectName"
                                    :disabled="!canEditProject"
                                    :bordered="isEditing('project')"
                                    class="detail-field-select"
                                    @change="stopEditing"
                                    @blur="stopEditing"
                                >
                                    <vort-select-option v-for="item in apiProjects" :key="item.id" :value="item.name">{{ item.name }}</vort-select-option>
                                </vort-select>
                            </div>
                        </div>
                        <div class="bug-detail-info-item bug-detail-info-item-row">
                            <label>版本</label>
                            <div
                                class="detail-field-shell"
                                :class="{ 'is-editing': isEditing('version') }"
                                @mousedown.capture="canEditVersion && startEditing('version')"
                            >
                                <vort-select
                                    v-model="detailVersion"
                                    placeholder="未设置"
                                    allow-clear
                                    :disabled="!canEditVersion"
                                    :bordered="isEditing('version')"
                                    class="detail-field-select"
                                    @change="stopEditing"
                                    @blur="stopEditing"
                                >
                                    <vort-select-option v-for="item in apiVersions" :key="item.id" :value="item.id">{{ item.name }}</vort-select-option>
                                </vort-select>
                            </div>
                        </div>
                        <div class="bug-detail-info-item bug-detail-info-item-row">
                            <label>关联仓库</label>
                            <div
                                class="detail-field-shell"
                                :class="{ 'is-editing': isEditing('repo') }"
                                @mousedown.capture="startEditing('repo')"
                            >
                                <vort-select
                                    v-model="detailRepoId"
                                    placeholder="未设置"
                                    allow-clear
                                    :bordered="isEditing('repo')"
                                    class="detail-field-select"
                                    @change="stopEditing"
                                    @blur="stopEditing"
                                >
                                    <vort-select-option v-for="item in apiRepos" :key="item.id" :value="item.id">{{ item.name }}</vort-select-option>
                                </vort-select>
                            </div>
                        </div>
                        <div class="bug-detail-info-item bug-detail-info-item-row">
                            <label>关联分支</label>
                            <div
                                class="detail-field-shell"
                                :class="{ 'is-editing': isEditing('branch') }"
                                @mousedown.capture="record.repoId && startEditing('branch')"
                            >
                                <vort-select
                                    v-model="detailBranch"
                                    :placeholder="record.repoId ? (branchLoading ? '分支加载中' : '未设置') : '请先选择仓库'"
                                    allow-clear
                                    :disabled="!record.repoId"
                                    :bordered="isEditing('branch')"
                                    class="detail-field-select"
                                    @change="stopEditing"
                                    @blur="stopEditing"
                                >
                                    <vort-select-option v-for="item in apiBranches" :key="item.name" :value="item.name">{{ item.name }}</vort-select-option>
                                </vort-select>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="bug-detail-sub-items" v-if="isHierarchyRecord">
                    <div class="bug-detail-sub-items-head">
                        <div class="flex items-center gap-2">
                            <h4>{{ childItemLabel }}</h4>
                            <span class="count">{{ childRecords.length }}</span>
                        </div>
                        <VortButton
                            class="add-sub-item-btn"
                            variant="text"
                            size="small"
                            :disabled="!canCreateChild"
                            @click="record && emit('createChild', record)"
                        >
                            <span class="icon">+</span> {{ addChildLabel }}
                        </VortButton>
                    </div>
                    
                    <div class="bug-detail-sub-items-content">
                        <div v-if="childRecords.length === 0" class="bug-detail-sub-items-empty">
                            <span class="empty-text">{{ emptyChildText }}</span>
                        </div>
                        <div v-else class="bug-detail-sub-items-list">
                            <div 
                                v-for="child in childRecords" 
                                :key="child.backendId || child.workNo"
                                class="bug-detail-sub-item group"
                                @click="emit('openRelated', child)"
                            >
                                <div class="sub-item-left">
                                    <span class="work-type-icon-small" :class="getWorkItemTypeIconClass(child.type)">
                                        {{ getWorkItemTypeIconSymbol(child.type) }}
                                    </span>
                                    <span class="sub-item-no">{{ child.workNo }}</span>
                                    <span class="sub-item-title group-hover:text-blue-600">{{ child.title }}</span>
                                </div>
                                <div class="sub-item-right">
                                    <div class="sub-item-owner">
                                        <span class="detail-assignee-avatar overflow-hidden" :style="{ backgroundColor: getAvatarBg(child.owner || '未指派'), width: '20px', height: '20px', fontSize: '10px' }">
                                            <img v-if="getMemberAvatarUrl(child.owner || '')" :src="getMemberAvatarUrl(child.owner || '')" class="w-full h-full object-cover" />
                                            <template v-else>{{ getAvatarLabel(child.owner || '未指派') }}</template>
                                        </span>
                                        <span class="owner-name">{{ child.owner || '未指派' }}</span>
                                    </div>
                                    <div class="sub-item-status">
                                        <span class="status-icon" :class="getStatusOption(child.status, child.type).iconClass">{{ getStatusOption(child.status, child.type).icon }}</span>
                                        <span class="status-text">{{ child.status }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="bug-detail-desc">
                    <div class="bug-detail-desc-head">
                        <h4>描述</h4>
                        <VortButton class="bug-detail-desc-edit-btn" variant="text" size="small" @click="openDetailDescEditor">
                            <SquarePen :size="14" />
                        </VortButton>
                    </div>
                    <template v-if="detailDescEditing">
                        <VortEditor v-model="detailDescDraft" placeholder="请输入描述内容..." min-height="300px" />
                        <div class="bug-detail-desc-actions">
                            <vort-button variant="primary" @click="saveDetailDescEditor">保存</vort-button>
                            <vort-button @click="cancelDetailDescEditor">取消</vort-button>
                            <vort-button
                                class="ml-auto"
                                :loading="descAi.loading.value"
                                @click="startAiEnrichDesc"
                            >
                                <Bot :size="14" class="mr-1" /> {{ aiEnrichBtnLabel }}
                            </vort-button>
                        </div>

                        <!-- AI description result area -->
                        <div v-if="descAi.html.value || descAi.loading.value" class="bug-detail-ai-desc">
                            <div class="bug-detail-ai-desc-head">
                                <h4 class="flex items-center gap-1.5">
                                    <Bot :size="14" class="text-blue-500" /> AI 生成的描述
                                </h4>
                                <div class="flex items-center gap-2">
                                    <button
                                        v-if="!descAi.loading.value && descAi.html.value"
                                        class="text-xs text-gray-400 hover:text-blue-500 transition-colors"
                                        @click="startAiEnrichDesc"
                                    >
                                        重新生成
                                    </button>
                                    <button
                                        v-if="descAi.loading.value"
                                        class="text-xs text-gray-400 hover:text-red-500 transition-colors"
                                        @click="descAi.abort()"
                                    >
                                        停止
                                    </button>
                                </div>
                            </div>

                            <div v-if="descAi.loading.value && !descAi.html.value" class="flex items-center gap-2 py-4 text-sm text-gray-400">
                                <Loader2 class="w-4 h-4 animate-spin" />
                                <span>{{ descAiPhaseLabel }}...</span>
                            </div>

                            <div
                                v-if="descAi.html.value"
                                class="ai-content text-[13px] leading-[1.75] text-gray-700"
                                v-html="descAi.html.value"
                            />

                            <div v-if="descAi.error.value" class="text-sm text-red-500 py-2">{{ descAi.error.value }}</div>

                            <div v-if="descAi.loading.value && descAi.html.value" class="flex items-center gap-1.5 mt-2 text-xs text-gray-400">
                                <Loader2 class="w-3 h-3 animate-spin" />
                                <span>{{ descAiPhaseLabel }}...</span>
                            </div>

                            <div v-if="descAi.html.value && !descAi.loading.value" class="bug-detail-ai-desc-apply">
                                <vort-button variant="primary" size="small" @click="applyAiDesc">
                                    应用 AI 描述
                                </vort-button>
                                <vort-button size="small" @click="descAi.clear()">
                                    忽略
                                </vort-button>
                            </div>
                        </div>
                    </template>
                    <template v-else>
                        <div v-if="(record.description || '').trim()" class="bug-detail-desc-content">
                            <MarkdownView :content="record.description || ''" />
                        </div>
                        <div v-else class="bug-detail-desc-content">-</div>
                    </template>
                </div>

                <div class="bug-detail-bottom-panel">
                    <div class="bug-detail-bottom-tabs">
                        <button
                            :class="{ active: detailBottomTab === 'comments' }"
                            @click="detailBottomTab = 'comments'"
                        >
                            评论
                            <span class="count">{{ detailComments.length }}</span>
                        </button>
                        <button
                            :class="{ active: detailBottomTab === 'logs' }"
                            @click="detailBottomTab = 'logs'"
                        >
                            操作日志
                            <span class="count">{{ detailLogs.length }}</span>
                        </button>
                    </div>

                    <div v-if="detailBottomTab === 'comments'" class="bug-detail-comments">
                        <div v-if="detailComments.length === 0" class="bug-detail-empty">暂无评论</div>
                        <div v-else class="bug-detail-comment-list">
                            <div v-for="item in detailComments" :key="item.id" class="bug-detail-comment-item">
                                <span class="bug-detail-comment-avatar">{{ item.author.slice(0, 1) }}</span>
                                <div class="bug-detail-comment-main">
                                    <div class="bug-detail-comment-meta">
                                        <span class="author">{{ item.author }}</span>
                                        <span class="time">{{ item.createdAt }}</span>
                                    </div>
                                    <div class="bug-detail-comment-content"><MarkdownView :content="item.content" /></div>
                                </div>
                            </div>
                        </div>

                        <div class="bug-detail-comment-editor">
                            <VortEditor v-model="detailCommentDraft" placeholder="发表您的看法（Ctrl/Command+Enter发送）" min-height="120px" />
                            <div class="bug-detail-desc-actions">
                                <vort-button variant="primary" @click="submitDetailComment">评论</vort-button>
                            </div>
                        </div>
                    </div>

                    <div v-else class="bug-detail-logs">
                        <div v-if="detailLogs.length === 0" class="bug-detail-empty">暂无操作日志</div>
                        <div v-else class="bug-detail-log-list">
                            <div v-for="item in detailLogs" :key="item.id" class="bug-detail-log-item">
                                <span class="bug-detail-log-dot" />
                                <span class="actor">{{ item.actor }}</span>
                                <span class="action">{{ item.action }}</span>
                                <span class="time">{{ item.createdAt }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="bug-detail-panel" v-else-if="detailActiveTab === 'worklog'">
                <p class="bug-detail-empty">暂无工作日志</p>
            </div>
            <div class="bug-detail-panel" v-else-if="detailActiveTab === 'related'">
                <WorkItemLinkPanel
                    v-if="record?.backendId"
                    :entity-type="linkEntityType"
                    :entity-id="record.backendId"
                    @open-related="(r) => emit('openRelated', r as any)"
                />
                <p v-else class="bug-detail-empty">暂无关联工作项</p>
            </div>
            <div class="bug-detail-panel" v-else-if="detailActiveTab === 'test'">
                <TestCaseLinkPanel
                    v-if="record?.backendId"
                    :entity-type="linkEntityType"
                    :entity-id="record.backendId"
                />
                <p v-else class="bug-detail-empty">暂无关联测试用例</p>
            </div>
            <div class="bug-detail-panel" v-else>
                <div class="bug-detail-empty">
                    <FileText :size="32" class="bug-detail-empty-icon" />
                    <span>暂无关联文档</span>
                </div>
            </div>
        </main>
        <div v-else class="p-4 text-center text-gray-500">加载中...</div>

        <NotifyDialog
            v-if="record"
            v-model:open="notifyDialogOpen"
            :entity-type="getEntityTypeKey()"
            :entity-id="record.backendId || ''"
            :title="record.title"
            :project-id="record.projectId || ''"
            :owner-id="record.ownerId || ''"
            :owner-name="record.owner === '未指派' ? '' : record.owner"
            :collaborator-names="record.collaborators || []"
            :get-member-id-by-name="getMemberIdByName"
            :get-avatar-bg="getAvatarBg"
            :get-member-avatar-url="getMemberAvatarUrl"
        />
    </div>
</template>

<style scoped>
.bug-detail-drawer {
    height: 100%;
}

.bug-detail-main {
    padding: 0 4px;
}

.bug-detail-meta-top {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
}

.work-type-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 6px;
    font-size: 18px;
}

.work-type-icon-demand {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: white;
}

.work-type-icon-task {
    background: linear-gradient(135deg, #0ea5e9 0%, #06b6d4 100%);
    color: white;
}

.work-type-icon-bug {
    background: linear-gradient(135deg, #ef4444 0%, #f97316 100%);
    color: white;
}

.work-type-icon-svg {
    width: 20px;
    height: 20px;
}

.bug-detail-no {
    font-size: 14px;
    color: var(--vort-text-secondary);
    font-weight: 500;
}

.detail-copy-link-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--vort-text-secondary);
    font-size: 12px;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
}

.detail-copy-link-btn:hover {
    background: var(--vort-primary-bg);
    color: var(--vort-text);
}

.detail-status-trigger {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    border-radius: 4px;
}

.detail-status-content {
    display: flex;
    align-items: center;
    gap: 4px;
}

.detail-status-icon {
    font-size: 14px;
}

.detail-status-text {
    font-size: 14px;
    color: var(--vort-text);
}

.status-arrow-simple {
    display: inline-block;
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 4px solid var(--vort-text-tertiary);
    transition: transform 0.2s;
}

.status-arrow-simple.open {
    transform: rotate(180deg);
}

.bug-detail-title {
    font-size: 20px;
    font-weight: 600;
    color: var(--vort-text);
    margin: 0 0 8px 0;
    line-height: 1.4;
}

.bug-detail-title-editable {
    cursor: text;
    border-radius: 4px;
    padding: 2px 6px;
    margin-left: -6px;
    transition: background 0.15s;
}

.bug-detail-title-editable:hover {
    background: var(--vort-bg-hover, rgba(0, 0, 0, 0.04));
}

.bug-detail-title-input {
    font-size: 20px;
    font-weight: 600;
    color: var(--vort-text);
    margin: 0 0 8px 0;
    line-height: 1.4;
    padding: 2px 6px;
    margin-left: -6px;
    width: 100%;
    border: 1px solid var(--vort-primary);
    border-radius: 4px;
    outline: none;
    background: var(--vort-bg);
    box-shadow: 0 0 0 2px rgba(var(--vort-primary-rgb, 59, 130, 246), 0.15);
}

.bug-detail-sub {
    font-size: 13px;
    color: var(--vort-text-secondary);
    margin: 0 0 20px 0;
}

.story-tree-header {
    margin-bottom: 8px;
}

.story-parent-node {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--vort-text-secondary);
    cursor: pointer;
    font-size: 14px;
    transition: color 0.2s;
}

.story-parent-node:hover {
    color: var(--vort-primary);
}

.work-type-icon-small {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
}

.work-type-icon-svg-small {
    width: 16px;
    height: 16px;
}

.parent-title {
    max-width: 400px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.story-child-node {
    display: flex;
    align-items: flex-start;
    margin-top: 4px;
}

.tree-line {
    width: 16px;
    height: 20px;
    border-left: 1.5px solid var(--vort-border);
    border-bottom: 1.5px solid var(--vort-border);
    border-bottom-left-radius: 6px;
    margin-left: 7px;
    margin-right: 8px;
    margin-top: -4px;
    flex-shrink: 0;
}

.bug-detail-tabs {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid var(--vort-border-secondary);
    margin-bottom: 20px;
}

.bug-detail-tabs button {
    padding: 10px 16px;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--vort-text-secondary);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
}

.bug-detail-tabs button:hover {
    color: var(--vort-text);
}

.bug-detail-tabs button.active {
    color: var(--vort-primary);
    border-bottom-color: var(--vort-primary);
}

.bug-detail-top-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px 48px;
    margin-bottom: 24px;
}

.bug-detail-left-col,
.bug-detail-right-col {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.bug-detail-info-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.bug-detail-info-item label {
    font-size: 13px;
    color: var(--vort-text-secondary);
    font-weight: 400;
}

.bug-detail-info-item > div {
    font-size: 14px;
    color: var(--vort-text);
}

.bug-detail-info-item-row {
    flex-direction: row;
    justify-content: flex-start;
    align-items: center;
    min-height: 32px;
}

.bug-detail-info-item-row label {
    flex-shrink: 0;
    width: 100px;
}

.bug-detail-info-assignee {
    cursor: pointer;
}

/* 子需求栏目样式 */
.bug-detail-sub-items {
    margin-bottom: 24px;
}

.bug-detail-sub-items-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
}

.bug-detail-sub-items-head h4 {
    font-size: 14px;
    font-weight: 600;
    color: var(--vort-text);
    margin: 0;
}

.bug-detail-sub-items-head .count {
    background: var(--vort-border-secondary);
    color: var(--vort-text-secondary);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}

.add-sub-item-btn {
    color: var(--vort-primary) !important;
    font-size: 13px !important;
    padding: 4px 8px !important;
    height: auto !important;
}

.add-sub-item-btn:hover {
    background: var(--vort-primary-bg) !important;
}

.add-sub-item-btn .icon {
    margin-right: 4px;
    font-size: 16px;
    line-height: 1;
}

.bug-detail-sub-items-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px 0;
    background: var(--vort-border-secondary);
    border: 1px dashed var(--vort-border);
    border-radius: 8px;
}

.bug-detail-sub-items-empty .empty-text {
    color: var(--vort-text-tertiary);
    font-size: 13px;
}

.bug-detail-sub-items-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.bug-detail-sub-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    background: var(--vort-bg);
    border: 1px solid var(--vort-border-secondary);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.bug-detail-sub-item:hover {
    border-color: var(--vort-primary-bg-hover);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

.sub-item-left {
    display: flex;
    align-items: center;
    gap: 12px;
    overflow: hidden;
}

.sub-item-no {
    font-size: 12px;
    font-weight: 500;
    color: var(--vort-text-tertiary);
    flex-shrink: 0;
}

.sub-item-title {
    font-size: 13px;
    color: var(--vort-text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: color 0.2s;
}

.sub-item-right {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-shrink: 0;
    margin-left: 16px;
}

.sub-item-owner {
    display: flex;
    align-items: center;
    gap: 6px;
}

.sub-item-owner .owner-name {
    font-size: 12px;
    color: var(--vort-text-secondary);
}

.sub-item-status {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    background: var(--vort-bg-elevated);
    border: 1px solid var(--vort-border-secondary);
    border-radius: 4px;
    min-width: 72px;
    justify-content: center;
}

.sub-item-status .status-icon {
    font-size: 12px;
    line-height: 1;
}

.sub-item-status .status-text {
    font-size: 12px;
    color: var(--vort-text-secondary);
}

.detail-assignee-trigger {
    display: flex;
    align-items: center;
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px solid transparent;
    margin-left: -10px;
}

.detail-assignee-trigger:hover,
.detail-assignee-trigger.active {
    background: var(--vort-bg-elevated);
    border-color: var(--vort-border-secondary);
}

.detail-assignee-split {
    display: flex;
    align-items: center;
    gap: 8px;
}

.detail-assignee-owner {
    display: flex;
    align-items: center;
    gap: 6px;
}

.detail-assignee-avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    font-size: 11px;
    color: white;
    font-weight: 500;
}

.detail-assignee-owner-name {
    font-size: 13px;
    color: var(--vort-text);
}

.detail-assignee-separator {
    color: var(--vort-border);
    font-size: 15px;
    margin: 0 6px;
}

.detail-assignee-collaborators {
    display: flex;
    align-items: center;
    gap: 4px;
}

.detail-assignee-add {
    background: var(--vort-border-secondary) !important;
    color: var(--vort-text-tertiary) !important;
    font-size: 14px !important;
    border: 1px dashed var(--vort-border);
}

.detail-assignee-dropdown {
    width: 280px;
    padding: 12px;
}

.detail-assignee-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-radius: 6px;
}

.detail-assignee-row:hover {
    background: var(--vort-bg-elevated);
}

.detail-assignee-row-left {
    display: flex;
    align-items: center;
    gap: 8px;
}

.detail-assignee-row-actions {
    display: flex;
    gap: 4px;
}

.detail-role-btn {
    font-size: 12px !important;
    padding: 4px 8px !important;
    color: var(--vort-text-secondary);
}

.detail-role-btn.active {
    color: var(--vort-primary);
    background: var(--vort-primary-bg);
}

.detail-role-btn.collab.active {
    color: #8b5cf6;
    background: #f5f3ff;
}

.bug-detail-desc {
    margin-bottom: 24px;
}

.bug-detail-desc-head {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-bottom: 12px;
}

.bug-detail-desc-head h4 {
    font-size: 14px;
    font-weight: 600;
    color: var(--vort-text);
    margin: 0;
}

.bug-detail-desc-edit-btn {
    color: var(--vort-text-secondary);
}

.bug-detail-desc-content {
    font-size: 14px;
    color: var(--vort-text-secondary);
    line-height: 1.6;
    padding: 12px;
    background: var(--vort-bg-elevated);
    border-radius: 8px;
    min-height: 60px;
}

.bug-detail-desc-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 12px;
}

.bug-detail-ai-bar {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 8px;
}

.bug-detail-ai-desc {
    margin-top: 16px;
    padding: 16px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
}

.bug-detail-ai-desc-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
}

.bug-detail-ai-desc-head h4 {
    font-size: 13px;
    font-weight: 500;
    color: #374151;
    margin: 0;
}

.bug-detail-ai-desc-apply {
    display: flex;
    gap: 8px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid #e2e8f0;
}

.ai-content :deep(h1),
.ai-content :deep(h2),
.ai-content :deep(h3),
.ai-content :deep(h4) {
    font-size: 13px;
    font-weight: 600;
    color: #374151;
    margin-top: 1em;
    margin-bottom: 0.4em;
}
.ai-content :deep(h1:first-child),
.ai-content :deep(h2:first-child),
.ai-content :deep(h3:first-child) {
    margin-top: 0;
}
.ai-content :deep(p) {
    margin: 0.4em 0;
}
.ai-content :deep(ul),
.ai-content :deep(ol) {
    margin: 0.3em 0;
    padding-left: 1.5em;
}
.ai-content :deep(li) {
    margin: 0.15em 0;
}
.ai-content :deep(pre) {
    background: #f1f5f9;
    border-radius: 6px;
    padding: 10px 12px;
    font-size: 12px;
    line-height: 1.6;
    overflow-x: auto;
    margin: 0.5em 0;
}
.ai-content :deep(code) {
    font-size: 12px;
    background: #f3f4f6;
    border-radius: 3px;
    padding: 1px 4px;
}
.ai-content :deep(pre code) {
    background: none;
    padding: 0;
}
.ai-content :deep(strong) {
    font-weight: 600;
    color: #1f2937;
}
.ai-content :deep(table) {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin: 0.5em 0;
}
.ai-content :deep(th),
.ai-content :deep(td) {
    border: 1px solid #e5e7eb;
    padding: 4px 8px;
    text-align: left;
}
.ai-content :deep(th) {
    background: #f9fafb;
    font-weight: 600;
}

.bug-detail-bottom-panel {
    border-top: 1px solid var(--vort-border-secondary);
    padding-top: 20px;
}

.bug-detail-bottom-tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 16px;
}

.bug-detail-bottom-tabs button {
    padding: 8px 12px;
    background: none;
    border: none;
    border-radius: 6px;
    color: var(--vort-text-secondary);
    font-size: 13px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
}

.bug-detail-bottom-tabs button:hover {
    background: var(--vort-border-secondary);
}

.bug-detail-bottom-tabs button.active {
    background: var(--vort-primary-bg);
    color: var(--vort-primary);
}

.bug-detail-bottom-tabs .count {
    background: var(--vort-border-secondary);
    padding: 2px 6px;
    border-radius: 10px;
    font-size: 11px;
}

.bug-detail-bottom-tabs button.active .count {
    background: var(--vort-primary-bg-hover);
}

.bug-detail-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 48px 20px;
    color: var(--vort-text-tertiary);
    font-size: 14px;
}

.bug-detail-empty-icon {
    color: var(--vort-text-quaternary, #d0d5dd);
}

.story-children-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.story-children-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    width: 100%;
    padding: 12px 14px;
    border: 1px solid var(--vort-border-secondary);
    border-radius: 10px;
    background: var(--vort-bg);
    text-align: left;
}

.story-children-item:hover {
    border-color: var(--vort-primary-bg-hover);
    background: var(--vort-primary-bg);
}

.story-children-title {
    color: var(--vort-text);
    font-size: 14px;
}

.story-children-status {
    color: var(--vort-text-secondary);
    font-size: 12px;
    white-space: nowrap;
}

.bug-detail-comment-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 20px;
}

.bug-detail-comment-item {
    display: flex;
    gap: 12px;
}

.bug-detail-comment-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 500;
    flex-shrink: 0;
}

.bug-detail-comment-main {
    flex: 1;
}

.bug-detail-comment-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}

.bug-detail-comment-meta .author {
    font-size: 13px;
    font-weight: 500;
    color: var(--vort-text);
}

.bug-detail-comment-meta .time {
    font-size: 12px;
    color: var(--vort-text-tertiary);
}

.bug-detail-comment-content {
    font-size: 14px;
    color: var(--vort-text-secondary);
    line-height: 1.5;
}

.bug-detail-comment-editor {
    border-top: 1px solid var(--vort-border-secondary);
    padding-top: 16px;
}

.bug-detail-log-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.bug-detail-log-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
}

.bug-detail-log-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--vort-border);
    flex-shrink: 0;
}

.bug-detail-log-item .actor {
    font-weight: 500;
    color: var(--vort-text);
}

.bug-detail-log-item .action {
    color: var(--vort-text-secondary);
}

.bug-detail-log-item .time {
    color: var(--vort-text-tertiary);
    margin-left: auto;
}

.detail-field-shell {
    display: inline-flex;
    align-items: center;
    min-width: 0;
    border-radius: 4px;
    transition: background 0.15s;
}

.detail-field-shell:not(.is-editing):hover {
    background: var(--vort-border-secondary);
}

.detail-field-shell :deep(.vort-select-selector) {
    width: auto;
}

.detail-field-shell:not(.is-editing) :deep(.vort-select-selector) {
    border-color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 4px 8px !important;
}

.detail-field-shell:not(.is-editing) :deep(.vort-select-arrow-wrapper),
.detail-field-shell:not(.is-editing) :deep(.vort-select-clear),
.detail-field-shell:not(.is-editing) :deep(.vort-rangepicker-prefix),
 .detail-field-shell:not(.is-editing) :deep(.vort-rangepicker-suffix),
 .detail-field-shell:not(.is-editing) :deep(.vort-date-picker-prefix),
 .detail-field-shell:not(.is-editing) :deep(.vort-date-picker-suffix),
 .detail-field-shell:not(.is-editing) :deep(.vort-input-number-handler-wrap) {
    display: none !important;
}

.detail-field-shell:not(.is-editing) :deep(.vort-select-placeholder),
.detail-field-shell:not(.is-editing) :deep(.vort-rangepicker-placeholder),
 .detail-field-shell:not(.is-editing) :deep(.vort-rangepicker-input-placeholder),
 .detail-field-shell:not(.is-editing) :deep(.vort-date-picker-input::placeholder),
 .detail-field-shell:not(.is-editing) :deep(.vort-input-number-input::placeholder) {
    color: var(--vort-text-tertiary) !important;
}

.detail-field-shell :deep(.vort-rangepicker-selector) {
    width: auto;
}

.detail-field-shell:not(.is-editing) :deep(.vort-rangepicker-selector) {
    border-color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 4px 8px !important;
}

.detail-field-picker :deep(.vort-rangepicker-prefix) {
    display: none;
}

.detail-field-picker :deep(.vort-rangepicker-separator) {
    padding: 0 4px;
}

.detail-field-picker :deep(.vort-rangepicker-input) {
    font-size: 14px;
}

.detail-field-shell :deep(.vort-date-picker) {
    width: auto;
}

.detail-field-shell:not(.is-editing) :deep(.vort-date-picker) {
    border-color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 4px 8px !important;
}

.detail-field-shell :deep(.vort-input-number) {
    width: 120px;
}

.detail-field-shell:not(.is-editing) :deep(.vort-input-number) {
    border-color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
}

.detail-field-shell:not(.is-editing) :deep(.vort-input-number-input) {
    padding-left: 8px !important;
    padding-right: 8px !important;
    background: transparent !important;
}
</style>
