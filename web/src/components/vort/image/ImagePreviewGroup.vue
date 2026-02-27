<script setup lang="ts">
import { ref, provide, computed, onMounted, onUnmounted, nextTick } from "vue";
import { X, ZoomIn, ZoomOut, RotateCw, RotateCcw, Maximize, Download, ChevronLeft, ChevronRight } from "lucide-vue-next";
import { getVortTeleportTo } from "@/components/vort/composables";

defineOptions({ name: "VortImagePreviewGroup" });

/**
 * Vort ImagePreviewGroup - 多图预览组
 *
 * 支持多张图片预览时的左右切换
 */

interface ImageItem {
    src: string;
    alt?: string;
}

interface Props {
    /** 点击遮罩是否可关闭预览 */
    maskClosable?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    maskClosable: true
});

// 注册的图片列表
const images = ref<ImageItem[]>([]);
// 当前预览索引
const currentIndex = ref(0);
// 预览可见状态
const previewVisible = ref(false);
// 控制 Teleport 是否渲染，避免产生 <!--v-if--> 注释
const shouldRenderTeleport = ref(false);
// 动画状态
const animationState = ref<"" | "enter" | "leave">("");
// transform-origin
const transformOriginStyle = ref("");
const teleportTo = computed(() => getVortTeleportTo());

// 预览状态
const scale = ref(1);
const rotate = ref(0);
const position = ref({ x: 0, y: 0 });
const isDragging = ref(false);
const dragStart = ref({ x: 0, y: 0 });
const isAnimating = ref(false);

// 惯性动画相关
const velocity = ref({ x: 0, y: 0 });
const lastMousePos = ref({ x: 0, y: 0 });
const lastMoveTime = ref(0);
let animationFrameId: number | null = null;

// 缩放配置
const MIN_SCALE = 0.1;
const MAX_SCALE = 10;
const SCALE_STEP = 0.5;
const DAMPING = 0.92;
const MIN_VELOCITY = 0.5;

// 全局鼠标位置
let mousePosition: { x: number; y: number } | null = null;

const getClickPosition = (e: MouseEvent) => {
    mousePosition = { x: e.clientX, y: e.clientY };
    setTimeout(() => {
        mousePosition = null;
    }, 100);
};

if (typeof window !== "undefined") {
    document.documentElement.addEventListener("click", getClickPosition, true);
}

// 当前预览图片
const currentImage = computed(() => images.value[currentIndex.value]);

// 是否有上一张
const hasPrev = computed(() => currentIndex.value > 0);

// 是否有下一张
const hasNext = computed(() => currentIndex.value < images.value.length - 1);

// 预览图片变换样式
const previewImageStyle = computed(() => {
    const noTransition = isDragging.value || isAnimating.value;
    return {
        transform: `translate3d(${position.value.x}px, ${position.value.y}px, 0) scale(${scale.value}) rotate(${rotate.value}deg)`,
        transition: noTransition ? "none" : "transform 0.3s cubic-bezier(0.215, 0.61, 0.355, 1)"
    };
});

// 注册图片
const registerImage = (item: ImageItem) => {
    const index = images.value.findIndex((img) => img.src === item.src);
    if (index === -1) {
        images.value.push(item);
    }
    return images.value.length - 1;
};

// 注销图片
const unregisterImage = (src: string) => {
    const index = images.value.findIndex((img) => img.src === src);
    if (index !== -1) {
        images.value.splice(index, 1);
    }
};

// 打开预览
const openPreview = (src: string) => {
    const index = images.value.findIndex((img) => img.src === src);
    if (index !== -1) {
        currentIndex.value = index;
        shouldRenderTeleport.value = true; // 先渲染 Teleport
        previewVisible.value = true;
        document.body.style.overflow = "hidden";

        nextTick(() => {
            requestAnimationFrame(() => {
                if (mousePosition) {
                    transformOriginStyle.value = `${mousePosition.x}px ${mousePosition.y}px`;
                } else {
                    transformOriginStyle.value = "center center";
                }
                animationState.value = "enter";
            });
        });
    }
};

// 关闭预览
const closePreview = () => {
    animationState.value = "leave";
};

