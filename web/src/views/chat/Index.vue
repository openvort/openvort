<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { useUserStore } from "@/stores";
import { Send, Bot, User, Loader2, Wrench, X, ImagePlus, FileText, MonitorPlay, Smile, Settings, Check } from "lucide-vue-next";
import { Popover as VortPopover } from "@/components/vort/popover";
import { sendChatMessage, getChatStreamUrl, getChatHistory } from "@/api";
import { marked } from "marked";

interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    images?: string[]; // base64 预览用
    toolCalls?: { name: string; status: string }[];
    timestamp: number;
    streaming?: boolean;
}

interface PendingImage {
    data: string; // pure base64 (no prefix)
    media_type: string;
    preview: string; // data:url for <img>
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
let messageCounter = 0;

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
        if (chatContainer.value) {
            chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
        }
    });
}

// --- 流式 Markdown 渲染：补全未闭合的代码块 ---
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
        if (!file.type.startsWith("image/")) {
            resolve(null);
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            const dataUrl = reader.result as string;
            // "data:image/png;base64,xxxxx" -> 拆出 media_type 和 data
            const match = dataUrl.match(/^data:(image\/[^;]+);base64,(.+)$/);
            if (match) {
                resolve({
                    data: match[2],
                    media_type: match[1],
                    preview: dataUrl,
                });
            } else {
                resolve(null);
            }
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

function removeImage(index: number) {
    pendingImages.value.splice(index, 1);
}

// Ctrl+V 粘贴图片
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
    if (imageFiles.length) {
        e.preventDefault();
        addFiles(imageFiles);
    }
}

// 拖拽
function handleDragOver(e: DragEvent) {
    e.preventDefault();
    isDragging.value = true;
}
function handleDragLeave(e: DragEvent) {
    e.preventDefault();
    isDragging.value = false;
}
function handleDrop(e: DragEvent) {
    e.preventDefault();
    isDragging.value = false;
    const files = e.dataTransfer?.files;
    if (files?.length) addFiles(files);
}

// --- 历史 & 发送 ---
async function loadHistory() {
    try {
        const res: any = await getChatHistory(50);
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

    // 添加用户消息
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
    scrollToBottom();

    // 添加助手占位消息
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
            images.map((i) => ({ data: i.data, media_type: i.media_type }))
        );
        const messageId = res?.message_id;
        if (!messageId) {
            assistantMsg.content = "发送失败，请重试。";
            loading.value = false;
            return;
        }

        // --- 打字机队列 ---
        let targetText = "";
        let twTimer: ReturnType<typeof setInterval> | null = null;
        let done = false;

        function tickTypewriter() {
            const shown = assistantMsg.content.length;
            const total = targetText.length;
            if (shown < total) {
                const buffered = total - shown;
                const charsPerTick = Math.min(Math.max(1, Math.ceil(buffered / 30)), 3);
                assistantMsg.content = targetText.slice(0, shown + charsPerTick);
                scrollToBottom();
            } else if (done) {
                stopTypewriter();
            }
        }

        function startTypewriter() {
            if (twTimer) return;
            twTimer = setInterval(tickTypewriter, 30);
        }

        function stopTypewriter() {
            if (twTimer) {
                clearInterval(twTimer);
                twTimer = null;
            }
        }

        function flushAndFinish() {
            done = true;
            stopTypewriter();
            assistantMsg.content = targetText;
            assistantMsg.streaming = false;
            loading.value = false;
            scrollToBottom();
        }

        // SSE 流式接收
        const url = getChatStreamUrl(messageId, userStore.token);
        const eventSource = new EventSource(url);

        eventSource.addEventListener("text", (e: MessageEvent) => {
            targetText = e.data;
            startTypewriter();
        });

        eventSource.addEventListener("thinking", (_e: MessageEvent) => {});

        eventSource.addEventListener("tool_use", (e: MessageEvent) => {
            try {
                const data = JSON.parse(e.data);
                if (!assistantMsg.toolCalls) assistantMsg.toolCalls = [];
                assistantMsg.toolCalls.push({ name: data.name, status: "running" });
                scrollToBottom();
            } catch { /* ignore */ }
        });

        eventSource.addEventListener("tool_result", (e: MessageEvent) => {
            try {
                const data = JSON.parse(e.data);
                const call = assistantMsg.toolCalls?.find(t => t.name === data.name && t.status === "running");
                if (call) call.status = "done";
                scrollToBottom();
            } catch { /* ignore */ }
        });

        eventSource.addEventListener("done", (_e: MessageEvent) => {
            eventSource.close();
            flushAndFinish();
        });

        eventSource.addEventListener("error", (e: MessageEvent) => {
            const data = (e as any).data;
            if (data) targetText += `\n\n错误: ${data}`;
            eventSource.close();
            flushAndFinish();
        });

        eventSource.onerror = () => {
            eventSource.close();
            if (loading.value) {
                if (!targetText) targetText = "连接中断，请重试。";
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
            // Ctrl+Enter 换行
            const textarea = e.target as HTMLTextAreaElement;
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;
            inputText.value = inputText.value.substring(0, start) + '\n' + inputText.value.substring(end);
            nextTick(() => {
                textarea.selectionStart = textarea.selectionEnd = start + 1;
            });
        } else {
            // Enter 发送
            e.preventDefault();
            handleSend();
        }
    } else {
        if (e.ctrlKey || e.metaKey) {
            // Ctrl+Enter 发送
            e.preventDefault();
            handleSend();
        }
        // 普通 Enter 换行（默认行为）
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
    input.onchange = () => {
        if (input.files?.length) addFiles(input.files);
    };
    input.click();
}

function triggerVideoInput() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.mp4,.mov,.avi,.wmv,.flv,.mkv';
    input.multiple = false;
    input.onchange = () => {
        // TODO: 处理视频上传
    };
    input.click();
}

