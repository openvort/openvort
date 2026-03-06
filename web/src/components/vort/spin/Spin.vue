<script setup lang="ts">
import { computed, ref, watch } from "vue";

defineOptions({ name: "VortSpin" });

/** Vort Spin - 加载组件 */

type SpinSize = "large" | "default" | "small";
type SpinIndicator = "dots" | "spinner";

interface Props {
    /** 是否为加载中状态 */
    spinning?: boolean;
    /** 组件大小 */
    size?: SpinSize;
    /** 自定义描述文案 */
    tip?: string;
    /** 延迟显示加载效果的时间（防止闪烁），单位毫秒 */
    delay?: number;
    /** 是否全屏显示 */
    fullscreen?: boolean;
    /** 指示器样式：dots（四点旋转）、spinner（半圆旋转） */
    indicator?: SpinIndicator;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    spinning: true,
    size: "default",
    indicator: "dots",
    delay: 0,
    fullscreen: false
});

const slots = defineSlots<{
    default?(): unknown;
    tip?(): unknown;
    indicator?(): unknown;
}>();

// 延迟显示逻辑
const shouldShowSpinner = ref(props.delay === 0 ? props.spinning : false);
let delayTimer: ReturnType<typeof setTimeout> | null = null;

watch(
    () => props.spinning,
    (newVal) => {
        if (delayTimer) {
            clearTimeout(delayTimer);
            delayTimer = null;
        }

        if (newVal) {
            if (props.delay > 0) {
                delayTimer = setTimeout(() => {
                    shouldShowSpinner.value = true;
                }, props.delay);
            } else {
                shouldShowSpinner.value = true;
            }
        } else {
            shouldShowSpinner.value = false;
        }
    },
    { immediate: true }
);

// 是否是包裹模式（有子内容）
const hasChildren = computed(() => !!slots.default);

// 尺寸配置
const sizeConfig = computed(() => {
    const configs = {
        small: { dotSize: 6, containerSize: 14, spinnerSize: 14 },
        default: { dotSize: 9, containerSize: 22, spinnerSize: 22 },
        large: { dotSize: 12, containerSize: 32, spinnerSize: 32 }
    };
    return configs[props.size];
});

// ========== 类名计算 ==========

const containerClasses = computed(() => {
    const classes = ["vort-spin"];
    if (props.fullscreen) classes.push("vort-spin-fullscreen");
    if (hasChildren.value) classes.push("vort-spin-nested");
    if (props.class) classes.push(props.class);
    return classes;
});

const spinnerClasses = computed(() => {
    const classes = ["vort-spin-spinning", `vort-spin-${props.size}`];
    if (props.tip) classes.push("vort-spin-with-tip");
    return classes;
});
</script>

