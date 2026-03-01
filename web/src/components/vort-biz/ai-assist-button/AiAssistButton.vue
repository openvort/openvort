<script setup lang="ts">
import { useRouter } from "vue-router";
import { Bot } from "lucide-vue-next";

defineOptions({ name: "AiAssistButton" });

const props = withDefaults(defineProps<{
    /** Pre-filled prompt text for the AI chat */
    prompt: string;
    /** Button label */
    label?: string;
}>(), {
    label: "AI 助手创建",
});

const router = useRouter();

function handleClick() {
    router.push({ name: "chat", query: { prompt: props.prompt } });
}
</script>

<template>
    <VortButton @click="handleClick">
        <Bot :size="14" class="mr-1" />
        {{ label }}
    </VortButton>
</template>
