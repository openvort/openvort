<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { Plus, X, Search, ClipboardCheck } from "lucide-vue-next";
import { message } from "@openvort/vort-ui";
import {
    getVortflowTestCases,
    getVortflowTestCaseLinks,
    createVortflowTestCaseLink,
    deleteVortflowTestCaseLink,
} from "@/api";

interface Props {
    entityType: "story" | "task" | "bug";
    entityId: string;
}

const props = defineProps<Props>();

const PRIORITY_LABELS: Record<number, string> = { 0: "P0", 1: "P1", 2: "P2", 3: "P3" };
const PRIORITY_COLORS: Record<number, string> = { 0: "#ef4444", 1: "#f97316", 2: "#3b82f6", 3: "#94a3b8" };

interface LinkedCase {
    link_id: string;
    test_case_id: string;
    title: string;
    priority: number;
    case_type: string;
    maintainer: string;
}

const linkedCases = ref<LinkedCase[]>([]);
const loading = ref(false);
const adding = ref(false);
const searchKeyword = ref("");
const searchResults = ref<any[]>([]);
const searchLoading = ref(false);
const showDropdown = ref(false);

const linkedIdSet = computed(() => new Set(linkedCases.value.map((c) => c.test_case_id)));

let searchTimer: ReturnType<typeof setTimeout> | null = null;

const loadLinks = async () => {
    if (!props.entityId) return;
    loading.value = true;
    try {
        const res = await getVortflowTestCaseLinks({
            entity_type: props.entityType,
            entity_id: props.entityId,
        }) as any;
        const items = res?.items || [];
        linkedCases.value = items.map((item: any) => ({
            link_id: item.link_id,
            test_case_id: item.test_case_id,
            title: item.test_case_title || "",
            priority: item.test_case_priority ?? 2,
            case_type: item.test_case_case_type || "",
            maintainer: item.test_case_maintainer || "",
        }));
    } catch { linkedCases.value = []; }
    finally { loading.value = false; }
};

const doSearch = async () => {
    const kw = searchKeyword.value.trim();
    if (!kw) { searchResults.value = []; showDropdown.value = false; return; }
    searchLoading.value = true;
    try {
        const res = await getVortflowTestCases({ keyword: kw, page_size: 20 }) as any;
        const items = (res?.items || []).filter((item: any) => !linkedIdSet.value.has(item.id));
        searchResults.value = items;
        showDropdown.value = true;
    } catch { searchResults.value = []; }
    finally { searchLoading.value = false; }
};

const onSearchInput = () => {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(doSearch, 300);
};

const onSearchClear = () => { searchKeyword.value = ""; searchResults.value = []; showDropdown.value = false; };

const selectResult = async (item: any) => {
    try {
        const res = await createVortflowTestCaseLink({
            test_case_id: item.id,
            entity_type: props.entityType,
            entity_id: props.entityId,
        }) as any;
        if (res?.error) { message.error(res.error); return; }
        message.success("关联成功");
        searchKeyword.value = "";
        searchResults.value = [];
        showDropdown.value = false;
        await loadLinks();
    } catch { message.error("关联失败"); }
};

const removeLink = async (item: LinkedCase) => {
    try {
        await deleteVortflowTestCaseLink(item.link_id);
        message.success("已取消关联");
        await loadLinks();
    } catch { message.error("取消关联失败"); }
};

const startAdding = () => { adding.value = true; searchKeyword.value = ""; searchResults.value = []; showDropdown.value = false; };
const cancelAdding = () => { adding.value = false; searchKeyword.value = ""; searchResults.value = []; showDropdown.value = false; };

const onSearchBlur = () => { setTimeout(() => { showDropdown.value = false; }, 200); };

watch(() => props.entityId, () => { adding.value = false; loadLinks(); }, { immediate: true });
</script>

<template>
    <div class="tcl-panel">
        <div v-if="adding" class="tcl-add-row">
            <div class="tcl-search-bar">
                <Search class="tcl-search-icon" :size="14" />
                <input
                    v-model="searchKeyword"
                    class="tcl-search-input"
                    type="text"
                    placeholder="搜索测试用例标题"
                    @input="onSearchInput"
                    @focus="searchKeyword.trim() && doSearch()"
                    @blur="onSearchBlur"
                />
                <button v-if="searchKeyword" type="button" class="tcl-search-clear" @mousedown.prevent="onSearchClear">
                    <X :size="12" />
                </button>
                <div v-if="showDropdown" class="tcl-dropdown">
                    <div v-if="searchLoading" class="tcl-dropdown-empty">搜索中...</div>
                    <div v-else-if="searchResults.length === 0" class="tcl-dropdown-empty">无匹配结果</div>
                    <button
                        v-else
                        v-for="item in searchResults"
                        :key="item.id"
                        type="button"
                        class="tcl-dropdown-item"
                        @mousedown.prevent="selectResult(item)"
                    >
                        <span class="tcl-dropdown-priority" :style="{ color: PRIORITY_COLORS[item.priority] }">P{{ item.priority }}</span>
                        <span class="tcl-dropdown-title">{{ item.title }}</span>
                    </button>
                </div>
            </div>
            <button type="button" class="tcl-cancel-btn" @click="cancelAdding">取消</button>
        </div>

        <div v-if="!adding" class="tcl-header">
            <button type="button" class="tcl-add-btn" @click="startAdding">
                <Plus :size="14" />
                <span>关联</span>
            </button>
        </div>

        <div v-if="loading" class="tcl-empty">加载中...</div>
        <div v-else-if="linkedCases.length === 0 && !adding" class="tcl-empty">
            <ClipboardCheck :size="32" class="tcl-empty-icon" />
            <span>暂无关联测试用例</span>
        </div>
        <div v-else class="tcl-list">
            <div v-for="item in linkedCases" :key="item.link_id" class="tcl-item">
                <div class="tcl-item-main">
                    <span class="tcl-item-priority" :style="{ color: PRIORITY_COLORS[item.priority], background: PRIORITY_COLORS[item.priority] + '18' }">
                        {{ PRIORITY_LABELS[item.priority] || 'P2' }}
                    </span>
                    <span class="tcl-item-title">{{ item.title }}</span>
                    <span class="tcl-item-maintainer">{{ item.maintainer }}</span>
                </div>
                <button type="button" class="tcl-remove-btn" title="取消关联" @click.stop="removeLink(item)">
                    <X :size="14" />
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.tcl-panel { padding: 4px 0; }

