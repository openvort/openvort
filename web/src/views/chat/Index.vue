<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch, computed } from "vue";
import { useUserStore } from "@/stores";
import {
    Send, Bot, User, Loader2, Wrench, X, ImagePlus, FileText, MonitorPlay, Smile,
    Settings, Check, Brain, PackageMinus, RotateCcw, Zap, MoreHorizontal,
    Pencil, Trash2, MessageSquare, PanelLeftClose, PanelLeftOpen, MessageSquarePlus, ListChecks
} from "lucide-vue-next";
import { Popover as VortPopover } from "@/components/vort/popover";
import {
    sendChatMessage, getChatStreamUrl, getChatHistory, getChatSessionInfo,
    setChatThinking, compactChatSession, resetChatSession,
    getChatSessions, createChatSession, renameChatSession, deleteChatSession,
    batchDeleteChatSessions
} from "@/api";
import { message } from "@/components/vort/message";
import { dialog } from "@/components/vort/dialog";
import { marked } from "marked";

interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    images?: string[];
    toolCalls?: { name: string; status: string }[];
    timestamp: number;
    streaming?: boolean;
}

interface ChatSession {
    session_id: string;
    title: string;
    created_at: number;
    updated_at: number;
}

interface PendingImage {
    data: string;
    media_type: string;
    preview: string;
}

const userStore = useUserStore();
const messages = ref<ChatMessage[]>([]);
const inputText = ref("");
const loading = ref(false);
const chatContainer = ref<HTMLElement>();
const inputArea = ref<HTMLElement>();
const pendingImages = ref<PendingImage[]>([]);
const isDragging = ref(false);
const sendMode = ref<'enter' | 'ctrl-enter'>('enter');
const settingsOpen = ref(false);
const emojiOpen = ref(false);
const thinkingLevel = ref<string>("off");
const thinkingOpen = ref(false);
const sessionTokens = ref({ input: 0, output: 0, messages: 0 });
const compacting = ref(false);
let messageCounter = 0;

// ---- 多会话状态 ----
const sessions = ref<ChatSession[]>([]);
const currentSessionId = ref<string>("");
const sessionsLoading = ref(false);
const batchMode = ref(false);
const selectedSessionIds = ref<string[]>([]);
const renamingSessionId = ref<string>("");
const renameText = ref("");
const renameInputRef = ref<HTMLInputElement>();
const sidebarCollapsed = ref(localStorage.getItem('chat-sidebar-collapsed') !== 'false');

// ---- 草稿暂存（切换会话时保留未发送内容）----
interface Draft { text: string; images: PendingImage[]; }
const drafts = new Map<string, Draft>();

function saveDraft() {
    const key = currentSessionId.value; // "" 代表新空对话
    if (inputText.value || pendingImages.value.length) {
        drafts.set(key, { text: inputText.value, images: [...pendingImages.value] });
    } else {
        drafts.delete(key);
    }
}

function restoreDraft(sessionId: string) {
    const draft = drafts.get(sessionId);
    inputText.value = draft?.text ?? "";
    pendingImages.value = draft?.images ? [...draft.images] : [];
}

watch(sidebarCollapsed, (val) => {
    localStorage.setItem('chat-sidebar-collapsed', String(val));
});

watch(currentSessionId, (val) => {
    localStorage.setItem('chat-last-session-id', val);
});

// ---- 红点 & 流式跨会话保持 ----
const unreadSessionIds = ref<Set<string>>(new Set());

interface ActiveStream {
    sessionId: string;
    eventSource: EventSource;
    assistantMsg: ChatMessage;
    targetText: string;
    done: boolean;
    twTimer: ReturnType<typeof setInterval> | null;
    messagesRef: ChatMessage[]; // 该会话的消息快照
}
const activeStreams = new Map<string, ActiveStream>();

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

const allSelected = computed(() =>
    sessions.value.length > 0 && selectedSessionIds.value.length === sessions.value.length
);

// --- 节流 scrollToBottom ---
let scrollRAF: number | null = null;
function scrollToBottom() {
    if (scrollRAF) return;
    scrollRAF = requestAnimationFrame(() => {
        scrollRAF = null;
        if (chatContainer.value) {
            chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
        }
    });
}

