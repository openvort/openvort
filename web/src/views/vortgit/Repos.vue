<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { useCrudPage } from "@/hooks";
import {
    getVortgitRepos, createVortgitRepo, updateVortgitRepo, deleteVortgitRepo,
    getVortgitProviders, getVortgitRemoteRepos, importVortgitRepos, syncVortgitRepo,
    getVortgitRepoCommits, getVortgitRepoBranches,
    getVortflowProjects,
} from "@/api";
import { Plus, RefreshCw, Download, GitCommit, GitBranch } from "lucide-vue-next";
import { message } from "@/components/vort/message";

interface RepoItem {
    id: string;
    provider_id: string;
    project_id: string | null;
    name: string;
    full_name: string;
    clone_url: string;
    description: string;
    language: string;
    repo_type: string;
    is_private: boolean;
    default_branch: string;
    last_synced_at: string | null;
    created_at: string;
}

interface CommitItem {
    sha: string;
    message: string;
    author_name: string;
    author_email: string;
    authored_date: string;
}

interface BranchItem {
    name: string;
    is_default: boolean;
    last_commit_sha: string;
}

type FilterParams = { page: number; size: number; keyword: string; provider_id: string; project_id: string };

const repoTypeOptions = [
    { label: "前端", value: "frontend" },
    { label: "后端", value: "backend" },
    { label: "移动端", value: "mobile" },
    { label: "文档", value: "docs" },
    { label: "基础设施", value: "infra" },
    { label: "其他", value: "other" },
];
const repoTypeLabel = (val: string) => repoTypeOptions.find(o => o.value === val)?.label || val;
const repoTypeColorMap: Record<string, string> = {
    frontend: "blue", backend: "green", mobile: "purple", docs: "cyan", infra: "orange", other: "default"
};

const langColorMap: Record<string, string> = {
    JavaScript: "processing", TypeScript: "blue", Python: "green", Java: "orange", Go: "cyan", Rust: "volcano",
};

const providers = ref<any[]>([]);
const projects = ref<any[]>([]);

const loadProviders = async () => {
    try {
        const res = await getVortgitProviders();
        providers.value = (res as any).items || [];
    } catch { /* ignore */ }
};
const loadProjects = async () => {
    try {
        const res = await getVortflowProjects({ page: 1, page_size: 200 });
        projects.value = (res as any).items || [];
    } catch { /* ignore */ }
};

const providerName = (id: string) => providers.value.find(p => p.id === id)?.name || "—";
const projectName = (id: string | null) => {
    if (!id) return "";
    return projects.value.find(p => p.id === id)?.name || "";
};

