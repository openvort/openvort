<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import {
    marketplaceSearch, marketplaceGetDetail,
    marketplaceInstallSkill, marketplaceInstallPlugin,
    marketplaceListInstalled, marketplaceUninstall,
} from "@/api";
import { message } from "@/components/vort/message";
import { dialog } from "@/components/vort/dialog";
import { usePluginStore } from "@/stores/modules/plugin";
import {
    Puzzle, BookOpen, Download, Star, Calendar,
    ArrowUpDown, ExternalLink, Github, Wrench, Package, Trash2,
} from "lucide-vue-next";
import MarkdownView from "@/components/vort-biz/editor/MarkdownView.vue";

interface MarketplaceItem {
    id: string;
    type: string;
    slug: string;
    name: string;
    displayName: string;
    description: string;
    version: string;
    author: string;
    authorAvatar: string;
    icon: string;
    category: string;
    tags: string[];
    license: string;
    downloads: number;
    stars: number;
    toolsCount?: number;
    promptsCount?: number;
}

interface InstalledItem {
    id?: string;
    name: string;
    description?: string;
    slug: string;
    author?: string;
    version?: string;
    skill_type?: string;
    enabled?: boolean;
    type: string;
    method?: string;
}

interface ExtensionDetail extends MarketplaceItem {
    readme: string;
    content: string;
    skillType: string;
    packageName: string;
    entryPoint: string;
    pythonRequires: string;
    dependencies: string[];
    hasUiExtensions: boolean;
    configSchema: object[];
    compatVersion: string;
    homepage: string;
    repository: string;
    bundleUrl: string;
    bundleHash: string;
    bundleSize: number;
    createdAt: string;
    updatedAt: string;
}

const router = useRouter();
const pluginStore = usePluginStore();

const viewMode = ref<"browse" | "installed">("installed");

// Browse state
const items = ref<MarketplaceItem[]>([]);
const loading = ref(false);
const searchQuery = ref("");
const typeFilter = ref<"all" | "skill" | "plugin">("all");
const sortBy = ref("downloads");
const page = ref(1);
const total = ref(0);
const pageSize = 12;
const installedSlugs = ref<Set<string>>(new Set());
const installingSlug = ref("");
const uninstallingSlug = ref("");

const totalPages = computed(() => Math.ceil(total.value / pageSize));

// Installed list state
const installedItems = ref<InstalledItem[]>([]);
const installedLoading = ref(false);
const installedTypeFilter = ref<"all" | "skill" | "plugin">("all");

const filteredInstalled = computed(() => {
    if (installedTypeFilter.value === "all") return installedItems.value;
    return installedItems.value.filter(i => i.type === installedTypeFilter.value);
});

async function loadInstalled() {
    installedLoading.value = true;
    try {
        const res: any = await marketplaceListInstalled();
        const list = res || [];
        installedItems.value = list;
        installedSlugs.value = new Set(list.map((i: any) => i.slug));
    } catch { /* ignore */ }
    finally { installedLoading.value = false; }
}

async function loadBrowse() {
    loading.value = true;
    try {
        const res: any = await marketplaceSearch({
            query: searchQuery.value,
            type: typeFilter.value === "all" ? undefined : typeFilter.value,
            sort: sortBy.value,
            page: page.value,
            limit: pageSize,
        });
        items.value = res?.items || [];
        total.value = res?.total || 0;
    } catch { /* ignore */ }
    finally { loading.value = false; }
}

async function loadAll() {
    await loadInstalled();
    if (viewMode.value === "browse") {
        await loadBrowse();
    }
}

async function handleInstall(item: MarketplaceItem | ExtensionDetail) {
    installingSlug.value = item.slug;
    try {
        if (item.type === "plugin") {
            await marketplaceInstallPlugin(item.slug, item.author);
            message.success(`插件「${item.displayName}」安装成功，需重启服务生效。可前往「Plugins 插件」页面管理。`);
        } else {
            await marketplaceInstallSkill(item.slug, item.author);
            message.success(`Skill「${item.displayName}」安装成功，已即时生效。可前往「Skills 技能」页面管理。`);
        }
        await loadInstalled();
        pluginStore.fetchExtensions();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "安装失败");
    } finally {
        installingSlug.value = "";
    }
}

