<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import {
    getSkills, getSkill, createSkill, updateSkill, deleteSkill, toggleSkill,
    getSkillTags, generateSkillContentPrompt,
    getPlugins, getPluginDetail, updatePlugin,
    marketplaceSearch, marketplaceGetDetail,
    marketplaceInstallSkill, marketplaceInstallPlugin,
    marketplaceListInstalled, marketplaceUninstall,
} from "@/api";
import { message } from "@/components/vort/message";
import { dialog } from "@/components/vort/dialog";
import {
    Puzzle, BookOpen, Search, Download, Star, Store,
    Trash2, Tag, Package, ExternalLink, Plus, Save, Bot, X,
    Wrench, ChevronDown, ChevronRight, Calendar, ArrowUpDown, Github,
} from "lucide-vue-next";
import MarkdownView from "@/components/vort-biz/editor/MarkdownView.vue";

const router = useRouter();
const activeTab = ref<string>("enabled");
const searchKeyword = ref("");
const sourceFilter = ref<"all" | "builtin" | "marketplace" | "custom">("all");

interface UnifiedItem {
    id: string;
    name: string;
    displayName: string;
    description: string;
    source: "builtin" | "marketplace" | "custom" | "pip" | "local";
    kind: "skill" | "plugin";
    enabled: boolean;
    tags: string[];
    toolsCount?: number;
    tools?: { name: string; description: string }[];
    slug?: string;
    author?: string;
    version?: string;
    hasConfig?: boolean;
    core?: boolean;
    _raw?: any;
}

const items = ref<UnifiedItem[]>([]);
const loading = ref(false);

const filteredItems = computed(() => {
    let list = items.value;
    if (sourceFilter.value !== "all") {
        if (sourceFilter.value === "custom") {
            list = list.filter(i => !["builtin", "marketplace"].includes(i.source));
        } else {
            list = list.filter(i => i.source === sourceFilter.value);
        }
    }
    if (searchKeyword.value) {
        const kw = searchKeyword.value.toLowerCase();
        list = list.filter(i =>
            i.name.toLowerCase().includes(kw)
            || i.displayName.toLowerCase().includes(kw)
            || i.description.toLowerCase().includes(kw)
            || i.tags.some(t => t.toLowerCase().includes(kw))
        );
    }
    return list;
});

async function loadAll() {
    loading.value = true;
    try {
        const [skillsRes, pluginsRes] = await Promise.all([getSkills(), getPlugins()]);
        const unified: UnifiedItem[] = [];

        const skillsList = (skillsRes as any)?.skills || skillsRes || [];
        for (const s of skillsList) {
            let source: UnifiedItem["source"] = "builtin";
            if (s.scope === "marketplace") source = "marketplace";
            else if (s.scope === "personal") source = "custom";
            else if (s.scope === "public") source = "custom";

            unified.push({
                id: s.id, name: s.name,
                displayName: s.marketplace_display_name || s.name,
                description: s.description || "", source, kind: "skill",
                enabled: s.enabled,
                tags: (() => { try { return JSON.parse(s.tags || "[]"); } catch { return []; } })(),
                slug: s.marketplace_slug, author: s.marketplace_author,
                version: s.marketplace_version, _raw: s,
            });
        }

        const pluginsList = (pluginsRes as any)?.plugins || pluginsRes || [];
        for (const p of pluginsList) {
            let source: UnifiedItem["source"] = "builtin";
            if (p.source === "pip") source = "pip";
            else if (p.source === "local") source = "local";

            unified.push({
                id: p.name, name: p.name,
                displayName: p.display_name || p.name,
                description: p.description || "", source, kind: "plugin",
                enabled: p.enabled, tags: [],
                toolsCount: p.tools_count || p.tools?.length || 0,
                tools: p.tools || [],
                hasConfig: p.has_config, core: p.core,
                version: p.version, _raw: p,
            });
        }
        items.value = unified;
    } catch (e: any) {
        message.error("加载失败: " + (e.message || e));
    } finally { loading.value = false; }
}

async function handleToggle(item: UnifiedItem) {
    try {
        if (item.kind === "skill") {
            const res: any = await toggleSkill(item.id);
            if (res?.success) item.enabled = res.enabled;
            message.success(item.enabled ? "已启用" : "已禁用");
        } else {
            await updatePlugin(item.name, { enabled: !item.enabled });
            item.enabled = !item.enabled;
            message.success(item.enabled ? "已启用" : "已禁用");
        }
    } catch (e: any) {
        message.error("操作失败: " + (e.message || e));
    }
}

