<script setup lang="ts">
import { ref, computed, provide, watch, onMounted, nextTick, reactive, type Slot } from "vue";
import { CloseOutlined, PlusOutlined } from "@/components/vort/icons";

defineOptions({ name: "VortTabs" });

/** Vort Tabs - 标签页组件 */

type TabsType = "line" | "card" | "editable-card";
type TabsPosition = "top" | "right" | "bottom" | "left";
type TabsSize = "large" | "middle" | "small";

interface TabItem {
    key: string;
    label: string;
    disabled?: boolean;
    closable?: boolean;
}

interface TabPaneInfo {
    key: string;
    tab: string;
    disabled: boolean;
    closable: boolean;
    tabSlot?: Slot;
    /** 用于 HMR 强制更新的版本号 */
    version?: number;
}

interface Props {
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

const props = withDefaults(defineProps<Props>(), {
    type: "line",
    tabPosition: "top",
    size: "middle",
    centered: false,
    bordered: true,
    animated: true,
    destroyInactiveTabPane: false,
    hideAdd: false,
    hideContent: false
});

const emit = defineEmits<{
    "update:activeKey": [key: string];
    change: [key: string];
    tabClick: [key: string, event: MouseEvent];
    edit: [targetKey: string | MouseEvent, action: "add" | "remove"];
}>();

// 内部状态
const currentKey = ref<string>(props.activeKey ?? props.defaultActiveKey ?? "");
const inkBarStyle = ref<Record<string, string>>({});
const tabNavRef = ref<HTMLElement | null>(null);

// 子组件注册的 panes（通过 provide/inject）
const registeredPanes = reactive<Map<string, TabPaneInfo>>(new Map());
const paneOrder = ref<string[]>([]);

// 注册 TabPane
const registerPane = (key: string, info: TabPaneInfo) => {
    // 使用 reactive 包装，保持响应性
    registeredPanes.set(key, reactive(info));
    if (!paneOrder.value.includes(key)) {
        paneOrder.value.push(key);
    }
    // 初始化第一个 tab
    if (!currentKey.value && paneOrder.value.length === 1) {
        currentKey.value = key;
    }
};

// 注销 TabPane
const unregisterPane = (key: string) => {
    registeredPanes.delete(key);
    const idx = paneOrder.value.indexOf(key);
    if (idx > -1) {
        paneOrder.value.splice(idx, 1);
    }
};

// 更新 TabPane 信息
const updatePane = (key: string, info: Partial<TabPaneInfo>) => {
    const existing = registeredPanes.get(key);
    if (existing) {
        // 更新所有提供的字段
        Object.assign(existing, info);
    }
};

// 收集的 tabPanes 列表
const tabPanes = computed<TabPaneInfo[]>(() => {
    // 优先使用 items 配置
    if (props.items && props.items.length > 0) {
        return props.items.map((item) => ({
            key: item.key,
            tab: item.label,
            disabled: item.disabled ?? false,
            closable: item.closable ?? true
        }));
    }

    // 使用注册的 panes
    return paneOrder.value.map((key) => registeredPanes.get(key)).filter((p): p is TabPaneInfo => p !== undefined);
});

// 监听 activeKey 变化（受控模式）
watch(
    () => props.activeKey,
    (val) => {
        if (val !== undefined) {
            currentKey.value = val;
        }
    }
);

// 更新指示条位置
const updateInkBar = async () => {
    if (props.type !== "line" || !tabNavRef.value) return;
    await nextTick();
    const activeTab = tabNavRef.value.querySelector(".vort-tabs-tab-active") as HTMLElement;
    const navWrap = tabNavRef.value.querySelector(".vort-tabs-nav-wrap") as HTMLElement;

    if (activeTab && navWrap) {
        const isVertical = props.tabPosition === "left" || props.tabPosition === "right";
        const tabRect = activeTab.getBoundingClientRect();
        const wrapRect = navWrap.getBoundingClientRect();

        if (isVertical) {
            inkBarStyle.value = {
                top: `${tabRect.top - wrapRect.top}px`,
                height: `${tabRect.height}px`
            };
        } else {
            inkBarStyle.value = {
                left: `${tabRect.left - wrapRect.left}px`,
                width: `${tabRect.width}px`
            };
        }
    }
};

// 监听激活项变化，更新指示条
watch(currentKey, updateInkBar);
watch(() => props.tabPosition, updateInkBar);
watch(tabPanes, updateInkBar, { deep: true });
onMounted(() => {
    nextTick(updateInkBar);
});

// 切换标签
const handleTabClick = (key: string, event: MouseEvent) => {
    const pane = tabPanes.value.find((p) => p.key === key);
    if (pane?.disabled) return;

    currentKey.value = key;
    emit("update:activeKey", key);
    emit("change", key);
    emit("tabClick", key, event);
};

// 删除标签
const handleRemove = (key: string, event: MouseEvent) => {
    event.stopPropagation();
    emit("edit", key, "remove");
};

// 新增标签
const handleAdd = (event: MouseEvent) => {
    emit("edit", event, "add");
};

// 提供给子组件的上下文
provide("tabsContext", {
    currentKey,
    animated: computed(() => props.animated),
    destroyInactiveTabPane: computed(() => props.destroyInactiveTabPane),
    registerPane,
    unregisterPane,
    updatePane
});

// 容器样式
const containerClasses = computed(() => {
    const classes = ["vort-tabs", `vort-tabs-${props.tabPosition}`, `vort-tabs-${props.type.replace("-", "")}`, `vort-tabs-${props.size}`];
    if (props.centered) classes.push("vort-tabs-centered");
    if (!props.bordered) classes.push("vort-tabs-no-border");
    if (props.class) classes.push(props.class);
    return classes;
});

// 标签间隙
const getTabStyle = (index: number) => {
    if (props.tabBarGutter !== undefined && index < tabPanes.value.length - 1) {
        const isVertical = props.tabPosition === "left" || props.tabPosition === "right";
        return isVertical ? { marginBottom: `${props.tabBarGutter}px` } : { marginRight: `${props.tabBarGutter}px` };
    }
    return undefined;
};
</script>

<template>
    <div :class="containerClasses">
        <!-- 标签栏 -->
        <div class="vort-tabs-nav" ref="tabNavRef">
            <div class="vort-tabs-nav-wrap">
                <div class="vort-tabs-nav-list">
                    <!-- 标签项 -->
                    <div
                        v-for="(pane, index) in tabPanes"
                        :key="pane.key"
                        class="vort-tabs-tab"
                        :class="{
                            'vort-tabs-tab-active': currentKey === pane.key,
                            'vort-tabs-tab-disabled': pane.disabled
                        }"
                        :style="getTabStyle(index)"
                        role="tab"
                        :aria-selected="currentKey === pane.key"
                        :aria-disabled="pane.disabled"
                        :tabindex="pane.disabled ? -1 : 0"
                        @click="handleTabClick(pane.key, $event)"
                        @keydown.enter="handleTabClick(pane.key, $event as any)"
                    >
                        <!-- 自定义标签内容 -->
                        <!-- 优先级: #tab-{key} 插槽 > TabPane 的 #tab 插槽 > tab 属性 -->
                        <slot :name="`tab-${pane.key}`" :tab="pane">
                            <component v-if="pane.tabSlot" :is="() => pane.tabSlot?.()" />
                            <span v-else class="vort-tabs-tab-btn">{{ pane.tab }}</span>
                        </slot>

                        <!-- 关闭按钮 -->
                        <button
                            v-if="type === 'editable-card' && pane.closable !== false"
                            class="vort-tabs-tab-remove"
                            type="button"
                            aria-label="remove"
                            @click="handleRemove(pane.key, $event)"
                        >
                            <CloseOutlined class="vort-tabs-icon-sm" />
                        </button>
                    </div>

                    <!-- 添加按钮 -->
                    <button v-if="type === 'editable-card' && !hideAdd" class="vort-tabs-nav-add" type="button" aria-label="Add tab" @click="handleAdd">
                        <PlusOutlined class="vort-tabs-icon-md" />
                    </button>
                </div>

                <!-- 指示条 (仅 line 类型) -->
                <div v-if="type === 'line'" class="vort-tabs-ink-bar" :style="inkBarStyle" />
            </div>

            <!-- 附加内容 -->
            <div v-if="$slots.tabBarExtraContent" class="vort-tabs-extra-content">
                <slot name="tabBarExtraContent" />
            </div>
        </div>

        <!-- 内容区 -->
        <div v-show="!hideContent" class="vort-tabs-content" :class="{ 'vort-tabs-content-animated': animated }">
            <!-- items 模式下渲染内容 -->
            <template v-if="items && items.length > 0">
                <div
                    v-for="item in items"
                    :key="item.key"
                    v-show="currentKey === item.key"
                    class="vort-tabs-tabpane"
                    :class="{ 'vort-tabs-tabpane-active': currentKey === item.key }"
                    role="tabpanel"
                >
                    <slot :name="item.key" />
                </div>
            </template>

            <!-- slot 模式下渲染 TabPane -->
            <slot v-else />
        </div>
    </div>
