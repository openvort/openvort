<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useUserStore } from "@/stores";

const props = withDefaults(defineProps<{
    embedded?: boolean;
    embeddedExpanded?: boolean;
    initialSessionId?: string;
    embeddedSidebar?: boolean;
}>(), {
    embedded: false,
    embeddedExpanded: false,
    initialSessionId: "",
    embeddedSidebar: false,
});
const emit = defineEmits<{
    'embedded-maximize': [];
    'embedded-close': [];
    'embedded-toggle-sidebar': [];
}>();
import {
    Send, Bot, Loader2, Wrench, X, ImagePlus, FileText, MonitorPlay, Smile,
    Settings, Check, Brain, PackageMinus, RotateCcw, Zap, StopCircle, Square,
    Hash, Bug, ListTodo, BookOpen, GitBranch, ChevronDown, ChevronRight,
    Copy, RefreshCw, Search, Clock, Pause, ChevronUp, Trash2, Paperclip, File,
    Maximize2, Minimize2, PanelLeftOpen, PanelLeftClose
} from "lucide-vue-next";
import { Popover as VortPopover, Image as VortImage, ImagePreviewGroup as VortImagePreviewGroup } from "@openvort/vort-ui";
import {
    getChatSessionInfo, setChatThinking, compactChatSession, resetChatSession,
    getChatContacts, getWorkAssignments, restoreChatContext, startMemberChat,
    deleteChatMessage
} from "@/api";
import { usePluginStore } from "@/stores/modules/plugin";
import { useNotificationStore } from "@/stores/modules/notification";
import { message } from "@openvort/vort-ui";
import ContactList from "./ContactList.vue";
import SessionSwitcher from "./SessionSwitcher.vue";
import MemberProfile from "./MemberProfile.vue";
import AiEmployeeBadge from "./AiEmployeeBadge.vue";
import WorkspaceViewer from "./WorkspaceViewer.vue";
import aiAvatarUrl from "@/assets/brand/ai-avatar.png";
import type { ChatMessage, ChatSession, Contact, Draft, ActionButton } from "./types";
import { shouldShowTimestamp, formatTimeDivider } from "./utils";
import { useChatImages } from "./composables/useChatImages";
import { useChatStream } from "./composables/useChatStream";
import { useChatHistory } from "./composables/useChatHistory";
import { useChatSession } from "./composables/useChatSession";
import { useChatMentions } from "./composables/useChatMentions";

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const pluginStore = usePluginStore();
const notificationStore = useNotificationStore();

// Restore persisted state synchronously to prevent flash on refresh
let _restoredContact: Contact | null = null;
let _restoredSessionId = '';
if (!props.embedded) {
    try {
        const raw = localStorage.getItem('chat-last-contact');
        if (raw) {
            const c = JSON.parse(raw);
            if (c?.type === 'member' && c.id) {
                _restoredContact = {
                    type: 'member', id: c.id, name: c.name || '',
                    avatar_url: c.avatar_url || '', position: c.position || '',
                    last_message: '', last_message_time: 0, unread: 0,
                    session_id: c.session_id || '',
                };
                _restoredSessionId = c.session_id || '';
            } else {
                _restoredContact = {
                    type: 'ai', id: 'ai', name: 'AI 助手',
                    avatar_url: '', last_message: '', last_message_time: 0,
                    unread: 0, pinned: true,
                };
                _restoredSessionId = localStorage.getItem('chat-last-session-id') || '';
            }
        }
    } catch { /* ignore */ }
}

// ---- Shared state ----
const messages = ref<ChatMessage[]>([]);
const inputText = ref("");
const loading = ref(false);
const currentSessionId = ref<string>(_restoredSessionId);
const activeContact = ref<Contact | null>(_restoredContact);
const sessions = ref<ChatSession[]>([]);
const sessionTokens = ref({ input: 0, output: 0, messages: 0, cacheCreation: 0, cacheRead: 0 });
const thinkingLevel = ref<string>("off");
const messageCounter = ref(0);
const drafts = new Map<string, Draft>();

// ---- Template refs ----
type ChatScrollbarRef = { wrapRef?: HTMLElement | null };
const chatScrollbar = ref<ChatScrollbarRef | null>(null);
const inputArea = ref<HTMLElement>();
const contactListRef = ref<InstanceType<typeof ContactList>>();
const sessionSwitcherRef = ref<InstanceType<typeof SessionSwitcher>>();

// ---- UI state ----
const sendMode = ref<'enter' | 'ctrl-enter'>('enter');
const settingsOpen = ref(false);
const emojiOpen = ref(false);
const thinkingOpen = ref(false);
const compacting = ref(false);
const memberProfileOpen = ref(false);

// ---- Message search ----
const searchOpen = ref(false);
const searchQuery = ref("");
const searchResults = ref<Array<{ id: number; session_id: string; sender_type: string; content: string; created_at: string }>>([]);
const searching = ref(false);

async function handleSearch() {
    const q = searchQuery.value.trim();
    if (q.length < 2) { searchResults.value = []; return; }
    searching.value = true;
    try {
        const { searchChatMessages } = await import("@/api");
        const res: any = await searchChatMessages(q, currentSessionId.value || undefined, 20);
        searchResults.value = res?.messages || [];
    } catch {
        searchResults.value = [];
    } finally {
        searching.value = false;
    }
}

// ---- Offline summary banner ----
const offlineSummary = ref<{ unreads: number; highlights: string[] } | null>(null);
function dismissOfflineSummary() { offlineSummary.value = null; }

// ---- Computed ----
const isAiMode = computed(() => !activeContact.value || activeContact.value.type === "ai");
const currentSessionTitle = computed(() => {
    if (!currentSessionId.value) return "新对话";
    const s = sessions.value.find(s => s.session_id === currentSessionId.value);
    return s?.title || "新对话";
});
const activeTaskStatus = computed(() => {
    const c = activeContact.value;
    if (!c || !c.is_virtual) return null;
    return notificationStore.getTaskStatus(c.id);
});

// ---- Assignments and task bar ----
const activeAssignments = ref<any[]>([]);
const taskBarCollapsed = ref(localStorage.getItem('chat-taskbar-collapsed') === '1');
function toggleTaskBar() {
    taskBarCollapsed.value = !taskBarCollapsed.value;
    localStorage.setItem('chat-taskbar-collapsed', taskBarCollapsed.value ? '1' : '0');
}
async function loadActiveAssignments() {
    const c = activeContact.value;
    if (!c || !c.is_virtual) { activeAssignments.value = []; return; }
    try {
        const res: any = await getWorkAssignments({ assignee_member_id: c.id });
        const all = res?.assignments || [];
        activeAssignments.value = all.filter((a: any) => a.status !== "completed" && a.status !== "cancelled");
    } catch { activeAssignments.value = []; }
}

// ---- Emojis ----
const emojis = [
    '😀','😃','😄','😁','😆','😅','😂','🤣','😊','😇',
    '🙂','🙃','😉','😌','😍','🥰','😘','😗','😙','😚',
    '😋','😛','😜','🤪','😝','🤑','🤗','🤭','🤫','🤔',
    '🤐','🤨','😐','😑','😶','😏','😒','🙄','😬','🤥',
    '😔','😪','🤤','😴','😷','🤒','🤕','🤢','🤮','🥵',
    '🥶','🥴','😵','🤯','🤠','🥳','😎','🤓','🧐','😕',
    '😟','🙁','☹️','😮','😯','😲','😳','🥺','😦','😧',
    '😨','😰','😥','😢','😭','😱','😖','😣','😞','😓',
    '😩','😫','🥱','😤','😡','😠','🤬','👍','👎','👏',
    '🙌','🤝','🙏','❤️','🔥','💯','✨','🎉','😺','😸',
];

// ---- Smart auto-scroll ----
const SCROLL_BOTTOM_THRESHOLD = 80;
let autoScrollEnabled = true;
let scrollRAF: number | null = null;
function scrollToBottom(force = false) {
    if (!force && !autoScrollEnabled) return;
    if (force) autoScrollEnabled = true;
    if (scrollRAF) return;
    scrollRAF = requestAnimationFrame(() => {
        scrollRAF = null;
        const wrap = chatScrollbar.value?.wrapRef;
        if (wrap) {
            wrap.scrollTop = wrap.scrollHeight;
        }
    });
}

// ---- Simple helper functions ----
function formatToolElapsed(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    return `${Math.floor(seconds / 60)}m${seconds % 60}s`;
}

function toggleToolsExpanded(msg: ChatMessage) {
    msg.toolsExpanded = !msg.toolsExpanded;
}

function getOutputLineCount(output: string): number {
    return output.split('\n').length;
}

