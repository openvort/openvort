import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import Tabs from "./Tabs.vue";
import TabPane from "./TabPane.vue";

describe("Tabs 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染 Tabs 容器", () => {
            const wrapper = mount(Tabs);
            expect(wrapper.find(".vort-tabs").exists()).toBe(true);
        });

        it("应该有正确的基础类名", () => {
            const wrapper = mount(Tabs);
            expect(wrapper.classes()).toContain("vort-tabs");
        });

        it("应该渲染导航栏和内容区", () => {
            const wrapper = mount(Tabs);
            expect(wrapper.find(".vort-tabs-nav").exists()).toBe(true);
            expect(wrapper.find(".vort-tabs-content").exists()).toBe(true);
        });
    });

    // ==================== 配置式 items ====================
    describe("配置式 items", () => {
        it("应该根据 items 渲染标签", () => {
            const wrapper = mount(Tabs, {
                props: {
                    items: [
                        { key: "1", label: "Tab 1" },
                        { key: "2", label: "Tab 2" },
                        { key: "3", label: "Tab 3" }
                    ]
                }
            });
            const tabs = wrapper.findAll(".vort-tabs-tab");
            expect(tabs).toHaveLength(3);
            expect(tabs[0].text()).toContain("Tab 1");
            expect(tabs[1].text()).toContain("Tab 2");
            expect(tabs[2].text()).toContain("Tab 3");
        });

        it("使用 defaultActiveKey 应该激活对应标签", async () => {
            const wrapper = mount(Tabs, {
                props: {
                    defaultActiveKey: "1",
                    items: [
                        { key: "1", label: "Tab 1" },
                        { key: "2", label: "Tab 2" }
                    ]
                }
            });
            await nextTick();
            const tabs = wrapper.findAll(".vort-tabs-tab");
            expect(tabs[0].classes()).toContain("vort-tabs-tab-active");
        });

        it("禁用的标签应该有禁用类名", () => {
            const wrapper = mount(Tabs, {
                props: {
                    items: [
                        { key: "1", label: "Tab 1" },
                        { key: "2", label: "Tab 2", disabled: true }
                    ]
                }
            });
            const tabs = wrapper.findAll(".vort-tabs-tab");
            expect(tabs[1].classes()).toContain("vort-tabs-tab-disabled");
        });
    });

    // ==================== 插槽式 TabPane ====================
    describe("插槽式 TabPane", () => {
        it("应该渲染 TabPane 子组件", async () => {
            const wrapper = mount(Tabs, {
                slots: {
                    default: [`<TabPane tab-key="1" tab="Tab 1">Content 1</TabPane>`, `<TabPane tab-key="2" tab="Tab 2">Content 2</TabPane>`].join("")
                },
                global: {
                    components: { TabPane }
                }
            });
            await nextTick();
            await nextTick(); // 等待注册完成
            const tabs = wrapper.findAll(".vort-tabs-tab");
            expect(tabs).toHaveLength(2);
        });

        it("TabPane 内容应该正确显示", async () => {
            const wrapper = mount(Tabs, {
                slots: {
                    default: `
                        <TabPane tab-key="1" tab="Tab 1">Content 1</TabPane>
                        <TabPane tab-key="2" tab="Tab 2">Content 2</TabPane>
                    `
                },
                global: {
                    components: { TabPane }
                }
            });
            await nextTick();
            await nextTick();
            const panes = wrapper.findAll(".vort-tabs-tabpane");
            expect(panes.length).toBeGreaterThan(0);
        });
    });

    // ==================== 类型 type ====================
    describe("类型 type", () => {
        it("默认类型应该是 line", () => {
            const wrapper = mount(Tabs);
            expect(wrapper.classes()).toContain("vort-tabs-line");
        });

        it.each(["line", "card", "editable-card"] as const)('类型 "%s" 应该添加对应类名', (type) => {
            const wrapper = mount(Tabs, {
                props: { type }
            });
            // editable-card 转换为 editablecard
            const expectedClass = `vort-tabs-${type.replace("-", "")}`;
            expect(wrapper.classes()).toContain(expectedClass);
        });

        it("editable-card 类型应该显示关闭按钮", () => {
            const wrapper = mount(Tabs, {
                props: {
                    type: "editable-card",
                    items: [{ key: "1", label: "Tab 1" }]
                }
            });
            expect(wrapper.find(".vort-tabs-tab-remove").exists()).toBe(true);
        });

        it("editable-card 类型应该显示添加按钮", () => {
            const wrapper = mount(Tabs, {
                props: {
                    type: "editable-card",
                    items: [{ key: "1", label: "Tab 1" }]
                }
            });
            expect(wrapper.find(".vort-tabs-nav-add").exists()).toBe(true);
        });

        it("hideAdd 为 true 时不应该显示添加按钮", () => {
            const wrapper = mount(Tabs, {
                props: {
                    type: "editable-card",
                    hideAdd: true,
                    items: [{ key: "1", label: "Tab 1" }]
                }
            });
            expect(wrapper.find(".vort-tabs-nav-add").exists()).toBe(false);
        });
    });

    // ==================== 位置 tabPosition ====================
    describe("位置 tabPosition", () => {
        it("默认位置应该是 top", () => {
            const wrapper = mount(Tabs);
            expect(wrapper.classes()).toContain("vort-tabs-top");
        });

        it.each(["top", "right", "bottom", "left"] as const)('位置 "%s" 应该添加对应类名', (tabPosition) => {
            const wrapper = mount(Tabs, {
                props: { tabPosition }
            });
            expect(wrapper.classes()).toContain(`vort-tabs-${tabPosition}`);
        });
    });

    // ==================== 尺寸 size ====================
    describe("尺寸 size", () => {
        it("默认尺寸应该是 middle", () => {
            const wrapper = mount(Tabs);
            expect(wrapper.classes()).toContain("vort-tabs-middle");
        });

        it.each(["large", "middle", "small"] as const)('尺寸 "%s" 应该添加对应类名', (size) => {
            const wrapper = mount(Tabs, {
                props: { size }
            });
            expect(wrapper.classes()).toContain(`vort-tabs-${size}`);
        });
    });

    // ==================== 居中 centered ====================
    describe("居中 centered", () => {
        it("默认不应该居中", () => {
            const wrapper = mount(Tabs);
            expect(wrapper.classes()).not.toContain("vort-tabs-centered");
        });

        it("centered 为 true 时应该添加居中类名", () => {
            const wrapper = mount(Tabs, {
                props: { centered: true }
            });
            expect(wrapper.classes()).toContain("vort-tabs-centered");
        });
    });

    // ==================== 边框 bordered ====================
    describe("边框 bordered", () => {
        it("默认应该有边框", () => {
            const wrapper = mount(Tabs);
            expect(wrapper.classes()).not.toContain("vort-tabs-no-border");
        });

        it("bordered 为 false 时应该添加无边框类名", () => {
            const wrapper = mount(Tabs, {
                props: { bordered: false }
            });
            expect(wrapper.classes()).toContain("vort-tabs-no-border");
        });
    });

    // ==================== 隐藏内容 hideContent ====================
    describe("隐藏内容 hideContent", () => {
        it("默认应该显示内容区", () => {
            const wrapper = mount(Tabs);
            const content = wrapper.find(".vort-tabs-content");
            expect(content.isVisible()).toBe(true);
        });

        it("hideContent 为 true 时内容区应该隐藏", () => {
            const wrapper = mount(Tabs, {
                props: { hideContent: true }
            });
            const content = wrapper.find(".vort-tabs-content");
            expect(content.isVisible()).toBe(false);
        });
    });

    // ==================== 动画 animated ====================
    describe("动画 animated", () => {
        it("默认应该启用动画", () => {
            const wrapper = mount(Tabs);
            expect(wrapper.find(".vort-tabs-content-animated").exists()).toBe(true);
        });

        it("animated 为 false 时不应该有动画类名", () => {
            const wrapper = mount(Tabs, {
                props: { animated: false }
            });
            expect(wrapper.find(".vort-tabs-content-animated").exists()).toBe(false);
        });
    });

    // ==================== activeKey 受控 ====================
    describe("activeKey 受控", () => {
        it("应该根据 activeKey 激活对应标签", async () => {
            const wrapper = mount(Tabs, {
                props: {
                    activeKey: "2",
                    items: [
                        { key: "1", label: "Tab 1" },
                        { key: "2", label: "Tab 2" }
                    ]
                }
            });
            await nextTick();
            const tabs = wrapper.findAll(".vort-tabs-tab");
            expect(tabs[1].classes()).toContain("vort-tabs-tab-active");
        });

        it("defaultActiveKey 应该设置初始激活标签", async () => {
            const wrapper = mount(Tabs, {
                props: {
                    defaultActiveKey: "2",
                    items: [
                        { key: "1", label: "Tab 1" },
                        { key: "2", label: "Tab 2" }
                    ]
                }
            });
            await nextTick();
            const tabs = wrapper.findAll(".vort-tabs-tab");
            expect(tabs[1].classes()).toContain("vort-tabs-tab-active");
        });
    });

    // ==================== 点击事件 ====================
    describe("点击事件", () => {
        it("点击标签应该触发 change 事件", async () => {
            const wrapper = mount(Tabs, {
                props: {
                    items: [
                        { key: "1", label: "Tab 1" },
                        { key: "2", label: "Tab 2" }
                    ]
                }
            });
            await nextTick();
            const tabs = wrapper.findAll(".vort-tabs-tab");
            await tabs[1].trigger("click");
            expect(wrapper.emitted("change")).toBeTruthy();
            expect(wrapper.emitted("change")![0]).toEqual(["2"]);
        });

        it("点击标签应该触发 update:activeKey 事件", async () => {
            const wrapper = mount(Tabs, {
                props: {
                    items: [
                        { key: "1", label: "Tab 1" },
                        { key: "2", label: "Tab 2" }
                    ]
                }
            });
            await nextTick();
            const tabs = wrapper.findAll(".vort-tabs-tab");
            await tabs[1].trigger("click");
            expect(wrapper.emitted("update:activeKey")).toBeTruthy();
            expect(wrapper.emitted("update:activeKey")![0]).toEqual(["2"]);
        });

        it("点击标签应该触发 tabClick 事件", async () => {
            const wrapper = mount(Tabs, {
                props: {
                    items: [
                        { key: "1", label: "Tab 1" },
                        { key: "2", label: "Tab 2" }
                    ]
                }
            });
            await nextTick();
            const tabs = wrapper.findAll(".vort-tabs-tab");
            await tabs[1].trigger("click");
            expect(wrapper.emitted("tabClick")).toBeTruthy();
            const emitted = wrapper.emitted("tabClick")![0];
            expect(emitted[0]).toBe("2");
            expect(emitted[1]).toBeInstanceOf(MouseEvent);
        });

        it("点击禁用的标签不应该触发事件", async () => {
            const wrapper = mount(Tabs, {
                props: {
                    items: [
                        { key: "1", label: "Tab 1" },
                        { key: "2", label: "Tab 2", disabled: true }
                    ]
                }
            });
            await nextTick();
            const tabs = wrapper.findAll(".vort-tabs-tab");
            await tabs[1].trigger("click");
            expect(wrapper.emitted("change")).toBeFalsy();
        });
    });

    // ==================== 编辑事件（editable-card） ====================
    describe("编辑事件", () => {
        it("点击关闭按钮应该触发 edit 事件", async () => {
            const wrapper = mount(Tabs, {
                props: {
                    type: "editable-card",
                    items: [{ key: "1", label: "Tab 1" }]
                }
            });
            const removeBtn = wrapper.find(".vort-tabs-tab-remove");
            await removeBtn.trigger("click");
            expect(wrapper.emitted("edit")).toBeTruthy();
            const emitted = wrapper.emitted("edit")![0];
            expect(emitted[0]).toBe("1");
            expect(emitted[1]).toBe("remove");
        });

        it("点击添加按钮应该触发 edit 事件", async () => {
            const wrapper = mount(Tabs, {
                props: {
                    type: "editable-card",
                    items: [{ key: "1", label: "Tab 1" }]
                }
            });
            const addBtn = wrapper.find(".vort-tabs-nav-add");
            await addBtn.trigger("click");
            expect(wrapper.emitted("edit")).toBeTruthy();
            const emitted = wrapper.emitted("edit")![0];
            expect(emitted[0]).toBeInstanceOf(MouseEvent);
            expect(emitted[1]).toBe("add");
        });

        it("closable 为 false 的标签不应该显示关闭按钮", () => {
            const wrapper = mount(Tabs, {
                props: {
                    type: "editable-card",
                    items: [
                        { key: "1", label: "Tab 1", closable: false },
                        { key: "2", label: "Tab 2" }
                    ]
                }
            });
            const tabs = wrapper.findAll(".vort-tabs-tab");
            expect(tabs[0].find(".vort-tabs-tab-remove").exists()).toBe(false);
            expect(tabs[1].find(".vort-tabs-tab-remove").exists()).toBe(true);
        });
    });

    // ==================== tabBarGutter ====================
    describe("tabBarGutter", () => {
        it("应该设置标签间隙样式", () => {
            const wrapper = mount(Tabs, {
                props: {
                    tabBarGutter: 20,
                    items: [
                        { key: "1", label: "Tab 1" },
                        { key: "2", label: "Tab 2" }
                    ]
                }
            });
            const tab = wrapper.find(".vort-tabs-tab");
            expect(tab.attributes("style")).toContain("margin-right: 20px");
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", () => {
            const wrapper = mount(Tabs, {
                props: { class: "my-custom-tabs" }
            });
            expect(wrapper.classes()).toContain("my-custom-tabs");
        });
    });

    // ==================== 附加内容插槽 ====================
    describe("附加内容插槽", () => {
        it("应该渲染 tabBarExtraContent 插槽", () => {
            const wrapper = mount(Tabs, {
                slots: {
                    tabBarExtraContent: "<button>Extra</button>"
                }
            });
            expect(wrapper.find(".vort-tabs-extra-content").exists()).toBe(true);
            expect(wrapper.find(".vort-tabs-extra-content button").exists()).toBe(true);
        });
    });

    // ==================== 无障碍属性 ====================
    describe("无障碍属性", () => {
        it("标签应该有正确的 role 属性", () => {
            const wrapper = mount(Tabs, {
                props: {
                    items: [{ key: "1", label: "Tab 1" }]
                }
            });
            const tab = wrapper.find(".vort-tabs-tab");
            expect(tab.attributes("role")).toBe("tab");
        });

        it("激活的标签应该有 aria-selected 为 true", async () => {
            const wrapper = mount(Tabs, {
                props: {
                    activeKey: "1",
                    items: [
                        { key: "1", label: "Tab 1" },
                        { key: "2", label: "Tab 2" }
                    ]
                }
            });
            await nextTick();
            const tabs = wrapper.findAll(".vort-tabs-tab");
            expect(tabs[0].attributes("aria-selected")).toBe("true");
            expect(tabs[1].attributes("aria-selected")).toBe("false");
        });

        it("禁用的标签应该有 aria-disabled 为 true", () => {
            const wrapper = mount(Tabs, {
                props: {
                    items: [{ key: "1", label: "Tab 1", disabled: true }]
                }
            });
            const tab = wrapper.find(".vort-tabs-tab");
            expect(tab.attributes("aria-disabled")).toBe("true");
        });

        it("内容面板应该有正确的 role 属性", () => {
            const wrapper = mount(Tabs, {
                props: {
                    items: [{ key: "1", label: "Tab 1" }]
                }
            });
            const pane = wrapper.find(".vort-tabs-tabpane");
            expect(pane.attributes("role")).toBe("tabpanel");
        });
    });
});

