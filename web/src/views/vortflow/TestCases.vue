<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from "vue";
import { Plus, Search, ChevronRight, ChevronDown, FolderOpen, Folder, MoreHorizontal, FolderPlus, Pencil, Trash2 } from "lucide-vue-next";
import { useCrudPage } from "@/hooks";
import { useVortFlowStore } from "@/stores";
import { message, Dropdown, DropdownMenuItem } from "@/components/vort";
import {
    getVortflowTestCases, deleteVortflowTestCase,
    getVortflowTestModules, createVortflowTestModule, updateVortflowTestModule, deleteVortflowTestModule,
} from "@/api";
import TestCaseEditDrawer from "./components/TestCaseEditDrawer.vue";
import TestCaseDetailDrawer from "./components/TestCaseDetailDrawer.vue";

const store = useVortFlowStore();
const currentProjectId = computed(() => store.selectedProjectId || "");

// ============ Module Tree ============

interface RawModule {
    id: string;
    name: string;
    parent_id: string | null;
    case_count: number;
}

interface FlatNode {
    id: string;
    name: string;
    parent_id: string | null;
    depth: number;
    case_count: number;
    hasChildren: boolean;
    expanded: boolean;
}

const rawModules = ref<RawModule[]>([]);
const expandedIds = ref<Set<string>>(new Set());
const selectedModuleId = ref("");
const moduleLoading = ref(false);

const moduleSearch = ref("");
const showModuleSearch = ref(false);

const addModuleParentId = ref<string | null>(null);
const addModuleName = ref("");
const showAddModule = ref(false);
const addModuleInputRef = ref<HTMLInputElement | null>(null);

const editModuleId = ref("");
const editModuleName = ref("");
const editModuleInputRef = ref<HTMLInputElement | null>(null);

const moduleMenuOpen = ref<Record<string, boolean>>({});

const flatNodes = computed<FlatNode[]>(() => {
    const map = new Map<string, RawModule>();
    const childMap = new Map<string, string[]>();
    for (const m of rawModules.value) {
        map.set(m.id, m);
        const pid = m.parent_id || "__root__";
        if (!childMap.has(pid)) childMap.set(pid, []);
        childMap.get(pid)!.push(m.id);
    }

    const kw = moduleSearch.value.trim().toLowerCase();

    const matchesSearch = (id: string): boolean => {
        if (!kw) return true;
        const mod = map.get(id);
        if (!mod) return false;
        if (mod.name.toLowerCase().includes(kw)) return true;
        const kids = childMap.get(id) || [];
        return kids.some((cid) => matchesSearch(cid));
    };

    const result: FlatNode[] = [];
    const walk = (parentId: string, depth: number) => {
        const children = childMap.get(parentId) || [];
        for (const id of children) {
            if (!matchesSearch(id)) continue;
            const mod = map.get(id)!;
            const hasChildren = (childMap.get(id) || []).length > 0;
            const expanded = kw ? true : expandedIds.value.has(id);
            result.push({ id: mod.id, name: mod.name, parent_id: mod.parent_id, depth, case_count: mod.case_count, hasChildren, expanded });
            if (expanded && hasChildren) {
                walk(id, depth + 1);
            }
        }
    };
    walk("__root__", 0);
    return result;
});

const totalCaseCount = computed(() => rawModules.value.reduce((s, m) => s + m.case_count, 0));

const loadModules = async () => {
    if (!currentProjectId.value) { rawModules.value = []; return; }
    moduleLoading.value = true;
    try {
        const res = await getVortflowTestModules({ project_id: currentProjectId.value });
        rawModules.value = (res as any)?.items || [];
        const parentIds = new Set(rawModules.value.filter((m) => m.parent_id).map((m) => m.parent_id!));
        for (const pid of parentIds) expandedIds.value.add(pid);
    } catch { rawModules.value = []; }
    finally { moduleLoading.value = false; }
};

const toggleExpand = (id: string) => {
    const next = new Set(expandedIds.value);
    if (next.has(id)) next.delete(id); else next.add(id);
    expandedIds.value = next;
};

const selectModule = (id: string) => {
    selectedModuleId.value = selectedModuleId.value === id ? "" : id;
    onSearchSubmit();
};

const toggleSearch = () => {
    showModuleSearch.value = !showModuleSearch.value;
    if (!showModuleSearch.value) moduleSearch.value = "";
};

