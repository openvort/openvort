<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from "vue";
import { useRoute, useRouter } from "vue-router";
import { message } from "@openvort/vort-ui";
import {
    ArrowLeft, Download, Plus, Send, Loader2, ImagePlus,
    FileCode2, Copy, Trash2, Pencil, MoreHorizontal, X, Square,
} from "lucide-vue-next";
import { Textarea as VortTextarea } from "@openvort/vort-ui";
import {
    getSketch, getSketchPage,
    createSketchPage, updateSketchPage, deleteSketchPage, duplicateSketchPage,
} from "@/api";
import SketchPreview from "./components/SketchPreview.vue";
import { useSketchStream, type SketchStreamResult, type SketchImage } from "./composables/useSketchStream";
import aiAvatarUrl from "@/assets/brand/ai-avatar.png";

interface PageItem {
    id: string;
    sketch_id: string;
    name: string;
    sort_order: number;
    created_at: string;
    updated_at: string;
}

interface ConversationItem {
    role: "user" | "assistant" | "system";
    content: string;
    images?: string[];
}

const route = useRoute();
const router = useRouter();
const { generating, streamingHtml, error: streamError, generate, iterate, abort } = useSketchStream();

const loading = ref(true);
const sketchId = computed(() => route.params.id as string);
const sketch = ref<any>(null);
const pages = ref<PageItem[]>([]);
const currentPageId = ref<string>("");
const htmlContent = ref("");
const fullscreen = ref(false);
const previewRef = ref<InstanceType<typeof SketchPreview> | null>(null);

const _chatStorageKey = computed(() => `vortsketch_chat_${sketchId.value}`);

const previewHtml = computed(() => {
    if (generating.value && streamingHtml.value) {
        const raw = streamingHtml.value;
        let start = raw.indexOf("<!DOCTYPE");
        if (start === -1) start = raw.indexOf("<html");
        if (start === -1) start = raw.indexOf("<!doctype");
        if (start >= 0) return raw.slice(start);
        return htmlContent.value;
    }
    return htmlContent.value;
});

const streamingSummary = computed(() => {
    if (!generating.value || !streamingHtml.value) return "";
    const raw = streamingHtml.value;
    const match = raw.match(/^SUMMARY:\s*(.+?)(?:\n|$)/);
    return match ? match[1].trim() : "";
});

const inputText = ref("");
const conversation = ref<ConversationItem[]>([]);
const chatScrollRef = ref<HTMLDivElement | null>(null);

const pendingImages = ref<{ data: string; media_type: string; preview: string }[]>([]);

const renamingPageId = ref("");
const renameValue = ref("");
const renameInputRef = ref<HTMLInputElement | null>(null);
const showMenuPageId = ref("");

const currentPage = computed(() => pages.value.find(p => p.id === currentPageId.value));

function scrollChatToBottom() {
    setTimeout(() => {
        if (chatScrollRef.value) {
            chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight;
        }
    }, 50);
}

// ---- Image paste/drop ----

function handlePaste(e: ClipboardEvent) {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
        if (item.type.startsWith("image/")) {
            const file = item.getAsFile();
            if (file) {
                e.preventDefault();
                addImageFile(file);
            }
        }
    }
}

function addImageFile(file: File) {
    if (pendingImages.value.length >= 5) {
        message.warning("最多 5 张图片");
        return;
    }
    const reader = new FileReader();
    reader.onload = () => {
        const dataUrl = reader.result as string;
        const match = dataUrl.match(/^data:(image\/[^;]+);base64,(.+)$/);
        if (match) {
            pendingImages.value.push({
                data: match[2]!,
                media_type: match[1]!,
                preview: dataUrl,
            });
        }
    };
    reader.readAsDataURL(file);
}

function removeImage(index: number) {
    pendingImages.value.splice(index, 1);
}

// ---- Sketch / Page ----

async function loadSketch() {
    loading.value = true;
    try {
        const res: any = await getSketch(sketchId.value);
        sketch.value = res;
        pages.value = res.pages || [];

        const queryPage = route.query.page as string;
        const targetPage = queryPage && pages.value.some(p => p.id === queryPage)
            ? queryPage
            : pages.value[0]?.id;
        if (targetPage && !currentPageId.value) {
            await selectPage(targetPage);
        }
    } catch {
        message.error("加载原型失败");
    } finally {
        loading.value = false;
    }
}

