import { ref } from "vue";

const pendingPrompt = ref("");
const _savedCorner = typeof window !== "undefined" ? localStorage.getItem("ai-float-corner") : null;
const docked = ref(_savedCorner === "tr");

export function useAiFloat() {
    function openWithPrompt(prompt: string) {
        pendingPrompt.value = prompt;
    }

    function consumePrompt(): string {
        const p = pendingPrompt.value;
        pendingPrompt.value = "";
        return p;
    }

    return { pendingPrompt, docked, openWithPrompt, consumePrompt };
}
