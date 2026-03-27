<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getKBDocument, updateKBDocument, reindexKBDocument, deleteKBDocument } from "@/api";
import {
    ArrowLeft, Pencil, Save, X, RefreshCw, Trash2,
    CheckCircle, AlertCircle, Loader2,
} from "lucide-vue-next";
import { message, dialog } from "@openvort/vort-ui";
import MarkdownView from "@/components/vort-biz/editor/MarkdownView.vue";
import VortEditor from "@/components/vort-biz/editor/VortEditor.vue";
import { useUserStore } from "@/stores";

interface DocData {
    id: string;
    title: string;
    folder_id: string;
    file_name: string;
    file_type: string;
    file_size: number;
    content: string;
    status: string;
    error_message: string;
    chunk_count: number;
    owner_id: string;
    created_at: string;
    updated_at: string;
}

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const isAdmin = computed(() => userStore.isAdmin);

const loading = ref(true);
const doc = ref<DocData | null>(null);
const editing = ref(false);
const saving = ref(false);
const editForm = ref({ title: "", content: "" });

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
    return d.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
};

const loadDoc = async () => {
    loading.value = true;
    try {
        const res = await getKBDocument(route.params.id as string) as any;
        doc.value = res;
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "文档不存在或加载失败");
        router.push("/knowledge");
    } finally {
        loading.value = false;
    }
};

const startEditing = () => {
    if (!doc.value) return;
    editForm.value = { title: doc.value.title, content: doc.value.content };
    editing.value = true;
};

const cancelEditing = () => {
    editing.value = false;
};

const handleSave = async () => {
    if (!doc.value) return;
    if (!editForm.value.title.trim()) {
        message.warning("标题不能为空");
        return;
    }

    saving.value = true;
    try {
        const res = await updateKBDocument(doc.value.id, {
            title: editForm.value.title,
            content: editForm.value.content,
        }) as any;
        doc.value.title = editForm.value.title;
        doc.value.content = editForm.value.content;
        doc.value.file_size = new Blob([editForm.value.content]).size;
        editing.value = false;
        message.success(res.reindexing ? "保存成功，正在重新索引" : "保存成功");
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "保存失败");
    } finally {
        saving.value = false;
    }
};

const handleReindex = async () => {
    if (!doc.value) return;
    try {
        await reindexKBDocument(doc.value.id);
        message.success("已开始重新索引");
        loadDoc();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "重新索引失败");
    }
};

const handleDelete = () => {
    if (!doc.value) return;
    dialog.confirm({
        title: "确认删除",
        content: `确定删除文档「${doc.value.title}」？此操作将同时删除所有关联的分块和向量数据，不可撤销。`,
        onOk: async () => {
            try {
                await deleteKBDocument(doc.value!.id);
                message.success("删除成功");
                router.push("/knowledge");
            } catch (e: any) {
                message.error(e?.response?.data?.detail || "删除失败");
            }
        },
    });
};

const goBack = () => {
    router.push("/knowledge");
};

onMounted(loadDoc);
</script>

<template>
    <div class="space-y-4">
        <!-- Loading -->
        <div v-if="loading" class="bg-white rounded-xl p-6 flex items-center justify-center min-h-[400px]">
            <Loader2 :size="24" class="animate-spin text-gray-400" />
            <span class="ml-2 text-sm text-gray-400">加载中...</span>
        </div>

        <template v-else-if="doc">
            <div class="bg-white rounded-xl">
                <!-- Header -->
                <div class="flex items-center justify-between px-6 pt-5 pb-4">
                    <div class="flex items-center gap-3 min-w-0">
                        <button class="p-1 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors" @click="goBack">
                            <ArrowLeft :size="18" />
                        </button>
                        <template v-if="editing">
                            <VortInput v-model="editForm.title" class="text-lg font-semibold w-[400px]" placeholder="文档标题" />
                        </template>
                        <template v-else>
                            <h2 class="text-lg font-semibold text-gray-800 truncate">{{ doc.title }}</h2>
                        </template>
                    </div>

                    <div class="flex items-center gap-2 shrink-0">
                        <template v-if="editing">
                            <VortButton @click="cancelEditing">取消</VortButton>
                            <VortButton variant="primary" :loading="saving" @click="handleSave">
                                <Save :size="14" class="mr-1" /> 保存
                            </VortButton>
                        </template>
                        <template v-else-if="isAdmin">
                            <VortButton size="small" @click="handleReindex">
                                <RefreshCw :size="14" class="mr-1" /> 重新索引
                            </VortButton>
                            <VortButton size="small" @click="startEditing">
                                <Pencil :size="14" class="mr-1" /> 编辑
                            </VortButton>
                            <VortButton size="small" danger @click="handleDelete">
                                <Trash2 :size="14" class="mr-1" /> 删除
                            </VortButton>
                        </template>
                    </div>
                </div>

                <!-- Meta -->
                <div class="flex items-center gap-3 px-6 pb-4 text-sm text-gray-400">
                    <VortTag size="small">{{ (doc.file_type || '').toUpperCase() }}</VortTag>
                    <span>{{ formatFileSize(doc.file_size) }}</span>
                    <span>{{ doc.chunk_count }} 个分块</span>
                    <VortTag :color="statusConfig[doc.status]?.color || 'default'" size="small">
                        <Loader2 v-if="doc.status === 'processing'" :size="12" class="animate-spin mr-1 inline" />
                        {{ statusConfig[doc.status]?.text || doc.status }}
                    </VortTag>
                    <VortTooltip v-if="doc.error_message" :title="doc.error_message">
                        <AlertCircle :size="14" class="text-red-400 cursor-help" />
                    </VortTooltip>
                    <span>更新于 {{ formatTime(doc.updated_at) }}</span>
                </div>

                <div class="border-t border-gray-100" />

                <!-- Content -->
                <div class="px-6 py-5">
                    <template v-if="editing">
                        <VortEditor v-model="editForm.content" placeholder="请输入文档内容..." min-height="500px" />
                    </template>
                    <template v-else>
                        <MarkdownView :content="doc.content" />
                    </template>
                </div>
            </div>
        </template>
    </div>
</template>
