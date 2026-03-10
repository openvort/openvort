<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ProTable, TableCell, type ProTableColumn, type ProTableRequestParams, type ProTableResponse } from "@/components/vort-biz";
import { Popover, message } from "@/components/vort";
import VortEditor from "@/components/vort-biz/editor/VortEditor.vue";
import MarkdownView from "@/components/vort-biz/editor/MarkdownView.vue";
import { Pencil } from "lucide-vue-next";
import WorkItemPriority from "@/components/vort-biz/work-item/WorkItemPriority.vue";
import WorkItemStatus from "@/components/vort-biz/work-item/WorkItemStatus.vue";
import WorkItemFilters from "@/components/vort-biz/work-item/WorkItemFilters.vue";
import WorkItemDetail from "./work-item/WorkItemDetail.vue";
import WorkItemCreate from "./work-item/WorkItemCreate.vue";
import { useWorkItemCommon } from "./work-item/useWorkItemCommon";
import {
    getVortflowStory, getVortflowStories, getVortflowTasks, getVortflowBugs,
    getVortflowProjects, createVortflowStory, createVortflowTask, createVortflowBug,
    deleteVortflowStory, deleteVortflowTask, deleteVortflowBug,
    updateVortflowStory, updateVortflowTask, updateVortflowBug
} from "@/api";
import type {
    WorkItemType,
    Priority,
    Status,
    DateRange,
    WorkItemTableProps,
    NewBugForm,
    RowItem,
    DetailComment,
    DetailLog,
    CreateBugAttachment,
    StatusOption
} from "@/components/vort-biz/work-item/WorkItemTable.types";

const props = withDefaults(defineProps<WorkItemTableProps>(), {
    pageTitle: "缺陷",
    createButtonText: "+ 新建缺陷",
    createDrawerTitle: "新建缺陷",
    detailDrawerTitle: "缺陷详情",
    descriptionPlaceholder: "请填写缺陷描述",
    useApi: false
});

const route = useRoute();
const router = useRouter();

const {
    memberOptions,
    ownerGroups,
    getStatusOptionsByType,
    getStatusOption,
    priorityOptions,
    priorityLabelMap,
    priorityClassMap,
    getAvatarBg,
    getAvatarLabel,
    getMemberAvatarUrl,
    loadMemberOptions,
    getMemberIdByName,
    getMemberNameById,
    getWorkItemTypeIconClass,
    getWorkItemTypeIconSymbol,
    mapBackendStateToStatus,
    mapBackendPriority,
    formatCnTime,
    formatDate,
    toBackendPriorityLevel,
    toTaskEstimateHours,
    getBackendStatesByDisplayStatus,
    bugStatusFilterOptions,
    demandStatusFilterOptions,
    taskStatusFilterOptions,
} = useWorkItemCommon();

const keyword = ref("");
const owner = ref("");
const ownerDropdownOpen = ref(false);
const ownerKeyword = ref("");
const openOwnerFor = ref<string | null>(null);
const ownerEditKeyword = ref("");
const openCollaboratorFor = ref<string | null>(null);
const collaboratorKeyword = ref("");
const type = ref<WorkItemType | "">(props.type ?? "");
const typeDropdownOpen = ref(false);
const typeKeyword = ref("");
const status = ref("");
const statusDropdownOpen = ref(false);
const statusKeyword = ref("");
const openStatusFor = ref<string | null>(null);
const rowStatusKeyword = ref("");
const rowStatusType = ref<WorkItemType>(props.type ?? "缺陷");
const openPlanTimeFor = ref<string | null>(null);
const totalCount = ref(0);
const createBugDrawerOpen = computed({
    get: () => {
        const action = route.query.action as string;
        return action === "create" || action === "detail";
    },
    set: (val: boolean) => {
        if (!val) {
            router.replace({ query: { ...route.query, action: undefined, id: undefined, parentId: undefined } });
        }
    }
});
const createBugPriorityDropdownOpen = ref(false);
const createBugDrawerMode = ref<"create" | "detail">("create");
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
const createWorkItemRef = ref<{
    submit: () => NewBugForm | null;
    reset: () => void;
    cancel: () => void;
} | null>(null);
const createBugAttachments = ref<CreateBugAttachment[]>([]);
const createAttachmentInputRef = ref<HTMLInputElement | null>(null);
const createAssigneeDropdownOpen = ref(false);
const createAssigneeKeyword = ref("");

const defaultDescriptionTemplate = [
    "环境：请填写",
    "",
    "账号：请填写",
    "",
    "密码：请填写",
    "",
    "前置条件：请填写",
    "",
    "操作步骤：",
    "步骤1：",
    "步骤2：",
    "",
    "实际结果：请填写",
    "",
    "预期结果：请填写",
].join("\n");

const createInitialBugForm = (): NewBugForm => ({
    title: "",
    owner: "",
    collaborators: [],
    type: props.type ?? "缺陷",
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
    description: defaultDescriptionTemplate
});
const createBugForm = reactive<NewBugForm>(createInitialBugForm());
const apiProjects = ref<Array<{ id: string; name: string }>>([]);
const apiStories = ref<Array<{ id: string; title: string }>>([]);
const storyRowsById = reactive<Record<string, RowItem>>({});
const storyChildrenMap = reactive<Record<string, RowItem[]>>({});
const expandedStoryIds = reactive<Record<string, boolean>>({});
const expandingStoryIds = reactive<Record<string, boolean>>({});
const createParentStoryId = ref("");
const createProjectId = ref("");
const selectedRowKeys = ref<Array<string | number>>([]);
const selectedRows = ref<RowItem[]>([]);
const pinnedRowsByType = reactive<Record<WorkItemType, RowItem[]>>({
    需求: [],
    任务: [],
    缺陷: [],
});

const createBugTagOptions = ["客户需求", "演示站", "运营需求", "待开会确认", "已发布", "高优先", "稳定性", "UI优化"];
const createBugProjectOptions = ["VortMall", "OpenVort", "VortFlow"];
const createBugRepoOptions = ["openvort/web", "openvort/core", "openvort/vortflow"];
const createBugBranchOptions = ["develop", "develop-wzh", "release/1.0"];

const allStatusFilterOptions: StatusOption[] = Array.from(
    new Map(
        [...demandStatusFilterOptions, ...taskStatusFilterOptions, ...bugStatusFilterOptions].map((item) => [item.value, item])
    ).values()
);

const priorityModel = reactive<Record<string, Priority>>({});
const openPriorityFor = ref<string | null>(null);
const tagPopoverOpen = reactive<Record<string, boolean>>({});
const tagKeyword = ref("");
const createTagDropdownOpen = ref(false);
const createTagKeyword = ref("");
const tagsModel = reactive<Record<string, string[]>>({});
const baseTagOptions = ["客户需求", "演示站", "运营需求", "待开会确认", "已发布", "高优先", "稳定性", "UI优化", "S1", "S2", "S3", "S4", "develop", "test"];
const dynamicTagOptions = ref<string[]>([]);
const newTagDialogOpen = ref(false);
const newTagName = ref("");
const newTagColor = ref<string>("");
const newTagTargetRecord = ref<RowItem | null>(null);
const newTagTargetText = ref<string[] | undefined>(undefined);
const planTimeModel = reactive<Record<string, any>>({});
const typeGroupOpen = reactive<Record<WorkItemType, boolean>>({
    需求: true,
    任务: true,
    缺陷: true
});
const ownerGroupOpen = reactive<Record<string, boolean>>({
    项目成员: true,
    企业成员: true,
    离职人员: true
});
const ownerEditGroupOpen = reactive<Record<string, boolean>>({
    项目成员: true,
    企业成员: true,
    离职人员: true
});
const collaboratorGroupOpen = reactive<Record<string, boolean>>({
    项目成员: true,
    企业成员: true,
    离职人员: true
});
const detailAssigneeGroupOpen = reactive<Record<string, boolean>>({
    项目成员: true,
    企业成员: true,
    离职人员: true
});
const createAssigneeGroupOpen = reactive<Record<string, boolean>>({
    项目成员: true,
    企业成员: true,
    离职人员: true
});
const collaboratorsModel = reactive<Record<string, string[]>>({});

const ensureOwnerGroupMapEntries = () => {
    ownerGroups.value.forEach((group) => {
        if (ownerGroupOpen[group.label] === undefined) ownerGroupOpen[group.label] = true;
        if (ownerEditGroupOpen[group.label] === undefined) ownerEditGroupOpen[group.label] = true;
        if (collaboratorGroupOpen[group.label] === undefined) collaboratorGroupOpen[group.label] = true;
        if (detailAssigneeGroupOpen[group.label] === undefined) detailAssigneeGroupOpen[group.label] = true;
        if (createAssigneeGroupOpen[group.label] === undefined) createAssigneeGroupOpen[group.label] = true;
    });
};

const rebuildMockDataset = () => {
    if (props.useApi) return;
    allData.value = buildDataset();
    totalCount.value = allData.value.length;
    Object.keys(planTimeModel).forEach((key) => delete planTimeModel[key]);
    for (const row of allData.value) {
        planTimeModel[row.workNo] = [...row.planTime];
    }
    collectTagOptions(allData.value);
    tableRef.value?.refresh?.();
};

const closeRowPopovers = () => {
    openPriorityFor.value = null;
    for (const key in tagPopoverOpen) {
        tagPopoverOpen[key] = false;
    }
    openStatusFor.value = null;
    openOwnerFor.value = null;
    openCollaboratorFor.value = null;
    openPlanTimeFor.value = null;
};
const resolveActiveType = (): WorkItemType => {
    if (props.type) return props.type;
    if (type.value === "需求" || type.value === "任务" || type.value === "缺陷") return type.value;
    return "缺陷";
};
const currentStatusFilterOptions = computed(() => getStatusOptionsByType(resolveActiveType()));

const toWorkNo = (index: number): string => {
    let n = index + 1000;
    let code = "";
    for (let i = 0; i < 6; i++) {
        code = String.fromCharCode(65 + (n % 26)) + code;
        n = Math.floor(n / 26);
    }
    return `#${code}`;
};

const normalizeDateValue = (value: unknown): string => {
    if (value instanceof Date) return formatDate(value);
    if (typeof value === "string") {
        const direct = value.trim();
        if (/^\d{4}-\d{2}-\d{2}$/.test(direct)) return direct;
        const parsed = new Date(direct);
        if (!Number.isNaN(parsed.getTime())) return formatDate(parsed);
    }
    return "";
};

