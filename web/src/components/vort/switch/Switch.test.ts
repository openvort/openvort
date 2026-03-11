import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import Switch from "./Switch.vue";

describe("Switch 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该渲染为 button 元素", () => {
            const wrapper = mount(Switch);
            expect(wrapper.element.tagName).toBe("BUTTON");
        });

        it("应该有正确的基础类名", () => {
            const wrapper = mount(Switch);
            expect(wrapper.classes()).toContain("vort-switch");
        });

        it("应该有正确的 role 属性", () => {
            const wrapper = mount(Switch);
            expect(wrapper.attributes("role")).toBe("switch");
        });

        it("默认应该是未选中状态", () => {
            const wrapper = mount(Switch);
            expect(wrapper.classes()).not.toContain("vort-switch-checked");
            expect(wrapper.attributes("aria-checked")).toBe("false");
        });
    });

    // ==================== v-model（checked） ====================
    describe("v-model checked", () => {
        it("checked 为 true 时应该显示选中状态", () => {
            const wrapper = mount(Switch, {
                props: { checked: true }
            });
            expect(wrapper.classes()).toContain("vort-switch-checked");
            expect(wrapper.attributes("aria-checked")).toBe("true");
        });

        it("checked 为 false 时应该显示未选中状态", () => {
            const wrapper = mount(Switch, {
                props: { checked: false }
            });
            expect(wrapper.classes()).not.toContain("vort-switch-checked");
            expect(wrapper.attributes("aria-checked")).toBe("false");
        });

        it("应该支持数字类型 1 作为选中状态", () => {
            const wrapper = mount(Switch, {
                props: { checked: 1 }
            });
            expect(wrapper.classes()).toContain("vort-switch-checked");
        });

        it("应该支持数字类型 0 作为未选中状态", () => {
            const wrapper = mount(Switch, {
                props: { checked: 0 }
            });
            expect(wrapper.classes()).not.toContain("vort-switch-checked");
        });

        it("点击应该触发 update:checked 事件", async () => {
            const wrapper = mount(Switch, {
                props: { checked: false }
            });
            await wrapper.trigger("click");
            expect(wrapper.emitted("update:checked")).toBeTruthy();
            expect(wrapper.emitted("update:checked")![0]).toEqual([true]);
        });

        it("点击选中状态应该切换为未选中", async () => {
            const wrapper = mount(Switch, {
                props: { checked: true }
            });
            await wrapper.trigger("click");
            expect(wrapper.emitted("update:checked")![0]).toEqual([false]);
        });

        it("点击应该触发 change 事件", async () => {
            const wrapper = mount(Switch, {
                props: { checked: false }
            });
            await wrapper.trigger("click");
            const emitted = wrapper.emitted("change");
            expect(emitted).toBeTruthy();
            expect(emitted![0]![0]).toBe(true);
            expect(emitted![0]![1]).toBeInstanceOf(MouseEvent);
        });
    });

    // ==================== 尺寸（size） ====================
    describe("尺寸 size", () => {
        it("默认尺寸应该是 default", () => {
            const wrapper = mount(Switch);
            expect(wrapper.classes()).not.toContain("vort-switch-small");
        });

        it("size 为 small 时应该添加对应类名", () => {
            const wrapper = mount(Switch, {
                props: { size: "small" }
            });
            expect(wrapper.classes()).toContain("vort-switch-small");
        });

        it("size 为 default 时不应该有 small 类名", () => {
            const wrapper = mount(Switch, {
                props: { size: "default" }
            });
            expect(wrapper.classes()).not.toContain("vort-switch-small");
        });
    });

    // ==================== 禁用状态 ====================
    describe("禁用状态", () => {
        it("disabled 为 true 时按钮应该被禁用", () => {
            const wrapper = mount(Switch, {
                props: { disabled: true }
            });
            expect(wrapper.attributes("disabled")).toBeDefined();
            expect(wrapper.classes()).toContain("vort-switch-disabled");
        });

        it("disabled 为 true 时 aria-disabled 应该为 true", () => {
            const wrapper = mount(Switch, {
                props: { disabled: true }
            });
            expect(wrapper.attributes("aria-disabled")).toBe("true");
        });

        it("disabled 时点击不应该触发事件", async () => {
            const wrapper = mount(Switch, {
                props: { disabled: true, checked: false }
            });
            await wrapper.trigger("click");
            expect(wrapper.emitted("update:checked")).toBeFalsy();
            expect(wrapper.emitted("change")).toBeFalsy();
        });
    });

    // ==================== 加载状态 ====================
    describe("加载状态", () => {
        it("loading 为 true 时应该显示加载图标", () => {
            const wrapper = mount(Switch, {
                props: { loading: true }
            });
            expect(wrapper.find(".vort-switch-loading").exists()).toBe(true);
        });

        it("loading 时开关应该被禁用", () => {
            const wrapper = mount(Switch, {
                props: { loading: true }
            });
            expect(wrapper.attributes("disabled")).toBeUndefined();
            expect(wrapper.attributes("aria-disabled")).toBe("true");
        });

        it("loading 时点击不应该触发事件", async () => {
            const wrapper = mount(Switch, {
                props: { loading: true, checked: false }
            });
            await wrapper.trigger("click");
            expect(wrapper.emitted("update:checked")).toBeFalsy();
            expect(wrapper.emitted("change")).toBeFalsy();
        });

        it("loading 时应该有 disabled 类名", () => {
            const wrapper = mount(Switch, {
                props: { loading: true }
            });
            expect(wrapper.classes()).toContain("vort-switch-disabled");
        });

        it("beforeChange 异步执行时应该使用原生 disabled 阻止重复触发", async () => {
            let resolveChange: ((value: boolean) => void) | undefined;
            const beforeChange = vi.fn().mockImplementation(() => new Promise<boolean>((resolve) => {
                resolveChange = resolve;
            }));
            const wrapper = mount(Switch, {
                props: { checked: false, beforeChange }
            });

            await wrapper.trigger("click");

            expect(wrapper.attributes("disabled")).toBeDefined();
            expect(wrapper.attributes("aria-disabled")).toBe("true");

            resolveChange?.(true);

            await vi.waitFor(() => {
                expect(wrapper.emitted("update:checked")).toBeTruthy();
            });
        });
    });

    // ==================== 自定义文字 ====================
    describe("自定义文字", () => {
        it("应该显示 checkedChildren 文字（选中时）", () => {
            const wrapper = mount(Switch, {
                props: { checked: true, checkedChildren: "开" }
            });
            expect(wrapper.find(".vort-switch-inner-checked").text()).toBe("开");
        });

        it("应该显示 unCheckedChildren 文字（未选中时）", () => {
            const wrapper = mount(Switch, {
                props: { checked: false, unCheckedChildren: "关" }
            });
            expect(wrapper.find(".vort-switch-inner-unchecked").text()).toBe("关");
        });

        it("应该支持通过 slot 自定义内容", () => {
            const wrapper = mount(Switch, {
                props: { checked: true },
                slots: {
                    checkedChildren: "已开启"
                }
            });
            expect(wrapper.find(".vort-switch-inner-checked").text()).toBe("已开启");
        });

        it("应该支持通过 slot 自定义未选中内容", () => {
            const wrapper = mount(Switch, {
                props: { checked: false },
                slots: {
                    unCheckedChildren: "已关闭"
                }
            });
            expect(wrapper.find(".vort-switch-inner-unchecked").text()).toBe("已关闭");
        });
    });

    // ==================== beforeChange 钩子 ====================
    describe("beforeChange 钩子", () => {
        it("beforeChange 返回 true 时应该切换", async () => {
            const beforeChange = vi.fn().mockReturnValue(true);
            const wrapper = mount(Switch, {
                props: { checked: false, beforeChange }
            });
            await wrapper.trigger("click");
            expect(beforeChange).toHaveBeenCalled();
            expect(wrapper.emitted("update:checked")).toBeTruthy();
        });

        it("beforeChange 返回 false 时应该阻止切换", async () => {
            const beforeChange = vi.fn().mockReturnValue(false);
            const wrapper = mount(Switch, {
                props: { checked: false, beforeChange }
            });
            await wrapper.trigger("click");
            expect(beforeChange).toHaveBeenCalled();
            expect(wrapper.emitted("update:checked")).toBeFalsy();
        });

        it("beforeChange 返回 Promise<true> 时应该切换", async () => {
            const beforeChange = vi.fn().mockResolvedValue(true);
            const wrapper = mount(Switch, {
                props: { checked: false, beforeChange }
            });
            await wrapper.trigger("click");
            // 等待 Promise 解析
            await vi.waitFor(() => {
                expect(wrapper.emitted("update:checked")).toBeTruthy();
            });
        });

        it("beforeChange 返回 Promise<false> 时应该阻止切换", async () => {
            const beforeChange = vi.fn().mockResolvedValue(false);
            const wrapper = mount(Switch, {
                props: { checked: false, beforeChange }
            });
            await wrapper.trigger("click");
            // 等待 Promise 解析
            await vi.waitFor(() => {
                expect(wrapper.emitted("update:checked")).toBeFalsy();
            });
        });

        it("beforeChange reject 时应该阻止切换", async () => {
            const beforeChange = vi.fn().mockRejectedValue(new Error("取消"));
            const wrapper = mount(Switch, {
                props: { checked: false, beforeChange }
            });
            await wrapper.trigger("click");
            // 等待 Promise reject
            await vi.waitFor(() => {
                expect(wrapper.emitted("update:checked")).toBeFalsy();
            });
        });
    });

    // ==================== 键盘操作 ====================
    describe("键盘操作", () => {
        it("按 Enter 键应该切换状态", async () => {
            const wrapper = mount(Switch, {
                props: { checked: false }
            });
            await wrapper.trigger("keydown", { key: "Enter" });
            expect(wrapper.emitted("update:checked")).toBeTruthy();
            expect(wrapper.emitted("update:checked")![0]).toEqual([true]);
        });

        it("按空格键应该切换状态", async () => {
            const wrapper = mount(Switch, {
                props: { checked: false }
            });
            await wrapper.trigger("keydown", { key: " " });
            expect(wrapper.emitted("update:checked")).toBeTruthy();
        });

        it("禁用时按 Enter 键不应该切换", async () => {
            const wrapper = mount(Switch, {
                props: { checked: false, disabled: true }
            });
            await wrapper.trigger("keydown", { key: "Enter" });
            expect(wrapper.emitted("update:checked")).toBeFalsy();
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", () => {
            const wrapper = mount(Switch, {
                props: { class: "my-custom-switch" }
            });
            expect(wrapper.classes()).toContain("my-custom-switch");
        });
    });
});
