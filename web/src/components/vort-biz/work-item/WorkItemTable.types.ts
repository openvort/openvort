export type WorkItemType = "缺陷" | "需求" | "任务";

export type Priority = "urgent" | "high" | "medium" | "low" | "none";

export type Status =
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

export type DateRange = [string, string];

export interface ViewFilters {
    owner?: string;
    status?: string;
    parentOnly?: boolean;
    creator?: string;
    participant?: string;
}

export interface WorkItemTableProps {
    type: WorkItemType;
    pageTitle?: string;
    createButtonText?: string;
    createDrawerTitle?: string;
    detailDrawerTitle?: string;
    descriptionPlaceholder?: string;
    useApi?: boolean;
    projectId?: string;
    viewFilters?: ViewFilters;
}

export interface NewBugForm {
    title: string;
    owner: string;
    collaborators: string[];
    type: WorkItemType;
    planTime: DateRange | [];
    project: string;
    projectId?: string;
    iteration: string;
    version: string;
    parentId?: string;
    storyId?: string;
    priority: Priority | "";
    tags: string[];
    repo: string;
    branch: string;
    startAt: string;
    endAt: string;
    remark: string;
    description: string;
}

export interface RowItem {
    backendId?: string;
    workNo: string;
    title: string;
    parentId?: string;
    parentTitle?: string;
    childrenCount?: number;
    isChild?: boolean;
    priority: Priority;
    tags: string[];
    status: Status;
    createdAt: string;
    collaborators: string[];
    type: WorkItemType;
    planTime: DateRange;
    description: string;
    ownerId?: string;
    owner: string;
    creator: string;
    projectId?: string;
    projectName?: string;
    children?: RowItem[];
}

export interface DetailComment {
    id: string;
    author: string;
    createdAt: string;
    content: string;
}

export interface DetailLog {
    id: string;
    actor: string;
    createdAt: string;
    action: string;
}

export interface CreateBugAttachment {
    id: string;
    name: string;
    size: number;
}

export interface MemberOption {
    id: string;
    name: string;
    avatarUrl: string;
}

export interface StatusOption {
    label: string;
    value: Status;
    icon: string;
    iconClass: string;
}
