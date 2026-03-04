<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useUserStore } from "@/stores";
import {
    Send, Bot, Loader2, Wrench, X, ImagePlus, FileText, MonitorPlay, Smile,
    Settings, Check, Brain, PackageMinus, RotateCcw, Zap, StopCircle, Square,
    Hash, Bug, ListTodo, BookOpen, Milestone, GitBranch, ChevronDown, ChevronRight
} from "lucide-vue-next";
import { Popover as VortPopover } from "@/components/vort/popover";
import { Image as VortImage, ImagePreviewGroup as VortImagePreviewGroup } from "@/components/vort/image";
import {
    sendChatMessage, getChatStreamUrl, getChatHistory, getChatSessionInfo,
    setChatThinking, compactChatSession, resetChatSession,
    getChatSessions, createChatSession, getChatMembers, abortChatMessage, startMemberChat,
    getVortflowBugs, getVortflowTasks, getVortflowStories, getVortflowMilestones
} from "@/api";
import { usePluginStore } from "@/stores/modules/plugin";
import { message } from "@/components/vort/message";
import { dialog } from "@/components/vort/dialog";
import { marked } from "marked";
import { pinyin } from "pinyin-pro";
import ContactList from "./ContactList.vue";
import SessionSwitcher from "./SessionSwitcher.vue";
import MemberProfile from "./MemberProfile.vue";
import type { ChatMessage, ChatSession, PendingImage, Contact, MentionMember, SlashCommand, Draft, HashTagCategory, HashTagItem, ToolCall } from "./types";

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const pluginStore = usePluginStore();
const messages = ref<ChatMessage[]>([]);
const inputText = ref("");
const loading = ref(false);
const aborting = ref(false);
const chatScrollbar = ref<InstanceType<typeof import("@/components/vort/scrollbar/Scrollbar.vue").default> | null>(null);
const inputArea = ref<HTMLElement>();
const pendingImages = ref<PendingImage[]>([]);
const isDragging = ref(false);
const sendMode = ref<'enter' | 'ctrl-enter'>('enter');
const settingsOpen = ref(false);
const emojiOpen = ref(false);
const thinkingLevel = ref<string>("off");
const thinkingOpen = ref(false);
const sessionTokens = ref({ input: 0, output: 0, messages: 0, cacheCreation: 0, cacheRead: 0 });
const compacting = ref(false);
let messageCounter = 0;

// ---- Contact & Session state ----
const activeContact = ref<Contact | null>(null);
const sessions = ref<ChatSession[]>([]);
const currentSessionId = ref<string>("");
const contactListRef = ref<InstanceType<typeof ContactList>>();
const sessionSwitcherRef = ref<InstanceType<typeof SessionSwitcher>>();

const memberProfileOpen = ref(false);

const isAiMode = computed(() => !activeContact.value || activeContact.value.type === "ai");
const currentSessionTitle = computed(() => {
    if (!currentSessionId.value) return "新对话";
    const s = sessions.value.find(s => s.session_id === currentSessionId.value);
    return s?.title || "新对话";
});

// ---- 草稿暂存（切换会话时保留未发送内容）----
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

watch(currentSessionId, (val) => {
    localStorage.setItem('chat-last-session-id', val);
});

watch(activeContact, (contact) => {
    if (contact) {
        localStorage.setItem('chat-last-contact', JSON.stringify({
            type: contact.type,
            id: contact.id,
            name: contact.name,
            avatar_url: contact.avatar_url,
            session_id: contact.session_id,
            position: contact.position,
        }));
    }
}, { deep: true });

// ---- 红点 & 流式跨会话保持 ----
const unreadSessionIds = ref<Set<string>>(new Set());

