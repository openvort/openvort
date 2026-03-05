<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import {
    getSkills, getSkill, createSkill, updateSkill, deleteSkill, toggleSkill,
    getRoleSkills, addRoleSkill, removeRoleSkill,
    getMemberSkillsWithSource, getMembers,
    getSkillDirectories, searchOnlineSkills, importSkillFromGithub,
    generateSkillContentPrompt,
} from "@/api";
import { message, dialog } from "@openvort/vort-ui";
import { Plus, Trash2, Save, User, Link, BookOpen, Zap, FileText, Settings, ChevronDown, ChevronUp, Code, ClipboardList, TestTube, Palette, Bot, Github, FolderOpen } from "lucide-vue-next";

const router = useRouter();

interface SkillItem {
    id: string;
    name: string;
    description: string;
    scope: string;
    skill_type: string;
    enabled: boolean;
    content?: string;
}

interface MemberOption {
    id: string;
    name: string;
}

interface MemberSkillItem {
    id: string;
    name: string;
    description: string;
    scope: string;
    skill_type: string;
    source: string;
    enabled: boolean;
}

// ---- Skill type config ----
const SKILL_TYPES = [
    { key: "role", label: "角色技能", icon: User, color: "blue", desc: "定义角色身份和人设" },
    { key: "workflow", label: "工作流技能", icon: Zap, color: "green", desc: "工作流程和方法论" },
    { key: "report", label: "报告模板", icon: FileText, color: "orange", desc: "报告和文档模板" },
    { key: "system", label: "系统配置", icon: Settings, color: "purple", desc: "系统级配置和约定" },
];

const SKILL_TYPE_MAP: Record<string, typeof SKILL_TYPES[0]> = {};
SKILL_TYPES.forEach(t => SKILL_TYPE_MAP[t.key] = t);

const ROLE_ICON_MAP: Record<string, any> = {
    developer: Code,
    pm: ClipboardList,
    qa: TestTube,
    designer: Palette,
    assistant: Bot,
};

const ROLE_OPTIONS = [
    { value: "developer", label: "开发工程师" },
    { value: "pm", label: "产品经理" },
    { value: "qa", label: "测试工程师" },
    { value: "designer", label: "设计师" },
    { value: "assistant", label: "通用助手" },
];

// ---- Skills list ----
const skills = ref<SkillItem[]>([]);
const loading = ref(false);
const collapsedTypes = ref<Set<string>>(new Set());

const groupedSkills = computed(() => {
    const groups: Record<string, SkillItem[]> = {};
    for (const t of SKILL_TYPES) {
        groups[t.key] = [];
    }
    for (const s of skills.value) {
        const key = s.skill_type || "workflow";
        if (!groups[key]) groups[key] = [];
        groups[key].push(s);
    }
    return groups;
});

async function loadSkills() {
    loading.value = true;
    try {
        const res: any = await getSkills();
        skills.value = res?.skills || [];
    } catch { /* ignore */ }
    finally { loading.value = false; }
}