const collectTagOptions = (rows: RowItem[]) => {
    const set = new Set<string>(baseTagOptions);
    for (const row of rows) {
        for (const tag of row.tags || []) {
            if (tag) set.add(tag);
        }
    }
    dynamicTagOptions.value = [...set];
};

const defaultBugDescription = defaultDescriptionTemplate;
const detailCurrentUser = "当前用户";
const formatFileSize = (size: number): string => {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

const buildDataset = (): RowItem[] => {
    const creators = ["周明", "林羽", "陈尧", "方怡"];
    const priorities: Priority[] = ["urgent", "high", "medium", "low"];
    const memberPool = Array.from(new Set(ownerGroups.value.flatMap((group) => [...group.members])));
    const tagPool = Array.from(new Set([...baseTagOptions, "订单域", "支付域", "库存域", "促销域", "用户域", "网关", "前端H5", "商家后台"]));
    const types: WorkItemType[] = props.type ? [props.type] : ["需求", "任务", "缺陷"];
    const countPerType = 50;
    const demandTitles = [
        "支持商家后台批量导入 SKU 并自动校验条码重复",
        "订单中心新增按渠道维度的成交额趋势看板",
        "会员中心支持成长值规则按活动模板配置",
        "结算中心支持分账结果失败自动补偿任务",
        "营销中心新增满减与优惠券叠加规则配置",
        "商品中心支持多规格图片按颜色维度管理",
        "风控中心接入异常下单实时拦截策略",
        "运费模板支持区域阶梯计价和偏远地区附加费",
        "门店自提支持核销码失效时间自定义",
        "售后工单中心支持按退款原因统计看板"
    ];
    const taskTitles = [
        "拆分订单服务结算逻辑到 settlement-service 并补齐单测",
        "接入 Redis 缓存热点商品详情并增加失效回源机制",
        "重构库存预占释放流程，支持 MQ 消息幂等处理",
        "网关统一鉴权拦截器升级，补齐租户与角色校验",
        "支付回调处理链路增加签名校验和重放攻击防护",
        "改造搜索接口分页参数，兼容游标与页码双模式",
        "搭建订单超时取消定时任务监控告警面板",
        "优化购物车合并逻辑，解决登录后重复项累加问题",
        "完善商品上下架事件通知链路，增加重试机制",
        "重写优惠券核销接口，支持批次并发锁"
    ];
    const bugTitles = [
        "秒杀高并发场景下库存扣减偶发出现负数",
        "提交订单后优惠券状态未及时更新导致可重复使用",
        "支付成功后订单状态偶发停留在待支付",
        "多门店分销场景结算金额计算结果与预期不一致",
        "退款成功后积分未回退且会员成长值未修正",
        "购物车跨端同步时商品勾选状态丢失",
        "商品详情页切换规格后价格展示未实时刷新",
        "商家后台导出订单在大数据量时出现超时失败",
        "订单备注包含 emoji 时保存后乱码",
        "促销活动边界时间判断错误导致提前结束"
    ];
    const list: RowItem[] = [];

    for (let t = 0; t < types.length; t++) {
        const currentType = types[t]!;
        const statuses = getStatusOptionsByType(currentType).map((x) => x.value as Status);
        const typeTitles = currentType === "需求" ? demandTitles : currentType === "任务" ? taskTitles : bugTitles;

        for (let i = 0; i < countPerType; i++) {
            const idx = t * countPerType + i + 1;
            const created = new Date(Date.now() - idx * 1000 * 60 * 60 * 3);
            const planStart = new Date(Date.now() + ((i + t) % 12) * 1000 * 60 * 60 * 24);
            const planEnd = new Date(planStart.getTime() + (((i + t) % 5) + 1) * 1000 * 60 * 60 * 24);
            const ownerName = i % 11 === 0 ? "未指派" : memberPool[(i + t) % memberPool.length]!;
            const collaboratorA = memberPool[(i + t + 3) % memberPool.length]!;
            const collaboratorB = memberPool[(i + t + 7) % memberPool.length]!;
            const collaborators = [collaboratorA, collaboratorB].filter((name, index, arr) => name !== ownerName && arr.indexOf(name) === index);
            const title = typeTitles[i % typeTitles.length]!;

            list.push({
                workNo: toWorkNo(idx),
                backendId: "",
                title: `【${currentType}】VortMall 微服务商城 - ${title}`,
                priority: priorities[(i + t) % priorities.length]!,
                tags: [tagPool[(i * 2 + t) % tagPool.length]!, tagPool[(i * 2 + t + 5) % tagPool.length]!],
                status: statuses[(i + t) % statuses.length]!,
                createdAt: formatCnTime(created),
                collaborators: collaborators.length ? collaborators : [memberPool[(i + t + 1) % memberPool.length]!],
                type: currentType,
                planTime: [formatDate(planStart), formatDate(planEnd)],
                description: defaultBugDescription,
                owner: ownerName,
                creator: creators[(i + t) % creators.length]!
            });
        }
    }
    return list;
};

const allData = ref<RowItem[]>(buildDataset());
collectTagOptions(allData.value);
for (const row of allData.value) {
    planTimeModel[row.workNo] = [...row.planTime];
}
const nextWorkNoIndex = ref(allData.value.length + 1);

const columns = computed<ProTableColumn<RowItem>[]>(() => [
    { title: "工作编号", dataIndex: "workNo", width: 130, sorter: true, align: "left", fixed: "left" },
    { title: "标题", dataIndex: "title", width: 228, ellipsis: true, align: "left", fixed: "left", slot: "title" },
    { title: "状态", dataIndex: "status", width: 120, slot: "status", align: "left" },
    { title: "负责人", dataIndex: "owner", width: 160, sorter: true, align: "left", slot: "owner" },
    { title: "优先级", dataIndex: "priority", width: 120, slot: "priority", align: "left" },
    { title: "标签", dataIndex: "tags", width: 180, slot: "tags", align: "left" },
    { title: "创建时间", dataIndex: "createdAt", width: 150, sorter: true, align: "left" },
    { title: "协作者", dataIndex: "collaborators", width: 140, slot: "collaborators", align: "left" },
    { title: "工作项类型", dataIndex: "type", width: 120, sorter: true, align: "left" },
    { title: "计划时间", dataIndex: "planTime", width: 260, sorter: true, align: "left", slot: "planTime" },
    { title: "创建人", dataIndex: "creator", width: 160, sorter: true, align: "left", slot: "creator" },
    { title: "操作", dataIndex: "actions", width: 100, fixed: "right", align: "left", slot: "actions" }
]);

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
        deadline?: string;
        pm_id?: string | null;
    }
) => {
    if (!props.useApi) return;
    const id = getRecordBackendId(record);
    if (!id) return;
    if (record.type === "需求") {
        await updateVortflowStory(id, {
            title: patch.title,
            description: patch.description,
            state: patch.state,
            priority: patch.priority,
            tags: patch.tags,
            collaborators: patch.collaborators,
            deadline: patch.deadline,
            pm_id: patch.pm_id,
        });
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
            deadline: patch.deadline,
        });
        return;
    }
    await updateVortflowBug(id, {
        title: patch.title,
        description: patch.description,
        severity: patch.severity,
        state: patch.state,
        assignee_id: patch.assignee_id === undefined ? undefined : (patch.assignee_id || undefined),
        tags: patch.tags,
        collaborators: patch.collaborators,
    });
};

const syncRecordStatusToApi = async (record: RowItem, displayStatus: Status) => {
    if (!props.useApi) return;
    const targetStates = getBackendStatesByDisplayStatus(record.type, displayStatus) || [];
    if (!targetStates.length) {
        throw new Error("当前状态不支持同步到后端");
    }
    await syncRecordUpdateToApi(record, { state: targetStates[0] });
};

const randomPeoplePool = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十", "郑十一", "王十二", "冯十三", "陈十四"];
const randomStatusPoolByType: Record<WorkItemType, Status[]> = {
    需求: demandStatusFilterOptions.map((x) => x.value),
    任务: taskStatusFilterOptions.map((x) => x.value),
    缺陷: bugStatusFilterOptions.map((x) => x.value),
};
const getOwnerDropdownPool = (): string[] => {
    const pool = Array.from(new Set(
        ownerGroups.value
            .flatMap((group) => group.members)
            .map((name) => String(name || "").trim())
            .filter(Boolean)
    ));
    return pool.length ? pool : randomPeoplePool;
};

const pickStableRandomPerson = (seed: string): string => {
    const peoplePool = getOwnerDropdownPool();
    let hash = 0;
    for (let i = 0; i < seed.length; i++) {
        hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
    }
    return peoplePool[hash % peoplePool.length]!;
};
const pickStableRandomStatus = (typeValue: WorkItemType, seed: string): Status => {
    const statusPool = randomStatusPoolByType[typeValue] || bugStatusFilterOptions.map((x) => x.value);
    let hash = 0;
    for (let i = 0; i < seed.length; i++) {
        hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
    }
    return statusPool[hash % statusPool.length]!;
};

const backendDemandTitles = [
    "支持商家后台批量导入 SKU 并自动校验条码重复",
    "订单中心新增按渠道维度的成交额趋势看板",
    "会员中心支持成长值规则按活动模板配置",
    "结算中心支持分账结果失败自动补偿任务",
    "营销中心新增满减与优惠券叠加规则配置",
];
const backendTaskTitles = [
    "拆分订单服务结算逻辑到 settlement-service 并补齐单测",
    "接入 Redis 缓存热点商品详情并增加失效回源机制",
    "重构库存预占释放流程，支持 MQ 消息幂等处理",
    "网关统一鉴权拦截器升级，补齐租户与角色校验",
    "支付回调处理链路增加签名校验和重放攻击防护",
];
const backendBugTitles = [
    "秒杀高并发场景下库存扣减偶发出现负数",
    "提交订单后优惠券状态未及时更新导致可重复使用",
    "支付成功后订单状态偶发停留在待支付",
    "多门店分销场景结算金额计算结果与预期不一致",
    "购物车跨端同步时商品勾选状态丢失",
];

const getBackendDisplayTitle = (rawTitle: string, typeValue: WorkItemType, index: number): string => {
    const source = rawTitle.trim();
    const fallback =
        typeValue === "需求"
            ? backendDemandTitles[index % backendDemandTitles.length]!
            : typeValue === "任务"
              ? backendTaskTitles[index % backendTaskTitles.length]!
              : backendBugTitles[index % backendBugTitles.length]!;
    const normalized = source && source !== "-" ? source : fallback;
    return normalized;
};

