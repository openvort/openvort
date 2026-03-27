<script setup lang="ts">
import { ref, computed, watch } from "vue";
import {
    Search, ChevronRight, ChevronDown, FolderOpen, Folder,
} from "lucide-vue-next";
import { Dialog } from "@openvort/vort-ui";
import { message } from "@openvort/vort-ui";
import {
    getVortflowTestModules,
    getVortflowTestCases,
    addVortflowTestPlanCases,
} from "@/api";

interface Props {
    open: boolean;
    planId: string;
    projectId: string;
}

const props = defineProps<Props>();

const emit = defineEmits<{
    "update:open": [val: boolean];
    saved: [];
}>();

const submitting = ref(false);
const casesLoading = ref(false);

// ============ Module Tree ============

interface RawModule {
    id: string;
    name: string;
    parent_id: string | null;
}

interface FlatNode {
    id: string;
    name: string;
    parent_id: string | null;
    depth: number;
    hasChildren: boolean;
    expanded: boolean;
}

const rawModules = ref<RawModule[]>([]);
const expandedIds = ref<Set<string>>(new Set());
const selectedModuleId = ref("");
const moduleSearch = ref("");
const showModuleSearch = ref(false);

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
        return (childMap.get(id) || []).some((cid) => matchesSearch(cid));
    };
    const result: FlatNode[] = [];
    const walk = (parentId: string, depth: number) => {
        const children = childMap.get(parentId) || [];
        for (const id of children) {
            if (!matchesSearch(id)) continue;
            const mod = map.get(id)!;
            const hasChildren = (childMap.get(id) || []).length > 0;
            const expanded = kw ? true : expandedIds.value.has(id);
            result.push({ id: mod.id, name: mod.name, parent_id: mod.parent_id, depth, hasChildren, expanded });
            if (expanded && hasChildren) walk(id, depth + 1);
        }
    };
    walk("__root__", 0);
    return result;
});

const loadModules = async () => {
    if (!props.projectId) return;
    try {
        const res = await getVortflowTestModules({ project_id: props.projectId });
        rawModules.value = (res as any)?.items || [];
        const parentIds = new Set(rawModules.value.filter((m) => m.parent_id).map((m) => m.parent_id!));
        for (const pid of parentIds) expandedIds.value.add(pid);
    } catch {
        rawModules.value = [];
    }
};

const toggleExpand = (id: string) => {
    const next = new Set(expandedIds.value);
    if (next.has(id)) next.delete(id); else next.add(id);
    expandedIds.value = next;
};

const selectModule = (id: string) => {
    selectedModuleId.value = selectedModuleId.value === id ? "" : id;
    loadCases();
};

// Module checkbox selection (to select all cases in a module)
const selectedModuleIds = ref<Set<string>>(new Set());

const toggleModuleCheck = (id: string) => {
    const next = new Set(selectedModuleIds.value);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedModuleIds.value = next;
};

// ============ Test Cases ============

interface TestCaseItem {
    id: string;
    title: string;
    case_type: string;
    priority: number;
    module_id: string;
    module_name: string;
    maintainer_name: string;
}

const cases = ref<TestCaseItem[]>([]);
const caseKeyword = ref("");
const caseTypeFilter = ref("");
const selectedCaseIds = ref<Set<string>>(new Set());

const caseTypeLabels: Record<string, string> = {
    functional: "功能测试",
    performance: "性能测试",
    api: "接口测试",
    ui: "UI 测试",
    security: "安全测试",
};
const caseTypeOptions = [
    { value: "", label: "用例类型" },
    { value: "functional", label: "功能测试" },
    { value: "performance", label: "性能测试" },
    { value: "api", label: "接口测试" },
    { value: "ui", label: "UI 测试" },
    { value: "security", label: "安全测试" },
];
const loadCases = async () => {
    if (!props.projectId) return;
    casesLoading.value = true;
    try {
        const res = await getVortflowTestCases({
            project_id: props.projectId,
            module_id: selectedModuleId.value || undefined,
            keyword: caseKeyword.value || undefined,
            case_type: caseTypeFilter.value || undefined,
            page_size: 500,
        });
        cases.value = ((res as any).items || []) as TestCaseItem[];
    } finally {
        casesLoading.value = false;
    }
};

const toggleCaseSelect = (id: string) => {
    const next = new Set(selectedCaseIds.value);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedCaseIds.value = next;
};

const allSelected = computed(() => cases.value.length > 0 && cases.value.every(c => selectedCaseIds.value.has(c.id)));

const toggleSelectAll = () => {
    if (allSelected.value) {
        selectedCaseIds.value = new Set();
    } else {
        selectedCaseIds.value = new Set(cases.value.map(c => c.id));
    }
};

// ============ Submit ============

