<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { useRouter } from "vue-router";
import {
    getMemberSkills, createPersonalSkill, updatePersonalSkill, deletePersonalSkill,
    getPublicSkills, subscribeMemberSkill, unsubscribeMemberSkill,
    updateMemberBio, generateMemberBioPrompt,
    getWorkAssignments, updateWorkAssignment, updateWorkAssignmentStatus, deleteWorkAssignment,
    getRemoteNodes, updateMember, getMember,
} from "@/api";
import { message, dialog } from "@/components/vort";
import { Bot, Plus, Trash2, Save, User, Globe, BookOpen, ClipboardList, Clock, Pause, Play, Square, Cpu } from "lucide-vue-next";

const props = defineProps<{
    open: boolean;
    memberId: string;
    memberName: string;
    memberAvatarUrl?: string;
    isVirtual?: boolean;
}>();

const emit = defineEmits<{
    (e: "update:open", val: boolean): void;
    (e: "assignments-changed"): void;
}>();

const router = useRouter();
const loading = ref(false);
const bio = ref("");
const personalSkills = ref<any[]>([]);
const disabledSkillIds = ref<Set<string>>(new Set());
const publicSkills = ref<any[]>([]);
const savingBio = ref(false);

// 工作节点
interface RemoteNodeOption {
    id: string;
    name: string;
    node_type: string;
    gateway_url: string;
    status: string;
}
const remoteNodes = ref<RemoteNodeOption[]>([]);
const boundNodeId = ref("");
const savingNodeBinding = ref(false);

async function loadRemoteNodes() {
    try {
        const res: any = await getRemoteNodes();
        remoteNodes.value = (res?.nodes || []).map((n: any) => ({
            id: n.id, name: n.name, node_type: n.node_type || "openclaw",
            gateway_url: n.gateway_url, status: n.status,
        }));
    } catch { /* ignore */ }
}

async function handleBindRemoteNode(nodeId: string) {
    savingNodeBinding.value = true;
    try {
        const res: any = await updateMember(props.memberId, { remote_node_id: nodeId } as any);
        if (res?.success) {
            boundNodeId.value = nodeId;
            message.success(nodeId ? "节点已绑定" : "已解除绑定");
        } else {
            message.error("绑定失败");
        }
    } catch {
        message.error("绑定失败");
    } finally {
        savingNodeBinding.value = false;
    }
}

// 工作安排
const activeTab = ref<"profile" | "work">("work");
const workAssignments = ref<any[]>([]);
const loadingWork = ref(false);
const statusFilter = ref("active");

const filterTabs = [
    { key: "active", label: "进行中" },
    { key: "all", label: "全部" },
    { key: "pending", label: "待执行" },
    { key: "ongoing", label: "持续进行" },
    { key: "paused", label: "已暂停" },
    { key: "completed", label: "已完成" },
];

const filteredAssignments = computed(() => {
    if (statusFilter.value === "all") return workAssignments.value;
    if (statusFilter.value === "active") {
        return workAssignments.value.filter((a: any) => a.status !== "completed" && a.status !== "cancelled");
    }
    return workAssignments.value.filter((a: any) => a.status === statusFilter.value);
});

