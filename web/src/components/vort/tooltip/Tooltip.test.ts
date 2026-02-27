import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";
import Tooltip from "./Tooltip.vue";

describe("Tooltip 组件", () => {
    let wrapper: VueWrapper;

    beforeEach(() => {
        // 创建 teleport 目标
        const el = document.createElement("div");
        el.id = "app";
        document.body.appendChild(el);
    });

    afterEach(() => {
        wrapper?.unmount();
        document.body.innerHTML = "";
    });

    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染触发器插槽内容", () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字" },
                slots: { default: "<button>按钮</button>" }
            });
            expect(wrapper.text()).toBe("按钮");
        });

        it("应该渲染 trigger 包裹元素", () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字" },
                slots: { default: "内容" }
            });
            expect(wrapper.find(".vort-tooltip-trigger").exists()).toBe(true);
        });

        it("默认不应该显示 tooltip 内容", () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字" },
                slots: { default: "触发器" }
            });
            expect(document.querySelector(".vort-tooltip")).toBeNull();
        });
    });

    // ==================== 触发方式 ====================
    describe("触发方式", () => {
        it("hover 触发 - mouseenter 应该显示 tooltip", async () => {
            vi.useFakeTimers();
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "hover", mouseEnterDelay: 0 },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("mouseenter");
            await vi.runAllTimersAsync();
            await nextTick();

            expect(document.querySelector(".vort-tooltip")).not.toBeNull();
            vi.useRealTimers();
        });

        it("hover 触发 - mouseleave 应该隐藏 tooltip", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "hover", mouseEnterDelay: 0, mouseLeaveDelay: 0 },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("mouseenter");
            await nextTick();
            await wrapper.find(".vort-tooltip-trigger").trigger("mouseleave");
            await nextTick();

            // 等待动画完成
            await new Promise((resolve) => setTimeout(resolve, 200));
            expect(document.querySelector(".vort-tooltip")).toBeNull();
        });

        it("click 触发 - 点击应该切换 tooltip 显示", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "click" },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            expect(document.querySelector(".vort-tooltip")).not.toBeNull();
        });

        it("focus 触发 - focus 应该显示 tooltip", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "focus" },
                slots: { default: "<input />" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("focus");
            await nextTick();

            expect(document.querySelector(".vort-tooltip")).not.toBeNull();
        });

        it("focus 触发 - blur 应该隐藏 tooltip", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "focus" },
                slots: { default: "<input />" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("focus");
            await nextTick();
            await wrapper.find(".vort-tooltip-trigger").trigger("blur");
            await nextTick();

            // 等待动画完成
            await new Promise((resolve) => setTimeout(resolve, 200));
            expect(document.querySelector(".vort-tooltip")).toBeNull();
        });

        it("contextMenu 触发 - 右键点击应该显示 tooltip", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "contextMenu" },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("contextmenu");
            await nextTick();

            expect(document.querySelector(".vort-tooltip")).not.toBeNull();
        });
    });

    // ==================== 位置配置 ====================
    describe("位置配置", () => {
        it.each([
            "top",
            "topLeft",
            "topRight",
            "bottom",
            "bottomLeft",
            "bottomRight",
            "left",
            "leftTop",
            "leftBottom",
            "right",
            "rightTop",
            "rightBottom"
        ] as const)('位置 "%s" 应该正确应用', async (placement) => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", placement, trigger: "click" },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            expect(document.querySelector(".vort-tooltip")).not.toBeNull();
        });

        it("默认位置应该是 top", () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字" },
                slots: { default: "触发器" }
            });
            // withDefaults 会将默认值合并到 props 中
            expect(wrapper.vm.$props.placement).toBe("top");
        });
    });

    // ==================== 内容渲染 ====================
    describe("内容渲染", () => {
        it("应该渲染 title prop 内容", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "这是提示文字", trigger: "click" },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            const tooltipInner = document.querySelector(".vort-tooltip-inner");
            expect(tooltipInner?.textContent).toBe("这是提示文字");
        });

        it("应该渲染 title 插槽内容", async () => {
            wrapper = mount(Tooltip, {
                props: { trigger: "click" },
                slots: {
                    default: "触发器",
                    title: "<strong>加粗提示</strong>"
                },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            const tooltipInner = document.querySelector(".vort-tooltip-inner");
            expect(tooltipInner?.innerHTML).toContain("<strong>加粗提示</strong>");
        });

        it("title 插槽应该优先于 title prop", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "prop 文字", trigger: "click" },
                slots: {
                    default: "触发器",
                    title: "插槽文字"
                },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            const tooltipInner = document.querySelector(".vort-tooltip-inner");
            expect(tooltipInner?.textContent).toBe("插槽文字");
        });
    });

    // ==================== 显示/隐藏 ====================
    describe("显示/隐藏", () => {
        it("open prop 为 true 时应该显示 tooltip", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", open: true },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await nextTick();
            expect(document.querySelector(".vort-tooltip")).not.toBeNull();
        });

        it("open prop 为 false 时应该隐藏 tooltip", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", open: false },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await nextTick();
            expect(document.querySelector(".vort-tooltip")).toBeNull();
        });

        it("disabled 时不应该显示 tooltip", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", disabled: true, trigger: "click" },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            expect(document.querySelector(".vort-tooltip")).toBeNull();
        });

        it("应该触发 openChange 事件", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "click" },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            expect(wrapper.emitted("openChange")).toBeTruthy();
            expect(wrapper.emitted("openChange")![0]).toEqual([true]);
        });

        it("应该触发 update:open 事件", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "click" },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            expect(wrapper.emitted("update:open")).toBeTruthy();
            expect(wrapper.emitted("update:open")![0]).toEqual([true]);
        });
    });

    // ==================== 箭头 ====================
    describe("箭头", () => {
        it("默认应该显示箭头", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "click" },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            expect(document.querySelector(".vort-tooltip-arrow")).not.toBeNull();
        });

        it("arrow 为 false 时不应该显示箭头", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "click", arrow: false },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            expect(document.querySelector(".vort-tooltip-arrow")).toBeNull();
        });
    });

    // ==================== 主题和颜色 ====================
    describe("主题和颜色", () => {
        it("dark 模式应该应用暗色背景", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "click", dark: true },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            const tooltip = document.querySelector(".vort-tooltip") as HTMLElement;
            expect(tooltip?.style.getPropertyValue("--tooltip-bg")).toBe("#222");
        });

        it("自定义 color 应该应用到背景", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "click", color: "#ff0000" },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            const tooltip = document.querySelector(".vort-tooltip") as HTMLElement;
            expect(tooltip?.style.getPropertyValue("--tooltip-bg")).toBe("#ff0000");
        });
    });

    // ==================== 浮层样式 ====================
    describe("浮层样式", () => {
        it("应该应用 overlayClass", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "click", overlayClass: "custom-overlay" },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            expect(document.querySelector(".vort-tooltip.custom-overlay")).not.toBeNull();
        });

        it("应该应用 overlayStyle", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", trigger: "click", overlayStyle: { maxWidth: "500px" } },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await wrapper.find(".vort-tooltip-trigger").trigger("click");
            await nextTick();

            const tooltip = document.querySelector(".vort-tooltip") as HTMLElement;
            expect(tooltip?.style.maxWidth).toBe("500px");
        });
    });

    // ==================== 暴露方法 ====================
    describe("暴露方法", () => {
        it("show 方法应该显示 tooltip", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字" },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            (wrapper.vm as any).show();
            await nextTick();

            expect(document.querySelector(".vort-tooltip")).not.toBeNull();
        });

        it("hide 方法应该隐藏 tooltip", async () => {
            wrapper = mount(Tooltip, {
                props: { title: "提示文字", open: true },
                slots: { default: "触发器" },
                attachTo: document.body
            });

            await nextTick();
            (wrapper.vm as any).hide();
            await nextTick();

            // 等待动画完成
            await new Promise((resolve) => setTimeout(resolve, 200));
            expect(document.querySelector(".vort-tooltip")).toBeNull();
        });
    });
});