function sourceLabel(source: string): string {
    const map: Record<string, string> = {
        builtin: "内置", marketplace: "市场", custom: "自定义",
        pip: "pip", local: "本地",
    };
    return map[source] || source;
}

function sourceTagColor(source: string): string {
    const map: Record<string, string> = {
        builtin: "blue", marketplace: "green", custom: "orange",
        pip: "purple", local: "default",
    };
    return map[source] || "default";
}

function handleCardClick(item: UnifiedItem) {
    if (item.kind === "skill") {
        openSkillDrawer(item);
    } else if (item.hasConfig) {
        openPluginConfig(item.name);
    }
}

// ---- Skill detail drawer ----
const skillDrawerOpen = ref(false);
const skillDrawerData = ref<any>(null);
const skillDrawerLoading = ref(false);
const skillSaving = ref(false);
const skillTagInput = ref("");

async function openSkillDrawer(item: UnifiedItem) {
    skillDrawerLoading.value = true;
    skillDrawerOpen.value = true;
    try {
        const res: any = await getSkill(item.id);
        skillDrawerData.value = {
            id: res.id, name: res.name, description: res.description,
            content: res.content, scope: res.scope, skill_type: res.skill_type,
            tags: res.tags || [], enabled: res.enabled,
        };
    } catch {
        message.error("加载详情失败");
        skillDrawerOpen.value = false;
    } finally { skillDrawerLoading.value = false; }
}

function addSkillTag() {
    if (!skillDrawerData.value || !skillTagInput.value.trim()) return;
    const tag = skillTagInput.value.trim();
    if (!skillDrawerData.value.tags.includes(tag)) {
        skillDrawerData.value.tags.push(tag);
    }
    skillTagInput.value = "";
}

function removeSkillTag(tag: string) {
    if (!skillDrawerData.value) return;
    skillDrawerData.value.tags = skillDrawerData.value.tags.filter((t: string) => t !== tag);
}

async function handleSaveSkill() {
    if (!skillDrawerData.value || skillDrawerData.value.scope === "builtin") return;
    skillSaving.value = true;
    try {
        await updateSkill(skillDrawerData.value.id, {
            name: skillDrawerData.value.name,
            description: skillDrawerData.value.description,
            content: skillDrawerData.value.content,
            tags: skillDrawerData.value.tags,
        });
        message.success("保存成功");
        skillDrawerOpen.value = false;
        loadAll();
    } catch { message.error("保存失败"); }
    finally { skillSaving.value = false; }
}

function handleDeleteSkill() {
    if (!skillDrawerData.value) return;
    dialog.confirm({
        title: `确认删除「${skillDrawerData.value.name}」？`,
        content: "删除后不可恢复",
        onOk: async () => {
            try {
                await deleteSkill(skillDrawerData.value.id);
                message.success("删除成功");
                skillDrawerOpen.value = false;
                loadAll();
            } catch { message.error("删除失败"); }
        },
    });
}

// ---- Create skill dialog ----
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
    if (tag && !createForm.value.tags.includes(tag)) createForm.value.tags.push(tag);
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
        loadAll();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "创建失败");
    } finally { creating.value = false; }
}

async function handleAiGenerate() {
    if (!createForm.value.name.trim()) { message.warning("请先输入 Skill 名称"); return; }
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
    } finally { creating.value = false; }
}

// ---- Plugin config drawer ----
interface ConfigField { key: string; label: string; type: string; required: boolean; secret: boolean; placeholder: string; options?: { value: string; label: string }[]; }
const pluginDrawerOpen = ref(false);
const pluginDrawerLoading = ref(false);
const pluginSaving = ref(false);
const currentPluginName = ref("");
const configSchema = ref<ConfigField[]>([]);
const configForm = ref<Record<string, string>>({});

async function openPluginConfig(name: string) {
    currentPluginName.value = name;
    pluginDrawerOpen.value = true;
    pluginDrawerLoading.value = true;
    try {
        const res: any = await getPluginDetail(name);
        configSchema.value = res?.config_schema || [];
        const config = res?.config || {};
        configForm.value = {};
        for (const field of configSchema.value) {
            configForm.value[field.key] = config[field.key] ?? "";
        }
    } catch { message.error("加载配置失败"); }
    finally { pluginDrawerLoading.value = false; }
}

