<script setup lang="ts">
import { computed } from "vue";
import { ChevronRight, ChevronDown, FolderTree, Users } from "lucide-vue-next";

export interface DeptNode {
    id: number;
    name: string;
    parent_id: number | null;
    platform: string;
    platform_dept_id: string;
    order: number;
    member_count: number;
    children: DeptNode[];
}

const props = withDefaults(defineProps<{
    nodes: DeptNode[];
    expandedIds: Set<number>;
    selectedId: number | null;
    showAllNode?: boolean;
    allNodeLabel?: string;
    allMemberCount?: number;
    depth?: number;
}>(), {
    showAllNode: false,
    allNodeLabel: "全部成员",
    allMemberCount: 0,
    depth: 0,
});

const emit = defineEmits<{
    select: [id: number | null];
    toggleExpand: [id: number];
}>();

const isAllSelected = computed(() => props.showAllNode && props.selectedId === null);
</script>

<template>
    <!-- "All members" virtual root node -->
    <div
        v-if="showAllNode && depth === 0"
        class="flex items-center px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm mb-0.5"
        :class="isAllSelected ? 'bg-blue-50 text-blue-700 font-medium' : 'hover:bg-gray-50 text-gray-700'"
        @click="emit('select', null)"
    >
        <Users :size="14" class="mr-2 flex-shrink-0" :class="isAllSelected ? 'text-blue-500' : 'text-gray-400'" />
        <span class="flex-1 truncate">{{ allNodeLabel }}</span>
        <span class="text-xs ml-1" :class="isAllSelected ? 'text-blue-400' : 'text-gray-400'">{{ allMemberCount }}</span>
    </div>

    <template v-for="node in nodes" :key="node.id">
        <div
            class="flex items-center px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm"
            :class="selectedId === node.id ? 'bg-blue-50 text-blue-700 font-medium' : 'hover:bg-gray-50 text-gray-700'"
            :style="{ paddingLeft: `${12 + depth * 16}px` }"
            @click="emit('select', node.id)"
        >
            <span
                v-if="node.children.length"
                class="mr-1 cursor-pointer flex-shrink-0"
                @click.stop="emit('toggleExpand', node.id)"
            >
                <ChevronDown v-if="expandedIds.has(node.id)" :size="14" />
                <ChevronRight v-else :size="14" />
            </span>
            <span v-else class="mr-1 w-3.5 flex-shrink-0" />
            <FolderTree :size="14" class="mr-2 flex-shrink-0" :class="selectedId === node.id ? 'text-blue-400' : 'text-gray-400'" />
            <span class="flex-1 truncate">{{ node.name }}</span>
            <span class="text-xs ml-1" :class="selectedId === node.id ? 'text-blue-400' : 'text-gray-400'">{{ node.member_count }}</span>
        </div>

        <!-- Recursive children -->
        <DeptTree
            v-if="node.children.length && expandedIds.has(node.id)"
            :nodes="node.children"
            :expanded-ids="expandedIds"
            :selected-id="selectedId"
            :depth="depth + 1"
            @select="emit('select', $event)"
            @toggle-expand="emit('toggleExpand', $event)"
        />
    </template>
</template>
