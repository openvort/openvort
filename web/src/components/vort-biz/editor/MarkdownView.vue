<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue";
import { marked } from "marked";
import { X, ZoomIn, ZoomOut, RotateCw, RotateCcw, Maximize, Download, ChevronLeft, ChevronRight } from "lucide-vue-next";
import { getVortTeleportTo } from "@/components/vort-biz/utils/teleport";

const props = defineProps<{
    content: string;
}>();

const html = computed(() => {
    if (!props.content) return "";
    return marked.parse(props.content, { async: false }) as string;
});

const contentRef = ref<HTMLElement | null>(null);
const images = ref<string[]>([]);
const previewVisible = ref(false);
const currentIndex = ref(0);
const scale = ref(1);
const rotate = ref(0);
const position = ref({ x: 0, y: 0 });
const isDragging = ref(false);
const dragStart = ref({ x: 0, y: 0 });

const MIN_SCALE = 0.1;
const MAX_SCALE = 10;
const SCALE_STEP = 0.5;

const currentSrc = computed(() => images.value[currentIndex.value] ?? "");
const hasPrev = computed(() => currentIndex.value > 0);
const hasNext = computed(() => currentIndex.value < images.value.length - 1);
const previewStyle = computed(() => ({
    transform: `translate3d(${position.value.x}px, ${position.value.y}px, 0) scale(${scale.value}) rotate(${rotate.value}deg)`,
    transition: isDragging.value ? "none" : "transform 0.3s ease",
}));

const collectImages = () => {
    if (!contentRef.value) return;
    const imgEls = contentRef.value.querySelectorAll("img");
    const srcs: string[] = [];
    imgEls.forEach((img) => {
        img.style.cursor = "pointer";
        img.onerror = () => {
            img.classList.add("mv-img-broken");
            img.alt = img.alt || "图片加载失败";
        };
        const src = img.getAttribute("src") || "";
        if (src.startsWith("http://") && window.location.protocol === "https:") {
            img.src = src.replace("http://", "https://");
        }
        if (img.src) srcs.push(img.src);
        img.onclick = () => openPreview(img.src);
    });
    images.value = srcs;
};

const openPreview = (src: string) => {
    const idx = images.value.indexOf(src);
    if (idx === -1) return;
    currentIndex.value = idx;
    resetTransform();
    previewVisible.value = true;
    document.body.style.overflow = "hidden";
};

const closePreview = () => {
    previewVisible.value = false;
    document.body.style.overflow = "";
};

const resetTransform = () => {
    scale.value = 1;
    rotate.value = 0;
    position.value = { x: 0, y: 0 };
};

const zoomIn = () => { scale.value = Math.min(MAX_SCALE, scale.value + SCALE_STEP); };
const zoomOut = () => { scale.value = Math.max(MIN_SCALE, scale.value - SCALE_STEP); };
const rotateRight = () => { rotate.value += 90; };
const rotateLeft = () => { rotate.value -= 90; };
const resetScale = () => { resetTransform(); };
const prevImage = () => { if (hasPrev.value) { currentIndex.value--; resetTransform(); } };
const nextImage = () => { if (hasNext.value) { currentIndex.value++; resetTransform(); } };

const downloadImage = () => {
    if (!currentSrc.value) return;
    const a = document.createElement("a");
    a.href = currentSrc.value;
    a.download = "image";
    a.target = "_blank";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
};

const handleWheel = (e: WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -SCALE_STEP : SCALE_STEP;
    scale.value = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale.value + delta));
};

const handleMouseDown = (e: MouseEvent) => {
    if (e.button !== 0) return;
    isDragging.value = true;
    dragStart.value = { x: e.clientX - position.value.x, y: e.clientY - position.value.y };
};
const handleMouseMove = (e: MouseEvent) => {
    if (!isDragging.value) return;
    position.value = { x: e.clientX - dragStart.value.x, y: e.clientY - dragStart.value.y };
};
const handleMouseUp = () => { isDragging.value = false; };

const handleKeydown = (e: KeyboardEvent) => {
    if (!previewVisible.value) return;
    if (e.key === "Escape") closePreview();
    else if (e.key === "ArrowLeft") prevImage();
    else if (e.key === "ArrowRight") nextImage();
};

const teleportTo = computed(() => getVortTeleportTo());

watch(html, () => { nextTick(collectImages); });
onMounted(() => {
    nextTick(collectImages);
    document.addEventListener("keydown", handleKeydown);
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
});
onUnmounted(() => {
    document.removeEventListener("keydown", handleKeydown);
    document.removeEventListener("mousemove", handleMouseMove);
    document.removeEventListener("mouseup", handleMouseUp);
    document.body.style.overflow = "";
});
</script>

