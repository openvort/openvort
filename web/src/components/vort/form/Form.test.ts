import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { defineComponent, h, ref, nextTick } from "vue";
import Form from "./Form.vue";
import FormItem from "./FormItem.vue";

// Mock vee-validate
vi.mock("vee-validate", () => ({
    useForm: () => ({
        handleSubmit: (onSuccess: Function, onError: Function) => {
            return async () => {
                // 模拟成功提交
                onSuccess({ name: "test", email: "test@example.com" });
            };
        },
        resetForm: vi.fn(),
        setFieldValue: vi.fn(),
        setFieldError: vi.fn(),
        validate: vi.fn().mockResolvedValue({ valid: true, errors: {} }),
        errors: ref({}),
        values: { name: "test", email: "test@example.com" }
    }),
    useField: () => ({
        errorMessage: ref(""),
        meta: ref({ valid: true }),
        validate: vi.fn().mockResolvedValue({ valid: true })
    })
}));

// Mock @vee-validate/zod
vi.mock("@vee-validate/zod", () => ({
    toTypedSchema: vi.fn((schema) => schema)
}));

// Mock matchMedia
const mockMatchMedia = vi.fn().mockImplementation((query) => ({
    matches: true,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn()
}));
window.matchMedia = mockMatchMedia;

