import { ref } from "vue";
import { useUserStore } from "@/stores";

export interface SketchStreamResult {
    page_id: string;
    html_content: string;
    ai_summary: string;
    tokens_used: number;
    patches?: Record<string, string>;
}

export interface SketchImage {
    data: string;
    media_type: string;
}

export function useSketchStream() {
    const generating = ref(false);
    const streamingHtml = ref("");
    const error = ref("");

    let _abortController: AbortController | null = null;

    async function generate(
        sketchId: string,
        pageId: string,
        options?: { description?: string; images?: SketchImage[] },
    ): Promise<SketchStreamResult | null> {
        return _doSSE(`/api/sketches/${sketchId}/pages/${pageId}/generate`, {
            description: options?.description || "",
            images: options?.images || [],
        });
    }

    async function iterate(
        sketchId: string,
        pageId: string,
        instruction: string,
        images?: SketchImage[],
    ): Promise<SketchStreamResult | null> {
        return _doSSE(`/api/sketches/${sketchId}/pages/${pageId}/iterate`, {
            instruction,
            images: images || [],
        });
    }

    function abort() {
        _abortController?.abort();
        _abortController = null;
    }

    async function _doSSE(
        url: string,
        body: Record<string, any>,
    ): Promise<SketchStreamResult | null> {
        generating.value = true;
        streamingHtml.value = "";
        error.value = "";

        _abortController = new AbortController();

        try {
            const userStore = useUserStore();
            const resp = await fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${userStore.token}`,
                },
                body: JSON.stringify(body),
                signal: _abortController.signal,
            });

            if (!resp.ok) {
                const text = await resp.text();
                throw new Error(text || `HTTP ${resp.status}`);
            }

            const reader = resp.body?.getReader();
            if (!reader) throw new Error("No response body");

            const decoder = new TextDecoder();
            let buffer = "";
            let accumulated = "";
            let result: SketchStreamResult | null = null;
            let currentEvent = "";

            console.log("[useSketchStream] SSE connected, reading...");

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (line.startsWith("event:")) {
                        currentEvent = line.slice(6).trim();
                    } else if (line.startsWith("data:")) {
                        const dataStr = line.slice(5).trim();
                        if (!dataStr) continue;
                        try {
                            const data = JSON.parse(dataStr);

                            if (currentEvent === "html_chunk" && data.text) {
                                accumulated += data.text;
                                streamingHtml.value = accumulated;
                            } else if (currentEvent === "done" && data.html_content) {
                                result = data as SketchStreamResult;
                            } else if (currentEvent === "error" && data.message) {
                                throw new Error(data.message);
                            }
                        } catch (e: any) {
                            if (e.message && e.message !== "Unexpected end of JSON input") {
                                throw e;
                            }
                        }
                        currentEvent = "";
                    }
                }
            }

            console.log("[useSketchStream] done, accumulated:", accumulated.length, "result:", !!result);
            return result;
        } catch (e: any) {
            if (e.name === "AbortError") {
                console.log("[useSketchStream] aborted by user");
                return null;
            }
            error.value = e.message || "生成失败";
            console.warn("[useSketchStream] error:", e.message);
            return null;
        } finally {
            _abortController = null;
            generating.value = false;
            streamingHtml.value = "";
        }
    }

    return { generating, streamingHtml, error, generate, iterate, abort };
}