async function selectPage(pageId: string) {
    if (pageId === currentPageId.value) return;

    _saveChatHistory();
    currentPageId.value = pageId;
    htmlContent.value = "";
    pendingImages.value = [];

    router.replace({ query: { ...route.query, page: pageId } });

    _restoreChatHistory(pageId);

    try {
        const res: any = await getSketchPage(sketchId.value, pageId);
        htmlContent.value = res?.html_content || "";
    } catch {
        message.error("加载页面失败");
    }
}

async function handleCreatePage() {
    const name = `页面 ${pages.value.length + 1}`;
    try {
        const res: any = await createSketchPage(sketchId.value, { name });
        pages.value.push(res);
        await selectPage(res.id);
    } catch {
        message.error("创建页面失败");
    }
}

async function handleDuplicate(page: PageItem) {
    showMenuPageId.value = "";
    try {
        const res: any = await duplicateSketchPage(sketchId.value, page.id);
        pages.value.push(res);
        await selectPage(res.id);
        message.success("已复制");
    } catch {
        message.error("复制失败");
    }
}

function startRename(page: PageItem) {
    showMenuPageId.value = "";
    renamingPageId.value = page.id;
    renameValue.value = page.name;
    nextTick(() => renameInputRef.value?.focus());
}

async function confirmRename() {
    const pageId = renamingPageId.value;
    const name = renameValue.value.trim();
    renamingPageId.value = "";
    if (!name || !pageId) return;
    const page = pages.value.find(p => p.id === pageId);
    if (!page || page.name === name) return;
    try {
        await updateSketchPage(sketchId.value, pageId, { name });
        page.name = name;
    } catch {
        message.error("重命名失败");
    }
}

function cancelRename() {
    renamingPageId.value = "";
}

async function handleDeletePage(page: PageItem) {
    showMenuPageId.value = "";
    try {
        await deleteSketchPage(sketchId.value, page.id);
        const idx = pages.value.findIndex(p => p.id === page.id);
        pages.value.splice(idx, 1);
        if (currentPageId.value === page.id) {
            if (pages.value.length > 0) {
                const next = pages.value[Math.min(idx, pages.value.length - 1)];
                await selectPage(next.id);
            } else {
                currentPageId.value = "";
                htmlContent.value = "";
                conversation.value = [];
            }
        }
        message.success("已删除");
    } catch {
        message.error("删除失败");
    }
}

// ---- Chat / Generate ----

async function handleSend() {
    const text = inputText.value.trim();
    if ((!text && pendingImages.value.length === 0) || generating.value || !currentPageId.value) return;

    const images: SketchImage[] = pendingImages.value.map(img => ({
        data: img.data,
        media_type: img.media_type,
    }));
    const previews = pendingImages.value.map(img => img.preview);

    inputText.value = "";
    pendingImages.value = [];

    conversation.value.push({
        role: "user",
        content: text,
        images: previews.length > 0 ? previews : undefined,
    });

    const hasHtml = !!htmlContent.value;
    conversation.value.push({
        role: "system",
        content: hasHtml ? "正在修改原型..." : "正在生成原型...",
    });
    scrollChatToBottom();

    let result: SketchStreamResult | null;
    if (hasHtml) {
        result = await iterate(
            sketchId.value, currentPageId.value, text,
            images.length > 0 ? images : undefined,
        );
    } else {
        result = await generate(
            sketchId.value, currentPageId.value,
            { description: text, images: images.length > 0 ? images : undefined },
        );
    }

    handleStreamResult(result);
}

async function handleStreamResult(result: SketchStreamResult | null) {
    const sysIdx = conversation.value.findLastIndex(m => m.role === "system");
    if (sysIdx >= 0) conversation.value.splice(sysIdx, 1);

    if (result?.html_content) {
        if (result.patches && previewRef.value) {
            for (const [name, sectionHtml] of Object.entries(result.patches)) {
                previewRef.value.patchSection(name, sectionHtml);
            }
        }
        htmlContent.value = result.html_content;
        conversation.value.push({ role: "assistant", content: result.ai_summary || "已生成原型" });
    } else if (streamError.value) {
        conversation.value.push({ role: "assistant", content: streamError.value });
        message.error(streamError.value);
    } else {
        await _reloadPageContent();
        if (htmlContent.value) {
            conversation.value.push({ role: "assistant", content: "已完成生成" });
        }
    }
    _saveChatHistory();
    scrollChatToBottom();
}

function handleStop() {
    abort();
    const sysIdx = conversation.value.findLastIndex(m => m.role === "system");
    if (sysIdx >= 0) conversation.value.splice(sysIdx, 1);
    conversation.value.push({ role: "assistant", content: "已停止生成" });
    _saveChatHistory();
    scrollChatToBottom();
}

