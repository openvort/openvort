<template>
    <Dialog
        :open="open"
        title="从 Git 仓库添加文档"
        :confirm-loading="submitting"
        ok-text="添加"
        :width="560"
        @ok="handleSubmit"
        @update:open="$emit('update:open', $event)"
    >
        <vort-form ref="formRef" :model="form" :rules="rules" label-width="80px">
            <vort-form-item label="仓库" name="repo_id" required>
                <vort-select
                    v-model="form.repo_id"
                    placeholder="选择仓库"
                    show-search
                    allow-clear
                    @change="handleRepoChange"
                >
                    <vort-select-option v-for="r in repos" :key="r.id" :value="r.id">
                        {{ r.name }}
                    </vort-select-option>
                </vort-select>
            </vort-form-item>

            <vort-form-item label="分支" name="branch" required>
                <vort-select
                    v-model="form.branch"
                    placeholder="选择分支"
                    show-search
                    allow-clear
                    :disabled="!form.repo_id"
                    @change="handleBranchChange"
                >
                    <vort-select-option v-for="b in branches" :key="b.name" :value="b.name">
                        {{ b.name }}
                    </vort-select-option>
                </vort-select>
            </vort-form-item>

            <vort-form-item label="文件" name="path" required>
                <div class="w-full">
                    <div v-if="form.path" class="flex items-center gap-2 mb-2 px-2 py-1.5 bg-blue-50 rounded text-sm text-blue-700">
                        <FileText :size="14" class="shrink-0" />
                        <span class="truncate">{{ form.path }}</span>
                        <button class="ml-auto text-blue-400 hover:text-blue-600" @click="form.path = ''">
                            <X :size="14" />
                        </button>
                    </div>

                    <div v-if="!form.repo_id || !form.branch" class="text-sm text-gray-400 py-4 text-center">
                        请先选择仓库和分支
                    </div>
                    <template v-else>
                        <!-- Breadcrumb -->
                        <div v-if="currentDir" class="flex items-center gap-1 mb-2 text-sm">
                            <button class="text-blue-600 hover:underline" @click="navigateTo('')">根目录</button>
                            <template v-for="(seg, idx) in dirSegments" :key="idx">
                                <ChevronRight :size="14" class="text-gray-300" />
                                <button
                                    class="text-blue-600 hover:underline"
                                    @click="navigateTo(dirSegments.slice(0, idx + 1).join('/'))"
                                >{{ seg }}</button>
                            </template>
                        </div>

                        <vort-spin :spinning="treeLoading">
                            <div class="border rounded max-h-[240px] overflow-auto">
                                <div v-if="treeItems.length === 0" class="text-sm text-gray-400 py-6 text-center">
                                    该目录下没有 Markdown 文件
                                </div>
                                <div
                                    v-for="item in treeItems"
                                    :key="item.path"
                                    class="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-gray-50 border-b last:border-b-0"
                                    @click="handleTreeItemClick(item)"
                                >
                                    <Folder v-if="item.type === 'dir'" :size="16" class="text-amber-400 shrink-0" />
                                    <FileText v-else :size="16" class="text-blue-400 shrink-0" />
                                    <span class="truncate" :class="item.type === 'dir' ? 'text-gray-700' : 'text-blue-600'">
                                        {{ item.name }}
                                    </span>
                                    <ChevronRight v-if="item.type === 'dir'" :size="14" class="ml-auto text-gray-300" />
                                </div>
                            </div>
                        </vort-spin>
                    </template>
                </div>
            </vort-form-item>
        </vort-form>
    </Dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { Dialog } from "@openvort/vort-ui";
import { z } from "zod";
import { FileText, Folder, ChevronRight, X } from "lucide-vue-next";
import { message } from "@openvort/vort-ui";
import {
    getVortgitRepos,
    getVortgitRepoBranches,
    getVortgitRepoTree,
} from "@/api";
import { createKBGitDocument } from "@/api";

