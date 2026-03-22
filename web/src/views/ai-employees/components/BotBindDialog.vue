<template>
    <Dialog
        :open="open"
        :title="`为「${memberName}」绑定 IM 身份`"
        :confirm-loading="submitting"
        :ok-text="step === 'channel' ? '下一步' : '测试并保存'"
        width="560px"
        @ok="handleOk"
        @update:open="handleClose"
    >
        <!-- Step 1: Select channel -->
        <div v-if="step === 'channel'" class="space-y-4">
            <div class="text-sm text-gray-500 mb-2">选择要绑定的 IM 通道</div>
            <div class="grid grid-cols-2 gap-3">
                <div
                    v-for="ch in availableChannels"
                    :key="ch.key"
                    class="cursor-pointer rounded-lg border-2 p-4 transition-colors flex items-center gap-3"
                    :class="selectedChannel === ch.key
                        ? 'border-blue-500 bg-blue-50'
                        : ch.bound
                            ? 'border-gray-100 bg-gray-50 opacity-50 cursor-not-allowed'
                            : 'border-gray-200 hover:border-gray-300'"
                    @click="!ch.bound && (selectedChannel = ch.key)"
                >
                    <img
                        v-if="ch.icon"
                        :src="ch.icon"
                        :alt="ch.label"
                        class="w-8 h-8 object-contain flex-shrink-0"
                    />
                    <div class="min-w-0">
                        <div class="text-sm font-medium" :class="selectedChannel === ch.key ? 'text-blue-700' : 'text-gray-700'">
                            {{ ch.label }}
                        </div>
                        <div v-if="ch.bound" class="text-xs text-gray-400 mt-0.5">已绑定</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Step 2: Fill credentials -->
        <div v-else class="space-y-4">
            <div class="flex items-center gap-2 mb-1">
                <button class="text-sm text-gray-400 hover:text-gray-600" @click="step = 'channel'">
                    &larr; 重新选择通道
                </button>
            </div>

            <div class="px-3 py-2.5 bg-blue-50 rounded-lg text-sm text-gray-600 leading-relaxed">
                在 IM 管理后台为该员工创建一个独立的机器人/应用，获取下方所需的凭证信息。
            </div>

            <vort-form ref="formRef" :model="credForm" :rules="credRules" label-width="120px">
                <vort-form-item
                    v-for="field in credFields"
                    :key="field.key"
                    :label="field.label"
                    :name="field.key"
                    :required="field.required"
                    :tooltip="field.description"
                >
                    <vort-input-password
                        v-if="field.secret"
                        v-model="credForm[field.key]"
                        :placeholder="field.placeholder || '请输入'"
                    />
                    <vort-input
                        v-else
                        v-model="credForm[field.key]"
                        :placeholder="field.placeholder || '请输入'"
                    />
                </vort-form-item>
            </vort-form>

            <vort-alert
                v-if="testResult"
                :type="testResult.ok ? 'success' : 'error'"
                :message="testResult.ok ? '连接成功' : '连接失败'"
                :description="testResult.message"
                show-icon
            />
        </div>
    </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { Dialog } from "@/components/vort";
import { message } from "@/components/vort";
import { z } from "zod";
import {
    getChannelBotCredentialFields,
    createChannelBot,
    testChannelBot,
    type CredentialField,
    type ChannelBotItem,
} from "@/api";

const props = defineProps<{
    open: boolean;
    memberId: string;
    memberName: string;
    existingBots: ChannelBotItem[];
}>();

const emit = defineEmits<{
    "update:open": [val: boolean];
    saved: [];
}>();

const CHANNEL_OPTIONS = [
    { key: "wecom", label: "企业微信", icon: "/icons/wecom.svg" },
    { key: "dingtalk", label: "钉钉", icon: "/icons/dingtalk.svg" },
    { key: "feishu", label: "飞书", icon: "/icons/feishu.svg" },
];

const step = ref<"channel" | "credentials">("channel");
const selectedChannel = ref("");
const submitting = ref(false);
const formRef = ref();
const credForm = ref<Record<string, string>>({});
const allCredFields = ref<Record<string, CredentialField[]>>({});
const testResult = ref<{ ok: boolean; message: string } | null>(null);

const availableChannels = computed(() =>
    CHANNEL_OPTIONS.map(ch => ({
        ...ch,
        bound: props.existingBots.some(b => b.channel_type === ch.key),
    }))
);

const credFields = computed(() => allCredFields.value[selectedChannel.value] || []);

const credRules = computed(() => {
    const shape: Record<string, z.ZodTypeAny> = {};
    for (const f of credFields.value) {
        shape[f.key] = f.required
            ? z.string().min(1, `请输入${f.label}`)
            : z.string().optional();
    }
    return z.object(shape);
});

watch(() => props.open, async (val) => {
    if (val) {
        step.value = "channel";
        selectedChannel.value = "";
        credForm.value = {};
        testResult.value = null;
        submitting.value = false;
        if (!Object.keys(allCredFields.value).length) {
            try {
                const res: any = await getChannelBotCredentialFields();
                allCredFields.value = res.fields || {};
            } catch { /* ignore */ }
        }
    }
});

watch(selectedChannel, () => {
    credForm.value = {};
    testResult.value = null;
});

function handleClose(val: boolean) {
    if (!val) emit("update:open", false);
}

async function handleOk() {
    if (step.value === "channel") {
        if (!selectedChannel.value) {
            message.warning("请选择一个通道");
            return;
        }
        step.value = "credentials";
        return;
    }

    try { await formRef.value?.validate(); } catch { return; }

    submitting.value = true;
    try {
        const res: any = await createChannelBot({
            channel_type: selectedChannel.value,
            member_id: props.memberId,
            credentials: credForm.value,
        });
        if (!res?.success) {
            message.error(res?.detail || "绑定失败");
            return;
        }

        const botId = res.bot?.id;
        if (botId) {
            testResult.value = null;
            try {
                const tr: any = await testChannelBot(botId);
                testResult.value = tr;
                if (!tr.ok) {
                    message.warning("Bot 已保存，但连接测试未通过，请检查凭证");
                }
            } catch {
                testResult.value = { ok: false, message: "测试请求失败" };
            }
        }

        message.success("IM 身份已绑定");
        emit("saved");
        emit("update:open", false);
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "绑定失败");
    } finally {
        submitting.value = false;
    }
}
</script>
