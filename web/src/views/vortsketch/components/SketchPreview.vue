<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from "vue";
import { Maximize2, Minimize2, RotateCcw, Loader2 } from "lucide-vue-next";

const SECTION_START_RE = /<!--\s*section:\s*([\w-]+)\s*-->/g;
const SECTION_END_RE = /<!--\s*\/section:\s*([\w-]+)\s*-->/g;

const props = withDefaults(defineProps<{
    html: string;
    fullscreen?: boolean;
    generating?: boolean;
}>(), {
    fullscreen: false,
    generating: false,
});

const emit = defineEmits<{
    "toggle-fullscreen": [];
}>();

const containerRef = ref<HTMLElement | null>(null);
const refreshKey = ref(0);

function _parseHtml(fullHtml: string) {
    const doc = new DOMParser().parseFromString(fullHtml, "text/html");
    const styles = Array.from(doc.querySelectorAll("style"))
        .map(s => s.textContent || "").join("\n");
    const bodyClasses = doc.body?.className || "";
    let bodyHtml = doc.body?.innerHTML || "";
    bodyHtml = bodyHtml
        .replace(/href\s*=\s*"(?:#[^"]*|\/[^"]*|)"/g, 'href="javascript:void(0)"')
        .replace(/href\s*=\s*'(?:#[^']*|\/[^']*|)'/g, "href='javascript:void(0)'");
    const bodyClassesFixed = bodyClasses
        .replace(/\bh-screen\b/g, "h-full")
        .replace(/\bmin-h-screen\b/g, "min-h-full");
    return { styles, bodyClasses: bodyClassesFixed, bodyHtml };
}

function _wrapSections(html: string): string {
    let result = html.replace(SECTION_START_RE, (m, name) =>
        `${m}<div data-vort-section="${name}" style="display:contents">`,
    );
    SECTION_START_RE.lastIndex = 0;
    result = result.replace(SECTION_END_RE, (m) => `</div>${m}`);
    SECTION_END_RE.lastIndex = 0;
    return result;
}

const parsed = computed(() => {
    if (!props.html) return null;
    const { styles, bodyClasses, bodyHtml } = _parseHtml(props.html);
    const wrapped = _wrapSections(bodyHtml);
    return { styles, bodyClasses, bodyHtml: wrapped };
});

function _blockNav(e: MouseEvent) {
    const a = (e.target as HTMLElement).closest?.("a");
    if (a) { e.preventDefault(); e.stopPropagation(); }
}

function _blockSubmit(e: Event) {
    e.preventDefault();
}

function _execInlineScripts() {
    const el = containerRef.value;
    if (!el) return;
    el.querySelectorAll("script").forEach(old => {
        if (old.src && /tailwindcss|cdn/i.test(old.src)) return;
        const s = document.createElement("script");
        s.textContent = old.textContent;
        old.parentNode?.replaceChild(s, old);
    });
}

watch(() => [parsed.value, refreshKey.value], () => {
    nextTick(() => _execInlineScripts());
});

function patchSection(name: string, html: string): boolean {
    const el = containerRef.value?.querySelector(`[data-vort-section="${name}"]`);
    if (!el) return false;
    el.innerHTML = html;
    return true;
}

function handleRefresh() {
    refreshKey.value++;
}

onMounted(() => {
    containerRef.value?.addEventListener("click", _blockNav, true);
    containerRef.value?.addEventListener("submit", _blockSubmit, true);
});

onBeforeUnmount(() => {
    containerRef.value?.removeEventListener("click", _blockNav, true);
    containerRef.value?.removeEventListener("submit", _blockSubmit, true);
});

defineExpose({ patchSection });
</script>

<template>
    <div class="relative flex flex-col h-full bg-white rounded-xl border overflow-hidden">
        <!-- Toolbar -->
        <div class="flex items-center justify-between px-3 py-1.5 border-b bg-gray-50/80 shrink-0">
            <div class="flex items-center gap-2">
                <span class="text-xs text-gray-400">Preview</span>
                <span v-if="generating" class="flex items-center gap-1 text-[10px] text-indigo-500">
                    <Loader2 :size="10" class="animate-spin" /> 生成中...
                </span>
            </div>
            <div class="flex items-center gap-1">
                <button class="p-1 rounded hover:bg-gray-200 text-gray-500" title="刷新" @click="handleRefresh">
                    <RotateCcw :size="14" />
                </button>
                <button class="p-1 rounded hover:bg-gray-200 text-gray-500" :title="fullscreen ? '退出全屏' : '全屏'" @click="emit('toggle-fullscreen')">
                    <Minimize2 v-if="fullscreen" :size="14" />
                    <Maximize2 v-else :size="14" />
                </button>
            </div>
        </div>

        <!-- Preview container (replaces iframe) -->
        <div class="flex-1 relative overflow-hidden">
            <div
                v-if="parsed"
                :key="refreshKey"
                ref="containerRef"
                class="sketch-preview absolute inset-0 overflow-auto"
                :class="parsed.bodyClasses"
            >
                <component :is="'style'" v-if="parsed.styles">{{ parsed.styles }}</component>
                <div class="sketch-preview-inner" v-html="parsed.bodyHtml" />
            </div>
            <div v-else class="absolute inset-0 flex items-center justify-center bg-white">
                <span class="text-sm text-gray-300">暂无内容</span>
            </div>
        </div>
    </div>
</template>

<style>
.sketch-preview {
    all: initial;
    display: block;
    position: absolute;
    inset: 0;
    overflow: auto;
    font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.5;
    color: #1f2937;
    -webkit-font-smoothing: antialiased;
    isolation: isolate;
}

.sketch-preview-inner {
    min-height: 100%;
}

.sketch-preview *,
.sketch-preview *::before,
.sketch-preview *::after {
    box-sizing: border-box;
}

/* h-screen / min-h-screen inside preview should reference the container, not the viewport */
.sketch-preview .h-screen {
    height: 100% !important;
}
.sketch-preview .min-h-screen {
    min-height: 100% !important;
}
</style>
