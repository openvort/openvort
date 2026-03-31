<template>
    <div class="dlp">
        <!-- State: Add Options -->
        <template v-if="showAddOptions">
            <div class="dlp-add-options">
                <div class="dlp-add-card" @click="openSelectDialog">
                    <FileSearch :size="28" class="dlp-add-icon text-blue-500" />
                    <span class="dlp-add-label">选择文档</span>
                    <span class="dlp-add-desc">从知识库选择</span>
                    <ChevronRight :size="16" class="dlp-add-arrow" />
                </div>
                <div class="dlp-add-card" @click="triggerUpload">
                    <Upload :size="28" class="dlp-add-icon text-green-500" />
                    <span class="dlp-add-label">上传文档</span>
                    <span class="dlp-add-desc">PDF / Word / Markdown / TXT</span>
                    <ChevronRight :size="16" class="dlp-add-arrow" />
                </div>
                <div class="dlp-add-card" @click="handleCreateNew">
                    <FilePlus :size="28" class="dlp-add-icon text-purple-500" />
                    <span class="dlp-add-label">新建文档</span>
                    <span class="dlp-add-desc">创建空白文档</span>
                    <ChevronRight :size="16" class="dlp-add-arrow" />
                </div>
            </div>
            <div v-if="linkedDocs.length > 0" class="dlp-add-back">
                <button type="button" class="dlp-back-btn" @click="showAddOptions = false">
                    <ArrowLeft :size="14" />
                    返回文档列表
                </button>
            </div>
        </template>

        <!-- State: Tab View -->
        <template v-else-if="linkedDocs.length > 0">
            <!-- Tab Bar -->
            <div class="dlp-tab-bar">
                <div class="dlp-tabs-scroll" ref="tabsScrollRef">
                    <div class="dlp-tabs-inner">
                        <div
                            v-for="doc in linkedDocs"
                            :key="doc.link_id"
                            class="dlp-tab"
                            :class="{ 'dlp-tab-active': activeDocId === doc.document_id }"
                            @click="activateDoc(doc.document_id)"
                            @contextmenu.prevent="openContextMenu($event, doc)"
                        >
                            <FileText :size="14" class="dlp-tab-icon" />
                            <span class="dlp-tab-title">{{ doc.title }}</span>
                        </div>
                    </div>
                </div>
                <div class="dlp-tab-actions">
                    <Dropdown v-if="linkedDocs.length > 3" trigger="click" placement="bottomRight">
                        <button type="button" class="dlp-tab-more" title="更多文档">
                            <MoreHorizontal :size="16" />
                        </button>
                        <template #overlay>
                            <DropdownMenuItem
                                v-for="doc in linkedDocs"
                                :key="doc.link_id"
                                @click="activateDoc(doc.document_id)"
                            >
                                <FileText :size="14" class="mr-1.5 text-gray-400" />
                                {{ doc.title }}
                            </DropdownMenuItem>
                        </template>
                    </Dropdown>
                    <button type="button" class="dlp-tab-add" title="添加文档" @click="showAddOptions = true">
                        <Plus :size="16" />
                    </button>
                </div>
            </div>

            <!-- Context Menu (teleported) -->
            <Teleport to="body">
                <div
                    v-if="ctxMenu.visible"
                    class="dlp-ctx-menu"
                    :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
                    @click="ctxMenu.visible = false"
                >
                    <button type="button" class="dlp-ctx-item" @click="handleCopyLink">
                        <Link :size="14" />
                        复制链接
                    </button>
                    <button type="button" class="dlp-ctx-item" @click="handleRenameTab">
                        <Pencil :size="14" />
                        修改页面名称
                    </button>
                    <div class="dlp-ctx-sep"></div>
                    <button type="button" class="dlp-ctx-item dlp-ctx-danger" @click="handleUnlinkDoc">
                        <Trash2 :size="14" />
                        取消关联
                    </button>
                </div>
            </Teleport>

            <!-- Document Content -->
            <div class="dlp-content">
                <template v-if="docLoading">
                    <div class="dlp-content-loading">
                        <Loader2 :size="20" class="animate-spin text-gray-400" />
                        <span class="text-sm text-gray-400">加载中...</span>
                    </div>
                </template>
                <template v-else-if="activeDocData">
                    <!-- Title & Toolbar -->
                    <div class="dlp-content-header">
                        <template v-if="renaming">
                            <input
                                ref="renameInputRef"
                                v-model="renameDraft"
                                class="dlp-rename-input"
                                @blur="saveRename"
                                @keydown.enter="saveRename"
                                @keydown.escape="renaming = false"
                            />
                        </template>
                        <h3 v-else class="dlp-content-title" @dblclick="startRename(activeDocData!)">{{ activeDocData.title }}</h3>
                        <div class="dlp-content-actions">
                            <template v-if="editing">
                                <button type="button" class="dlp-action-btn" @click="cancelEdit">
                                    <X :size="14" />
                                    取消
                                </button>
                                <button type="button" class="dlp-action-btn dlp-action-primary" @click="saveEdit" :disabled="saving">
                                    <Save :size="14" />
                                    {{ saving ? "保存中..." : "保存" }}
                                </button>
                            </template>
                            <button v-else type="button" class="dlp-action-btn" @click="startEdit">
                                <Pencil :size="14" />
                                编辑
                            </button>
                        </div>
                    </div>

                    <!-- Editor / Viewer -->
                    <div class="dlp-content-body">
                        <VortEditor
                            v-if="editing"
                            v-model="editContent"
                            placeholder="请输入文档内容..."
                            min-height="360px"
                        />
                        <MarkdownView v-else :content="activeDocData.content || ''" />
                    </div>
                </template>
            </div>
        </template>

        <!-- State: Empty (loading) -->
        <template v-else>
            <div v-if="loading" class="dlp-empty">
                <Loader2 :size="24" class="animate-spin text-gray-300" />
            </div>
            <div v-else class="dlp-empty">
                <FileText :size="32" class="dlp-empty-icon" />
                <span>暂无关联文档</span>
                <button type="button" class="dlp-empty-add" @click="showAddOptions = true">
                    <Plus :size="14" />
                    添加文档
                </button>
            </div>
        </template>

        <!-- Hidden file input -->
        <input ref="fileInputRef" type="file" class="hidden" accept=".pdf,.docx,.doc,.md,.markdown,.txt,.text" @change="handleFileSelected" />

        <!-- Select KB Doc Dialog -->
        <SelectKBDocDialog
            v-model:open="selectDialogOpen"
            :linked-doc-ids="linkedDocIds"
            @select="handleDocSelected"
        />
    </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from "vue";
