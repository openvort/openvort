<script setup lang="ts">
import { ref, watch } from "vue";
import { ChevronDown, ChevronRight, Monitor, Terminal, FileText, Globe } from "lucide-vue-next";
import ScreencastView from "./ScreencastView.vue";

const props = defineProps<{
    nodeId?: string;
    isWorking: boolean;
    terminalOutput: string;
    recentFiles: string[];
    hasBrowser?: boolean;
}>();

const SCREENCAST_KEY = "chat-screencast-visible";
const stored = localStorage.getItem(SCREENCAST_KEY);
const expanded = ref(true);
const showScreencast = ref(stored !== null ? stored === "1" : true);

function toggleScreencast() {
    showScreencast.value = !showScreencast.value;
    localStorage.setItem(SCREENCAST_KEY, showScreencast.value ? "1" : "0");
}
</script>

<template>
    <div class="border border-gray-200 rounded-xl overflow-hidden mb-2">
        <div
            class="flex items-center justify-between px-3 py-2 bg-gray-50 cursor-pointer select-none hover:bg-gray-100 transition-colors"
            @click="expanded = !expanded"
        >
            <span class="text-xs text-gray-500 flex items-center gap-1.5">
                <Monitor :size="14" />
                工作过程
                <span
                    v-if="isWorking"
                    class="inline-block w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"
                />
            </span>
            <component :is="expanded ? ChevronDown : ChevronRight" :size="14" class="text-gray-400" />
        </div>
        <div v-if="expanded" class="divide-y divide-gray-100">
            <div v-if="terminalOutput" class="relative">
                <div class="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-400 bg-gray-900">
                    <Terminal :size="12" />
                    终端
                </div>
                <div
                    class="max-h-60 overflow-y-auto bg-gray-900 text-green-400 text-xs font-mono px-3 py-2 whitespace-pre-wrap break-words leading-5"
                    ref="terminalRef"
                >{{ terminalOutput }}</div>
            </div>
            <div v-if="recentFiles.length" class="px-3 py-2">
                <div class="flex items-center gap-1 text-xs text-gray-400 mb-1">
                    <FileText :size="12" />
                    最近文件变更
                </div>
                <div v-for="f in recentFiles" :key="f" class="text-xs text-gray-500 truncate">
                    {{ f }}
                </div>
            </div>
            <div v-if="hasBrowser && props.nodeId" class="border-t border-gray-100">
                <div class="flex items-center gap-2 px-3 py-2">
                    <button
                        @click="toggleScreencast"
                        class="flex items-center gap-1 text-xs px-2 py-1 rounded-md transition-colors"
                        :class="showScreencast
                            ? 'bg-red-50 text-red-500 hover:bg-red-100'
                            : 'bg-blue-50 text-blue-500 hover:bg-blue-100'"
                    >
                        <Globe :size="12" />
                        {{ showScreencast ? '关闭实时画面' : '查看实时画面' }}
                    </button>
                </div>
                <ScreencastView
                    v-if="showScreencast"
                    :node-id="props.nodeId"
                    :active="showScreencast"
                />
            </div>
            <div v-if="!terminalOutput && !recentFiles.length && !hasBrowser" class="px-3 py-3 text-xs text-gray-400 text-center">
                暂无操作记录
            </div>
        </div>
    </div>
</template>