// --- 流式 Markdown 渲染 ---
function renderMarkdown(text: string): string {
    if (!text) return "";
    const fenceCount = (text.match(/^```/gm) || []).length;
    let patched = text;
    if (fenceCount % 2 !== 0) {
        patched += "\n```";
    }
    return marked.parse(patched, { async: false }) as string;
}

// --- 图片处理 ---
function fileToBase64(file: File): Promise<PendingImage | null> {
    return new Promise((resolve) => {
        if (!file.type.startsWith("image/")) { resolve(null); return; }
        const reader = new FileReader();
        reader.onload = () => {
            const dataUrl = reader.result as string;
            const match = dataUrl.match(/^data:(image\/[^;]+);base64,(.+)$/);
            if (match) {
                resolve({ data: match[2], media_type: match[1], preview: dataUrl });
            } else { resolve(null); }
        };
        reader.onerror = () => resolve(null);
        reader.readAsDataURL(file);
    });
}

async function addFiles(files: FileList | File[]) {
    for (const file of files) {
        if (pendingImages.value.length >= 10) break;
        const img = await fileToBase64(file);
        if (img) pendingImages.value.push(img);
    }
}

function removeImage(index: number) { pendingImages.value.splice(index, 1); }

function handlePaste(e: ClipboardEvent) {
    const items = e.clipboardData?.items;
    if (!items) return;
    const imageFiles: File[] = [];
    for (const item of items) {
        if (item.type.startsWith("image/")) {
            const file = item.getAsFile();
            if (file) imageFiles.push(file);
        }
    }
    if (imageFiles.length) { e.preventDefault(); addFiles(imageFiles); }
}

function handleDragOver(e: DragEvent) { e.preventDefault(); isDragging.value = true; }
function handleDragLeave(e: DragEvent) { e.preventDefault(); isDragging.value = false; }
function handleDrop(e: DragEvent) {
    e.preventDefault(); isDragging.value = false;
    const files = e.dataTransfer?.files;
    if (files?.length) addFiles(files);
}

// --- 多会话管理 ---
async function loadSessions() {
    sessionsLoading.value = true;
    try {
        const res: any = await getChatSessions();
        sessions.value = res?.sessions || [];
    } catch { sessions.value = []; }
    finally { sessionsLoading.value = false; }
}

function handleNewSession() {
    // 隐性新对话：只重置右侧，不立即创建会话，发第一条消息时再创建
    if (!currentSessionId.value && messages.value.length === 0) {
        message.info("已经是最新对话");
        return;
    }
    saveDraft();
    currentSessionId.value = "";
    messages.value = [];
    messageCounter = 0;
    sessionTokens.value = { input: 0, output: 0, messages: 0 };
    loading.value = false;
    thinkingLevel.value = "off";
    restoreDraft("");
}

async function switchSession(sessionId: string) {
    if (currentSessionId.value === sessionId && messages.value.length > 0) return;

    // 保存当前会话的草稿
    saveDraft();

    // 保存当前会话的流式状态（如果正在流式输出）
    const prevId = currentSessionId.value;
    if (prevId && loading.value) {
        const stream = activeStreams.get(prevId);
        if (stream) {
            stream.messagesRef = [...messages.value];
        }
    }

    currentSessionId.value = sessionId;
    messageCounter = 0;
    sessionTokens.value = { input: 0, output: 0, messages: 0 };

    // 清除红点
    unreadSessionIds.value.delete(sessionId);

    // 检查是否有活跃的流式连接
    const existingStream = activeStreams.get(sessionId);
    if (existingStream && !existingStream.done) {
        // 恢复流式输出状态
        messages.value = existingStream.messagesRef;
        // 找到正在流式输出的 assistant 消息并重新绑定打字机
        const lastMsg = messages.value[messages.value.length - 1];
        if (lastMsg && lastMsg.role === "assistant" && lastMsg.streaming) {
            existingStream.assistantMsg = lastMsg;
            lastMsg.content = existingStream.targetText;
            loading.value = true;
            scrollToBottom();
        }
        restoreDraft(sessionId);
        await loadSessionInfo();
        return;
    }

    messages.value = [];
    loading.value = false;
    await loadHistory();
    restoreDraft(sessionId);
    await loadSessionInfo();
}

async function handleDeleteSession(sessionId: string) {
    dialog.confirm({
        title: "确认删除该对话？",
        content: "删除后不可恢复",
        onOk: async () => {
            try {
                await deleteChatSession(sessionId);
                sessions.value = sessions.value.filter(s => s.session_id !== sessionId);
                if (currentSessionId.value === sessionId) {
                    if (sessions.value.length > 0) {
                        await switchSession(sessions.value[0].session_id);
                    } else {
                        currentSessionId.value = "";
                        messages.value = [];
                    }
                }
                message.success("已删除");
            } catch { message.error("删除失败"); }
        },
    });
}

function startRename(session: ChatSession) {
    renamingSessionId.value = session.session_id;
    renameText.value = session.title;
    nextTick(() => renameInputRef.value?.focus());
}

async function confirmRename() {
    const sid = renamingSessionId.value;
    const title = renameText.value.trim();
    if (!sid || !title) { renamingSessionId.value = ""; return; }
    try {
        await renameChatSession(sid, title);
        const s = sessions.value.find(s => s.session_id === sid);
        if (s) s.title = title;
    } catch { message.error("重命名失败"); }
    renamingSessionId.value = "";
}

function cancelRename() { renamingSessionId.value = ""; }

// 批量删除
function toggleBatchMode() {
    batchMode.value = !batchMode.value;
    selectedSessionIds.value = [];
}

function toggleSelectAll() {
    if (allSelected.value) { selectedSessionIds.value = []; }
    else { selectedSessionIds.value = sessions.value.map(s => s.session_id); }
}

function toggleSelectSession(sessionId: string) {
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
                if (deleted.has(currentSessionId.value)) {
                    if (sessions.value.length > 0) {
                        await switchSession(sessions.value[0].session_id);
                    } else {
                        currentSessionId.value = "";
                        messages.value = [];
                    }
                }
                selectedSessionIds.value = [];
                batchMode.value = false;
                message.success("批量删除成功");
            } catch { message.error("批量删除失败"); }
        },
    });
}

