<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { z } from "zod";
import { Tag, Plus, Settings, Trash2, Calendar, Rocket } from "lucide-vue-next";
import {
    getVortflowVersions, createVortflowVersion, updateVortflowVersion, deleteVortflowVersion,
    releaseVortflowVersion, getVortflowProjects,
} from "@/api";

interface VersionItem {
    id: string;
    project_id: string;
    name: string;
    description: string;
    release_date: string | null;
    status: string;
    created_at: string | null;
}

interface ProjectItem {
    id: string;
    name: string;
}

const loading = ref(true);
const versions = ref<VersionItem[]>([]);
const projects = ref<ProjectItem[]>([]);
const selectedProjectId = ref("");
const selectedStatus = ref("");

const statusColorMap: Record<string, string> = {
    planning: "default", released: "success", archived: "default"
};
const statusLabels: Record<string, string> = {
    planning: "规划中", released: "已发布", archived: "已归档"
};

const filteredVersions = computed(() => {
    let list = versions.value;
    if (selectedProjectId.value) {
        list = list.filter(v => v.project_id === selectedProjectId.value);
    }
    if (selectedStatus.value) {
        list = list.filter(v => v.status === selectedStatus.value);
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
        const [verRes, projRes] = await Promise.all([
            getVortflowVersions({ page: 1, page_size: 100 }),
            getVortflowProjects(),
        ]);
        versions.value = ((verRes as any)?.items || []);
        projects.value = ((projRes as any)?.items || []);
    } catch { /* silent */ }
    finally { loading.value = false; }
};

// Drawer
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"add" | "edit">("add");
const currentVersion = ref<Partial<VersionItem>>({});
const formRef = ref();
const formLoading = ref(false);

const versionValidationSchema = z.object({
    project_id: z.string().min(1, "请选择项目"),
    name: z.string().min(1, "版本名称不能为空"),
    description: z.string().optional(),
    release_date: z.string().optional(),
    status: z.string().optional(),
});

const handleAddVersion = () => {
    drawerMode.value = "add";
    drawerTitle.value = "新增版本";
    currentVersion.value = { status: "planning" };
    drawerVisible.value = true;
};

const handleEditVersion = (v: VersionItem) => {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑版本";
    currentVersion.value = {
        ...v,
        release_date: v.release_date ? v.release_date.split("T")[0] : "",
    };
    drawerVisible.value = true;
};

const handleSaveVersion = async () => {
    try { await formRef.value?.validate(); } catch { return; }
    const v = currentVersion.value;
    formLoading.value = true;
    try {
        if (drawerMode.value === "add") {
            await createVortflowVersion({
                project_id: v.project_id!,
                name: v.name!,
                description: v.description || "",
                release_date: v.release_date || undefined,
                status: v.status || "planning",
            });
        } else {
            await updateVortflowVersion(v.id!, {
                name: v.name,
                description: v.description,
                release_date: v.release_date || undefined,
                status: v.status,
            });
        }
        drawerVisible.value = false;
        loadData();
    } finally { formLoading.value = false; }
};

const handleDeleteVersion = async (v: VersionItem) => {
    await deleteVortflowVersion(v.id);
    loadData();
};

const handleReleaseVersion = async (v: VersionItem) => {
    await releaseVortflowVersion(v.id);
    loadData();
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
                        <Tag :size="16" class="text-gray-400" />
                        <span class="text-sm text-gray-500">筛选</span>
                    </div>
                    <vort-select v-model="selectedProjectId" placeholder="全部项目" clearable style="width: 180px">
                        <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                    </vort-select>
                    <vort-select v-model="selectedStatus" placeholder="全部状态" clearable style="width: 120px">
                        <vort-select-option value="planning">规划中</vort-select-option>
                        <vort-select-option value="released">已发布</vort-select-option>
                        <vort-select-option value="archived">已归档</vort-select-option>
                    </vort-select>
                    <vort-button variant="primary" @click="handleAddVersion">
                        <Plus :size="14" class="mr-1" /> 新增版本
                    </vort-button>
                </div>
            </div>

            <!-- Versions Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
                <div v-for="v in filteredVersions" :key="v.id"
                    class="bg-white rounded-xl p-5 hover:shadow-sm transition-shadow"
                >
                    <div class="flex items-start justify-between mb-3">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-lg bg-green-50 flex items-center justify-center">
                                <Tag :size="16" class="text-green-600" />
                            </div>
                            <div>
                                <h4 class="text-sm font-medium text-gray-800">{{ v.name }}</h4>
                                <p class="text-xs text-gray-400">{{ projectNameById(v.project_id) }}</p>
                            </div>
                        </div>
                        <vort-tag :color="statusColorMap[v.status] || 'default'" size="small">
                            {{ statusLabels[v.status] || v.status }}
                        </vort-tag>
                    </div>

                    <div v-if="v.description" class="text-xs text-gray-500 mb-3 line-clamp-2">
                        {{ v.description }}
                    </div>

                    <div class="flex items-center gap-4 text-xs text-gray-400 mb-4">
                        <div class="flex items-center gap-1">
                            <Calendar :size="12" />
                            <span>计划发布: {{ formatDate(v.release_date) }}</span>
                        </div>
                    </div>

                    <div class="flex items-center justify-between pt-3 border-t border-gray-100">
                        <vort-button v-if="v.status === 'planning'" size="small" @click="handleReleaseVersion(v)">
                            <Rocket :size="12" class="mr-1" /> 发布版本
                        </vort-button>
                        <span v-else></span>
                        <div class="flex items-center gap-1">
                            <vort-tooltip title="编辑">
                                <a class="text-gray-400 hover:text-blue-600 cursor-pointer" @click="handleEditVersion(v)">
                                    <Settings :size="14" />
                                </a>
                            </vort-tooltip>
                            <vort-popconfirm title="确认删除该版本？" @confirm="handleDeleteVersion(v)">
                                <a class="text-gray-400 hover:text-red-500 cursor-pointer">
                                    <Trash2 :size="14" />
                                </a>
                            </vort-popconfirm>
                        </div>
                    </div>
                </div>

                <div v-if="filteredVersions.length === 0" class="col-span-full">
                    <div class="bg-white rounded-xl p-12 text-center">
                        <Tag :size="48" class="mx-auto mb-3 text-gray-300" />
                        <p class="text-gray-400">暂无版本，点击上方按钮创建</p>
                    </div>
                </div>
            </div>
        </vort-spin>

        <!-- Drawer -->
        <vort-drawer :open="drawerVisible" :title="drawerTitle" :width="500" @update:open="drawerVisible = $event">
            <vort-form ref="formRef" :model="currentVersion" :rules="versionValidationSchema" label-width="80px">
                <vort-form-item label="所属项目" name="project_id" required>
                    <vort-select v-model="currentVersion.project_id" placeholder="请选择项目" :disabled="drawerMode === 'edit'" class="w-full">
                        <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                    </vort-select>
                </vort-form-item>
                <vort-form-item label="版本名称" name="name" required>
                    <vort-input v-model="currentVersion.name" placeholder="如：v1.0.0" />
                </vort-form-item>
                <vort-form-item label="版本描述" name="description">
                    <vort-textarea v-model="currentVersion.description" placeholder="版本描述/更新" :rows="3" />
                </vort-form-item>
                <vort-form-item label="计划发布日期" name="release_date">
                    <vort-date-picker v-model="currentVersion.release_date" value-format="YYYY-MM-DD" placeholder="请选择发布日期" class="w-full" />
                </vort-form-item>
                <vort-form-item label="状态" name="status">
                    <vort-select v-model="currentVersion.status" class="w-full">
                        <vort-select-option value="planning">规划中</vort-select-option>
                        <vort-select-option value="released">已发布</vort-select-option>
                        <vort-select-option value="archived">已归档</vort-select-option>
                    </vort-select>
                </vort-form-item>
            </vort-form>
            <div class="flex justify-end gap-3 mt-6">
                <vort-button @click="drawerVisible = false">取消</vort-button>
                <vort-button variant="primary" :loading="formLoading" @click="handleSaveVersion">确定</vort-button>
            </div>
        </vort-drawer>
    </div>
</template>