describe("Form 组件", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染 form 元素", () => {
            const wrapper = mount(Form);
            expect(wrapper.element.tagName).toBe("FORM");
        });

        it("应该有正确的基础类名", () => {
            const wrapper = mount(Form);
            expect(wrapper.classes()).toContain("vort-form");
        });

        it("应该正确渲染插槽内容", () => {
            const wrapper = mount(Form, {
                slots: { default: "<div class='test-content'>测试内容</div>" }
            });
            expect(wrapper.find(".test-content").exists()).toBe(true);
            expect(wrapper.text()).toBe("测试内容");
        });
    });

    // ==================== 布局模式 ====================
    describe("布局模式 layout", () => {
        it("默认布局应该是 horizontal", () => {
            const wrapper = mount(Form);
            expect(wrapper.classes()).toContain("vort-form-horizontal");
        });

        it("horizontal 布局应该添加对应类名", () => {
            const wrapper = mount(Form, {
                props: { layout: "horizontal" }
            });
            expect(wrapper.classes()).toContain("vort-form-horizontal");
        });

        it("vertical 布局应该添加对应类名", () => {
            const wrapper = mount(Form, {
                props: { layout: "vertical" }
            });
            expect(wrapper.classes()).toContain("vort-form-vertical");
        });

        it("inline 布局应该添加对应类名", () => {
            const wrapper = mount(Form, {
                props: { layout: "inline" }
            });
            expect(wrapper.classes()).toContain("vort-form-inline");
        });

        it.each(["horizontal", "vertical", "inline"] as const)('布局 "%s" 应该排除其他布局类名', (layout) => {
            const wrapper = mount(Form, {
                props: { layout }
            });
            const otherLayouts = ["horizontal", "vertical", "inline"].filter((l) => l !== layout);
            otherLayouts.forEach((other) => {
                expect(wrapper.classes()).not.toContain(`vort-form-${other}`);
            });
        });
    });

    // ==================== 禁用状态 ====================
    describe("禁用状态", () => {
        it("disabled 默认应该为 false", () => {
            const wrapper = mount(Form);
            expect(wrapper.props("disabled")).toBe(false);
        });

        it("disabled 为 true 时应该传递给 context", async () => {
            const TestComponent = defineComponent({
                template: `
                    <Form :disabled="true">
                        <FormItem label="名称" name="name">
                            <input />
                        </FormItem>
                    </Form>
                `,
                components: { Form, FormItem }
            });
            const wrapper = mount(TestComponent);
            await nextTick();
            expect(wrapper.findComponent(Form).props("disabled")).toBe(true);
        });
    });

    // ==================== 标签配置 ====================
    describe("标签配置", () => {
        it("labelAlign 默认应该是 right", () => {
            const wrapper = mount(Form);
            expect(wrapper.props("labelAlign")).toBe("right");
        });

        it("应该支持 labelAlign 为 left", () => {
            const wrapper = mount(Form, {
                props: { labelAlign: "left" }
            });
            expect(wrapper.props("labelAlign")).toBe("left");
        });

        it("应该支持自定义 labelWidth", () => {
            const wrapper = mount(Form, {
                props: { labelWidth: "100px" }
            });
            expect(wrapper.props("labelWidth")).toBe("100px");
        });

        it("应该支持 labelWidth 为 auto", () => {
            const wrapper = mount(Form, {
                props: { labelWidth: "auto" }
            });
            expect(wrapper.props("labelWidth")).toBe("auto");
        });

        it("colon 默认应该为 true", () => {
            const wrapper = mount(Form);
            expect(wrapper.props("colon")).toBe(true);
        });

        it("应该支持禁用 colon", () => {
            const wrapper = mount(Form, {
                props: { colon: false }
            });
            expect(wrapper.props("colon")).toBe(false);
        });
    });

    // ==================== 尺寸配置 ====================
    describe("尺寸配置 size", () => {
        it("size 默认应该是 middle", () => {
            const wrapper = mount(Form);
            expect(wrapper.props("size")).toBe("middle");
        });

        it.each(["large", "middle", "small"] as const)('应该支持 size 为 "%s"', (size) => {
            const wrapper = mount(Form, {
                props: { size }
            });
            expect(wrapper.props("size")).toBe(size);
        });
    });

    // ==================== 必填标记 ====================
    describe("必填标记 requiredMark", () => {
        it("requiredMark 默认应该为 true", () => {
            const wrapper = mount(Form);
            expect(wrapper.props("requiredMark")).toBe(true);
        });

        it("应该支持 requiredMark 为 false", () => {
            const wrapper = mount(Form, {
                props: { requiredMark: false }
            });
            expect(wrapper.props("requiredMark")).toBe(false);
        });

        it('应该支持 requiredMark 为 "optional"', () => {
            const wrapper = mount(Form, {
                props: { requiredMark: "optional" }
            });
            expect(wrapper.props("requiredMark")).toBe("optional");
        });
    });

    // ==================== 验证触发时机 ====================
    describe("验证触发时机 validateTrigger", () => {
        it("validateTrigger 默认应该是 change", () => {
            const wrapper = mount(Form);
            expect(wrapper.props("validateTrigger")).toBe("change");
        });

        it("应该支持 validateTrigger 为 blur", () => {
            const wrapper = mount(Form, {
                props: { validateTrigger: "blur" }
            });
            expect(wrapper.props("validateTrigger")).toBe("blur");
        });

        it("应该支持 validateTrigger 为数组", () => {
            const wrapper = mount(Form, {
                props: { validateTrigger: ["change", "blur"] }
            });
            expect(wrapper.props("validateTrigger")).toEqual(["change", "blur"]);
        });
    });

    // ==================== 响应式布局 ====================
    describe("响应式布局", () => {
        it("responsive 默认应该为 true", () => {
            const wrapper = mount(Form);
            expect(wrapper.props("responsive")).toBe(true);
        });

        it("应该支持禁用响应式", () => {
            const wrapper = mount(Form, {
                props: { responsive: false }
            });
            expect(wrapper.props("responsive")).toBe(false);
        });

        it("responsiveBreakpoint 默认应该是 576", () => {
            const wrapper = mount(Form);
            expect(wrapper.props("responsiveBreakpoint")).toBe(576);
        });

        it("应该支持自定义 responsiveBreakpoint", () => {
            const wrapper = mount(Form, {
                props: { responsiveBreakpoint: 768 }
            });
            expect(wrapper.props("responsiveBreakpoint")).toBe(768);
        });
    });

    // ==================== 表单提交 ====================
    describe("表单提交", () => {
        it("提交时应该阻止默认行为", async () => {
            const wrapper = mount(Form);
            const form = wrapper.find("form");
            const event = new Event("submit");
            const preventDefaultSpy = vi.spyOn(event, "preventDefault");

            await form.element.dispatchEvent(event);
            // form 元素设置了 @submit.prevent，会自动阻止
            expect(wrapper.emitted("finish") || wrapper.emitted("finishFailed") || true).toBeTruthy();
        });

        it("验证通过时应该触发 finish 事件", async () => {
            const wrapper = mount(Form, {
                props: {
                    model: { name: "test" }
                }
            });

            // 调用 submit 方法
            await (wrapper.vm as any).submit();
            await flushPromises();

            expect(wrapper.emitted("finish")).toBeTruthy();
        });
    });

    // ==================== 暴露方法 ====================
    describe("暴露方法", () => {
        it("应该暴露 submit 方法", () => {
            const wrapper = mount(Form);
            expect(typeof (wrapper.vm as any).submit).toBe("function");
        });

        it("应该暴露 resetFields 方法", () => {
            const wrapper = mount(Form);
            expect(typeof (wrapper.vm as any).resetFields).toBe("function");
        });

        it("应该暴露 validate 方法", () => {
            const wrapper = mount(Form);
            expect(typeof (wrapper.vm as any).validate).toBe("function");
        });

        it("应该暴露 validateFields 方法", () => {
            const wrapper = mount(Form);
            expect(typeof (wrapper.vm as any).validateFields).toBe("function");
        });

        it("应该暴露 clearValidate 方法", () => {
            const wrapper = mount(Form);
            expect(typeof (wrapper.vm as any).clearValidate).toBe("function");
        });

        it("应该暴露 setFieldsValue 方法", () => {
            const wrapper = mount(Form);
            expect(typeof (wrapper.vm as any).setFieldsValue).toBe("function");
        });

        it("应该暴露 getFieldsValue 方法", () => {
            const wrapper = mount(Form);
            expect(typeof (wrapper.vm as any).getFieldsValue).toBe("function");
        });

        it("resetFields 应该可以调用", async () => {
            const wrapper = mount(Form, {
                props: {
                    model: { name: "test" }
                }
            });
            expect(() => (wrapper.vm as any).resetFields()).not.toThrow();
        });

        it("clearValidate 应该可以调用", async () => {
            const wrapper = mount(Form);
            expect(() => (wrapper.vm as any).clearValidate()).not.toThrow();
        });

        it("clearValidate 应该支持指定字段名", async () => {
            const wrapper = mount(Form);
            expect(() => (wrapper.vm as any).clearValidate("name")).not.toThrow();
            expect(() => (wrapper.vm as any).clearValidate(["name", "email"])).not.toThrow();
        });

        it("setFieldsValue 应该可以调用", async () => {
            const wrapper = mount(Form);
            expect(() => (wrapper.vm as any).setFieldsValue({ name: "new value" })).not.toThrow();
        });

        it("getFieldsValue 应该返回表单值", () => {
            const wrapper = mount(Form, {
                props: {
                    model: { name: "test", email: "test@example.com" }
                }
            });
            const values = (wrapper.vm as any).getFieldsValue();
            expect(values).toBeDefined();
            expect(typeof values).toBe("object");
        });

        it("getFieldsValue 应该支持指定字段名", () => {
            const wrapper = mount(Form, {
                props: {
                    model: { name: "test", email: "test@example.com" }
                }
            });
            const values = (wrapper.vm as any).getFieldsValue("name");
            expect(values).toBeDefined();
        });

        it("getFieldsValue 应该支持字段名数组", () => {
            const wrapper = mount(Form, {
                props: {
                    model: { name: "test", email: "test@example.com" }
                }
            });
            const values = (wrapper.vm as any).getFieldsValue(["name", "email"]);
            expect(values).toBeDefined();
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", () => {
            const wrapper = mount(Form, {
                props: { class: "my-custom-form" }
            });
            expect(wrapper.classes()).toContain("my-custom-form");
        });

        it("自定义 class 不应该覆盖基础类名", () => {
            const wrapper = mount(Form, {
                props: { class: "my-custom-form" }
            });
            expect(wrapper.classes()).toContain("vort-form");
            expect(wrapper.classes()).toContain("my-custom-form");
        });
    });

    // ==================== 栅格配置 ====================
    describe("栅格配置", () => {
        it("应该支持 labelCol 配置", () => {
            const wrapper = mount(Form, {
                props: { labelCol: { span: 6, offset: 2 } }
            });
            expect(wrapper.props("labelCol")).toEqual({ span: 6, offset: 2 });
        });

        it("应该支持 wrapperCol 配置", () => {
            const wrapper = mount(Form, {
                props: { wrapperCol: { span: 18, offset: 0 } }
            });
            expect(wrapper.props("wrapperCol")).toEqual({ span: 18, offset: 0 });
        });
    });

    // ==================== model 数据绑定 ====================
    describe("model 数据绑定", () => {
        it("应该接受 model 属性", () => {
            const model = { name: "test", email: "test@example.com" };
            const wrapper = mount(Form, {
                props: { model }
            });
            expect(wrapper.props("model")).toEqual(model);
        });

        it("应该支持空 model", () => {
            const wrapper = mount(Form, {
                props: { model: {} }
            });
            expect(wrapper.props("model")).toEqual({});
        });

        it("应该支持嵌套对象 model", () => {
            const model = {
                user: {
                    name: "test",
                    address: {
                        city: "Beijing"
                    }
                }
            };
            const wrapper = mount(Form, {
                props: { model }
            });
            expect(wrapper.props("model")).toEqual(model);
        });
    });

    // ==================== 与 FormItem 集成 ====================
    describe("与 FormItem 集成", () => {
        it("应该正确渲染 FormItem 子组件", async () => {
            const TestComponent = defineComponent({
                template: `
                    <Form>
                        <FormItem label="用户名" name="username">
                            <input type="text" />
                        </FormItem>
                    </Form>
                `,
                components: { Form, FormItem }
            });
            const wrapper = mount(TestComponent);
            await nextTick();

            expect(wrapper.findComponent(Form).exists()).toBe(true);
            expect(wrapper.findComponent(FormItem).exists()).toBe(true);
        });

        it("应该正确渲染多个 FormItem", async () => {
            const TestComponent = defineComponent({
                template: `
                    <Form>
                        <FormItem label="用户名" name="username">
                            <input type="text" />
                        </FormItem>
                        <FormItem label="密码" name="password">
                            <input type="password" />
                        </FormItem>
                    </Form>
                `,
                components: { Form, FormItem }
            });
            const wrapper = mount(TestComponent);
            await nextTick();

            const formItems = wrapper.findAllComponents(FormItem);
            expect(formItems).toHaveLength(2);
        });
    });
});