// --- 历史 & 发送 ---
async function loadHistory() {
    if (!currentSessionId.value) return;
    try {
        const res: any = await getChatHistory(50, currentSessionId.value);
        if (res?.messages) {
            messages.value = res.messages.map((m: any) => ({
                id: m.id || String(++messageCounter),
                role: m.role,
                content: m.content,
                timestamp: m.timestamp || Date.now()
            }));
            scrollToBottom();
        }
    } catch { /* 首次无历史 */ }
}

async function handleSend() {
    const text = inputText.value.trim();
    const images = [...pendingImages.value];
    if ((!text && !images.length) || loading.value) return;

    // 如果没有当前会话，先创建一个
    if (!currentSessionId.value) {
        try {
            const res: any = await createChatSession();
            const newSession: ChatSession = {
                session_id: res.session_id,
                title: res.title || "新对话",
                created_at: Date.now() / 1000,
                updated_at: Date.now() / 1000,
            };
            sessions.value.unshift(newSession);
            // 迁移草稿 key：从 "" 到真实 session ID
            const emptyDraft = drafts.get("");
            if (emptyDraft) { drafts.delete(""); }
            currentSessionId.value = newSession.session_id;
        } catch {
            message.error("创建对话失败");
            return;
        }
    }

    const sendSessionId = currentSessionId.value;

    const userMsg: ChatMessage = {
        id: String(++messageCounter),
        role: "user",
        content: text,
        images: images.map((i) => i.preview),
        timestamp: Date.now()
    };
    messages.value.push(userMsg);
    inputText.value = "";
    pendingImages.value = [];
    drafts.delete(sendSessionId);
    scrollToBottom();

    const rawAssistantMsg: ChatMessage = {
        id: String(++messageCounter),
        role: "assistant",
        content: "",
        toolCalls: [],
        timestamp: Date.now(),
        streaming: true,
    };
    messages.value.push(rawAssistantMsg);
    const assistantMsg = messages.value[messages.value.length - 1];
    loading.value = true;

    try {
        const res: any = await sendChatMessage(
            text,
            images.map((i) => ({ data: i.data, media_type: i.media_type })),
            sendSessionId
        );
        const messageId = res?.message_id;
        if (!messageId) {
            assistantMsg.content = "发送失败，请重试。";
            loading.value = false;
            return;
        }

        // 创建流式状态
        const streamState: ActiveStream = {
            sessionId: sendSessionId,
            eventSource: null as any,
            assistantMsg,
            targetText: "",
            done: false,
            twTimer: null,
            messagesRef: messages.value,
        };
        activeStreams.set(sendSessionId, streamState);

        function tickTypewriter() {
            const shown = streamState.assistantMsg.content.length;
            const total = streamState.targetText.length;
            if (shown < total) {
                const buffered = total - shown;
                const charsPerTick = Math.min(Math.max(1, Math.ceil(buffered / 30)), 3);
                streamState.assistantMsg.content = streamState.targetText.slice(0, shown + charsPerTick);
                if (currentSessionId.value === sendSessionId) scrollToBottom();
            } else if (streamState.done) { stopTypewriter(); }
        }

        function startTypewriter() {
            if (streamState.twTimer) return;
            streamState.twTimer = setInterval(tickTypewriter, 30);
        }
        function stopTypewriter() {
            if (streamState.twTimer) { clearInterval(streamState.twTimer); streamState.twTimer = null; }
        }

        function flushAndFinish() {
            streamState.done = true;
            stopTypewriter();
            streamState.assistantMsg.content = streamState.targetText;
            streamState.assistantMsg.streaming = false;
            activeStreams.delete(sendSessionId);

            // 如果当前不在这个会话，标记红点
            if (currentSessionId.value !== sendSessionId) {
                unreadSessionIds.value.add(sendSessionId);
            } else {
                loading.value = false;
                scrollToBottom();
                loadSessionInfo();
            }
        }

        const url = getChatStreamUrl(messageId, userStore.token);
        const eventSource = new EventSource(url);
        streamState.eventSource = eventSource;

        eventSource.addEventListener("text", (e: MessageEvent) => {
            streamState.targetText = e.data;
            startTypewriter();
        });

        eventSource.addEventListener("thinking", (_e: MessageEvent) => {});

        eventSource.addEventListener("tool_use", (e: MessageEvent) => {
            try {
                const data = JSON.parse(e.data);
                if (!streamState.assistantMsg.toolCalls) streamState.assistantMsg.toolCalls = [];
                streamState.assistantMsg.toolCalls.push({ name: data.name, status: "running" });
                if (currentSessionId.value === sendSessionId) scrollToBottom();
            } catch { /* ignore */ }
        });

        eventSource.addEventListener("tool_result", (e: MessageEvent) => {
            try {
                const data = JSON.parse(e.data);
                const call = streamState.assistantMsg.toolCalls?.find(t => t.name === data.name && t.status === "running");
                if (call) call.status = "done";
                if (currentSessionId.value === sendSessionId) scrollToBottom();
            } catch { /* ignore */ }
        });

        eventSource.addEventListener("title_updated", (e: MessageEvent) => {
            try {
                const data = JSON.parse(e.data);
                const s = sessions.value.find(s => s.session_id === data.session_id);
                if (s) s.title = data.title;
            } catch { /* ignore */ }
        });

        eventSource.addEventListener("done", (_e: MessageEvent) => {
            eventSource.close();
            flushAndFinish();
        });

        eventSource.addEventListener("error", (e: MessageEvent) => {
            const data = (e as any).data;
            if (data) streamState.targetText += `\n\n错误: ${data}`;
            eventSource.close();
            flushAndFinish();
        });

        eventSource.onerror = () => {
            eventSource.close();
            if (!streamState.done) {
                if (!streamState.targetText) streamState.targetText = "连接中断，请重试。";
                flushAndFinish();
            }
        };
    } catch {
        assistantMsg.content = "请求失败，请检查服务是否运行。";
        loading.value = false;
    }
}

