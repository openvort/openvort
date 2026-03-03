<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import {
    getSkills, getSkill, createSkill, updateSkill, deleteSkill, toggleSkill,
    getMemberSkills, createPersonalSkill, updatePersonalSkill, deletePersonalSkill,
    getMembers,
} from "@/api";
import { message } from "@/components/vort/message";
import { dialog } from "@/components/vort/dialog";
import { Plus, Trash2, Save, Package, Globe, User, Search } from "lucide-vue-next";

interface SkillItem {
    id: string;
    name: string;
    description: string;
    scope: string;
    enabled: boolean;
    content?: string;
}

interface MemberOption {
    id: string;
    name: string;
}

// ---- Tab state ----
const activeTab = ref("builtin");

// ---- Builtin + Public lists ----
const builtinSkills = ref<SkillItem[]>([]);
const publicSkills = ref<SkillItem[]>([]);
const loading = ref(false);

async function loadSkills() {
    loading.value = true;
    try {
        const res: any = await getSkills();
        builtinSkills.value = res?.builtin || [];
        publicSkills.value = res?.public || [];
    } catch { /* ignore */ }
    finally { loading.value = false; }
}

// ---- Toggle ----
async function handleToggle(skill: SkillItem) {
    try {
        const res: any = await toggleSkill(skill.id);
        if (res?.success) {
            skill.enabled = res.enabled;
            message.success(res.enabled ? "已启用" : "已禁用");
        }
    } catch {
        message.error("操作失败");
    }
}

// ---- Drawer (builtin/public detail/edit) ----
const drawerOpen = ref(false);
const drawerSkill = ref<SkillItem | null>(null);
const drawerLoading = ref(false);
const saving = ref(false);

async function openDrawer(skill: SkillItem) {
    drawerLoading.value = true;
    drawerOpen.value = true;
    try {
        const res: any = await getSkill(skill.id);
        drawerSkill.value = {
            id: res.id, name: res.name, description: res.description,
            content: res.content, scope: res.scope, enabled: res.enabled,
        };
    } catch {
        message.error("加载 Skill 详情失败");
        drawerOpen.value = false;
    } finally {
        drawerLoading.value = false;
    }
}

async function handleSaveDrawer() {
    if (!drawerSkill.value || drawerSkill.value.scope !== "public") return;
    saving.value = true;
    try {
        await updateSkill(drawerSkill.value.id, {
            name: drawerSkill.value.name,
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
            } catch {
                message.error("删除失败");
            }
        },
    });
}

// ---- Create public skill dialog ----
const createDialogOpen = ref(false);
const createForm = ref({ name: "", description: "", content: "" });
const creating = ref(false);

function openCreateDialog() {
    createForm.value = { name: "", description: "", content: "" };
    createDialogOpen.value = true;
}

