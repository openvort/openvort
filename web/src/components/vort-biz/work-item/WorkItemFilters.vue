<script setup lang="ts">
import { computed, ref, reactive } from "vue";
import { Popover } from "@/components/vort";
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

const ownerGroupOpen = reactive<Record<string, boolean>>({});

const filteredOwnerGroups = computed(() => {
    const kw = ownerKeyword.value.trim();
    if (!kw) return props.ownerGroups;
    return props.ownerGroups
        .map(g => ({ ...g, members: g.members.filter(m => m.includes(kw)) }))
        .filter(g => g.members.length > 0);
});

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

const toggleOwnerGroup = (group: string) => {
    ownerGroupOpen[group] = !ownerGroupOpen[group];
};

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

const avatarBgPalette = ["#2f80ed", "#5b8ff9", "#9b59b6", "#27ae60", "#f39c12", "#e67e22", "#16a085", "#8e44ad"];
const getAvatarBg = (name: string): string => {
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return avatarBgPalette[Math.abs(hash) % avatarBgPalette.length] || avatarBgPalette[0]!;
};
const getAvatarLabel = (name: string) => name.slice(0, 1).toUpperCase();
const getMemberAvatarUrl = (name: string): string => props.memberOptions.find(m => m.name === name)?.avatarUrl || "";

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

            <!-- Owner Filter -->
            <Popover v-model:open="ownerDropdownOpen" trigger="click" placement="bottomLeft" :arrow="false">
                <VortButton
                    class="h-8 min-w-[130px] px-3 border border-slate-300 rounded-md bg-white hover:border-slate-400 font-normal"
                    :class="ownerDropdownOpen ? 'border-blue-500 ring-1 ring-blue-200' : ''"
                >
                    <div class="flex items-center justify-between w-full gap-2">
                        <span class="text-sm text-gray-700">{{ owner || "负责人" }}</span>
                        <span class="status-arrow-simple" :class="{ open: ownerDropdownOpen }" />
                    </div>
                </VortButton>
                <template #content>
                    <div class="w-[260px]">
                        <div class="mb-2">
                            <VortInput v-model="ownerKeyword" placeholder="搜索..." class="w-full" />
                        </div>
                        <div class="max-h-[460px] overflow-y-auto pr-1">
                            <div
                                class="w-full px-2 py-1 rounded-md hover:bg-gray-50 cursor-pointer"
                                :class="owner === '' ? 'bg-slate-100' : ''"
                                @click.stop="selectOwner('')"
                            >
                                <div class="flex items-center gap-3">
                                    <vort-checkbox
                                        :checked="owner === ''"
                                        style="min-height: 24px;"
                                        @click.stop
                                        @update:checked="selectOwner('')"
                                    />
                                    <span class="text-sm text-gray-700 leading-5">全部</span>
                                </div>
                            </div>
                            <div
                                class="w-full px-2 py-1 rounded-md hover:bg-gray-50 cursor-pointer"
                                :class="owner === '未指派' ? 'bg-slate-100' : ''"
                                @click.stop="selectOwner('未指派')"
                            >
                                <div class="flex items-center gap-3">
                                    <vort-checkbox
                                        :checked="owner === '未指派'"
                                        style="min-height: 24px;"
                                        @click.stop
                                        @update:checked="selectOwner('未指派')"
                                    />
                                    <span class="text-sm text-gray-700 leading-5">未指派</span>
                                </div>
                            </div>

                            <div v-for="group in filteredOwnerGroups" :key="group.label">
                                <div
                                    class="w-full h-10 px-2 bg-slate-50 flex items-center justify-between cursor-pointer"
                                    @click.stop="toggleOwnerGroup(group.label)"
                                >
                                    <span class="text-gray-700 text-sm">{{ group.label }}（{{ group.members.length }}）</span>
                                    <span class="status-arrow-simple" :class="{ open: ownerGroupOpen[group.label] }" />
                                </div>
                                <div
                                    v-for="member in (ownerGroupOpen[group.label] ? group.members : [])"
                                    :key="group.label + member"
                                    class="w-full px-2 py-1 rounded-md hover:bg-gray-50 cursor-pointer"
                                    :class="owner === member ? 'bg-slate-100' : ''"
                                    @click.stop="selectOwner(member)"
                                >
                                    <div class="flex items-center gap-3">
                                        <vort-checkbox
                                            :checked="owner === member"
                                            style="min-height: 24px;"
                                            @click.stop
                                            @update:checked="selectOwner(member)"
                                        />
                                        <span
                                            class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center overflow-hidden flex-shrink-0"
                                            :style="{ backgroundColor: getAvatarBg(member) }"
                                        >
                                            <img v-if="getMemberAvatarUrl(member)" :src="getMemberAvatarUrl(member)" class="w-full h-full object-cover" />
                                            <template v-else>{{ getAvatarLabel(member) }}</template>
                                        </span>
                                        <span class="text-sm text-gray-700 leading-5">{{ member }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </template>
            </Popover>

            <!-- Type Filter -->
            <Popover v-if="props.showTypeFilter" v-model:open="typeDropdownOpen" trigger="click" placement="bottomLeft" :arrow="false">
                <VortButton
                    class="h-8 min-w-[110px] px-3 border border-slate-300 rounded-md bg-white hover:border-slate-400 font-normal"
                    :class="typeDropdownOpen ? 'border-blue-500 ring-1 ring-blue-200' : ''"
                >
                    <div class="flex items-center justify-between w-full gap-2">
                        <span class="text-sm text-gray-700">{{ type || "类型" }}</span>
                        <span class="status-arrow-simple" :class="{ open: typeDropdownOpen }" />
                    </div>
                </VortButton>
                <template #content>
                    <div class="w-[180px]">
                        <div class="mb-2">
                            <VortInput v-model="typeKeyword" placeholder="搜索..." class="w-full" size="small" />
                        </div>
                        <div class="max-h-[260px] overflow-y-auto pr-1">
                            <div v-for="group in filteredTypeOptions" :key="group">
                                <VortButton
                                    class="w-full h-10 px-3 bg-slate-100 flex items-center justify-between text-left"
                                    variant="text"
                                    @click.stop="selectType(group)"
                                >
                                    <span class="text-gray-700 text-sm">{{ group }}</span>
                                    <span v-if="type === group" class="text-blue-500">✓</span>
                                </VortButton>
                            </div>
                        </div>
                    </div>
                </template>
            </Popover>

            <!-- Status Filter -->
            <Popover v-model:open="statusDropdownOpen" trigger="click" placement="bottomLeft" :arrow="false">
                <VortButton
                    class="h-8 min-w-[130px] px-3 border border-slate-300 rounded-md bg-white hover:border-slate-400 font-normal"
                    :class="statusDropdownOpen ? 'border-blue-500 ring-1 ring-blue-200' : ''"
                >
                    <div class="flex items-center justify-between w-full gap-2">
                        <span class="text-sm text-gray-700">{{ statusDisplayText }}</span>
                        <span class="status-arrow-simple" :class="{ open: statusDropdownOpen }" />
                    </div>
                </VortButton>
                <template #content>
                    <div class="w-[240px]" @click.stop>
                        <div class="mb-2">
                            <VortInput v-model="statusKeyword" placeholder="搜索..." class="w-full" size="small" />
                        </div>
                        <div class="max-h-[220px] overflow-y-auto pr-1">
                            <div
                                class="w-full px-2 py-1 rounded-md hover:bg-gray-50 cursor-pointer"
                                :class="status === '' ? 'bg-slate-100' : ''"
                                @click.stop="selectStatus('')"
                            >
                                <div class="flex items-center gap-3">
                                    <vort-checkbox
                                        :checked="status === ''"
                                        style="min-height: 24px;"
                                        @click.stop
                                        @update:checked="selectStatus('')"
                                    />
                                    <span class="text-sm text-gray-700 leading-5">全部</span>
                                </div>
                            </div>
                            <div
                                v-for="opt in filteredStatusOptions"
                                :key="opt.value"
                                class="w-full px-2 py-1 rounded-md hover:bg-gray-50 cursor-pointer"
                                :class="status === opt.value ? 'bg-slate-100' : ''"
                                @click.stop="selectStatus(opt.value)"
                            >
                                <div class="flex items-center gap-3">
                                    <vort-checkbox
                                        :checked="status === opt.value"
                                        style="min-height: 24px;"
                                        @click.stop
                                        @update:checked="selectStatus(opt.value)"
                                    />
                                    <span class="text-sm text-gray-700 leading-5">{{ opt.label }}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </template>
            </Popover>

            <VortButton variant="primary" @click="onSearch">查询</VortButton>
            <VortButton @click="onReset">重置</VortButton>
            <VortButton variant="primary" class="ml-auto" @click="onCreate">{{ props.createButtonText }}</VortButton>
        </div>
    </div>
</template>