async function handleSavePlugin() {
    pluginSaving.value = true;
    try {
        await updatePlugin(currentPluginName.value, configForm.value);
        message.success("配置已保存");
        pluginDrawerOpen.value = false;
        loadAll();
    } catch { message.error("保存失败"); }
    finally { pluginSaving.value = false; }
}

// ---- Tool list expand ----
const expandedTools = ref<Record<string, boolean>>({});
function toggleTools(name: string) { expandedTools.value[name] = !expandedTools.value[name]; }

// ---- Uninstall marketplace item ----
function handleUninstall(item: UnifiedItem) {
    dialog.confirm({
        title: "确认卸载",
        content: `确定卸载「${item.displayName}」？`,
        onOk: async () => {
            try {
                await marketplaceUninstall(item.slug || item.name, item.kind);
                message.success("已卸载");
                loadAll();
            } catch (e: any) { message.error("卸载失败: " + (e.message || e)); }
        },
    });
}

// ---- Marketplace Tab ----
const mpSearch = ref("");
const mpItems = ref<any[]>([]);
const mpLoading = ref(false);
const mpInstalled = ref<Set<string>>(new Set());

async function loadMarketplace() {
    mpLoading.value = true;
    try {
        const [searchRes, installedRes] = await Promise.all([
            marketplaceSearch({ query: mpSearch.value, limit: 20 }),
            marketplaceListInstalled(),
        ]);
        mpItems.value = (searchRes as any)?.items || [];
        const installed = (installedRes as any) || [];
        mpInstalled.value = new Set(installed.map((i: any) => i.slug));
    } catch { message.error("加载市场失败"); }
    finally { mpLoading.value = false; }
}

const mpInstallingSlug = ref("");

async function handleInstall(item: any) {
    mpInstallingSlug.value = item.slug;
    try {
        if (item.type === "plugin") await marketplaceInstallPlugin(item.slug, item.author);
        else await marketplaceInstallSkill(item.slug, item.author);
        mpInstalled.value.add(item.slug);
        message.success(`${item.displayName} 安装成功`);
        loadAll();
    } catch (e: any) { message.error("安装失败: " + (e.message || e)); }
    finally { mpInstallingSlug.value = ""; }
}

// ---- Marketplace detail drawer ----
const mpDetailOpen = ref(false);
const mpDetailLoading = ref(false);
const mpDetail = ref<any>(null);
const mpDetailTab = ref("readme");

async function openMpDetail(item: any) {
    mpDetailOpen.value = true;
    mpDetailLoading.value = true;
    mpDetailTab.value = "readme";
    mpDetail.value = null;
    try {
        const res: any = await marketplaceGetDetail(item.slug, item.author || "");
        mpDetail.value = res;
        mpDetailTab.value = res?.readme ? "readme" : (res?.type === "skill" && res?.content ? "content" : "readme");
    } catch { message.error("加载详情失败"); }
    finally { mpDetailLoading.value = false; }
}

function formatDate(date: string) {
    if (!date) return "-";
    return new Date(date).toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric" });
}

const skillTypeLabel: Record<string, string> = { role: "角色入设", workflow: "工作流程", knowledge: "知识库" };

let mpDebounce: ReturnType<typeof setTimeout>;
watch(mpSearch, () => { clearTimeout(mpDebounce); mpDebounce = setTimeout(loadMarketplace, 300); });
watch(activeTab, (tab) => { if (tab === "marketplace" && mpItems.value.length === 0) loadMarketplace(); });

