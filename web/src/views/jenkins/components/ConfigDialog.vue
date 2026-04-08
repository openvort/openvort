<template>
    <Dialog
        :open="open"
        :title="jobName + ' - 配置详情'"
        :show-footer="false"
        width="680px"
        @update:open="handleClose"
    >
        <div v-if="loading" class="flex items-center justify-center py-16">
            <Loader2 class="w-5 h-5 animate-spin text-gray-400" />
        </div>

        <div v-else-if="config && config.sections.length > 0" class="space-y-4 max-h-[65vh] overflow-auto -mx-1 px-1">
            <!-- AI interpretation area (top) -->
            <div>
                <!-- No result yet: show action buttons -->
                <div v-if="!ai.html.value && !ai.loading.value" class="flex items-center gap-2">
                    <VortButton v-if="ai.hasCached.value" variant="outline" size="small" @click="showCachedResult">
                        <History :size="14" class="mr-1" /> 查看上次解读
                    </VortButton>
                    <VortButton variant="primary" size="small" @click="startAiInterpret">
                        <Bot :size="14" class="mr-1" /> {{ ai.hasCached.value ? "重新解读" : "AI 解读完整配置" }}
                    </VortButton>
                    <span class="text-xs text-gray-400 ml-auto">XML {{ config.raw_xml_length.toLocaleString() }} 字节</span>
                </div>

                <!-- Streaming / result -->
                <div v-else>
                    <div class="flex items-center justify-between mb-3">
                        <h3 class="text-sm font-medium text-gray-700 flex items-center gap-1.5">
                            <Bot :size="14" class="text-blue-500" /> AI 解读
                        </h3>
                        <div class="flex items-center gap-2">
                            <button
                                v-if="!ai.loading.value"
                                class="text-xs text-gray-400 hover:text-blue-500 transition-colors"
                                @click="startAiInterpret"
                            >
                                重新解读
                            </button>
                            <button
                                v-if="ai.loading.value"
                                class="text-xs text-gray-400 hover:text-red-500 transition-colors"
                                @click="ai.abort()"
                            >
                                停止
                            </button>
                        </div>
                    </div>

                    <div v-if="ai.loading.value && !ai.html.value" class="flex items-center gap-2 py-4 text-sm text-gray-400">
                        <Loader2 class="w-4 h-4 animate-spin" />
                        <span>{{ phaseLabel }}...</span>
                    </div>

                    <div
                        v-if="ai.html.value"
                        class="ai-content text-[13px] leading-[1.75] text-gray-700"
                        v-html="ai.html.value"
                    />

                    <div v-if="ai.error.value" class="text-sm text-red-500 py-2">{{ ai.error.value }}</div>

                    <div v-if="ai.loading.value && ai.html.value" class="flex items-center gap-1.5 mt-2 text-xs text-gray-400">
                        <Loader2 class="w-3 h-3 animate-spin" />
                        <span>{{ phaseLabel }}...</span>
                    </div>
                </div>
            </div>

            <!-- Structured config sections -->
            <div class="border-t border-gray-100 pt-4 space-y-4">
                <div v-for="(section, si) in config.sections" :key="si">
                    <h3 class="text-sm font-medium text-gray-700 mb-2">{{ section.title }}</h3>
                    <div class="space-y-1.5">
                        <div v-for="(item, ii) in section.items" :key="ii" class="flex items-start gap-3 text-sm">
                            <span class="text-gray-400 shrink-0 w-24 text-right text-xs leading-5">{{ item.label }}</span>
                            <pre
                                v-if="item.type === 'code'"
                                class="text-gray-700 font-mono text-xs bg-gray-50 rounded px-2.5 py-1.5 max-h-40 overflow-auto whitespace-pre-wrap break-all min-w-0 flex-1"
                            >{{ item.value }}</pre>
                            <span v-else class="text-gray-700 break-all min-w-0 text-xs leading-5">{{ item.value }}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div v-else class="text-center py-12 text-sm text-gray-400">
            无法解析配置信息
        </div>
    </Dialog>
</template>

<script setup lang="ts">
import { computed, watch } from "vue";
import { Loader2, Bot, History } from "lucide-vue-next";
import { Dialog } from "@openvort/vort-ui";
import { useInlineAi } from "../composables/useInlineAi";
import type { JenkinsConfigSummary } from "../types";

const props = defineProps<{
    open: boolean;
    jobName: string;
    config: JenkinsConfigSummary | null;
    loading: boolean;
}>();

const emit = defineEmits<{
    (e: "update:open", val: boolean): void;
}>();

const ai = useInlineAi();

const phaseLabel = computed(() => {
    switch (ai.phase.value) {
        case "thinking": return "思考中";
        case "tool_running": return "正在获取配置";
        case "generating": return "生成中";
        default: return "处理中";
    }
});

function buildPrompt() {
    if (!props.jobName || !props.config?.config_xml) return "";
    const xml = props.config.config_xml;
    const truncated = xml.length > 8000 ? xml.slice(0, 8000) + "\n<!-- ... 已截断 -->" : xml;
    return `请解读以下 Jenkins Job「${props.jobName}」的 config.xml 配置，用通俗易懂的中文解释这个 Job 做了什么，包括：源码管理、构建触发条件、构建步骤、参数化配置、后置操作等关键信息。请直接给出解读结果，不要调用任何工具。\n\n\`\`\`xml\n${truncated}\n\`\`\``;
}

function startAiInterpret() {
    const prompt = buildPrompt();
    if (!prompt) return;
    ai.run(prompt, props.jobName);
}

function showCachedResult() {
    ai.loadCache(props.jobName);
}

function handleClose(val: boolean) {
    if (!val) ai.abort();
    emit("update:open", val);
}

watch(() => props.open, (val) => {
    if (val) {
        ai.clear();
        ai.loadCache(props.jobName);
    }
});
</script>

<style scoped>
.ai-content :deep(h1),
.ai-content :deep(h2),
.ai-content :deep(h3),
.ai-content :deep(h4) {
    font-size: 13px;
    font-weight: 600;
    color: #374151;
    margin-top: 1em;
    margin-bottom: 0.4em;
}
.ai-content :deep(h1:first-child),
.ai-content :deep(h2:first-child),
.ai-content :deep(h3:first-child) {
    margin-top: 0;
}
.ai-content :deep(p) {
    margin: 0.4em 0;
}
.ai-content :deep(ul),
.ai-content :deep(ol) {
    margin: 0.3em 0;
    padding-left: 1.5em;
}
.ai-content :deep(li) {
    margin: 0.15em 0;
}
.ai-content :deep(pre) {
    background: #f9fafb;
    border-radius: 6px;
    padding: 10px 12px;
    font-size: 12px;
    line-height: 1.6;
    overflow-x: auto;
    margin: 0.5em 0;
}
.ai-content :deep(code) {
    font-size: 12px;
    background: #f3f4f6;
    border-radius: 3px;
    padding: 1px 4px;
}
.ai-content :deep(pre code) {
    background: none;
    padding: 0;
}
.ai-content :deep(strong) {
    font-weight: 600;
    color: #1f2937;
}
.ai-content :deep(table) {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin: 0.5em 0;
}
.ai-content :deep(th),
.ai-content :deep(td) {
    border: 1px solid #e5e7eb;
    padding: 4px 8px;
    text-align: left;
}
.ai-content :deep(th) {
    background: #f9fafb;
    font-weight: 600;
}
</style>
