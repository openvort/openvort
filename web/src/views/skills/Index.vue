<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import {
    getSkills, getSkill, createSkill, updateSkill, deleteSkill, toggleSkill,
    getSkillTags,
    generateSkillContentPrompt,
} from "@/api";
import { message, dialog } from "@/components/vort";
import { Plus, Trash2, Save, BookOpen, Bot, X, Tag, Search } from "lucide-vue-next";

const router = useRouter();

interface SkillItem {
    id: string;
    name: string;
    description: string;
    scope: string;
    skill_type: string;
    tags: string[];
    enabled: boolean;
    content?: string;
}

// ---- Tag system ----
const allTags = ref<string[]>([]);
const selectedTags = ref<string[]>([]);
const searchKeyword = ref("");

async function loadTags() {
    try {
        const res: any = await getSkillTags();
        allTags.value = res?.tags || [];
    } catch { /* ignore */ }
}

function toggleTag(tag: string) {
    const idx = selectedTags.value.indexOf(tag);
    if (idx >= 0) {
        selectedTags.value.splice(idx, 1);
    } else {
        selectedTags.value.push(tag);
    }
}

function clearTags() {
    selectedTags.value = [];
}

// ---- Skills list ----
const skills = ref<SkillItem[]>([]);
const loading = ref(false);

const filteredSkills = computed(() => {
    let list = skills.value;
    if (selectedTags.value.length > 0) {
        list = list.filter(s =>
            s.tags && s.tags.some(t => selectedTags.value.includes(t))
        );
    }
    if (searchKeyword.value.trim()) {
        const kw = searchKeyword.value.trim().toLowerCase();
        list = list.filter(s =>
            s.name.toLowerCase().includes(kw) ||
            (s.description || "").toLowerCase().includes(kw)
        );
    }
    return list;
});

async function loadSkills() {
    loading.value = true;
    try {
        const res: any = await getSkills();
        skills.value = (res?.skills || []).map((s: any) => ({
            ...s,
            tags: s.tags || [],
        }));
    } catch { /* ignore */ }
    finally { loading.value = false; }
}

async function handleToggle(skill: SkillItem) {
    try {
        const res: any = await toggleSkill(skill.id);
        if (res?.success) {
            skill.enabled = res.enabled;
            message.success(res.enabled ? "已启用" : "已禁用");
        }
    } catch { message.error("操作失败"); }
}

// ---- Detail drawer ----
const drawerOpen = ref(false);
const drawerSkill = ref<SkillItem | null>(null);
const drawerLoading = ref(false);
const saving = ref(false);
const tagInput = ref("");

async function openDrawer(skill: SkillItem) {
    drawerLoading.value = true;
    drawerOpen.value = true;
    try {
        const res: any = await getSkill(skill.id);
        drawerSkill.value = {
            id: res.id, name: res.name, description: res.description,
            content: res.content, scope: res.scope, skill_type: res.skill_type,
            tags: res.tags || [], enabled: res.enabled,
        };
    } catch {
        message.error("加载详情失败");
        drawerOpen.value = false;
    } finally { drawerLoading.value = false; }
}

function addTagToDrawer(tag?: string) {
    if (!drawerSkill.value) return;
    const t = (tag || tagInput.value).trim();
    if (!t) return;
    if (!drawerSkill.value.tags.includes(t)) {
        drawerSkill.value.tags.push(t);
    }
    tagInput.value = "";
}

function removeTagFromDrawer(tag: string) {
    if (!drawerSkill.value) return;
    drawerSkill.value.tags = drawerSkill.value.tags.filter(t => t !== tag);
}

function toggleDrawerTag(tag: string) {
    if (!drawerSkill.value) return;
    if (drawerSkill.value.tags.includes(tag)) {
        removeTagFromDrawer(tag);
    } else {
        addTagToDrawer(tag);
    }
}

async function handleSaveDrawer() {
    if (!drawerSkill.value || drawerSkill.value.scope === "builtin") return;
    saving.value = true;
    try {
        await updateSkill(drawerSkill.value.id, {
            name: drawerSkill.value.name,
            description: drawerSkill.value.description,
            content: drawerSkill.value.content,
            tags: drawerSkill.value.tags,
        });
        message.success("保存成功");
        drawerOpen.value = false;
        loadSkills();
        loadTags();
    } catch { message.error("保存失败"); }
    finally { saving.value = false; }
}

