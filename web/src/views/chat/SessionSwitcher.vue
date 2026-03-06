<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { ChevronDown, Plus, Loader2, Pencil, Trash2, ListChecks, MoreHorizontal, Search } from "lucide-vue-next";
import { Popover as VortPopover } from "@/components/vort";
import {
    getChatSessions, createChatSession, renameChatSession, deleteChatSession, batchDeleteChatSessions
} from "@/api";
import { message, dialog } from "@/components/vort";
import type { ChatSession } from "./types";

const props = defineProps<{
    currentSessionId: string;
    currentTitle: string;
}>();

const emit = defineEmits<{
    (e: "switch", sessionId: string): void;
    (e: "new-session"): void;
    (e: "sessions-loaded", sessions: ChatSession[]): void;
}>();

const sessions = ref<ChatSession[]>([]);
const sessionsLoading = ref(false);
const dropdownOpen = ref(false);
const searchKeyword = ref("");
const drawerVisible = ref(false);

// Batch mode state (for drawer)
const batchMode = ref(false);
const selectedSessionIds = ref<string[]>([]);
const renamingSessionId = ref("");
const renameText = ref("");

const filteredSessions = computed(() => {
    if (!searchKeyword.value.trim()) return sessions.value;
    const kw = searchKeyword.value.toLowerCase();
    return sessions.value.filter(s => s.title.toLowerCase().includes(kw));
});

const allSelected = computed(() =>
    sessions.value.length > 0 && selectedSessionIds.value.length === sessions.value.length
);

async function loadSessions() {
    sessionsLoading.value = true;
    try {
        const res: any = await getChatSessions("ai");
        sessions.value = res?.sessions || [];
        emit("sessions-loaded", sessions.value);
    } catch {
        sessions.value = [];
    } finally {
        sessionsLoading.value = false;
    }
}

function handleSelect(sessionId: string) {
    dropdownOpen.value = false;
    searchKeyword.value = "";
    emit("switch", sessionId);
}

function handleNewSession() {
    dropdownOpen.value = false;
    emit("new-session");
}

function openDrawer() {
    dropdownOpen.value = false;
    drawerVisible.value = true;
    batchMode.value = false;
    selectedSessionIds.value = [];
}

// Rename
function startRename(session: ChatSession) {
    renamingSessionId.value = session.session_id;
    renameText.value = session.title;
}

async function confirmRename() {
    const sid = renamingSessionId.value;
    const title = renameText.value.trim();
    if (!sid || !title) { renamingSessionId.value = ""; return; }
    try {
        await renameChatSession(sid, title);
        const s = sessions.value.find(s => s.session_id === sid);
        if (s) s.title = title;
    } catch {
        message.error("重命名失败");
    }
    renamingSessionId.value = "";
}

// Delete
async function handleDelete(sessionId: string) {
    dialog.confirm({
        title: "确认删除该对话？",
        content: "删除后不可恢复",
        onOk: async () => {
            try {
                await deleteChatSession(sessionId);
                sessions.value = sessions.value.filter(s => s.session_id !== sessionId);
                emit("sessions-loaded", sessions.value);
                if (props.currentSessionId === sessionId) {
                    if (sessions.value.length > 0) {
                        emit("switch", sessions.value[0].session_id);
                    } else {
                        emit("new-session");
                    }
                }
                message.success("已删除");
            } catch {
                message.error("删除失败");
            }
        },
    });
}

// Batch
function toggleBatchMode() {
    batchMode.value = !batchMode.value;
    selectedSessionIds.value = [];
}

function toggleSelectAll() {
    if (allSelected.value) selectedSessionIds.value = [];
    else selectedSessionIds.value = sessions.value.map(s => s.session_id);
}

function toggleSelect(sessionId: string) {
    const idx = selectedSessionIds.value.indexOf(sessionId);
    if (idx >= 0) selectedSessionIds.value.splice(idx, 1);
    else selectedSessionIds.value.push(sessionId);
}

async function handleBatchDelete() {
    if (!selectedSessionIds.value.length) return;
    dialog.confirm({
        title: `确认删除 ${selectedSessionIds.value.length} 个对话？`,
        content: "删除后不可恢复",
        onOk: async () => {
            try {
                await batchDeleteChatSessions(selectedSessionIds.value);
                const deleted = new Set(selectedSessionIds.value);
                sessions.value = sessions.value.filter(s => !deleted.has(s.session_id));
                emit("sessions-loaded", sessions.value);
                if (deleted.has(props.currentSessionId)) {
                    if (sessions.value.length > 0) emit("switch", sessions.value[0].session_id);
                    else emit("new-session");
                }
                selectedSessionIds.value = [];
                batchMode.value = false;
                message.success("批量删除成功");
            } catch {
                message.error("批量删除失败");
            }
        },
    });
}