async function handleCreate() {
    if (!createForm.value.name.trim()) {
        message.error("请输入名称");
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

// ---- Personal skills tab ----
const members = ref<MemberOption[]>([]);
const selectedMemberId = ref("");
const personalSkills = ref<SkillItem[]>([]);
const personalLoading = ref(false);
const memberBio = ref("");

async function loadMembers() {
    try {
        const res: any = await getMembers({ size: 500 });
        members.value = (res?.items || []).map((m: any) => ({ id: m.id, name: m.name }));
    } catch { /* ignore */ }
}

async function loadPersonalSkills() {
    if (!selectedMemberId.value) {
        personalSkills.value = [];
        return;
    }
    personalLoading.value = true;
    try {
        const res: any = await getMemberSkills(selectedMemberId.value);
        personalSkills.value = res?.personal || [];
        memberBio.value = res?.bio || "";
    } catch { personalSkills.value = []; }
    finally { personalLoading.value = false; }
}

watch(selectedMemberId, () => loadPersonalSkills());

// ---- Personal skill drawer ----
const personalDrawerOpen = ref(false);
const personalDrawerMode = ref<"add" | "edit">("add");
const personalDrawerForm = ref({ id: "", name: "", description: "", content: "" });
const personalSaving = ref(false);

function openPersonalAdd() {
    if (!selectedMemberId.value) {
        message.warning("请先选择成员");
        return;
    }
    personalDrawerMode.value = "add";
    personalDrawerForm.value = { id: "", name: "", description: "", content: "" };
    personalDrawerOpen.value = true;
}

async function openPersonalEdit(skill: SkillItem) {
    personalDrawerMode.value = "edit";
    personalDrawerForm.value = {
        id: skill.id,
        name: skill.name,
        description: skill.description,
        content: skill.content || "",
    };
    // Load full content if not available
    if (!skill.content) {
        try {
            const res: any = await getSkill(skill.id);
            personalDrawerForm.value.content = res?.content || "";
        } catch { /* ignore */ }
    }
    personalDrawerOpen.value = true;
}

async function handleSavePersonal() {
    if (!personalDrawerForm.value.name.trim()) {
        message.error("请输入名称");
        return;
    }
    personalSaving.value = true;
    try {
        if (personalDrawerMode.value === "add") {
            await createPersonalSkill(selectedMemberId.value, {
                name: personalDrawerForm.value.name,
                description: personalDrawerForm.value.description,
                content: personalDrawerForm.value.content,
            });
        } else {
            await updatePersonalSkill(personalDrawerForm.value.id, {
                name: personalDrawerForm.value.name,
                description: personalDrawerForm.value.description,
                content: personalDrawerForm.value.content,
            });
        }
        message.success("保存成功");
        personalDrawerOpen.value = false;
        loadPersonalSkills();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "保存失败");
    } finally {
        personalSaving.value = false;
    }
}

function handleDeletePersonal(skill: SkillItem) {
    dialog.confirm({
        title: `确认删除个人技能「${skill.name}」？`,
        content: "删除后不可恢复",
        onOk: async () => {
            try {
                await deletePersonalSkill(skill.id);
                message.success("删除成功");
                loadPersonalSkills();
            } catch {
                message.error("删除失败");
            }
        },
    });
}

onMounted(() => {
    loadSkills();
    loadMembers();
});
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-lg font-medium text-gray-800">技能管理</h2>
                <VortButton v-if="activeTab === 'public'" variant="primary" @click="openCreateDialog">
                    <Plus :size="14" class="mr-1" /> 新建公共技能
                </VortButton>
                <VortButton v-if="activeTab === 'personal'" variant="primary" @click="openPersonalAdd">
                    <Plus :size="14" class="mr-1" /> 新增个人技能
                </VortButton>
            </div>

            <VortTabs v-model="activeTab">
                <VortTabPane key="builtin" tab="内置技能" />
                <VortTabPane key="public" tab="公共技能" />
                <VortTabPane key="personal" tab="个人技能" />
            </VortTabs>
        </div>

        <!-- Builtin tab -->
        <div v-if="activeTab === 'builtin'" class="bg-white rounded-xl p-6">
            <VortSpin :spinning="loading">
                <div v-if="builtinSkills.length === 0 && !loading" class="text-center py-8 text-gray-400 text-sm">
                    暂无内置技能
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <VortCard v-for="skill in builtinSkills" :key="skill.id" :shadow="false" padding="small"
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
                                <VortTag color="blue" size="small">内置</VortTag>
                                <VortSwitch :checked="skill.enabled" size="small" @change="handleToggle(skill)" />
                            </div>
                        </div>
                    </VortCard>
                </div>
            </VortSpin>
        </div>

        <!-- Public tab -->
        <div v-if="activeTab === 'public'" class="bg-white rounded-xl p-6">
            <VortSpin :spinning="loading">
                <div v-if="publicSkills.length === 0 && !loading" class="text-center py-8 text-gray-400 text-sm">
                    暂无公共技能，点击右上角新建
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <VortCard v-for="skill in publicSkills" :key="skill.id" :shadow="false" padding="small"
                        class="cursor-pointer hover:border-blue-200 transition-colors" @click="openDrawer(skill)">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center min-w-0">
                                <div class="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center mr-3 flex-shrink-0">
                                    <Globe :size="20" class="text-green-600" />
                                </div>
                                <div class="min-w-0">
                                    <h4 class="text-sm font-medium text-gray-800 truncate">{{ skill.name }}</h4>
                                    <p class="text-xs text-gray-400 truncate">{{ skill.description || '暂无描述' }}</p>
                                </div>
                            </div>
                            <div class="flex items-center gap-2 flex-shrink-0 ml-3" @click.stop>
                                <VortTag color="green" size="small">公共</VortTag>
                                <VortSwitch :checked="skill.enabled" size="small" @change="handleToggle(skill)" />
                            </div>
                        </div>
                    </VortCard>
                </div>
            </VortSpin>
        </div>

        <!-- Personal tab -->
        <div v-if="activeTab === 'personal'" class="bg-white rounded-xl p-6">
            <div class="flex items-center gap-4 mb-4">
                <span class="text-sm text-gray-500 whitespace-nowrap">选择成员</span>
                <VortSelect v-model="selectedMemberId" placeholder="请选择成员" allow-clear class="w-[200px]">
                    <VortSelectOption v-for="m in members" :key="m.id" :value="m.id">{{ m.name }}</VortSelectOption>
                </VortSelect>
            </div>

            <VortSpin :spinning="personalLoading">
                <div v-if="!selectedMemberId" class="text-center py-8 text-gray-400 text-sm">
                    请选择一个成员查看其个人技能
                </div>
                <div v-else-if="personalSkills.length === 0 && !personalLoading" class="text-center py-8 text-gray-400 text-sm">
                    该成员暂无个人技能
                </div>
                <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <VortCard v-for="skill in personalSkills" :key="skill.id" :shadow="false" padding="small"
                        class="cursor-pointer hover:border-purple-200 transition-colors" @click="openPersonalEdit(skill)">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center min-w-0">
                                <div class="w-10 h-10 rounded-lg bg-purple-50 flex items-center justify-center mr-3 flex-shrink-0">
                                    <User :size="20" class="text-purple-600" />
                                </div>
                                <div class="min-w-0">
                                    <h4 class="text-sm font-medium text-gray-800 truncate">{{ skill.name }}</h4>
                                    <p class="text-xs text-gray-400 truncate">{{ skill.description || '暂无描述' }}</p>
                                </div>
                            </div>
                            <div class="flex items-center gap-2 flex-shrink-0 ml-3" @click.stop>
                                <VortTag color="purple" size="small">个人</VortTag>
                                <VortPopconfirm title="确认删除？" @confirm="handleDeletePersonal(skill)">
                                    <a class="text-sm text-red-500 cursor-pointer"><Trash2 :size="14" /></a>
                                </VortPopconfirm>
                            </div>
                        </div>
                    </VortCard>
                </div>
            </VortSpin>
        </div>

        <!-- Builtin/Public detail drawer -->
        <VortDrawer :open="drawerOpen" :title="drawerSkill?.name || 'Skill 详情'" :width="640" @update:open="drawerOpen = $event">
            <VortSpin :spinning="drawerLoading">
                <div v-if="drawerSkill" class="space-y-4">
                    <VortForm label-width="80px">
                        <VortFormItem label="名称">
                            <VortInput v-model="drawerSkill.name" :disabled="drawerSkill.scope === 'builtin'" />
                        </VortFormItem>
                        <VortFormItem label="类型">
                            <VortTag :color="drawerSkill.scope === 'builtin' ? 'blue' : 'green'">
                                {{ drawerSkill.scope === 'builtin' ? '内置' : '公共' }}
                            </VortTag>
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
                        <VortButton v-if="drawerSkill?.scope === 'public'" variant="primary" :loading="saving" @click="handleSaveDrawer">
                            <Save :size="14" class="mr-1" /> 保存
                        </VortButton>
                    </div>
                </div>
            </template>
        </VortDrawer>

        <!-- Personal skill drawer -->
        <VortDrawer :open="personalDrawerOpen" :title="personalDrawerMode === 'add' ? '新增个人技能' : '编辑个人技能'" :width="550" @update:open="personalDrawerOpen = $event">
            <VortForm label-width="80px">
                <VortFormItem label="名称" required>
                    <VortInput v-model="personalDrawerForm.name" placeholder="如：Python 开发、项目管理" />
                </VortFormItem>
                <VortFormItem label="描述">
                    <VortInput v-model="personalDrawerForm.description" placeholder="简短描述" />
                </VortFormItem>
                <VortFormItem label="内容">
                    <VortTextarea v-model="personalDrawerForm.content"
                        placeholder="详细描述该成员在此技能方面的专业知识、经验和能力..." :rows="12"
                        style="font-family: monospace; font-size: 13px;" />
                </VortFormItem>
            </VortForm>
            <template #footer>
                <div class="flex justify-end gap-2">
                    <VortButton @click="personalDrawerOpen = false">取消</VortButton>
                    <VortButton variant="primary" :loading="personalSaving" @click="handleSavePersonal">
                        <Save :size="14" class="mr-1" /> 保存
                    </VortButton>
                </div>
            </template>
        </VortDrawer>

        <!-- Create public skill dialog -->
        <VortDialog :open="createDialogOpen" title="新建公共技能" @update:open="createDialogOpen = $event">
            <VortForm label-width="80px">
                <VortFormItem label="名称" required>
                    <VortInput v-model="createForm.name" placeholder="如：代码审查规范" />
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
