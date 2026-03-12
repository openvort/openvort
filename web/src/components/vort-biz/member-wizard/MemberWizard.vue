<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { ChevronLeft, ChevronRight, Check, User, Bot, Cpu, Webhook, ExternalLink } from "lucide-vue-next";
import { message } from "@/components/vort";
import type { Component } from "vue";

interface RoleOption {
    value: string;
    label: string;
    description: string;
}

interface RemoteNodeOption {
    id: string;
    name: string;
    node_type: string;
    gateway_url: string;
    status: string;
}

interface StepConfig {
    key: "type" | "role" | "info" | "capabilities";
    title: string;
}

const REAL_STEPS: StepConfig[] = [
    { key: "type", title: "选择类型" },
    { key: "info", title: "填写信息" },
];

const VIRTUAL_STEPS: StepConfig[] = [
    { key: "type", title: "选择类型" },
    { key: "role", title: "选择岗位" },
    { key: "info", title: "填写信息" },
    { key: "capabilities", title: "能力配置" },
];

const props = defineProps<{
    open: boolean;
    defaultMemberType?: "real" | "virtual";
}>();

const emit = defineEmits<{
    "update:open": [value: boolean];
    "complete": [data: any];
}>();

const currentStep = ref(1);

// 表单数据
const formData = ref({
    memberType: (props.defaultMemberType || "") as "" | "real" | "virtual",
    roles: [] as string[],
    name: "",
    email: "",
    phone: "",
    position: "",
    persona: "",
    autoReport: false,
    reportFrequency: "daily",
    remoteNodeId: "",
});

const steps = computed<StepConfig[]>(() => {
    const base = formData.value.memberType === "real" ? REAL_STEPS : VIRTUAL_STEPS;
    if (props.defaultMemberType) return base.filter(s => s.key !== "type");
    return base;
});

const totalSteps = computed(() => steps.value.length);
const currentStepKey = computed(() => steps.value[currentStep.value - 1]?.key || "type");
const currentStepTitle = computed(() => steps.value[currentStep.value - 1]?.title || "");

// 角色选项（从 API 加载）
const roleOptions = ref<RoleOption[]>([]);
const loadingRoles = ref(false);

async function loadRoleOptions() {
    loadingRoles.value = true;
    try {
        const { getVirtualRoles } = await import("@/api");
        const res: any = await getVirtualRoles(true);
        if (res?.posts) {
            roleOptions.value = res.posts.map((r: any) => ({
                value: r.key,
                label: r.name,
                description: r.description,
            }));
        }
    } catch (e) {
        console.error("加载岗位列表失败", e);
    } finally {
        loadingRoles.value = false;
    }
}

// 远程节点列表
const remoteNodes = ref<RemoteNodeOption[]>([]);

async function loadRemoteNodes() {
    try {
        const { getRemoteNodes } = await import("@/api");
        const res: any = await getRemoteNodes();
        remoteNodes.value = (res?.nodes || []).map((n: any) => ({
            id: n.id, name: n.name, node_type: n.node_type || "openclaw",
            gateway_url: n.gateway_url, status: n.status,
        }));
    } catch { /* ignore */ }
}

// 打开弹窗时加载数据
watch(() => props.open, (isOpen) => {
    if (isOpen) {
        loadRoleOptions();
        loadRemoteNodes();
    }
});

function resetForm() {
    currentStep.value = 1;
    formData.value = {
        memberType: props.defaultMemberType || "",
        roles: [],
        name: "",
        email: "",
        phone: "",
        position: "",
        persona: "",
        autoReport: false,
        reportFrequency: "daily",
        remoteNodeId: "",
    };
}

function handleClose() {
    resetForm();
    emit("update:open", false);
}

