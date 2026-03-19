<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { getPlugins, getPluginDetail, updatePlugin, installPlugin, uninstallPlugin, pipInstallPlugin, uploadPlugin, deletePlugin } from "@/api";
import { Puzzle, Wrench, Plus, Upload, Trash2, ChevronDown, ChevronRight, Download } from "lucide-vue-next";
import { message } from "@/components/vort/message";
import { dialog } from "@/components/vort/dialog";
import { usePluginStore } from "@/stores/modules/plugin";

interface PluginTool {
    name: string;
    description: string;
}

interface ConfigField {
    key: string;
    label: string;
    type: string;
    required: boolean;
    secret: boolean;
    placeholder: string;
    options?: { value: string; label: string }[];
}

interface PluginInfo {
    name: string;
    display_name: string;
    description: string;
    version: string;
    source: string;
    core: boolean;
    status: string;
    enabled: boolean;
    installed: boolean;
    has_config: boolean;
    tools: PluginTool[];
}

const plugins = ref<PluginInfo[]>([]);
const loading = ref(false);

const activeTab = ref<"installed" | "available">("installed");
const searchQuery = ref("");
const filterSource = ref<"all" | "builtin" | "pip" | "local">("all");

const applyFilters = (list: PluginInfo[]) => {
    return list.filter((plugin) => {
        const query = searchQuery.value.toLowerCase().trim();
        if (query) {
            const matchName = plugin.name.toLowerCase().includes(query);
            const matchDisplay = plugin.display_name.toLowerCase().includes(query);
            const matchDesc = plugin.description?.toLowerCase().includes(query);
            const matchTool = plugin.tools.some(
                (t) => t.name.toLowerCase().includes(query) || t.description?.toLowerCase().includes(query)
            );
            if (!matchName && !matchDisplay && !matchDesc && !matchTool) {
                return false;
            }
        }
        if (filterSource.value !== "all" && plugin.source !== filterSource.value) {
            return false;
        }
        return true;
    });
};

const installedPlugins = computed(() => {
    const list = plugins.value.filter((p) => p.installed);
    return applyFilters(list).sort((a, b) => {
        if (a.core !== b.core) return a.core ? 1 : -1;
        return a.display_name.localeCompare(b.display_name);
    });
});

const availablePlugins = computed(() => {
    const list = plugins.value.filter((p) => !p.installed);
    return applyFilters(list).sort((a, b) => a.display_name.localeCompare(b.display_name));
});

// Config drawer
const drawerOpen = ref(false);
const drawerLoading = ref(false);
const saving = ref(false);
const currentPlugin = ref<string>("");
const configSchema = ref<ConfigField[]>([]);
const configForm = ref<Record<string, string>>({});

// Tool list collapse state
const expandedTools = ref<Record<string, boolean>>({});
const toggleTools = (pluginName: string) => {
    expandedTools.value[pluginName] = !expandedTools.value[pluginName];
};

const loadPlugins = async () => {
    loading.value = true;
    try {
        const res: any = await getPlugins();
        plugins.value = res?.plugins || [];
    } catch { /* ignore */ }
    finally { loading.value = false; }
};

const needRestart = ref(false);
const pluginStore = usePluginStore();

const handleInstall = async (plugin: PluginInfo) => {
    try {
        await installPlugin(plugin.name);
        plugin.installed = true;
        plugin.enabled = true;
        message.success(`已安装「${plugin.display_name}」`);
        pluginStore.fetchExtensions();
    } catch {
        message.error("安装失败");
    }
};

const handleUninstall = (plugin: PluginInfo) => {
    dialog.confirm({
        title: "确认卸载",
        content: `确定要卸载插件「${plugin.display_name}」吗？卸载后其工具将不再对 AI 可用，配置将被保留。`,
        onOk: async () => {
            try {
                await uninstallPlugin(plugin.name);
                plugin.installed = false;
                plugin.enabled = false;
                message.success(`已卸载「${plugin.display_name}」`);
                pluginStore.fetchExtensions();
            } catch {
                message.error("卸载失败");
            }
        },
    });
};

const openConfig = async (name: string) => {
    currentPlugin.value = name;
    drawerOpen.value = true;
    drawerLoading.value = true;
    try {
        const res: any = await getPluginDetail(name);
        configSchema.value = res?.config_schema || [];
        const config = res?.config || {};
        configForm.value = {};
        for (const field of configSchema.value) {
            configForm.value[field.key] = config[field.key] ?? "";
        }
    } catch {
        message.error("加载配置失败");
    } finally {
        drawerLoading.value = false;
    }
};