describe("TabPane 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该在 Tabs 内正确渲染", async () => {
            const wrapper = mount(Tabs, {
                slots: {
                    default: `<TabPane tab-key="1" tab="Tab 1">Content</TabPane>`
                },
                global: {
                    components: { TabPane }
                }
            });
            await nextTick();
            await nextTick();
            expect(wrapper.find(".vort-tabs-tabpane").exists()).toBe(true);
        });

        it("应该渲染插槽内容", async () => {
            const wrapper = mount(Tabs, {
                slots: {
                    default: `<TabPane tab-key="1" tab="Tab 1">Hello World</TabPane>`
                },
                global: {
                    components: { TabPane }
                }
            });
            await nextTick();
            await nextTick();
            expect(wrapper.text()).toContain("Hello World");
        });
    });

    // ==================== 激活状态 ====================
    describe("激活状态", () => {
        it("激活的面板应该有 active 类名", async () => {
            const wrapper = mount(Tabs, {
                slots: {
                    default: `
                        <TabPane tab-key="1" tab="Tab 1">Content 1</TabPane>
                        <TabPane tab-key="2" tab="Tab 2">Content 2</TabPane>
                    `
                },
                global: {
                    components: { TabPane }
                }
            });
            await nextTick();
            await nextTick();
            const panes = wrapper.findAll(".vort-tabs-tabpane");
            expect(panes[0].classes()).toContain("vort-tabs-tabpane-active");
        });
    });

    // ==================== 禁用状态 ====================
    describe("禁用状态", () => {
        it("禁用的 TabPane 对应的标签应该有禁用类名", async () => {
            const wrapper = mount(Tabs, {
                slots: {
                    default: `
                        <TabPane tab-key="1" tab="Tab 1">Content 1</TabPane>
                        <TabPane tab-key="2" tab="Tab 2" disabled>Content 2</TabPane>
                    `
                },
                global: {
                    components: { TabPane }
                }
            });
            await nextTick();
            await nextTick();
            const tabs = wrapper.findAll(".vort-tabs-tab");
            expect(tabs[1].classes()).toContain("vort-tabs-tab-disabled");
        });
    });

    // ==================== 无障碍属性 ====================
    describe("无障碍属性", () => {
        it("面板应该有正确的 role 属性", async () => {
            const wrapper = mount(Tabs, {
                slots: {
                    default: `<TabPane tab-key="1" tab="Tab 1">Content</TabPane>`
                },
                global: {
                    components: { TabPane }
                }
            });
            await nextTick();
            await nextTick();
            const pane = wrapper.find(".vort-tabs-tabpane");
            expect(pane.attributes("role")).toBe("tabpanel");
        });

        it("激活的面板 tabindex 应该为 0", async () => {
            const wrapper = mount(Tabs, {
                slots: {
                    default: `<TabPane tab-key="1" tab="Tab 1">Content</TabPane>`
                },
                global: {
                    components: { TabPane }
                }
            });
            await nextTick();
            await nextTick();
            const pane = wrapper.find(".vort-tabs-tabpane-active");
            expect(pane.attributes("tabindex")).toBe("0");
        });
    });
});
