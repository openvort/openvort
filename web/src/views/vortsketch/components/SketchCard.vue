<script setup lang="ts">
import { ref, computed } from "vue";
import { Tag as VortTag } from "@openvort/vort-ui";
import { Clock, MoreHorizontal, Pencil, Copy, Trash2, FileCode2, Files } from "lucide-vue-next";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/zh-cn";

dayjs.extend(relativeTime);
dayjs.locale("zh-cn");

interface SketchItem {
    id: string;
    name: string;
    description: string;
    project_id?: string;
    story_id?: string;
    story_type?: string;
    page_count: number;
    is_archived: boolean;
    created_at: string;
    updated_at: string;
    thumbnail_url?: string;
}

const props = defineProps<{ sketch: SketchItem }>();
const emit = defineEmits<{
    click: [sketch: SketchItem];
    edit: [sketch: SketchItem];
    duplicate: [sketch: SketchItem];
    delete: [sketch: SketchItem];
}>();

const showMenu = ref(false);

const timeAgo = computed(() => {
    return props.sketch.updated_at ? dayjs(props.sketch.updated_at).fromNow() : "";
});

const storyTypeLabel = computed(() => {
    const map: Record<string, string> = { story: "需求", task: "任务", bug: "缺陷" };
    return map[props.sketch.story_type || ""] || "";
});

const hasMultiplePages = computed(() => props.sketch.page_count > 1);

function toggleMenu() {
    showMenu.value = !showMenu.value;
    if (showMenu.value) {
        setTimeout(() => document.addEventListener("click", closeMenu, { once: true }), 0);
    }
}

function closeMenu() {
    showMenu.value = false;
}

function onEdit() {
    showMenu.value = false;
    emit("edit", props.sketch);
}

function onDuplicate() {
    showMenu.value = false;
    emit("duplicate", props.sketch);
}

function onDelete() {
    showMenu.value = false;
    emit("delete", props.sketch);
}
</script>

<template>
    <div
        class="group flex flex-col rounded-xl border bg-white transition-all cursor-pointer hover:shadow-md hover:border-[var(--vort-primary,#1456f0)]"
        @click="emit('click', sketch)"
    >
        <!-- Thumbnail area with stacked effect for multi-page -->
        <div class="relative px-3 pt-3">
            <div class="sketch-thumb-wrapper" :class="{ 'is-stacked': hasMultiplePages }">
                <div class="sketch-thumb rounded-lg bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center overflow-hidden">
                    <img
                        v-if="sketch.thumbnail_url"
                        :src="sketch.thumbnail_url"
                        :alt="sketch.name"
                        class="w-full h-full object-cover"
                    />
                    <div v-else class="flex flex-col items-center gap-2 text-gray-300">
                        <FileCode2 :size="36" :stroke-width="1.2" />
                        <span v-if="sketch.page_count === 0" class="text-xs">待生成</span>
                    </div>
                </div>
            </div>

            <!-- Hover: more actions -->
            <div class="absolute top-4.5 right-4.5 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                <button
                    class="p-1.5 rounded-lg bg-white/90 text-gray-500 hover:text-gray-700 shadow-sm"
                    @click.stop="toggleMenu"
                >
                    <MoreHorizontal :size="14" />
                </button>
                <div
                    v-if="showMenu"
                    class="absolute right-0 top-full mt-1 w-32 bg-white rounded-lg shadow-lg border py-1 z-30"
                    @click.stop
                >
                    <button class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50" @click="onEdit">
                        <Pencil :size="12" /> 编辑
                    </button>
                    <button class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50" @click="onDuplicate">
                        <Copy :size="12" /> 创建副本
                    </button>
                    <div class="my-1 border-t" />
                    <button class="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-500 hover:bg-red-50" @click="onDelete">
                        <Trash2 :size="12" /> 删除
                    </button>
                </div>
            </div>
        </div>

        <!-- Info -->
        <div class="flex flex-col gap-1 p-3.5 pt-2.5">
            <div class="flex items-center justify-between gap-2">
                <h3 class="text-sm font-medium text-gray-900 truncate">{{ sketch.name }}</h3>
                <span v-if="sketch.page_count > 0" class="shrink-0 flex items-center gap-1 text-[11px] text-gray-400">
                    <Files :size="12" />
                    {{ sketch.page_count }} 页面
                </span>
            </div>

            <p v-if="sketch.description" class="text-xs text-gray-500 line-clamp-1">{{ sketch.description }}</p>

            <div class="flex items-center gap-2 mt-0.5">
                <VortTag v-if="storyTypeLabel && sketch.story_id" size="small" color="blue">
                    {{ storyTypeLabel }}
                </VortTag>
                <span class="flex items-center gap-1 text-xs text-gray-400 ml-auto">
                    <Clock :size="12" />
                    {{ timeAgo }}
                </span>
            </div>
        </div>
    </div>
</template>

<style scoped>
.sketch-thumb {
    position: relative;
    height: 10rem;
    z-index: 2;
}

.sketch-thumb-wrapper {
    position: relative;
}

.sketch-thumb-wrapper.is-stacked::before,
.sketch-thumb-wrapper.is-stacked::after {
    content: "";
    position: absolute;
    border-radius: 0.5rem;
    background: linear-gradient(135deg, #f9fafb, #f3f4f6);
    border: 1px solid #e5e7eb;
}

.sketch-thumb-wrapper.is-stacked::before {
    inset: 4px 0 -4px 4px;
    z-index: 1;
}

.sketch-thumb-wrapper.is-stacked::after {
    inset: 8px -1px -8px 8px;
    z-index: 0;
    opacity: 0.6;
}
</style>