const handleSave = async () => {
    saving.value = true;
    try {
        await updatePlugin(currentPlugin.value, configForm.value);
        message.success("配置已保存");
        drawerOpen.value = false;
        loadPlugins();
    } catch {
        message.error("保存失败");
    } finally {
        saving.value = false;
    }
};

// Add plugin dialog (pip / upload)
const addDialogOpen = ref(false);
const installMode = ref<"pip" | "upload">("pip");
const packageName = ref("");
const installing = ref(false);

const handlePipInstall = async () => {
    if (!packageName.value.trim()) {
        message.error("请输入包名");
        return;
    }
    installing.value = true;
    try {
        const res: any = await pipInstallPlugin(packageName.value.trim());
        message.success(res.message || "安装成功，需重启服务生效");
        needRestart.value = true;
        addDialogOpen.value = false;
        packageName.value = "";
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "安装失败");
    } finally {
        installing.value = false;
    }
};

const handleUpload = async (file: File) => {
    installing.value = true;
    try {
        const res: any = await uploadPlugin(file);
        message.success(res.message || "上传成功，需重启服务生效");
        needRestart.value = true;
        addDialogOpen.value = false;
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "上传失败");
    } finally {
        installing.value = false;
    }
};

const onFileChange = (e: Event) => {
    const input = e.target as HTMLInputElement;
    if (input.files?.[0]) {
        handleUpload(input.files[0]);
    }
};

const handleDelete = (plugin: PluginInfo) => {
    dialog.confirm({
        title: "确认删除",
        content: `确定要删除插件「${plugin.display_name}」吗？此操作将删除插件文件和配置，重启后生效。`,
        onOk: async () => {
            try {
                await deletePlugin(plugin.name);
                message.success("已删除，需重启服务生效");
                needRestart.value = true;
                loadPlugins();
            } catch (e: any) {
                message.error(e?.response?.data?.detail || "删除失败");
            }
        },
    });
};

onMounted(loadPlugins);
</script>