<template>
    <!-- 全屏模式 -->
    <Transition name="vort-spin-fade">
        <div v-if="fullscreen && shouldShowSpinner" class="vort-spin-fullscreen-container">
            <div :class="spinnerClasses">
                <!-- 自定义指示器插槽 -->
                <slot name="indicator">
                    <!-- Dots 指示器（默认） -->
                    <span v-if="indicator === 'dots'" class="vort-spin-dot vort-spin-dot-spin">
                        <i
                            v-for="n in 4"
                            :key="n"
                            class="vort-spin-dot-item"
                            :style="{
                                width: `${sizeConfig.dotSize}px`,
                                height: `${sizeConfig.dotSize}px`
                            }"
                        />
                    </span>
                    <!-- Spinner 指示器（半圆） -->
                    <span v-else class="vort-spin-spinner">
                        <svg
                            class="vort-spin-spinner-icon"
                            :style="{
                                width: `${sizeConfig.spinnerSize}px`,
                                height: `${sizeConfig.spinnerSize}px`
                            }"
                            viewBox="0 0 1024 1024"
                            fill="currentColor"
                        >
                            <path
                                d="M988 548c-19.9 0-36-16.1-36-36 0-59.4-11.6-117-34.6-171.3a440.45 440.45 0 0 0-94.3-139.9 437.71 437.71 0 0 0-139.9-94.3C629 83.6 571.4 72 512 72c-19.9 0-36-16.1-36-36s16.1-36 36-36c69.1 0 136.2 13.5 199.3 40.3C772.3 66 827 103 876 152.1c49 49 86 103.8 109.7 164.8 26.8 63.1 40.3 130.2 40.3 199.3 0 19.9-16.1 36-36 36z"
                            />
                        </svg>
                    </span>
                </slot>
                <!-- 提示文案 -->
                <div v-if="tip || $slots.tip" class="vort-spin-text">
                    <slot name="tip">{{ tip }}</slot>
                </div>
            </div>
        </div>
    </Transition>

    <!-- 嵌套模式（包裹内容） -->
    <div v-if="hasChildren && !(fullscreen && shouldShowSpinner)" :class="containerClasses">
        <Transition name="vort-spin-fade">
            <div v-if="shouldShowSpinner" class="vort-spin-nested-loading">
                <div :class="spinnerClasses">
                    <slot name="indicator">
                        <span v-if="indicator === 'dots'" class="vort-spin-dot vort-spin-dot-spin">
                            <i
                                v-for="n in 4"
                                :key="n"
                                class="vort-spin-dot-item"
                                :style="{
                                    width: `${sizeConfig.dotSize}px`,
                                    height: `${sizeConfig.dotSize}px`
                                }"
                            />
                        </span>
                        <span v-else class="vort-spin-spinner">
                            <svg
                                class="vort-spin-spinner-icon"
                                :style="{
                                    width: `${sizeConfig.spinnerSize}px`,
                                    height: `${sizeConfig.spinnerSize}px`
                                }"
                                viewBox="0 0 1024 1024"
                                fill="currentColor"
                            >
                                <path
                                    d="M988 548c-19.9 0-36-16.1-36-36 0-59.4-11.6-117-34.6-171.3a440.45 440.45 0 0 0-94.3-139.9 437.71 437.71 0 0 0-139.9-94.3C629 83.6 571.4 72 512 72c-19.9 0-36-16.1-36-36s16.1-36 36-36c69.1 0 136.2 13.5 199.3 40.3C772.3 66 827 103 876 152.1c49 49 86 103.8 109.7 164.8 26.8 63.1 40.3 130.2 40.3 199.3 0 19.9-16.1 36-36 36z"
                                />
                            </svg>
                        </span>
                    </slot>
                    <div v-if="tip || $slots.tip" class="vort-spin-text">
                        <slot name="tip">{{ tip }}</slot>
                    </div>
                </div>
            </div>
        </Transition>
        <div class="vort-spin-container" :class="{ 'vort-spin-blur': shouldShowSpinner }">
            <slot />
        </div>
    </div>

    <!-- 简单模式（无子内容） -->
    <Transition name="vort-spin-fade">
        <div v-if="shouldShowSpinner && !hasChildren && !fullscreen" :class="containerClasses">
            <div :class="spinnerClasses">
                <slot name="indicator">
                    <span v-if="indicator === 'dots'" class="vort-spin-dot vort-spin-dot-spin">
                        <i
                            v-for="n in 4"
                            :key="n"
                            class="vort-spin-dot-item"
                            :style="{
                                width: `${sizeConfig.dotSize}px`,
                                height: `${sizeConfig.dotSize}px`
                            }"
                        />
                    </span>
                    <span v-else class="vort-spin-spinner">
                        <svg
                            class="vort-spin-spinner-icon"
                            :style="{
                                width: `${sizeConfig.spinnerSize}px`,
                                height: `${sizeConfig.spinnerSize}px`
                            }"
                            viewBox="0 0 1024 1024"
                            fill="currentColor"
                        >
                            <path
                                d="M988 548c-19.9 0-36-16.1-36-36 0-59.4-11.6-117-34.6-171.3a440.45 440.45 0 0 0-94.3-139.9 437.71 437.71 0 0 0-139.9-94.3C629 83.6 571.4 72 512 72c-19.9 0-36-16.1-36-36s16.1-36 36-36c69.1 0 136.2 13.5 199.3 40.3C772.3 66 827 103 876 152.1c49 49 86 103.8 109.7 164.8 26.8 63.1 40.3 130.2 40.3 199.3 0 19.9-16.1 36-36 36z"
                            />
                        </svg>
                    </span>
                </slot>
                <div v-if="tip || $slots.tip" class="vort-spin-text">
                    <slot name="tip">{{ tip }}</slot>
                </div>
            </div>
        </div>
    </Transition>