.tcl-header { display: flex; justify-content: flex-end; margin-bottom: 8px; }

.tcl-add-btn {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 4px 12px; font-size: 13px; color: var(--vort-primary);
    background: none; border: 1px solid var(--vort-primary); border-radius: 6px; cursor: pointer; transition: background 0.15s;
}
.tcl-add-btn:hover { background: var(--vort-primary-bg); }

.tcl-add-row {
    display: flex; align-items: center; gap: 8px; margin-bottom: 12px;
    padding: 8px 10px; border: 1px solid var(--vort-border-secondary); border-radius: 8px; background: var(--vort-bg-secondary, #fafafa);
}

.tcl-search-bar {
    position: relative; display: flex; align-items: center; flex: 1;
    border: 1px solid var(--vort-border); border-radius: 6px; background: var(--vort-bg);
}

.tcl-search-icon { position: absolute; left: 8px; color: var(--vort-text-tertiary); pointer-events: none; }

.tcl-search-input {
    width: 100%; padding: 6px 28px; font-size: 13px; color: var(--vort-text);
    background: transparent; border: none; outline: none;
}
.tcl-search-input::placeholder { color: var(--vort-text-tertiary); }

.tcl-search-clear {
    position: absolute; right: 6px; display: flex; align-items: center; justify-content: center;
    width: 18px; height: 18px; padding: 0; color: var(--vort-text-tertiary); background: none; border: none; border-radius: 50%; cursor: pointer;
}
.tcl-search-clear:hover { color: var(--vort-text-secondary); background: var(--vort-bg-hover); }

.tcl-cancel-btn {
    flex-shrink: 0; padding: 5px 14px; font-size: 13px; color: var(--vort-text-secondary);
    background: var(--vort-bg); border: 1px solid var(--vort-border); border-radius: 6px; cursor: pointer;
}
.tcl-cancel-btn:hover { color: var(--vort-text); }

.tcl-dropdown {
    position: absolute; top: calc(100% + 4px); left: -1px; right: 0; z-index: 100;
    max-height: 280px; overflow-y: auto; background: var(--vort-bg);
    border: 1px solid var(--vort-border); border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.tcl-dropdown-empty { padding: 16px; text-align: center; font-size: 13px; color: var(--vort-text-tertiary); }

.tcl-dropdown-item {
    display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 12px;
    font-size: 13px; color: var(--vort-text); background: none; border: none; text-align: left; cursor: pointer; transition: background 0.1s;
}
.tcl-dropdown-item:hover { background: var(--vort-primary-bg); }
.tcl-dropdown-item + .tcl-dropdown-item { border-top: 1px solid var(--vort-border-secondary); }

.tcl-dropdown-priority { flex-shrink: 0; font-size: 12px; font-weight: 600; }
.tcl-dropdown-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.tcl-list { display: flex; flex-direction: column; gap: 6px; }

.tcl-item {
    display: flex; align-items: center; gap: 4px;
    border: 1px solid var(--vort-border-secondary); border-radius: 8px; background: var(--vort-bg); transition: border-color 0.15s;
}
.tcl-item:hover { border-color: var(--vort-primary-bg-hover); }

.tcl-item-main {
    display: flex; align-items: center; gap: 8px; flex: 1; padding: 10px 12px; overflow: hidden;
}

.tcl-item-priority {
    flex-shrink: 0; font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 4px;
}

.tcl-item-title {
    flex: 1; font-size: 13px; color: var(--vort-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.tcl-item-maintainer {
    flex-shrink: 0; font-size: 12px; color: var(--vort-text-tertiary);
}

.tcl-remove-btn {
    display: flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; margin-right: 6px; padding: 0;
    color: var(--vort-text-tertiary); background: none; border: none; border-radius: 6px; cursor: pointer;
    opacity: 0; transition: opacity 0.15s, color 0.15s, background 0.15s;
}
.tcl-item:hover .tcl-remove-btn { opacity: 1; }
.tcl-remove-btn:hover { color: #dc2626; background: #fee2e2; }

.tcl-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 48px 20px;
    color: var(--vort-text-tertiary);
    font-size: 14px;
}

.tcl-empty-icon {
    color: var(--vort-text-quaternary, #d0d5dd);
}
</style>
