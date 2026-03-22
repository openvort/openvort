<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { getVortPopupContainer, useFloating, useZIndex } from "@/components/vort/composables";
import { Input } from "@/components/vort/input";
import { Select } from "@/components/vort/select";
import type { SelectOptionType } from "@/components/vort/select";
import { Button } from "@/components/vort/button";

defineOptions({ name: "VortColorPicker" });

// 使用 z-index 上下文，在 Dialog/Drawer 内时自动获得更高的层级
const zIndex = useZIndex("popup");

/** Vort ColorPicker - 颜色选择器组件 */

type ColorFormat = "hex" | "rgb" | "hsl" | "hsb";
type TriggerType = "click" | "hover";

interface ColorPreset {
    label?: string;
    colors: (string | { color: string; percent?: number })[];
    defaultOpen?: boolean;
}

interface Props {
    /** 颜色值（v-model） */
    modelValue?: string;
    /** 默认颜色 */
    defaultValue?: string;
    /** 是否允许清除 */
    allowClear?: boolean;
    /** 箭头是否指向目标元素中心 */
    arrow?: boolean;
    /** 颜色格式 */
    format?: ColorFormat;
    /** 是否禁用 */
    disabled?: boolean;
    /** 取消拾色器聚焦状态的 blur 事件 */
    disabledAlpha?: boolean;
    /** 配置预设颜色 */
    presets?: ColorPreset[];
    /** 触发方式 */
    trigger?: TriggerType;
    /** 菜单渲染父节点。默认渲染到 body 上，如果你遇到菜单滚动定位问题，试试修改为滚动的区域，并相对其定位 */
    getPopupContainer?: () => HTMLElement;
    /** 自定义类名 */
    class?: string;
    /** 触发器尺寸 */
    size?: "large" | "middle" | "small";
    /** 显示颜色清除按钮 */
    showText?: boolean | ((color: string) => string);
    /** 浮层的位置 */
    placement?: "top" | "topLeft" | "topRight" | "bottom" | "bottomLeft" | "bottomRight";
}

const props = withDefaults(defineProps<Props>(), {
    defaultValue: "#00000000",
    format: "hex",
    disabled: false,
    disabledAlpha: false,
    allowClear: false,
    arrow: true,
    trigger: "click",
    placement: "bottomLeft",
    showText: false
});

const emit = defineEmits<{
    "update:modelValue": [value: string];
    change: [value: string, hex: string];
    changeComplete: [value: string];
    clear: [];
}>();

// ==================== 颜色状态 ====================
const hue = ref(215); // 0-360
const saturation = ref(91); // 0-100
const brightness = ref(100); // 0-100 (HSB 的亮度)
const alpha = ref(100); // 0-100

// ==================== 浮层 ====================
const { triggerRef, floatingRef, isOpen, position, triggerHandlers, floatingHandlers, hide } = useFloating({
    placement: props.placement,
    trigger: props.trigger as any,
    disabled: props.disabled,
    gap: props.arrow ? 10 : 4
});

// 控制 Teleport 是否渲染，避免产生 <!--v-if--> 注释
const shouldRenderTeleport = ref(false);

// 监听浮层打开状态
watch(isOpen, (val) => {
    if (val) {
        shouldRenderTeleport.value = true;
    }
});

// Transition 离开动画完成后移除 Teleport
const handleAfterLeave = () => {
    shouldRenderTeleport.value = false;
};

// 面板容器 ref（用于 Select 组件挂载）
const panelRef = ref<HTMLElement>();

// Select 组件的挂载容器获取函数
const getSelectPopupContainer = () => panelRef.value || document.body;

const popupContainer = computed(() => props.getPopupContainer?.() ?? getVortPopupContainer());

// ==================== 颜色转换工具 ====================

// HSB 转 RGB
const hsbToRgb = (h: number, s: number, b: number) => {
    s = s / 100;
    b = b / 100;
    const k = (n: number) => (n + h / 60) % 6;
    const f = (n: number) => b * (1 - s * Math.max(0, Math.min(k(n), 4 - k(n), 1)));
    return {
        r: Math.round(255 * f(5)),
        g: Math.round(255 * f(3)),
        b: Math.round(255 * f(1))
    };
};

