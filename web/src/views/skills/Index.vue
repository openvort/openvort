<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import {
    getSkills, getSkill, createSkill, updateSkill, deleteSkill, toggleSkill,
    getSkillTags,
    searchOnlineSkills, importSkillFromGithub,
    generateSkillContentPrompt,
} from "@/api";
import { message, dialog } from "@/components/vort";
import { Plus, Trash2, Save, BookOpen, Github, Bot, X, Tag, Search } from "lucide-vue-next";

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

function addTagToDrawer() {
    if (!drawerSkill.value || !tagInput.value.trim()) return;
    const tag = tagInput.value.trim();
    if (!drawerSkill.value.tags.includes(tag)) {
        drawerSkill.value.tags.push(tag);
    }
    tagInput.value = "";
}

function removeTagFromDrawer(tag: string) {
    if (!drawerSkill.value) return;
    drawerSkill.value.tags = drawerSkill.value.tags.filter(t => t !== tag);
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

function addCreateTag() {
    const tag = createTagInput.value.trim();
    if (tag && !createForm.value.tags.includes(tag)) {
        createForm.value.tags.push(tag);
    }
    createTagInput.value = "";
}

function removeCreateTag(tag: string) {
    createForm.value.tags = createForm.value.tags.filter(t => t !== tag);
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
    return "个人";
}

function scopeColor(scope: string): string {
    if (scope === "builtin") return "blue";
    if (scope === "public") return "green";
    return "purple";
}

onMounted(() => { loadSkills(); loadTags(); });

// ---- GitHub 导入 ----
const importDialogOpen = ref(false);
const importUrl = ref("");
const importLoading = ref(false);
const searchResults = ref<any[]>([]);
const searchLoading = ref(false);
const searchQuery = ref("");

async function handleSearchOnline() {
    if (!searchQuery.value.trim()) return;
    searchLoading.value = true;
    try {
        const res: any = await searchOnlineSkills(searchQuery.value);
        searchResults.value = res?.results || [];
    } catch { searchResults.value = []; }
    finally { searchLoading.value = false; }
}

async function handleImportFromUrl() {
    if (!importUrl.value.trim()) { message.error("请输入 GitHub URL"); return; }
    importLoading.value = true;
    try {
        const res: any = await importSkillFromGithub(importUrl.value);
        if (res?.success) {
            message.success("导入成功");
            importDialogOpen.value = false;
            importUrl.value = "";
            loadSkills();
            loadTags();
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "导入失败");
    }
    finally { importLoading.value = false; }
}

async function handleImportResult(result: any) {
    importLoading.value = true;
    try {
        const url = result.html_url || result.url;
        const res: any = await importSkillFromGithub(url);
        if (res?.success) {
            message.success(`成功导入: ${result.name}`);
            loadSkills();
            loadTags();
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "导入失败");
    }
    finally { importLoading.value = false; }
}

function openImportDialog() {
    importUrl.value = "";
    searchQuery.value = "";
    searchResults.value = [];
    importDialogOpen.value = true;
}
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
                    <VortButton variant="secondary" size="small" @click="openImportDialog">
                        <Github :size="14" class="mr-1" /> 从 GitHub 导入
                    </VortButton>
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
                    <div class="relative">
                        <Search :size="14" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                        <input
                            v-model="searchKeyword"
                            type="text"
                            placeholder="搜索技能..."
                            class="pl-8 pr-3 py-1.5 text-xs border border-gray-200 rounded-lg bg-gray-50 focus:bg-white focus:border-blue-300 focus:outline-none transition-colors w-[180px]"
                        />
                    </div>
                </div>
            </div>

            <!-- Skills grid -->
            <VortSpin :spinning="loading">
                <div v-if="filteredSkills.length === 0 && !loading" class="text-center py-12 text-gray-400 text-sm">
                    {{ searchKeyword || selectedTags.length ? '没有匹配的技能' : '暂无技能' }}
                </div>

                <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    <div v-for="skill in filteredSkills" :key="skill.id"
                        class="flex flex-col px-4 py-3 rounded-lg border border-gray-100 hover:border-blue-200 hover:shadow-sm transition-all cursor-pointer"
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
                                    <span v-for="tag in drawerSkill.tags" :key="tag"
                                        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 text-xs">
                                        {{ tag }}
                                        <button v-if="drawerSkill.scope !== 'builtin'"
                                            class="text-blue-400 hover:text-red-500"
                                            @click="removeTagFromDrawer(tag)">
                                            <X :size="10" />
                                        </button>
                                    </span>
                                    <span v-if="!drawerSkill.tags.length" class="text-xs text-gray-400">暂无标签</span>
                                </div>
                                <div v-if="drawerSkill.scope !== 'builtin'" class="flex gap-2">
                                    <input v-model="tagInput" type="text" placeholder="输入标签名，回车添加"
                                        class="flex-1 px-2.5 py-1.5 text-xs border border-gray-200 rounded-md focus:border-blue-300 focus:outline-none"
                                        @keydown.enter.prevent="addTagToDrawer" />
                                    <VortButton size="small" @click="addTagToDrawer">添加</VortButton>
                                </div>
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
                        <div class="flex flex-wrap gap-1.5" v-if="createForm.tags.length">
                            <span v-for="tag in createForm.tags" :key="tag"
                                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 text-xs">
                                {{ tag }}
                                <button class="text-blue-400 hover:text-red-500" @click="removeCreateTag(tag)">
                                    <X :size="10" />
                                </button>
                            </span>
                        </div>
                        <div class="flex gap-2">
                            <input v-model="createTagInput" type="text" placeholder="输入标签名，回车添加"
                                class="flex-1 px-2.5 py-1.5 text-xs border border-gray-200 rounded-md focus:border-blue-300 focus:outline-none"
                                list="existing-tags"
                                @keydown.enter.prevent="addCreateTag" />
                            <datalist id="existing-tags">
                                <option v-for="t in allTags" :key="t" :value="t" />
                            </datalist>
                            <VortButton size="small" @click="addCreateTag">添加</VortButton>
                        </div>
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

        <!-- GitHub import dialog -->
        <VortDialog :open="importDialogOpen" title="从 GitHub 导入 Skill" :width="600" @update:open="importDialogOpen = $event">
            <div class="space-y-4">
                <div>
                    <label class="block text-sm text-gray-600 mb-2">直接导入</label>
                    <div class="flex gap-2">
                        <VortInput v-model="importUrl" placeholder="输入 GitHub 仓库或 SKILL.md 文件 URL" class="flex-1" />
                        <VortButton variant="primary" :loading="importLoading" @click="handleImportFromUrl">导入</VortButton>
                    </div>
                    <p class="text-xs text-gray-400 mt-1">支持仓库 URL（如 https://github.com/owner/repo）或 SKILL.md 文件 URL</p>
                </div>

                <div class="border-t border-gray-200 my-4"></div>

                <div>
                    <label class="block text-sm text-gray-600 mb-2">在线搜索</label>
                    <VortInputSearch
                        v-model="searchQuery"
                        placeholder="输入关键词搜索"
                        allow-clear
                        enter-button="搜索"
                        :loading="searchLoading"
                        class="w-full"
                        @search="handleSearchOnline"
                    />
                </div>

                <div v-if="searchResults.length > 0" class="space-y-2 max-h-[300px] overflow-y-auto">
                    <div v-for="result in searchResults" :key="result.repo"
                        class="flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:border-blue-200">
                        <div class="min-w-0 flex-1">
                            <div class="flex items-center gap-2">
                                <span class="text-sm font-medium text-gray-800">{{ result.name }}</span>
                                <span class="text-xs text-gray-400">{{ result.stars }}</span>
                            </div>
                            <div class="text-xs text-gray-400 truncate">{{ result.repo }}</div>
                            <div class="text-xs text-gray-400 truncate">{{ result.description }}</div>
                        </div>
                        <VortButton size="small" variant="primary" :loading="importLoading" @click="handleImportResult(result)">
                            导入
                        </VortButton>
                    </div>
                </div>
                <div v-else-if="searchLoading" class="text-center py-4 text-gray-400 text-sm">搜索中...</div>
                <div v-else-if="searchQuery && !searchLoading" class="text-center py-4 text-gray-400 text-sm">未找到相关 Skills</div>
            </div>
            <template #footer>
                <div class="flex justify-end gap-2">
                    <VortButton @click="importDialogOpen = false">关闭</VortButton>
                </div>
            </template>
        </VortDialog>
    </div>
</template>
