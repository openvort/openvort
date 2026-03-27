<template>
    <Dialog
        :open="open"
        title="配置 Jenkins 凭证"
        :confirm-loading="submitting"
        ok-text="保存"
        @ok="handleSubmit"
        @update:open="$emit('update:open', $event)"
    >
        <p class="text-sm text-gray-500 mb-4">为实例「<span class="font-medium text-gray-700">{{ instanceName }}</span>」配置你的 Jenkins 账号。</p>
        <vort-form ref="formRef" :model="form" :rules="rules" label-width="120px">
            <vort-form-item label="Jenkins 用户名" name="username" required>
                <vort-input v-model="form.username" placeholder="你的 Jenkins 登录用户名" />
            </vort-form-item>
            <vort-form-item label="API Token" name="api_token" required>
                <vort-input-password v-model="form.api_token" placeholder="在 Jenkins 个人设置中生成" />
                <p class="mt-1 text-xs text-gray-400">Jenkins > 用户 > 设置 > API Token > 生成新 Token</p>
            </vort-form-item>
        </vort-form>
    </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { Dialog } from "@openvort/vort-ui";
import { z } from "zod";

const props = defineProps<{
    open: boolean;
    instanceName: string;
}>();

const emit = defineEmits<{
    (e: "update:open", val: boolean): void;
    (e: "submit", data: { username: string; api_token: string }): void;
}>();

const formRef = ref();
const submitting = ref(false);
const form = ref({ username: "", api_token: "" });

const rules = z.object({
    username: z.string().min(1, "请输入 Jenkins 用户名"),
    api_token: z.string().min(1, "请输入 API Token"),
});

watch(() => props.open, (val) => {
    if (val) {
        form.value = { username: "", api_token: "" };
        submitting.value = false;
    }
});

async function handleSubmit() {
    try { await formRef.value?.validate(); } catch { return; }
    submitting.value = true;
    try {
        emit("submit", { username: form.value.username.trim(), api_token: form.value.api_token.trim() });
    } finally {
        setTimeout(() => { submitting.value = false; }, 2000);
    }
}
</script>
