<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import {
    getKBDocuments, uploadKBDocument, createKBTextDocument,
    deleteKBDocument, reindexKBDocument, searchKB, getKBStats,
    getKBFolders, getKBFolder, createKBFolder, updateKBFolder, deleteKBFolder, moveKBItems,
} from "@/api";
import {
    Upload, Search, RefreshCw, FileText,
    CheckCircle, AlertCircle, Loader2, BookOpen, Trash2,
    ChevronRight, Home, MoreHorizontal, Plus,
} from "lucide-vue-next";
import { message, dialog } from "@openvort/vort-ui";
import type { UploadRequestOption } from "@openvort/vort-ui";
import { useUserStore } from "@/stores";

interface KBFolderItem {
    id: string;
    name: string;
    parent_id: string;
    description: string;
    owner_id: string;
    created_at: string;
    updated_at: string;
}

interface KBDocument {
    id: string;
    title: string;
    folder_id: string;
    file_name: string;
    file_type: string;
    file_size: number;
    status: string;
    error_message: string;
    chunk_count: number;
    owner_id: string;
    created_at: string;
    updated_at: string;
}

interface Breadcrumb {
    id: string;
    name: string;
}

interface ListRow {
    _type: "folder" | "document";
    _key: string;
    name: string;
    updated_at: string;
    raw: KBFolderItem | KBDocument;
}

interface SearchResult {
    document_id: string;
    document_title: string;
    chunk_index: number;
    content: string;
    score: number;
}

interface KBStatsData {
    document_count: number;
    ready_count: number;
    chunk_count: number;
    embedding_available: boolean;
}

const router = useRouter();
const userStore = useUserStore();
const isAdmin = computed(() => userStore.isAdmin);

const currentFolderId = ref("");
const breadcrumbs = ref<Breadcrumb[]>([]);

const folders = ref<KBFolderItem[]>([]);
const documents = ref<KBDocument[]>([]);
const loading = ref(false);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const keyword = ref("");
const stats = ref<KBStatsData>({ document_count: 0, ready_count: 0, chunk_count: 0, embedding_available: false });

const uploadDialogOpen = ref(false);
const textDialogOpen = ref(false);
const searchDialogOpen = ref(false);
const folderDialogOpen = ref(false);
const moveDialogOpen = ref(false);
const saving = ref(false);

const textForm = ref({ title: "", content: "" });
const folderForm = ref({ name: "" });
const searchQuery = ref("");

// Move dialog state
const moveItem = ref<{ type: "folder" | "document"; id: string; name: string } | null>(null);
const moveFolderTree = ref<KBFolderItem[]>([]);
const moveTargetId = ref("");
const moveLoading = ref(false);
const searchResults = ref<SearchResult[]>([]);
const searching = ref(false);

const renamingFolderId = ref("");
const renamingFolderName = ref("");

const statusConfig: Record<string, { text: string; color: string }> = {
    pending: { text: "等待处理", color: "warning" },
    processing: { text: "处理中", color: "processing" },
    ready: { text: "已就绪", color: "success" },
    error: { text: "处理失败", color: "error" },
};

const tableRows = computed<ListRow[]>(() => {
    const rows: ListRow[] = [];
    for (const f of folders.value) {
        rows.push({ _type: "folder", _key: `f_${f.id}`, name: f.name, updated_at: f.updated_at, raw: f });
    }
    for (const d of documents.value) {
        rows.push({ _type: "document", _key: `d_${d.id}`, name: d.title, updated_at: d.updated_at, raw: d });
    }
    return rows;
});

const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
};

const formatTime = (iso: string) => {
    if (!iso) return "-";
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
};

const navigateToFolder = async (folderId: string) => {
    currentFolderId.value = folderId;
    page.value = 1;
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

const loadContent = async () => {
    loading.value = true;
    try {
        const [foldersRes, docsRes] = await Promise.all([
            getKBFolders(currentFolderId.value),
            getKBDocuments({
                page: page.value,
                page_size: pageSize.value,
                keyword: keyword.value || undefined,
                folder_id: currentFolderId.value,
            }),
        ]) as [any, any];

        folders.value = foldersRes.items || [];
        documents.value = docsRes.items || [];
        total.value = docsRes.total || 0;
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "加载失败");
    } finally {
        loading.value = false;
    }
};

