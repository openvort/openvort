<template>
    <Dialog
        :open="open"
        title="选择知识库文档"
        :width="640"
        :footer="false"
        @update:open="$emit('update:open', $event)"
    >
        <div class="skd-container">
            <div class="skd-toolbar">
                <div class="skd-breadcrumb">
                    <span
                        class="skd-crumb"
                        :class="{ 'skd-crumb-active': !currentFolderId }"
                        @click="navigateToFolder('')"
                    >知识库</span>
                    <template v-for="crumb in breadcrumbs" :key="crumb.id">
                        <ChevronRight :size="14" class="skd-crumb-sep" />
                        <span
                            class="skd-crumb"
                            :class="{ 'skd-crumb-active': crumb.id === currentFolderId }"
                            @click="navigateToFolder(crumb.id)"
                        >{{ crumb.name }}</span>
                    </template>
                </div>
                <div class="skd-search">
                    <Search :size="14" class="skd-search-icon" />
                    <input
                        v-model="keyword"
                        class="skd-search-input"
                        type="text"
                        placeholder="搜索文档..."
                        @input="onSearchInput"
                    />
                    <button v-if="keyword" type="button" class="skd-search-clear" @click="clearSearch">
                        <X :size="12" />
                    </button>
                </div>
            </div>

            <div v-if="loading" class="skd-empty">加载中...</div>
            <div v-else-if="rows.length === 0" class="skd-empty">暂无内容</div>
            <div v-else class="skd-list">
                <div
                    v-for="row in rows"
                    :key="row.id"
                    class="skd-row"
                    :class="{
                        'skd-row-folder': row._type === 'folder',
                        'skd-row-disabled': row._type === 'document' && linkedIds.has(row.id),
                    }"
                    @click="handleRowClick(row)"
                >
                    <div class="skd-row-icon">
                        <FolderOpen v-if="row._type === 'folder'" :size="18" class="text-amber-500" />
                        <FileText v-else :size="18" class="text-blue-500" />
                    </div>
                    <div class="skd-row-info">
                        <span class="skd-row-title">{{ row.name }}</span>
                        <span v-if="row._type === 'document' && row.fileType" class="skd-row-meta">{{ row.fileType.toUpperCase() }}</span>
                    </div>
                    <div v-if="row._type === 'document'" class="skd-row-action">
                        <span v-if="linkedIds.has(row.id)" class="skd-row-linked">已关联</span>
                        <span v-else class="skd-row-select">
                            <Plus :size="14" />
                            选择
                        </span>
                    </div>
                    <ChevronRight v-if="row._type === 'folder'" :size="16" class="skd-row-arrow" />
                </div>
            </div>
        </div>
    </Dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { Dialog, message } from "@openvort/vort-ui";
import { FolderOpen, FileText, ChevronRight, Search, X, Plus } from "lucide-vue-next";
import { getKBFolders, getKBDocuments, getKBFolder } from "@/api";

interface Props {
    open: boolean;
    linkedDocIds: string[];
}

const props = defineProps<Props>();
const emit = defineEmits<{
    (e: "update:open", val: boolean): void;
    (e: "select", doc: { id: string; title: string }): void;
}>();

interface ListRow {
    _type: "folder" | "document";
    id: string;
    name: string;
    fileType?: string;
}

interface Breadcrumb {
    id: string;
    name: string;
}

const loading = ref(false);
const currentFolderId = ref("");
const breadcrumbs = ref<Breadcrumb[]>([]);
const folders = ref<any[]>([]);
const documents = ref<any[]>([]);
const keyword = ref("");
let searchTimer: ReturnType<typeof setTimeout> | null = null;

const linkedIds = computed(() => new Set(props.linkedDocIds));

const rows = computed<ListRow[]>(() => {
    const result: ListRow[] = [];
    if (!keyword.value.trim()) {
        for (const f of folders.value) {
            result.push({ _type: "folder", id: f.id, name: f.name });
        }
    }
    for (const d of documents.value) {
        result.push({ _type: "document", id: d.id, name: d.title, fileType: d.file_type });
    }
    return result;
});

const loadContent = async () => {
    loading.value = true;
    try {
        const kw = keyword.value.trim();
        const [foldersRes, docsRes] = await Promise.all([
            kw ? Promise.resolve({ items: [] }) : getKBFolders(currentFolderId.value),
            getKBDocuments({
                page: 1,
                page_size: 100,
                keyword: kw || undefined,
                folder_id: kw ? undefined : currentFolderId.value,
            }),
        ]) as [any, any];
        folders.value = foldersRes?.items || [];
        documents.value = docsRes?.items || [];
    } catch {
        folders.value = [];
        documents.value = [];
    } finally {
        loading.value = false;
    }
};

