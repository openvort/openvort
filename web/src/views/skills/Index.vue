<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getSkills, getSkill, createSkill, updateSkill, deleteSkill, toggleSkill } from "@/api";
import { message } from "@/components/vort/message";
import { dialog } from "@/components/vort/dialog";
import { BookOpen, Plus, Trash2, Save, Package, FolderOpen } from "lucide-vue-next";

interface SkillItem {
    name: string;
    description: string;
    source: string;
    enabled: boolean;
}

// ---- 列表状态 ----
const builtinSkills = ref<SkillItem[]>([]);
const workspaceSkills = ref<SkillItem[]>([]);
const loading = ref(false);

async function loadSkills() {
    loading.value = true;
    try {
        const res: any = await getSkills();
        builtinSkills.value = res?.builtin || [];
        workspaceSkills.value = res?.workspace || [];
    } catch { /* ignore */ }
    finally { loading.value = false; }
}

// ---- 启用/禁用 ----
async function handleToggle(skill: SkillItem) {
    try {
        const res: any = await toggleSkill(skill.name);
        if (res?.success) {
            skill.enabled = res.enabled;
            message.success(res.enabled ? "已启用" : "已禁用");
        }
    } catch {
        message.error("操作失败");
    }
}

// ---- Drawer 编辑 ----
const drawerOpen = ref(false);
const drawerSkill = ref<{ name: string; description: string; content: string; source: string; enabled: boolean } | null>(null);
const drawerLoading = ref(false);
const saving = ref(false);

async function openDrawer(skill: SkillItem) {
    drawerLoading.value = true;
    drawerOpen.value = true;
    try {
        const res: any = await getSkill(skill.name);
        drawerSkill.value = {
            name: res.name,
            description: res.description,
            content: res.content,
            source: res.source,
            enabled: res.enabled,
        };
    } catch {
        message.error("加载 Skill 详情失败");
        drawerOpen.value = false;
    } finally {
        drawerLoading.value = false;
    }
}

async function handleSave() {
    if (!drawerSkill.value || drawerSkill.value.source !== "workspace") return;
    saving.value = true;
    try {
        await updateSkill(drawerSkill.value.name, {
            description: drawerSkill.value.description,
            content: drawerSkill.value.content,
        });
        message.success("保存成功");
        drawerOpen.value = false;
        loadSkills();
    } catch {
        message.error("保存失败");
    } finally {
        saving.value = false;
    }
}

// ---- 删除 ----
function handleDelete(skill: SkillItem) {
    dialog.confirm({
        title: `确认删除 Skill「${skill.name}」？`,
        content: "删除后不可恢复",
        onOk: async () => {
            try {
                await deleteSkill(skill.name);
                message.success("删除成功");
                drawerOpen.value = false;
                loadSkills();
            } catch {
                message.error("删除失败");
            }
        },
    });
}

// ---- 新建 Dialog ----
const createDialogOpen = ref(false);
const createForm = ref({ name: "", description: "", content: "" });
const creating = ref(false);

function openCreateDialog() {
    createForm.value = { name: "", description: "", content: "" };
    createDialogOpen.value = true;
}

async function handleCreate() {
    if (!createForm.value.name.trim()) {
        message.error("请输入 Skill 名称");
        return;
    }
    creating.value = true;
    try {
        await createSkill(createForm.value);
        message.success("创建成功");
        createDialogOpen.value = false;
        loadSkills();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "创建失败");
    } finally {
        creating.value = false;
    }
}

onMounted(loadSkills);
</script>

