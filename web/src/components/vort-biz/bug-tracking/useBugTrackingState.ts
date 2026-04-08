import { computed, reactive, ref } from "vue";
import { formatFileSize } from "@/utils/format";
import type { ProTableColumn, ProTableRequestParams, ProTableResponse } from "@/components/vort-biz/pro-table";
import {
    type RowItem,
    type NewBugForm,
    type BugFilterParams,
    type Priority,
    type Status,
    type WorkType,
    type DateRange,
    type DetailComment,
    type DetailLog,
    type BugAttachment,
    priorityOptions,
    statusFilterOptions,
    priorityLabelMap,
    statusIconMap,
    priorityClassMap,
    statusClassMap,
    tagOptions,
    createBugTagOptions,
    createBugProjectOptions,
    createBugRepoOptions,
    createBugBranchOptions
} from "./types";
import { useWorkItemCommon } from "@/views/vortflow/work-item/useWorkItemCommon";

export function useBugTrackingState() {
    const { ownerGroups, loadMemberOptions } = useWorkItemCommon();
    loadMemberOptions();

    // ==================== 筛选状态 ====================
    const keyword = ref("");
    const owner = ref("");
    const ownerDropdownOpen = ref(false);
    const ownerKeyword = ref("");
    const type = ref("");
    const typeDropdownOpen = ref(false);
    const typeKeyword = ref("");
    const status = ref("");
    const statusDropdownOpen = ref(false);
    const statusKeyword = ref("");

    // ==================== 列表状态 ====================
    const allData = ref<RowItem[]>([]);
    const totalCount = ref(0);
    const tableRef = ref<any>(null);
    const nextWorkNoIndex = ref(0);

    // ==================== 行内编辑状态 ====================
    const priorityModel = reactive<Record<string, Priority>>({});
    const openPriorityFor = ref<string | null>(null);
    const openTagFor = ref<string | null>(null);
    const tagKeyword = ref("");
    const tagsModel = reactive<Record<string, string[]>>({});
    const planTimeModel = reactive<Record<string, DateRange>>({});
    const openStatusFor = ref<string | null>(null);
    const rowStatusKeyword = ref("");
    const openOwnerFor = ref<string | null>(null);
    const ownerEditKeyword = ref("");
    const openCollaboratorFor = ref<string | null>(null);
    const collaboratorKeyword = ref("");
    const openPlanTimeFor = ref<string | null>(null);

    // ==================== 创建Drawer状态 ====================
    const createBugDrawerOpen = ref(false);
    const createBugPriorityDropdownOpen = ref(false);
    const createBugDrawerMode = ref<"create" | "detail">("create");
    const createBugAttachments = ref<BugAttachment[]>([]);
    const createAttachmentInputRef = ref<HTMLInputElement | null>(null);
    const createAssigneeDropdownOpen = ref(false);
    const createAssigneeKeyword = ref("");

    const createInitialBugForm = (): NewBugForm => ({
        title: "",
        owner: "",
        collaborators: [],
        type: "缺陷",
        planTime: [],
        project: "VortMall",
        iteration: "",
        version: "",
        priority: "",
        tags: [],
        repo: "",
        branch: "",
        startAt: "",
        endAt: "",
        remark: "",
        description: "环境：-\n账号：-\n密码：-\n前置条件：-\n操作步骤：-\n实际结果：-\n预期结果：-"
    });
    const createBugForm = reactive<NewBugForm>(createInitialBugForm());

    // ==================== 详情Drawer状态 ====================
    const detailActiveTab = ref("detail");
    const detailSelectedWorkNo = ref("");
    const detailStatusDropdownOpen = ref(false);
    const detailStatusKeyword = ref("");
    const detailAssigneeDropdownOpen = ref(false);
    const detailAssigneeKeyword = ref("");
    const detailDescEditing = ref(false);
    const detailDescDraft = ref("");
    const detailBottomTab = ref<"comments" | "logs">("comments");
    const detailCommentDraft = ref("");
    const detailCommentsMap = reactive<Record<string, DetailComment[]>>({});
    const detailLogsMap = reactive<Record<string, DetailLog[]>>({});

    // ==================== 展开状态 ====================
    const typeGroupOpen = reactive<Record<WorkType, boolean>>({
        需求: true,
        任务: true,
        缺陷: true
    });
    const ownerGroupOpen = reactive<Record<string, boolean>>({});
    const ownerEditGroupOpen = reactive<Record<string, boolean>>({});
    const collaboratorGroupOpen = reactive<Record<string, boolean>>({});
    const detailAssigneeGroupOpen = reactive<Record<string, boolean>>({});
    const createAssigneeGroupOpen = reactive<Record<string, boolean>>({});
    const isGroupOpen = (map: Record<string, boolean>, label: string) => map[label] !== false;
    const collaboratorsModel = reactive<Record<string, string[]>>({});

    // ==================== 常量 ====================
    const avatarBgPalette = ["#2f80ed", "#5b8ff9", "#9b59b6", "#27ae60", "#f39c12", "#e67e22", "#16a085", "#8e44ad"];
    const tagColorPalette = ["#ef4444", "#d946ef", "#eab308", "#22c55e", "#3b82f6", "#f97316", "#14b8a6", "#8b5cf6"];
    const detailCurrentUser = "当前用户";

    // ==================== 辅助函数 ====================
    const toWorkNo = (index: number): string => {
        let n = index + 1000;
        let code = "";
        for (let i = 0; i < 6; i++) {
            code = String.fromCharCode(65 + (n % 26)) + code;
            n = Math.floor(n / 26);
        }
        return `#${code}`;
    };

    const buildDataset = (): RowItem[] => {
        const owners = ["张三", "李四", "王五", "赵六", "钱七", "孙八"];
        const creators = ["周明", "林羽", "陈尧", "方怡"];
        const types: WorkType[] = ["缺陷", "需求", "任务"];
        const priorities: Priority[] = ["urgent", "high", "medium", "low"];
        const statuses: Status[] = ["待确认", "修复中", "已修复", "延期处理", "设计如此", "再次打开", "无法复现", "已关闭", "暂时搁置"];
        const tagPool = ["后端", "前端", "测试", "性能", "稳定性", "文档", "发布", "核心"];
        const list: RowItem[] = [];

        for (let i = 1; i <= 79; i++) {
            const created = new Date(Date.now() - i * 1000 * 60 * 60 * 5);
            const planStart = new Date(Date.now() + (i % 12) * 1000 * 60 * 60 * 24);
            const planEnd = new Date(planStart.getTime() + ((i % 6) + 1) * 1000 * 60 * 60 * 24);
            const ownerName = owners[i % owners.length]!;
            const collab = [owners[(i + 1) % owners.length]!, owners[(i + 2) % owners.length]!];

            list.push({
                workNo: toWorkNo(i),
                title: `【${types[i % types.length]}】示例工作项标题 ${i}，用于对齐 Gitee 风格列表展示`,
                priority: priorities[i % priorities.length]!,
                tags: [tagPool[i % tagPool.length]!, tagPool[(i + 3) % tagPool.length]!],
                status: statuses[i % statuses.length]!,
                createdAt: created.toISOString().slice(0, 16).replace("T", " "),
                collaborators: collab,
                type: types[i % types.length]!,
                planTime: [planStart.toISOString().slice(0, 10), planEnd.toISOString().slice(0, 10)],
                description: "",
                owner: ownerName,
                creator: creators[i % creators.length]!
            });
        }

        return list;
    };

    const getAvatarBg = (name: string): string => {
        let hash = 0;
        for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
        return avatarBgPalette[Math.abs(hash) % avatarBgPalette.length]!;
    };

    const getAvatarLabel = (name: string): string => name.slice(0, 1).toUpperCase();

    const getTagColor = (name: string): string => {
        let hash = 0;
        for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
        return tagColorPalette[Math.abs(hash) % tagColorPalette.length]!;
    };

    // ==================== 行内编辑方法 ====================
    const getRowPriority = (record: RowItem, text?: Priority): Priority => priorityModel[record.workNo] ?? text ?? record.priority;
    const getRowStatus = (record: RowItem, text?: Status): Status => (statusModel[record.workNo] ?? text ?? record.status) as Status;
    const getRowOwner = (record: RowItem, text?: string): string => ownerModel[record.workNo] ?? text ?? record.owner;
    const getRowCollaborators = (record: RowItem, text?: string[]): string[] => collaboratorsModel[record.workNo] ?? text ?? record.collaborators;
    const getRowTags = (record: RowItem, text?: string[]): string[] => tagsModel[record.workNo] ?? text ?? record.tags;
    const getRowPlanTime = (record: RowItem, text?: DateRange): DateRange => planTimeModel[record.workNo] ?? text ?? record.planTime;

    // 临时存储
    const statusModel = reactive<Record<string, Status>>({});
    const ownerModel = reactive<Record<string, string>>({});

    const togglePriorityMenu = (workNo: string) => {
        openPriorityFor.value = openPriorityFor.value === workNo ? null : workNo;
        openTagFor.value = null;
        openStatusFor.value = null;
        openOwnerFor.value = null;
        openCollaboratorFor.value = null;
        openPlanTimeFor.value = null;
    };

    const selectPriority = (workNo: string, value: Priority) => {
        priorityModel[workNo] = value;
        openPriorityFor.value = null;
    };

    const toggleRowStatusMenu = (workNo: string) => {
        openStatusFor.value = openStatusFor.value === workNo ? null : workNo;
        openPriorityFor.value = null;
        openTagFor.value = null;
        openOwnerFor.value = null;
        openCollaboratorFor.value = null;
        openPlanTimeFor.value = null;
    };

    const selectRowStatus = (record: RowItem, value: Status) => {
        statusModel[record.workNo] = value;
        openStatusFor.value = null;
    };

    const toggleRowOwnerMenu = (workNo: string) => {
        openOwnerFor.value = openOwnerFor.value === workNo ? null : workNo;
        openPriorityFor.value = null;
        openTagFor.value = null;
        openStatusFor.value = null;
        openCollaboratorFor.value = null;
        openPlanTimeFor.value = null;
    };

    const selectRowOwner = (record: RowItem, value: string) => {
        ownerModel[record.workNo] = value;
        openOwnerFor.value = null;
    };

    const toggleCollaboratorMenu = (workNo: string) => {
        openCollaboratorFor.value = openCollaboratorFor.value === workNo ? null : workNo;
        openPriorityFor.value = null;
        openTagFor.value = null;
        openStatusFor.value = null;
        openOwnerFor.value = null;
        openPlanTimeFor.value = null;
    };

    const toggleRowCollaborator = (record: RowItem, member: string, text?: string[]) => {
        const current = getRowCollaborators(record, text);
        const idx = current.indexOf(member);
        if (idx > -1) current.splice(idx, 1);
        else current.push(member);
        collaboratorsModel[record.workNo] = [...current];
    };

    const toggleTagMenu = (workNo: string) => {
        openTagFor.value = openTagFor.value === workNo ? null : workNo;
        openPriorityFor.value = null;
        openStatusFor.value = null;
        openOwnerFor.value = null;
        openCollaboratorFor.value = null;
        openPlanTimeFor.value = null;
    };

    const toggleTagOption = (record: RowItem, tag: string, text?: string[]) => {
        const current = getRowTags(record, text);
        const idx = current.indexOf(tag);
        if (idx > -1) current.splice(idx, 1);
        else current.push(tag);
        tagsModel[record.workNo] = [...current];
    };

    const finishTagEdit = () => {
        openTagFor.value = null;
    };

    const togglePlanTimeMenu = (workNo: string) => {
        openPlanTimeFor.value = openPlanTimeFor.value === workNo ? null : workNo;
        openPriorityFor.value = null;
        openTagFor.value = null;
        openStatusFor.value = null;
        openOwnerFor.value = null;
        openCollaboratorFor.value = null;
    };

    const onPlanTimeChange = (workNo: string, value?: DateRange) => {
        planTimeModel[workNo] = value || ["", ""];
        openPlanTimeFor.value = null;
    };

    const getRowPlanTimeText = (record: RowItem, text?: DateRange): string => {
        const pt = getRowPlanTime(record, text);
        if (!pt || !pt[0]) return "设置计划时间";
        const start = pt[0];
        const end = pt[1];
        const currentYear = String(new Date().getFullYear());
        const stripYear = (d: string) => d.slice(5);
        if (!end) {
            return (start.startsWith(currentYear) ? stripYear(start) : start) + " 开始";
        }
        const startYear = start.slice(0, 4);
        const endYear = end.slice(0, 4);
        if (startYear === endYear) {
            const isCurrentYear = startYear === currentYear;
            return `${isCurrentYear ? stripYear(start) : start}~${stripYear(end)}`;
        }
        return `${start}~${end}`;
    };

    const getCollapsedTags = (tags: string[], resolvedWidth?: string | number): { visible: string[]; hidden: number } => {
        const maxWidth = typeof resolvedWidth === "number" ? resolvedWidth : parseInt(resolvedWidth || "150") || 150;
        let currentWidth = 0;
        const visible: string[] = [];
        let hidden = 0;

        for (const tag of tags) {
            const tagWidth = tag.length * 12 + 12;
            if (currentWidth + tagWidth < maxWidth && visible.length < 3) {
                visible.push(tag);
                currentWidth += tagWidth;
            } else {
                hidden++;
            }
        }

        return { visible, hidden };
    };

    const getTagRenderInfo = (record: RowItem, text: string[] | undefined, resolvedWidth?: string | number) => {
        return getCollapsedTags(getRowTags(record, text), resolvedWidth);
    };

    // ==================== 筛选方法 ====================
    const filteredOwnerGroups = computed(() => {
        if (!ownerKeyword.value) return ownerGroups.value;
        const kw = ownerKeyword.value.toLowerCase();
        return ownerGroups.value
            .map(g => ({ ...g, members: g.members.filter(m => m.toLowerCase().includes(kw)) }))
            .filter(g => g.members.length > 0);
    });

    const filteredOwnerEditGroups = computed(() => {
        if (!ownerEditKeyword.value) return ownerGroups.value;
        const kw = ownerEditKeyword.value.toLowerCase();
        return ownerGroups.value
            .map(g => ({ ...g, members: g.members.filter(m => m.toLowerCase().includes(kw)) }))
            .filter(g => g.members.length > 0);
    });

    const filteredCollaboratorGroups = computed(() => {
        if (!collaboratorKeyword.value) return ownerGroups.value;
        const kw = collaboratorKeyword.value.toLowerCase();
        return ownerGroups.value
            .map(g => ({ ...g, members: g.members.filter(m => m.toLowerCase().includes(kw)) }))
            .filter(g => g.members.length > 0);
    });

    const filteredStatusOptions = computed(() => {
        if (!statusKeyword.value) return statusFilterOptions;
        const kw = statusKeyword.value.toLowerCase();
        return statusFilterOptions.filter(o => o.label.toLowerCase().includes(kw));
    });

    const filteredRowStatusOptions = computed(() => {
        if (!rowStatusKeyword.value) return statusFilterOptions;
        const kw = rowStatusKeyword.value.toLowerCase();
        return statusFilterOptions.filter(o => o.label.toLowerCase().includes(kw));
    });

    const filteredTagOptions = computed(() => {
        if (!tagKeyword.value) return tagOptions;
        const kw = tagKeyword.value.toLowerCase();
        return tagOptions.filter(t => t.toLowerCase().includes(kw));
    });

    const filteredDetailAssigneeGroups = computed(() => {
        if (!detailAssigneeKeyword.value) return ownerGroups.value;
        const kw = detailAssigneeKeyword.value.toLowerCase();
        return ownerGroups.value
            .map(g => ({ ...g, members: g.members.filter(m => m.toLowerCase().includes(kw)) }))
            .filter(g => g.members.length > 0);
    });

    const filteredCreateAssigneeGroups = computed(() => {
        if (!createAssigneeKeyword.value) return ownerGroups.value;
        const kw = createAssigneeKeyword.value.toLowerCase();
        return ownerGroups.value
            .map(g => ({ ...g, members: g.members.filter(m => m.toLowerCase().includes(kw)) }))
            .filter(g => g.members.length > 0);
    });

    const filteredDetailStatusOptions = computed(() => {
        if (!detailStatusKeyword.value) return statusFilterOptions;
        const kw = detailStatusKeyword.value.toLowerCase();
        return statusFilterOptions.filter(o => o.label.toLowerCase().includes(kw));
    });

    const typeGroups = computed<WorkType[]>(() => ["缺陷", "需求", "任务"]);

    const toggleOwnerGroup = (group: string) => { ownerGroupOpen[group] = !isGroupOpen(ownerGroupOpen, group); };
    const toggleOwnerEditGroup = (group: string) => { ownerEditGroupOpen[group] = !isGroupOpen(ownerEditGroupOpen, group); };
    const toggleCollaboratorGroup = (group: string) => { collaboratorGroupOpen[group] = !isGroupOpen(collaboratorGroupOpen, group); };
    const toggleTypeGroup = (group: WorkType) => { typeGroupOpen[group] = !typeGroupOpen[group]; };
    const toggleDetailAssigneeGroup = (group: string) => { detailAssigneeGroupOpen[group] = !isGroupOpen(detailAssigneeGroupOpen, group); };
    const toggleCreateAssigneeGroup = (group: string) => { createAssigneeGroupOpen[group] = !isGroupOpen(createAssigneeGroupOpen, group); };

    const selectOwner = (value: string) => {
        owner.value = value;
        ownerDropdownOpen.value = false;
    };
    const selectType = (value: WorkType) => {
        type.value = value;
        typeDropdownOpen.value = false;
    };
    const selectStatus = (value: string) => {
        status.value = value;
        statusDropdownOpen.value = false;
    };

    // ==================== 创建表单方法 ====================
    const resetCreateBugForm = () => {
        const form = createInitialBugForm();
        Object.assign(createBugForm, form);
        createBugAttachments.value = [];
    };

    const handleCreateBug = () => {
        resetCreateBugForm();
        createBugDrawerMode.value = "create";
        createBugDrawerOpen.value = true;
    };

    const handleCancelCreateBug = () => {
        createBugDrawerOpen.value = false;
    };

    const handleSubmitCreateBug = () => {
        createBugDrawerOpen.value = false;
    };

    const toggleCreateBugPriorityMenu = () => {
        createBugPriorityDropdownOpen.value = !createBugPriorityDropdownOpen.value;
    };

    const selectCreateBugPriority = (value: Priority) => {
        createBugForm.priority = value;
        createBugPriorityDropdownOpen.value = false;
    };

    const toggleDetailAssigneeMenu = () => {
        detailAssigneeDropdownOpen.value = !detailAssigneeDropdownOpen.value;
    };

    const toggleCreateAssigneeMenu = () => {
        createAssigneeDropdownOpen.value = !createAssigneeDropdownOpen.value;
    };

    const isDetailOwner = (member: string): boolean => detailCurrentRecord.value?.owner === member;
    const isDetailCollaborator = (member: string): boolean => detailCurrentRecord.value?.collaborators.includes(member) || false;
    const isCreateOwner = (member: string): boolean => createBugForm.owner === member;
    const isCreateCollaborator = (member: string): boolean => createBugForm.collaborators.includes(member);

    const setDetailOwner = (member: string) => {
        if (detailCurrentRecord.value) {
            detailCurrentRecord.value.owner = member;
            detailAssigneeDropdownOpen.value = false;
        }
    };

    const setCreateOwner = (member: string) => {
        createBugForm.owner = member;
        createAssigneeDropdownOpen.value = false;
    };

    const toggleDetailCollaborator = (member: string) => {
        if (!detailCurrentRecord.value) return;
        const idx = detailCurrentRecord.value.collaborators.indexOf(member);
        if (idx > -1) detailCurrentRecord.value.collaborators.splice(idx, 1);
        else detailCurrentRecord.value.collaborators.push(member);
    };

    const toggleCreateCollaborator = (member: string) => {
        const idx = createBugForm.collaborators.indexOf(member);
        if (idx > -1) createBugForm.collaborators.splice(idx, 1);
        else createBugForm.collaborators.push(member);
    };

    // ==================== 详情相关方法 ====================
    const detailCurrentRecord = computed<RowItem | null>(() => {
        if (!detailSelectedWorkNo.value) return null;
        return allData.value.find(r => r.workNo === detailSelectedWorkNo.value) || null;
    });

    const detailComments = computed<DetailComment[]>(() => {
        if (!detailSelectedWorkNo.value) return [];
        return detailCommentsMap[detailSelectedWorkNo.value] || [];
    });

    const detailLogs = computed<DetailLog[]>(() => {
        if (!detailSelectedWorkNo.value) return [];
        return detailLogsMap[detailSelectedWorkNo.value] || [];
    });

    const ensureDetailPanelsData = (record: RowItem) => {
        if (!detailCommentsMap[record.workNo]) {
            detailCommentsMap[record.workNo] = [
                { id: "1", author: "张三", createdAt: "2024-01-15 10:30", content: "这个问题我已经复现了，确实存在。" },
                { id: "2", author: "李四", createdAt: "2024-01-15 14:20", content: "我这边也确认了，准备开始修复。" }
            ];
        }
        if (!detailLogsMap[record.workNo]) {
            detailLogsMap[record.workNo] = [
                { id: "1", actor: "王五", createdAt: "2024-01-14 09:00", action: "创建了此工作项" },
                { id: "2", actor: "张三", createdAt: "2024-01-15 10:30", action: "修改了状态为修复中" }
            ];
        }
    };

    const appendDetailLog = (action: string) => {
        if (!detailSelectedWorkNo.value) return;
        if (!detailLogsMap[detailSelectedWorkNo.value]) {
            detailLogsMap[detailSelectedWorkNo.value] = [];
        }
        detailLogsMap[detailSelectedWorkNo.value].unshift({
            id: Date.now().toString(),
            actor: detailCurrentUser,
            createdAt: new Date().toISOString().slice(0, 16).replace("T", " "),
            action
        });
    };

    const submitDetailComment = () => {
        if (!detailCommentDraft.value.trim() || !detailSelectedWorkNo.value) return;
        if (!detailCommentsMap[detailSelectedWorkNo.value]) {
            detailCommentsMap[detailSelectedWorkNo.value] = [];
        }
        detailCommentsMap[detailSelectedWorkNo.value].push({
            id: Date.now().toString(),
            author: detailCurrentUser,
            createdAt: new Date().toISOString().slice(0, 16).replace("T", " "),
            content: detailCommentDraft.value
        });
        detailCommentDraft.value = "";
    };

    const toggleDetailStatusMenu = () => {
        detailStatusDropdownOpen.value = !detailStatusDropdownOpen.value;
    };

    const selectDetailStatus = (value: Status) => {
        if (detailCurrentRecord.value) {
            detailCurrentRecord.value.status = value;
            appendDetailLog(`修改状态为${value}`);
        }
        detailStatusDropdownOpen.value = false;
    };

    const openDetailDescEditor = () => {
        detailDescEditing.value = true;
        detailDescDraft.value = detailCurrentRecord.value?.description || "";
    };

    const cancelDetailDescEditor = () => {
        detailDescEditing.value = false;
        detailDescDraft.value = "";
    };

    const saveDetailDescEditor = () => {
        if (detailCurrentRecord.value) {
            detailCurrentRecord.value.description = detailDescDraft.value;
            appendDetailLog("更新了描述");
        }
        detailDescEditing.value = false;
    };

    const handleOpenBugDetail = (record: RowItem) => {
        detailSelectedWorkNo.value = record.workNo;
        detailActiveTab.value = "detail";
        ensureDetailPanelsData(record);
    };

    // ==================== 附件处理 ====================
    const openCreateAttachmentDialog = () => {
        createAttachmentInputRef.value?.click();
    };

    const onCreateAttachmentChange = (event: Event) => {
        const target = event.target as HTMLInputElement;
        const files = target.files;
        if (!files) return;

        for (let i = 0; i < files.length; i++) {
            const file = files[i]!;
            createBugAttachments.value.push({
                id: Date.now().toString() + i,
                name: file.name,
                size: file.size
            });
        }
        target.value = "";
    };

    const removeCreateAttachment = (id: string) => {
        const idx = createBugAttachments.value.findIndex(a => a.id === id);
        if (idx > -1) createBugAttachments.value.splice(idx, 1);
    };

    // ==================== ProTable 配置 ====================
    const queryParams = computed<BugFilterParams>(() => ({
        page: 1,
        size: 20,
        keyword: keyword.value,
        owner: owner.value,
        type: type.value as WorkType | "",
        status: status.value as Status | ""
    }));

    const onReset = () => {
        keyword.value = "";
        owner.value = "";
        type.value = "";
        status.value = "";
    };

    const request = async (params: ProTableRequestParams): Promise<ProTableResponse<RowItem>> => {
        const filtered = allData.value.filter(item => {
            if (keyword.value && !item.title.toLowerCase().includes(keyword.value.toLowerCase())) return false;
            if (owner.value && item.owner !== owner.value) return false;
            if (type.value && item.type !== type.value) return false;
            if (status.value && item.status !== status.value) return false;
            return true;
        });

        const page = params.page || 1;
        const size = params.size || 20;
        const start = (page - 1) * size;
        const end = start + size;

        return {
            records: filtered.slice(start, end),
            total: filtered.length
        };
    };

    // ==================== 全局点击关闭 ====================
    const onGlobalClick = () => {
        openPriorityFor.value = null;
        openTagFor.value = null;
        openStatusFor.value = null;
        openOwnerFor.value = null;
        openCollaboratorFor.value = null;
        openPlanTimeFor.value = null;
        ownerDropdownOpen.value = false;
        typeDropdownOpen.value = false;
        statusDropdownOpen.value = false;
        ownerDropdownOpen.value = false;
    };

    // ==================== 初始化 ====================
    const initData = () => {
        allData.value = buildDataset();
        nextWorkNoIndex.value = allData.value.length + 1;
        totalCount.value = allData.value.length;
    };

    initData();

    return {
        // 筛选状态
        keyword, owner, ownerDropdownOpen, ownerKeyword, type, typeDropdownOpen, typeKeyword, status, statusDropdownOpen, statusKeyword,
        // 列表状态
        allData, totalCount, tableRef, nextWorkNoIndex,
        // 行内编辑状态
        priorityModel, openPriorityFor, openTagFor, tagKeyword, tagsModel, planTimeModel, openStatusFor, rowStatusKeyword, openOwnerFor, ownerEditKeyword, openCollaboratorFor, collaboratorKeyword, openPlanTimeFor,
        // 创建Drawer状态
        createBugDrawerOpen, createBugPriorityDropdownOpen, createBugDrawerMode, createBugAttachments, createAttachmentInputRef, createAssigneeDropdownOpen, createAssigneeKeyword, createBugForm,
        // 详情Drawer状态
        detailActiveTab, detailSelectedWorkNo, detailStatusDropdownOpen, detailStatusKeyword, detailAssigneeDropdownOpen, detailAssigneeKeyword, detailDescEditing, detailDescDraft, detailBottomTab, detailCommentDraft, detailCommentsMap, detailLogsMap,
        // 展开状态
        ownerGroups, isGroupOpen, typeGroupOpen, ownerGroupOpen, ownerEditGroupOpen, collaboratorGroupOpen, detailAssigneeGroupOpen, createAssigneeGroupOpen, collaboratorsModel,
        // 辅助函数
        toWorkNo, getAvatarBg, getAvatarLabel, getTagColor, formatFileSize, getWorkTypeIconClass,
        // 行内编辑方法
        getRowPriority, getRowStatus, getRowOwner, getRowCollaborators, getRowTags, getRowPlanTime, togglePriorityMenu, selectPriority, toggleRowStatusMenu, selectRowStatus, toggleRowOwnerMenu, selectRowOwner, toggleCollaboratorMenu, toggleRowCollaborator, toggleTagMenu, toggleTagOption, finishTagEdit, togglePlanTimeMenu, onPlanTimeChange, getRowPlanTimeText, getCollapsedTags, getTagRenderInfo,
        // 筛选方法
        filteredOwnerGroups, filteredOwnerEditGroups, filteredCollaboratorGroups, filteredStatusOptions, filteredRowStatusOptions, filteredTagOptions, filteredDetailAssigneeGroups, filteredCreateAssigneeGroups, filteredDetailStatusOptions, typeGroups, toggleOwnerGroup, toggleOwnerEditGroup, toggleCollaboratorGroup, toggleTypeGroup, toggleDetailAssigneeGroup, toggleCreateAssigneeGroup, selectOwner, selectType, selectStatus,
        // 创建表单方法
        resetCreateBugForm, handleCreateBug, handleCancelCreateBug, handleSubmitCreateBug, toggleCreateBugPriorityMenu, selectCreateBugPriority, toggleDetailAssigneeMenu, toggleCreateAssigneeMenu, isDetailOwner, isDetailCollaborator, isCreateOwner, isCreateCollaborator, setDetailOwner, setCreateOwner, toggleDetailCollaborator, toggleCreateCollaborator,
        // 详情方法
        detailCurrentRecord, detailComments, detailLogs, ensureDetailPanelsData, appendDetailLog, submitDetailComment, toggleDetailStatusMenu, selectDetailStatus, openDetailDescEditor, cancelDetailDescEditor, saveDetailDescEditor, handleOpenBugDetail,
        // 附件方法
        openCreateAttachmentDialog, onCreateAttachmentChange, removeCreateAttachment,
        // ProTable 配置
        queryParams, request, onReset, tableRef,
        // 全局
        onGlobalClick, initData
    };
}

// 辅助函数（未导出，需要从 hook 返回）
function getWorkTypeIconClass(type: WorkType): string {
    if (type === "需求") return "work-type-icon-demand";
    if (type === "任务") return "work-type-icon-task";
    return "work-type-icon-bug";
}

