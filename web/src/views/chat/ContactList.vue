<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from "vue";
import { Bot, Plus, Search, Loader2, Pin } from "lucide-vue-next";
import { getChatContacts, getChatMembers, startMemberChat, togglePinContact, hideChatContact, resetChatSession } from "@/api";
import { message } from "@/components/vort/message";
import { dialog } from "@/components/vort/dialog";
import { Popover as VortPopover } from "@/components/vort/popover";
import { pinyin } from "pinyin-pro";
import type { Contact, MentionMember } from "./types";

const props = defineProps<{
    activeContactId: string;
}>();

const emit = defineEmits<{
    (e: "select", contact: Contact): void;
}>();

const contacts = ref<Contact[]>([]);
const contactsLoading = ref(false);
const searchKeyword = ref("");
const showNewChatPopover = ref(false);
const newChatKeyword = ref("");
const newChatMembers = ref<MentionMember[]>([]);
const newChatLoading = ref(false);
const newChatActiveIndex = ref(-1);
const newChatInputRef = ref<HTMLInputElement | null>(null);
const newChatListRef = ref<any>(null);

const filteredContacts = computed(() => {
    if (!searchKeyword.value.trim()) return contacts.value;
    const kw = searchKeyword.value.toLowerCase();
    return contacts.value.filter(c =>
        c.name.toLowerCase().includes(kw) ||
        c.last_message.toLowerCase().includes(kw)
    );
});

async function loadContacts() {
    contactsLoading.value = true;
    try {
        const res: any = await getChatContacts();
        contacts.value = res?.contacts || [];
    } catch {
        contacts.value = [];
    } finally {
        contactsLoading.value = false;
    }
}

function handleSelectContact(contact: Contact) {
    emit("select", contact);
}

