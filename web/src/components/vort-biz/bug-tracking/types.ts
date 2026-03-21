// 缺陷追踪相关类型定义

export type Priority = "urgent" | "high" | "medium" | "low" | "none";
export type Status = "待确认" | "修复中" | "已修复" | "延期处理" | "设计如此" | "再次打开" | "无法复现" | "已关闭" | "暂时搁置";
export type WorkType = "缺陷" | "需求" | "任务";
export type DateRange = [string, string];

// 列表项
export interface RowItem {
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
}

// 新建表单
export interface NewBugForm {
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
}

// 详情评论
export interface DetailComment {
    id: string;
    author: string;
    createdAt: string;
    content: string;
}

// 详情日志
export interface DetailLog {
    id: string;
    actor: string;
    createdAt: string;
    action: string;
}

// 附件
export interface BugAttachment {
    id: string;
    name: string;
    size: number;
}

// 筛选参数
export interface BugFilterParams {
    page: number;
    size: number;
    keyword: string;
    owner: string;
    type: WorkType | "";
    status: Status | "";
}

// 状态选项
export interface StatusOption {
    label: string;
    value: Status;
    icon: string;
    iconClass: string;
}

// 优先级选项
export interface PriorityOption {
    label: string;
    value: Priority;
}

// 成员组
export interface MemberGroup {
    label: string;
    members: readonly string[];
}

// 常量映射
export const priorityOptions: PriorityOption[] = [
    { label: "紧急", value: "urgent" },
    { label: "高", value: "high" },
    { label: "中", value: "medium" },
    { label: "低", value: "low" },
    { label: "无优先级", value: "none" }
];

export const statusFilterOptions: StatusOption[] = [
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

export const statusIconMap: Record<Status, string> = {
    待确认: "○",
    修复中: "◔",
    已修复: "✓",
    延期处理: "▷",
    设计如此: "⌛",
    再次打开: "⚡",
    无法复现: "!",
    已关闭: "✓",
    暂时搁置: "⌛"
};

export const priorityLabelMap: Record<Priority, string> = {
    urgent: "紧急",
    high: "高",
    medium: "中",
    low: "低",
    none: "无优先级"
};

export const priorityClassMap: Record<Priority, string> = {
    urgent: "text-red-500 border-red-500 bg-red-50",
    high: "text-amber-500 border-amber-500 bg-amber-50",
    medium: "text-blue-500 border-blue-500 bg-blue-50",
    low: "text-emerald-500 border-emerald-500 bg-emerald-50",
    none: "text-gray-400 border-gray-300 bg-gray-50"
};

export const statusClassMap: Record<Status, string> = {
    待确认: "bg-gray-100 text-gray-400 border-gray-200",
    修复中: "bg-blue-50 text-blue-600 border-blue-100",
    已修复: "bg-blue-50 text-blue-600 border-blue-100",
    延期处理: "bg-sky-100 text-sky-700 border-sky-200",
    设计如此: "bg-amber-100 text-amber-600 border-amber-200",
    再次打开: "bg-red-100 text-red-600 border-red-200",
    无法复现: "bg-amber-100 text-amber-600 border-amber-200",
    已关闭: "bg-gray-100 text-gray-700 border-gray-200",
    暂时搁置: "bg-gray-100 text-gray-500 border-gray-200"
};


export const tagOptions = ["客户需求", "演示站", "运营需求", "待开会确认", "已发布", "高优先", "稳定性", "UI优化"];

export const createBugTagOptions = tagOptions;
export const createBugProjectOptions = ["VortMall", "OpenVort", "VortFlow"];
export const createBugRepoOptions = ["openvort/web", "openvort/core", "openvort/vortflow"];
export const createBugBranchOptions = ["develop", "develop-wzh", "release/1.0"];
