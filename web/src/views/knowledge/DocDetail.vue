<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
    getKBDocument, updateKBDocument, reindexKBDocument,
    deleteKBDocument, createKBTextDocument, getKBDocGitContent,
} from "@/api";
import { getVortgitRepoBranches } from "@/api";
import {
    ArrowLeft, Pencil, Save, X, RefreshCw, Trash2,
    CheckCircle, AlertCircle, Loader2, Link, GitBranch, FileCode,
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
    git_repo_id?: string;
    git_branch?: string;
    git_path?: string;
    git_repo_name?: string;
}

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const isAdmin = computed(() => userStore.isAdmin);
const isNew = computed(() => route.params.id === "new");
const isGitDoc = computed(() => doc.value?.file_type === "git");

const loading = ref(true);
const doc = ref<DocData | null>(null);
const editing = ref(false);
const saving = ref(false);
const editForm = ref({ title: "", content: "" });

// Git branch switching
const gitBranches = ref<{ name: string; is_default: boolean }[]>([]);
const currentBranch = ref("");
const branchLoading = ref(false);
const displayContent = ref("");
const branchNotFound = ref(false);

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
    if (isNew.value) {
        doc.value = {
            id: "", title: "", folder_id: (route.query.folder_id as string) || "",
            file_name: "", file_type: "QA", file_size: 0, content: "",
            status: "", error_message: "", chunk_count: 0, owner_id: "",
            created_at: "", updated_at: new Date().toISOString(),
        };
        editForm.value = { title: "", content: "" };
        editing.value = true;
        loading.value = false;
        return;
    }
    loading.value = true;
    try {
        const res = await getKBDocument(route.params.id as string) as any;
        doc.value = res;
        displayContent.value = res.content || "";
        branchNotFound.value = false;

        if (res.file_type === "git" && res.git_repo_id) {
            currentBranch.value = res.git_branch || "";
            loadGitBranches(res.git_repo_id);
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "文档不存在或加载失败");
        router.push("/knowledge");
    } finally {
        loading.value = false;
    }
};

const loadGitBranches = async (repoId: string) => {
    try {
        const res = await getVortgitRepoBranches(repoId) as any;
        gitBranches.value = res.items || [];
    } catch {
        gitBranches.value = [];
    }
};

const handleBranchSwitch = async (branch: any) => {
    if (!doc.value || branch === currentBranch.value) return;
    currentBranch.value = branch;
    branchLoading.value = true;
    branchNotFound.value = false;
    try {
        const res = await getKBDocGitContent(doc.value.id, branch) as any;
        displayContent.value = res.content || "";
        branchNotFound.value = false;
    } catch (e: any) {
        const status = e?.response?.status;
        if (status === 404) {
            branchNotFound.value = true;
            displayContent.value = "";
        } else {
            message.error(e?.response?.data?.detail || "获取内容失败");
        }
    } finally {
        branchLoading.value = false;
    }
};

const startEditing = () => {
    if (!doc.value) return;
    editForm.value = { title: doc.value.title, content: doc.value.content };
    editing.value = true;
};

const cancelEditing = () => {
    if (isNew.value) {
        router.push("/knowledge");
        return;
    }
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
        if (isNew.value) {
            const res = await createKBTextDocument({
                title: editForm.value.title,
                content: editForm.value.content,
                folder_id: doc.value.folder_id || undefined,
            }) as any;
            message.success("文档创建成功");
            router.replace(`/knowledge/doc/${res.id}`);
            return;
        }
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

const copyShareLink = () => {
    const url = window.location.origin + route.fullPath;
    const textarea = document.createElement("textarea");
    textarea.value = url;
    textarea.style.cssText = "position:fixed;opacity:0";
    document.body.appendChild(textarea);
    textarea.select();
    try {
        document.execCommand("copy");
        message.success("链接已复制");
    } catch {
        message.error("复制失败");
    }
    document.body.removeChild(textarea);
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
                            <VortInput v-model="editForm.title" class="text-lg font-semibold flex-1 min-w-0" :placeholder="isNew ? '请输入文档标题' : '文档标题'" />
                        </template>
                        <template v-else>
                            <h2 class="text-lg font-semibold text-gray-800 truncate">{{ doc.title }}</h2>
                            <button class="p-1 rounded-lg hover:bg-gray-100 text-gray-300 hover:text-gray-500 transition-colors" title="复制分享链接" @click="copyShareLink">
                                <Link :size="16" />
                            </button>
                        </template>
                    </div>

                    <div class="flex items-center gap-2 shrink-0">
                        <template v-if="editing">
                            <VortButton @click="cancelEditing">取消</VortButton>
                            <VortButton variant="primary" :loading="saving" @click="handleSave">
                                <Save :size="14" class="mr-1" /> 保存
                            </VortButton>
                        </template>
                        <template v-else-if="isAdmin && !isGitDoc">
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
                        <template v-else-if="isAdmin && isGitDoc">
                            <VortButton size="small" danger @click="handleDelete">
                                <Trash2 :size="14" class="mr-1" /> 删除
                            </VortButton>
                        </template>
                    </div>
                </div>

                <!-- Git branch selector -->
                <div v-if="isGitDoc && !isNew" class="flex items-center gap-3 px-6 pb-3">
                    <div class="flex items-center gap-2 text-sm text-gray-500">
                        <GitBranch :size="14" class="text-gray-400" />
                        <vort-select
                            :model-value="currentBranch"
                            placeholder="选择分支"
                            show-search
                            class="w-[200px]"
                            @change="handleBranchSwitch"
                        >
                            <vort-select-option v-for="b in gitBranches" :key="b.name" :value="b.name">
                                {{ b.name }}
                            </vort-select-option>
                        </vort-select>
                    </div>
                    <div v-if="doc.git_repo_name" class="flex items-center gap-1.5 text-sm text-gray-400">
                        <FileCode :size="14" />
                        <span>{{ doc.git_repo_name }}</span>
                        <span class="text-gray-300">/</span>
                        <span class="text-gray-500">{{ doc.git_path }}</span>
                    </div>
                </div>

                <!-- Meta (hidden in new mode) -->
                <div v-if="!isNew" class="flex items-center gap-3 px-6 pb-4 text-sm text-gray-400">
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
                    <template v-else-if="isGitDoc">
                        <vort-spin :spinning="branchLoading">
                            <div v-if="branchNotFound" class="flex flex-col items-center justify-center py-16 text-gray-400">
                                <AlertCircle :size="40" class="mb-3 text-gray-300" />
                                <p class="text-base font-medium text-gray-500 mb-1">该分支下不存在该文档</p>
                                <p class="text-sm">分支 <span class="font-mono text-gray-600">{{ currentBranch }}</span> 中找不到文件 <span class="font-mono text-gray-600">{{ doc.git_path }}</span></p>
                            </div>
                            <MarkdownView v-else :content="displayContent" />
                        </vort-spin>
                    </template>
                    <template v-else>
                        <MarkdownView :content="doc.content" />
                    </template>
                </div>
            </div>
        </template>
    </div>
</template>