onMounted(loadAll);
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-1">
                <h3 class="text-base font-medium text-gray-800">扩展管理</h3>
                <vort-button variant="primary" size="small" @click="openCreateDialog">
                    <Plus :size="14" class="mr-1" /> 新建技能
                </vort-button>
            </div>
            <p class="text-sm text-gray-400">管理所有扩展，启用的扩展将增强 AI 的知识和能力</p>
        </div>

        <div class="bg-white rounded-xl p-6">
            <vort-tabs v-model:activeKey="activeTab">
                <vort-tab-pane tab-key="enabled" tab="已启用">
                    <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4 mb-4 mt-2">
                        <vort-input-search
                            v-model="searchKeyword"
                            placeholder="搜索扩展..."
                            allow-clear
                            class="flex-1 sm:w-[280px]"
                        />
                        <vort-radio-group v-model="sourceFilter" size="small">
                            <vort-radio-button value="all">全部</vort-radio-button>
                            <vort-radio-button value="builtin">内置</vort-radio-button>
                            <vort-radio-button value="marketplace">市场</vort-radio-button>
                            <vort-radio-button value="custom">自定义</vort-radio-button>
                        </vort-radio-group>
                    </div>

                    <vort-spin :spinning="loading">
                        <div v-if="!loading && filteredItems.length === 0" class="text-center py-20 text-gray-400">
                            <Puzzle class="w-12 h-12 mx-auto mb-3 opacity-30" />
                            <p>暂无扩展</p>
                        </div>

                        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div
                                v-for="item in filteredItems"
                                :key="item.id"
                                class="border rounded-xl p-4 hover:shadow-sm hover:border-[var(--vort-primary,#1456f0)] transition-all cursor-pointer"
                                @click="handleCardClick(item)"
                            >
                                <div class="flex items-start justify-between gap-3">
                                    <div class="flex items-start gap-3 min-w-0 flex-1">
                                        <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                                            :class="item.kind === 'plugin' ? 'bg-purple-50' : 'bg-blue-50'">
                                            <component :is="item.kind === 'plugin' ? Puzzle : BookOpen"
                                                class="w-5 h-5" :class="item.kind === 'plugin' ? 'text-purple-500' : 'text-blue-500'" />
                                        </div>
                                        <div class="min-w-0">
                                            <div class="flex items-center gap-2 flex-wrap">
                                                <h4 class="font-semibold text-sm truncate">{{ item.displayName }}</h4>
                                                <vort-tag :color="sourceTagColor(item.source)" size="small">
                                                    {{ sourceLabel(item.source) }}
                                                </vort-tag>
                                            </div>
                                            <p class="text-xs text-gray-500 mt-0.5 line-clamp-1">{{ item.description }}</p>
                                            <div v-if="item.tags.length" class="flex gap-1 mt-1.5 flex-wrap">
                                                <vort-tag v-for="tag in item.tags.slice(0, 3)" :key="tag" size="small">{{ tag }}</vort-tag>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="flex items-center gap-2 shrink-0" @click.stop>
                                        <vort-tooltip v-if="item.source === 'marketplace'" title="卸载">
                                            <a class="text-sm text-red-500 cursor-pointer" @click="handleUninstall(item)">
                                                <Trash2 class="w-4 h-4" />
                                            </a>
                                        </vort-tooltip>
                                        <vort-button v-if="item.kind === 'plugin' && item.hasConfig" size="small" @click="openPluginConfig(item.name)">
                                            设置
                                        </vort-button>
                                        <vort-switch
                                            :checked="item.enabled"
                                            size="small"
                                            :disabled="item.kind === 'plugin' && item.core"
                                            @update:checked="handleToggle(item)"
                                        />
                                    </div>
                                </div>

                                <!-- Plugin tool list -->
                                <div v-if="item.kind === 'plugin' && item.tools?.length" class="mt-3 pt-3 border-t border-gray-100" @click.stop>
                                    <button
                                        class="flex items-center gap-1 text-xs text-gray-500 font-medium hover:text-blue-600 transition-colors"
                                        @click="toggleTools(item.name)"
                                    >
                                        <component :is="expandedTools[item.name] ? ChevronDown : ChevronRight" :size="12" />
                                        工具列表 ({{ item.tools.length }})
                                    </button>
                                    <div v-show="expandedTools[item.name]" class="mt-2 space-y-2">
                                        <div v-for="tool in item.tools" :key="tool.name"
                                            class="flex items-start gap-2 p-2 rounded bg-gray-50 text-xs">
                                            <Wrench :size="12" class="text-gray-400 mt-0.5 flex-shrink-0" />
                                            <div>
                                                <span class="font-medium text-gray-700">{{ tool.name }}</span>
                                                <p class="text-gray-400 mt-0.5">{{ tool.description }}</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </vort-spin>
                </vort-tab-pane>

                <vort-tab-pane tab-key="marketplace" tab="市场">
                    <div class="mb-4 mt-2">
                        <vort-input-search v-model="mpSearch" placeholder="搜索扩展市场..." allow-clear class="sm:w-[320px]" />
                    </div>

                    <vort-spin :spinning="mpLoading">
                        <div v-if="!mpLoading && mpItems.length === 0" class="text-center py-20 text-gray-400">
                            <Store class="w-12 h-12 mx-auto mb-3 opacity-30" />
                            <p>暂无结果</p>
                            <p class="text-xs mt-1">
                                浏览更多:
                                <a href="https://www.openvort.com/extensions" target="_blank" class="text-blue-500 hover:underline inline-flex items-center gap-1">
                                    openvort.com/extensions <ExternalLink class="w-3 h-3" />
                                </a>
                            </p>
                        </div>

                        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            <div
                                v-for="item in mpItems"
                                :key="item.id"
                                class="border rounded-xl p-4 hover:shadow-sm hover:border-[var(--vort-primary,#1456f0)] transition-all cursor-pointer"
                                @click="openMpDetail(item)"
                            >
                                <div class="flex items-start gap-3 mb-3">
                                    <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                                        :class="item.type === 'plugin' ? 'bg-purple-50' : 'bg-blue-50'">
                                        <component :is="item.type === 'plugin' ? Puzzle : BookOpen"
                                            class="w-5 h-5" :class="item.type === 'plugin' ? 'text-purple-500' : 'text-blue-500'" />
                                    </div>
                                    <div class="min-w-0 flex-1">
                                        <div class="flex items-center gap-1.5">
                                            <h4 class="font-semibold text-sm truncate">{{ item.displayName }}</h4>
                                            <vort-tag :color="item.type === 'plugin' ? 'purple' : 'blue'" size="small" :bordered="false">
                                                {{ item.type === 'plugin' ? 'Plugin' : 'Skill' }}
                                            </vort-tag>
                                        </div>
                                        <p class="text-xs text-gray-400">by {{ item.author }} &middot; v{{ item.version }}</p>
                                    </div>
                                </div>
                                <p class="text-xs text-gray-500 line-clamp-2 mb-3">{{ item.description }}</p>
                                <div v-if="item.tags?.length" class="flex flex-wrap gap-1 mb-3">
                                    <vort-tag v-for="tag in (item.tags || []).slice(0, 3)" :key="tag" size="small">{{ tag }}</vort-tag>
                                </div>
                                <div class="flex items-center justify-between pt-2 border-t border-gray-50">
                                    <div class="flex items-center gap-3 text-xs text-gray-400">
                                        <span class="flex items-center gap-1"><Download class="w-3 h-3" /> {{ item.downloads || 0 }}</span>
                                        <span class="flex items-center gap-1"><Star class="w-3 h-3" /> {{ item.stars || 0 }}</span>
                                    </div>
                                    <div @click.stop>
                                        <vort-button v-if="mpInstalled.has(item.slug)" size="small" disabled>已安装</vort-button>
                                        <vort-button v-else size="small" variant="primary" :loading="mpInstallingSlug === item.slug" @click="handleInstall(item)">安装</vort-button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="mt-8 text-center">
                            <a href="https://www.openvort.com/extensions" target="_blank"
                                class="text-sm text-blue-500 hover:underline inline-flex items-center gap-1">
                                浏览完整市场 <ExternalLink class="w-3.5 h-3.5" />
                            </a>
                        </div>
                    </vort-spin>
                </vort-tab-pane>
            </vort-tabs>
        </div>

        <!-- Skill detail drawer -->
        <vort-drawer :open="skillDrawerOpen" :title="skillDrawerData?.name || '技能详情'" :width="640" @update:open="skillDrawerOpen = $event">
            <vort-spin :spinning="skillDrawerLoading">
                <div v-if="skillDrawerData" class="space-y-4">
                    <vort-form label-width="80px">
                        <vort-form-item label="名称">
                            <vort-input v-model="skillDrawerData.name" :disabled="skillDrawerData.scope === 'builtin'" />
                        </vort-form-item>
                        <vort-form-item label="来源">
                            <vort-tag :color="sourceTagColor(skillDrawerData.scope === 'builtin' ? 'builtin' : skillDrawerData.scope === 'marketplace' ? 'marketplace' : 'custom')">
                                {{ sourceLabel(skillDrawerData.scope === 'public' ? 'custom' : skillDrawerData.scope) }}
                            </vort-tag>
                        </vort-form-item>
                        <vort-form-item label="标签">
                            <div class="space-y-2">
                                <div class="flex flex-wrap gap-1.5">
                                    <span v-for="tag in skillDrawerData.tags" :key="tag"
                                        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 text-xs">
                                        {{ tag }}
                                        <button v-if="skillDrawerData.scope !== 'builtin'"
                                            class="text-blue-400 hover:text-red-500" @click="removeSkillTag(tag)">
                                            <X :size="10" />
                                        </button>
                                    </span>
                                    <span v-if="!skillDrawerData.tags.length" class="text-xs text-gray-400">暂无标签</span>
                                </div>
                                <div v-if="skillDrawerData.scope !== 'builtin'" class="flex gap-2">
                                    <vort-input v-model="skillTagInput" class="flex-1" placeholder="输入标签名，回车添加" @press-enter="addSkillTag" />
                                    <vort-button size="small" @click="addSkillTag">添加</vort-button>
                                </div>
                            </div>
                        </vort-form-item>
                        <vort-form-item label="描述">
                            <vort-input v-model="skillDrawerData.description" :disabled="skillDrawerData.scope === 'builtin'" placeholder="Skill 描述" />
                        </vort-form-item>
                        <vort-form-item label="内容">
                            <vort-textarea v-model="skillDrawerData.content" :disabled="skillDrawerData.scope === 'builtin'"
                                placeholder="Markdown 格式的 Skill 内容" :rows="16"
                                style="font-family: monospace; font-size: 13px;" />
                        </vort-form-item>
                    </vort-form>
                </div>
            </vort-spin>
            <template #footer>
                <div class="flex items-center justify-between w-full">
                    <div>
                        <vort-button v-if="skillDrawerData?.scope === 'public'" danger @click="handleDeleteSkill">
                            <Trash2 :size="14" class="mr-1" /> 删除
                        </vort-button>
                    </div>
                    <div class="flex items-center gap-2">
                        <vort-button @click="skillDrawerOpen = false">关闭</vort-button>
                        <vort-button v-if="skillDrawerData?.scope !== 'builtin'" variant="primary" :loading="skillSaving" @click="handleSaveSkill">
                            <Save :size="14" class="mr-1" /> 保存
                        </vort-button>
                    </div>
                </div>
            </template>
        </vort-drawer>

        <!-- Plugin config drawer -->
        <vort-drawer :open="pluginDrawerOpen" title="插件配置" :width="480" @update:open="pluginDrawerOpen = $event">
            <vort-spin :spinning="pluginDrawerLoading">
                <vort-form v-if="configSchema.length" label-width="100px">
                    <vort-form-item v-for="field in configSchema" :key="field.key" :label="field.label" :required="field.required">
                        <vort-input-password v-if="field.secret" v-model="configForm[field.key]" :placeholder="field.placeholder" />
                        <vort-select v-else-if="field.type === 'select' && field.options" v-model="configForm[field.key]" :placeholder="field.placeholder">
                            <vort-select-option v-for="opt in field.options" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                        </vort-select>
                        <vort-input v-else v-model="configForm[field.key]" :placeholder="field.placeholder" />
                    </vort-form-item>
                </vort-form>
                <div v-else class="text-center py-8 text-gray-400 text-sm">该插件暂无可配置项</div>
            </vort-spin>
            <template #footer>
                <div class="flex justify-end gap-3">
                    <vort-button @click="pluginDrawerOpen = false">取消</vort-button>
                    <vort-button variant="primary" :loading="pluginSaving" @click="handleSavePlugin">保存</vort-button>
                </div>
            </template>
        </vort-drawer>

        <!-- Marketplace detail drawer -->
        <vort-drawer :open="mpDetailOpen" :title="mpDetail?.displayName || '扩展详情'" :width="720" @update:open="mpDetailOpen = $event">
            <vort-spin :spinning="mpDetailLoading">
                <div v-if="mpDetail" class="space-y-6">
                    <div class="flex items-start gap-4">
                        <div class="w-14 h-14 rounded-xl flex items-center justify-center shrink-0"
                            :class="mpDetail.type === 'plugin' ? 'bg-purple-50' : 'bg-blue-50'">
                            <component :is="mpDetail.type === 'plugin' ? Puzzle : BookOpen"
                                :size="28" :class="mpDetail.type === 'plugin' ? 'text-purple-500' : 'text-blue-500'" />
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2">
                                <h3 class="text-lg font-semibold text-gray-800">{{ mpDetail.displayName }}</h3>
                                <vort-tag :color="mpDetail.type === 'plugin' ? 'purple' : 'blue'" size="small" :bordered="false">
                                    {{ mpDetail.type === 'plugin' ? 'Plugin' : 'Skill' }}
                                </vort-tag>
                            </div>
                            <p class="text-sm text-gray-500 mt-1">{{ mpDetail.description }}</p>
                            <div class="flex flex-wrap items-center gap-2 mt-2">
                                <span class="text-xs text-gray-400">by <strong class="text-gray-600">{{ mpDetail.author || '?' }}</strong></span>
                                <vort-tag color="blue" size="small" :bordered="false">v{{ mpDetail.version }}</vort-tag>
                                <vort-tag v-if="mpDetail.license" color="green" size="small" :bordered="false">{{ mpDetail.license }}</vort-tag>
                                <vort-tag v-for="tag in (mpDetail.tags || [])" :key="tag" size="small" :bordered="false">{{ tag }}</vort-tag>
                            </div>
                        </div>
                    </div>

                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div class="bg-gray-50 rounded-lg p-3 text-center">
                            <div class="flex items-center justify-center gap-1 text-gray-400 mb-1"><Download :size="14" /><span class="text-xs">下载</span></div>
                            <div class="text-lg font-semibold text-gray-700">{{ mpDetail.downloads || 0 }}</div>
                        </div>
                        <div class="bg-gray-50 rounded-lg p-3 text-center">
                            <div class="flex items-center justify-center gap-1 text-gray-400 mb-1"><Star :size="14" /><span class="text-xs">收藏</span></div>
                            <div class="text-lg font-semibold text-gray-700">{{ mpDetail.stars || 0 }}</div>
                        </div>
                        <div class="bg-gray-50 rounded-lg p-3 text-center">
                            <div class="flex items-center justify-center gap-1 text-gray-400 mb-1"><Calendar :size="14" /><span class="text-xs">发布</span></div>
                            <div class="text-sm font-medium text-gray-700">{{ formatDate(mpDetail.createdAt) }}</div>
                        </div>
                        <div class="bg-gray-50 rounded-lg p-3 text-center">
                            <div class="flex items-center justify-center gap-1 text-gray-400 mb-1"><ArrowUpDown :size="14" /><span class="text-xs">更新</span></div>
                            <div class="text-sm font-medium text-gray-700">{{ formatDate(mpDetail.updatedAt) }}</div>
                        </div>
                    </div>

                    <div v-if="mpDetail.type === 'plugin'" class="bg-purple-50/50 border border-purple-100 rounded-lg p-4">
                        <h4 class="text-sm font-medium text-purple-700 mb-3">插件能力</h4>
                        <div class="grid grid-cols-2 gap-3 text-sm">
                            <div class="flex items-center justify-between">
                                <span class="text-gray-500">工具 (Tools)</span>
                                <vort-tag color="green" size="small" :bordered="false">{{ mpDetail.toolsCount || 0 }}</vort-tag>
                            </div>
                            <div class="flex items-center justify-between">
                                <span class="text-gray-500">Prompts</span>
                                <vort-tag color="orange" size="small" :bordered="false">{{ mpDetail.promptsCount || 0 }}</vort-tag>
                            </div>
                        </div>
                        <div v-if="mpDetail.dependencies?.length" class="mt-3 pt-3 border-t border-purple-100">
                            <p class="text-xs text-gray-500 mb-2">依赖:</p>
                            <div class="flex flex-wrap gap-1">
                                <vort-tag v-for="dep in mpDetail.dependencies" :key="dep" size="small" :bordered="false">{{ dep }}</vort-tag>
                            </div>
                        </div>
                    </div>

                    <div v-if="mpDetail.type === 'skill' && mpDetail.skillType" class="bg-blue-50/50 border border-blue-100 rounded-lg p-4">
                        <h4 class="text-sm font-medium text-blue-700 mb-2">Skill 信息</h4>
                        <div class="flex items-center justify-between text-sm">
                            <span class="text-gray-500">类型</span>
                            <vort-tag color="blue" size="small" :bordered="false">{{ skillTypeLabel[mpDetail.skillType] || mpDetail.skillType }}</vort-tag>
                        </div>
                    </div>

                    <div class="flex flex-wrap gap-2">
                        <a :href="`https://openvort.com/${mpDetail.author}/${mpDetail.slug}`" target="_blank"
                            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-50 text-sm text-gray-600 hover:bg-gray-100 transition-colors">
                            <ExternalLink :size="14" /> 主页
                        </a>
                        <a v-if="mpDetail.repository" :href="mpDetail.repository" target="_blank"
                            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-50 text-sm text-gray-600 hover:bg-gray-100 transition-colors">
                            <Github :size="14" /> 源代码
                        </a>
                    </div>

                    <div v-if="mpDetail.readme || (mpDetail.type === 'skill' && mpDetail.content)" class="border-t border-gray-100 pt-4">
                        <div class="flex gap-1 mb-4">
                            <button v-if="mpDetail.readme"
                                class="px-3 py-1.5 text-sm font-medium rounded-md transition-colors"
                                :class="mpDetailTab === 'readme' ? 'bg-blue-50 text-blue-600' : 'text-gray-500 hover:bg-gray-50'"
                                @click="mpDetailTab = 'readme'">README</button>
                            <button v-if="mpDetail.type === 'skill' && mpDetail.content"
                                class="px-3 py-1.5 text-sm font-medium rounded-md transition-colors"
                                :class="mpDetailTab === 'content' ? 'bg-blue-50 text-blue-600' : 'text-gray-500 hover:bg-gray-50'"
                                @click="mpDetailTab = 'content'">Skill 内容</button>
                        </div>
                        <div v-if="mpDetailTab === 'readme' && mpDetail.readme" class="bg-gray-50 rounded-lg p-5">
                            <MarkdownView :content="mpDetail.readme" />
                        </div>
                        <div v-if="mpDetailTab === 'content' && mpDetail.type === 'skill' && mpDetail.content" class="bg-gray-50 rounded-lg p-5">
                            <MarkdownView :content="mpDetail.content" />
                        </div>
                    </div>
                </div>
            </vort-spin>
            <template #footer>
                <div class="flex items-center justify-end gap-2">
                    <vort-button @click="mpDetailOpen = false">关闭</vort-button>
                    <template v-if="mpDetail">
                        <vort-button v-if="mpInstalled.has(mpDetail.slug)" danger @click="handleUninstall({ ...mpDetail, kind: mpDetail.type, displayName: mpDetail.displayName, name: mpDetail.name, slug: mpDetail.slug })">
                            <Trash2 :size="14" class="mr-1" /> 卸载
                        </vort-button>
                        <vort-button v-else variant="primary" :loading="mpInstallingSlug === mpDetail.slug" @click="handleInstall(mpDetail)">
                            <Download :size="14" class="mr-1" /> 安装
                        </vort-button>
                    </template>
                </div>
            </template>
        </vort-drawer>

        <!-- Create skill dialog -->
        <vort-dialog :open="createDialogOpen" title="新建技能" @update:open="createDialogOpen = $event">
            <vort-form label-width="80px">
                <vort-form-item label="名称" required>
                    <vort-input v-model="createForm.name" placeholder="如：代码审查规范" />
                </vort-form-item>
                <vort-form-item label="标签">
                    <div class="space-y-2">
                        <div v-if="createForm.tags.length" class="flex flex-wrap gap-1.5">
                            <span v-for="tag in createForm.tags" :key="tag"
                                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 text-xs">
                                {{ tag }}
                                <button class="text-blue-400 hover:text-red-500" @click="removeCreateTag(tag)"><X :size="10" /></button>
                            </span>
                        </div>
                        <div class="flex gap-2">
                            <vort-input v-model="createTagInput" class="flex-1" placeholder="输入标签名，回车添加" @press-enter="addCreateTag" />
                            <vort-button size="small" @click="addCreateTag">添加</vort-button>
                        </div>
                    </div>
                </vort-form-item>
                <vort-form-item label="描述">
                    <vort-input v-model="createForm.description" placeholder="Skill 用途描述" />
                </vort-form-item>
                <vort-form-item label="内容">
                    <div class="space-y-2">
                        <vort-textarea v-model="createForm.content" placeholder="Markdown 格式的 Skill 内容" :rows="8"
                            style="font-family: monospace; font-size: 13px;" />
                        <div class="flex justify-end">
                            <vort-button size="small" @click="handleAiGenerate">
                                <Bot :size="12" class="mr-1" /> AI 助手创建
                            </vort-button>
                        </div>
                    </div>
                </vort-form-item>
            </vort-form>
            <template #footer>
                <div class="flex justify-end gap-2">
                    <vort-button @click="createDialogOpen = false">取消</vort-button>
                    <vort-button variant="primary" :loading="creating" @click="handleCreate">创建</vort-button>
                </div>
            </template>
        </vort-dialog>
    </div>
</template>
