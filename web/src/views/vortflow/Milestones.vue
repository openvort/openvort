<script setup lang="ts">
import { ref } from "vue";
import { useCrudPage } from "@/hooks";
import { getVortflowMilestones } from "@/api";
import { Check, Clock, Milestone } from "lucide-vue-next";

interface MilestoneItem {
    id: string;
    name: string;
    due_date: string | null;
    completed_at: string | null;
    created_at: string | null;
    description?: string;
}

type FilterParams = { page: number; size: number };

const isOverdue = (dueDate: string | null, completedAt: string | null) => {
    if (!dueDate || completedAt) return false;
    return new Date(dueDate) < new Date();
};

const fetchMilestones = async (params: FilterParams) => {
    const res = await getVortflowMilestones({ page: params.page, page_size: params.size });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const { listData, loading, total, filterParams, showPagination, loadData } =
    useCrudPage<MilestoneItem, FilterParams>({
        api: fetchMilestones,
        defaultParams: { page: 1, size: 20 },
    });

// Drawer
const drawerVisible = ref(false);
const currentRow = ref<Partial<MilestoneItem>>({});

const handleView = (item: MilestoneItem) => {
    currentRow.value = { ...item };
    drawerVisible.value = true;
};

loadData();
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">里程碑</h3>
            </div>

            <vort-spin :spinning="loading">
                <div v-if="listData.length === 0 && !loading" class="text-center py-12 text-gray-400">
                    <Milestone :size="48" class="mx-auto mb-3 text-gray-300" />
                    <p>暂无里程碑</p>
                </div>
                <div v-else class="space-y-3">
                    <div
                        v-for="item in listData" :key="item.id"
                        class="border rounded-lg p-4 flex items-center justify-between hover:shadow-sm transition-shadow cursor-pointer"
                        @click="handleView(item)"
                    >
                        <div class="flex items-center gap-3">
                            <div
                                class="w-8 h-8 rounded-full flex items-center justify-center"
                                :class="item.completed_at ? 'bg-green-50' : isOverdue(item.due_date, item.completed_at) ? 'bg-red-50' : 'bg-blue-50'"
                            >
                                <Check v-if="item.completed_at" :size="16" class="text-green-600" />
                                <Clock v-else :size="16" :class="isOverdue(item.due_date, item.completed_at) ? 'text-red-600' : 'text-blue-600'" />
                            </div>
                            <div>
                                <h4 class="font-medium text-gray-800">{{ item.name }}</h4>
                                <span class="text-xs text-gray-400">创建于 {{ item.created_at ? item.created_at.split('T')[0] : '-' }}</span>
                            </div>
                        </div>
                        <div class="flex items-center gap-3">
                            <vort-tag v-if="item.completed_at" color="green">已完成</vort-tag>
                            <vort-tag v-else-if="isOverdue(item.due_date, item.completed_at)" color="red">已逾期</vort-tag>
                            <vort-tag v-else color="blue">进行中</vort-tag>
                            <span v-if="item.due_date" class="text-sm text-gray-500">截止: {{ item.due_date.split('T')[0] }}</span>
                        </div>
                    </div>
                </div>
            </vort-spin>

            <div v-if="showPagination" class="flex justify-end mt-4">
                <vort-pagination
                    v-model:current="filterParams.page"
                    v-model:page-size="filterParams.size"
                    :total="total"
                    show-total-info
                    show-size-changer
                    @change="loadData"
                />
            </div>
        </div>

        <!-- Drawer -->
        <vort-drawer v-model:open="drawerVisible" title="里程碑详情" :width="550">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div class="sm:col-span-2">
                    <span class="text-sm text-gray-400">名称</span>
                    <div class="text-sm text-gray-800 mt-1">{{ currentRow.name }}</div>
                </div>
                <div>
                    <span class="text-sm text-gray-400">状态</span>
                    <div class="mt-1">
                        <vort-tag v-if="currentRow.completed_at" color="green">已完成</vort-tag>
                        <vort-tag v-else-if="isOverdue(currentRow.due_date!, currentRow.completed_at!)" color="red">已逾期</vort-tag>
                        <vort-tag v-else color="blue">进行中</vort-tag>
                    </div>
                </div>
                <div>
                    <span class="text-sm text-gray-400">截止日期</span>
                    <div class="text-sm text-gray-800 mt-1">{{ currentRow.due_date ? currentRow.due_date.split('T')[0] : '-' }}</div>
                </div>
                <div>
                    <span class="text-sm text-gray-400">创建时间</span>
                    <div class="text-sm text-gray-800 mt-1">{{ currentRow.created_at ? currentRow.created_at.split('T')[0] : '-' }}</div>
                </div>
                <div v-if="currentRow.completed_at">
                    <span class="text-sm text-gray-400">完成时间</span>
                    <div class="text-sm text-gray-800 mt-1">{{ currentRow.completed_at.split('T')[0] }}</div>
                </div>
                <div v-if="currentRow.description" class="sm:col-span-2">
                    <span class="text-sm text-gray-400">描述</span>
                    <div class="text-sm text-gray-800 mt-1 whitespace-pre-wrap">{{ currentRow.description }}</div>
                </div>
            </div>
        </vort-drawer>
    </div>
</template>
