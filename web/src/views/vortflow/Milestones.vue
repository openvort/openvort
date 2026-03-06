<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { z } from "zod";
import { useCrudPage, useDirtyCheck } from "@/hooks";
import {
    getVortflowMilestones, getVortflowProjects, createVortflowMilestone,
    updateVortflowMilestone, deleteVortflowMilestone, completeVortflowMilestone,
    generateVortflowDescriptionPrompt,
} from "@/api";
import { message } from "@/components/vort";
import { Check, Clock, Milestone, Plus, Bot } from "lucide-vue-next";

const router = useRouter();

interface MilestoneItem {
    id: string;
    name: string;
    description?: string;
    project_id: string;
    story_id: string | null;
    due_date: string | null;
    completed_at: string | null;
    created_at: string | null;
}

type FilterParams = { page: number; size: number; project_id: string; keyword: string };

const isOverdue = (dueDate: string | null, completedAt: string | null) => {
    if (!dueDate || completedAt) return false;
    return new Date(dueDate) < new Date();
};

// Projects
const projects = ref<{ id: string; name: string }[]>([]);
const loadProjects = async () => {
    try {
        const res = await getVortflowProjects();
        projects.value = (res as any)?.items || [];
    } catch { /* silent */ }
};
loadProjects();

// CRUD
const fetchMilestones = async (params: FilterParams) => {
    const res = await getVortflowMilestones({
        project_id: params.project_id, keyword: params.keyword,
        page: params.page, page_size: params.size,
    });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const { listData, loading, total, filterParams, showPagination, loadData, onSearchSubmit, resetParams } =
    useCrudPage<MilestoneItem, FilterParams>({
        api: fetchMilestones,
        defaultParams: { page: 1, size: 20, project_id: "", keyword: "" },
    });

// Drawer
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"view" | "edit" | "add">("view");
const currentRow = ref<Partial<MilestoneItem>>({});
const formRef = ref();
const formLoading = ref(false);
const { takeSnapshot, confirmClose } = useDirtyCheck(currentRow);

const milestoneValidationSchema = z.object({
    project_id: z.string().min(1, '请选择项目'),
    name: z.string().min(1, '里程碑名称不能为空'),
    due_date: z.string().optional().or(z.literal('')).nullable(),
    description: z.string().optional().or(z.literal('')),
});

const handleAdd = () => {
    drawerMode.value = "add";
    drawerTitle.value = "新增里程碑";
    currentRow.value = { project_id: projects.value[0]?.id || "" };
    drawerVisible.value = true;
    takeSnapshot();
};
const handleEdit = (item: MilestoneItem) => {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑里程碑";
    currentRow.value = { ...item, due_date: item.due_date ? item.due_date.split("T")[0] : "" };
    drawerVisible.value = true;
    takeSnapshot();
};
const handleView = (item: MilestoneItem) => {
    drawerMode.value = "view";
    drawerTitle.value = "里程碑详情";
    currentRow.value = { ...item };
    drawerVisible.value = true;
};

const handleSave = async () => {
    try { await formRef.value?.validate(); } catch { return; }
    const r = currentRow.value;
    formLoading.value = true;
    try {
        if (drawerMode.value === "add") {
            await createVortflowMilestone({
                project_id: r.project_id!, name: r.name!,
                description: r.description, due_date: r.due_date || undefined,
            });
        } else {
            await updateVortflowMilestone(r.id!, {
                name: r.name, description: r.description,
                due_date: r.due_date || undefined,
            });
        }
        drawerVisible.value = false;
        loadData();
    } finally { formLoading.value = false; }
};

// AI 生成描述
async function handleAiGenerateDescription() {
    if (!currentRow.value.name?.trim()) {
        message.warning("请先输入里程碑名称");
        return;
    }
    const projectName = projects.value.find(p => p.id === currentRow.value.project_id)?.name || "";
    try {
        const res: any = await generateVortflowDescriptionPrompt("milestone", projectName, currentRow.value.name);
        if (res?.prompt) {
            drawerVisible.value = false;
            router.push({ name: "chat", query: { prompt: res.prompt } });
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "生成失败");
    }
}

const handleDelete = async (item: MilestoneItem) => {
    await deleteVortflowMilestone(item.id);
    loadData();
};

const handleComplete = async (item: MilestoneItem) => {
    await completeVortflowMilestone(item.id);
    loadData();
    if (drawerVisible.value && currentRow.value.id === item.id) {
        currentRow.value.completed_at = new Date().toISOString();
    }
};

const projectName = (id: string) => projects.value.find(p => p.id === id)?.name || '-';

loadData();
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">里程碑</h3>
                <vort-button variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增里程碑
                </vort-button>
            </div>
            <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4 mb-4">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                    <vort-input-search v-model="filterParams.keyword" placeholder="搜索里程碑..." allow-clear class="flex-1 sm:w-[200px]" @search="onSearchSubmit" @keyup.enter="onSearchSubmit" />
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">项目</span>
                    <vort-select v-model="filterParams.project_id" placeholder="全部项目" allow-clear class="flex-1 sm:w-[160px]" @change="onSearchSubmit">
                        <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2">
                    <vort-button variant="primary" @click="onSearchSubmit">查询</vort-button>
                    <vort-button @click="resetParams">重置</vort-button>
                </div>
            </div>

            <vort-spin :spinning="loading">
                <div v-if="listData.length === 0 && !loading" class="text-center py-12 text-gray-400">
                    <Milestone :size="48" class="mx-auto mb-3 text-gray-300" />
                    <p>暂无里程碑</p>
                </div>
                <div v-else class="space-y-3">
                    <div
                        v-for="item in listData" :key="item.id"
                        class="border rounded-lg p-4 flex items-center justify-between hover:shadow-sm transition-shadow"
                    >
                        <div class="flex items-center gap-3 cursor-pointer flex-1" @click="handleView(item)">
                            <div
                                class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                                :class="item.completed_at ? 'bg-green-50' : isOverdue(item.due_date, item.completed_at) ? 'bg-red-50' : 'bg-blue-50'"
                            >
                                <Check v-if="item.completed_at" :size="16" class="text-green-600" />
                                <Clock v-else :size="16" :class="isOverdue(item.due_date, item.completed_at) ? 'text-red-600' : 'text-blue-600'" />
                            </div>
                            <div>
                                <h4 class="font-medium text-gray-800">{{ item.name }}</h4>
                                <div class="flex items-center gap-2 mt-0.5">
                                    <span class="text-xs text-gray-400">{{ projectName(item.project_id) }}</span>
                                    <span class="text-xs text-gray-300">·</span>
                                    <span class="text-xs text-gray-400">创建于 {{ item.created_at ? item.created_at.split('T')[0] : '-' }}</span>
                                </div>
                            </div>
                        </div>
                        <div class="flex items-center gap-3">
                            <vort-tag v-if="item.completed_at" color="green">已完成</vort-tag>
                            <vort-tag v-else-if="isOverdue(item.due_date, item.completed_at)" color="red">已逾期</vort-tag>
                            <vort-tag v-else color="blue">进行中</vort-tag>
                            <span v-if="item.due_date" class="text-sm text-gray-500">截止: {{ item.due_date.split('T')[0] }}</span>
                            <div class="flex items-center gap-1">
                                <vort-tooltip v-if="!item.completed_at" title="标记完成">
                                    <a class="text-sm text-green-600 cursor-pointer" @click.stop="handleComplete(item)">完成</a>
                                </vort-tooltip>
                                <vort-divider type="vertical" />
                                <a class="text-sm text-blue-600 cursor-pointer" @click.stop="handleEdit(item)">编辑</a>
                                <vort-divider type="vertical" />
                                <vort-popconfirm title="确认删除该里程碑？" @confirm="handleDelete(item)">
                                    <a class="text-sm text-red-500 cursor-pointer" @click.stop>删除</a>
                                </vort-popconfirm>
                            </div>
                        </div>
                    </div>
                </div>
            </vort-spin>

            <div v-if="showPagination" class="flex justify-end mt-4">
                <vort-pagination v-model:current="filterParams.page" v-model:page-size="filterParams.size" :total="total" show-total-info show-size-changer @change="loadData" />
            </div>
        </div>

        <!-- Drawer -->
        <vort-drawer :open="drawerVisible" :title="drawerTitle" :width="900" @update:open="(val: boolean) => { if (!val && drawerMode !== 'view') { confirmClose(() => { drawerVisible = false }) } else { drawerVisible = val } }">
            <!-- View -->
            <div v-if="drawerMode === 'view'">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div class="sm:col-span-2">
                        <span class="text-sm text-gray-400">名称</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentRow.name }}</div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">项目</span>
                        <div class="text-sm text-gray-800 mt-1">{{ projectName(currentRow.project_id!) }}</div>
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
                        <div class="mt-1">
                            <MarkdownView :content="currentRow.description" />
                        </div>
                    </div>
                </div>
            </div>
            <!-- Edit / Add -->
            <template v-else>
                <vort-form ref="formRef" :model="currentRow" :rules="milestoneValidationSchema" label-width="80px">
                    <vort-form-item label="项目" name="project_id" required has-feedback>
                        <vort-select v-model="currentRow.project_id" placeholder="选择项目" :disabled="drawerMode === 'edit'" class="w-full">
                            <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                    <vort-form-item label="名称" name="name" required has-feedback>
                        <vort-input v-model="currentRow.name" placeholder="请输入里程碑名称" />
                    </vort-form-item>
                    <vort-form-item label="截止日期" name="due_date">
                        <vort-date-picker v-model="currentRow.due_date" value-format="YYYY-MM-DD" placeholder="请选择截止日期" class="w-full" />
                    </vort-form-item>
                    <vort-form-item label="描述" name="description">
                        <div class="space-y-2">
                            <VortEditor v-model="currentRow.description" placeholder="请输入描述" min-height="160px" />
                            <div class="flex justify-end">
                                <vort-button size="small" @click="handleAiGenerateDescription">
                                    <Bot :size="12" class="mr-1" /> AI 助手创建
                                </vort-button>
                            </div>
                        </div>
                    </vort-form-item>
                </vort-form>
                <div class="flex justify-end gap-3 mt-6">
                    <vort-button @click="confirmClose(() => { drawerVisible = false })">取消</vort-button>
                    <vort-button variant="primary" :loading="formLoading" @click="handleSave">确定</vort-button>
                </div>
            </template>
        </vort-drawer>
    </div>
</template>
