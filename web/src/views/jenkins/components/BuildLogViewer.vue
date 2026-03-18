<template>
    <Dialog :open="open" width="900px" :footer="false" @update:open="$emit('update:open', $event)">
        <template #title>
            <div class="flex items-center gap-2">
                <CheckCircle2 v-if="buildResult === 'SUCCESS'" class="w-5 h-5 text-green-500" />
                <XCircle v-else-if="buildResult === 'FAILURE'" class="w-5 h-5 text-red-500" />
                <CircleDot v-else class="w-5 h-5 text-gray-400" />
                <span>控制台输出</span>
                <span class="text-sm text-gray-400 font-normal">#{{ buildNumber }}</span>
            </div>
        </template>

        <div class="relative">
            <!-- Actions bar -->
            <div class="flex items-center justify-between mb-2">
                <div class="text-xs text-gray-400">
                    <template v-if="truncated">显示最后 {{ logContent.split("\n").length }} 行 (共 {{ lineCount }} 行)</template>
                    <template v-else>共 {{ lineCount }} 行</template>
                </div>
                <div class="flex items-center gap-2">
                    <VortButton
                        v-if="truncated"
                        variant="text"
                        size="small"
                        @click="$emit('loadFull')"
                    >
                        加载全部
                    </VortButton>
                    <VortTooltip title="复制">
                        <button
                            class="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600"
                            @click="copyLog"
                        >
                            <Copy class="w-4 h-4" />
                        </button>
                    </VortTooltip>
                </div>
            </div>

            <!-- Log content -->
            <div v-if="logLoading" class="flex items-center justify-center py-12">
                <Loader2 class="w-5 h-5 animate-spin text-gray-400" />
            </div>
            <div v-else class="bg-gray-50 border border-gray-200 rounded-lg overflow-auto max-h-[60vh]">
                <pre class="p-4 text-[13px] leading-5 font-mono text-gray-900 whitespace-pre-wrap break-words">{{ logContent || "（无日志内容）" }}</pre>
            </div>
        </div>
    </Dialog>
</template>

<script setup lang="ts">
import { CheckCircle2, XCircle, CircleDot, Copy, Loader2 } from "lucide-vue-next";
import { Dialog, message } from "@/components/vort";

defineProps<{
    open: boolean;
    buildNumber: number;
    buildResult: string;
    logContent: string;
    logLoading: boolean;
    truncated: boolean;
    lineCount: number;
}>();

defineEmits<{
    (e: "update:open", val: boolean): void;
    (e: "loadFull"): void;
}>();

function copyLog() {
    const el = document.querySelector("pre");
    if (el) {
        navigator.clipboard.writeText(el.textContent || "").then(() => {
            message.success("已复制到剪贴板");
        });
    }
}
</script>