function getLastLines(output: string, n: number): string {
    const lines = output.split('\n');
    return lines.slice(-n).join('\n');
}

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ---- Session info and settings ----
async function loadSessionInfo() {
    if (!currentSessionId.value) return;
    try {
        const res: any = await getChatSessionInfo(currentSessionId.value);
        if (res) {
            thinkingLevel.value = res.thinking_level || "off";
            sessionTokens.value = {
                input: res.total_input_tokens || 0,
                output: res.total_output_tokens || 0,
                messages: res.message_count || 0,
                cacheCreation: res.total_cache_creation_tokens || 0,
                cacheRead: res.total_cache_read_tokens || 0,
            };
        }
    } catch { /* ignore */ }
}

async function handleThinkingChange(level: string) {
    if (!currentSessionId.value) return;
    try {
        await setChatThinking(level, currentSessionId.value);
        thinkingLevel.value = level;
        thinkingOpen.value = false;
        message.success(`Thinking 已设为 ${level}`);
    } catch { message.error("设置失败"); }
}

async function handleCompact() {
    if (!currentSessionId.value) return;
    compacting.value = true;
    try {
        const res: any = await compactChatSession(currentSessionId.value);
        if (res?.success) {
            message.success(`上下文已压缩：${res.old_count} → ${res.new_count} 条消息`);
            await loadSessionInfo();
        } else { message.warning(res?.error || "压缩失败"); }
    } catch { message.error("压缩失败"); }
    finally { compacting.value = false; }
}

// ---- Composables ----
const {
    pendingImages, pendingFiles, isDragging, addFiles, removeImage, removeFile,
    handlePaste, handleDragOver, handleDragLeave, handleDrop,
} = useChatImages();

const {
    aborting, activeStreams, handleSend, handleAbortCurrentStream,
    toggleToolCollapsed, getStreamPhase, getAccumulatedOutput,
    getRecentFileChanges, renderMarkdown,
} = useChatStream({
    messages, inputText, loading, currentSessionId, activeContact, sessions,
    sessionTokens, pendingImages, pendingFiles, isAiMode, messageCounter, drafts,
    sessionSwitcherRef, scrollToBottom, loadSessionInfo, loadActiveAssignments,
});

const {
    hasMoreHistory, historyOffset, loadingMore, contextResetAt,
    loadHistory, loadMoreHistory, formatTokens,
} = useChatHistory({
    messages, currentSessionId, chatScrollbar, messageCounter, scrollToBottom,
});

const {
    switchSession, handleNewSession, handleContactSelect,
    handleSessionsLoaded, saveDraft, restoreDraft,
} = useChatSession({
    messages, inputText, loading, currentSessionId, activeContact, sessions,
    sessionTokens, thinkingLevel, pendingImages, pendingFiles, messageCounter,
    hasMoreHistory, historyOffset, contextResetAt,
    activeStreams, drafts, sessionSwitcherRef,
    loadHistory, loadSessionInfo, scrollToBottom,
});

const {
    showMentionPanel, showCommandPanel, showHashTagPanel,
    mentionMembers, filteredCommands,
    mentionActiveIndex, commandActiveIndex, hashTagActiveIndex,
    panelStyle, hashTagLevel, hashTagSelectedCategory,
    hashTagItemsLoading, filteredHashTagCategories, filteredHashTagItems,
    hashTagQuery, selectMention, selectCommand,
    selectHashTagCategory, selectHashTagItem,
    handlePanelKeydown, isAnyPanelOpen, handleClickOutsidePanel,
} = useChatMentions({ inputText, pluginStore });

// ---- Functions that depend on composable returns ----
async function handleReset() {
    if (!currentSessionId.value) return;
    try {
        const res: any = await resetChatSession(currentSessionId.value);
        messages.value = [];
        sessionTokens.value = { input: 0, output: 0, messages: 0, cacheCreation: 0, cacheRead: 0 };
        contextResetAt.value = res?.context_reset_at || Date.now() / 1000;
        hasMoreHistory.value = false;
        historyOffset.value = 0;
        message.success("上下文已重置");
    } catch { message.error("重置失败"); }
}

function handleHistoryCleared(contact: Contact) {
    if (activeContact.value?.id === contact.id) {
        messages.value = [];
        sessionTokens.value = { input: 0, output: 0, messages: 0, cacheCreation: 0, cacheRead: 0 };
        contextResetAt.value = 0;
        hasMoreHistory.value = false;
        historyOffset.value = 0;
    }
}

async function handleReloadHistory() {
    if (!currentSessionId.value || loadingMore.value) return;
    loadingMore.value = true;
    const prevResetAt = contextResetAt.value;
    try {
        await restoreChatContext(currentSessionId.value);
        const ok = await loadHistory();
        if (!ok) {
            contextResetAt.value = prevResetAt;
            message.error("加载历史记录失败");
            return;
        }
        await loadSessionInfo();
    } catch {
        contextResetAt.value = prevResetAt;
        message.error("加载历史记录失败");
    } finally {
        loadingMore.value = false;
    }
}

function handlePressEnter(e: KeyboardEvent) {
    if (handlePanelKeydown(e)) return;

    if (sendMode.value === 'enter') {
        if (e.ctrlKey || e.metaKey) {
            const textarea = e.target as HTMLTextAreaElement;
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;
            inputText.value = inputText.value.substring(0, start) + '\n' + inputText.value.substring(end);
            nextTick(() => { textarea.selectionStart = textarea.selectionEnd = start + 1; });
        } else { e.preventDefault(); handleSend(); }
    } else {
        if (e.ctrlKey || e.metaKey) { e.preventDefault(); handleSend(); }
    }
}

function setSendMode(mode: 'enter' | 'ctrl-enter') {
    sendMode.value = mode;
    settingsOpen.value = false;
}

function triggerFileInput() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.jpg,.jpeg,.png,.txt,.rar,.zip,.doc,.docx,.xls,.7z';
    input.multiple = true;
    input.onchange = () => { if (input.files?.length) addFiles(input.files); };
    input.click();
}

function triggerVideoInput() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.mp4,.mov,.avi,.wmv,.flv,.mkv';
    input.multiple = false;
    input.onchange = () => { if (input.files?.length) addFiles(input.files); };
    input.click();
}

function insertEmoji(emoji: string) { inputText.value += emoji; emojiOpen.value = false; }

async function copyMessageContent(msg: ChatMessage) {
    const text = msg.content || '';
    if (!text) return;
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
        } else {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        }
        message.success("已复制到剪贴板");
    } catch {
        message.error("复制失败");
    }
}

async function removeMessage(msg: ChatMessage) {
    const idx = parseInt(msg.id, 10);
    if (isNaN(idx)) return;
    try {
        await deleteChatMessage(currentSessionId.value || "default", idx, msg.role);
        const i = messages.value.indexOf(msg);
        if (i !== -1) messages.value.splice(i, 1);
    } catch {
        message.error("删除失败");
    }
}

function resendMessage(msg: ChatMessage) {
    if (loading.value) return;
    inputText.value = msg.content || '';
    nextTick(() => handleSend());
}

async function handleActionButton(_msg: ChatMessage, btn: ActionButton) {
    if (btn.clicked || btn.loading) return;
    btn.loading = true;
    try {
        if (btn.action === "create_node") {
            const { createRemoteNode } = await import("@/api/index");
            const memberId = btn.params?.member_id || "";
            const image = btn.params?.image || "python:3.11-slim";
            const result = await createRemoteNode({
                name: `work-${memberId.substring(0, 8)}`,
                node_type: "docker",
                image,
            });
            const nodeId = result?.data?.id;
            if (nodeId && memberId) {
                const { updateMember } = await import("@/api/index");
                await updateMember(memberId, { remote_node_id: nodeId });
            }
            btn.clicked = true;
            message.success("工作电脑配置成功");
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "操作失败");
    } finally {
        btn.loading = false;
    }
}

async function fetchLatestMemberContact(memberId: string): Promise<Contact | null> {
    try {
        const res: any = await getChatContacts();
        const contacts = Array.isArray(res?.contacts) ? res.contacts as Contact[] : [];
        return contacts.find(c => c.type === "member" && c.id === memberId) || null;
    } catch {
        return null;
    }
}

function applyPromptFromQuery() {
    const promptParam = route.query.prompt as string | undefined;
    if (promptParam) {
        handleNewSession();
        inputText.value = promptParam;
        router.replace({ name: "chat", query: {} });
        nextTick(() => {
            const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
            if (textarea) textarea.focus();
        });
    }
}

function fillPrompt(text: string) {
    if (!text) return;
    handleNewSession();
    inputText.value = text;
    nextTick(() => {
        const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
        if (textarea) textarea.focus();
    });
}

// ---- Watchers ----
watch(currentSessionId, (val) => {
    if (!props.embedded) localStorage.setItem('chat-last-session-id', val);
});

watch(activeContact, (contact) => {
    if (!props.embedded && contact) {
        localStorage.setItem('chat-last-contact', JSON.stringify({
            type: contact.type,
            id: contact.id,
            name: contact.name,
            avatar_url: contact.avatar_url,
            session_id: contact.session_id,
            position: contact.position,
        }));
    }
    if (!props.embedded) loadActiveAssignments();
}, { deep: true });