function handleDeletePublic(skill: SkillItem) {
    dialog.confirm({
        title: `确认删除「${skill.name}」？`,
        content: "删除后不可恢复",
        onOk: async () => {
            try {
                await deleteSkill(skill.id);
                message.success("删除成功");
                drawerOpen.value = false;
                loadSkills();
                loadTags();
            } catch { message.error("删除失败"); }
        },
    });
}

// ---- Create skill ----
const createDialogOpen = ref(false);
const createForm = ref({ name: "", description: "", content: "", tags: [] as string[] });
const creating = ref(false);
const createTagInput = ref("");

function openCreateDialog() {
    createForm.value = { name: "", description: "", content: "", tags: [] };
    createTagInput.value = "";
    createDialogOpen.value = true;
}

function addCreateTag(tag?: string) {
    const t = (tag || createTagInput.value).trim();
    if (!t) return;
    if (!createForm.value.tags.includes(t)) {
        createForm.value.tags.push(t);
    }
    createTagInput.value = "";
}

function removeCreateTag(tag: string) {
    createForm.value.tags = createForm.value.tags.filter(t => t !== tag);
}

function toggleCreateTag(tag: string) {
    if (createForm.value.tags.includes(tag)) {
        removeCreateTag(tag);
    } else {
        addCreateTag(tag);
    }
}

async function handleCreate() {
    if (!createForm.value.name.trim()) { message.error("请输入名称"); return; }
    creating.value = true;
    try {
        await createSkill({
            name: createForm.value.name,
            description: createForm.value.description,
            content: createForm.value.content,
            tags: createForm.value.tags,
        });
        message.success("创建成功");
        createDialogOpen.value = false;
        loadSkills();
        loadTags();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "创建失败");
    } finally { creating.value = false; }
}

async function handleAiGenerateContent() {
    if (!createForm.value.name.trim()) {
        message.warning("请先输入 Skill 名称");
        return;
    }
    creating.value = true;
    try {
        const res: any = await createSkill({
            name: createForm.value.name,
            description: createForm.value.description || "",
            content: "（AI 生成中...）",
            tags: createForm.value.tags,
        });
        message.success("Skill 已创建，正在生成内容...");
        const promptRes: any = await generateSkillContentPrompt(res.id || res.skill?.id);
        if (promptRes?.prompt) {
            createDialogOpen.value = false;
            router.push({ name: "chat", query: { prompt: promptRes.prompt } });
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "创建失败");
    } finally {
        creating.value = false;
    }
}

// ---- Helpers ----
function scopeLabel(scope: string): string {
    if (scope === "builtin") return "内置";
    if (scope === "public") return "公共";
    if (scope === "marketplace") return "市场";
    return "个人";
}

function scopeColor(scope: string): string {
    if (scope === "builtin") return "blue";
    if (scope === "public") return "green";
    if (scope === "marketplace") return "cyan";
    return "purple";
}

onMounted(() => { loadSkills(); loadTags(); });

