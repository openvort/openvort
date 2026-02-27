import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import Upload from "./Upload.vue";
import UploadDragger from "./UploadDragger.vue";
import type { UploadFile } from "./types";

// Mock createObjectURL
const mockCreateObjectURL = vi.fn(() => "blob:mock-url");
const mockRevokeObjectURL = vi.fn();

beforeEach(() => {
    global.URL.createObjectURL = mockCreateObjectURL;
    global.URL.revokeObjectURL = mockRevokeObjectURL;
});

afterEach(() => {
    vi.restoreAllMocks();
});

describe("Upload 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染上传组件", () => {
            const wrapper = mount(Upload);
            expect(wrapper.find(".vort-upload").exists()).toBe(true);
        });

        it("应该渲染隐藏的文件输入框", () => {
            const wrapper = mount(Upload);
            const input = wrapper.find("input[type='file']");
            expect(input.exists()).toBe(true);
            expect(input.classes()).toContain("vort-upload-input");
        });

        it("应该渲染默认上传按钮", () => {
            const wrapper = mount(Upload);
            expect(wrapper.find(".vort-upload-btn").exists()).toBe(true);
        });

        it("应该支持自定义插槽内容", () => {
            const wrapper = mount(Upload, {
                slots: { default: "<span class='custom-trigger'>自定义上传</span>" }
            });
            expect(wrapper.find(".custom-trigger").exists()).toBe(true);
        });
    });

    // ==================== listType 属性 ====================
    describe("listType 属性", () => {
        it("默认 listType 应该是 text", () => {
            const wrapper = mount(Upload);
            expect(wrapper.find(".vort-upload-text").exists()).toBe(true);
        });

        it("listType='picture' 应该添加对应类名", () => {
            const wrapper = mount(Upload, {
                props: { listType: "picture" }
            });
            expect(wrapper.find(".vort-upload-picture").exists()).toBe(true);
        });

        it("listType='picture-card' 应该渲染卡片布局", () => {
            const wrapper = mount(Upload, {
                props: { listType: "picture-card" }
            });
            expect(wrapper.find(".vort-upload-picture-card").exists()).toBe(true);
            expect(wrapper.find(".vort-upload-list-card").exists()).toBe(true);
        });

        it("listType='picture-circle' 应该渲染圆形布局", () => {
            const wrapper = mount(Upload, {
                props: { listType: "picture-circle" }
            });
            expect(wrapper.find(".vort-upload-picture-circle").exists()).toBe(true);
        });
    });

    // ==================== 禁用状态 ====================
    describe("禁用状态", () => {
        it("disabled 为 true 时应该添加禁用类名", () => {
            const wrapper = mount(Upload, {
                props: { disabled: true }
            });
            expect(wrapper.find(".vort-upload-disabled").exists()).toBe(true);
        });

        it("disabled 为 true 时文件输入框应该被禁用", () => {
            const wrapper = mount(Upload, {
                props: { disabled: true }
            });
            expect(wrapper.find("input[type='file']").attributes("disabled")).toBeDefined();
        });

        it("disabled 为 true 时上传按钮应该被禁用", () => {
            const wrapper = mount(Upload, {
                props: { disabled: true }
            });
            expect(wrapper.find(".vort-upload-btn").attributes("disabled")).toBeDefined();
        });
    });

    // ==================== 文件输入属性 ====================
    describe("文件输入属性", () => {
        it("accept 属性应该正确传递到 input", () => {
            const wrapper = mount(Upload, {
                props: { accept: "image/*" }
            });
            expect(wrapper.find("input[type='file']").attributes("accept")).toBe("image/*");
        });

        it("multiple 属性应该正确传递到 input", () => {
            const wrapper = mount(Upload, {
                props: { multiple: true }
            });
            expect(wrapper.find("input[type='file']").attributes("multiple")).toBeDefined();
        });

        it("directory 属性应该设置 webkitdirectory", () => {
            const wrapper = mount(Upload, {
                props: { directory: true }
            });
            expect(wrapper.find("input[type='file']").attributes("webkitdirectory")).toBeDefined();
        });
    });

    // ==================== 文件列表 ====================
    describe("文件列表", () => {
        const mockFileList: UploadFile[] = [
            { uid: "1", name: "test1.png", status: "done" },
            { uid: "2", name: "test2.jpg", status: "done" }
        ];

        it("应该渲染 fileList 中的文件", () => {
            const wrapper = mount(Upload, {
                props: { fileList: mockFileList }
            });
            const items = wrapper.findAll(".vort-upload-list-item");
            expect(items.length).toBe(2);
        });

        it("应该显示文件名", () => {
            const wrapper = mount(Upload, {
                props: { fileList: mockFileList }
            });
            expect(wrapper.text()).toContain("test1.png");
            expect(wrapper.text()).toContain("test2.jpg");
        });

        it("showUploadList=false 时不应该显示文件列表", () => {
            const wrapper = mount(Upload, {
                props: { fileList: mockFileList, showUploadList: false }
            });
            expect(wrapper.find(".vort-upload-list-text").exists()).toBe(false);
        });

        it("应该根据文件状态添加对应类名", () => {
            const fileList: UploadFile[] = [
                { uid: "1", name: "uploading.png", status: "uploading" },
                { uid: "2", name: "done.png", status: "done" },
                { uid: "3", name: "error.png", status: "error" }
            ];
            const wrapper = mount(Upload, {
                props: { fileList }
            });
            expect(wrapper.find(".vort-upload-list-item-uploading").exists()).toBe(true);
            expect(wrapper.find(".vort-upload-list-item-done").exists()).toBe(true);
            expect(wrapper.find(".vort-upload-list-item-error").exists()).toBe(true);
        });
    });

    // ==================== maxCount 限制 ====================
    describe("maxCount 限制", () => {
        it("达到 maxCount 时不应该显示上传按钮（卡片模式）", () => {
            const fileList: UploadFile[] = [
                { uid: "1", name: "test1.png", status: "done" },
                { uid: "2", name: "test2.png", status: "done" }
            ];
            const wrapper = mount(Upload, {
                props: { listType: "picture-card", fileList, maxCount: 2 }
            });
            expect(wrapper.find(".vort-upload-select").exists()).toBe(false);
        });

        it("未达到 maxCount 时应该显示上传按钮（卡片模式）", () => {
            const fileList: UploadFile[] = [{ uid: "1", name: "test1.png", status: "done" }];
            const wrapper = mount(Upload, {
                props: { listType: "picture-card", fileList, maxCount: 2 }
            });
            expect(wrapper.find(".vort-upload-select").exists()).toBe(true);
        });
    });

    // ==================== 事件触发 ====================
    describe("事件触发", () => {
        it("点击移除按钮应该触发 remove 事件", async () => {
            const fileList: UploadFile[] = [{ uid: "1", name: "test.png", status: "done" }];
            const wrapper = mount(Upload, {
                props: { fileList }
            });

            // 先hover触发操作按钮显示
            const item = wrapper.find(".vort-upload-list-item");
            await item.trigger("mouseenter");

            const removeBtn = wrapper.find(".vort-upload-list-item-action");
            await removeBtn.trigger("click");
            expect(wrapper.emitted("remove")).toBeTruthy();
        });

        it("点击文件名应该触发 preview 事件", async () => {
            const fileList: UploadFile[] = [{ uid: "1", name: "test.png", status: "done" }];
            const wrapper = mount(Upload, {
                props: { fileList }
            });
            await wrapper.find(".vort-upload-list-item-name").trigger("click");
            expect(wrapper.emitted("preview")).toBeTruthy();
        });
    });

    // ==================== showUploadList 配置 ====================
    describe("showUploadList 配置", () => {
        const fileList: UploadFile[] = [{ uid: "1", name: "test.png", status: "done", url: "http://example.com/test.png" }];

        it("showDownloadIcon=true 时应该显示下载按钮", () => {
            const wrapper = mount(Upload, {
                props: {
                    fileList,
                    showUploadList: { showDownloadIcon: true, showRemoveIcon: true }
                }
            });
            // 下载按钮需要文件有 url 且状态为 done
            const buttons = wrapper.findAll(".vort-upload-list-item-action");
            expect(buttons.length).toBeGreaterThan(0);
        });

        it("showRemoveIcon=false 时不应该显示移除按钮", () => {
            const wrapper = mount(Upload, {
                props: {
                    fileList,
                    showUploadList: { showRemoveIcon: false }
                }
            });
            expect(wrapper.find(".vort-upload-list-item-action").exists()).toBe(false);
        });
    });

    // ==================== 卡片类型特殊渲染 ====================
    describe("卡片类型特殊渲染", () => {
        it("picture-card 应该渲染缩略图区域", () => {
            const fileList: UploadFile[] = [{ uid: "1", name: "test.png", status: "done", type: "image/png" }];
            const wrapper = mount(Upload, {
                props: { listType: "picture-card", fileList }
            });
            expect(wrapper.find(".vort-upload-list-item-thumbnail").exists()).toBe(true);
        });

        it("picture-circle 应该有圆形类名", () => {
            const fileList: UploadFile[] = [{ uid: "1", name: "test.png", status: "done" }];
            const wrapper = mount(Upload, {
                props: { listType: "picture-circle", fileList }
            });
            expect(wrapper.find(".vort-upload-list-item-circle").exists()).toBe(true);
        });

        it("上传中状态应该显示加载图标", () => {
            const fileList: UploadFile[] = [{ uid: "1", name: "test.png", status: "uploading", percent: 50 }];
            const wrapper = mount(Upload, {
                props: { listType: "picture-card", fileList }
            });
            expect(wrapper.find(".vort-upload-list-item-loading").exists()).toBe(true);
        });

        it("上传中状态应该显示进度条", () => {
            const fileList: UploadFile[] = [{ uid: "1", name: "test.png", status: "uploading", percent: 50 }];
            const wrapper = mount(Upload, {
                props: { listType: "picture-card", fileList }
            });
            expect(wrapper.find(".vort-upload-list-item-progress").exists()).toBe(true);
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", () => {
            const wrapper = mount(Upload, {
                props: { class: "my-custom-upload" }
            });
            expect(wrapper.find(".my-custom-upload").exists()).toBe(true);
        });
    });
});