// RGB 转 HSB
const rgbToHsb = (r: number, g: number, b: number) => {
    r /= 255;
    g /= 255;
    b /= 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const delta = max - min;

    let h = 0;
    if (delta !== 0) {
        if (max === r) {
            h = 60 * (((g - b) / delta) % 6);
        } else if (max === g) {
            h = 60 * ((b - r) / delta + 2);
        } else {
            h = 60 * ((r - g) / delta + 4);
        }
    }
    if (h < 0) h += 360;

    const s = max === 0 ? 0 : (delta / max) * 100;
    const v = max * 100;

    return { h, s, b: v };
};

// RGB 转 HEX
const rgbToHex = (r: number, g: number, b: number, a?: number) => {
    const hex = `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${b.toString(16).padStart(2, "0")}`;
    if (a !== undefined && a < 100) {
        return (
            hex +
            Math.round((a / 100) * 255)
                .toString(16)
                .padStart(2, "0")
        );
    }
    return hex;
};

// 解析颜色字符串
const parseColor = (color: string) => {
    if (!color) return null;

    // HEX
    if (color.startsWith("#")) {
        const hex = color.slice(1);
        let r = 0,
            g = 0,
            b = 0,
            a = 100;

        if (hex.length === 3) {
            r = parseInt(hex[0]! + hex[0]!, 16);
            g = parseInt(hex[1]! + hex[1]!, 16);
            b = parseInt(hex[2]! + hex[2]!, 16);
        } else if (hex.length === 6) {
            r = parseInt(hex.slice(0, 2), 16);
            g = parseInt(hex.slice(2, 4), 16);
            b = parseInt(hex.slice(4, 6), 16);
        } else if (hex.length === 8) {
            r = parseInt(hex.slice(0, 2), 16);
            g = parseInt(hex.slice(2, 4), 16);
            b = parseInt(hex.slice(4, 6), 16);
            a = Math.round((parseInt(hex.slice(6, 8), 16) / 255) * 100);
        }

        return { r, g, b, a };
    }

    // RGB/RGBA
    const rgbMatch = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
    if (rgbMatch) {
        return {
            r: parseInt(rgbMatch[1]!),
            g: parseInt(rgbMatch[2]!),
            b: parseInt(rgbMatch[3]!),
            a: rgbMatch[4] ? parseFloat(rgbMatch[4]) * 100 : 100
        };
    }

    // HSL/HSLA
    const hslMatch = color.match(/hsla?\((\d+),\s*(\d+)%,\s*(\d+)%(?:,\s*([\d.]+))?\)/);
    if (hslMatch) {
        const h = parseInt(hslMatch[1]!);
        const s = parseInt(hslMatch[2]!) / 100;
        const l = parseInt(hslMatch[3]!) / 100;
        const a = hslMatch[4] ? parseFloat(hslMatch[4]) * 100 : 100;

        // HSL 转 RGB
        const c = (1 - Math.abs(2 * l - 1)) * s;
        const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
        const m = l - c / 2;

        let r = 0,
            g = 0,
            b = 0;
        if (h >= 0 && h < 60) {
            r = c;
            g = x;
            b = 0;
        } else if (h >= 60 && h < 120) {
            r = x;
            g = c;
            b = 0;
        } else if (h >= 120 && h < 180) {
            r = 0;
            g = c;
            b = x;
        } else if (h >= 180 && h < 240) {
            r = 0;
            g = x;
            b = c;
        } else if (h >= 240 && h < 300) {
            r = x;
            g = 0;
            b = c;
        } else if (h >= 300 && h < 360) {
            r = c;
            g = 0;
            b = x;
        }

        return {
            r: Math.round((r + m) * 255),
            g: Math.round((g + m) * 255),
            b: Math.round((b + m) * 255),
            a
        };
    }

    // HSB/HSBA (HSV)
    const hsbMatch = color.match(/hsba?\((\d+),\s*(\d+)%,\s*(\d+)%(?:,\s*([\d.]+))?\)/);
    if (hsbMatch) {
        const h = parseInt(hsbMatch[1]!);
        const s = parseInt(hsbMatch[2]!);
        const b = parseInt(hsbMatch[3]!);
        const a = hsbMatch[4] ? parseFloat(hsbMatch[4]) * 100 : 100;

        // HSB 转 RGB
        const rgb = hsbToRgb(h, s, b);
        return { ...rgb, a };
    }

    return null;
};

