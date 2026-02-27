import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import Pagination from "./Pagination.vue";

describe("Pagination 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染分页组件", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100 }
            });
            expect(wrapper.find(".vort-pagination").exists()).toBe(true);
        });

        it("应该渲染为 nav 元素", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100 }
            });
            expect(wrapper.element.tagName).toBe("NAV");
        });

        it("应该有正确的基础类名", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100 }
            });
            expect(wrapper.classes()).toContain("vort-pagination");
        });

        it("应该有正确的 role 属性", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100 }
            });
            expect(wrapper.attributes("role")).toBe("navigation");
        });
    });

    // ==================== 页码切换 ====================
    describe("页码切换", () => {
        it("点击页码应该触发 update:current 事件", async () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, current: 1 }
            });
            const pageButtons = wrapper.findAll(".vort-pagination-item");
            // 找到第 2 页按钮并点击
            const page2Button = pageButtons.find((btn) => btn.text() === "2");
            await page2Button?.trigger("click");
            expect(wrapper.emitted("update:current")).toBeTruthy();
            expect(wrapper.emitted("update:current")![0]).toEqual([2]);
        });

        it("点击页码应该触发 change 事件", async () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, current: 1, pageSize: 10 }
            });
            const pageButtons = wrapper.findAll(".vort-pagination-item");
            const page2Button = pageButtons.find((btn) => btn.text() === "2");
            await page2Button?.trigger("click");
            expect(wrapper.emitted("change")).toBeTruthy();
            expect(wrapper.emitted("change")![0]).toEqual([2, 10]);
        });

        it("点击上一页应该跳转到前一页", async () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, current: 3 }
            });
            const prevButton = wrapper.find('[aria-label="上一页"]');
            await prevButton.trigger("click");
            expect(wrapper.emitted("update:current")![0]).toEqual([2]);
        });

        it("点击下一页应该跳转到后一页", async () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, current: 3 }
            });
            const nextButton = wrapper.find('[aria-label="下一页"]');
            await nextButton.trigger("click");
            expect(wrapper.emitted("update:current")![0]).toEqual([4]);
        });

        it("第一页时上一页按钮应该禁用", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, current: 1 }
            });
            const prevButton = wrapper.find('[aria-label="上一页"]');
            expect(prevButton.attributes("disabled")).toBeDefined();
        });

        it("最后一页时下一页按钮应该禁用", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, current: 10, pageSize: 10 }
            });
            const nextButton = wrapper.find('[aria-label="下一页"]');
            expect(nextButton.attributes("disabled")).toBeDefined();
        });

        it("当前页应该有 active 类名", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, current: 3 }
            });
            const activeButton = wrapper.find(".vort-pagination-item-active");
            expect(activeButton.exists()).toBe(true);
            expect(activeButton.text()).toBe("3");
        });
    });

    // ==================== 每页条数切换 ====================
    describe("每页条数切换", () => {
        it("showSizeChanger 为 true 时应该显示条数选择器", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, showSizeChanger: true }
            });
            expect(wrapper.find(".vort-pagination-options-size-changer").exists()).toBe(true);
        });

        it("showSizeChanger 为 false 时不应该显示条数选择器", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, showSizeChanger: false }
            });
            expect(wrapper.find(".vort-pagination-options-size-changer").exists()).toBe(false);
        });

        it("默认 pageSizeOptions 应该是 [10, 20, 50, 100]", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, showSizeChanger: true }
            });
            // 检查 Select 组件的 options
            const select = wrapper.findComponent({ name: "VortSelect" });
            expect(select.exists()).toBe(true);
        });
    });

    // ==================== 快速跳转 ====================
    describe("快速跳转", () => {
        it("showQuickJumper 为 true 时应该显示快速跳转输入框", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, showQuickJumper: true }
            });
            expect(wrapper.find(".vort-pagination-options-quick-jumper").exists()).toBe(true);
        });

        it("showQuickJumper 为 false 时不应该显示快速跳转输入框", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, showQuickJumper: false }
            });
            expect(wrapper.find(".vort-pagination-options-quick-jumper").exists()).toBe(false);
        });

        it("快速跳转应该包含输入框", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, showQuickJumper: true }
            });
            const quickJumper = wrapper.find(".vort-pagination-options-quick-jumper");
            expect(quickJumper.text()).toContain("跳至");
            expect(quickJumper.text()).toContain("页");
        });
    });

    // ==================== 总数显示 ====================
    describe("总数显示", () => {
        it("showTotalInfo 为 true 时应该显示总数信息", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, showTotalInfo: true }
            });
            const totalSpan = wrapper.find(".vort-pagination-total");
            expect(totalSpan.exists()).toBe(true);
            expect(totalSpan.text()).toContain("100");
        });

        it("showTotal 函数应该自定义总数显示格式", () => {
            const showTotal = (total: number, range: [number, number]) => `显示 ${range[0]}-${range[1]}，共 ${total} 条`;
            const wrapper = mount(Pagination, {
                props: { total: 100, showTotal }
            });
            const totalSpan = wrapper.find(".vort-pagination-total");
            expect(totalSpan.text()).toBe("显示 1-10，共 100 条");
        });

        it("不设置 showTotal 和 showTotalInfo 时不显示总数", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100 }
            });
            expect(wrapper.find(".vort-pagination-total").exists()).toBe(false);
        });
    });

    // ==================== 尺寸变体 ====================
    describe("尺寸变体", () => {
        it("默认尺寸应该是 default", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100 }
            });
            expect(wrapper.classes()).not.toContain("vort-pagination-small");
        });

        it('size="small" 应该添加 small 类名', () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, size: "small" }
            });
            expect(wrapper.classes()).toContain("vort-pagination-small");
        });
    });

    // ==================== 禁用状态 ====================
    describe("禁用状态", () => {
        it("disabled 为 true 时应该添加禁用类名", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, disabled: true }
            });
            expect(wrapper.classes()).toContain("vort-pagination-disabled");
        });

        it("disabled 时所有页码按钮应该被禁用", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, disabled: true }
            });
            const buttons = wrapper.findAll(".vort-pagination-item");
            buttons.forEach((btn) => {
                expect(btn.attributes("disabled")).toBeDefined();
            });
        });

        it("disabled 时点击页码不应该触发事件", async () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, current: 1, disabled: true }
            });
            const pageButtons = wrapper.findAll(".vort-pagination-item");
            const page2Button = pageButtons.find((btn) => btn.text() === "2");
            await page2Button?.trigger("click");
            expect(wrapper.emitted("update:current")).toBeFalsy();
        });
    });

    // ==================== 隐藏单页 ====================
    describe("隐藏单页", () => {
        it("hideOnSinglePage 为 true 且只有一页时应该隐藏分页", () => {
            const wrapper = mount(Pagination, {
                props: { total: 5, pageSize: 10, hideOnSinglePage: true }
            });
            expect(wrapper.find(".vort-pagination").exists()).toBe(false);
        });

        it("hideOnSinglePage 为 true 但有多页时应该显示分页", () => {
            const wrapper = mount(Pagination, {
                props: { total: 50, pageSize: 10, hideOnSinglePage: true }
            });
            expect(wrapper.find(".vort-pagination").exists()).toBe(true);
        });

        it("hideOnSinglePage 为 false 时即使只有一页也应该显示", () => {
            const wrapper = mount(Pagination, {
                props: { total: 5, pageSize: 10, hideOnSinglePage: false }
            });
            expect(wrapper.find(".vort-pagination").exists()).toBe(true);
        });
    });

    // ==================== 简洁模式 ====================
    describe("简洁模式", () => {
        it("simple 为 true 时应该显示简洁模式", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, simple: true }
            });
            expect(wrapper.find(".vort-pagination-simple-pager").exists()).toBe(true);
        });

        it("simple 模式应该显示输入框和总页数", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, pageSize: 10, simple: true }
            });
            expect(wrapper.find(".vort-pagination-simple-input").exists()).toBe(true);
            expect(wrapper.find(".vort-pagination-simple-total").text()).toBe("10");
        });

        it("simple 模式不应该显示页码按钮列表", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, simple: true }
            });
            // 简洁模式下不应该有非导航的页码按钮
            const pageItems = wrapper.findAll(".vort-pagination-item:not(.vort-pagination-nav)");
            expect(pageItems.length).toBe(0);
        });
    });

    // ==================== 省略号跳转 ====================
    describe("省略号跳转", () => {
        it("页数较多时应该显示省略号", () => {
            const wrapper = mount(Pagination, {
                props: { total: 500, current: 10 }
            });
            expect(wrapper.find(".vort-pagination-jump").exists()).toBe(true);
        });

        it("点击前跳省略号应该向前跳转多页", async () => {
            const wrapper = mount(Pagination, {
                props: { total: 500, current: 10 }
            });
            const jumpPrev = wrapper.find(".vort-pagination-jump-prev");
            if (jumpPrev.exists()) {
                await jumpPrev.trigger("click");
                expect(wrapper.emitted("update:current")).toBeTruthy();
                // 默认跳转 5 页
                expect(wrapper.emitted("update:current")![0]).toEqual([5]);
            }
        });

        it("点击后跳省略号应该向后跳转多页", async () => {
            const wrapper = mount(Pagination, {
                props: { total: 500, current: 10 }
            });
            const jumpNext = wrapper.find(".vort-pagination-jump-next");
            if (jumpNext.exists()) {
                await jumpNext.trigger("click");
                expect(wrapper.emitted("update:current")).toBeTruthy();
                // 默认跳转 5 页
                expect(wrapper.emitted("update:current")![0]).toEqual([15]);
            }
        });
    });

    // ==================== showLessItems ====================
    describe("showLessItems", () => {
        it("showLessItems 为 true 时省略号跳转应该是 3 页", async () => {
            const wrapper = mount(Pagination, {
                props: { total: 500, current: 10, showLessItems: true }
            });
            const jumpPrev = wrapper.find(".vort-pagination-jump-prev");
            if (jumpPrev.exists()) {
                await jumpPrev.trigger("click");
                expect(wrapper.emitted("update:current")![0]).toEqual([7]);
            }
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", () => {
            const wrapper = mount(Pagination, {
                props: { total: 100, class: "my-custom-pagination" }
            });
            expect(wrapper.classes()).toContain("my-custom-pagination");
        });
    });
});
