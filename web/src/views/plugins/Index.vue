<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getPlugins, getPluginDetail, updatePlugin, togglePlugin, installPlugin, uploadPlugin, deletePlugin } from "@/api";
import { Puzzle, Wrench, CheckCircle, XCircle, Settings, Plus, Upload, Trash2 } from "lucide-vue-next";
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

// 配置抽屉
const drawerOpen = ref(false);
const drawerLoading = ref(false);
const saving = ref(false);
const currentPlugin = ref<string>("");
const configSchema = ref<ConfigField[]>([]);
const configForm = ref<Record<string, string>>({});

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
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <vort-card v-for="plugin in plugins" :key="plugin.name" :shadow="false" padding="small">
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

                    <div v-if="plugin.tools.length" class="space-y-2">
                        <p class="text-xs text-gray-500 font-medium">工具列表 ({{ plugin.tools.length }})</p>
                        <div v-for="tool in plugin.tools" :key="tool.name"
                            class="flex items-start gap-2 p-2 rounded bg-gray-50 text-xs">
                            <Wrench :size="12" class="text-gray-400 mt-0.5 flex-shrink-0" />
                            <div>
                                <span class="font-medium text-gray-700">{{ tool.name }}</span>
                                <p class="text-gray-400 mt-0.5">{{ tool.description }}</p>
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