<template>
    <div ref="contentRef" class="markdown-view" v-html="html" />

    <Teleport :to="teleportTo">
        <div v-if="previewVisible" class="mv-preview-root">
            <div class="mv-preview-mask" @click="closePreview" />
            <div class="mv-preview-wrap" @wheel="handleWheel">
                <div class="mv-preview-toolbar">
                    <span v-if="images.length > 1" class="mv-preview-counter">{{ currentIndex + 1 }} / {{ images.length }}</span>
                    <button :disabled="scale <= MIN_SCALE" @click="zoomOut"><ZoomOut :size="20" /></button>
                    <button :disabled="scale >= MAX_SCALE" @click="zoomIn"><ZoomIn :size="20" /></button>
                    <button @click="resetScale"><Maximize :size="20" /></button>
                    <button @click="rotateLeft"><RotateCcw :size="20" /></button>
                    <button @click="rotateRight"><RotateCw :size="20" /></button>
                    <button @click="downloadImage"><Download :size="20" /></button>
                    <button @click="closePreview"><X :size="20" /></button>
                </div>
                <button v-if="images.length > 1" class="mv-preview-nav mv-preview-nav-left" :disabled="!hasPrev" @click="prevImage"><ChevronLeft :size="24" /></button>
                <button v-if="images.length > 1" class="mv-preview-nav mv-preview-nav-right" :disabled="!hasNext" @click="nextImage"><ChevronRight :size="24" /></button>
                <div class="mv-preview-body" @click.self="closePreview">
                    <img
                        :key="currentSrc"
                        :src="currentSrc"
                        class="mv-preview-img"
                        :class="{ 'mv-preview-img-dragging': isDragging }"
                        :style="previewStyle"
                        @mousedown="handleMouseDown"
                    />
                </div>
            </div>
        </div>
    </Teleport>
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
.markdown-view img { max-width: 100%; max-height: 600px; object-fit: contain; border-radius: 4px; cursor: pointer; }
.markdown-view img.mv-img-broken {
    display: inline-block; min-height: 40px; min-width: 120px; padding: 8px 12px;
    background: #f5f5f5; border: 1px dashed #d9d9d9; border-radius: 4px;
    font-size: 12px; color: #999; text-align: center; cursor: default;
}
.markdown-view table { border-collapse: collapse; width: 100%; margin: 0.5em 0; }
.markdown-view th, .markdown-view td { border: 1px solid #e5e5e5; padding: 6px 12px; text-align: left; }
.markdown-view th { background: #fafafa; font-weight: 600; }

.mv-preview-root { position: fixed; inset: 0; z-index: 1080; }
.mv-preview-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.45); z-index: 0; }
.mv-preview-wrap { position: fixed; inset: 0; z-index: 1; display: flex; align-items: center; justify-content: center; }

.mv-preview-toolbar {
    position: fixed; top: 0; left: 0; right: 0; z-index: 10;
    display: flex; justify-content: center; padding: 16px; pointer-events: none;
}
.mv-preview-toolbar > * { pointer-events: auto; }
.mv-preview-toolbar {
    gap: 0;
}
.mv-preview-toolbar button,
.mv-preview-toolbar span {
    display: inline-flex; align-items: center; justify-content: center;
    height: 36px; padding: 0 8px; border: none; border-radius: 0;
    background: rgba(0,0,0,0.1); backdrop-filter: blur(8px);
    color: rgba(255,255,255,0.85); cursor: pointer; transition: all 0.2s;
}
.mv-preview-toolbar > :first-child { border-radius: 100px 0 0 100px; padding-left: 16px; }
.mv-preview-toolbar > :last-child  { border-radius: 0 100px 100px 0; padding-right: 16px; }
.mv-preview-toolbar button:hover { background: rgba(255,255,255,0.15); color: #fff; }
.mv-preview-toolbar button:disabled { color: rgba(255,255,255,0.25); cursor: not-allowed; }
.mv-preview-counter { font-size: 14px; padding: 0 12px !important; cursor: default; }

.mv-preview-nav {
    position: fixed; top: 50%; transform: translateY(-50%); z-index: 10;
    display: flex; align-items: center; justify-content: center;
    width: 44px; height: 44px; padding: 0; border: none; border-radius: 50%;
    background: rgba(0,0,0,0.1); backdrop-filter: blur(8px);
    color: rgba(255,255,255,0.85); cursor: pointer; transition: all 0.2s;
}
.mv-preview-nav:hover { background: rgba(0,0,0,0.2); color: #fff; }
.mv-preview-nav:disabled { color: rgba(255,255,255,0.25); cursor: not-allowed; }
.mv-preview-nav-left  { left: 16px; }
.mv-preview-nav-right { right: 16px; }

.mv-preview-body { display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; }
.mv-preview-img { max-width: 100%; max-height: 100%; cursor: grab; user-select: none; -webkit-user-drag: none; will-change: transform; }
.mv-preview-img-dragging { cursor: grabbing; }
</style>