// 动画结束回调
const handleAnimationEnd = () => {
    if (animationState.value === "leave") {
        previewVisible.value = false;
        animationState.value = "";
        document.body.style.overflow = "";
        resetPreview();
        shouldRenderTeleport.value = false; // 动画结束后移除 Teleport
    } else if (animationState.value === "enter") {
        animationState.value = "";
    }
};

// 重置预览状态
const resetPreview = () => {
    stopInertia();
    scale.value = 1;
    rotate.value = 0;
    position.value = { x: 0, y: 0 };
    velocity.value = { x: 0, y: 0 };
};

// 切换到上一张
const prevImage = () => {
    if (hasPrev.value) {
        currentIndex.value--;
        resetPreview();
    }
};

// 切换到下一张
const nextImage = () => {
    if (hasNext.value) {
        currentIndex.value++;
        resetPreview();
    }
};

// 放大
const zoomIn = () => {
    scale.value = Math.min(MAX_SCALE, scale.value + SCALE_STEP);
};

// 缩小
const zoomOut = () => {
    scale.value = Math.max(MIN_SCALE, scale.value - SCALE_STEP);
};

// 顺时针旋转
const rotateRight = () => {
    rotate.value += 90;
};

// 逆时针旋转
const rotateLeft = () => {
    rotate.value -= 90;
};

// 1:1 显示
const resetScale = () => {
    scale.value = 1;
    position.value = { x: 0, y: 0 };
};

// 下载图片
const downloadImage = () => {
    if (!currentImage.value) return;
    const link = document.createElement("a");
    link.href = currentImage.value.src;
    link.download = currentImage.value.alt || "image";
    link.target = "_blank";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};

// 鼠标滚轮缩放
const handleWheel = (e: WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -SCALE_STEP : SCALE_STEP;
    scale.value = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale.value + delta));
};

// 停止惯性动画
const stopInertia = () => {
    if (animationFrameId !== null) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
    isAnimating.value = false;
};

// 惯性动画
const startInertia = () => {
    if (Math.abs(velocity.value.x) < MIN_VELOCITY && Math.abs(velocity.value.y) < MIN_VELOCITY) {
        isAnimating.value = false;
        return;
    }

    isAnimating.value = true;

    const animate = () => {
        velocity.value.x *= DAMPING;
        velocity.value.y *= DAMPING;
        position.value = {
            x: position.value.x + velocity.value.x,
            y: position.value.y + velocity.value.y
        };

        if (Math.abs(velocity.value.x) > MIN_VELOCITY || Math.abs(velocity.value.y) > MIN_VELOCITY) {
            animationFrameId = requestAnimationFrame(animate);
        } else {
            isAnimating.value = false;
        }
    };

    animationFrameId = requestAnimationFrame(animate);
};

// 拖拽开始
const handleMouseDown = (e: MouseEvent) => {
    if (e.button !== 0) return;
    stopInertia();
    isDragging.value = true;
    dragStart.value = {
        x: e.clientX - position.value.x,
        y: e.clientY - position.value.y
    };
    lastMousePos.value = { x: e.clientX, y: e.clientY };
    lastMoveTime.value = Date.now();
    velocity.value = { x: 0, y: 0 };
};

// 拖拽移动
const handleMouseMove = (e: MouseEvent) => {
    if (!isDragging.value) return;
    const now = Date.now();
    const dt = now - lastMoveTime.value;
    const newX = e.clientX - dragStart.value.x;
    const newY = e.clientY - dragStart.value.y;

    if (dt > 0) {
        const factor = 16 / dt;
        velocity.value = {
            x: (e.clientX - lastMousePos.value.x) * factor,
            y: (e.clientY - lastMousePos.value.y) * factor
        };
    }

    position.value = { x: newX, y: newY };
    lastMousePos.value = { x: e.clientX, y: e.clientY };
    lastMoveTime.value = now;
};

// 拖拽结束
const handleMouseUp = () => {
    if (!isDragging.value) return;
    isDragging.value = false;
    startInertia();
};

// 键盘事件
const handleKeydown = (e: KeyboardEvent) => {
    if (!previewVisible.value) return;

    switch (e.key) {
        case "Escape":
            closePreview();
            break;
        case "ArrowLeft":
            prevImage();
            break;
        case "ArrowRight":
            nextImage();
            break;
    }
};

