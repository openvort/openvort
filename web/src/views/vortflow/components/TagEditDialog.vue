<script setup lang="ts">
import { ref, watch } from "vue";
import { createVortflowTag, updateVortflowTag } from "@/api";
import { message } from "@openvort/vort-ui";

interface Props {
    open: boolean;
    mode?: "add" | "edit";
    data?: { id?: string; name?: string; color?: string };
}

const props = withDefaults(defineProps<Props>(), {
    mode: "add",
    data: () => ({}),
});

const emit = defineEmits<{
    "update:open": [val: boolean];
    saved: [];
}>();

const COLOR_PRESETS = [
    { label: "预设", colors: [
        "#ef4444", "#f97316", "#eab308", "#22c55e",
        "#3b82f6", "#8b5cf6", "#d946ef", "#ec4899",
        "#14b8a6", "#6366f1", "#0ea5e9", "#f43f5e",
    ] },
];

const loading = ref(false);
const formName = ref("");
const formColor = ref("#3b82f6");

watch(() => props.open, (val) => {
    if (val) {
        if (props.mode === "edit" && props.data) {
            formName.value = props.data.name || "";
            formColor.value = props.data.color || "#3b82f6";
        } else {
            formName.value = "";
            formColor.value = "#3b82f6";
        }
    }
});

const handleSubmit = async () => {
    const name = formName.value.trim();
    if (!name) {
        message.warning("请输入标签名称");
        return;
    }
    loading.value = true;
    try {
        if (props.mode === "edit" && props.data?.id) {
            const res: any = await updateVortflowTag(props.data.id, { name, color: formColor.value });
            if (res?.error) {
                message.error(res.error);
                return;
            }
        } else {
            const res: any = await createVortflowTag({ name, color: formColor.value });
            if (res?.error) {
                message.error(res.error);
                return;
            }
        }
        message.success(props.mode === "edit" ? "标签已更新" : "标签已创建");
        emit("update:open", false);
        emit("saved");
    } catch (e: any) {
        message.error(e?.message || "操作失败");
    } finally {
        loading.value = false;
    }
};

const close = () => emit("update:open", false);
</script>

<template>
    <vort-dialog
        :open="open"
        :title="mode === 'edit' ? '编辑标签' : '新建标签'"
        :width="440"
        :centered="true"
        @update:open="close"
        @ok="handleSubmit"
    >
        <vort-form label-width="80px" class="mt-4">
            <vort-form-item label="名称" required>
                <vort-input v-model="formName" placeholder="请输入标签名称" @keyup.enter="handleSubmit" />
            </vort-form-item>
            <vort-form-item label="颜色">
                <vort-color-picker
                    v-model="formColor"
                    :presets="COLOR_PRESETS"
                    :disabled-alpha="true"
                    show-text
                />
            </vort-form-item>
            <vort-form-item label="预览">
                <vort-tag :color="formColor" class="text-sm">{{ formName || '标签名称' }}</vort-tag>
            </vort-form-item>
        </vort-form>
        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button @click="close">取消</vort-button>
                <vort-button variant="primary" :loading="loading" @click="handleSubmit">确定</vort-button>
            </div>
        </template>
    </vort-dialog>
</template>