function nextStep() {
    const key = currentStepKey.value;

    if (key === "type") {
        if (!formData.value.memberType) {
            message.warning("请选择成员类型");
            return;
        }
    }
    if (key === "role") {
        if (formData.value.roles.length === 0) {
            message.warning("请至少选择一个岗位");
            return;
        }
    }
    if (key === "info") {
        if (!formData.value.name.trim()) {
            message.warning("请输入姓名");
            return;
        }
        if (formData.value.memberType === "real") {
            complete();
            return;
        }
    }
    if (key === "capabilities") {
        complete();
        return;
    }
    currentStep.value++;
}

function prevStep() {
    if (currentStep.value > 1) {
        currentStep.value--;
    }
}

async function complete() {
    const { createMember } = await import("@/api");

    const data: any = {
        name: formData.value.name,
        email: formData.value.email,
        phone: formData.value.phone,
        position: formData.value.position,
        is_account: false,
    };

    if (formData.value.memberType === "virtual") {
        const selectedPosts = formData.value.roles.map(role => role.trim()).filter(Boolean);
        data.is_virtual = true;
        data.virtual_role = selectedPosts[0] || "";
        data.posts = selectedPosts;
        data.bio = formData.value.persona;
        data.auto_report = formData.value.autoReport;
        data.report_frequency = formData.value.reportFrequency;
        if (formData.value.remoteNodeId) {
            data.remote_node_id = formData.value.remoteNodeId;
        }
    }

    try {
        const res: any = await createMember(data);
        if (res?.success) {
            message.success("成员创建成功");
            handleClose();
            emit("complete", res);
        } else {
            message.error(res?.error || "创建失败");
        }
    } catch (e) {
        message.error("创建失败");
    }
}
</script>

