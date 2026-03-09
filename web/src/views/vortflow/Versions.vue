<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useCrudPage } from "@/hooks";
import { Plus, UserRound } from "lucide-vue-next";
import { message } from "@/components/vort";
import {
    getVortflowVersions, createVortflowVersion, updateVortflowVersion, deleteVortflowVersion,
    releaseVortflowVersion, getVortflowProjects, getMembers,
} from "@/api";

interface VersionItem {
    id: string;
    project_id: string;
    name: string;
    description: string;
    owner_id?: string | null;
    planned_release_at?: string | null;
    actual_release_at?: string | null;
    progress?: number;
    release_date: string | null;
    status: string;
    created_at: string | null;
}

interface ProjectItem { id: string; name: string }
interface MemberOption { id: string; name: string; avatarUrl: string }

type FilterParams = { page: number; size: number; keyword: string; status: string; owner_id: string };

const projects = ref<ProjectItem[]>([]);
const memberOptions = ref<MemberOption[]>([]);
const activeTab = ref("version-list");

const statusOptions = [
    { label: "全部", value: "" },
    { label: "规划中", value: "planning" },
    { label: "已发布", value: "released" },
    { label: "已归档", value: "archived" },
];
const statusColorMap: Record<string, string> = { planning: "default", released: "green", archived: "default" };
const statusLabels: Record<string, string> = { planning: "规划中", released: "已发布", archived: "已归档" };
const stageLabelMap: Record<string, string> = { planning: "开发环境", released: "已发布", archived: "已归档" };

