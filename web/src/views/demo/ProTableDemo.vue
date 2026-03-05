<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ProTable, type ProTableColumn, type ProTableRequestParams, type ProTableResponse } from "@/components/vort-biz/pro-table";
import { message } from "@openvort/vort-ui";
import VortEditor from "@/components/vort-biz/editor/VortEditor.vue";
import MarkdownView from "@/components/vort-biz/editor/MarkdownView.vue";
import { Pencil } from "lucide-vue-next";
import {
    getVortflowStories, getVortflowTasks, getVortflowBugs,
    getVortflowProjects, createVortflowStory, createVortflowTask, createVortflowBug,
    deleteVortflowStory, deleteVortflowTask, deleteVortflowBug, getMembers,
    updateVortflowStory, updateVortflowTask, updateVortflowBug
} from "@/api";

type Priority = "urgent" | "high" | "medium" | "low" | "none";
type Status =
    | "待确认"
    | "修复中"
    | "已修复"
    | "延期处理"
    | "设计如此"
    | "再次打开"
    | "无法复现"
    | "已关闭"
    | "暂时搁置"
    | "已取消"
    | "意向"
    | "暂搁置"
    | "设计中"
    | "开发中"
    | "开发完成"
    | "测试完成"
    | "待发布"
    | "发布完成"
    | "已完成"
    | "待办的"
    | "进行中";
type WorkType = "缺陷" | "需求" | "任务";
type DateRange = [string, string];
type DemoModeProps = {
    fixedType?: WorkType;
    pageTitle?: string;
    createButtonText?: string;
    createDrawerTitle?: string;
    detailDrawerTitle?: string;
    descriptionPlaceholder?: string;
    useApi?: boolean;
};
type NewBugForm = {
    title: string;
    owner: string;
    collaborators: string[];
    type: WorkType;
    planTime: DateRange | [];
    project: string;
    iteration: string;
    version: string;
    priority: Priority | "";
    tags: string[];
    repo: string;
    branch: string;
    startAt: string;
    endAt: string;
    remark: string;
    description: string;
};

type RowItem = {
    backendId?: string;
    workNo: string;
    title: string;
    priority: Priority;
    tags: string[];
    status: Status;
    createdAt: string;
    collaborators: string[];
    type: WorkType;
    planTime: DateRange;
    description: string;
    owner: string;
    creator: string;
};

type DetailComment = {
    id: string;
    author: string;
    createdAt: string;
    content: string;
};

type DetailLog = {
    id: string;
    actor: string;
    createdAt: string;
    action: string;
};

type CreateBugAttachment = {
    id: string;
    name: string;
    size: number;
};

type MemberOption = {
    id: string;
    name: string;
    avatarUrl: string;
};

type StatusOption = {
    label: string;
    value: Status;
    icon: string;
    iconClass: string;
};

const props = withDefaults(defineProps<DemoModeProps>(), {
    fixedType: undefined,
    pageTitle: "缺陷",
    createButtonText: "+ 新建缺陷",
    createDrawerTitle: "新建缺陷",
    detailDrawerTitle: "缺陷详情",
    descriptionPlaceholder: "请填写缺陷描述",
    useApi: false
});

const keyword = ref("");
const owner = ref("");
const ownerDropdownOpen = ref(false);
const ownerKeyword = ref("");
const openOwnerFor = ref<string | null>(null);
const ownerEditKeyword = ref("");
const ownerTriggerRefs = ref<Record<string, HTMLElement | null>>({});
const ownerDropdownStyle = ref<Record<string, string>>({});
const priorityTriggerRefs = ref<Record<string, HTMLElement | null>>({});
const priorityDropdownStyle = ref<Record<string, string>>({});
const tagTriggerRefs = ref<Record<string, HTMLElement | null>>({});
const tagDropdownStyle = ref<Record<string, string>>({});
const statusTriggerRefs = ref<Record<string, HTMLElement | null>>({});
const statusDropdownStyle = ref<Record<string, string>>({});
const collaboratorTriggerRefs = ref<Record<string, HTMLElement | null>>({});
const collaboratorDropdownStyle = ref<Record<string, string>>({});
const openCollaboratorFor = ref<string | null>(null);
const collaboratorKeyword = ref("");
const type = ref<WorkType | "">(props.fixedType ?? "");
const typeDropdownOpen = ref(false);
const typeKeyword = ref("");
const status = ref("");
const statusDropdownOpen = ref(false);
const statusKeyword = ref("");
const openStatusFor = ref<string | null>(null);
const rowStatusKeyword = ref("");
const rowStatusType = ref<WorkType>(props.fixedType ?? "缺陷");
const openPlanTimeFor = ref<string | null>(null);
const totalCount = ref(0);
const createBugDrawerOpen = ref(false);
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
    type: props.fixedType ?? "缺陷",
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
    description: defaultDescriptionTemplate
});
const createBugForm = reactive<NewBugForm>(createInitialBugForm());
const apiProjects = ref<Array<{ id: string; name: string }>>([]);
const apiStories = ref<Array<{ id: string; title: string }>>([]);
const selectedRowKeys = ref<Array<string | number>>([]);
const selectedRows = ref<RowItem[]>([]);
const pinnedRowsByType = reactive<Record<WorkType, RowItem[]>>({
    需求: [],
    任务: [],
    缺陷: [],
});

const createBugTagOptions = ["客户需求", "演示站", "运营需求", "待开会确认", "已发布", "高优先", "稳定性", "UI优化"];
const createBugProjectOptions = ["VortMall", "OpenVort", "VortFlow"];
const createBugRepoOptions = ["openvort/web", "openvort/core", "openvort/vortflow"];
const createBugBranchOptions = ["develop", "develop-wzh", "release/1.0"];

const defaultOwnerGroups = [
    { label: "项目成员", members: ["代志祥", "陈艳", "陈曦", "祝璞", "刘洋", "甘洋", "邱锐", "熊纲强"] },
    { label: "企业成员", members: ["apollo_Xuuu", "曾春红", "superdargon", "邱锐", "熊纲强"] },
    { label: "离职人员", members: ["金杜森", "熊军", "杨旭"] }
] as const;
const memberOptions = ref<MemberOption[]>([]);
const ownerGroups = ref<Array<{ label: string; members: string[] }>>(
    defaultOwnerGroups.map((g) => ({ label: g.label, members: [...g.members] }))
);
const bugStatusFilterOptions: StatusOption[] = [
    { label: "待确认", value: "待确认", icon: "○", iconClass: "text-gray-400" },
    { label: "修复中", value: "修复中", icon: "◔", iconClass: "text-blue-500" },
    { label: "已修复", value: "已修复", icon: "✓", iconClass: "text-blue-500" },
    { label: "延期处理", value: "延期处理", icon: "▷", iconClass: "text-blue-500" },
    { label: "设计如此", value: "设计如此", icon: "⌛", iconClass: "text-amber-500" },
    { label: "再次打开", value: "再次打开", icon: "⚡", iconClass: "text-red-500" },
    { label: "无法复现", value: "无法复现", icon: "!", iconClass: "text-amber-500" },
    { label: "已关闭", value: "已关闭", icon: "✓", iconClass: "text-gray-700" },
    { label: "暂时搁置", value: "暂时搁置", icon: "⌛", iconClass: "text-slate-400" }
];
const demandStatusFilterOptions: StatusOption[] = [
    { label: "已取消", value: "已取消", icon: "✕", iconClass: "text-red-500" },
    { label: "意向", value: "意向", icon: "○", iconClass: "text-slate-500" },
    { label: "暂搁置", value: "暂搁置", icon: "⌛", iconClass: "text-slate-400" },
    { label: "设计中", value: "设计中", icon: "✎", iconClass: "text-indigo-500" },
    { label: "开发中", value: "开发中", icon: "◔", iconClass: "text-blue-500" },
    { label: "开发完成", value: "开发完成", icon: "✓", iconClass: "text-cyan-600" },
    { label: "测试完成", value: "测试完成", icon: "✓", iconClass: "text-violet-600" },
    { label: "待发布", value: "待发布", icon: "◌", iconClass: "text-amber-600" },
    { label: "发布完成", value: "发布完成", icon: "✓", iconClass: "text-emerald-600" },
    { label: "已完成", value: "已完成", icon: "✓", iconClass: "text-emerald-700" },
];
const taskStatusFilterOptions: StatusOption[] = [
    { label: "待办的", value: "待办的", icon: "○", iconClass: "text-slate-500" },
    { label: "进行中", value: "进行中", icon: "◔", iconClass: "text-blue-500" },
    { label: "已完成", value: "已完成", icon: "✓", iconClass: "text-emerald-700" },
    { label: "已取消", value: "已取消", icon: "✕", iconClass: "text-red-500" },
];
const statusFilterOptionsByType: Record<WorkType, StatusOption[]> = {
    需求: demandStatusFilterOptions,
    任务: taskStatusFilterOptions,
    缺陷: bugStatusFilterOptions,
};
const allStatusFilterOptions: StatusOption[] = Array.from(
    new Map(
        [...demandStatusFilterOptions, ...taskStatusFilterOptions, ...bugStatusFilterOptions].map((item) => [item.value, item])
    ).values()
);
const getStatusOptionsByType = (typeValue: WorkType): StatusOption[] => {
    return statusFilterOptionsByType[typeValue] || bugStatusFilterOptions;
};
const getStatusOption = (value: Status, typeValue?: WorkType) => {
    const options = typeValue ? getStatusOptionsByType(typeValue) : allStatusFilterOptions;
    return options.find((x) => x.value === value) || options[0] || allStatusFilterOptions[0]!;
};

const getWorkTypeIconClass = (type: WorkType): string => {
    if (type === "需求") return "work-type-icon-demand";
    if (type === "任务") return "work-type-icon-task";
    return "work-type-icon-bug";
};

const getWorkTypeIconSymbol = (type: WorkType): string => {
    if (type === "需求") return "≡";
    if (type === "任务") return "☑";
    return "✹";
};
const priorityOptions: Array<{ label: string; value: Priority }> = [
    { label: "紧急", value: "urgent" },
    { label: "高", value: "high" },
    { label: "中", value: "medium" },
    { label: "低", value: "low" },
    { label: "无优先级", value: "none" }
];

const statusClassMap: Record<Status, string> = {
    待确认: "bg-gray-100 text-gray-400 border-gray-200",
    修复中: "bg-blue-50 text-blue-600 border-blue-100",
    已修复: "bg-blue-50 text-blue-600 border-blue-100",
    延期处理: "bg-sky-100 text-sky-700 border-sky-200",
    设计如此: "bg-amber-100 text-amber-600 border-amber-200",
    再次打开: "bg-red-100 text-red-600 border-red-200",
    无法复现: "bg-amber-100 text-amber-600 border-amber-200",
    已关闭: "bg-gray-100 text-gray-700 border-gray-200",
    暂时搁置: "bg-gray-100 text-gray-500 border-gray-200",
    已取消: "bg-red-100 text-red-600 border-red-200",
    意向: "bg-slate-100 text-slate-600 border-slate-200",
    暂搁置: "bg-slate-100 text-slate-500 border-slate-200",
    设计中: "bg-indigo-100 text-indigo-600 border-indigo-200",
    开发中: "bg-blue-100 text-blue-600 border-blue-200",
    开发完成: "bg-cyan-100 text-cyan-700 border-cyan-200",
    测试完成: "bg-violet-100 text-violet-700 border-violet-200",
    待发布: "bg-amber-100 text-amber-700 border-amber-200",
    发布完成: "bg-emerald-100 text-emerald-700 border-emerald-200",
    已完成: "bg-emerald-100 text-emerald-700 border-emerald-200",
    待办的: "bg-slate-100 text-slate-600 border-slate-200",
    进行中: "bg-blue-100 text-blue-600 border-blue-200",
};

