<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { ProTable, type ProTableColumn, type ProTableRequestParams, type ProTableResponse } from "@/components/vort-biz/pro-table";

type Priority = "urgent" | "high" | "medium" | "low" | "none";
type Status = "待确认" | "修复中" | "已修复" | "延期处理" | "设计如此" | "再次打开" | "无法复现" | "已关闭" | "暂时搁置";
type WorkType = "缺陷" | "需求" | "任务";

type RowItem = {
    workNo: string;
    title: string;
    priority: Priority;
    tags: string[];
    status: Status;
    createdAt: string;
    collaborators: string[];
    type: WorkType;
    planTime: string;
    owner: string;
    creator: string;
};

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
const totalCount = ref(0);

const ownerGroups = [
    { label: "项目成员", members: ["代志祥", "陈艳", "陈曦", "祝璞", "刘洋", "甘洋", "邱锐", "熊纲强"] },
    { label: "企业成员", members: ["apollo_Xuuu", "曾春红", "superdargon", "邱锐", "熊纲强"] },
    { label: "离职人员", members: ["金杜森", "熊军", "杨旭"] }
] as const;
const statusFilterOptions = [
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
const statusIconMap: Record<Status, string> = {
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
    暂时搁置: "bg-gray-100 text-gray-500 border-gray-200"
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
    return `${month}月${day}号 ${hh}:${mm}`;
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
        const plan = new Date(Date.now() + (i % 9) * 1000 * 60 * 60 * 12);
        const ownerName = owners[i % owners.length]!;
        const collab = [owners[(i + 1) % owners.length]!, owners[(i + 2) % owners.length]!];

        list.push({
            workNo: toWorkNo(i),
            title: `【${types[i % types.length]}】示例工作项标题 ${i}，用于对齐 Gitee 风格列表展示`,
            priority: priorities[i % priorities.length]!,
            tags: [tagPool[i % tagPool.length]!, tagPool[(i + 3) % tagPool.length]!],
            status: statuses[i % statuses.length]!,
            createdAt: formatCnTime(created),
            collaborators: collab,
            type: types[i % types.length]!,
            planTime: formatCnTime(plan),
            owner: i % 10 === 0 ? "未指派" : ownerName,
            creator: creators[i % creators.length]!
        });
    }
    return list;
};

const allData = buildDataset();

const columns = computed<ProTableColumn<RowItem>[]>(() => [
    { title: "工作编号", dataIndex: "workNo", width: 130, sorter: true, align: "left", fixed: "left" },
    { title: "标题", dataIndex: "title", width: 380, ellipsis: true, align: "left", fixed: "left" },
    { title: "优先级", dataIndex: "priority", width: 120, slot: "priority", align: "left" },
    { title: "标签", dataIndex: "tags", width: 180, slot: "tags", align: "left" },
    { title: "状态", dataIndex: "status", width: 120, slot: "status", align: "left" },
    { title: "创建时间", dataIndex: "createdAt", width: 150, sorter: true, align: "left" },
    { title: "协作者", dataIndex: "collaborators", width: 140, slot: "collaborators", align: "left" },
    { title: "工作项类型", dataIndex: "type", width: 120, sorter: true, align: "left" },
    { title: "计划时间", dataIndex: "planTime", width: 150, sorter: true, align: "left", slot: "planTime" },
    { title: "负责人", dataIndex: "owner", width: 120, sorter: true, align: "left" },
    { title: "创建人", dataIndex: "creator", width: 120, sorter: true, align: "left" }
]);

const request = async (params: ProTableRequestParams): Promise<ProTableResponse<RowItem>> => {
    await new Promise((r) => setTimeout(r, 180));
    const kw = String(params.keyword ?? "").trim().toLowerCase();
    const ownerValue = String(params.owner ?? "").trim();
    const typeValue = String(params.type ?? "").trim();
    const statusValue = String(params.status ?? "").trim();

    let list = allData.slice();
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
        list.sort((a: any, b: any) => (a[sortField] > b[sortField] ? dir : -dir));
    }

    const total = list.length;
    totalCount.value = total;
    const current = Number(params.current || 1);
    const pageSize = Number(params.pageSize || 10);
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
    type: type.value,
    status: status.value
}));

const onReset = () => {
    keyword.value = "";
    owner.value = "";
    type.value = "";
    status.value = "";
    tableRef.value?.refresh?.();
};

const getAvatarText = (name: string): string => name.slice(0, 1);

const getRowPriority = (record: RowItem, text?: Priority): Priority => {
    return priorityModel[record.workNo] || text || record.priority;
};

const togglePriorityMenu = (workNo: string) => {
    openPriorityFor.value = openPriorityFor.value === workNo ? null : workNo;
};

const selectPriority = (workNo: string, value: Priority) => {
    priorityModel[workNo] = value;
    openPriorityFor.value = null;
};

const onGlobalClick = () => {
    openPriorityFor.value = null;
    ownerDropdownOpen.value = false;
    typeDropdownOpen.value = false;
    statusDropdownOpen.value = false;
};

