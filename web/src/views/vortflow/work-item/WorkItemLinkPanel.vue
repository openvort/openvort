<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { Plus, X, Search, ChevronDown, Check, Link2 } from "lucide-vue-next";
import { message } from "@/components/vort";
import {
    getVortflowStories,
    getVortflowTasks,
    getVortflowBugs,
    getVortflowWorkItemLinks,
    createVortflowWorkItemLink,
    deleteVortflowWorkItemLink,
} from "@/api";
import { useWorkItemCommon } from "./useWorkItemCommon";
import type { WorkItemType, Status } from "@/components/vort-biz/work-item/WorkItemTable.types";

interface Props {
    entityType: "story" | "task" | "bug";
    entityId: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
    openRelated: [record: { backendId: string; type: WorkItemType; title: string }];
}>();

const {
    getWorkItemTypeIconClass,
    getWorkItemTypeIconSymbol,
    mapBackendStateToStatus,
    getMemberNameById,
} = useWorkItemCommon();

interface LinkedItem {
    link_id: string;
    link_type: "story" | "task" | "bug";
    id: string;
    title: string;
    state: string;
    displayType: WorkItemType;
    displayStatus: Status;
    workNo: string;
    owner: string;
}

interface SearchResultItem {
    id: string;
    title: string;
    state: string;
    workNo: string;
    displayType: WorkItemType;
}

const BACKEND_TYPE_MAP: Record<WorkItemType, "story" | "task" | "bug"> = {
    "需求": "story",
    "任务": "task",
    "缺陷": "bug",
};

const DISPLAY_TYPE_MAP: Record<string, WorkItemType> = {
    story: "需求",
    task: "任务",
    bug: "缺陷",
};

const TYPE_OPTIONS: WorkItemType[] = ["需求", "任务", "缺陷"];

const linkedItems = ref<LinkedItem[]>([]);
const loading = ref(false);
const adding = ref(false);
const searchKeyword = ref("");
const searchType = ref<WorkItemType>("缺陷");
const searchResults = ref<SearchResultItem[]>([]);
const searchLoading = ref(false);
const showDropdown = ref(false);
const typeDropdownOpen = ref(false);
const linkedIdSet = computed(() => new Set(linkedItems.value.map((i) => `${i.link_type}:${i.id}`)));

let searchTimer: ReturnType<typeof setTimeout> | null = null;

const toWorkNo = (id: string) =>
    `#${id.replace(/-/g, "").slice(0, 6).toUpperCase().padEnd(6, "X")}`;

const getOwnerId = (item: any): string =>
    String(item?.assignee_id || item?.pm_id || item?.developer_id || "").trim();

const loadLinks = async () => {
    if (!props.entityId) return;
    loading.value = true;
    try {
        const res = await getVortflowWorkItemLinks({
            entity_type: props.entityType,
            entity_id: props.entityId,
        });
        const items = (res?.items || []) as any[];
        linkedItems.value = items.map((item) => {
            const linkType = item.link_type as "story" | "task" | "bug";
            const displayType = DISPLAY_TYPE_MAP[linkType] || "缺陷";
            return {
                link_id: item.link_id,
                link_type: linkType,
                id: item.id,
                title: item.title || "",
                state: item.state || "",
                displayType,
                displayStatus: mapBackendStateToStatus(displayType, item.state || ""),
                workNo: toWorkNo(item.id),
                owner: getMemberNameById(getOwnerId(item)) || "未指派",
            };
        });
    } catch {
        linkedItems.value = [];
    } finally {
        loading.value = false;
    }
};

const doSearch = async () => {
    const kw = searchKeyword.value.trim();
    if (!kw) {
        searchResults.value = [];
        showDropdown.value = false;
        return;
    }
    searchLoading.value = true;
    try {
        const backendType = BACKEND_TYPE_MAP[searchType.value];
        let res: any;
        if (backendType === "story") {
            res = await getVortflowStories({ keyword: kw, page_size: 20 });
        } else if (backendType === "task") {
            res = await getVortflowTasks({ keyword: kw, page_size: 20 });
        } else {
            res = await getVortflowBugs({ keyword: kw, page_size: 20 });
        }
        const items = (res?.items || []) as any[];
        searchResults.value = items
            .filter((item) => {
                const key = `${backendType}:${item.id}`;
                if (linkedIdSet.value.has(key)) return false;
                if (backendType === props.entityType && item.id === props.entityId) return false;
                return true;
            })
            .map((item) => ({
                id: item.id,
                title: item.title || "",
                state: item.state || "",
                workNo: toWorkNo(item.id),
                displayType: searchType.value,
            }));
        showDropdown.value = true;
    } catch {
        searchResults.value = [];
    } finally {
        searchLoading.value = false;
    }
};

