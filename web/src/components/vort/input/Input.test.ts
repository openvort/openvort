import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import Input from "./Input.vue";

describe("Input 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染输入框", () => {
            const wrapper = mount(Input);
            expect(wrapper.find("input").exists()).toBe(true);
        });

        it("应该有正确的基础类名", () => {
            const wrapper = mount(Input);
            // 无 prefix/suffix 时直接渲染 input
            expect(wrapper.find("input").classes()).toContain("vort-input");
        });

        it("应该正确渲染 placeholder", () => {
            const wrapper = mount(Input, {
                props: { placeholder: "请输入" }
            });
            expect(wrapper.find("input").attributes("placeholder")).toBe("请输入");
        });
    });

    // ==================== v-model ====================
    describe("v-model", () => {
        it("应该正确显示 modelValue", () => {
            const wrapper = mount(Input, {
                props: { modelValue: "hello" }
            });
            expect(wrapper.find("input").element.value).toBe("hello");
        });

        it("输入时应该触发 update:modelValue 事件", async () => {
            const wrapper = mount(Input, {
                props: { modelValue: "" }
            });
            await wrapper.find("input").setValue("test");
            expect(wrapper.emitted("update:modelValue")).toBeTruthy();
            expect(wrapper.emitted("update:modelValue")![0]).toEqual(["test"]);
        });

        it("应该支持默认值 defaultValue", () => {
            const wrapper = mount(Input, {
                props: { defaultValue: "default" }
            });
            expect(wrapper.find("input").element.value).toBe("default");
        });
    });

    // ==================== 尺寸（size） ====================
    describe("尺寸 size", () => {
        it("默认尺寸应该是 middle", () => {
            const wrapper = mount(Input);
            expect(wrapper.find("input").classes()).toContain("vort-input-middle");
        });

        it.each(["large", "middle", "small"] as const)('尺寸 "%s" 应该添加对应类名', (size) => {
            const wrapper = mount(Input, {
                props: { size }
            });
            expect(wrapper.find("input").classes()).toContain(`vort-input-${size}`);
        });
    });

    // ==================== 状态（status） ====================
    describe("状态 status", () => {
        it.each(["error", "warning"] as const)('状态 "%s" 应该添加对应类名', (status) => {
            const wrapper = mount(Input, {
                props: { status }
            });
            expect(wrapper.find("input").classes()).toContain(`vort-input-${status}`);
        });
    });

    // ==================== 变体（variant） ====================
    describe("变体 variant", () => {
        it("默认变体应该是 outlined", () => {
            const wrapper = mount(Input);
            expect(wrapper.find("input").classes()).toContain("vort-input-outlined");
        });

        it.each(["outlined", "filled", "borderless", "underlined"] as const)('变体 "%s" 应该添加对应类名', (variant) => {
            const wrapper = mount(Input, {
                props: { variant }
            });
            expect(wrapper.find("input").classes()).toContain(`vort-input-${variant}`);
        });

        it("bordered=false 应该等同于 borderless 变体", () => {
            const wrapper = mount(Input, {
                props: { bordered: false }
            });
            expect(wrapper.find("input").classes()).toContain("vort-input-borderless");
        });
    });

    // ==================== 禁用状态 ====================
    describe("禁用状态", () => {
        it("disabled 为 true 时输入框应该被禁用", () => {
            const wrapper = mount(Input, {
                props: { disabled: true }
            });
            expect(wrapper.find("input").attributes("disabled")).toBeDefined();
        });

        it("disabled 时应该有禁用类名", () => {
            const wrapper = mount(Input, {
                props: { disabled: true }
            });
            expect(wrapper.find("input").classes()).toContain("vort-input-disabled");
        });
    });

    // ==================== 事件 ====================
    describe("事件", () => {
        it("输入时应该触发 input 事件", async () => {
            const wrapper = mount(Input);
            await wrapper.find("input").trigger("input");
            expect(wrapper.emitted("input")).toBeTruthy();
        });

        it("值变化时应该触发 change 事件", async () => {
            const wrapper = mount(Input);
            await wrapper.find("input").trigger("change");
            expect(wrapper.emitted("change")).toBeTruthy();
        });

        it("获得焦点时应该触发 focus 事件", async () => {
            const wrapper = mount(Input);
            await wrapper.find("input").trigger("focus");
            expect(wrapper.emitted("focus")).toBeTruthy();
        });

        it("失去焦点时应该触发 blur 事件", async () => {
            const wrapper = mount(Input);
            await wrapper.find("input").trigger("blur");
            expect(wrapper.emitted("blur")).toBeTruthy();
        });

        it("按下回车键应该触发 pressEnter 事件", async () => {
            const wrapper = mount(Input);
            await wrapper.find("input").trigger("keydown", { key: "Enter" });
            expect(wrapper.emitted("pressEnter")).toBeTruthy();
        });
    });

    // ==================== 清除功能 ====================
    describe("清除功能", () => {
        it("allowClear 为 true 且有值时应该渲染清除按钮", async () => {
            const wrapper = mount(Input, {
                props: { allowClear: true, modelValue: "test" }
            });
            expect(wrapper.find(".vort-input-clear").exists()).toBe(true);
        });

        it("allowClear 为 true 但值为空时清除按钮不可见", () => {
            const wrapper = mount(Input, {
                props: { allowClear: true, modelValue: "" }
            });
            const clearBtn = wrapper.find(".vort-input-clear");
            // 按钮存在但不可见
            expect(clearBtn.exists()).toBe(true);
            expect(clearBtn.classes()).not.toContain("vort-input-clear-visible");
        });

        it("点击清除按钮应该清空内容并触发事件", async () => {
            const wrapper = mount(Input, {
                props: { allowClear: true, modelValue: "test" }
            });
            await wrapper.find(".vort-input-clear").trigger("click");
            expect(wrapper.emitted("update:modelValue")![0]).toEqual([""]);
            expect(wrapper.emitted("clear")).toBeTruthy();
        });
    });

    // ==================== 字数统计 ====================
    describe("字数统计", () => {
        it("showCount 为 true 时应该显示字数", () => {
            const wrapper = mount(Input, {
                props: { showCount: true, modelValue: "hello" }
            });
            expect(wrapper.find(".vort-input-count").exists()).toBe(true);
            expect(wrapper.find(".vort-input-count").text()).toBe("5");
        });

        it("有 maxlength 时应该显示 当前/最大 格式", () => {
            const wrapper = mount(Input, {
                props: { showCount: true, maxlength: 10, modelValue: "hello" }
            });
            expect(wrapper.find(".vort-input-count").text()).toBe("5 / 10");
        });
    });

    // ==================== maxlength ====================
    describe("maxlength", () => {
        it("应该正确设置 maxlength 属性", () => {
            const wrapper = mount(Input, {
                props: { maxlength: 20 }
            });
            expect(wrapper.find("input").attributes("maxlength")).toBe("20");
        });
    });

    // ==================== 暴露方法 ====================
    describe("暴露方法", () => {
        it("应该暴露 focus 方法", () => {
            const wrapper = mount(Input);
            expect(typeof wrapper.vm.focus).toBe("function");
        });

        it("应该暴露 blur 方法", () => {
            const wrapper = mount(Input);
            expect(typeof wrapper.vm.blur).toBe("function");
        });

        it("应该暴露 input ref", () => {
            const wrapper = mount(Input);
            expect(wrapper.vm.input).toBeDefined();
        });
    });
});