</template>

<style scoped>
/* 基础容器 */
.vort-spin {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
}

/* 嵌套模式 */
.vort-spin-nested {
    display: block;
    position: relative;
}

.vort-spin-nested-loading {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.65);
    z-index: 10;
    transition: all var(--vort-duration-slow, 300ms);
}

.vort-spin-container {
    transition: opacity var(--vort-duration-slow, 300ms);
}

.vort-spin-blur {
    user-select: none;
    pointer-events: none;
    opacity: 0.5;
    filter: blur(0.5px);
}

/* 加载器 */
.vort-spin-spinning {
    display: inline-flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
}

/* 四点指示器 - Ant Design 默认样式 */
.vort-spin-dot {
    position: relative;
    display: inline-block;
    transform: rotate(45deg);
    animation: vort-spin-rotate 1.2s infinite linear;
}

.vort-spin-dot-item {
    position: absolute;
    display: block;
    background-color: var(--vort-primary, #1456f0);
    border-radius: 100%;
    transform: scale(0.75);
    transform-origin: 50% 50%;
    opacity: 0.3;
    animation: vort-spin-dot-move 1s infinite linear alternate;
}

/* 四个点的定位 */
.vort-spin-dot-item:nth-child(1) {
    top: 0;
    left: 0;
}

.vort-spin-dot-item:nth-child(2) {
    top: 0;
    right: 0;
    animation-delay: 0.4s;
}

.vort-spin-dot-item:nth-child(3) {
    right: 0;
    bottom: 0;
    animation-delay: 0.8s;
}

.vort-spin-dot-item:nth-child(4) {
    bottom: 0;
    left: 0;
    animation-delay: 1.2s;
}

/* 根据尺寸设置点容器大小 */
.vort-spin-small .vort-spin-dot {
    width: 14px;
    height: 14px;
}

.vort-spin-default .vort-spin-dot {
    width: 22px;
    height: 22px;
}

.vort-spin-large .vort-spin-dot {
    width: 32px;
    height: 32px;
}

/* 半圆指示器 */
.vort-spin-spinner {
    display: inline-flex;
    animation: vort-spin-rotate 1s infinite linear;
    color: var(--vort-primary, #1456f0);
}

.vort-spin-spinner-icon {
    display: block;
}

/* 提示文案 */
.vort-spin-text {
    font-size: var(--vort-font-size-sm, 14px);
    text-align: center;
    color: var(--vort-primary, #1456f0);
}

.vort-spin-small .vort-spin-text {
    font-size: var(--vort-font-size-xs, 12px);
}

.vort-spin-large .vort-spin-text {
    font-size: var(--vort-font-size-md, 16px);
}

/* 全屏模式 */
.vort-spin-fullscreen-container {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.45);
    z-index: 1000;
}

.vort-spin-fullscreen-container .vort-spin-text {
    color: #fff;
}

.vort-spin-fullscreen-container .vort-spin-dot-item {
    background-color: #fff;
}

.vort-spin-fullscreen-container .vort-spin-spinner {
    color: #fff;
}

/* 动画 */
@keyframes vort-spin-rotate {
    to {
        transform: rotate(405deg);
    }
}

@keyframes vort-spin-dot-move {
    to {
        opacity: 1;
    }
}

/* 过渡动画 */
.vort-spin-fade-enter-active,
.vort-spin-fade-leave-active {
    transition: opacity var(--vort-duration-slow, 300ms) var(--vort-ease-in-out, ease-in-out);
}

.vort-spin-fade-enter-from,
.vort-spin-fade-leave-to {
    opacity: 0;
}
</style>