function toggleCollapse(type: string) {
    if (collapsedTypes.value.has(type)) {
        collapsedTypes.value.delete(type);
    } else {
        collapsedTypes.value.add(type);
    }
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

async function openDrawer(skill: SkillItem) {
    drawerLoading.value = true;
    drawerOpen.value = true;
    try {
        const res: any = await getSkill(skill.id);
        drawerSkill.value = {
            id: res.id, name: res.name, description: res.description,
            content: res.content, scope: res.scope, skill_type: res.skill_type,
            enabled: res.enabled,
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
            skill_type: drawerSkill.value.skill_type,
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

// ---- Create skill ----
const createDialogOpen = ref(false);
const createForm = ref({ name: "", description: "", content: "", skill_type: "workflow" });
const creating = ref(false);

function openCreateDialog() {
    createForm.value = { name: "", description: "", content: "", skill_type: "workflow" };
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

// AI 生成 Skill 内容
async function handleAiGenerateContent() {
    if (!createForm.value.name.trim()) {
        message.warning("请先输入 Skill 名称");
        return;
    }
    // 先创建 Skill（使用临时内容），然后生成内容
    creating.value = true;
    try {
        const res: any = await createSkill({
            name: createForm.value.name,
            description: createForm.value.description || "",
            skill_type: createForm.value.skill_type || "workflow",
            content: "（AI 生成中...）",
        });
        message.success("Skill 已创建，正在生成内容...");

        // 调用生成 prompt API
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

// ---- Role-Skill mapping ----
const roleSkillsMap = ref<Record<string, SkillItem[]>>({});
const roleLoading = ref(false);
const roleCollapsed = ref(false);

async function loadRoleSkills() {
    roleLoading.value = true;
    try {
        const res: any = await getRoleSkills();
        roleSkillsMap.value = res?.roles || {};
    } catch { /* ignore */ }
    finally { roleLoading.value = false; }
}

// Role skill mapping: add/remove
const roleSkillDialogOpen = ref(false);
const roleSkillDialogRole = ref("");
const roleSkillDialogSkillId = ref("");

function openAddRoleSkillDialog(role: string) {
    roleSkillDialogRole.value = role;
    roleSkillDialogSkillId.value = "";
    roleSkillDialogOpen.value = true;
}

async function handleAddRoleSkill() {
    if (!roleSkillDialogSkillId.value) { message.warning("请选择技能"); return; }
    try {
        const res: any = await addRoleSkill(roleSkillDialogRole.value, roleSkillDialogSkillId.value);
        if (res?.success) {
            message.success("已添加");
            roleSkillDialogOpen.value = false;
            loadRoleSkills();
        } else {
            message.error(res?.error || "添加失败");
        }
    } catch { message.error("添加失败"); }
}

async function handleRemoveRoleSkill(role: string, skillId: string) {
    try {
        await removeRoleSkill(role, skillId);
        message.success("已移除");
        loadRoleSkills();
    } catch { message.error("移除失败"); }
}

// Available skills for adding to role (exclude already mapped)
const availableSkillsForRole = computed(() => {
    const mapped = new Set((roleSkillsMap.value[roleSkillDialogRole.value] || []).map((s: any) => s.id));
    return skills.value.filter(s => !mapped.has(s.id) && s.enabled);
});

// ---- Member skills overview ----
const members = ref<MemberOption[]>([]);
const selectedMemberId = ref("");
const memberSkills = ref<MemberSkillItem[]>([]);
const memberLoading = ref(false);

async function loadMembers() {
    try {
        const res: any = await getMembers({ size: 500 });
        members.value = (res?.members || []).map((m: any) => ({ id: m.id, name: m.name }));
    } catch { /* ignore */ }
}

async function loadMemberSkills() {
    if (!selectedMemberId.value) { memberSkills.value = []; return; }
    memberLoading.value = true;
    try {
        const res: any = await getMemberSkillsWithSource(selectedMemberId.value);
        memberSkills.value = res?.skills || [];
    } catch { memberSkills.value = []; }
    finally { memberLoading.value = false; }
}

watch(selectedMemberId, () => loadMemberSkills());

// ---- Source label helpers ----
function sourceLabel(source: string): string {
    if (source.startsWith("role:")) {
        const roleName = source.replace("role:", "");
        const r = ROLE_OPTIONS.find(o => o.value === roleName);
        return r ? `角色：${r.label}` : `角色：${roleName}`;
    }
    if (source === "personal") return "个人";
    return "公共订阅";
}

function sourceColor(source: string): string {
    if (source.startsWith("role:")) return "blue";
    if (source === "personal") return "purple";
    return "green";
}

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

function getRoleLabelByValue(value: string): string {
    return ROLE_OPTIONS.find(o => o.value === value)?.label || value;
}

onMounted(() => { loadSkills(); loadRoleSkills(); loadMembers(); loadDirectories(); });

// ---- Skill 目录管理 ----
const directories = ref<any[]>([]);
const directoriesLoading = ref(false);

async function loadDirectories() {
    directoriesLoading.value = true;
    try {
        const res: any = await getSkillDirectories();
        directories.value = res?.directories || [];
    } catch { /* ignore */ }
    finally { directoriesLoading.value = false; }
}

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
            loadDirectories();
            loadSkills();
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
            loadDirectories();
            loadSkills();
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
        <!-- 区域一：技能库 -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-5">
                <div class="flex items-center gap-2">
                    <BookOpen :size="18" class="text-blue-600" />
                    <h3 class="text-base font-medium text-gray-800">技能库</h3>
                    <span class="text-xs text-gray-400">按类型分组管理所有技能</span>
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

            <VortSpin :spinning="loading">
                <div v-if="skills.length === 0 && !loading" class="text-center py-8 text-gray-400 text-sm">暂无技能</div>

                <div class="space-y-4">
                    <div v-for="typeConfig in SKILL_TYPES" :key="typeConfig.key">
                        <div v-if="groupedSkills[typeConfig.key]?.length"
                            class="border border-gray-100 rounded-lg overflow-hidden">
                            <!-- Group header -->
                            <div class="flex items-center justify-between px-4 py-2.5 bg-gray-50/80 cursor-pointer select-none hover:bg-gray-100/80 transition-colors"
                                @click="toggleCollapse(typeConfig.key)">
                                <div class="flex items-center gap-2">
                                    <component :is="typeConfig.icon" :size="15" class="text-gray-500" />
                                    <span class="text-sm font-medium text-gray-700">{{ typeConfig.label }}</span>
                                    <span class="text-xs text-gray-400">({{ groupedSkills[typeConfig.key].length }})</span>
                                    <span class="text-xs text-gray-400 hidden sm:inline">{{ typeConfig.desc }}</span>
                                </div>
                                <component :is="collapsedTypes.has(typeConfig.key) ? ChevronDown : ChevronUp" :size="14" class="text-gray-400" />
                            </div>
                            <!-- Group body -->
                            <div v-if="!collapsedTypes.has(typeConfig.key)" class="p-3">
                                <div class="grid grid-cols-1 lg:grid-cols-2 gap-2.5">
                                    <div v-for="skill in groupedSkills[typeConfig.key]" :key="skill.id"
                                        class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-100 hover:border-blue-200 transition-colors cursor-pointer"
                                        @click="openDrawer(skill)">
                                        <div class="min-w-0 flex-1">
                                            <div class="text-sm font-medium text-gray-800 truncate">{{ skill.name }}</div>
                                            <div class="text-xs text-gray-400 truncate mt-0.5">{{ skill.description || '暂无描述' }}</div>
                                        </div>
                                        <div class="flex items-center gap-2 flex-shrink-0 ml-3" @click.stop>
                                            <VortTag :color="scopeColor(skill.scope)" size="small">{{ scopeLabel(skill.scope) }}</VortTag>
                                            <VortSwitch :checked="skill.enabled" size="small" @change="handleToggle(skill)" />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </VortSpin>
        </div>

        <!-- 区域二：角色-技能映射 -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-2 cursor-pointer" @click="roleCollapsed = !roleCollapsed">
                    <Link :size="18" class="text-indigo-600" />
                    <h3 class="text-base font-medium text-gray-800">角色-技能映射</h3>
                    <span class="text-xs text-gray-400">创建 AI 员工时按角色自动推荐技能</span>
                </div>
                <component :is="roleCollapsed ? ChevronDown : ChevronUp" :size="14" class="text-gray-400 cursor-pointer" @click="roleCollapsed = !roleCollapsed" />
            </div>

            <VortSpin :spinning="roleLoading">
                <div v-if="!roleCollapsed" class="space-y-3">
                    <div v-for="role in ROLE_OPTIONS" :key="role.value"
                        class="border border-gray-100 rounded-lg px-4 py-3">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <component :is="ROLE_ICON_MAP[role.value] || Code" :size="16" class="text-gray-500" />
                                <span class="text-sm font-medium text-gray-700">{{ role.label }}</span>
                            </div>
                            <VortButton size="small" @click="openAddRoleSkillDialog(role.value)">
                                <Plus :size="12" class="mr-0.5" /> 添加
                            </VortButton>
                        </div>
                        <div class="flex flex-wrap gap-2 mt-2" v-if="roleSkillsMap[role.value]?.length">
                            <div v-for="skill in roleSkillsMap[role.value]" :key="skill.id"
                                class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-blue-50 text-blue-700 text-xs group">
                                <span>{{ skill.name }}</span>
                                <button class="opacity-0 group-hover:opacity-100 transition-opacity text-blue-400 hover:text-red-500"
                                    @click="handleRemoveRoleSkill(role.value, skill.id)">
                                    <Trash2 :size="11" />
                                </button>
                            </div>
                        </div>
                        <div v-else class="text-xs text-gray-400 mt-2">暂无映射的技能</div>
                    </div>
                </div>
            </VortSpin>
        </div>

        <!-- 区域三：Skill 目录管理 -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-2 cursor-pointer">
                    <FolderOpen :size="18" class="text-green-600" />
                    <h3 class="text-base font-medium text-gray-800">Skill 目录</h3>
                    <span class="text-xs text-gray-400">多目录扫描：内置 / 用户 / 企业</span>
                </div>
            </div>

            <VortSpin :spinning="directoriesLoading">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div v-for="dir in directories" :key="dir.key"
                        class="p-4 rounded-lg border border-gray-100 hover:border-gray-200">
                        <div class="flex items-center justify-between mb-2">
                            <div class="flex items-center gap-2">
                                <FolderOpen :size="16" class="text-gray-500" />
                                <span class="text-sm font-medium text-gray-800">{{ dir.name }}</span>
                            </div>
                            <VortTag :color="dir.enabled ? 'green' : 'default'" size="small">
                                {{ dir.enabled ? '启用' : '禁用' }}
                            </VortTag>
                        </div>
                        <div class="text-xs text-gray-400 mb-2">{{ dir.description }}</div>
                        <div class="text-xs text-gray-500">
                            <span class="bg-gray-100 px-2 py-0.5 rounded">{{ dir.skill_count || 0 }} 个 Skills</span>
                            <span v-if="dir.writable" class="ml-2 text-green-500">可写</span>
                        </div>
                        <div class="text-xs text-gray-400 mt-1 truncate" :title="dir.path">{{ dir.path }}</div>
                    </div>
                </div>
            </VortSpin>
        </div>

        <!-- 区域四：成员技能总览 -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center gap-2 mb-4">
                <User :size="18" class="text-purple-600" />
                <h3 class="text-base font-medium text-gray-800">成员技能总览</h3>
                <span class="text-xs text-gray-400">查看成员的生效技能（按来源分组）</span>
            </div>

            <div class="flex items-center gap-4 mb-4">
                <span class="text-sm text-gray-500 whitespace-nowrap">选择成员</span>
                <VortSelect v-model="selectedMemberId" placeholder="请选择成员" allow-clear class="w-[200px]">
                    <VortSelectOption v-for="m in members" :key="m.id" :value="m.id">{{ m.name }}</VortSelectOption>
                </VortSelect>
            </div>

            <VortSpin :spinning="memberLoading">
                <div v-if="!selectedMemberId" class="text-center py-6 text-gray-400 text-sm">请选择成员查看其技能配置</div>
                <div v-else-if="memberSkills.length === 0 && !memberLoading" class="text-center py-6 text-gray-400 text-sm">该成员暂无技能</div>
                <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-2.5">
                    <div v-for="skill in memberSkills" :key="skill.id"
                        class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-100">
                        <div class="min-w-0 flex-1">
                            <div class="text-sm font-medium text-gray-800 truncate">{{ skill.name }}</div>
                            <div class="text-xs text-gray-400 truncate mt-0.5">{{ skill.description || '暂无描述' }}</div>
                        </div>
                        <div class="flex items-center gap-2 flex-shrink-0 ml-3">
                            <VortTag :color="sourceColor(skill.source)" size="small">{{ sourceLabel(skill.source) }}</VortTag>
                            <span :class="skill.enabled ? 'text-green-500' : 'text-gray-400'" class="text-xs">
                                {{ skill.enabled ? '已启用' : '已禁用' }}
                            </span>
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
                        <VortFormItem label="类型">
                            <VortSelect v-if="drawerSkill.scope === 'public'" v-model="drawerSkill.skill_type" class="w-[200px]">
                                <VortSelectOption v-for="t in SKILL_TYPES" :key="t.key" :value="t.key">{{ t.label }}</VortSelectOption>
                            </VortSelect>
                            <VortTag v-else :color="SKILL_TYPE_MAP[drawerSkill.skill_type]?.color || 'default'">
                                {{ SKILL_TYPE_MAP[drawerSkill.skill_type]?.label || drawerSkill.skill_type }}
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

        <!-- Create skill dialog -->
        <VortDialog :open="createDialogOpen" title="新建公共技能" @update:open="createDialogOpen = $event">
            <VortForm label-width="80px">
                <VortFormItem label="名称" required>
                    <VortInput v-model="createForm.name" placeholder="如：代码审查规范" />
                </VortFormItem>
                <VortFormItem label="类型" required>
                    <VortSelect v-model="createForm.skill_type" class="w-[200px]">
                        <VortSelectOption v-for="t in SKILL_TYPES" :key="t.key" :value="t.key">{{ t.label }}</VortSelectOption>
                    </VortSelect>
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
                <!-- 直接导入 -->
                <div>
                    <label class="block text-sm text-gray-600 mb-2">直接导入</label>
                    <div class="flex gap-2">
                        <VortInput v-model="importUrl" placeholder="输入 GitHub 仓库或 SKILL.md 文件 URL" class="flex-1" />
                        <VortButton variant="primary" :loading="importLoading" @click="handleImportFromUrl">导入</VortButton>
                    </div>
                    <p class="text-xs text-gray-400 mt-1">支持仓库 URL（如 https://github.com/owner/repo）或 SKILL.md 文件 URL</p>
                </div>

                <div class="border-t border-gray-200 my-4"></div>

                <!-- 在线搜索 -->
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

                <!-- 搜索结果 -->
                <div v-if="searchResults.length > 0" class="space-y-2 max-h-[300px] overflow-y-auto">
                    <div v-for="result in searchResults" :key="result.repo"
                        class="flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:border-blue-200">
                        <div class="min-w-0 flex-1">
                            <div class="flex items-center gap-2">
                                <span class="text-sm font-medium text-gray-800">{{ result.name }}</span>
                                <span class="text-xs text-gray-400">⭐ {{ result.stars }}</span>
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

        <!-- Add role skill dialog -->
        <VortDialog :open="roleSkillDialogOpen" title="添加角色技能映射" @update:open="roleSkillDialogOpen = $event">
            <div class="space-y-4">
                <div>
                    <label class="block text-sm text-gray-600 mb-1">角色</label>
                    <div class="flex items-center gap-2">
                        <component :is="ROLE_ICON_MAP[roleSkillDialogRole] || Code" :size="16" class="text-gray-500" />
                        <span class="font-medium">{{ getRoleLabelByValue(roleSkillDialogRole) }}</span>
                    </div>
                </div>
                <div>
                    <label class="block text-sm text-gray-600 mb-1">选择技能</label>
                    <VortSelect v-model="roleSkillDialogSkillId" placeholder="请选择技能" class="w-full">
                        <VortSelectOption v-for="s in availableSkillsForRole" :key="s.id" :value="s.id">
                            {{ s.name }} <span class="text-gray-400">({{ SKILL_TYPE_MAP[s.skill_type]?.label || s.skill_type }})</span>
                        </VortSelectOption>
                    </VortSelect>
                </div>
            </div>
            <template #footer>
                <div class="flex justify-end gap-2">
                    <VortButton @click="roleSkillDialogOpen = false">取消</VortButton>
                    <VortButton variant="primary" @click="handleAddRoleSkill">添加</VortButton>
                </div>
            </template>
        </VortDialog>
    </div>
</template>