<template>
    <VortDialog
        :open="open"
        :title="`添加成员 - ${currentStepTitle}`"
        width="720px"
        :footer="false"
        body-max-height="70vh"
        @update:open="handleClose"
    >
        <!-- 步骤指示器 -->
        <div class="flex items-center justify-center mb-8">
            <div v-for="(stepCfg, idx) in steps" :key="stepCfg.key" class="flex items-center">
                <div
                    class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all duration-300"
                    :class="idx + 1 < currentStep
                        ? 'bg-blue-500 text-white'
                        : idx + 1 === currentStep
                            ? 'bg-blue-500 text-white'
                            : 'bg-gray-100 text-gray-400'"
                >
                    <Check v-if="idx + 1 < currentStep" :size="16" />
                    <span v-else>{{ idx + 1 }}</span>
                </div>
                <div
                    v-if="idx < steps.length - 1"
                    class="w-16 h-0.5 mx-2 transition-colors duration-300"
                    :class="idx + 1 < currentStep ? 'bg-blue-500' : 'bg-gray-200'"
                />
            </div>
        </div>

        <!-- 选择成员类型 -->
        <div v-if="currentStepKey === 'type'" class="space-y-4">
            <div class="text-center mb-6">
                <div class="text-lg font-medium text-gray-800">选择要添加的成员类型</div>
                <div class="text-sm text-gray-400 mt-1">选择成员的属性，以便我们为您提供更好的配置选项</div>
            </div>

            <div class="grid grid-cols-2 gap-4">
                <div
                    class="p-6 rounded-xl border-2 cursor-pointer transition-all"
                    :class="formData.memberType === 'real'
                        ? 'border-blue-400 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'"
                    @click="formData.memberType = 'real'"
                >
                    <div class="flex flex-col items-center text-center">
                        <div class="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mb-4">
                            <User :size="32" class="text-green-600" />
                        </div>
                        <div class="text-lg font-medium text-gray-800 mb-1">真实员工</div>
                        <div class="text-sm text-gray-500">团队中的真实成员，需要同步到系统的同事</div>
                        <div v-if="formData.memberType === 'real'" class="mt-3">
                            <Check :size="20" class="text-blue-500" />
                        </div>
                    </div>
                </div>

                <div
                    class="p-6 rounded-xl border-2 cursor-pointer transition-all"
                    :class="formData.memberType === 'virtual'
                        ? 'border-blue-400 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'"
                    @click="formData.memberType = 'virtual'"
                >
                    <div class="flex flex-col items-center text-center">
                        <div class="w-16 h-16 rounded-full bg-purple-100 flex items-center justify-center mb-4">
                            <Bot :size="32" class="text-purple-600" />
                        </div>
                        <div class="text-lg font-medium text-gray-800 mb-1">AI 员工</div>
                        <div class="text-sm text-gray-500">AI 数字员工，可以替你完成特定工作的智能助手</div>
                        <div v-if="formData.memberType === 'virtual'" class="mt-3">
                            <Check :size="20" class="text-blue-500" />
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 选择岗位（AI 员工） -->
        <div v-if="currentStepKey === 'role'" class="space-y-4">
            <div class="text-center mb-6">
                <div class="text-lg font-medium text-gray-800">选择岗位</div>
                <div class="text-sm text-gray-400 mt-1">为 AI 员工选择一个岗位</div>
            </div>

            <div class="grid grid-cols-2 gap-3 max-h-[400px] overflow-y-auto pr-1">
                <div
                    v-for="role in roleOptions"
                    :key="role.value"
                    class="p-4 rounded-xl border-2 cursor-pointer transition-all"
                    :class="formData.roles.includes(role.value)
                        ? 'border-blue-400 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'"
                    @click="
                        formData.roles.includes(role.value)
                            ? formData.roles = formData.roles.filter(r => r !== role.value)
                            : formData.roles.push(role.value)
                    "
                >
                    <div class="flex items-start gap-3">
                        <div class="flex-1">
                            <div class="flex items-center justify-between">
                                <div class="font-medium text-gray-800">{{ role.label }}</div>
                                <Check v-if="formData.roles.includes(role.value)" :size="18" class="text-blue-500" />
                            </div>
                            <div class="text-sm text-gray-500 mt-0.5">{{ role.description }}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 填写基本信息 -->
        <div v-if="currentStepKey === 'info'" class="space-y-4">
            <div class="text-center mb-6">
                <div class="text-lg font-medium text-gray-800">填写基本信息</div>
                <div class="text-sm text-gray-400 mt-1">请填写成员的基本信息</div>
            </div>

            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">
                        姓名 <span class="text-red-500">*</span>
                    </label>
                    <VortInput v-model="formData.name" placeholder="请输入姓名" />
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">邮箱</label>
                        <VortInput v-model="formData.email" placeholder="请输入邮箱" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">手机</label>
                        <VortInput v-model="formData.phone" placeholder="请输入手机号" />
                    </div>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">职位</label>
                    <VortInput v-model="formData.position" placeholder="请输入职位" />
                </div>

                <!-- AI 员工额外字段 -->
                <template v-if="formData.memberType === 'virtual'">
                    <div class="border-t border-gray-200 pt-4 mt-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">个人介绍（Persona）</label>
                            <VortTextarea
                                v-model="formData.persona"
                                placeholder="描述这个 AI 员工的性格、说话风格、工作方式..."
                                :rows="3"
                            />
                        </div>

                        <div class="flex items-center gap-2 mt-4">
                            <VortSwitch v-model:checked="formData.autoReport" />
                            <span class="text-sm text-gray-600">启用自动汇报</span>
                        </div>

                        <div v-if="formData.autoReport" class="mt-3">
                            <label class="block text-sm font-medium text-gray-700 mb-1">汇报频率</label>
                            <VortSelect v-model="formData.reportFrequency" style="width: 200px">
                                <VortSelectOption value="daily">每日</VortSelectOption>
                                <VortSelectOption value="weekly">每周</VortSelectOption>
                            </VortSelect>
                        </div>
                    </div>
                </template>
            </div>
        </div>

        <!-- 能力配置（AI 员工可选步骤） -->
        <div v-if="currentStepKey === 'capabilities'" class="space-y-4">
            <div class="text-center mb-6">
                <div class="text-lg font-medium text-gray-800">能力配置</div>
                <div class="text-sm text-gray-400 mt-1">为 AI 员工扩展工作能力，可跳过此步稍后配置</div>
            </div>

            <!-- Remote work node -->
            <div class="rounded-xl border-2 border-gray-200 p-5 space-y-3">
                <div class="flex items-center gap-2">
                    <div class="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center">
                        <Cpu :size="16" class="text-emerald-600" />
                    </div>
                    <div>
                        <div class="text-sm font-medium text-gray-800">远程工作节点</div>
                        <div class="text-xs text-gray-400">让 AI 员工拥有一台"工作电脑"</div>
                    </div>
                </div>
                <div class="text-sm text-gray-500 leading-relaxed">
                    绑定远程节点后，AI 员工可以在远程电脑上执行编码、运行命令、操作文件等实际工作任务。
                    适用于需要 AI 员工动手操作的场景，如代码开发、服务器运维、自动化部署等。
                </div>
                <div v-if="remoteNodes.length">
                    <VortSelect
                        v-model="formData.remoteNodeId"
                        placeholder="选择要绑定的远程节点（可选）"
                        allow-clear
                        style="width: 100%"
                    >
                        <VortSelectOption v-for="node in remoteNodes" :key="node.id" :value="node.id">
                            <div class="flex items-center gap-2">
                                <span
                                    class="w-2 h-2 rounded-full flex-shrink-0"
                                    :class="node.status === 'online' ? 'bg-green-500' : node.status === 'offline' ? 'bg-red-400' : 'bg-gray-300'"
                                />
                                <span>{{ node.name }}</span>
                                <span class="text-xs text-gray-400">{{ node.gateway_url }}</span>
                            </div>
                        </VortSelectOption>
                    </VortSelect>
                </div>
                <div v-else class="text-sm text-gray-400 flex items-center gap-1.5 py-1 px-3 bg-gray-50 rounded-lg">
                    暂无可用节点，可稍后在
                    <router-link to="/remote-nodes" class="text-blue-600 hover:underline inline-flex items-center gap-0.5" @click.stop>
                        远程节点管理 <ExternalLink :size="12" />
                    </router-link>
                    中配置
                </div>
            </div>

            <!-- Webhook / external connections -->
            <div class="rounded-xl border-2 border-gray-200 p-5 space-y-3">
                <div class="flex items-center gap-2">
                    <div class="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center">
                        <Webhook :size="16" class="text-indigo-600" />
                    </div>
                    <div>
                        <div class="text-sm font-medium text-gray-800">外部连接</div>
                        <div class="text-xs text-gray-400">让 AI 员工"听到"外部系统的事件</div>
                    </div>
                </div>
                <div class="text-sm text-gray-500 leading-relaxed">
                    通过 Webhook 接收外部系统（如 GitHub、GitLab、OpenClaw 等）推送的事件，AI 员工可以自动响应代码提交、
                    Issue 创建、IM 消息等事件并执行对应处理。适用于 CI/CD 集成、跨平台消息桥接等场景。
                </div>
                <div class="text-sm text-gray-400 flex items-center gap-1.5 py-1 px-3 bg-gray-50 rounded-lg">
                    创建完成后，可在
                    <router-link to="/webhooks" target="_blank" class="text-blue-600 hover:underline inline-flex items-center gap-0.5" @click.stop>
                        外部连接管理 <ExternalLink :size="12" />
                    </router-link>
                    中为该 AI 员工配置 Webhook
                </div>
            </div>
        </div>

        <!-- 底部按钮 -->
        <div class="flex items-center justify-between mt-8 pt-4 border-t border-gray-200">
            <VortButton v-if="currentStep > 1" @click="prevStep">
                <ChevronLeft :size="16" class="mr-1" /> 上一步
            </VortButton>
            <div v-else />

            <VortButton v-if="currentStep < totalSteps" variant="primary" @click="nextStep">
                下一步 <ChevronRight :size="16" class="ml-1" />
            </VortButton>
            <VortButton v-else variant="primary" @click="nextStep">
                完成创建
            </VortButton>
        </div>
    </VortDialog>
</template>
