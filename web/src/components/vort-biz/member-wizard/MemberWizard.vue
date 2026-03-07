<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { ChevronLeft, ChevronRight, Check, User, Bot } from "lucide-vue-next";
import { message } from "@/components/vort";
import type { Component } from "vue";

interface RoleOption {
    value: string;
    label: string;
    description: string;
}

interface SkillOption {
    id: string;
    name: string;
    description: string;
    checked: boolean;
    source: string;
}

interface StepConfig {
    key: "type" | "role" | "skill" | "info";
    title: string;
}

const REAL_STEPS: StepConfig[] = [
    { key: "type", title: "选择类型" },
    { key: "info", title: "填写信息" },
];

const VIRTUAL_STEPS: StepConfig[] = [
    { key: "type", title: "选择类型" },
    { key: "role", title: "选择岗位" },
    { key: "skill", title: "确认技能" },
    { key: "info", title: "填写信息" },
];

const props = defineProps<{
    open: boolean;
}>();

const emit = defineEmits<{
    "update:open": [value: boolean];
    "complete": [data: any];
}>();

const currentStep = ref(1);

// 表单数据
const formData = ref({
    memberType: "" as "" | "real" | "virtual",
    roles: [] as string[],
    skills: [] as SkillOption[],
    name: "",
    email: "",
    phone: "",
    position: "",
    persona: "",
    autoReport: false,
    reportFrequency: "daily",
});

const steps = computed<StepConfig[]>(() => {
    if (formData.value.memberType === "real") return REAL_STEPS;
    return VIRTUAL_STEPS;
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

// 技能选项（从角色推荐中获取）
const availableSkills = ref<SkillOption[]>([]);
const loadingSkills = ref(false);

async function loadRoleSkills() {
    if (formData.value.roles.length === 0) {
        availableSkills.value = [];
        return;
    }

    loadingSkills.value = true;
    try {
        const { getRoleSkills } = await import("@/api");
        const allSkills: SkillOption[] = [];

        for (const role of formData.value.roles) {
            const res: any = await getRoleSkills(role);
            if (res?.skills) {
                for (const skill of res.skills) {
                    const exists = allSkills.find(s => s.id === skill.id);
                    if (!exists) {
                        allSkills.push({
                            id: skill.id,
                            name: skill.name,
                            description: skill.description,
                            checked: true,
                            source: `role:${role}`,
                        });
                    }
                }
            }
        }

        availableSkills.value = allSkills;
    } catch (e) {
        console.error("加载岗位技能失败", e);
    } finally {
        loadingSkills.value = false;
    }
}

watch(() => formData.value.roles, async () => {
    if (currentStepKey.value === "skill") {
        await loadRoleSkills();
    }
});

watch(currentStepKey, async (key) => {
    if (key === "skill") {
        await loadRoleSkills();
    }
});

// 打开弹窗时加载角色列表
watch(() => props.open, (isOpen) => {
    if (isOpen) {
        loadRoleOptions();
    }
});

function resetForm() {
    currentStep.value = 1;
    formData.value = {
        memberType: "",
        roles: [],
        skills: [],
        name: "",
        email: "",
        phone: "",
        position: "",
        persona: "",
        autoReport: false,
        reportFrequency: "daily",
    };
    availableSkills.value = [];
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
    if (key === "skill") {
        formData.value.skills = availableSkills.value.filter(s => s.checked);
    }
    if (key === "info") {
        if (!formData.value.name.trim()) {
            message.warning("请输入姓名");
            return;
        }
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
        data.is_virtual = true;
        data.virtual_role = formData.value.roles[0] || "";
        data.skills = formData.value.skills.map(s => s.id);
        data.auto_report = formData.value.autoReport;
        data.report_frequency = formData.value.reportFrequency;
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
                <div class="text-sm text-gray-400 mt-1">为 AI 员工选择一个或多个岗位，每个岗位会推荐一组技能</div>
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

        <!-- 确认技能（AI 员工） -->
        <div v-if="currentStepKey === 'skill'" class="space-y-4">
            <div class="text-center mb-6">
                <div class="text-lg font-medium text-gray-800">确认技能</div>
                <div class="text-sm text-gray-400 mt-1">根据选择的岗位自动推荐了以下技能，您可以调整</div>
            </div>

            <VortSpin :spinning="loadingSkills">
                <div v-if="availableSkills.length" class="space-y-2 max-h-80 overflow-y-auto">
                    <div
                        v-for="skill in availableSkills"
                        :key="skill.id"
                        class="flex items-center gap-3 p-3 rounded-lg border border-gray-100 hover:bg-gray-50"
                    >
                        <VortCheckbox v-model:checked="skill.checked" />
                        <div class="flex-1">
                            <div class="font-medium text-gray-800">{{ skill.name }}</div>
                            <div class="text-sm text-gray-500">{{ skill.description }}</div>
                        </div>
                        <VortTag size="small" color="blue">{{ skill.source }}</VortTag>
                    </div>
                </div>
                <div v-else class="text-center py-8 text-gray-400">
                    暂无推荐技能，请先选择岗位
                </div>
            </VortSpin>
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