import { message } from "@openvort/vort-ui";
import { Dropdown, DropdownMenuItem } from "@openvort/vort-ui";
import {
    FileText, FileSearch, Upload, FilePlus, Plus, ChevronRight,
    MoreHorizontal, Pencil, Save, X, Trash2, Link, Loader2, ArrowLeft,
} from "lucide-vue-next";
import VortEditor from "@/components/vort-biz/editor/VortEditor.vue";
import MarkdownView from "@/components/vort-biz/editor/MarkdownView.vue";
import SelectKBDocDialog from "./SelectKBDocDialog.vue";
import {
    getVortflowDocLinks,
    createVortflowDocLink,
    createVortflowDocWithLink,
    uploadVortflowDocWithLink,
    deleteVortflowDocLink,
} from "@/api";
import { getKBDocument, updateKBDocument } from "@/api";

interface Props {
    entityType: string;
    entityId: string;
    projectId: string;
}

const props = defineProps<Props>();

interface LinkedDoc {
    link_id: string;
    document_id: string;
    title: string;
    file_type: string;
    sort_order: number;
}

interface DocData {
    id: string;
    title: string;
    content: string;
    file_type: string;
}

const loading = ref(false);
const linkedDocs = ref<LinkedDoc[]>([]);
const activeDocId = ref("");
const activeDocData = ref<DocData | null>(null);
const docLoading = ref(false);
const showAddOptions = ref(false);
const selectDialogOpen = ref(false);
const editing = ref(false);
const editContent = ref("");
const saving = ref(false);
const renaming = ref(false);
const renameDraft = ref("");
const renameInputRef = ref<HTMLInputElement | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const tabsScrollRef = ref<HTMLDivElement | null>(null);

