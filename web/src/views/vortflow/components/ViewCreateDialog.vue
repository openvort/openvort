<script setup lang="ts">
import { ref, watch } from "vue";
import { Dialog, Button, Input, Radio, RadioGroup } from "@/components/vort";

const open = defineModel<boolean>("open", { default: false });

const emit = defineEmits<{
    create: [data: { name: string; scope: "personal" | "shared" }];
}>();

const name = ref("");
const scope = ref<"personal" | "shared">("personal");
const nameError = ref("");

watch(open, (v) => {
    if (v) {
        name.value = "";
        scope.value = "personal";
        nameError.value = "";
    }
});

watch(name, () => {
    if (nameError.value) nameError.value = "";
});

const handleSave = () => {
    const trimmed = name.value.trim();
    if (!trimmed) {
        nameError.value = "请输入视图名称";
        return;
    }
    if (trimmed.length > 20) {
        nameError.value = "名称不超过 20 个字";
        return;
    }
    emit("create", { name: trimmed, scope: scope.value });
    open.value = false;
};
</script>

<template>
    <Dialog v-model:open="open" title="新建视图" width="480px">
        <div class="create-view-form">
            <div class="form-field">
                <label class="field-label required">视图名称</label>
                <Input
                    v-model="name"
                    placeholder="输入视图名称 (20 个字以内)"
                    :status="nameError ? 'error' : undefined"
                    allow-clear
                    :maxlength="20"
                    show-count
                />
                <span v-if="nameError" class="field-error">{{ nameError }}</span>
            </div>

            <div class="form-field">
                <label class="field-label required">视图类型</label>
                <RadioGroup v-model="scope" class="scope-radios">
                    <Radio value="personal">
                        <span>保存为个人视图，仅为个人可见</span>
                    </Radio>
                    <Radio value="shared">
                        <span>保存公共视图，所有成员可见</span>
                    </Radio>
                </RadioGroup>
            </div>
        </div>

        <template #footer>
            <div class="flex justify-end gap-2">
                <Button @click="open = false">取消</Button>
                <Button type="primary" @click="handleSave">保存</Button>
            </div>
        </template>
    </Dialog>
</template>

<style scoped>
.create-view-form {
    display: flex;
    flex-direction: column;
    gap: 20px;
}
.field-label {
    display: block;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 8px;
    color: #333;
}
.field-label.required::before {
    content: "* ";
    color: #ff4d4f;
}
.field-error {
    font-size: 12px;
    color: #ff4d4f;
    margin-top: 4px;
}
.scope-radios {
    display: flex;
    flex-direction: column;
    gap: 12px;
}
</style>