function handlePressEnter(e: KeyboardEvent) {
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
    input.onchange = () => { /* TODO */ };
    input.click();
}

function insertEmoji(emoji: string) { inputText.value += emoji; emojiOpen.value = false; }

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

async function handleReset() {
    if (!currentSessionId.value) return;
    try {
        await resetChatSession(currentSessionId.value);
        messages.value = [];
        sessionTokens.value = { input: 0, output: 0, messages: 0 };
        message.success("会话已重置");
    } catch { message.error("重置失败"); }
}

function formatTokens(n: number): string {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return String(n);
}

function formatTime(ts: number): string {
    if (!ts) return "";
    const d = new Date(ts * 1000);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

onMounted(async () => {
    document.addEventListener("paste", handlePaste);
    await loadSessions();

    const lastSessionId = localStorage.getItem('chat-last-session-id');

    if (lastSessionId && sessions.value.some(s => s.session_id === lastSessionId)) {
        await switchSession(lastSessionId);
    } else if (sessions.value.length > 0) {
        await switchSession(sessions.value[0].session_id);
    }
});

onUnmounted(() => {
    document.removeEventListener("paste", handlePaste);
});
</script>

<template>
    <div class="flex h-full">
        <!-- 左侧对话列表 -->
        <div v-if="!sidebarCollapsed" class="w-[260px] flex-shrink-0 border-r border-gray-100 flex flex-col bg-white">
            <!-- 顶部操作栏 -->
            <div class="flex items-center justify-between px-4 h-14 border-b border-gray-100">
                <VortTooltip title="收起侧边栏">
                    <button
                        class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer"
                        @click="sidebarCollapsed = true"
                    >
                        <PanelLeftClose :size="18" />
                    </button>
                </VortTooltip>
                <VortTooltip title="新建对话">
                    <button
                        class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer"
                        @click="handleNewSession"
                    >
                        <MessageSquarePlus :size="18" />
                    </button>
                </VortTooltip>
            </div>

            <!-- 批量操作栏 -->
            <div v-if="batchMode" class="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-100">
                <VortCheckbox
                    :checked="allSelected"
                    :indeterminate="selectedSessionIds.length > 0 && !allSelected"
                    @update:checked="toggleSelectAll"
                >
                    <span class="text-xs text-gray-500">全选</span>
                </VortCheckbox>
                <div class="flex items-center gap-2">
                    <span class="text-xs text-gray-400">已选 {{ selectedSessionIds.length }} 项</span>
                    <button class="text-xs text-gray-400 hover:text-gray-600 cursor-pointer" @click="toggleBatchMode">取消</button>
                </div>
            </div>

            <!-- 对话列表 -->
            <div class="flex-1 overflow-y-auto">
                <div v-if="sessionsLoading" class="flex items-center justify-center py-8">
                    <Loader2 :size="20" class="animate-spin text-gray-300" />
                </div>
                <div v-else-if="sessions.length === 0" class="flex flex-col items-center justify-center py-12 text-gray-400">
                    <MessageSquare :size="32" class="mb-2 text-gray-300" />
                    <p class="text-xs">暂无对话</p>
                </div>
                <div v-else class="py-1">
                    <div
                        v-for="s in sessions" :key="s.session_id"
                        class="group flex items-center gap-2 mx-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors mb-0.5"
                        :class="currentSessionId === s.session_id && !batchMode ? 'bg-gray-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50/50'"
                        @click="batchMode ? toggleSelectSession(s.session_id) : switchSession(s.session_id)"
                    >
                        <!-- 批量选择 checkbox -->
                        <div v-if="batchMode" class="flex-shrink-0" @click.stop="toggleSelectSession(s.session_id)">
                            <VortCheckbox
                                :checked="selectedSessionIds.includes(s.session_id)"
                                @update:checked="toggleSelectSession(s.session_id)"
                            />
                        </div>

                        <!-- 标题 -->
                        <div v-if="renamingSessionId === s.session_id" class="flex-1 min-w-0" @click.stop>
                            <input
                                ref="renameInputRef"
                                v-model="renameText"
                                class="w-full text-sm bg-white border border-blue-300 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-blue-400"
                                @keydown.enter="confirmRename"
                                @keydown.escape="cancelRename"
                                @blur="confirmRename"
                            />
                        </div>
                        <div v-else class="flex-1 min-w-0">
                            <div class="text-sm truncate">{{ s.title }}</div>
                            <div class="text-[11px] text-gray-400 mt-0.5">{{ formatTime(s.updated_at) }}</div>
                        </div>

                        <!-- 未读红点 -->
                        <div v-if="!batchMode && unreadSessionIds.has(s.session_id)" class="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-red-500" />

                        <!-- 更多操作（三个点） -->
                        <div v-if="!batchMode && renamingSessionId !== s.session_id"
                            class="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                            <VortDropdown trigger="click" @click.stop>
                                <button class="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 cursor-pointer">
                                    <MoreHorizontal :size="16" />
                                </button>
                                <template #overlay>
                                    <VortDropdownMenuItem @click="toggleBatchMode">
                                        <ListChecks :size="14" class="mr-2" /> 批量操作
                                    </VortDropdownMenuItem>
                                    <VortDropdownMenuItem @click="startRename(s)">
                                        <Pencil :size="14" class="mr-2" /> 编辑名称
                                    </VortDropdownMenuItem>
                                    <VortDropdownMenuSeparator />
                                    <VortDropdownMenuItem danger @click="handleDeleteSession(s.session_id)">
                                        <Trash2 :size="14" class="mr-2" /> 删除
                                    </VortDropdownMenuItem>
                                </template>
                            </VortDropdown>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 批量删除底栏 -->
            <div v-if="batchMode" class="px-4 py-3 border-t border-gray-100">
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
        </div>

        <!-- 右侧聊天区域 -->
        <div class="flex-1 flex flex-col min-w-0">
            <!-- 头部 -->
            <div class="flex items-center justify-between px-6 h-14 border-b border-gray-100 bg-white">
                <div class="flex items-center">
                    <VortTooltip v-if="sidebarCollapsed" title="展开侧边栏">
                        <button
                            class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer mr-2"
                            @click="sidebarCollapsed = false"
                        >
                            <PanelLeftOpen :size="18" />
                        </button>
                    </VortTooltip>
                    <VortTooltip v-if="sidebarCollapsed" title="新建对话">
                        <button
                            class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer mr-3"
                            @click="handleNewSession"
                        >
                            <MessageSquarePlus :size="18" />
                        </button>
                    </VortTooltip>
                    <Bot :size="20" class="text-blue-600 mr-2" />
                    <h2 class="text-base font-medium text-gray-800">OpenVort AI 助手</h2>
                    <span v-if="loading" class="ml-3 flex items-center text-xs text-gray-400">
                        <Loader2 :size="14" class="animate-spin mr-1" /> 思考中...
                    </span>
                </div>
                <div class="flex items-center gap-2">
                    <VortTooltip :title="`Input: ${formatTokens(sessionTokens.input)} / Output: ${formatTokens(sessionTokens.output)} / 消息: ${sessionTokens.messages}`">
                        <span class="text-xs text-gray-400 flex items-center gap-1 cursor-default">
                            <Zap :size="14" />
                            {{ formatTokens(sessionTokens.input + sessionTokens.output) }}
                        </span>
                    </VortTooltip>
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
                    <VortTooltip title="重置会话">
                        <button class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer"
                            @click="handleReset">
                            <RotateCcw :size="16" />
                        </button>
                    </VortTooltip>
                </div>
            </div>

            <!-- 消息列表 -->
            <div ref="chatContainer" class="flex-1 overflow-y-auto px-6 py-4 space-y-4">
                <!-- 无会话状态 -->
                <div v-if="!currentSessionId" class="flex flex-col items-center justify-center h-full text-gray-400">
                    <Bot :size="48" class="mb-4 text-gray-300" />
                    <p class="text-sm">你好，我是 OpenVort AI 助手</p>
                    <p class="text-xs mt-1">点击左侧「新建对话」开始聊天</p>
                </div>
                <!-- 空消息状态 -->
                <div v-else-if="messages.length === 0 && !loading" class="flex flex-col items-center justify-center h-full text-gray-400">
                    <Bot :size="48" class="mb-4 text-gray-300" />
                    <p class="text-sm">你好，我是 OpenVort AI 助手</p>
                    <p class="text-xs mt-1">可以帮你管理任务、查询 Bug、了解项目进展</p>
                </div>

                <!-- 消息气泡 -->
                <div v-for="msg in messages" :key="msg.id" class="flex" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
                    <div class="flex max-w-[80%]" :class="msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'">
                        <div class="flex-shrink-0" :class="msg.role === 'user' ? 'ml-3' : 'mr-3'">
                            <div class="w-8 h-8 rounded-full flex items-center justify-center"
                                :class="msg.role === 'user' ? 'bg-blue-600' : 'bg-gray-100'">
                                <User v-if="msg.role === 'user'" :size="16" class="text-white" />
                                <Bot v-else :size="16" class="text-blue-600" />
                            </div>
                        </div>
                        <div>
                            <div v-if="msg.role === 'user' && msg.images?.length" class="flex flex-wrap gap-2 mb-2 justify-end">
                                <img v-for="(src, i) in msg.images" :key="i" :src="src"
                                    class="w-20 h-20 object-cover rounded-lg border border-white/30" />
                            </div>
                            <div v-if="msg.toolCalls?.length" class="mb-2 space-y-1">
                                <div v-for="(tool, i) in msg.toolCalls" :key="i"
                                    class="inline-flex items-center px-2 py-1 rounded text-xs mr-2"
                                    :class="tool.status === 'running' ? 'bg-yellow-50 text-yellow-700' : 'bg-green-50 text-green-700'">
                                    <Wrench :size="12" class="mr-1" />
                                    {{ tool.name }}
                                    <Loader2 v-if="tool.status === 'running'" :size="12" class="ml-1 animate-spin" />
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
                        </div>
                    </div>
                </div>
            </div>

            <!-- 输入区域 -->
            <div class="relative px-6 py-4" ref="inputArea"
                @dragover="handleDragOver" @dragleave="handleDragLeave" @drop="handleDrop">
                <div v-if="isDragging"
                    class="absolute inset-0 z-10 flex items-center justify-center bg-blue-50/80 border-2 border-dashed border-blue-400 rounded-xl pointer-events-none">
                    <div class="text-blue-500 text-sm font-medium flex items-center gap-2">
                        <ImagePlus :size="20" /> 松开以添加图片
                    </div>
                </div>
                <div class="chat-input-box bg-white rounded-xl border border-gray-200 overflow-hidden">
                    <div v-if="pendingImages.length" class="flex flex-wrap gap-2 px-4 pt-3">
                        <div v-for="(img, i) in pendingImages" :key="i" class="relative group">
                            <img :src="img.preview" class="w-[72px] h-[72px] object-cover rounded-lg border border-gray-200 shadow-sm" />
                            <button @click="removeImage(i)"
                                class="absolute -top-1.5 -right-1.5 w-5 h-5 bg-black/60 hover:bg-black/80 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                <X :size="12" />
                            </button>
                        </div>
                    </div>
                    <VortTextarea
                        v-model="inputText"
                        placeholder="请描述您问题，支持 Ctrl+V 粘贴图片。"
                        :auto-size="{ minRows: 3, maxRows: 6 }"
                        :bordered="false"
                        class="chat-textarea"
                        @press-enter="handlePressEnter"
                    />
                    <div class="flex items-center justify-between px-4 py-2">
                        <div class="flex items-center gap-1">
                            <VortPopover placement="top" :arrow="true">
                                <button @click="triggerFileInput"
                                    class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer">
                                    <FileText :size="18" />
                                </button>
                                <template #content>
                                    <span class="text-xs text-gray-500 whitespace-nowrap">.jpg,.jpeg,.png,.txt,.rar,.zip,.doc,.docx,.xls,.7z</span>
                                </template>
                            </VortPopover>
                            <VortPopover placement="top" :arrow="true">
                                <button @click="triggerVideoInput"
                                    class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer">
                                    <MonitorPlay :size="18" />
                                </button>
                                <template #content>
                                    <span class="text-xs text-gray-500 whitespace-nowrap">.mp4,.mov,.avi,.wmv,.flv,.mkv</span>
                                </template>
                            </VortPopover>
                            <VortPopover v-model:open="emojiOpen" trigger="click" placement="topLeft" :arrow="false" :overlay-style="{ maxWidth: '424px' }">
                                <button class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer">
                                    <Smile :size="18" />
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
                            <VortPopover v-model:open="settingsOpen" trigger="click" placement="topRight" :arrow="false">
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
                                :disabled="(!inputText.trim() && !pendingImages.length) || loading"
                                @click="handleSend"
                                class="w-20 h-9 rounded-lg flex items-center justify-center transition-colors send-btn"
                                :class="(!inputText.trim() && !pendingImages.length) || loading ? 'send-btn-disabled' : 'send-btn-active'"
                            >
                                <Send :size="16" class="text-white" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.prose :deep(pre) {
    background: #1e1e1e;
    color: #d4d4d4;
    border-radius: 8px;
    padding: 12px 16px;
    overflow-x: auto;
}
.prose :deep(code) {
    font-size: 13px;
}
.prose :deep(p:last-child) {
    margin-bottom: 0;
}

.chat-textarea {
    padding: 15px 16px 12px !important;
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
    max-height: 320px;
    overflow-y: auto;
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
</style>