const linkedDocIds = computed(() => linkedDocs.value.map((d) => d.document_id));

const ctxMenu = ref({
    visible: false,
    x: 0,
    y: 0,
    doc: null as LinkedDoc | null,
});

const closeCtxMenu = () => { ctxMenu.value.visible = false; };

onMounted(() => { document.addEventListener("click", closeCtxMenu); });
onUnmounted(() => { document.removeEventListener("click", closeCtxMenu); });

// ---- Data Loading ----

const loadLinks = async () => {
    if (!props.entityId) return;
    loading.value = true;
    try {
        const res = await getVortflowDocLinks({
            entity_type: props.entityType,
            entity_id: props.entityId,
        }) as any;
        linkedDocs.value = (res?.items || []).map((item: any) => ({
            link_id: item.link_id,
            document_id: item.document_id,
            title: item.title,
            file_type: item.file_type,
            sort_order: item.sort_order,
        }));
        const first = linkedDocs.value[0];
        if (first && !activeDocId.value) {
            activateDoc(first.document_id);
        } else if (linkedDocs.value.length === 0) {
            activeDocId.value = "";
            activeDocData.value = null;
            showAddOptions.value = true;
        }
    } catch {
        linkedDocs.value = [];
    } finally {
        loading.value = false;
    }
};

const loadDocContent = async (docId: string) => {
    docLoading.value = true;
    activeDocData.value = null;
    editing.value = false;
    try {
        const res = await getKBDocument(docId) as any;
        activeDocData.value = {
            id: res.id,
            title: res.title,
            content: res.content || "",
            file_type: res.file_type,
        };
    } catch {
        message.error("文档加载失败");
    } finally {
        docLoading.value = false;
    }
};

const activateDoc = (docId: string) => {
    if (activeDocId.value === docId && activeDocData.value) return;
    activeDocId.value = docId;
    loadDocContent(docId);
};

// ---- Add: Select from KB ----

const openSelectDialog = () => { selectDialogOpen.value = true; };

const handleDocSelected = async (doc: { id: string; title: string }) => {
    try {
        const res = await createVortflowDocLink({
            document_id: doc.id,
            entity_type: props.entityType,
            entity_id: props.entityId,
        }) as any;
        if (res?.error) { message.error(res.error); return; }
        message.success("关联成功");
        selectDialogOpen.value = false;
        showAddOptions.value = false;
        await loadLinks();
        activateDoc(doc.id);
    } catch {
        message.error("关联失败");
    }
};

// ---- Add: Upload ----

const triggerUpload = () => { fileInputRef.value?.click(); };

const handleFileSelected = async (e: Event) => {
    const target = e.target as HTMLInputElement;
    const file = target.files?.[0];
    if (!file) return;
    target.value = "";

    try {
        message.info("正在上传...");
        const res = await uploadVortflowDocWithLink(
            file,
            props.entityType,
            props.entityId,
            props.projectId,
        ) as any;
        if (res?.error) { message.error(res.error); return; }
        message.success("上传并关联成功");
        showAddOptions.value = false;
        await loadLinks();
        if (res.document_id) activateDoc(res.document_id);
    } catch {
        message.error("上传失败");
    }
};

// ---- Add: Create New ----

const handleCreateNew = async () => {
    try {
        const res = await createVortflowDocWithLink({
            title: "无标题文档",
            content: "",
            entity_type: props.entityType,
            entity_id: props.entityId,
            project_id: props.projectId,
        }) as any;
        if (res?.error) { message.error(res.error); return; }
        showAddOptions.value = false;
        await loadLinks();
        if (res.document_id) {
            activateDoc(res.document_id);
            await nextTick();
            startRenameById(res.document_id);
        }
    } catch {
        message.error("创建失败");
    }
};

// ---- Edit Document Content ----

const startEdit = () => {
    if (!activeDocData.value) return;
    editContent.value = activeDocData.value.content;
    editing.value = true;
};

const cancelEdit = () => { editing.value = false; };

const saveEdit = async () => {
    if (!activeDocData.value) return;
    saving.value = true;
    try {
        await updateKBDocument(activeDocData.value.id, { content: editContent.value });
        activeDocData.value.content = editContent.value;
        editing.value = false;
        message.success("保存成功");
    } catch {
        message.error("保存失败");
    } finally {
        saving.value = false;
    }
};