const prependPinnedRow = (typeValue: WorkItemType, row: RowItem) => {
    const list = pinnedRowsByType[typeValue] || [];
    const rowId = row.backendId || row.workNo;
    pinnedRowsByType[typeValue] = [row, ...list.filter((x) => (x.backendId || x.workNo) !== rowId)];
};

const cacheStoryRows = (rows: RowItem[]) => {
    for (const row of rows) {
        if (row.type !== "需求" || !row.backendId) continue;
        storyRowsById[row.backendId] = row;
    }
};

const findStoryRowById = (storyId?: string): RowItem | null => {
    if (!storyId) return null;
    return storyRowsById[storyId] || null;
};

const loadStoryById = async (storyId?: string): Promise<RowItem | null> => {
    if (!storyId) return null;
    const cached = findStoryRowById(storyId);
    if (cached) return cached;
    try {
        const res: any = await getVortflowStory(storyId);
        if (!res?.id) return null;
        const row = mapBackendItemToRow(res, "需求", 0);
        storyRowsById[storyId] = row;
        return row;
    } catch {
        return null;
    }
};

const loadChildStories = async (parentStoryId: string, projectId?: string): Promise<RowItem[]> => {
    if (!parentStoryId) return [];
    const res: any = await getVortflowStories({
        parent_id: parentStoryId,
        project_id: projectId,
        page: 1,
        page_size: 100,
    });
    const rows = ((res?.items || []) as any[]).map((item, index) => {
        const row = mapBackendItemToRow(item, "需求", index);
        row.isChild = true;
        return row;
    });
    cacheStoryRows(rows);
    storyChildrenMap[parentStoryId] = rows;
    return rows;
};

const mapBackendItemToRow = (item: any, typeValue: WorkItemType, index: number): RowItem => {
    const created = item?.created_at ? new Date(item.created_at) : new Date();
    const createdAt = formatCnTime(created);
    const deadline = item?.deadline ? String(item.deadline).split("T")[0] : "";
    const backendId = String(item?.id || index + 1);
    const workNo = `#${backendId.replace(/-/g, "").slice(0, 6).toUpperCase().padEnd(6, "X")}`;
    const ownerSourceId = String(item?.assignee_id || item?.pm_id || item?.developer_id || "").trim();
    const ownerSourceName = getMemberNameById(ownerSourceId);
    const creatorSeed = String(item?.reporter_id || `${backendId}-creator`);
    const collabSeed = String(item?.story_id || item?.task_id || `${backendId}-collab`);
    const ownerName = ownerSourceName || (ownerSourceId ? ownerSourceId : "未指派");
    const creatorName = pickStableRandomPerson(creatorSeed);
    const collaboratorName = pickStableRandomPerson(collabSeed);
    const fallbackCollaborator = pickStableRandomPerson(`${collabSeed}-alt`);
    const collaboratorsFromBackend = Array.isArray(item?.collaborators)
        ? (item.collaborators as any[]).map((x) => String(x || "").trim()).filter(Boolean)
        : [];
    const collaborators = collaboratorsFromBackend.length
        ? collaboratorsFromBackend
        : [collaboratorName === ownerName ? fallbackCollaborator : collaboratorName];
    const tags: string[] = Array.isArray(item?.tags)
        ? (item.tags as any[]).map((x) => String(x || "").trim()).filter(Boolean)
        : [];
    if (typeValue === "任务" && item?.task_type) tags.push(String(item.task_type));
    if (typeValue === "需求" && item?.project_id) tags.push("需求");
    if (typeValue === "缺陷" && item?.severity) tags.push(`S${item.severity}`);

    const planDate = deadline || formatDate(created);
    return {
        backendId,
        workNo,
        title: getBackendDisplayTitle(String(item?.title || ""), typeValue, index),
        parentId: item?.parent_id ? String(item.parent_id) : "",
        parentTitle: "",
        childrenCount: Number(item?.children_count || 0),
        isChild: Boolean(item?.parent_id),
        priority: mapBackendPriority(item, typeValue),
        tags,
        status: mapBackendStateToStatus(typeValue, String(item?.state || "")),
        createdAt,
        collaborators,
        type: typeValue,
        planTime: [planDate, planDate],
        description: item?.description || "",
        ownerId: ownerSourceId,
        owner: ownerName,
        creator: creatorName,
        projectId: item?.project_id ? String(item.project_id) : "",
        projectName: "",
    };
};

const createOwnerMatcher = (ownerValue: string) => {
    const normalizedOwner = String(ownerValue || "").trim();
    const ownerMemberId = normalizedOwner && normalizedOwner !== "未指派" ? getMemberIdByName(normalizedOwner) : "";
    const matchOwner = (row: RowItem) => {
        if (!normalizedOwner) return true;
        if (normalizedOwner === "未指派") return !String(row.ownerId || "").trim();
        if (ownerMemberId) return String(row.ownerId || "").trim() === ownerMemberId;
        return row.owner === normalizedOwner;
    };
    return { ownerMemberId, matchOwner };
};

const getVisibleStoryRows = (rows: RowItem[], ownerValue = owner.value, statusValue = status.value) => {
    const currentType = String(props.type ?? type.value ?? "").trim();
    if (!props.useApi || currentType !== "需求") return rows;
    const { matchOwner } = createOwnerMatcher(ownerValue);
    const flattenedRows: RowItem[] = [];
    for (const row of rows) {
        flattenedRows.push(row);
        const storyId = String(row.backendId || "").trim();
        if (!storyId || !expandedStoryIds[storyId]) continue;
        const children = (storyChildrenMap[storyId] || [])
            .filter((child) => !statusValue || child.status === statusValue)
            .filter(matchOwner)
            .map((child) => ({ ...child, isChild: true }));
        flattenedRows.push(...children);
    }
    return flattenedRows;
};

const postProcessTableRows = (rows: RowItem[]) => getVisibleStoryRows(rows);

const request = async (params: ProTableRequestParams): Promise<ProTableResponse<RowItem>> => {
    const kw = String(params.keyword ?? "").trim().toLowerCase();
    const ownerValue = String(params.owner ?? "").trim();
    const { ownerMemberId, matchOwner } = createOwnerMatcher(ownerValue);
    const typeValue = String(props.type ?? params.type ?? "").trim();
    const statusValue = String(params.status ?? "").trim();
    const current = Number(params.current || 1);
    const pageSize = Number(params.pageSize || 20);

    if (props.useApi && (typeValue === "需求" || typeValue === "任务" || typeValue === "缺陷")) {
        const workType = typeValue as WorkItemType;
        const backendStates = statusValue ? getBackendStatesByDisplayStatus(workType, statusValue) : undefined;
        if (statusValue && (!backendStates || backendStates.length === 0)) {
            totalCount.value = 0;
            return { data: [], total: 0, current, pageSize };
        }
        const requestByState = async (state?: string, page = current, size = pageSize) => {
            if (workType === "需求") {
                return getVortflowStories({ keyword: kw, state, parent_id: "root", page, page_size: size });
            }
            if (workType === "任务") {
                return getVortflowTasks({
                    keyword: kw,
                    state,
                    assignee_id: ownerMemberId || undefined,
                    page,
                    page_size: size
                });
            }
            return getVortflowBugs({
                keyword: kw,
                state,
                assignee_id: ownerMemberId || undefined,
                page,
                page_size: size
            });
        };
        const fetchAllItemsByState = async (state?: string): Promise<any[]> => {
            const batchSize = 100;
            const firstRes: any = await requestByState(state, 1, batchSize);
            const allItems: any[] = [...((firstRes as any)?.items || [])];
            const total = Number((firstRes as any)?.total || allItems.length);
            const totalPages = Math.max(1, Math.ceil(total / batchSize));
            for (let page = 2; page <= totalPages; page++) {
                const pageRes: any = await requestByState(state, page, batchSize);
                const pageItems = ((pageRes as any)?.items || []);
                if (!pageItems.length) break;
                allItems.push(...pageItems);
            }
            return allItems;
        };
        const buildRowsFromItems = (items: any[]): RowItem[] => {
            const rows = items.map((item: any, idx: number) => mapBackendItemToRow(item, workType, idx));
            if (workType === "需求") {
                cacheStoryRows(rows);
            }
            return rows;
        };

        let rows: RowItem[] = [];
        let totalFromApi = 0;

        if (backendStates && backendStates.length > 1) {
            // Multi-state display filters need full merged querying across all pages.
            const merged = new Map<string, any>();
            const itemGroups = await Promise.all(backendStates.map((state) => fetchAllItemsByState(state)));
            for (const items of itemGroups) {
                for (const item of items) {
                    const id = String(item?.id || "");
                    if (!id || merged.has(id)) continue;
                    merged.set(id, item);
                }
            }
            const mergedItems = [...merged.values()];
            const allRows = buildRowsFromItems(mergedItems)
                .filter((x) => !statusValue || x.status === statusValue)
                .filter(matchOwner);
            totalFromApi = allRows.length;
            const start = (current - 1) * pageSize;
            rows = allRows.slice(start, start + pageSize);
        } else {
            const backendState = backendStates?.[0];
            if (ownerValue && (workType === "需求" || ownerValue === "未指派" || !ownerMemberId)) {
                const allItems = await fetchAllItemsByState(backendState);
                const allRows = buildRowsFromItems(allItems)
                    .filter((x) => !statusValue || x.status === statusValue)
                    .filter(matchOwner);
                totalFromApi = allRows.length;
                const start = (current - 1) * pageSize;
                rows = allRows.slice(start, start + pageSize);
            } else {
                const res: any = await requestByState(backendState, current, pageSize);
                rows = buildRowsFromItems((res as any)?.items || []);
                if (statusValue) rows = rows.filter((x) => x.status === statusValue);
                if (ownerValue) rows = rows.filter(matchOwner);
                totalFromApi = Number((res as any)?.total || rows.length);
            }
        }

        if (current === 1) {
            let pinnedRows = pinnedRowsByType[workType] || [];
            if (statusValue) pinnedRows = pinnedRows.filter((x) => x.status === statusValue);
            if (ownerValue) pinnedRows = pinnedRows.filter(matchOwner);
            const pinnedIds = new Set(pinnedRows.map((x) => x.backendId || x.workNo));
            rows = [...pinnedRows, ...rows.filter((x) => !pinnedIds.has(x.backendId || x.workNo))];
            rows = rows.slice(0, pageSize);
        }
        collectTagOptions(workType === "需求" ? getVisibleStoryRows(rows, ownerValue, statusValue) : rows);
        totalCount.value = totalFromApi;
        return { data: rows, total: totalFromApi, current, pageSize };
    }

    let list = allData.value.slice();
    if (kw) {
        list = list.filter((x) => x.workNo.toLowerCase().includes(kw) || x.title.toLowerCase().includes(kw) || x.owner.toLowerCase().includes(kw));
    }
    if (ownerValue) {
        list = list.filter((x) => x.owner === ownerValue);
    }
    if (typeValue) {
        list = list.filter((x) => x.type === typeValue);
    }
    if (statusValue) {
        list = list.filter((x) => x.status === statusValue);
    }

    const { sortField, sortOrder } = params;
    if (sortField && sortOrder) {
        const dir = sortOrder === "ascend" ? 1 : -1;
        const getSortValue = (item: RowItem, field: string): string => {
            if (field === "planTime") return item.planTime?.[0] || "";
            return String((item as any)[field] ?? "");
        };
        list.sort((a, b) => (getSortValue(a, sortField) > getSortValue(b, sortField) ? dir : -dir));
    }

    const total = list.length;
    totalCount.value = total;
    collectTagOptions(list);
    const start = (current - 1) * pageSize;
    return {
        data: list.slice(start, start + pageSize),
        total,
        current,
        pageSize
    };
};

