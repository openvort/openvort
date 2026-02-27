<script setup lang="ts">
import { inject, computed, onMounted, onUnmounted, watch, useSlots, ref, type Ref, type ComputedRef, type Slot } from "vue";

defineOptions({ name: "VortTabPane" });

/** Vort TabPane - 标签面板组件 */

interface TabPaneInfo {
    key: string;
    tab: string;
    disabled: boolean;
    closable: boolean;
    tabSlot?: Slot;
    /** 用于强制更新的版本号 */
    version?: number;
}

interface Props {
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

const props = withDefaults(defineProps<Props>(), {
    tab: "",
    disabled: false,
    closable: true,
    forceRender: false
});

const slots = useSlots();

// 版本计数器，用于 HMR 时强制更新
const slotVersion = ref(0);

// 创建 slot 包装器，确保每次调用都能获取最新的 slot 内容
const createTabSlotWrapper = (): Slot | undefined => {
    if (!slots.tab) return undefined;
    // 返回一个新的包装函数，调用时总是使用最新的 slots.tab
    return (...args: Parameters<Slot>) => slots.tab?.(...args) ?? [];
};

// 获取父级上下文
interface TabsContext {
    currentKey: Ref<string>;
    animated: ComputedRef<boolean>;
    destroyInactiveTabPane: ComputedRef<boolean>;
    registerPane: (key: string, info: TabPaneInfo) => void;
    unregisterPane: (key: string) => void;
    updatePane: (key: string, info: Partial<TabPaneInfo>) => void;
}

const tabsContext = inject<TabsContext>("tabsContext");

// 获取当前 pane 的信息
const getPaneInfo = (): TabPaneInfo => ({
    key: props.tabKey,
    tab: props.tab,
    disabled: props.disabled,
    closable: props.closable,
    tabSlot: createTabSlotWrapper(),
    version: slotVersion.value
});

// 挂载时注册
onMounted(() => {
    if (tabsContext?.registerPane) {
        tabsContext.registerPane(props.tabKey, getPaneInfo());
    }
});

// 卸载时注销
onUnmounted(() => {
    if (tabsContext?.unregisterPane) {
        tabsContext.unregisterPane(props.tabKey);
    }
});

// 监听 props 变化，更新注册信息
watch(
    () => [props.tab, props.disabled, props.closable],
    () => {
        if (tabsContext?.updatePane) {
            tabsContext.updatePane(props.tabKey, getPaneInfo());
        }
    }
);

// 支持 HMR 热更新：监听开发环境的模块热替换
if (import.meta.hot) {
    import.meta.hot.accept(() => {
        // HMR 更新时递增版本号，强制 Tabs 重新渲染 slot
        slotVersion.value++;
        if (tabsContext?.updatePane) {
            tabsContext.updatePane(props.tabKey, {
                tabSlot: createTabSlotWrapper(),
                version: slotVersion.value
            });
        }
    });
}

// 是否激活
const isActive = computed(() => {
    return tabsContext?.currentKey.value === props.tabKey;
});

// 是否应该渲染
const shouldRender = computed(() => {
    if (props.forceRender) return true;
    if (tabsContext?.destroyInactiveTabPane.value) {
        return isActive.value;
    }
    return true; // 默认保留 DOM
});

// 面板样式
const paneClasses = computed(() => {
    const classes = ["vort-tabs-tabpane"];
    if (isActive.value) classes.push("vort-tabs-tabpane-active");
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <div v-if="shouldRender" v-show="isActive" :class="paneClasses" role="tabpanel" :tabindex="isActive ? 0 : -1" :aria-hidden="!isActive">
        <slot />
    </div>
</template>

<style scoped>
.vort-tabs-tabpane {
    outline: none;
}

.vort-tabs-tabpane:not(.vort-tabs-tabpane-active) {
    display: none;
}
</style>