function insertEmoji(emoji: string) {
    inputText.value += emoji;
    emojiOpen.value = false;
}

onMounted(() => {
    loadHistory();
    // 全局粘贴监听
    document.addEventListener("paste", handlePaste);
});

onUnmounted(() => {
    document.removeEventListener("paste", handlePaste);
});
</script>

<template>
    <div class="flex flex-col h-full">
        <!-- 头部 -->
        <div class="flex items-center px-6 py-4 border-b border-gray-100">
            <Bot :size="20" class="text-blue-600 mr-2" />
            <h2 class="text-base font-medium text-gray-800">OpenVort AI 助手</h2>
            <span v-if="loading" class="ml-3 flex items-center text-xs text-gray-400">
                <Loader2 :size="14" class="animate-spin mr-1" /> 思考中...
            </span>
        </div>

        <!-- 消息列表 -->
        <div ref="chatContainer" class="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            <!-- 空状态 -->
            <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400">
                <Bot :size="48" class="mb-4 text-gray-300" />
                <p class="text-sm">你好，我是 OpenVort AI 助手</p>
                <p class="text-xs mt-1">可以帮你管理任务、查询 Bug、了解项目进展</p>
            </div>

            <!-- 消息气泡 -->
            <div v-for="msg in messages" :key="msg.id" class="flex" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
                <div class="flex max-w-[80%]" :class="msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'">
                    <!-- 头像 -->
                    <div class="flex-shrink-0" :class="msg.role === 'user' ? 'ml-3' : 'mr-3'">
                        <div class="w-8 h-8 rounded-full flex items-center justify-center"
                            :class="msg.role === 'user' ? 'bg-blue-600' : 'bg-gray-100'">
                            <User v-if="msg.role === 'user'" :size="16" class="text-white" />
                            <Bot v-else :size="16" class="text-blue-600" />
                        </div>
                    </div>
                    <!-- 内容 -->
                    <div>
                        <!-- 用户消息中的图片 -->
                        <div v-if="msg.role === 'user' && msg.images?.length" class="flex flex-wrap gap-2 mb-2 justify-end">
                            <img v-for="(src, i) in msg.images" :key="i" :src="src"
                                class="w-20 h-20 object-cover rounded-lg border border-white/30" />
                        </div>
                        <!-- 工具调用标签 -->
                        <div v-if="msg.toolCalls?.length" class="mb-2 space-y-1">
                            <div v-for="(tool, i) in msg.toolCalls" :key="i"
                                class="inline-flex items-center px-2 py-1 rounded text-xs mr-2"
                                :class="tool.status === 'running' ? 'bg-yellow-50 text-yellow-700' : 'bg-green-50 text-green-700'">
                                <Wrench :size="12" class="mr-1" />
                                {{ tool.name }}
                                <Loader2 v-if="tool.status === 'running'" :size="12" class="ml-1 animate-spin" />
                            </div>
                        </div>
                        <!-- 消息文本 -->
                        <div class="rounded-2xl px-4 py-3 text-sm leading-relaxed"
                            :class="msg.role === 'user'
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-100 text-gray-800'">
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
        <div class="relative px-6 py-4"
            ref="inputArea"
            @dragover="handleDragOver"
            @dragleave="handleDragLeave"
            @drop="handleDrop">
            <!-- 拖拽覆盖层 -->
            <div v-if="isDragging"
                class="absolute inset-0 z-10 flex items-center justify-center bg-blue-50/80 border-2 border-dashed border-blue-400 rounded-xl pointer-events-none">
                <div class="text-blue-500 text-sm font-medium flex items-center gap-2">
                    <ImagePlus :size="20" />
                    松开以添加图片
                </div>
            </div>
            <!-- 白色输入容器 -->
            <div class="chat-input-box bg-white rounded-xl border border-gray-200 overflow-hidden">
                <!-- 图片预览条 -->
                <div v-if="pendingImages.length" class="flex flex-wrap gap-2 px-4 pt-3">
                    <div v-for="(img, i) in pendingImages" :key="i" class="relative group">
                        <img :src="img.preview"
                            class="w-[72px] h-[72px] object-cover rounded-lg border border-gray-200 shadow-sm" />
                        <button @click="removeImage(i)"
                            class="absolute -top-1.5 -right-1.5 w-5 h-5 bg-black/60 hover:bg-black/80 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                            <X :size="12" />
                        </button>
                    </div>
                </div>
                <!-- Textarea -->
                <VortTextarea
                    v-model="inputText"
                    placeholder="请描述您问题，支持 Ctrl+V 粘贴图片。"
                    :auto-size="{ minRows: 3, maxRows: 6 }"
                    :bordered="false"
                    class="chat-textarea"
                    @press-enter="handlePressEnter"
                />
                <!-- 底部工具栏 -->
                <div class="flex items-center justify-between px-4 py-2">
                    <div class="flex items-center gap-1">
                        <VortPopover placement="top" :arrow="true">
                            <button @click="triggerFileInput"
                                class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors">
                                <FileText :size="18" />
                            </button>
                            <template #content>
                                <span class="text-xs text-gray-500 whitespace-nowrap">.jpg,.jpeg,.png,.txt,.rar,.zip,.doc,.docx,.xls,.7z</span>
                            </template>
                        </VortPopover>
                        <VortPopover placement="top" :arrow="true">
                            <button @click="triggerVideoInput"
                                class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors">
                                <MonitorPlay :size="18" />
                            </button>
                            <template #content>
                                <span class="text-xs text-gray-500 whitespace-nowrap">.mp4,.mov,.avi,.wmv,.flv,.mkv</span>
                            </template>
                        </VortPopover>
                        <VortPopover v-model:open="emojiOpen" trigger="click" placement="topLeft" :arrow="false">
                            <button class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors">
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
                        <!-- 设置按钮 + Popover -->
                        <VortPopover v-model:open="settingsOpen" trigger="click" placement="topRight" :arrow="false">
                            <button class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors">
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
                        <!-- 发送按钮 -->
                        <button
                            :disabled="(!inputText.trim() && !pendingImages.length) || loading"
                            @click="handleSend"
                            class="w-20 h-9 rounded-lg flex items-center justify-center transition-colors send-btn"
                            :class="(!inputText.trim() && !pendingImages.length) || loading
                                ? 'send-btn-disabled'
                                : 'send-btn-active'"
                        >
                            <Send :size="16" class="text-white" />
                        </button>
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

/* ========== 流式输出打字光标 ========== */

/* 聊天输入框样式 */
.chat-textarea :deep(.vort-textarea) {
    padding: 12px 16px;
}
.chat-input-box:focus-within {
    border-color: var(--vort-primary, #1456f0);
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

/* 发送按钮 */
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

/* 表情网格 */
.emoji-grid {
    display: grid;
    grid-template-columns: repeat(10, 1fr);
    gap: 2px;
    width: 400px;
    max-height: 320px;
    overflow-y: auto;
    padding: 4px;
}

/* 流式输出打字光标 */
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