const loadStats = async () => {
    try {
        const res = await getKBStats() as any;
        stats.value = res;
    } catch {
        // ignore
    }
};

// ---- Row click ----
const handleRowClick = (row: ListRow) => {
    if (row._type === "folder") {
        navigateToFolder((row.raw as KBFolderItem).id);
    } else {
        router.push(`/knowledge/doc/${(row.raw as KBDocument).id}`);
    }
};

// ---- Folder actions ----
const handleCreateFolder = async () => {
    if (!folderForm.value.name.trim()) {
        message.warning("请输入文件夹名称");
        return;
    }
    saving.value = true;
    try {
        await createKBFolder({
            name: folderForm.value.name.trim(),
            parent_id: currentFolderId.value,
        });
        message.success("文件夹创建成功");
        folderDialogOpen.value = false;
        folderForm.value = { name: "" };
        loadContent();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "创建失败");
    } finally {
        saving.value = false;
    }
};

const startRenameFolder = (folder: KBFolderItem) => {
    renamingFolderId.value = folder.id;
    renamingFolderName.value = folder.name;
};

const confirmRenameFolder = async () => {
    if (!renamingFolderName.value.trim()) {
        message.warning("名称不能为空");
        return;
    }
    try {
        await updateKBFolder(renamingFolderId.value, { name: renamingFolderName.value.trim() });
        message.success("重命名成功");
        renamingFolderId.value = "";
        loadContent();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "重命名失败");
    }
};

const cancelRenameFolder = () => {
    renamingFolderId.value = "";
};

const handleDeleteFolder = (folder: KBFolderItem) => {
    dialog.confirm({
        title: "确认删除文件夹",
        content: `确定删除「${folder.name}」？文件夹内的子文件夹和文档将移到上一级目录。`,
        onOk: async () => {
            try {
                await deleteKBFolder(folder.id);
                message.success("删除成功");
                loadContent();
            } catch (e: any) {
                message.error(e?.response?.data?.detail || "删除失败");
            }
        },
    });
};

// ---- Document actions ----
const handleCustomUpload = ref(async (options: UploadRequestOption) => {
    try {
        const res = await uploadKBDocument(options.file, undefined, currentFolderId.value || undefined);
        options.onSuccess?.(res, options.file);
        message.success(`${options.file.name} 上传成功`);
        loadContent();
        loadStats();
    } catch (e: any) {
        options.onError?.(new Error(e?.response?.data?.detail || "上传失败"));
        message.error(`${options.file.name}: ${e?.response?.data?.detail || "上传失败"}`);
    }
});

const handleCreateText = async () => {
    if (!textForm.value.title.trim()) {
        message.warning("请输入文档标题");
        return;
    }
    if (!textForm.value.content.trim()) {
        message.warning("请输入文档内容");
        return;
    }

    saving.value = true;
    try {
        await createKBTextDocument({
            title: textForm.value.title,
            content: textForm.value.content,
            folder_id: currentFolderId.value || undefined,
        });
        message.success("文档创建成功");
        textDialogOpen.value = false;
        textForm.value = { title: "", content: "" };
        loadContent();
        loadStats();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "创建失败");
    } finally {
        saving.value = false;
    }
};

const handleDelete = (doc: KBDocument) => {
    dialog.confirm({
        title: "确认删除",
        content: `确定删除文档「${doc.title}」？此操作将同时删除所有关联的分块和向量数据，不可撤销。`,
        onOk: async () => {
            try {
                await deleteKBDocument(doc.id);
                message.success("删除成功");
                loadContent();
                loadStats();
            } catch (e: any) {
                message.error(e?.response?.data?.detail || "删除失败");
            }
        },
    });
};

const handleReindex = async (doc: KBDocument) => {
    try {
        await reindexKBDocument(doc.id);
        message.success("已开始重新索引");
        loadContent();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "重新索引失败");
    }
};

const handleSearch = async () => {
    if (!searchQuery.value.trim()) {
        message.warning("请输入搜索内容");
        return;
    }

    searching.value = true;
    try {
        const res = await searchKB(searchQuery.value) as any;
        searchResults.value = res.items || [];
        if (!searchResults.value.length) {
            message.info("未找到相关内容");
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "搜索失败");
    } finally {
        searching.value = false;
    }
};

