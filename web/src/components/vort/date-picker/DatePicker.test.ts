import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, VueWrapper } from "@vue/test-utils";
import DatePicker from "./DatePicker.vue";
import RangePicker from "./RangePicker.vue";

// Mock Teleport
vi.mock("vue", async () => {
    const actual = await vi.importActual("vue");
    return {
        ...actual,
        Teleport: (props: any, { slots }: any) => slots.default?.()
    };
});

describe("DatePicker 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染日期选择器", () => {
            const wrapper = mount(DatePicker);
            expect(wrapper.find(".vort-datepicker-selector").exists()).toBe(true);
        });

        it("应该显示默认 placeholder", () => {
            const wrapper = mount(DatePicker);
            expect(wrapper.text()).toContain("请选择日期");
        });

        it("应该显示自定义 placeholder", () => {
            const wrapper = mount(DatePicker, {
                props: { placeholder: "选择开始日期" }
            });
            expect(wrapper.text()).toContain("选择开始日期");
        });

        it("showTime 模式应该显示对应 placeholder", () => {
            const wrapper = mount(DatePicker, {
                props: { showTime: true }
            });
            expect(wrapper.text()).toContain("请选择日期时间");
        });
    });

    // ==================== 尺寸 (size) ====================
    describe("尺寸 size", () => {
        it("默认尺寸应该是 middle", () => {
            const wrapper = mount(DatePicker);
            expect(wrapper.find(".vort-datepicker-middle").exists()).toBe(true);
        });

        it.each(["large", "middle", "small"] as const)('尺寸 "%s" 应该添加对应类名', (size) => {
            const wrapper = mount(DatePicker, {
                props: { size }
            });
            expect(wrapper.find(`.vort-datepicker-${size}`).exists()).toBe(true);
        });
    });

    // ==================== 状态 ====================
    describe("状态", () => {
        it("error 状态应该添加对应类名", () => {
            const wrapper = mount(DatePicker, {
                props: { status: "error" }
            });
            expect(wrapper.find(".vort-datepicker-error").exists()).toBe(true);
        });

        it("warning 状态应该添加对应类名", () => {
            const wrapper = mount(DatePicker, {
                props: { status: "warning" }
            });
            expect(wrapper.find(".vort-datepicker-warning").exists()).toBe(true);
        });

        it("disabled 状态应该添加对应类名", () => {
            const wrapper = mount(DatePicker, {
                props: { disabled: true }
            });
            expect(wrapper.find(".vort-datepicker-disabled").exists()).toBe(true);
        });
    });

    // ==================== 值绑定 ====================
    describe("值绑定", () => {
        it("应该正确显示 Date 对象的值", () => {
            const date = new Date(2024, 0, 15); // 2024-01-15
            const wrapper = mount(DatePicker, {
                props: { modelValue: date }
            });
            expect(wrapper.text()).toContain("2024-01-15");
        });

        it("应该正确显示字符串日期值", () => {
            const wrapper = mount(DatePicker, {
                props: { modelValue: "2024-06-20" }
            });
            expect(wrapper.text()).toContain("2024-06-20");
        });

        it("应该正确显示时间戳值", () => {
            const timestamp = new Date(2024, 5, 20).getTime();
            const wrapper = mount(DatePicker, {
                props: { modelValue: timestamp }
            });
            expect(wrapper.text()).toContain("2024-06-20");
        });

        it("空值应该显示 placeholder", () => {
            const wrapper = mount(DatePicker, {
                props: { modelValue: null }
            });
            expect(wrapper.text()).toContain("请选择日期");
        });
    });

    // ==================== 格式化 ====================
    describe("格式化", () => {
        it("应该支持自定义显示格式", () => {
            const date = new Date(2024, 0, 15);
            const wrapper = mount(DatePicker, {
                props: {
                    modelValue: date,
                    format: "YYYY/MM/DD"
                }
            });
            expect(wrapper.text()).toContain("2024/01/15");
        });

        it("picker=month 时应该显示年月格式", () => {
            const date = new Date(2024, 5, 1);
            const wrapper = mount(DatePicker, {
                props: {
                    modelValue: date,
                    picker: "month"
                }
            });
            expect(wrapper.text()).toContain("2024-06");
        });

        it("picker=year 时应该显示年份格式", () => {
            const date = new Date(2024, 0, 1);
            const wrapper = mount(DatePicker, {
                props: {
                    modelValue: date,
                    picker: "year"
                }
            });
            expect(wrapper.text()).toContain("2024");
        });

        it("showTime 模式应该显示时间", () => {
            const date = new Date(2024, 0, 15, 14, 30, 45);
            const wrapper = mount(DatePicker, {
                props: {
                    modelValue: date,
                    showTime: true
                }
            });
            expect(wrapper.text()).toContain("2024-01-15 14:30:45");
        });
    });

    // ==================== picker 类型 ====================
    describe("picker 类型", () => {
        it.each(["date", "month", "year"] as const)('picker="%s" 应该正确设置', (picker) => {
            const wrapper = mount(DatePicker, {
                props: { picker }
            });
            expect(wrapper.vm).toBeDefined();
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", () => {
            const wrapper = mount(DatePicker, {
                props: { class: "my-custom-picker" }
            });
            expect(wrapper.find(".my-custom-picker").exists()).toBe(true);
        });
    });
});