const handleSubmit = async () => {
    const ids = [...selectedCaseIds.value];
    if (!ids.length) {
        message.warning("请选择至少一个用例");
        return;
    }
    submitting.value = true;
    try {
        const res = await addVortflowTestPlanCases(props.planId, { test_case_ids: ids });
        const added = (res as any).added || 0;
        message.success(`已添加 ${added} 个用例`);
        emit("saved");
        emit("update:open", false);
    } finally {
        submitting.value = false;
    }
};

// ============ Init on open ============

watch(() => props.open, async (val) => {
    if (!val) return;
    selectedCaseIds.value = new Set();
    selectedModuleId.value = "";
    caseKeyword.value = "";
    caseTypeFilter.value = "";
    await loadModules();
    await loadCases();
});
</script>

<template>
    <Dialog
        :open="open"
        title="添加用例"
        :width="900"
        :confirm-loading="submitting"
        ok-text="添加"
        @ok="handleSubmit"
        @update:open="emit('update:open', $event)"
    >
        <div class="flex min-h-[400px] max-h-[60vh] -mx-6 -my-2">
            <!-- Left: Module Tree -->
            <div class="w-[200px] border-r border-gray-100 p-3 shrink-0 overflow-y-auto">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-sm font-medium text-gray-700">功能模块</span>
                    <Search
                        :size="14"
                        class="text-gray-400 cursor-pointer hover:text-gray-600"
                        @click="showModuleSearch = !showModuleSearch"
                    />
                </div>

                <div v-if="showModuleSearch" class="mb-2">
                    <vort-input-search
                        v-model="moduleSearch"
                        placeholder="搜索"
                        allow-clear
                        size="small"
                    />
                </div>

                <div
                    class="flex items-center gap-1.5 px-2 py-1.5 rounded cursor-pointer text-sm mb-1"
                    :class="selectedModuleId === '' ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                    @click="selectModule('')"
                >
                    <FolderOpen :size="14" />
                    <span>全部用例</span>
                </div>

                <div
                    v-for="node in flatNodes"
                    :key="node.id"
                    class="flex items-center gap-1 px-2 py-1.5 rounded cursor-pointer text-sm"
                    :class="selectedModuleId === node.id ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                    :style="{ paddingLeft: `${8 + node.depth * 16}px` }"
                    @click="selectModule(node.id)"
                >
                    <span
                        v-if="node.hasChildren"
                        class="shrink-0 cursor-pointer"
                        @click.stop="toggleExpand(node.id)"
                    >
                        <ChevronDown v-if="node.expanded" :size="12" />
                        <ChevronRight v-else :size="12" />
                    </span>
                    <span v-else class="w-3 shrink-0" />
                    <component :is="node.hasChildren && node.expanded ? FolderOpen : Folder" :size="14" class="shrink-0" />
                    <span class="truncate">{{ node.name }}</span>
                </div>
            </div>

            <!-- Right: Cases List -->
            <div class="flex-1 p-3 overflow-y-auto">
                <div class="flex items-center gap-2 mb-3">
                    <vort-select
                        v-model="caseTypeFilter"
                        placeholder="用例类型"
                        allow-clear
                        size="small"
                        class="w-[120px]"
                        @change="loadCases"
                    >
                        <vort-select-option v-for="opt in caseTypeOptions" :key="opt.value" :value="opt.value">
                            {{ opt.label }}
                        </vort-select-option>
                    </vort-select>
                    <vort-input-search
                        v-model="caseKeyword"
                        placeholder="搜索用例"
                        allow-clear
                        size="small"
                        class="w-[200px]"
                        @search="loadCases"
                        @keyup.enter="loadCases"
                    />
                </div>

                <vort-table :data-source="cases" :loading="casesLoading" :pagination="false" row-key="id" size="small">
                    <vort-table-column :width="40">
                        <template #header>
                            <vort-checkbox :checked="allSelected" @update:checked="toggleSelectAll" />
                        </template>
                        <template #default="{ row }">
                            <vort-checkbox
                                :checked="selectedCaseIds.has(row.id)"
                                @update:checked="toggleCaseSelect(row.id)"
                            />
                        </template>
                    </vort-table-column>

                    <vort-table-column label="编号" :width="70">
                        <template #default="{ row }">
                            <span class="text-xs text-gray-400 font-mono">{{ row.id?.slice(0, 5)?.toUpperCase() }}</span>
                        </template>
                    </vort-table-column>

                    <vort-table-column label="标题" :min-width="160">
                        <template #default="{ row }">
                            <span class="text-sm text-gray-800">{{ row.title }}</span>
                        </template>
                    </vort-table-column>

                    <vort-table-column label="类型" :width="90">
                        <template #default="{ row }">
                            <span class="text-sm text-gray-500">{{ caseTypeLabels[row.case_type] || row.case_type }}</span>
                        </template>
                    </vort-table-column>
                </vort-table>
            </div>
        </div>
    </Dialog>
</template>
