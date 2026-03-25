import { ref } from "vue";
import { getMembersSimple, getVortflowStatuses } from "@/api";
import { resolveIconKey } from "@/components/vort-biz/work-item/statusIcons";
import type {
    WorkItemType,
    Priority,
    Status,
    MemberOption,
    StatusOption
} from "@/components/vort-biz/work-item/WorkItemTable.types";

export type OwnerGroup = { label: string; members: string[] };

interface ApiMemberRecord {
    id?: string;
    name?: string;
    avatar_url?: string;
    avatar?: string;
    status?: string;
}

const normalizeMemberName = (value: unknown): string => String(value || "").trim();

const dedupeNames = (members: string[]): string[] => {
    const result: string[] = [];
    const seen = new Set<string>();
    for (const member of members) {
        const normalized = normalizeMemberName(member);
        if (!normalized || seen.has(normalized)) continue;
        seen.add(normalized);
        result.push(normalized);
    }
    return result;
};

const buildOwnerGroupsFromMembers = (members: ApiMemberRecord[]): OwnerGroup[] => {
    const activeNames: string[] = [];
    const inactiveNames: string[] = [];

    for (const item of members) {
        const name = normalizeMemberName(item?.name);
        if (!name) continue;

        if (String(item?.status || "").toLowerCase() === "inactive") {
            inactiveNames.push(name);
        } else {
            activeNames.push(name);
        }
    }

    const groups: OwnerGroup[] = [];
    if (activeNames.length > 0) {
        groups.push({ label: "企业成员", members: dedupeNames(activeNames) });
    }
    if (inactiveNames.length > 0) {
        groups.push({ label: "离职人员", members: dedupeNames(inactiveNames) });
    }
    return groups;
};

const sharedMemberOptions = ref<MemberOption[]>([]);
const sharedOwnerGroups = ref<OwnerGroup[]>([]);
let memberOptionsLoadTask: Promise<void> | null = null;

interface ApiStatusItem {
    name: string;
    icon: string;
    icon_color: string;
    command: string;
    work_item_types: string[];
}

const sharedApiStatuses = ref<ApiStatusItem[]>([]);
let statusLoadTask: Promise<void> | null = null;

const HEX_TO_TW: Record<string, string> = {
    "#64748b": "text-gray-500", "#ef4444": "text-red-500", "#6366f1": "text-indigo-500",
    "#3b82f6": "text-blue-500", "#22c55e": "text-emerald-500", "#7c3aed": "text-violet-600",
    "#f59e0b": "text-amber-500", "#0284c7": "text-sky-600",
};

const toIconClass = (hex: string): string => HEX_TO_TW[hex] || "text-gray-500";
const toLucideIcon = (raw: string): string => resolveIconKey(raw) || "circle";

const buildOptionsForType = (type: string): StatusOption[] =>
    sharedApiStatuses.value
        .filter((s) => s.work_item_types.includes(type) && s.command)
        .map((s) => ({
            label: s.name,
            value: s.name,
            icon: toLucideIcon(s.icon),
            iconClass: toIconClass(s.icon_color),
            iconColor: s.icon_color,
        }));

const buildStateToNameMap = (type: string): Record<string, string> => {
    const map: Record<string, string> = {};
    for (const s of sharedApiStatuses.value) {
        if (!s.work_item_types.includes(type) || !s.command) continue;
        for (const state of s.command.split(",")) {
            const key = state.trim();
            if (key && !map[key]) map[key] = s.name;
        }
    }
    return map;
};

const buildNameToStatesMap = (type: string): Record<string, string[]> => {
    const map: Record<string, string[]> = {};
    for (const s of sharedApiStatuses.value) {
        if (!s.work_item_types.includes(type) || !s.command) continue;
        map[s.name] = s.command.split(",").map((x) => x.trim()).filter(Boolean);
    }
    return map;
};