</template>

<style scoped>
.vort-tabs {
    display: flex;
    flex-direction: column;
    width: 100%;
    font-size: 14px;
    color: var(--vort-text);
    box-sizing: border-box;
}

/* ========== 位置变体 ========== */
.vort-tabs-left {
    flex-direction: row;
}

.vort-tabs-right {
    flex-direction: row-reverse;
}

.vort-tabs-bottom {
    flex-direction: column-reverse;
}

/* ========== 导航栏 ========== */
.vort-tabs-nav {
    display: flex;
    align-items: center;
    position: relative;
    flex-shrink: 0;
}

/* top/bottom 位置的下划线 */
.vort-tabs-top > .vort-tabs-nav::before,
.vort-tabs-bottom > .vort-tabs-nav::before {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    border-bottom: 1px solid var(--vort-border);
}

.vort-tabs-top > .vort-tabs-nav::before {
    bottom: 0;
}

.vort-tabs-bottom > .vort-tabs-nav::before {
    top: 0;
}

/* left/right 位置的边线 */
.vort-tabs-left > .vort-tabs-nav::before,
.vort-tabs-right > .vort-tabs-nav::before {
    content: "";
    position: absolute;
    top: 0;
    bottom: 0;
    border-right: 1px solid var(--vort-border);
}

