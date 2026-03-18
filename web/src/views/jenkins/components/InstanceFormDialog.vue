<template>
    <Dialog
        :open="open"
        :title="editInstance ? '编辑实例' : '添加 Jenkins 实例'"
        :confirm-loading="submitting"
        :ok-text="editInstance ? '保存' : '添加'"
        @ok="handleSubmit"
        @update:open="$emit('update:open', $event)"
    >
        <vort-form ref="formRef" :model="form" :rules="rules" label-width="120px">
            <vort-form-item label="实例名称" name="name" required>
                <vort-input v-model="form.name" placeholder="如「生产环境」" />
            </vort-form-item>
            <vort-form-item label="Jenkins URL" name="url" required>
                <vort-input v-model="form.url" placeholder="http://jenkins.company.com:8080" />
            </vort-form-item>
            <vort-form-item label="验证 SSL">
                <vort-switch v-model:checked="form.verify_ssl" />
            </vort-form-item>
            <vort-form-item label="设为默认">
                <vort-switch v-model:checked="form.is_default" />
            </vort-form-item>
        </vort-form>
    </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { Dialog } from "@/components/vort";
import { z } from "zod";
import type { JenkinsInstance } from "../types";

const props = defineProps<{
    open: boolean;
    editInstance: JenkinsInstance | null;
}>();

const emit = defineEmits<{
    (e: "update:open", val: boolean): void;
    (e: "submit", data: { name: string; url: string; verify_ssl: boolean; is_default: boolean }): void;
}>();

const formRef = ref();
const submitting = ref(false);
const form = ref({ name: "", url: "", verify_ssl: true, is_default: false });

const rules = z.object({
    name: z.string().min(1, "请输入实例名称"),
    url: z.string().min(1, "请输入 Jenkins URL"),
    verify_ssl: z.boolean().optional(),
    is_default: z.boolean().optional(),
});

watch(() => props.open, (val) => {
    if (val) {
        if (props.editInstance) {
            form.value = {
                name: props.editInstance.name,
                url: props.editInstance.url,
                verify_ssl: props.editInstance.verify_ssl,
                is_default: props.editInstance.is_default,
            };
        } else {
            form.value = { name: "", url: "", verify_ssl: true, is_default: false };
        }
        submitting.value = false;
    }
});

async function handleSubmit() {
    try { await formRef.value?.validate(); } catch { return; }
    submitting.value = true;
    try {
        emit("submit", { ...form.value });
    } finally {
        setTimeout(() => { submitting.value = false; }, 2000);
    }
}
</script>
