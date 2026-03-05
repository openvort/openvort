<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { useRouter } from "vue-router";
import {
    getMemberSkills, createPersonalSkill, updatePersonalSkill, deletePersonalSkill,
    getPublicSkills, subscribeMemberSkill, unsubscribeMemberSkill,
    updateMemberBio, generateMemberBioPrompt,
    getWorkAssignments, updateWorkAssignmentStatus,
} from "@/api";
import { message, dialog } from "@openvort/vort-ui";
import { Bot, Plus, Trash2, Save, User, Globe, BookOpen, ClipboardList, Clock } from "lucide-vue-next";

const props = defineProps<{
    open: boolean;
    memberId: string;
    memberName: string;
    memberAvatarUrl?: string;
}>();

const emit = defineEmits<{
    (e: "update:open", val: boolean): void;
}>();

const router = useRouter();
const loading = ref(false);
const bio = ref("");
const personalSkills = ref<any[]>([]);
const subscribedSkillIds = ref<Set<string>>(new Set());
const publicSkills = ref<any[]>([]);
const savingBio = ref(false);

// 工作安排
const activeTab = ref<"profile" | "work">("profile");
const workAssignments = ref<any[]>([]);
const loadingWork = ref(false);

const tabs = [
    { key: "profile", label: "个人档案", icon: User },
    { key: "work", label: "工作安排", icon: ClipboardList },
];

async function loadWorkAssignments() {
    if (!props.memberId) return;
    loadingWork.value = true;
    try {
        const res: any = await getWorkAssignments({ assignee_member_id: props.memberId });
        workAssignments.value = res?.assignments || [];
    } catch { /* ignore */ }
    finally { loadingWork.value = false; }
}

async function loadData() {
    if (!props.memberId) return;
    loading.value = true;
    try {
        const [memberRes, publicRes]: any[] = await Promise.all([
            getMemberSkills(props.memberId),
            getPublicSkills(),
        ]);
        personalSkills.value = memberRes?.personal || [];
        bio.value = memberRes?.bio || "";
        publicSkills.value = publicRes?.skills || [];

        const subIds = new Set<string>();
        for (const s of (memberRes?.subscribed || [])) {
            subIds.add(s.id);
        }
        subscribedSkillIds.value = subIds;
    } catch { /* ignore */ }
    finally { loading.value = false; }
}

watch(() => props.open, (val) => {
    if (val && props.memberId) {
        loadData();
        if (activeTab.value === "work") {
            loadWorkAssignments();
        }
    }
});

watch(activeTab, (tab) => {
    if (tab === "work") {
        loadWorkAssignments();
    }
});

// ---- Bio ----
async function handleSaveBio() {
    savingBio.value = true;
    try {
        await updateMemberBio(props.memberId, bio.value);
        message.success("简介已保存");
    } catch {
        message.error("保存失败");
    } finally {
        savingBio.value = false;
    }
}

async function handleAiGenerateBio() {
    try {
        const res: any = await generateMemberBioPrompt(props.memberId);
        if (res?.prompt) {
            emit("update:open", false);
            router.push({ name: "chat", query: { prompt: res.prompt } });
        }
    } catch {
        message.error("生成失败");
    }
}

// ---- Personal skill CRUD ----
const skillDrawerOpen = ref(false);
const skillDrawerMode = ref<"add" | "edit">("add");
const skillForm = ref({ id: "", name: "", description: "", content: "" });
const skillSaving = ref(false);

function openAddSkill() {
    skillDrawerMode.value = "add";
    skillForm.value = { id: "", name: "", description: "", content: "" };
    skillDrawerOpen.value = true;
}

function openEditSkill(skill: any) {
    skillDrawerMode.value = "edit";
    skillForm.value = { id: skill.id, name: skill.name, description: skill.description, content: skill.content || "" };
    skillDrawerOpen.value = true;
}

async function handleSaveSkill() {
    if (!skillForm.value.name.trim()) {
        message.error("请输入名称");
        return;
    }
    skillSaving.value = true;
    try {
        if (skillDrawerMode.value === "add") {
            await createPersonalSkill(props.memberId, {
                name: skillForm.value.name,
                description: skillForm.value.description,
                content: skillForm.value.content,
            });
        } else {
            await updatePersonalSkill(skillForm.value.id, {
                name: skillForm.value.name,
                description: skillForm.value.description,
                content: skillForm.value.content,
            });
        }
        message.success("保存成功");
        skillDrawerOpen.value = false;
        loadData();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "保存失败");
    } finally {
        skillSaving.value = false;
    }
}

function handleDeleteSkill(skill: any) {
    dialog.confirm({
        title: `确认删除「${skill.name}」？`,
        onOk: async () => {
            try {
                await deletePersonalSkill(skill.id);
                message.success("已删除");
                loadData();
            } catch {
                message.error("删除失败");
            }
        },
    });
}

