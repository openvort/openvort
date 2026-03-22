<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import {
    getSkills, getSkill, createSkill, updateSkill, deleteSkill, toggleSkill,
    getSkillTags,
    generateSkillContentPrompt,
} from "@/api";
import { message, dialog } from "@/components/vort";
import { Plus, Trash2, Save, BookOpen, Bot, X, Tag, Search, Info, ArrowUpDown, Pencil } from "lucide-vue-next";
import MarkdownView from "@/components/vort-biz/editor/MarkdownView.vue";

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

// ---- Filters ----
const allTags = ref<string[]>([]);
const selectedTags = ref<string[]>([]);
const searchKeyword = ref("");
const selectedScope = ref("");
const sortBy = ref<"name" | "scope">("name");

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

const scopeOptions = [
    { label: "全部", value: "" },
    { label: "内置", value: "builtin" },
    { label: "公共", value: "public" },
    { label: "市场", value: "marketplace" },
];

function scopeCount(scope: string): number {
    if (!scope) return skills.value.length;
    return skills.value.filter(s => s.scope === scope).length;
}

const SCOPE_ORDER: Record<string, number> = { builtin: 0, public: 1, marketplace: 2, personal: 3 };

const filteredSkills = computed(() => {
    let list = skills.value;
    if (selectedScope.value) {
        list = list.filter(s => s.scope === selectedScope.value);
    }
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
    const sorted = [...list];
    if (sortBy.value === "name") {
        sorted.sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
    } else {
        sorted.sort((a, b) => (SCOPE_ORDER[a.scope] ?? 9) - (SCOPE_ORDER[b.scope] ?? 9));
    }
    return sorted;
});

const hasFilter = computed(() => !!searchKeyword.value || selectedTags.value.length > 0 || !!selectedScope.value);
const enabledCount = computed(() => skills.value.filter(s => s.enabled).length);

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
const contentTab = ref<"edit" | "preview">("edit");
const editing = ref(false);

