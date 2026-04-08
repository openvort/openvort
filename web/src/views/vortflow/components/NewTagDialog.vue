<script setup lang="ts">
import { Dialog as VortDialog, Button as VortButton, Input as VortInput } from "@openvort/vort-ui";

defineProps<{
    open: boolean;
    tagName: string;
    tagColor: string;
    colorPalette: string[];
}>();

const emit = defineEmits<{
    "update:open": [val: boolean];
    "update:tagName": [val: string];
    "update:tagColor": [val: string];
    cancel: [];
    confirm: [];
}>();
</script>

<template>
    <VortDialog
        :open="open"
        title="新建标签"
        :width="520"
        @update:open="emit('update:open', $event)"
    >
        <div class="space-y-5 mt-2">
            <div>
                <div class="text-sm text-gray-700 mb-1">名称</div>
                <VortInput :model-value="tagName" placeholder="请输入标签名称" @update:model-value="emit('update:tagName', $event)" />
            </div>
            <div>
                <div class="text-sm text-gray-700 mb-2">颜色</div>
                <div class="grid grid-cols-8 gap-2">
                    <button
                        v-for="color in colorPalette"
                        :key="color"
                        type="button"
                        class="w-8 h-8 rounded-sm border-2 flex items-center justify-center transition"
                        :class="tagColor === color ? 'border-blue-500 shadow-sm' : 'border-transparent'"
                        :style="{ backgroundColor: color }"
                        @click="emit('update:tagColor', color)"
                    >
                        <span v-if="tagColor === color" class="text-white text-xs">&#10003;</span>
                    </button>
                </div>
            </div>
        </div>
        <template #footer>
            <VortButton @click="emit('cancel')">取消</VortButton>
            <VortButton variant="primary" class="ml-2" @click="emit('confirm')">确定</VortButton>
        </template>
    </VortDialog>
</template>