// 点击遮罩关闭
const handleMaskClick = () => {
    if (props.maskClosable) {
        closePreview();
    }
};

// Provide 给子组件
provide("imagePreviewGroup", {
    registerImage,
    unregisterImage,
    openPreview
});

onMounted(() => {
    document.addEventListener("keydown", handleKeydown);
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
});

onUnmounted(() => {
    document.removeEventListener("keydown", handleKeydown);
    document.removeEventListener("mousemove", handleMouseMove);
    document.removeEventListener("mouseup", handleMouseUp);
    document.body.style.overflow = "";
    stopInertia();
});
</script>

<template>
    <div class="vort-image-preview-group">
        <slot />

        <!-- 预览弹层 -->
        <Teleport v-if="shouldRenderTeleport" :to="teleportTo">
            <div v-if="previewVisible" class="vort-image-preview-root">
                <!-- 遮罩层 -->
                <Transition name="vort-mask">
                    <div v-show="animationState !== 'leave'" class="vort-image-preview-mask" />
                </Transition>

                <!-- 预览容器 -->
                <div
                    class="vort-image-preview-wrap"
                    :data-state="animationState"
                    :style="{ transformOrigin: transformOriginStyle }"
                    @wheel="handleWheel"
                    @animationend="handleAnimationEnd"
                >
                    <!-- 工具栏 -->
                    <div class="vort-image-preview-operations">
                        <div class="vort-image-preview-operations-wrapper">
                            <!-- 计数器 -->
                            <span v-if="images.length > 1" class="vort-image-preview-counter"> {{ currentIndex + 1 }} / {{ images.length }} </span>
                            <!-- 缩小 -->
                            <button class="vort-image-preview-operation" :disabled="scale <= MIN_SCALE" @click="zoomOut">
                                <ZoomOut class="vort-image-preview-icon" />
                            </button>
                            <!-- 放大 -->
                            <button class="vort-image-preview-operation" :disabled="scale >= MAX_SCALE" @click="zoomIn">
                                <ZoomIn class="vort-image-preview-icon" />
                            </button>
                            <!-- 1:1 -->
                            <button class="vort-image-preview-operation" @click="resetScale">
                                <Maximize class="vort-image-preview-icon" />
                            </button>
                            <!-- 逆时针旋转 -->
                            <button class="vort-image-preview-operation" @click="rotateLeft">
                                <RotateCcw class="vort-image-preview-icon" />
                            </button>
                            <!-- 顺时针旋转 -->
                            <button class="vort-image-preview-operation" @click="rotateRight">
                                <RotateCw class="vort-image-preview-icon" />
                            </button>
                            <!-- 下载 -->
                            <button class="vort-image-preview-operation" @click="downloadImage">
                                <Download class="vort-image-preview-icon" />
                            </button>
                            <!-- 关闭 -->
                            <button class="vort-image-preview-operation" @click="closePreview">
                                <X class="vort-image-preview-icon" />
                            </button>
                        </div>
                    </div>

                    <!-- 左箭头 -->
                    <button v-if="images.length > 1" class="vort-image-preview-switch vort-image-preview-switch-left" :disabled="!hasPrev" @click="prevImage">
                        <ChevronLeft class="vort-image-preview-switch-icon" />
                    </button>

                    <!-- 右箭头 -->
                    <button v-if="images.length > 1" class="vort-image-preview-switch vort-image-preview-switch-right" :disabled="!hasNext" @click="nextImage">
                        <ChevronRight class="vort-image-preview-switch-icon" />
                    </button>

                    <!-- 预览图片 -->
                    <div class="vort-image-preview-body" @click.self="handleMaskClick">
                        <img
                            v-if="currentImage"
                            :key="currentImage.src"
                            class="vort-image-preview-img"
                            :class="{ 'vort-image-preview-img-dragging': isDragging }"
                            :src="currentImage.src"
                            :alt="currentImage.alt"
                            :style="previewImageStyle"
                            @mousedown="handleMouseDown"
                        />
                    </div>
                </div>
            </div>
        </Teleport>
    </div>
