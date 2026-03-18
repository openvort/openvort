import { ref } from "vue";

const pendingPrompt = ref("");

export function useAiFloat() {
    function openWithPrompt(prompt: string) {
        pendingPrompt.value = prompt;
    }

    function consumePrompt(): string {
        const p = pendingPrompt.value;
        pendingPrompt.value = "";
        return p;
    }

    return { pendingPrompt, openWithPrompt, consumePrompt };
}