// ---- Public skill subscription ----
async function toggleSubscribe(skill: any) {
    const isSubscribed = subscribedSkillIds.value.has(skill.id);
    try {
        if (isSubscribed) {
            await unsubscribeMemberSkill(props.memberId, skill.id);
            const next = new Set(subscribedSkillIds.value);
            next.delete(skill.id);
            subscribedSkillIds.value = next;
            message.success("已取消订阅");
        } else {
            await subscribeMemberSkill(props.memberId, skill.id);
            const next = new Set(subscribedSkillIds.value);
            next.add(skill.id);
            subscribedSkillIds.value = next;
            message.success("已订阅");
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "操作失败");
    }
}

// ---- Work assignment actions ----
const statusOptions = [
    { value: "pending", label: "待处理" },
    { value: "in_progress", label: "进行中" },
    { value: "completed", label: "已完成" },
    { value: "ongoing", label: "持续进行" },
];

async function handleUpdateStatus(assignment: any, newStatus: string) {
    try {
        await updateWorkAssignmentStatus(assignment.id, newStatus);
        assignment.status = newStatus;
        message.success("状态已更新");
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "更新失败");
    }
}

const priorityColors: Record<string, string> = {
    low: "bg-gray-100 text-gray-500",
    normal: "bg-blue-100 text-blue-600",
    high: "bg-orange-100 text-orange-600",
    urgent: "bg-red-100 text-red-600",
};

const statusColors: Record<string, string> = {
    pending: "bg-gray-100 text-gray-600",
    in_progress: "bg-blue-100 text-blue-600",
    completed: "bg-green-100 text-green-600",
    ongoing: "bg-purple-100 text-purple-600",
};

const sourceTypeLabels: Record<string, string> = {
    manual: "手动创建",
    chat: "聊天安排",
    code_task: "代码任务",
    schedule: "定时任务",
};
</script>

