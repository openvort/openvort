<script setup lang="ts">
import { computed, ref } from "vue";
import PopoverSelect from "@/components/vort-biz/popover-select/PopoverSelect.vue";
import WorkItemMemberPicker from "./WorkItemMemberPicker.vue";
import type { WorkItemType, Status, MemberOption } from "../work-item";

export interface WorkItemFiltersProps {
    keyword?: string;
    owner?: string;
    type?: WorkItemType | "";
    status?: string;
    pageTitle?: string;
    createButtonText?: string;
    totalCount?: number;
    memberOptions?: MemberOption[];
    ownerGroups?: Array<{ label: string; members: string[] }>;
    statusOptions?: Array<{ label: string; value: Status; icon: string; iconClass: string }>;
    typeOptions?: WorkItemType[];
    showTypeFilter?: boolean;
}

const props = withDefaults(defineProps<WorkItemFiltersProps>(), {
    keyword: "",
    owner: "",
    type: "",
    status: "",
    pageTitle: "缺陷",
    createButtonText: "+ 新建缺陷",
    totalCount: 0,
    memberOptions: () => [],
    ownerGroups: () => [],
    statusOptions: () => [],
    typeOptions: () => ["缺陷", "需求", "任务"],
    showTypeFilter: true
});

const emit = defineEmits<{
    "update:keyword": [value: string];
    "update:owner": [value: string];
    "update:type": [value: string];
    "update:status": [value: string];
    search: [];
    reset: [];
    create: [];
}>();

const keyword = computed({
    get: () => props.keyword,
    set: (val) => emit("update:keyword", val)
});

const owner = computed({
    get: () => props.owner,
    set: (val) => emit("update:owner", val)
});

const type = computed({
    get: () => props.type,
    set: (val) => emit("update:type", val)
});

const status = computed({
    get: () => props.status,
    set: (val: string) => emit("update:status", val)
});

const statusDisplayText = computed(() => {
    if (!status.value) return "状态";
    const opt = props.statusOptions.find(o => o.value === status.value);
    return opt?.label || status.value;
});

const ownerDropdownOpen = ref(false);
const ownerKeyword = ref("");
const typeDropdownOpen = ref(false);
const typeKeyword = ref("");
const statusDropdownOpen = ref(false);
const statusKeyword = ref("");

const filteredStatusOptions = computed(() => {
    const kw = statusKeyword.value.trim().toLowerCase();
    if (!kw) return props.statusOptions;
    return props.statusOptions.filter(opt => opt.label.toLowerCase().includes(kw));
});

const filteredTypeOptions = computed(() => {
    const kw = typeKeyword.value.trim();
    if (!kw) return props.typeOptions;
    return props.typeOptions.filter(t => t.includes(kw));
});

const selectOwner = (value: string) => {
    owner.value = value;
    ownerDropdownOpen.value = false;
    ownerKeyword.value = "";
};

const selectType = (value: WorkItemType) => {
    type.value = value;
    typeDropdownOpen.value = false;
    typeKeyword.value = "";
};

const selectStatus = (value: string) => {
    status.value = value;
    statusDropdownOpen.value = false;
    statusKeyword.value = "";
};

const onSearch = () => emit("search");
const onReset = () => emit("reset");
const onCreate = () => emit("create");
</script>