const FALLBACK_BUG: StatusOption[] = [
    { label: "待确认", value: "待确认", icon: "circle", iconClass: "text-gray-500" },
    { label: "修复中", value: "修复中", icon: "circle-dot", iconClass: "text-blue-500" },
    { label: "已修复", value: "已修复", icon: "check", iconClass: "text-blue-500" },
    { label: "已关闭", value: "已关闭", icon: "check", iconClass: "text-gray-500" },
];
const FALLBACK_DEMAND: StatusOption[] = [
    { label: "已取消", value: "已取消", icon: "x", iconClass: "text-red-500" },
    { label: "收集中", value: "收集中", icon: "diamond", iconClass: "text-gray-400" },
    { label: "意向", value: "意向", icon: "circle", iconClass: "text-gray-500" },
    { label: "设计中", value: "设计中", icon: "pencil", iconClass: "text-indigo-500" },
    { label: "开发中", value: "开发中", icon: "circle-dot", iconClass: "text-blue-500" },
    { label: "测试完成", value: "测试完成", icon: "check", iconClass: "text-violet-600" },
    { label: "已完成", value: "已完成", icon: "circle-check", iconClass: "text-emerald-500" },
];
const FALLBACK_TASK: StatusOption[] = [
    { label: "待办的", value: "待办的", icon: "circle", iconClass: "text-gray-500" },
    { label: "进行中", value: "进行中", icon: "circle-dot", iconClass: "text-blue-500" },
    { label: "已完成", value: "已完成", icon: "circle-check", iconClass: "text-emerald-500" },
    { label: "已取消", value: "已取消", icon: "x", iconClass: "text-red-500" },
];
const FALLBACK_MAP: Record<WorkItemType, StatusOption[]> = {
    缺陷: FALLBACK_BUG, 需求: FALLBACK_DEMAND, 任务: FALLBACK_TASK,
};