async function openDrawer(skill: SkillItem) {
    drawerLoading.value = true;
    drawerOpen.value = true;
    contentTab.value = "edit";
    editing.value = false;
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

function handleDeleteSkill(skill: SkillItem) {
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

const SCOPE_BG: Record<string, string> = {
    builtin: "bg-blue-500",
    public: "bg-emerald-500",
    marketplace: "bg-cyan-500",
    personal: "bg-purple-500",
};

function scopeBgClass(scope: string): string {
    return SCOPE_BG[scope] || "bg-gray-400";
}

const isEditable = (scope: string) => scope !== "builtin";
const isDeletable = (scope: string) => scope === "public" || scope === "marketplace";

onMounted(() => { loadSkills(); loadTags(); });

</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <!-- Header -->
            <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                    <BookOpen :size="18" class="text-blue-600" />
                    <h3 class="text-base font-medium text-gray-800">技能管理</h3>
                    <span class="text-xs text-gray-400">管理 AI 的知识与工作流，通过知识、脚本和模板增强 AI 的专业能力</span>
                </div>
                <div class="flex items-center gap-2">
                    <AiAssistButton prompt="我想创建一个新的技能（Skill），请引导我完成创建。请先询问我技能的名称、描述和用途，然后帮我生成专业的 Skill 内容并创建。" label="AI 助手创建" />
                    <VortButton variant="primary" @click="openCreateDialog">
                        <Plus :size="14" class="mr-1" /> 新建技能
                    </VortButton>
                </div>
            </div>

            <!-- Stats -->
            <div class="flex items-center gap-3 mb-5 text-xs">
                <span class="text-gray-400">共 {{ skills.length }} 个技能</span>
                <span class="text-emerald-500">{{ enabledCount }} 个已启用</span>
            </div>

            <!-- Scope filter + Sort + Search -->
            <div class="flex items-center justify-between gap-4 mb-3">
                <div class="flex items-center gap-1 bg-gray-50 rounded-lg p-0.5">
                    <button
                        v-for="opt in scopeOptions" :key="opt.value"
                        class="px-3 py-1.5 rounded-md text-xs font-medium transition-all"
                        :class="selectedScope === opt.value
                            ? 'bg-white text-gray-800 shadow-sm'
                            : 'text-gray-500 hover:text-gray-700'"
                        @click="selectedScope = opt.value"
                    >{{ opt.label }}<span class="ml-1 text-[10px] text-gray-400">{{ scopeCount(opt.value) }}</span></button>
                </div>
                <div class="flex items-center gap-2">
                    <VortTooltip title="切换排序方式">
                        <button
                            class="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-gray-500 hover:bg-gray-50 transition-colors whitespace-nowrap flex-shrink-0"
                            @click="sortBy = sortBy === 'name' ? 'scope' : 'name'"
                        >
                            <ArrowUpDown :size="13" />
                            {{ sortBy === 'name' ? '按名称' : '按来源' }}
                        </button>
                    </VortTooltip>
                    <VortInput
                        v-model="searchKeyword"
                        size="small"
                        allow-clear
                        placeholder="搜索技能..."
                        class="w-[200px]"
                    >
                        <template #prefix>
                            <Search :size="14" class="text-gray-400" />
                        </template>
                    </VortInput>
                </div>
            </div>

            <!-- Tag filter bar -->
            <div v-if="allTags.length" class="flex items-center gap-2 mb-4 flex-wrap">
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
            </div>

            <!-- Skills grid -->
            <VortSpin :spinning="loading">
                <!-- Empty state -->
                <div v-if="filteredSkills.length === 0 && !loading" class="flex flex-col items-center justify-center py-16">
                    <BookOpen :size="48" class="text-gray-200 mb-4" />
                    <p class="text-sm text-gray-400 mb-1">
                        {{ hasFilter ? '没有匹配的技能' : '暂无技能' }}
                    </p>
                    <p v-if="!hasFilter" class="text-xs text-gray-300 mb-4">
                        技能可以让 AI 获得特定领域的知识和工作流程
                    </p>
                    <VortButton v-if="!hasFilter" variant="primary" size="small" @click="openCreateDialog">
                        <Plus :size="14" class="mr-1" /> 创建第一个技能
                    </VortButton>
                </div>

                <!-- Match count hint -->
                <div v-if="hasFilter && filteredSkills.length > 0" class="text-xs text-gray-400 mb-3">
                    找到 {{ filteredSkills.length }} 个技能
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    <div v-for="skill in filteredSkills" :key="skill.id"
                        class="group flex flex-col p-4 rounded-xl border transition-all cursor-pointer"
                        :class="skill.enabled
                            ? 'border-gray-100 hover:border-blue-200 hover:shadow-md bg-white'
                            : 'border-gray-100 bg-gray-50/50 opacity-55 hover:opacity-80 hover:shadow-sm'"
                        @click="openDrawer(skill)">
                        <div class="flex items-start gap-3">
                            <div class="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 text-xs font-bold text-white"
                                :class="scopeBgClass(skill.scope)">
                                {{ skill.name.charAt(0) }}
                            </div>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2">
                                    <span class="text-sm font-semibold text-gray-800 truncate">{{ skill.name }}</span>
                                    <VortTag :color="scopeColor(skill.scope)" size="small">{{ scopeLabel(skill.scope) }}</VortTag>
                                </div>
                                <div class="text-xs text-gray-400 line-clamp-2 mt-1 leading-relaxed">{{ skill.description || '暂无描述' }}</div>
                            </div>
                            <div class="flex-shrink-0" @click.stop>
                                <VortSwitch :checked="skill.enabled" size="small" @change="handleToggle(skill)" />
                            </div>
                        </div>
                        <div v-if="skill.tags?.length" class="flex flex-wrap gap-1.5 mt-3 pt-3 border-t border-gray-100/60">
                            <span v-for="tag in skill.tags" :key="tag"
                                class="px-2 py-0.5 rounded-md text-[11px] bg-gray-50 text-gray-500 group-hover:bg-gray-100 transition-colors">{{ tag }}</span>
                        </div>
                    </div>
                </div>
            </VortSpin>
        </div>

        <!-- Detail / edit drawer -->
        <VortDrawer :open="drawerOpen" :title="drawerSkill?.name || '技能详情'" :width="720" @update:open="drawerOpen = $event">
            <VortSpin :spinning="drawerLoading">
                <div v-if="drawerSkill" class="space-y-6">
                    <!-- Builtin hint -->
                    <div v-if="drawerSkill.scope === 'builtin'"
                        class="flex items-center gap-2 px-3 py-2.5 bg-blue-50 rounded-lg text-xs text-blue-600">
                        <Info :size="14" class="flex-shrink-0" />
                        内置技能不可编辑，如需自定义请创建新的公共技能
                    </div>

                    <!-- Hero header -->
                    <div class="flex items-start gap-4">
                        <div
                            class="w-14 h-14 rounded-xl flex items-center justify-center flex-shrink-0 text-lg font-bold text-white"
                            :class="scopeBgClass(drawerSkill.scope)"
                        >{{ drawerSkill.name.charAt(0) }}</div>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2">
                                <h3 class="text-lg font-semibold text-gray-800">{{ drawerSkill.name }}</h3>
                                <VortTag :color="scopeColor(drawerSkill.scope)" size="small" :bordered="false">
                                    {{ scopeLabel(drawerSkill.scope) }}
                                </VortTag>
                            </div>
                            <p class="text-sm text-gray-500 mt-1">{{ drawerSkill.description || '暂无描述' }}</p>
                            <div v-if="drawerSkill.tags?.length" class="flex flex-wrap items-center gap-1.5 mt-2">
                                <VortTag
                                    v-for="tag in drawerSkill.tags"
                                    :key="tag"
                                    color="default"
                                    size="small"
                                    :bordered="false"
                                >{{ tag }}</VortTag>
                            </div>
                        </div>
                        <div class="flex items-center gap-2 flex-shrink-0">
                            <VortSwitch :checked="drawerSkill.enabled" size="small" @change="handleToggle(drawerSkill!)" />
                        </div>
                    </div>

                    <!-- Skill info card -->
                    <div class="bg-blue-50/50 border border-blue-100 rounded-lg p-4">
                        <h4 class="text-sm font-medium text-blue-700 mb-2">Skill 信息</h4>
                        <div class="grid grid-cols-2 gap-3 text-sm">
                            <div class="flex items-center justify-between">
                                <span class="text-gray-500">类型</span>
                                <VortTag color="blue" size="small" :bordered="false">{{ drawerSkill.skill_type || '通用' }}</VortTag>
                            </div>
                            <div class="flex items-center justify-between">
                                <span class="text-gray-500">来源</span>
                                <VortTag :color="scopeColor(drawerSkill.scope)" size="small" :bordered="false">{{ scopeLabel(drawerSkill.scope) }}</VortTag>
                            </div>
                        </div>
                    </div>

                    <!-- Editable sections -->
                    <template v-if="isEditable(drawerSkill.scope) && editing">
                        <div class="border-t border-gray-100 pt-4">
                            <h4 class="text-sm font-medium text-gray-700 mb-3">基本信息</h4>
                            <div class="space-y-3">
                                <div>
                                    <label class="text-xs text-gray-500 mb-1 block">名称</label>
                                    <VortInput v-model="drawerSkill.name" />
                                </div>
                                <div>
                                    <label class="text-xs text-gray-500 mb-1 block">描述</label>
                                    <VortInput v-model="drawerSkill.description" placeholder="Skill 描述" />
                                </div>
                            </div>
                        </div>

                        <div class="border-t border-gray-100 pt-4">
                            <h4 class="text-sm font-medium text-gray-700 mb-3">标签</h4>
                            <div class="space-y-2">
                                <div class="flex flex-wrap gap-1.5">
                                    <button
                                        v-for="tag in allTags" :key="tag"
                                        class="px-2 py-0.5 rounded-md text-xs font-medium transition-colors"
                                        :class="drawerSkill.tags.includes(tag)
                                            ? 'bg-blue-100 text-blue-700 ring-1 ring-blue-200'
                                            : 'bg-gray-50 text-gray-500 hover:bg-gray-100'"
                                        @click="toggleDrawerTag(tag)"
                                    >{{ tag }}</button>
                                </div>
                                <div class="flex flex-wrap gap-1.5" v-if="drawerSkill.tags.some(t => !allTags.includes(t))">
                                    <span v-for="tag in drawerSkill.tags.filter(t => !allTags.includes(t))" :key="tag"
                                        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 text-xs">
                                        {{ tag }}
                                        <button class="text-blue-400 hover:text-red-500" @click="removeTagFromDrawer(tag)">
                                            <X :size="10" />
                                        </button>
                                    </span>
                                </div>
                                <VortInput
                                    v-model="tagInput"
                                    placeholder="输入自定义标签，回车添加"
                                    @press-enter="() => addTagToDrawer()"
                                />
                            </div>
                        </div>
                    </template>

                    <!-- Content section -->
                    <div class="border-t border-gray-100 pt-4">
                        <template v-if="isEditable(drawerSkill.scope) && editing">
                            <div class="flex gap-1 mb-4">
                                <button
                                    class="px-3 py-1.5 text-sm font-medium rounded-md transition-colors"
                                    :class="contentTab === 'edit' ? 'bg-blue-50 text-blue-600' : 'text-gray-500 hover:bg-gray-50'"
                                    @click="contentTab = 'edit'"
                                >编辑</button>
                                <button
                                    class="px-3 py-1.5 text-sm font-medium rounded-md transition-colors"
                                    :class="contentTab === 'preview' ? 'bg-blue-50 text-blue-600' : 'text-gray-500 hover:bg-gray-50'"
                                    @click="contentTab = 'preview'"
                                >预览</button>
                            </div>
                            <VortTextarea
                                v-if="contentTab === 'edit'"
                                v-model="drawerSkill.content"
                                placeholder="Markdown 格式的 Skill 内容"
                                :rows="16"
                                style="font-family: monospace; font-size: 13px;"
                            />
                            <div v-else class="bg-gray-50 rounded-lg p-5">
                                <MarkdownView v-if="drawerSkill.content" :content="drawerSkill.content" />
                                <p v-else class="text-sm text-gray-400">暂无内容</p>
                            </div>
                        </template>
                        <template v-else>
                            <h4 class="text-sm font-medium text-gray-700 mb-3">Skill 内容</h4>
                            <div class="bg-gray-50 rounded-lg p-5">
                                <MarkdownView v-if="drawerSkill.content" :content="drawerSkill.content" />
                                <p v-else class="text-sm text-gray-400">暂无内容</p>
                            </div>
                        </template>
                    </div>
                </div>
            </VortSpin>
            <template #footer>
                <div class="flex items-center justify-between w-full">
                    <div>
                        <VortButton v-if="drawerSkill && isDeletable(drawerSkill.scope)" danger @click="handleDeleteSkill(drawerSkill!)">
                            <Trash2 :size="14" class="mr-1" /> 删除
                        </VortButton>
                    </div>
                    <div class="flex items-center gap-2">
                        <VortButton @click="drawerOpen = false">关闭</VortButton>
                        <template v-if="drawerSkill && isEditable(drawerSkill.scope)">
                            <VortButton v-if="!editing" @click="editing = true">
                                <Pencil :size="14" class="mr-1" /> 编辑
                            </VortButton>
                            <VortButton v-else variant="primary" :loading="saving" @click="handleSaveDrawer">
                                <Save :size="14" class="mr-1" /> 保存
                            </VortButton>
                        </template>
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
