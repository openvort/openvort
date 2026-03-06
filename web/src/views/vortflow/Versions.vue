<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from "vue";
import { Plus, Settings, Trash2, Rocket, MoreHorizontal, UserRound, Search } from "lucide-vue-next";
import { message } from "@openvort/vort-ui";
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
const ownerDropdownOpen = ref(false);
const ownerKeyword = ref("");
const ownerGroupOpen = ref(true);
const ownerDropdownRef = ref<HTMLElement | null>(null);
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

const statusColorMap: Record<string, string> = {
    planning: "default", released: "success", archived: "default"
};
const statusLabels: Record<string, string> = {
    planning: "规划中", released: "已发布", archived: "已归档"
};

const filteredVersions = computed(() => {
    let list = versions.value;
    if (selectedOwnerId.value === "__unassigned__") {
        list = list.filter(v => !getVersionOwnerId(v));
    } else if (selectedOwnerId.value) {
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

const filteredOwnerOptions = computed(() => {
    const kw = ownerKeyword.value.trim().toLowerCase();
    if (!kw) return memberOptions.value;
    return memberOptions.value.filter(item => item.name.toLowerCase().includes(kw));
});

const selectedOwnerText = computed(() => {
    if (!selectedOwnerId.value) return "负责人";
    if (selectedOwnerId.value === "__unassigned__") return "未指派";
    return memberOptions.value.find(m => m.id === selectedOwnerId.value)?.name || "负责人";
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
    return String(item.owner_id || "").trim();
};

const getMemberNameById = (memberId: string): string => {
    if (!memberId) return "待指派";
    return memberOptions.value.find(m => m.id === memberId)?.name || "待指派";
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

const handleAddVersion = () => {
    versionDialogMode.value = "create";
    editingVersionId.value = "";
    editingVersionStatus.value = "planning";
    createVersionForm.value = {
        version_no: "",
        title: "",
        owner_id: memberOptions.value[0]?.id || "",
        release_date: "",
        release_log: "",
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
    if (!String(data.version_no || "").trim()) {
        message.warning("版本号必填");
        return;
    }
    if (!String(data.title || "").trim()) {
        message.warning("标题必填");
        return;
    }
    if (!String(data.owner_id || "").trim()) {
        message.warning("负责人必填");
        return;
    }
    createFormLoading.value = true;
    try {
        if (versionDialogMode.value === "create") {
            await createVortflowVersion({
                project_id: projectId,
                name: String(data.version_no).trim(),
                description: String(data.title).trim(),
                owner_id: data.owner_id || undefined,
                planned_release_at: data.release_date || undefined,
                progress: 0,
                status: "planning",
            });
            await loadData();
            if (andContinue) {
                createVersionForm.value = {
                    version_no: "",
                    title: "",
                    owner_id: data.owner_id || "",
                    release_date: "",
                    release_log: "",
                };
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
            await loadData();
            createDialogOpen.value = false;
        }
    } finally {
        createFormLoading.value = false;
    }
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

const getVersionProgress = (row: VersionItem): number => {
    const explicit = Number(row.progress);
    if (Number.isFinite(explicit) && explicit >= 0) return Math.min(100, Math.max(0, explicit));
    return progressByStatus[row.status] ?? 0;
};

const resetFilters = () => {
    selectedOwnerId.value = "";
    keyword.value = "";
};

const selectOwner = (value: string) => {
    selectedOwnerId.value = value;
    ownerDropdownOpen.value = false;
};

const clearOwnerFilter = () => {
    selectedOwnerId.value = "";
    ownerDropdownOpen.value = false;
};

const selectUnassignedOwner = () => {
    selectedOwnerId.value = "__unassigned__";
    ownerDropdownOpen.value = false;
};

const ownerAvatarClass = (name: string) => {
    const palette = [
        "bg-emerald-500", "bg-sky-500", "bg-indigo-500", "bg-violet-500",
        "bg-amber-500", "bg-rose-500", "bg-teal-500", "bg-cyan-500",
    ];
    const seed = name.split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
    return palette[seed % palette.length];
};

const onDocumentClick = (e: MouseEvent) => {
    const target = e.target as Node;
    if (ownerDropdownRef.value && !ownerDropdownRef.value.contains(target)) ownerDropdownOpen.value = false;
};

onMounted(async () => {
    await loadData();
    document.addEventListener("click", onDocumentClick);
});

onBeforeUnmount(() => {
    document.removeEventListener("click", onDocumentClick);
});
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-6">
                    <h3 class="text-base font-medium text-gray-800 whitespace-nowrap leading-6">版本</h3>
                    <vort-tabs v-model:activeKey="activeTab" :hide-content="true">
                        <vort-tab-pane tab-key="version-list" tab="版本列表" />
                        <vort-tab-pane tab-key="release-plan" tab="发布计划" />
                    </vort-tabs>
                </div>
                <vort-button v-if="activeTab === 'version-list'" variant="primary" @click="handleAddVersion">
                    <Plus :size="14" class="mr-1" /> 新建版本
                </vort-button>
            </div>

            <div v-if="activeTab === 'version-list'" class="mt-4">
                <vort-spin :spinning="loading">
                    <div class="bg-white rounded-xl px-5 py-3 mb-4">
                        <div class="flex flex-wrap items-center gap-3 text-sm">
                            <div class="text-gray-500 mr-2">
                                共 <span class="text-gray-800 font-medium">{{ filteredVersions.length }}</span> 项
                            </div>
                            <div class="relative w-[220px]">
                                <vort-input
                                    v-model="keyword"
                                    placeholder="请输入版本号/名称"
                                    class="w-full"
                                >
                                    <template #prefix>
                                        <Search :size="14" class="text-gray-400" />
                                    </template>
                                </vort-input>
                            </div>
                            <div ref="ownerDropdownRef" class="relative w-[130px]" @click.stop>
                                <button
                                    class="h-8 w-full px-3 rounded border border-slate-300 bg-white text-left flex items-center justify-between transition-colors hover:border-slate-400"
                                    :class="{ 'border-blue-500 bg-white': ownerDropdownOpen }"
                                    @click.stop="ownerDropdownOpen = !ownerDropdownOpen"
                                >
                                    <span
                                        class="text-sm truncate"
                                        :class="selectedOwnerText === '负责人' ? 'text-gray-400' : 'text-gray-700'"
                                    >{{ selectedOwnerText }}</span>
                                    <span class="text-gray-400 text-xs">▾</span>
                                </button>
                                <div v-if="ownerDropdownOpen" class="absolute z-30 mt-2 w-[270px] bg-white border border-gray-200 rounded-lg shadow-lg p-2.5 owner-dropdown-panel">
                                    <div class="relative mb-2">
                                        <input
                                            v-model="ownerKeyword"
                                            placeholder="搜索..."
                                            class="w-full h-8 pl-2.5 pr-7 border border-gray-300 rounded-md text-sm"
                                        />
                                        <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                                    </div>
                                    <div class="max-h-[300px] overflow-auto space-y-1 owner-list">
                                        <button
                                            class="w-full text-left px-2 py-1.5 rounded-md text-sm text-slate-700 hover:bg-gray-50"
                                            :class="{ 'bg-blue-50 text-blue-700': !selectedOwnerId }"
                                            @click="clearOwnerFilter"
                                        >
                                            全部
                                        </button>
                                        <button
                                            class="w-full text-left px-2 py-1.5 rounded-md text-sm text-slate-700 hover:bg-gray-50"
                                            :class="{ 'bg-blue-50 text-blue-700': selectedOwnerId === '__unassigned__' }"
                                            @click="selectUnassignedOwner"
                                        >
                                            未指派
                                        </button>
                                        <div class="mt-1">
                                            <button
                                                class="w-full flex items-center justify-between px-2 py-1.5 rounded-md bg-slate-100 text-sm text-slate-700"
                                                @click="ownerGroupOpen = !ownerGroupOpen"
                                            >
                                                <span>全部成员（{{ filteredOwnerOptions.length }}）</span>
                                                <span class="text-base leading-none">{{ ownerGroupOpen ? "⌃" : "⌄" }}</span>
                                            </button>
                                        </div>
                                        <button
                                            v-for="member in (ownerGroupOpen ? filteredOwnerOptions : [])"
                                            :key="member.id"
                                            class="w-full text-left px-2 py-1.5 rounded-md text-sm hover:bg-gray-50 flex items-center gap-2"
                                            :class="{ 'bg-blue-50 text-blue-700': selectedOwnerId === member.id }"
                                            @click="selectOwner(member.id)"
                                        >
                                            <span
                                                class="w-5 h-5 rounded-full text-white text-[11px] flex items-center justify-center shrink-0"
                                                :class="ownerAvatarClass(member.name)"
                                            >
                                                {{ member.name.slice(0, 1) }}
                                            </span>
                                            <span class="truncate text-slate-700">{{ member.name }}</span>
                                        </button>
                                        <div v-if="filteredOwnerOptions.length === 0" class="px-2 py-2 text-xs text-gray-400">暂无匹配成员</div>
                                    </div>
                                </div>
                            </div>
                            <div class="ml-auto flex items-center gap-2">
                                <vort-button @click="resetFilters">重置</vort-button>
                            </div>
                        </div>
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
                                    {{ row.description || "-" }}
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
                                    {{ formatDate((row.planned_release_at || row.release_date || null) as any) }} / {{ formatDate((row.actual_release_at || null) as any) }}
                                </span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="进度" :width="170">
                            <template #default="{ row }">
                                <div class="flex items-center gap-2">
                                    <div class="w-[110px] h-1.5 rounded-full bg-gray-100 overflow-hidden">
                                        <div
                                            class="h-full rounded-full bg-blue-500 transition-all"
                                            :style="{ width: `${getVersionProgress(row)}%` }"
                                        />
                                    </div>
                                    <span class="text-xs text-gray-500">{{ getVersionProgress(row) }}%</span>
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

        <!-- 新建版本弹窗 -->
        <vort-dialog
            :open="createDialogOpen"
            :title="versionDialogMode === 'edit' ? '编辑版本' : '新建版本'"
            :width="1000"
            :centered="true"
            @update:open="createDialogOpen = $event"
        >
            <div class="space-y-4 px-2 version-create-dialog">
                <div class="version-create-row version-create-row-top">
                    <div class="version-field">
                        <div class="text-sm font-semibold text-slate-700 mb-2 whitespace-nowrap">版本号 <span class="text-red-500">*</span></div>
                        <vort-input v-model="createVersionForm.version_no" placeholder="请输入版本号" class="w-full" />
                        <div v-if="!createVersionForm.version_no" class="text-xs text-red-500 mt-1">版本号必填</div>
                    </div>
                    <div class="version-field">
                        <div class="text-sm font-semibold text-slate-700 mb-2 whitespace-nowrap">标题</div>
                        <vort-input v-model="createVersionForm.title" placeholder="请输入标题" class="w-full" />
                    </div>
                </div>

                <div class="version-create-row version-create-row-mid">
                    <div class="version-field">
                        <div class="text-sm font-semibold text-slate-700 mb-2 whitespace-nowrap">负责人 <span class="text-red-500">*</span></div>
                        <vort-select v-model="createVersionForm.owner_id" placeholder="请选择负责人" class="w-full">
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
                    </div>
                    <div class="version-field">
                        <div class="text-sm font-semibold text-slate-700 mb-2 whitespace-nowrap">发布时间</div>
                        <vort-date-picker
                            v-model="createVersionForm.release_date"
                            value-format="YYYY-MM-DD"
                            placeholder="请选择发布时间"
                            class="w-full"
                        />
                    </div>
                </div>

                <div class="version-field">
                    <div class="text-sm font-semibold text-slate-700 mb-2 whitespace-nowrap">发布日志</div>
                    <vort-textarea v-model="createVersionForm.release_log" placeholder="请输入发布日志" :rows="8" class="w-full" />
                </div>
            </div>

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

<style scoped>
:deep(.version-filter-select .vort-select-selector) {
    height: 32px;
    border: 1px solid transparent;
    background: #f8fafc;
    box-shadow: none;
}

:deep(.version-filter-select.vort-select-focused .vort-select-selector) {
    border-color: #3b82f6;
    background: #ffffff;
}

:deep(.version-filter-select .vort-select-selection-placeholder),
:deep(.version-filter-select .vort-select-selection-item) {
    white-space: nowrap;
}

.version-create-row {
    display: grid;
    gap: 16px;
}

.version-create-row-top {
    grid-template-columns: 220px minmax(0, 1fr);
}

.version-create-row-mid {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

.version-field {
    min-width: 0;
}
</style>
