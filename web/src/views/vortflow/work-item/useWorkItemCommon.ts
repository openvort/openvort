import { ref } from "vue";
import { getMembers } from "@/api";
import type {
    WorkItemType,
    Priority,
    Status,
    MemberOption,
    StatusOption
} from "@/components/vort-biz/work-item/WorkItemTable.types";

const DEFAULT_OWNER_GROUPS = [
    { label: "项目成员", members: ["代志祥", "陈艳", "陈曦", "祝璞", "刘洋", "甘洋", "邱锐", "熊纲强"] },
    { label: "企业成员", members: ["apollo_Xuuu", "曾春红", "superdargon", "邱锐", "熊纲强"] },
    { label: "离职人员", members: ["金杜森", "熊军", "杨旭"] }
] as const;

const cloneDefaultOwnerGroups = (): Array<{ label: string; members: string[] }> => (
    DEFAULT_OWNER_GROUPS.map((group) => ({
        label: group.label,
        members: [...group.members]
    }))
);

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

const buildOwnerGroupsFromMembers = (members: ApiMemberRecord[]) => {
    const defaultGroups = cloneDefaultOwnerGroups();
    const defaultGroupMap = new Map(defaultGroups.map((group) => [group.label, new Set(group.members)]));
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

    const projectSeedSet = defaultGroupMap.get("项目成员") || new Set<string>();
    const enterpriseSeedSet = defaultGroupMap.get("企业成员") || new Set<string>();
    const leaverSeedSet = defaultGroupMap.get("离职人员") || new Set<string>();

    const projectMembers = dedupeNames(activeNames.filter((name) => projectSeedSet.has(name)));
    const enterpriseMembers = dedupeNames([
        ...activeNames.filter((name) => enterpriseSeedSet.has(name) && !projectSeedSet.has(name)),
        ...activeNames.filter((name) => !projectSeedSet.has(name) && !enterpriseSeedSet.has(name))
    ]);
    const leaverMembers = dedupeNames([
        ...inactiveNames,
        ...activeNames.filter((name) => leaverSeedSet.has(name))
    ]);

    return [
        { label: "项目成员", members: projectMembers },
        { label: "企业成员", members: enterpriseMembers },
        { label: "离职人员", members: leaverMembers }
    ];
};

const sharedMemberOptions = ref<MemberOption[]>([]);
const sharedOwnerGroups = ref<Array<{ label: string; members: string[] }>>(cloneDefaultOwnerGroups());
let memberOptionsLoadTask: Promise<void> | null = null;

export function useWorkItemCommon() {
    const memberOptions = sharedMemberOptions;
    const ownerGroups = sharedOwnerGroups;
    const defaultOwnerGroups = cloneDefaultOwnerGroups();

    const bugStatusFilterOptions: StatusOption[] = [
        { label: "待确认", value: "待确认", icon: "○", iconClass: "text-gray-400" },
        { label: "修复中", value: "修复中", icon: "◔", iconClass: "text-blue-500" },
        { label: "已修复", value: "已修复", icon: "✓", iconClass: "text-blue-500" },
        { label: "已关闭", value: "已关闭", icon: "✓", iconClass: "text-gray-700" },
    ];

    const demandStatusFilterOptions: StatusOption[] = [
        { label: "已取消", value: "已取消", icon: "✕", iconClass: "text-red-500" },
        { label: "意向", value: "意向", icon: "○", iconClass: "text-slate-500" },
        { label: "设计中", value: "设计中", icon: "✎", iconClass: "text-indigo-500" },
        { label: "开发中", value: "开发中", icon: "◔", iconClass: "text-blue-500" },
        { label: "测试完成", value: "测试完成", icon: "✓", iconClass: "text-violet-600" },
        { label: "已完成", value: "已完成", icon: "✓", iconClass: "text-emerald-700" },
    ];

    const taskStatusFilterOptions: StatusOption[] = [
        { label: "待办的", value: "待办的", icon: "○", iconClass: "text-slate-500" },
        { label: "进行中", value: "进行中", icon: "◔", iconClass: "text-blue-500" },
        { label: "已完成", value: "已完成", icon: "✓", iconClass: "text-emerald-700" },
        { label: "已取消", value: "已取消", icon: "✕", iconClass: "text-red-500" },
    ];

    const statusFilterOptionsByType: Record<WorkItemType, StatusOption[]> = {
        需求: demandStatusFilterOptions,
        任务: taskStatusFilterOptions,
        缺陷: bugStatusFilterOptions,
    };

    const getStatusOptionsByType = (typeValue: WorkItemType): StatusOption[] => {
        return statusFilterOptionsByType[typeValue] || bugStatusFilterOptions;
    };

    const getStatusOption = (value: Status, typeValue?: WorkItemType) => {
        const options = typeValue ? getStatusOptionsByType(typeValue) : bugStatusFilterOptions;
        return options.find((x) => x.value === value) || options[0] || bugStatusFilterOptions[0]!;
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
                const res: any = await getMembers({ search: "", role: "", page: 1, size: 100 });
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

            ownerGroups.value = cloneDefaultOwnerGroups();
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

    const mapBackendStateToStatus = (typeValue: WorkItemType, stateValue: string): Status => {
        const normalized = String(stateValue || "").toLowerCase();
        if (typeValue === "需求") {
            const map: Record<string, Status> = {
                intake: "意向", review: "意向", rejected: "已取消",
                pm_refine: "设计中", design: "设计中", breakdown: "开发中",
                dev_assign: "开发中", in_progress: "开发中", testing: "测试完成",
                bugfix: "开发中", done: "已完成",
            };
            return map[normalized] || "意向";
        }
        if (typeValue === "任务") {
            const map: Record<string, Status> = {
                todo: "待办的", in_progress: "进行中", done: "已完成",
                closed: "已取消", fixing: "进行中", resolved: "已完成", verified: "已完成",
            };
            return map[normalized] || "待办的";
        }
        const map: Record<string, Status> = {
            open: "待确认",
            confirmed: "待确认",
            fixing: "修复中",
            resolved: "已修复",
            verified: "已关闭",
            closed: "已关闭",
        };
        return map[normalized] || "待确认";
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

    const getBackendStatesByDisplayStatus = (typeValue: WorkItemType, statusValue: string): string[] | undefined => {
        const statusToStateMap: Record<WorkItemType, Partial<Record<Status, string[]>>> = {
            需求: { 已取消: ["rejected"], 意向: ["intake", "review"], 设计中: ["pm_refine", "design"], 开发中: ["breakdown", "dev_assign", "in_progress", "bugfix"], 测试完成: ["testing"], 已完成: ["done"] },
            任务: { 待办的: ["todo"], 进行中: ["in_progress"], 已完成: ["done"], 已取消: ["closed"] },
            缺陷: { 待确认: ["open", "confirmed"], 修复中: ["fixing"], 已修复: ["resolved"], 已关闭: ["verified", "closed"] },
        };
        return statusToStateMap[typeValue]?.[statusValue as Status];
    };

    return {
        memberOptions,
        ownerGroups,
        defaultOwnerGroups,
        bugStatusFilterOptions,
        demandStatusFilterOptions,
        taskStatusFilterOptions,
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
    };
}