watch(() => route.query.prompt, (val) => {
    if (!props.embedded && val) applyPromptFromQuery();
});

// ---- Lifecycle ----
onMounted(async () => {
    document.addEventListener("paste", handlePaste);
    document.addEventListener("click", handleClickOutsidePanel);

    if (!props.embedded) {
        try {
            const { useWebSocket } = await import("@/composables/useWebSocket");
            const { on } = useWebSocket();
            on("offline_summary", (data: any) => {
                if (data.unreads > 0) {
                    offlineSummary.value = { unreads: data.unreads, highlights: data.highlights || [] };
                }
            });
            on("node_status_change", (data: any) => {
                if (activeContact.value && activeContact.value.remote_node_id === data.node_id) {
                    (activeContact.value as any).remote_node_status = data.status;
                }
            });
            on("message", (data: any) => {
                if (!data?.session_id || !data?.content) return;
                if (data.session_id === currentSessionId.value && !loading.value) {
                    const newMsg: ChatMessage = {
                        id: String(++messageCounter.value),
                        role: "assistant",
                        content: data.content,
                        timestamp: Date.now(),
                        avatar_url: activeContact.value?.avatar_url,
                    };
                    messages.value.push(newMsg);
                    nextTick(scrollToBottom);
                }
                contactListRef.value?.refreshContacts?.();
            });
            on("schedule_result", () => { loadActiveAssignments(); });
            on("unread_update", () => { contactListRef.value?.refreshContacts?.(); });
            on("_reconnected", () => {
                contactListRef.value?.refreshContacts?.();
                if (currentSessionId.value) loadHistory();
                loadActiveAssignments();
            });
        } catch { /* silent */ }
    }

    nextTick(() => {
        const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
        if (textarea) {
            textarea.addEventListener('keydown', (e: KeyboardEvent) => {
                if (isAnyPanelOpen.value) {
                    if (['ArrowUp', 'ArrowDown', 'Escape', 'Tab', 'Backspace'].includes(e.key)) {
                        handlePanelKeydown(e);
                    }
                }
            });
        }
    });

    // Embedded mode: simplified initialization
    if (props.embedded) {
        activeContact.value = {
            type: "ai", id: "ai", name: "AI 助手",
            avatar_url: "", last_message: "", last_message_time: 0, unread: 0, pinned: true,
        };
        if (props.initialSessionId) {
            currentSessionId.value = props.initialSessionId;
            await loadHistory();
            await loadSessionInfo();
        }
        await nextTick();
        const scrollWrap = chatScrollbar.value?.wrapRef;
        if (scrollWrap) scrollWrap.addEventListener("scroll", onChatScroll);
        return;
    }

    const querySession = route.query.session as string | undefined;
    const queryContact = route.query.contact as string | undefined;
    const queryType = route.query.type as string | undefined;

    if (queryType === "member" && queryContact) {
        router.replace({ name: "chat", query: {} });
        const latestContact = await fetchLatestMemberContact(queryContact);
        activeContact.value = {
            type: "member",
            id: queryContact,
            name: latestContact?.name || "",
            avatar_url: latestContact?.avatar_url || "",
            position: latestContact?.position || "",
            last_message: "",
            last_message_time: 0,
            unread: 0,
            session_id: querySession || latestContact?.session_id || "",
            pinned: latestContact?.pinned,
            is_virtual: latestContact?.is_virtual,
            remote_node_id: latestContact?.remote_node_id || "",
            remote_node_status: latestContact?.remote_node_status || "",
        };
        const targetSessionId = querySession || latestContact?.session_id;
        if (targetSessionId) {
            await switchSession(targetSessionId);
        }
    } else {
        let restoredContact: { type: string; id: string; name?: string; avatar_url?: string; session_id?: string; position?: string } | null = null;
        try {
            const saved = localStorage.getItem('chat-last-contact');
            if (saved) restoredContact = JSON.parse(saved);
        } catch { /* ignore */ }

        if (restoredContact?.type === "member" && restoredContact.id) {
            const latestContact = await fetchLatestMemberContact(restoredContact.id);
            activeContact.value = {
                type: "member",
                id: restoredContact.id,
                name: latestContact?.name || restoredContact.name || "",
                avatar_url: latestContact?.avatar_url || restoredContact.avatar_url || "",
                position: latestContact?.position || restoredContact.position || "",
                last_message: "",
                last_message_time: 0,
                unread: 0,
                session_id: latestContact?.session_id || restoredContact.session_id || "",
                pinned: latestContact?.pinned,
                is_virtual: latestContact?.is_virtual,
                remote_node_id: latestContact?.remote_node_id || "",
                remote_node_status: latestContact?.remote_node_status || "",
            };
            if (restoredContact.session_id) {
                await switchSession(latestContact?.session_id || restoredContact.session_id);
            } else {
                try {
                    const res: any = await startMemberChat(restoredContact.id);
                    if (res?.session_id) {
                        activeContact.value.session_id = res.session_id;
                        await switchSession(res.session_id);
                    }
                } catch { /* fallback to empty state */ }
            }
        } else {
            activeContact.value = {
                type: "ai", id: "ai", name: "AI 助手",
                avatar_url: "", last_message: "", last_message_time: 0, unread: 0, pinned: true,
            };
            await sessionSwitcherRef.value?.loadSessions();

            const lastSessionId = localStorage.getItem('chat-last-session-id');
            if (lastSessionId && sessions.value.some(s => s.session_id === lastSessionId)) {
                await switchSession(lastSessionId);
            } else if (sessions.value.length > 0) {
                await switchSession(sessions.value[0].session_id);
            }
        }
    }

    applyPromptFromQuery();

    const floatDraft = localStorage.getItem("ai-float-draft");
    if (floatDraft) {
        localStorage.removeItem("ai-float-draft");
        inputText.value = floatDraft;
        nextTick(() => {
            const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
            if (textarea) textarea.focus();
        });
    }

    await nextTick();
    const scrollWrap = chatScrollbar.value?.wrapRef;
    if (scrollWrap) {
        scrollWrap.addEventListener("scroll", onChatScroll);
    }
});

function onChatScroll() {
    const wrap = chatScrollbar.value?.wrapRef;
    if (!wrap) return;
    autoScrollEnabled = wrap.scrollHeight - wrap.scrollTop - wrap.clientHeight < SCROLL_BOTTOM_THRESHOLD;
    if (!hasMoreHistory.value || loadingMore.value) return;
    if (wrap.scrollTop < 60) {
        loadMoreHistory();
    }
}

onUnmounted(() => {
    document.removeEventListener("paste", handlePaste);
    document.removeEventListener("click", handleClickOutsidePanel);
    const scrollWrap = chatScrollbar.value?.wrapRef;
    if (scrollWrap) {
        scrollWrap.removeEventListener("scroll", onChatScroll);
    }
    for (const stream of activeStreams.values()) {
        try { stream.eventSource?.close(); } catch { /* noop */ }
        if (stream.twTimer) clearInterval(stream.twTimer);
    }
    activeStreams.clear();
});

defineExpose({ currentSessionId, inputText, handleReset, switchSession, handleNewSession, activeContact, sessions, isAiMode, fillPrompt });
</script>

