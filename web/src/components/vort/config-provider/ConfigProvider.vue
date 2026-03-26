<script setup lang="ts">
import { computed, provide, watchEffect } from "vue";
import type { ConfigProviderProps, ConfigProviderContext } from "./types";
import { CONFIG_PROVIDER_KEY } from "./types";
import { VORT_TELEPORT_CONTAINER_ID } from "../composables/useTeleportContainer";
import { localeContextKey, setGlobalLocale } from "../locale/useLocale";
import zhCN from "../locale/zh-CN";

defineOptions({ name: "VortConfigProvider" });

/** Vort ConfigProvider - 全局配置组件 */

const props = defineProps<ConfigProviderProps>();

// ===== 颜色工具函数 =====

/** 解析 hex 颜色为 RGB */
const hexToRgb = (hex: string): { r: number; g: number; b: number } | null => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result
        ? {
              // noUncheckedIndexedAccess 下 result[n] 可能为 undefined，需要兜底
              r: parseInt(result[1] ?? "00", 16),
              g: parseInt(result[2] ?? "00", 16),
              b: parseInt(result[3] ?? "00", 16)
          }
        : null;
};

/** RGB 转 hex */
const rgbToHex = (r: number, g: number, b: number): string => {
    const toHex = (n: number) => {
        const hex = Math.round(Math.max(0, Math.min(255, n))).toString(16);
        return hex.length === 1 ? "0" + hex : hex;
    };
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
};

/** RGB 转 HSL */
const rgbToHsl = (r: number, g: number, b: number): { h: number; s: number; l: number } => {
    r /= 255;
    g /= 255;
    b /= 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h = 0;
    let s = 0;
    const l = (max + min) / 2;

    if (max !== min) {
        const d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
            case r:
                h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
                break;
            case g:
                h = ((b - r) / d + 2) / 6;
                break;
            case b:
                h = ((r - g) / d + 4) / 6;
                break;
        }
    }
    return { h: h * 360, s: s * 100, l: l * 100 };
};

/** HSL 转 RGB */
const hslToRgb = (h: number, s: number, l: number): { r: number; g: number; b: number } => {
    h /= 360;
    s /= 100;
    l /= 100;
    let r, g, b;

    if (s === 0) {
        r = g = b = l;
    } else {
        const hue2rgb = (p: number, q: number, t: number) => {
            if (t < 0) t += 1;
            if (t > 1) t -= 1;
            if (t < 1 / 6) return p + (q - p) * 6 * t;
            if (t < 1 / 2) return q;
            if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
            return p;
        };
        const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
        const p = 2 * l - q;
        r = hue2rgb(p, q, h + 1 / 3);
        g = hue2rgb(p, q, h);
        b = hue2rgb(p, q, h - 1 / 3);
    }
    return { r: r * 255, g: g * 255, b: b * 255 };
};

/** 调整颜色亮度 */
const adjustLightness = (hex: string, amount: number): string => {
    const rgb = hexToRgb(hex);
    if (!rgb) return hex;
    const hsl = rgbToHsl(rgb.r, rgb.g, rgb.b);
    hsl.l = Math.max(0, Math.min(100, hsl.l + amount));
    const newRgb = hslToRgb(hsl.h, hsl.s, hsl.l);
    return rgbToHex(newRgb.r, newRgb.g, newRgb.b);
};

/** 混合颜色与白色 */
const mixWithWhite = (hex: string, ratio: number): string => {
    const rgb = hexToRgb(hex);
    if (!rgb) return hex;
    const r = Math.round(rgb.r + (255 - rgb.r) * ratio);
    const g = Math.round(rgb.g + (255 - rgb.g) * ratio);
    const b = Math.round(rgb.b + (255 - rgb.b) * ratio);
    return rgbToHex(r, g, b);
};

/**
 * 根据主色自动计算完整的衍生色
 */