export function useWorkItemCommon() {
    const memberOptions = sharedMemberOptions;
    const ownerGroups = sharedOwnerGroups;

    const bugStatusFilterOptions = FALLBACK_BUG;
    const demandStatusFilterOptions = FALLBACK_DEMAND;
    const taskStatusFilterOptions = FALLBACK_TASK;

    const getStatusOptionsByType = (typeValue: WorkItemType): StatusOption[] => {
        const dynamic = buildOptionsForType(typeValue);
        return dynamic.length ? dynamic : (FALLBACK_MAP[typeValue] || FALLBACK_BUG);
    };

    const getStatusOption = (value: Status, typeValue?: WorkItemType) => {
        const options = typeValue ? getStatusOptionsByType(typeValue) : getStatusOptionsByType("缺陷");
        return options.find((x) => x.value === value) || options[0] || FALLBACK_BUG[0]!;
    };

    const loadStatusOptions = async () => {
        if (sharedApiStatuses.value.length > 0) return;
        if (statusLoadTask) return statusLoadTask;
        statusLoadTask = (async () => {
            try {
                const res: any = await getVortflowStatuses();
                const items = ((res?.items || []) as any[]).map((s: any): ApiStatusItem => ({
                    name: String(s.name || ""),
                    icon: String(s.icon || "○"),
                    icon_color: String(s.icon_color || "#64748b"),
                    command: String(s.command || ""),
                    work_item_types: Array.isArray(s.work_item_types) ? s.work_item_types : [],
                }));
                if (items.length) sharedApiStatuses.value = items;
            } catch { /* keep fallback */ } finally { statusLoadTask = null; }
        })();
        return statusLoadTask;
    };

    const priorityOptions: Array<{ label: string; value: Priority }> = [
        { label: "紧急", value: "urgent" },
        { label: "高", value: "high" },
        { label: "中", value: "medium" },
        { label: "低", value: "low" },
        { label: "无优先级", value: "none" }
    ];

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

    const avatarBgPalette = ["#2f80ed", "#5b8ff9", "#9b59b6", "#27ae60", "#f39c12", "#e67e22", "#16a085", "#8b44ad"];
    const getAvatarBg = (name: string): string => {
        let hash = 0;
        for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
        return avatarBgPalette[hash % avatarBgPalette.length]!;
    };
    const getAvatarLabel = (name: string): string => name.slice(0, 1).toUpperCase();
    const getMemberAvatarUrl = (name: string): string => memberOptions.value.find((m) => m.name === name)?.avatarUrl || "";

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

    const loadMemberOptions = async () => {
        if (memberOptions.value.length > 0 && ownerGroups.value.length > 0) return;
        if (memberOptionsLoadTask) return memberOptionsLoadTask;

        memberOptionsLoadTask = (async () => {
            try {
                const res: any = await getMembersSimple({ search: "", page: 1, size: 100 });
                const members = Array.isArray(res?.members) ? res.members : [];
                const next: MemberOption[] = [];
                const seenIds = new Set<string>();

                for (const item of members) {
                    const id = String(item?.id || "").trim();
                    const name = String(item?.name || "").trim();
                    if (!id || !name || seenIds.has(id)) continue;
                    seenIds.add(id);
                    next.push({
                        id,
                        name,
                        avatarUrl: String(item?.avatar_url || item?.avatar || "")
                    });
                }

                if (next.length > 0) {
                    memberOptions.value = next;
                    ownerGroups.value = buildOwnerGroupsFromMembers(members);
                    return;
                }
            } catch {
                // Keep fallback groups when the organization member API is unavailable.
            } finally {
                memberOptionsLoadTask = null;
            }

            ownerGroups.value = [];
        })();

        return memberOptionsLoadTask;
    };

    const getWorkItemTypeIconClass = (type: WorkItemType): string => {
        if (type === "需求") return "work-type-icon-demand";
        if (type === "任务") return "work-type-icon-task";
        return "work-type-icon-bug";
    };

    const getWorkItemTypeIconSymbol = (type: WorkItemType): string => {
        if (type === "需求") return "≡";
        if (type === "任务") return "☑";
        return "✹";
    };

    const FALLBACK_STATE_MAP: Record<WorkItemType, Record<string, Status>> = {
        需求: {
            submitted: "收集中", intake: "意向", review: "意向", rejected: "已取消",
            pm_refine: "设计中", design: "设计中", breakdown: "开发中",
            dev_assign: "开发中", in_progress: "开发中", testing: "测试完成",
            bugfix: "开发中", done: "已完成",
        },
        任务: {
            todo: "待办的", in_progress: "进行中", done: "已完成",
            closed: "已取消", fixing: "进行中", resolved: "已完成", verified: "已完成",
        },
        缺陷: {
            open: "待确认", confirmed: "待确认", fixing: "修复中",
            resolved: "已修复", verified: "已关闭", closed: "已关闭",
        },
    };
    const FALLBACK_DEFAULT: Record<WorkItemType, Status> = {
        需求: "收集中", 任务: "待办的", 缺陷: "待确认",
    };

    const mapBackendStateToStatus = (typeValue: WorkItemType, stateValue: string): Status => {
        const normalized = String(stateValue || "").toLowerCase();
        const dynamicMap = buildStateToNameMap(typeValue);
        if (dynamicMap[normalized]) return dynamicMap[normalized] as Status;
        return (FALLBACK_STATE_MAP[typeValue]?.[normalized] || FALLBACK_DEFAULT[typeValue] || "待确认") as Status;
    };

    const mapBackendPriority = (item: any, typeValue: WorkItemType): Priority => {
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

    const toBackendPriorityLevel = (value: Priority): number => {
        const map: Record<Priority, number> = { urgent: 1, high: 2, medium: 3, low: 4, none: 4 };
        return map[value] || 4;
    };

    const toTaskEstimateHours = (value: Priority): number => {
        const map: Record<Priority, number> = { urgent: 16, high: 8, medium: 4, low: 2, none: 2 };
        return map[value] || 2;
    };

    const FALLBACK_STATUS_TO_STATES: Record<WorkItemType, Partial<Record<Status, string[]>>> = {
        需求: { 已取消: ["rejected"], 意向: ["intake", "review"], 设计中: ["pm_refine", "design"], 开发中: ["breakdown", "dev_assign", "in_progress", "bugfix"], 测试完成: ["testing"], 已完成: ["done"] },
        任务: { 待办的: ["todo"], 进行中: ["in_progress"], 已完成: ["done"], 已取消: ["closed"] },
        缺陷: { 待确认: ["open", "confirmed"], 修复中: ["fixing"], 已修复: ["resolved"], 已关闭: ["verified", "closed"] },
    };

    const getBackendStatesByDisplayStatus = (typeValue: WorkItemType, statusValue: string): string[] | undefined => {
        const dynamicMap = buildNameToStatesMap(typeValue);
        if (dynamicMap[statusValue]) return dynamicMap[statusValue];
        return FALLBACK_STATUS_TO_STATES[typeValue]?.[statusValue as Status];
    };

    return {
        memberOptions,
        ownerGroups,
        bugStatusFilterOptions,
        demandStatusFilterOptions,
        taskStatusFilterOptions,
        getStatusOptionsByType,
        getStatusOption,
        loadStatusOptions,
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
    };
}