<template>
    <div class="space-y-6">
        <div class="flex items-center justify-between">
            <h2 class="text-lg font-medium text-gray-800">插件中心</h2>
        </div>

        <!-- Search & filter -->
        <div class="flex flex-wrap items-center gap-3">
            <VortInputSearch
                v-model="searchQuery"
                placeholder="搜索插件名称、描述、工具..."
                allow-clear
                class="flex-1 min-w-[200px] max-w-md"
            />
            <VortSelect v-model="filterSource" class="w-28">
                <VortSelectOption value="all">全部来源</VortSelectOption>
                <VortSelectOption value="builtin">内置</VortSelectOption>
                <VortSelectOption value="pip">pip</VortSelectOption>
                <VortSelectOption value="local">本地</VortSelectOption>
            </VortSelect>
        </div>

        <VortAlert
            v-if="needRestart"
            type="warning"
            class="mb-4"
        >
            <template #message>
                <span>插件状态已变更，请重启 OpenVort 服务使更改生效：<code class="bg-amber-100 px-1.5 py-0.5 rounded text-xs font-mono">openvort start</code></span>
            </template>
        </VortAlert>

        <VortSpin :spinning="loading">
            <VortTabs v-model:activeKey="activeTab">
                <VortTabPane tab-key="installed" :tab="`已安装 (${installedPlugins.length})`">
                    <div v-if="installedPlugins.length === 0" class="text-center py-12 text-gray-400 text-sm">
                        暂无已安装的插件
                    </div>
                    <div v-else class="masonry-grid">
                        <vort-card v-for="plugin in installedPlugins" :key="plugin.name" class="masonry-item" :shadow="false" padding="small">
                            <div class="flex items-center justify-between mb-4">
                                <div class="flex items-center">
                                    <div class="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center mr-3">
                                        <Puzzle :size="20" class="text-blue-600" />
                                    </div>
                                    <div>
                                        <h3 class="text-sm font-medium text-gray-800 flex items-center gap-1">
                                            {{ plugin.display_name }}
                                            <VortTag v-if="plugin.core" color="volcano" size="small" :bordered="false">核心</VortTag>
                                            <VortTag v-else :color="{ builtin: 'blue', pip: 'cyan', local: 'purple' }[plugin.source] || 'default'" size="small" :bordered="false">
                                                {{ { builtin: '内置', pip: 'pip', local: '本地' }[plugin.source] || plugin.source }}
                                            </VortTag>
                                        </h3>
                                        <p class="text-xs text-gray-400">{{ plugin.name }} v{{ plugin.version }}</p>
                                    </div>
                                </div>
                                <div class="flex items-center gap-1">
                                    <VortButton v-if="plugin.has_config" size="small" @click="openConfig(plugin.name)">设置</VortButton>
                                    <VortTooltip v-if="plugin.core" title="核心插件不可禁用">
                                        <VortButton size="small" disabled>禁用</VortButton>
                                    </VortTooltip>
                                    <VortButton v-else size="small" @click="handleUninstall(plugin)">禁用</VortButton>
                                    <VortTooltip v-if="plugin.core" title="核心插件不可卸载">
                                        <VortButton size="small" disabled>卸载</VortButton>
                                    </VortTooltip>
                                    <VortButton v-else size="small" @click="handleUninstall(plugin)">卸载</VortButton>
                                </div>
                            </div>

                            <p v-if="plugin.description" class="text-xs text-gray-500 mb-3">{{ plugin.description }}</p>

                            <div v-if="plugin.tools.length" class="mt-3 pt-3 border-t border-gray-100">
                                <button
                                    class="flex items-center gap-1 text-xs text-gray-500 font-medium hover:text-blue-600 transition-colors"
                                    @click="toggleTools(plugin.name)"
                                >
                                    <component :is="expandedTools[plugin.name] ? ChevronDown : ChevronRight" :size="12" />
                                    工具列表 ({{ plugin.tools.length }})
                                </button>
                                <div v-show="expandedTools[plugin.name]" class="mt-2 space-y-2">
                                    <div v-for="tool in plugin.tools" :key="tool.name"
                                        class="flex items-start gap-2 p-2 rounded bg-gray-50 text-xs">
                                        <Wrench :size="12" class="text-gray-400 mt-0.5 flex-shrink-0" />
                                        <div>
                                            <span class="font-medium text-gray-700">{{ tool.name }}</span>
                                            <p class="text-gray-400 mt-0.5">{{ tool.description }}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </vort-card>
                    </div>
                </VortTabPane>

                <VortTabPane tab-key="available" :tab="`未安装 (${availablePlugins.length})`">
                    <div class="masonry-grid">
                        <vort-card v-for="plugin in availablePlugins" :key="plugin.name" class="masonry-item" :shadow="false" padding="small">
                            <div class="flex items-center justify-between mb-4">
                                <div class="flex items-center">
                                    <div class="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center mr-3">
                                        <Puzzle :size="20" class="text-gray-400" />
                                    </div>
                                    <div>
                                        <h3 class="text-sm font-medium text-gray-800 flex items-center gap-1">
                                            {{ plugin.display_name }}
                                            <VortTag :color="{ builtin: 'blue', pip: 'cyan', local: 'purple' }[plugin.source] || 'default'" size="small" :bordered="false">
                                                {{ { builtin: '内置', pip: 'pip', local: '本地' }[plugin.source] || plugin.source }}
                                            </VortTag>
                                        </h3>
                                        <p class="text-xs text-gray-400">{{ plugin.name }} v{{ plugin.version }}</p>
                                    </div>
                                </div>
                                <div class="flex items-center gap-2">
                                    <VortButton size="small" variant="primary" @click="handleInstall(plugin)">
                                        <Download :size="14" class="mr-1" /> 安装
                                    </VortButton>
                                </div>
                            </div>

                            <p v-if="plugin.description" class="text-xs text-gray-500 mb-3">{{ plugin.description }}</p>

                            <div v-if="plugin.tools.length" class="mt-3 pt-3 border-t border-gray-100">
                                <button
                                    class="flex items-center gap-1 text-xs text-gray-500 font-medium hover:text-blue-600 transition-colors"
                                    @click="toggleTools(plugin.name)"
                                >
                                    <component :is="expandedTools[plugin.name] ? ChevronDown : ChevronRight" :size="12" />
                                    工具列表 ({{ plugin.tools.length }})
                                </button>
                                <div v-show="expandedTools[plugin.name]" class="mt-2 space-y-2">
                                    <div v-for="tool in plugin.tools" :key="tool.name"
                                        class="flex items-start gap-2 p-2 rounded bg-gray-50 text-xs">
                                        <Wrench :size="12" class="text-gray-400 mt-0.5 flex-shrink-0" />
                                        <div>
                                            <span class="font-medium text-gray-700">{{ tool.name }}</span>
                                            <p class="text-gray-400 mt-0.5">{{ tool.description }}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div v-if="plugin.source === 'local'" class="mt-4 pt-3 border-t border-gray-100 flex justify-end">
                                <VortButton size="small" variant="text" danger @click="handleDelete(plugin)">
                                    <Trash2 :size="14" class="mr-1" /> 删除
                                </VortButton>
                            </div>
                        </vort-card>

                        <!-- Add third-party plugin card -->
                        <div
                            class="masonry-item bg-white rounded-xl border-2 border-dashed border-gray-200 flex items-center justify-center cursor-pointer hover:border-blue-400 transition-colors min-h-[120px]"
                            @click="addDialogOpen = true"
                        >
                            <div class="text-center text-gray-400">
                                <Plus :size="24" class="mx-auto mb-1" />
                                <span class="text-sm">添加第三方插件</span>
                            </div>
                        </div>
                    </div>
                </VortTabPane>
            </VortTabs>
        </VortSpin>

        <!-- Config drawer -->
        <VortDrawer :open="drawerOpen" title="插件配置" :width="480" @update:open="drawerOpen = $event">
            <VortSpin :spinning="drawerLoading">
                <VortForm v-if="configSchema.length" label-width="100px">
                    <VortFormItem
                        v-for="field in configSchema"
                        :key="field.key"
                        :label="field.label"
                        :required="field.required"
                    >
                        <VortInputPassword
                            v-if="field.secret"
                            v-model="configForm[field.key]"
                            :placeholder="field.placeholder"
                        />
                        <VortSelect
                            v-else-if="field.type === 'select' && field.options"
                            v-model="configForm[field.key]"
                            :placeholder="field.placeholder"
                        >
                            <VortSelectOption v-for="opt in field.options" :key="opt.value" :value="opt.value">{{ opt.label }}</VortSelectOption>
                        </VortSelect>
                        <VortInput
                            v-else
                            v-model="configForm[field.key]"
                            :placeholder="field.placeholder"
                        />
                    </VortFormItem>
                </VortForm>
                <div v-else class="text-center py-8 text-gray-400 text-sm">该插件暂无可配置项</div>
            </VortSpin>
            <template #footer>
                <div class="flex justify-end gap-2">
                    <VortButton @click="drawerOpen = false">取消</VortButton>
                    <VortButton variant="primary" :loading="saving" @click="handleSave">保存</VortButton>
                </div>
            </template>
        </VortDrawer>

        <!-- Add plugin dialog -->
        <VortDialog :open="addDialogOpen" title="添加第三方插件" @update:open="addDialogOpen = $event">
            <div class="space-y-4">
                <VortRadioGroup v-model="installMode">
                    <VortRadioButton value="pip">pip 安装</VortRadioButton>
                    <VortRadioButton value="upload">上传 zip</VortRadioButton>
                </VortRadioGroup>

                <div v-if="installMode === 'pip'">
                    <p class="text-xs text-gray-400 mb-2">输入 PyPI 包名，如 openvort-plugin-gitlab</p>
                    <VortInput v-model="packageName" placeholder="包名" @keyup.enter="handlePipInstall" />
                </div>

                <div v-else>
                    <p class="text-xs text-gray-400 mb-2">上传包含 plugin.py 的 zip 文件（最大 10MB）</p>
                    <label class="flex items-center justify-center w-full h-24 border-2 border-dashed border-gray-200 rounded-lg cursor-pointer hover:border-blue-400 transition-colors">
                        <div class="text-center">
                            <Upload :size="20" class="mx-auto text-gray-400 mb-1" />
                            <span class="text-xs text-gray-400">点击选择 .zip 文件</span>
                        </div>
                        <input type="file" accept=".zip" class="hidden" @change="onFileChange" />
                    </label>
                </div>
            </div>

            <template #footer>
                <div class="flex justify-end gap-2">
                    <VortButton @click="addDialogOpen = false">取消</VortButton>
                    <VortButton
                        v-if="installMode === 'pip'"
                        variant="primary"
                        :loading="installing"
                        @click="handlePipInstall"
                    >安装</VortButton>
                </div>
            </template>
        </VortDialog>
    </div>
</template>

<style scoped>
.masonry-grid {
    column-count: 1;
    column-gap: 16px;
}
.masonry-item {
    break-inside: avoid;
    margin-bottom: 16px;
}
@media (min-width: 640px) {
    .masonry-grid {
        column-count: 2;
    }
}
@media (min-width: 1280px) {
    .masonry-grid {
        column-count: 3;
    }
}
</style>