<template>
    <div class="bg-white rounded-xl p-4">
        <h3 class="text-base font-medium text-gray-800 mb-3">{{ props.pageTitle }}</h3>
        <div class="flex flex-wrap items-center gap-3 text-sm">
            <div class="text-gray-600"><span class="text-gray-900 font-medium">共{{ totalCount }}项</span></div>
            <div class="w-[180px] shrink-0">
                <VortInput v-model="keyword" placeholder="输入关键词" @keyup.enter="onSearch" />
            </div>

            <WorkItemMemberPicker
                mode="owner"
                :owner="owner"
                :groups="props.ownerGroups"
                :open="ownerDropdownOpen"
                v-model:keyword="ownerKeyword"
                :show-all-option="true"
                :show-unassigned="true"
                unassigned-value="未指派"
                :dropdown-max-height="460"
                @update:open="(open) => ownerDropdownOpen = open"
                @update:owner="selectOwner"
            >
                <template #trigger="{ open }">
                    <VortButton
                        class="h-8 min-w-[130px] px-3 border border-slate-300 rounded-md bg-white hover:border-slate-400 font-normal"
                        :class="open ? 'border-blue-500 ring-1 ring-blue-200' : ''"
                        @click.stop="ownerDropdownOpen = !ownerDropdownOpen"
                    >
                        <div class="flex items-center justify-between w-full gap-2">
                            <span class="text-sm" :class="owner ? 'text-gray-700' : 'text-gray-400'">{{ owner || "负责人" }}</span>
                            <span class="status-arrow-simple" :class="{ open }" />
                        </div>
                    </VortButton>
                </template>
            </WorkItemMemberPicker>

            <!-- Type Filter -->
            <PopoverSelect
                v-if="props.showTypeFilter"
                v-model:open="typeDropdownOpen"
                v-model:keyword="typeKeyword"
                :show-search="true"
                search-placeholder="搜索..."
                :dropdown-width="180"
                :dropdown-max-height="260"
                :bordered="false"
            >
                <template #trigger="{ open }">
                    <VortButton
                        class="h-8 min-w-[110px] px-3 border border-slate-300 rounded-md bg-white hover:border-slate-400 font-normal"
                        :class="open ? 'border-blue-500 ring-1 ring-blue-200' : ''"
                        @click.stop="typeDropdownOpen = !typeDropdownOpen"
                    >
                        <div class="flex items-center justify-between w-full gap-2">
                            <span class="text-sm" :class="type ? 'text-gray-700' : 'text-gray-400'">{{ type || "类型" }}</span>
                            <span class="status-arrow-simple" :class="{ open }" />
                        </div>
                    </VortButton>
                </template>

                <div class="p-1">
                    <VortButton
                        v-for="group in filteredTypeOptions"
                        :key="group"
                        class="w-full h-9 px-3 flex items-center justify-between text-left"
                        variant="text"
                        :class="type === group ? 'bg-slate-100' : ''"
                        @click.stop="selectType(group)"
                    >
                        <span class="text-gray-700 text-sm">{{ group }}</span>
                        <span v-if="type === group" class="text-blue-500">✓</span>
                    </VortButton>
                </div>
            </PopoverSelect>

            <!-- Status Filter -->
            <PopoverSelect
                v-model:open="statusDropdownOpen"
                v-model:keyword="statusKeyword"
                :show-search="true"
                search-placeholder="搜索..."
                :dropdown-width="240"
                :dropdown-max-height="220"
                :bordered="false"
            >
                <template #trigger="{ open }">
                    <VortButton
                        class="h-8 min-w-[130px] px-3 border border-slate-300 rounded-md bg-white hover:border-slate-400 font-normal"
                        :class="open ? 'border-blue-500 ring-1 ring-blue-200' : ''"
                        @click.stop="statusDropdownOpen = !statusDropdownOpen"
                    >
                        <div class="flex items-center justify-between w-full gap-2">
                            <span class="text-sm" :class="status ? 'text-gray-700' : 'text-gray-400'">{{ statusDisplayText }}</span>
                            <span class="status-arrow-simple" :class="{ open }" />
                        </div>
                    </VortButton>
                </template>

                <div class="p-1">
                    <div
                        class="status-filter-row"
                        :class="{ 'is-active': status === '' }"
                        @click.stop="selectStatus('')"
                    >
                        <div class="flex items-center gap-3">
                            <vort-checkbox
                                :checked="status === ''"
                                @click.stop
                                @update:checked="selectStatus('')"
                            />
                            <span class="text-sm text-gray-700 leading-5">全部</span>
                        </div>
                    </div>
                    <div
                        v-for="opt in filteredStatusOptions"
                        :key="opt.value"
                        class="status-filter-row"
                        :class="{ 'is-active': status === opt.value }"
                        @click.stop="selectStatus(opt.value)"
                    >
                        <div class="flex items-center gap-3">
                            <vort-checkbox
                                :checked="status === opt.value"
                                @click.stop
                                @update:checked="selectStatus(opt.value)"
                            />
                            <span class="text-sm text-gray-700 leading-5">{{ opt.label }}</span>
                        </div>
                    </div>
                </div>
            </PopoverSelect>

            <VortButton variant="primary" @click="onSearch">查询</VortButton>
            <VortButton @click="onReset">重置</VortButton>
            <VortButton variant="primary" class="ml-auto" @click="onCreate">{{ props.createButtonText }}</VortButton>
        </div>
    </div>
</template>

<style scoped>
.status-filter-row {
    min-height: 36px;
    padding: 6px 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.15s ease;
}

.status-filter-row:hover {
    background: rgba(0, 0, 0, 0.04);
}

.status-filter-row.is-active {
    background: #f1f5f9;
}
</style>