const onSearchInput = () => {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(doSearch, 300);
};

const onSearchClear = () => {
    searchKeyword.value = "";
    searchResults.value = [];
    showDropdown.value = false;
};

const selectResult = async (item: SearchResultItem) => {
    const targetType = BACKEND_TYPE_MAP[item.displayType];
    try {
        const res = await createVortflowWorkItemLink({
            source_type: props.entityType,
            source_id: props.entityId,
            target_type: targetType,
            target_id: item.id,
        });
        if ((res as any)?.error) {
            message.error((res as any).error);
            return;
        }
        message.success("关联成功");
        searchKeyword.value = "";
        searchResults.value = [];
        showDropdown.value = false;
        await loadLinks();
    } catch {
        message.error("关联失败");
    }
};

const removeLink = async (item: LinkedItem) => {
    try {
        await deleteVortflowWorkItemLink(item.link_id);
        message.success("已取消关联");
        await loadLinks();
    } catch {
        message.error("取消关联失败");
    }
};

const openLinkedItem = (item: LinkedItem) => {
    emit("openRelated", {
        backendId: item.id,
        type: item.displayType,
        title: item.title,
    });
};

const startAdding = () => {
    adding.value = true;
    searchKeyword.value = "";
    searchResults.value = [];
    showDropdown.value = false;
};

const cancelAdding = () => {
    adding.value = false;
    searchKeyword.value = "";
    searchResults.value = [];
    showDropdown.value = false;
};

const toggleTypeDropdown = () => {
    typeDropdownOpen.value = !typeDropdownOpen.value;
};

const selectType = (t: WorkItemType) => {
    searchType.value = t;
    typeDropdownOpen.value = false;
    searchResults.value = [];
    showDropdown.value = false;
    if (searchKeyword.value.trim()) {
        doSearch();
    }
};

const onTypeBlur = () => {
    setTimeout(() => {
        typeDropdownOpen.value = false;
    }, 150);
};

const onSearchBlur = () => {
    setTimeout(() => {
        showDropdown.value = false;
    }, 200);
};

watch(
    () => props.entityId,
    () => {
        adding.value = false;
        loadLinks();
    },
    { immediate: true },
);
</script>