const fetchList = async (params: FilterParams) => {
    const res = await getVortgitRepos({
        provider_id: params.provider_id || undefined,
        project_id: params.project_id || undefined,
        keyword: params.keyword || undefined,
        page: params.page,
        page_size: params.size,
    });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const { listData, loading, total, filterParams, showPagination, loadData, onSearchSubmit, resetParams } =
    useCrudPage<RepoItem, FilterParams>({
        api: fetchList,
        defaultParams: { page: 1, size: 20, keyword: "", provider_id: "", project_id: "" },
    });

// ---- Drawer ----
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"view" | "edit" | "add">("view");
const currentRow = ref<Partial<RepoItem>>({});
const saving = ref(false);
const viewTab = ref("info");

const commits = ref<CommitItem[]>([]);
const branches = ref<BranchItem[]>([]);
const commitsLoading = ref(false);
const branchesLoading = ref(false);

const handleView = (row: RepoItem) => {
    drawerMode.value = "view";
    drawerTitle.value = "仓库详情";
    currentRow.value = { ...row };
    viewTab.value = "info";
    commits.value = [];
    branches.value = [];
    drawerVisible.value = true;
};
const handleEdit = (row: RepoItem) => { drawerMode.value = "edit"; drawerTitle.value = "编辑仓库"; currentRow.value = { ...row }; drawerVisible.value = true; };

const loadCommits = async () => {
    if (!currentRow.value.id || commitsLoading.value) return;
    commitsLoading.value = true;
    try {
        const res = await getVortgitRepoCommits(currentRow.value.id, { per_page: 30 });
        commits.value = (res as any).items || [];
    } catch { commits.value = []; }
    finally { commitsLoading.value = false; }
};

const loadBranches = async () => {
    if (!currentRow.value.id || branchesLoading.value) return;
    branchesLoading.value = true;
    try {
        const res = await getVortgitRepoBranches(currentRow.value.id);
        branches.value = (res as any).items || [];
    } catch { branches.value = []; }
    finally { branchesLoading.value = false; }
};

watch(viewTab, (tab) => {
    if (tab === "commits" && commits.value.length === 0) loadCommits();
    if (tab === "branches" && branches.value.length === 0) loadBranches();
});

const formatDate = (dateStr: string) => {
    if (!dateStr) return "—";
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
};

const shortSha = (sha: string) => sha ? sha.slice(0, 8) : "";
const commitFirstLine = (msg: string) => msg ? msg.split("\n")[0].slice(0, 80) : "";

const handleSave = async () => {
    const data = currentRow.value;
    saving.value = true;
    try {
        await updateVortgitRepo(data.id!, {
            name: data.name,
            description: data.description,
            repo_type: data.repo_type,
            project_id: data.project_id || "",
        });
        message.success("更新成功");
        drawerVisible.value = false;
        loadData();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "操作失败");
    } finally {
        saving.value = false;
    }
};

const handleDelete = async (row: RepoItem) => {
    try {
        await deleteVortgitRepo(row.id);
        message.success("已删除");
        loadData();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "删除失败");
    }
};

const handleSync = async (row: RepoItem) => {
    try {
        await syncVortgitRepo(row.id);
        message.success("同步成功");
        loadData();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "同步失败");
    }
};

// ---- Import Dialog ----
const importVisible = ref(false);
const importProviderId = ref("");
const importSearch = ref("");
const importLoading = ref(false);
const remoteRepos = ref<any[]>([]);
const selectedImports = ref<Set<string>>(new Set());
const importRepoTypes = ref<Record<string, string>>({});
const importProjectIds = ref<Record<string, string>>({});
const importing = ref(false);

const handleOpenImport = () => {
    importProviderId.value = providers.value[0]?.id || "";
    remoteRepos.value = [];
    selectedImports.value = new Set();
    importVisible.value = true;
};

const fetchRemoteRepos = async () => {
    if (!importProviderId.value) return;
    importLoading.value = true;
    try {
        const res = await getVortgitRemoteRepos(importProviderId.value, { page: 1, per_page: 50, search: importSearch.value });
        remoteRepos.value = (res as any).items || [];
    } catch (e: any) {
        message.error("获取远程仓库失败");
    } finally {
        importLoading.value = false;
    }
};

const toggleImportSelect = (fullName: string) => {
    if (selectedImports.value.has(fullName)) {
        selectedImports.value.delete(fullName);
    } else {
        selectedImports.value.add(fullName);
    }
};

const doImport = async () => {
    if (selectedImports.value.size === 0) {
        message.warning("请选择要导入的仓库");
        return;
    }
    importing.value = true;
    try {
        const repos = Array.from(selectedImports.value).map(fn => ({
            full_name: fn,
            project_id: importProjectIds.value[fn] || undefined,
            repo_type: importRepoTypes.value[fn] || "other",
        }));
        const res = await importVortgitRepos({ provider_id: importProviderId.value, repos });
        message.success(`成功导入 ${(res as any).imported || 0} 个仓库`);
        importVisible.value = false;
        loadData();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "导入失败");
    } finally {
        importing.value = false;
    }
};

loadProviders();
loadProjects();
loadData();
</script>

