<template>
    <Dialog
        :open="open"
        title="新建视图"
        :confirm-loading="submitting"
        ok-text="创建"
        @ok="handleSubmit"
        @update:open="$emit('update:open', $event)"
    >
        <p class="text-sm text-gray-500 mb-4">创建一个 Jenkins 视图来组织和筛选 Job</p>
        <vort-form ref="formRef" :model="form" :rules="rules" label-width="120px">
            <vort-form-item label="视图名称" name="name" required>
                <vort-input v-model="form.name" placeholder="例如：frontend、backend" />
            </vort-form-item>
            <vort-form-item label="Job 过滤正则" name="include_regex">
                <vort-input v-model="form.include_regex" placeholder="例如：frontend-.* 或 .*-deploy" />
                <p class="text-xs text-gray-400 mt-1">匹配此正则的 Job 将自动包含在视图中，留空则创建空视图</p>
            </vort-form-item>
        </vort-form>
    </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { Dialog } from "@/components/vort";
import { z } from "zod";

const props = defineProps<{
    open: boolean;
}>();

const emit = defineEmits<{
    (e: "update:open", val: boolean): void;
    (e: "submit", data: { name: string; include_regex: string }): void;
}>();

const formRef = ref();
const submitting = ref(false);
const form = ref({ name: "", include_regex: "" });

const rules = z.object({
    name: z.string().min(1, "请输入视图名称"),
    include_regex: z.string().optional(),
});

watch(() => props.open, (val) => {
    if (val) {
        form.value = { name: "", include_regex: "" };
        submitting.value = false;
    }
});

async function handleSubmit() {
    try { await formRef.value?.validate(); } catch { return; }
    submitting.value = true;
    try {
        emit("submit", { name: form.value.name.trim(), include_regex: form.value.include_regex.trim() });
    } finally {
        setTimeout(() => { submitting.value = false; }, 2000);
    }
}
</script>