// ---- Rename ----

const startRename = (doc: DocData) => {
    renameDraft.value = doc.title;
    renaming.value = true;
    nextTick(() => { renameInputRef.value?.focus(); renameInputRef.value?.select(); });
};

const startRenameById = (docId: string) => {
    if (activeDocData.value && activeDocData.value.id === docId) {
        startRename(activeDocData.value);
    }
};

const saveRename = async () => {
    if (!activeDocData.value || !renameDraft.value.trim()) { renaming.value = false; return; }
    const newTitle = renameDraft.value.trim();
    if (newTitle === activeDocData.value.title) { renaming.value = false; return; }
    try {
        await updateKBDocument(activeDocData.value.id, { title: newTitle });
        activeDocData.value.title = newTitle;
        const linked = linkedDocs.value.find((d) => d.document_id === activeDocData.value!.id);
        if (linked) linked.title = newTitle;
        message.success("重命名成功");
    } catch {
        message.error("重命名失败");
    } finally {
        renaming.value = false;
    }
};

// ---- Context Menu ----

const openContextMenu = (e: MouseEvent, doc: LinkedDoc) => {
    ctxMenu.value = { visible: true, x: e.clientX, y: e.clientY, doc };
};

const handleCopyLink = () => {
    const doc = ctxMenu.value.doc;
    if (!doc) return;
    const url = `${window.location.origin}/knowledge/doc/${doc.document_id}`;
    navigator.clipboard.writeText(url).then(() => message.success("链接已复制")).catch(() => message.error("复制失败"));
};

const handleRenameTab = () => {
    const doc = ctxMenu.value.doc;
    if (!doc) return;
    activateDoc(doc.document_id);
    nextTick(() => {
        if (activeDocData.value) startRename(activeDocData.value);
    });
};

const handleUnlinkDoc = async () => {
    const doc = ctxMenu.value.doc;
    if (!doc) return;
    try {
        await deleteVortflowDocLink(doc.link_id);
        message.success("已取消关联");
        if (activeDocId.value === doc.document_id) {
            activeDocId.value = "";
            activeDocData.value = null;
        }
        await loadLinks();
    } catch {
        message.error("操作失败");
    }
};

// ---- Init ----

watch(() => props.entityId, () => {
    activeDocId.value = "";
    activeDocData.value = null;
    showAddOptions.value = false;
    editing.value = false;
    loadLinks();
}, { immediate: true });
</script>

<style scoped>
.dlp { display: flex; flex-direction: column; min-height: 200px; }

