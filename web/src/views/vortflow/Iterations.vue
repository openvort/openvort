<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { z } from "zod";
import { useRouter } from "vue-router";
import { Repeat, Plus, Settings, Trash2, Calendar, Target, Filter } from "lucide-vue-next";
import {
    getVortflowIterations, createVortflowIteration, updateVortflowIteration, deleteVortflowIteration,
    getVortflowProjects, getVortflowIterationStories,
} from "@/api";

interface IterationItem {
    id: string;
    project_id: string;
    name: string;
    goal: string;
    start_date: string | null;
    end_date: string | null;
    status: string;
    created_at: string | null;
}

interface ProjectItem {
    id: string;
    name: string;
}

const router = useRouter();
const loading = ref(true);
const iterations = ref<IterationItem[]>([]);
const projects = ref<ProjectItem[]>([]);
const selectedProjectId = ref("");
const selectedStatus = ref("");

const statusColorMap: Record<string, string> = {
    planning: "default", active: "processing", completed: "success"
};
const statusLabels: Record<string, string> = {
    planning: "规划中", active: "进行中", completed: "已完成"
};

const filteredIterations = computed(() => {
    let list = iterations.value;
    if (selectedProjectId.value) {
        list = list.filter(i => i.project_id === selectedProjectId.value);
    }
    if (selectedStatus.value) {
        list = list.filter(i => i.status === selectedStatus.value);
    }
    return list;
});

const projectNameById = (id: string) => {
    const p = projects.value.find(p => p.id === id);
    return p ? p.name : id;
};

const loadData = async () => {
    loading.value = true;
    try {
        const [iterRes, projRes] = await Promise.all([
            getVortflowIterations({ page: 1, page_size: 100 }),
            getVortflowProjects(),
        ]);
        iterations.value = ((iterRes as any)?.items || []);
        projects.value = ((projRes as any)?.items || []);
    } catch { /* silent */ }
    finally { loading.value = false; }
};

const loadIterations = async () => {
    const res = await getVortflowIterations({ page: 1, page_size: 100 });
    iterations.value = ((res as any)?.items || []);
};

// Drawer
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"add" | "edit">("add");
const currentIteration = ref<Partial<IterationItem>>({});
const formRef = ref();
const formLoading = ref(false);

const iterationValidationSchema = z.object({
    project_id: z.string().min(1, "请选择项目"),
    name: z.string().min(1, "迭代名称不能为空"),
    goal: z.string().optional(),
    start_date: z.string().optional(),
    end_date: z.string().optional(),
    status: z.string().optional(),
});

const handleAddIteration = () => {
    drawerMode.value = "add";
    drawerTitle.value = "新增迭代";
    currentIteration.value = { status: "planning" };
    drawerVisible.value = true;
};

const handleEditIteration = (i: IterationItem) => {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑迭代";
    currentIteration.value = {
        ...i,
        start_date: i.start_date ? i.start_date.split("T")[0] : "",
        end_date: i.end_date ? i.end_date.split("T")[0] : "",
    };
    drawerVisible.value = true;
};

const handleSaveIteration = async () => {
    try { await formRef.value?.validate(); } catch { return; }
    const r = currentIteration.value;
    formLoading.value = true;
    try {
        if (drawerMode.value === "add") {
            await createVortflowIteration({
                project_id: r.project_id!,
                name: r.name!,
                goal: r.goal || "",
                start_date: r.start_date || undefined,
                end_date: r.end_date || undefined,
                status: r.status || "planning",
            });
        } else {
            await updateVortflowIteration(r.id!, {
                name: r.name,
                goal: r.goal,
                start_date: r.start_date || undefined,
                end_date: r.end_date || undefined,
                status: r.status,
            });
        }
        drawerVisible.value = false;
        loadData();
    } finally { formLoading.value = false; }
};

const handleDeleteIteration = async (i: IterationItem) => {
    await deleteVortflowIteration(i.id);
    loadData();
};

const handleViewStories = (i: IterationItem) => {
    router.push(`/vortflow/iterations/${i.id}/stories`);
};

const formatDate = (iso: string | null) => {
    if (!iso) return "-";
    return iso.split("T")[0];
};

onMounted(loadData);
</script>