.vort-tabs-left > .vort-tabs-nav::before {
    right: 0;
}

.vort-tabs-right > .vort-tabs-nav::before {
    left: 0;
}

/* 垂直布局 */
.vort-tabs-left > .vort-tabs-nav,
.vort-tabs-right > .vort-tabs-nav {
    flex-direction: column;
    min-width: 50px;
}

.vort-tabs-nav-wrap {
    position: relative;
    display: flex;
    flex: auto;
    overflow: hidden;
    white-space: nowrap;
}

.vort-tabs-left .vort-tabs-nav-wrap,
.vort-tabs-right .vort-tabs-nav-wrap {
    flex-direction: column;
}

.vort-tabs-nav-list {
    display: flex;
    position: relative;
    transition: transform 0.3s;
}

.vort-tabs-left .vort-tabs-nav-list,
.vort-tabs-right .vort-tabs-nav-list {
    flex-direction: column;
}

/* 居中 */
.vort-tabs-centered > .vort-tabs-nav .vort-tabs-nav-wrap {
    justify-content: center;
}

/* 无边框 */
.vort-tabs-no-border > .vort-tabs-nav::before {
    display: none;
}

/* ========== 标签项 ========== */
.vort-tabs-tab {
    display: inline-flex;
    align-items: center;
    position: relative;
    padding: 12px 0;
    margin: 0 32px 0 0;
    font-size: 14px;
    cursor: pointer;
    color: var(--vort-text);
    background: transparent;
    border: 0;
    outline: none;
    transition: color 0.2s;
    font-weight: bold;
}

.vort-tabs-tab:last-child {
    margin-right: 0;
}

.vort-tabs-tab:hover {
    color: var(--vort-primary);
}

.vort-tabs-tab.vort-tabs-tab-active {
    color: var(--vort-primary);
}

.vort-tabs-tab.vort-tabs-tab-disabled {
    color: var(--vort-text-quaternary);
    cursor: not-allowed;
}

.vort-tabs-tab.vort-tabs-tab-disabled:hover {
    color: var(--vort-text-quaternary);
}

.vort-tabs-tab-btn {
    outline: none;
    transition: all 0.2s;
}

/* 垂直模式标签项 */
.vort-tabs-left .vort-tabs-tab,
.vort-tabs-right .vort-tabs-tab {
    margin: 0 0 16px 0;
    padding: 8px 24px;
    text-align: center;
}

.vort-tabs-left .vort-tabs-tab:last-child,
.vort-tabs-right .vort-tabs-tab:last-child {
    margin-bottom: 0;
}

/* ========== 指示条 ========== */
.vort-tabs-ink-bar {
    position: absolute;
    background: var(--vort-primary);
    pointer-events: none;
    transition:
        left 0.3s cubic-bezier(0.645, 0.045, 0.355, 1),
        width 0.3s cubic-bezier(0.645, 0.045, 0.355, 1),
        top 0.3s cubic-bezier(0.645, 0.045, 0.355, 1),
        height 0.3s cubic-bezier(0.645, 0.045, 0.355, 1);
}

/* top/bottom 水平指示条 */
.vort-tabs-top .vort-tabs-ink-bar {
    bottom: 0;
    height: 2px;
}

.vort-tabs-bottom .vort-tabs-ink-bar {
    top: 0;
    height: 2px;
}

