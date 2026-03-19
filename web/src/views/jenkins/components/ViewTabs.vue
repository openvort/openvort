<template>
    <div class="flex items-center gap-1 border-b border-gray-200 px-4 overflow-x-auto" style="-ms-overflow-style: none; scrollbar-width: none;">
        <div
            v-for="view in views"
            :key="view.name"
            class="group relative flex items-center"
        >
            <button
                class="px-3 py-2 text-sm whitespace-nowrap border-b-2 transition-colors -mb-px"
                :class="activeView === view.name
                    ? 'border-blue-600 text-blue-600 font-medium'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
                @click="$emit('switch', view.name)"
                @contextmenu.prevent="handleContextMenu(view.name, $event)"
            >
                {{ view.name }}
            </button>
        </div>

        <button
            v-if="showAdd"
            class="px-2 py-2 text-sm text-gray-400 hover:text-gray-600 transition-colors -mb-px border-b-2 border-transparent"
            @click="$emit('add')"
        >
            <Plus :size="14" />
        </button>

        <!-- Context menu -->
        <Teleport to="body">
            <div
                v-if="contextMenu.show"
                class="fixed z-50 bg-white rounded-lg shadow-lg border border-gray-200 py-1 min-w-[120px]"
                :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
            >
                <button
                    class="w-full px-3 py-1.5 text-sm text-left text-red-600 hover:bg-red-50 transition-colors"
                    @click="handleDelete"
                >
                    删除视图
                </button>
            </div>
            <div v-if="contextMenu.show" class="fixed inset-0 z-40" @click="contextMenu.show = false" />
        </Teleport>
    </div>
</template>

<script setup lang="ts">
import { reactive } from "vue";
import { Plus } from "lucide-vue-next";
import type { JenkinsView } from "../types";

defineProps<{
    views: JenkinsView[];
    activeView: string;
    showAdd?: boolean;
}>();

const emit = defineEmits<{
    (e: "switch", viewName: string): void;
    (e: "add"): void;
    (e: "delete", viewName: string): void;
}>();

const contextMenu = reactive({ show: false, x: 0, y: 0, viewName: "" });

function handleContextMenu(viewName: string, event: MouseEvent) {
    if (viewName.toLowerCase() === "all") return;
    contextMenu.show = true;
    contextMenu.x = event.clientX;
    contextMenu.y = event.clientY;
    contextMenu.viewName = viewName;
}

function handleDelete() {
    emit("delete", contextMenu.viewName);
    contextMenu.show = false;
}
</script>
