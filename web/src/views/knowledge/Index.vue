<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import {
    getKBDocuments, uploadKBDocument, createKBTextDocument,
    deleteKBDocument, reindexKBDocument, searchKB, getKBStats,
} from "@/api";
import {
    Upload, Search, RefreshCw, FileText,
    CheckCircle, AlertCircle, Loader2, BookOpen, Trash2,
} from "lucide-vue-next";
import { message, dialog } from "@/components/vort";
import type { UploadRequestOption } from "@/components/vort/upload/types";
import { useUserStore } from "@/stores";

interface KBDocument {
    id: string;
    title: string;
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

const userStore = useUserStore();
const isAdmin = computed(() => userStore.isAdmin);

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
const saving = ref(false);

const textForm = ref({ title: "", content: "" });
const searchQuery = ref("");
const searchResults = ref<SearchResult[]>([]);
const searching = ref(false);

const statusConfig: Record<string, { text: string; color: string }> = {
    pending: { text: "等待处理", color: "warning" },
    processing: { text: "处理中", color: "processing" },
    ready: { text: "已就绪", color: "success" },
    error: { text: "处理失败", color: "error" },
};

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
    return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
};

const loadDocuments = async () => {
    loading.value = true;
    try {
        const res = await getKBDocuments({
            page: page.value,
            page_size: pageSize.value,
            keyword: keyword.value || undefined,
        }) as any;
        documents.value = res.items || [];
        total.value = res.total || 0;
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

const handleCustomUpload = ref(async (options: UploadRequestOption) => {
    try {
        const res = await uploadKBDocument(options.file);
        options.onSuccess?.(res, options.file);
        message.success(`${options.file.name} 上传成功`);
        loadDocuments();
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
        });
        message.success("文档创建成功");
        textDialogOpen.value = false;
        textForm.value = { title: "", content: "" };
        loadDocuments();
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
                loadDocuments();
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
        loadDocuments();
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

const handlePaginationChange = () => {
    loadDocuments();
};

let pollTimer: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
    loadDocuments();
    loadStats();
    pollTimer = setInterval(() => {
        const hasPending = documents.value.some(d => d.status === "pending" || d.status === "processing");
        if (hasPending) {
            loadDocuments();
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

        <!-- Table -->
        <div class="bg-white rounded-xl p-6">
            <!-- Filter Bar -->
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-3">
                    <VortInputSearch
                        v-model="keyword"
                        placeholder="搜索文档标题..."
                        allow-clear
                        class="w-[240px]"
                        @search="loadDocuments"
                        @keyup.enter="loadDocuments"
                    />
                    <VortButton @click="loadDocuments">查询</VortButton>
                </div>
            </div>

            <!-- Document Table -->
            <VortTable
                :data-source="documents"
                :loading="loading"
                row-key="id"
                :pagination="false"
            >
                <VortTableColumn label="文档" prop="title" :min-width="220">
                    <template #default="{ row }">
                        <div class="font-medium text-gray-800">{{ row.title }}</div>
                        <div v-if="row.file_name && row.file_name !== row.title" class="text-xs text-gray-400 mt-0.5 truncate max-w-[280px]">
                            {{ row.file_name }}
                        </div>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="类型" prop="file_type" :width="80" align="center">
                    <template #default="{ row }">
                        <VortTag size="small">{{ (row.file_type || '').toUpperCase() }}</VortTag>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="大小" prop="file_size" :width="90">
                    <template #default="{ row }">
                        <span class="text-gray-500">{{ formatFileSize(row.file_size) }}</span>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="状态" prop="status" :width="110">
                    <template #default="{ row }">
                        <VortTag :color="statusConfig[row.status]?.color || 'default'" size="small">
                            <Loader2 v-if="row.status === 'processing'" :size="12" class="animate-spin mr-1 inline" />
                            {{ statusConfig[row.status]?.text || row.status }}
                        </VortTag>
                        <VortTooltip v-if="row.error_message" :title="row.error_message">
                            <AlertCircle :size="14" class="ml-1 text-red-400 cursor-help inline" />
                        </VortTooltip>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="分块" prop="chunk_count" :width="70" align="center">
                    <template #default="{ row }">
                        <span class="text-gray-500">{{ row.chunk_count }}</span>
                    </template>
                </VortTableColumn>

                <VortTableColumn label="创建时间" prop="created_at" :width="130">
                    <template #default="{ row }">
                        <span class="text-gray-500">{{ formatTime(row.created_at) }}</span>
                    </template>
                </VortTableColumn>

                <VortTableColumn v-if="isAdmin" label="操作" :width="120" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2">
                            <VortTooltip title="重新索引">
                                <VortButton variant="text" size="small" @click="handleReindex(row)">
                                    <RefreshCw :size="14" />
                                </VortButton>
                            </VortTooltip>
                            <VortTooltip title="删除">
                                <VortButton variant="text" size="small" danger @click="handleDelete(row)">
                                    <Trash2 :size="14" />
                                </VortButton>
                            </VortTooltip>
                        </div>
                    </template>
                </VortTableColumn>

                <template #empty>
                    <div class="flex flex-col items-center py-12 text-gray-400">
                        <BookOpen :size="48" class="mb-3 text-gray-300" />
                        <p class="text-sm">暂无文档</p>
                        <p class="text-xs mt-1 text-gray-300">上传 PDF、Word、Markdown 或文本文件开始构建知识库</p>
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

        <!-- Upload Dialog -->
        <VortDialog :open="uploadDialogOpen" title="上传文档" @update:open="uploadDialogOpen = $event" :footer="false">
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

