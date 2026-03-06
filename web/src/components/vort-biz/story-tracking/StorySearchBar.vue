<script setup lang="ts">
import { STATE_OPTIONS, PRIORITY_OPTIONS, type Project } from "./useStory";

interface FilterParams {
    keyword: string;
    project_id: string;
    state: string;
    priority: string;
}

defineProps<{
    filterParams: FilterParams;
    projects: Project[];
    loading?: boolean;
}>();

const emit = defineEmits<{
    search: [];
    reset: [];
    add: [];
}>();
</script>

<template>
    <div class="bg-white rounded-xl p-6">
        <div class="flex items-center justify-between mb-4">
            <h3 class="text-base font-medium text-gray-800">需求列表</h3>
            <vort-button variant="primary" :loading="loading" @click="emit('add')">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="mr-1">
                    <path d="M5 12h14"/><path d="M12 5v14"/>
                </svg>
                新增需求
            </vort-button>
        </div>
        <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4 flex-wrap">
            <div class="flex items-center gap-2 w-full sm:w-auto">
                <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                <vort-input-search
                    v-model="filterParams.keyword"
                    placeholder="搜索需求..."
                    allow-clear
                    class="flex-1 sm:w-[200px]"
                    @search="emit('search')"
                    @keyup.enter="emit('search')"
                />
            </div>
            <div class="flex items-center gap-2 w-full sm:w-auto">
                <span class="text-sm text-gray-500 whitespace-nowrap">项目</span>
                <vort-select
                    v-model="filterParams.project_id"
                    placeholder="全部"
                    allow-clear
                    class="flex-1 sm:w-[140px]"
                    @change="emit('search')"
                >
                    <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                </vort-select>
            </div>
            <div class="flex items-center gap-2 w-full sm:w-auto">
                <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                <vort-select
                    v-model="filterParams.state"
                    placeholder="全部"
                    allow-clear
                    class="flex-1 sm:w-[120px]"
                    @change="emit('search')"
                >
                    <vort-select-option v-for="opt in STATE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                </vort-select>
            </div>
            <div class="flex items-center gap-2 w-full sm:w-auto">
                <span class="text-sm text-gray-500 whitespace-nowrap">优先级</span>
                <vort-select
                    v-model="filterParams.priority"
                    placeholder="全部"
                    allow-clear
                    class="flex-1 sm:w-[100px]"
                    @change="emit('search')"
                >
                    <vort-select-option v-for="opt in PRIORITY_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                </vort-select>
            </div>
            <div class="flex items-center gap-2">
                <vort-button variant="primary" @click="emit('search')">查询</vort-button>
                <vort-button @click="emit('reset')">重置</vort-button>
            </div>
        </div>
    </div>
</template>