// ==================== 当前颜色计算 ====================
const currentRgb = computed(() => hsbToRgb(hue.value, saturation.value, brightness.value));

// ==================== 格式选择 ====================
const formatOptions: SelectOptionType[] = [
    { value: "hex", label: "HEX" },
    { value: "hsb", label: "HSB" },
    { value: "rgb", label: "RGB" },
    { value: "hsl", label: "HSL" }
];

const selectedFormat = ref<ColorFormat>(props.format);

// 监听格式变化
watch(selectedFormat, () => {
    emitChange();
});

// 根据选中的格式计算颜色值
const currentColor = computed(() => {
    const { r, g, b } = currentRgb.value;
    const a = alpha.value;

    switch (selectedFormat.value) {
        case "rgb":
            return a < 100 ? `rgba(${r}, ${g}, ${b}, ${(a / 100).toFixed(2)})` : `rgb(${r}, ${g}, ${b})`;
        case "hsl": {
            // RGB 转 HSL
            const rNorm = r / 255;
            const gNorm = g / 255;
            const bNorm = b / 255;
            const max = Math.max(rNorm, gNorm, bNorm);
            const min = Math.min(rNorm, gNorm, bNorm);
            const delta = max - min;

            let h = 0;
            if (delta !== 0) {
                if (max === rNorm) h = 60 * (((gNorm - bNorm) / delta) % 6);
                else if (max === gNorm) h = 60 * ((bNorm - rNorm) / delta + 2);
                else h = 60 * ((rNorm - gNorm) / delta + 4);
            }
            if (h < 0) h += 360;

            const l = (max + min) / 2;
            const s = delta === 0 ? 0 : delta / (1 - Math.abs(2 * l - 1));

            return a < 100
                ? `hsla(${Math.round(h)}, ${Math.round(s * 100)}%, ${Math.round(l * 100)}%, ${(a / 100).toFixed(2)})`
                : `hsl(${Math.round(h)}, ${Math.round(s * 100)}%, ${Math.round(l * 100)}%)`;
        }
        case "hsb":
            return a < 100
                ? `hsba(${hue.value}, ${saturation.value}%, ${brightness.value}%, ${(a / 100).toFixed(2)})`
                : `hsb(${hue.value}, ${saturation.value}%, ${brightness.value}%)`;
        case "hex":
        default:
            return rgbToHex(r, g, b, props.disabledAlpha ? undefined : a);
    }
});

// 颜色值输入状态
const colorInputValue = ref("");

// 监听 currentColor 变化，同步到输入框
watch(
    currentColor,
    (newVal) => {
        colorInputValue.value = newVal;
    },
    { immediate: true }
);

// 处理颜色值输入完成（失焦或回车）
const handleColorInputComplete = () => {
    const value = colorInputValue.value.trim();
    if (!value) return;

    // 尝试解析输入的颜色值
    const parsed = parseColor(value);
    if (parsed) {
        const hsb = rgbToHsb(parsed.r, parsed.g, parsed.b);
        hue.value = Math.round(hsb.h);
        saturation.value = Math.round(hsb.s);
        brightness.value = Math.round(hsb.b);
        alpha.value = parsed.a;
        emitChange();
    } else {
        // 解析失败，恢复为当前有效值
        colorInputValue.value = currentColor.value;
    }
};

