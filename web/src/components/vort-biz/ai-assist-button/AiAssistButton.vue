<script setup lang="ts">
import { computed } from "vue";
import { Bot } from "lucide-vue-next";
import {
    DropdownButton,
    DropdownMenuItem,
} from "@/components/vort/dropdown";
import { useAiFloat } from "@/composables/useAiFloat";

export interface AiAssistPromptItem {
    /** Menu item label */
    label: string;
    /** Prompt text */
    prompt: string;
}

defineOptions({ name: "AiAssistButton" });

const props = withDefaults(defineProps<{
    /** Single prompt (simple button mode) */
    prompt?: string;
    /** Button label */
    label?: string;
    /** Multiple prompts (dropdown mode); first item is the default action */
    prompts?: AiAssistPromptItem[];
}>(), {
    prompt: "",
    label: "AI 助手",
});

const { openWithPrompt } = useAiFloat();

const isDropdown = computed(() => Array.isArray(props.prompts) && props.prompts.length > 0);

const defaultPrompt = computed(() => {
    if (isDropdown.value) return props.prompts![0].prompt;
    return props.prompt;
});

function go(prompt: string) {
    if (!prompt) return;
    openWithPrompt(prompt);
}
</script>

<template>
    <!-- Dropdown mode -->
    <DropdownButton v-if="isDropdown" @click="go(defaultPrompt)">
        <Bot :size="14" class="mr-1" />
        {{ label }}
        <template #overlay>
            <DropdownMenuItem
                v-for="(item, idx) in prompts"
                :key="idx"
                @click="go(item.prompt)"
            >
                {{ item.label }}
            </DropdownMenuItem>
        </template>
    </DropdownButton>

    <!-- Simple button mode (backward compatible) -->
    <VortButton v-else @click="go(defaultPrompt)">
        <Bot :size="14" class="mr-1" />
        {{ label }}
    </VortButton>
</template>