const fetchList = async (params: FilterParams) => {
    const res = await getVortflowVersions({
        keyword: params.keyword, status: params.status, owner_id: params.owner_id,
        page: params.page, page_size: params.size,
    });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const { listData, loading, total, filterParams, showPagination, loadData, onSearchSubmit, resetParams } =
    useCrudPage<VersionItem, FilterParams>({
        api: fetchList,
        defaultParams: { page: 1, size: 20, keyword: "", status: "", owner_id: "" },
    });

const loadOptions = async () => {
    try {
        const [projRes, memberRes] = await Promise.all([
            getVortflowProjects(),
            getMembers({ search: "", role: "", page: 1, size: 100 }),
        ]);
        projects.value = (projRes as any)?.items || [];
        const members = Array.isArray((memberRes as any)?.members) ? (memberRes as any).members : [];
        memberOptions.value = members
            .map((item: any) => ({
                id: String(item?.id || ""),
                name: String(item?.name || "").trim(),
                avatarUrl: String(item?.avatar_url || item?.avatar || ""),
            }))
            .filter((m: MemberOption) => m.id && m.name);
    } catch { /* silent */ }
};

const getMemberNameById = (id: string) => {
    if (!id) return "待指派";
    return memberOptions.value.find(m => m.id === id)?.name || "待指派";
};

const getMemberAvatarUrlById = (id: string) => {
    if (!id) return "";
    return memberOptions.value.find(m => m.id === id)?.avatarUrl || "";
};

const getVersionOwnerId = (item: VersionItem) => String(item.owner_id || "").trim();

const formatDate = (iso: string | null) => {
    if (!iso) return "-";
    return iso.split("T")[0];
};

const getVersionProgress = (row: VersionItem): number => {
    const explicit = Number(row.progress);
    if (Number.isFinite(explicit) && explicit >= 0) return Math.min(100, Math.max(0, explicit));
    const byStatus: Record<string, number> = { planning: 0, released: 100, archived: 100 };
    return byStatus[row.status] ?? 0;
};

// Dialog
const createDialogOpen = ref(false);
const createFormLoading = ref(false);
const versionDialogMode = ref<"create" | "edit">("create");
const editingVersionId = ref("");
const editingVersionStatus = ref("planning");
const createVersionForm = ref({
    version_no: "",
    title: "",
    owner_id: "",
    release_date: "",
    release_log: "",
});

const handleAddVersion = () => {
    versionDialogMode.value = "create";
    editingVersionId.value = "";
    editingVersionStatus.value = "planning";
    createVersionForm.value = {
        version_no: "", title: "",
        owner_id: memberOptions.value[0]?.id || "",
        release_date: "", release_log: "",
    };
    createDialogOpen.value = true;
};

const handleEditVersion = (v: VersionItem) => {
    versionDialogMode.value = "edit";
    editingVersionId.value = v.id;
    editingVersionStatus.value = v.status || "planning";
    createVersionForm.value = {
        version_no: v.name || "",
        title: v.description || "",
        owner_id: String(v.owner_id || ""),
        release_date: (v.planned_release_at || v.release_date || "") ? String(v.planned_release_at || v.release_date).split("T")[0] : "",
        release_log: "",
    };
    createDialogOpen.value = true;
};

const handleCreateVersion = async (andContinue = false) => {
    const projectId = projects.value[0]?.id;
    if (!projectId) return;
    const data = createVersionForm.value;
    if (!String(data.version_no || "").trim()) { message.warning("版本号必填"); return; }
    if (!String(data.title || "").trim()) { message.warning("标题必填"); return; }
    if (!String(data.owner_id || "").trim()) { message.warning("负责人必填"); return; }
    createFormLoading.value = true;
    try {
        if (versionDialogMode.value === "create") {
            await createVortflowVersion({
                project_id: projectId,
                name: String(data.version_no).trim(),
                description: String(data.title).trim(),
                owner_id: data.owner_id || undefined,
                planned_release_at: data.release_date || undefined,
                progress: 0, status: "planning",
            });
            if (andContinue) {
                createVersionForm.value = { version_no: "", title: "", owner_id: data.owner_id || "", release_date: "", release_log: "" };
            } else {
                createDialogOpen.value = false;
            }
        } else {
            if (!editingVersionId.value) return;
            await updateVortflowVersion(editingVersionId.value, {
                name: String(data.version_no).trim(),
                description: String(data.title).trim(),
                owner_id: data.owner_id || undefined,
                planned_release_at: data.release_date || undefined,
                status: editingVersionStatus.value,
            });
            createDialogOpen.value = false;
        }
        loadData();
    } finally { createFormLoading.value = false; }
};

const handleDeleteVersion = async (v: VersionItem) => {
    await deleteVortflowVersion(v.id);
    loadData();
};

const handleReleaseVersion = async (v: VersionItem) => {
    await releaseVortflowVersion(v.id);
    loadData();
};

onMounted(async () => {
    await Promise.all([loadOptions(), loadData()]);
});
</script>

<template>
    <div class="space-y-4">
        <!-- 搜索卡片 -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-6">
                    <h3 class="text-base font-medium text-gray-800 whitespace-nowrap leading-6">版本管理</h3>
                    <vort-tabs v-model:activeKey="activeTab" :hide-content="true">
                        <vort-tab-pane tab-key="version-list" tab="版本列表" />
                        <vort-tab-pane tab-key="release-plan" tab="发布计划" />
                    </vort-tabs>
                </div>
                <vort-button variant="primary" @click="handleAddVersion">
                    <Plus :size="14" class="mr-1" /> 新建版本
                </vort-button>
            </div>
            <div v-if="activeTab === 'version-list'" class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                    <vort-input-search
                        v-model="filterParams.keyword"
                        placeholder="版本号/名称"
                        allow-clear
                        class="flex-1 sm:w-[200px]"
                        @search="onSearchSubmit"
                        @keyup.enter="onSearchSubmit"
                    />
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                    <vort-select v-model="filterParams.status" placeholder="全部" allow-clear class="flex-1 sm:w-[120px]" @change="onSearchSubmit">
                        <vort-select-option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">负责人</span>
                    <vort-select v-model="filterParams.owner_id" placeholder="全部" allow-clear class="flex-1 sm:w-[140px]" @change="onSearchSubmit">
                        <vort-select-option v-for="m in memberOptions" :key="m.id" :value="m.id">{{ m.name }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2">
                    <vort-button variant="primary" @click="onSearchSubmit">查询</vort-button>
                    <vort-button @click="resetParams">重置</vort-button>
                </div>
            </div>
        </div>

        <!-- 表格卡片 -->
        <div v-if="activeTab === 'version-list'" class="bg-white rounded-xl p-6">
            <vort-table :data-source="listData" :loading="loading" :pagination="false">
                <vort-table-column label="版本号" :width="120">
                    <template #default="{ row }">
                        <span class="inline-flex items-center px-2 py-0.5 rounded bg-blue-50 text-blue-600 text-xs font-medium">
                            {{ row.name }}
                        </span>
                    </template>
                </vort-table-column>

                <vort-table-column label="版本名称" :min-width="220">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-800">{{ row.description || "-" }}</span>
                    </template>
                </vort-table-column>

                <vort-table-column label="阶段" :width="120">
                    <template #default="{ row }">
                        <vort-tag :color="statusColorMap[row.status] || 'default'">
                            {{ stageLabelMap[row.status] || statusLabels[row.status] || row.status }}
                        </vort-tag>
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
                            {{ formatDate((row.planned_release_at || row.release_date || null) as any) }} / {{ formatDate((row.actual_release_at || null) as any) }}
                        </span>
                    </template>
                </vort-table-column>

                <vort-table-column label="进度" :width="170">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2">
                            <div class="w-[110px] h-1.5 rounded-full bg-gray-100 overflow-hidden">
                                <div class="h-full rounded-full bg-blue-500 transition-all" :style="{ width: `${getVersionProgress(row)}%` }" />
                            </div>
                            <span class="text-xs text-gray-500">{{ getVersionProgress(row) }}%</span>
                        </div>
                    </template>
                </vort-table-column>

                <vort-table-column label="操作" :width="170" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2 whitespace-nowrap">
                            <a v-if="row.status === 'planning'" class="text-sm text-blue-600 cursor-pointer" @click="handleReleaseVersion(row)">发布</a>
                            <vort-divider v-if="row.status === 'planning'" type="vertical" />
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEditVersion(row)">编辑</a>
                            <vort-divider type="vertical" />
                            <vort-popconfirm title="确认删除该版本？" @confirm="handleDeleteVersion(row)">
                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                            </vort-popconfirm>
                        </div>
                    </template>
                </vort-table-column>
            </vort-table>

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

        <!-- 发布计划占位 -->
        <div v-if="activeTab === 'release-plan'" class="bg-white rounded-xl p-6">
            <div class="py-12 text-center text-sm text-gray-400">发布计划模块待上线</div>
        </div>

        <!-- 新建/编辑版本弹窗 -->
        <vort-dialog
            :open="createDialogOpen"
            :title="versionDialogMode === 'edit' ? '编辑版本' : '新建版本'"
            :width="700"
            :centered="true"
            @update:open="createDialogOpen = $event"
        >
            <vort-form label-width="90px">
                <div class="grid grid-cols-2 gap-x-4">
                    <vort-form-item label="版本号" required>
                        <vort-input v-model="createVersionForm.version_no" placeholder="请输入版本号" />
                    </vort-form-item>
                    <vort-form-item label="标题" required>
                        <vort-input v-model="createVersionForm.title" placeholder="请输入标题" />
                    </vort-form-item>
                </div>
                <div class="grid grid-cols-2 gap-x-4">
                    <vort-form-item label="负责人" required>
                        <vort-select v-model="createVersionForm.owner_id" placeholder="请选择负责人" class="w-full">
                            <vort-select-option v-for="m in memberOptions" :key="m.id" :value="m.id">{{ m.name }}</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                    <vort-form-item label="发布时间">
                        <vort-date-picker
                            v-model="createVersionForm.release_date"
                            value-format="YYYY-MM-DD"
                            placeholder="请选择发布时间"
                            class="w-full"
                        />
                    </vort-form-item>
                </div>
                <vort-form-item label="发布日志">
                    <vort-textarea v-model="createVersionForm.release_log" placeholder="请输入发布日志" :rows="6" />
                </vort-form-item>
            </vort-form>

            <template #footer>
                <div class="flex justify-end gap-3">
                    <vort-button @click="createDialogOpen = false">取消</vort-button>
                    <vort-button v-if="versionDialogMode === 'create'" @click="handleCreateVersion(true)">新建并继续</vort-button>
                    <vort-button variant="primary" :loading="createFormLoading" @click="handleCreateVersion(false)">确定</vort-button>
                </div>
            </template>
        </vort-dialog>
    </div>
</template>