const displayColor = computed(() => {
    const { r, g, b } = currentRgb.value;
    return `rgba(${r}, ${g}, ${b}, ${alpha.value / 100})`;
});

// transform-origin 根据弹出方向设置
const transformOrigin = computed(() => {
    const p = props.placement;
    if (p === "top") return "center bottom";
    if (p === "topLeft") return "left bottom";
    if (p === "topRight") return "right bottom";
    if (p === "bottom") return "center top";
    if (p === "bottomLeft") return "left top";
    if (p === "bottomRight") return "right top";
    return "center top";
});

// ==================== 初始化颜色 ====================
const initColor = (color: string) => {
    const parsed = parseColor(color);
    if (parsed) {
        const hsb = rgbToHsb(parsed.r, parsed.g, parsed.b);
        hue.value = Math.round(hsb.h);
        saturation.value = Math.round(hsb.s);
        brightness.value = Math.round(hsb.b);
        alpha.value = parsed.a;
    }
};

// 监听 modelValue 变化
watch(
    () => props.modelValue,
    (newVal) => {
        // 初始化颜色，如果没有 modelValue 则使用 defaultValue
        initColor(newVal || props.defaultValue);
    },
    { immediate: true }
);

// ==================== 色板交互 ====================
const paletteRef = ref<HTMLElement | null>(null);
const isDraggingPalette = ref(false);

const updatePaletteColor = (e: MouseEvent) => {
    if (!paletteRef.value) return;
    const rect = paletteRef.value.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const y = Math.max(0, Math.min(e.clientY - rect.top, rect.height));

    saturation.value = Math.round((x / rect.width) * 100);
    brightness.value = Math.round((1 - y / rect.height) * 100);

    // 如果透明度为0，自动恢复到100%
    if (alpha.value === 0) {
        alpha.value = 100;
    }

    emitChange();
};

const handlePaletteMouseDown = (e: MouseEvent) => {
    isDraggingPalette.value = true;
    updatePaletteColor(e);
};

const handlePaletteMouseMove = (e: MouseEvent) => {
    if (isDraggingPalette.value) {
        updatePaletteColor(e);
    }
};

const handlePaletteMouseUp = () => {
    if (isDraggingPalette.value) {
        isDraggingPalette.value = false;
        emit("changeComplete", currentColor.value);
    }
};

// ==================== 色相滑块交互 ====================
const hueSliderRef = ref<HTMLElement | null>(null);
const isDraggingHue = ref(false);

const updateHueFromPosition = (clientX: number) => {
    if (!hueSliderRef.value) return;
    const rect = hueSliderRef.value.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    hue.value = Math.round((x / rect.width) * 360);
    emitChange();
};

const handleHueMouseDown = (e: MouseEvent) => {
    isDraggingHue.value = true;
    updateHueFromPosition(e.clientX);
};

const handleHueMouseMove = (e: MouseEvent) => {
    if (isDraggingHue.value) {
        updateHueFromPosition(e.clientX);
    }
};

const handleHueMouseUp = () => {
    if (isDraggingHue.value) {
        isDraggingHue.value = false;
        emit("changeComplete", currentColor.value);
    }
};

// ==================== 透明度滑块交互 ====================
const alphaSliderRef = ref<HTMLElement | null>(null);
const isDraggingAlpha = ref(false);

const updateAlphaFromPosition = (clientX: number) => {
    if (!alphaSliderRef.value) return;
    const rect = alphaSliderRef.value.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    alpha.value = Math.round((x / rect.width) * 100);
    emitChange();
};

const handleAlphaMouseDown = (e: MouseEvent) => {
    isDraggingAlpha.value = true;
    updateAlphaFromPosition(e.clientX);
};

const handleAlphaMouseMove = (e: MouseEvent) => {
    if (isDraggingAlpha.value) {
        updateAlphaFromPosition(e.clientX);
    }
};

const handleAlphaMouseUp = () => {
    if (isDraggingAlpha.value) {
        isDraggingAlpha.value = false;
        emit("changeComplete", currentColor.value);
    }
};

