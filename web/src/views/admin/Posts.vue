<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import {
    getVirtualRoles, getVirtualRole, createVirtualRole, updateVirtualRole, deleteVirtualRole,
    getVirtualRoleSkills, bindVirtualRoleSkills,
    getSkills, generateRolePersonaPrompt,
} from "@/api";
import { message } from "@/components/vort";
import { Plus, Trash2, Save, Settings, Bot, Check } from "lucide-vue-next";

const router = useRouter();

interface PostItem {
    id: string;
    key: string;
    name: string;
    description: string;
    icon: string;
    default_persona: string;
    default_auto_report: boolean;
    default_report_frequency: string;
    enabled: boolean;
    created_at?: string;
    updated_at?: string;
}

interface SkillItem {
    id: string;
    name: string;
    description: string;
    scope: string;
    skill_type: string;
}

// List data
const posts = ref<PostItem[]>([]);
const loading = ref(false);
const allSkills = ref<SkillItem[]>([]);

// Drawer state
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"add" | "edit" | "view">("add");
const currentPost = ref<Partial<PostItem>>({});
const submitting = ref(false);

// Skill binding
const boundSkills = ref<SkillItem[]>([]);
const loadingSkills = ref(false);

// Load posts list
async function loadPosts() {
    loading.value = true;
    try {
        const res: any = await getVirtualRoles();
        posts.value = res.posts || [];
    } catch (e) {
        console.error("加载岗位列表失败", e);
        message.error("加载岗位列表失败");
    } finally {
        loading.value = false;
    }
}

// Load all skills
async function loadAllSkills() {
    try {
        const res: any = await getSkills();
        allSkills.value = res.skills || [];
    } catch (e) {
        console.error("加载技能列表失败", e);
    }
}

// Load post's bound skills
async function loadBoundSkills(postKey: string) {
    loadingSkills.value = true;
    try {
        const res: any = await getVirtualRoleSkills(postKey);
        boundSkills.value = res.skills || [];
    } catch (e) {
        console.error("加载岗位技能失败", e);
        boundSkills.value = [];
    } finally {
        loadingSkills.value = false;
    }
}

// Add new
function handleAdd() {
    drawerMode.value = "add";
    drawerTitle.value = "新增岗位";
    currentPost.value = {
        key: "",
        name: "",
        description: "",
        icon: "Bot",
        default_persona: "",
        default_auto_report: false,
        default_report_frequency: "daily",
        enabled: true,
    };
    boundSkills.value = [];
    drawerVisible.value = true;
}

// Edit
async function handleEdit(row: PostItem) {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑岗位";
    currentPost.value = { ...row };
    await loadBoundSkills(row.key);
    drawerVisible.value = true;
}

// View
async function handleView(row: PostItem) {
    drawerMode.value = "view";
    drawerTitle.value = "岗位详情";
    currentPost.value = { ...row };
    await loadBoundSkills(row.key);
    drawerVisible.value = true;
}

// Delete
async function handleDelete(row: PostItem) {
    try {
        await deleteVirtualRole(row.id);
        message.success("删除成功");
        loadPosts();
    } catch (e: any) {
        message.error(e.message || "删除失败");
    }
}

// Save
async function handleSave() {
    if (!currentPost.value.key?.trim()) {
        message.warning("请输入岗位标识");
        return;
    }
    if (!currentPost.value.name?.trim()) {
        message.warning("请输入岗位名称");
        return;
    }

    submitting.value = true;
    try {
        if (drawerMode.value === "add") {
            await createVirtualRole({
                key: currentPost.value.key,
                name: currentPost.value.name,
                description: currentPost.value.description || "",
                icon: currentPost.value.icon || "Bot",
                default_persona: currentPost.value.default_persona || "",
                default_auto_report: currentPost.value.default_auto_report || false,
                default_report_frequency: currentPost.value.default_report_frequency || "daily",
            });
            message.success("创建成功");
        } else {
            await updateVirtualRole(currentPost.value.id!, {
                name: currentPost.value.name,
                description: currentPost.value.description,
                icon: currentPost.value.icon,
                default_persona: currentPost.value.default_persona,
                default_auto_report: currentPost.value.default_auto_report,
                default_report_frequency: currentPost.value.default_report_frequency,
            });
            message.success("更新成功");
        }

        // Save skill binding
        await bindVirtualRoleSkills(currentPost.value.key, {
            skill_ids: boundSkills.value.map(s => s.id),
        });

        drawerVisible.value = false;
        loadPosts();
    } catch (e: any) {
        message.error(e.message || "操作失败");
    } finally {
        submitting.value = false;
    }
}

