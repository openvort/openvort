<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { Dialog as VortDialog, Button as VortButton, Input as VortInput, Textarea as VortTextarea } from "@/components/vort";

interface SketchEditData {
    id?: string;
    name: string;
    description: string;
}

const props = defineProps<{
    open: boolean;
    editData?: SketchEditData | null;
}>();

const emit = defineEmits<{
    "update:open": [value: boolean];
    submit: [data: { name: string; description: string }];
}>();

const name = ref("");
const description = ref("");
const submitting = ref(false);

const isEdit = computed(() => !!props.editData?.id);
const dialogTitle = computed(() => isEdit.value ? "编辑原型" : "新建原型");
const submitLabel = computed(() => isEdit.value ? "保存" : "开始生成");

watch(() => props.open, (val) => {
    if (val) {
        name.value = props.editData?.name || "";
        description.value = props.editData?.description || "";
    }
});

function handleSubmit() {
    if (!name.value.trim()) return;
    submitting.value = true;
    emit("submit", {
        name: name.value.trim(),
        description: description.value.trim(),
    });
    submitting.value = false;
}

function handleClose() {
    emit("update:open", false);
}
</script>

<template>
    <VortDialog :open="open" :title="dialogTitle" width="520px" @update:open="handleClose">
        <div class="flex flex-col gap-4 py-2">
            <div class="flex flex-col gap-1.5">
                <label class="text-sm font-medium text-gray-700">原型名称 <span class="text-red-500">*</span></label>
                <VortInput v-model="name" placeholder="如: 用户管理页面、订单详情..." />
            </div>

            <div class="flex flex-col gap-1.5">
                <label class="text-sm font-medium text-gray-700">界面描述</label>
                <VortTextarea
                    v-model="description"
                    placeholder="描述你想要的界面，包括布局、功能区域、交互方式等..."
                    :rows="5"
                />
                <p v-if="!isEdit" class="text-xs text-gray-400">描述越详细，AI 生成的原型越精准</p>
            </div>
        </div>

        <template #footer>
            <div class="flex justify-end gap-2">
                <VortButton @click="handleClose">取消</VortButton>
                <VortButton type="primary" :loading="submitting" :disabled="!name.trim()" @click="handleSubmit">
                    {{ submitLabel }}
                </VortButton>
            </div>
        </template>
    </VortDialog>
</template>