// ==================== 事件触发 ====================
const emitChange = () => {
    const color = currentColor.value;
    const { r, g, b } = currentRgb.value;
    const hex = rgbToHex(r, g, b);
    emit("update:modelValue", color);
    emit("change", color, hex);
};

// ==================== 预设颜色 ====================
const handlePresetClick = (color: string) => {
    initColor(color);
    emitChange();
    emit("changeComplete", currentColor.value);
};

// ==================== 清除 ====================
const handleClear = () => {
    // 只把透明度设为0，其他颜色值保持不变
    alpha.value = 0;

    emit("clear");
    emit("update:modelValue", "");
    emitChange();
};

// ==================== 尺寸 ====================
const triggerSizeClass = computed(() => `vort-color-picker-trigger-${props.size || "middle"}`);
const blockSizeClass = computed(() => `vort-color-picker-block-${props.size || "middle"}`);

// ==================== 显示文本 ====================
const displayText = computed(() => {
    if (props.showText === false) return null;
    if (typeof props.showText === "function") {
        return props.showText(currentColor.value);
    }
    return currentColor.value.toUpperCase();
});

// 色板指示器位置
const paletteHandlerStyle = computed(() => ({
    left: `${saturation.value}%`,
    bottom: `${brightness.value}%`
}));

// 色板背景色（纯色相）
const paletteBackground = computed(() => `hsl(${hue.value}, 100%, 50%)`);

// 挂载时监听全局鼠标事件
onMounted(() => {
    document.addEventListener("mousemove", handlePaletteMouseMove);
    document.addEventListener("mouseup", handlePaletteMouseUp);
    document.addEventListener("mousemove", handleHueMouseMove);
    document.addEventListener("mouseup", handleHueMouseUp);
    document.addEventListener("mousemove", handleAlphaMouseMove);
    document.addEventListener("mouseup", handleAlphaMouseUp);
});

// 初始化
initColor(props.modelValue || props.defaultValue);
</script>