<template>
    <div class="flex h-full">
        <!-- 左侧联系人列表 -->
        <div v-if="!embedded || embeddedSidebar" :class="embedded ? 'flex-shrink-0 w-[200px] overflow-hidden border-r border-gray-100' : 'flex-shrink-0 w-[260px] overflow-hidden'">
            <ContactList
                ref="contactListRef"
                :active-contact-id="activeContact?.id || 'ai'"
                :compact="embedded"
                @select="handleContactSelect"
                @history-cleared="handleHistoryCleared"
            />
        </div>

        <!-- 右侧聊天区域 -->
        <div class="flex-1 flex flex-col min-w-0">
            <!-- 头部 -->
            <div :class="embedded ? 'flex items-center justify-between px-3 h-11 border-b border-gray-100 bg-white' : 'flex items-center justify-between px-6 h-14 border-b border-gray-100 bg-white'">
                <div class="flex min-w-0 flex-1 items-center pr-3">
                    <button v-if="embedded" @click="emit('embedded-toggle-sidebar')"
                        class="mr-1 flex-shrink-0 rounded-md p-1 text-gray-400 transition-colors cursor-pointer hover:text-gray-600 hover:bg-gray-50">
                        <PanelLeftOpen v-if="embeddedSidebar" :size="14" />
                        <PanelLeftClose v-else :size="14" />
                    </button>
                    <!-- AI mode: session switcher -->
                    <template v-if="isAiMode">
                        <img :src="aiAvatarUrl" :class="embedded ? 'w-4 h-4 mr-1.5' : 'w-5 h-5 mr-2'" class="flex-shrink-0 rounded-full object-cover" />
                        <div class="min-w-0">
                            <SessionSwitcher
                                ref="sessionSwitcherRef"
                                :current-session-id="currentSessionId"
                                :current-title="currentSessionTitle"
                                :compact="embedded"
                                @switch="switchSession"
                                @new-session="handleNewSession"
                                @sessions-loaded="handleSessionsLoaded"
                            />
                        </div>
                    </template>
                    <!-- Member mode: show member info (click to open profile) -->
                    <template v-else>
                        <div class="flex min-w-0 items-center cursor-pointer transition-opacity hover:opacity-80" @click="memberProfileOpen = true">
                            <div :class="[embedded ? 'w-6 h-6 mr-1.5' : 'w-8 h-8 mr-2', 'rounded-full flex items-center justify-center overflow-hidden flex-shrink-0', activeContact?.avatar_url ? '' : 'bg-gray-100']">
                                <img v-if="activeContact?.avatar_url" :src="activeContact.avatar_url" class="w-full h-full object-cover" />
                                <span v-else :class="[embedded ? 'text-xs' : 'text-sm', 'font-medium text-gray-500']">{{ (activeContact?.name || '?')[0] }}</span>
                            </div>
                            <h2 :class="[embedded ? 'text-xs' : 'text-base', 'min-w-0 truncate font-medium text-gray-800']">{{ activeContact?.name }}</h2>
                            <span v-if="activeContact?.position" :class="[embedded ? 'ml-1.5 text-[10px]' : 'ml-2 text-xs', 'min-w-0 truncate text-gray-400']">{{ activeContact.position }}</span>
                            <AiEmployeeBadge v-if="activeContact?.is_virtual" :class="[embedded ? 'ml-1 scale-90' : 'ml-1.5', 'flex-shrink-0']" />
                            <VortTooltip v-if="activeContact?.remote_node_id" :title="['online', 'running'].includes(activeContact.remote_node_status) ? '工作节点在线' : ['offline', 'stopped', 'error'].includes(activeContact.remote_node_status) ? '工作节点离线' : '工作节点状态未知'">
                                <span class="inline-block w-2 h-2 rounded-full ml-1.5 flex-shrink-0"
                                    :class="['online', 'running'].includes(activeContact.remote_node_status) ? 'bg-green-500' : ['offline', 'stopped', 'error'].includes(activeContact.remote_node_status) ? 'bg-red-400' : 'bg-gray-300'" />
                            </VortTooltip>
                        </div>
                    </template>
                    <span v-if="loading" class="ml-3 flex flex-shrink-0 items-center whitespace-nowrap text-xs text-gray-400">
                        <Loader2 :size="14" class="animate-spin mr-1" /> 思考中...
                    </span>
                </div>
                <div class="flex flex-shrink-0 items-center gap-2">
                    <template v-if="!embedded">
                        <VortTooltip :overlay-style="{ maxWidth: 'none' }">
                            <template #title>
                                <div class="flex flex-col leading-tight">
                                    <span>输入 tokens: {{ formatTokens(sessionTokens.input) }} / 输出 tokens: {{ formatTokens(sessionTokens.output) }} / 缓存命中: {{ formatTokens(sessionTokens.cacheRead) }} / 消息数: {{ sessionTokens.messages }}</span>
                                    <span class="text-[11px] text-gray-400 mt-1">Token 统计受模型网关返回影响，可能存在偏差</span>
                                </div>
                            </template>
                            <span class="text-xs text-gray-400 flex items-center gap-1 cursor-default">
                                <Zap :size="14" />
                                {{ formatTokens(sessionTokens.input + sessionTokens.output) }}
                            </span>
                        </VortTooltip>
                        <VortPopover v-model:open="searchOpen" trigger="click" placement="bottomRight" :arrow="false">
                            <VortTooltip title="搜索消息">
                                <button class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer">
                                    <Search :size="16" />
                                </button>
                            </VortTooltip>
                            <template #content>
                                <div class="w-[320px] -m-1">
                                    <input
                                        v-model="searchQuery"
                                        placeholder="输入关键词搜索消息..."
                                        class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400"
                                        @input="handleSearch"
                                        @keydown.enter="handleSearch"
                                    />
                                    <div v-if="searching" class="py-3 text-center text-xs text-gray-400">搜索中...</div>
                                    <div v-else-if="searchResults.length" class="max-h-[300px] overflow-y-auto mt-2 space-y-1">
                                        <div
                                            v-for="r in searchResults" :key="r.id"
                                            class="px-3 py-2 rounded-lg hover:bg-gray-50 cursor-pointer"
                                            @click="searchOpen = false"
                                        >
                                            <div class="text-xs text-gray-400">{{ r.sender_type === 'user' ? '我' : 'AI' }} - {{ r.created_at?.slice(0, 10) }}</div>
                                            <div class="text-sm text-gray-700 line-clamp-2 mt-0.5">{{ r.content }}</div>
                                        </div>
                                    </div>
                                    <div v-else-if="searchQuery.length >= 2" class="py-3 text-center text-xs text-gray-400">无结果</div>
                                </div>
                            </template>
                        </VortPopover>
                        <VortPopover v-model:open="thinkingOpen" trigger="click" placement="bottomRight" :arrow="false">
                            <VortTooltip title="Thinking 级别">
                                <button class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer">
                                    <Brain :size="16" :class="thinkingLevel !== 'off' ? 'text-blue-500' : ''" />
                                </button>
                            </VortTooltip>
                            <template #content>
                                <div class="w-[200px] -m-1">
                                    <div v-for="lvl in ['off', 'low', 'medium', 'high']" :key="lvl"
                                        @click="handleThinkingChange(lvl)"
                                        class="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors"
                                        :class="thinkingLevel === lvl ? 'bg-blue-50' : 'hover:bg-gray-50'">
                                        <Check :size="14" :class="thinkingLevel === lvl ? 'text-blue-600' : 'text-transparent'" />
                                        <span class="text-sm text-gray-700 capitalize">{{ lvl }}</span>
                                    </div>
                                </div>
                            </template>
                        </VortPopover>
                        <VortTooltip title="压缩上下文">
                            <button class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer"
                                :disabled="compacting" @click="handleCompact">
                                <PackageMinus :size="16" :class="compacting ? 'animate-pulse' : ''" />
                            </button>
                        </VortTooltip>
                    </template>
                    <VortTooltip title="重置上下文">
                        <button class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer"
                            @click="handleReset">
                            <RotateCcw :size="16" />
                        </button>
                    </VortTooltip>
                    <template v-if="embedded">
                        <VortTooltip :title="embeddedExpanded ? '缩小窗口' : '展开半屏'">
                            <button class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer"
                                @click="emit('embedded-maximize')">
                                <Minimize2 v-if="embeddedExpanded" :size="14" />
                                <Maximize2 v-else :size="14" />
                            </button>
                        </VortTooltip>
                        <VortTooltip title="关闭">
                            <button class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer"
                                @click="emit('embedded-close')">
                                <X :size="14" />
                            </button>
                        </VortTooltip>
                    </template>
                </div>
            </div>

            <!-- Offline summary banner -->
            <div v-if="!embedded && offlineSummary" class="mx-4 mt-3 mb-1">
                <div class="relative overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                    <div class="absolute inset-y-0 left-0 w-1 bg-blue-500" />
                    <div class="flex items-start gap-3 px-4 py-4 pl-5">
                        <div class="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-blue-50 text-blue-600">
                            <Clock :size="16" />
                        </div>
                        <div class="min-w-0 flex-1">
                            <div class="flex flex-wrap items-center gap-2">
                                <div class="text-sm font-semibold text-slate-800">离开期间未读消息</div>
                                <span class="inline-flex items-center rounded-full border border-blue-100 bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                                    {{ offlineSummary.unreads }} 条
                                </span>
                            </div>
                            <p class="mt-1 text-xs text-slate-500">为你摘取了最近的关键消息，方便快速回看。</p>
                            <div v-if="offlineSummary.highlights.length" class="mt-3 space-y-2">
                                <div
                                    v-for="(h, i) in offlineSummary.highlights.slice(0, 3)"
                                    :key="i"
                                    class="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600 line-clamp-2"
                                >
                                    {{ h }}
                                </div>
                            </div>
                            <div v-if="offlineSummary.highlights.length > 3" class="mt-2 text-xs text-slate-400">
                                还有 {{ offlineSummary.highlights.length - 3 }} 条摘要未展开
                            </div>
                        </div>
                        <button
                            class="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
                            @click="dismissOfflineSummary"
                        >
                            <X :size="14" />
                        </button>
                    </div>
                </div>
            </div>

            <!-- 重置后：重新加载会话记录按钮 -->
            <div v-if="!embedded && contextResetAt > 0 && currentSessionId" class="flex justify-center py-2 ">
                <button
                    class="text-xs text-blue-500 hover:text-blue-600 cursor-pointer transition-colors flex items-center gap-1"
                    :disabled="loadingMore"
                    @click="handleReloadHistory"
                >
                    <Loader2 v-if="loadingMore" :size="14" class="animate-spin" />
                    <RefreshCw v-else :size="14" />
                    <span>{{ loadingMore ? '加载中...' : '重新加载会话记录' }}</span>
                </button>
            </div>

            <!-- 消息列表 -->
            <VortScrollbar ref="chatScrollbar" class="flex-1" :wrap-class="embedded ? 'px-4 py-3' : 'px-6 py-4'" view-class="flex flex-col min-h-full">
                <VortImagePreviewGroup class="space-y-6">
                    <!-- 无会话状态 -->
                    <div v-if="!currentSessionId && isAiMode" class="flex flex-col items-center justify-center flex-1 text-gray-400">
                        <img :src="aiAvatarUrl" class="w-12 h-12 rounded-full object-cover mb-4" />
                        <p class="text-sm">你好，我是 OpenVort AI 助手</p>
                        <p class="text-xs mt-1">开始新的对话吧</p>
                    </div>
                    <!-- 空消息状态 -->
                    <div v-else-if="messages.length === 0 && !loading" class="flex flex-col items-center justify-center flex-1 text-gray-400">
                        <img v-if="isAiMode" :src="aiAvatarUrl" class="w-12 h-12 rounded-full object-cover mb-4" />
                        <div v-else class="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-4">
                            <span class="text-lg font-medium text-gray-400">{{ (activeContact?.name || '?')[0] }}</span>
                        </div>
                        <p class="text-sm">{{ isAiMode ? '你好，我是 OpenVort AI 助手' : `与 ${activeContact?.name} 的对话` }}</p>
                        <p class="text-xs mt-1">{{ isAiMode ? '可以帮你管理任务、查询 Bug、了解项目进展' : 'AI 将以该成员的身份背景为你提供上下文相关的对话' }}</p>
                    </div>

                    <!-- 滚动到顶加载更多指示器 -->
                    <div v-if="loadingMore && messages.length > 0" class="flex justify-center py-2">
                        <Loader2 :size="16" class="animate-spin text-gray-400" />
                    </div>

                    <!-- 全部历史已加载标记 -->
                    <div v-if="messages.length > 0 && historyOffset > 0 && !hasMoreHistory && !loadingMore" class="flex justify-center py-2">
                        <span class="text-xs text-gray-300 select-none">- 已加载全部历史记录 -</span>
                    </div>

                    <!-- 消息气泡 -->
                    <template v-for="(msg, msgIdx) in messages" :key="msg.id">
                    <div v-if="shouldShowTimestamp(messages, msgIdx)" class="chat-time-divider flex justify-center my-3">
                        <span class="text-xs text-gray-400 px-3 py-0.5 rounded-full select-none">{{ formatTimeDivider(msg.timestamp) }}</span>
                    </div>
                    <div class="flex group" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
                            <div class="flex min-w-0" :class="[msg.role === 'user' ? 'flex-row-reverse max-w-[80%]' : 'flex-row max-w-[min(80%,640px)]']">
                            <div class="flex-shrink-0 relative" :class="msg.role === 'user' ? 'ml-3' : 'mr-3'">
                                <!-- 用户消息头像 -->
                                <div v-if="msg.role === 'user'" class="w-8 h-8 rounded-full flex items-center justify-center bg-blue-600">
                                    <span class="text-white text-xs font-medium">{{ (userStore.userInfo.name || 'U')[0] }}</span>
                                </div>
                                <!-- AI 回复头像 -->
                                <div v-else class="w-8 h-8 rounded-full flex items-center justify-center overflow-hidden"
                                    :class="[
                                        isAiMode ? 'bg-gray-100' : ((msg.avatar_url || activeContact?.avatar_url) ? '' : 'bg-gray-100'),
                                        !isAiMode ? 'cursor-pointer hover:opacity-80 transition-opacity' : ''
                                    ]"
                                    @click="!isAiMode && (memberProfileOpen = true)">
                                    <!-- AI 模式：显示头像 -->
                                    <template v-if="isAiMode">
                                        <img :src="aiAvatarUrl" class="w-full h-full object-cover" />
                                    </template>
                                    <!-- 成员聊天模式：显示成员头像 -->
                                    <template v-else>
                                        <img v-if="msg.avatar_url || activeContact?.avatar_url" :src="msg.avatar_url || activeContact?.avatar_url" class="w-full h-full object-cover" />
                                        <span v-else class="text-sm font-medium text-gray-500">{{ (activeContact?.name || '?')[0] }}</span>
                                        <!-- AI 小标识 -->
                                        <div class="absolute -top-1 -right-1 w-4 h-4 bg-blue-500 rounded-full flex items-center justify-center">
                                            <Bot :size="10" class="text-white" />
                                        </div>
                                    </template>
                                </div>
                            </div>
                            <div class="min-w-0 overflow-hidden">
                                <div v-if="msg.role === 'user' && msg.images?.length" class="flex flex-wrap gap-2 mb-2 justify-end">
                                    <VortImage v-for="(src, i) in msg.images" :key="i" :src="src"
                                        width="80" height="80" fit="cover"
                                        class="rounded-lg border border-white/30" />
                                </div>
                                <div v-if="msg.role === 'user' && msg.files?.length" class="flex flex-wrap gap-2 mb-2 justify-end">
                                    <a v-for="(f, fi) in msg.files" :key="fi"
                                        :href="f.file_url" target="_blank"
                                        class="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-blue-500/20 text-white text-xs hover:bg-blue-500/30 transition-colors max-w-[200px]">
                                        <Paperclip :size="12" class="flex-shrink-0" />
                                        <span class="truncate">{{ f.filename }}</span>
                                    </a>
                                </div>
                            <!-- 桌面视角面板 -->
                            <WorkspaceViewer
                                v-if="msg.toolCalls?.some(t => t.name.startsWith('node_'))"
                                :node-id="activeContact?.remote_node_id"
                                :is-working="msg.streaming && getStreamPhase(msg) === 'tool_running'"
                                :terminal-output="getAccumulatedOutput(msg)"
                                :recent-files="getRecentFileChanges(msg)"
                                :has-browser="msg.toolCalls?.some(t => t.name === 'node_browse')"
                            />
                            <!-- 流式进行中：所有工具调用显示在气泡上方 -->
                            <div v-if="msg.streaming && msg.toolCalls?.length" class="mb-2 space-y-1">
                                <div v-for="(tool, i) in msg.toolCalls" :key="'live-' + i" class="block">
                                    <div class="inline-flex items-center px-2 py-1 rounded text-xs cursor-pointer select-none"
                                        :class="tool.status === 'running' ? 'bg-yellow-50 text-yellow-700' : 'bg-green-50 text-green-700'"
                                        @click="tool.output && !tool.hasLiveOutput && toggleToolCollapsed(tool)">
                                        <component :is="tool.collapsed ? ChevronRight : ChevronDown" v-if="tool.output && !tool.hasLiveOutput" :size="12" class="mr-0.5 flex-shrink-0" />
                                        <Wrench :size="12" class="mr-1 flex-shrink-0" />
                                        {{ tool.name }}
                                        <span v-if="tool.input?.command" class="ml-1 opacity-60 font-mono truncate max-w-xs">$ {{ tool.input.command.substring(0, 80) }}{{ tool.input.command.length > 80 ? '...' : '' }}</span>
                                        <span v-else-if="tool.input?.path" class="ml-1 opacity-60 font-mono truncate max-w-xs">{{ tool.input.path }}</span>
                                        <span v-if="(tool.count || 1) > 1" class="ml-1 opacity-70">&times;{{ tool.count }}</span>
                                        <template v-if="tool.status === 'running'">
                                            <Loader2 :size="12" class="ml-1 animate-spin" />
                                            <span v-if="tool.elapsed" class="ml-1 text-yellow-500">{{ formatToolElapsed(tool.elapsed) }}</span>
                                        </template>
                                    </div>
                                    <div v-if="tool.output && (tool.hasLiveOutput ? true : !tool.collapsed)"
                                        :ref="(el: any) => { if (el) el.scrollTop = el.scrollHeight }"
                                        class="mt-1 ml-1 max-h-60 overflow-y-auto rounded-lg bg-gray-900 text-green-400 text-xs font-mono px-3 py-2 whitespace-pre-wrap break-words leading-5 border border-gray-700/50 shadow-inner">{{ tool.output }}</div>
                                    <!-- 工具截图 -->
                                    <div v-if="tool.screenshots?.length" class="mt-2 ml-1 flex flex-wrap gap-2">
                                        <VortImage v-for="(screenshot, idx) in tool.screenshots" :key="idx"
                                            :src="'data:image/png;base64,' + screenshot"
                                            :preview-src-list="tool.screenshots.map(s => 'data:image/png;base64,' + s)"
                                            :initial-index="idx"
                                            fit="contain"
                                            class="rounded-lg border border-gray-600 cursor-pointer"
                                            style="max-width: 200px; max-height: 150px;" />
                                    </div>
                                </div>
                            </div>
                            <!-- "正在思考..."指示器: tool_result 后等待下一轮 LLM -->
                            <div v-if="msg.streaming && getStreamPhase(msg) === 'thinking' && msg.toolCalls?.length && !msg.content" class="flex items-center gap-1.5 px-2 py-1.5 text-xs text-gray-400 mb-1">
                                <Loader2 :size="12" class="animate-spin" />
                                正在思考...
                            </div>
                            <!-- 已完成的工具调用（历史加载时，显示在气泡上方可展开）-->
                            <div v-if="!msg.streaming && msg.toolCalls?.length" class="mb-2">
                                <button
                                    class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer select-none"
                                    @click="toggleToolsExpanded(msg)">
                                    <component :is="msg.toolsExpanded ? ChevronDown : ChevronRight" :size="14" />
                                    <Wrench :size="12" />
                                    <span>工具调用 ({{ msg.toolCalls.reduce((s, t) => s + (t.count || 1), 0) }})</span>
                                </button>
                                <div v-if="msg.toolsExpanded" class="mt-1.5 space-y-1.5 pl-1">
                                    <div v-for="(tool, i) in msg.toolCalls" :key="'done-' + i" class="block">
                                        <div class="inline-flex items-center px-2 py-1 rounded text-xs bg-green-50 text-green-700 cursor-pointer select-none hover:bg-green-100"
                                            @click="tool.output && toggleToolCollapsed(tool)">
                                            <component :is="tool.collapsed ? ChevronRight : ChevronDown" v-if="tool.output" :size="12" class="mr-0.5 flex-shrink-0" />
                                            <Wrench :size="12" class="mr-1 flex-shrink-0" />
                                            {{ tool.name }}
                                            <span v-if="tool.input?.command" class="ml-1 opacity-60 font-mono truncate max-w-xs">$ {{ tool.input.command.substring(0, 80) }}{{ tool.input.command.length > 80 ? '...' : '' }}</span>
                                            <span v-else-if="tool.input?.path" class="ml-1 opacity-60 font-mono truncate max-w-xs">{{ tool.input.path }}</span>
                                            <span v-if="(tool.count || 1) > 1" class="ml-1 opacity-70">&times;{{ tool.count }}</span>
                                        </div>
                                        <div v-if="tool.output && !tool.collapsed" class="mt-1 ml-1 rounded-lg bg-gray-900 text-green-400 text-xs font-mono px-3 py-2 border border-gray-700/50 shadow-inner">
                                            <template v-if="getOutputLineCount(tool.output) > 30 && !tool.outputExpanded">
                                                <div class="text-gray-500 text-center py-1 cursor-pointer hover:text-gray-300" @click="tool.outputExpanded = true">... 共 {{ getOutputLineCount(tool.output) }} 行，点击展开全部 ...</div>
                                                <pre class="whitespace-pre-wrap max-h-40 overflow-y-auto break-words leading-5">{{ getLastLines(tool.output, 20) }}</pre>
                                            </template>
                                            <pre v-else class="whitespace-pre-wrap max-h-60 overflow-y-auto break-words leading-5">{{ tool.output }}</pre>
                                        </div>
                                        <!-- 工具截图 -->
                                        <div v-if="tool.screenshots?.length" class="mt-2 ml-1 flex flex-wrap gap-2">
                                            <VortImage v-for="(screenshot, idx) in tool.screenshots" :key="idx"
                                                :src="'data:image/png;base64,' + screenshot"
                                                :preview-src-list="tool.screenshots.map(s => 'data:image/png;base64,' + s)"
                                                :initial-index="idx"
                                                fit="contain"
                                                class="rounded-lg border border-gray-600 cursor-pointer"
                                                style="max-width: 200px; max-height: 150px;" />
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div
                                v-if="msg.role === 'assistant' || msg.content"
                                class="rounded-2xl px-4 py-3 text-sm leading-relaxed"
                                :class="msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-800'">
                                <div v-if="msg.role === 'assistant' && msg.content"
                                    class="prose prose-sm max-w-none prose-p:my-1 prose-pre:my-2">
                                    <div v-html="renderMarkdown(msg.content)" />
                                    <span v-if="msg.streaming" class="streaming-cursor" />
                                    <span v-if="msg.interrupted" class="text-xs text-gray-400 ml-2">[已中止]</span>
                                </div>
                                <span v-else-if="msg.role === 'assistant' && !msg.content && loading" class="flex items-center">
                                    <span class="flex space-x-1">
                                        <span class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms" />
                                        <span class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms" />
                                        <span class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms" />
                                    </span>
                                </span>
                                <template v-else>{{ msg.content }}</template>
                            </div>
                            <!-- Action buttons (e.g. "一键配置工作电脑") -->
                            <div v-if="msg.actionButtons?.length" class="mt-2 flex flex-wrap gap-2">
                                <button v-for="(btn, bi) in msg.actionButtons" :key="bi"
                                    :disabled="btn.clicked || btn.loading"
                                    @click="handleActionButton(msg, btn)"
                                    class="inline-flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border transition-colors cursor-pointer"
                                    :class="btn.clicked ? 'border-gray-200 text-gray-400 bg-gray-50' : 'border-blue-200 text-blue-600 hover:bg-blue-50'">
                                    <Loader2 v-if="btn.loading" :size="12" class="animate-spin" />
                                    {{ btn.clicked ? '已完成' : btn.label }}
                                </button>
                            </div>
                            <!-- Message action buttons -->
                            <div v-if="!msg.streaming && msg.content"
                                class="flex mt-1 gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                                :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
                                <vort-tooltip title="复制">
                                    <button @click="copyMessageContent(msg)"
                                        class="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors cursor-pointer">
                                        <Copy :size="14" />
                                    </button>
                                </vort-tooltip>
                                <vort-tooltip v-if="msg.role === 'user'" title="重新发送">
                                    <button @click="resendMessage(msg)"
                                        class="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors cursor-pointer"
                                        :disabled="loading">
                                        <RefreshCw :size="14" />
                                    </button>
                                </vort-tooltip>
                                <vort-tooltip title="删除">
                                    <button @click="removeMessage(msg)"
                                        class="p-1 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors cursor-pointer">
                                        <Trash2 :size="14" />
                                    </button>
                                </vort-tooltip>
                            </div>
                        </div>
                    </div>
                </div>
                </template>
                </VortImagePreviewGroup>
            </VortScrollbar>

            <!-- AI employee active tasks bar -->
            <div v-if="!embedded && activeContact?.is_virtual && activeAssignments.length > 0"
                class="mx-6 pt-2 mb-0 flex items-center gap-1.5 text-xs">
                <span class="text-gray-400 text-xs leading-none mr-0.5 flex-shrink-0">{{ activeAssignments.length }} 项进行中任务{{ taskBarCollapsed ? '' : '：' }}</span>
                <template v-if="!taskBarCollapsed">
                    <div class="flex items-center gap-1.5 flex-wrap min-w-0 flex-1">
                        <span v-for="a in activeAssignments.slice(0, 4)" :key="a.id"
                            @click="memberProfileOpen = true"
                            class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded cursor-pointer whitespace-nowrap max-w-[200px] transition-colors"
                            :class="{
                                'bg-purple-50 text-purple-600 hover:bg-purple-100': a.status === 'ongoing',
                                'bg-amber-50 text-amber-600 hover:bg-amber-100': a.status === 'pending',
                                'bg-blue-50 text-blue-600 hover:bg-blue-100': a.status === 'in_progress',
                                'bg-gray-50 text-gray-400 hover:bg-gray-100': a.status === 'paused',
                            }">
                            <Pause v-if="a.status === 'paused'" :size="10" class="flex-shrink-0" />
                            <span v-else :class="{
                                'bg-purple-500 animate-pulse': a.status === 'ongoing',
                                'bg-amber-400': a.status === 'pending',
                                'bg-blue-500 animate-pulse': a.status === 'in_progress',
                            }" class="inline-block w-1.5 h-1.5 rounded-full flex-shrink-0" />
                            <span class="truncate">{{ a.status === 'paused' ? '[已暂停] ' : '' }}{{ a.title }}</span>
                        </span>
                        <span v-if="activeAssignments.length > 4"
                            @click="memberProfileOpen = true"
                            class="text-gray-400 text-[10px] cursor-pointer hover:text-blue-500">+{{ activeAssignments.length - 4 }}</span>
                        <button @click="toggleTaskBar"
                            class="text-gray-300 hover:text-gray-500 transition-colors cursor-pointer flex-shrink-0 p-0.5">
                            <ChevronUp :size="14" />
                        </button>
                    </div>
                </template>
                <button v-if="taskBarCollapsed" @click="toggleTaskBar"
                    class="text-gray-300 hover:text-gray-500 transition-colors cursor-pointer flex-shrink-0 p-0.5">
                    <ChevronDown :size="14" />
                </button>
            </div>

            <!-- 输入区域 -->
            <div :class="embedded ? 'relative px-3 pt-2 pb-3' : 'relative px-6 pt-2.5 pb-4'" ref="inputArea"
                @dragover="handleDragOver" @dragleave="handleDragLeave" @drop="handleDrop">
                <div v-if="isDragging"
                    class="absolute inset-0 z-10 flex items-center justify-center bg-blue-50/80 border-2 border-dashed border-blue-400 rounded-xl pointer-events-none">
                    <div class="text-blue-500 text-sm font-medium flex items-center gap-2">
                        <ImagePlus :size="20" /> 松开以添加文件
                    </div>
                </div>

                <!-- @mention 弹出面板 (directly positioned, bottom-aligned) -->
                <Transition name="vort-popover">
                    <div v-if="showMentionPanel"
                        class="mention-panel absolute z-50 bottom-full mb-2"
                        :style="{ left: panelStyle.left }">
                        <div class="w-[280px] bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden">
                            <div class="px-3 py-2 text-xs text-gray-400 border-b border-gray-100">提及成员</div>
                            <VortScrollbar max-height="240px">
                                <div class="py-1">
                                    <div v-for="(member, i) in mentionMembers" :key="member.id"
                                        :data-mention-index="i"
                                        class="flex items-center gap-2.5 px-3 py-2 cursor-pointer transition-colors"
                                        :class="i === mentionActiveIndex ? 'bg-blue-50' : 'hover:bg-gray-50'"
                                        @click="selectMention(member)"
                                        @mouseenter="mentionActiveIndex = i">
                                        <div
                                            class="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 overflow-hidden"
                                            :class="member.avatar_url ? 'bg-gray-100' : 'bg-blue-100 text-blue-600'"
                                        >
                                            <img v-if="member.avatar_url" :src="member.avatar_url" class="w-full h-full object-cover" />
                                            <span v-else class="text-xs font-medium">{{ member.name.charAt(0) }}</span>
                                        </div>
                                        <div class="min-w-0 flex-1">
                                            <div class="text-sm text-gray-800 truncate">{{ member.name }}</div>
                                            <div v-if="member.email" class="text-xs text-gray-400 truncate">{{ member.email }}</div>
                                        </div>
                                    </div>
                                </div>
                            </VortScrollbar>
                        </div>
                    </div>
                </Transition>

                <!-- /command 弹出面板 -->
                <Transition name="vort-popover">
                    <div v-if="showCommandPanel"
                        class="mention-panel absolute z-50 bottom-full mb-2"
                        :style="{ left: panelStyle.left }">
                        <div class="w-[320px] bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden">
                            <div class="px-3 py-2 text-xs text-gray-400 border-b border-gray-100">快捷命令</div>
                            <VortScrollbar max-height="240px">
                                <div class="py-1">
                                    <div v-for="(cmd, i) in filteredCommands" :key="cmd.name"
                                        :data-command-index="i"
                                        class="flex items-center gap-2.5 px-3 py-2 cursor-pointer transition-colors"
                                        :class="i === commandActiveIndex ? 'bg-blue-50' : 'hover:bg-gray-50'"
                                        @click="selectCommand(cmd)"
                                        @mouseenter="commandActiveIndex = i">
                                        <div class="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
                                            <Zap :size="14" class="text-gray-500" />
                                        </div>
                                        <div class="min-w-0 flex-1">
                                            <div class="text-sm text-gray-800 font-mono">{{ cmd.label }}</div>
                                            <div class="text-xs text-gray-400">{{ cmd.description }}</div>
                                        </div>
                                    </div>
                                </div>
                            </VortScrollbar>
                        </div>
                    </div>
                </Transition>

                <!-- #tag 弹出面板 -->
                <Transition name="vort-popover">
                    <div v-if="showHashTagPanel"
                        class="mention-panel absolute z-50 bottom-full mb-2"
                        :style="{ left: panelStyle.left }">
                        <div class="w-[340px] bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden">
                            <div class="px-3 py-2 text-xs text-gray-400 border-b border-gray-100 flex items-center gap-1">
                                <Hash :size="12" />
                                <template v-if="hashTagLevel === 'category'">引用工作项</template>
                                <template v-else>
                                    <span class="cursor-pointer hover:text-blue-500" @click="hashTagLevel = 'category'; hashTagSelectedCategory = null; hashTagQuery = ''">引用工作项</span>
                                    <span class="mx-0.5">/</span>
                                    <span class="text-gray-600">{{ hashTagSelectedCategory?.description }}</span>
                                </template>
                            </div>
                            <!-- Category level -->
                            <template v-if="hashTagLevel === 'category'">
                                <div class="py-1">
                                    <div v-for="(cat, i) in filteredHashTagCategories" :key="cat.key"
                                        :data-hashtag-index="i"
                                        class="flex items-center gap-2.5 px-3 py-2.5 cursor-pointer transition-colors"
                                        :class="i === hashTagActiveIndex ? 'bg-blue-50' : 'hover:bg-gray-50'"
                                        @click="selectHashTagCategory(cat)"
                                        @mouseenter="hashTagActiveIndex = i">
                                        <div class="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                                            :class="cat.key === 'bug' ? 'bg-red-50 text-red-500' : cat.key === 'task' ? 'bg-blue-50 text-blue-500' : cat.key === 'story' ? 'bg-green-50 text-green-500' : 'bg-purple-50 text-purple-500'">
                                            <Bug v-if="cat.key === 'bug'" :size="14" />
                                            <ListTodo v-else-if="cat.key === 'task'" :size="14" />
                                            <BookOpen v-else :size="14" />
                                        </div>
                                        <div class="min-w-0 flex-1">
                                            <div class="text-sm text-gray-800 font-medium">{{ cat.label }}</div>
                                            <div class="text-xs text-gray-400">{{ cat.description }}</div>
                                        </div>
                                    </div>
                                    <div v-if="filteredHashTagCategories.length === 0" class="px-3 py-4 text-xs text-gray-400 text-center">
                                        无匹配的分类
                                    </div>
                                </div>
                            </template>
                            <!-- Items level -->
                            <template v-else>
                                <VortScrollbar max-height="280px">
                                    <div v-if="hashTagItemsLoading" class="flex items-center justify-center py-6">
                                        <Loader2 :size="16" class="animate-spin text-gray-400" />
                                        <span class="ml-2 text-xs text-gray-400">加载中...</span>
                                    </div>
                                    <div v-else-if="filteredHashTagItems.length === 0" class="px-3 py-4 text-xs text-gray-400 text-center">
                                        暂无数据，可输入 ID 或名称筛选
                                    </div>
                                    <div v-else class="py-1">
                                        <div v-for="(item, i) in filteredHashTagItems" :key="item.id"
                                            :data-hashtag-index="i"
                                            class="flex items-center gap-2.5 px-3 py-2 cursor-pointer transition-colors"
                                            :class="i === hashTagActiveIndex ? 'bg-blue-50' : 'hover:bg-gray-50'"
                                            @click="selectHashTagItem(item)"
                                            @mouseenter="hashTagActiveIndex = i">
                                            <div class="min-w-0 flex-1">
                                                <div class="text-sm text-gray-800 truncate">{{ item.title }}</div>
                                                <div class="flex items-center gap-2 mt-0.5">
                                                    <span class="text-gray-400 font-mono text-xs truncate max-w-[180px]">#{{ item.id }}</span>
                                                    <span v-if="item.state" class="text-xs text-gray-400">{{ item.state }}</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </VortScrollbar>
                            </template>
                        </div>
                    </div>
                </Transition>

                <div class="chat-input-box bg-white rounded-xl border border-gray-200 overflow-hidden relative">
                    <div v-if="pendingImages.length || pendingFiles.length" class="flex flex-wrap gap-2 px-4 pt-3">
                        <div v-for="(img, i) in pendingImages" :key="'img-' + i" class="relative group">
                            <VortImage :src="img.preview" width="72" height="72" fit="cover"
                                class="rounded-lg border border-gray-200 shadow-sm" />
                            <button @click="removeImage(i)"
                                class="absolute -top-1.5 -right-1.5 w-5 h-5 bg-black/60 hover:bg-black/80 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                <X :size="12" />
                            </button>
                        </div>
                        <div v-for="(f, i) in pendingFiles" :key="'file-' + i"
                            class="relative group flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 bg-gray-50 max-w-[220px]">
                            <Loader2 v-if="f.uploading" :size="16" class="animate-spin text-gray-400 flex-shrink-0" />
                            <File v-else :size="16" class="text-blue-500 flex-shrink-0" />
                            <div class="min-w-0 flex-1">
                                <div class="text-xs text-gray-700 truncate">{{ f.filename }}</div>
                                <div class="text-[10px] text-gray-400">{{ formatFileSize(f.file_size) }}</div>
                            </div>
                            <button @click="removeFile(i)"
                                class="w-4 h-4 flex items-center justify-center rounded-full text-gray-300 hover:text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                                <X :size="12" />
                            </button>
                        </div>
                    </div>
                    <VortTextarea
                        v-model="inputText"
                        :placeholder="embedded ? '输入你的问题...' : '请描述您问题，支持 Ctrl+V 粘贴图片。输入 @ 提及成员，/ 使用命令，# 引用工作项。'"
                        :auto-size="embedded ? { minRows: 1, maxRows: 4 } : { minRows: 3, maxRows: 6 }"
                        :bordered="false"
                        :class="embedded ? 'chat-textarea-compact' : 'chat-textarea'"
                        @press-enter="handlePressEnter"
                    />
                    <div :class="embedded ? 'flex items-center justify-between px-3 py-1.5' : 'flex items-center justify-between px-4 py-2'">
                        <div class="flex items-center gap-1">
                            <VortPopover placement="top" :arrow="true">
                                <button @click="triggerFileInput"
                                    :class="embedded ? 'p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer' : 'p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer'">
                                    <FileText :size="embedded ? 16 : 18" />
                                </button>
                                <template #content>
                                    <span class="text-xs text-gray-500 whitespace-nowrap">.jpg,.jpeg,.png,.txt,.rar,.zip,.doc,.docx,.xls,.7z</span>
                                </template>
                            </VortPopover>
                            <VortPopover placement="top" :arrow="true">
                                <button @click="triggerVideoInput"
                                    :class="embedded ? 'p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer' : 'p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer'">
                                    <MonitorPlay :size="embedded ? 16 : 18" />
                                </button>
                                <template #content>
                                    <span class="text-xs text-gray-500 whitespace-nowrap">.mp4,.mov,.avi,.wmv,.flv,.mkv</span>
                                </template>
                            </VortPopover>
                            <VortPopover v-model:open="emojiOpen" trigger="click" placement="topLeft" :arrow="false" :overlay-style="{ maxWidth: '424px' }">
                                <button :class="embedded ? 'p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer' : 'p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer'">
                                    <Smile :size="embedded ? 16 : 18" />
                                </button>
                                <template #content>
                                    <div class="emoji-grid">
                                        <button v-for="(emoji, i) in emojis" :key="i"
                                            @click="insertEmoji(emoji)"
                                            class="w-9 h-9 flex items-center justify-center text-xl rounded-md hover:bg-gray-100 transition-colors cursor-pointer">
                                            {{ emoji }}
                                        </button>
                                    </div>
                                </template>
                            </VortPopover>
                        </div>
                        <div class="flex items-center gap-2">
                            <VortPopover v-if="!embedded" v-model:open="settingsOpen" trigger="click" placement="topRight" :arrow="false">
                                <button class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer">
                                    <Settings :size="18" />
                                </button>
                                <template #content>
                                    <div class="w-[280px] -m-1">
                                        <div @click="setSendMode('enter')"
                                            class="flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors"
                                            :class="sendMode === 'enter' ? 'bg-blue-50' : 'hover:bg-gray-50'">
                                            <Check :size="16" :class="sendMode === 'enter' ? 'text-blue-600' : 'text-transparent'" />
                                            <span class="text-sm text-gray-700">按 Enter 快捷发送；Ctrl+Enter 换行</span>
                                        </div>
                                        <div @click="setSendMode('ctrl-enter')"
                                            class="flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors"
                                            :class="sendMode === 'ctrl-enter' ? 'bg-blue-50' : 'hover:bg-gray-50'">
                                            <Check :size="16" :class="sendMode === 'ctrl-enter' ? 'text-blue-600' : 'text-transparent'" />
                                            <span class="text-sm text-gray-700">按 Ctrl+Enter 快捷发送；Enter 换行</span>
                                        </div>
                                    </div>
                                </template>
                            </VortPopover>
                            <button
                                v-if="loading"
                                :disabled="aborting"
                                @click="handleAbortCurrentStream"
                                class="rounded-lg flex items-center justify-center gap-1.5 transition-colors send-btn"
                                :class="aborting ? 'send-btn-disabled px-3 h-8' : 'send-btn-stop h-8 w-16'"
                            >
                                <Square :size="14" fill="currentColor" class="text-white" />
                                <span v-if="aborting" class="text-white text-xs">正在中止...</span>
                            </button>
                            <button
                                v-else
                                :disabled="!inputText.trim() && !pendingImages.length && !pendingFiles.length"
                                @click="handleSend"
                                :class="[
                                    embedded ? 'w-16 h-8' : 'w-20 h-9',
                                    'rounded-lg flex items-center justify-center transition-colors send-btn',
                                    !inputText.trim() && !pendingImages.length && !pendingFiles.length ? 'send-btn-disabled' : 'send-btn-active'
                                ]"
                            >
                                <Send :size="embedded ? 14 : 16" class="text-white" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Member profile drawer -->
        <MemberProfile
            v-if="!embedded && activeContact && activeContact.type === 'member'"
            v-model:open="memberProfileOpen"
            :member-id="activeContact.id"
            :member-name="activeContact.name"
            :member-avatar-url="activeContact.avatar_url"
            :is-virtual="activeContact.is_virtual"
            @assignments-changed="loadActiveAssignments"
        />
    </div>
