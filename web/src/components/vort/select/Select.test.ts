import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import Select from "./Select.vue";

// 测试选项数据
const mockOptions = [
    { value: "apple", label: "苹果" },
    { value: "banana", label: "香蕉" },
    { value: "orange", label: "橙子" },
    { value: "grape", label: "葡萄", disabled: true }
];

describe("Select 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染选择器", () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions }
            });
            expect(wrapper.find(".vort-select-selector").exists()).toBe(true);
        });

        it("应该显示默认占位文本", () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions }
            });
            expect(wrapper.find(".vort-select-placeholder").text()).toBe("请选择");
        });

        it("应该支持自定义占位文本", () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions, placeholder: "请选择水果" }
            });
            expect(wrapper.find(".vort-select-placeholder").text()).toBe("请选择水果");
        });

        it("应该有正确的基础类名", () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions }
            });
            expect(wrapper.find(".vort-select-selector").classes()).toContain("vort-select-selector");
        });
    });

    // ==================== v-model 绑定 ====================
    describe("v-model 绑定", () => {
        it("单选模式应该正确显示选中值", async () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    modelValue: "apple"
                }
            });
            await nextTick();
            expect(wrapper.find(".vort-select-value").text()).toBe("苹果");
        });

        it("选中后应该触发 update:modelValue 事件", async () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    modelValue: undefined
                }
            });

            // 点击打开下拉
            await wrapper.find(".vort-select-selector").trigger("click");
            await nextTick();

            // 模拟选中
            wrapper.vm.internalValue = "banana";
            await nextTick();

            expect(wrapper.emitted("update:modelValue")).toBeTruthy();
        });

        it("多选模式应该支持数组值", async () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    modelValue: ["apple", "banana"],
                    mode: "multiple"
                }
            });
            await nextTick();
            const tags = wrapper.findAll(".vort-select-tag");
            expect(tags.length).toBe(2);
        });
    });

    // ==================== 尺寸变体 ====================
    describe("尺寸 size", () => {
        it("默认尺寸应该是 middle", () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions }
            });
            expect(wrapper.find(".vort-select-selector").classes()).toContain("vort-select-middle");
        });

        it.each(["large", "middle", "small"] as const)('尺寸 "%s" 应该添加对应类名', (size) => {
            const wrapper = mount(Select, {
                props: { options: mockOptions, size }
            });
            expect(wrapper.find(".vort-select-selector").classes()).toContain(`vort-select-${size}`);
        });
    });

    // ==================== 状态（error/warning） ====================
    describe("状态 status", () => {
        it("error 状态应该添加对应类名", () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions, status: "error" }
            });
            expect(wrapper.find(".vort-select-selector").classes()).toContain("vort-select-error");
        });

        it("warning 状态应该添加对应类名", () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions, status: "warning" }
            });
            expect(wrapper.find(".vort-select-selector").classes()).toContain("vort-select-warning");
        });
    });

    // ==================== 禁用状态 ====================
    describe("禁用状态", () => {
        it("disabled 为 true 时应该添加禁用类名", () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions, disabled: true }
            });
            expect(wrapper.find(".vort-select-selector").classes()).toContain("vort-select-disabled");
        });

        it("disabled 时点击不应该打开下拉菜单", async () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions, disabled: true }
            });
            await wrapper.find(".vort-select-selector").trigger("click");
            await nextTick();
            expect(wrapper.vm.isOpen).toBe(false);
        });
    });

    // ==================== 清除功能 ====================
    describe("清除功能", () => {
        it("allowClear 为 false 时不应该显示清除按钮", async () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    modelValue: "apple",
                    allowClear: false
                }
            });
            // 模拟 hover
            await wrapper.find(".vort-select-selector").trigger("mouseenter");
            await nextTick();
            expect(wrapper.find(".vort-select-clear").exists()).toBe(false);
        });

        it("allowClear 为 true 且有值时应该显示清除按钮", async () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    modelValue: "apple",
                    allowClear: true
                }
            });
            // 模拟 hover
            await wrapper.find(".vort-select-selector").trigger("mouseenter");
            await nextTick();
            expect(wrapper.find(".vort-select-clear").exists()).toBe(true);
        });

        it("点击清除按钮应该清空值并触发 clear 事件", async () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    modelValue: "apple",
                    allowClear: true
                }
            });
            // 模拟 hover
            await wrapper.find(".vort-select-selector").trigger("mouseenter");
            await nextTick();

            const clearBtn = wrapper.find(".vort-select-clear");
            await clearBtn.trigger("click");
            await nextTick();

            expect(wrapper.emitted("clear")).toBeTruthy();
            expect(wrapper.emitted("update:modelValue")).toBeTruthy();
        });
    });

    // ==================== 搜索功能 ====================
    describe("搜索功能", () => {
        it("showSearch 为 true 时应该显示搜索输入框", async () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    showSearch: true
                }
            });
            expect(wrapper.find(".vort-select-search-input").exists()).toBe(true);
        });

        it("输入搜索内容应该触发 search 事件", async () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    showSearch: true
                }
            });

            const input = wrapper.find(".vort-select-search-input");
            await input.setValue("苹");
            await nextTick();

            expect(wrapper.emitted("search")).toBeTruthy();
        });

        it("搜索应该过滤选项", async () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    showSearch: true
                }
            });

            // 设置搜索值
            wrapper.vm.searchValue = "苹";
            await nextTick();

            // 检查 filteredOptions
            expect(wrapper.vm.filteredOptions.length).toBe(1);
            expect(wrapper.vm.filteredOptions[0].label).toBe("苹果");
        });

        it("支持自定义 filterOption 函数", async () => {
            const filterFn = vi.fn((inputValue: string, option: any) => {
                return option.value.includes(inputValue);
            });

            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    showSearch: true,
                    filterOption: filterFn
                }
            });

            wrapper.vm.searchValue = "app";
            await nextTick();

            // 访问 filteredOptions 触发计算
            const filtered = wrapper.vm.filteredOptions;
            expect(filterFn).toHaveBeenCalled();
            expect(filtered.length).toBe(1);
        });
    });

    // ==================== 多选模式 ====================
    describe("多选模式", () => {
        it('mode="multiple" 应该添加多选类名', () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    mode: "multiple"
                }
            });
            expect(wrapper.find(".vort-select-selector").classes()).toContain("vort-select-multiple");
        });

        it('mode="tags" 应该添加多选类名', () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    mode: "tags"
                }
            });
            expect(wrapper.find(".vort-select-selector").classes()).toContain("vort-select-multiple");
        });

        it("多选时应该显示已选标签", async () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    modelValue: ["apple", "banana"],
                    mode: "multiple"
                }
            });
            await nextTick();
            const tags = wrapper.findAll(".vort-select-tag:not(.vort-select-tag-placeholder)");
            expect(tags.length).toBe(2);
        });

        it("点击标签删除按钮应该移除该选项", async () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    modelValue: ["apple", "banana"],
                    mode: "multiple"
                }
            });
            await nextTick();

            const removeBtn = wrapper.find(".vort-select-tag-remove");
            await removeBtn.trigger("click");
            await nextTick();

            expect(wrapper.emitted("update:modelValue")).toBeTruthy();
            expect(wrapper.emitted("deselect")).toBeTruthy();
        });

        it("maxTagCount 应该限制显示的标签数量", async () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    modelValue: ["apple", "banana", "orange"],
                    mode: "multiple",
                    maxTagCount: 2
                }
            });
            await nextTick();

            const displayedTags = wrapper.findAll(".vort-select-tag:not(.vort-select-tag-placeholder)");
            expect(displayedTags.length).toBe(2);

            // 应该显示隐藏数量提示
            expect(wrapper.find(".vort-select-tag-placeholder").exists()).toBe(true);
        });
    });

    // ==================== 边框样式 ====================
    describe("边框样式", () => {
        it("bordered 默认为 true", () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions }
            });
            expect(wrapper.find(".vort-select-selector").classes()).not.toContain("vort-select-borderless");
        });

        it("bordered 为 false 时应该添加无边框类名", () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions, bordered: false }
            });
            expect(wrapper.find(".vort-select-selector").classes()).toContain("vort-select-borderless");
        });
    });

    // ==================== 自定义类名 ====================
    describe("自定义类名", () => {
        it("应该支持自定义 class", () => {
            const wrapper = mount(Select, {
                props: {
                    options: mockOptions,
                    class: "my-custom-select"
                }
            });
            expect(wrapper.find(".vort-select-selector").classes()).toContain("my-custom-select");
        });
    });

    // ==================== 事件 ====================
    describe("事件", () => {
        it("选中选项应该触发 select 事件", async () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions }
            });

            // 直接调用 handleSelect 方法
            wrapper.vm.handleSelect("apple");
            await nextTick();

            expect(wrapper.emitted("select")).toBeTruthy();
            const selectEvent = wrapper.emitted("select")![0];
            expect(selectEvent[0]).toBe("apple");
        });

        it("聚焦和失焦应该触发对应事件", async () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions }
            });

            const trigger = wrapper.find(".vort-select-selector");
            await trigger.trigger("focus");
            expect(wrapper.emitted("focus")).toBeTruthy();

            await trigger.trigger("blur");
            expect(wrapper.emitted("blur")).toBeTruthy();
        });
    });

    // ==================== 下拉箭头 ====================
    describe("下拉箭头", () => {
        it("应该显示下拉箭头", () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions }
            });
            expect(wrapper.find(".vort-select-arrow").exists()).toBe(true);
        });

        it("打开时箭头应该旋转", async () => {
            const wrapper = mount(Select, {
                props: { options: mockOptions }
            });

            // 打开下拉
            await wrapper.find(".vort-select-selector").trigger("click");
            await nextTick();

            expect(wrapper.find(".vort-select-arrow").classes()).toContain("vort-select-arrow-open");
        });
    });

    // ==================== 空数据提示 ====================
    describe("空数据提示", () => {
        it("应该支持自定义空数据提示", () => {
            const wrapper = mount(Select, {
                props: {
                    options: [],
                    notFoundContent: "没有找到数据"
                }
            });
            expect(wrapper.props("notFoundContent")).toBe("没有找到数据");
        });
    });
});