</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <!-- Header -->
            <div class="flex items-center justify-between mb-5">
                <div class="flex items-center gap-2">
                    <BookOpen :size="18" class="text-blue-600" />
                    <h3 class="text-base font-medium text-gray-800">技能库</h3>
                    <span class="text-xs text-gray-400">管理所有技能，启用的技能对全局 AI 对话生效</span>
                </div>
                <div class="flex items-center gap-2">
                    <VortButton variant="primary" size="small" @click="openCreateDialog">
                        <Plus :size="14" class="mr-1" /> 新建技能
                    </VortButton>
                </div>
            </div>

            <!-- Tag filter bar -->
            <div class="flex items-center gap-2 mb-4 flex-wrap">
                <Tag :size="14" class="text-gray-400 flex-shrink-0" />
                <button
                    class="px-2.5 py-1 rounded-full text-xs font-medium transition-colors"
                    :class="selectedTags.length === 0
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
                    @click="clearTags"
                >全部</button>
                <button
                    v-for="tag in allTags" :key="tag"
                    class="px-2.5 py-1 rounded-full text-xs font-medium transition-colors"
                    :class="selectedTags.includes(tag)
                        ? 'bg-blue-100 text-blue-700'
                        : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
                    @click="toggleTag(tag)"
                >{{ tag }}</button>

                <div class="ml-auto flex-shrink-0">
                    <VortInput
                        v-model="searchKeyword"
                        size="small"
                        allow-clear
                        placeholder="搜索技能..."
                        class="w-[180px]"
                    >
                        <template #prefix>
                            <Search :size="14" class="text-gray-400" />
                        </template>
                    </VortInput>
                </div>
            </div>

            <!-- Skills grid -->
            <VortSpin :spinning="loading">
                <div v-if="filteredSkills.length === 0 && !loading" class="text-center py-12 text-gray-400 text-sm">
                    {{ searchKeyword || selectedTags.length ? '没有匹配的技能' : '暂无技能' }}
                </div>

                <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    <div v-for="skill in filteredSkills" :key="skill.id"
                        class="flex flex-col px-4 py-3 rounded-lg border border-gray-100 hover:border-[var(--vort-primary,#1456f0)] hover:shadow-sm transition-all cursor-pointer"
                        @click="openDrawer(skill)">
                        <div class="flex items-start justify-between">
                            <div class="min-w-0 flex-1">
                                <div class="text-sm font-medium text-gray-800 truncate">{{ skill.name }}</div>
                                <div class="text-xs text-gray-400 truncate mt-0.5">{{ skill.description || '暂无描述' }}</div>
                            </div>
                            <div class="flex items-center gap-2 flex-shrink-0 ml-3" @click.stop>
                                <VortTag :color="scopeColor(skill.scope)" size="small">{{ scopeLabel(skill.scope) }}</VortTag>
                                <VortSwitch :checked="skill.enabled" size="small" @change="handleToggle(skill)" />
                            </div>
                        </div>
                        <div v-if="skill.tags?.length" class="flex flex-wrap gap-1 mt-2">
                            <span v-for="tag in skill.tags" :key="tag"
                                class="px-1.5 py-0.5 rounded text-[10px] bg-gray-100 text-gray-500">{{ tag }}</span>
                        </div>
                    </div>
                </div>
            </VortSpin>
        </div>

        <!-- Detail / edit drawer -->
        <VortDrawer :open="drawerOpen" :title="drawerSkill?.name || '技能详情'" :width="640" @update:open="drawerOpen = $event">
            <VortSpin :spinning="drawerLoading">
                <div v-if="drawerSkill" class="space-y-4">
                    <VortForm label-width="80px">
                        <VortFormItem label="名称">
                            <VortInput v-model="drawerSkill.name" :disabled="drawerSkill.scope === 'builtin'" />
                        </VortFormItem>
                        <VortFormItem label="来源">
                            <VortTag :color="scopeColor(drawerSkill.scope)">
                                {{ scopeLabel(drawerSkill.scope) }}
                            </VortTag>
                        </VortFormItem>
                        <VortFormItem label="标签">
                            <div class="space-y-2">
                                <div class="flex flex-wrap gap-1.5">
                                    <button
                                        v-for="tag in allTags" :key="tag"
                                        class="px-2 py-0.5 rounded-md text-xs font-medium transition-colors"
                                        :class="drawerSkill.tags.includes(tag)
                                            ? 'bg-blue-100 text-blue-700 ring-1 ring-blue-200'
                                            : 'bg-gray-50 text-gray-500 hover:bg-gray-100'"
                                        :disabled="drawerSkill.scope === 'builtin'"
                                        @click="toggleDrawerTag(tag)"
                                    >{{ tag }}</button>
                                </div>
                                <div class="flex flex-wrap gap-1.5" v-if="drawerSkill.tags.some(t => !allTags.includes(t))">
                                    <span v-for="tag in drawerSkill.tags.filter(t => !allTags.includes(t))" :key="tag"
                                        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 text-xs">
                                        {{ tag }}
                                        <button v-if="drawerSkill.scope !== 'builtin'"
                                            class="text-blue-400 hover:text-red-500"
                                            @click="removeTagFromDrawer(tag)">
                                            <X :size="10" />
                                        </button>
                                    </span>
                                </div>
                                <VortInput
                                    v-if="drawerSkill.scope !== 'builtin'"
                                    v-model="tagInput"
                                    placeholder="输入自定义标签，回车添加"
                                    @press-enter="() => addTagToDrawer()"
                                />
                            </div>
                        </VortFormItem>
                        <VortFormItem label="描述">
                            <VortInput v-model="drawerSkill.description" :disabled="drawerSkill.scope === 'builtin'" placeholder="Skill 描述" />
                        </VortFormItem>
                        <VortFormItem label="内容">
                            <VortTextarea v-model="drawerSkill.content" :disabled="drawerSkill.scope === 'builtin'"
                                placeholder="Markdown 格式的 Skill 内容" :rows="16"
                                style="font-family: monospace; font-size: 13px;" />
                        </VortFormItem>
                    </VortForm>
                </div>
            </VortSpin>
            <template #footer>
                <div class="flex items-center justify-between w-full">
                    <div>
                        <VortButton v-if="drawerSkill?.scope === 'public'" danger @click="handleDeletePublic(drawerSkill!)">
                            <Trash2 :size="14" class="mr-1" /> 删除
                        </VortButton>
                    </div>
                    <div class="flex items-center gap-2">
                        <VortButton @click="drawerOpen = false">关闭</VortButton>
                        <VortButton v-if="drawerSkill?.scope !== 'builtin'" variant="primary" :loading="saving" @click="handleSaveDrawer">
                            <Save :size="14" class="mr-1" /> 保存
                        </VortButton>
                    </div>
                </div>
            </template>
        </VortDrawer>

        <!-- Create skill dialog -->
        <VortDialog :open="createDialogOpen" title="新建技能" @update:open="createDialogOpen = $event">
            <VortForm label-width="80px">
                <VortFormItem label="名称" required>
                    <VortInput v-model="createForm.name" placeholder="如：代码审查规范" />
                </VortFormItem>
                <VortFormItem label="标签">
                    <div class="space-y-2">
                        <div class="flex flex-wrap gap-1.5">
                            <button
                                v-for="tag in allTags" :key="tag"
                                class="px-2 py-0.5 rounded-md text-xs font-medium transition-colors"
                                :class="createForm.tags.includes(tag)
                                    ? 'bg-blue-100 text-blue-700 ring-1 ring-blue-200'
                                    : 'bg-gray-50 text-gray-500 hover:bg-gray-100'"
                                @click="toggleCreateTag(tag)"
                            >{{ tag }}</button>
                        </div>
                        <div class="flex flex-wrap gap-1.5" v-if="createForm.tags.some(t => !allTags.includes(t))">
                            <span v-for="tag in createForm.tags.filter(t => !allTags.includes(t))" :key="tag"
                                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 text-xs">
                                {{ tag }}
                                <button class="text-blue-400 hover:text-red-500" @click="removeCreateTag(tag)">
                                    <X :size="10" />
                                </button>
                            </span>
                        </div>
                        <VortInput
                            v-model="createTagInput"
                            placeholder="输入自定义标签，回车添加"
                            @press-enter="() => addCreateTag()"
                        />
                    </div>
                </VortFormItem>
                <VortFormItem label="描述">
                    <VortInput v-model="createForm.description" placeholder="Skill 用途描述" />
                </VortFormItem>
                <VortFormItem label="内容">
                    <div class="space-y-2">
                        <VortTextarea v-model="createForm.content" placeholder="Markdown 格式的 Skill 内容" :rows="8"
                            style="font-family: monospace; font-size: 13px;" />
                        <div class="flex justify-end">
                            <VortButton size="small" @click="handleAiGenerateContent">
                                <Bot :size="12" class="mr-1" /> AI 助手创建
                            </VortButton>
                        </div>
                    </div>
                </VortFormItem>
            </VortForm>
            <template #footer>
                <div class="flex justify-end gap-2">
                    <VortButton @click="createDialogOpen = false">取消</VortButton>
                    <VortButton variant="primary" :loading="creating" @click="handleCreate">创建</VortButton>
                </div>
            </template>
        </VortDialog>

    </div>
</template>
