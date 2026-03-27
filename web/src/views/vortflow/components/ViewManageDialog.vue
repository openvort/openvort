<script setup lang="ts">
import { ref, computed, watch, nextTick } from "vue";
import { Dialog, Button, Input, Checkbox } from "@openvort/vort-ui";
import { GripVertical, Pencil, Trash2, Check, X, Search } from "lucide-vue-next";
import ViewCreateDialog from "./ViewCreateDialog.vue";
import { useVortFlowStore } from "@/stores";
import { SYSTEM_VIEWS } from "../composables/useVortFlowViews";
import type { CustomView } from "@/stores/modules/vortflow";

interface ManagedView {
    id: string;
    name: string;
    scope: "system" | "shared" | "personal";
    visible: boolean;
    editable: boolean;
}

const props = defineProps<{
    workItemType?: string;
    currentFilters?: Record<string, any>;
    currentColumns?: Array<{ key: string; visible: boolean }>;
}>();
const open = defineModel<boolean>("open", { default: false });
const store = useVortFlowStore();

const searchKeyword = ref("");
const showCreateDialog = ref(false);
const editingId = ref<string | null>(null);
const editingName = ref("");
const editInputRef = ref<HTMLInputElement | null>(null);

// Drag state
const dragIndex = ref<number | null>(null);
const dragOverIndex = ref<number | null>(null);

const managedViews = computed<ManagedView[]>(() => {
    const systemList: ManagedView[] = SYSTEM_VIEWS.map(v => ({
        id: v.id,
        name: v.name,
        scope: v.scope as "system" | "shared",
        visible: true,
        editable: false,
    }));
    const customList: ManagedView[] = [...store.customViews]
        .sort((a, b) => a.order - b.order)
        .map(v => ({
            id: v.id,
            name: v.name,
            scope: v.scope,
            visible: v.visible,
            editable: true,
        }));
    return [...systemList, ...customList];
});

const filteredViews = computed(() => {
    const kw = searchKeyword.value.trim().toLowerCase();
    if (!kw) return managedViews.value;
    return managedViews.value.filter(v => v.name.toLowerCase().includes(kw));
});

const scopeLabel = (scope: string) => {
    if (scope === "system") return "系统";
    if (scope === "shared") return "公共";
    return "个人";
};

const handleCreateView = async (data: { name: string; scope: "personal" | "shared" }) => {
    const maxOrder = store.customViews.reduce((max, v) => Math.max(max, v.order), -1);
    await store.addCustomView({
        name: data.name,
        work_item_type: props.workItemType || "缺陷",
        scope: data.scope,
        visible: true,
        filters: props.currentFilters ?? {},
        columns: props.currentColumns ?? [],
        order: maxOrder + 1,
    });
    showCreateDialog.value = false;
};

const handleDeleteView = (id: string) => {
    store.deleteCustomView(id);
};

const handleToggleView = (view: ManagedView) => {
    store.toggleViewVisibility(view.id, !view.visible);
};

const startEditing = (view: ManagedView) => {
    if (!view.editable) return;
    editingId.value = view.id;
    editingName.value = view.name;
    nextTick(() => editInputRef.value?.focus());
};

const confirmEditing = () => {
    const trimmed = editingName.value.trim();
    if (!trimmed || !editingId.value) {
        cancelEditing();
        return;
    }
    store.updateCustomView(editingId.value, { name: trimmed });
    editingId.value = null;
    editingName.value = "";
};

const cancelEditing = () => {
    editingId.value = null;
    editingName.value = "";
};

const handleEditKeydown = (e: KeyboardEvent) => {
    if (e.key === "Enter") confirmEditing();
    else if (e.key === "Escape") cancelEditing();
};

// --- HTML5 drag-and-drop for custom views ---

const customViewIds = computed(() =>
    [...store.customViews].sort((a, b) => a.order - b.order).map(v => v.id)
);

const isCustomView = (id: string) => store.customViews.some(v => v.id === id);

const getCustomDragIndex = (viewId: string): number => customViewIds.value.indexOf(viewId);

const onDragStart = (e: DragEvent, view: ManagedView) => {
    if (!view.editable) { e.preventDefault(); return; }
    dragIndex.value = getCustomDragIndex(view.id);
    e.dataTransfer!.effectAllowed = "move";
    e.dataTransfer!.setData("text/plain", view.id);
};

const onDragOver = (e: DragEvent, view: ManagedView) => {
    if (!isCustomView(view.id)) return;
    e.preventDefault();
    e.dataTransfer!.dropEffect = "move";
    dragOverIndex.value = getCustomDragIndex(view.id);
};

const onDragLeave = () => {
    dragOverIndex.value = null;
};

const onDrop = (e: DragEvent, view: ManagedView) => {
    e.preventDefault();
    const fromId = e.dataTransfer!.getData("text/plain");
    const toId = view.id;
    if (!fromId || fromId === toId || !isCustomView(toId)) return;

    const ids = [...customViewIds.value];
    const fromIdx = ids.indexOf(fromId);
    const toIdx = ids.indexOf(toId);
    if (fromIdx === -1 || toIdx === -1) return;

    ids.splice(fromIdx, 1);
    ids.splice(toIdx, 0, fromId);
    store.reorderViews(ids);

    dragIndex.value = null;
    dragOverIndex.value = null;
};

const onDragEnd = () => {
    dragIndex.value = null;
    dragOverIndex.value = null;
};

watch(open, (v) => {
    if (v) {
        searchKeyword.value = "";
        editingId.value = null;
    }
});
</script>