async function _reloadPageContent() {
    if (!currentPageId.value) return;
    try {
        const res: any = await getSketchPage(sketchId.value, currentPageId.value);
        if (res?.html_content) htmlContent.value = res.html_content;
    } catch { /* ignore */ }
}

function _chatKey(pageId?: string) {
    return `${_chatStorageKey.value}_${pageId || currentPageId.value}`;
}

function _saveChatHistory() {
    if (!currentPageId.value || conversation.value.length === 0) return;
    try {
        const items = conversation.value.filter(m => m.role !== "system");
        sessionStorage.setItem(_chatKey(), JSON.stringify(items));
    } catch { /* quota exceeded */ }
}

function _restoreChatHistory(pageId: string) {
    try {
        const raw = sessionStorage.getItem(_chatKey(pageId));
        conversation.value = raw ? JSON.parse(raw) : [];
    } catch {
        conversation.value = [];
    }
}

function handlePressEnter(e: KeyboardEvent) {
    if (e.shiftKey) return;
    e.preventDefault();
    handleSend();
}

function handleExport() {
    if (!htmlContent.value) return;
    const blob = new Blob([htmlContent.value], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${currentPage.value?.name || "prototype"}.html`;
    a.click();
    URL.revokeObjectURL(url);
}

function goBack() {
    window.close();
}

function toggleMenu(pageId: string) {
    showMenuPageId.value = showMenuPageId.value === pageId ? "" : pageId;
}

watch(streamingSummary, (val) => {
    if (!val) return;
    const sysIdx = conversation.value.findLastIndex(m => m.role === "system");
    if (sysIdx >= 0) {
        conversation.value[sysIdx].content = val;
        scrollChatToBottom();
    }
});

watch(showMenuPageId, (val) => {
    if (!val) return;
    const handler = (e: MouseEvent) => {
        const target = e.target as HTMLElement;
        if (!target.closest("[data-page-menu]")) {
            showMenuPageId.value = "";
        }
    };
    setTimeout(() => document.addEventListener("click", handler, { once: true }), 0);
});

function _ensureTailwindCdn() {
    if (document.getElementById("vort-tw-cdn")) return;
    const cfg = document.createElement("script");
    cfg.id = "vort-tw-cdn-cfg";
    cfg.textContent = 'window.tailwind=window.tailwind||{};window.tailwind.config={important:".sketch-preview"};';
    document.head.appendChild(cfg);
    const s = document.createElement("script");
    s.id = "vort-tw-cdn";
    s.src = "https://cdn.tailwindcss.com";
    document.head.appendChild(s);
}

onMounted(() => {
    _ensureTailwindCdn();
    loadSketch();
    document.addEventListener("paste", handlePaste);
});

onUnmounted(() => {
    document.removeEventListener("paste", handlePaste);
});
</script>

<template>
    <div class="flex flex-col h-screen overflow-hidden bg-gray-50">
        <!-- Top bar -->
        <div class="flex items-center justify-between px-4 py-2.5 border-b bg-white shrink-0">
            <div class="flex items-center gap-3">
                <button class="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500" @click="goBack">
                    <ArrowLeft :size="18" />
                </button>
                <div v-if="sketch">
                    <h1 class="text-sm font-semibold text-gray-900">{{ sketch.name }}</h1>
                    <p class="text-xs text-gray-400">{{ pages.length }} 个页面</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <vort-button size="small" :disabled="!htmlContent || generating" @click="handleExport">
                    <Download :size="14" class="mr-1" />
                    导出 HTML
                </vort-button>
            </div>
        </div>

        <!-- Main content -->
        <div v-if="loading" class="flex-1 flex items-center justify-center">
            <vort-spin :spinning="true" />
        </div>
        <div v-else class="flex flex-1 min-h-0">
            <!-- Left: Page list -->
            <div class="w-52 flex flex-col border-r bg-white shrink-0">
                <div class="flex items-center justify-between px-3 py-2.5 border-b">
                    <span class="text-xs font-medium text-gray-500">页面</span>
                    <button class="p-1 rounded hover:bg-gray-100 text-gray-500" title="新建页面" @click="handleCreatePage">
                        <Plus :size="14" />
                    </button>
                </div>
                <div class="flex-1 overflow-y-auto py-1">
                    <div v-for="(page, idx) in pages" :key="page.id" class="group relative mx-1.5 mb-0.5">
                        <div v-if="renamingPageId === page.id" class="flex items-center gap-1 px-2 py-1.5">
                            <input
                                ref="renameInputRef"
                                v-model="renameValue"
                                class="flex-1 text-xs px-1.5 py-0.5 border rounded outline-none focus:ring-1 focus:ring-indigo-300"
                                @keydown.enter="confirmRename"
                                @keydown.escape="cancelRename"
                                @blur="confirmRename"
                            />
                        </div>
                        <div
                            v-else
                            class="flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer text-xs transition-colors"
                            :class="currentPageId === page.id
                                ? 'bg-indigo-50 text-indigo-700 font-medium'
                                : 'text-gray-600 hover:bg-gray-50'"
                            @click="selectPage(page.id)"
                        >
                            <FileCode2 :size="14" class="shrink-0 opacity-50" />
                            <span class="truncate flex-1">{{ page.name }}</span>
                            <span class="shrink-0 text-[10px] text-gray-300 mr-0.5">{{ idx + 1 }}</span>
                            <button
                                data-page-menu
                                class="shrink-0 p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-gray-200 text-gray-400"
                                @click.stop="toggleMenu(page.id)"
                            >
                                <MoreHorizontal :size="12" />
                            </button>
                            <div
                                v-if="showMenuPageId === page.id"
                                data-page-menu
                                class="absolute right-0 top-full z-20 mt-0.5 w-28 bg-white rounded-lg shadow-lg border py-1"
                            >
                                <button class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50" @click.stop="startRename(page)">
                                    <Pencil :size="12" /> 重命名
                                </button>
                                <button class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50" @click.stop="handleDuplicate(page)">
                                    <Copy :size="12" /> 复制
                                </button>
                                <button class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-500 hover:bg-red-50" @click.stop="handleDeletePage(page)">
                                    <Trash2 :size="12" /> 删除
                                </button>
                            </div>
                        </div>
                    </div>
                    <div v-if="pages.length === 0" class="flex flex-col items-center justify-center py-10 px-4 text-center">
                        <FileCode2 :size="24" class="text-gray-300 mb-2" />
                        <p class="text-xs text-gray-400 mb-3">还没有页面</p>
                        <vort-button size="small" @click="handleCreatePage">
                            <Plus :size="12" class="mr-1" /> 创建页面
                        </vort-button>
                    </div>
                </div>
            </div>

            <!-- Center: Preview -->
            <div class="flex-1 flex flex-col min-w-0 p-3">
                <template v-if="currentPageId">
                    <SketchPreview
                        ref="previewRef"
                        :html="previewHtml"
                        :fullscreen="fullscreen"
                        :generating="generating"
                        class="flex-1 min-h-0"
                        @toggle-fullscreen="fullscreen = !fullscreen"
                    />
                </template>
                <div v-else class="flex-1 flex items-center justify-center">
                    <div class="text-center">
                        <FileCode2 :size="48" :stroke-width="1" class="mx-auto text-gray-200 mb-4" />
                        <p class="text-sm text-gray-400 mb-1">选择一个页面开始编辑</p>
                        <p class="text-xs text-gray-300">或点击左侧 + 创建新页面</p>
                    </div>
                </div>
            </div>

            <!-- Right: Chat panel -->
            <div v-if="!fullscreen" class="w-80 xl:w-96 flex flex-col border-l bg-white shrink-0">
                <template v-if="currentPageId">
                    <!-- Header -->
                    <div class="flex items-center gap-2 px-4 py-2.5 border-b shrink-0">
                        <img :src="aiAvatarUrl" class="w-6 h-6 rounded-full" />
                        <span class="text-xs font-medium text-gray-700">AI 原型助手</span>
                        <span v-if="generating" class="ml-auto text-[10px] text-indigo-500 flex items-center gap-1">
                            <Loader2 :size="10" class="animate-spin" /> 生成中
                        </span>
                    </div>

                    <!-- Conversation -->
                    <div ref="chatScrollRef" class="flex-1 overflow-y-auto p-4 space-y-4">
                        <div v-if="conversation.length === 0 && !generating" class="flex flex-col items-center justify-center h-full">
                            <img :src="aiAvatarUrl" class="w-14 h-14 rounded-full mb-3 opacity-80" />
                            <p class="text-sm text-gray-400 text-center px-6 leading-relaxed">
                                {{ previewHtml ? '描述你想修改的内容，我来帮你调整' : '描述你想要的界面，我来帮你生成' }}
                            </p>
                        </div>

                        <template v-for="(msg, idx) in conversation" :key="idx">
                            <!-- System -->
                            <div v-if="msg.role === 'system'" class="flex justify-center">
                                <span class="flex items-center gap-2 text-xs text-indigo-500 bg-indigo-50 px-3 py-1.5 rounded-full">
                                    <Loader2 :size="12" class="animate-spin" />
                                    {{ msg.content }}
                                </span>
                            </div>

                            <!-- User -->
                            <div v-else-if="msg.role === 'user'" class="flex flex-col items-end gap-1.5">
                                <div v-if="msg.images?.length" class="flex gap-1.5 flex-wrap justify-end max-w-[85%]">
                                    <img
                                        v-for="(imgSrc, imgIdx) in msg.images"
                                        :key="imgIdx"
                                        :src="imgSrc"
                                        class="w-20 h-20 object-cover rounded-lg border"
                                    />
                                </div>
                                <div v-if="msg.content" class="max-w-[85%] rounded-2xl rounded-tr-md px-3.5 py-2 text-sm bg-indigo-600 text-white">
                                    {{ msg.content }}
                                </div>
                            </div>

                            <!-- Assistant -->
                            <div v-else class="flex gap-2 items-start">
                                <img :src="aiAvatarUrl" class="w-7 h-7 rounded-full shrink-0 mt-0.5" />
                                <div class="max-w-[85%] rounded-2xl rounded-tl-md px-3.5 py-2 text-sm bg-gray-100 text-gray-700">
                                    {{ msg.content }}
                                </div>
                            </div>
                        </template>
                    </div>

                    <!-- Input box -->
                    <div class="p-3 shrink-0">
                        <div class="sketch-input-box bg-white rounded-xl border border-gray-200 overflow-hidden relative">
                            <div v-if="pendingImages.length" class="flex flex-wrap gap-2 px-4 pt-3">
                                <div v-for="(img, idx) in pendingImages" :key="idx" class="relative group">
                                    <img :src="img.preview" class="w-[72px] h-[72px] object-cover rounded-lg border border-gray-200 shadow-sm" />
                                    <button
                                        @click="removeImage(idx)"
                                        class="absolute -top-1.5 -right-1.5 w-5 h-5 bg-black/60 hover:bg-black/80 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                                    >
                                        <X :size="12" />
                                    </button>
                                </div>
                            </div>
                            <VortTextarea
                                v-model="inputText"
                                :placeholder="previewHtml ? '描述你想修改的内容，支持ctrl+v粘贴图片' : '描述你想要的界面，支持ctrl+v粘贴图片'"
                                :auto-size="{ minRows: 1, maxRows: 4 }"
                                :bordered="false"
                                class="sketch-textarea"
                                :disabled="generating"
                                @press-enter="handlePressEnter"
                            />
                            <div class="flex items-center justify-between px-3 py-1.5">
                                <div class="flex items-center gap-1">
                                    <vort-tooltip title="粘贴图片 (Ctrl+V)">
                                        <button class="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors cursor-pointer">
                                            <ImagePlus :size="16" />
                                        </button>
                                    </vort-tooltip>
                                </div>
                                <div class="flex items-center gap-2">
                                    <button
                                        v-if="generating"
                                        @click="handleStop"
                                        class="w-16 h-8 rounded-lg flex items-center justify-center transition-colors sketch-send-btn sketch-send-btn-stop"
                                    >
                                        <Square :size="14" fill="currentColor" class="text-white" />
                                    </button>
                                    <button
                                        v-else
                                        :disabled="!inputText.trim() && !pendingImages.length"
                                        @click="handleSend"
                                        :class="[
                                            'w-16 h-8 rounded-lg flex items-center justify-center transition-colors sketch-send-btn',
                                            !inputText.trim() && !pendingImages.length ? 'sketch-send-btn-disabled' : 'sketch-send-btn-active'
                                        ]"
                                    >
                                        <Send :size="14" class="text-white" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </template>

                <div v-else class="flex-1 flex items-center justify-center text-gray-300">
                    <p class="text-sm">选择页面后开始对话</p>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.sketch-textarea {
    padding: 8px 12px 4px !important;
    line-height: 1.6 !important;
    font-size: 13px !important;
}
.sketch-input-box:focus-within {
    border-color: var(--vort-primary, #1456f0);
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}
.sketch-send-btn {
    color: #fff;
}
.sketch-send-btn-active {
    background-color: var(--vort-primary, #1456f0);
    cursor: pointer;
}
.sketch-send-btn-active:hover {
    background-color: var(--vort-primary-hover, #3372f7);
}
.sketch-send-btn-stop {
    background-color: var(--vort-primary, #1456f0);
    cursor: pointer;
}
.sketch-send-btn-stop:hover {
    background-color: var(--vort-primary-hover, #3372f7);
}
.sketch-send-btn-disabled {
    background-color: var(--vort-primary, #1456f0);
    opacity: 0.4;
    cursor: not-allowed;
}
</style>
