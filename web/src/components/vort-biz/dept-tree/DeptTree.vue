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

export interface InlineMember {
    id: string;
    name: string;
    avatar_url?: string;
}

const ALL_SENTINEL = 0;

const props = withDefaults(defineProps<{
    nodes: DeptNode[];
    expandedIds: Set<number>;
    selectedId: number | null;
    showAllNode?: boolean;
    allNodeLabel?: string;
    allMemberCount?: number;
    depth?: number;
    // Inline member display (optional, backward compatible)
    deptMembers?: Record<string, InlineMember[]>;
    selectedMemberIds?: Set<string>;
}>(), {
    showAllNode: false,
    allNodeLabel: "全部成员",
    allMemberCount: 0,
    depth: 0,
});

const emit = defineEmits<{
    select: [id: number | null];
    toggleExpand: [id: number];
    toggleMember: [id: string];
}>();

const inlineMode = computed(() => !!props.deptMembers);
const isAllSelected = computed(() => props.showAllNode && props.selectedId === null);
const isAllExpanded = computed(() => inlineMode.value && props.expandedIds.has(ALL_SENTINEL));

const COLORS = [
    "bg-red-500", "bg-orange-500", "bg-amber-500", "bg-green-500",
    "bg-teal-500", "bg-blue-500", "bg-indigo-500", "bg-purple-500",
    "bg-pink-500", "bg-cyan-500",
];
function avatarColor(name: string) {
    let h = 0;
    for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
    return COLORS[Math.abs(h) % COLORS.length];
}
function initial(name: string) {
    if (!name) return "?";
    const c = name.trim().charAt(0);
    return /[a-zA-Z]/.test(c) ? c.toUpperCase() : c;
}

function getDeptMembers(deptId: number): InlineMember[] {
    return props.deptMembers?.[String(deptId)] || [];
}

function getAllMembers(): InlineMember[] {
    return props.deptMembers?.["all"] || [];
}

function handleAllClick() {
    if (inlineMode.value) {
        emit("toggleExpand", ALL_SENTINEL);
    } else {
        emit("select", null);
    }
}
</script>

<template>
    <!-- "All members" virtual root node -->
    <div
        v-if="showAllNode && depth === 0"
        class="flex items-center px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm mb-0.5"
        :class="(inlineMode ? isAllExpanded : isAllSelected) ? 'bg-blue-50 text-blue-700 font-medium' : 'hover:bg-gray-50 text-gray-700'"
        @click="handleAllClick"
    >
        <span v-if="inlineMode" class="mr-1 cursor-pointer flex-shrink-0">
            <ChevronDown v-if="isAllExpanded" :size="14" />
            <ChevronRight v-else :size="14" />
        </span>
        <Users :size="14" class="mr-2 flex-shrink-0" :class="(inlineMode ? isAllExpanded : isAllSelected) ? 'text-blue-500' : 'text-gray-400'" />
        <span class="flex-1 truncate">{{ allNodeLabel }}</span>
        <span class="text-xs ml-1" :class="(inlineMode ? isAllExpanded : isAllSelected) ? 'text-blue-400' : 'text-gray-400'">{{ allMemberCount }}</span>
    </div>

    <!-- All members inline (expanded in inline mode) -->
    <template v-if="inlineMode && isAllExpanded && depth === 0">
        <label
            v-for="m in getAllMembers()" :key="'all-' + m.id"
            class="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer"
            style="padding-left: 36px"
        >
            <vort-checkbox
                :checked="selectedMemberIds?.has(m.id)"
                @update:checked="emit('toggleMember', m.id)"
            />
            <span
                class="inline-flex items-center justify-center w-7 h-7 rounded-full text-white text-xs font-medium flex-shrink-0"
                :class="avatarColor(m.name)"
            >{{ initial(m.name) }}</span>
            <span class="text-sm text-gray-800 truncate">{{ m.name }}</span>
        </label>
    </template>

    <template v-for="node in nodes" :key="node.id">
        <div
            class="flex items-center px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm"
            :class="inlineMode
                ? 'hover:bg-gray-50 text-gray-700'
                : (selectedId === node.id ? 'bg-blue-50 text-blue-700 font-medium' : 'hover:bg-gray-50 text-gray-700')"
            :style="{ paddingLeft: `${12 + depth * 16}px` }"
            @click="inlineMode ? emit('toggleExpand', node.id) : emit('select', node.id)"
        >
            <span
                v-if="node.children.length || inlineMode"
                class="mr-1 cursor-pointer flex-shrink-0"
                @click.stop="emit('toggleExpand', node.id)"
            >
                <ChevronDown v-if="expandedIds.has(node.id)" :size="14" />
                <ChevronRight v-else :size="14" />
            </span>
            <span v-else class="mr-1 w-3.5 flex-shrink-0" />
            <FolderTree :size="14" class="mr-2 flex-shrink-0" :class="(!inlineMode && selectedId === node.id) ? 'text-blue-400' : 'text-gray-400'" />
            <span class="flex-1 truncate">{{ node.name }}</span>
            <span class="text-xs ml-1" :class="(!inlineMode && selectedId === node.id) ? 'text-blue-400' : 'text-gray-400'">{{ node.member_count }}</span>
        </div>

        <!-- Inline members for this dept (members before child departments) -->
        <template v-if="inlineMode && expandedIds.has(node.id)">
            <label
                v-for="m in getDeptMembers(node.id)" :key="'dept-' + node.id + '-' + m.id"
                class="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer"
                :style="{ paddingLeft: `${28 + depth * 16}px` }"
            >
                <vort-checkbox
                    :checked="selectedMemberIds?.has(m.id)"
                    @update:checked="emit('toggleMember', m.id)"
                />
                <span
                    class="inline-flex items-center justify-center w-7 h-7 rounded-full text-white text-xs font-medium flex-shrink-0"
                    :class="avatarColor(m.name)"
                >{{ initial(m.name) }}</span>
                <span class="text-sm text-gray-800 truncate">{{ m.name }}</span>
            </label>
        </template>

        <!-- Recursive children (after members) -->
        <DeptTree
            v-if="node.children.length && expandedIds.has(node.id)"
            :nodes="node.children"
            :expanded-ids="expandedIds"
            :selected-id="selectedId"
            :depth="depth + 1"
            :dept-members="deptMembers"
            :selected-member-ids="selectedMemberIds"
            @select="emit('select', $event)"
            @toggle-expand="emit('toggleExpand', $event)"
            @toggle-member="emit('toggleMember', $event)"
        />
    </template>
</template>
