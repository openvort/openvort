<script setup lang="ts">
import { computed } from "vue";
import { marked } from "marked";

const props = defineProps<{
    content: string;
}>();

const html = computed(() => {
    if (!props.content) return "";
    return marked.parse(props.content, { async: false }) as string;
});
</script>

<template>
    <div class="markdown-view" v-html="html" />
</template>

<style>
.markdown-view {
    font-size: 14px;
    line-height: 1.7;
    color: #262626;
    word-break: break-word;
}
.markdown-view h1 { font-size: 1.5em; font-weight: 700; margin: 0.67em 0; }
.markdown-view h2 { font-size: 1.25em; font-weight: 600; margin: 0.5em 0; }
.markdown-view h3 { font-size: 1.1em; font-weight: 600; margin: 0.4em 0; }
.markdown-view p { margin: 0.4em 0; }
.markdown-view ul { list-style: disc; padding-left: 1.5em; }
.markdown-view ol { list-style: decimal; padding-left: 1.5em; }
.markdown-view li { margin: 0.15em 0; }
.markdown-view blockquote {
    border-left: 3px solid #d9d9d9;
    padding-left: 12px;
    margin: 0.5em 0;
    color: #8c8c8c;
}
.markdown-view code {
    background: #f5f5f5;
    padding: 0.15em 0.4em;
    border-radius: 3px;
    font-size: 0.9em;
    color: #d63384;
}
.markdown-view pre {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 12px 16px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 0.5em 0;
}
.markdown-view pre code {
    background: none;
    color: inherit;
    padding: 0;
    border-radius: 0;
    font-size: 0.875em;
}
.markdown-view hr {
    border: none;
    border-top: 1px solid #e5e5e5;
    margin: 1em 0;
}
.markdown-view strong { font-weight: 700; }
.markdown-view em { font-style: italic; }
.markdown-view s { text-decoration: line-through; }
.markdown-view a { color: #3b82f6; text-decoration: underline; }
.markdown-view img { max-width: 100%; border-radius: 4px; }
.markdown-view table { border-collapse: collapse; width: 100%; margin: 0.5em 0; }
.markdown-view th, .markdown-view td { border: 1px solid #e5e5e5; padding: 6px 12px; text-align: left; }
.markdown-view th { background: #fafafa; font-weight: 600; }
</style>