<template>
    <div :class="['vort-color-picker', props.class]">
        <!-- 颜色块触发器 -->
        <div
            ref="triggerRef"
            v-bind="triggerHandlers"
            :class="[
                'vort-color-picker-trigger',
                disabled && 'vort-color-picker-trigger-disabled',
                displayText ? 'vort-color-picker-trigger-with-text' : triggerSizeClass
            ]"
        >
            <!-- 颜色块容器 -->
            <div :class="['vort-color-picker-color-block', displayText ? blockSizeClass : 'vort-color-picker-block-full']">
                <!-- 棋盘格背景 -->
                <div class="vort-color-picker-checkerboard" />
                <!-- 颜色显示层 -->
                <div class="vort-color-picker-color-block-inner" :style="{ backgroundColor: displayColor }" />
            </div>

            <!-- 文本 -->
            <span v-if="displayText" class="vort-color-picker-trigger-text">
                {{ displayText }}
            </span>
        </div>

        <!-- 浮层面板 -->
        <Teleport v-if="shouldRenderTeleport" :to="popupContainer">
            <Transition name="vort-zoom" appear @after-leave="handleAfterLeave">
                <div
                    v-if="isOpen"
                    ref="floatingRef"
                    v-bind="floatingHandlers"
                    :style="{
                        position: 'fixed',
                        top: `${position.top}px`,
                        left: `${position.left}px`,
                        zIndex: zIndex,
                        pointerEvents: 'auto',
                        '--transform-origin': transformOrigin
                    }"
                    class="vort-color-picker-panel"
                >
                    <div ref="panelRef" class="vort-color-picker-panel-inner" @click.stop>
                        <!-- 色板 -->
                        <div
                            ref="paletteRef"
                            class="vort-color-picker-palette"
                            :style="{ backgroundColor: paletteBackground }"
                            @mousedown="handlePaletteMouseDown"
                        >
                            <!-- 白色渐变 (饱和度) -->
                            <div class="vort-color-picker-palette-white" />
                            <!-- 黑色渐变 (亮度) -->
                            <div class="vort-color-picker-palette-black" />
                            <!-- 指示器 -->
                            <div class="vort-color-picker-palette-handler" :style="paletteHandlerStyle">
                                <div class="vort-color-picker-palette-handler-inner" :style="{ backgroundColor: displayColor }" />
                            </div>
                        </div>

                        <!-- 滑块区域（左右布局：滑块组 + 颜色预览） -->
                        <div class="vort-color-picker-sliders">
                            <!-- 左侧：滑块组 -->
                            <div class="vort-color-picker-sliders-left">
                                <!-- 色相滑块 -->
                                <div ref="hueSliderRef" class="vort-color-picker-hue-slider" @mousedown="handleHueMouseDown">
                                    <!-- 滑块手柄 -->
                                    <div
                                        class="vort-color-picker-slider-handle"
                                        :style="{
                                            left: `${(hue / 360) * 100}%`,
                                            backgroundColor: `hsl(${hue}, 100%, 50%)`
                                        }"
                                    />
                                </div>

                                <!-- 透明度滑块 -->
                                <div v-if="!disabledAlpha" class="vort-color-picker-alpha-slider">
                                    <!-- 棋盘格背景 -->
                                    <div class="vort-color-picker-alpha-bg" />
                                    <!-- 渐变层 -->
                                    <div
                                        ref="alphaSliderRef"
                                        class="vort-color-picker-alpha-gradient"
                                        :style="{
                                            background: `linear-gradient(to right, transparent, rgb(${currentRgb.r}, ${currentRgb.g}, ${currentRgb.b}))`
                                        }"
                                        @mousedown="handleAlphaMouseDown"
                                    >
                                        <!-- 滑块手柄 -->
                                        <div class="vort-color-picker-slider-handle" :style="{ left: `${alpha}%`, backgroundColor: displayColor }" />
                                    </div>
                                </div>
                            </div>

                            <!-- 右侧：颜色预览块 -->
                            <div class="vort-color-picker-preview">
                                <!-- 棋盘格背景 -->
                                <div class="vort-color-picker-preview-bg" />
                                <!-- 颜色 -->
                                <div class="vort-color-picker-preview-color" :style="{ backgroundColor: displayColor }" />
                            </div>
                        </div>

                        <!-- 颜色输入（格式选择 + 输入框 + 清除按钮） -->
                        <div class="vort-color-picker-input-row">
                            <div class="vort-color-picker-input-group">
                                <!-- 格式选择器 -->
                                <Select
                                    v-model="selectedFormat"
                                    :options="formatOptions"
                                    size="small"
                                    class="vort-color-picker-format-select"
                                    :get-popup-container="getSelectPopupContainer"
                                    :bordered="false"
                                />
                                <!-- 颜色值输入 -->
                                <Input
                                    v-model="colorInputValue"
                                    size="small"
                                    class="vort-color-picker-value-input"
                                    @blur="handleColorInputComplete"
                                    @keydown.enter="handleColorInputComplete"
                                />
                                <!-- 清除按钮 -->
                                <Button v-if="allowClear" type="text" size="small" class="vort-color-picker-clear-btn" @click="handleClear"> 清除 </Button>
                            </div>
                        </div>

                        <!-- 预设颜色 -->
                        <div v-if="presets && presets.length" class="vort-color-picker-presets">
                            <div v-for="(preset, idx) in presets" :key="idx" class="vort-color-picker-preset-group">
                                <div class="vort-color-picker-preset-colors">
                                    <div
                                        v-for="(colorItem, colorIdx) in preset.colors"
                                        :key="colorIdx"
                                        class="vort-color-picker-preset-item"
                                        @click="handlePresetClick(typeof colorItem === 'string' ? colorItem : colorItem.color)"
                                    >
                                        <!-- 棋盘格背景 -->
                                        <div class="vort-color-picker-preset-bg" />
                                        <!-- 颜色 -->
                                        <div
                                            class="vort-color-picker-preset-color"
                                            :style="{ backgroundColor: typeof colorItem === 'string' ? colorItem : colorItem.color }"
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </Transition>
        </Teleport>
    </div>