function handleUninstall(item: InstalledItem | MarketplaceItem) {
    const name = (item as any).displayName || item.name;
    const isPlugin = item.type === "plugin";
    dialog.confirm({
        title: "确认卸载",
        content: `确定卸载「${name}」吗？${isPlugin ? "卸载后需重启服务生效。" : "卸载后立即生效。"}`,
        onOk: async () => {
            uninstallingSlug.value = item.slug;
            try {
                await marketplaceUninstall(item.slug, item.type);
                message.success(isPlugin ? `已卸载「${name}」，需重启服务生效` : `已卸载「${name}」`);
                await loadInstalled();
                pluginStore.fetchExtensions();
            } catch (e: any) {
                message.error(e?.response?.data?.detail || "卸载失败");
            } finally {
                uninstallingSlug.value = "";
            }
        },
    });
}

function goToManage(type: string) {
    router.push(type === "plugin" ? "/plugins" : "/skills");
}

watch([searchQuery, typeFilter, sortBy], () => {
    page.value = 1;
    loadBrowse();
});

watch(viewMode, (mode) => {
    if (mode === "installed") loadInstalled();
    else loadBrowse();
});

onMounted(loadAll);

// Detail drawer
const drawerOpen = ref(false);
const drawerLoading = ref(false);
const detail = ref<ExtensionDetail | null>(null);
const detailTab = ref("readme");

async function openDetail(item: MarketplaceItem | InstalledItem) {
    drawerOpen.value = true;
    drawerLoading.value = true;
    detailTab.value = "readme";
    detail.value = null;
    try {
        const res: any = await marketplaceGetDetail(item.slug, (item as any).author || "");
        detail.value = res;
        detailTab.value = res?.readme ? "readme" : (res?.type === "skill" && res?.content ? "content" : "readme");
    } catch {
        message.error("加载详情失败");
    } finally {
        drawerLoading.value = false;
    }
}

function formatDate(date: string) {
    if (!date) return "-";
    return new Date(date).toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric" });
}

const skillTypeLabel: Record<string, string> = { role: "角色入设", workflow: "工作流程", knowledge: "知识库" };
</script>