const generateColorVariants = (primaryColor: string) => {
    const rgb = hexToRgb(primaryColor);
    return {
        primary: primaryColor,
        // hover 态：亮度增加 10%
        primaryHover: adjustLightness(primaryColor, 10),
        // active 态：亮度降低 10%
        primaryActive: adjustLightness(primaryColor, -10),
        // 背景色：与白色混合 90%（非常浅）
        primaryBg: mixWithWhite(primaryColor, 0.9),
        // 背景悬停色：与白色混合 80%
        primaryBgHover: mixWithWhite(primaryColor, 0.8),
        // 阴影色：带透明度
        primaryShadow: rgb ? `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.1)` : "rgba(0, 0, 0, 0.1)"
    };
};

/**
 * 将 ThemeToken 转换为 CSS 变量对象
 */
const cssVars = computed(() => {
    const token = props.theme?.token;
    if (!token) return {};

    const vars: Record<string, string> = {};

    // ===== 主题色 =====
    if (token.colorPrimary) {
        const colors = generateColorVariants(token.colorPrimary);
        vars["--vort-primary"] = colors.primary;
        // 自动生成衍生色，用户也可以覆盖
        vars["--vort-primary-hover"] = token.colorPrimaryHover ?? colors.primaryHover;
        vars["--vort-primary-active"] = token.colorPrimaryActive ?? colors.primaryActive;
        vars["--vort-primary-bg"] = token.colorPrimaryBg ?? colors.primaryBg;
        vars["--vort-primary-bg-hover"] = token.colorPrimaryBgHover ?? colors.primaryBgHover;
        vars["--vort-primary-shadow"] = colors.primaryShadow;
    }

    // ===== 功能色 - Success =====
    if (token.colorSuccess) {
        const colors = generateColorVariants(token.colorSuccess);
        vars["--vort-success"] = colors.primary;
        vars["--vort-success-hover"] = token.colorSuccessHover ?? colors.primaryHover;
        vars["--vort-success-active"] = token.colorSuccessActive ?? colors.primaryActive;
        vars["--vort-success-bg"] = token.colorSuccessBg ?? colors.primaryBg;
    }

    // ===== 功能色 - Warning =====
    if (token.colorWarning) {
        const colors = generateColorVariants(token.colorWarning);
        vars["--vort-warning"] = colors.primary;
        vars["--vort-warning-hover"] = token.colorWarningHover ?? colors.primaryHover;
        vars["--vort-warning-active"] = token.colorWarningActive ?? colors.primaryActive;
        vars["--vort-warning-bg"] = token.colorWarningBg ?? colors.primaryBg;
    }

    // ===== 功能色 - Error =====
    if (token.colorError) {
        const colors = generateColorVariants(token.colorError);
        vars["--vort-error"] = colors.primary;
        vars["--vort-error-hover"] = token.colorErrorHover ?? colors.primaryHover;
        vars["--vort-error-active"] = token.colorErrorActive ?? colors.primaryActive;
        vars["--vort-error-bg"] = token.colorErrorBg ?? colors.primaryBg;
    }

    // ===== 功能色 - Info =====
    if (token.colorInfo) {
        const colors = generateColorVariants(token.colorInfo);
        vars["--vort-info"] = colors.primary;
        vars["--vort-info-hover"] = token.colorInfoHover ?? colors.primaryHover;
        vars["--vort-info-active"] = token.colorInfoActive ?? colors.primaryActive;
        vars["--vort-info-bg"] = token.colorInfoBg ?? colors.primaryBg;
    }

    // ===== 中性色 =====
    if (token.colorText) vars["--vort-text"] = token.colorText;
    if (token.colorTextSecondary) vars["--vort-text-secondary"] = token.colorTextSecondary;
    if (token.colorTextTertiary) vars["--vort-text-tertiary"] = token.colorTextTertiary;
    if (token.colorTextQuaternary) vars["--vort-text-quaternary"] = token.colorTextQuaternary;

    if (token.colorBorder) vars["--vort-border"] = token.colorBorder;
    if (token.colorBorderSecondary) vars["--vort-border-secondary"] = token.colorBorderSecondary;

    if (token.colorBg) vars["--vort-bg"] = token.colorBg;
    if (token.colorBgElevated) vars["--vort-bg-elevated"] = token.colorBgElevated;
    if (token.colorBgMask) vars["--vort-bg-mask"] = token.colorBgMask;

    // ===== 圆角 =====
    if (token.borderRadius !== undefined) {
        vars["--vort-border-radius"] = `${token.borderRadius}px`;
        // 兼容简写变量名（部分组件使用 --vort-radius）
        vars["--vort-radius"] = `${token.borderRadius}px`;

        // 自动计算 SM 和 LG 圆角（参考 Ant Design 的比例关系）
        // SM = 基础值 / 2（最小为 2）
        // LG = 基础值 * 1.5
        const autoRadiusSM = Math.max(2, Math.round(token.borderRadius / 2));
        const autoRadiusLG = Math.round(token.borderRadius * 1.5);

        vars["--vort-border-radius-sm"] = `${token.borderRadiusSM ?? autoRadiusSM}px`;
        vars["--vort-radius-sm"] = `${token.borderRadiusSM ?? autoRadiusSM}px`;
        vars["--vort-border-radius-lg"] = `${token.borderRadiusLG ?? autoRadiusLG}px`;
        vars["--vort-radius-lg"] = `${token.borderRadiusLG ?? autoRadiusLG}px`;

        // 布局圆角：优先使用 borderRadiusLG，否则使用自动计算的 LG 值
        vars["--vort-layout-radius"] = `${token.borderRadiusLG ?? autoRadiusLG}px`;
    } else {
        // 未设置 borderRadius 时，仍支持单独设置 SM/LG
        if (token.borderRadiusSM !== undefined) {
            vars["--vort-border-radius-sm"] = `${token.borderRadiusSM}px`;
            vars["--vort-radius-sm"] = `${token.borderRadiusSM}px`;
        }
        if (token.borderRadiusLG !== undefined) {
            vars["--vort-border-radius-lg"] = `${token.borderRadiusLG}px`;
            vars["--vort-radius-lg"] = `${token.borderRadiusLG}px`;
            vars["--vort-layout-radius"] = `${token.borderRadiusLG}px`;
        }
    }

    // ===== 尺寸 =====
    if (token.controlHeight !== undefined) {
        vars["--vort-control-height"] = `${token.controlHeight}px`;
        vars["--vort-height-md"] = `${token.controlHeight}px`;
    }
    if (token.controlHeightSM !== undefined) {
        vars["--vort-control-height-sm"] = `${token.controlHeightSM}px`;
        vars["--vort-height-sm"] = `${token.controlHeightSM}px`;
    }
    if (token.controlHeightLG !== undefined) {
        vars["--vort-control-height-lg"] = `${token.controlHeightLG}px`;
        vars["--vort-height-lg"] = `${token.controlHeightLG}px`;
    }

    // ===== 间距 =====
    if (token.marginXS !== undefined) vars["--vort-margin-xs"] = `${token.marginXS}px`;
    if (token.marginSM !== undefined) vars["--vort-margin-sm"] = `${token.marginSM}px`;
    if (token.margin !== undefined) vars["--vort-margin"] = `${token.margin}px`;
    if (token.marginMD !== undefined) vars["--vort-margin-md"] = `${token.marginMD}px`;
    if (token.marginLG !== undefined) vars["--vort-margin-lg"] = `${token.marginLG}px`;
    if (token.marginXL !== undefined) vars["--vort-margin-xl"] = `${token.marginXL}px`;

    if (token.paddingXS !== undefined) vars["--vort-padding-xs"] = `${token.paddingXS}px`;
    if (token.paddingSM !== undefined) vars["--vort-padding-sm"] = `${token.paddingSM}px`;
    if (token.padding !== undefined) vars["--vort-padding"] = `${token.padding}px`;
    if (token.paddingMD !== undefined) vars["--vort-padding-md"] = `${token.paddingMD}px`;
    if (token.paddingLG !== undefined) vars["--vort-padding-lg"] = `${token.paddingLG}px`;
    if (token.paddingXL !== undefined) vars["--vort-padding-xl"] = `${token.paddingXL}px`;

    // ===== 字体 =====
    if (token.fontSize !== undefined) {
        // 设置基础字号（对应 --vort-font-size-sm，项目中大多数组件使用此变量）
        vars["--vort-font-size"] = `${token.fontSize}px`;
        vars["--vort-font-size-sm"] = `${token.fontSize}px`;

        // 自动计算 XS 和 MD/LG 字号（参考 Ant Design 的比例关系）
        // XS = 基础值 - 2（最小为 10）
        // MD/LG = 基础值 + 2
        const autoFontSizeXS = Math.max(10, token.fontSize - 2);
        const autoFontSizeLG = token.fontSize + 2;

        vars["--vort-font-size-xs"] = `${token.fontSizeSM ?? autoFontSizeXS}px`;
        vars["--vort-font-size-md"] = `${token.fontSizeLG ?? autoFontSizeLG}px`;
    } else {
        // 未设置 fontSize 时，仍支持单独设置 SM/LG
        if (token.fontSizeSM !== undefined) {
            vars["--vort-font-size-xs"] = `${token.fontSizeSM}px`;
        }
        if (token.fontSizeLG !== undefined) {
            vars["--vort-font-size-md"] = `${token.fontSizeLG}px`;
        }
    }

    if (token.fontFamily) vars["--vort-font-family"] = token.fontFamily;

    // ===== 阴影 =====
    if (token.boxShadow) vars["--vort-box-shadow"] = token.boxShadow;
    if (token.boxShadowSecondary) vars["--vort-box-shadow-secondary"] = token.boxShadowSecondary;

    // ===== 动画 =====
    if (token.motionDurationFast !== undefined) vars["--vort-motion-duration-fast"] = `${token.motionDurationFast}ms`;
    if (token.motionDurationMid !== undefined) vars["--vort-motion-duration-mid"] = `${token.motionDurationMid}ms`;
    if (token.motionDurationSlow !== undefined) vars["--vort-motion-duration-slow"] = `${token.motionDurationSlow}ms`;
    if (token.motionEaseInOut) vars["--vort-motion-ease-in-out"] = token.motionEaseInOut;
    if (token.motionEaseOut) vars["--vort-motion-ease-out"] = token.motionEaseOut;

    // ===== 层级 =====
    if (token.zIndexBase !== undefined) vars["--vort-z-index-base"] = String(token.zIndexBase);
    if (token.zIndexPopup !== undefined) vars["--vort-z-index-popup"] = String(token.zIndexPopup);

    return vars;
});