<template>
    <div class="space-y-4">
        <!-- Search card -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-2">
                <h3 class="text-base font-medium text-gray-800">代码仓库</h3>
                <div class="flex items-center gap-2">
                    <vort-button @click="handleOpenImport">
                        <Download :size="14" class="mr-1" /> 导入仓库
                    </vort-button>
                </div>
            </div>
            <p class="text-sm text-gray-400 mb-4">从已接入的 Git 平台导入仓库，可关联 VortFlow 项目进行需求追踪，并通过 AI 完成编码、提交与 PR 创建。</p>
            <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                    <vort-input-search v-model="filterParams.keyword" placeholder="搜索仓库..." allow-clear class="flex-1 sm:w-[220px]" @search="onSearchSubmit" @keyup.enter="onSearchSubmit" />
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">平台</span>
                    <vort-select v-model="filterParams.provider_id" placeholder="全部" allow-clear class="flex-1 sm:w-[150px]" @change="onSearchSubmit">
                        <vort-select-option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">项目</span>
                    <vort-select v-model="filterParams.project_id" placeholder="全部" allow-clear class="flex-1 sm:w-[150px]" @change="onSearchSubmit">
                        <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2">
                    <vort-button variant="primary" @click="onSearchSubmit">查询</vort-button>
                    <vort-button @click="resetParams">重置</vort-button>
                </div>
            </div>
        </div>

        <!-- Repo cards -->
        <div class="bg-white rounded-xl p-6">
            <vort-spin :spinning="loading">
                <div v-if="listData.length === 0 && !loading" class="py-12 text-center text-gray-400">
                    暂无仓库，请先导入
                </div>
                <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div v-for="repo in listData" :key="repo.id" class="border border-gray-100 rounded-xl p-4 hover:shadow-md transition-shadow cursor-pointer" @click="handleView(repo)">
                        <div class="flex items-start justify-between mb-2">
                            <div class="flex-1 min-w-0">
                                <h4 class="font-medium text-gray-800 truncate">{{ repo.name }}</h4>
                                <p class="text-xs text-gray-400 truncate">{{ repo.full_name }}</p>
                            </div>
                            <vort-tag v-if="repo.is_private" size="small" color="default">私有</vort-tag>
                        </div>
                        <p class="text-xs text-gray-500 line-clamp-2 mb-3 min-h-[2rem]">{{ repo.description || '暂无描述' }}</p>
                        <div class="flex items-center gap-2 flex-wrap">
                            <vort-tag v-if="repo.language" size="small" :color="langColorMap[repo.language] || 'default'">{{ repo.language }}</vort-tag>
                            <vort-tag size="small" :color="repoTypeColorMap[repo.repo_type] || 'default'">{{ repoTypeLabel(repo.repo_type) }}</vort-tag>
                            <span v-if="projectName(repo.project_id)" class="text-xs text-blue-500">{{ projectName(repo.project_id) }}</span>
                            <span v-else class="text-xs text-orange-400">未关联项目</span>
                        </div>
                    </div>
                </div>
            </vort-spin>

            <div v-if="showPagination" class="flex justify-end mt-4">
                <vort-pagination v-model:current="filterParams.page" v-model:page-size="filterParams.size" :total="total" show-total-info show-size-changer @change="loadData" />
            </div>
        </div>

        <!-- View/Edit Drawer -->
        <vort-drawer v-model:open="drawerVisible" :title="drawerTitle" :width="620">
            <div v-if="drawerMode === 'view'">
                <vort-tabs v-model="viewTab">
                    <vort-tab-pane key="info" tab="基本信息">
                        <div class="space-y-4 pt-2">
                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div><span class="text-sm text-gray-400">仓库名</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.name }}</div></div>
                                <div><span class="text-sm text-gray-400">完整路径</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.full_name }}</div></div>
                                <div><span class="text-sm text-gray-400">语言</span><div class="mt-1"><vort-tag v-if="currentRow.language" :color="langColorMap[currentRow.language!] || 'default'">{{ currentRow.language }}</vort-tag><span v-else class="text-sm text-gray-400">—</span></div></div>
                                <div><span class="text-sm text-gray-400">类型</span><div class="mt-1"><vort-tag :color="repoTypeColorMap[currentRow.repo_type!] || 'default'">{{ repoTypeLabel(currentRow.repo_type || 'other') }}</vort-tag></div></div>
                                <div><span class="text-sm text-gray-400">默认分支</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.default_branch }}</div></div>
                                <div><span class="text-sm text-gray-400">平台</span><div class="text-sm text-gray-800 mt-1">{{ providerName(currentRow.provider_id!) }}</div></div>
                                <div><span class="text-sm text-gray-400">关联项目</span><div class="text-sm mt-1" :class="projectName(currentRow.project_id!) ? 'text-blue-600' : 'text-orange-400'">{{ projectName(currentRow.project_id!) || '未关联' }}</div></div>
                                <div><span class="text-sm text-gray-400">克隆地址</span><div class="text-sm text-gray-800 mt-1 break-all">{{ currentRow.clone_url }}</div></div>
                            </div>
                            <div class="sm:col-span-2"><span class="text-sm text-gray-400">描述</span><div class="text-sm text-gray-800 mt-1 whitespace-pre-wrap">{{ currentRow.description || '暂无描述' }}</div></div>
                            <div class="flex gap-3 mt-4">
                                <vort-button @click="handleEdit(currentRow as RepoItem)">编辑</vort-button>
                                <vort-button @click="handleSync(currentRow as RepoItem)"><RefreshCw :size="14" class="mr-1" />同步</vort-button>
                                <vort-popconfirm title="确认删除该仓库？" @confirm="handleDelete(currentRow as RepoItem)">
                                    <vort-button><span class="text-red-500">删除</span></vort-button>
                                </vort-popconfirm>
                            </div>
                        </div>
                    </vort-tab-pane>

                    <vort-tab-pane key="commits" tab="提交记录">
                        <div class="pt-2">
                            <div class="flex items-center justify-between mb-3">
                                <span class="text-sm text-gray-500">最近 30 条提交</span>
                                <vort-button size="small" :loading="commitsLoading" @click="loadCommits">
                                    <RefreshCw :size="12" class="mr-1" />刷新
                                </vort-button>
                            </div>
                            <vort-spin :spinning="commitsLoading">
                                <div v-if="commits.length === 0 && !commitsLoading" class="py-8 text-center text-gray-400 text-sm">暂无提交记录</div>
                                <div v-else class="space-y-1">
                                    <div v-for="c in commits" :key="c.sha" class="flex items-start gap-3 py-2.5 px-3 rounded-lg hover:bg-gray-50">
                                        <div class="mt-0.5 shrink-0">
                                            <GitCommit :size="14" class="text-gray-400" />
                                        </div>
                                        <div class="flex-1 min-w-0">
                                            <div class="text-sm text-gray-800 truncate">{{ commitFirstLine(c.message) }}</div>
                                            <div class="flex items-center gap-3 mt-1">
                                                <code class="text-xs text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">{{ shortSha(c.sha) }}</code>
                                                <span class="text-xs text-gray-400">{{ c.author_name }}</span>
                                                <span class="text-xs text-gray-400">{{ formatDate(c.authored_date) }}</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </vort-spin>
                        </div>
                    </vort-tab-pane>

                    <vort-tab-pane key="branches" tab="分支">
                        <div class="pt-2">
                            <div class="flex items-center justify-between mb-3">
                                <span class="text-sm text-gray-500">{{ branches.length }} 个分支</span>
                                <vort-button size="small" :loading="branchesLoading" @click="loadBranches">
                                    <RefreshCw :size="12" class="mr-1" />刷新
                                </vort-button>
                            </div>
                            <vort-spin :spinning="branchesLoading">
                                <div v-if="branches.length === 0 && !branchesLoading" class="py-8 text-center text-gray-400 text-sm">暂无分支信息</div>
                                <div v-else class="space-y-1">
                                    <div v-for="b in branches" :key="b.name" class="flex items-center gap-3 py-2.5 px-3 rounded-lg hover:bg-gray-50">
                                        <GitBranch :size="14" class="text-gray-400 shrink-0" />
                                        <span class="text-sm text-gray-800 flex-1">{{ b.name }}</span>
                                        <vort-tag v-if="b.is_default" size="small" color="green">默认</vort-tag>
                                        <code v-if="b.last_commit_sha" class="text-xs text-gray-400">{{ shortSha(b.last_commit_sha) }}</code>
                                    </div>
                                </div>
                            </vort-spin>
                        </div>
                    </vort-tab-pane>
                </vort-tabs>
            </div>
            <template v-else>
                <vort-form label-width="100px">
                    <vort-form-item label="仓库名">
                        <vort-input v-model="currentRow.name" />
                    </vort-form-item>
                    <vort-form-item label="描述">
                        <vort-textarea v-model="currentRow.description" :rows="3" />
                    </vort-form-item>
                    <vort-form-item label="仓库类型">
                        <vort-select v-model="currentRow.repo_type">
                            <vort-select-option v-for="opt in repoTypeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                    <vort-form-item label="关联项目">
                        <vort-select v-model="currentRow.project_id" placeholder="选择项目" allow-clear>
                            <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                </vort-form>
                <div class="flex justify-end gap-3 mt-6">
                    <vort-button @click="drawerVisible = false">取消</vort-button>
                    <vort-button variant="primary" :loading="saving" @click="handleSave">确定</vort-button>
                </div>
            </template>
        </vort-drawer>

        <!-- Import Dialog -->
        <vort-dialog :open="importVisible" title="从平台导入仓库" :width="700" @update:open="importVisible = $event">
            <div class="space-y-4">
                <div class="flex items-center gap-3">
                    <vort-select v-model="importProviderId" placeholder="选择平台" class="w-[200px]">
                        <vort-select-option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                    </vort-select>
                    <vort-input-search v-model="importSearch" placeholder="搜索仓库..." class="flex-1" @search="fetchRemoteRepos" @keyup.enter="fetchRemoteRepos" />
                    <vort-button variant="primary" :loading="importLoading" @click="fetchRemoteRepos">获取</vort-button>
                </div>
                <div v-if="remoteRepos.length > 0" class="max-h-[400px] overflow-y-auto space-y-2">
                    <div v-for="repo in remoteRepos" :key="repo.full_name" class="flex items-center gap-3 p-3 border border-gray-100 rounded-lg hover:bg-gray-50">
                        <vort-checkbox :model-value="selectedImports.has(repo.full_name)" @update:model-value="toggleImportSelect(repo.full_name)" />
                        <div class="flex-1 min-w-0">
                            <div class="text-sm font-medium text-gray-800 truncate">{{ repo.full_name }}</div>
                            <div class="text-xs text-gray-400 truncate">{{ repo.description || '无描述' }}</div>
                        </div>
                        <vort-select v-if="selectedImports.has(repo.full_name)" v-model="importRepoTypes[repo.full_name]" placeholder="类型" class="w-[100px]" size="small">
                            <vort-select-option v-for="opt in repoTypeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                        </vort-select>
                        <vort-select v-if="selectedImports.has(repo.full_name)" v-model="importProjectIds[repo.full_name]" placeholder="关联项目" allow-clear class="w-[140px]" size="small">
                            <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                        </vort-select>
                    </div>
                </div>
                <div v-else-if="!importLoading" class="py-8 text-center text-gray-400 text-sm">
                    点击「获取」从平台拉取仓库列表
                </div>
            </div>
            <template #footer>
                <div class="flex justify-end gap-3">
                    <vort-button @click="importVisible = false">取消</vort-button>
                    <vort-button variant="primary" :loading="importing" :disabled="selectedImports.size === 0" @click="doImport">
                        导入 {{ selectedImports.size > 0 ? `(${selectedImports.size})` : '' }}
                    </vort-button>
                </div>
            </template>
        </vort-dialog>
    </div>
</template>