<template>
    <div class="space-y-6">
        <!-- Header -->
        <div>
            <h2 class="text-lg font-medium text-gray-800">扩展市场</h2>
            <p class="text-sm text-gray-400 mt-1">发现并安装社区 Skills 与插件，扩展 OpenVort 的能力</p>
        </div>

        <!-- View mode tabs -->
        <VortTabs v-model:activeKey="viewMode">
            <VortTabPane tab-key="installed" :tab="`已安装 (${installedItems.length})`" />
            <VortTabPane tab-key="browse" tab="浏览市场" />
        </VortTabs>

        <!-- ====== Browse Mode ====== -->
        <template v-if="viewMode === 'browse'">
            <div class="flex flex-wrap items-center gap-3">
                <VortInputSearch
                    v-model="searchQuery"
                    placeholder="搜索扩展..."
                    allow-clear
                    class="flex-1 min-w-[200px] max-w-md"
                />

                <div class="flex bg-gray-100 rounded-lg p-0.5">
                    <button
                        v-for="opt in ([
                            { value: 'all', label: '全部' },
                            { value: 'skill', label: 'Skills' },
                            { value: 'plugin', label: '插件' },
                        ] as const)"
                        :key="opt.value"
                        class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors"
                        :class="typeFilter === opt.value
                            ? 'bg-white text-gray-800 shadow-sm'
                            : 'text-gray-500 hover:text-gray-700'"
                        @click="typeFilter = opt.value"
                    >{{ opt.label }}</button>
                </div>

                <VortSelect v-model="sortBy" class="w-32">
                    <VortSelectOption value="downloads">推荐</VortSelectOption>
                    <VortSelectOption value="latest">最新发布</VortSelectOption>
                    <VortSelectOption value="stars">最多收藏</VortSelectOption>
                </VortSelect>
            </div>

            <div v-if="!loading && total > 0" class="text-xs text-gray-400">
                共 {{ total }} 个扩展
            </div>

            <VortSpin :spinning="loading">
                <div v-if="items.length === 0 && !loading" class="text-center py-16 text-gray-400">
                    <Package :size="48" class="mx-auto mb-3 opacity-30" />
                    <p class="text-sm">暂无扩展，或市场不可达</p>
                </div>

                <div v-else class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                    <div
                        v-for="item in items"
                        :key="item.id"
                        class="bg-white rounded-xl border border-gray-100 p-4 hover:border-blue-300 hover:shadow-sm transition-all cursor-pointer"
                        @click="openDetail(item)"
                    >
                        <div class="flex items-start gap-3 mb-3">
                            <div
                                class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                                :class="item.type === 'plugin' ? 'bg-purple-50' : 'bg-blue-50'"
                            >
                                <component
                                    :is="item.type === 'plugin' ? Puzzle : BookOpen"
                                    :size="20"
                                    :class="item.type === 'plugin' ? 'text-purple-500' : 'text-blue-500'"
                                />
                            </div>
                            <div class="min-w-0 flex-1">
                                <div class="flex items-center gap-1.5">
                                    <h3 class="text-sm font-medium text-gray-800 truncate">{{ item.displayName }}</h3>
                                    <VortTag
                                        :color="item.type === 'plugin' ? 'purple' : 'blue'"
                                        size="small"
                                        :bordered="false"
                                    >{{ item.type === 'plugin' ? 'Plugin' : 'Skill' }}</VortTag>
                                </div>
                                <p class="text-xs text-gray-400 truncate">by {{ item.author || '?' }} · v{{ item.version || '1.0.0' }}</p>
                            </div>
                            <div class="flex items-center gap-1 flex-shrink-0" @click.stop>
                                <VortButton
                                    v-if="installedSlugs.has(item.slug)"
                                    size="small"
                                    danger
                                    :loading="uninstallingSlug === item.slug"
                                    @click="handleUninstall(item)"
                                >卸载</VortButton>
                                <VortButton
                                    v-else
                                    size="small"
                                    variant="primary"
                                    :loading="installingSlug === item.slug"
                                    @click="handleInstall(item)"
                                >
                                    <Download :size="14" class="mr-1" /> 安装
                                </VortButton>
                            </div>
                        </div>

                        <p class="text-xs text-gray-500 mb-3 line-clamp-2">{{ item.description || '暂无描述' }}</p>

                        <div v-if="item.tags?.length" class="flex flex-wrap gap-1 mb-3">
                            <span
                                v-for="tag in (item.tags || []).slice(0, 3)"
                                :key="tag"
                                class="px-1.5 py-0.5 rounded text-[10px] bg-gray-100 text-gray-500"
                            >{{ tag }}</span>
                            <span v-if="item.tags.length > 3" class="px-1.5 py-0.5 rounded text-[10px] bg-gray-100 text-gray-400">
                                +{{ item.tags.length - 3 }}
                            </span>
                        </div>

                        <div class="flex items-center gap-3 text-xs text-gray-400 pt-2 border-t border-gray-50">
                            <span class="flex items-center gap-0.5">
                                <Download :size="12" /> {{ item.downloads || 0 }}
                            </span>
                            <span class="flex items-center gap-0.5">
                                <Star :size="12" /> {{ item.stars || 0 }}
                            </span>
                            <span v-if="item.type === 'plugin' && item.toolsCount" class="flex items-center gap-0.5">
                                <Wrench :size="12" /> {{ item.toolsCount }} Tools
                            </span>
                        </div>
                    </div>
                </div>
            </VortSpin>

            <div v-if="totalPages > 1" class="flex items-center justify-center gap-3 pt-2">
                <VortButton size="small" :disabled="page <= 1" @click="page--; loadBrowse()">上一页</VortButton>
                <span class="text-sm text-gray-500">{{ page }} / {{ totalPages }}</span>
                <VortButton size="small" :disabled="page >= totalPages" @click="page++; loadBrowse()">下一页</VortButton>
            </div>
        </template>

        <!-- ====== Installed Mode ====== -->
        <template v-if="viewMode === 'installed'">
            <div class="flex items-center gap-3">
                <div class="flex bg-gray-100 rounded-lg p-0.5">
                    <button
                        v-for="opt in ([
                            { value: 'all', label: '全部' },
                            { value: 'skill', label: 'Skills' },
                            { value: 'plugin', label: '插件' },
                        ] as const)"
                        :key="opt.value"
                        class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors"
                        :class="installedTypeFilter === opt.value
                            ? 'bg-white text-gray-800 shadow-sm'
                            : 'text-gray-500 hover:text-gray-700'"
                        @click="installedTypeFilter = opt.value"
                    >{{ opt.label }}</button>
                </div>
            </div>

            <VortSpin :spinning="installedLoading">
                <div v-if="filteredInstalled.length === 0 && !installedLoading" class="text-center py-16 text-gray-400">
                    <Package :size="48" class="mx-auto mb-3 opacity-30" />
                    <p class="text-sm">暂无已安装的市场扩展</p>
                    <VortButton variant="primary" size="small" class="mt-4" @click="viewMode = 'browse'">去浏览市场</VortButton>
                </div>

                <div v-else class="space-y-3">
                    <div
                        v-for="item in filteredInstalled"
                        :key="item.slug"
                        class="bg-white rounded-xl border border-gray-100 p-4 hover:border-blue-300 hover:shadow-sm transition-all cursor-pointer"
                        @click="openDetail(item)"
                    >
                        <div class="flex items-center gap-4">
                            <div
                                class="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                                :class="item.type === 'plugin' ? 'bg-purple-50' : 'bg-blue-50'"
                            >
                                <component
                                    :is="item.type === 'plugin' ? Puzzle : BookOpen"
                                    :size="20"
                                    :class="item.type === 'plugin' ? 'text-purple-500' : 'text-blue-500'"
                                />
                            </div>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2">
                                    <h3 class="text-sm font-medium text-gray-800 truncate">{{ item.name }}</h3>
                                    <VortTag
                                        :color="item.type === 'plugin' ? 'purple' : 'blue'"
                                        size="small"
                                        :bordered="false"
                                    >{{ item.type === 'plugin' ? 'Plugin' : 'Skill' }}</VortTag>
                                    <VortTag v-if="item.version" color="default" size="small" :bordered="false">v{{ item.version }}</VortTag>
                                </div>
                                <p class="text-xs text-gray-400 mt-0.5">
                                    <span v-if="item.author">by {{ item.author }}</span>
                                    <span v-if="item.description"> · {{ item.description }}</span>
                                </p>
                            </div>
                            <div class="flex items-center gap-2 flex-shrink-0" @click.stop>
                                <VortButton
                                    size="small"
                                    @click="goToManage(item.type)"
                                >管理</VortButton>
                                <VortButton
                                    size="small"
                                    danger
                                    :loading="uninstallingSlug === item.slug"
                                    @click="handleUninstall(item)"
                                >
                                    <Trash2 :size="14" class="mr-1" /> 卸载
                                </VortButton>
                            </div>
                        </div>
                    </div>
                </div>
            </VortSpin>
        </template>

        <!-- ====== Detail Drawer ====== -->
        <VortDrawer :open="drawerOpen" :title="detail?.displayName || '扩展详情'" :width="720" @update:open="drawerOpen = $event">
            <VortSpin :spinning="drawerLoading">
                <div v-if="detail" class="space-y-6">
                    <div class="flex items-start gap-4">
                        <div
                            class="w-14 h-14 rounded-xl flex items-center justify-center flex-shrink-0"
                            :class="detail.type === 'plugin' ? 'bg-purple-50' : 'bg-blue-50'"
                        >
                            <component
                                :is="detail.type === 'plugin' ? Puzzle : BookOpen"
                                :size="28"
                                :class="detail.type === 'plugin' ? 'text-purple-500' : 'text-blue-500'"
                            />
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2">
                                <h3 class="text-lg font-semibold text-gray-800">{{ detail.displayName }}</h3>
                                <VortTag
                                    :color="detail.type === 'plugin' ? 'purple' : 'blue'"
                                    size="small"
                                    :bordered="false"
                                >{{ detail.type === 'plugin' ? 'Plugin' : 'Skill' }}</VortTag>
                            </div>
                            <p class="text-sm text-gray-500 mt-1">{{ detail.description }}</p>
                            <div class="flex flex-wrap items-center gap-2 mt-2">
                                <span class="text-xs text-gray-400">by <strong class="text-gray-600">{{ detail.author || '?' }}</strong></span>
                                <VortTag color="blue" size="small" :bordered="false">v{{ detail.version }}</VortTag>
                                <VortTag v-if="detail.license" color="green" size="small" :bordered="false">{{ detail.license }}</VortTag>
                                <VortTag
                                    v-for="tag in (detail.tags || [])"
                                    :key="tag"
                                    color="default"
                                    size="small"
                                    :bordered="false"
                                >{{ tag }}</VortTag>
                            </div>
                        </div>
                    </div>

                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div class="bg-gray-50 rounded-lg p-3 text-center">
                            <div class="flex items-center justify-center gap-1 text-gray-400 mb-1">
                                <Download :size="14" />
                                <span class="text-xs">下载</span>
                            </div>
                            <div class="text-lg font-semibold text-gray-700">{{ detail.downloads || 0 }}</div>
                        </div>
                        <div class="bg-gray-50 rounded-lg p-3 text-center">
                            <div class="flex items-center justify-center gap-1 text-gray-400 mb-1">
                                <Star :size="14" />
                                <span class="text-xs">收藏</span>
                            </div>
                            <div class="text-lg font-semibold text-gray-700">{{ detail.stars || 0 }}</div>
                        </div>
                        <div class="bg-gray-50 rounded-lg p-3 text-center">
                            <div class="flex items-center justify-center gap-1 text-gray-400 mb-1">
                                <Calendar :size="14" />
                                <span class="text-xs">发布</span>
                            </div>
                            <div class="text-sm font-medium text-gray-700">{{ formatDate(detail.createdAt) }}</div>
                        </div>
                        <div class="bg-gray-50 rounded-lg p-3 text-center">
                            <div class="flex items-center justify-center gap-1 text-gray-400 mb-1">
                                <ArrowUpDown :size="14" />
                                <span class="text-xs">更新</span>
                            </div>
                            <div class="text-sm font-medium text-gray-700">{{ formatDate(detail.updatedAt) }}</div>
                        </div>
                    </div>

                    <div v-if="detail.type === 'plugin'" class="bg-purple-50/50 border border-purple-100 rounded-lg p-4">
                        <h4 class="text-sm font-medium text-purple-700 mb-3">插件能力</h4>
                        <div class="grid grid-cols-2 gap-3 text-sm">
                            <div class="flex items-center justify-between">
                                <span class="text-gray-500">工具 (Tools)</span>
                                <VortTag color="green" size="small" :bordered="false">{{ detail.toolsCount || 0 }}</VortTag>
                            </div>
                            <div class="flex items-center justify-between">
                                <span class="text-gray-500">Prompts</span>
                                <VortTag color="orange" size="small" :bordered="false">{{ detail.promptsCount || 0 }}</VortTag>
                            </div>
                            <div v-if="detail.hasUiExtensions" class="flex items-center justify-between">
                                <span class="text-gray-500">UI 扩展</span>
                                <VortTag color="blue" size="small" :bordered="false">有</VortTag>
                            </div>
                            <div v-if="detail.pythonRequires" class="flex items-center justify-between">
                                <span class="text-gray-500">Python</span>
                                <span class="text-xs font-medium text-gray-600">{{ detail.pythonRequires }}</span>
                            </div>
                        </div>
                        <div v-if="(detail.dependencies as string[])?.length" class="mt-3 pt-3 border-t border-purple-100">
                            <p class="text-xs text-gray-500 mb-2">依赖:</p>
                            <div class="flex flex-wrap gap-1">
                                <VortTag
                                    v-for="dep in (detail.dependencies as string[])"
                                    :key="dep"
                                    size="small"
                                    :bordered="false"
                                >{{ dep }}</VortTag>
                            </div>
                        </div>
                    </div>

                    <div v-if="detail.type === 'skill' && detail.skillType" class="bg-blue-50/50 border border-blue-100 rounded-lg p-4">
                        <h4 class="text-sm font-medium text-blue-700 mb-2">Skill 信息</h4>
                        <div class="flex items-center justify-between text-sm">
                            <span class="text-gray-500">类型</span>
                            <VortTag color="blue" size="small" :bordered="false">{{ skillTypeLabel[detail.skillType] || detail.skillType }}</VortTag>
                        </div>
                    </div>

                    <div v-if="detail.homepage || detail.repository" class="flex flex-wrap gap-2">
                        <a
                            v-if="detail.homepage"
                            :href="detail.homepage"
                            target="_blank"
                            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-50 text-sm text-gray-600 hover:bg-gray-100 transition-colors"
                        >
                            <ExternalLink :size="14" /> 主页
                        </a>
                        <a
                            v-if="detail.repository"
                            :href="detail.repository"
                            target="_blank"
                            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-50 text-sm text-gray-600 hover:bg-gray-100 transition-colors"
                        >
                            <Github :size="14" /> 源代码
                        </a>
                    </div>

                    <div v-if="detail.compatVersion" class="text-xs text-gray-400">
                        兼容 OpenVort {{ detail.compatVersion }}
                    </div>

                    <div v-if="detail.readme || (detail.type === 'skill' && detail.content)" class="border-t border-gray-100 pt-4">
                        <div class="flex gap-1 mb-4">
                            <button
                                v-if="detail.readme"
                                class="px-3 py-1.5 text-sm font-medium rounded-md transition-colors"
                                :class="detailTab === 'readme'
                                    ? 'bg-blue-50 text-blue-600'
                                    : 'text-gray-500 hover:bg-gray-50'"
                                @click="detailTab = 'readme'"
                            >README</button>
                            <button
                                v-if="detail.type === 'skill' && detail.content"
                                class="px-3 py-1.5 text-sm font-medium rounded-md transition-colors"
                                :class="detailTab === 'content'
                                    ? 'bg-blue-50 text-blue-600'
                                    : 'text-gray-500 hover:bg-gray-50'"
                                @click="detailTab = 'content'"
                            >Skill 内容</button>
                        </div>

                        <div v-if="detailTab === 'readme' && detail.readme">
                            <div class="bg-gray-50 rounded-lg p-5">
                                <MarkdownView :content="detail.readme" />
                            </div>
                        </div>

                        <div v-if="detailTab === 'content' && detail.type === 'skill' && detail.content">
                            <div class="bg-gray-50 rounded-lg p-5">
                                <MarkdownView :content="detail.content" />
                            </div>
                        </div>
                    </div>
                </div>
            </VortSpin>

            <template #footer>
                <div class="flex items-center justify-between w-full">
                    <div class="text-xs text-gray-400">
                        <span v-if="detail?.category">{{ detail.category }}</span>
                    </div>
                    <div class="flex items-center gap-2">
                        <VortButton @click="drawerOpen = false">关闭</VortButton>
                        <template v-if="detail">
                            <template v-if="installedSlugs.has(detail.slug)">
                                <VortButton size="small" @click="goToManage(detail.type)">
                                    前往管理
                                </VortButton>
                                <VortButton
                                    danger
                                    :loading="uninstallingSlug === detail.slug"
                                    @click="handleUninstall(detail)"
                                >
                                    <Trash2 :size="14" class="mr-1" /> 卸载
                                </VortButton>
                            </template>
                            <VortButton
                                v-else
                                variant="primary"
                                :loading="installingSlug === detail.slug"
                                @click="handleInstall(detail)"
                            >
                                <Download :size="14" class="mr-1" /> 安装
                            </VortButton>
                        </template>
                    </div>
                </div>
            </template>
        </VortDrawer>
    </div>
</template>