/* ---- Add Options ---- */
.dlp-add-options {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
    padding: 24px 0;
}
.dlp-add-card {
    display: flex; flex-direction: column; align-items: flex-start; gap: 6px;
    padding: 20px 16px; border: 1px solid var(--vort-border-secondary);
    border-radius: 10px; cursor: pointer; position: relative; transition: all 0.15s;
}
.dlp-add-card:hover {
    border-color: var(--vort-primary); background: var(--vort-primary-bg, #eff6ff);
}
.dlp-add-icon { margin-bottom: 4px; }
.dlp-add-label { font-size: 14px; font-weight: 500; color: var(--vort-text); }
.dlp-add-desc { font-size: 12px; color: var(--vort-text-tertiary); }
.dlp-add-arrow {
    position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
    color: var(--vort-text-quaternary); transition: color 0.15s;
}
.dlp-add-card:hover .dlp-add-arrow { color: var(--vort-primary); }

.dlp-add-back { display: flex; justify-content: center; margin-top: 4px; }
.dlp-back-btn {
    display: inline-flex; align-items: center; gap: 4px; padding: 6px 14px;
    font-size: 13px; color: var(--vort-text-secondary); background: none;
    border: 1px solid var(--vort-border); border-radius: 6px; cursor: pointer;
}
.dlp-back-btn:hover { color: var(--vort-primary); border-color: var(--vort-primary); }

/* ---- Tab Bar ---- */
.dlp-tab-bar {
    display: flex; align-items: center; gap: 0;
    border-bottom: 1px solid var(--vort-border-secondary);
}
.dlp-tabs-scroll {
    flex: 1; overflow-x: auto; overflow-y: hidden; min-width: 0;
    scrollbar-width: none;
}
.dlp-tabs-scroll::-webkit-scrollbar { display: none; }
.dlp-tabs-inner { display: flex; }

.dlp-tab {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 14px; font-size: 13px; color: var(--vort-text-secondary);
    white-space: nowrap; cursor: pointer; border-bottom: 2px solid transparent;
    transition: all 0.15s; flex-shrink: 0;
}
.dlp-tab:hover { color: var(--vort-text); background: var(--vort-bg-hover, #f5f5f5); }
.dlp-tab-active {
    color: var(--vort-primary); border-bottom-color: var(--vort-primary);
    font-weight: 500;
}
.dlp-tab-icon { flex-shrink: 0; }
.dlp-tab-title { max-width: 140px; overflow: hidden; text-overflow: ellipsis; }

.dlp-tab-actions { display: flex; align-items: center; gap: 2px; padding: 0 4px; flex-shrink: 0; }
.dlp-tab-more, .dlp-tab-add {
    display: flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; padding: 0; color: var(--vort-text-tertiary);
    background: none; border: none; border-radius: 6px; cursor: pointer;
}
.dlp-tab-more:hover, .dlp-tab-add:hover { color: var(--vort-primary); background: var(--vort-primary-bg, #eff6ff); }

/* ---- Context Menu ---- */
.dlp-ctx-menu {
    position: fixed; z-index: 9999; min-width: 160px;
    background: var(--vort-bg, #fff); border: 1px solid var(--vort-border);
    border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.12);
    padding: 4px;
}
.dlp-ctx-item {
    display: flex; align-items: center; gap: 8px; width: 100%;
    padding: 8px 12px; font-size: 13px; color: var(--vort-text);
    background: none; border: none; border-radius: 6px; cursor: pointer; text-align: left;
}
.dlp-ctx-item:hover { background: var(--vort-bg-hover, #f5f5f5); }
.dlp-ctx-danger { color: #dc2626; }
.dlp-ctx-danger:hover { background: #fef2f2; }
.dlp-ctx-sep { height: 1px; margin: 4px 8px; background: var(--vort-border-secondary); }

/* ---- Content ---- */
.dlp-content { flex: 1; padding-top: 12px; }
.dlp-content-loading {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    min-height: 200px;
}
.dlp-content-header {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    margin-bottom: 12px;
}
.dlp-content-title {
    font-size: 15px; font-weight: 600; color: var(--vort-text);
    cursor: default; margin: 0;
}
.dlp-content-actions { display: flex; align-items: center; gap: 6px; }

.dlp-action-btn {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 5px 12px; font-size: 13px; color: var(--vort-text-secondary);
    background: var(--vort-bg); border: 1px solid var(--vort-border);
    border-radius: 6px; cursor: pointer; transition: all 0.15s;
}
.dlp-action-btn:hover { color: var(--vort-text); border-color: var(--vort-text-tertiary); }
.dlp-action-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.dlp-action-primary {
    color: #fff; background: var(--vort-primary); border-color: var(--vort-primary);
}
.dlp-action-primary:hover { opacity: 0.9; color: #fff; }

.dlp-rename-input {
    flex: 1; font-size: 15px; font-weight: 600; color: var(--vort-text);
    padding: 2px 8px; border: 1px solid var(--vort-primary); border-radius: 4px;
    outline: none; background: var(--vort-bg);
}

.dlp-content-body {
    border: 1px solid var(--vort-border-secondary); border-radius: 8px;
    padding: 16px; min-height: 200px; background: var(--vort-bg);
}

/* ---- Empty ---- */
.dlp-empty {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 12px; padding: 48px 20px; color: var(--vort-text-tertiary); font-size: 14px;
}
.dlp-empty-icon { color: var(--vort-text-quaternary, #d0d5dd); }
.dlp-empty-add {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 6px 16px; font-size: 13px; color: var(--vort-primary);
    background: none; border: 1px solid var(--vort-primary); border-radius: 6px;
    cursor: pointer; margin-top: 4px; transition: background 0.15s;
}
.dlp-empty-add:hover { background: var(--vort-primary-bg, #eff6ff); }
</style>
