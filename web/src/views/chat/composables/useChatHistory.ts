import { ref, nextTick, type Ref } from "vue";
import type { ChatMessage, ToolCall } from "../types";
import { getChatHistory } from "@/api";
import { mergeToolCalls } from "./useChatStream";

type ChatScrollbarRef = { wrapRef?: HTMLElement | null };

const HISTORY_PAGE_SIZE = 20;

interface UseChatHistoryOptions {
    messages: Ref<ChatMessage[]>;
    currentSessionId: Ref<string>;
    chatScrollbar: Ref<ChatScrollbarRef | null>;
    messageCounter: Ref<number>;
    scrollToBottom: (force?: boolean) => void;
}

export function useChatHistory(options: UseChatHistoryOptions) {
    const { messages, currentSessionId, chatScrollbar, messageCounter, scrollToBottom } = options;

    const hasMoreHistory = ref(false);
    const historyOffset = ref(0);
    const loadingMore = ref(false);
    const contextResetAt = ref(0);

    function parseHistoryMessages(raw: any[]): ChatMessage[] {
        const parsed: ChatMessage[] = raw.map((m: any) => {
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
                id: m.id || String(++messageCounter.value),
                role: m.role,
                content,
                images,
                timestamp: m.timestamp ? m.timestamp * 1000 : 0,
                interrupted: m.interrupted || false,
            };
            if (m.tool_calls?.length) {
                msg.toolCalls = mergeToolCalls(
                    m.tool_calls.map((tc: any) => {
                        let output = tc.output || "";
                        let screenshots: string[] | undefined;
                        if (output && output.includes("[screenshot]")) {
                            const matches = Array.from(output.matchAll(/\[screenshot\]([A-Za-z0-9+/=]+)/g));
                            if (matches.length) {
                                screenshots = matches.map((m) => m[1].trim());
                                output = output.replace(/\[screenshot\][A-Za-z0-9+/=]+/g, "").trim();
                            }
                        }
                        return { name: tc.name, status: tc.status || "done", output, screenshots, collapsed: true, count: 1 } as ToolCall;
                    })
                );
            }
            return msg;
        });
        const NO_MERGE_RE = /^【/;
        const merged: ChatMessage[] = [];
        for (const msg of parsed) {
            const last = merged[merged.length - 1];
            const isNotification = NO_MERGE_RE.test(msg.content) || (last && NO_MERGE_RE.test(last.content));
            if (msg.role === "assistant" && last?.role === "assistant" && !isNotification) {
                if (msg.content) {
                    last.content = last.content ? last.content + "\n\n" + msg.content : msg.content;
                }
                if (msg.toolCalls?.length) {
                    last.toolCalls = [...(last.toolCalls || []), ...msg.toolCalls];
                }
            } else {
                merged.push(msg);
            }
        }
        return merged;
    }

    async function loadHistory(): Promise<boolean> {
        if (!currentSessionId.value) return false;
        hasMoreHistory.value = false;
        historyOffset.value = 0;
        try {
            const res: any = await getChatHistory(currentSessionId.value, HISTORY_PAGE_SIZE, 0);
            contextResetAt.value = res?.context_reset_at || 0;
            if (res?.messages) {
                messages.value = parseHistoryMessages(res.messages);
                historyOffset.value = messages.value.length;
                hasMoreHistory.value = res.has_more || false;
                scrollToBottom(true);
            }
            return true;
        } catch {
            return false;
        }
    }

    async function loadMoreHistory() {
        if (!currentSessionId.value || loadingMore.value || !hasMoreHistory.value) return;

        const wrap = chatScrollbar.value?.wrapRef;
        if (!wrap) return;

        loadingMore.value = true;
        const prevScrollHeight = wrap.scrollHeight;
        const prevScrollTop = wrap.scrollTop;

        try {
            const res: any = await getChatHistory(currentSessionId.value, HISTORY_PAGE_SIZE, historyOffset.value);
            if (res?.messages?.length) {
                const older = parseHistoryMessages(res.messages);
                messages.value = [...older, ...messages.value];
                historyOffset.value += older.length;
                hasMoreHistory.value = res.has_more || false;

                await nextTick();
                wrap.scrollTop = prevScrollTop + (wrap.scrollHeight - prevScrollHeight);
            } else {
                hasMoreHistory.value = false;
            }
        } catch { /* ignore */ }
        finally { loadingMore.value = false; }
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

    return {
        hasMoreHistory,
        historyOffset,
        loadingMore,
        contextResetAt,
        parseHistoryMessages,
        loadHistory,
        loadMoreHistory,
        formatTokens,
        formatTime,
    };
}
