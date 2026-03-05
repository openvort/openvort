<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { z } from "zod";
import { Plus, Settings, Trash2, Rocket, MoreHorizontal, UserRound } from "lucide-vue-next";
import {
    getVortflowVersions, createVortflowVersion, updateVortflowVersion, deleteVortflowVersion,
    releaseVortflowVersion, getVortflowProjects, getMembers,
} from "@/api";

interface VersionItem {
    id: string;
    project_id: string;
    name: string;
    description: string;
    release_date: string | null;
    status: string;
    created_at: string | null;
    assignee_id?: string | null;
    owner_id?: string | null;
    pm_id?: string | null;
}

interface ProjectItem {
    id: string;
    name: string;
}

interface MemberOption {
    id: string;
    name: string;
    avatarUrl: string;
}

const loading = ref(true);
const versions = ref<VersionItem[]>([]);
const projects = ref<ProjectItem[]>([]);
const keyword = ref("");
const selectedOwnerId = ref("");
const activeTab = ref("version-list");
const memberOptions = ref<MemberOption[]>([]);

const statusColorMap: Record<string, string> = {
    planning: "default", released: "success", archived: "default"
};
const statusLabels: Record<string, string> = {
    planning: "规划中", released: "已发布", archived: "已归档"
};

const filteredVersions = computed(() => {
    let list = versions.value;
    if (selectedOwnerId.value) {
        list = list.filter(v => getVersionOwnerId(v) === selectedOwnerId.value);
    }
    if (keyword.value.trim()) {
        const k = keyword.value.trim().toLowerCase();
        list = list.filter(v =>
            v.name.toLowerCase().includes(k) ||
            (v.description || "").toLowerCase().includes(k),
        );
    }
    return list;
});

const stageLabelMap: Record<string, string> = {
    planning: "开发环境",
    released: "已发布",
    archived: "已归档",
};

const progressByStatus: Record<string, number> = {
    planning: 0,
    released: 100,
    archived: 100,
};

const projectNameById = (id: string) => {
    const p = projects.value.find(p => p.id === id);
    return p ? p.name : id;
};

const getVersionOwnerId = (item: VersionItem): string => {
    return String(item.assignee_id || item.owner_id || item.pm_id || "").trim();
};

const getMemberNameById = (memberId: string): string => {
    if (!memberId) return "待指派";
    return memberOptions.value.find(m => m.id === memberId)?.name || memberId;
};

const getMemberAvatarUrlById = (memberId: string): string => {
    if (!memberId) return "";
    return memberOptions.value.find(m => m.id === memberId)?.avatarUrl || "";
};

const getAvatarLabel = (name: string): string => {
    const normalized = String(name || "").trim();
    if (!normalized) return "?";
    return normalized.slice(0, 1).toUpperCase();
};

