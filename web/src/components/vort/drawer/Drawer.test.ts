import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";
import Drawer from "./Drawer.vue";

// Mock Teleport
const mockTeleport = {
    name: "Teleport",
    template: "<div><slot /></div>"
};

describe("Drawer 组件", () => {
    let wrapper: VueWrapper;

    beforeEach(() => {
        // 清理 body 样式
        document.body.style.overflow = "";
        // 清理全局抽屉栈
        (window as unknown as { __vortDrawerStack__?: unknown[] }).__vortDrawerStack__ = [];
    });

    afterEach(() => {
        wrapper?.unmount();
        document.body.style.overflow = "";
    });

    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("关闭状态下不应该渲染抽屉内容", () => {
            wrapper = mount(Drawer, {
                props: { open: false },
                global: { stubs: { Teleport: mockTeleport } }
            });
            expect(wrapper.find(".vort-drawer").exists()).toBe(false);
        });

        it("打开状态下应该渲染抽屉", async () => {
            wrapper = mount(Drawer, {
                props: { open: true },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            // 等待 requestAnimationFrame
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(".vort-drawer").exists()).toBe(true);
        });

        it("应该正确渲染插槽内容", async () => {
            wrapper = mount(Drawer, {
                props: { open: true },
                slots: { default: "抽屉内容" },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(".vort-drawer-body").text()).toBe("抽屉内容");
        });
    });

    // ==================== 打开/关闭 ====================
    describe("打开/关闭", () => {
        it("从关闭到打开应该触发显示", async () => {
            wrapper = mount(Drawer, {
                props: { open: false },
                global: { stubs: { Teleport: mockTeleport } }
            });
            expect(wrapper.find(".vort-drawer").exists()).toBe(false);

            await wrapper.setProps({ open: true });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(".vort-drawer").exists()).toBe(true);
        });

        it("点击关闭按钮应该触发 close 事件", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, closable: true },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();

            const closeBtn = wrapper.find(".vort-drawer-close");
            expect(closeBtn.exists()).toBe(true);
            await closeBtn.trigger("click");

            expect(wrapper.emitted("update:open")).toBeTruthy();
            expect(wrapper.emitted("update:open")![0]).toEqual([false]);
            expect(wrapper.emitted("close")).toBeTruthy();
        });

        it("打开时应该禁止 body 滚动", async () => {
            wrapper = mount(Drawer, {
                props: { open: true },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(document.body.style.overflow).toBe("hidden");
        });
    });

    // ==================== 位置（placement） ====================
    describe("位置 placement", () => {
        it("默认位置应该是 right", async () => {
            wrapper = mount(Drawer, {
                props: { open: true },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(".vort-drawer-right").exists()).toBe(true);
        });

        it.each(["left", "right", "top", "bottom"] as const)('位置 "%s" 应该添加对应类名', async (placement) => {
            wrapper = mount(Drawer, {
                props: { open: true, placement },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(`.vort-drawer-${placement}`).exists()).toBe(true);
        });
    });

    // ==================== 标题和内容 ====================
    describe("标题和内容", () => {
        it("应该正确渲染标题", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, title: "测试标题" },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(".vort-drawer-title").text()).toBe("测试标题");
        });

        it("应该支持标题插槽", async () => {
            wrapper = mount(Drawer, {
                props: { open: true },
                slots: { title: "自定义标题" },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(".vort-drawer-title").text()).toBe("自定义标题");
        });

        it("应该正确渲染底部插槽", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, footer: true },
                slots: { footer: "底部内容" },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(".vort-drawer-footer").text()).toBe("底部内容");
        });

        it("没有标题和关闭按钮时不应该渲染头部", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, closable: false },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(".vort-drawer-header").exists()).toBe(false);
        });
    });

    // ==================== 关闭按钮 ====================
    describe("关闭按钮", () => {
        it("默认应该显示关闭按钮", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, title: "标题" },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(".vort-drawer-close").exists()).toBe(true);
        });

        it("closable 为 false 时不应该显示关闭按钮", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, title: "标题", closable: false },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(".vort-drawer-close").exists()).toBe(false);
        });
    });

    // ==================== 遮罩层 ====================
    describe("遮罩层", () => {
        it("默认应该显示遮罩", async () => {
            wrapper = mount(Drawer, {
                props: { open: true },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(".vort-drawer-mask").exists()).toBe(true);
        });

        it("mask 为 false 时不应该显示遮罩", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, mask: false },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(".vort-drawer-mask").exists()).toBe(false);
        });

        it("点击遮罩应该关闭抽屉", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, maskClosable: true },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();

            await wrapper.find(".vort-drawer-mask").trigger("click");
            expect(wrapper.emitted("update:open")).toBeTruthy();
            expect(wrapper.emitted("update:open")![0]).toEqual([false]);
        });

        it("maskClosable 为 false 时点击遮罩不应该关闭", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, maskClosable: false },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();

            await wrapper.find(".vort-drawer-mask").trigger("click");
            expect(wrapper.emitted("update:open")).toBeFalsy();
        });
    });

    // ==================== 宽度/高度 ====================
    describe("宽度/高度", () => {
        it("left/right 位置应该使用 width", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, placement: "right", width: 500 },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            const drawer = wrapper.find(".vort-drawer");
            expect(drawer.attributes("style")).toContain("width: 500px");
        });

        it("top/bottom 位置应该使用 height", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, placement: "bottom", height: 300 },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            const drawer = wrapper.find(".vort-drawer");
            expect(drawer.attributes("style")).toContain("height: 300px");
        });

        it("应该支持字符串格式的尺寸", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, placement: "right", width: "50%" },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            const drawer = wrapper.find(".vort-drawer");
            expect(drawer.attributes("style")).toContain("width: 50%");
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, class: "my-custom-drawer" },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            expect(wrapper.find(".vort-drawer-root").classes()).toContain("my-custom-drawer");
        });
    });

    // ==================== 键盘事件 ====================
    describe("键盘事件", () => {
        it("默认按 ESC 应该关闭抽屉", async () => {
            wrapper = mount(Drawer, {
                props: { open: true },
                global: { stubs: { Teleport: mockTeleport } },
                attachTo: document.body
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();

            // 模拟 ESC 键按下
            const event = new KeyboardEvent("keydown", { key: "Escape" });
            document.dispatchEvent(event);

            expect(wrapper.emitted("update:open")).toBeTruthy();
            expect(wrapper.emitted("update:open")![0]).toEqual([false]);
        });

        it("keyboard 为 false 时按 ESC 不应该关闭", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, keyboard: false },
                global: { stubs: { Teleport: mockTeleport } },
                attachTo: document.body
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();

            const event = new KeyboardEvent("keydown", { key: "Escape" });
            document.dispatchEvent(event);

            expect(wrapper.emitted("update:open")).toBeFalsy();
        });
    });

    // ==================== zIndex ====================
    describe("zIndex", () => {
        it("应该正确设置 z-index", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, zIndex: 2000 },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            const drawer = wrapper.find(".vort-drawer");
            expect(drawer.attributes("style")).toContain("z-index");
        });
    });

    // ==================== bodyStyle ====================
    describe("bodyStyle", () => {
        it("应该正确应用 bodyStyle", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, bodyStyle: { padding: "32px" } },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            const body = wrapper.find(".vort-drawer-body");
            expect(body.attributes("style")).toContain("padding: 32px");
        });
    });

    // ==================== contentBg ====================
    describe("contentBg", () => {
        it("应该正确设置内容区背景色", async () => {
            wrapper = mount(Drawer, {
                props: { open: true, contentBg: "#f0f0f0" },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            const body = wrapper.find(".vort-drawer-body");
            expect(body.attributes("style")).toContain("background: rgb(240, 240, 240)");
        });
    });

    // ==================== ARIA 属性 ====================
    describe("ARIA 属性", () => {
        it("应该有正确的 ARIA 属性", async () => {
            wrapper = mount(Drawer, {
                props: { open: true },
                global: { stubs: { Teleport: mockTeleport } }
            });
            await nextTick();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await nextTick();
            const drawer = wrapper.find(".vort-drawer");
            expect(drawer.attributes("role")).toBe("dialog");
            expect(drawer.attributes("aria-modal")).toBe("true");
        });
    });
});
