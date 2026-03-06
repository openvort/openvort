<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick, inject } from "vue";
import { X, ZoomIn, ZoomOut, RotateCw, RotateCcw, Maximize, Download } from "lucide-vue-next";
import { ImageOutlined, ImageBrokenOutlined } from "@/components/vort/icons";
import { getVortTeleportTo } from "@/components/vort/composables";

defineOptions({ name: "VortImage" });

/** Vort Image - 图片组件 */

interface PreviewConfig {
    /** 是否显示预览 */
    visible?: boolean;
    /** 预览图片地址（默认使用 src） */
    src?: string;
    /** 关闭回调 */
    onVisibleChange?: (visible: boolean) => void;
}

interface Props {
    /** 图片地址 */
    src?: string;
    /** 替代文本 */
    alt?: string;
    /** 图片宽度 */
    width?: number | string;
    /** 图片高度 */
    height?: number | string;
    /** 图片填充模式 */
    fit?: "fill" | "contain" | "cover" | "none" | "scale-down";
    /** 是否支持预览，或预览配置 */
    preview?: boolean | PreviewConfig;
    /** 加载失败显示的图片 */
    fallback?: string;
    /** 加载中显示的内容 */
    placeholder?: boolean;
    /** 点击遮罩是否可关闭预览 */
    maskClosable?: boolean;
    /** 自定义类名 */
    class?: string;
    /** 自定义样式 */
    style?: string | Record<string, string>;
}

const props = withDefaults(defineProps<Props>(), {
    src: "",
    alt: "",
    fit: "cover",
    preview: true,
    placeholder: false,
    maskClosable: true
});

const emit = defineEmits<{
    /** 图片加载完成 */
    load: [event: Event];
    /** 图片加载失败 */
    error: [event: Event];
    /** 预览可见状态变化 */
    previewVisibleChange: [visible: boolean];
}>();

// 状态
const loading = ref(true);
const error = ref(false);
const fallbackLoading = ref(false);
const fallbackError = ref(false);
const previewVisible = ref(false);
const shouldRenderTeleport = ref(false); // 控制 Teleport 是否渲染，避免产生 <!--v-if--> 注释
const animationState = ref<"" | "enter" | "leave">("");
const previewRef = ref<HTMLDivElement | null>(null);
const imageRef = ref<HTMLImageElement | null>(null);
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

// 阻尼系数（越小阻力越大，减速越快）
const DAMPING = 0.92;
// 最小速度阈值
const MIN_VELOCITY = 0.5;

// 注入预览组（如果存在）
interface ImagePreviewGroupContext {
    registerImage: (item: { src: string; alt?: string }) => number;
    unregisterImage: (src: string) => void;
    openPreview: (src: string) => void;
}
const previewGroup = inject<ImagePreviewGroupContext | null>("imagePreviewGroup", null);

// 是否在预览组内
const isInGroup = computed(() => previewGroup !== null);

// 全局鼠标位置追踪
let mousePosition: { x: number; y: number } | null = null;

// 获取点击位置
const getClickPosition = (e: MouseEvent) => {
    mousePosition = {
        x: e.clientX,
        y: e.clientY
    };
    // 100ms 后清除，避免影响其他组件
    setTimeout(() => {
        mousePosition = null;
    }, 100);
};

// 只在 document 上监听 click 获取位置
if (typeof window !== "undefined") {
    document.documentElement.addEventListener("click", getClickPosition, true);
}

// 计算 transform-origin（基于点击位置）
const setTransformOrigin = () => {
    if (!mousePosition) {
        // 如果没有鼠标位置，使用图片中心
        if (imageRef.value) {
            const rect = imageRef.value.getBoundingClientRect();
            mousePosition = {
                x: rect.left + rect.width / 2,
                y: rect.top + rect.height / 2
            };
        } else {
            transformOriginStyle.value = "center center";
            return;
        }
    }

    // 使用视口坐标作为 transform-origin
    transformOriginStyle.value = `${mousePosition.x}px ${mousePosition.y}px`;
};

// 是否启用预览
const isPreviewEnabled = computed(() => {
    if (typeof props.preview === "boolean") {
        return props.preview;
    }
    return Boolean(props.preview) !== false;
});

// 预览图片地址
const previewSrc = computed(() => {
    if (typeof props.preview === "object" && props.preview.src) {
        return props.preview.src;
    }
    // 如果原图失败且有 fallback，使用 fallback
    if (error.value && props.fallback && !fallbackError.value) {
        return props.fallback;
    }
    return props.src;
});

