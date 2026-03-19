import { ref } from "vue";
import { sendChatMessage, getChatStreamUrl, createChatSession } from "@/api";
import { useUserStore } from "@/stores";
import { marked } from "marked";

/**
 * Lightweight composable for inline AI streaming.
 * Sends a prompt via the chat API and returns the streamed markdown response.
 * Caches results per key so re-opening shows the last interpretation.
 */
export function useInlineAi() {
    const loading = ref(false);
    const text = ref("");
    const html = ref("");
    const error = ref("");
    const phase = ref<"idle" | "thinking" | "tool_running" | "generating">("idle");
    const hasCached = ref(false);

    let eventSource: EventSource | null = null;
    let sessionId = "";
    let finished = false;

    const cache = new Map<string, { text: string; html: string }>();

    function renderMd(raw: string) {
        if (!raw) return "";
        const fenceCount = (raw.match(/^```/gm) || []).length;
        let patched = raw;
        if (fenceCount % 2 !== 0) patched += "\n```";
        return marked.parse(patched, { async: false }) as string;
    }

    function closeStream() {
        finished = true;
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
    }

    /** Load cached result for *key*. Returns true if cache hit. */
    function loadCache(key: string): boolean {
        const entry = cache.get(key);
        if (entry) {
            text.value = entry.text;
            html.value = entry.html;
            hasCached.value = true;
            return true;
        }
        hasCached.value = false;
        return false;
    }

    async function run(prompt: string, cacheKey: string = "") {
        abort();
        loading.value = true;
        text.value = "";
        html.value = "";
        error.value = "";
        phase.value = "thinking";
        hasCached.value = false;
        finished = false;

        const userStore = useUserStore();

        try {
            if (!sessionId) {
                const res: any = await createChatSession("Jenkins 配置解读", "ai", "");
                sessionId = res.session_id;
            }

            const sendRes: any = await sendChatMessage(prompt, [], sessionId);
            const messageId = sendRes?.message_id;
            if (!messageId) {
                error.value = "发送失败";
                loading.value = false;
                phase.value = "idle";
                return;
            }

            const url = getChatStreamUrl(messageId, userStore.token);
            eventSource = new EventSource(url);

            eventSource.addEventListener("text", (e: MessageEvent) => {
                if (finished) return;
                text.value = e.data;
                html.value = renderMd(e.data);
                phase.value = "generating";
            });

            eventSource.addEventListener("thinking", () => {
                if (finished) return;
                phase.value = "thinking";
            });

            eventSource.addEventListener("tool_use", () => {
                if (finished) return;
                phase.value = "tool_running";
            });

            eventSource.addEventListener("tool_result", () => {
                if (finished) return;
                phase.value = "thinking";
            });

            eventSource.addEventListener("done", () => {
                if (finished) return;
                html.value = renderMd(text.value);
                loading.value = false;
                phase.value = "idle";
                if (cacheKey && text.value) {
                    cache.set(cacheKey, { text: text.value, html: html.value });
                }
                closeStream();
            });

            eventSource.addEventListener("server_error", (e: MessageEvent) => {
                if (finished) return;
                error.value = e.data || "AI 服务暂时不可用";
                loading.value = false;
                phase.value = "idle";
                closeStream();
            });

            eventSource.addEventListener("interrupted", () => {
                if (finished) return;
                loading.value = false;
                phase.value = "idle";
                closeStream();
            });

            eventSource.onerror = () => {
                if (finished) return;
                if (loading.value) {
                    if (!text.value) error.value = "连接中断";
                    loading.value = false;
                    phase.value = "idle";
                }
                closeStream();
            };
        } catch {
            error.value = "请求失败";
            loading.value = false;
            phase.value = "idle";
        }
    }

    function abort() {
        closeStream();
        loading.value = false;
        phase.value = "idle";
    }

    function clear() {
        abort();
        text.value = "";
        html.value = "";
        error.value = "";
        hasCached.value = false;
    }

    function reset() {
        clear();
        sessionId = "";
    }

    return { loading, text, html, error, phase, hasCached, run, loadCache, abort, clear, reset };
}
