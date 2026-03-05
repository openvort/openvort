<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import {
    getSkills, getSkill, createSkill, updateSkill, deleteSkill, toggleSkill,
    getMemberSkills, createPersonalSkill, updatePersonalSkill, deletePersonalSkill,
    getMembers,
} from "@/api";
import { message, dialog } from "@openvort/vort-ui";
import { Plus, Trash2, Save, Package, Globe, User } from "lucide-vue-next";

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

async function handleToggle(skill: SkillItem) {
    try {
        const res: any = await toggleSkill(skill.id);
        if (res?.success) {
            skill.enabled = res.enabled;
            message.success(res.enabled ? "已启用" : "已禁用");
        }
    } catch { message.error("操作失败"); }
}

// ---- Detail drawer (builtin readonly / public editable) ----
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
        message.error("加载详情失败");
        drawerOpen.value = false;
    } finally { drawerLoading.value = false; }
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
            } catch { message.error("删除失败"); }
        },
    });
}

// ---- Create public skill ----
const createDialogOpen = ref(false);
const createForm = ref({ name: "", description: "", content: "" });
const creating = ref(false);

function openCreateDialog() {
    createForm.value = { name: "", description: "", content: "" };
    createDialogOpen.value = true;
}

async function handleCreate() {
    if (!createForm.value.name.trim()) { message.error("请输入名称"); return; }
    creating.value = true;
    try {
        await createSkill(createForm.value);
        message.success("创建成功");
        createDialogOpen.value = false;
        loadSkills();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "创建失败");
    } finally { creating.value = false; }
}

// ---- Personal skills ----
const members = ref<MemberOption[]>([]);
const selectedMemberId = ref("");
const personalSkills = ref<SkillItem[]>([]);
const personalLoading = ref(false);

async function loadMembers() {
    try {
        const res: any = await getMembers({ size: 500 });
        members.value = (res?.members || []).map((m: any) => ({ id: m.id, name: m.name }));
    } catch { /* ignore */ }
}

async function loadPersonalSkills() {
    if (!selectedMemberId.value) { personalSkills.value = []; return; }
    personalLoading.value = true;
    try {
        const res: any = await getMemberSkills(selectedMemberId.value);
        personalSkills.value = res?.personal || [];
    } catch { personalSkills.value = []; }
    finally { personalLoading.value = false; }
}

watch(selectedMemberId, () => loadPersonalSkills());

const personalDrawerOpen = ref(false);
const personalDrawerMode = ref<"add" | "edit">("add");
const personalDrawerForm = ref({ id: "", name: "", description: "", content: "" });
const personalSaving = ref(false);

function openPersonalAdd() {
    if (!selectedMemberId.value) { message.warning("请先选择成员"); return; }
    personalDrawerMode.value = "add";
    personalDrawerForm.value = { id: "", name: "", description: "", content: "" };
    personalDrawerOpen.value = true;
}

function openPersonalEdit(skill: SkillItem) {
    personalDrawerMode.value = "edit";
    personalDrawerForm.value = { id: skill.id, name: skill.name, description: skill.description, content: skill.content || "" };
    personalDrawerOpen.value = true;
}

async function handleSavePersonal() {
    if (!personalDrawerForm.value.name.trim()) { message.error("请输入名称"); return; }
    personalSaving.value = true;
    try {
        if (personalDrawerMode.value === "add") {
            await createPersonalSkill(selectedMemberId.value, {
                name: personalDrawerForm.value.name, description: personalDrawerForm.value.description,
                content: personalDrawerForm.value.content,
            });
        } else {
            await updatePersonalSkill(personalDrawerForm.value.id, {
                name: personalDrawerForm.value.name, description: personalDrawerForm.value.description,
                content: personalDrawerForm.value.content,
            });
        }
        message.success("保存成功");
        personalDrawerOpen.value = false;
        loadPersonalSkills();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "保存失败");
    } finally { personalSaving.value = false; }
}

function handleDeletePersonal(skill: SkillItem) {
    dialog.confirm({
        title: `确认删除「${skill.name}」？`,
        onOk: async () => {
            try {
                await deletePersonalSkill(skill.id);
                message.success("已删除");
                loadPersonalSkills();
            } catch { message.error("删除失败"); }
        },
    });
}

onMounted(() => { loadSkills(); loadMembers(); });
</script>