<template>
    <div class="space-y-6">
        <div class="flex items-center justify-between">
            <h2 class="text-lg font-medium text-gray-800">技能管理</h2>
            <VortButton variant="primary" @click="openCreateDialog">
                <Plus :size="14" class="mr-1" /> 新建 Skill
            </VortButton>
        </div>

        <VortSpin :spinning="loading">
            <!-- 用户 Skills -->
            <div class="mb-6" v-if="workspaceSkills.length > 0 || !loading">
                <div class="flex items-center justify-between mb-3">
                    <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wide">用户 Skills</h3>
                    <span class="text-xs text-gray-400">{{ workspaceSkills.length }} 个</span>
                </div>
                <div v-if="workspaceSkills.length === 0" class="text-center py-8 text-gray-400 text-sm bg-white rounded-xl">
                    暂无用户 Skill，点击右上角新建
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <VortCard v-for="skill in workspaceSkills" :key="skill.name" :shadow="false" padding="small"
                        class="cursor-pointer hover:border-blue-200 transition-colors" @click="openDrawer(skill)">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center min-w-0">
                                <div class="w-10 h-10 rounded-lg bg-purple-50 flex items-center justify-center mr-3 flex-shrink-0">
                                    <FolderOpen :size="20" class="text-purple-600" />
                                </div>
                                <div class="min-w-0">
                                    <h4 class="text-sm font-medium text-gray-800 truncate">{{ skill.name }}</h4>
                                    <p class="text-xs text-gray-400 truncate">{{ skill.description || '暂无描述' }}</p>
                                </div>
                            </div>
                            <div class="flex items-center gap-2 flex-shrink-0 ml-3" @click.stop>
                                <VortTag color="purple" size="small">workspace</VortTag>
                                <VortSwitch :checked="skill.enabled" size="small" @change="handleToggle(skill)" />
                            </div>
                        </div>
                    </VortCard>
                </div>
            </div>

            <!-- 内置 Skills -->
            <div v-if="builtinSkills.length > 0 || !loading">
                <div class="flex items-center justify-between mb-3">
                    <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wide">内置 Skills</h3>
                    <span class="text-xs text-gray-400">{{ builtinSkills.length }} 个</span>
                </div>
                <div v-if="builtinSkills.length === 0 && !loading" class="text-center py-8 text-gray-400 text-sm bg-white rounded-xl">
                    暂无内置 Skill
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <VortCard v-for="skill in builtinSkills" :key="skill.name" :shadow="false" padding="small"
                        class="cursor-pointer hover:border-blue-200 transition-colors" @click="openDrawer(skill)">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center min-w-0">
                                <div class="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center mr-3 flex-shrink-0">
                                    <Package :size="20" class="text-blue-600" />
                                </div>
                                <div class="min-w-0">
                                    <h4 class="text-sm font-medium text-gray-800 truncate">{{ skill.name }}</h4>
                                    <p class="text-xs text-gray-400 truncate">{{ skill.description || '暂无描述' }}</p>
                                </div>
                            </div>
                            <div class="flex items-center gap-2 flex-shrink-0 ml-3" @click.stop>
                                <VortTag color="blue" size="small">builtin</VortTag>
                                <VortSwitch :checked="skill.enabled" size="small" @change="handleToggle(skill)" />
                            </div>
                        </div>
                    </VortCard>
                </div>
            </div>
        </VortSpin>

        <!-- 编辑 Drawer -->
        <VortDrawer :open="drawerOpen" :title="drawerSkill?.name || 'Skill 详情'" :width="640"
            @update:open="drawerOpen = $event">
            <VortSpin :spinning="drawerLoading">
                <div v-if="drawerSkill" class="space-y-4">
                    <VortForm label-width="80px">
                        <VortFormItem label="名称">
                            <VortInput :model-value="drawerSkill.name" disabled />
                        </VortFormItem>
                        <VortFormItem label="来源">
                            <VortTag :color="drawerSkill.source === 'builtin' ? 'blue' : 'purple'">
                                {{ drawerSkill.source === 'builtin' ? '内置' : '用户' }}
                            </VortTag>
                        </VortFormItem>
                        <VortFormItem label="描述">
                            <VortInput v-model="drawerSkill.description"
                                :disabled="drawerSkill.source !== 'workspace'"
                                placeholder="Skill 描述" />
                        </VortFormItem>
                        <VortFormItem label="内容">
                            <VortTextarea v-model="drawerSkill.content"
                                :disabled="drawerSkill.source !== 'workspace'"
                                placeholder="Markdown 格式的 Skill 内容"
                                :rows="16"
                                style="font-family: monospace; font-size: 13px;" />
                        </VortFormItem>
                    </VortForm>
                </div>
            </VortSpin>
            <template #footer>
                <div class="flex items-center justify-between w-full">
                    <div>
                        <VortButton v-if="drawerSkill?.source === 'workspace'" danger @click="handleDelete(drawerSkill!)">
                            <Trash2 :size="14" class="mr-1" /> 删除
                        </VortButton>
                    </div>
                    <div class="flex items-center gap-2">
                        <VortButton @click="drawerOpen = false">关闭</VortButton>
                        <VortButton v-if="drawerSkill?.source === 'workspace'" variant="primary" :loading="saving" @click="handleSave">
                            <Save :size="14" class="mr-1" /> 保存
                        </VortButton>
                    </div>
                </div>
            </template>
        </VortDrawer>

        <!-- 新建 Dialog -->
        <VortDialog :open="createDialogOpen" title="新建 Skill" @update:open="createDialogOpen = $event">
            <VortForm label-width="80px">
                <VortFormItem label="名称" required>
                    <VortInput v-model="createForm.name" placeholder="英文标识，如 daily-report" />
                </VortFormItem>
                <VortFormItem label="描述">
                    <VortInput v-model="createForm.description" placeholder="Skill 用途描述" />
                </VortFormItem>
                <VortFormItem label="内容">
                    <VortTextarea v-model="createForm.content" placeholder="Markdown 格式的 Skill 内容" :rows="8"
                        style="font-family: monospace; font-size: 13px;" />
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