</template>

<style scoped>
.vort-image-preview-group {
    display: contents;
}

/* ===== 预览弹层 ===== */
.vort-image-preview-root {
    position: fixed;
    inset: 0;
    z-index: 1080;
}

/* 遮罩层 */
.vort-image-preview-mask {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 0;
}

/* 遮罩动画 */
.vort-mask-enter-active,
.vort-mask-leave-active {
    transition: opacity 0.3s;
}

.vort-mask-enter-from,
.vort-mask-leave-to {
    opacity: 0;
}

/* 预览容器 */
.vort-image-preview-wrap {
    position: fixed;
    inset: 0;
    z-index: 1;
    outline: 0;
    display: flex;
    align-items: center;
    justify-content: center;
}

/* 缩放动画 */
.vort-image-preview-wrap[data-state="enter"] {
    animation: vortImageZoomIn 0.3s cubic-bezier(0.08, 0.82, 0.17, 1) forwards;
}

.vort-image-preview-wrap[data-state="leave"] {
    animation: vortImageZoomOut 0.2s cubic-bezier(0.78, 0.14, 0.15, 0.86) forwards;
}

@keyframes vortImageZoomIn {
    0% {
        opacity: 0;
        transform: scale(0.2);
    }
    100% {
        opacity: 1;
        transform: scale(1);
    }
}

@keyframes vortImageZoomOut {
    0% {
        opacity: 1;
        transform: scale(1);
    }
    100% {
        opacity: 0;
        transform: scale(0.2);
    }
}

/* 工具栏 */
.vort-image-preview-operations {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 10;
    display: flex;
    justify-content: center;
    padding: 16px;
    pointer-events: none;
}

.vort-image-preview-operations-wrapper {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: rgba(0, 0, 0, 0.1);
    backdrop-filter: blur(8px);
    border-radius: 100px;
    pointer-events: auto;
}

.vort-image-preview-counter {
    padding: 0 12px;
    font-size: 14px;
    color: rgba(255, 255, 255, 0.85);
}

.vort-image-preview-operation {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    padding: 0;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: rgba(255, 255, 255, 0.85);
    cursor: pointer;
    transition: all 0.2s;
}

.vort-image-preview-operation:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
}

.vort-image-preview-operation:active {
    background: rgba(255, 255, 255, 0.15);
}

.vort-image-preview-operation:disabled {
    color: rgba(255, 255, 255, 0.25);
    cursor: not-allowed;
}

.vort-image-preview-operation:disabled:hover {
    background: transparent;
}

.vort-image-preview-icon {
    width: 20px;
    height: 20px;
}

/* 切换按钮 */
.vort-image-preview-switch {
    position: fixed;
    top: 50%;
    transform: translateY(-50%);
    z-index: 10;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    padding: 0;
    border: none;
    border-radius: 50%;
    background: rgba(0, 0, 0, 0.1);
    backdrop-filter: blur(8px);
    color: rgba(255, 255, 255, 0.85);
    cursor: pointer;
    transition: all 0.2s;
}

.vort-image-preview-switch:hover {
    background: rgba(0, 0, 0, 0.2);
    color: #fff;
}

.vort-image-preview-switch:active {
    background: rgba(0, 0, 0, 0.3);
}

.vort-image-preview-switch:disabled {
    color: rgba(255, 255, 255, 0.25);
    cursor: not-allowed;
}

.vort-image-preview-switch:disabled:hover {
    background: rgba(0, 0, 0, 0.1);
}

.vort-image-preview-switch-left {
    left: 16px;
}

.vort-image-preview-switch-right {
    right: 16px;
}

.vort-image-preview-switch-icon {
    width: 24px;
    height: 24px;
}

/* 预览图片区域 */
.vort-image-preview-body {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
}

.vort-image-preview-img {
    max-width: 100%;
    max-height: 100%;
    cursor: grab;
    user-select: none;
    -webkit-user-drag: none;
    will-change: transform;
    backface-visibility: hidden;
    -webkit-backface-visibility: hidden;
    transform-style: preserve-3d;
}

.vort-image-preview-img-dragging {
    cursor: grabbing;
}
</style>