const tabs = [
    { key: "work", label: "工作安排", icon: ClipboardList },
    { key: "profile", label: "个人档案", icon: User },
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
        const promises: Promise<any>[] = [
            getMemberSkills(props.memberId),
            getPublicSkills(),
        ];
        if (props.isVirtual) {
            promises.push(getMember(props.memberId));
            promises.push(loadRemoteNodes());
        }
        const [memberRes, publicRes, memberDetail]: any[] = await Promise.all(promises);
        personalSkills.value = memberRes?.personal || [];
        bio.value = memberRes?.bio || "";
        publicSkills.value = publicRes?.skills || [];

        const disabled = new Set<string>();
        for (const id of (memberRes?.disabled_public_skill_ids || [])) {
            disabled.add(id);
        }
        disabledSkillIds.value = disabled;

        if (props.isVirtual && memberDetail) {
            boundNodeId.value = memberDetail.remote_node_id || "";
        }
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

// ---- Public skill subscription (opt-out model: default all enabled) ----
async function toggleSubscribe(skill: any) {
    const isDisabled = disabledSkillIds.value.has(skill.id);
    try {
        if (isDisabled) {
            await subscribeMemberSkill(props.memberId, skill.id);
            const next = new Set(disabledSkillIds.value);
            next.delete(skill.id);
            disabledSkillIds.value = next;
            message.success("已启用");
        } else {
            await unsubscribeMemberSkill(props.memberId, skill.id);
            const next = new Set(disabledSkillIds.value);
            next.add(skill.id);
            disabledSkillIds.value = next;
            message.success("已关闭");
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "操作失败");
    }
}

// ---- Work assignment actions ----
const statusLabels: Record<string, string> = {
    pending: "待执行",
    in_progress: "执行中",
    completed: "已完成",
    ongoing: "持续进行",
    paused: "已暂停",
};

async function handlePause(assignment: any) {
    try {
        await updateWorkAssignmentStatus(assignment.id, "paused");
        assignment.status = "paused";
        message.success("已暂停");
        emit("assignments-changed");
    } catch { message.error("操作失败"); }
}

async function handleResume(assignment: any) {
    const target = assignment.source_type === "schedule" ? "ongoing" : "pending";
    try {
        await updateWorkAssignmentStatus(assignment.id, target);
        assignment.status = target;
        message.success("已恢复");
        emit("assignments-changed");
    } catch { message.error("操作失败"); }
}

async function handleComplete(assignment: any) {
    try {
        await updateWorkAssignmentStatus(assignment.id, "completed");
        assignment.status = "completed";
        message.success("已结束");
        emit("assignments-changed");
    } catch { message.error("操作失败"); }
}

async function handleDelete(assignment: any) {
    dialog.confirm({
        title: "删除工作安排",
        content: `确定删除「${assignment.title}」？关联的定时任务也会一并删除。`,
        okText: "删除",
        cancelText: "取消",
        okVariant: "danger",
        onOk: async () => {
            try {
                await deleteWorkAssignment(assignment.id);
                workAssignments.value = workAssignments.value.filter((a: any) => a.id !== assignment.id);
                message.success("已删除");
                emit("assignments-changed");
            } catch { message.error("删除失败"); }
        },
    });
}

// ---- Schedule execution detail dialog ----
const execDetailOpen = ref(false);
const execDetailAssignment = ref<any>(null);
const instructionEditing = ref(false);
const instructionDraft = ref("");
const instructionSaving = ref(false);

function handleAssignmentClick(assignment: any) {
    if (assignment.source_type === "schedule" && assignment.schedule_info) {
        execDetailAssignment.value = assignment;
        instructionEditing.value = false;
        instructionDraft.value = assignment.source_detail || "";
        execDetailOpen.value = true;
    }
}

function handleEditInstruction() {
    instructionDraft.value = execDetailAssignment.value?.source_detail || "";
    instructionEditing.value = true;
}

function handleCancelEditInstruction() {
    instructionDraft.value = execDetailAssignment.value?.source_detail || "";
    instructionEditing.value = false;
}

async function handleSaveInstruction() {
    const assignment = execDetailAssignment.value;
    if (!assignment) return;

    instructionSaving.value = true;
    try {
        await updateWorkAssignment(assignment.id, { source_detail: instructionDraft.value });
        assignment.source_detail = instructionDraft.value;

        const target = workAssignments.value.find((item: any) => item.id === assignment.id);
        if (target) {
            target.source_detail = instructionDraft.value;
        }

        instructionEditing.value = false;
        message.success("任务指令已保存");
        emit("assignments-changed");
    } catch (e: any) {
        message.error(e?.response?.data?.detail || e?.response?.data?.error || "保存失败");
    } finally {
        instructionSaving.value = false;
    }
}

function formatFullTime(iso: string | null): string {
    if (!iso) return "-";
    return new Date(iso).toLocaleString("zh-CN", {
        year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
}

const scheduleTypeLabels: Record<string, string> = {
    cron: "定时执行",
    interval: "固定间隔",
    once: "一次性",
};

const execStatusLabels: Record<string, string> = {
    success: "成功",
    failed: "失败",
    pending: "未执行",
};

const execStatusColors: Record<string, string> = {
    success: "bg-green-100 text-green-600",
    failed: "bg-red-100 text-red-600",
    pending: "bg-gray-100 text-gray-500",
};

const priorityColors: Record<string, string> = {
    low: "bg-gray-100 text-gray-500",
    normal: "bg-blue-100 text-blue-600",
    high: "bg-orange-100 text-orange-600",
    urgent: "bg-red-100 text-red-600",
};

const statusColors: Record<string, string> = {
    pending: "bg-amber-50 text-amber-600",
    in_progress: "bg-blue-100 text-blue-600",
    completed: "bg-green-100 text-green-600",
    ongoing: "bg-purple-100 text-purple-600",
    paused: "bg-gray-100 text-gray-500",
};

const sourceTypeLabels: Record<string, string> = {
    manual: "手动创建",
    chat: "聊天安排",
    code_task: "代码任务",
    schedule: "计划任务",
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
        <div v-show="activeTab === 'profile'">
        <VortSpin :spinning="loading">
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
                            <VortSwitch :checked="!disabledSkillIds.has(skill.id)" size="small" @change="toggleSubscribe(skill)" />
                        </div>
                    </div>
                </div>

                <!-- Remote work node (AI employees only) -->
                <div v-if="isVirtual" class="rounded-lg border border-gray-100 bg-white">
                    <div class="flex items-center gap-2 px-3 py-2.5 border-b border-gray-100 bg-gray-50/60 rounded-t-lg">
                        <Cpu :size="14" class="text-gray-400" />
                        <h4 class="text-sm font-medium text-gray-600">工作节点（Outbound）</h4>
                    </div>
                    <div class="px-3 py-3">
                        <div class="text-xs text-gray-400 mb-2">
                            绑定远程节点后，AI 员工可在远程电脑上执行编码、运行命令、操作文件等实际工作任务。
                        </div>
                        <VortSpin :spinning="savingNodeBinding">
                            <VortSelect
                                :model-value="boundNodeId"
                                placeholder="未绑定（选择节点后可远程执行任务）"
                                allow-clear
                                style="width: 100%"
                                @update:model-value="(val: string) => handleBindRemoteNode(val || '')"
                            >
                                <VortSelectOption v-for="node in remoteNodes" :key="node.id" :value="node.id">
                                    <div class="flex items-center gap-2">
                                        <span
                                            class="w-2 h-2 rounded-full flex-shrink-0"
                                            :class="['online', 'running'].includes(node.status) ? 'bg-green-500' : ['offline', 'stopped', 'error'].includes(node.status) ? 'bg-red-400' : 'bg-gray-300'"
                                        />
                                        <span>{{ node.name }}</span>
                                        <span class="text-xs px-1 py-0.5 rounded" :class="node.node_type === 'docker' ? 'bg-purple-50 text-purple-600' : 'bg-blue-50 text-blue-600'">
                                            {{ node.node_type === 'docker' ? 'Docker' : 'OpenClaw' }}
                                        </span>
                                        <span class="text-xs text-gray-400">
                                            {{ node.node_type === 'docker' ? (['running', 'stopped'].includes(node.status) ? (node.status === 'running' ? '运行中' : '已停止') : node.status) : node.gateway_url }}
                                        </span>
                                    </div>
                                </VortSelectOption>
                            </VortSelect>
                            <div class="mt-1.5 text-xs">
                                <router-link to="/remote-nodes" class="text-blue-600 hover:underline">管理节点</router-link>
                            </div>
                        </VortSpin>
                    </div>
                </div>
            </div>
        </VortSpin>
        </div>

        <!-- Tab: 工作安排 -->
        <div v-show="activeTab === 'work'">
        <!-- filter bar -->
        <div class="flex items-center gap-1 mb-3 flex-wrap">
            <button v-for="ft in filterTabs" :key="ft.key"
                class="px-2.5 py-1 text-xs rounded-full transition-colors cursor-pointer"
                :class="statusFilter === ft.key
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
                @click="statusFilter = ft.key">
                {{ ft.label }}
            </button>
        </div>
        <VortSpin :spinning="loadingWork">
            <div class="space-y-4">
                <div v-if="filteredAssignments.length === 0" class="text-xs text-gray-400 py-8 text-center bg-gray-50 rounded-lg">
                    {{ statusFilter === 'all' ? '暂无工作安排' : '暂无此状态的工作安排' }}
                </div>
                <div v-else class="space-y-3">
                    <div v-for="assignment in filteredAssignments" :key="assignment.id"
                        class="p-3 bg-gray-50 rounded-lg hover:bg-gray-100/80 transition-colors group cursor-pointer"
                        @click="handleAssignmentClick(assignment)">
                        <!-- row 1: title + status badge -->
                        <div class="flex items-start justify-between gap-2">
                            <div class="min-w-0 flex-1">
                                <div class="text-sm font-medium text-gray-800 truncate" :class="{ 'line-through opacity-50': assignment.status === 'completed' }">{{ assignment.title }}</div>
                                <div v-if="assignment.summary" class="text-xs text-gray-500 mt-0.5 line-clamp-2">{{ assignment.summary }}</div>
                            </div>
                            <div class="flex-shrink-0 flex items-center gap-1.5">
                                <span class="text-[10px] px-1.5 py-0.5 rounded" :class="priorityColors[assignment.priority] || priorityColors.normal">
                                    {{ assignment.priority === 'urgent' ? '紧急' : assignment.priority === 'high' ? '高' : assignment.priority === 'low' ? '低' : '普通' }}
                                </span>
                                <span class="text-[10px] px-1.5 py-0.5 rounded" :class="statusColors[assignment.status] || statusColors.pending">
                                    {{ statusLabels[assignment.status] || assignment.status }}
                                </span>
                            </div>
                        </div>
                        <!-- row 2: meta + actions -->
                        <div class="flex items-center justify-between mt-2">
                            <div class="flex items-center gap-3 text-[10px] text-gray-400">
                                <span v-if="assignment.source_type" class="flex items-center gap-0.5">
                                    <Clock :size="10" />
                                    {{ sourceTypeLabels[assignment.source_type] || assignment.source_type }}
                                </span>
                                <span v-if="assignment.last_action_at">
                                    最近行动: {{ new Date(assignment.last_action_at).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }) }}
                                </span>
                            </div>
                            <div class="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity" @click.stop>
                                <!-- pause / resume -->
                                <button v-if="assignment.status === 'paused'"
                                    class="p-1 rounded hover:bg-green-100 text-green-600 cursor-pointer" title="恢复"
                                    @click="handleResume(assignment)">
                                    <Play :size="13" />
                                </button>
                                <button v-else-if="assignment.status !== 'completed'"
                                    class="p-1 rounded hover:bg-amber-100 text-amber-600 cursor-pointer" title="暂停"
                                    @click="handlePause(assignment)">
                                    <Pause :size="13" />
                                </button>
                                <!-- complete -->
                                <button v-if="assignment.status !== 'completed'"
                                    class="p-1 rounded hover:bg-green-100 text-green-600 cursor-pointer" title="结束"
                                    @click="handleComplete(assignment)">
                                    <Square :size="13" />
                                </button>
                                <!-- delete -->
                                <button class="p-1 rounded hover:bg-red-100 text-red-500 cursor-pointer" title="删除"
                                    @click="handleDelete(assignment)">
                                    <Trash2 :size="13" />
                                </button>
                            </div>
                        </div>
                        <div v-if="assignment.plan" class="mt-2 pt-2 border-t border-gray-200">
                            <div class="text-[10px] text-gray-400 mb-1">执行计划:</div>
                            <div class="text-xs text-gray-600 whitespace-pre-line">{{ assignment.plan }}</div>
                        </div>
                        <!-- Schedule execution summary -->
                        <div v-if="assignment.schedule_info" class="mt-2 pt-2 border-t border-gray-200">
                            <div class="flex items-center gap-2 text-[10px]">
                                <span class="text-gray-400">{{ scheduleTypeLabels[assignment.schedule_info.schedule_type] || assignment.schedule_info.schedule_type }}</span>
                                <span class="px-1 py-0.5 rounded" :class="execStatusColors[assignment.schedule_info.last_status] || execStatusColors.pending">
                                    {{ execStatusLabels[assignment.schedule_info.last_status] || assignment.schedule_info.last_status }}
                                </span>
                                <span v-if="assignment.schedule_info.last_run_at" class="text-gray-400">
                                    {{ formatFullTime(assignment.schedule_info.last_run_at) }}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </VortSpin>
        </div>

        <!-- Schedule execution detail dialog (nested) -->
        <VortDialog :open="execDetailOpen" title="执行详情" :width="520" :footer="false" @update:open="execDetailOpen = $event">
            <template v-if="execDetailAssignment">
                <div class="space-y-4">
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <span class="text-xs text-gray-400">任务名称</span>
                            <div class="text-sm text-gray-800 mt-0.5">{{ execDetailAssignment.title }}</div>
                        </div>
                        <div>
                            <span class="text-xs text-gray-400">状态</span>
                            <div class="mt-0.5">
                                <span class="text-xs px-1.5 py-0.5 rounded" :class="statusColors[execDetailAssignment.status] || statusColors.pending">
                                    {{ statusLabels[execDetailAssignment.status] || execDetailAssignment.status }}
                                </span>
                            </div>
                        </div>
                    </div>

                    <template v-if="execDetailAssignment.schedule_info">
                        <div class="border-t border-gray-100 pt-3">
                            <h4 class="text-xs font-medium text-gray-600 mb-2">调度信息</h4>
                            <div class="grid grid-cols-2 gap-3">
                                <div>
                                    <span class="text-xs text-gray-400">调度类型</span>
                                    <div class="text-sm text-gray-800 mt-0.5">{{ scheduleTypeLabels[execDetailAssignment.schedule_info.schedule_type] || execDetailAssignment.schedule_info.schedule_type }}</div>
                                </div>
                                <div>
                                    <span class="text-xs text-gray-400">调度规则</span>
                                    <div class="text-sm text-gray-800 mt-0.5 font-mono">{{ execDetailAssignment.schedule_info.schedule }}</div>
                                </div>
                                <div>
                                    <span class="text-xs text-gray-400">启用状态</span>
                                    <div class="mt-0.5">
                                        <span class="text-xs px-1.5 py-0.5 rounded" :class="execDetailAssignment.schedule_info.enabled ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-500'">
                                            {{ execDetailAssignment.schedule_info.enabled ? '已启用' : '已禁用' }}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="border-t border-gray-100 pt-3">
                            <h4 class="text-xs font-medium text-gray-600 mb-2">最近执行记录</h4>
                            <div v-if="!execDetailAssignment.schedule_info.last_run_at" class="text-xs text-gray-400 py-3 text-center bg-gray-50 rounded">
                                尚未执行
                            </div>
                            <template v-else>
                                <div class="grid grid-cols-2 gap-3 mb-3">
                                    <div>
                                        <span class="text-xs text-gray-400">执行时间</span>
                                        <div class="text-sm text-gray-800 mt-0.5">{{ formatFullTime(execDetailAssignment.schedule_info.last_run_at) }}</div>
                                    </div>
                                    <div>
                                        <span class="text-xs text-gray-400">执行状态</span>
                                        <div class="mt-0.5">
                                            <span class="text-xs px-1.5 py-0.5 rounded" :class="execStatusColors[execDetailAssignment.schedule_info.last_status] || execStatusColors.pending">
                                                {{ execStatusLabels[execDetailAssignment.schedule_info.last_status] || execDetailAssignment.schedule_info.last_status }}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                <div v-if="execDetailAssignment.schedule_info.last_result">
                                    <span class="text-xs text-gray-400">执行结果</span>
                                    <div class="mt-1 p-3 bg-gray-50 rounded-lg text-xs text-gray-700 whitespace-pre-wrap max-h-[300px] overflow-y-auto leading-relaxed">{{ execDetailAssignment.schedule_info.last_result }}</div>
                                </div>
                            </template>
                        </div>
                    </template>

                    <div class="border-t border-gray-100 pt-3">
                        <div class="flex items-center justify-between gap-2">
                            <span class="text-xs text-gray-400">任务指令</span>
                            <div class="flex items-center gap-2">
                                <VortButton
                                    v-if="instructionEditing"
                                    size="small"
                                    :disabled="instructionSaving"
                                    @click="handleCancelEditInstruction"
                                >
                                    取消
                                </VortButton>
                                <VortButton
                                    v-if="instructionEditing"
                                    size="small"
                                    variant="primary"
                                    :loading="instructionSaving"
                                    @click="handleSaveInstruction"
                                >
                                    保存
                                </VortButton>
                                <VortButton
                                    v-else
                                    size="small"
                                    @click="handleEditInstruction"
                                >
                                    编辑
                                </VortButton>
                            </div>
                        </div>
                        <div v-if="instructionEditing" class="mt-2">
                            <VortTextarea
                                v-model="instructionDraft"
                                placeholder="请输入任务指令内容"
                                :rows="6"
                            />
                        </div>
                        <div v-else class="mt-1 p-3 bg-gray-50 rounded-lg text-xs text-gray-700 whitespace-pre-wrap min-h-[96px]">{{ execDetailAssignment.source_detail || "暂无任务指令" }}</div>
                    </div>
                </div>
            </template>
        </VortDialog>

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