const openDoc = (doc: KBDocument) => {
    router.push(`/knowledge/doc/${doc.id}`);
};

// ---- Move to folder ----
const openMoveDialog = async (type: "folder" | "document", id: string, name: string) => {
    moveItem.value = { type, id, name };
    moveTargetId.value = "";
    moveDialogOpen.value = true;
    moveLoading.value = true;
    try {
        const res = await getAllFolders() as KBFolderItem[];
        moveFolderTree.value = res.filter(f => f.id !== id);
    } catch {
        moveFolderTree.value = [];
    } finally {
        moveLoading.value = false;
    }
};

async function getAllFolders(parentId: string = "", collected: KBFolderItem[] = []): Promise<KBFolderItem[]> {
    const res = await getKBFolders(parentId) as any;
    const items: KBFolderItem[] = res.items || [];
    for (const f of items) {
        collected.push(f);
        await getAllFolders(f.id, collected);
    }
    return collected;
}

const handleMove = async () => {
    if (!moveItem.value) return;
    saving.value = true;
    try {
        const payload: { folder_ids?: string[]; document_ids?: string[]; target_folder_id: string } = {
            target_folder_id: moveTargetId.value,
        };
        if (moveItem.value.type === "folder") {
            payload.folder_ids = [moveItem.value.id];
        } else {
            payload.document_ids = [moveItem.value.id];
        }
        await moveKBItems(payload);
        message.success("移动成功");
        moveDialogOpen.value = false;
        loadContent();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "移动失败");
    } finally {
        saving.value = false;
    }
};

const handlePaginationChange = () => {
    loadContent();
};

let pollTimer: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
    loadContent();
    loadStats();
    pollTimer = setInterval(() => {
        const hasPending = documents.value.some(d => d.status === "pending" || d.status === "processing");
        if (hasPending) {
            loadContent();
            loadStats();
        }
    }, 3000);
});

onUnmounted(() => {
    if (pollTimer) clearInterval(pollTimer);
});
</script>