const navigateToFolder = async (folderId: string) => {
    currentFolderId.value = folderId;
    keyword.value = "";
    if (!folderId) {
        breadcrumbs.value = [];
    } else {
        try {
            const res = await getKBFolder(folderId) as any;
            breadcrumbs.value = [
                ...(res.breadcrumb || []),
                { id: res.id, name: res.name },
            ];
        } catch {
            breadcrumbs.value = [];
        }
    }
    loadContent();
};

const handleRowClick = (row: ListRow) => {
    if (row._type === "folder") {
        navigateToFolder(row.id);
        return;
    }
    if (linkedIds.value.has(row.id)) return;
    emit("select", { id: row.id, title: row.name });
};

const onSearchInput = () => {
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(loadContent, 300);
};

const clearSearch = () => {
    keyword.value = "";
    loadContent();
};

watch(() => props.open, (val) => {
    if (val) {
        currentFolderId.value = "";
        breadcrumbs.value = [];
        keyword.value = "";
        loadContent();
    }
});
</script>

<style scoped>
.skd-container { min-height: 300px; max-height: 480px; display: flex; flex-direction: column; }

.skd-toolbar {
    display: flex; align-items: center; gap: 10px; padding-bottom: 12px;
    border-bottom: 1px solid var(--vort-border-secondary);
}

.skd-breadcrumb {
    display: flex; align-items: center; gap: 2px; flex: 1; min-width: 0; overflow: hidden;
    font-size: 13px; color: var(--vort-text-secondary);
}
.skd-crumb { cursor: pointer; white-space: nowrap; transition: color 0.15s; }
.skd-crumb:hover { color: var(--vort-primary); }
.skd-crumb-active { color: var(--vort-text); font-weight: 500; }
.skd-crumb-sep { color: var(--vort-text-quaternary); flex-shrink: 0; }

.skd-search {
    position: relative; display: flex; align-items: center; width: 180px; flex-shrink: 0;
    border: 1px solid var(--vort-border); border-radius: 6px; background: var(--vort-bg);
}
.skd-search-icon { position: absolute; left: 8px; color: var(--vort-text-tertiary); pointer-events: none; }
.skd-search-input {
    width: 100%; padding: 5px 28px; font-size: 13px; color: var(--vort-text);
    background: transparent; border: none; outline: none;
}
.skd-search-input::placeholder { color: var(--vort-text-tertiary); }
.skd-search-clear {
    position: absolute; right: 6px; display: flex; align-items: center; justify-content: center;
    width: 18px; height: 18px; padding: 0; color: var(--vort-text-tertiary);
    background: none; border: none; border-radius: 50%; cursor: pointer;
}
.skd-search-clear:hover { color: var(--vort-text-secondary); background: var(--vort-bg-hover); }

.skd-list { flex: 1; overflow-y: auto; padding-top: 8px; }

.skd-row {
    display: flex; align-items: center; gap: 10px; padding: 10px 12px;
    border-radius: 8px; cursor: pointer; transition: background 0.12s;
}
.skd-row:hover { background: var(--vort-bg-hover, #f5f5f5); }
.skd-row-disabled { opacity: 0.5; cursor: not-allowed; }
.skd-row-disabled:hover { background: transparent; }

.skd-row-icon { flex-shrink: 0; display: flex; align-items: center; }
.skd-row-info { flex: 1; display: flex; align-items: center; gap: 8px; min-width: 0; }
.skd-row-title { font-size: 13px; color: var(--vort-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.skd-row-meta { font-size: 11px; color: var(--vort-text-tertiary); flex-shrink: 0; }

.skd-row-action { flex-shrink: 0; font-size: 12px; }
.skd-row-linked { color: var(--vort-text-tertiary); }
.skd-row-select {
    display: inline-flex; align-items: center; gap: 2px; color: var(--vort-primary);
    opacity: 0; transition: opacity 0.15s;
}
.skd-row:hover .skd-row-select { opacity: 1; }

.skd-row-arrow { flex-shrink: 0; color: var(--vort-text-quaternary); }

.skd-empty {
    display: flex; align-items: center; justify-content: center;
    min-height: 200px; font-size: 14px; color: var(--vort-text-tertiary);
}
</style>
