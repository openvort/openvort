<template>
    <div class="flex flex-col h-full">
        <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <span class="text-sm font-medium text-gray-700">Jenkins 实例</span>
            <VortButton v-if="isAdmin" variant="text" size="small" @click="$emit('add')">
                <Plus :size="14" class="mr-1" /> 添加
            </VortButton>
        </div>
        <div class="flex-1 overflow-y-auto p-2 space-y-1">
            <div
                v-for="inst in instances"
                :key="inst.id"
                class="group relative px-3 py-2.5 rounded-lg cursor-pointer transition-colors"
                :class="selectedId === inst.id ? 'bg-blue-50 border border-blue-200' : 'hover:bg-gray-50 border border-transparent'"
                @click="$emit('select', inst)"
            >
                <div class="flex items-center gap-2">
                    <HardDrive class="w-4 h-4 shrink-0" :class="selectedId === inst.id ? 'text-blue-600' : 'text-gray-400'" />
                    <div class="min-w-0 flex-1">
                        <div class="flex items-center gap-1.5">
                            <span class="text-sm font-medium truncate" :class="selectedId === inst.id ? 'text-blue-700' : 'text-gray-800'">{{ inst.name }}</span>
                            <VortTag v-if="inst.is_default" color="blue" size="small" class="shrink-0">默认</VortTag>
                        </div>
                        <div class="text-xs text-gray-400 truncate mt-0.5">{{ inst.url }}</div>
                    </div>
                </div>

                <!-- Action menu -->
                <div v-if="isAdmin" class="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <div class="relative" @click.stop>
                        <button class="p-1 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-600" @click="toggleMenu(inst.id)">
                            <MoreVertical class="w-3.5 h-3.5" />
                        </button>
                        <div
                            v-if="openMenuId === inst.id"
                            class="absolute right-0 top-full mt-1 w-32 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-1"
                        >
                            <button class="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 text-gray-700" @click="handleAction('edit', inst)">编辑</button>
                            <button class="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 text-gray-700" @click="handleAction('verify', inst)">测试连接</button>
                            <button v-if="!inst.is_default" class="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 text-gray-700" @click="handleAction('default', inst)">设为默认</button>
                            <button class="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 text-red-600" @click="handleAction('delete', inst)">删除</button>
                        </div>
                    </div>
                </div>
            </div>

            <div v-if="instances.length === 0 && !loading" class="px-3 py-8 text-center text-sm text-gray-400">
                暂无实例
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Plus, HardDrive, MoreVertical } from "lucide-vue-next";
import type { JenkinsInstance } from "../types";

defineProps<{
    instances: JenkinsInstance[];
    selectedId: string | null;
    loading: boolean;
    isAdmin: boolean;
}>();

const emit = defineEmits<{
    (e: "select", inst: JenkinsInstance): void;
    (e: "add"): void;
    (e: "edit", inst: JenkinsInstance): void;
    (e: "delete", inst: JenkinsInstance): void;
    (e: "verify", inst: JenkinsInstance): void;
    (e: "setDefault", inst: JenkinsInstance): void;
}>();

const openMenuId = ref<string | null>(null);

function toggleMenu(id: string) {
    openMenuId.value = openMenuId.value === id ? null : id;
}

function handleAction(action: string, inst: JenkinsInstance) {
    openMenuId.value = null;
    if (action === "edit") emit("edit", inst);
    else if (action === "delete") emit("delete", inst);
    else if (action === "verify") emit("verify", inst);
    else if (action === "default") emit("setDefault", inst);
}
</script>