interface TreeEntry {
    name: string;
    path: string;
    type: "file" | "dir";
    size: number;
}

const props = defineProps<{
    open: boolean;
    folderId?: string;
}>();

const emit = defineEmits<{
    (e: "update:open", val: boolean): void;
    (e: "saved"): void;
}>();

const formRef = ref();
const submitting = ref(false);
const form = ref({ repo_id: "", branch: "", path: "" });

const rules = z.object({
    repo_id: z.string().min(1, "请选择仓库"),
    branch: z.string().min(1, "请选择分支"),
    path: z.string().min(1, "请选择文件"),
}) as any;

const repos = ref<{ id: string; name: string; default_branch: string }[]>([]);
const branches = ref<{ name: string; is_default: boolean }[]>([]);
const treeItems = ref<TreeEntry[]>([]);
const treeLoading = ref(false);
const currentDir = ref("");

const dirSegments = computed(() => currentDir.value ? currentDir.value.split("/") : []);

watch(() => props.open, async (val) => {
    if (val) {
        form.value = { repo_id: "", branch: "", path: "" };
        branches.value = [];
        treeItems.value = [];
        currentDir.value = "";
        submitting.value = false;
        await loadRepos();
    }
});

async function loadRepos() {
    try {
        const res = await getVortgitRepos({ page: 1, page_size: 200 }) as any;
        repos.value = (res.items || []).map((r: any) => ({
            id: r.id,
            name: r.name,
            default_branch: r.default_branch || "main",
        }));
    } catch {
        repos.value = [];
    }
}

async function handleRepoChange(repoId: any) {
    form.value.branch = "";
    form.value.path = "";
    branches.value = [];
    treeItems.value = [];
    currentDir.value = "";
    if (!repoId) return;

    try {
        const res = await getVortgitRepoBranches(repoId) as any;
        branches.value = res.items || [];
        const repo = repos.value.find((r) => r.id === repoId);
        const defaultBranch = branches.value.find((b) => b.is_default)?.name
            || repo?.default_branch
            || branches.value[0]?.name
            || "";
        if (defaultBranch) {
            form.value.branch = defaultBranch;
            await loadTree();
        }
    } catch {
        branches.value = [];
    }
}

async function handleBranchChange() {
    form.value.path = "";
    currentDir.value = "";
    treeItems.value = [];
    if (form.value.branch) {
        await loadTree();
    }
}

async function loadTree() {
    if (!form.value.repo_id || !form.value.branch) return;
    treeLoading.value = true;
    try {
        const res = await getVortgitRepoTree(form.value.repo_id, {
            path: currentDir.value,
            ref: form.value.branch,
        }) as any;
        const items: TreeEntry[] = res.items || [];
        treeItems.value = items
            .filter((item: TreeEntry) => item.type === "dir" || item.name.endsWith(".md"))
            .sort((a: TreeEntry, b: TreeEntry) => {
                if (a.type === b.type) return a.name.localeCompare(b.name);
                return a.type === "dir" ? -1 : 1;
            });
    } catch {
        treeItems.value = [];
    } finally {
        treeLoading.value = false;
    }
}

function handleTreeItemClick(item: TreeEntry) {
    if (item.type === "dir") {
        navigateTo(item.path);
    } else {
        form.value.path = item.path;
    }
}

function navigateTo(path: string) {
    currentDir.value = path;
    loadTree();
}

async function handleSubmit() {
    try { await formRef.value?.validate(); } catch { return; }
    submitting.value = true;
    try {
        await createKBGitDocument({
            repo_id: form.value.repo_id,
            branch: form.value.branch,
            path: form.value.path,
            folder_id: props.folderId || undefined,
        });
        message.success("Git 文档添加成功");
        emit("saved");
        emit("update:open", false);
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "添加失败");
    } finally {
        submitting.value = false;
    }
}
</script>