function formatTime(ts: number): string {
    if (!ts) return "";
    const d = new Date(ts * 1000);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

defineExpose({ loadSessions, sessions });
</script>

<template>
    <div class="flex items-center">
        <!-- Session dropdown trigger -->
        <VortPopover v-model:open="dropdownOpen" trigger="click" placement="bottomLeft" :arrow="false">
            <button class="flex items-center gap-1 px-2 py-1 rounded-md hover:bg-gray-50 transition-colors cursor-pointer max-w-[300px]">
                <span class="text-base font-medium text-gray-800 truncate">{{ currentTitle || '新对话' }}</span>
                <ChevronDown :size="16" class="text-gray-400 flex-shrink-0" :class="dropdownOpen ? 'rotate-180' : ''" />
            </button>
            <template #content>
                <div class="w-[320px] -m-3">
                    <!-- Search -->
                    <div class="px-3 pt-3 pb-2">
                        <div class="relative">
                            <Search :size="14" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                            <input
                                v-model="searchKeyword"
                                placeholder="搜索会话..."
                                class="w-full h-8 pl-8 pr-3 text-sm bg-gray-50 border border-gray-200 rounded-md outline-none focus:ring-1 focus:ring-blue-400"
                            />
                        </div>
                    </div>
                    <!-- Session list -->
                    <div class="max-h-[360px] overflow-y-auto py-1">
                        <div v-if="sessionsLoading" class="flex items-center justify-center py-6">
                            <Loader2 :size="16" class="animate-spin text-gray-400" />
                        </div>
                        <div v-else-if="filteredSessions.length === 0" class="px-3 py-4 text-xs text-gray-400 text-center">
                            暂无对话
                        </div>
                        <div
                            v-for="s in filteredSessions" :key="s.session_id"
                            class="flex items-center gap-2 px-3 py-2 mx-1 rounded-md cursor-pointer transition-colors"
                            :class="currentSessionId === s.session_id ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                            @click="handleSelect(s.session_id)"
                        >
                            <div class="flex-1 min-w-0">
                                <div class="text-sm truncate">{{ s.title }}</div>
                            </div>
                            <span class="text-[11px] text-gray-400 flex-shrink-0">{{ formatTime(s.updated_at) }}</span>
                        </div>
                    </div>
                    <!-- Footer -->
                    <div class="border-t border-gray-100 px-3 py-2">
                        <button
                            class="w-full text-left text-sm text-gray-500 hover:text-gray-700 py-1 cursor-pointer"
                            @click="openDrawer"
                        >
                            管理会话
                        </button>
                    </div>
                </div>
            </template>
        </VortPopover>

        <!-- New session button -->
        <VortTooltip title="新建对话">
            <button
                class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer ml-1"
                @click="handleNewSession"
            >
                <Plus :size="18" />
            </button>
        </VortTooltip>

        <!-- Manage sessions drawer -->
        <vort-drawer v-model:open="drawerVisible" title="管理会话" :width="400">
            <!-- Batch mode toggle -->
            <div v-if="batchMode" class="flex items-center justify-between mb-4">
                <VortCheckbox :checked="allSelected" @update:checked="toggleSelectAll">
                    <span class="text-sm text-gray-600">全选</span>
                </VortCheckbox>
                <div class="flex items-center gap-2">
                    <span class="text-xs text-gray-400">已选 {{ selectedSessionIds.length }} 项</span>
                    <button class="text-xs text-gray-400 hover:text-gray-600 cursor-pointer" @click="toggleBatchMode">取消</button>
                </div>
            </div>
            <div v-else class="flex items-center justify-between mb-4">
                <span class="text-sm text-gray-500">共 {{ sessions.length }} 个对话</span>
                <button class="text-xs text-gray-400 hover:text-gray-600 cursor-pointer" @click="toggleBatchMode">批量操作</button>
            </div>

            <!-- Session list -->
            <div class="space-y-1">
                <div
                    v-for="s in sessions" :key="s.session_id"
                    class="group flex items-center gap-2 px-3 py-2.5 rounded-lg transition-colors"
                    :class="batchMode ? 'hover:bg-gray-50' : (currentSessionId === s.session_id ? 'bg-gray-50' : 'hover:bg-gray-50/50')"
                >
                    <VortCheckbox
                        v-if="batchMode"
                        :checked="selectedSessionIds.includes(s.session_id)"
                        @update:checked="toggleSelect(s.session_id)"
                        @click.stop
                    />
                    <!-- Rename input -->
                    <div v-if="renamingSessionId === s.session_id" class="flex-1 min-w-0">
                        <input
                            v-model="renameText"
                            class="w-full text-sm bg-white border border-blue-300 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-blue-400"
                            @keydown.enter="confirmRename"
                            @keydown.escape="renamingSessionId = ''"
                            @blur="confirmRename"
                            autofocus
                        />
                    </div>
                    <div v-else class="flex-1 min-w-0">
                        <div class="text-sm text-gray-700 truncate">{{ s.title }}</div>
                        <div class="text-[11px] text-gray-400 mt-0.5">{{ formatTime(s.updated_at) }}</div>
                    </div>
                    <!-- Actions -->
                    <div v-if="!batchMode && renamingSessionId !== s.session_id"
                        class="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                        <button class="p-1 rounded text-gray-400 hover:text-gray-600 cursor-pointer" @click="startRename(s)">
                            <Pencil :size="14" />
                        </button>
                        <button class="p-1 rounded text-gray-400 hover:text-red-500 cursor-pointer" @click="handleDelete(s.session_id)">
                            <Trash2 :size="14" />
                        </button>
                    </div>
                </div>
            </div>

            <!-- Batch delete footer -->
            <div v-if="batchMode" class="mt-4 pt-3 border-t border-gray-100">
                <VortButton
                    danger
                    size="small"
                    :disabled="selectedSessionIds.length === 0"
                    class="w-full"
                    @click="handleBatchDelete"
                >
                    <Trash2 :size="14" class="mr-1" />
                    删除所选 ({{ selectedSessionIds.length }})
                </VortButton>
            </div>
        </vort-drawer>
    </div>
</template>
