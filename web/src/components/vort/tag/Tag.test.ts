import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import Tag from "./Tag.vue";
import CheckableTag from "./CheckableTag.vue";

describe("Tag 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染标签文字", () => {
            const wrapper = mount(Tag, {
                slots: { default: "标签" }
            });
            expect(wrapper.text()).toBe("标签");
        });

        it("应该渲染为 span 元素", () => {
            const wrapper = mount(Tag);
            expect(wrapper.element.tagName).toBe("SPAN");
        });

        it("应该有正确的基础类名", () => {
            const wrapper = mount(Tag);
            expect(wrapper.classes()).toContain("vort-tag");
        });
    });

    // ==================== 颜色（color） ====================
    describe("颜色 color", () => {
        describe("预设状态颜色", () => {
            it.each(["success", "processing", "error", "warning", "default"] as const)('预设状态颜色 "%s" 应该添加对应类名', (color) => {
                const wrapper = mount(Tag, {
                    props: { color }
                });
                expect(wrapper.classes()).toContain(`vort-tag-${color}`);
            });
        });

        describe("预设颜色", () => {
            it.each(["magenta", "red", "volcano", "orange", "gold", "lime", "green", "cyan", "teal", "blue", "geekblue", "purple"] as const)(
                '预设颜色 "%s" 应该添加对应类名',
                (color) => {
                    const wrapper = mount(Tag, {
                        props: { color }
                    });
                    expect(wrapper.classes()).toContain(`vort-tag-${color}`);
                }
            );
        });

        describe("自定义颜色", () => {
            it("自定义颜色应该添加 custom 类名", () => {
                const wrapper = mount(Tag, {
                    props: { color: "#ff0000" }
                });
                expect(wrapper.classes()).toContain("vort-tag-custom");
            });

            it("自定义颜色应该设置 CSS 变量", () => {
                const wrapper = mount(Tag, {
                    props: { color: "#ff0000" }
                });
                const style = wrapper.attributes("style");
                expect(style).toContain("--_tag-bg: #ff0000");
            });
        });
    });

    // ==================== 可关闭（closable） ====================
    describe("可关闭 closable", () => {
        it("默认不显示关闭按钮", () => {
            const wrapper = mount(Tag);
            expect(wrapper.find(".vort-tag-close").exists()).toBe(false);
        });

        it("closable 为 true 时应该显示关闭按钮", () => {
            const wrapper = mount(Tag, {
                props: { closable: true }
            });
            expect(wrapper.find(".vort-tag-close").exists()).toBe(true);
        });

        it("点击关闭按钮应该触发 close 事件", async () => {
            const wrapper = mount(Tag, {
                props: { closable: true }
            });
            await wrapper.find(".vort-tag-close").trigger("click");
            expect(wrapper.emitted("close")).toHaveLength(1);
        });

        it("close 事件应该传递 MouseEvent", async () => {
            const wrapper = mount(Tag, {
                props: { closable: true }
            });
            await wrapper.find(".vort-tag-close").trigger("click");
            const emitted = wrapper.emitted("close");
            expect(emitted).toBeTruthy();
            expect(emitted![0]![0]).toBeInstanceOf(MouseEvent);
        });
    });

    // ==================== 边框（bordered） ====================
    describe("边框 bordered", () => {
        it("默认应该有边框", () => {
            const wrapper = mount(Tag);
            expect(wrapper.classes()).not.toContain("vort-tag-borderless");
        });

        it("bordered 为 false 时应该添加无边框类名", () => {
            const wrapper = mount(Tag, {
                props: { bordered: false }
            });
            expect(wrapper.classes()).toContain("vort-tag-borderless");
        });
    });

    // ==================== 简易样式（plain） ====================
    describe("简易样式 plain", () => {
        it("默认不应该有 plain 类名", () => {
            const wrapper = mount(Tag);
            expect(wrapper.classes()).not.toContain("vort-tag-plain");
        });

        it("plain 为 true 时应该添加对应类名", () => {
            const wrapper = mount(Tag, {
                props: { plain: true }
            });
            expect(wrapper.classes()).toContain("vort-tag-plain");
        });
    });

    // ==================== 白色背景（white） ====================
    describe("白色背景 white", () => {
        it("默认不应该有 white 类名", () => {
            const wrapper = mount(Tag);
            expect(wrapper.classes()).not.toContain("vort-tag-white");
        });

        it("white 为 true 时应该添加对应类名", () => {
            const wrapper = mount(Tag, {
                props: { white: true }
            });
            expect(wrapper.classes()).toContain("vort-tag-white");
        });
    });

    // ==================== 实心模式（solid） ====================
    describe("实心模式 solid", () => {
        it("默认不应该有 solid 类名", () => {
            const wrapper = mount(Tag);
            expect(wrapper.classes()).not.toContain("vort-tag-solid");
        });

        it("solid 为 true 时应该添加对应类名", () => {
            const wrapper = mount(Tag, {
                props: { solid: true }
            });
            expect(wrapper.classes()).toContain("vort-tag-solid");
        });
    });

    // ==================== 尺寸（size） ====================
    describe("尺寸 size", () => {
        it("默认尺寸应该是 default", () => {
            const wrapper = mount(Tag);
            expect(wrapper.classes()).toContain("vort-tag-default");
        });

        it('size 为 "small" 时应该添加对应类名', () => {
            const wrapper = mount(Tag, {
                props: { size: "small" }
            });
            expect(wrapper.classes()).toContain("vort-tag-small");
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", () => {
            const wrapper = mount(Tag, {
                props: { class: "my-custom-class" }
            });
            expect(wrapper.classes()).toContain("my-custom-class");
        });
    });

    // ==================== 插槽 ====================
    describe("插槽", () => {
        it("应该渲染默认插槽内容", () => {
            const wrapper = mount(Tag, {
                slots: { default: "测试内容" }
            });
            expect(wrapper.text()).toContain("测试内容");
        });

        it("应该渲染 icon 插槽", () => {
            const wrapper = mount(Tag, {
                slots: {
                    default: "标签",
                    icon: '<span class="custom-icon">★</span>'
                }
            });
            expect(wrapper.find(".vort-tag-icon").exists()).toBe(true);
            expect(wrapper.find(".custom-icon").exists()).toBe(true);
        });

        it("应该渲染 closeIcon 插槽", () => {
            const wrapper = mount(Tag, {
                props: { closable: true },
                slots: {
                    closeIcon: '<span class="custom-close">×</span>'
                }
            });
            expect(wrapper.find(".custom-close").exists()).toBe(true);
        });
    });
});