describe("UploadDragger 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染拖拽上传组件", () => {
            const wrapper = mount(UploadDragger);
            expect(wrapper.find(".vort-upload-dragger").exists()).toBe(true);
        });

        it("应该渲染默认拖拽区域内容", () => {
            const wrapper = mount(UploadDragger);
            expect(wrapper.find(".vort-upload-dragger-content").exists()).toBe(true);
            expect(wrapper.find(".vort-upload-dragger-icon").exists()).toBe(true);
            expect(wrapper.find(".vort-upload-dragger-text").exists()).toBe(true);
            expect(wrapper.find(".vort-upload-dragger-hint").exists()).toBe(true);
        });

        it("应该支持自定义插槽内容", () => {
            const wrapper = mount(UploadDragger, {
                slots: { default: "<div class='custom-dragger'>自定义内容</div>" }
            });
            expect(wrapper.find(".custom-dragger").exists()).toBe(true);
        });
    });

    // ==================== 禁用状态 ====================
    describe("禁用状态", () => {
        it("disabled 为 true 时应该添加禁用类名", () => {
            const wrapper = mount(UploadDragger, {
                props: { disabled: true }
            });
            expect(wrapper.find(".vort-upload-dragger-disabled").exists()).toBe(true);
        });
    });

    // ==================== height 属性 ====================
    describe("height 属性", () => {
        it("应该支持数字类型的 height", () => {
            const wrapper = mount(UploadDragger, {
                props: { height: 300 }
            });
            const dragger = wrapper.find(".vort-upload-dragger");
            expect(dragger.attributes("style")).toContain("height: 300px");
        });

        it("应该支持字符串类型的 height", () => {
            const wrapper = mount(UploadDragger, {
                props: { height: "50vh" }
            });
            const dragger = wrapper.find(".vort-upload-dragger");
            expect(dragger.attributes("style")).toContain("height: 50vh");
        });
    });

    // ==================== 文件属性传递 ====================
    describe("文件属性传递", () => {
        it("默认 multiple 应该为 true", () => {
            const wrapper = mount(UploadDragger);
            const input = wrapper.find("input[type='file']");
            expect(input.attributes("multiple")).toBeDefined();
        });

        it("accept 属性应该正确传递", () => {
            const wrapper = mount(UploadDragger, {
                props: { accept: ".pdf,.doc" }
            });
            const input = wrapper.find("input[type='file']");
            expect(input.attributes("accept")).toBe(".pdf,.doc");
        });
    });

    // ==================== 文件列表 ====================
    describe("文件列表", () => {
        const mockFileList: UploadFile[] = [
            { uid: "1", name: "doc1.pdf", status: "done" },
            { uid: "2", name: "doc2.pdf", status: "done" }
        ];

        it("应该渲染文件列表", () => {
            const wrapper = mount(UploadDragger, {
                props: { fileList: mockFileList }
            });
            expect(wrapper.text()).toContain("doc1.pdf");
            expect(wrapper.text()).toContain("doc2.pdf");
        });
    });

    // ==================== 事件触发 ====================
    describe("事件触发", () => {
        it("拖拽文件进入时应该显示高亮状态", async () => {
            const wrapper = mount(UploadDragger);
            const dragger = wrapper.find(".vort-upload-dragger");

            await dragger.trigger("dragenter");
            expect(wrapper.find(".vort-upload-dragger-drag-hover").exists()).toBe(true);
        });

        it("拖拽文件离开时应该移除高亮状态", async () => {
            const wrapper = mount(UploadDragger);
            const dragger = wrapper.find(".vort-upload-dragger");

            await dragger.trigger("dragenter");
            expect(wrapper.find(".vort-upload-dragger-drag-hover").exists()).toBe(true);

            await dragger.trigger("dragleave");
            expect(wrapper.find(".vort-upload-dragger-drag-hover").exists()).toBe(false);
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", () => {
            const wrapper = mount(UploadDragger, {
                props: { class: "my-custom-dragger" }
            });
            expect(wrapper.find(".my-custom-dragger").exists()).toBe(true);
        });
    });
});