<template>
    <div class="wi-link-panel">
        <div v-if="adding" class="wi-link-add-row">
            <div class="wi-link-search-bar">
                <div class="wi-link-type-picker" tabindex="0" @blur="onTypeBlur">
                    <button type="button" class="wi-link-type-btn" @click="toggleTypeDropdown">
                        <span :class="['wi-link-type-badge', getWorkItemTypeIconClass(searchType)]">
                            {{ getWorkItemTypeIconSymbol(searchType) }}
                        </span>
                        <span class="wi-link-type-label">{{ searchType }}</span>
                        <ChevronDown class="wi-link-type-chevron" :size="12" />
                    </button>
                    <div v-if="typeDropdownOpen" class="wi-link-type-dropdown">
                        <button
                            v-for="t in TYPE_OPTIONS"
                            :key="t"
                            type="button"
                            class="wi-link-type-option"
                            :class="{ selected: searchType === t }"
                            @mousedown.prevent="selectType(t)"
                        >
                            <span :class="['wi-link-type-badge', getWorkItemTypeIconClass(t)]">
                                {{ getWorkItemTypeIconSymbol(t) }}
                            </span>
                            <span class="wi-link-type-option-label">{{ t }}</span>
                            <Check v-if="searchType === t" class="wi-link-type-check" :size="14" />
                        </button>
                    </div>
                </div>
                <div class="wi-link-search-wrap">
                    <Search class="wi-link-search-icon" :size="14" />
                    <input
                        v-model="searchKeyword"
                        class="wi-link-search-input"
                        type="text"
                        placeholder="搜索工作项标题或编号"
                        @input="onSearchInput"
                        @focus="searchKeyword.trim() && doSearch()"
                        @blur="onSearchBlur"
                    />
                    <button
                        v-if="searchKeyword"
                        type="button"
                        class="wi-link-search-clear"
                        @mousedown.prevent="onSearchClear"
                    >
                        <X :size="12" />
                    </button>
                    <div v-if="showDropdown" class="wi-link-dropdown">
                        <div v-if="searchLoading" class="wi-link-dropdown-empty">搜索中...</div>
                        <div v-else-if="searchResults.length === 0" class="wi-link-dropdown-empty">无匹配结果</div>
                        <button
                            v-else
                            v-for="item in searchResults"
                            :key="item.id"
                            type="button"
                            class="wi-link-dropdown-item"
                            @mousedown.prevent="selectResult(item)"
                        >
                            <span class="wi-link-dropdown-no">{{ item.workNo }}</span>
                            <span class="wi-link-dropdown-title">{{ item.title }}</span>
                            <span class="wi-link-dropdown-type">{{ item.displayType }}</span>
                        </button>
                    </div>
                </div>
            </div>
            <button type="button" class="wi-link-cancel-btn" @click="cancelAdding">取消</button>
        </div>

        <div v-if="!adding" class="wi-link-header">
            <button type="button" class="wi-link-add-btn" @click="startAdding">
                <Plus :size="14" />
                <span>添加</span>
            </button>
        </div>

        <div v-if="loading" class="wi-link-empty">加载中...</div>
        <div v-else-if="linkedItems.length === 0 && !adding" class="wi-link-empty">
            <Link2 :size="32" class="wi-link-empty-icon" />
            <span>暂无关联工作项</span>
        </div>
        <div v-else class="wi-link-list">
            <div
                v-for="item in linkedItems"
                :key="item.link_id"
                class="wi-link-item"
            >
                <button type="button" class="wi-link-item-main" @click="openLinkedItem(item)">
                    <span :class="['wi-link-type-badge', getWorkItemTypeIconClass(item.displayType)]">
                        {{ getWorkItemTypeIconSymbol(item.displayType) }}
                    </span>
                    <span class="wi-link-item-no">{{ item.workNo }}</span>
                    <span class="wi-link-item-title">{{ item.title }}</span>
                    <span class="wi-link-item-status">{{ item.displayStatus }}</span>
                    <span class="wi-link-item-owner">{{ item.owner }}</span>
                </button>
                <button type="button" class="wi-link-remove-btn" title="取消关联" @click.stop="removeLink(item)">
                    <X :size="14" />
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.wi-link-panel {
    padding: 4px 0;
}

.wi-link-header {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 8px;
}

.wi-link-add-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 12px;
    font-size: 13px;
    color: var(--vort-primary);
    background: none;
    border: 1px solid var(--vort-primary);
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.15s;
}

.wi-link-add-btn:hover {
    background: var(--vort-primary-bg);
}

.wi-link-add-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    padding: 8px 10px;
    border: 1px solid var(--vort-border-secondary);
    border-radius: 8px;
    background: var(--vort-bg-secondary, #fafafa);
}

.wi-link-search-bar {
    display: flex;
    align-items: center;
    flex: 1;
    gap: 0;
    border: 1px solid var(--vort-border);
    border-radius: 6px;
    background: var(--vort-bg);
}

.wi-link-type-picker {
    position: relative;
    flex-shrink: 0;
    outline: none;
}

.wi-link-type-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 100%;
    padding: 6px 8px 6px 10px;
    font-size: 13px;
    color: var(--vort-text);
    background: var(--vort-bg-secondary, #f5f5f5);
    border: none;
    border-right: 1px solid var(--vort-border);
    border-radius: 6px 0 0 6px;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.15s;
}

