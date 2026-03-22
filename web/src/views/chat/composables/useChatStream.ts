import { ref, type Ref, type ComputedRef } from "vue";
import type { ChatMessage, ChatSession, PendingImage, PendingFile, Contact, Draft, ToolCall } from "../types";
import { sendChatMessage, getChatStreamUrl, createChatSession, abortChatMessage } from "@/api";
import { useUserStore } from "@/stores";
import { message } from "@/components/vort";
import { marked } from "marked";

export interface ActiveStream {
    sessionId: string;
    messageId: string;
    eventSource: EventSource;
    assistantMsg: ChatMessage;
    targetText: string;
    done: boolean;
    twTimer: ReturnType<typeof setInterval> | null;
    messagesRef: ChatMessage[];
    phase: "thinking" | "generating" | "tool_running" | "idle";
    _abortTimeout?: ReturnType<typeof setTimeout> | null;
}

export function mergeToolCalls(tools: ToolCall[]): ToolCall[] {
    const merged: ToolCall[] = [];
    for (const t of tools) {
        const last = merged[merged.length - 1];
        const isNodeTool = t.name.startsWith("node_");
        if (!isNodeTool && last && last.name === t.name && last.status === "done" && t.status === "done") {
            last.count = (last.count || 1) + 1;
            if (t.output) {
                last.output = last.output ? last.output + "\n" + t.output : t.output;
            }
            if (t.screenshots?.length) {
                last.screenshots = [...(last.screenshots || []), ...t.screenshots];
            }
        } else {
            merged.push({ ...t, count: t.count || 1 });
        }
    }
    return merged;
}

interface UseChatStreamOptions {
    messages: Ref<ChatMessage[]>;
    inputText: Ref<string>;
    loading: Ref<boolean>;
    currentSessionId: Ref<string>;
    activeContact: Ref<Contact | null>;
    sessions: Ref<ChatSession[]>;
    sessionTokens: Ref<{ input: number; output: number; messages: number; cacheCreation: number; cacheRead: number }>;
    pendingImages: Ref<PendingImage[]>;
    pendingFiles: Ref<PendingFile[]>;
    isAiMode: ComputedRef<boolean>;
    messageCounter: Ref<number>;
    drafts: Map<string, Draft>;
    sessionSwitcherRef: Ref<any>;
    scrollToBottom: (force?: boolean) => void;
    loadSessionInfo: () => Promise<void>;
    loadActiveAssignments: () => Promise<void>;
}