</template>

<style scoped>
/* Markdown in chat bubbles */
.prose :deep(h1),
.prose :deep(h2),
.prose :deep(h3),
.prose :deep(h4) {
    font-size: 14px;
    font-weight: 600;
    color: #1f2937;
    margin-top: 0.8em;
    margin-bottom: 0.3em;
    line-height: 1.5;
}
.prose :deep(h1:first-child),
.prose :deep(h2:first-child),
.prose :deep(h3:first-child) {
    margin-top: 0;
}
.prose :deep(p) {
    margin: 0.4em 0;
}
.prose :deep(p:last-child) {
    margin-bottom: 0;
}
.prose :deep(ul),
.prose :deep(ol) {
    margin: 0.3em 0;
    padding-left: 1.5em;
}
.prose :deep(li) {
    margin: 0.15em 0;
}
.prose :deep(li p) {
    margin: 0;
}
.prose :deep(pre) {
    background: #1e1e1e;
    color: #d4d4d4;
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 12px;
    line-height: 1.6;
    overflow-x: auto;
    margin: 0.5em 0;
}
.prose :deep(code) {
    font-size: 12px;
    background: rgba(0, 0, 0, 0.08);
    border-radius: 4px;
    padding: 2px 5px;
}
.prose :deep(pre code) {
    background: none;
    padding: 0;
    color: inherit;
}
.prose :deep(strong) {
    font-weight: 600;
    color: #111827;
}
.prose :deep(table) {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin: 0.5em 0;
}
.prose :deep(th),
.prose :deep(td) {
    border: 1px solid #d1d5db;
    padding: 5px 10px;
    text-align: left;
}
.prose :deep(th) {
    background: rgba(0, 0, 0, 0.04);
    font-weight: 600;
    color: #374151;
}
.prose :deep(blockquote) {
    border-left: 3px solid #d1d5db;
    padding-left: 12px;
    margin: 0.5em 0;
    color: #6b7280;
    font-style: normal;
}
.prose :deep(hr) {
    border-color: #e5e7eb;
    margin: 0.8em 0;
}