// --- Add module ---
const startAddModule = (parentId: string | null = null) => {
    moduleMenuOpen.value = {};
    addModuleParentId.value = parentId;
    addModuleName.value = "";
    showAddModule.value = true;
    if (parentId) {
        const next = new Set(expandedIds.value);
        next.add(parentId);
        expandedIds.value = next;
    }
    nextTick(() => addModuleInputRef.value?.focus());
};

const confirmAddModule = async () => {
    if (!addModuleName.value.trim() || !currentProjectId.value) return;
    try {
        await createVortflowTestModule({ project_id: currentProjectId.value, parent_id: addModuleParentId.value, name: addModuleName.value.trim() });
        showAddModule.value = false;
        await loadModules();
    } catch { message.error("创建失败"); }
};

const cancelAddModule = () => { showAddModule.value = false; };

// --- Edit module ---
const startEditModule = (node: FlatNode) => {
    moduleMenuOpen.value = {};
    editModuleId.value = node.id;
    editModuleName.value = node.name;
    nextTick(() => editModuleInputRef.value?.focus());
};

const confirmEditModule = async () => {
    if (!editModuleName.value.trim() || !editModuleId.value) return;
    try {
        await updateVortflowTestModule(editModuleId.value, { name: editModuleName.value.trim() });
        editModuleId.value = "";
        await loadModules();
    } catch { message.error("更新失败"); }
};

const cancelEditModule = () => { editModuleId.value = ""; };

// --- Delete module ---
const handleDeleteModule = async (node: FlatNode) => {
    moduleMenuOpen.value = {};
    try {
        const res = await deleteVortflowTestModule(node.id);
        if ((res as any)?.error) { message.error((res as any).error); return; }
        if (selectedModuleId.value === node.id) selectedModuleId.value = "";
        message.success("已删除");
        await loadModules();
        loadData();
    } catch { message.error("删除失败"); }
};

// ============ Test Case List ============

interface TestCaseItem {
    id: string;
    title: string;
    module_name: string;
    case_type: string;
    priority: number;
    maintainer_name: string;
    created_at: string;
}

type FilterParams = { page: number; size: number; keyword: string; case_type: string; priority: string };

const CASE_TYPE_OPTIONS = [
    { label: "全部", value: "" },
    { label: "功能测试", value: "functional" },
    { label: "性能测试", value: "performance" },
    { label: "接口测试", value: "api" },
    { label: "UI 测试", value: "ui" },
    { label: "安全测试", value: "security" },
];

const PRIORITY_OPTIONS = [
    { label: "全部", value: "" },
    { label: "P0", value: "0" },
    { label: "P1", value: "1" },
    { label: "P2", value: "2" },
    { label: "P3", value: "3" },
];

const caseTypeLabel = (val: string) => CASE_TYPE_OPTIONS.find((o) => o.value === val)?.label || val;
const priorityLabel = (val: number) => `P${val}`;
const priorityColor = (val: number): string => ({ 0: "red", 1: "orange", 2: "blue", 3: "default" }[val] ?? "default");

const fetchList = async (params: FilterParams) => {
    const apiParams: Record<string, any> = { page: params.page, page_size: params.size };
    if (currentProjectId.value) apiParams.project_id = currentProjectId.value;
    if (selectedModuleId.value) apiParams.module_id = selectedModuleId.value;
    if (params.keyword) apiParams.keyword = params.keyword;
    if (params.case_type) apiParams.case_type = params.case_type;
    if (params.priority) apiParams.priority = parseInt(params.priority);
    const res = await getVortflowTestCases(apiParams);
    return { records: (res as any)?.items || [], total: (res as any)?.total || 0 };
};

const { listData, loading, total, filterParams, showPagination, loadData, onSearchSubmit, resetParams } =
    useCrudPage<TestCaseItem, FilterParams>({
        api: fetchList,
        defaultParams: { page: 1, size: 20, keyword: "", case_type: "", priority: "" },
    });

// ============ Drawers ============

const editDrawerOpen = ref(false);
const editMode = ref<"add" | "edit">("add");
const editCaseId = ref("");
const detailDrawerOpen = ref(false);
const detailCaseId = ref("");

