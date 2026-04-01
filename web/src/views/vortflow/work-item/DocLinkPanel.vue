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
                        >
                            <svg class="dlp-tab-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg"><path d="M284.417081 0a166.911207 166.911207 0 0 0-166.911207 166.655208v691.196717A166.655208 166.655208 0 0 0 284.417081 1023.995136h520.445528A166.655208 166.655208 0 0 0 972.797811 856.82793V343.294369a63.2317 63.2317 0 0 0-18.431912-44.799787L673.279234 18.431912A64.511694 64.511694 0 0 0 628.479447 0z" fill="#3F70FF"/><path d="M953.341904 298.494582L673.279234 18.431912A63.743697 63.743697 0 0 0 639.999392 1.279994a6.143971 6.143971 0 0 0-7.167966 6.39997v135.423356a195.071073 195.071073 0 0 0 195.071073 195.071074h135.423357a6.143971 6.143971 0 0 0 6.143971-7.167966 61.439708 61.439708 0 0 0-16.127923-32.511846z" fill="#2A58D8"/><path d="M835.582463 307.198541h124.671408a55.295737 55.295737 0 0 0-6.911967-8.44796L673.279234 18.431912a71.167662 71.167662 0 0 0-7.679964-6.911967v124.415409A171.007188 171.007188 0 0 0 835.582463 307.198541z" fill="#C6E1FF"/><path d="M253.185229 273.918699m33.79184 0l274.942694 0q33.791839 0 33.791839 33.791839l0 0.255999q0 33.791839-33.791839 33.79184l-274.942694 0q-33.791839 0-33.79184-33.79184l0-0.255999q0-33.791839 33.79184-33.791839Z" fill="#FFF"/><path d="M253.185229 478.461727m33.79184 0l482.04571 0q33.791839 0 33.79184 33.79184l0 0.255999q0 33.791839-33.79184 33.791839l-482.04571 0q-33.791839 0-33.79184-33.791839l0-0.255999q0-33.791839 33.79184-33.79184Z" fill="#FFF"/><path d="M253.185229 683.004756m33.79184 0l482.04571 0q33.791839 0 33.79184 33.791839l0 0.255999q0 33.791839-33.79184 33.791839l-482.04571 0q-33.791839 0-33.79184-33.791839l0-0.255999q0-33.791839 33.79184-33.791839Z" fill="#FFF"/></svg>
                            <span class="dlp-tab-title">{{ doc.title }}</span>
                            <Dropdown trigger="click" placement="bottomRight" @click.stop>
                                <button
                                    type="button"
                                    class="dlp-tab-more-btn"
                                    @click.stop
                                >
                                    <MoreVertical :size="14" />
                                </button>
                                <template #overlay>
                                    <DropdownMenuItem @click.stop="handleMoveToFirst(doc)">
                                        <ArrowLeftToLine :size="14" />
                                        移到最前
                                    </DropdownMenuItem>
                                    <DropdownMenuItem @click.stop="handleCopyLink(doc)">
                                        <Link :size="14" />
                                        复制链接
                                    </DropdownMenuItem>
                                    <DropdownMenuItem @click.stop="handleRenameTab(doc)">
                                        <Pencil :size="14" />
                                        修改页面名称
                                    </DropdownMenuItem>
                                    <DropdownMenuItem @click.stop="handleUnlinkDoc(doc)" class="dlp-menu-danger">
                                        <Trash2 :size="14" />
                                        删除
                                    </DropdownMenuItem>
                                </template>
                            </Dropdown>
                        </div>
                    </div>
                </div>
                <button type="button" class="dlp-tab-add" title="添加文档" @click="showAddOptions = true">
                    <Plus :size="16" />
                </button>
            </div>

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
import { ref, computed, watch, nextTick } from "vue";
import { message } from "@openvort/vort-ui";
import { Dropdown, DropdownMenuItem } from "@openvort/vort-ui";
import {
    FileText, FileSearch, Upload, FilePlus, Plus, ChevronRight,
    MoreVertical, Pencil, Save, X, Trash2, Link, Loader2, ArrowLeft,
    ArrowLeftToLine,
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

// ---- Tab Actions ----

const handleMoveToFirst = (doc: LinkedDoc) => {
    const idx = linkedDocs.value.findIndex((d) => d.link_id === doc.link_id);
    if (idx > 0) {
        const removed = linkedDocs.value.splice(idx, 1);
        if (removed[0]) linkedDocs.value.unshift(removed[0]);
    }
};

const handleCopyLink = (doc: LinkedDoc) => {
    const url = `${window.location.origin}/knowledge/doc/${doc.document_id}`;
    navigator.clipboard.writeText(url).then(() => message.success("链接已复制")).catch(() => message.error("复制失败"));
};

const handleRenameTab = (doc: LinkedDoc) => {
    activateDoc(doc.document_id);
    nextTick(() => {
        if (activeDocData.value) startRename(activeDocData.value);
    });
};

const handleUnlinkDoc = async (doc: LinkedDoc) => {
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
    display: flex; align-items: stretch;
    border-bottom: 1px solid var(--vort-border-secondary, #e8e8e8);
    min-height: 36px;
}
.dlp-tabs-scroll {
    flex: 1; overflow-x: auto; overflow-y: hidden; min-width: 0;
    scrollbar-width: none;
}
.dlp-tabs-scroll::-webkit-scrollbar { display: none; }
.dlp-tabs-inner { display: flex; height: 100%; }

.dlp-tab {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 0 10px; font-size: 13px; color: var(--vort-text-secondary);
    white-space: nowrap; cursor: pointer;
    transition: background 0.15s; flex-shrink: 0;
    position: relative; max-width: 180px;
}
.dlp-tab:hover { background: var(--vort-bg-hover, #f0f0f0); }
.dlp-tab-active {
    color: var(--vort-text); background: var(--vort-bg-hover, #f0f0f0);
    font-weight: 500;
}
.dlp-tab-icon { flex-shrink: 0; width: 16px; height: 16px; }
.dlp-tab-title { overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0; }

.dlp-tab-more-btn {
    display: none; align-items: center; justify-content: center;
    width: 22px; height: 22px; padding: 0; flex-shrink: 0;
    color: var(--vort-text-tertiary); background: none; border: none;
    border-radius: 4px; cursor: pointer; margin-left: 2px;
}
.dlp-tab:hover .dlp-tab-more-btn,
.dlp-tab-active .dlp-tab-more-btn { display: inline-flex; }
.dlp-tab-more-btn:hover { color: var(--vort-text); background: rgba(0,0,0,0.08); }

.dlp-menu-danger { color: #dc2626 !important; }

.dlp-tab-add {
    display: flex; align-items: center; justify-content: center;
    width: 36px; flex-shrink: 0; padding: 0;
    color: var(--vort-text-tertiary); background: none; border: none;
    cursor: pointer; transition: color 0.15s;
}
.dlp-tab-add:hover { color: var(--vort-primary); }

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