const filteredStatusOptions = computed(() => {
    const kw = statusKeyword.value.trim();
    if (!kw) return statusFilterOptions;
    return statusFilterOptions.filter((x) => x.label.includes(kw));
});

const selectStatus = (value: string) => {
    status.value = value;
    statusDropdownOpen.value = false;
};

const filteredOwnerGroups = computed(() => {
    const kw = ownerKeyword.value.trim();
    if (!kw) return ownerGroups;
    return ownerGroups
        .map((g) => ({
            ...g,
            members: g.members.filter((m) => m.includes(kw))
        }))
        .filter((g) => g.members.length > 0);
});

const toggleOwnerGroup = (group: string) => {
    ownerGroupOpen[group] = !ownerGroupOpen[group];
};

const selectOwner = (value: string) => {
    owner.value = value;
    ownerDropdownOpen.value = false;
};

const avatarBgPalette = ["#2f80ed", "#5b8ff9", "#9b59b6", "#27ae60", "#f39c12", "#e67e22", "#16a085", "#8e44ad"];
const getAvatarBg = (name: string): string => {
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
    return avatarBgPalette[hash % avatarBgPalette.length]!;
};
const getAvatarLabel = (name: string): string => name.slice(0, 1).toUpperCase();

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
    type.value = value;
    typeDropdownOpen.value = false;
};

onMounted(() => {
    document.addEventListener("click", onGlobalClick);
});

onBeforeUnmount(() => {
    document.removeEventListener("click", onGlobalClick);
});
</script>

<template>
    <div class="p-6 space-y-4">
        <div class="bg-white rounded-xl p-4">
            <h3 class="text-base font-medium text-gray-800 mb-3">缺陷</h3>
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
                                        class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center"
                                        :style="{ backgroundColor: getAvatarBg(member) }"
                                    >
                                        {{ getAvatarLabel(member) }}
                                    </span>
                                    <span class="text-sm text-gray-700">{{ member }}</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="relative" @click.stop>
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
                                <span class="text-[14px] leading-none w-4 text-center" :class="opt.iconClass">{{ opt.icon }}</span>
                                <span class="text-sm text-gray-700">{{ opt.label }}</span>
                            </button>
                        </div>
                    </div>
                </div>
                <button class="h-8 px-4 bg-blue-600 text-white rounded hover:bg-blue-700" @click="tableRef?.refresh?.()">查询</button>
                <button class="h-8 px-4 border border-gray-300 rounded hover:bg-gray-50" @click="onReset">重置</button>
            </div>
        </div>

        <div class="bg-white rounded-xl p-4">
            <ProTable
                ref="tableRef"
                :columns="columns"
                :request="request"
                :params="queryParams"
                :pagination="{ showSizeChanger: true, showQuickJumper: true, pageSizeOptions: [10, 20, 50] }"
                :toolbar="false"
                bordered
            >
                <template #priority="{ text, record }">
                    <div class="relative inline-block text-left" @click.stop>
                        <button
                            class="h-7 px-2 text-xs rounded border leading-none"
                            :class="priorityClassMap[getRowPriority(record, text)]"
                            @click.stop="togglePriorityMenu(record.workNo)"
                        >
                            {{ priorityLabelMap[getRowPriority(record, text)] }}
                        </button>
                        <div
                            v-if="openPriorityFor === record.workNo"
                            class="absolute z-20 mt-1 w-[112px] bg-white border border-gray-200 rounded-md shadow-sm py-1"
                        >
                            <button
                                v-for="opt in priorityOptions"
                                :key="opt.value"
                                class="w-full text-left px-2 py-1 text-xs hover:bg-gray-50"
                                @click.stop="selectPriority(record.workNo, opt.value)"
                            >
                                <span class="inline-block px-1.5 py-0.5 rounded border" :class="priorityClassMap[opt.value]">
                                    {{ opt.label }}
                                </span>
                            </button>
                        </div>
                    </div>
                </template>

                <template #tags="{ text }">
                    <div class="flex items-center gap-1 flex-wrap">
                        <span v-for="tag in text" :key="tag" class="px-1.5 py-0.5 rounded text-xs bg-sky-50 text-sky-700 border border-sky-200">
                            {{ tag }}
                        </span>
                    </div>
                </template>

                <template #status="{ text }">
                    <span class="status-badge" :class="statusClassMap[text]">
                        <span class="status-badge-icon">{{ statusIconMap[text] }}</span>
                        <span>{{ text }}</span>
                    </span>
                </template>

                <template #collaborators="{ text }">
                    <div class="flex items-center">
                        <div
                            v-for="(name, idx) in text"
                            :key="name + idx"
                            class="-ml-1 first:ml-0 w-6 h-6 rounded-full border border-white bg-indigo-500 text-white text-[11px] flex items-center justify-center"
                            :title="name"
                        >
                            {{ getAvatarText(name) }}
                        </div>
                    </div>
                </template>

                <template #planTime="{ text }">
                    <span class="text-red-500">{{ text }}</span>
                </template>
            </ProTable>
        </div>
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
</style>