<template>
    <Dialog v-model:open="open" title="视图管理" width="680px">
        <div class="view-manage-content">
            <div class="view-manage-toolbar">
                <div class="search-wrapper">
                    <Input
                        v-model:value="searchKeyword"
                        placeholder="请输入视图名称"
                        allow-clear
                        size="small"
                    >
                        <template #suffix>
                            <Search :size="14" class="text-gray-400" />
                        </template>
                    </Input>
                </div>
                <Button type="primary" @click="showCreateDialog = true">
                    新建视图
                </Button>
            </div>

            <div class="view-list-header">
                <span class="col-order">顺序</span>
                <span class="col-name">名称</span>
                <span class="col-type">类型</span>
                <span class="col-show">显示</span>
                <span class="col-ops">操作</span>
            </div>

            <div class="view-list">
                <div
                    v-for="view in filteredViews"
                    :key="view.id"
                    class="view-list-row"
                    :class="{
                        'is-dragging': dragIndex !== null && isCustomView(view.id) && getCustomDragIndex(view.id) === dragIndex,
                        'drag-over': dragOverIndex !== null && isCustomView(view.id) && getCustomDragIndex(view.id) === dragOverIndex,
                    }"
                    :draggable="view.editable"
                    @dragstart="onDragStart($event, view)"
                    @dragover="onDragOver($event, view)"
                    @dragleave="onDragLeave"
                    @drop="onDrop($event, view)"
                    @dragend="onDragEnd"
                >
                    <span class="col-order">
                        <GripVertical
                            :size="14"
                            class="drag-handle"
                            :class="view.editable ? 'cursor-grab text-gray-400' : 'text-gray-200 cursor-not-allowed'"
                        />
                    </span>
                    <span class="col-name">
                        <template v-if="editingId === view.id">
                            <div class="inline-edit-wrapper">
                                <input
                                    ref="editInputRef"
                                    v-model="editingName"
                                    class="inline-edit-input"
                                    maxlength="20"
                                    @keydown="handleEditKeydown"
                                    @blur="confirmEditing"
                                />
                                <button type="button" class="inline-edit-btn confirm" @mousedown.prevent="confirmEditing">
                                    <Check :size="14" />
                                </button>
                                <button type="button" class="inline-edit-btn cancel" @mousedown.prevent="cancelEditing">
                                    <X :size="14" />
                                </button>
                            </div>
                        </template>
                        <template v-else>{{ view.name }}</template>
                    </span>
                    <span class="col-type">{{ scopeLabel(view.scope) }}</span>
                    <span class="col-show">
                        <Checkbox
                            :checked="view.visible"
                            :disabled="!view.editable"
                            @update:checked="handleToggleView(view)"
                        />
                    </span>
                    <span class="col-ops">
                        <button
                            type="button"
                            class="op-btn"
                            :disabled="!view.editable"
                            @click="view.editable && startEditing(view)"
                        >
                            <Pencil :size="14" />
                        </button>
                        <button
                            type="button"
                            class="op-btn"
                            :disabled="!view.editable"
                            @click="view.editable && handleDeleteView(view.id)"
                        >
                            <Trash2 :size="14" />
                        </button>
                    </span>
                </div>
            </div>
        </div>

        <template #footer>
            <Button @click="open = false">关闭</Button>
        </template>
    </Dialog>

    <ViewCreateDialog v-model:open="showCreateDialog" @create="handleCreateView" />
</template>

<style scoped>
.view-manage-content {
    min-height: 300px;
}
.view-manage-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
}
.search-wrapper {
    flex: 1;
}
.view-list-header {
    display: flex;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #f0f0f0;
    font-size: 12px;
    color: #999;
}
.view-list-row {
    display: flex;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid #f5f5f5;
    font-size: 13px;
    transition: background 0.15s;
}
.view-list-row:hover {
    background: rgba(0, 0, 0, 0.02);
}
.view-list-row.is-dragging {
    opacity: 0.4;
}
.view-list-row.drag-over {
    border-top: 2px solid var(--vort-primary);
}
.col-order { width: 50px; text-align: center; flex-shrink: 0; }
.col-name { flex: 1; min-width: 0; }
.col-type { width: 80px; text-align: center; flex-shrink: 0; color: #666; }
.col-show { width: 60px; text-align: center; flex-shrink: 0; }
.col-ops { width: 80px; display: flex; gap: 4px; justify-content: center; flex-shrink: 0; }
.op-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: #999;
    cursor: pointer;
    transition: all 0.2s;
}
.op-btn:hover:not(:disabled) {
    color: var(--vort-primary);
    background: var(--vort-primary-bg);
}
.op-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
}

.inline-edit-wrapper {
    display: flex;
    align-items: center;
    gap: 4px;
}
.inline-edit-input {
    height: 28px;
    padding: 0 8px;
    border: 1px solid #d9d9d9;
    border-radius: 4px;
    font-size: 13px;
    outline: none;
    width: 160px;
    transition: border-color 0.2s;
}
.inline-edit-input:focus {
    border-color: var(--vort-primary);
}
.inline-edit-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border: none;
    border-radius: 4px;
    background: transparent;
    cursor: pointer;
    transition: all 0.15s;
}
.inline-edit-btn.confirm {
    color: #52c41a;
}
.inline-edit-btn.confirm:hover {
    background: rgba(82, 196, 26, 0.1);
}
.inline-edit-btn.cancel {
    color: #999;
}
.inline-edit-btn.cancel:hover {
    color: #ff4d4f;
    background: rgba(255, 77, 79, 0.08);
}

.drag-handle {
    transition: color 0.15s;
}
</style>
