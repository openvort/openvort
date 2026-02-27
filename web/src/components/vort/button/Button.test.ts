import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import Button from "./Button.vue";

describe("Button 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染按钮文字", () => {
            const wrapper = mount(Button, {
                slots: { default: "点击我" }
            });
            expect(wrapper.text()).toBe("点击我");
        });

        it("应该渲染为 button 元素", () => {
            const wrapper = mount(Button);
            expect(wrapper.element.tagName).toBe("BUTTON");
        });

        it("应该有正确的基础类名", () => {
            const wrapper = mount(Button);
            expect(wrapper.classes()).toContain("vort-btn");
        });
    });

    // ==================== 变体（variant） ====================
    describe("变体 variant", () => {
        it("默认变体应该是 default", () => {
            const wrapper = mount(Button);
            expect(wrapper.classes()).toContain("vort-btn-default");
        });

        it.each(["primary", "default", "dashed", "text", "link", "plain", "soft"] as const)('变体 "%s" 应该添加对应类名', (variant) => {
            const wrapper = mount(Button, {
                props: { variant }
            });
            expect(wrapper.classes()).toContain(`vort-btn-${variant}`);
        });

        it("type 属性应该作为 variant 的别名", () => {
            const wrapper = mount(Button, {
                props: { type: "primary" }
            });
            expect(wrapper.classes()).toContain("vort-btn-primary");
        });

        it("variant 应该优先于 type", () => {
            const wrapper = mount(Button, {
                props: { variant: "dashed", type: "primary" }
            });
            expect(wrapper.classes()).toContain("vort-btn-dashed");
            expect(wrapper.classes()).not.toContain("vort-btn-primary");
        });
    });

    // ==================== 尺寸（size） ====================
    describe("尺寸 size", () => {
        it("默认尺寸应该是 middle", () => {
            const wrapper = mount(Button);
            expect(wrapper.classes()).toContain("vort-btn-middle");
        });

        it.each(["large", "middle", "small"] as const)('尺寸 "%s" 应该添加对应类名', (size) => {
            const wrapper = mount(Button, {
                props: { size }
            });
            expect(wrapper.classes()).toContain(`vort-btn-${size}`);
        });
    });

    // ==================== 形状（shape） ====================
    describe("形状 shape", () => {
        it("默认不应该有形状类名", () => {
            const wrapper = mount(Button);
            expect(wrapper.classes()).not.toContain("vort-btn-round");
            expect(wrapper.classes()).not.toContain("vort-btn-circle");
        });

        it("round 形状应该添加对应类名", () => {
            const wrapper = mount(Button, {
                props: { shape: "round" }
            });
            expect(wrapper.classes()).toContain("vort-btn-round");
        });

        it("circle 形状应该添加对应类名", () => {
            const wrapper = mount(Button, {
                props: { shape: "circle" }
            });
            expect(wrapper.classes()).toContain("vort-btn-circle");
        });
    });

    // ==================== 状态 ====================
    describe("状态", () => {
        it("danger 状态应该添加对应类名", () => {
            const wrapper = mount(Button, {
                props: { danger: true }
            });
            expect(wrapper.classes()).toContain("vort-btn-danger");
        });

        it("ghost 状态应该添加对应类名", () => {
            const wrapper = mount(Button, {
                props: { ghost: true }
            });
            expect(wrapper.classes()).toContain("vort-btn-ghost");
        });

        it("block 状态应该添加对应类名", () => {
            const wrapper = mount(Button, {
                props: { block: true }
            });
            expect(wrapper.classes()).toContain("vort-btn-block");
        });

        it("icon 状态应该添加对应类名", () => {
            const wrapper = mount(Button, {
                props: { icon: true }
            });
            expect(wrapper.classes()).toContain("vort-btn-icon-only");
        });
    });

    // ==================== 禁用状态 ====================
    describe("禁用状态", () => {
        it("disabled 为 true 时按钮应该被禁用", () => {
            const wrapper = mount(Button, {
                props: { disabled: true }
            });
            expect(wrapper.attributes("disabled")).toBeDefined();
            expect(wrapper.classes()).toContain("vort-btn-disabled");
        });

        it("disabled 时点击不应该触发 click 事件", async () => {
            const onClick = vi.fn();
            const wrapper = mount(Button, {
                props: { disabled: true },
                attrs: { onClick }
            });
            await wrapper.trigger("click");
            expect(onClick).not.toHaveBeenCalled();
        });
    });

    // ==================== 加载状态 ====================
    describe("加载状态", () => {
        it("loading 为 true 时应该显示加载图标", () => {
            const wrapper = mount(Button, {
                props: { loading: true }
            });
            expect(wrapper.find(".vort-btn-loading-icon").exists()).toBe(true);
            expect(wrapper.classes()).toContain("vort-btn-loading");
        });

        it("loading 时按钮应该被禁用", () => {
            const wrapper = mount(Button, {
                props: { loading: true }
            });
            expect(wrapper.attributes("disabled")).toBeDefined();
        });

        it("loading 时点击不应该触发 click 事件", async () => {
            const onClick = vi.fn();
            const wrapper = mount(Button, {
                props: { loading: true },
                attrs: { onClick }
            });
            await wrapper.trigger("click");
            expect(onClick).not.toHaveBeenCalled();
        });
    });

    // ==================== 点击事件 ====================
    describe("点击事件", () => {
        it("点击应该触发 click 事件", async () => {
            const wrapper = mount(Button);
            await wrapper.trigger("click");
            expect(wrapper.emitted("click")).toHaveLength(1);
        });

        it("click 事件应该传递 MouseEvent", async () => {
            const wrapper = mount(Button);
            await wrapper.trigger("click");
            const emitted = wrapper.emitted("click");
            expect(emitted).toBeTruthy();
            expect(emitted![0]![0]).toBeInstanceOf(MouseEvent);
        });
    });

    // ==================== htmlType 属性 ====================
    describe("htmlType 属性", () => {
        it("默认 htmlType 应该是 button", () => {
            const wrapper = mount(Button);
            expect(wrapper.attributes("type")).toBe("button");
        });

        it.each(["button", "submit", "reset"] as const)('htmlType "%s" 应该设置正确的 type 属性', (htmlType) => {
            const wrapper = mount(Button, {
                props: { htmlType }
            });
            expect(wrapper.attributes("type")).toBe(htmlType);
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", () => {
            const wrapper = mount(Button, {
                props: { class: "my-custom-class" }
            });
            expect(wrapper.classes()).toContain("my-custom-class");
        });
    });
});
