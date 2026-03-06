/**
 * Tabs 组件类型定义
 */

import type { Slot } from "vue";

/** 标签页样式类型 */
export type TabsType = "line" | "card" | "editable-card";

/** 标签页位置 */
export type TabsPosition = "top" | "right" | "bottom" | "left";

/** 标签页尺寸 */
export type TabsSize = "large" | "middle" | "small";

/** 编辑操作类型 */
export type TabsEditAction = "add" | "remove";

/** 标签项配置（配置式用法） */
export interface TabItem {
    /** 标签唯一标识 */
    key: string;
    /** 标签显示文字 */
    label: string;
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否可关闭（editable-card 类型时有效） */
    closable?: boolean;
}

/** 内部标签面板信息 */
export interface TabPaneInfo {
    /** 面板唯一标识 */
    key: string;
    /** 标签显示文字 */
    tab: string;
    /** 是否禁用 */
    disabled: boolean;
    /** 是否可关闭 */
    closable: boolean;
    /** 自定义标签插槽 */
    tabSlot?: Slot;
    /** 用于 HMR 强制更新的版本号 */
    version?: number;
}

/** Tabs 组件 Props */
export interface TabsProps {
    /** 当前激活 tab 面板的 key */
    activeKey?: string;
    /** 初始化选中面板的 key，如果没有设置 activeKey */
    defaultActiveKey?: string;
    /** 页签的基本样式 */
    type?: TabsType;
    /** 页签位置 */
    tabPosition?: TabsPosition;
    /** 大小，提供 large middle 和 small 三种大小 */
    size?: TabsSize;
    /** 标签居中展示 */
    centered?: boolean;
    /** 是否显示边框线 */
    bordered?: boolean;
    /** tabs 之间的间隙 */
    tabBarGutter?: number;
    /** 是否使用动画切换 Tabs */
    animated?: boolean;
    /** 被隐藏时是否销毁 DOM 结构 */
    destroyInactiveTabPane?: boolean;
    /** 是否隐藏添加按钮（type="editable-card" 时有效） */
    hideAdd?: boolean;
    /** 配置式标签项 */
    items?: TabItem[];
    /** 隐藏内容区域，仅显示标签栏（用于只需要 tab 导航条的场景） */
    hideContent?: boolean;
    /** 自定义类名 */
    class?: string;
}

/** Tabs 组件 Emits */
export interface TabsEmits {
    /** 更新激活的 key（v-model:activeKey） */
    (e: "update:activeKey", key: string): void;
    /** 切换面板的回调 */
    (e: "change", key: string): void;
    /** tab 被点击的回调 */
    (e: "tabClick", key: string, event: MouseEvent): void;
    /** 新增和删除页签的回调（editable-card 类型时有效） */
    (e: "edit", targetKey: string | MouseEvent, action: TabsEditAction): void;
}

/** TabPane 组件 Props */
export interface TabPaneProps {
    /** 面板的 key，对应 activeKey */
    tabKey: string;
    /** 选项卡头显示文字 */
    tab?: string;
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否可关闭（editable-card 类型时可用） */
    closable?: boolean;
    /** 强制渲染，即使未激活也渲染 DOM */
    forceRender?: boolean;
    /** 自定义类名 */
    class?: string;
}