const tableRef = ref<any>(null);

const queryParams = computed(() => ({
    keyword: keyword.value,
    owner: owner.value,
    type: props.type || type.value,
    status: status.value
}));

const onReset = () => {
    keyword.value = "";
    owner.value = "";
    type.value = props.type ?? "";
    status.value = "";
    tableRef.value?.refresh?.();
};

const rowKeyGetter = (record: RowItem) => record.backendId || record.workNo;

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
};

const deleteOne = async (record: RowItem) => {
    if (props.useApi) {
        const id = record.backendId;
        if (!id) throw new Error("缺少记录ID");
        const itemType = (props.type || record.type) as WorkItemType;
        if (itemType === "需求") await deleteVortflowStory(id);
        else if (itemType === "任务") await deleteVortflowTask(id);
        else await deleteVortflowBug(id);
        return;
    }
    allData.value = allData.value.filter((x) => x.workNo !== record.workNo);
    totalCount.value = allData.value.length;
};

const handleDelete = async (record: RowItem) => {
    try {
        await deleteOne(record);
        message.success("删除成功");
        clearSelection();
        tableRef.value?.refresh?.();
    } catch (error: any) {
        message.error(error?.message || "删除失败");
    }
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

const resetCreateBugForm = () => {
    Object.assign(createBugForm, createInitialBugForm());
    createBugPriorityDropdownOpen.value = false;
    createAssigneeDropdownOpen.value = false;
    createTagDropdownOpen.value = false;
    createAssigneeKeyword.value = "";
    createTagKeyword.value = "";
    createBugAttachments.value = [];
};

const handleCreateBug = async () => {
    await loadApiMetadata(props.type === "任务");
    createBugDrawerMode.value = "create";
    createParentStoryId.value = "";
    createProjectId.value = "";
    resetCreateBugForm();
    createBugForm.type = props.type ?? createBugForm.type;
    router.replace({ query: { ...route.query, action: "create", parentId: undefined } });
};

const handleCancelCreateBug = () => {
    createBugDrawerOpen.value = false;
    createParentStoryId.value = "";
    createProjectId.value = "";
    createBugPriorityDropdownOpen.value = false;
    createAssigneeDropdownOpen.value = false;
    createTagDropdownOpen.value = false;
};

const handleCancelCreateWorkItem = () => {
    if (createWorkItemRef.value) {
        createWorkItemRef.value.cancel();
        return;
    }
    handleCancelCreateBug();
};

const handleDetailUpdate = (data: Partial<RowItem>) => {
    if (detailCurrentRecord.value) {
        Object.assign(detailCurrentRecord.value, data);
        tableRef.value?.refresh?.();
    }
};

const toggleStoryExpand = async (record: RowItem) => {
    if (record.type !== "需求" || !record.childrenCount || !record.backendId) return;
    const storyId = String(record.backendId);
    if (expandingStoryIds[storyId]) return;
    if (expandedStoryIds[storyId]) {
        expandedStoryIds[storyId] = false;
        return;
    }
    if (!storyChildrenMap[storyId]) {
        expandingStoryIds[storyId] = true;
        try {
            await loadChildStories(storyId, record.projectId);
        } finally {
            expandingStoryIds[storyId] = false;
        }
    }
    expandedStoryIds[storyId] = true;
};

const detailParentRecord = ref<RowItem | null>(null);
const detailChildRecords = ref<RowItem[]>([]);

const syncDetailRelations = async (record: RowItem) => {
    if (record.type !== "需求") {
        detailParentRecord.value = null;
        detailChildRecords.value = [];
        return;
    }
    detailParentRecord.value = await loadStoryById(record.parentId);
    if (record.backendId && record.childrenCount) {
        detailChildRecords.value = await loadChildStories(record.backendId, record.projectId);
    } else {
        detailChildRecords.value = [];
    }
};

const handleCreateSuccess = async (formData: NewBugForm, keepCreating = false) => {
    if (createBugDrawerMode.value !== "create") {
        createBugDrawerOpen.value = false;
        createBugPriorityDropdownOpen.value = false;
        return;
    }

    const title = formData.title.trim();
    if (!title) {
        message.warning("请填写标题");
        return;
    }

    if (props.useApi) {
        const type = (props.type || formData.type || "缺陷") as WorkItemType;
        try {
            let createdItem: any = null;
            const ownerId = getMemberIdByName(formData.owner) || undefined;
            if (type === "需求") {
                const defaultProject = formData.projectId || createProjectId.value || resolveCreateProjectId();
                createdItem = await createVortflowStory({
                    project_id: defaultProject,
                    title,
                    description: formData.description || defaultBugDescription,
                    priority: formData.priority === "urgent" ? 1 : formData.priority === "high" ? 2 : formData.priority === "medium" ? 3 : 4,
                    parent_id: formData.parentId || undefined,
                    tags: [...formData.tags],
                    collaborators: [...formData.collaborators],
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
                    story_id: String(formData.storyId || ""),
                    title,
                    description: formData.description || "",
                    task_type: "develop",
                    assignee_id: ownerId,
                    tags: [...formData.tags],
                    collaborators: [...formData.collaborators],
                    deadline: formData.planTime?.[1] || undefined,
                });
            } else {
                createdItem = await createVortflowBug({
                    story_id: formData.storyId || undefined,
                    title,
                    description: formData.description || defaultBugDescription,
                    severity: formData.priority === "urgent" ? 1 : formData.priority === "high" ? 2 : formData.priority === "medium" ? 3 : 4,
                    assignee_id: ownerId,
                    tags: [...formData.tags],
                    collaborators: [...formData.collaborators],
                });
            }
            if (createdItem) {
                const pinnedRow = mapBackendItemToRow(createdItem, type, 0);
                if (type === "需求" && formData.parentId) {
                    const parentId = formData.parentId;
                    const existingChildren = storyChildrenMap[parentId] || [];
                    storyChildrenMap[parentId] = [{ ...pinnedRow, isChild: true }, ...existingChildren];
                    const parentRow = storyRowsById[parentId];
                    if (parentRow) {
                        parentRow.childrenCount = (parentRow.childrenCount || 0) + 1;
                    }
                    expandedStoryIds[parentId] = true;
                } else {
                    prependPinnedRow(type, pinnedRow);
                }
            }
            tableRef.value?.refresh?.();
            message.success("新建成功");
            if (keepCreating) {
                createWorkItemRef.value?.reset();
            } else {
                handleCancelCreateBug();
            }
            return;
        } catch (error: any) {
            message.error(error?.message || "新建失败");
            return;
        }
    }

    const now = new Date();
    const workNo = toWorkNo(nextWorkNoIndex.value++);
    const fallbackPlanDate = formatDate(now);
    const planTime: DateRange = (formData.planTime as DateRange)?.length === 2
        ? [...(formData.planTime as DateRange)]
        : [fallbackPlanDate, fallbackPlanDate];
    const newPriority: Priority = formData.priority || "none";
    const ownerName = formData.owner || "未指派";
    const collaborators = [...formData.collaborators];

    const newRow: RowItem = {
        workNo,
        title,
        parentId: formData.parentId || "",
        childrenCount: 0,
        isChild: Boolean(formData.parentId),
        priority: newPriority,
        tags: [...formData.tags],
        status: "待确认",
        createdAt: formatCnTime(now),
        collaborators,
        type: formData.type || props.type || "缺陷",
        planTime,
        description: formData.description || defaultBugDescription,
        ownerId: "",
        owner: ownerName,
        creator: "当前用户",
        projectId: formData.projectId || "",
        projectName: formData.project || "",
    };

    allData.value.unshift(newRow);
    planTimeModel[workNo] = [...planTime];
    priorityModel[workNo] = newPriority;
    totalCount.value = allData.value.length;
    tableRef.value?.refresh?.();
    message.success("新建成功");
    if (keepCreating) {
        createWorkItemRef.value?.reset();
    } else {
        handleCancelCreateBug();
    }
};

const handleSubmitCreateBug = async (keepCreating = false) => {
    const formData = createWorkItemRef.value?.submit();
    if (!formData) return;
    await handleCreateSuccess(formData, keepCreating);
};

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
            size: file.size
        });
    }
    createBugAttachments.value = next;
    target.value = "";
};

const removeCreateAttachment = (id: string) => {
    createBugAttachments.value = createBugAttachments.value.filter((x) => x.id !== id);
};

const detailRecordSnapshot = ref<RowItem | null>(null);

const handleOpenBugDetail = async (record: RowItem) => {
    detailSelectedWorkNo.value = record.workNo;
    detailRecordSnapshot.value = record;
    detailActiveTab.value = "detail";
    detailBottomTab.value = "comments";
    detailCommentDraft.value = "";
    detailStatusDropdownOpen.value = false;
    detailStatusKeyword.value = "";
    detailAssigneeDropdownOpen.value = false;
    detailAssigneeKeyword.value = "";
    detailDescEditing.value = false;
    detailDescDraft.value = "";
    ensureDetailPanelsData(record);
    await syncDetailRelations(record);

    const currentPriority = getRowPriority(record, record.priority);
    const currentTags = getRowTags(record, record.tags);
    const currentPlanTime = planTimeModel[record.workNo] || record.planTime;
    const base = createInitialBugForm();

    createBugDrawerMode.value = "detail";
    Object.assign(createBugForm, {
        ...base,
        title: record.title,
        owner: record.owner === "未指派" ? "" : record.owner,
        type: record.type,
        planTime: [...currentPlanTime],
        priority: currentPriority,
        tags: [...currentTags],
        description: record.description || base.description
    });

    createBugPriorityDropdownOpen.value = false;
    router.replace({ query: { ...route.query, action: "detail", id: record.workNo } });
};