/* left/right 垂直指示条 */
.vort-tabs-left .vort-tabs-ink-bar {
    right: 0;
    width: 2px;
}

.vort-tabs-right .vort-tabs-ink-bar {
    left: 0;
    width: 2px;
}

/* ========== Card 类型 ========== */
.vort-tabs-card .vort-tabs-tab,
.vort-tabs-editablecard .vort-tabs-tab {
    position: relative;
    margin: 0 2px 0 0;
    padding: 8px 16px;
    background: #fafafa;
    background-clip: padding-box;
    /* 背景不延伸到 border 区域 */
    border: 1px solid var(--vort-border);
    border-bottom-color: transparent;
    /* 底边透明，让分隔线显示 */
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px)) var(--vort-border-radius-lg, var(--vort-border-radius, 8px)) 0 0;
    transition: all 0.2s;
}

.vort-tabs-card .vort-tabs-tab:last-child,
.vort-tabs-editablecard .vort-tabs-tab:last-child {
    margin-right: 0;
}

.vort-tabs-card .vort-tabs-tab.vort-tabs-tab-active,
.vort-tabs-editablecard .vort-tabs-tab.vort-tabs-tab-active {
    background: var(--vort-bg-elevated, #fff);
    background-clip: padding-box;
    border-bottom-color: transparent;
}

/* 选中的 tab 用伪元素遮盖分隔线 */
.vort-tabs-card .vort-tabs-tab.vort-tabs-tab-active::after,
.vort-tabs-editablecard .vort-tabs-tab.vort-tabs-tab-active::after {
    content: "";
    position: absolute;
    left: -1px;
    right: -1px;
    bottom: 0;
    height: 1px;
    background: var(--vort-bg-elevated, #fff);
    transform: translateY(100%);
}

/* Editable Card 关闭按钮 */
.vort-tabs-editablecard .vort-tabs-tab {
    padding: 8px 12px;
}

.vort-tabs-tab-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-left: 8px;
    padding: 0;
    width: 16px;
    height: 16px;
    color: var(--vort-text-tertiary);
    background: transparent;
    border: none;
    border-radius: var(--vort-border-radius-sm, 2px);
    cursor: pointer;
    transition: all 0.2s;
}

.vort-tabs-icon-sm {
    width: 12px;
    height: 12px;
}

.vort-tabs-icon-md {
    width: 16px;
    height: 16px;
}

.vort-tabs-tab-remove:hover {
    color: var(--vort-text);
    background: rgba(0, 0, 0, 0.06);
}

.vort-tabs-nav-add {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    min-width: 40px;
    height: 40px;
    margin: 0 0 0 2px;
    padding: 0 8px;
    color: var(--vort-text);
    background: #fafafa;
    background-clip: padding-box;
    border: 1px solid var(--vort-border);
    border-bottom-color: transparent;
    /* 底边透明，让分隔线显示 */
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px)) var(--vort-border-radius-lg, var(--vort-border-radius, 8px)) 0 0;
    cursor: pointer;
    transition: all 0.2s;
}

.vort-tabs-nav-add:hover {
    color: var(--vort-primary);
}

/* ========== 尺寸变体 ========== */
.vort-tabs-large .vort-tabs-tab {
    padding: 16px 0;
    font-size: 16px;
}

.vort-tabs-large.vort-tabs-card .vort-tabs-tab,
.vort-tabs-large.vort-tabs-editablecard .vort-tabs-tab {
    padding: 12px 20px;
}

.vort-tabs-small .vort-tabs-tab {
    padding: 8px 0;
}

.vort-tabs-small.vort-tabs-card .vort-tabs-tab,
.vort-tabs-small.vort-tabs-editablecard .vort-tabs-tab {
    padding: 6px 12px;
}

/* ========== 附加内容 ========== */
.vort-tabs-extra-content {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    margin-left: auto;
    padding-left: 16px;
}

/* ========== 内容区 ========== */
.vort-tabs-content {
    width: 100%;
    padding-top: 16px;
}

.vort-tabs-content-animated .vort-tabs-tabpane {
    transition: opacity 0.3s;
}

.vort-tabs-tabpane {
    outline: none;
}

.vort-tabs-tabpane:not(.vort-tabs-tabpane-active) {
    display: none;
}

/* 垂直模式内容区 */
.vort-tabs-left > .vort-tabs-content,
.vort-tabs-right > .vort-tabs-content {
    flex: auto;
    min-width: 0;
    min-height: 0;
    margin-left: 0;
    padding: 0 0 0 24px;
}

.vort-tabs-right > .vort-tabs-content {
    padding: 0 24px 0 0;
}
</style>