function formatTime(ts: number): string {
    if (!ts) return "";
    const d = new Date(ts * 1000);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return "昨天";
    return d.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

// Right-click context menu
const contextMenuContact = ref<Contact | null>(null);

async function handleTogglePin(contact: Contact) {
    if (contact.type === "ai") return;
    const sessionId = contact.session_id;
    if (!sessionId) return;
    const newPinned = !contact.pinned;
    try {
        await togglePinContact(sessionId, newPinned);
        contact.pinned = newPinned;
        message.success(newPinned ? "已置顶" : "已取消置顶");
    } catch {
        message.error("操作失败");
    }
}

function handleMarkUnread(contact: Contact) {
    contact.unread = contact.unread ? 0 : 1;
}

async function handleClearHistory(contact: Contact) {
    const sessionId = contact.type === "ai" ? undefined : contact.session_id;
    if (!sessionId && contact.type !== "ai") return;
    dialog.confirm({
        title: "确认清空聊天记录？",
        content: "清空后不可恢复",
        onOk: async () => {
            try {
                if (contact.type === "ai") {
                    message.info("请在 AI 对话中使用重置功能");
                    return;
                }
                await resetChatSession(sessionId!);
                contact.last_message = "";
                message.success("聊天记录已清空");
            } catch {
                message.error("清空失败");
            }
        },
    });
}

async function handleHideContact(contact: Contact) {
    if (contact.type === "ai") return;
    const sessionId = contact.session_id;
    if (!sessionId) return;
    try {
        await hideChatContact(sessionId);
        contacts.value = contacts.value.filter(c => c.id !== contact.id);
        message.success("已隐藏");
    } catch {
        message.error("操作失败");
    }
}

// New chat: search members
let searchTimer: ReturnType<typeof setTimeout> | null = null;

function getFirstLetter(name: string): string {
    if (!name) return "#";
    const first = name.charAt(0);
    if (/[a-zA-Z]/.test(first)) return first.toUpperCase();
    const py = pinyin(first, { pattern: "first", toneType: "none" });
    if (py && /[a-zA-Z]/.test(py.charAt(0))) return py.charAt(0).toUpperCase();
    return "#";
}

interface LetterGroup {
    letter: string;
    members: MentionMember[];
}

const groupedNewChatMembers = computed<LetterGroup[]>(() => {
    const map = new Map<string, MentionMember[]>();
    for (const m of newChatMembers.value) {
        const letter = getFirstLetter(m.name);
        if (!map.has(letter)) map.set(letter, []);
        map.get(letter)!.push(m);
    }
    return Array.from(map.entries())
        .sort((a, b) => a[0] === "#" ? 1 : b[0] === "#" ? -1 : a[0].localeCompare(b[0]))
        .map(([letter, members]) => ({ letter, members }));
});

const flatNewChatMembers = computed(() =>
    groupedNewChatMembers.value.flatMap(g => g.members)
);

function getFlatIndex(groupIndex: number, memberIndex: number): number {
    let offset = 0;
    for (let i = 0; i < groupIndex; i++) {
        offset += groupedNewChatMembers.value[i].members.length;
    }
    return offset + memberIndex;
}

async function loadNewChatMembers(keyword = "") {
    newChatLoading.value = true;
    try {
        const res: any = await getChatMembers(keyword, 200);
        newChatMembers.value = res?.members || [];
    } catch {
        newChatMembers.value = [];
    } finally {
        newChatLoading.value = false;
    }
}

watch(showNewChatPopover, (open) => {
    if (open) {
        newChatKeyword.value = "";
        newChatMembers.value = [];
        newChatActiveIndex.value = -1;
        loadNewChatMembers();
        nextTick(() => newChatInputRef.value?.focus());
    }
});

watch(newChatKeyword, (kw) => {
    if (searchTimer) clearTimeout(searchTimer);
    newChatActiveIndex.value = -1;
    searchTimer = setTimeout(() => loadNewChatMembers(kw.trim()), 300);
});

function handleNewChatKeydown(e: KeyboardEvent) {
    const flat = flatNewChatMembers.value;
    const len = flat.length;
    if (!len) return;

    if (e.key === "ArrowDown") {
        e.preventDefault();
        newChatActiveIndex.value = (newChatActiveIndex.value + 1) % len;
        scrollActiveIntoView();
    } else if (e.key === "ArrowUp") {
        e.preventDefault();
        newChatActiveIndex.value = (newChatActiveIndex.value - 1 + len) % len;
        scrollActiveIntoView();
    } else if (e.key === "Enter") {
        e.preventDefault();
        const idx = newChatActiveIndex.value;
        if (idx >= 0 && idx < len) {
            handleStartChat(flat[idx]);
        }
    }
}

function scrollActiveIntoView() {
    nextTick(() => {
        const container = newChatListRef.value?.wrapRef ?? newChatListRef.value;
        if (!container) return;
        const items = container.querySelectorAll("[data-member-item]");
        const active = items[newChatActiveIndex.value] as HTMLElement | undefined;
        active?.scrollIntoView({ block: "nearest" });
    });
}

async function handleStartChat(member: MentionMember) {
    showNewChatPopover.value = false;
    newChatKeyword.value = "";
    try {
        const res: any = await startMemberChat(member.id);
        await loadContacts();
        const contact = contacts.value.find(c => c.id === member.id);
        if (contact) {
            emit("select", contact);
        }
    } catch {
        message.error("发起聊天失败");
    }
}

function refreshContacts() {
    loadContacts();
}

onMounted(() => {
    loadContacts();
});

defineExpose({ refreshContacts, loadContacts });
</script>

<template>
    <div class="flex flex-col h-full bg-white border-r border-gray-100">
        <!-- Search bar -->
        <div class="flex items-center gap-2 px-3 py-3 border-b border-gray-100">
            <div class="relative flex-1">
                <Search :size="14" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                    v-model="searchKeyword"
                    placeholder="搜索"
                    class="w-full h-8 pl-8 pr-3 text-sm bg-gray-50 border-none rounded-md outline-none focus:ring-1 focus:ring-blue-400 focus:bg-white transition-colors"
                />
            </div>
            <VortPopover v-model:open="showNewChatPopover" trigger="click" placement="bottomRight" :arrow="false">
                <button class="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-md text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors cursor-pointer">
                    <Plus :size="18" />
                </button>
                <template #content>
                    <div class="w-[280px] -m-3">
                        <div class="px-3 pt-3 pb-2">
                            <input
                                ref="newChatInputRef"
                                v-model="newChatKeyword"
                                placeholder="搜索成员..."
                                class="w-full h-8 px-3 text-sm bg-gray-50 border border-gray-200 rounded-md outline-none focus:ring-1 focus:ring-blue-400 focus:bg-white"
                                @keydown="handleNewChatKeydown"
                            />
                        </div>
                        <VortScrollbar ref="newChatListRef" max-height="300px">
                            <div v-if="newChatLoading" class="flex items-center justify-center py-6">
                                <Loader2 :size="16" class="animate-spin text-gray-400" />
                            </div>
                            <div v-else-if="newChatMembers.length === 0" class="px-3 py-4 text-xs text-gray-400 text-center">
                                未找到匹配的成员
                            </div>
                            <template v-else v-for="(group, gi) in groupedNewChatMembers" :key="group.letter">
                                <div class="px-3 pt-2.5 pb-1 text-[11px] font-medium text-gray-400 sticky top-0 bg-white z-[1]">{{ group.letter }}</div>
                                <div
                                    v-for="(m, mi) in group.members" :key="m.id"
                                    data-member-item
                                    class="flex items-center gap-2.5 px-3 py-2 cursor-pointer transition-colors"
                                    :class="getFlatIndex(gi, mi) === newChatActiveIndex ? 'bg-blue-50' : 'hover:bg-gray-50'"
                                    @click="handleStartChat(m)"
                                    @mouseenter="newChatActiveIndex = getFlatIndex(gi, mi)"
                                >
                                    <div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 text-xs font-medium text-blue-600">
                                        {{ m.name.charAt(0) }}
                                    </div>
                                    <div class="min-w-0 flex-1">
                                        <div class="text-sm text-gray-800 truncate">{{ m.name }}</div>
                                        <div v-if="m.department || m.position" class="text-xs text-gray-400 truncate">{{ [m.department, m.position].filter(Boolean).join(' / ') }}</div>
                                        <div v-else-if="m.email" class="text-xs text-gray-400 truncate">{{ m.email }}</div>
                                    </div>
                                </div>
                            </template>
                        </VortScrollbar>
                    </div>
                </template>
            </VortPopover>
        </div>

        <!-- Contact list -->
        <VortScrollbar class="flex-1">
            <div v-if="contactsLoading" class="flex items-center justify-center py-8">
                <Loader2 :size="20" class="animate-spin text-gray-300" />
            </div>
            <div v-else-if="filteredContacts.length === 0" class="flex flex-col items-center justify-center py-12 text-gray-400">
                <p class="text-xs">暂无联系人</p>
            </div>
            <div v-else class="py-1">
                <VortDropdown
                    v-for="c in filteredContacts" :key="c.id"
                    trigger="contextMenu"
                    class="!block"
                >
                    <div
                        class="flex items-center gap-3 mx-2 px-3 py-3 rounded-lg cursor-pointer transition-colors mb-0.5"
                        :class="activeContactId === c.id ? 'bg-gray-50' : 'hover:bg-gray-50/50'"
                        @click="handleSelectContact(c)"
                    >
                        <!-- Avatar -->
                        <div class="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center overflow-hidden"
                            :class="c.type === 'ai' ? 'bg-blue-50' : 'bg-gray-100'">
                            <Bot v-if="c.type === 'ai'" :size="20" class="text-blue-600" />
                            <img v-else-if="c.avatar_url" :src="c.avatar_url" class="w-full h-full object-cover" />
                            <span v-else class="text-sm font-medium text-gray-500">{{ c.name.charAt(0) }}</span>
                        </div>

                        <!-- Name + last message -->
                        <div class="flex-1 min-w-0 overflow-hidden">
                            <div class="flex items-center justify-between gap-2">
                                <div class="flex items-center gap-1 min-w-0">
                                    <span class="text-sm font-medium text-gray-800 truncate">{{ c.name }}</span>
                                    <vort-tag
                                        v-if="c.is_virtual"
                                        size="small"
                                        color="blue"
                                        :bordered="false"
                                        class="flex-shrink-0"
                                    >
                                        AI 员工
                                    </vort-tag>
                                </div>
                                <span class="text-[11px] text-gray-400 flex-shrink-0 whitespace-nowrap">{{ formatTime(c.last_message_time) }}</span>
                            </div>
                            <div class="flex items-center justify-between mt-0.5 gap-2">
                                <span class="text-xs text-gray-400 truncate min-w-0">{{ c.last_message || (c.type === 'ai' ? '点击开始对话' : '') }}</span>
                                <div class="flex items-center gap-1 flex-shrink-0">
                                    <Pin v-if="c.pinned && c.type !== 'ai'" :size="12" class="text-gray-300 rotate-45" />
                                    <div v-if="c.unread" class="w-4 h-4 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center">
                                        {{ c.unread > 99 ? '99+' : c.unread }}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <template #overlay>
                        <VortDropdownMenuItem @click="handleMarkUnread(c)">
                            {{ c.unread ? '标为已读' : '标为未读' }}
                        </VortDropdownMenuItem>
                        <VortDropdownMenuItem v-if="c.type !== 'ai'" @click="handleTogglePin(c)">
                            {{ c.pinned ? '取消置顶' : '置顶' }}
                        </VortDropdownMenuItem>
                        <VortDropdownMenuSeparator />
                        <VortDropdownMenuItem @click="handleClearHistory(c)">清空聊天记录</VortDropdownMenuItem>
                        <VortDropdownMenuItem v-if="c.type !== 'ai'" danger @click="handleHideContact(c)">不显示</VortDropdownMenuItem>
                    </template>
                </VortDropdown>
            </div>
        </VortScrollbar>
    </div>
</template>