const priorityLabelMap: Record<Priority, string> = {
    urgent: "紧急",
    high: "高",
    medium: "中",
    low: "低",
    none: "无优先级"
};

const priorityClassMap: Record<Priority, string> = {
    urgent: "text-red-500 border-red-500 bg-red-50",
    high: "text-amber-500 border-amber-500 bg-amber-50",
    medium: "text-blue-500 border-blue-500 bg-blue-50",
    low: "text-emerald-500 border-emerald-500 bg-emerald-50",
    none: "text-gray-400 border-gray-300 bg-gray-50"
};

const priorityModel = reactive<Record<string, Priority>>({});
const openPriorityFor = ref<string | null>(null);
const openTagFor = ref<string | null>(null);
const tagKeyword = ref("");
const createTagDropdownOpen = ref(false);
const createTagKeyword = ref("");
const tagsModel = reactive<Record<string, string[]>>({});
const baseTagOptions = ["客户需求", "演示站", "运营需求", "待开会确认", "已发布", "高优先", "稳定性", "UI优化", "S1", "S2", "S3", "S4", "develop", "test"];
const dynamicTagOptions = ref<string[]>([]);
const planTimeModel = reactive<Record<string, DateRange>>({});
const typeGroupOpen = reactive<Record<WorkType, boolean>>({
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
const resolveActiveType = (): WorkType => {
    if (props.fixedType) return props.fixedType;
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

const formatCnTime = (d: Date): string => {
    const month = d.getMonth() + 1;
    const day = d.getDate();
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `${month}月${day}日 ${hh}:${mm}`;
};

const formatDate = (d: Date): string => {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
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
    const types: WorkType[] = props.fixedType ? [props.fixedType] : ["需求", "任务", "缺陷"];
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

const mapBackendStateToStatus = (typeValue: WorkType, stateValue: string, seed: string): Status => {
    const normalized = String(stateValue || "").toLowerCase();
    if (typeValue === "需求") {
        const map: Record<string, Status> = {
            intake: "意向",
            review: "意向",
            rejected: "已取消",
            pm_refine: "设计中",
            design: "设计中",
            breakdown: "开发中",
            dev_assign: "开发中",
            in_progress: "开发中",
            testing: "测试完成",
            bugfix: "开发中",
            done: "已完成",
            closed: "发布完成",
        };
        return map[normalized] || pickStableRandomStatus(typeValue, seed);
    }
    if (typeValue === "任务") {
        const map: Record<string, Status> = {
            todo: "待办的",
            in_progress: "进行中",
            done: "已完成",
            closed: "已取消",
            fixing: "进行中",
            resolved: "已完成",
            verified: "已完成",
        };
        return map[normalized] || pickStableRandomStatus(typeValue, seed);
    }
    const map: Record<string, Status> = {
        intake: "待确认",
        review: "待确认",
        rejected: "暂时搁置",
        pm_refine: "设计如此",
        design: "延期处理",
        breakdown: "待确认",
        dev_assign: "待确认",
        in_progress: "修复中",
        testing: "延期处理",
        bugfix: "再次打开",
        done: "已修复",
        todo: "待确认",
        closed: "已关闭",
        open: "待确认",
        confirmed: "待确认",
        fixing: "修复中",
        resolved: "已修复",
        verified: "已关闭",
    };
    return map[normalized] || pickStableRandomStatus(typeValue, seed);
};

const getBackendStatesByDisplayStatus = (typeValue: WorkType, statusValue: string): string[] | undefined => {
    const statusToStateMap: Record<WorkType, Partial<Record<Status, string[]>>> = {
        需求: {
            已取消: ["rejected"],
            意向: ["intake", "review"],
            暂搁置: ["rejected"],
            设计中: ["pm_refine", "design"],
            开发中: ["breakdown", "dev_assign", "in_progress", "bugfix"],
            开发完成: ["testing"],
            测试完成: ["testing"],
            待发布: ["done"],
            发布完成: ["done"],
            已完成: ["done"],
        },
        任务: {
            待办的: ["todo"],
            进行中: ["in_progress", "fixing"],
            已完成: ["done"],
            已取消: ["closed"],
        },
        缺陷: {
            待确认: ["open", "confirmed"],
            修复中: ["fixing"],
            已修复: ["resolved"],
            已关闭: ["closed"],
            再次打开: ["open"],
        },
    };
    return statusToStateMap[typeValue]?.[statusValue as Status];
};

const mapBackendPriority = (item: any, typeValue: WorkType): Priority => {
    if (typeValue === "需求") {
        const map: Record<number, Priority> = { 1: "urgent", 2: "high", 3: "medium", 4: "low" };
        return map[Number(item?.priority)] || "none";
    }
    if (typeValue === "缺陷") {
        const map: Record<number, Priority> = { 1: "urgent", 2: "high", 3: "medium", 4: "low" };
        return map[Number(item?.severity)] || "none";
    }
    const estimate = Number(item?.estimate_hours || 0);
    if (estimate >= 16) return "urgent";
    if (estimate >= 8) return "high";
    if (estimate >= 4) return "medium";
    return "low";
};

const toBackendPriorityLevel = (value: Priority): number => {
    const map: Record<Priority, number> = {
        urgent: 1,
        high: 2,
        medium: 3,
        low: 4,
        none: 4,
    };
    return map[value] || 4;
};
const toTaskEstimateHours = (value: Priority): number => {
    const map: Record<Priority, number> = {
        urgent: 16,
        high: 8,
        medium: 4,
        low: 2,
        none: 2,
    };
    return map[value] || 2;
};

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
const randomStatusPoolByType: Record<WorkType, Status[]> = {
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
const getMemberIdByName = (name: string): string => {
    const normalized = String(name || "").trim();
    if (!normalized) return "";
    return memberOptions.value.find((m) => m.name === normalized)?.id || "";
};
const getMemberNameById = (memberId: string): string => {
    const normalized = String(memberId || "").trim();
    if (!normalized) return "";
    return memberOptions.value.find((m) => m.id === normalized)?.name || "";
};
const pickStableRandomPerson = (seed: string): string => {
    const peoplePool = getOwnerDropdownPool();
    let hash = 0;
    for (let i = 0; i < seed.length; i++) {
        hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
    }
    return peoplePool[hash % peoplePool.length]!;
};
const pickStableRandomStatus = (typeValue: WorkType, seed: string): Status => {
    const statusPool = randomStatusPoolByType[typeValue] || bugStatusFilterOptions.map((x) => x.value);
    let hash = 0;
    for (let i = 0; i < seed.length; i++) {
        hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
    }
    return statusPool[hash % statusPool.length]!;
};

const loadMemberOptions = async () => {
    try {
        const res: any = await getMembers({ search: "", role: "", page: 1, size: 50 });
        const members = Array.isArray(res?.members) ? res.members : [];
        const next: MemberOption[] = [];
        const seen = new Set<string>();
        for (const item of members) {
            const name = String(item?.name || "").trim();
            if (!name || seen.has(name)) continue;
            seen.add(name);
            next.push({
                id: String(item?.id || name),
                name,
                avatarUrl: String(item?.avatar_url || item?.avatar || "")
            });
        }

        if (!next.length) return;

        memberOptions.value = next;
        ownerGroups.value = [{ label: "全部成员", members: next.map((x) => x.name) }];
        ownerGroupOpen["全部成员"] = true;
        ownerEditGroupOpen["全部成员"] = true;
        collaboratorGroupOpen["全部成员"] = true;
        detailAssigneeGroupOpen["全部成员"] = true;
        createAssigneeGroupOpen["全部成员"] = true;

        if (!props.useApi) {
            allData.value = buildDataset();
            totalCount.value = allData.value.length;
            for (const row of allData.value) {
                planTimeModel[row.workNo] = [...row.planTime];
            }
            collectTagOptions(allData.value);
            tableRef.value?.refresh?.();
        }
    } catch {
        // keep fallback groups
    }
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

const getBackendDisplayTitle = (rawTitle: string, typeValue: WorkType, index: number): string => {
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

const prependPinnedRow = (typeValue: WorkType, row: RowItem) => {
    const list = pinnedRowsByType[typeValue] || [];
    const rowId = row.backendId || row.workNo;
    pinnedRowsByType[typeValue] = [row, ...list.filter((x) => (x.backendId || x.workNo) !== rowId)];
};

const mapBackendItemToRow = (item: any, typeValue: WorkType, index: number): RowItem => {
    const created = item?.created_at ? new Date(item.created_at) : new Date();
    const createdAt = formatCnTime(created);
    const deadline = item?.deadline ? String(item.deadline).split("T")[0] : "";
    const backendId = String(item?.id || index + 1);
    const workNo = `#${backendId.replace(/-/g, "").slice(0, 6).toUpperCase().padEnd(6, "X")}`;
    const ownerSourceId = String(item?.assignee_id || item?.pm_id || item?.developer_id || "").trim();
    const ownerSourceName = getMemberNameById(ownerSourceId);
    const ownerSeed = ownerSourceId || `${backendId}-owner`;
    const creatorSeed = String(item?.reporter_id || `${backendId}-creator`);
    const collabSeed = String(item?.story_id || item?.task_id || `${backendId}-collab`);
    const statusSeed = `${typeValue}-${backendId}-${String(item?.state || "state")}`;
    const ownerName = ownerSourceName || pickStableRandomPerson(ownerSeed);
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
        priority: mapBackendPriority(item, typeValue),
        tags,
        status: mapBackendStateToStatus(typeValue, String(item?.state || ""), statusSeed),
        createdAt,
        collaborators,
        type: typeValue,
        planTime: [planDate, planDate],
        description: item?.description || "",
        owner: ownerName,
        creator: creatorName,
    };
};

const request = async (params: ProTableRequestParams): Promise<ProTableResponse<RowItem>> => {
    const kw = String(params.keyword ?? "").trim().toLowerCase();
    const ownerValue = String(params.owner ?? "").trim();
    const typeValue = String(props.fixedType ?? params.type ?? "").trim();
    const statusValue = String(params.status ?? "").trim();
    const current = Number(params.current || 1);
    const pageSize = Number(params.pageSize || 20);

    if (props.useApi && (typeValue === "需求" || typeValue === "任务" || typeValue === "缺陷")) {
        const workType = typeValue as WorkType;
        const backendStates = statusValue ? getBackendStatesByDisplayStatus(workType, statusValue) : undefined;
        if (statusValue && (!backendStates || backendStates.length === 0)) {
            totalCount.value = 0;
            return { data: [], total: 0, current, pageSize };
        }

        const requestByState = async (state?: string, page = current, size = pageSize) => {
            if (workType === "需求") return getVortflowStories({ keyword: kw, state, page, page_size: size });
            if (workType === "任务") return getVortflowTasks({ keyword: kw, state, page, page_size: size });
            return getVortflowBugs({ keyword: kw, state, page, page_size: size });
        };
        const fetchAllItemsByState = async (state?: string): Promise<any[]> => {
            const batchSize = 200;
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
            return items.map((item: any, idx: number) => mapBackendItemToRow(item, workType, idx));
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
                .filter((x) => !ownerValue || x.owner === ownerValue);
            totalFromApi = allRows.length;
            const start = (current - 1) * pageSize;
            rows = allRows.slice(start, start + pageSize);
        } else {
            const backendState = backendStates?.[0];
            if (ownerValue) {
                const allItems = await fetchAllItemsByState(backendState);
                const allRows = buildRowsFromItems(allItems)
                    .filter((x) => !statusValue || x.status === statusValue)
                    .filter((x) => x.owner === ownerValue);
                totalFromApi = allRows.length;
                const start = (current - 1) * pageSize;
                rows = allRows.slice(start, start + pageSize);
            } else {
                const res: any = await requestByState(backendState, current, pageSize);
                rows = buildRowsFromItems((res as any)?.items || []);
                if (statusValue) rows = rows.filter((x) => x.status === statusValue);
                totalFromApi = Number((res as any)?.total || rows.length);
            }
        }

        if (current === 1) {
            let pinnedRows = pinnedRowsByType[workType] || [];
            if (statusValue) pinnedRows = pinnedRows.filter((x) => x.status === statusValue);
            if (ownerValue) pinnedRows = pinnedRows.filter((x) => x.owner === ownerValue);
            const pinnedIds = new Set(pinnedRows.map((x) => x.backendId || x.workNo));
            rows = [...pinnedRows, ...rows.filter((x) => !pinnedIds.has(x.backendId || x.workNo))];
            rows = rows.slice(0, pageSize);
        }
        collectTagOptions(rows);
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

const tableRef = ref<InstanceType<typeof ProTable> | null>(null);

const queryParams = computed(() => ({
    keyword: keyword.value,
    owner: owner.value,
    type: props.fixedType || type.value,
    status: status.value
}));

const onReset = () => {
    keyword.value = "";
    owner.value = "";
    type.value = props.fixedType ?? "";
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
        const itemType = (props.fixedType || record.type) as WorkType;
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
    await loadApiMetadata(props.fixedType === "任务");
    createBugDrawerMode.value = "create";
    resetCreateBugForm();
    createBugForm.type = props.fixedType ?? createBugForm.type;
    createBugDrawerOpen.value = true;
};

const handleCancelCreateBug = () => {
    createBugDrawerOpen.value = false;
    createBugPriorityDropdownOpen.value = false;
    createAssigneeDropdownOpen.value = false;
    createTagDropdownOpen.value = false;
};

const handleSubmitCreateBug = async () => {
    if (createBugDrawerMode.value !== "create") {
        createBugDrawerOpen.value = false;
        createBugPriorityDropdownOpen.value = false;
        return;
    }

    const title = createBugForm.title.trim();
    if (!title) {
        message.warning("请填写标题");
        return;
    }

    if (props.useApi) {
        const fixedType = (props.fixedType || createBugForm.type || "缺陷") as WorkType;
        try {
            let createdItem: any = null;
            if (fixedType === "需求") {
                const defaultProject = resolveCreateProjectId();
                createdItem = await createVortflowStory({
                    project_id: defaultProject,
                    title,
                    description: createBugForm.description || defaultBugDescription,
                    priority: createBugForm.priority === "urgent" ? 1 : createBugForm.priority === "high" ? 2 : createBugForm.priority === "medium" ? 3 : 4,
                    tags: [...createBugForm.tags],
                    collaborators: [...createBugForm.collaborators],
                    deadline: createBugForm.planTime?.[1] || undefined,
                });
            } else if (fixedType === "任务") {
                if (!apiStories.value.length) {
                    try {
                        const storiesRes = await getVortflowStories({ page: 1, page_size: 100 });
                        apiStories.value = ((storiesRes as any)?.items || []).map((x: any) => ({ id: String(x.id), title: String(x.title || x.id) }));
                    } catch {
                        // fallback handled below
                    }
                }
                const selectedStoryId = apiStories.value[0]?.id || "";
                createdItem = await createVortflowTask({
                    story_id: selectedStoryId,
                    title,
                    description: createBugForm.description || "",
                    task_type: "develop",
                    assignee_id: getMemberIdByName(createBugForm.owner) || undefined,
                    tags: [...createBugForm.tags],
                    collaborators: [...createBugForm.collaborators],
                    deadline: createBugForm.planTime?.[1] || undefined,
                });
            } else {
                createdItem = await createVortflowBug({
                    title,
                    description: createBugForm.description || defaultBugDescription,
                    severity: createBugForm.priority === "urgent" ? 1 : createBugForm.priority === "high" ? 2 : createBugForm.priority === "medium" ? 3 : 4,
                    assignee_id: getMemberIdByName(createBugForm.owner) || undefined,
                    tags: [...createBugForm.tags],
                    collaborators: [...createBugForm.collaborators],
                });
            }
            if (createdItem) {
                const pinnedRow = mapBackendItemToRow(createdItem, fixedType, 0);
                prependPinnedRow(fixedType, pinnedRow);
            }
            tableRef.value?.refresh?.();
            message.success("新建成功");
            createBugDrawerOpen.value = false;
            createBugPriorityDropdownOpen.value = false;
            createAssigneeDropdownOpen.value = false;
            return;
        } catch (error: any) {
            message.error(error?.message || "新建失败");
            return;
        }
    }

    const now = new Date();
    const workNo = toWorkNo(nextWorkNoIndex.value++);
    const fallbackPlanDate = formatDate(now);
    const planTime: DateRange = (createBugForm.planTime as DateRange)?.length === 2
        ? [...(createBugForm.planTime as DateRange)]
        : [fallbackPlanDate, fallbackPlanDate];
    const newPriority: Priority = createBugForm.priority || "none";
    const ownerName = createBugForm.owner || "未指派";
    const collaborators = [...createBugForm.collaborators];

    const newRow: RowItem = {
        workNo,
        title,
        priority: newPriority,
        tags: [...createBugForm.tags],
        status: "待确认",
        createdAt: formatCnTime(now),
        collaborators,
        type: createBugForm.type || props.fixedType || "缺陷",
        planTime,
        description: createBugForm.description || defaultBugDescription,
        owner: ownerName,
        creator: "当前用户"
    };

    allData.value.unshift(newRow);
    planTimeModel[workNo] = [...planTime];
    priorityModel[workNo] = newPriority;
    totalCount.value = allData.value.length;
    tableRef.value?.refresh?.();
    message.success("新建成功");
    createBugDrawerOpen.value = false;
    createBugPriorityDropdownOpen.value = false;
    createAssigneeDropdownOpen.value = false;
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

const handleOpenBugDetail = (record: RowItem) => {
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
    createBugDrawerOpen.value = true;
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
    openPriorityFor.value = willOpen ? workNo : null;
    if (willOpen) nextTick(() => updatePriorityDropdownPosition(workNo));
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

const onGlobalClick = () => {
    openPriorityFor.value = null;
    openTagFor.value = null;
    openOwnerFor.value = null;
    openCollaboratorFor.value = null;
    openStatusFor.value = null;
    openPlanTimeFor.value = null;
    detailStatusDropdownOpen.value = false;
    detailAssigneeDropdownOpen.value = false;
    createAssigneeDropdownOpen.value = false;
    ownerDropdownOpen.value = false;
    typeDropdownOpen.value = false;
    statusDropdownOpen.value = false;
    createBugPriorityDropdownOpen.value = false;
    createTagDropdownOpen.value = false;
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
    if (openStatusFor.value === record.workNo) {
        openStatusFor.value = null;
        rowStatusKeyword.value = "";
        return;
    }
    rowStatusType.value = record.type || resolveActiveType();
    openStatusFor.value = record.workNo;
    rowStatusKeyword.value = "";
    nextTick(() => updateStatusDropdownPosition(record.workNo));
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
    openOwnerFor.value = willOpen ? workNo : null;
    ownerEditKeyword.value = "";
    if (willOpen) {
        nextTick(() => updateOwnerDropdownPosition(workNo));
    }
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

const setOwnerTriggerRef = (workNo: string, el: HTMLElement | null) => {
    if (el) ownerTriggerRefs.value[workNo] = el;
    else delete ownerTriggerRefs.value[workNo];
};

const updateOwnerDropdownPosition = (workNo?: string) => {
    const targetWorkNo = workNo || openOwnerFor.value;
    if (!targetWorkNo) return;
    const trigger = ownerTriggerRefs.value[targetWorkNo];
    if (!trigger) return;

    const rect = trigger.getBoundingClientRect();
    const panelWidth = 260;
    const panelHeight = 420;
    const gap = 6;
    const viewportPadding = 8;

    let left = rect.left;
    const maxLeft = window.innerWidth - panelWidth - viewportPadding;
    left = Math.min(Math.max(viewportPadding, left), Math.max(viewportPadding, maxLeft));

    let top = rect.bottom + gap;
    if (top + panelHeight > window.innerHeight - viewportPadding) {
        top = rect.top - panelHeight - gap;
    }
    if (top < viewportPadding) top = viewportPadding;

    ownerDropdownStyle.value = {
        position: "fixed",
        left: `${left}px`,
        top: `${top}px`,
        zIndex: "9999"
    };
};

const buildFloatingDropdownStyle = (trigger: HTMLElement, panelWidth: number, panelHeight: number): Record<string, string> => {
    const rect = trigger.getBoundingClientRect();
    const gap = 6;
    const viewportPadding = 8;

    let left = rect.left;
    const maxLeft = window.innerWidth - panelWidth - viewportPadding;
    left = Math.min(Math.max(viewportPadding, left), Math.max(viewportPadding, maxLeft));

    let top = rect.bottom + gap;
    if (top + panelHeight > window.innerHeight - viewportPadding) {
        top = rect.top - panelHeight - gap;
    }
    if (top < viewportPadding) top = viewportPadding;

    return {
        position: "fixed",
        left: `${left}px`,
        top: `${top}px`,
        zIndex: "9999"
    };
};

const setPriorityTriggerRef = (workNo: string, el: HTMLElement | null) => {
    if (el) priorityTriggerRefs.value[workNo] = el;
    else delete priorityTriggerRefs.value[workNo];
};

const updatePriorityDropdownPosition = (workNo?: string) => {
    const targetWorkNo = workNo || openPriorityFor.value;
    if (!targetWorkNo) return;
    const trigger = priorityTriggerRefs.value[targetWorkNo];
    if (!trigger) return;
    priorityDropdownStyle.value = buildFloatingDropdownStyle(trigger, 124, 220);
};

const setTagTriggerRef = (workNo: string, el: HTMLElement | null) => {
    if (el) tagTriggerRefs.value[workNo] = el;
    else delete tagTriggerRefs.value[workNo];
};

const updateTagDropdownPosition = (workNo?: string) => {
    const targetWorkNo = workNo || openTagFor.value;
    if (!targetWorkNo) return;
    const trigger = tagTriggerRefs.value[targetWorkNo];
    if (!trigger) return;
    tagDropdownStyle.value = buildFloatingDropdownStyle(trigger, 240, 320);
};

const setStatusTriggerRef = (workNo: string, el: HTMLElement | null) => {
    if (el) statusTriggerRefs.value[workNo] = el;
    else delete statusTriggerRefs.value[workNo];
};

const updateStatusDropdownPosition = (workNo?: string) => {
    const targetWorkNo = workNo || openStatusFor.value;
    if (!targetWorkNo) return;
    const trigger = statusTriggerRefs.value[targetWorkNo];
    if (!trigger) return;
    statusDropdownStyle.value = buildFloatingDropdownStyle(trigger, 240, 330);
};

const setCollaboratorTriggerRef = (workNo: string, el: HTMLElement | null) => {
    if (el) collaboratorTriggerRefs.value[workNo] = el;
    else delete collaboratorTriggerRefs.value[workNo];
};

const updateCollaboratorDropdownPosition = (workNo?: string) => {
    const targetWorkNo = workNo || openCollaboratorFor.value;
    if (!targetWorkNo) return;
    const trigger = collaboratorTriggerRefs.value[targetWorkNo];
    if (!trigger) return;
    collaboratorDropdownStyle.value = buildFloatingDropdownStyle(trigger, 260, 360);
};

const onViewportChangeForOwnerDropdown = () => {
    if (openOwnerFor.value) updateOwnerDropdownPosition();
    if (openPriorityFor.value) updatePriorityDropdownPosition();
    if (openTagFor.value) updateTagDropdownPosition();
    if (openStatusFor.value) updateStatusDropdownPosition();
    if (openCollaboratorFor.value) updateCollaboratorDropdownPosition();
};

const getRowCollaborators = (record: RowItem, text?: string[]): string[] => {
    return collaboratorsModel[record.workNo] || text || record.collaborators || [];
};

const toggleCollaboratorMenu = (workNo: string) => {
    const willOpen = openCollaboratorFor.value !== workNo;
    openCollaboratorFor.value = willOpen ? workNo : null;
    collaboratorKeyword.value = "";
    if (willOpen) nextTick(() => updateCollaboratorDropdownPosition(workNo));
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

const finishCollaboratorEdit = () => {
    openCollaboratorFor.value = null;
};

const avatarBgPalette = ["#2f80ed", "#5b8ff9", "#9b59b6", "#27ae60", "#f39c12", "#e67e22", "#16a085", "#8e44ad"];
const getAvatarBg = (name: string): string => {
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
    return avatarBgPalette[hash % avatarBgPalette.length]!;
};
const getAvatarLabel = (name: string): string => name.slice(0, 1).toUpperCase();
const getMemberAvatarUrl = (name: string): string => memberOptions.value.find((m) => m.name === name)?.avatarUrl || "";

const tagColorPalette = ["#ef4444", "#d946ef", "#eab308", "#22c55e", "#3b82f6", "#f97316", "#14b8a6", "#8b5cf6"];
const getTagColor = (name: string): string => {
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
    return tagColorPalette[hash % tagColorPalette.length]!;
};

const getRowTags = (record: RowItem, text?: string[]): string[] => {
    return tagsModel[record.workNo] || text || [];
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
    const willOpen = openTagFor.value !== workNo;
    openTagFor.value = willOpen ? workNo : null;
    tagKeyword.value = "";
    if (willOpen) nextTick(() => updateTagDropdownPosition(workNo));
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

const finishTagEdit = () => {
    openTagFor.value = null;
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

const typeGroups = computed<WorkType[]>(() => {
    const all: WorkType[] = ["需求", "任务", "缺陷"];
    const kw = typeKeyword.value.trim();
    if (!kw) return all;
    return all.filter((x) => x.includes(kw));
});

const toggleTypeGroup = (group: WorkType) => {
    typeGroupOpen[group] = !typeGroupOpen[group];
};

const selectType = (value: WorkType) => {
    if (props.fixedType) return;
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
    if (projectsRes.status === "fulfilled") {
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
    document.addEventListener("click", onGlobalClick);
    document.addEventListener("scroll", onViewportChangeForOwnerDropdown, true);
    window.addEventListener("resize", onViewportChangeForOwnerDropdown);
    await loadMemberOptions();
    await loadApiMetadata(false);
});

onBeforeUnmount(() => {
    document.removeEventListener("click", onGlobalClick);
    document.removeEventListener("scroll", onViewportChangeForOwnerDropdown, true);
    window.removeEventListener("resize", onViewportChangeForOwnerDropdown);
});
</script>

<template>
    <div class="p-6 space-y-4">
        <div class="bg-white rounded-xl p-4">
            <h3 class="text-base font-medium text-gray-800 mb-3">{{ props.pageTitle }}</h3>
            <div class="flex flex-wrap items-center gap-3 text-sm">
                <div class="text-gray-600"><span class="text-gray-900 font-medium">共{{ totalCount || allData.length }}项</span></div>
                <input v-model="keyword" placeholder="输入关键词" class="h-8 px-3 border border-gray-300 rounded w-[180px]" />
                <div class="relative" @click.stop>
                    <button
                        class="h-8 min-w-[130px] px-3 border border-slate-300 rounded-md bg-white flex items-center justify-between text-left hover:border-slate-400"
                        :class="{ 'border-blue-500 ring-1 ring-blue-200': ownerDropdownOpen }"
                        @click.stop="ownerDropdownOpen = !ownerDropdownOpen"
                    >
                        <span class="text-sm text-gray-700">{{ owner || "负责人" }}</span>
                        <span class="status-arrow-simple" :class="{ open: ownerDropdownOpen }" />
                    </button>
                    <div v-if="ownerDropdownOpen" class="absolute z-30 mt-1 w-[260px] bg-white border border-gray-200 rounded-lg shadow-md p-3">
                        <div class="mb-2">
                            <div class="relative">
                                <input
                                    v-model="ownerKeyword"
                                    placeholder="搜索..."
                                    class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm"
                                />
                                <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                            </div>
                        </div>
                        <div class="max-h-[460px] overflow-y-auto -mx-3">
                            <button class="w-full h-10 px-3 text-left text-gray-700 hover:bg-gray-50" @click.stop="selectOwner('')">全部</button>
                            <button class="w-full h-10 px-3 text-left text-gray-700 hover:bg-gray-50" @click.stop="selectOwner('未指派')">未指派</button>

                            <div v-for="group in filteredOwnerGroups" :key="group.label">
                                <button
                                    class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left"
                                    @click.stop="toggleOwnerGroup(group.label)"
                                >
                                    <span class="text-gray-700 text-sm">{{ group.label }}（{{ group.members.length }}）</span>
                                    <span class="status-arrow-simple" :class="{ open: ownerGroupOpen[group.label] }" />
                                </button>
                                <button
                                    v-for="member in (ownerGroupOpen[group.label] ? group.members : [])"
                                    :key="group.label + member"
                                    class="w-full h-10 px-3 flex items-center gap-2 text-left hover:bg-gray-50"
                                    @click.stop="selectOwner(member)"
                                >
                                    <span
                                        class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center overflow-hidden"
                                        :style="{ backgroundColor: getAvatarBg(member) }"
                                    >
                                        <img v-if="getMemberAvatarUrl(member)" :src="getMemberAvatarUrl(member)" class="w-full h-full object-cover" />
                                        <template v-else>{{ getAvatarLabel(member) }}</template>
                                    </span>
                                    <span class="text-sm text-gray-700">{{ member }}</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
                <div v-if="!props.fixedType" class="relative" @click.stop>
                    <button
                        class="h-8 min-w-[110px] px-3 border border-slate-300 rounded-md bg-white flex items-center justify-between text-left hover:border-slate-400"
                        :class="{ 'border-blue-500 ring-1 ring-blue-200': typeDropdownOpen }"
                        @click.stop="typeDropdownOpen = !typeDropdownOpen"
                    >
                        <span class="text-sm text-gray-700">{{ type || "类型" }}</span>
                        <span class="status-arrow-simple" :class="{ open: typeDropdownOpen }" />
                    </button>
                    <div v-if="typeDropdownOpen" class="absolute z-30 mt-1 w-[180px] bg-white border border-gray-200 rounded-lg shadow-md p-3">
                        <div class="mb-2">
                            <div class="relative">
                                <input
                                    v-model="typeKeyword"
                                    placeholder="搜索..."
                                    class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm"
                                />
                                <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                            </div>
                        </div>
                        <div class="max-h-[260px] overflow-y-auto -mx-3">
                            <div v-for="group in typeGroups" :key="group">
                                <button
                                    class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left"
                                    @click.stop="toggleTypeGroup(group)"
                                >
                                    <span class="text-gray-700 text-sm">{{ group }}</span>
                                    <span class="status-arrow-simple" :class="{ open: typeGroupOpen[group] }" />
                                </button>
                                <button
                                    v-if="typeGroupOpen[group]"
                                    class="w-full h-10 px-3 flex items-center gap-3 text-left hover:bg-gray-50"
                                    @click.stop="selectType(group)"
                                >
                                    <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                        <span v-if="type === group">✓</span>
                                    </span>
                                    <span class="text-gray-700 text-sm">{{ group }}</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="relative" @click.stop>
                    <button
                        class="h-8 min-w-[130px] px-3 border border-slate-300 rounded-md bg-white flex items-center justify-between text-left hover:border-slate-400"
                        @click.stop="statusDropdownOpen = !statusDropdownOpen"
                    >
                        <span class="text-sm text-gray-700">{{ status || "状态" }}</span>
                        <span class="status-arrow-simple" />
                    </button>
                    <div v-if="statusDropdownOpen" class="absolute z-30 mt-1 w-[240px] bg-white border border-gray-200 rounded-lg shadow-md p-3">
                        <div class="mb-2">
                            <input
                                v-model="statusKeyword"
                                placeholder="搜索..."
                                class="w-full h-9 px-3 border border-gray-300 rounded-md text-sm"
                            />
                        </div>
                        <div class="max-h-[220px] overflow-y-auto pr-1">
                            <button
                                v-for="opt in filteredStatusOptions"
                                :key="opt.value"
                                class="w-full h-10 px-2 rounded-md flex items-center gap-2 text-left hover:bg-gray-50"
                                :class="{ 'bg-slate-100': status === opt.value }"
                                @click.stop="selectStatus(opt.value)"
                            >
                                <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                    <span v-if="status === opt.value">✓</span>
                                </span>
                                <span class="text-sm text-gray-700">{{ opt.label }}</span>
                            </button>
                        </div>
                    </div>
                </div>
                <button class="h-8 px-4 bg-blue-600 text-white rounded hover:bg-blue-700" @click="tableRef?.refresh?.()">查询</button>
                <button class="h-8 px-4 border border-gray-300 rounded hover:bg-gray-50" @click="onReset">重置</button>
                <button class="h-8 px-4 bg-blue-600 text-white rounded hover:bg-blue-700 ml-auto" @click="handleCreateBug">{{ props.createButtonText }}</button>
            </div>
        </div>

        <div class="bg-white rounded-xl p-4">
            <div v-if="selectedRows.length > 0" class="mb-3 flex items-center gap-3 text-sm">
                <span class="text-gray-500">已选 {{ selectedRows.length }} 项</span>
                <vort-popconfirm title="确认批量删除选中记录？" @confirm="handleBatchDelete">
                    <button class="text-red-500 hover:text-red-600">批量删除</button>
                </vort-popconfirm>
                <button class="text-blue-600 hover:text-blue-700" @click="clearSelection">取消选择</button>
            </div>
            <ProTable
                ref="tableRef"
                :columns="columns"
                :request="request"
                :params="queryParams"
                :row-key="rowKeyGetter"
                :row-selection="rowSelection"
                :pagination="{ pageSize: 20, showSizeChanger: true, showQuickJumper: true, pageSizeOptions: [10, 20, 50] }"
                :toolbar="false"
                bordered
            >
                <template #title="{ text, record }">
                    <button class="title-link-cell" :title="text" @click.stop="handleOpenBugDetail(record)">
                        <span class="title-link-text">{{ text }}</span>
                    </button>
                </template>

                <template #priority="{ text, record }">
                    <div class="relative inline-block text-left" @click.stop>
                        <button
                            class="priority-cell-trigger"
                            :ref="(el) => setPriorityTriggerRef(record.workNo, el as HTMLElement | null)"
                            @click.stop="togglePriorityMenu(record.workNo)"
                        >
                            <span class="priority-pill" :class="priorityClassMap[getRowPriority(record, text)]">
                                {{ priorityLabelMap[getRowPriority(record, text)] }}
                            </span>
                        </button>
                        <Teleport to="body">
                            <div
                                v-if="openPriorityFor === record.workNo"
                                class="priority-cell-menu"
                                :style="priorityDropdownStyle"
                                @click.stop
                            >
                                <button
                                    v-for="opt in priorityOptions"
                                    :key="opt.value"
                                    class="priority-cell-menu-item"
                                    :class="{ 'is-selected': getRowPriority(record, text) === opt.value }"
                                    @click.stop="selectPriority(record, opt.value)"
                                >
                                    <span class="priority-pill" :class="priorityClassMap[opt.value]">
                                        {{ opt.label }}
                                    </span>
                                </button>
                            </div>
                        </Teleport>
                    </div>
                </template>

                <template #tags="{ text, record, resolvedWidth }">
                    <div class="relative inline-block w-full" @click.stop>
                        <button class="w-full text-left" :ref="(el) => setTagTriggerRef(record.workNo, el as HTMLElement | null)" @click.stop="toggleTagMenu(record.workNo)">
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
                        </button>

                        <Teleport to="body">
                            <div
                                v-if="openTagFor === record.workNo"
                                class="w-[240px] bg-white border border-gray-200 rounded-lg shadow-md p-3"
                                :style="tagDropdownStyle"
                                @click.stop
                            >
                                <div class="mb-2">
                                    <div class="relative">
                                        <input
                                            v-model="tagKeyword"
                                            placeholder="搜索..."
                                            class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm"
                                        />
                                        <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                                    </div>
                                </div>
                                <div class="max-h-[200px] overflow-y-auto pr-1">
                                    <button
                                        v-for="tag in filteredTagOptions"
                                        :key="record.workNo + '-opt-' + tag"
                                        class="w-full h-10 px-2 rounded-md flex items-center gap-2 text-left hover:bg-gray-50"
                                        @click.stop="toggleTagOption(record, tag, text)"
                                    >
                                        <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                            <span v-if="getRowTags(record, text).includes(tag)">✓</span>
                                        </span>
                                        <span class="w-5 h-5 rounded-full" :style="{ backgroundColor: getTagColor(tag) }" />
                                        <span class="text-sm text-gray-700">{{ tag }}</span>
                                    </button>
                                </div>
                                <div class="mt-2 flex justify-end">
                                    <button class="h-8 px-3 text-sm bg-blue-600 text-white rounded hover:bg-blue-700" @click.stop="finishTagEdit">
                                        完成
                                    </button>
                                </div>
                            </div>
                        </Teleport>
                    </div>
                </template>

                <template #status="{ text, record }">
                    <div class="relative inline-block text-left" @click.stop>
                        <button
                            class="status-edit-trigger"
                            :ref="(el) => setStatusTriggerRef(record.workNo, el as HTMLElement | null)"
                            @click.stop="toggleRowStatusMenu(record)"
                        >
                            <span class="status-badge table-status-badge" :class="statusClassMap[getRowStatus(record, text)]">
                                <span>{{ getRowStatus(record, text) }}</span>
                            </span>
                        </button>
                        <Teleport to="body">
                            <div
                                v-if="openStatusFor === record.workNo"
                                class="w-[240px] bg-white border border-gray-200 rounded-lg shadow-md p-3"
                                :style="statusDropdownStyle"
                                @click.stop
                            >
                                <div class="mb-2">
                                    <input
                                        v-model="rowStatusKeyword"
                                        placeholder="搜索..."
                                        class="w-full h-9 px-3 border border-gray-300 rounded-md text-sm"
                                    />
                                </div>
                                <div class="max-h-[220px] overflow-y-auto pr-1">
                                    <button
                                        v-for="opt in filteredRowStatusOptions"
                                        :key="record.workNo + '-status-' + opt.value"
                                        class="w-full h-10 px-2 rounded-md flex items-center gap-2 text-left hover:bg-gray-50"
                                        :class="{ 'bg-slate-100': getRowStatus(record, text) === opt.value }"
                                        @click.stop="selectRowStatus(record, opt.value as Status)"
                                    >
                                        <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                            <span v-if="getRowStatus(record, text) === opt.value">✓</span>
                                        </span>
                                        <span class="text-sm text-gray-700">{{ opt.label }}</span>
                                    </button>
                                </div>
                            </div>
                        </Teleport>
                    </div>
                </template>

                <template #owner="{ text, record }">
                    <div class="relative inline-block" @click.stop>
                        <button
                            class="h-8 max-w-[150px] px-2 rounded-md bg-transparent flex items-center gap-2"
                            :class="{ 'ring-1 ring-blue-200': openOwnerFor === record.workNo }"
                            :ref="(el) => setOwnerTriggerRef(record.workNo, el as HTMLElement | null)"
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
                        </button>

                        <Teleport to="body">
                            <div
                                v-if="openOwnerFor === record.workNo"
                                class="w-[260px] bg-white border border-gray-200 rounded-lg shadow-md p-3"
                                :style="ownerDropdownStyle"
                                @click.stop
                            >
                                <div class="mb-2">
                                    <div class="relative">
                                        <input
                                            v-model="ownerEditKeyword"
                                            placeholder="搜索..."
                                            class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm"
                                        />
                                        <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                                    </div>
                                </div>
                                <div class="max-h-[420px] overflow-y-auto -mx-3">
                                    <button class="w-full h-10 px-3 text-left text-gray-700 hover:bg-gray-50" @click.stop="selectRowOwner(record, '')">
                                        未指派
                                    </button>
                                    <div v-for="group in filteredOwnerEditGroups" :key="'row-owner-' + group.label">
                                        <button
                                            class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left"
                                            @click.stop="toggleOwnerEditGroup(group.label)"
                                        >
                                            <span class="text-gray-700 text-sm">{{ group.label }}（{{ group.members.length }}）</span>
                                            <span class="status-arrow-simple" :class="{ open: ownerEditGroupOpen[group.label] }" />
                                        </button>
                                        <button
                                            v-for="member in (ownerEditGroupOpen[group.label] ? group.members : [])"
                                            :key="'row-owner-member-' + group.label + member"
                                            class="w-full h-10 px-3 flex items-center gap-2 text-left hover:bg-gray-50"
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
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </Teleport>
                    </div>
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
                        <a class="text-sm text-red-500 cursor-pointer">删除</a>
                    </vort-popconfirm>
                </template>

                <template #collaborators="{ text, record }">
                    <div class="relative inline-block" @click.stop>
                        <button
                            class="h-8 px-1 rounded-md bg-transparent flex items-center"
                            :ref="(el) => setCollaboratorTriggerRef(record.workNo, el as HTMLElement | null)"
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
                        </button>

                        <Teleport to="body">
                            <div
                                v-if="openCollaboratorFor === record.workNo"
                                class="w-[260px] bg-white border border-gray-200 rounded-lg shadow-md p-3"
                                :style="collaboratorDropdownStyle"
                                @click.stop
                            >
                                <div class="mb-2">
                                    <div class="relative">
                                        <input
                                            v-model="collaboratorKeyword"
                                            placeholder="搜索..."
                                            class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm"
                                        />
                                        <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                                    </div>
                                </div>
                                <div class="max-h-[260px] overflow-y-auto -mx-3">
                                    <div v-for="group in filteredCollaboratorGroups" :key="'collab-' + group.label">
                                        <button
                                            class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left"
                                            @click.stop="toggleCollaboratorGroup(group.label)"
                                        >
                                            <span class="text-gray-700 text-sm">{{ group.label }}（{{ group.members.length }}）</span>
                                            <span class="status-arrow-simple" :class="{ open: collaboratorGroupOpen[group.label] }" />
                                        </button>
                                        <button
                                            v-for="member in (collaboratorGroupOpen[group.label] ? group.members : [])"
                                            :key="'collab-member-' + group.label + member"
                                            class="w-full h-10 px-3 flex items-center gap-2 text-left hover:bg-gray-50"
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
                                        </button>
                                    </div>
                                </div>
                                <div class="mt-2 flex justify-end">
                                    <button class="h-8 px-3 text-sm bg-blue-600 text-white rounded hover:bg-blue-700" @click.stop="finishCollaboratorEdit">
                                        完成
                                    </button>
                                </div>
                            </div>
                        </Teleport>
                    </div>
                </template>

                <template #planTime="{ text, record }">
                    <div class="relative inline-block" @click.stop>
                        <button
                            v-if="openPlanTimeFor !== record.workNo"
                            class="plan-time-display"
                            @click.stop="togglePlanTimeMenu(record.workNo, record, text)"
                        >
                            {{ getRowPlanTimeText(record, text) }}
                        </button>
                        <vort-range-picker
                            v-else
                            v-model="planTimeModel[record.workNo]"
                            value-format="YYYY-MM-DD"
                            format="YYYY-MM-DD"
                            separator="~"
                            :placeholder="['开始日期', '结束日期']"
                            class="plan-time-picker"
                            @change="(value: DateRange) => onPlanTimeChange(record, value || text)"
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
                <div class="bug-detail-drawer">
                    <main class="bug-detail-main" v-if="detailCurrentRecord">
                        <div class="bug-detail-meta-top">
                            <span class="work-type-icon" :class="getWorkTypeIconClass(detailCurrentRecord.type)">
                                <svg v-if="detailCurrentRecord.type === '缺陷'" class="work-type-icon-svg" viewBox="0 0 24 24" aria-hidden="true">
                                    <circle cx="12" cy="7.5" r="3.2" fill="white" />
                                    <rect x="8" y="10.5" width="8" height="9" rx="3.8" fill="white" />
                                    <rect x="11.2" y="10.8" width="1.6" height="8.6" rx="0.8" fill="#ef4444" />
                                    <path d="M8.3 12.3H5.2M8.1 15.1H4.8M15.9 12.3H18.8M16.1 15.1H19.2" stroke="white" stroke-width="1.5" stroke-linecap="round" />
                                    <path d="M10.2 4.8 8.7 3.3M13.8 4.8 15.3 3.3" stroke="white" stroke-width="1.5" stroke-linecap="round" />
                                </svg>
                                <template v-else>{{ getWorkTypeIconSymbol(detailCurrentRecord.type) }}</template>
                            </span>
                            <span class="bug-detail-no">{{ detailCurrentRecord.workNo }}</span>
                            <div class="relative inline-block text-left" @click.stop>
                                <button class="detail-status-trigger" @click.stop="toggleDetailStatusMenu">
                                    <span class="detail-status-content">
                                        <span class="detail-status-icon" :class="getStatusOption(detailCurrentRecord.status, detailCurrentRecord.type).iconClass">
                                            {{ getStatusOption(detailCurrentRecord.status, detailCurrentRecord.type).icon }}
                                        </span>
                                        <span class="detail-status-text">{{ detailCurrentRecord.status }}</span>
                                    </span>
                                    <span class="status-arrow-simple" :class="{ open: detailStatusDropdownOpen }" />
                                </button>
                                <div
                                    v-if="detailStatusDropdownOpen"
                                    class="absolute z-30 mt-1 w-[240px] bg-white border border-gray-200 rounded-lg shadow-md p-3"
                                >
                                    <div class="mb-2">
                                        <input
                                            v-model="detailStatusKeyword"
                                            placeholder="搜索..."
                                            class="w-full h-9 px-3 border border-gray-300 rounded-md text-sm"
                                        />
                                    </div>
                                    <div class="max-h-[220px] overflow-y-auto pr-1">
                                        <button
                                            v-for="opt in filteredDetailStatusOptions"
                                            :key="'detail-status-' + opt.value"
                                            class="w-full h-10 px-2 rounded-md flex items-center gap-2 text-left hover:bg-gray-50"
                                            :class="{ 'bg-slate-100': detailCurrentRecord.status === opt.value }"
                                            @click.stop="selectDetailStatus(opt.value as Status)"
                                        >
                                            <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                                <span v-if="detailCurrentRecord.status === opt.value">✓</span>
                                            </span>
                                            <span class="text-[14px] leading-none w-4 text-center" :class="opt.iconClass">{{ opt.icon }}</span>
                                            <span class="text-sm text-gray-700">{{ opt.label }}</span>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <h2 class="bug-detail-title">{{ detailCurrentRecord.title }}</h2>
                        <p class="bug-detail-sub">
                            {{ detailCurrentRecord.owner || "未指派" }}，创建于 {{ detailCurrentRecord.createdAt }}，最近更新于 {{ detailCurrentRecord.createdAt }}
                        </p>

                        <div class="bug-detail-tabs">
                            <button :class="{ active: detailActiveTab === 'detail' }" @click="detailActiveTab = 'detail'">详情</button>
                            <button :class="{ active: detailActiveTab === 'worklog' }" @click="detailActiveTab = 'worklog'">工作日志</button>
                            <button :class="{ active: detailActiveTab === 'related' }" @click="detailActiveTab = 'related'">关联工作项</button>
                            <button :class="{ active: detailActiveTab === 'test' }" @click="detailActiveTab = 'test'">关联测试用例</button>
                            <button :class="{ active: detailActiveTab === 'docs' }" @click="detailActiveTab = 'docs'">关联文档</button>
                        </div>

                        <div class="bug-detail-panel" v-if="detailActiveTab === 'detail'">
                            <div class="bug-detail-top-grid">
                                <div class="bug-detail-left-col">
                                    <div class="bug-detail-info-item bug-detail-info-item-row bug-detail-info-assignee" @click.stop>
                                    <label>负责人 / 协作</label>
                                    <button
                                        class="detail-assignee-trigger"
                                        :class="{ active: detailAssigneeDropdownOpen }"
                                        @click.stop="toggleDetailAssigneeMenu"
                                    >
                                        <div class="detail-assignee-split">
                                            <div class="detail-assignee-owner">
                                                <span
                                                    v-if="detailCurrentRecord.owner && detailCurrentRecord.owner !== '未指派'"
                                                    class="detail-assignee-avatar overflow-hidden"
                                                    :style="{ backgroundColor: getAvatarBg(detailCurrentRecord.owner) }"
                                                >
                                                    <img v-if="getMemberAvatarUrl(detailCurrentRecord.owner)" :src="getMemberAvatarUrl(detailCurrentRecord.owner)" class="w-full h-full object-cover" />
                                                    <template v-else>{{ getAvatarLabel(detailCurrentRecord.owner) }}</template>
                                                </span>
                                                <span class="detail-assignee-owner-name">
                                                    {{ detailCurrentRecord.owner || "未指派" }}
                                                </span>
                                            </div>
                                            <span class="detail-assignee-separator">/</span>
                                            <div class="detail-assignee-collaborators detail-collab-stack">
                                                <template v-if="detailCurrentRecord.collaborators.length > 0">
                                                    <span
                                                        v-for="name in detailCurrentRecord.collaborators"
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
                                    </button>

                                    <div
                                        v-if="detailAssigneeDropdownOpen"
                                        class="detail-assignee-dropdown"
                                    >
                                        <div class="mb-2">
                                            <div class="relative">
                                                <input
                                                    v-model="detailAssigneeKeyword"
                                                    placeholder="输入搜索用户名"
                                                    class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm"
                                                />
                                                <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                                            </div>
                                        </div>
                                        <div class="max-h-[320px] overflow-y-auto -mx-3">
                                            <div v-for="group in filteredDetailAssigneeGroups" :key="'detail-assignee-' + group.label">
                                                <button
                                                    class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left"
                                                    @click.stop="toggleDetailAssigneeGroup(group.label)"
                                                >
                                                    <span class="text-gray-700 text-sm">{{ group.label }}（{{ group.members.length }}）</span>
                                                    <span class="status-arrow-simple" :class="{ open: detailAssigneeGroupOpen[group.label] }" />
                                                </button>
                                                <div v-if="detailAssigneeGroupOpen[group.label]">
                                                    <div
                                                        v-for="member in group.members"
                                                        :key="'detail-assignee-member-' + group.label + member"
                                                        class="detail-assignee-row"
                                                    >
                                                        <div class="detail-assignee-row-left">
                                                            <span
                                                                class="detail-assignee-avatar overflow-hidden"
                                                                :style="{ backgroundColor: getAvatarBg(member) }"
                                                            >
                                                                <img v-if="getMemberAvatarUrl(member)" :src="getMemberAvatarUrl(member)" class="w-full h-full object-cover" />
                                                                <template v-else>{{ getAvatarLabel(member) }}</template>
                                                            </span>
                                                            <span class="text-sm text-gray-700">{{ member }}</span>
                                                        </div>
                                                        <div class="detail-assignee-row-actions">
                                                            <button
                                                                class="detail-role-btn"
                                                                :class="{ active: isDetailOwner(member) }"
                                                                @click.stop="setDetailOwner(member)"
                                                            >
                                                                负责人
                                                            </button>
                                                            <button
                                                                class="detail-role-btn collab"
                                                                :class="{ active: isDetailCollaborator(member) }"
                                                                @click.stop="toggleDetailCollaborator(member)"
                                                            >
                                                                协作者
                                                            </button>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    </div>
                                    <div class="bug-detail-info-item bug-detail-info-item-row"><label>计划时间</label><div>{{ detailCurrentRecord.planTime[0] }} ~ {{ detailCurrentRecord.planTime[1] }}</div></div>
                                    <div class="bug-detail-info-item bug-detail-info-item-row"><label>迭代</label><div>{{ createBugForm.iteration || "未设置" }}</div></div>
                                </div>
                                <div class="bug-detail-right-col">
                                    <div class="bug-detail-info-item bug-detail-info-item-row"><label>类型</label><div>{{ detailCurrentRecord.type }}</div></div>
                                    <div class="bug-detail-info-item bug-detail-info-item-row"><label>项目</label><div>{{ createBugForm.project || "VortMall" }}</div></div>
                                    <div class="bug-detail-info-item bug-detail-info-item-row"><label>版本</label><div>{{ createBugForm.version || "未设置" }}</div></div>
                                </div>
                            </div>
                            <div class="bug-detail-desc">
                                <div class="bug-detail-desc-head">
                                    <h4>描述</h4>
                                    <button class="bug-detail-desc-edit-btn" @click="openDetailDescEditor">
                                        <Pencil :size="14" />
                                    </button>
                                </div>
                                <template v-if="detailDescEditing">
                                    <VortEditor v-model="detailDescDraft" placeholder="请输入描述内容..." min-height="300px" />
                                    <div class="bug-detail-desc-actions">
                                        <vort-button variant="primary" @click="saveDetailDescEditor">保存</vort-button>
                                        <vort-button @click="cancelDetailDescEditor">取消</vort-button>
                                    </div>
                                </template>
                                <template v-else>
                                    <div v-if="(detailCurrentRecord.description || '').trim()" class="bug-detail-desc-content">
                                        <MarkdownView :content="detailCurrentRecord.description || ''" />
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
                                                <div class="bug-detail-comment-content">{{ item.content }}</div>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="bug-detail-comment-editor">
                                        <VortEditor v-model="detailCommentDraft" placeholder="发表您的看法（Ctrl/Command+Enter发送）" min-height="120px" />
                                        <div class="bug-detail-desc-actions">
                                            <vort-button variant="primary" @click="submitDetailComment">评论</vort-button>
                                            <vort-button @click="detailCommentDraft = ''">取消</vort-button>
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
                            <p class="bug-detail-empty">暂无关联工作项</p>
                        </div>
                        <div class="bug-detail-panel" v-else-if="detailActiveTab === 'test'">
                            <p class="bug-detail-empty">暂无关联测试用例</p>
                        </div>
                        <div class="bug-detail-panel" v-else>
                            <p class="bug-detail-empty">暂无关联文档</p>
                        </div>
                    </main>
                </div>
            </template>

            <template v-else>
            <div class="create-bug-drawer">
                <div class="create-bug-main">
                    <div class="create-bug-row create-bug-row-full">
                        <div class="create-bug-field">
                            <label class="create-bug-label">标题 <span class="required">*</span></label>
                            <vort-input v-model="createBugForm.title" placeholder="请填写" />
                        </div>
                    </div>

                    <div class="create-bug-row">
                        <div class="create-bug-field">
                            <label class="create-bug-label">负责人/协作者</label>
                            <div class="bug-detail-info-assignee create-assignee-wrapper" @click.stop>
                                <button
                                    class="detail-assignee-trigger create-assignee-trigger"
                                    :class="{ active: createAssigneeDropdownOpen }"
                                    @click.stop="toggleCreateAssigneeMenu"
                                >
                                    <div class="detail-assignee-split">
                                        <div class="detail-assignee-owner">
                                            <span
                                                v-if="createBugForm.owner"
                                                class="detail-assignee-avatar overflow-hidden"
                                                :style="{ backgroundColor: getAvatarBg(createBugForm.owner) }"
                                            >
                                                <img v-if="getMemberAvatarUrl(createBugForm.owner)" :src="getMemberAvatarUrl(createBugForm.owner)" class="w-full h-full object-cover" />
                                                <template v-else>{{ getAvatarLabel(createBugForm.owner) }}</template>
                                            </span>
                                            <span class="detail-assignee-owner-name">
                                                {{ createBugForm.owner || "未指派" }}
                                            </span>
                                        </div>
                                        <span class="detail-assignee-separator">/</span>
                                        <div class="detail-assignee-collaborators detail-collab-stack">
                                            <template v-if="createBugForm.collaborators.length > 0">
                                                <span
                                                    v-for="name in createBugForm.collaborators"
                                                    :key="'create-collab-' + name"
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
                                </button>

                                <div
                                    v-if="createAssigneeDropdownOpen"
                                    class="detail-assignee-dropdown create-assignee-dropdown"
                                >
                                    <div class="mb-2">
                                        <div class="relative">
                                            <input
                                                v-model="createAssigneeKeyword"
                                                placeholder="输入搜索用户名"
                                                class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm"
                                            />
                                            <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                                        </div>
                                    </div>
                                    <div class="max-h-[320px] overflow-y-auto -mx-3">
                                        <div v-for="group in filteredCreateAssigneeGroups" :key="'create-assignee-' + group.label">
                                            <button
                                                class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left"
                                                @click.stop="toggleCreateAssigneeGroup(group.label)"
                                            >
                                                <span class="text-gray-700 text-sm">{{ group.label }}（{{ group.members.length }}）</span>
                                                <span class="status-arrow-simple" :class="{ open: createAssigneeGroupOpen[group.label] }" />
                                            </button>
                                            <div v-if="createAssigneeGroupOpen[group.label]">
                                                <div
                                                    v-for="member in group.members"
                                                    :key="'create-assignee-member-' + group.label + member"
                                                    class="detail-assignee-row"
                                                >
                                                    <div class="detail-assignee-row-left">
                                                        <span
                                                            class="detail-assignee-avatar overflow-hidden"
                                                            :style="{ backgroundColor: getAvatarBg(member) }"
                                                        >
                                                            <img v-if="getMemberAvatarUrl(member)" :src="getMemberAvatarUrl(member)" class="w-full h-full object-cover" />
                                                            <template v-else>{{ getAvatarLabel(member) }}</template>
                                                        </span>
                                                        <span class="text-sm text-gray-700">{{ member }}</span>
                                                    </div>
                                                    <div class="detail-assignee-row-actions">
                                                        <button
                                                            class="detail-role-btn"
                                                            :class="{ active: isCreateOwner(member) }"
                                                            @click.stop="setCreateOwner(member)"
                                                        >
                                                            负责人
                                                        </button>
                                                        <button
                                                            class="detail-role-btn collab"
                                                            :class="{ active: isCreateCollaborator(member) }"
                                                            @click.stop="toggleCreateCollaborator(member)"
                                                        >
                                                            协作者
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div v-if="!props.fixedType" class="create-bug-field">
                            <label class="create-bug-label">类型 <span class="required">*</span></label>
                            <vort-select v-model="createBugForm.type">
                                <vort-select-option value="缺陷">缺陷</vort-select-option>
                                <vort-select-option value="需求">需求</vort-select-option>
                                <vort-select-option value="任务">任务</vort-select-option>
                            </vort-select>
                        </div>
                    </div>

                    <div class="create-bug-row">
                        <div class="create-bug-field">
                            <label class="create-bug-label">计划时间</label>
                            <vort-range-picker
                                v-model="createBugForm.planTime"
                                value-format="YYYY-MM-DD"
                                format="YYYY-MM-DD"
                                separator="~"
                                :placeholder="['未设置', '未设置']"
                            />
                        </div>
                        <div class="create-bug-field">
                            <label class="create-bug-label">关联项目</label>
                            <vort-select v-model="createBugForm.project">
                                <vort-select-option v-for="item in createProjectOptions" :key="item" :value="item">{{ item }}</vort-select-option>
                            </vort-select>
                        </div>
                    </div>

                    <div class="create-bug-row">
                        <div class="create-bug-field">
                            <label class="create-bug-label">迭代</label>
                            <vort-select v-model="createBugForm.iteration" placeholder="选择迭代" allow-clear>
                                <vort-select-option value="Sprint 1">Sprint 1</vort-select-option>
                                <vort-select-option value="Sprint 2">Sprint 2</vort-select-option>
                            </vort-select>
                        </div>
                        <div class="create-bug-field">
                            <label class="create-bug-label">版本</label>
                            <vort-select v-model="createBugForm.version" placeholder="选择版本" allow-clear>
                                <vort-select-option value="v1.0.0">v1.0.0</vort-select-option>
                                <vort-select-option value="v1.1.0">v1.1.0</vort-select-option>
                            </vort-select>
                        </div>
                    </div>

                    <div class="create-bug-row create-bug-row-full">
                        <div class="create-bug-field">
                            <label class="create-bug-label">描述</label>
                            <VortEditor v-model="createBugForm.description" :placeholder="props.descriptionPlaceholder" min-height="260px" />
                            <div class="create-bug-attachment">
                                <input
                                    ref="createAttachmentInputRef"
                                    type="file"
                                    multiple
                                    class="hidden"
                                    @change="onCreateAttachmentChange"
                                />
                                <button class="create-bug-attachment-trigger" @click="openCreateAttachmentDialog">附件 +</button>
                                <div v-if="createBugAttachments.length > 0" class="create-bug-attachment-list">
                                    <div v-for="item in createBugAttachments" :key="item.id" class="create-bug-attachment-item">
                                        <span class="name">{{ item.name }}</span>
                                        <span class="size">{{ formatFileSize(item.size) }}</span>
                                        <button class="remove" @click="removeCreateAttachment(item.id)">移除</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="create-bug-side">
                    <div class="create-bug-field">
                        <label class="create-bug-label">优先级</label>
                        <div class="relative" @click.stop>
                            <button
                                class="create-bug-priority-trigger"
                                :class="{ active: createBugPriorityDropdownOpen }"
                                @click.stop="toggleCreateBugPriorityMenu"
                            >
                                <span
                                    v-if="createBugForm.priority"
                                    class="priority-pill"
                                    :class="priorityClassMap[createBugForm.priority]"
                                >
                                    {{ priorityLabelMap[createBugForm.priority] }}
                                </span>
                                <span v-else class="text-sm text-gray-400">请选择</span>
                                <span class="status-arrow-simple ml-auto" :class="{ open: createBugPriorityDropdownOpen }" />
                            </button>
                            <div
                                v-if="createBugPriorityDropdownOpen"
                                class="create-bug-priority-menu absolute z-30 mt-1 w-full"
                            >
                                <button
                                    v-for="opt in priorityOptions"
                                    :key="opt.value"
                                    class="create-bug-priority-option"
                                    :class="{ 'is-selected': createBugForm.priority === opt.value }"
                                    @click.stop="selectCreateBugPriority(opt.value)"
                                >
                                    <span class="priority-pill" :class="priorityClassMap[opt.value]">
                                        {{ opt.label }}
                                    </span>
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="create-bug-field">
                        <label class="create-bug-label">标签</label>
                        <div class="relative inline-block w-full" @click.stop>
                            <button class="create-tag-trigger" :class="{ active: createTagDropdownOpen }" @click.stop="toggleCreateTagMenu">
                                <div class="create-tag-preview">
                                    <template v-if="createBugForm.tags.length > 0">
                                        <span
                                            v-for="tag in createBugForm.tags.slice(0, 3)"
                                            :key="'create-tag-chip-' + tag"
                                            class="px-1.5 py-0.5 rounded text-xs text-white inline-block"
                                            :style="{ backgroundColor: getTagColor(tag) }"
                                        >
                                            {{ tag }}
                                        </span>
                                        <span v-if="createBugForm.tags.length > 3" class="text-gray-400 text-xs">+{{ createBugForm.tags.length - 3 }}</span>
                                    </template>
                                    <span v-else class="text-gray-400">选择标签</span>
                                </div>
                                <span class="status-arrow-simple" :class="{ open: createTagDropdownOpen }" />
                            </button>

                            <div v-if="createTagDropdownOpen" class="absolute z-30 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-md p-3">
                                <div class="mb-2">
                                    <div class="relative">
                                        <input
                                            v-model="createTagKeyword"
                                            placeholder="搜索..."
                                            class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm"
                                        />
                                        <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                                    </div>
                                </div>
                                <div class="max-h-[220px] overflow-y-auto pr-1">
                                    <button
                                        v-for="tag in filteredCreateTagOptions"
                                        :key="'create-tag-opt-' + tag"
                                        class="w-full h-10 px-2 rounded-md flex items-center gap-2 text-left hover:bg-gray-50"
                                        @click.stop="toggleCreateTagOption(tag)"
                                    >
                                        <span class="w-5 h-5 rounded border border-gray-300 bg-white flex items-center justify-center text-[12px] text-gray-500">
                                            <span v-if="createBugForm.tags.includes(tag)">✓</span>
                                        </span>
                                        <span class="w-5 h-5 rounded-full" :style="{ backgroundColor: getTagColor(tag) }" />
                                        <span class="text-sm text-gray-700">{{ tag }}</span>
                                    </button>
                                </div>
                                <div class="mt-2 flex justify-end">
                                    <button class="h-8 px-3 text-sm bg-blue-600 text-white rounded hover:bg-blue-700" @click.stop="finishCreateTagEdit">
                                        完成
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="create-bug-field">
                        <label class="create-bug-label">关联仓库</label>
                        <vort-select v-model="createBugForm.repo" placeholder="选择仓库" allow-clear>
                            <vort-select-option v-for="item in createBugRepoOptions" :key="item" :value="item">{{ item }}</vort-select-option>
                        </vort-select>
                    </div>
                    <div class="create-bug-field">
                        <label class="create-bug-label">关联分支</label>
                        <vort-select v-model="createBugForm.branch" placeholder="选择分支" allow-clear>
                            <vort-select-option v-for="item in createBugBranchOptions" :key="item" :value="item">{{ item }}</vort-select-option>
                        </vort-select>
                    </div>
                    <div class="create-bug-field">
                        <label class="create-bug-label">实际开始时间</label>
                        <vort-date-picker
                            v-model="createBugForm.startAt"
                            value-format="YYYY-MM-DD HH:mm:ss"
                            format="YYYY-MM-DD HH:mm:ss"
                            :show-time="true"
                            placeholder="选择日期时间"
                        />
                    </div>
                    <div class="create-bug-field">
                        <label class="create-bug-label">实际结束时间</label>
                        <vort-date-picker
                            v-model="createBugForm.endAt"
                            value-format="YYYY-MM-DD HH:mm:ss"
                            format="YYYY-MM-DD HH:mm:ss"
                            :show-time="true"
                            placeholder="选择日期时间"
                        />
                    </div>
                    <div class="create-bug-field">
                        <label class="create-bug-label">备注说明</label>
                        <vort-input v-model="createBugForm.remark" placeholder="测试用备注" />
                    </div>
                </div>
            </div>
            </template>

            <template #footer>
                <div class="create-bug-footer">
                    <vort-button v-if="createBugDrawerMode === 'create'" variant="primary" @click="handleSubmitCreateBug">新建</vort-button>
                    <vort-button v-if="createBugDrawerMode === 'create'" @click="resetCreateBugForm">新建并继续</vort-button>
                    <vort-button @click="handleCancelCreateBug">取消</vort-button>
                </div>
            </template>
        </vort-drawer>
    </div>
</template>

<style scoped>
.status-arrow-simple {
    width: 6px;
    height: 6px;
    border-right: 1.5px solid #4b5563;
    border-bottom: 1.5px solid #4b5563;
    transform: rotate(45deg);
    margin-right: 1px;
    margin-top: -1px;
    transition: transform 0.15s ease;
}

.status-arrow-simple.open {
    transform: rotate(-135deg);
}

.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 6px;
    border-width: 1px;
    font-size: 13px;
    line-height: 1.2;
    font-weight: 500;
}

.status-badge-icon {
    font-size: 13px;
    line-height: 1;
}

.table-status-badge {
    gap: 3px;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 12px;
}

.table-status-badge .status-badge-icon {
    font-size: 12px;
}

.status-edit-trigger {
    height: 28px;
    max-width: 100%;
    padding: 0;
    border: none;
    background: transparent;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
}

.priority-cell-trigger {
    height: 22px;
    min-width: 58px;
    padding: 0 6px;
    border: none;
    background: transparent;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    justify-content: flex-start;
}

.priority-cell-menu {
    z-index: 1200;
    width: 124px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #fff;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
    padding: 8px;
}

.priority-cell-menu-item {
    width: 100%;
    height: 32px;
    padding: 0 6px;
    border: none;
    border-radius: 6px;
    background: transparent;
    text-align: left;
    display: flex;
    align-items: center;
    margin-bottom: 4px;
}

.priority-cell-menu-item:hover {
    background: #f8fafc;
}

.priority-cell-menu-item.is-selected {
    background: #eef4ff;
}

.priority-cell-menu-item:last-child {
    margin-bottom: 0;
}

.detail-status-trigger {
    height: 32px;
    min-width: 124px;
    padding: 0 10px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    background: #f8fafc;
    display: inline-flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    color: #334155;
}

.detail-status-trigger:hover {
    border-color: #94a3b8;
}

.detail-status-content {
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.detail-status-icon {
    width: 14px;
    text-align: center;
    font-size: 13px;
    line-height: 1;
}

.detail-status-text {
    font-size: 14px;
    line-height: 1;
}

:deep(.plan-time-picker) {
    width: 228px;
}

.plan-time-display {
    border: none;
    background: transparent;
    padding: 0;
    color: #334155;
    font-size: 14px;
    line-height: 1.4;
    white-space: nowrap;
    cursor: pointer;
}

.title-link-cell {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 0;
    border: none;
    background: transparent;
    text-align: left;
    color: #111827;
    cursor: default;
    transition: color 0.15s ease;
}

.title-link-text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.title-link-cell:hover {
    color: #60a5fa;
    cursor: pointer;
}

.work-type-icon {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    line-height: 1;
    flex-shrink: 0;
}

.work-type-icon-svg {
    width: 12px;
    height: 12px;
    display: block;
}

.work-type-icon-demand {
    background: #7c3aed;
}

.work-type-icon-task {
    background: #38bdf8;
}

.work-type-icon-bug {
    background: #ef4444;
}

.create-bug-drawer {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr);
    gap: 16px;
}

.create-bug-main,
.create-bug-side {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.create-bug-row {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
}

.create-bug-row-full {
    grid-template-columns: minmax(0, 1fr);
}

.create-bug-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.create-tag-trigger {
    width: 100%;
    min-height: 32px;
    padding: 4px 10px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    background: #fff;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.create-tag-trigger.active {
    border-color: #3b82f6;
    box-shadow: 0 0 0 1px #bfdbfe;
}

.create-tag-preview {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
    min-height: 20px;
}

.create-bug-label {
    font-size: 13px;
    color: #344054;
    font-weight: 500;
}

.required {
    color: #ef4444;
}

.create-bug-footer {
    display: flex;
    justify-content: flex-start;
    gap: 8px;
}

.create-bug-priority-trigger {
    width: 100%;
    height: 32px;
    padding: 0 10px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    background: #fff;
    display: flex;
    align-items: center;
    gap: 8px;
    text-align: left;
}

.create-bug-priority-trigger:hover,
.create-bug-priority-trigger.active {
    border-color: #3b82f6;
}

.create-bug-priority-menu {
    padding: 8px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #ffffff;
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
}

.create-bug-priority-option {
    width: 100%;
    height: 34px;
    padding: 0 8px;
    border: none;
    border-radius: 6px;
    background: transparent;
    display: flex;
    align-items: center;
    text-align: left;
    margin-bottom: 5px;
}

.create-bug-priority-option:last-child {
    margin-bottom: 0;
}

.create-bug-priority-option:hover {
    background: #f8fafc;
}

.create-bug-priority-option.is-selected {
    background: #eef4ff;
}

.priority-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 18px;
    padding: 0 9px;
    border-radius: 3px;
    border-width: 1px;
    font-size: 11px;
    line-height: 1;
    white-space: nowrap;
}

.create-bug-attachment {
    margin-top: 8px;
}

.create-bug-attachment-trigger {
    border: none;
    background: transparent;
    color: #64748b;
    font-size: 13px;
    line-height: 1.4;
    padding: 0;
    cursor: pointer;
}

.create-bug-attachment-trigger:hover {
    color: #334155;
}

.create-bug-attachment-list {
    margin-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.create-bug-attachment-item {
    display: flex;
    align-items: center;
    gap: 8px;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}

.create-bug-attachment-item .name {
    color: #334155;
    flex: 1;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.create-bug-attachment-item .size {
    color: #94a3b8;
}

.create-bug-attachment-item .remove {
    border: none;
    background: transparent;
    color: #ef4444;
    cursor: pointer;
    font-size: 12px;
}

.bug-detail-drawer {
    min-height: 640px;
}

.bug-detail-main {
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 14px 16px;
    overflow: auto;
}

.bug-detail-meta-top {
    display: flex;
    align-items: center;
    gap: 8px;
}

.bug-detail-no {
    color: #64748b;
    font-size: 12px;
}

.bug-detail-title {
    margin: 10px 0 4px;
    font-size: 28px;
    color: #0f172a;
    font-weight: 700;
    flex: 1;
    min-width: 0;
}

.bug-detail-sub {
    margin: 0 0 12px;
    color: #64748b;
    font-size: 12px;
}

.bug-detail-tabs {
    display: flex;
    gap: 18px;
    border-bottom: 1px solid #e5e7eb;
    margin-bottom: 12px;
}

.bug-detail-tabs button {
    border: none;
    background: transparent;
    padding: 10px 0;
    color: #64748b;
    font-size: 13px;
    cursor: pointer;
}

.bug-detail-tabs button.active {
    color: #2563eb;
    font-weight: 600;
    box-shadow: inset 0 -2px 0 #2563eb;
}

.bug-detail-top-grid {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
    gap: 16px;
    margin-bottom: 12px;
    align-items: start;
}

.bug-detail-left-col,
.bug-detail-right-col {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.bug-detail-info-item > label {
    display: block;
    color: #94a3b8;
    font-size: 12px;
    margin-bottom: 4px;
}

.bug-detail-info-item > div {
    color: #0f172a;
    font-size: 13px;
}

.bug-detail-info-item {
    min-width: 0;
}

.bug-detail-info-item-row {
    display: flex;
    align-items: center;
    gap: 10px;
}

.bug-detail-info-item-row > label {
    width: 90px;
    margin-bottom: 0;
    flex-shrink: 0;
}

.bug-detail-info-item-row > div {
    flex: 1;
    min-width: 0;
}

.bug-detail-info-assignee {
    position: relative;
    overflow: visible;
    align-items: flex-start;
}

.bug-detail-info-assignee > label {
    margin-top: 7px;
}

.detail-assignee-trigger {
    width: auto;
    min-height: 32px;
    border: none;
    border-radius: 0;
    background: transparent;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 6px;
    text-align: left;
}

.detail-assignee-trigger.active,
.detail-assignee-trigger:hover {
    border-color: transparent;
}

.detail-assignee-selected {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    min-height: 22px;
}

.detail-assignee-split {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
}

.detail-assignee-owner {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    flex: 1;
}

.detail-assignee-owner-name {
    color: #0f172a;
    font-size: 14px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.detail-assignee-separator {
    color: #64748b;
    font-size: 14px;
    line-height: 1;
}

.detail-assignee-collaborators {
    display: flex;
    align-items: center;
    gap: 4px;
    min-width: 0;
}

.detail-collab-stack .detail-assignee-avatar {
    margin-left: -5px;
    border: 2px solid #fff;
}

.detail-collab-stack .detail-assignee-avatar:first-child {
    margin-left: 0;
}

.detail-assignee-add {
    background: #2563eb;
    color: #fff;
    font-weight: 700;
}

.create-assignee-wrapper {
    width: 100%;
}

.create-assignee-trigger {
    width: 100%;
    min-height: 36px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    background: #fff;
    padding: 5px 10px;
}

.create-assignee-trigger.active,
.create-assignee-trigger:hover {
    border-color: #93c5fd;
}

.create-assignee-dropdown {
    left: 0;
    width: 100%;
    min-width: 420px;
}

.detail-assignee-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 2px 6px;
    border-radius: 999px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    max-width: 220px;
}

.detail-assignee-avatar {
    width: 20px;
    height: 20px;
    border-radius: 999px;
    color: #fff;
    font-size: 11px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.detail-role-tag {
    font-size: 11px;
    line-height: 1;
    padding: 3px 6px;
    border-radius: 5px;
    border: 1px solid #dbeafe;
    color: #2563eb;
    background: #eff6ff;
}

.detail-role-tag.collab {
    border-color: #bbf7d0;
    color: #16a34a;
    background: #f0fdf4;
}

.detail-assignee-dropdown {
    position: absolute;
    z-index: 30;
    margin-top: 6px;
    left: 100px;
    width: min(460px, calc(100% - 100px));
    min-width: 380px;
    max-width: calc(100vw - 120px);
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    box-shadow: 0 12px 30px rgba(15, 23, 42, 0.12);
    padding: 12px;
}

.detail-assignee-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    gap: 10px;
}

.detail-assignee-row:hover {
    background: #f8fafc;
}

.detail-assignee-row-left {
    display: flex;
    align-items: center;
    gap: 8px;
}

.detail-assignee-row-actions {
    display: flex;
    align-items: center;
    gap: 6px;
}

.detail-role-btn {
    border: 1px solid #dbeafe;
    color: #2563eb;
    background: #f8fbff;
    font-size: 12px;
    border-radius: 6px;
    padding: 2px 8px;
}

.detail-role-btn.active {
    border-color: #3b82f6;
    background: #eff6ff;
    font-weight: 600;
}

.detail-role-btn.collab {
    border-color: #bbf7d0;
    color: #16a34a;
    background: #f0fdf4;
}

.detail-role-btn.collab.active {
    border-color: #22c55e;
    font-weight: 600;
}

.bug-detail-desc-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}

.bug-detail-desc h4 {
    margin: 0;
    color: #334155;
    font-size: 13px;
}

.bug-detail-desc-edit-btn {
    border: none;
    background: transparent;
    color: #94a3b8;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}

.bug-detail-desc-edit-btn:hover {
    color: #64748b;
}

.bug-detail-desc-content {
    color: #334155;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
}

.bug-detail-desc-actions {
    margin-top: 10px;
    display: flex;
    gap: 8px;
}

.bug-detail-bottom-panel {
    margin-top: 14px;
    border-top: 1px solid #e5e7eb;
    padding-top: 12px;
}

.bug-detail-bottom-tabs {
    display: flex;
    gap: 18px;
    border-bottom: 1px solid #e5e7eb;
    margin-bottom: 12px;
}

.bug-detail-bottom-tabs button {
    border: none;
    background: transparent;
    padding: 8px 0;
    color: #64748b;
    font-size: 14px;
    cursor: pointer;
}

.bug-detail-bottom-tabs button.active {
    color: #2563eb;
    font-weight: 600;
    box-shadow: inset 0 -2px 0 #2563eb;
}

.bug-detail-bottom-tabs .count {
    margin-left: 4px;
    color: #94a3b8;
}

.bug-detail-comment-list,
.bug-detail-log-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
}

.bug-detail-comment-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid #f1f5f9;
}

.bug-detail-comment-avatar {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #3b82f6;
    color: #fff;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    flex-shrink: 0;
}

.bug-detail-comment-main {
    flex: 1;
    min-width: 0;
}

.bug-detail-comment-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}

.bug-detail-comment-meta .author {
    color: #334155;
    font-weight: 600;
    font-size: 13px;
}

.bug-detail-comment-meta .time {
    color: #94a3b8;
    font-size: 12px;
}

.bug-detail-comment-content {
    color: #334155;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
}

.bug-detail-log-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    border-bottom: 1px solid #f1f5f9;
    color: #334155;
    font-size: 13px;
}

.bug-detail-log-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #94a3b8;
    display: inline-block;
}

.bug-detail-log-item .actor {
    color: #334155;
    font-weight: 600;
}

.bug-detail-log-item .action {
    color: #475569;
}

.bug-detail-log-item .time {
    color: #94a3b8;
    margin-left: auto;
    white-space: nowrap;
}

.bug-detail-empty {
    color: #94a3b8;
    font-size: 13px;
}
</style>