<template>
    <div class="space-y-4">
        <vort-spin :spinning="loading">
            <!-- Filters -->
            <div class="bg-white rounded-xl p-4">
                <div class="flex items-center gap-4 flex-wrap">
                    <div class="flex items-center gap-2">
                        <Filter :size="16" class="text-gray-400" />
                        <span class="text-sm text-gray-500">筛选</span>
                    </div>
                    <vort-select v-model="selectedProjectId" placeholder="全部项目" clearable style="width: 180px">
                        <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                    </vort-select>
                    <vort-select v-model="selectedStatus" placeholder="全部状态" clearable style="width: 120px">
                        <vort-select-option value="planning">规划中</vort-select-option>
                        <vort-select-option value="active">进行中</vort-select-option>
                        <vort-select-option value="completed">已完成</vort-select-option>
                    </vort-select>
                    <vort-button variant="primary" @click="handleAddIteration">
                        <Plus :size="14" class="mr-1" /> 新增迭代
                    </vort-button>
                </div>
            </div>

            <!-- Iterations Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
                <div v-for="i in filteredIterations" :key="i.id"
                    class="bg-white rounded-xl p-5 hover:shadow-sm transition-shadow"
                >
                    <div class="flex items-start justify-between mb-3">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
                                <Repeat :size="16" class="text-blue-600" />
                            </div>
                            <div>
                                <h4 class="text-sm font-medium text-gray-800">{{ i.name }}</h4>
                                <p class="text-xs text-gray-400">{{ projectNameById(i.project_id) }}</p>
                            </div>
                        </div>
                        <vort-tag :color="statusColorMap[i.status] || 'default'" size="small">
                            {{ statusLabels[i.status] || i.status }}
                        </vort-tag>
                    </div>

                    <div v-if="i.goal" class="text-xs text-gray-500 mb-3 line-clamp-2">
                        {{ i.goal }}
                    </div>

                    <div class="flex items-center gap-4 text-xs text-gray-400 mb-4">
                        <div class="flex items-center gap-1">
                            <Calendar :size="12" />
                            <span>{{ formatDate(i.start_date) }} ~ {{ formatDate(i.end_date) }}</span>
                        </div>
                    </div>

                    <div class="flex items-center justify-between pt-3 border-t border-gray-100">
                        <a class="text-xs text-blue-600 hover:underline cursor-pointer" @click="handleViewStories(i)">
                            查看需求
                        </a>
                        <div class="flex items-center gap-1">
                            <vort-tooltip title="编辑">
                                <a class="text-gray-400 hover:text-blue-600 cursor-pointer" @click="handleEditIteration(i)">
                                    <Settings :size="14" />
                                </a>
                            </vort-tooltip>
                            <vort-popconfirm title="确认删除该迭代？" @confirm="handleDeleteIteration(i)">
                                <a class="text-gray-400 hover:text-red-500 cursor-pointer">
                                    <Trash2 :size="14" />
                                </a>
                            </vort-popconfirm>
                        </div>
                    </div>
                </div>

                <div v-if="filteredIterations.length === 0" class="col-span-full">
                    <div class="bg-white rounded-xl p-12 text-center">
                        <Repeat :size="48" class="mx-auto mb-3 text-gray-300" />
                        <p class="text-gray-400">暂无迭代，点击上方按钮创建</p>
                    </div>
                </div>
            </div>
        </vort-spin>

        <!-- Drawer -->
        <vort-drawer :open="drawerVisible" :title="drawerTitle" :width="500" @update:open="drawerVisible = $event">
            <vort-form ref="formRef" :model="currentIteration" :rules="iterationValidationSchema" label-width="80px">
                <vort-form-item label="所属项目" name="project_id" required>
                    <vort-select v-model="currentIteration.project_id" placeholder="请选择项目" :disabled="drawerMode === 'edit'" class="w-full">
                        <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                    </vort-select>
                </vort-form-item>
                <vort-form-item label="迭代名称" name="name" required>
                    <vort-input v-model="currentIteration.name" placeholder="如：Sprint 1" />
                </vort-form-item>
                <vort-form-item label="迭代目标" name="goal">
                    <vort-textarea v-model="currentIteration.goal" placeholder="迭代目标描述" :rows="3" />
                </vort-form-item>
                <vort-form-item label="开始日期" name="start_date">
                    <vort-date-picker v-model="currentIteration.start_date" value-format="YYYY-MM-DD" placeholder="请选择开始日期" class="w-full" />
                </vort-form-item>
                <vort-form-item label="结束日期" name="end_date">
                    <vort-date-picker v-model="currentIteration.end_date" value-format="YYYY-MM-DD" placeholder="请选择结束日期" class="w-full" />
                </vort-form-item>
                <vort-form-item label="状态" name="status">
                    <vort-select v-model="currentIteration.status" class="w-full">
                        <vort-select-option value="planning">规划中</vort-select-option>
                        <vort-select-option value="active">进行中</vort-select-option>
                        <vort-select-option value="completed">已完成</vort-select-option>
                    </vort-select>
                </vort-form-item>
            </vort-form>
            <div class="flex justify-end gap-3 mt-6">
                <vort-button @click="drawerVisible = false">取消</vort-button>
                <vort-button variant="primary" :loading="formLoading" @click="handleSaveIteration">确定</vort-button>
            </div>
        </vort-drawer>
    </div>
</template>
