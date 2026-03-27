<template>
    <Dialog
        :open="open"
        title="添加代码评审 (PR)"
        :width="680"
        ok-text="添加"
        :confirm-loading="submitting"
        @ok="handleSubmit"
        @update:open="$emit('update:open', $event)"
    >
        <div class="space-y-4">
            <div class="flex items-center gap-3">
                <span class="text-sm text-gray-500 whitespace-nowrap w-16">仓库</span>
                <vort-select
                    v-model="selectedRepoId"
                    placeholder="选择仓库"
                    show-search
                    allow-clear
                    class="flex-1"
                    @change="handleRepoChange"
                >
                    <vort-select-option v-for="repo in repos" :key="repo.id" :value="repo.id">
                        {{ repo.name }}
                        <span class="text-xs text-gray-400 ml-1">({{ repo.full_name }})</span>
                    </vort-select-option>
                </vort-select>
            </div>

            <vort-spin :spinning="prsLoading">
                <div v-if="selectedRepoId && !prsLoading && prs.length === 0" class="text-center py-8 text-sm text-gray-400">
                    该仓库暂无 Open 状态的 PR
                </div>
                <div v-else-if="prs.length > 0" class="border rounded-lg overflow-hidden">
                    <vort-table :data-source="prs" :pagination="false" row-key="number" size="small">
                        <vort-table-column :width="50">
                            <template #default="{ row }">
                                <vort-checkbox
                                    :checked="selectedPRs.has(row.number)"
                                    :disabled="row.already_added"
                                    @update:checked="togglePR(row, $event)"
                                />
                            </template>
                        </vort-table-column>
                        <vort-table-column label="PR" :width="60">
                            <template #default="{ row }">
                                <span class="text-xs font-mono text-gray-500">#{{ row.number }}</span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="标题" :min-width="200">
                            <template #default="{ row }">
                                <div class="flex items-center gap-1.5">
                                    <span class="text-sm text-gray-800 truncate">{{ row.title }}</span>
                                    <vort-tag v-if="row.already_added" color="default" size="small">已添加</vort-tag>
                                </div>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="分支" :width="220">
                            <template #default="{ row }">
                                <span class="text-xs text-gray-500 font-mono">{{ row.head }} &rarr; {{ row.base }}</span>
                            </template>
                        </vort-table-column>
                    </vort-table>
                </div>
            </vort-spin>
        </div>
    </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { Dialog, message } from "@openvort/vort-ui";
import { getVortgitRepos } from "@/api";
import {
    getVortflowAvailablePRs,
    addVortflowTestPlanReviews,
} from "@/api";

const props = defineProps<{
    open: boolean;
    planId: string;
    projectId: string;
}>();

const emit = defineEmits<{
    (e: "update:open", val: boolean): void;
    (e: "saved"): void;
}>();

const repos = ref<any[]>([]);
const selectedRepoId = ref("");
const prs = ref<any[]>([]);
const prsLoading = ref(false);
const submitting = ref(false);
const selectedPRs = ref<Map<number, any>>(new Map());

watch(() => props.open, async (val) => {
    if (val) {
        selectedRepoId.value = "";
        prs.value = [];
        selectedPRs.value = new Map();
        submitting.value = false;
        await loadRepos();
    }
});

async function loadRepos() {
    try {
        const res = await getVortgitRepos({ project_id: props.projectId, page_size: 100 }) as any;
        repos.value = res.items || [];
    } catch {
        repos.value = [];
    }
}

async function handleRepoChange(repoId: string) {
    selectedPRs.value = new Map();
    if (!repoId) {
        prs.value = [];
        return;
    }
    prsLoading.value = true;
    try {
        const res = await getVortflowAvailablePRs(props.planId, repoId) as any;
        prs.value = res.items || [];
    } catch {
        prs.value = [];
        message.error("获取 PR 列表失败");
    } finally {
        prsLoading.value = false;
    }
}

function togglePR(pr: any, checked: boolean) {
    const map = new Map(selectedPRs.value);
    if (checked) {
        map.set(pr.number, pr);
    } else {
        map.delete(pr.number);
    }
    selectedPRs.value = map;
}

async function handleSubmit() {
    if (selectedPRs.value.size === 0) {
        message.warning("请至少选择一个 PR");
        return;
    }
    submitting.value = true;
    try {
        const reviews = Array.from(selectedPRs.value.values()).map((pr: any) => ({
            repo_id: selectedRepoId.value,
            pr_number: pr.number,
            pr_url: pr.url || "",
            pr_title: pr.title || "",
            head_branch: pr.head || "",
            base_branch: pr.base || "",
        }));
        await addVortflowTestPlanReviews(props.planId, { reviews });
        message.success(`已添加 ${reviews.length} 个 PR`);
        emit("saved");
        emit("update:open", false);
    } catch {
        message.error("添加失败");
    } finally {
        submitting.value = false;
    }
}
</script>
