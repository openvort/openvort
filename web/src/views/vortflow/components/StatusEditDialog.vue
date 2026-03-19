<script setup lang="ts">
import { ref, watch } from "vue";
import { createVortflowStatus, updateVortflowStatus } from "@/api";
import { message } from "@/components/vort/message";
import { HelpCircle } from "lucide-vue-next";

interface Props {
    open: boolean;
    mode?: "add" | "edit";
    data?: { id?: string; name?: string; icon?: string; icon_color?: string; command?: string };
}

const props = withDefaults(defineProps<Props>(), {
    mode: "add",
    data: () => ({}),
});

const emit = defineEmits<{
    "update:open": [val: boolean];
    saved: [];
}>();

const ICON_OPTIONS = [
    "▷", "☺", "☹", "⊙", "‖", "⊖", "⌛", "⊗",
    "⊜", "●", "⊘", "⊕", "△", "⊠",
    "☰", "⬠", "✎", "✓5", "✓6", "✓6",
    "◎", "◔", "✓", "⊕", "◔", "✓", "⊙", "?",
];

const COLOR_OPTIONS = [
    "#f97316", "#60a5fa", "#22c55e", "#ef4444",
    "#f87171", "#fb923c", "#fbbf24", "#a3e635",
    "#34d399", "#2dd4bf", "#22d3ee", "#818cf8",
    "#a78bfa", "#c084fc",
    "#ec4899", "#92400e", "#9ca3af", "#374151",
    "#a8a29e", "#bef264", "#94a3b8",
];

const loading = ref(false);
const formName = ref("");
const formIcon = ref("○");
const formIconColor = ref("#3b82f6");
const formCommand = ref("");

watch(() => props.open, (val) => {
    if (val) {
        if (props.mode === "edit" && props.data) {
            formName.value = props.data.name || "";
            formIcon.value = props.data.icon || "○";
            formIconColor.value = props.data.icon_color || "#3b82f6";
            formCommand.value = props.data.command || "";
        } else {
            formName.value = "";
            formIcon.value = "○";
            formIconColor.value = "#3b82f6";
            formCommand.value = "";
        }
    }
});

const handleSubmit = async () => {
    const name = formName.value.trim();
    if (!name) {
        message.warning("请输入状态名称");
        return;
    }
    loading.value = true;
    try {
        const payload = {
            name,
            icon: formIcon.value,
            icon_color: formIconColor.value,
            command: formCommand.value.trim(),
        };
        if (props.mode === "edit" && props.data?.id) {
            const res: any = await updateVortflowStatus(props.data.id, payload);
            if (res?.error) {
                message.error(res.error);
                return;
            }
        } else {
            const res: any = await createVortflowStatus(payload);
            if (res?.error) {
                message.error(res.error);
                return;
            }
        }
        message.success(props.mode === "edit" ? "状态已更新" : "状态已创建");
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
        :title="mode === 'edit' ? '修改工作项状态' : '新建工作项状态'"
        :width="520"
        :centered="true"
        @update:open="close"
        @ok="handleSubmit"
    >
        <div class="mt-4 space-y-5">
            <div>
                <div class="text-sm font-medium text-gray-800 mb-2">状态名称</div>
                <vort-input v-model="formName" placeholder="请输入状态名称" @keyup.enter="handleSubmit" />
            </div>

            <div>
                <div class="text-sm font-medium text-gray-800 mb-2">图标</div>
                <div class="flex items-center gap-2 flex-wrap">
                    <div
                        v-for="ic in ICON_OPTIONS"
                        :key="ic"
                        class="icon-swatch"
                        :class="{ 'is-selected': formIcon === ic }"
                        @click="formIcon = ic"
                    >
                        <span class="text-sm" :style="{ color: formIconColor }">{{ ic }}</span>
                    </div>
                </div>
            </div>

            <div>
                <div class="text-sm font-medium text-gray-800 mb-2">图标颜色</div>
                <div class="flex items-center gap-2 flex-wrap">
                    <div
                        v-for="c in COLOR_OPTIONS"
                        :key="c"
                        class="color-swatch"
                        :class="{ 'is-selected': formIconColor === c }"
                        :style="{ backgroundColor: c }"
                        @click="formIconColor = c"
                    >
                        <svg v-if="formIconColor === c" class="w-3.5 h-3.5 text-white" viewBox="0 0 16 16" fill="currentColor">
                            <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" />
                        </svg>
                    </div>
                </div>
            </div>

            <div>
                <div class="flex items-center gap-1 mb-2">
                    <span class="text-sm font-medium text-gray-800">指令</span>
                    <span class="text-sm text-gray-400">(选填)</span>
                    <vort-tooltip title="当 AI 处理工作项时，流转到此状态会触发对应指令">
                        <HelpCircle :size="14" class="text-gray-400 cursor-help" />
                    </vort-tooltip>
                </div>
                <vort-input v-model="formCommand" placeholder="请输入指令" />
            </div>
        </div>

        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button @click="close">取消</vort-button>
                <vort-button variant="primary" :loading="loading" @click="handleSubmit">
                    {{ mode === "edit" ? "修改" : "创建" }}
                </vort-button>
            </div>
        </template>
    </vort-dialog>
</template>

<style scoped>
.icon-swatch {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    cursor: pointer;
    transition: border-color 0.15s, background-color 0.15s;
}
.icon-swatch:hover {
    border-color: #93c5fd;
    background-color: #f0f9ff;
}
.icon-swatch.is-selected {
    border-color: #3b82f6;
    background-color: #eff6ff;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.color-swatch {
    width: 36px;
    height: 36px;
    border-radius: 6px;
    cursor: pointer;
    border: 2px solid transparent;
    transition: border-color 0.15s, transform 0.15s;
    display: flex;
    align-items: center;
    justify-content: center;
}
.color-swatch:hover {
    transform: scale(1.1);
}
.color-swatch.is-selected {
    border-color: rgba(0, 0, 0, 0.15);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
}
</style>