const handleAdd = () => { editMode.value = "add"; editCaseId.value = ""; editDrawerOpen.value = true; };
const handleEdit = (row: TestCaseItem) => { editMode.value = "edit"; editCaseId.value = row.id; editDrawerOpen.value = true; };
const handleView = (row: TestCaseItem) => { detailCaseId.value = row.id; detailDrawerOpen.value = true; };
const handleDelete = async (row: TestCaseItem) => {
    try { await deleteVortflowTestCase(row.id); message.success("已删除"); loadData(); loadModules(); }
    catch { message.error("删除失败"); }
};
const onSaved = () => { editDrawerOpen.value = false; loadData(); loadModules(); };

watch(currentProjectId, () => { selectedModuleId.value = ""; loadModules(); loadData(); });
onMounted(() => { loadModules(); loadData(); });
</script>

<template>
    <div class="tc-layout">
        <!-- Left: Module Tree Sidebar -->
        <div class="tc-sidebar">
            <div class="tc-sidebar-header">
                <span class="tc-sidebar-title">功能模块</span>
                <div class="tc-sidebar-actions">
                    <button class="tc-sidebar-icon-btn" @click="toggleSearch" title="搜索模块">
                        <Search :size="14" />
                    </button>
                    <button class="tc-sidebar-add-btn" @click="startAddModule(null)">
                        <Plus :size="12" />
                        <span>添加</span>
                    </button>
                </div>
            </div>

            <div v-if="showModuleSearch" class="tc-sidebar-search">
                <Search :size="13" class="tc-sidebar-search-icon" />
                <input v-model="moduleSearch" class="tc-sidebar-search-input" placeholder="搜索模块..." autofocus />
            </div>

            <div class="tc-sidebar-body">
                <!-- All Cases root node -->
                <div class="tc-module-node tc-module-root" :class="{ active: !selectedModuleId }" @click="selectModule('')">
                    <FolderOpen :size="14" class="tc-module-icon" />
                    <span class="tc-module-label">全部用例</span>
                </div>

                <!-- Inline add at root level -->
                <div v-if="showAddModule && !addModuleParentId" class="tc-module-add-row" :style="{ paddingLeft: '12px' }">
                    <Folder :size="14" class="tc-module-icon" style="flex-shrink:0" />
                    <input
                        ref="addModuleInputRef"
                        v-model="addModuleName"
                        class="tc-inline-input"
                        placeholder="模块名称"
                        @keyup.enter="confirmAddModule"
                        @keyup.escape="cancelAddModule"
                        @blur="cancelAddModule"
                    />
                </div>

                <!-- Tree nodes -->
                <template v-for="node in flatNodes" :key="node.id">
                    <!-- Normal display mode -->
                    <div
                        v-if="editModuleId !== node.id"
                        class="tc-module-node"
                        :class="{ active: selectedModuleId === node.id }"
                        :style="{ paddingLeft: `${12 + node.depth * 20}px` }"
                        @click="selectModule(node.id)"
                    >
                        <button v-if="node.hasChildren" class="tc-module-expand" @click.stop="toggleExpand(node.id)">
                            <component :is="node.expanded ? ChevronDown : ChevronRight" :size="12" />
                        </button>
                        <span v-else class="tc-module-expand-placeholder" />
                        <component :is="node.expanded && node.hasChildren ? FolderOpen : Folder" :size="14" class="tc-module-icon" />
                        <span class="tc-module-label">{{ node.name }}</span>
                        <span class="tc-module-more-wrap" @click.stop>
                            <Dropdown v-model:open="moduleMenuOpen[node.id]" trigger="click" placement="bottomRight">
                                <button class="tc-module-more">
                                    <MoreHorizontal :size="14" />
                                </button>
                                <template #overlay>
                                <DropdownMenuItem @click="startAddModule(node.id)">
                                    <FolderPlus :size="14" class="text-gray-400" />
                                    <span>新建</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem @click="startEditModule(node)">
                                    <Pencil :size="14" class="text-gray-400" />
                                    <span>编辑</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem danger @click="handleDeleteModule(node)">
                                    <Trash2 :size="14" />
                                    <span>删除</span>
                                </DropdownMenuItem>
                                </template>
                            </Dropdown>
                        </span>
                    </div>

                    <!-- Inline edit mode -->
                    <div
                        v-else
                        class="tc-module-add-row"
                        :style="{ paddingLeft: `${12 + node.depth * 20 + 22}px` }"
                    >
                        <Folder :size="14" class="tc-module-icon" style="flex-shrink:0" />
                        <input
                            ref="editModuleInputRef"
                            v-model="editModuleName"
                            class="tc-inline-input"
                            @keyup.enter="confirmEditModule"
                            @keyup.escape="cancelEditModule"
                            @blur="confirmEditModule"
                        />
                    </div>

                    <!-- Inline add as child (after the parent node) -->
                    <div
                        v-if="showAddModule && addModuleParentId === node.id"
                        class="tc-module-add-row"
                        :style="{ paddingLeft: `${12 + (node.depth + 1) * 20 + 22}px` }"
                    >
                        <Folder :size="14" class="tc-module-icon" style="flex-shrink:0" />
                        <input
                            ref="addModuleInputRef"
                            v-model="addModuleName"
                            class="tc-inline-input"
                            placeholder="子模块名称"
                            @keyup.enter="confirmAddModule"
                            @keyup.escape="cancelAddModule"
                            @blur="cancelAddModule"
                        />
                    </div>
                </template>
            </div>
        </div>

        <!-- Right: Test Case Table -->
        <div class="tc-main">
            <div class="space-y-4">
                <div class="bg-white rounded-xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-base font-medium text-gray-800">测试用例</h3>
                        <vort-button variant="primary" @click="handleAdd">
                            <Plus :size="14" class="mr-1" /> 新建用例
                        </vort-button>
                    </div>
                    <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4 flex-wrap">
                        <div class="flex items-center gap-2 w-full sm:w-auto">
                            <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                            <vort-input-search v-model="filterParams.keyword" placeholder="搜索用例标题..." allow-clear class="flex-1 sm:w-[200px]" @search="onSearchSubmit" @keyup.enter="onSearchSubmit" />
                        </div>
                        <div class="flex items-center gap-2 w-full sm:w-auto">
                            <span class="text-sm text-gray-500 whitespace-nowrap">类型</span>
                            <vort-select v-model="filterParams.case_type" placeholder="全部" allow-clear class="flex-1 sm:w-[120px]" @change="onSearchSubmit">
                                <vort-select-option v-for="opt in CASE_TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                            </vort-select>
                        </div>
                        <div class="flex items-center gap-2 w-full sm:w-auto">
                            <span class="text-sm text-gray-500 whitespace-nowrap">优先级</span>
                            <vort-select v-model="filterParams.priority" placeholder="全部" allow-clear class="flex-1 sm:w-[100px]" @change="onSearchSubmit">
                                <vort-select-option v-for="opt in PRIORITY_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                            </vort-select>
                        </div>
                        <div class="flex items-center gap-2">
                            <vort-button variant="primary" @click="onSearchSubmit">查询</vort-button>
                            <vort-button @click="resetParams">重置</vort-button>
                        </div>
                    </div>
                </div>

                <div class="bg-white rounded-xl p-6">
                    <div class="text-sm text-gray-500 mb-3">共 {{ total }} 项</div>
                    <vort-table :data-source="listData" :loading="loading" :pagination="false" row-key="id">
                        <vort-table-column label="用例标题" :min-width="200">
                            <template #default="{ row }">
                                <a class="text-sm text-blue-600 cursor-pointer hover:underline" @click="handleView(row)">{{ row.title }}</a>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="功能模块" prop="module_name" :width="140" />
                        <vort-table-column label="用例类型" :width="100">
                            <template #default="{ row }">{{ caseTypeLabel(row.case_type) }}</template>
                        </vort-table-column>
                        <vort-table-column label="优先级" :width="80">
                            <template #default="{ row }">
                                <vort-tag :color="priorityColor(row.priority)" size="small">{{ priorityLabel(row.priority) }}</vort-tag>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="维护人" prop="maintainer_name" :width="100" />
                        <vort-table-column label="创建时间" :width="110">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-500">{{ row.created_at?.slice(0, 10) }}</span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="操作" :width="140" fixed="right">
                            <template #default="{ row }">
                                <div class="flex items-center gap-2 whitespace-nowrap">
                                    <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
                                    <vort-divider type="vertical" />
                                    <vort-popconfirm title="确认删除该用例？" @confirm="handleDelete(row)">
                                        <a class="text-sm text-red-500 cursor-pointer">删除</a>
                                    </vort-popconfirm>
                                </div>
                            </template>
                        </vort-table-column>
                    </vort-table>
                    <div v-if="showPagination" class="flex justify-end mt-4">
                        <vort-pagination v-model:current="filterParams.page" v-model:page-size="filterParams.size" :total="total" show-total-info show-size-changer @change="loadData" />
                    </div>
                </div>
            </div>
        </div>

        <TestCaseEditDrawer v-model:open="editDrawerOpen" :mode="editMode" :case-id="editCaseId" :project-id="currentProjectId" :default-module-id="selectedModuleId" @saved="onSaved" />
        <TestCaseDetailDrawer v-model:open="detailDrawerOpen" :case-id="detailCaseId" @edit="(id: string) => { detailDrawerOpen = false; editCaseId = id; editMode = 'edit'; editDrawerOpen = true; }" />
    </div>