// Toggle enabled
async function handleToggle(row: PostItem) {
    try {
        await updateVirtualRole(row.id, { enabled: !row.enabled });
        message.success(row.enabled ? "已禁用" : "已启用");
        loadPosts();
    } catch (e: any) {
        message.error(e.message || "操作失败");
    }
}

// AI generate Persona
async function handleAiGeneratePersona() {
    if (!currentPost.value.key) {
        message.warning("请先保存岗位后再生成 Persona");
        return;
    }
    try {
        const res: any = await generateRolePersonaPrompt(currentPost.value.key);
        if (res?.prompt) {
            drawerVisible.value = false;
            router.push({ name: "chat", query: { prompt: res.prompt } });
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "生成失败");
    }
}

onMounted(() => {
    loadPosts();
    loadAllSkills();
});
</script>

<template>
    <div class="space-y-4">
        <!-- Search card -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">AI 员工岗位</h3>
                <vort-button variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增
                </vort-button>
            </div>
            <div class="text-sm text-gray-500">
                管理 AI 员工的岗位模板，配置岗位属性和推荐技能
            </div>
        </div>

        <!-- Table card -->
        <div class="bg-white rounded-xl p-6">
            <vort-table :data-source="posts" :loading="loading" :pagination="false">
                <vort-table-column label="岗位" :width="200">
                    <template #default="{ row }">
                        <div>
                            <div class="font-medium text-gray-800">{{ row.name }}</div>
                            <div class="text-xs text-gray-400">{{ row.key }}</div>
                        </div>
                    </template>
                </vort-table-column>
                <vort-table-column label="描述" prop="description" />
                <vort-table-column label="默认自动汇报" :width="120">
                    <template #default="{ row }">
                        <vort-tag :color="row.default_auto_report ? 'green' : 'default'">
                            {{ row.default_auto_report ? '是' : '否' }}
                        </vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="汇报频率" :width="100">
                    <template #default="{ row }">
                        {{ row.default_report_frequency === 'daily' ? '每日' : '每周' }}
                    </template>
                </vort-table-column>
                <vort-table-column label="状态" :width="80">
                    <template #default="{ row }">
                        <vort-switch
                            :checked="row.enabled"
                            size="small"
                            @click="handleToggle(row)"
                        />
                    </template>
                </vort-table-column>
                <vort-table-column label="操作" :width="180" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2 whitespace-nowrap">
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleView(row)">详情</a>
                            <vort-divider type="vertical" />
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
                            <vort-divider type="vertical" />
                            <vort-popconfirm title="确认删除？" @confirm="handleDelete(row)">
                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                            </vort-popconfirm>
                        </div>
                    </template>
                </vort-table-column>
            </vort-table>
        </div>

        <!-- Drawer -->
        <vort-drawer v-model:open="drawerVisible" :title="drawerTitle" :width="600">
            <!-- View mode -->
            <div v-if="drawerMode === 'view'" class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <span class="text-sm text-gray-400">岗位标识</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentPost.key }}</div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">岗位名称</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentPost.name }}</div>
                    </div>
                    <div class="col-span-2">
                        <span class="text-sm text-gray-400">描述</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentPost.description || '-' }}</div>
                    </div>
                    <div class="col-span-2">
                        <span class="text-sm text-gray-400">默认 Persona</span>
                        <div class="text-sm text-gray-800 mt-1 whitespace-pre-wrap">{{ currentPost.default_persona || '-' }}</div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">自动汇报</span>
                        <div class="mt-1">
                            <vort-tag :color="currentPost.default_auto_report ? 'green' : 'default'">
                                {{ currentPost.default_auto_report ? '启用' : '禁用' }}
                            </vort-tag>
                        </div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">汇报频率</span>
                        <div class="text-sm text-gray-800 mt-1">
                            {{ currentPost.default_report_frequency === 'daily' ? '每日' : '每周' }}
                        </div>
                    </div>
                </div>

                <vort-divider />

                <div>
                    <span class="text-sm text-gray-400">推荐技能</span>
                    <div class="flex flex-wrap gap-2 mt-2">
                        <vort-tag v-for="skill in boundSkills" :key="skill.id" color="blue">
                            {{ skill.name }}
                        </vort-tag>
                        <span v-if="boundSkills.length === 0" class="text-sm text-gray-400">暂无绑定</span>
                    </div>
                </div>
            </div>

            <!-- Edit/Add mode -->
            <template v-else>
                <vort-form label-width="100px">
                    <vort-form-item label="岗位标识" required>
                        <vort-input
                            v-model="currentPost.key"
                            placeholder="如 developer, pm"
                            :disabled="drawerMode === 'edit'"
                        />
                    </vort-form-item>
                    <vort-form-item label="岗位名称" required>
                        <vort-input v-model="currentPost.name" placeholder="如 开发工程师" />
                    </vort-form-item>
                    <vort-form-item label="描述">
                        <vort-input v-model="currentPost.description" placeholder="一句话描述岗位职责" />
                    </vort-form-item>
                    <vort-form-item label="默认 Persona">
                        <div class="space-y-2">
                            <vort-textarea
                                v-model="currentPost.default_persona"
                                placeholder="设置 AI 员工的默认人设描述"
                                :rows="3"
                            />
                            <div class="flex justify-end">
                                <vort-button size="small" @click="handleAiGeneratePersona">
                                    <Bot :size="12" class="mr-1" /> AI 助手创建
                                </vort-button>
                            </div>
                        </div>
                    </vort-form-item>
                    <vort-form-item label="自动汇报">
                        <vort-switch v-model:checked="currentPost.default_auto_report" />
                        <span class="ml-2 text-sm text-gray-600">启用后自动生成汇报</span>
                    </vort-form-item>
                    <vort-form-item v-if="currentPost.default_auto_report" label="汇报频率">
                        <vort-select v-model="currentPost.default_report_frequency" style="width: 200px">
                            <vort-select-option value="daily">每日</vort-select-option>
                            <vort-select-option value="weekly">每周</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                </vort-form>

                <vort-divider />

                <div>
                    <div class="flex items-center justify-between mb-3">
                        <span class="text-sm font-medium text-gray-700">推荐技能</span>
                        <vort-spin v-if="loadingSkills" :spinning="true" :size="16" />
                    </div>
                    <div class="space-y-1 max-h-48 overflow-y-auto">
                        <div
                            v-for="skill in allSkills"
                            :key="skill.id"
                            class="flex items-start gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors"
                            :class="boundSkills.some(s => s.id === skill.id) ? 'bg-blue-50' : 'hover:bg-gray-50'"
                            @click="() => {
                                if (boundSkills.some(s => s.id === skill.id)) {
                                    boundSkills = boundSkills.filter(s => s.id !== skill.id);
                                } else {
                                    boundSkills.push(skill);
                                }
                            }"
                        >
                            <vort-checkbox
                                :checked="boundSkills.some(s => s.id === skill.id)"
                                class="mt-0.5"
                            />
                            <div class="min-w-0">
                                <div class="text-sm text-gray-800">{{ skill.name }}</div>
                                <div v-if="skill.description" class="text-xs text-gray-400 truncate">{{ skill.description }}</div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="flex justify-end gap-3 mt-6">
                    <vort-button @click="drawerVisible = false">取消</vort-button>
                    <vort-button variant="primary" :loading="submitting" @click="handleSave">确定</vort-button>
                </div>
            </template>
        </vort-drawer>
    </div>
</template>
