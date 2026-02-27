import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, VueWrapper } from "@vue/test-utils";
import { nextTick } from "vue";
import Dialog from "./Dialog.vue";

// Mock Teleport 以便测试
const teleportTarget = document.createElement("div");
teleportTarget.id = "vort-app";
document.body.appendChild(teleportTarget);

describe("Dialog 组件", () => {
    let wrapper: VueWrapper;

    beforeEach(() => {
        // 清理 body 样式
        document.body.style.overflow = "";
    });

    afterEach(() => {
        if (wrapper) {
            wrapper.unmount();
        }
        // 清理 teleport 内容
        teleportTarget.innerHTML = "";
        document.body.style.overflow = "";
    });

    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("open 为 false 时不应该渲染对话框", () => {
            wrapper = mount(Dialog, {
                props: { open: false }
            });
            expect(document.querySelector(".vort-dialog-root")).toBeNull();
        });

        it("open 为 true 时应该渲染对话框", async () => {
            wrapper = mount(Dialog, {
                props: { open: true }
            });
            await nextTick();
            expect(document.querySelector(".vort-dialog-root")).not.toBeNull();
        });

        it("应该有正确的 role 属性", async () => {
            wrapper = mount(Dialog, {
                props: { open: true }
            });
            await nextTick();
            const dialog = document.querySelector(".vort-dialog");
            expect(dialog?.getAttribute("role")).toBe("dialog");
            expect(dialog?.getAttribute("aria-modal")).toBe("true");
        });
    });

    // ==================== 打开/关闭 ====================
    describe("打开/关闭", () => {
        it("打开时应该锁定 body 滚动", async () => {
            wrapper = mount(Dialog, {
                props: { open: true }
            });
            await nextTick();
            expect(document.body.style.overflow).toBe("hidden");
        });

        it("点击取消按钮应该触发 update:open 和 cancel 事件", async () => {
            wrapper = mount(Dialog, {
                props: { open: true }
            });
            await nextTick();

            const cancelBtn = document.querySelector(".vort-dialog-footer .vort-btn:first-child") as HTMLElement;
            cancelBtn?.click();

            expect(wrapper.emitted("update:open")).toBeTruthy();
            expect(wrapper.emitted("update:open")![0]).toEqual([false]);
            expect(wrapper.emitted("cancel")).toBeTruthy();
        });

        it("点击确定按钮应该触发 ok 事件", async () => {
            wrapper = mount(Dialog, {
                props: { open: true }
            });
            await nextTick();

            const okBtn = document.querySelector(".vort-dialog-footer .vort-btn-primary") as HTMLElement;
            okBtn?.click();

            expect(wrapper.emitted("ok")).toBeTruthy();
        });
    });

    // ==================== 标题和内容 ====================
    describe("标题和内容", () => {
        it("应该正确渲染标题", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, title: "测试标题" }
            });
            await nextTick();

            const title = document.querySelector(".vort-dialog-title");
            expect(title?.textContent).toBe("测试标题");
        });

        it("没有标题时不应该渲染头部", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, title: "" }
            });
            await nextTick();

            const header = document.querySelector(".vort-dialog-header");
            expect(header).toBeNull();
        });

        it("应该正确渲染插槽内容", async () => {
            wrapper = mount(Dialog, {
                props: { open: true },
                slots: { default: "<p>对话框内容</p>" }
            });
            await nextTick();

            const body = document.querySelector(".vort-dialog-body");
            expect(body?.innerHTML).toContain("对话框内容");
        });

        it("应该支持自定义标题插槽", async () => {
            wrapper = mount(Dialog, {
                props: { open: true },
                slots: { title: "<strong>自定义标题</strong>" }
            });
            await nextTick();

            const header = document.querySelector(".vort-dialog-header");
            expect(header?.innerHTML).toContain("自定义标题");
        });
    });

    // ==================== 底部按钮 ====================
    describe("底部按钮", () => {
        it("默认应该显示底部按钮区域", async () => {
            wrapper = mount(Dialog, {
                props: { open: true }
            });
            await nextTick();

            const footer = document.querySelector(".vort-dialog-footer");
            expect(footer).not.toBeNull();
        });

        it("footer 为 false 时不应该显示底部按钮区域", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, footer: false }
            });
            await nextTick();

            const footer = document.querySelector(".vort-dialog-footer");
            expect(footer).toBeNull();
        });

        it("应该正确渲染自定义按钮文字", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, okText: "提交", cancelText: "返回" }
            });
            await nextTick();

            const buttons = document.querySelectorAll(".vort-dialog-footer .vort-btn");
            expect(buttons[0]?.textContent?.trim()).toBe("返回");
            expect(buttons[1]?.textContent?.trim()).toBe("提交");
        });

        it("confirmLoading 为 true 时确定按钮应该显示加载状态", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, confirmLoading: true }
            });
            await nextTick();

            const okBtn = document.querySelector(".vort-dialog-footer .vort-btn-primary");
            expect(okBtn?.classList.contains("vort-btn-loading")).toBe(true);
        });

        it("应该支持自定义底部插槽", async () => {
            wrapper = mount(Dialog, {
                props: { open: true },
                slots: { footer: "<button>自定义按钮</button>" }
            });
            await nextTick();

            const footer = document.querySelector(".vort-dialog-footer");
            expect(footer?.innerHTML).toContain("自定义按钮");
        });
    });

    // ==================== 关闭按钮 ====================
    describe("关闭按钮", () => {
        it("默认应该显示关闭按钮", async () => {
            wrapper = mount(Dialog, {
                props: { open: true }
            });
            await nextTick();

            const closeBtn = document.querySelector(".vort-dialog-close");
            expect(closeBtn).not.toBeNull();
        });

        it("closable 为 false 时不应该显示关闭按钮", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, closable: false }
            });
            await nextTick();

            const closeBtn = document.querySelector(".vort-dialog-close");
            expect(closeBtn).toBeNull();
        });

        it("点击关闭按钮应该触发关闭事件", async () => {
            wrapper = mount(Dialog, {
                props: { open: true }
            });
            await nextTick();

            const closeBtn = document.querySelector(".vort-dialog-close") as HTMLElement;
            closeBtn?.click();

            expect(wrapper.emitted("update:open")).toBeTruthy();
            expect(wrapper.emitted("update:open")![0]).toEqual([false]);
            expect(wrapper.emitted("cancel")).toBeTruthy();
        });
    });

    // ==================== 遮罩层点击 ====================
    describe("遮罩层点击", () => {
        it("maskClosable 为 true 时点击遮罩应该关闭对话框", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, maskClosable: true }
            });
            await nextTick();

            const mask = document.querySelector(".vort-dialog-mask") as HTMLElement;
            mask?.click();

            expect(wrapper.emitted("update:open")).toBeTruthy();
            expect(wrapper.emitted("cancel")).toBeTruthy();
        });

        it("maskClosable 为 false 时点击遮罩不应该关闭对话框", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, maskClosable: false }
            });
            await nextTick();

            const mask = document.querySelector(".vort-dialog-mask") as HTMLElement;
            mask?.click();

            expect(wrapper.emitted("update:open")).toBeFalsy();
        });

        it("mask 为 false 时不应该显示遮罩层", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, mask: false }
            });
            await nextTick();

            const mask = document.querySelector(".vort-dialog-mask");
            expect(mask).toBeNull();
        });
    });

    // ==================== 宽度 ====================
    describe("宽度", () => {
        it('width 为 "small" 时应该设置 416px', async () => {
            wrapper = mount(Dialog, {
                props: { open: true, width: "small" }
            });
            await nextTick();

            const dialog = document.querySelector(".vort-dialog") as HTMLElement;
            expect(dialog?.style.width).toBe("416px");
        });

        it('width 为 "default" 时应该设置 520px', async () => {
            wrapper = mount(Dialog, {
                props: { open: true, width: "default" }
            });
            await nextTick();

            const dialog = document.querySelector(".vort-dialog") as HTMLElement;
            expect(dialog?.style.width).toBe("520px");
        });

        it('width 为 "large" 时应该设置 800px', async () => {
            wrapper = mount(Dialog, {
                props: { open: true, width: "large" }
            });
            await nextTick();

            const dialog = document.querySelector(".vort-dialog") as HTMLElement;
            expect(dialog?.style.width).toBe("800px");
        });

        it("width 为数字时应该设置对应的 px 值", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, width: 600 }
            });
            await nextTick();

            const dialog = document.querySelector(".vort-dialog") as HTMLElement;
            expect(dialog?.style.width).toBe("600px");
        });

        it("width 为字符串时应该直接使用", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, width: "50%" }
            });
            await nextTick();

            const dialog = document.querySelector(".vort-dialog") as HTMLElement;
            expect(dialog?.style.width).toBe("50%");
        });
    });

    // ==================== 居中模式 ====================
    describe("居中模式", () => {
        it("centered 为 true 时应该添加居中类名", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, centered: true }
            });
            await nextTick();

            const wrap = document.querySelector(".vort-dialog-wrap");
            expect(wrap?.classList.contains("vort-dialog-centered")).toBe(true);
        });

        it("centered 为 false 时不应该添加居中类名", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, centered: false }
            });
            await nextTick();

            const wrap = document.querySelector(".vort-dialog-wrap");
            expect(wrap?.classList.contains("vort-dialog-centered")).toBe(false);
        });
    });

    // ==================== 键盘事件 ====================
    describe("键盘事件", () => {
        it("keyboard 为 true 时按 ESC 应该关闭对话框", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, keyboard: true }
            });
            await nextTick();

            const event = new KeyboardEvent("keydown", { key: "Escape" });
            document.dispatchEvent(event);

            expect(wrapper.emitted("update:open")).toBeTruthy();
            expect(wrapper.emitted("cancel")).toBeTruthy();
        });

        it("keyboard 为 false 时按 ESC 不应该关闭对话框", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, keyboard: false }
            });
            await nextTick();

            const event = new KeyboardEvent("keydown", { key: "Escape" });
            document.dispatchEvent(event);

            expect(wrapper.emitted("update:open")).toBeFalsy();
        });
    });

    // ==================== z-index ====================
    describe("z-index", () => {
        it("应该正确设置 z-index", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, zIndex: 2000 }
            });
            await nextTick();

            const root = document.querySelector(".vort-dialog-root") as HTMLElement;
            expect(root?.style.zIndex).toBe("2000");
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, class: "my-custom-dialog" }
            });
            await nextTick();

            const dialog = document.querySelector(".vort-dialog");
            expect(dialog?.classList.contains("my-custom-dialog")).toBe(true);
        });

        it("应该支持自定义 wrapClass", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, wrapClass: "my-wrap-class" }
            });
            await nextTick();

            const root = document.querySelector(".vort-dialog-root");
            expect(root?.classList.contains("my-wrap-class")).toBe(true);
        });
    });

    // ==================== body 样式 ====================
    describe("body 样式", () => {
        it("bodyNoPadding 为 true 时应该移除内边距", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, bodyNoPadding: true }
            });
            await nextTick();

            const body = document.querySelector(".vort-dialog-body");
            expect(body?.classList.contains("vort-dialog-body-no-padding")).toBe(true);
        });

        it("应该支持自定义 contentBg", async () => {
            wrapper = mount(Dialog, {
                props: { open: true, contentBg: "#f0f0f0" }
            });
            await nextTick();

            const body = document.querySelector(".vort-dialog-body") as HTMLElement;
            expect(body?.style.background).toBe("rgb(240, 240, 240)");
        });
    });
});