</template>

<style scoped>
.tc-layout {
    display: flex;
    gap: 16px;
    min-height: calc(100vh - 160px);
}

.tc-sidebar {
    width: 240px;
    flex-shrink: 0;
    background: white;
    border-radius: 12px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}

.tc-sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 12px 10px;
    border-bottom: 1px solid var(--vort-border-secondary, #f0f0f0);
}

.tc-sidebar-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--vort-text);
}

.tc-sidebar-actions {
    display: flex;
    align-items: center;
    gap: 6px;
}

.tc-sidebar-icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    padding: 0;
    color: var(--vort-text-tertiary);
    background: none;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}

.tc-sidebar-icon-btn:hover {
    color: var(--vort-primary);
    background: var(--vort-primary-bg);
}

.tc-sidebar-add-btn {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 3px 10px;
    font-size: 12px;
    color: var(--vort-primary);
    background: none;
    border: none;
    cursor: pointer;
    border-radius: 4px;
    white-space: nowrap;
}

.tc-sidebar-add-btn:hover {
    background: var(--vort-primary-bg);
}

/* Search bar */
.tc-sidebar-search {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 8px 10px 4px;
    padding: 5px 8px;
    border: 1px solid var(--vort-border);
    border-radius: 6px;
    background: var(--vort-bg);
}