// 图片尺寸样式
const imageStyle = computed(() => {
    const style: Record<string, string> = {};
    if (props.width) {
        style.width = typeof props.width === "number" ? `${props.width}px` : props.width;
    }
    if (props.height) {
        style.height = typeof props.height === "number" ? `${props.height}px` : props.height;
    }
    // 合并外部传入的 style
    if (props.style) {
        if (typeof props.style === "string") {
            // 解析字符串样式
            props.style.split(";").forEach((item) => {
                const [key, value] = item.split(":").map((s) => s.trim());
                if (key && value) {
                    // 将 kebab-case 转为 camelCase
                    const camelKey = key.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
                    style[camelKey] = value;
                }
            });
        } else {
            Object.assign(style, props.style);
        }
    }
    return style;
});

// 预览图片变换样式
const previewImageStyle = computed(() => {
    // 拖动中或惯性动画中不使用过渡
    const noTransition = isDragging.value || isAnimating.value;
    return {
        transform: `translate3d(${position.value.x}px, ${position.value.y}px, 0) scale(${scale.value}) rotate(${rotate.value}deg)`,
        transition: noTransition ? "none" : "transform 0.3s cubic-bezier(0.215, 0.61, 0.355, 1)"
    };
});

// 图片加载完成
const handleLoad = (e: Event) => {
    loading.value = false;
    error.value = false;
    emit("load", e);
};

// 图片加载失败
const handleError = (e: Event) => {
    loading.value = false;
    error.value = true;
    // 如果有 fallback，开始加载 fallback
    if (props.fallback) {
        fallbackLoading.value = true;
    }
    emit("error", e);
};

// Fallback 图片加载完成
const handleFallbackLoad = () => {
    fallbackLoading.value = false;
    fallbackError.value = false;
};

// Fallback 图片加载失败
const handleFallbackError = () => {
    fallbackLoading.value = false;
    fallbackError.value = true;
};

// 打开预览
const openPreview = () => {
    if (!isPreviewEnabled.value) return;
    // 如果有错误且没有可用的 fallback，不打开预览
    if (error.value && (!props.fallback || fallbackError.value)) return;

    // 如果在预览组内，委托给组处理
    if (isInGroup.value && previewGroup) {
        const srcToPreview = error.value && props.fallback ? props.fallback : props.src;
        previewGroup.openPreview(srcToPreview);
        return;
    }

    shouldRenderTeleport.value = true; // 先渲染 Teleport
    previewVisible.value = true;
    document.body.style.overflow = "hidden";
    emit("previewVisibleChange", true);

    nextTick(() => {
        requestAnimationFrame(() => {
            setTransformOrigin();
            animationState.value = "enter";
        });
    });
};

// 关闭预览
const closePreview = () => {
    animationState.value = "leave";
    emit("previewVisibleChange", false);
};

// 动画结束回调
const handleAnimationEnd = () => {
    if (animationState.value === "leave") {
        previewVisible.value = false;
        animationState.value = "";
        document.body.style.overflow = "";
        // 重置预览状态
        resetPreview();
        // 移除 Teleport，避免产生 <!--v-if--> 注释
        shouldRenderTeleport.value = false;
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
    const link = document.createElement("a");
    link.href = previewSrc.value;
    link.download = props.alt || "image";
    link.target = "_blank";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};

// 鼠标滚轮缩放
const handleWheel = (e: WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -SCALE_STEP : SCALE_STEP;
    const newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale.value + delta));
    scale.value = newScale;
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
        // 应用阻尼
        velocity.value.x *= DAMPING;
        velocity.value.y *= DAMPING;

        // 更新位置
        position.value = {
            x: position.value.x + velocity.value.x,
            y: position.value.y + velocity.value.y
        };

        // 检查是否需要继续动画
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
    if (e.button !== 0) return; // 只响应左键

    // 停止正在进行的惯性动画
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

    // 计算新位置
    const newX = e.clientX - dragStart.value.x;
    const newY = e.clientY - dragStart.value.y;

    // 计算速度（像素/帧，约16ms）
    if (dt > 0) {
        const factor = 16 / dt; // 归一化到约60fps
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

    // 启动惯性动画
    startInertia();
};

// ESC 键关闭
const handleKeydown = (e: KeyboardEvent) => {
    if (e.key === "Escape" && previewVisible.value) {
        closePreview();
    }
};