interface ActiveStream {
    sessionId: string;
    messageId: string;
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

// --- 节流 scrollToBottom ---
let scrollRAF: number | null = null;
function scrollToBottom() {
    if (scrollRAF) return;
    scrollRAF = requestAnimationFrame(() => {
        scrollRAF = null;
        const wrap = chatScrollbar.value?.wrapRef;
        if (wrap) {
            wrap.scrollTop = wrap.scrollHeight;
        }
    });
}

function formatToolElapsed(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    return `${Math.floor(seconds / 60)}m${seconds % 60}s`;
}

function mergeToolCalls(tools: ToolCall[]): ToolCall[] {
    const merged: ToolCall[] = [];
    for (const t of tools) {
        const last = merged[merged.length - 1];
        if (last && last.name === t.name && last.status === "done" && t.status === "done") {
            last.count = (last.count || 1) + 1;
            if (t.output) {
                last.output = last.output ? last.output + "\n" + t.output : t.output;
            }
        } else {
            merged.push({ ...t, count: t.count || 1 });
        }
    }
    return merged;
}

function toggleToolCollapsed(tool: ToolCall) {
    tool.collapsed = !tool.collapsed;
    nextTick(scrollToBottom);
}

function toggleToolsExpanded(msg: ChatMessage) {
    msg.toolsExpanded = !msg.toolsExpanded;
    if (msg.toolsExpanded) {
        nextTick(scrollToBottom);
    }
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

// --- Contact selection ---
async function handleContactSelect(contact: Contact) {
    activeContact.value = contact;
    if (contact.type === "ai") {
        // Load AI sessions, select the last one
        await sessionSwitcherRef.value?.loadSessions();
        const lastSessionId = localStorage.getItem('chat-last-session-id');
        if (lastSessionId && sessions.value.some(s => s.session_id === lastSessionId)) {
            await switchSession(lastSessionId);
        } else if (sessions.value.length > 0) {
            await switchSession(sessions.value[0].session_id);
        } else {
            handleNewSession();
        }
    } else {
        // Member mode: single session
        if (contact.session_id) {
            await switchSession(contact.session_id);
        } else {
            try {
                const res: any = await startMemberChat(contact.id);
                if (res?.session_id) {
                    contact.session_id = res.session_id;
                    await switchSession(res.session_id);
                }
            } catch {
                message.error("进入对话失败");
            }
        }
    }
}

function handleSessionsLoaded(loadedSessions: ChatSession[]) {
    sessions.value = loadedSessions;
}

function handleNewSession() {
    if (!currentSessionId.value && messages.value.length === 0) {
        message.info("已经是最新对话");
        return;
    }
    saveDraft();
    currentSessionId.value = "";
    messages.value = [];
    messageCounter = 0;
    sessionTokens.value = { input: 0, output: 0, messages: 0, cacheCreation: 0, cacheRead: 0 };
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
    sessionTokens.value = { input: 0, output: 0, messages: 0, cacheCreation: 0, cacheRead: 0 };

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

// --- 历史 & 发送 ---
async function loadHistory() {
    if (!currentSessionId.value) return;
    try {
        const res: any = await getChatHistory(50, currentSessionId.value);
        if (res?.messages) {
            const raw: ChatMessage[] = res.messages.map((m: any) => {
                const images = m.images?.map((img: string) => {
                    if (img && !img.startsWith('data:') && !img.startsWith('http') && !img.startsWith('/')) {
                        return `/api/${img}`;
                    }
                    return img;
                });
                let content = m.content || "";
                if (images?.length && /^(请看图片)+$/.test(content.trim())) {
                    content = "";
                }
                const msg: ChatMessage = {
                    id: m.id || String(++messageCounter),
                    role: m.role,
                    content,
                    images,
                    timestamp: m.timestamp || Date.now()
                };
                if (m.tool_calls?.length) {
                    msg.toolCalls = mergeToolCalls(
                        m.tool_calls.map((tc: any) => ({
                            name: tc.name,
                            status: tc.status || "done",
                            output: tc.output || "",
                            collapsed: true,
                            count: 1,
                        }))
                    );
                }
                return msg;
            });
            // Merge tool-only assistant messages into the next assistant message
            const merged: ChatMessage[] = [];
            let pendingTools: ToolCall[] = [];
            for (const msg of raw) {
                if (msg.role === "assistant" && !msg.content && msg.toolCalls?.length) {
                    pendingTools.push(...msg.toolCalls);
                } else {
                    if (msg.role === "assistant" && pendingTools.length) {
                        msg.toolCalls = [...pendingTools, ...(msg.toolCalls || [])];
                        pendingTools = [];
                    }
                    merged.push(msg);
                }
            }
            if (pendingTools.length) {
                merged.push({ id: String(++messageCounter), role: "assistant", content: "", toolCalls: pendingTools, timestamp: Date.now() });
            }
            messages.value = merged;
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
    const assistantMsg = messages.value[messages.value.length - 1]!;
    loading.value = true;
    aborting.value = false;

    try {
        const res: any = await sendChatMessage(
            text,
            images.map((i) => ({ data: i.data, media_type: i.media_type })),
            sendSessionId,
            activeContact.value?.type || "ai",
            activeContact.value?.type === "member" ? activeContact.value.id : "",
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
            messageId,
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

        function flushAndFinish(options?: { interrupted?: boolean }) {
            if (streamState.done) return;
            streamState.done = true;
            aborting.value = false;
            stopTypewriter();
            let finalText = streamState.targetText;
            if (options?.interrupted) {
                finalText = finalText ? `${finalText}...` : "";
            }
            streamState.assistantMsg.content = finalText;
            streamState.assistantMsg.streaming = false;
            activeStreams.delete(sendSessionId);

            // 始终重置当前会话的 loading 状态，避免卡住
            if (currentSessionId.value === sendSessionId) {
                loading.value = false;
            }

            // 如果当前不在这个会话，标记红点
            if (currentSessionId.value !== sendSessionId) {
                unreadSessionIds.value.add(sendSessionId);
            } else {
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
                const calls = streamState.assistantMsg.toolCalls;
                const last = calls[calls.length - 1];
                if (last && last.name === data.name && last.status === "done") {
                    last.count = (last.count || 1) + 1;
                    last.status = "running";
                    last.elapsed = undefined;
                } else {
                    calls.push({ name: data.name, status: "running", count: 1 });
                }
                if (currentSessionId.value === sendSessionId) scrollToBottom();
            } catch { /* ignore */ }
        });

        eventSource.addEventListener("tool_output", (e: MessageEvent) => {
            try {
                const data = JSON.parse(e.data);
                const calls = streamState.assistantMsg.toolCalls;
                const call = calls && [...calls].reverse().find(t => t.name === data.name && t.status === "running");
                if (call) {
                    call.output = call.output ? call.output + "\n" + data.output : data.output;
                    if (currentSessionId.value === sendSessionId) scrollToBottom();
                }
            } catch { /* ignore */ }
        });

        eventSource.addEventListener("tool_progress", (e: MessageEvent) => {
            try {
                const data = JSON.parse(e.data);
                const calls = streamState.assistantMsg.toolCalls;
                const call = calls && [...calls].reverse().find(t => t.name === data.name && t.status === "running");
                if (call) call.elapsed = data.elapsed;
            } catch { /* ignore */ }
        });

        eventSource.addEventListener("tool_result", (e: MessageEvent) => {
            try {
                const data = JSON.parse(e.data);
                const calls = streamState.assistantMsg.toolCalls;
                const call = calls && [...calls].reverse().find(t => t.name === data.name && t.status === "running");
                if (call) {
                    call.status = "done";
                    if (data.result) {
                        call.output = call.output
                            ? call.output + "\n---\n" + data.result
                            : data.result;
                    }
                    call.collapsed = !!call.output;
                }
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

        eventSource.addEventListener("usage", (e: MessageEvent) => {
            try {
                const data = JSON.parse(e.data);
                sessionTokens.value = {
                    input: data.total_input_tokens || 0,
                    output: data.total_output_tokens || 0,
                    messages: sessionTokens.value.messages,
                    cacheCreation: data.total_cache_creation_tokens || 0,
                    cacheRead: data.total_cache_read_tokens || 0,
                };
            } catch { /* ignore */ }
        });

        eventSource.addEventListener("done", (_e: MessageEvent) => {
            eventSource.close();
            flushAndFinish();
        });

        eventSource.addEventListener("interrupted", (_e: MessageEvent) => {
            eventSource.close();
            flushAndFinish({ interrupted: true });
        });

        eventSource.addEventListener("server_error", (e: MessageEvent) => {
            const data = e.data;
            if (data) {
                // 解析错误信息，提供用户友好的提示
                let errorMsg = "AI 服务暂时不可用，请稍后重试";
                try {
                    // 尝试解析常见的错误格式
                    if (data.includes("Model name not specified")) {
                        errorMsg = "模型配置错误，请检查编码模型设置";
                    } else if (data.includes("rate_limit") || data.includes("429")) {
                        errorMsg = "请求过于频繁，请稍后再试";
                    } else if (data.includes("authentication") || data.includes("401")) {
                        errorMsg = "API 密钥验证失败，请检查配置";
                    } else if (data.includes("timeout") || data.includes("504")) {
                        errorMsg = "请求超时，请重试";
                    } else if (data.includes("400")) {
                        errorMsg = "请求参数错误，请检查模型配置";
                    } else if (data.includes("500") || data.includes("503")) {
                        errorMsg = "服务暂时不可用，请稍后重试";
                    }
                } catch {
                    // 解析失败时使用默认错误信息
                }
                streamState.targetText += `\n\n${errorMsg}`;
            }
            eventSource.close();
            flushAndFinish();
        });

        eventSource.onerror = () => {
            eventSource.close();
            if (!streamState.done) {
                if (aborting.value) {
                    flushAndFinish({ interrupted: true });
                    return;
                }
                if (!streamState.targetText) streamState.targetText = "连接中断，请重试。";
                flushAndFinish();
            }
        };

        // SSE timeout: if no events received within 30s, abort
        let lastEventTime = Date.now();
        const sseTimeoutCheck = setInterval(() => {
            if (streamState.done) { clearInterval(sseTimeoutCheck); return; }
            if (Date.now() - lastEventTime > 30000) {
                clearInterval(sseTimeoutCheck);
                eventSource.close();
                if (!streamState.targetText) streamState.targetText = "AI 响应超时，请重试。";
                flushAndFinish();
            }
        }, 5000);
        // Track last event time on every SSE event
        const trackEvent = () => { lastEventTime = Date.now(); };
        for (const evtName of ["text", "tool_use", "tool_output", "tool_progress", "tool_result", "usage", "thinking", "done", "server_error", "interrupted"]) {
            eventSource.addEventListener(evtName, trackEvent);
        }
    } catch (err: any) {
        // 提供用户友好的错误提示
        let errorMsg = "请求失败，请检查网络连接";
        if (err?.response?.status === 400) {
            errorMsg = "请求参数错误，请检查模型配置";
        } else if (err?.response?.status === 401) {
            errorMsg = "API 密钥验证失败，请检查配置";
        } else if (err?.response?.status === 429) {
            errorMsg = "请求过于频繁，请稍后再试";
        } else if (err?.response?.status >= 500) {
            errorMsg = "服务暂时不可用，请稍后重试";
        } else if (err?.message?.includes("Network")) {
            errorMsg = "网络连接失败，请检查网络";
        }
        assistantMsg.content = errorMsg;
        loading.value = false;
        aborting.value = false;
    }
}

async function handleAbortCurrentStream() {
    if (!loading.value || aborting.value) return;
    const sessionId = currentSessionId.value;
    const streamState = activeStreams.get(sessionId);
    if (!streamState) {
        loading.value = false;
        return;
    }

    aborting.value = true;
    try {
        await abortChatMessage(streamState.messageId);
    } catch {
        // Fall back to local close/finalize even if abort API fails.
    } finally {
        try { streamState.eventSource?.close(); } catch { /* noop */ }
        if (!streamState.done) {
            streamState.done = true;
            if (streamState.twTimer) {
                clearInterval(streamState.twTimer);
                streamState.twTimer = null;
            }
                streamState.assistantMsg.content = streamState.targetText
                ? `${streamState.targetText}...`
                : "";
            streamState.assistantMsg.streaming = false;
            activeStreams.delete(sessionId);
            loading.value = false;
            scrollToBottom();
            loadSessionInfo();
        }
        aborting.value = false;
    }
}

function handlePressEnter(e: KeyboardEvent) {
    // If mention/command panel is open, let panel handle it
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

async function handleReset() {
    if (!currentSessionId.value) return;
    try {
        await resetChatSession(currentSessionId.value);
        messages.value = [];
        sessionTokens.value = { input: 0, output: 0, messages: 0, cacheCreation: 0, cacheRead: 0 };
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

// ---- @mention、/command、#tag 提示 ----
const slashCommands: SlashCommand[] = [
    { name: "/new", label: "/new", description: "重置会话" },
    { name: "/status", label: "/status", description: "查看会话状态" },
    { name: "/compact", label: "/compact", description: "压缩上下文" },
    { name: "/think", label: "/think", description: "设置思考级别 (off|low|medium|high)" },
    { name: "/usage", label: "/usage", description: "设置用量显示 (off|tokens|full)" },
    { name: "/help", label: "/help", description: "显示帮助" },
];

const showMentionPanel = ref(false);
const showCommandPanel = ref(false);
const showHashTagPanel = ref(false);
const mentionMembers = ref<MentionMember[]>([]);
const filteredCommands = ref<SlashCommand[]>([]);
const mentionActiveIndex = ref(0);
const commandActiveIndex = ref(0);
const hashTagActiveIndex = ref(0);
const mentionQuery = ref("");
const commandQuery = ref("");
const hashTagQuery = ref("");
const panelStyle = ref({ left: '0px' });
let mentionStartPos = -1;
let hashTagStartPos = -1;

// #tag two-level state
const hashTagLevel = ref<'category' | 'items'>('category');
const hashTagSelectedCategory = ref<HashTagCategory | null>(null);
const hashTagItems = ref<HashTagItem[]>([]);
const hashTagItemsLoading = ref(false);

const allHashTagCategories: HashTagCategory[] = [
    { key: 'bug', label: '#bug', description: '缺陷跟踪', plugin: 'vortflow' },
    { key: 'task', label: '#task', description: '任务管理', plugin: 'vortflow' },
    { key: 'story', label: '#story', description: '需求列表', plugin: 'vortflow' },
    { key: 'milestone', label: '#milestone', description: '里程碑', plugin: 'vortflow' },
];

const availableHashTagCategories = computed(() => {
    const enabledPlugins = new Set(pluginStore.extensions.map(e => e.plugin));
    return allHashTagCategories.filter(c => enabledPlugins.has(c.plugin));
});

const filteredHashTagCategories = computed(() => {
    if (!hashTagQuery.value) return availableHashTagCategories.value;
    const kw = hashTagQuery.value.toLowerCase();
    return availableHashTagCategories.value.filter(
        c => c.key.includes(kw) || c.label.includes(kw) || c.description.includes(kw)
    );
});

const filteredHashTagItems = computed(() => {
    if (!hashTagQuery.value) return hashTagItems.value;
    const kw = hashTagQuery.value.toLowerCase();
    return hashTagItems.value.filter(
        item => item.id.toLowerCase().includes(kw) || item.title.toLowerCase().includes(kw)
    );
});

// Unified display list for the #tag panel
const hashTagDisplayList = computed(() => {
    if (hashTagLevel.value === 'category') return filteredHashTagCategories.value;
    return filteredHashTagItems.value;
});

// All members cache for local pinyin search
const allMembers = ref<MentionMember[]>([]);
let allMembersLoaded = false;

async function ensureMembersLoaded() {
    if (allMembersLoaded) return;
    try {
        const res: any = await getChatMembers("", 200);
        allMembers.value = res?.members || [];
        allMembersLoaded = true;
    } catch { /* ignore */ }
}

/**
 * Match member name by pinyin initials (supports polyphones)
 */
function matchPinyin(name: string, keyword: string): boolean {
    if (!keyword) return true;
    const kw = keyword.toLowerCase();

    // Direct name/email match
    if (name.toLowerCase().includes(kw)) return true;

    // Full pinyin match
    const fullPy = pinyin(name, { toneType: 'none', type: 'array' }).join('').toLowerCase();
    if (fullPy.includes(kw)) return true;

    // Pinyin initials match (with polyphone support via multiple mode)
    const initialsArr = pinyin(name, { pattern: 'first', type: 'array', multiple: true });
    // Build all possible initial combinations for polyphones
    const combos = initialsArr.reduce<string[]>((acc, cur) => {
        // cur may be a string with multiple initials separated by space for polyphones
        const options = typeof cur === 'string' ? cur.split(' ') : [cur];
        if (acc.length === 0) return options.map(o => o.toLowerCase());
        const result: string[] = [];
        for (const prefix of acc) {
            for (const opt of options) {
                result.push(prefix + opt.toLowerCase());
            }
        }
        return result;
    }, []);

    return combos.some(c => c.includes(kw));
}

function filterMembersByKeyword(keyword: string): MentionMember[] {
    if (!keyword) return allMembers.value.slice(0, 20);
    return allMembers.value.filter(m =>
        matchPinyin(m.name, keyword) ||
        (m.email && m.email.toLowerCase().includes(keyword.toLowerCase()))
    ).slice(0, 20);
}

async function searchMembers(keyword: string) {
    await ensureMembersLoaded();
    mentionMembers.value = filterMembersByKeyword(keyword);
    mentionActiveIndex.value = 0;
    showMentionPanel.value = mentionMembers.value.length > 0;
}

function updatePanelPosition() {
    const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
    const container = document.querySelector('.relative.px-6') as HTMLElement;
    if (!textarea || !container) return;

    // Create a mirror div to measure cursor position
    const mirror = document.createElement('div');
    const style = window.getComputedStyle(textarea);
    const mirrorProps = [
        'fontFamily', 'fontSize', 'fontWeight', 'lineHeight', 'letterSpacing',
        'wordSpacing', 'textIndent', 'whiteSpace', 'wordWrap', 'overflowWrap',
        'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
        'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
        'boxSizing', 'width',
    ];
    mirror.style.position = 'absolute';
    mirror.style.visibility = 'hidden';
    mirror.style.overflow = 'hidden';
    for (const prop of mirrorProps) {
        (mirror.style as any)[prop] = style.getPropertyValue(prop.replace(/([A-Z])/g, '-$1').toLowerCase());
    }
    document.body.appendChild(mirror);

    const text = textarea.value.substring(0, textarea.selectionStart);
    mirror.textContent = text;
    const span = document.createElement('span');
    span.textContent = '|';
    mirror.appendChild(span);

    const textareaRect = textarea.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const spanRect = span.getBoundingClientRect();
    const mirrorRect = mirror.getBoundingClientRect();

    document.body.removeChild(mirror);

    // Calculate left position relative to container
    const cursorLeft = textareaRect.left + (spanRect.left - mirrorRect.left) - textarea.scrollLeft;
    const relativeLeft = Math.max(0, cursorLeft - containerRect.left);

    panelStyle.value = { left: `${relativeLeft}px` };
}

// Whether any popup panel is open
const isAnyPanelOpen = computed(() => showMentionPanel.value || showCommandPanel.value || showHashTagPanel.value);

// Watch inputText to detect @, / and # triggers
watch(inputText, () => {
    nextTick(() => handleInput());
});

function closeAllPanels() {
    showMentionPanel.value = false;
    showCommandPanel.value = false;
    showHashTagPanel.value = false;
    hashTagLevel.value = 'category';
    hashTagSelectedCategory.value = null;
}

function handleInput() {
    const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
    if (!textarea) return;

    const cursorPos = textarea.selectionStart;
    const text = textarea.value;
    const textBeforeCursor = text.substring(0, cursorPos);

    // Check for @ mention
    const atMatch = textBeforeCursor.match(/@([^\s@]*)$/);
    if (atMatch) {
        mentionStartPos = cursorPos - atMatch[1].length - 1;
        mentionQuery.value = atMatch[1];
        mentionActiveIndex.value = 0;
        showCommandPanel.value = false;
        showHashTagPanel.value = false;
        updatePanelPosition();
        searchMembers(atMatch[1]);
        return;
    }

    // Check for # tag (when VortFlow/VortGit plugins are enabled)
    if (availableHashTagCategories.value.length > 0) {
        const hashMatch = textBeforeCursor.match(/#([^\s#]*)$/);
        if (hashMatch) {
            hashTagStartPos = cursorPos - hashMatch[1].length - 1;
            showMentionPanel.value = false;
            showCommandPanel.value = false;

            const rawQuery = hashMatch[1];
            // Check if query matches a category prefix (e.g., "bug" or "bug/keyword")
            const slashIdx = rawQuery.indexOf('/');
            if (slashIdx >= 0) {
                // Two-level: category selected, now filtering items
                const catKey = rawQuery.substring(0, slashIdx);
                const itemQuery = rawQuery.substring(slashIdx + 1);
                const cat = availableHashTagCategories.value.find(c => c.key === catKey);
                if (cat) {
                    if (hashTagSelectedCategory.value?.key !== cat.key) {
                        hashTagSelectedCategory.value = cat;
                        hashTagLevel.value = 'items';
                        loadHashTagItems(cat.key);
                    }
                    hashTagQuery.value = itemQuery;
                    hashTagActiveIndex.value = 0;
                    showHashTagPanel.value = true;
                    updatePanelPosition();
                    return;
                }
            }

            // Check if the full query exactly matches a category
            const exactCat = availableHashTagCategories.value.find(c => c.key === rawQuery);
            if (exactCat && hashTagLevel.value === 'category') {
                // User typed "#bug" exactly - show items level
                hashTagSelectedCategory.value = exactCat;
                hashTagLevel.value = 'items';
                hashTagQuery.value = '';
                hashTagActiveIndex.value = 0;
                showHashTagPanel.value = true;
                updatePanelPosition();
                loadHashTagItems(exactCat.key);
                return;
            }

            // First level: filtering categories
            if (hashTagLevel.value !== 'items') {
                hashTagLevel.value = 'category';
                hashTagSelectedCategory.value = null;
            }
            hashTagQuery.value = rawQuery;
            hashTagActiveIndex.value = 0;
            showHashTagPanel.value = hashTagDisplayList.value.length > 0 || hashTagLevel.value === 'items';
            updatePanelPosition();
            return;
        }
    }

    // Check for / command (only at start of input)
    const slashMatch = textBeforeCursor.match(/^\/(\S*)$/);
    if (slashMatch) {
        commandQuery.value = slashMatch[1];
        commandActiveIndex.value = 0;
        showMentionPanel.value = false;
        showHashTagPanel.value = false;
        updatePanelPosition();
        filterCommands(slashMatch[1]);
        return;
    }

    // Close panels
    closeAllPanels();
}

function filterCommands(keyword: string) {
    const kw = keyword.toLowerCase();
    filteredCommands.value = slashCommands.filter(
        c => c.name.toLowerCase().includes(kw) || c.description.includes(kw)
    );
    showCommandPanel.value = filteredCommands.value.length > 0;
}

function selectMention(member: MentionMember) {
    const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
    if (!textarea) return;

    const before = inputText.value.substring(0, mentionStartPos);
    const after = inputText.value.substring(textarea.selectionStart);
    inputText.value = before + `@${member.name} ` + after;
    showMentionPanel.value = false;

    nextTick(() => {
        const newPos = mentionStartPos + member.name.length + 2; // @name + space
        textarea.selectionStart = textarea.selectionEnd = newPos;
        textarea.focus();
    });
}

function selectCommand(cmd: SlashCommand) {
    inputText.value = cmd.name + " ";
    showCommandPanel.value = false;

    nextTick(() => {
        const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
        if (textarea) {
            textarea.selectionStart = textarea.selectionEnd = inputText.value.length;
            textarea.focus();
        }
    });
}

// ---- #tag: load items for a category ----
async function loadHashTagItems(categoryKey: string) {
    hashTagItemsLoading.value = true;
    hashTagItems.value = [];
    try {
        let res: any;
        switch (categoryKey) {
            case 'bug':
                res = await getVortflowBugs({ page: 1, page_size: 20 });
                hashTagItems.value = (res?.items || res?.bugs || []).map((b: any) => ({
                    id: b.id || b.bug_id, title: b.title, state: b.state, priority: b.severity, category: 'bug'
                }));
                break;
            case 'task':
                res = await getVortflowTasks({ page: 1, page_size: 20 });
                hashTagItems.value = (res?.items || res?.tasks || []).map((t: any) => ({
                    id: t.id || t.task_id, title: t.title, state: t.state, category: 'task'
                }));
                break;
            case 'story':
                res = await getVortflowStories({ page: 1, page_size: 20 });
                hashTagItems.value = (res?.items || res?.stories || []).map((s: any) => ({
                    id: s.id || s.story_id, title: s.title, state: s.state, priority: s.priority, category: 'story'
                }));
                break;
            case 'milestone':
                res = await getVortflowMilestones({ page: 1, page_size: 20 });
                hashTagItems.value = (res?.items || res?.milestones || []).map((m: any) => ({
                    id: m.id || m.milestone_id, title: m.name || m.title, state: m.status, category: 'milestone'
                }));
                break;
        }
    } catch { /* ignore */ }
    hashTagItemsLoading.value = false;
}

function selectHashTagCategory(cat: HashTagCategory) {
    const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
    if (!textarea) return;

    // Replace the # query with #category/
    const before = inputText.value.substring(0, hashTagStartPos);
    const after = inputText.value.substring(textarea.selectionStart);
    inputText.value = before + `#${cat.key}/` + after;
    hashTagSelectedCategory.value = cat;
    hashTagLevel.value = 'items';
    hashTagQuery.value = '';
    hashTagActiveIndex.value = 0;
    loadHashTagItems(cat.key);

    nextTick(() => {
        const newPos = hashTagStartPos + cat.key.length + 2; // # + key + /
        textarea.selectionStart = textarea.selectionEnd = newPos;
        textarea.focus();
    });
}

function selectHashTagItem(item: HashTagItem) {
    const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
    if (!textarea) return;

    const before = inputText.value.substring(0, hashTagStartPos);
    const after = inputText.value.substring(textarea.selectionStart);
    const tag = `#${item.category}/${item.id} `;
    inputText.value = before + tag + after;
    closeAllPanels();

    nextTick(() => {
        const newPos = hashTagStartPos + tag.length;
        textarea.selectionStart = textarea.selectionEnd = newPos;
        textarea.focus();
    });
}

function scrollActiveItemIntoView(type: 'mention' | 'command' | 'hashtag') {
    nextTick(() => {
        const attr = type === 'mention' ? 'data-mention-index' : type === 'command' ? 'data-command-index' : 'data-hashtag-index';
        const idx = type === 'mention' ? mentionActiveIndex.value : type === 'command' ? commandActiveIndex.value : hashTagActiveIndex.value;
        const el = document.querySelector(`[${attr}="${idx}"]`) as HTMLElement;
        if (el) el.scrollIntoView({ block: 'nearest' });
    });
}

function handlePanelKeydown(e: KeyboardEvent) {
    if (showMentionPanel.value) {
        const list = mentionMembers.value;
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            mentionActiveIndex.value = (mentionActiveIndex.value + 1) % list.length;
            scrollActiveItemIntoView('mention');
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            mentionActiveIndex.value = (mentionActiveIndex.value - 1 + list.length) % list.length;
            scrollActiveItemIntoView('mention');
        } else if (e.key === 'Enter' || e.key === 'Tab') {
            e.preventDefault();
            e.stopPropagation();
            if (list[mentionActiveIndex.value]) selectMention(list[mentionActiveIndex.value]);
        } else if (e.key === 'Escape') {
            e.preventDefault();
            showMentionPanel.value = false;
        }
        return true;
    }
    if (showCommandPanel.value) {
        const list = filteredCommands.value;
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            commandActiveIndex.value = (commandActiveIndex.value + 1) % list.length;
            scrollActiveItemIntoView('command');
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            commandActiveIndex.value = (commandActiveIndex.value - 1 + list.length) % list.length;
            scrollActiveItemIntoView('command');
        } else if (e.key === 'Enter' || e.key === 'Tab') {
            e.preventDefault();
            e.stopPropagation();
            if (list[commandActiveIndex.value]) selectCommand(list[commandActiveIndex.value]);
        } else if (e.key === 'Escape') {
            e.preventDefault();
            showCommandPanel.value = false;
        }
        return true;
    }
    if (showHashTagPanel.value) {
        const list = hashTagDisplayList.value;
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            hashTagActiveIndex.value = (hashTagActiveIndex.value + 1) % (list.length || 1);
            scrollActiveItemIntoView('hashtag');
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            hashTagActiveIndex.value = (hashTagActiveIndex.value - 1 + (list.length || 1)) % (list.length || 1);
            scrollActiveItemIntoView('hashtag');
        } else if (e.key === 'Enter' || e.key === 'Tab') {
            e.preventDefault();
            e.stopPropagation();
            if (hashTagLevel.value === 'category') {
                const cat = filteredHashTagCategories.value[hashTagActiveIndex.value];
                if (cat) selectHashTagCategory(cat as HashTagCategory);
            } else {
                const item = filteredHashTagItems.value[hashTagActiveIndex.value];
                if (item) selectHashTagItem(item as HashTagItem);
            }
        } else if (e.key === 'Escape') {
            e.preventDefault();
            if (hashTagLevel.value === 'items') {
                // Go back to category level
                hashTagLevel.value = 'category';
                hashTagSelectedCategory.value = null;
                hashTagQuery.value = '';
                hashTagActiveIndex.value = 0;
                // Reset input to just #
                const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
                if (textarea) {
                    const before = inputText.value.substring(0, hashTagStartPos);
                    const after = inputText.value.substring(textarea.selectionStart);
                    inputText.value = before + '#' + after;
                    nextTick(() => {
                        textarea.selectionStart = textarea.selectionEnd = hashTagStartPos + 1;
                        textarea.focus();
                    });
                }
            } else {
                showHashTagPanel.value = false;
            }
        } else if (e.key === 'Backspace' && hashTagLevel.value === 'items' && !hashTagQuery.value) {
            // If at items level with empty query, go back to category
            e.preventDefault();
            hashTagLevel.value = 'category';
            hashTagSelectedCategory.value = null;
            const textarea = document.querySelector('textarea.chat-textarea') as HTMLTextAreaElement;
            if (textarea) {
                const before = inputText.value.substring(0, hashTagStartPos);
                const after = inputText.value.substring(textarea.selectionStart);
                inputText.value = before + '#' + after;
                nextTick(() => {
                    textarea.selectionStart = textarea.selectionEnd = hashTagStartPos + 1;
                    textarea.focus();
                });
            }
        }
        return true;
    }
    return false;
}

function handleClickOutsidePanel(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest('.mention-panel') && !target.closest('.chat-textarea')) {
        closeAllPanels();
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

watch(() => route.query.prompt, (val) => {
    if (val) applyPromptFromQuery();
});

onMounted(async () => {
    document.addEventListener("paste", handlePaste);
    document.addEventListener("click", handleClickOutsidePanel);

    // Bind native keydown on textarea for panel keyboard interception (arrows, ESC, Tab, Backspace)
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

    // Restore last active contact from localStorage
    let restoredContact: { type: string; id: string; name?: string; avatar_url?: string; session_id?: string; position?: string } | null = null;
    try {
        const saved = localStorage.getItem('chat-last-contact');
        if (saved) restoredContact = JSON.parse(saved);
    } catch { /* ignore */ }

    if (restoredContact?.type === "member" && restoredContact.id) {
        activeContact.value = {
            type: "member",
            id: restoredContact.id,
            name: restoredContact.name || "",
            avatar_url: restoredContact.avatar_url || "",
            position: restoredContact.position || "",
            last_message: "",
            last_message_time: 0,
            unread: 0,
            session_id: restoredContact.session_id || "",
        };
        if (restoredContact.session_id) {
            await switchSession(restoredContact.session_id);
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

    // Handle pre-filled prompt from query parameter (e.g., AiAssistButton)
    applyPromptFromQuery();
});

onUnmounted(() => {
    document.removeEventListener("paste", handlePaste);
    document.removeEventListener("click", handleClickOutsidePanel);
    for (const stream of activeStreams.values()) {
        try { stream.eventSource?.close(); } catch { /* noop */ }
        if (stream.twTimer) clearInterval(stream.twTimer);
    }
    activeStreams.clear();
});
</script>

<template>
    <div class="flex h-full">
        <!-- 左侧联系人列表 -->
        <div class="flex-shrink-0 w-[260px] overflow-hidden">
            <ContactList
                ref="contactListRef"
                :active-contact-id="activeContact?.id || 'ai'"
                @select="handleContactSelect"
            />
        </div>

        <!-- 右侧聊天区域 -->
        <div class="flex-1 flex flex-col min-w-0">
            <!-- 头部 -->
            <div class="flex items-center justify-between px-6 h-14 border-b border-gray-100 bg-white">
                <div class="flex items-center">
                    <!-- AI mode: session switcher -->
                    <template v-if="isAiMode">
                        <Bot :size="20" class="text-blue-600 mr-2" />
                        <SessionSwitcher
                            ref="sessionSwitcherRef"
                            :current-session-id="currentSessionId"
                            :current-title="currentSessionTitle"
                            @switch="switchSession"
                            @new-session="handleNewSession"
                            @sessions-loaded="handleSessionsLoaded"
                        />
                    </template>
                    <!-- Member mode: show member info (click to open profile) -->
                    <template v-else>
                        <div class="flex items-center cursor-pointer hover:opacity-80 transition-opacity" @click="memberProfileOpen = true">
                            <div class="w-8 h-8 rounded-full flex items-center justify-center mr-2 overflow-hidden"
                                :class="activeContact?.avatar_url ? '' : 'bg-gray-100'">
                                <img v-if="activeContact?.avatar_url" :src="activeContact.avatar_url" class="w-full h-full object-cover" />
                                <span v-else class="text-sm font-medium text-gray-500">{{ (activeContact?.name || '?')[0] }}</span>
                            </div>
                            <h2 class="text-base font-medium text-gray-800">{{ activeContact?.name }}</h2>
                            <span v-if="activeContact?.position" class="ml-2 text-xs text-gray-400">{{ activeContact.position }}</span>
                        </div>
                    </template>
                    <span v-if="loading" class="ml-3 flex items-center text-xs text-gray-400">
                        <Loader2 :size="14" class="animate-spin mr-1" /> 思考中...
                    </span>
                </div>
                <div class="flex items-center gap-2">
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
            <VortScrollbar ref="chatScrollbar" class="flex-1" wrap-class="px-6 py-4" view-class="min-h-full">
                <VortImagePreviewGroup class="space-y-6 min-h-full">
                    <!-- 无会话状态 -->
                    <div v-if="!currentSessionId && isAiMode" class="flex flex-col items-center justify-center h-full text-gray-400">
                        <Bot :size="48" class="mb-4 text-gray-300" />
                        <p class="text-sm">你好，我是 OpenVort AI 助手</p>
                        <p class="text-xs mt-1">开始新的对话吧</p>
                    </div>
                    <!-- 空消息状态 -->
                    <div v-else-if="messages.length === 0 && !loading" class="flex flex-col items-center justify-center h-full text-gray-400">
                        <Bot v-if="isAiMode" :size="48" class="mb-4 text-gray-300" />
                        <div v-else class="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mb-4">
                            <span class="text-lg font-medium text-gray-400">{{ (activeContact?.name || '?')[0] }}</span>
                        </div>
                        <p class="text-sm">{{ isAiMode ? '你好，我是 OpenVort AI 助手' : `与 ${activeContact?.name} 的对话` }}</p>
                        <p class="text-xs mt-1">{{ isAiMode ? '可以帮你管理任务、查询 Bug、了解项目进展' : 'AI 将以该成员的身份背景为你提供上下文相关的对话' }}</p>
                    </div>

                    <!-- 消息气泡 -->
                    <div v-for="msg in messages" :key="msg.id" class="flex" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
                        <div class="flex max-w-[80%]" :class="msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'">
                            <div class="flex-shrink-0" :class="msg.role === 'user' ? 'ml-3' : 'mr-3'">
                                <div class="w-8 h-8 rounded-full flex items-center justify-center"
                                    :class="msg.role === 'user' ? 'bg-blue-600' : 'bg-gray-100'">
                                    <span v-if="msg.role === 'user'" class="text-white text-xs font-medium">{{ (userStore.userInfo.name || 'U')[0] }}</span>
                                    <Bot v-else :size="16" class="text-blue-600" />
                                </div>
                            </div>
                            <div>
                                <div v-if="msg.role === 'user' && msg.images?.length" class="flex flex-wrap gap-2 mb-2 justify-end">
                                    <VortImage v-for="(src, i) in msg.images" :key="i" :src="src"
                                        width="80" height="80" fit="cover"
                                        class="rounded-lg border border-white/30" />
                                </div>
                            <!-- 运行中的工具调用（流式时显示在气泡上方）-->
                            <div v-if="msg.toolCalls?.some(t => t.status === 'running')" class="mb-2 space-y-1">
                                <div v-for="(tool, i) in msg.toolCalls.filter(t => t.status === 'running')" :key="'run-' + i" class="block">
                                    <div class="inline-flex items-center px-2 py-1 rounded text-xs bg-yellow-50 text-yellow-700">
                                        <Wrench :size="12" class="mr-1 flex-shrink-0" />
                                        {{ tool.name }}
                                        <span v-if="(tool.count || 1) > 1" class="ml-1 opacity-70">&times;{{ tool.count }}</span>
                                        <Loader2 :size="12" class="ml-1 animate-spin" />
                                        <span v-if="tool.elapsed" class="ml-1 text-yellow-500">{{ formatToolElapsed(tool.elapsed) }}</span>
                                    </div>
                                    <div v-if="tool.output"
                                        :ref="(el: any) => { if (el) el.scrollTop = el.scrollHeight }"
                                        class="mt-1 ml-1 max-h-60 overflow-y-auto rounded-lg bg-gray-900 text-green-400 text-xs font-mono px-3 py-2 whitespace-pre-wrap break-words leading-5 border border-gray-700/50 shadow-inner">{{ tool.output }}</div>
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
                            <!-- 已完成的工具调用（气泡下方，可展开）-->
                            <div v-if="msg.toolCalls?.some(t => t.status === 'done')" class="mt-1.5">
                                <button
                                    class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer select-none"
                                    @click="toggleToolsExpanded(msg)">
                                    <component :is="msg.toolsExpanded ? ChevronDown : ChevronRight" :size="14" />
                                    <Wrench :size="12" />
                                    <span>工具调用 ({{ msg.toolCalls.filter(t => t.status === 'done').reduce((s, t) => s + (t.count || 1), 0) }})</span>
                                </button>
                                <div v-if="msg.toolsExpanded" class="mt-1.5 space-y-1.5 pl-1">
                                    <div v-for="(tool, i) in msg.toolCalls.filter(t => t.status === 'done')" :key="'done-' + i" class="block">
                                        <div class="inline-flex items-center px-2 py-1 rounded text-xs bg-green-50 text-green-700 cursor-pointer select-none hover:bg-green-100"
                                            @click="tool.output && toggleToolCollapsed(tool)">
                                            <component :is="tool.collapsed ? ChevronRight : ChevronDown" v-if="tool.output" :size="12" class="mr-0.5 flex-shrink-0" />
                                            <Wrench :size="12" class="mr-1 flex-shrink-0" />
                                            {{ tool.name }}
                                            <span v-if="(tool.count || 1) > 1" class="ml-1 opacity-70">&times;{{ tool.count }}</span>
                                        </div>
                                        <div v-if="tool.output && !tool.collapsed"
                                            class="mt-1 ml-1 max-h-60 overflow-y-auto rounded-lg bg-gray-900 text-green-400 text-xs font-mono px-3 py-2 whitespace-pre-wrap break-words leading-5 border border-gray-700/50 shadow-inner">{{ tool.output }}</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                </VortImagePreviewGroup>
            </VortScrollbar>

            <!-- 输入区域 -->
            <div class="relative px-6 py-4" ref="inputArea"
                @dragover="handleDragOver" @dragleave="handleDragLeave" @drop="handleDrop">
                <div v-if="isDragging"
                    class="absolute inset-0 z-10 flex items-center justify-center bg-blue-50/80 border-2 border-dashed border-blue-400 rounded-xl pointer-events-none">
                    <div class="text-blue-500 text-sm font-medium flex items-center gap-2">
                        <ImagePlus :size="20" /> 松开以添加图片
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
                                        <div class="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 text-xs font-medium text-blue-600">
                                            {{ member.name.charAt(0) }}
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
                                            <BookOpen v-else-if="cat.key === 'story'" :size="14" />
                                            <Milestone v-else :size="14" />
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
                                                <div class="text-sm text-gray-800 truncate">
                                                    <span class="text-gray-400 font-mono text-xs mr-1.5">#{{ item.id }}</span>
                                                    {{ item.title }}
                                                </div>
                                                <div v-if="item.state" class="text-xs text-gray-400 mt-0.5">{{ item.state }}</div>
                                            </div>
                                        </div>
                                    </div>
                                </VortScrollbar>
                            </template>
                        </div>
                    </div>
                </Transition>

                <div class="chat-input-box bg-white rounded-xl border border-gray-200 overflow-hidden relative">
                    <div v-if="pendingImages.length" class="flex flex-wrap gap-2 px-4 pt-3">
                        <div v-for="(img, i) in pendingImages" :key="i" class="relative group">
                            <VortImage :src="img.preview" width="72" height="72" fit="cover"
                                class="rounded-lg border border-gray-200 shadow-sm" />
                            <button @click="removeImage(i)"
                                class="absolute -top-1.5 -right-1.5 w-5 h-5 bg-black/60 hover:bg-black/80 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                <X :size="12" />
                            </button>
                        </div>
                    </div>
                    <VortTextarea
                        v-model="inputText"
                        placeholder="请描述您问题，支持 Ctrl+V 粘贴图片。输入 @ 提及成员，/ 使用命令，# 引用工作项。"
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
                                v-if="loading"
                                :disabled="aborting"
                                @click="handleAbortCurrentStream"
                                class="w-20 h-9 rounded-lg flex items-center justify-center transition-colors send-btn"
                                :class="aborting ? 'send-btn-disabled' : 'send-btn-stop'"
                            >
                                <Square :size="14" fill="currentColor" class="text-white" />
                            </button>
                            <button
                                v-else
                                :disabled="!inputText.trim() && !pendingImages.length"
                                @click="handleSend"
                                class="w-20 h-9 rounded-lg flex items-center justify-center transition-colors send-btn"
                                :class="!inputText.trim() && !pendingImages.length ? 'send-btn-disabled' : 'send-btn-active'"
                            >
                                <Send :size="16" class="text-white" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Member profile drawer -->
        <MemberProfile
            v-if="activeContact && activeContact.type === 'member'"
            v-model:open="memberProfileOpen"
            :member-id="activeContact.id"
            :member-name="activeContact.name"
            :member-avatar-url="activeContact.avatar_url"
        />
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