const detailCurrentRecord = computed<RowItem | null>(() => {
    if (!detailSelectedWorkNo.value) return null;
    if (detailRecordSnapshot.value?.workNo === detailSelectedWorkNo.value) {
        return detailRecordSnapshot.value;
    }
    return allData.value.find((x) => x.workNo === detailSelectedWorkNo.value) || detailRecordSnapshot.value || null;
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
        action
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
        content
    });
    detailCommentDraft.value = "";
    appendDetailLog("发布评论");
    message.success("评论已发布");
};

const filteredDetailAssigneeGroups = computed(() => {
    const kw = detailAssigneeKeyword.value.trim();
    if (!kw) return ownerGroups.value;
    return ownerGroups.value
        .map((g) => ({
            ...g,
            members: g.members.filter((m) => m.includes(kw))
        }))
        .filter((g) => g.members.length > 0);
});

const filteredCreateAssigneeGroups = computed(() => {
    const kw = createAssigneeKeyword.value.trim();
    if (!kw) return ownerGroups.value;
    return ownerGroups.value
        .map((g) => ({
            ...g,
            members: g.members.filter((m) => m.includes(kw))
        }))
        .filter((g) => g.members.length > 0);
});

const toggleDetailAssigneeMenu = () => {
    detailAssigneeDropdownOpen.value = !detailAssigneeDropdownOpen.value;
    if (!detailAssigneeDropdownOpen.value) detailAssigneeKeyword.value = "";
};

const toggleCreateAssigneeMenu = () => {
    createAssigneeDropdownOpen.value = !createAssigneeDropdownOpen.value;
    if (!createAssigneeDropdownOpen.value) createAssigneeKeyword.value = "";
};

const toggleDetailAssigneeGroup = (group: string) => {
    detailAssigneeGroupOpen[group] = !detailAssigneeGroupOpen[group];
};

const toggleCreateAssigneeGroup = (group: string) => {
    createAssigneeGroupOpen[group] = !createAssigneeGroupOpen[group];
};

const isDetailOwner = (member: string): boolean => {
    return detailCurrentRecord.value?.owner === member;
};

const isDetailCollaborator = (member: string): boolean => {
    return (detailCurrentRecord.value?.collaborators || []).includes(member);
};

const isCreateOwner = (member: string): boolean => {
    return createBugForm.owner === member;
};

const isCreateCollaborator = (member: string): boolean => {
    return createBugForm.collaborators.includes(member);
};

const setDetailOwner = async (member: string) => {
    if (!detailCurrentRecord.value) return;
    const record = detailCurrentRecord.value;
    const prev = detailCurrentRecord.value.owner;
    const nextOwner = member || "未指派";
    detailCurrentRecord.value.owner = nextOwner;
    if (prev !== nextOwner) {
        const memberId = member ? getMemberIdByName(member) : "";
        if (member && !memberId) {
            detailCurrentRecord.value.owner = prev;
            message.error("未找到负责人对应的成员ID，无法同步");
            return;
        }
        try {
            if (record.type === "需求") {
                await syncRecordUpdateToApi(record, { pm_id: memberId || null });
            } else {
                await syncRecordUpdateToApi(record, { assignee_id: memberId || null });
            }
        } catch (error: any) {
            detailCurrentRecord.value.owner = prev;
            message.error(error?.message || "负责人同步失败");
            return;
        }
        appendDetailLog(`将负责人从 ${prev || "未指派"} 修改为 ${detailCurrentRecord.value.owner}`);
    }
};

const setCreateOwner = (member: string) => {
    createBugForm.owner = member || "";
    createBugForm.collaborators = createBugForm.collaborators.filter((x) => x !== member);
};

const toggleDetailCollaborator = async (member: string) => {
    if (!detailCurrentRecord.value) return;
    const record = detailCurrentRecord.value;
    const list = [...(detailCurrentRecord.value.collaborators || [])];
    const idx = list.indexOf(member);
    if (idx >= 0) {
        list.splice(idx, 1);
    } else {
        list.push(member);
    }
    const prev = [...(detailCurrentRecord.value.collaborators || [])];
    detailCurrentRecord.value.collaborators = list;
    try {
        await syncRecordUpdateToApi(record, { collaborators: list });
    } catch (error: any) {
        detailCurrentRecord.value.collaborators = prev;
        message.error(error?.message || "协作者同步失败");
        return;
    }
    appendDetailLog(`${idx >= 0 ? "取消" : "添加"}协作者 ${member}`);
};

const toggleCreateCollaborator = (member: string) => {
    if (createBugForm.owner === member) return;
    const list = [...createBugForm.collaborators];
    const idx = list.indexOf(member);
    if (idx >= 0) list.splice(idx, 1);
    else list.push(member);
    createBugForm.collaborators = list;
};

const openDetailDescEditor = () => {
    if (!detailCurrentRecord.value) return;
    detailDescDraft.value = detailCurrentRecord.value.description || "";
    detailDescEditing.value = true;
};

const cancelDetailDescEditor = () => {
    detailDescEditing.value = false;
    detailDescDraft.value = "";
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
    appendDetailLog("更新描述");
    message.success("描述已保存");
};

const getRowPriority = (record: RowItem, text?: Priority): Priority => {
    return priorityModel[record.workNo] || text || record.priority;
};

const togglePriorityMenu = (workNo: string) => {
    const willOpen = openPriorityFor.value !== workNo;
    closeRowPopovers();
    openPriorityFor.value = willOpen ? workNo : null;
};

const selectPriority = async (record: RowItem, value: Priority) => {
    const workNo = record.workNo;
    const prev = getRowPriority(record, record.priority);
    priorityModel[workNo] = value;
    record.priority = value;
    try {
        if (record.type === "缺陷") {
            await syncRecordUpdateToApi(record, { severity: toBackendPriorityLevel(value) });
        } else if (record.type === "任务") {
            await syncRecordUpdateToApi(record, { estimate_hours: toTaskEstimateHours(value) });
        } else {
            await syncRecordUpdateToApi(record, { priority: toBackendPriorityLevel(value) });
        }
    } catch (error: any) {
        priorityModel[workNo] = prev;
        record.priority = prev;
        message.error(error?.message || "优先级同步失败");
        openPriorityFor.value = null;
        return;
    }
    openPriorityFor.value = null;
};

const toggleCreateBugPriorityMenu = () => {
    createBugPriorityDropdownOpen.value = !createBugPriorityDropdownOpen.value;
};

const selectCreateBugPriority = (value: Priority) => {
    createBugForm.priority = value;
    createBugPriorityDropdownOpen.value = false;
};

const filteredStatusOptions = computed(() => {
    const kw = statusKeyword.value.trim();
    if (!kw) return currentStatusFilterOptions.value;
    return currentStatusFilterOptions.value.filter((x) => x.label.includes(kw));
});

const selectStatus = (value: string) => {
    status.value = value;
    statusDropdownOpen.value = false;
};

const getRowStatus = (record: RowItem, text?: Status): Status => {
    return text || record.status;
};

const toggleRowStatusMenu = (record: RowItem) => {
    rowStatusKeyword.value = "";
    const willOpen = openStatusFor.value !== record.workNo;
    closeRowPopovers();
    if (!willOpen) return;
    rowStatusType.value = record.type || resolveActiveType();
    openStatusFor.value = record.workNo;
};

const filteredRowStatusOptions = computed(() => {
    const kw = rowStatusKeyword.value.trim();
    const options = getStatusOptionsByType(rowStatusType.value);
    if (!kw) return options;
    return options.filter((x) => x.label.includes(kw));
});

const toggleDetailStatusMenu = () => {
    detailStatusDropdownOpen.value = !detailStatusDropdownOpen.value;
    if (!detailStatusDropdownOpen.value) detailStatusKeyword.value = "";
};

const filteredDetailStatusOptions = computed(() => {
    const kw = detailStatusKeyword.value.trim();
    const detailType = detailCurrentRecord.value?.type || resolveActiveType();
    const options = getStatusOptionsByType(detailType);
    if (!kw) return options;
    return options.filter((x) => x.label.includes(kw));
});

const selectDetailStatus = async (value: Status) => {
    if (detailCurrentRecord.value) {
        const prev = detailCurrentRecord.value.status;
        detailCurrentRecord.value.status = value;
        if (prev !== value) {
            try {
                await syncRecordStatusToApi(detailCurrentRecord.value, value);
            } catch (error: any) {
                detailCurrentRecord.value.status = prev;
                message.error(error?.message || "状态同步失败");
                detailStatusDropdownOpen.value = false;
                detailStatusKeyword.value = "";
                return;
            }
            appendDetailLog(`将状态从 ${prev} 修改为 ${value}`);
        }
    }
    detailStatusDropdownOpen.value = false;
    detailStatusKeyword.value = "";
};

const selectRowStatus = async (record: RowItem, value: Status) => {
    const prev = record.status;
    record.status = value;
    if (prev !== value) {
        try {
            await syncRecordStatusToApi(record, value);
        } catch (error: any) {
            record.status = prev;
            message.error(error?.message || "状态同步失败");
            openStatusFor.value = null;
            rowStatusKeyword.value = "";
            return;
        }
    }
    openStatusFor.value = null;
    rowStatusKeyword.value = "";
};

const filteredOwnerGroups = computed(() => {
    const kw = ownerKeyword.value.trim();
    if (!kw) return ownerGroups.value;
    return ownerGroups.value
        .map((g) => ({
            ...g,
            members: g.members.filter((m) => m.includes(kw))
        }))
        .filter((g) => g.members.length > 0);
});

const filteredOwnerEditGroups = computed(() => {
    const kw = ownerEditKeyword.value.trim();
    if (!kw) return ownerGroups.value;
    return ownerGroups.value
        .map((g) => ({
            ...g,
            members: g.members.filter((m) => m.includes(kw))
        }))
        .filter((g) => g.members.length > 0);
});

const filteredCollaboratorGroups = computed(() => {
    const kw = collaboratorKeyword.value.trim();
    if (!kw) return ownerGroups.value;
    return ownerGroups.value
        .map((g) => ({
            ...g,
            members: g.members.filter((m) => m.includes(kw))
        }))
        .filter((g) => g.members.length > 0);
});

const toggleOwnerGroup = (group: string) => {
    ownerGroupOpen[group] = !ownerGroupOpen[group];
};