// 点击遮罩关闭
const handleMaskClick = () => {
    if (props.maskClosable) {
        closePreview();
    }
};

onMounted(() => {
    document.addEventListener("keydown", handleKeydown);
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    // 向预览组注册
    if (previewGroup && props.src) {
        previewGroup.registerImage({ src: props.src, alt: props.alt });
    }
});

onUnmounted(() => {
    document.removeEventListener("keydown", handleKeydown);
    document.removeEventListener("mousemove", handleMouseMove);
    document.removeEventListener("mouseup", handleMouseUp);
    document.body.style.overflow = "";
    stopInertia();

    // 从预览组注销
    if (previewGroup && props.src) {
        previewGroup.unregisterImage(props.src);
    }
});
</script>

<template>
    <div :class="['vort-image', props.class]" :style="imageStyle">
        <!-- 加载中占位 -->
        <div v-if="(loading || fallbackLoading) && placeholder" class="vort-image-placeholder">
            <ImageOutlined class="vort-image-placeholder-icon" />
        </div>

        <!-- 主图片 -->
        <img
            ref="imageRef"
            v-show="!loading && !error"
            :class="['vort-image-img', { 'vort-image-img-preview': isPreviewEnabled }]"
            :style="{ objectFit: fit }"
            :src="src"
            :alt="alt"
            @load="handleLoad"
            @error="handleError"
            @click="openPreview"
        />

        <!-- Fallback 图片 -->
        <img
            v-if="error && fallback"
            v-show="!fallbackLoading && !fallbackError"
            :class="['vort-image-img', { 'vort-image-img-preview': isPreviewEnabled }]"
            :style="{ objectFit: fit }"
            :src="fallback"
            :alt="alt"
            @load="handleFallbackLoad"
            @error="handleFallbackError"
            @click="openPreview"
        />

        <!-- 错误状态（无 fallback 或 fallback 也失败） -->
        <div v-if="(error && !fallback) || fallbackError" class="vort-image-error">
            <ImageBrokenOutlined class="vort-image-error-icon" />
        </div>

        <!-- 预览弹层 -->
        <Teleport v-if="shouldRenderTeleport" :to="teleportTo">
            <div v-if="previewVisible" class="vort-image-preview-root">
                <!-- 遮罩层 -->
                <Transition name="vort-mask">
                    <div v-show="animationState !== 'leave'" class="vort-image-preview-mask" />
                </Transition>

                <!-- 预览容器 -->
                <div
                    ref="previewRef"
                    class="vort-image-preview-wrap"
                    :data-state="animationState"
                    :style="{ transformOrigin: transformOriginStyle }"
                    @wheel="handleWheel"
                    @animationend="handleAnimationEnd"
                >
                    <!-- 工具栏 -->
                    <div class="vort-image-preview-operations">
                        <div class="vort-image-preview-operations-wrapper">
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

                    <!-- 预览图片 -->
                    <div class="vort-image-preview-body" @click.self="handleMaskClick">
                        <img
                            class="vort-image-preview-img"
                            :class="{ 'vort-image-preview-img-dragging': isDragging }"
                            :src="previewSrc"
                            :alt="alt"
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
.vort-image {
    position: relative;
    display: inline-block;
    overflow: hidden;
}

.vort-image-img {
    display: block;
    width: 100%;
    height: 100%;
}

.vort-image-img-preview {
    cursor: pointer;
}

/* 加载占位 */
.vort-image-placeholder {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.04);
}

.vort-image-placeholder-icon {
    width: 48px;
    height: 48px;
    color: rgba(0, 0, 0, 0.25);
    animation: vort-image-placeholder-pulse 1.5s ease-in-out infinite;
}

@keyframes vort-image-placeholder-pulse {
    0%,
    100% {
        opacity: 1;
    }
    50% {
        opacity: 0.4;
    }
}

/* 错误状态 */
.vort-image-error {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.04);
}

.vort-image-error-icon {
    width: 48px;
    height: 48px;
    max-width: 35%;
    max-height: 35%;
    color: rgba(0, 0, 0, 0.25);
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
    /* GPU 加速，防止残影 */
    will-change: transform;
    backface-visibility: hidden;
    -webkit-backface-visibility: hidden;
    transform-style: preserve-3d;
}

.vort-image-preview-img-dragging {
    cursor: grabbing;
}
</style>
