/** Vort ConfigProvider 主题配置类型定义 */

import type { Locale } from "../locale/types";

/** 主题 Token 配置 */
export interface ThemeToken {
    // ===== 主题色 =====
    /** 主题色 */
    colorPrimary?: string;
    /** 主题色悬停态 */
    colorPrimaryHover?: string;
    /** 主题色激活态 */
    colorPrimaryActive?: string;
    /** 主题色背景 */
    colorPrimaryBg?: string;
    /** 主题色背景悬停态 */
    colorPrimaryBgHover?: string;

    // ===== 功能色 =====
    /** 成功色 */
    colorSuccess?: string;
    /** 成功色悬停态 */
    colorSuccessHover?: string;
    /** 成功色激活态 */
    colorSuccessActive?: string;
    /** 成功色背景 */
    colorSuccessBg?: string;

    /** 警告色 */
    colorWarning?: string;
    /** 警告色悬停态 */
    colorWarningHover?: string;
    /** 警告色激活态 */
    colorWarningActive?: string;
    /** 警告色背景 */
    colorWarningBg?: string;

    /** 错误色 */
    colorError?: string;
    /** 错误色悬停态 */
    colorErrorHover?: string;
    /** 错误色激活态 */
    colorErrorActive?: string;
    /** 错误色背景 */
    colorErrorBg?: string;

    /** 信息色（默认同主题色） */
    colorInfo?: string;
    /** 信息色悬停态 */
    colorInfoHover?: string;
    /** 信息色激活态 */
    colorInfoActive?: string;
    /** 信息色背景 */
    colorInfoBg?: string;

    // ===== 中性色 =====
    /** 主文本色 */
    colorText?: string;
    /** 次要文本色 */
    colorTextSecondary?: string;
    /** 三级文本色 */
    colorTextTertiary?: string;
    /** 四级文本色（占位符等） */
    colorTextQuaternary?: string;

    /** 边框色 */
    colorBorder?: string;
    /** 次要边框色 */
    colorBorderSecondary?: string;

    /** 背景色 */
    colorBg?: string;
    /** 容器背景色（卡片、弹窗等） */
    colorBgElevated?: string;
    /** 遮罩层背景色 */
    colorBgMask?: string;

    // ===== 圆角 =====
    /** 基础圆角（用于 Button, Input, Select 等小型组件） */
    borderRadius?: number;
    /** 小圆角 */
    borderRadiusSM?: number;
    /** 大圆角（用于 Card, Modal, Drawer 等容器组件） */
    borderRadiusLG?: number;

    // ===== 尺寸 =====
    /** 控件高度 */
    controlHeight?: number;
    /** 小号控件高度 */
    controlHeightSM?: number;
    /** 大号控件高度 */
    controlHeightLG?: number;

    // ===== 间距 =====
    /** 外边距 XS（4px） */
    marginXS?: number;
    /** 外边距 SM（8px） */
    marginSM?: number;
    /** 外边距（16px） */
    margin?: number;
    /** 外边距 MD（20px） */
    marginMD?: number;
    /** 外边距 LG（24px） */
    marginLG?: number;
    /** 外边距 XL（32px） */
    marginXL?: number;

    /** 内边距 XS（4px） */
    paddingXS?: number;
    /** 内边距 SM（8px） */
    paddingSM?: number;
    /** 内边距（16px） */
    padding?: number;
    /** 内边距 MD（20px） */
    paddingMD?: number;
    /** 内边距 LG（24px） */
    paddingLG?: number;
    /** 内边距 XL（32px） */
    paddingXL?: number;

    // ===== 字体 =====
    /** 基础字号（默认 14px，用于正文和大多数组件） */
    fontSize?: number;
    /** 小号字号（默认 12px，用于辅助文本、标签等） */
    fontSizeSM?: number;
    /** 大号字号（默认 16px，用于标题、强调文本等） */
    fontSizeLG?: number;
    /** 字体家族 */
    fontFamily?: string;

    // ===== 阴影 =====
    /** 基础阴影（用于下拉菜单、弹窗等） */
    boxShadow?: string;
    /** 次要阴影（用于悬停状态等） */
    boxShadowSecondary?: string;

    // ===== 动画 =====
    /** 动画时长（快速，默认 100ms） */
    motionDurationFast?: number;
    /** 动画时长（中等，默认 200ms） */
    motionDurationMid?: number;
    /** 动画时长（慢速，默认 300ms） */
    motionDurationSlow?: number;
    /** 动画缓动函数 */
    motionEaseInOut?: string;
    /** 动画缓动函数（弹出） */
    motionEaseOut?: string;

    // ===== 层级 =====
    /** 基础 z-index */
    zIndexBase?: number;
    /** 弹出层 z-index */
    zIndexPopup?: number;
}

/** ConfigProvider 组件 Props */
export interface ConfigProviderProps {
    /** 主题配置 */
    theme?: {
        /** Design Token */
        token?: ThemeToken;
    };
    /**
     * 弹出层容器配置
     * - true: 自动创建内置 Teleport 容器（推荐）
     * - false/undefined: 使用 document.body
     */
    getPopupContainer?: boolean;
    /**
     * 国际化配置
     * - 默认为中文简体 (zh-CN)
     * - 可传入 enUS 切换为英文
     *
     * @example
     * ```vue
     * <ConfigProvider :locale="enUS">
     *   <App />
     * </ConfigProvider>
     * ```
     */
    locale?: Locale;
}

/** 注入的配置上下文类型 */
export interface ConfigProviderContext {
    /** 主题 Token */
    token: ThemeToken;
}

/** ConfigProvider 注入 Key */
export const CONFIG_PROVIDER_KEY = Symbol("vortConfigProvider");