</template>

<style scoped>
/* ============ 触发器 ============ */
.vort-color-picker-trigger {
    display: inline-flex;
    align-items: center;
    border-radius: var(--vort-border-radius, 6px);
    cursor: pointer;
    transition: all var(--vort-duration-normal, 200ms);
    border: 1px solid var(--vort-border);
    background: #fff;
}

.vort-color-picker-trigger:hover {
    border-color: var(--vort-primary);
}

.vort-color-picker-trigger-disabled {
    cursor: not-allowed;
    opacity: 0.5;
}

.vort-color-picker-trigger-disabled:hover {
    border-color: var(--vort-border);
}

.vort-color-picker-trigger-with-text {
    gap: 8px;
    padding: 2px 10px 2px 2px;
}

/* 触发器尺寸 */
.vort-color-picker-trigger-large {
    width: 48px;
    height: 48px;
    padding: 2px;
    justify-content: center;
}

.vort-color-picker-trigger-middle {
    width: 32px;
    height: 32px;
    padding: 2px;
    justify-content: center;
}

.vort-color-picker-trigger-small {
    width: 24px;
    height: 24px;
    padding: 2px;
    justify-content: center;
}

/* ============ 颜色块 ============ */
.vort-color-picker-color-block {
    position: relative;
    overflow: hidden;
    border-radius: var(--vort-border-radius-sm, 4px);
    flex-shrink: 0;
}

.vort-color-picker-block-full {
    width: 100%;
    height: 100%;
}

.vort-color-picker-block-large {
    width: 32px;
    height: 32px;
}

.vort-color-picker-block-middle {
    width: 24px;
    height: 24px;
}

.vort-color-picker-block-small {
    width: 20px;
    height: 20px;
}

.vort-color-picker-checkerboard {
    position: absolute;
    inset: 0;
    background-image: conic-gradient(rgba(0, 0, 0, 0.06) 0 25%, transparent 0 50%, rgba(0, 0, 0, 0.06) 0 75%, transparent 0);
    background-size: 8px 8px;
}

.vort-color-picker-color-block-inner {
    position: absolute;
    inset: 0;
    border-radius: var(--vort-border-radius-sm, 4px);
    box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.06);
}

.vort-color-picker-trigger-text {
    font-size: 14px;
    color: var(--vort-text);
}

/* ============ 面板 ============ */
.vort-color-picker-panel {
    background: #fff;
    border-radius: var(--vort-border-radius-lg, 8px);
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
}

.vort-color-picker-panel-inner {
    padding: 12px;
    width: 280px;
}

/* ============ 色板 ============ */
.vort-color-picker-palette {
    position: relative;
    width: 100%;
    height: 180px;
    border-radius: var(--vort-border-radius, 6px);
    cursor: crosshair;
    margin-bottom: 12px;
    overflow: hidden;
    user-select: none;
}