describe("RangePicker 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染范围选择器", () => {
            const wrapper = mount(RangePicker);
            expect(wrapper.find(".vort-rangepicker-selector").exists()).toBe(true);
        });

        it("应该显示默认 placeholder", () => {
            const wrapper = mount(RangePicker);
            expect(wrapper.text()).toContain("开始日期");
            expect(wrapper.text()).toContain("结束日期");
        });

        it("应该显示自定义 placeholder", () => {
            const wrapper = mount(RangePicker, {
                props: { placeholder: ["起始", "截止"] }
            });
            expect(wrapper.text()).toContain("起始");
            expect(wrapper.text()).toContain("截止");
        });

        it("应该显示分隔符", () => {
            const wrapper = mount(RangePicker);
            expect(wrapper.find(".vort-rangepicker-separator").text()).toBe("~");
        });

        it("应该支持自定义分隔符", () => {
            const wrapper = mount(RangePicker, {
                props: { separator: "至" }
            });
            expect(wrapper.find(".vort-rangepicker-separator").text()).toBe("至");
        });
    });

    // ==================== 尺寸 (size) ====================
    describe("尺寸 size", () => {
        it("默认尺寸应该是 middle", () => {
            const wrapper = mount(RangePicker);
            expect(wrapper.find(".vort-rangepicker-middle").exists()).toBe(true);
        });

        it.each(["large", "middle", "small"] as const)('尺寸 "%s" 应该添加对应类名', (size) => {
            const wrapper = mount(RangePicker, {
                props: { size }
            });
            expect(wrapper.find(`.vort-rangepicker-${size}`).exists()).toBe(true);
        });
    });

    // ==================== 状态 ====================
    describe("状态", () => {
        it("error 状态应该添加对应类名", () => {
            const wrapper = mount(RangePicker, {
                props: { status: "error" }
            });
            expect(wrapper.find(".vort-rangepicker-error").exists()).toBe(true);
        });

        it("warning 状态应该添加对应类名", () => {
            const wrapper = mount(RangePicker, {
                props: { status: "warning" }
            });
            expect(wrapper.find(".vort-rangepicker-warning").exists()).toBe(true);
        });

        it("disabled 状态应该添加对应类名", () => {
            const wrapper = mount(RangePicker, {
                props: { disabled: true }
            });
            expect(wrapper.find(".vort-rangepicker-disabled").exists()).toBe(true);
        });
    });

    // ==================== 值绑定 ====================
    describe("值绑定", () => {
        it("应该正确显示范围值", () => {
            const startDate = new Date(2024, 0, 1);
            const endDate = new Date(2024, 0, 31);
            const wrapper = mount(RangePicker, {
                props: { modelValue: [startDate, endDate] }
            });
            expect(wrapper.text()).toContain("2024-01-01");
            expect(wrapper.text()).toContain("2024-01-31");
        });

        it("空值应该显示 placeholder", () => {
            const wrapper = mount(RangePicker, {
                props: { modelValue: null }
            });
            expect(wrapper.text()).toContain("开始日期");
            expect(wrapper.text()).toContain("结束日期");
        });

        it("只有开始日期时应该只显示开始日期", () => {
            const startDate = new Date(2024, 0, 1);
            const wrapper = mount(RangePicker, {
                props: { modelValue: [startDate, null] }
            });
            expect(wrapper.text()).toContain("2024-01-01");
            expect(wrapper.text()).toContain("结束日期");
        });
    });

    // ==================== 格式化 ====================
    describe("格式化", () => {
        it("应该支持自定义显示格式", () => {
            const startDate = new Date(2024, 0, 1);
            const endDate = new Date(2024, 0, 31);
            const wrapper = mount(RangePicker, {
                props: {
                    modelValue: [startDate, endDate],
                    format: "YYYY/MM/DD"
                }
            });
            expect(wrapper.text()).toContain("2024/01/01");
            expect(wrapper.text()).toContain("2024/01/31");
        });

        it("showTime 模式应该显示时间", () => {
            const startDate = new Date(2024, 0, 1, 9, 0, 0);
            const endDate = new Date(2024, 0, 31, 18, 0, 0);
            const wrapper = mount(RangePicker, {
                props: {
                    modelValue: [startDate, endDate],
                    showTime: true
                }
            });
            expect(wrapper.text()).toContain("2024-01-01 09:00:00");
            expect(wrapper.text()).toContain("2024-01-31 18:00:00");
        });
    });

    // ==================== showTime 模式 ====================
    describe("showTime 模式", () => {
        it("showTime 应该添加对应类名", () => {
            const wrapper = mount(RangePicker, {
                props: { showTime: true }
            });
            expect(wrapper.find(".vort-rangepicker-showtime").exists()).toBe(true);
        });

        it("showTime 模式应该显示日期时间 placeholder", () => {
            const wrapper = mount(RangePicker, {
                props: { showTime: true }
            });
            expect(wrapper.text()).toContain("开始日期时间");
            expect(wrapper.text()).toContain("结束日期时间");
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", () => {
            const wrapper = mount(RangePicker, {
                props: { class: "my-custom-range-picker" }
            });
            expect(wrapper.find(".my-custom-range-picker").exists()).toBe(true);
        });
    });
});