const toggleOwnerEditGroup = (group: string) => {
    ownerEditGroupOpen[group] = !ownerEditGroupOpen[group];
};

const toggleCollaboratorGroup = (group: string) => {
    collaboratorGroupOpen[group] = !collaboratorGroupOpen[group];
};

const selectOwner = (value: string) => {
    owner.value = value;
    ownerDropdownOpen.value = false;
};

const getRowOwner = (record: RowItem, text?: string): string => {
    return text || record.owner || "未指派";
};

const toggleRowOwnerMenu = (workNo: string) => {
    const willOpen = openOwnerFor.value !== workNo;
    closeRowPopovers();
    openOwnerFor.value = willOpen ? workNo : null;
    ownerEditKeyword.value = "";
};

const selectRowOwner = async (record: RowItem, value: string) => {
    const prev = record.owner;
    const nextOwner = value || "未指派";
    record.owner = nextOwner;
    if (prev !== nextOwner) {
        const memberId = value ? getMemberIdByName(value) : "";
        if (value && !memberId) {
            record.owner = prev;
            message.error("未找到负责人对应的成员ID，无法同步");
            openOwnerFor.value = null;
            return;
        }
        try {
            if (record.type === "需求") {
                await syncRecordUpdateToApi(record, { pm_id: memberId || null });
            } else {
                await syncRecordUpdateToApi(record, { assignee_id: memberId || null });
            }
        } catch (error: any) {
            record.owner = prev;
            message.error(error?.message || "负责人同步失败");
            openOwnerFor.value = null;
            return;
        }
    }
    openOwnerFor.value = null;
};

const getRowCollaborators = (record: RowItem, text?: string[]): string[] => {
    return collaboratorsModel[record.workNo] || text || record.collaborators || [];
};

const toggleCollaboratorMenu = (workNo: string) => {
    const willOpen = openCollaboratorFor.value !== workNo;
    closeRowPopovers();
    openCollaboratorFor.value = willOpen ? workNo : null;
    collaboratorKeyword.value = "";
};

const toggleRowCollaborator = async (record: RowItem, member: string, text?: string[]) => {
    const current = [...getRowCollaborators(record, text)];
    const idx = current.indexOf(member);
    if (idx >= 0) current.splice(idx, 1);
    else current.push(member);
    const prev = [...getRowCollaborators(record, text)];
    collaboratorsModel[record.workNo] = current;
    record.collaborators = current;
    try {
        await syncRecordUpdateToApi(record, { collaborators: current });
    } catch (error: any) {
        collaboratorsModel[record.workNo] = prev;
        record.collaborators = prev;
        message.error(error?.message || "协作者同步失败");
    }
};

const tagColorPalette = ["#ef4444", "#d946ef", "#eab308", "#22c55e", "#3b82f6", "#f97316", "#14b8a6", "#8b5cf6"];
const tagColorOverrides = reactive<Record<string, string>>({});

const getTagColor = (name: string): string => {
    if (tagColorOverrides[name]) return tagColorOverrides[name]!;
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
    return tagColorPalette[hash % tagColorPalette.length]!;
};

const getRowTags = (record: RowItem, text?: string[]): string[] => {
    return tagsModel[record.workNo] || text || [];
};

const openCreateTagDialog = (record?: RowItem | null, text?: string[]) => {
    if (record) {
        tagPopoverOpen[record.workNo] = false;
    }
    newTagName.value = "";
    newTagColor.value = tagColorPalette[0] || "#3b82f6";
    newTagTargetRecord.value = record || null;
    newTagTargetText.value = text;
    newTagDialogOpen.value = true;
};

const handleCancelCreateTag = () => {
    newTagDialogOpen.value = false;
};

const handleConfirmCreateTag = async () => {
    const name = newTagName.value.trim();
    if (!name) {
        message.error("请输入标签名称");
        return;
    }
    const existing = new Set<string>([...baseTagOptions, ...dynamicTagOptions.value]);
    if (existing.has(name)) {
        message.error("该标签已存在");
        return;
    }
    dynamicTagOptions.value = [...dynamicTagOptions.value, name];
    if (newTagColor.value) {
        tagColorOverrides[name] = newTagColor.value;
    }
    if (newTagTargetRecord.value) {
        await toggleTagOption(newTagTargetRecord.value, name, newTagTargetText.value);
    }
    newTagDialogOpen.value = false;
};

const onPlanTimeChange = async (record: RowItem, value?: any) => {
    const workNo = record.workNo;
    if (!value || value.length !== 2) return;
    const start = normalizeDateValue(value[0]);
    const end = normalizeDateValue(value[1]);
    if (!start || !end) return;
    const prev = [...getRowPlanTime(record, record.planTime)] as DateRange;
    planTimeModel[workNo] = [start, end];
    record.planTime = [start, end];
    try {
        if (record.type === "缺陷") {
            // 缺陷模型无 deadline 字段，保持前端显示，不进行后端同步
            message.warning("缺陷暂不支持计划时间同步到后端");
        } else {
            await syncRecordUpdateToApi(record, { deadline: end });
        }
    } catch (error: any) {
        planTimeModel[workNo] = prev;
        record.planTime = prev;
        message.error(error?.message || "计划时间同步失败");
        openPlanTimeFor.value = null;
        return;
    }
    openPlanTimeFor.value = null;
};

const getRowPlanTime = (record: RowItem, text?: DateRange): DateRange => {
    return planTimeModel[record.workNo] || text || record.planTime;
};

const getRowPlanTimeText = (record: RowItem, text?: DateRange): string => {
    const value = getRowPlanTime(record, text);
    const start = normalizeDateValue(value[0]) || "-";
    const end = normalizeDateValue(value[1]) || "-";
    return `${start} ~ ${end}`;
};

const togglePlanTimeMenu = (workNo: string, record?: RowItem, text?: DateRange) => {
    const willOpen = openPlanTimeFor.value !== workNo;
    closeRowPopovers();
    if (willOpen) {
        const value = record ? getRowPlanTime(record, text) : undefined;
        const start = normalizeDateValue(value?.[0]);
        const end = normalizeDateValue(value?.[1]);
        if (start && end) {
            planTimeModel[workNo] = [start, end];
        }
    }
    openPlanTimeFor.value = willOpen ? workNo : null;
};

const getCollapsedTags = (tags: string[], resolvedWidth?: string | number): { visible: string[]; hidden: number } => {
    const width = typeof resolvedWidth === "number"
        ? resolvedWidth
        : (typeof resolvedWidth === "string" ? Number.parseFloat(resolvedWidth) : 180);
    const cellWidth = Number.isFinite(width) ? width : 180;
    const available = Math.max(48, cellWidth - 14);
    const moreReserve = 34;
    const gap = 4;
    let used = 0;
    const visible: string[] = [];
    const chipWidth = (text: string) => Math.max(36, text.length * 13 + 14);

    for (let i = 0; i < tags.length; i++) {
        const w = chipWidth(tags[i]!);
        const remaining = tags.length - i - 1;
        const nextUsed = used + (visible.length > 0 ? gap : 0) + w;
        const limit = remaining > 0 ? available - moreReserve : available;
        if (nextUsed > limit) break;
        visible.push(tags[i]!);
        used = nextUsed;
    }
    return { visible, hidden: Math.max(0, tags.length - visible.length) };
};

const getTagRenderInfo = (record: RowItem, text: string[] | undefined, resolvedWidth?: string | number) => {
    return getCollapsedTags(getRowTags(record, text), resolvedWidth);
};

const toggleTagMenu = (workNo: string) => {
    tagKeyword.value = "";
};

const toggleTagOption = async (record: RowItem, tag: string, text?: string[]) => {
    const current = [...getRowTags(record, text)];
    const idx = current.indexOf(tag);
    if (idx >= 0) current.splice(idx, 1);
    else current.push(tag);
    const prev = [...getRowTags(record, text)];
    tagsModel[record.workNo] = current;
    record.tags = current;
    try {
        await syncRecordUpdateToApi(record, { tags: current });
    } catch (error: any) {
        tagsModel[record.workNo] = prev;
        record.tags = prev;
        message.error(error?.message || "标签同步失败");
    }
};

const filteredTagOptions = computed(() => {
    const kw = tagKeyword.value.trim();
    const options = dynamicTagOptions.value.length ? dynamicTagOptions.value : baseTagOptions;
    if (!kw) return options;
    return options.filter((x) => x.includes(kw));
});

const createTagOptions = computed(() => {
    const merged = new Set<string>([...createBugTagOptions, ...baseTagOptions, ...dynamicTagOptions.value]);
    return [...merged];
});

const createProjectOptions = computed(() => {
    if (props.useApi && apiProjects.value.length > 0) {
        return apiProjects.value.map((x) => x.name);
    }
    return createBugProjectOptions;
});

const resolveCreateProjectId = (): string => {
    if (!apiProjects.value.length) return "";
    const selected = createBugForm.project?.trim();
    if (!selected) return apiProjects.value[0]?.id || "";
    const match = apiProjects.value.find((x) => x.name === selected || x.id === selected);
    return match?.id || apiProjects.value[0]?.id || "";
};

const filteredCreateTagOptions = computed(() => {
    const kw = createTagKeyword.value.trim();
    if (!kw) return createTagOptions.value;
    return createTagOptions.value.filter((x) => x.includes(kw));
});

const toggleCreateTagMenu = () => {
    createTagDropdownOpen.value = !createTagDropdownOpen.value;
    if (!createTagDropdownOpen.value) createTagKeyword.value = "";
};

const toggleCreateTagOption = (tag: string) => {
    const list = [...createBugForm.tags];
    const idx = list.indexOf(tag);
    if (idx >= 0) list.splice(idx, 1);
    else list.push(tag);
    createBugForm.tags = list;
};

const finishCreateTagEdit = () => {
    createTagDropdownOpen.value = false;
    createTagKeyword.value = "";
};

const typeGroups = computed<WorkItemType[]>(() => {
    const all: WorkItemType[] = ["需求", "任务", "缺陷"];
    const kw = typeKeyword.value.trim();
    if (!kw) return all;
    return all.filter((x) => x.includes(kw));
});

const toggleTypeGroup = (group: WorkItemType) => {
    typeGroupOpen[group] = !typeGroupOpen[group];
};

const selectType = (value: WorkItemType) => {
    if (props.type) return;
    type.value = value;
    if (status.value && !getStatusOptionsByType(value).some((x) => x.value === status.value)) {
        status.value = "";
    }
    typeDropdownOpen.value = false;
};

