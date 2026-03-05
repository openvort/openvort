<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { getPlugins, getPluginDetail, updatePlugin, togglePlugin, installPlugin, uploadPlugin, deletePlugin } from "@/api";
import { Puzzle, Wrench, CheckCircle, XCircle, Settings, Plus, Upload, Trash2, Search, ChevronDown, ChevronRight } from "lucide-vue-next";
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
    has_config: boolean;
    tools: PluginTool[];
}

const plugins = ref<PluginInfo[]>([]);
const loading = ref(false);

// 搜索和筛选
const searchQuery = ref("");
const filterSource = ref<"all" | "builtin" | "pip" | "local">("all");
const filterStatus = ref<"all" | "enabled" | "disabled">("all");

// 筛选后的插件列表
const filteredPlugins = computed(() => {
    return plugins.value.filter((plugin) => {
        // 搜索过滤
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
        // 来源筛选
        if (filterSource.value !== "all" && plugin.source !== filterSource.value) {
            return false;
        }
        // 状态筛选
        if (filterStatus.value === "enabled" && !plugin.enabled) {
            return false;
        }
        if (filterStatus.value === "disabled" && plugin.enabled) {
            return false;
        }
        return true;
    });
});

// 配置抽屉
const drawerOpen = ref(false);
const drawerLoading = ref(false);
const saving = ref(false);
const currentPlugin = ref<string>("");
const configSchema = ref<ConfigField[]>([]);
const configForm = ref<Record<string, string>>({});

// 工具列表折叠状态
const collapsedTools = ref<Record<string, boolean>>({});
const toggleTools = (pluginName: string) => {
    collapsedTools.value[pluginName] = !collapsedTools.value[pluginName];
};

// 加载插件列表
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

const handleToggle = async (plugin: PluginInfo) => {
    try {
        const res: any = await togglePlugin(plugin.name);
        plugin.enabled = res.enabled;
        message.success(res.enabled ? "已启用" : "已禁用");
        pluginStore.fetchExtensions();
    } catch {
        message.error("操作失败");
    }
};

// 打开配置抽屉
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

// 保存配置
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

// 添加插件弹窗
const addDialogOpen = ref(false);
const installMode = ref<"pip" | "upload">("pip");
const packageName = ref("");
const installing = ref(false);

const handleInstall = async () => {
    if (!packageName.value.trim()) {
        message.error("请输入包名");
        return;
    }
    installing.value = true;
    try {
        const res: any = await installPlugin(packageName.value.trim());
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

// 删除本地插件
const handleDelete = (plugin: PluginInfo) => {
    dialog.confirm({
        title: "确认删除",
        content: `确定要删除插件「${plugin.display_name}」吗？重启后生效。`,
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
            <h2 class="text-lg font-medium text-gray-800">插件管理</h2>
            <VortButton variant="primary" @click="addDialogOpen = true">
                <Plus :size="14" class="mr-1" /> 添加插件
            </VortButton>
        </div>

        <!-- 搜索和筛选 -->
        <div class="flex flex-wrap items-center gap-3">
            <div class="relative flex-1 min-w-[200px] max-w-md">
                <Search :size="14" class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                    v-model="searchQuery"
                    type="text"
                    placeholder="搜索插件名称、描述、工具..."
                    class="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400"
                />
            </div>
            <VortSelect v-model="filterSource" class="w-28">
                <VortSelectOption value="all">全部来源</VortSelectOption>
                <VortSelectOption value="builtin">内置</VortSelectOption>
                <VortSelectOption value="pip">pip</VortSelectOption>
                <VortSelectOption value="local">本地</VortSelectOption>
            </VortSelect>
            <VortSelect v-model="filterStatus" class="w-28">
                <VortSelectOption value="all">全部状态</VortSelectOption>
                <VortSelectOption value="enabled">已启用</VortSelectOption>
                <VortSelectOption value="disabled">已禁用</VortSelectOption>
            </VortSelect>
            <span v-if="filteredPlugins.length !== plugins.length" class="text-xs text-gray-400">
                {{ filteredPlugins.length }} / {{ plugins.length }}
            </span>
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
            <div v-if="plugins.length === 0 && !loading" class="text-center py-12 text-gray-400 text-sm">
                暂无已加载的插件
            </div>
            <div v-else-if="filteredPlugins.length === 0" class="text-center py-12 text-gray-400 text-sm">
                没有匹配的插件
            </div>
            <div v-else class="masonry-grid">
                <vort-card v-for="plugin in filteredPlugins" :key="plugin.name" class="masonry-item" :shadow="false" padding="small">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center">
                            <div class="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center mr-3">
                                <Puzzle :size="20" class="text-blue-600" />
                            </div>
                            <div>
                                <h3 class="text-sm font-medium text-gray-800">{{ plugin.display_name }}</h3>
                                <p class="text-xs text-gray-400">{{ plugin.name }} v{{ plugin.version }}</p>
                            </div>
                        </div>
                        <div class="flex items-center gap-2">
                            <VortTag :color="{ builtin: 'blue', pip: 'cyan', local: 'purple' }[plugin.source] || 'default'" size="small">
                                {{ { builtin: '内置', pip: 'pip', local: '本地' }[plugin.source] || plugin.source }}
                            </VortTag>
                            <VortTag v-if="plugin.core" color="geekblue" size="small">核心</VortTag>
                            <VortButton v-if="plugin.has_config" size="small" variant="text" @click="openConfig(plugin.name)">
                                <Settings :size="14" />
                            </VortButton>
                            <VortTooltip v-if="plugin.core" title="核心插件不可禁用">
                                <VortSwitch :checked="true" disabled size="small" />
                            </VortTooltip>
                            <VortSwitch
                                v-else
                                :checked="plugin.enabled"
                                size="small"
                                @change="handleToggle(plugin)"
                            />
                        </div>
                    </div>

                    <p v-if="plugin.description" class="text-xs text-gray-500 mb-3">{{ plugin.description }}</p>

                    <div v-if="plugin.tools.length" class="mt-3 pt-3 border-t border-gray-100">
                        <button
                            class="flex items-center gap-1 text-xs text-gray-500 font-medium hover:text-blue-600 transition-colors"
                            @click="toggleTools(plugin.name)"
                        >
                            <component :is="collapsedTools[plugin.name] ? ChevronRight : ChevronDown" :size="12" />
                            工具列表 ({{ plugin.tools.length }})
                        </button>
                        <div v-show="!collapsedTools[plugin.name]" class="mt-2 space-y-2">
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
            </div>
        </VortSpin>

        <!-- 配置抽屉 -->
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

        <!-- 添加插件弹窗 -->
        <VortDialog :open="addDialogOpen" title="添加插件" @update:open="addDialogOpen = $event">
            <div class="space-y-4">
                <VortRadioGroup v-model="installMode">
                    <VortRadioButton value="pip">pip 安装</VortRadioButton>
                    <VortRadioButton value="upload">上传 zip</VortRadioButton>
                </VortRadioGroup>

                <div v-if="installMode === 'pip'">
                    <p class="text-xs text-gray-400 mb-2">输入 PyPI 包名，如 openvort-plugin-gitlab</p>
                    <VortInput v-model="packageName" placeholder="包名" @keyup.enter="handleInstall" />
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
                        @click="handleInstall"
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