describe("CheckableTag 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染标签文字", () => {
            const wrapper = mount(CheckableTag, {
                slots: { default: "可选标签" }
            });
            expect(wrapper.text()).toBe("可选标签");
        });

        it("应该渲染为 span 元素", () => {
            const wrapper = mount(CheckableTag);
            expect(wrapper.element.tagName).toBe("SPAN");
        });

        it("应该有正确的基础类名", () => {
            const wrapper = mount(CheckableTag);
            expect(wrapper.classes()).toContain("vort-checkable-tag");
        });
    });

    // ==================== 选中状态（checked） ====================
    describe("选中状态 checked", () => {
        it("默认应该不是选中状态", () => {
            const wrapper = mount(CheckableTag);
            expect(wrapper.classes()).not.toContain("vort-checkable-tag-checked");
        });

        it("checked 为 true 时应该添加选中类名", () => {
            const wrapper = mount(CheckableTag, {
                props: { checked: true }
            });
            expect(wrapper.classes()).toContain("vort-checkable-tag-checked");
        });
    });

    // ==================== 点击事件 ====================
    describe("点击事件", () => {
        it("点击应该触发 change 事件", async () => {
            const wrapper = mount(CheckableTag);
            await wrapper.trigger("click");
            expect(wrapper.emitted("change")).toHaveLength(1);
        });

        it("点击未选中标签应该传递 true", async () => {
            const wrapper = mount(CheckableTag, {
                props: { checked: false }
            });
            await wrapper.trigger("click");
            const emitted = wrapper.emitted("change");
            expect(emitted![0]).toEqual([true]);
        });

        it("点击已选中标签应该传递 false", async () => {
            const wrapper = mount(CheckableTag, {
                props: { checked: true }
            });
            await wrapper.trigger("click");
            const emitted = wrapper.emitted("change");
            expect(emitted![0]).toEqual([false]);
        });

        it("点击应该触发 update:checked 事件", async () => {
            const wrapper = mount(CheckableTag);
            await wrapper.trigger("click");
            expect(wrapper.emitted("update:checked")).toHaveLength(1);
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", () => {
            const wrapper = mount(CheckableTag, {
                props: { class: "my-custom-class" }
            });
            expect(wrapper.classes()).toContain("my-custom-class");
        });
    });
});