.tc-sidebar-search-icon {
    flex-shrink: 0;
    color: var(--vort-text-tertiary);
}

.tc-sidebar-search-input {
    flex: 1;
    font-size: 12px;
    color: var(--vort-text);
    border: none;
    outline: none;
    background: transparent;
}

.tc-sidebar-search-input::placeholder {
    color: var(--vort-text-tertiary);
}

.tc-sidebar-body {
    flex: 1;
    overflow-y: auto;
    padding: 4px 8px;
}

/* Tree nodes */
.tc-module-node {
    position: relative;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    min-height: 34px;
    font-size: 13px;
    color: var(--vort-text);
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
    border: none;
    background: none;
    width: 100%;
    text-align: left;
    border-radius: 6px;
    margin-bottom: 1px;
}

.tc-module-node:hover {
    background: var(--vort-bg-hover, #f5f5f5);
}

.tc-module-node.active {
    background: var(--vort-primary-bg, #eff6ff);
    color: var(--vort-primary);
}

.tc-module-root {
    font-weight: 500;
}

.tc-module-icon {
    flex-shrink: 0;
    color: var(--vort-text-tertiary);
}

.tc-module-node.active .tc-module-icon {
    color: var(--vort-primary);
}

.tc-module-label {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.tc-module-expand {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 16px;
    padding: 0;
    color: var(--vort-text-tertiary);
    background: none;
    border: none;
    cursor: pointer;
    flex-shrink: 0;
}

.tc-module-expand-placeholder {
    width: 16px;
    flex-shrink: 0;
}

/* More button wrapper - stops click propagation to parent node */
.tc-module-more-wrap {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
}

.tc-module-more {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    flex-shrink: 0;
    color: var(--vort-text-tertiary);
    background: none;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.1s;
}

.tc-module-node:hover .tc-module-more {
    opacity: 1;
}

.tc-module-more:hover {
    color: var(--vort-text);
    background: var(--vort-bg-hover, #eee);
}

/* Inline add / edit row */
.tc-module-add-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
}

.tc-inline-input {
    flex: 1;
    min-width: 0;
    padding: 3px 8px;
    font-size: 13px;
    color: var(--vort-text);
    border: 1px solid var(--vort-primary);
    border-radius: 4px;
    outline: none;
    background: var(--vort-bg);
}

.tc-main {
    flex: 1;
    min-width: 0;
}
</style>
