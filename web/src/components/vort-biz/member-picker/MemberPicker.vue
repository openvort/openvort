<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { Search, X } from "lucide-vue-next";
import { getDepartmentTree, getMembersSimple, getDepartmentMembers } from "@/api";
import DeptTree from "@/components/vort-biz/dept-tree/DeptTree.vue";
import type { DeptNode } from "@/components/vort-biz/dept-tree/DeptTree.vue";

const props = withDefaults(defineProps<{
    modelValue: string[];
    title?: string;
    showSendReminder?: boolean;
}>(), {
    title: "选择联系人",
    showSendReminder: false,
});

const emit = defineEmits<{
    "update:modelValue": [ids: string[]];
}>();

interface SimpleMember {
    id: string;
    name: string;
    avatar_url?: string;
    is_virtual?: boolean;
    dept?: string;
}

const searchQuery = ref("");
const deptNodes = ref<DeptNode[]>([]);
const expandedIds = ref<Set<number>>(new Set());
const selectedDeptId = ref<number | null>(null);
const allMembers = ref<SimpleMember[]>([]);
const deptMembers = ref<SimpleMember[]>([]);
const loadingMembers = ref(false);
const loadingDepts = ref(false);
const totalCount = ref(0);
const sendReminder = ref(true);

const selectedIds = computed({
    get: () => new Set(props.modelValue),
    set: () => {},
});

const displayMembers = computed(() => {
    const list = selectedDeptId.value !== null ? deptMembers.value : allMembers.value;
    if (!searchQuery.value.trim()) return list;
    const q = searchQuery.value.trim().toLowerCase();
    return list.filter(m => m.name.toLowerCase().includes(q));
});

const selectedMembers = computed(() =>
    allMembers.value.filter(m => selectedIds.value.has(m.id))
);

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

function toggleMember(id: string) {
    const ids = [...props.modelValue];
    const idx = ids.indexOf(id);
    if (idx > -1) ids.splice(idx, 1);
    else ids.push(id);
    emit("update:modelValue", ids);
}

function removeMember(id: string) {
    emit("update:modelValue", props.modelValue.filter(i => i !== id));
}

async function loadDepartments() {
    loadingDepts.value = true;
    try {
        const res: any = await getDepartmentTree();
        deptNodes.value = res?.departments || [];
        if (deptNodes.value.length > 0) {
            expandedIds.value = new Set(deptNodes.value.map(d => d.id));
        }
    } catch { /* ignore */ }
    finally { loadingDepts.value = false; }
}

async function loadAllMembers() {
    loadingMembers.value = true;
    try {
        const res: any = await getMembersSimple({ size: 500 });
        allMembers.value = (res?.members || []).filter((m: any) => m.id && !m.is_virtual);
        totalCount.value = allMembers.value.length;
    } catch { allMembers.value = []; }
    finally { loadingMembers.value = false; }
}

async function loadDeptMembers(deptId: number) {
    loadingMembers.value = true;
    try {
        const res: any = await getDepartmentMembers(deptId);
        deptMembers.value = (res?.members || []).filter((m: any) => m.id && !m.is_virtual);
    } catch { deptMembers.value = []; }
    finally { loadingMembers.value = false; }
}

function handleDeptSelect(id: number | null) {
    selectedDeptId.value = id;
    if (id !== null) {
        loadDeptMembers(id);
    }
}

function handleToggleExpand(id: number) {
    const s = new Set(expandedIds.value);
    if (s.has(id)) s.delete(id);
    else s.add(id);
    expandedIds.value = s;
}

onMounted(() => {
    loadDepartments();
    loadAllMembers();
});
</script>

<template>
    <div class="flex border border-gray-200 rounded-lg overflow-hidden" style="height: 420px">
        <!-- Left: dept tree + member list -->
        <div class="w-[280px] flex flex-col border-r border-gray-200">
            <div class="px-3 py-2 border-b border-gray-100">
                <div class="relative">
                    <Search :size="14" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input
                        v-model="searchQuery"
                        type="text"
                        placeholder="搜索"
                        class="w-full h-8 pl-8 pr-3 text-sm border border-gray-200 rounded-md outline-none focus:border-blue-500 bg-white"
                    />
                </div>
            </div>

            <div class="flex-1 flex flex-col overflow-hidden">
                <div class="max-h-[180px] overflow-y-auto shrink-0 px-1 py-1">
                    <DeptTree
                        :nodes="deptNodes"
                        :expanded-ids="expandedIds"
                        :selected-id="selectedDeptId"
                        :show-all-node="true"
                        :all-member-count="totalCount"
                        @select="handleDeptSelect"
                        @toggle-expand="handleToggleExpand"
                    />
                </div>

                <div class="flex-1 overflow-y-auto border-t border-gray-100">
                    <vort-spin :spinning="loadingMembers">
                        <div v-if="displayMembers.length" class="divide-y divide-gray-50">
                            <label
                                v-for="m in displayMembers" :key="m.id"
                                class="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 cursor-pointer"
                            >
                                <vort-checkbox
                                    :checked="selectedIds.has(m.id)"
                                    @update:checked="toggleMember(m.id)"
                                />
                                <span
                                    class="inline-flex items-center justify-center w-7 h-7 rounded-full text-white text-xs font-medium flex-shrink-0"
                                    :class="avatarColor(m.name)"
                                >{{ initial(m.name) }}</span>
                                <div class="min-w-0">
                                    <div class="text-sm text-gray-800 truncate">{{ m.name }}</div>
                                    <div v-if="m.dept" class="text-xs text-gray-400 truncate">
                                        {{ m.dept }}
                                    </div>
                                </div>
                            </label>
                        </div>
                        <div v-else class="text-gray-400 text-sm text-center py-8">无匹配成员</div>
                    </vort-spin>
                </div>
            </div>
        </div>

        <!-- Right: selected list -->
        <div class="flex-1 flex flex-col">
            <div class="flex items-center justify-between px-4 py-2.5 border-b border-gray-100">
                <span class="text-sm font-medium text-gray-700">{{ title }}</span>
                <span class="text-xs text-gray-400">已选择 {{ modelValue.length }} 个联系人</span>
            </div>

            <div class="flex-1 overflow-y-auto px-4 py-2">
                <div v-if="selectedMembers.length" class="space-y-1">
                    <div
                        v-for="m in selectedMembers" :key="m.id"
                        class="flex items-center justify-between py-2"
                    >
                        <div class="flex items-center gap-3">
                            <span
                                class="inline-flex items-center justify-center w-8 h-8 rounded-full text-white text-xs font-medium flex-shrink-0"
                                :class="avatarColor(m.name)"
                            >{{ initial(m.name) }}</span>
                            <span class="text-sm text-gray-800">{{ m.name }}</span>
                        </div>
                        <button class="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600" @click="removeMember(m.id)">
                            <X :size="14" />
                        </button>
                    </div>
                </div>
                <div v-else class="text-gray-400 text-sm text-center py-12">请从左侧选择成员</div>
            </div>

            <div v-if="showSendReminder" class="px-4 py-3 border-t border-gray-100">
                <label class="flex items-center gap-2 cursor-pointer">
                    <vort-checkbox v-model:checked="sendReminder" />
                    <span class="text-sm text-gray-600">发送填写提醒</span>
                </label>
            </div>
        </div>
    </div>
</template>