export function useChatStream(options: UseChatStreamOptions) {
    const {
        messages, inputText, loading, currentSessionId, activeContact, sessions,
        sessionTokens, pendingImages, pendingFiles, isAiMode, messageCounter, drafts,
        sessionSwitcherRef, scrollToBottom, loadSessionInfo, loadActiveAssignments,
    } = options;

    const userStore = useUserStore();
    const aborting = ref(false);
    const activeStreams = new Map<string, ActiveStream>();

    function toggleToolCollapsed(tool: ToolCall) {
        tool.collapsed = !tool.collapsed;
    }

    function getStreamPhase(msg: ChatMessage): string {
        if (!msg.streaming) return "idle";
        const sessionId = currentSessionId.value;
        const stream = activeStreams.get(sessionId);
        return stream?.phase || "thinking";
    }

    function getAccumulatedOutput(msg: ChatMessage): string {
        if (!msg.toolCalls) return "";
        return msg.toolCalls
            .filter(t => t.name.startsWith("node_") && t.output)
            .map(t => {
                const prefix = t.input?.command ? `$ ${t.input.command}\n` : "";
                return prefix + (t.output || "");
            })
            .join("\n");
    }

    function getRecentFileChanges(msg: ChatMessage): string[] {
        if (!msg.toolCalls) return [];
        return msg.toolCalls
            .filter(t => t.name === "node_file_write" && t.input?.path)
            .map(t => t.input!.path as string);
    }

    function renderMarkdown(text: string): string {
        if (!text) return "";
        const fenceCount = (text.match(/^```/gm) || []).length;
        let patched = text;
        if (fenceCount % 2 !== 0) {
            patched += "\n```";
        }
        return marked.parse(patched, { async: false }) as string;
    }

    async function handleSend() {
        const text = inputText.value.trim();
        const images = [...pendingImages.value];
        const files = [...pendingFiles.value].filter(f => !f.uploading);
        if (pendingFiles.value.some(f => f.uploading)) {
            message.warning("文件正在上传中，请稍候...");
            return;
        }
        if ((!text && !images.length && !files.length) || loading.value) return;

        if (!currentSessionId.value) {
            try {
                const res: any = await createChatSession();
                const newSession: ChatSession = {
                    session_id: res.session_id,
                    title: res.title || "新对话",
                    created_at: Date.now() / 1000,
                    updated_at: Date.now() / 1000,
                };
                sessions.value = [newSession, ...sessions.value];
                sessionSwitcherRef.value?.upsertSession(newSession);
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
            id: String(++messageCounter.value),
            role: "user",
            content: text,
            images: images.map((i) => i.preview),
            files: files.map(f => ({ filename: f.filename, file_url: f.file_url, file_size: f.file_size })),
            timestamp: Date.now()
        };
        messages.value.push(userMsg);
        inputText.value = "";
        pendingImages.value = [];
        pendingFiles.value = [];
        drafts.delete(sendSessionId);
        scrollToBottom(true);

        const rawAssistantMsg: ChatMessage = {
            id: String(++messageCounter.value),
            role: "assistant",
            content: "",
            toolCalls: [],
            timestamp: Date.now(),
            streaming: true,
            avatar_url: !isAiMode.value ? activeContact.value?.avatar_url : undefined,
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
                files.map(f => ({
                    file_id: f.file_id,
                    filename: f.filename,
                    file_url: f.file_url,
                    content_text: f.content_text,
                    file_size: f.file_size,
                })),
            );
            const messageId = res?.message_id;
            if (!messageId) {
                assistantMsg.content = "发送失败，请重试。";
                loading.value = false;
                return;
            }

            const streamState: ActiveStream = {
                sessionId: sendSessionId,
                messageId,
                eventSource: null as any,
                assistantMsg,
                targetText: "",
                done: false,
                twTimer: null,
                messagesRef: messages.value,
                phase: "thinking" as const,
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

            function flushAndFinish(finishOptions?: { interrupted?: boolean }) {
                if (streamState.done) return;
                streamState.done = true;
                if (streamState._abortTimeout) {
                    clearTimeout(streamState._abortTimeout);
                    streamState._abortTimeout = null;
                }
                aborting.value = false;
                stopTypewriter();
                let finalText = streamState.targetText;
                if (finishOptions?.interrupted) {
                    if (!finalText) finalText = "";
                    streamState.assistantMsg.interrupted = true;
                }
                streamState.assistantMsg.content = finalText;
                streamState.assistantMsg.streaming = false;
                activeStreams.delete(sendSessionId);

                if (currentSessionId.value === sendSessionId) {
                    loading.value = false;
                }

                if (currentSessionId.value !== sendSessionId) {
                    // noop: unread is managed by notification store via WebSocket
                } else {
                    scrollToBottom();
                    loadSessionInfo();
                }
                loadActiveAssignments();
            }

            const url = getChatStreamUrl(messageId, userStore.token);
            const eventSource = new EventSource(url);
            streamState.eventSource = eventSource;

            eventSource.addEventListener("text", (e: MessageEvent) => {
                streamState.targetText = e.data;
                streamState.phase = "generating";
                startTypewriter();
            });

            eventSource.addEventListener("thinking", (_e: MessageEvent) => {});

            eventSource.addEventListener("tool_use", (e: MessageEvent) => {
                try {
                    const data = JSON.parse(e.data);
                    streamState.phase = "tool_running";
                    if (!streamState.assistantMsg.toolCalls) streamState.assistantMsg.toolCalls = [];
                    const calls = streamState.assistantMsg.toolCalls;
                    const last = calls[calls.length - 1];
                    const isNodeTool = data.name.startsWith("node_");
                    if (!isNodeTool && last && last.name === data.name && last.status === "done") {
                        last.count = (last.count || 1) + 1;
                        last.status = "running";
                        last.elapsed = undefined;
                    } else {
                        calls.push({ name: data.name, status: "running", count: 1, id: data.id, input: data.input });
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
                        call.hasLiveOutput = true;
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
                    streamState.phase = "thinking";
                    const calls = streamState.assistantMsg.toolCalls;
                    const call = calls && [...calls].reverse().find(t => t.name === data.name && t.status === "running");
                    if (call) {
                        call.status = "done";
                        if (data.result) {
                            if (data.result.includes("[screenshot]")) {
                                const matches = Array.from(
                                    data.result.matchAll(/\[screenshot\]([A-Za-z0-9+/=]+)/g),
                                );
                                if (matches.length) {
                                    const newScreenshots = matches.map((m: any) => m[1].trim());
                                    call.screenshots = [
                                        ...(call.screenshots || []),
                                        ...newScreenshots,
                                    ];
                                    call.output = data.result
                                        .replace(/\[screenshot\][A-Za-z0-9+/=]+/g, "")
                                        .trim();
                                } else {
                                    call.output = data.result;
                                }
                            } else {
                                call.output = data.result;
                            }
                        }
                        call.collapsed = call.hasLiveOutput ? false : !!call.output;
                    }
                    if (currentSessionId.value === sendSessionId) scrollToBottom();
                } catch { /* ignore */ }
            });

            eventSource.addEventListener("title_updated", (e: MessageEvent) => {
                try {
                    const data = JSON.parse(e.data);
                    let updated = false;
                    sessions.value = sessions.value.map((session) => {
                        if (session.session_id !== data.session_id) return session;
                        if (session.title === data.title) return session;
                        updated = true;
                        return { ...session, title: data.title };
                    });
                    if (updated) {
                        sessionSwitcherRef.value?.updateSessionTitle(data.session_id, data.title);
                    }
                } catch { /* ignore */ }
            });

            eventSource.addEventListener("action_button", (e: MessageEvent) => {
                try {
                    const data = JSON.parse(e.data);
                    if (!streamState.assistantMsg.actionButtons) streamState.assistantMsg.actionButtons = [];
                    streamState.assistantMsg.actionButtons.push({
                        action: data.action,
                        label: data.label,
                        params: data.params,
                    });
                    if (currentSessionId.value === sendSessionId) scrollToBottom();
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
                streamState.phase = "idle";
                eventSource.close();
                flushAndFinish();
            });

            eventSource.addEventListener("interrupted", (_e: MessageEvent) => {
                streamState.phase = "idle";
                eventSource.close();
                flushAndFinish({ interrupted: true });
            });

            eventSource.addEventListener("server_error", (e: MessageEvent) => {
                const data = e.data;
                if (data) {
                    let errorMsg = "AI 服务暂时不可用，请稍后重试";
                    try {
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
                        // use default error message
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
            const trackEvent = () => { lastEventTime = Date.now(); };
            for (const evtName of ["text", "tool_use", "tool_output", "tool_progress", "tool_result", "usage", "thinking", "done", "server_error", "interrupted"]) {
                eventSource.addEventListener(evtName, trackEvent);
            }
        } catch (err: any) {
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
        if (!streamState || streamState.done) {
            loading.value = false;
            return;
        }

        aborting.value = true;

        function forceFinalize() {
            if (streamState.done) return;
            streamState.done = true;
            if (streamState._abortTimeout) {
                clearTimeout(streamState._abortTimeout);
                streamState._abortTimeout = null;
            }
            aborting.value = false;
            if (streamState.twTimer) {
                clearInterval(streamState.twTimer);
                streamState.twTimer = null;
            }
            streamState.assistantMsg.content = streamState.targetText || "";
            streamState.assistantMsg.streaming = false;
            streamState.assistantMsg.interrupted = true;
            activeStreams.delete(sessionId);
            loading.value = false;
            scrollToBottom(true);
            loadSessionInfo();
        }

        try {
            await abortChatMessage(streamState.messageId);
        } catch {
            try { streamState.eventSource?.close(); } catch { /* noop */ }
            forceFinalize();
            return;
        }

        if (!streamState.done) {
            streamState._abortTimeout = setTimeout(() => {
                try { streamState.eventSource?.close(); } catch { /* noop */ }
                forceFinalize();
            }, 15000);
        }
    }

    return {
        aborting,
        activeStreams,
        handleSend,
        handleAbortCurrentStream,
        toggleToolCollapsed,
        getStreamPhase,
        getAccumulatedOutput,
        getRecentFileChanges,
        renderMarkdown,
    };
}