.vort-color-picker-palette-white {
    position: absolute;
    inset: 0;
    background: linear-gradient(to right, #fff, transparent);
}

.vort-color-picker-palette-black {
    position: absolute;
    inset: 0;
    background: linear-gradient(to top, #000, transparent);
    box-shadow: inset 0 0 1px 0 rgba(0, 0, 0, 0.12);
}

.vort-color-picker-palette-handler {
    position: absolute;
    width: 16px;
    height: 16px;
    border: 2px solid #fff;
    border-radius: 50%;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    transform: translate(-50%, 50%);
    pointer-events: none;
}

.vort-color-picker-palette-handler-inner {
    position: absolute;
    inset: 2px;
    border-radius: 50%;
}

/* ============ 滑块区域 ============ */
.vort-color-picker-sliders {
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 12px;
}

.vort-color-picker-sliders-left {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

/* 色相滑块 */
.vort-color-picker-hue-slider {
    position: relative;
    height: 10px;
    border-radius: 9999px;
    cursor: pointer;
    user-select: none;
    background: linear-gradient(to right, #f00 0%, #ff0 17%, #0f0 33%, #0ff 50%, #00f 67%, #f0f 83%, #f00 100%);
}

/* 透明度滑块 */
.vort-color-picker-alpha-slider {
    position: relative;
    height: 10px;
    border-radius: 9999px;
    cursor: pointer;
    user-select: none;
}

.vort-color-picker-alpha-bg {
    position: absolute;
    inset: 0;
    background-image: conic-gradient(rgba(0, 0, 0, 0.06) 0 25%, transparent 0 50%, rgba(0, 0, 0, 0.06) 0 75%, transparent 0);
    background-size: 8px 8px;
}

.vort-color-picker-alpha-gradient {
    position: absolute;
    inset: 0;
    border-radius: 9999px;
}

/* 滑块手柄 */
.vort-color-picker-slider-handle {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 16px;
    height: 16px;
    border-radius: 50%;
    border: 2px solid #fff;
    box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.1);
    cursor: grab;
}

.vort-color-picker-slider-handle:active {
    cursor: grabbing;
}

/* 颜色预览 */
.vort-color-picker-preview {
    width: 40px;
    height: 40px;
    border-radius: var(--vort-border-radius, 6px);
    border: 1px solid var(--vort-border);
    flex-shrink: 0;
    position: relative;
    overflow: hidden;
}

.vort-color-picker-preview-bg {
    position: absolute;
    inset: 0;
    background-image: conic-gradient(rgba(0, 0, 0, 0.06) 0 25%, transparent 0 50%, rgba(0, 0, 0, 0.06) 0 75%, transparent 0);
    background-size: 10px 10px;
}

.vort-color-picker-preview-color {
    position: absolute;
    inset: 4px;
    border-radius: var(--vort-border-radius-sm, 4px);
}

/* ============ 输入区域 ============ */
.vort-color-picker-input-row {
    margin-bottom: 12px;
}

.vort-color-picker-input-group {
    display: flex;
    align-items: center;
    gap: 8px;
}

.vort-color-picker-format-select {
    width: 60px;
    flex-shrink: 0;
}

.vort-color-picker-value-input {
    flex: 1;
    font-family: monospace;
    font-size: 12px;
}

.vort-color-picker-clear-btn {
    flex-shrink: 0;
}

/* ============ 预设颜色 ============ */
.vort-color-picker-presets {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.vort-color-picker-preset-colors {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.vort-color-picker-preset-item {
    position: relative;
    width: 20px;
    height: 20px;
    border-radius: var(--vort-border-radius-sm, 4px);
    cursor: pointer;
    overflow: hidden;
    transition: transform var(--vort-duration-fast, 100ms);
}

.vort-color-picker-preset-item:hover {
    transform: scale(1.1);
}

.vort-color-picker-preset-bg {
    position: absolute;
    inset: 0;
    background-image: conic-gradient(rgba(0, 0, 0, 0.06) 0 25%, transparent 0 50%, rgba(0, 0, 0, 0.06) 0 75%, transparent 0);
    background-size: 4px 4px;
}

.vort-color-picker-preset-color {
    position: absolute;
    inset: 0;
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: var(--vort-border-radius-sm, 4px);
}

/* ============ 动画 ============ */
.vort-zoom-enter-active {
    animation: vortZoomIn 0.2s cubic-bezier(0.08, 0.82, 0.17, 1);
    transform-origin: var(--transform-origin, center top);
}

.vort-zoom-leave-active {
    animation: vortZoomOut 0.2s cubic-bezier(0.78, 0.14, 0.15, 0.86);
    transform-origin: var(--transform-origin, center top);
}

@keyframes vortZoomIn {
    0% {
        opacity: 0;
        transform: scale(0.8);
    }
    100% {
        opacity: 1;
        transform: scale(1);
    }
}

@keyframes vortZoomOut {
    0% {
        opacity: 1;
        transform: scale(1);
    }
    100% {
        opacity: 0;
        transform: scale(0.8);
    }
}
</style>