<template>
    <div class="space-y-4">
        <!-- 内置技能 -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-2">
                    <Package :size="18" class="text-blue-600" />
                    <h3 class="text-base font-medium text-gray-800">内置技能</h3>
                    <span class="text-xs text-gray-400">随代码内置，全局生效</span>
                </div>
            </div>
            <VortSpin :spinning="loading">
                <div v-if="builtinSkills.length === 0 && !loading" class="text-center py-6 text-gray-400 text-sm">暂无内置技能</div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    <div v-for="skill in builtinSkills" :key="skill.id"
                        class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-100 hover:border-blue-200 transition-colors cursor-pointer"
                        @click="openDrawer(skill)">
                        <div class="min-w-0 flex-1">
                            <div class="text-sm font-medium text-gray-800 truncate">{{ skill.name }}</div>
                            <div class="text-xs text-gray-400 truncate mt-0.5">{{ skill.description || '暂无描述' }}</div>
                        </div>
                        <div class="flex items-center gap-2 flex-shrink-0 ml-3" @click.stop>
                            <VortTag color="blue" size="small">内置</VortTag>
                            <VortSwitch :checked="skill.enabled" size="small" @change="handleToggle(skill)" />
                        </div>
                    </div>
                </div>
            </VortSpin>
        </div>

        <!-- 公共技能 -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-2">
                    <Globe :size="18" class="text-green-600" />
                    <h3 class="text-base font-medium text-gray-800">公共技能</h3>
                    <span class="text-xs text-gray-400">管理员维护，成员可订阅</span>
                </div>
                <VortButton variant="primary" size="small" @click="openCreateDialog">
                    <Plus :size="14" class="mr-1" /> 新建
                </VortButton>
            </div>
            <VortSpin :spinning="loading">
                <div v-if="publicSkills.length === 0 && !loading" class="text-center py-6 text-gray-400 text-sm">
                    暂无公共技能，点击右上角新建
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    <div v-for="skill in publicSkills" :key="skill.id"
                        class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-100 hover:border-green-200 transition-colors cursor-pointer"
                        @click="openDrawer(skill)">
                        <div class="min-w-0 flex-1">
                            <div class="text-sm font-medium text-gray-800 truncate">{{ skill.name }}</div>
                            <div class="text-xs text-gray-400 truncate mt-0.5">{{ skill.description || '暂无描述' }}</div>
                        </div>
                        <div class="flex items-center gap-2 flex-shrink-0 ml-3" @click.stop>
                            <VortTag color="green" size="small">公共</VortTag>
                            <VortSwitch :checked="skill.enabled" size="small" @change="handleToggle(skill)" />
                        </div>
                    </div>
                </div>
            </VortSpin>
        </div>

        <!-- 成员技能总览（管理员代管） -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-2">
                    <User :size="18" class="text-purple-600" />
                    <h3 class="text-base font-medium text-gray-800">成员技能总览</h3>
                    <span class="text-xs text-gray-400">查看和代管成员的个人技能，成员也可在个人中心自行管理</span>
                </div>
            </div>

            <div class="flex items-center gap-4 mb-4">
                <span class="text-sm text-gray-500 whitespace-nowrap">选择成员</span>
                <VortSelect v-model="selectedMemberId" placeholder="请选择成员" allow-clear class="w-[200px]">
                    <VortSelectOption v-for="m in members" :key="m.id" :value="m.id">{{ m.name }}</VortSelectOption>
                </VortSelect>
                <VortButton v-if="selectedMemberId" size="small" @click="openPersonalAdd">
                    <Plus :size="14" class="mr-1" /> 为该成员添加
                </VortButton>
            </div>

            <VortSpin :spinning="personalLoading">
                <div v-if="!selectedMemberId" class="text-center py-6 text-gray-400 text-sm">请选择成员查看其技能配置</div>
                <div v-else-if="personalSkills.length === 0 && !personalLoading" class="text-center py-6 text-gray-400 text-sm">该成员暂无个人技能</div>
                <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    <div v-for="skill in personalSkills" :key="skill.id"
                        class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-100 hover:border-purple-200 transition-colors cursor-pointer"
                        @click="openPersonalEdit(skill)">
                        <div class="min-w-0 flex-1">
                            <div class="text-sm font-medium text-gray-800 truncate">{{ skill.name }}</div>
                            <div class="text-xs text-gray-400 truncate mt-0.5">{{ skill.description || '暂无描述' }}</div>
                        </div>
                        <div class="flex items-center gap-2 flex-shrink-0 ml-3" @click.stop>
                            <VortTag color="purple" size="small">个人</VortTag>
                            <VortPopconfirm title="确认删除？" @confirm="handleDeletePersonal(skill)">
                                <a class="text-red-400 hover:text-red-500 cursor-pointer"><Trash2 :size="14" /></a>
                            </VortPopconfirm>
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
