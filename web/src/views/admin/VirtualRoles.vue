<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import {
    getVirtualRoles, getVirtualRole, createVirtualRole, updateVirtualRole, deleteVirtualRole,
    getVirtualRoleSkills, bindVirtualRoleSkills,
    getSkills, generateRolePersonaPrompt,
} from "@/api";
import { message } from "@/components/vort/message";
import { Plus, Trash2, Save, Settings, Bot, Check } from "lucide-vue-next";

const router = useRouter();

interface VirtualRoleItem {
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

// 列表数据
const posts = ref<VirtualRoleItem[]>([]);
const loading = ref(false);
const allSkills = ref<SkillItem[]>([]);

// 分页
const pagination = ref({
    current: 1,
    pageSize: 30,
    total: 0,
});

// 弹窗状态
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"add" | "edit" | "view">("add");
const currentRole = ref<Partial<VirtualRoleItem>>({});
const submitting = ref(false);

// 技能绑定
const boundSkills = ref<SkillItem[]>([]);
const loadingSkills = ref(false);

// 加载角色列表
async function loadRoles() {
    loading.value = true;
    try {
        const res: any = await getVirtualRoles();
        posts.value = res.posts || [];
    } catch (e) {
        console.error("加载角色列表失败", e);
        message.error("加载角色列表失败");
    } finally {
        loading.value = false;
    }
}

// 加载所有技能
async function loadAllSkills() {
    try {
        const res: any = await getSkills();
        allSkills.value = res.skills || [];
    } catch (e) {
        console.error("加载技能列表失败", e);
    }
}

// 加载角色的绑定技能
async function loadBoundSkills(roleKey: string) {
    loadingSkills.value = true;
    try {
        const res: any = await getVirtualRoleSkills(roleKey);
        boundSkills.value = res.skills || [];
    } catch (e) {
        console.error("加载角色技能失败", e);
        boundSkills.value = [];
    } finally {
        loadingSkills.value = false;
    }
}

// 新增
function handleAdd() {
    drawerMode.value = "add";
    drawerTitle.value = "新增角色";
    currentRole.value = {
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

// 编辑
async function handleEdit(row: VirtualRoleItem) {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑角色";
    currentRole.value = { ...row };
    await loadBoundSkills(row.key);
    drawerVisible.value = true;
}

// 查看
async function handleView(row: VirtualRoleItem) {
    drawerMode.value = "view";
    drawerTitle.value = "角色详情";
    currentRole.value = { ...row };
    await loadBoundSkills(row.key);
    drawerVisible.value = true;
}

// 删除
async function handleDelete(row: VirtualRoleItem) {
    try {
        await deleteVirtualRole(row.id);
        message.success("删除成功");
        loadRoles();
    } catch (e: any) {
        message.error(e.message || "删除失败");
    }
}

// 保存
async function handleSave() {
    if (!currentRole.value.key?.trim()) {
        message.warning("请输入角色标识");
        return;
    }
    if (!currentRole.value.name?.trim()) {
        message.warning("请输入角色名称");
        return;
    }

    submitting.value = true;
    try {
        if (drawerMode.value === "add") {
            await createVirtualRole({
                key: currentRole.value.key,
                name: currentRole.value.name,
                description: currentRole.value.description || "",
                icon: currentRole.value.icon || "Bot",
                default_persona: currentRole.value.default_persona || "",
                default_auto_report: currentRole.value.default_auto_report || false,
                default_report_frequency: currentRole.value.default_report_frequency || "daily",
            });
            message.success("创建成功");
        } else {
            await updateVirtualRole(currentRole.value.id!, {
                name: currentRole.value.name,
                description: currentRole.value.description,
                icon: currentRole.value.icon,
                default_persona: currentRole.value.default_persona,
                default_auto_report: currentRole.value.default_auto_report,
                default_report_frequency: currentRole.value.default_report_frequency,
            });
            message.success("更新成功");
        }

        // 保存技能绑定
        await bindVirtualRoleSkills(currentRole.value.key, {
            skill_ids: boundSkills.value.map(s => s.id),
        });

        drawerVisible.value = false;
        loadRoles();
    } catch (e: any) {
        message.error(e.message || "操作失败");
    } finally {
        submitting.value = false;
    }
}

// 切换启用状态
async function handleToggle(row: VirtualRoleItem) {
    try {
        await updateVirtualRole(row.id, { enabled: !row.enabled });
        message.success(row.enabled ? "已禁用" : "已启用");
        loadRoles();
    } catch (e: any) {
        message.error(e.message || "操作失败");
    }
}

// AI 生成 Persona
async function handleAiGeneratePersona() {
    if (!currentRole.value.key) {
        message.warning("请先保存角色后再生成 Persona");
        return;
    }
    try {
        const res: any = await generateRolePersonaPrompt(currentRole.value.key);
        if (res?.prompt) {
            drawerVisible.value = false;
            router.push({ name: "chat", query: { prompt: res.prompt } });
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "生成失败");
    }
}

onMounted(() => {
    loadRoles();
    loadAllSkills();
});
</script>

<template>
    <div class="space-y-4">
        <!-- 搜索卡片 -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">AI 员工角色</h3>
                <vort-button variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增
                </vort-button>
            </div>
            <div class="text-sm text-gray-500">
                管理 AI 员工的角色模板，配置角色属性和推荐技能
            </div>
        </div>

        <!-- 表格卡片 -->
        <div class="bg-white rounded-xl p-6">
            <vort-table
                :data-source="posts"
                :loading="loading"
                :pagination="{
                    current: pagination.current,
                    pageSize: pagination.pageSize,
                    total: pagination.total,
                }"
                @change="handlePageChange"
            >
                <vort-table-column label="角色" :width="200">
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

        <!-- 抽屉 -->
        <vort-drawer v-model:open="drawerVisible" :title="drawerTitle" :width="600">
            <!-- 查看模式 -->
            <div v-if="drawerMode === 'view'" class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <span class="text-sm text-gray-400">角色标识</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentRole.key }}</div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">角色名称</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentRole.name }}</div>
                    </div>
                    <div class="col-span-2">
                        <span class="text-sm text-gray-400">描述</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentRole.description || '-' }}</div>
                    </div>
                    <div class="col-span-2">
                        <span class="text-sm text-gray-400">默认 Persona</span>
                        <div class="text-sm text-gray-800 mt-1 whitespace-pre-wrap">{{ currentRole.default_persona || '-' }}</div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">自动汇报</span>
                        <div class="mt-1">
                            <vort-tag :color="currentRole.default_auto_report ? 'green' : 'default'">
                                {{ currentRole.default_auto_report ? '启用' : '禁用' }}
                            </vort-tag>
                        </div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">汇报频率</span>
                        <div class="text-sm text-gray-800 mt-1">
                            {{ currentRole.default_report_frequency === 'daily' ? '每日' : '每周' }}
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

            <!-- 编辑/新增模式 -->
            <template v-else>
                <vort-form label-width="100px">
                    <vort-form-item label="角色标识" required>
                        <vort-input
                            v-model="currentRole.key"
                            placeholder="如 developer, pm"
                            :disabled="drawerMode === 'edit'"
                        />
                    </vort-form-item>
                    <vort-form-item label="角色名称" required>
                        <vort-input v-model="currentRole.name" placeholder="如 开发工程师" />
                    </vort-form-item>
                    <vort-form-item label="描述">
                        <vort-input v-model="currentRole.description" placeholder="一句话描述角色职能" />
                    </vort-form-item>
                    <vort-form-item label="默认 Persona">
                        <div class="space-y-2">
                            <vort-textarea
                                v-model="currentRole.default_persona"
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
                        <vort-switch v-model:checked="currentRole.default_auto_report" />
                        <span class="ml-2 text-sm text-gray-600">启用后自动生成汇报</span>
                    </vort-form-item>
                    <vort-form-item v-if="currentRole.default_auto_report" label="汇报频率">
                        <vort-select v-model="currentRole.default_report_frequency" style="width: 200px">
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
                    <div class="flex flex-wrap gap-2 max-h-48 overflow-y-auto">
                        <vort-checkbox
                            v-for="skill in allSkills"
                            :key="skill.id"
                            :checked="boundSkills.some(s => s.id === skill.id)"
                            @update:checked="(checked: boolean) => {
                                if (checked) {
                                    if (!boundSkills.some(s => s.id === skill.id)) {
                                        boundSkills.push(skill);
                                    }
                                } else {
                                    boundSkills = boundSkills.filter(s => s.id !== skill.id);
                                }
                            }"
                        >
                            <span class="text-sm">{{ skill.name }}</span>
                        </vort-checkbox>
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
