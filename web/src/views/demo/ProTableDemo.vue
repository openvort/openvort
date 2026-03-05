<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { ProTable, type ProTableColumn, type ProTableRequestParams, type ProTableResponse } from "@/components/vort-biz/pro-table";

type Priority = "urgent" | "high" | "medium" | "low";
type Status = "todo" | "doing" | "review" | "done";
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
const type = ref("");
const status = ref("");
const totalCount = ref(0);

const ownerOptions = ["全部", "张三", "李四", "王五", "赵六", "钱七", "孙八"];
const typeOptions = ["全部", "缺陷", "需求", "任务"];
const statusOptions = ["全部", "待处理", "进行中", "评审中", "已完成"];
const priorityOptions: Array<{ label: string; value: Priority }> = [
    { label: "紧急", value: "urgent" },
    { label: "高", value: "high" },
    { label: "中", value: "medium" },
    { label: "低", value: "low" }
];

const statusLabelMap: Record<Status, string> = {
    todo: "待处理",
    doing: "进行中",
    review: "评审中",
    done: "已完成"
};

const statusClassMap: Record<Status, string> = {
    todo: "bg-orange-50 text-orange-700 border-orange-200",
    doing: "bg-blue-50 text-blue-700 border-blue-200",
    review: "bg-purple-50 text-purple-700 border-purple-200",
    done: "bg-green-50 text-green-700 border-green-200"
};

const priorityLabelMap: Record<Priority, string> = {
    urgent: "紧急",
    high: "高",
    medium: "中",
    low: "低"
};

const priorityModel = reactive<Record<string, Priority>>({});

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
    const statuses: Status[] = ["todo", "doing", "review", "done"];
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
            owner: ownerName,
            creator: creators[i % creators.length]!
        });
    }
    return list;
};

const allData = buildDataset();

const columns = computed<ProTableColumn<RowItem>[]>(() => [
    { title: "工作编号", dataIndex: "workNo", width: 130, sorter: true, align: "left" },
    { title: "标题", dataIndex: "title", width: 380, ellipsis: true, align: "left" },
    { title: "优先级", dataIndex: "priority", width: 120, slot: "priority", align: "center" },
    { title: "标签", dataIndex: "tags", width: 180, slot: "tags", align: "left" },
    { title: "状态", dataIndex: "status", width: 120, slot: "status", align: "center" },
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
        const map: Record<string, Status> = { 待处理: "todo", 进行中: "doing", 评审中: "review", 已完成: "done" };
        const target = map[statusValue];
        if (target) {
            list = list.filter((x) => x.status === target);
        }
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
</script>

<template>
    <div class="p-6 space-y-4">
        <div class="bg-white rounded-xl p-4">
            <h3 class="text-base font-medium text-gray-800 mb-3">缺陷</h3>
            <div class="flex flex-wrap items-center gap-3 text-sm">
                <div class="text-gray-600">项目总数 <span class="text-gray-900 font-medium">共{{ totalCount || allData.length }}项</span></div>
                <input v-model="keyword" placeholder="输入关键词" class="h-8 px-3 border border-gray-300 rounded w-[180px]" />
                <select v-model="owner" class="h-8 px-2 border border-gray-300 rounded w-[120px]">
                    <option value="">负责人</option>
                    <option v-for="opt in ownerOptions.filter((x) => x !== '全部')" :key="opt" :value="opt">{{ opt }}</option>
                </select>
                <select v-model="type" class="h-8 px-2 border border-gray-300 rounded w-[110px]">
                    <option value="">类型</option>
                    <option v-for="opt in typeOptions.filter((x) => x !== '全部')" :key="opt" :value="opt">{{ opt }}</option>
                </select>
                <select v-model="status" class="h-8 px-2 border border-gray-300 rounded w-[110px]">
                    <option value="">状态</option>
                    <option v-for="opt in statusOptions.filter((x) => x !== '全部')" :key="opt" :value="opt">{{ opt }}</option>
                </select>
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
                :row-selection="{ type: 'checkbox', columnWidth: 42 }"
                :pagination="{ showSizeChanger: true, showQuickJumper: true, pageSizeOptions: [10, 20, 50] }"
                :toolbar="false"
                bordered
            >
                <template #priority="{ text, record }">
                    <select
                        :value="priorityModel[record.workNo] || text"
                        class="h-7 px-2 text-xs border border-gray-300 rounded bg-white"
                        @change="(e) => { priorityModel[record.workNo] = (e.target as HTMLSelectElement).value as Priority; }"
                    >
                        <option v-for="opt in priorityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                    </select>
                </template>

                <template #tags="{ text }">
                    <div class="flex items-center gap-1 flex-wrap">
                        <span v-for="tag in text" :key="tag" class="px-1.5 py-0.5 rounded text-xs bg-sky-50 text-sky-700 border border-sky-200">
                            {{ tag }}
                        </span>
                    </div>
                </template>

                <template #status="{ text }">
                    <span class="inline-flex items-center px-2 py-0.5 rounded border text-xs" :class="statusClassMap[text]">
                        {{ statusLabelMap[text] }}
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