<template>
    <VortDrawer :open="open" :title="`${memberName} · 成员档案`" :width="520" @update:open="emit('update:open', $event)">
        <!-- Tabs -->
        <div class="flex border-b border-gray-200 mb-4 -mx-6 px-6">
            <button v-for="tab in tabs" :key="tab.key"
                class="flex items-center gap-1.5 px-4 py-2.5 text-sm border-b-2 transition-colors -mb-px"
                :class="activeTab === tab.key
                    ? 'border-blue-500 text-blue-600 font-medium'
                    : 'border-transparent text-gray-500 hover:text-gray-700'"
                @click="activeTab = tab.key as any">
                <component :is="tab.icon" :size="14" />
                {{ tab.label }}
            </button>
        </div>

        <!-- Tab: 个人档案 -->
        <VortSpin :spinning="loading" v-show="activeTab === 'profile'">
            <div class="space-y-6">
                <!-- Avatar + name -->
                <div class="flex items-center gap-3">
                    <div class="w-14 h-14 rounded-full flex items-center justify-center overflow-hidden"
                        :class="memberAvatarUrl ? '' : 'bg-gray-100'">
                        <img v-if="memberAvatarUrl" :src="memberAvatarUrl" class="w-full h-full object-cover" />
                        <span v-else class="text-xl font-medium text-gray-400">{{ (memberName || '?')[0] }}</span>
                    </div>
                    <div>
                        <h3 class="text-base font-medium text-gray-800">{{ memberName }}</h3>
                        <span class="text-xs text-gray-400">成员 AI 代理</span>
                    </div>
                </div>

                <!-- Bio -->
                <div>
                    <div class="flex items-center justify-between mb-2">
                        <h4 class="text-sm font-medium text-gray-600">个人简介</h4>
                        <div class="flex items-center gap-2">
                            <VortButton size="small" @click="handleAiGenerateBio">
                                <Bot :size="12" class="mr-1" /> AI 助手创建
                            </VortButton>
                            <VortButton size="small" variant="primary" :loading="savingBio" @click="handleSaveBio">
                                <Save :size="12" class="mr-1" /> 保存
                            </VortButton>
                        </div>
                    </div>
                    <VortTextarea v-model="bio" placeholder="描述这位成员的角色、专长和个性特点..." :rows="3" />
                </div>

                <!-- Personal skills -->
                <div>
                    <div class="flex items-center justify-between mb-2">
                        <h4 class="text-sm font-medium text-gray-600">个人技能</h4>
                        <VortButton size="small" @click="openAddSkill">
                            <Plus :size="12" class="mr-1" /> 添加
                        </VortButton>
                    </div>
                    <div v-if="personalSkills.length === 0" class="text-xs text-gray-400 py-4 text-center bg-gray-50 rounded-lg">
                        暂无个人技能，点击添加
                    </div>
                    <div v-else class="space-y-2">
                        <div v-for="skill in personalSkills" :key="skill.id"
                            class="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer"
                            @click="openEditSkill(skill)">
                            <div class="min-w-0 flex-1">
                                <div class="text-sm text-gray-800 truncate">{{ skill.name }}</div>
                                <div v-if="skill.description" class="text-xs text-gray-400 truncate">{{ skill.description }}</div>
                            </div>
                            <div class="flex-shrink-0 ml-2" @click.stop>
                                <VortPopconfirm title="确认删除？" @confirm="handleDeleteSkill(skill)">
                                    <a class="text-gray-400 hover:text-red-500 cursor-pointer"><Trash2 :size="14" /></a>
                                </VortPopconfirm>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Public skills subscription -->
                <div v-if="publicSkills.length > 0">
                    <h4 class="text-sm font-medium text-gray-600 mb-2">公共技能订阅</h4>
                    <div class="space-y-2">
                        <div v-for="skill in publicSkills" :key="skill.id"
                            class="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg">
                            <div class="flex items-center gap-2 min-w-0">
                                <Globe :size="14" class="text-green-500 flex-shrink-0" />
                                <div class="min-w-0">
                                    <div class="text-sm text-gray-800 truncate">{{ skill.name }}</div>
                                    <div v-if="skill.description" class="text-xs text-gray-400 truncate">{{ skill.description }}</div>
                                </div>
                            </div>
                            <VortSwitch :checked="subscribedSkillIds.has(skill.id)" size="small" @change="toggleSubscribe(skill)" />
                        </div>
                    </div>
                </div>
            </div>
        </VortSpin>

        <!-- Tab: 工作安排 -->
        <VortSpin :spinning="loadingWork" v-show="activeTab === 'work'">
            <div class="space-y-4">
                <div v-if="workAssignments.length === 0" class="text-xs text-gray-400 py-8 text-center bg-gray-50 rounded-lg">
                    暂无工作安排
                </div>
                <div v-else class="space-y-3">
                    <div v-for="assignment in workAssignments" :key="assignment.id"
                        class="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                        <div class="flex items-start justify-between gap-2 mb-2">
                            <div class="min-w-0 flex-1">
                                <div class="text-sm font-medium text-gray-800 truncate">{{ assignment.title }}</div>
                                <div v-if="assignment.summary" class="text-xs text-gray-500 mt-0.5 line-clamp-2">{{ assignment.summary }}</div>
                            </div>
                            <div class="flex-shrink-0 flex items-center gap-1.5">
                                <span class="text-[10px] px-1.5 py-0.5 rounded" :class="priorityColors[assignment.priority] || priorityColors.normal">
                                    {{ assignment.priority === 'urgent' ? '紧急' : assignment.priority === 'high' ? '高' : assignment.priority === 'low' ? '低' : '普通' }}
                                </span>
                                <span class="text-[10px] px-1.5 py-0.5 rounded" :class="statusColors[assignment.status] || statusColors.pending">
                                    {{ statusOptions.find(s => s.value === assignment.status)?.label || assignment.status }}
                                </span>
                            </div>
                        </div>
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-3 text-[10px] text-gray-400">
                                <span v-if="assignment.source_type" class="flex items-center gap-0.5">
                                    <Clock :size="10" />
                                    {{ sourceTypeLabels[assignment.source_type] || assignment.source_type }}
                                </span>
                                <span v-if="assignment.last_action_at">
                                    最近行动: {{ new Date(assignment.last_action_at).toLocaleDateString() }}
                                </span>
                            </div>
                            <VortSelect
                                :value="assignment.status"
                                size="small"
                                style="width: 90px"
                                @change="handleUpdateStatus(assignment, $event)">
                                <VortSelectOption v-for="opt in statusOptions" :key="opt.value" :value="opt.value" :label="opt.label" />
                            </VortSelect>
                        </div>
                        <div v-if="assignment.plan" class="mt-2 pt-2 border-t border-gray-200">
                            <div class="text-[10px] text-gray-400 mb-1">执行计划:</div>
                            <div class="text-xs text-gray-600 whitespace-pre-line">{{ assignment.plan }}</div>
                        </div>
                    </div>
                </div>
            </div>
        </VortSpin>

        <!-- Personal skill edit drawer (nested) -->
        <VortDialog :open="skillDrawerOpen" :title="skillDrawerMode === 'add' ? '新增个人技能' : '编辑个人技能'" :width="480" @update:open="skillDrawerOpen = $event">
            <VortForm label-width="60px">
                <VortFormItem label="名称" required>
                    <VortInput v-model="skillForm.name" placeholder="如：Python 开发、项目管理" />
                </VortFormItem>
                <VortFormItem label="描述">
                    <VortInput v-model="skillForm.description" placeholder="简短描述" />
                </VortFormItem>
                <VortFormItem label="内容">
                    <VortTextarea v-model="skillForm.content"
                        placeholder="详细描述该成员在此技能方面的能力和经验..." :rows="8"
                        style="font-family: monospace; font-size: 13px;" />
                </VortFormItem>
            </VortForm>
            <template #footer>
                <div class="flex justify-end gap-2">
                    <VortButton @click="skillDrawerOpen = false">取消</VortButton>
                    <VortButton variant="primary" :loading="skillSaving" @click="handleSaveSkill">保存</VortButton>
                </div>
            </template>
        </VortDialog>
    </VortDrawer>
</template>