const loadData = async () => {
    loading.value = true;
    try {
        const [verRes, projRes, memberRes] = await Promise.all([
            getVortflowVersions({ page: 1, page_size: 100 }),
            getVortflowProjects(),
            getMembers({ search: "", role: "", page: 1, size: 50 }),
        ]);
        versions.value = ((verRes as any)?.items || []);
        projects.value = ((projRes as any)?.items || []);
        const members = Array.isArray((memberRes as any)?.members) ? (memberRes as any).members : [];
        memberOptions.value = members
            .map((item: any) => ({
                id: String(item?.id || ""),
                name: String(item?.name || "").trim(),
                avatarUrl: String(item?.avatar_url || item?.avatar || ""),
            }))
            .filter((item: MemberOption) => item.id && item.name);
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

const resetFilters = () => {
    selectedOwnerId.value = "";
    keyword.value = "";
};

onMounted(loadData);
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <vort-tabs v-model:activeKey="activeTab" :hide-content="true">
                <vort-tab-pane tab-key="version-list" tab="版本列表" />
                <vort-tab-pane tab-key="release-plan" tab="发布计划" />
            </vort-tabs>

            <div v-if="activeTab === 'version-list'" class="mt-4">
                <vort-spin :spinning="loading">
                    <div class="flex items-center justify-between mb-3">
                        <div class="text-sm text-gray-500">共计 {{ filteredVersions.length }} 项</div>
                        <vort-button variant="primary" @click="handleAddVersion">
                            <Plus :size="14" class="mr-1" /> 新建版本
                        </vort-button>
                    </div>

                    <div class="flex items-center gap-2 mb-4">
                        <span class="text-sm text-gray-500 whitespace-nowrap">筛选项</span>
                        <vort-input
                            v-model="keyword"
                            placeholder="版本号/版本名称"
                            allow-clear
                            class="w-[240px]"
                        />
                        <vort-select
                            v-model="selectedOwnerId"
                            placeholder="负责人"
                            allow-clear
                            class="w-[220px] shrink-0 version-owner-filter"
                        >
                            <vort-select-option
                                v-for="m in memberOptions"
                                :key="m.id"
                                :value="m.id"
                            >
                                <div class="flex items-center gap-2">
                                    <span
                                        class="w-5 h-5 rounded-full bg-sky-50 text-sky-600 inline-flex items-center justify-center text-[11px] overflow-hidden"
                                    >
                                        <img
                                            v-if="m.avatarUrl"
                                            :src="m.avatarUrl"
                                            class="w-full h-full object-cover"
                                        >
                                        <template v-else>{{ getAvatarLabel(m.name) }}</template>
                                    </span>
                                    <span class="text-sm text-gray-700">{{ m.name }}</span>
                                </div>
                            </vort-select-option>
                        </vort-select>
                        <vort-button @click="resetFilters">重置</vort-button>
                    </div>

                    <vort-table :data-source="filteredVersions" :pagination="false">
                        <vort-table-column label="版本号" :width="120">
                            <template #default="{ row }">
                                <span class="inline-flex items-center px-2 py-0.5 rounded bg-blue-50 text-blue-600 text-xs font-medium">
                                    {{ row.name }}
                                </span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="版本名称" :min-width="220">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-800">
                                    {{ row.description || projectNameById(row.project_id) }}
                                </span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="阶段" :width="120">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-700">
                                    {{ stageLabelMap[row.status] || statusLabels[row.status] || row.status }}
                                </span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="负责人" :width="140">
                            <template #default="{ row }">
                                <div class="flex items-center gap-1.5 text-sm text-gray-700">
                                    <span class="w-5 h-5 rounded-full bg-sky-50 text-sky-600 inline-flex items-center justify-center overflow-hidden">
                                        <img
                                            v-if="getMemberAvatarUrlById(getVersionOwnerId(row))"
                                            :src="getMemberAvatarUrlById(getVersionOwnerId(row))"
                                            class="w-full h-full object-cover"
                                        >
                                        <UserRound v-else :size="12" />
                                    </span>
                                    {{ getMemberNameById(getVersionOwnerId(row)) }}
                                </div>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="发布时间/实际发布时间" :width="210">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-500">
                                    {{ formatDate(row.release_date) }} / -
                                </span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="进度" :width="170">
                            <template #default="{ row }">
                                <div class="flex items-center gap-2">
                                    <div class="w-[110px] h-1.5 rounded-full bg-gray-100 overflow-hidden">
                                        <div
                                            class="h-full rounded-full bg-blue-500 transition-all"
                                            :style="{ width: `${progressByStatus[row.status] ?? 0}%` }"
                                        />
                                    </div>
                                    <span class="text-xs text-gray-500">{{ progressByStatus[row.status] ?? 0 }}%</span>
                                </div>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="操作" :width="170" fixed="right">
                            <template #default="{ row }">
                                <div class="flex items-center gap-2 whitespace-nowrap">
                                    <a
                                        v-if="row.status === 'planning'"
                                        class="text-sm text-blue-600 cursor-pointer"
                                        @click="handleReleaseVersion(row)"
                                    >
                                        <Rocket :size="12" class="inline mr-1" />发布
                                    </a>
                                    <a class="text-sm text-blue-600 cursor-pointer" @click="handleEditVersion(row)">
                                        <Settings :size="12" class="inline mr-1" />编辑
                                    </a>
                                    <vort-popconfirm title="确认删除该版本？" @confirm="handleDeleteVersion(row)">
                                        <a class="text-sm text-red-500 cursor-pointer">
                                            <Trash2 :size="12" class="inline mr-1" />删除
                                        </a>
                                    </vort-popconfirm>
                                    <a class="text-gray-400 cursor-default">
                                        <MoreHorizontal :size="14" />
                                    </a>
                                </div>
                            </template>
                        </vort-table-column>
                    </vort-table>

                    <div v-if="filteredVersions.length === 0" class="py-12 text-center text-sm text-gray-400">
                        暂无版本数据
                    </div>
                </vort-spin>
            </div>

            <div v-else class="mt-6 py-12 text-center text-sm text-gray-400">
                发布计划模块待上线
            </div>
        </div>

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

<style scoped>
.version-owner-filter :deep(.vort-select-selection-placeholder),
.version-owner-filter :deep(.vort-select-selection-item) {
    white-space: nowrap;
}
</style>