const loadApiMetadata = async (withStories = false) => {
    if (!props.useApi) return;
    const tasks: Promise<any>[] = [getVortflowProjects()];
    if (withStories) {
        tasks.push(getVortflowStories({ page: 1, page_size: 100 }));
    }
    const results = await Promise.allSettled(tasks);
    const projectsRes = results[0];
    const storiesRes = withStories ? results[1] : undefined;
    if (projectsRes && projectsRes.status === "fulfilled") {
        apiProjects.value = ((projectsRes.value as any)?.items || []).map((x: any) => ({ id: String(x.id), name: String(x.name || x.id) }));
        if (apiProjects.value.length > 0) {
            const names = new Set(apiProjects.value.map((x) => x.name));
            if (!createBugForm.project || !names.has(createBugForm.project)) {
                createBugForm.project = apiProjects.value[0]!.name;
            }
        }
    }
    if (storiesRes && storiesRes.status === "fulfilled") {
        apiStories.value = ((storiesRes.value as any)?.items || []).map((x: any) => ({ id: String(x.id), title: String(x.title || x.id) }));
    }
};

onMounted(async () => {
    await loadMemberOptions();
    ensureOwnerGroupMapEntries();
    rebuildMockDataset();
    await loadApiMetadata(false);
    if (props.useApi) {
        tableRef.value?.refresh?.();
    }

    // Handle route query parameters for direct access
    const action = route.query.action as string;
    const id = route.query.id as string;
    const parentId = route.query.parentId as string;
    if (action === "create") {
        await handleCreateBug();
        if (parentId) {
            createParentStoryId.value = parentId;
            createProjectId.value = findStoryRowById(parentId)?.projectId || "";
        }
    } else if (action === "detail" && id) {
        // Find the record by workNo and open detail
        const record = allData.value.find(x => x.workNo === id);
        if (record) {
            handleOpenBugDetail(record);
        }
    }
});
</script>

<template>
    <div class="p-6 space-y-4">
        <WorkItemFilters
            v-model:keyword="keyword"
            v-model:owner="owner"
            v-model:type="type"
            v-model:status="status"
            :page-title="props.pageTitle"
            :create-button-text="props.createButtonText"
            :total-count="totalCount || allData.length"
            :member-options="memberOptions"
            :owner-groups="ownerGroups"
            :status-options="currentStatusFilterOptions"
            :show-type-filter="!props.type"
            @search="tableRef?.refresh?.()"
            @reset="onReset"
            @create="handleCreateBug"
        />

        <div class="bg-white rounded-xl p-4">
            <div v-if="selectedRows.length > 0" class="mb-3 flex items-center gap-3 text-sm">
                <span class="text-gray-500">已选 {{ selectedRows.length }} 项</span>
                <vort-popconfirm title="确认批量删除选中记录？" @confirm="handleBatchDelete">
                    <VortButton  variant="text" danger>批量删除</VortButton>
                </vort-popconfirm>
                <VortButton  variant="link" @click="clearSelection">取消选择</VortButton>
            </div>
            <ProTable
                ref="tableRef"
                :columns="columns"
                :request="request"
                :post-process-data="postProcessTableRows"
                :params="queryParams"
                :row-key="rowKeyGetter"
                :row-selection="rowSelection"
                :pagination="{ pageSize: 20, showSizeChanger: true, showQuickJumper: true, pageSizeOptions: [10, 20, 50] }"
                :toolbar="false"
                bordered
            >
                <template #title="{ text, record }">
                    <VortButton class="title-link-cell" :title="text" variant="link" @click.stop="handleOpenBugDetail(record)">
                        <span
                            v-if="record.type === '需求' && record.childrenCount"
                            class="story-expand-toggle"
                            :class="{
                                expanded: expandedStoryIds[String(record.backendId || '')],
                                loading: expandingStoryIds[String(record.backendId || '')]
                            }"
                            @click.stop="toggleStoryExpand(record)"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" aria-hidden="true" role="img" class="flex-shrink-0 iconify iconify--gitee icon-caret-down" width="1em" height="1em" preserveAspectRatio="xMidYMid meet" viewBox="0 0 16 16"><g fill="none" fill-rule="evenodd"><path d="M0 0h16v16H0z"></path><path fill="currentColor" fill-rule="nonzero" d="m10.835 7.638-2.388 2.666a.628.628 0 01-.441.196.57.57 0 01-.426-.195L5.192 7.638c-.188-.19-.24-.478-.147-.725s.313-.413.556-.413h4.793c.243 0 .462.162.556.411.093.25.058.537-.115.727z"></path></g></svg>
                        </span>
                        <span v-else-if="record.isChild" class="story-child-indent"></span>
                        <span v-else class="story-expand-placeholder"></span>
                        
                        <span class="work-type-icon" :class="getWorkItemTypeIconClass(record.type)">
                            {{ getWorkItemTypeIconSymbol(record.type) }}
                        </span>

                        <span class="title-link-text" :class="{ 'story-child-text': record.isChild }">{{ text }}</span>
                    </VortButton>
                </template>

                <template #priority="{ text, record }">
                    <WorkItemPriority
                        :model-value="getRowPriority(record, text)"
                        :open="openPriorityFor === record.workNo"
                        @update:open="(open) => { if (!open && openPriorityFor === record.workNo) openPriorityFor = null; }"
                        @click.stop="togglePriorityMenu(record.workNo)"
                        @change="(value) => selectPriority(record, value)"
                    />
                </template>

                <template #tags="{ text, record, resolvedWidth }">
                        <TableCell @click.stop="tagPopoverOpen[record.workNo] = !tagPopoverOpen[record.workNo]">
                    <Popover
                        :open="tagPopoverOpen[record.workNo]"
                        trigger="click"
                        placement="bottomLeft"
                        :arrow="false"
                        @update:open="(open) => { if (!open) tagPopoverOpen[record.workNo] = false; }"
                    >
                            <div class="flex items-center gap-1 flex-nowrap whitespace-nowrap overflow-hidden">
                                <template v-for="tag in getTagRenderInfo(record, text, resolvedWidth).visible" :key="record.workNo + '-' + tag">
                                    <span
                                        class="px-1.5 py-0.5 rounded text-xs text-white inline-block"
                                        :style="{ backgroundColor: getTagColor(tag) }"
                                    >
                                        {{ tag }}
                                    </span>
                                </template>
                                <span v-if="getTagRenderInfo(record, text, resolvedWidth).hidden > 0" class="text-gray-400 font-medium text-sm">
                                    +{{ getTagRenderInfo(record, text, resolvedWidth).hidden }}
                                </span>
                            </div>

                        <template #content>
                            <div class="w-[240px]" @click.stop>
                                <div class="mb-2">
                                    <div class="relative">
                                        <VortInput
                                            v-model="tagKeyword"
                                            placeholder="搜索..."
                                            class="w-full"
                                            size="small"
                                        />
                                    </div>
                                </div>
                                <div class="max-h-[200px] overflow-y-auto pr-1">
                                    <div
                                        v-for="tag in filteredTagOptions"
                                        :key="record.workNo + '-opt-' + tag"
                                        class="w-full px-2 py-1 rounded-md hover:bg-gray-50 cursor-pointer"
                                        @click.stop="toggleTagOption(record, tag, text)"
                                    >
                                        <div class="flex items-center gap-3">
                                            <vort-checkbox
                                                :checked="getRowTags(record, text).includes(tag)"
                                                @update:checked="() => toggleTagOption(record, tag, text)"
                                                @click.stop
                                                style="min-height: 24px;"
                                            />
                                            <span
                                                class="inline-block w-3 h-3 rounded-full flex-shrink-0"
                                                :style="{ backgroundColor: getTagColor(tag) }"
                                            />
                                            <span class="text-sm text-gray-700 leading-5">{{ tag }}</span>
                                        </div>
                                    </div>
                                </div>
                                <div class="mt-1 pt-2 border-t border-gray-100 text-left">
                                    <button
                                        type="button"
                                        class="inline-flex items-center gap-1 px-2 py-1 text-sm text-blue-600 hover:text-blue-700"
                                        @click.stop="openCreateTagDialog()"
                                    >
                                        <span class="text-base leading-none">+</span>
                                        <span>新建标签</span>
                                    </button>
                                </div>
                            </div>
                        </template>
                    </Popover>
                        </TableCell>
                </template>

                <template #status="{ text, record }">
                    <WorkItemStatus
                        :model-value="getRowStatus(record, text)"
                        :options="filteredRowStatusOptions"
                        :open="openStatusFor === record.workNo"
                        v-model:keyword="rowStatusKeyword"
                        @update:open="(open) => { if (!open && openStatusFor === record.workNo) openStatusFor = null; }"
                        @click.stop="toggleRowStatusMenu(record)"
                        @change="(value) => selectRowStatus(record, value)"
                    />
                </template>

                <template #owner="{ text, record }">
                    <Popover
                        :open="openOwnerFor === record.workNo"
                        trigger="click"
                        placement="bottomLeft"
                        :arrow="false"
                        @update:open="(open) => { if (!open && openOwnerFor === record.workNo) openOwnerFor = null; }"
                    >
                        <VortButton
                            class="h-8 max-w-[150px] px-2 rounded-md bg-transparent flex items-center gap-2"
                            variant="text"
                            :class="openOwnerFor === record.workNo ? 'ring-1 ring-blue-200' : ''"
                            @click.stop="toggleRowOwnerMenu(record.workNo)"
                        >
                            <span
                                class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center shrink-0 overflow-hidden"
                                :style="{ backgroundColor: getAvatarBg(getRowOwner(record, text)) }"
                            >
                                <img v-if="getMemberAvatarUrl(getRowOwner(record, text))" :src="getMemberAvatarUrl(getRowOwner(record, text))" class="w-full h-full object-cover" />
                                <template v-else>{{ getAvatarLabel(getRowOwner(record, text)) }}</template>
                            </span>
                            <span class="text-sm text-gray-700 truncate">{{ getRowOwner(record, text) }}</span>
                        </VortButton>

                        <template #content>
                            <div class="w-[260px] p-3" @click.stop>
                                <div class="mb-2">
                                    <div class="relative">
                                        <VortInput
                                            v-model="ownerEditKeyword"
                                            placeholder="搜索..."
                                            class="w-full"
                                            size="small"
                                        />
                                    </div>
                                </div>
                                <div class="max-h-[420px] overflow-y-auto -mx-3 text-left">
                                    <VortButton class="w-full h-10 px-3 flex justify-start text-left text-gray-700 hover:bg-gray-50" variant="text" @click.stop="selectRowOwner(record, '')">
                                        未指派
                                    </VortButton>
                                    <div v-for="group in filteredOwnerEditGroups" :key="'row-owner-' + group.label">
                                        <VortButton
                                            class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left"
                                            variant="text"
                                            @click.stop="toggleOwnerEditGroup(group.label)"
                                        >
                                            <span class="text-gray-700 text-sm">{{ group.label }}（{{ group.members.length }}）</span>
                                            <span class="status-arrow-simple" :class="{ open: ownerEditGroupOpen[group.label] }" />
                                        </VortButton>
                                        <VortButton
                                            v-for="member in (ownerEditGroupOpen[group.label] ? group.members : [])"
                                            :key="'row-owner-member-' + group.label + member"
                                            class="w-full h-10 px-3 flex items-center justify-start gap-2 text-left hover:bg-gray-50"
                                            variant="text"
                                            @click.stop="selectRowOwner(record, member)"
                                        >
                                            <span
                                                class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center overflow-hidden"
                                                :style="{ backgroundColor: getAvatarBg(member) }"
                                            >
                                                <img v-if="getMemberAvatarUrl(member)" :src="getMemberAvatarUrl(member)" class="w-full h-full object-cover" />
                                                <template v-else>{{ getAvatarLabel(member) }}</template>
                                            </span>
                                            <span class="text-sm text-gray-700">{{ member }}</span>
                                        </VortButton>
                                    </div>
                                </div>
                            </div>
                        </template>
                    </Popover>
                </template>

                <template #creator="{ text }">
                    <div class="h-8 max-w-[150px] px-2 rounded-md bg-transparent flex items-center gap-2">
                        <span
                            class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center shrink-0"
                            :style="{ backgroundColor: getAvatarBg(text) }"
                        >
                            {{ getAvatarLabel(text) }}
                        </span>
                        <span class="text-sm text-gray-700 truncate">{{ text }}</span>
                    </div>
                </template>

                <template #actions="{ record }">
                    <vort-popconfirm title="确认删除？" @confirm="handleDelete(record)">
                        <VortButton size="small" variant="link" danger>删除</VortButton>
                    </vort-popconfirm>
                </template>

                <template #collaborators="{ text, record }">
                    <Popover
                        :open="openCollaboratorFor === record.workNo"
                        trigger="click"
                        placement="bottomLeft"
                        :arrow="false"
                        @update:open="(open) => { if (!open && openCollaboratorFor === record.workNo) openCollaboratorFor = null; }"
                    >
                        <VortButton
                            class="h-8 px-1 rounded-md bg-transparent flex items-center"
                            variant="text"
                            @click.stop="toggleCollaboratorMenu(record.workNo)"
                        >
                            <div class="flex items-center">
                                <div
                                    v-for="(name, idx) in getRowCollaborators(record, text)"
                                    :key="record.workNo + '-c-' + name + idx"
                                    class="-ml-1 first:ml-0 w-6 h-6 rounded-full border border-white text-white text-[11px] flex items-center justify-center"
                                    :style="{ backgroundColor: getAvatarBg(name) }"
                                    :title="name"
                                >
                                    {{ getAvatarLabel(name) }}
                                </div>
                            </div>
                        </VortButton>

                        <template #content>
                            <div class="w-[260px] p-3" @click.stop>
                                <div class="mb-2">
                                    <div class="relative">
                                        <VortInput
                                            v-model="collaboratorKeyword"
                                            placeholder="搜索..."
                                            class="w-full"
                                            size="small"
                                        />
                                    </div>
                                </div>
                                <div class="max-h-[260px] overflow-y-auto -mx-3 text-left">
                                    <div v-for="group in filteredCollaboratorGroups" :key="'collab-' + group.label">
                                        <VortButton
                                            class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left"
                                            variant="text"
                                            @click.stop="toggleCollaboratorGroup(group.label)"
                                        >
                                            <span class="text-gray-700 text-sm">{{ group.label }}（{{ group.members.length }}）</span>
                                            <span class="status-arrow-simple" :class="{ open: collaboratorGroupOpen[group.label] }" />
                                        </VortButton>
                                        <VortButton
                                            v-for="member in (collaboratorGroupOpen[group.label] ? group.members : [])"
                                            :key="'collab-member-' + group.label + member"
                                            class="w-full h-10 px-3 flex items-center justify-start gap-2 text-left hover:bg-gray-50"
                                            variant="text"
                                            @click.stop="toggleRowCollaborator(record, member, text)"
                                        >
                                            <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                                <span v-if="getRowCollaborators(record, text).includes(member)">✓</span>
                                            </span>
                                            <span
                                                class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center"
                                                :style="{ backgroundColor: getAvatarBg(member) }"
                                            >
                                                {{ getAvatarLabel(member) }}
                                            </span>
                                            <span class="text-sm text-gray-700">{{ member }}</span>
                                        </VortButton>
                                    </div>
                                </div>
                            </div>
                        </template>
                    </Popover>
                </template>

                <template #planTime="{ text, record }">
                    <div class="relative inline-block" @click.stop>
                        <VortButton
                            v-if="openPlanTimeFor !== record.workNo"
                            class="plan-time-display"
                            variant="text"
                            @click.stop="togglePlanTimeMenu(record.workNo, record, text)"
                        >
                            {{ getRowPlanTimeText(record, text) }}
                        </VortButton>
                        <vort-range-picker
                            v-else
                            v-model="planTimeModel[record.workNo]"
                            value-format="YYYY-MM-DD"
                            format="YYYY-MM-DD"
                            separator="~"
                            :placeholder="['开始日期', '结束日期']"
                            class="plan-time-picker"
                            @change="(value: any) => onPlanTimeChange(record, value || text)"
                            @click.stop
                        />
                    </div>
                </template>
            </ProTable>
        </div>

        <vort-drawer
            v-model:open="createBugDrawerOpen"
            :title="createBugDrawerMode === 'create' ? props.createDrawerTitle : props.detailDrawerTitle"
            :width="1180"
            :body-style="{ padding: '16px 20px 20px' }"
        >
            <template v-if="createBugDrawerMode === 'detail'">
                <WorkItemDetail
                    v-if="detailCurrentRecord"
                    :work-no="detailCurrentRecord.workNo"
                    :initial-data="detailCurrentRecord"
                    :parent-record="detailParentRecord"
                    :child-records="detailChildRecords"
                    @close="handleCancelCreateBug"
                    @update="handleDetailUpdate"
                    @open-related="handleOpenBugDetail"
                />
            </template>
            <template v-else>
                <WorkItemCreate
                    ref="createWorkItemRef"
                    :type="props.type"
                    :title="props.createDrawerTitle"
                    :use-api="props.useApi"
                    :project-id="createProjectId"
                    :parent-id="createParentStoryId"
                    @close="handleCancelCreateBug"
                    @success="handleCreateSuccess"
                />
            </template>
            <template #footer>
                <div v-if="createBugDrawerMode === 'create'" class="create-bug-footer">
                    <VortButton variant="primary" @click="handleSubmitCreateBug()">新建</VortButton>
                    <VortButton @click="handleSubmitCreateBug(true)">新建并继续</VortButton>
                    <VortButton @click="handleCancelCreateWorkItem">取消</VortButton>
                </div>
            </template>
        </vort-drawer>

        <VortDialog
            :open="newTagDialogOpen"
            title="新建标签"
            :width="520"
            @update:open="(val) => (newTagDialogOpen = val)"
        >
            <div class="space-y-5 mt-2">
                <div>
                    <div class="text-sm text-gray-700 mb-1">名称</div>
                    <VortInput v-model="newTagName" placeholder="请输入标签名称" />
                </div>
                <div>
                    <div class="text-sm text-gray-700 mb-2">颜色</div>
                    <div class="grid grid-cols-8 gap-2">
                        <button
                            v-for="color in tagColorPalette"
                            :key="color"
                            type="button"
                            class="w-8 h-8 rounded-sm border-2 flex items-center justify-center transition"
                            :class="newTagColor === color ? 'border-blue-500 shadow-sm' : 'border-transparent'"
                            :style="{ backgroundColor: color }"
                            @click="newTagColor = color"
                        >
                            <span v-if="newTagColor === color" class="text-white text-xs">✓</span>
                        </button>
                    </div>
                </div>
            </div>
            <template #footer>
                <VortButton @click="handleCancelCreateTag">取消</VortButton>
                <VortButton variant="primary" class="ml-2" @click="handleConfirmCreateTag">确定</VortButton>
            </template>
        </VortDialog>
    </div>