.chat-textarea {
    padding: 15px 16px 12px !important;
    line-height: 1.8 !important;
}
.chat-textarea-compact {
    padding: 8px 12px 4px !important;
    line-height: 1.6 !important;
    font-size: 13px !important;
}
.chat-input-box:focus-within {
    border-color: var(--vort-primary, #1456f0);
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

.send-btn {
    color: #fff;
}
.send-btn-active {
    background-color: var(--vort-primary, #1456f0);
    cursor: pointer;
}
.send-btn-active:hover {
    background-color: var(--vort-primary-hover, #3372f7);
}
.send-btn-stop {
    background-color: var(--vort-primary, #1456f0);
    cursor: pointer;
}
.send-btn-stop:hover {
    background-color: var(--vort-primary-hover, #3372f7);
}
.send-btn-disabled {
    background-color: var(--vort-primary, #1456f0);
    opacity: 0.4;
    cursor: not-allowed;
}

.emoji-grid {
    display: grid;
    grid-template-columns: repeat(10, 1fr);
    gap: 2px;
    width: 400px;
    padding: 4px;
}

.streaming-cursor {
    display: inline-block;
    width: 2px;
    height: 1em;
    background-color: #3b82f6;
    margin-left: 2px;
    vertical-align: text-bottom;
    animation: cursor-blink 0.8s steps(2) infinite;
}
@keyframes cursor-blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

.mention-panel {
    box-shadow: 0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05);
    border-radius: 12px;
}

/* Vue Transition for popup panels */
.vort-popover-enter-active {
    animation: mention-slide-up 0.15s ease-out;
}
.vort-popover-leave-active {
    animation: mention-slide-down 0.1s ease-in;
}
@keyframes mention-slide-up {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes mention-slide-down {
    from { opacity: 1; transform: translateY(0); }
    to { opacity: 0; transform: translateY(4px); }
}
</style>