// 提供配置上下文给子组件（可选，用于需要读取配置的场景）
const configContext = computed<ConfigProviderContext>(() => ({
    token: props.theme?.token ?? {}
}));

provide(CONFIG_PROVIDER_KEY, configContext);

// 提供国际化上下文给子组件（使用 computed 保持响应式）
const resolvedLocale = computed(() => props.locale ?? zhCN);
provide(localeContextKey, resolvedLocale);

// 同步到全局 locale（供 dialog.confirm 等独立 app 实例使用）
watchEffect(() => {
    setGlobalLocale(resolvedLocale.value);
});
</script>

<template>
    <div class="vort-config-provider" :style="cssVars">
        <slot />
        <!-- 当 getPopupContainer 为 true 时自动渲染 Teleport 容器 -->
        <div v-if="getPopupContainer" :id="VORT_TELEPORT_CONTAINER_ID" class="vort-teleport-container" />
    </div>
</template>

<style scoped>
.vort-config-provider {
    /* 确保配置容器不影响布局 */
    display: contents;
}
</style>

<style>
/* Teleport 容器样式（不使用 scoped，让样式能作用到 teleport 的内容） */
.vort-teleport-container {
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 2000;
}
.vort-teleport-container > * {
    pointer-events: auto;
}
</style>