</template>

<style scoped>
@reference "../../assets/styles/index.css";

.title-link-cell {
    @apply flex items-center justify-start gap-2 cursor-pointer max-w-full !p-0 !h-auto !bg-transparent;
}

.title-link-text {
    @apply truncate text-blue-600 hover:underline;
}

.story-expand-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45));
    transition: transform 0.2s ease, color 0.2s ease;
    flex-shrink: 0;
}

.story-expand-toggle svg {
    width: 18px;
    height: 18px;
    transform: rotate(-90deg);
    transition: transform 0.2s ease;
}

.story-expand-toggle.expanded svg {
    transform: rotate(0deg);
}

.story-expand-toggle.expanded {
    transform: none;
}

.story-expand-toggle.loading {
    pointer-events: none;
}

.story-expand-toggle.loading svg {
    animation: story-expand-spin 0.8s linear infinite;
}

.story-expand-placeholder {
    display: inline-block;
    width: 20px;
    flex-shrink: 0;
}

.story-child-indent {
    display: inline-block;
    width: 44px;
    flex-shrink: 0;
}

@keyframes story-expand-spin {
    from {
        transform: rotate(-90deg);
    }
    to {
        transform: rotate(270deg);
    }
}

.work-type-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    border-radius: 3px;
    font-size: 12px;
    color: #fff;
    flex-shrink: 0;
}

.work-type-icon-demand {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
}

.work-type-icon-task {
    background: linear-gradient(135deg, #0ea5e9 0%, #06b6d4 100%);
}

.work-type-icon-bug {
    background: linear-gradient(135deg, #ef4444 0%, #f97316 100%);
}

.story-child-text {
    padding-left: 0;
}

.story-children-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 20px;
    padding: 0 6px;
    margin-left: 6px;
    border-radius: 999px;
    background: rgba(99, 102, 241, 0.12);
    color: #4f46e5;
    font-size: 12px;
    line-height: 20px;
}

.plan-time-picker {
    @apply w-full;
}

.create-bug-footer {
    display: flex;
    gap: 12px;
}

</style>