<template>
    <div class="space-y-4">
        <!-- Header -->
        <div class="flex items-center justify-between">
            <div>
                <h2 class="text-lg font-semibold text-gray-800">知识库</h2>
                <p class="text-sm text-gray-400 mt-0.5">上传文档到知识库，AI 对话时自动检索相关内容</p>
            </div>
            <div class="flex items-center gap-2">
                <VortButton @click="searchDialogOpen = true">
                    <Search :size="14" class="mr-1" /> 搜索测试
                </VortButton>
                <VortButton v-if="isAdmin" @click="textDialogOpen = true">
                    <FileText :size="14" class="mr-1" /> 手动添加
                </VortButton>
                <VortButton v-if="isAdmin" variant="primary" @click="uploadDialogOpen = true">
                    <Upload :size="14" class="mr-1" /> 上传文档
                </VortButton>
            </div>
        </div>

        <!-- Stats -->
        <div class="grid grid-cols-4 gap-4">
            <VortCard padding="default">
                <VortStatistic title="文档总数" :value="stats.document_count" />
            </VortCard>
            <VortCard padding="default">
                <VortStatistic title="已就绪" :value="stats.ready_count" :value-style="{ color: '#16a34a' }" />
            </VortCard>
            <VortCard padding="default">
                <VortStatistic title="文本分块" :value="stats.chunk_count" />
            </VortCard>
            <VortCard padding="default">
                <div class="text-sm text-gray-500 mb-1">Embedding 服务</div>
                <div class="flex items-center gap-1.5 mt-2">
                    <CheckCircle v-if="stats.embedding_available" :size="18" class="text-green-500" />
                    <AlertCircle v-else :size="18" class="text-yellow-500" />
                    <span class="text-sm font-medium" :class="stats.embedding_available ? 'text-green-600' : 'text-yellow-600'">
                        {{ stats.embedding_available ? "已连接" : "未配置" }}
                    </span>
                </div>
            </VortCard>
        </div>

        <!-- File Browser -->
        <div class="bg-white rounded-xl p-6">
            <!-- Breadcrumb -->
            <div class="flex items-center gap-1 text-sm mb-4 min-w-0 overflow-hidden">
                <span
                    class="flex items-center gap-1 cursor-pointer hover:text-blue-600 shrink-0"
                    :class="currentFolderId ? 'text-blue-600' : 'text-gray-800 font-medium'"
                    @click="navigateToFolder('')"
                >
                    <Home :size="14" />
                    <span>知识库</span>
                </span>
                <template v-for="crumb in breadcrumbs" :key="crumb.id">
                    <ChevronRight :size="14" class="text-gray-300 shrink-0" />
                    <span
                        class="cursor-pointer hover:text-blue-600 truncate"
                        :class="crumb.id === currentFolderId ? 'text-gray-800 font-medium' : 'text-blue-600'"
                        @click="navigateToFolder(crumb.id)"
                    >
                        {{ crumb.name }}
                    </span>
                </template>
            </div>

            <!-- Toolbar -->
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-3">
                    <VortInputSearch
                        v-model="keyword"
                        placeholder="请输入关键字"
                        allow-clear
                        class="w-[220px]"
                        @search="loadContent"
                        @keyup.enter="loadContent"
                    />
                </div>
                <div class="flex items-center gap-2">
                    <VortDropdown v-if="isAdmin" trigger="click" placement="bottomRight">
                        <VortButton variant="primary">
                            <Plus :size="14" class="mr-1" /> 新建
                        </VortButton>
                        <template #overlay>
                            <VortDropdownMenuItem @click="folderDialogOpen = true">
                                <svg class="mr-2 shrink-0" width="14" height="14" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg"><path d="M918.673 883H104.327C82.578 883 65 867.368 65 848.027V276.973C65 257.632 82.578 242 104.327 242h814.346C940.422 242 958 257.632 958 276.973v571.054C958 867.28 940.323 883 918.673 883z" fill="#FFE9B4"/><path d="M512 411H65V210.37C65 188.597 82.598 171 104.371 171h305.92c17.4 0 32.71 11.334 37.681 28.036L512 411z" fill="#FFB02C"/><path d="M918.673 883H104.327C82.578 883 65 865.42 65 843.668V335.332C65 313.58 82.578 296 104.327 296h814.346C940.422 296 958 313.58 958 335.332v508.336C958 865.32 940.323 883 918.673 883z" fill="#FFCA28"/></svg>新建文件夹
                            </VortDropdownMenuItem>
                            <VortDropdownMenuItem @click="uploadDialogOpen = true">
                                <Upload :size="14" class="mr-2 text-gray-400" />上传文档
                            </VortDropdownMenuItem>
                            <VortDropdownMenuItem @click="textDialogOpen = true">
                                <FileText :size="14" class="mr-2 text-gray-400" />手动添加
                            </VortDropdownMenuItem>
                        </template>
                    </VortDropdown>
                </div>
            </div>

            <!-- Unified Table -->
            <VortTable
                :data-source="tableRows"
                :loading="loading"
                row-key="_key"
                :pagination="false"
            >
                <VortTableColumn label="名称" prop="name" :min-width="280">
                    <template #default="{ row }: { row: ListRow }">
                        <div class="flex items-center gap-2.5 cursor-pointer" @click="handleRowClick(row)">
                            <template v-if="row._type === 'folder'">
                                <svg class="shrink-0" width="20" height="20" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg"><path d="M918.673 883H104.327C82.578 883 65 867.368 65 848.027V276.973C65 257.632 82.578 242 104.327 242h814.346C940.422 242 958 257.632 958 276.973v571.054C958 867.28 940.323 883 918.673 883z" fill="#FFE9B4"/><path d="M512 411H65V210.37C65 188.597 82.598 171 104.371 171h305.92c17.4 0 32.71 11.334 37.681 28.036L512 411z" fill="#FFB02C"/><path d="M918.673 883H104.327C82.578 883 65 865.42 65 843.668V335.332C65 313.58 82.578 296 104.327 296h814.346C940.422 296 958 313.58 958 335.332v508.336C958 865.32 940.323 883 918.673 883z" fill="#FFCA28"/></svg>
                                <template v-if="renamingFolderId === (row.raw as KBFolderItem).id">
                                    <input
                                        v-model="renamingFolderName"
                                        class="flex-1 text-sm border border-blue-300 rounded px-1.5 py-0.5 outline-none focus:ring-1 focus:ring-blue-400 min-w-0"
                                        @click.stop
                                        @keyup.enter="confirmRenameFolder"
                                        @keyup.escape="cancelRenameFolder"
                                        @blur="confirmRenameFolder"
                                        autofocus
                                    />
                                </template>
                                <template v-else>
                                    <span class="text-sm text-gray-800 hover:text-blue-600 font-medium">{{ row.name }}</span>
                                </template>
                            </template>
                            <template v-else>
                                <svg class="shrink-0" width="20" height="20" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg"><path d="M676.267 241.92h179.626a22.187 22.187 0 0 0 15.787-37.973L692.053 24.32a22.187 22.187 0 0 0-37.973 15.787v179.626a22.187 22.187 0 0 0 22.187 22.187z" fill="#F9BBB8"/><path d="M810.667 298.667h-128a85.333 85.333 0 0 1-85.334-85.334V85.333A85.333 85.333 0 0 0 512 0H213.333A85.333 85.333 0 0 0 128 85.333v853.334A85.333 85.333 0 0 0 213.333 1024h597.334A85.333 85.333 0 0 0 896 938.667V384a85.333 85.333 0 0 0-85.333-85.333zm-256 512H341.333a42.667 42.667 0 0 1 0-85.334h213.334a42.667 42.667 0 0 1 0 85.334zm128-170.667H341.333a42.667 42.667 0 0 1 0-85.333h341.334a42.667 42.667 0 0 1 0 85.333zm0-170.667H341.333a42.667 42.667 0 0 1 0-85.333h341.334a42.667 42.667 0 0 1 0 85.333z" fill="#F55E55"/></svg>
                                <span class="text-sm text-blue-600 hover:text-blue-700 hover:underline">{{ row.name }}</span>
                            </template>
                        </div>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="类型" :width="80" align="center">
                    <template #default="{ row }: { row: ListRow }">
                        <template v-if="row._type === 'document'">
                            <VortTag size="small">{{ ((row.raw as KBDocument).file_type || '').toUpperCase() }}</VortTag>
                        </template>
                        <span v-else class="text-gray-300">-</span>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="大小" :width="90">
                    <template #default="{ row }: { row: ListRow }">
                        <template v-if="row._type === 'document'">
                            <span class="text-gray-500">{{ formatFileSize((row.raw as KBDocument).file_size) }}</span>
                        </template>
                        <span v-else class="text-gray-300">-</span>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="状态" :width="110">
                    <template #default="{ row }: { row: ListRow }">
                        <template v-if="row._type === 'document'">
                            <VortTag :color="statusConfig[(row.raw as KBDocument).status]?.color || 'default'" size="small">
                                <Loader2 v-if="(row.raw as KBDocument).status === 'processing'" :size="12" class="animate-spin mr-1 inline" />
                                {{ statusConfig[(row.raw as KBDocument).status]?.text || (row.raw as KBDocument).status }}
                            </VortTag>
                            <VortTooltip v-if="(row.raw as KBDocument).error_message" :title="(row.raw as KBDocument).error_message">
                                <AlertCircle :size="14" class="ml-1 text-red-400 cursor-help inline" />
                            </VortTooltip>
                        </template>
                        <span v-else class="text-gray-300">-</span>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="更新时间" prop="updated_at" :width="160">
                    <template #default="{ row }: { row: ListRow }">
                        <span class="text-gray-500">{{ formatTime(row.updated_at) }}</span>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="操作" :width="60" align="center" fixed="right">
                    <template #default="{ row }: { row: ListRow }">
                        <VortDropdown trigger="click" placement="bottomRight">
                            <button class="p-1 rounded hover:bg-gray-100">
                                <MoreHorizontal :size="16" class="text-gray-400" />
                            </button>
                            <template #overlay>
                                <template v-if="row._type === 'folder'">
                                    <VortDropdownMenuItem @click="navigateToFolder((row.raw as KBFolderItem).id)">打开</VortDropdownMenuItem>
                                    <VortDropdownMenuItem v-if="isAdmin" @click="startRenameFolder(row.raw as KBFolderItem)">重命名</VortDropdownMenuItem>
                                    <VortDropdownMenuItem v-if="isAdmin" @click="openMoveDialog('folder', (row.raw as KBFolderItem).id, (row.raw as KBFolderItem).name)">移动到</VortDropdownMenuItem>
                                    <VortDropdownMenuSeparator v-if="isAdmin" />
                                    <VortDropdownMenuItem v-if="isAdmin" @click="handleDeleteFolder(row.raw as KBFolderItem)" class="text-red-500">删除</VortDropdownMenuItem>
                                </template>
                                <template v-else>
                                    <VortDropdownMenuItem @click="openDoc(row.raw as KBDocument)">查看</VortDropdownMenuItem>
                                    <VortDropdownMenuItem v-if="isAdmin" @click="openMoveDialog('document', (row.raw as KBDocument).id, (row.raw as KBDocument).title)">移动到</VortDropdownMenuItem>
                                    <VortDropdownMenuItem v-if="isAdmin" @click="handleReindex(row.raw as KBDocument)">重新索引</VortDropdownMenuItem>
                                    <VortDropdownMenuSeparator v-if="isAdmin" />
                                    <VortDropdownMenuItem v-if="isAdmin" @click="handleDelete(row.raw as KBDocument)" class="text-red-500">删除</VortDropdownMenuItem>
                                </template>
                            </template>
                        </VortDropdown>
                    </template>
                </VortTableColumn>

                <template #empty>
                    <div class="flex flex-col items-center py-12 text-gray-400">
                        <BookOpen :size="48" class="mb-3 text-gray-300" />
                        <p class="text-sm">{{ currentFolderId ? '当前文件夹为空' : '暂无内容' }}</p>
                        <p class="text-xs mt-1 text-gray-300">点击「新建」创建文件夹或上传文档</p>
                    </div>
                </template>
            </VortTable>

            <!-- Pagination -->
            <div v-if="total > pageSize" class="flex justify-end mt-4">
                <VortPagination
                    v-model:current="page"
                    v-model:page-size="pageSize"
                    :total="total"
                    show-total-info
                    show-size-changer
                    @change="handlePaginationChange"
                />
            </div>
        </div>

        <!-- New Folder Dialog -->
        <VortDialog
            :open="folderDialogOpen"
            title="新建文件夹"
            @update:open="folderDialogOpen = $event"
            :confirm-loading="saving"
            ok-text="创建"
            @ok="handleCreateFolder"
        >
            <VortForm label-width="80px" class="mt-2">
                <VortFormItem label="名称" required>
                    <VortInput v-model="folderForm.name" placeholder="文件夹名称" @keyup.enter="handleCreateFolder" />
                </VortFormItem>
            </VortForm>
        </VortDialog>

        <!-- Upload Dialog -->
        <VortDialog :open="uploadDialogOpen" title="上传文档" @update:open="uploadDialogOpen = $event" :footer="false">
            <div v-if="currentFolderId && breadcrumbs.length" class="mb-3 text-sm text-gray-500">
                上传到：{{ breadcrumbs.map(b => b.name).join(' / ') }}
            </div>
            <VortUploadDragger
                v-model:custom-request="handleCustomUpload"
                accept=".pdf,.docx,.doc,.md,.markdown,.txt,.text"
                :multiple="true"
                placeholder="点击或拖拽文件到此区域上传"
            >
                <div class="flex flex-col items-center gap-2 py-2">
                    <Upload :size="36" class="text-gray-300" />
                    <p class="text-sm text-gray-500">点击或拖拽文件到此处上传</p>
                    <p class="text-xs text-gray-400">支持 PDF、Word、Markdown、TXT 格式</p>
                </div>
            </VortUploadDragger>
        </VortDialog>

        <!-- Text/QA Dialog -->
        <VortDialog :open="textDialogOpen" title="手动添加文档" width="large" @update:open="textDialogOpen = $event">
            <VortForm label-width="80px" class="mt-2">
                <VortFormItem label="标题" required>
                    <VortInput v-model="textForm.title" placeholder="文档标题" />
                </VortFormItem>
                <VortFormItem label="内容" required>
                    <VortTextarea v-model="textForm.content" :rows="12" placeholder="输入文档内容（支持 Markdown）" />
                </VortFormItem>
            </VortForm>
            <template #footer>
                <div class="flex justify-end gap-2">
                    <VortButton @click="textDialogOpen = false">取消</VortButton>
                    <VortButton variant="primary" :loading="saving" @click="handleCreateText">保存</VortButton>
                </div>
            </template>
        </VortDialog>

        <!-- Move Dialog -->
        <VortDialog
            :open="moveDialogOpen"
            :title="`移动「${moveItem?.name || ''}」到`"
            @update:open="moveDialogOpen = $event"
            :confirm-loading="saving"
            ok-text="移动"
            @ok="handleMove"
        >
            <div v-if="moveLoading" class="flex items-center justify-center py-8">
                <Loader2 :size="20" class="animate-spin text-gray-400" />
                <span class="ml-2 text-sm text-gray-400">加载文件夹...</span>
            </div>
            <div v-else class="space-y-1 max-h-[360px] overflow-y-auto">
                <div
                    class="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors"
                    :class="moveTargetId === '' ? 'bg-blue-50 text-blue-600' : 'hover:bg-gray-50 text-gray-700'"
                    @click="moveTargetId = ''"
                >
                    <Home :size="16" class="shrink-0" />
                    <span class="text-sm font-medium">根目录</span>
                </div>
                <div
                    v-for="folder in moveFolderTree"
                    :key="folder.id"
                    class="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors"
                    :class="moveTargetId === folder.id ? 'bg-blue-50 text-blue-600' : 'hover:bg-gray-50 text-gray-700'"
                    @click="moveTargetId = folder.id"
                >
                    <svg class="shrink-0" width="16" height="16" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg"><path d="M918.673 883H104.327C82.578 883 65 867.368 65 848.027V276.973C65 257.632 82.578 242 104.327 242h814.346C940.422 242 958 257.632 958 276.973v571.054C958 867.28 940.323 883 918.673 883z" fill="#FFE9B4"/><path d="M512 411H65V210.37C65 188.597 82.598 171 104.371 171h305.92c17.4 0 32.71 11.334 37.681 28.036L512 411z" fill="#FFB02C"/><path d="M918.673 883H104.327C82.578 883 65 865.42 65 843.668V335.332C65 313.58 82.578 296 104.327 296h814.346C940.422 296 958 313.58 958 335.332v508.336C958 865.32 940.323 883 918.673 883z" fill="#FFCA28"/></svg>
                    <span class="text-sm">{{ folder.name }}</span>
                </div>
                <div v-if="!moveFolderTree.length" class="text-center py-6 text-sm text-gray-400">暂无文件夹，请先创建</div>
            </div>
        </VortDialog>

        <!-- Search Dialog -->
        <VortDialog :open="searchDialogOpen" title="搜索测试" width="large" @update:open="searchDialogOpen = $event" :footer="false">
            <div class="space-y-4">
                <div class="flex items-center gap-2">
                    <VortInput
                        v-model="searchQuery"
                        placeholder="输入自然语言查询..."
                        class="flex-1"
                        @keyup.enter="handleSearch"
                    />
                    <VortButton variant="primary" :loading="searching" @click="handleSearch">
                        <Search :size="14" class="mr-1" /> 搜索
                    </VortButton>
                </div>

                <VortScrollbar max-height="400px">
                    <div v-if="!searchResults.length && !searching" class="text-center py-12 text-sm text-gray-400">
                        输入查询语句并点击搜索
                    </div>
                    <div v-else class="space-y-3">
                        <VortCard v-for="(result, idx) in searchResults" :key="idx" padding="small">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-sm font-medium text-gray-800">{{ result.document_title }}</span>
                                <VortTag color="processing" size="small">
                                    相似度 {{ (result.score * 100).toFixed(1) }}%
                                </VortTag>
                            </div>
                            <p class="text-sm text-gray-600 whitespace-pre-wrap line-clamp-4">{{ result.content }}</p>
                        </VortCard>
                    </div>
                </VortScrollbar>
            </div>
        </VortDialog>
    </div>
</template>