.wi-link-type-btn:hover {
    background: var(--vort-bg-hover, #efefef);
}

.wi-link-type-label {
    font-size: 13px;
}

.wi-link-type-chevron {
    color: var(--vort-text-tertiary);
    flex-shrink: 0;
}

.wi-link-type-dropdown {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    z-index: 110;
    min-width: 130px;
    background: var(--vort-bg);
    border: 1px solid var(--vort-border);
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    padding: 4px;
}

.wi-link-type-option {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 7px 10px;
    font-size: 13px;
    color: var(--vort-text);
    background: none;
    border: none;
    border-radius: 5px;
    text-align: left;
    cursor: pointer;
    transition: background 0.1s;
}

.wi-link-type-option:hover {
    background: var(--vort-primary-bg, #eff6ff);
}

.wi-link-type-option.selected {
    color: var(--vort-primary);
    font-weight: 500;
}

.wi-link-type-option-label {
    flex: 1;
}

.wi-link-type-check {
    color: var(--vort-primary);
    flex-shrink: 0;
}

.wi-link-search-wrap {
    position: relative;
    display: flex;
    align-items: center;
    flex: 1;
    min-width: 0;
}

.wi-link-search-icon {
    position: absolute;
    left: 8px;
    color: var(--vort-text-tertiary);
    pointer-events: none;
}

.wi-link-search-input {
    width: 100%;
    padding: 6px 28px 6px 28px;
    font-size: 13px;
    color: var(--vort-text);
    background: transparent;
    border: none;
    outline: none;
}

.wi-link-search-input::placeholder {
    color: var(--vort-text-tertiary);
}

.wi-link-search-clear {
    position: absolute;
    right: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    padding: 0;
    color: var(--vort-text-tertiary);
    background: none;
    border: none;
    border-radius: 50%;
    cursor: pointer;
}

.wi-link-search-clear:hover {
    color: var(--vort-text-secondary);
    background: var(--vort-bg-hover);
}

.wi-link-cancel-btn {
    flex-shrink: 0;
    padding: 5px 14px;
    font-size: 13px;
    color: var(--vort-text-secondary);
    background: var(--vort-bg);
    border: 1px solid var(--vort-border);
    border-radius: 6px;
    cursor: pointer;
}

.wi-link-cancel-btn:hover {
    color: var(--vort-text);
    border-color: var(--vort-border-hover, var(--vort-border));
}

.wi-link-dropdown {
    position: absolute;
    top: calc(100% + 4px);
    left: -1px;
    right: 0;
    z-index: 100;
    max-height: 280px;
    overflow-y: auto;
    background: var(--vort-bg);
    border: 1px solid var(--vort-border);
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.wi-link-dropdown-empty {
    padding: 16px;
    text-align: center;
    font-size: 13px;
    color: var(--vort-text-tertiary);
}

.wi-link-dropdown-item {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 12px;
    font-size: 13px;
    color: var(--vort-text);
    background: none;
    border: none;
    text-align: left;
    cursor: pointer;
    transition: background 0.1s;
}

.wi-link-dropdown-item:hover {
    background: var(--vort-primary-bg);
}

.wi-link-dropdown-item + .wi-link-dropdown-item {
    border-top: 1px solid var(--vort-border-secondary);
}

.wi-link-dropdown-no {
    flex-shrink: 0;
    font-size: 12px;
    font-family: monospace;
    color: var(--vort-text-secondary);
}

.wi-link-dropdown-title {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.wi-link-dropdown-type {
    flex-shrink: 0;
    font-size: 12px;
    color: var(--vort-text-tertiary);
}

.wi-link-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.wi-link-item {
    display: flex;
    align-items: center;
    gap: 4px;
    border: 1px solid var(--vort-border-secondary);
    border-radius: 8px;
    background: var(--vort-bg);
    transition: border-color 0.15s;
}

.wi-link-item:hover {
    border-color: var(--vort-primary-bg-hover);
}

.wi-link-item-main {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    padding: 10px 12px;
    background: none;
    border: none;
    text-align: left;
    cursor: pointer;
    overflow: hidden;
}

.wi-link-type-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    font-size: 11px;
    border-radius: 4px;
    flex-shrink: 0;
}

.wi-link-type-badge.work-type-icon-demand {
    color: #2563eb;
    background: #dbeafe;
}

.wi-link-type-badge.work-type-icon-task {
    color: #16a34a;
    background: #dcfce7;
}

.wi-link-type-badge.work-type-icon-bug {
    color: #dc2626;
    background: #fee2e2;
}

.wi-link-item-no {
    flex-shrink: 0;
    font-size: 12px;
    font-family: monospace;
    color: var(--vort-text-secondary);
}

.wi-link-item-title {
    flex: 1;
    font-size: 13px;
    color: var(--vort-text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.wi-link-item-status {
    flex-shrink: 0;
    font-size: 12px;
    color: var(--vort-text-secondary);
    padding: 1px 6px;
    border-radius: 4px;
    background: var(--vort-bg-secondary, #f5f5f5);
}

.wi-link-item-owner {
    flex-shrink: 0;
    font-size: 12px;
    color: var(--vort-text-tertiary);
}

.wi-link-remove-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    margin-right: 6px;
    padding: 0;
    color: var(--vort-text-tertiary);
    background: none;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.15s, color 0.15s, background 0.15s;
}

.wi-link-item:hover .wi-link-remove-btn {
    opacity: 1;
}

.wi-link-remove-btn:hover {
    color: #dc2626;
    background: #fee2e2;
}

.wi-link-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 48px 20px;
    color: var(--vort-text-tertiary);
    font-size: 14px;
}

.wi-link-empty-icon {
    color: var(--vort-text-quaternary, #d0d5dd);
}
</style>
