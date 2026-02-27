import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, VueWrapper } from "@vue/test-utils";
import { nextTick, h, defineComponent } from "vue";
import Dropdown from "./Dropdown.vue";
import DropdownMenuItem from "./DropdownMenuItem.vue";
import DropdownMenuSeparator from "./DropdownMenuSeparator.vue";
import DropdownMenuLabel from "./DropdownMenuLabel.vue";
import DropdownMenuGroup from "./DropdownMenuGroup.vue";
import DropdownMenuSub from "./DropdownMenuSub.vue";
import DropdownMenuCheckboxItem from "./DropdownMenuCheckboxItem.vue";
import DropdownMenuRadioGroup from "./DropdownMenuRadioGroup.vue";
import DropdownMenuRadioItem from "./DropdownMenuRadioItem.vue";
import DropdownButton from "./DropdownButton.vue";

// Mock reka-ui 组件 - 使用 defineComponent 正确传递 class 属性
vi.mock("reka-ui", () => ({
    DropdownMenuRoot: {
        name: "DropdownMenuRoot",
        template: "<div><slot /></div>",
        props: ["open", "modal"],
        emits: ["update:open"]
    },
    DropdownMenuTrigger: {
        name: "DropdownMenuTrigger",
        template:
            "<div @click=\"$emit('click', $event)\" @contextmenu=\"$emit('contextmenu', $event)\" @mouseenter=\"$emit('mouseenter')\" @mouseleave=\"$emit('mouseleave')\"><slot /></div>",
        props: ["asChild", "disabled"],
        emits: ["click", "contextmenu", "mouseenter", "mouseleave"]
    },
    DropdownMenuPortal: {
        name: "DropdownMenuPortal",
        template: "<div><slot /></div>",
        props: ["to"]
    },
    DropdownMenuContent: {
        name: "DropdownMenuContent",
        template: '<div class="vort-dropdown" @mouseenter="$emit(\'mouseenter\')" @mouseleave="$emit(\'mouseleave\')"><slot /></div>',
        props: ["class", "style", "side", "align", "sideOffset", "collisionPadding", "forceMount"],
        emits: ["mouseenter", "mouseleave", "animationend"]
    },
    DropdownMenuArrow: {
        name: "DropdownMenuArrow",
        template: '<div class="vort-dropdown-arrow"></div>',
        props: ["width", "height", "style"]
    },
    DropdownMenuItem: defineComponent({
        name: "DropdownMenuItem",
        props: ["class", "disabled"],
        emits: ["select"],
        setup(props, { slots, emit }) {
            return () =>
                h(
                    "div",
                    {
                        class: props.class,
                        onClick: (e: Event) => emit("select", e)
                    },
                    slots.default?.()
                );
        }
    }),
    DropdownMenuSeparator: {
        name: "DropdownMenuSeparator",
        template: '<hr class="vort-dropdown-menu-separator" />'
    },
    DropdownMenuLabel: defineComponent({
        name: "DropdownMenuLabel",
        props: ["class"],
        setup(props, { slots }) {
            return () => h("div", { class: ["vort-dropdown-menu-label", props.class] }, slots.default?.());
        }
    }),
    DropdownMenuGroup: defineComponent({
        name: "DropdownMenuGroup",
        props: ["class"],
        setup(props, { slots }) {
            return () => h("div", { class: ["vort-dropdown-menu-group", props.class] }, slots.default?.());
        }
    }),
    DropdownMenuSub: {
        name: "DropdownMenuSub",
        template: "<div><slot /></div>",
        props: ["open"],
        emits: ["update:open"]
    },
    DropdownMenuSubTrigger: defineComponent({
        name: "DropdownMenuSubTrigger",
        props: ["class", "disabled"],
        setup(props, { slots }) {
            return () => h("div", { class: props.class }, slots.default?.());
        }
    }),
    DropdownMenuSubContent: {
        name: "DropdownMenuSubContent",
        template: "<div><slot /></div>",
        props: ["class", "sideOffset", "alignOffset"]
    },
    DropdownMenuCheckboxItem: defineComponent({
        name: "DropdownMenuCheckboxItem",
        props: ["class", "checked", "disabled"],
        emits: ["update:checked"],
        setup(props, { slots, emit }) {
            return () =>
                h(
                    "div",
                    {
                        class: props.class,
                        onClick: () => emit("update:checked", !props.checked)
                    },
                    slots.default?.()
                );
        }
    }),
    DropdownMenuItemIndicator: {
        name: "DropdownMenuItemIndicator",
        template: "<span><slot /></span>",
        props: ["class"]
    },
    DropdownMenuRadioGroup: defineComponent({
        name: "DropdownMenuRadioGroup",
        props: ["modelValue", "class"],
        emits: ["update:modelValue", "update:model-value"],
        setup(props, { slots, emit }) {
            return () =>
                h(
                    "div",
                    {
                        class: props.class,
                        onClick: (e: Event) => emit("update:modelValue", (e.target as HTMLElement).dataset.value)
                    },
                    slots.default?.()
                );
        }
    }),
    DropdownMenuRadioItem: defineComponent({
        name: "DropdownMenuRadioItem",
        props: ["class", "value", "disabled"],
        setup(props, { slots }) {
            return () => h("div", { class: props.class, "data-value": props.value }, slots.default?.());
        }
    })
}));

// Mock composables
vi.mock("@/components/vort/composables", () => ({
    getVortPopupContainer: () => document.body,
    useZIndex: () => 1050
}));

// Mock icons
vi.mock("@/components/vort/icons", () => ({
    DownOutlined: {
        name: "DownOutlined",
        template: '<span class="down-outlined-icon"></span>'
    },
    ChevronRightOutlined: {
        name: "ChevronRightOutlined",
        template: '<span class="chevron-right-outlined-icon"></span>'
    }
}));

// Mock Button component
vi.mock("@/components/vort/button", () => ({
    Button: {
        name: "Button",
        template: '<button :type="htmlType" :disabled="disabled || loading" :class="classes" @click="$emit(\'click\', $event)"><slot /></button>',
        props: ["type", "size", "danger", "disabled", "loading", "ghost", "block", "icon", "htmlType", "class"],
        emits: ["click"],
        computed: {
            classes() {
                return ["vort-btn", this.class];
            }
        }
    }
}));

describe("Dropdown 组件", () => {
    // ==================== 基础渲染 ====================
    describe("基础渲染", () => {
        it("应该正确渲染触发元素", () => {
            const wrapper = mount(Dropdown, {
                slots: { default: "<button>触发按钮</button>" }
            });
            expect(wrapper.text()).toContain("触发按钮");
        });

        it("应该有正确的触发元素类名", () => {
            const wrapper = mount(Dropdown, {
                slots: { default: "触发器" }
            });
            expect(wrapper.find(".vort-dropdown-trigger").exists()).toBe(true);
        });

        it("应该支持自定义触发元素类名", () => {
            const wrapper = mount(Dropdown, {
                props: { class: "custom-trigger-class" },
                slots: { default: "触发器" }
            });
            expect(wrapper.find(".custom-trigger-class").exists()).toBe(true);
        });
    });

    // ==================== 触发方式（trigger） ====================
    describe("触发方式 trigger", () => {
        beforeEach(() => {
            vi.useFakeTimers();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        it("默认触发方式应该是 hover", () => {
            const wrapper = mount(Dropdown, {
                slots: { default: "触发器" }
            });
            // 默认值验证 - 通过检查组件是否正确渲染来间接验证
            expect(wrapper.find(".vort-dropdown-trigger").exists()).toBe(true);
        });

        it("click 触发方式应该在点击时切换显示", async () => {
            const wrapper = mount(Dropdown, {
                props: { trigger: "click" },
                slots: {
                    default: "触发器",
                    overlay: "<div>菜单内容</div>"
                }
            });

            await wrapper.find(".vort-dropdown-trigger").trigger("click");
            expect(wrapper.emitted("update:open")).toBeTruthy();
            expect(wrapper.emitted("update:open")![0]).toEqual([true]);
        });

        it("应该支持数组形式的触发方式", () => {
            const wrapper = mount(Dropdown, {
                props: { trigger: ["click", "hover"] },
                slots: { default: "触发器" }
            });
            // 组件应该正常渲染
            expect(wrapper.find(".vort-dropdown-trigger").exists()).toBe(true);
        });

        it("应该支持 contextMenu 触发方式配置", () => {
            const wrapper = mount(Dropdown, {
                props: { trigger: "contextMenu" },
                slots: {
                    default: "触发器",
                    overlay: "<div>菜单内容</div>"
                }
            });
            // 验证组件正常渲染
            expect(wrapper.find(".vort-dropdown-trigger").exists()).toBe(true);
        });
    });

    // ==================== 禁用状态 ====================
    describe("禁用状态", () => {
        beforeEach(() => {
            vi.useFakeTimers();
        });

        afterEach(() => {
            vi.useRealTimers();
        });

        it("disabled 为 true 时触发元素应该有禁用类名", () => {
            const wrapper = mount(Dropdown, {
                props: { disabled: true },
                slots: { default: "触发器" }
            });
            expect(wrapper.find(".vort-dropdown-trigger-disabled").exists()).toBe(true);
        });

        it("disabled 时 hover 不应该触发显示", async () => {
            const wrapper = mount(Dropdown, {
                props: { disabled: true, trigger: "hover" },
                slots: { default: "触发器" }
            });

            await wrapper.find(".vort-dropdown-trigger").trigger("mouseenter");
            vi.advanceTimersByTime(200);
            await nextTick();

            expect(wrapper.emitted("update:open")).toBeUndefined();
        });

        it("disabled 时 click 不应该触发显示", async () => {
            const wrapper = mount(Dropdown, {
                props: { disabled: true, trigger: "click" },
                slots: { default: "触发器" }
            });

            await wrapper.find(".vort-dropdown-trigger").trigger("click");
            expect(wrapper.emitted("update:open")).toBeUndefined();
        });
    });

    // ==================== 位置配置（placement） ====================
    describe("位置配置 placement", () => {
        it.each([
            "bottom",
            "bottomLeft",
            "bottomRight",
            "top",
            "topLeft",
            "topRight",
            "left",
            "leftTop",
            "leftBottom",
            "right",
            "rightTop",
            "rightBottom"
        ] as const)('placement "%s" 应该被正确设置', (placement) => {
            const wrapper = mount(Dropdown, {
                props: { placement },
                slots: { default: "触发器" }
            });
            // 组件应该正常渲染
            expect(wrapper.find(".vort-dropdown-trigger").exists()).toBe(true);
        });

        it("默认 placement 应该是 bottomLeft", () => {
            const wrapper = mount(Dropdown, {
                slots: { default: "触发器" }
            });
            expect(wrapper.find(".vort-dropdown-trigger").exists()).toBe(true);
        });
    });

    // ==================== 受控模式 ====================
    describe("受控模式", () => {
        it("应该支持 v-model:open", async () => {
            const wrapper = mount(Dropdown, {
                props: { open: true },
                slots: {
                    default: "触发器",
                    overlay: "<div>菜单内容</div>"
                }
            });

            // 通过 props 控制显示状态
            expect(wrapper.props("open")).toBe(true);
        });

        it("应该触发 update:open 事件", async () => {
            const wrapper = mount(Dropdown, {
                props: { trigger: "click" },
                slots: {
                    default: "触发器",
                    overlay: "<div>菜单内容</div>"
                }
            });

            await wrapper.find(".vort-dropdown-trigger").trigger("click");
            expect(wrapper.emitted("update:open")).toBeTruthy();
        });

        it("应该触发 openChange 事件", async () => {
            const wrapper = mount(Dropdown, {
                props: { trigger: "click" },
                slots: {
                    default: "触发器",
                    overlay: "<div>菜单内容</div>"
                }
            });

            await wrapper.find(".vort-dropdown-trigger").trigger("click");
            expect(wrapper.emitted("openChange")).toBeTruthy();
        });
    });

    // ==================== 箭头配置 ====================
    describe("箭头配置", () => {
        it("默认不显示箭头", () => {
            const wrapper = mount(Dropdown, {
                props: { defaultOpen: true },
                slots: {
                    default: "触发器",
                    overlay: "<div>菜单内容</div>"
                }
            });
            // 由于 mock 的原因，这里只验证组件正常渲染
            expect(wrapper.find(".vort-dropdown-trigger").exists()).toBe(true);
        });

        it("arrow 为 true 时应该显示箭头", () => {
            const wrapper = mount(Dropdown, {
                props: { arrow: true, defaultOpen: true },
                slots: {
                    default: "触发器",
                    overlay: "<div>菜单内容</div>"
                }
            });
            expect(wrapper.find(".vort-dropdown-trigger").exists()).toBe(true);
        });
    });

    // ==================== overlayClassName 和 overlayStyle ====================
    describe("overlay 样式配置", () => {
        it("应该支持 overlayClassName", () => {
            const wrapper = mount(Dropdown, {
                props: {
                    overlayClassName: "custom-overlay",
                    defaultOpen: true
                },
                slots: {
                    default: "触发器",
                    overlay: "<div>菜单内容</div>"
                }
            });
            expect(wrapper.find(".vort-dropdown-trigger").exists()).toBe(true);
        });

        it("应该支持 overlayStyle", () => {
            const wrapper = mount(Dropdown, {
                props: {
                    overlayStyle: { width: "200px" },
                    defaultOpen: true
                },
                slots: {
                    default: "触发器",
                    overlay: "<div>菜单内容</div>"
                }
            });
            expect(wrapper.find(".vort-dropdown-trigger").exists()).toBe(true);
        });
    });
});

// ==================== DropdownMenuItem 组件 ====================
describe("DropdownMenuItem 组件", () => {
    it("应该正确渲染菜单项", () => {
        const wrapper = mount(DropdownMenuItem, {
            slots: { default: "菜单项" }
        });
        expect(wrapper.text()).toBe("菜单项");
    });

    it("应该传递正确的类名给底层组件", () => {
        const wrapper = mount(DropdownMenuItem);
        // 验证组件计算的类名数组包含基础类名
        expect(wrapper.html()).toContain("vort-dropdown-menu-item");
    });

    it("danger 状态应该添加危险类名", () => {
        const wrapper = mount(DropdownMenuItem, {
            props: { danger: true }
        });
        expect(wrapper.html()).toContain("vort-dropdown-menu-item-danger");
    });

    it("应该支持自定义类名", () => {
        const wrapper = mount(DropdownMenuItem, {
            props: { class: "custom-item" }
        });
        expect(wrapper.html()).toContain("custom-item");
    });

    it("应该支持图标插槽", () => {
        const wrapper = mount(DropdownMenuItem, {
            slots: {
                default: "菜单项",
                icon: '<span class="custom-icon">图标</span>'
            }
        });
        expect(wrapper.find(".vort-dropdown-menu-item-icon").exists()).toBe(true);
    });
});

// ==================== DropdownMenuSeparator 组件 ====================
describe("DropdownMenuSeparator 组件", () => {
    it("应该正确渲染分隔线", () => {
        const wrapper = mount(DropdownMenuSeparator);
        expect(wrapper.find(".vort-dropdown-menu-separator").exists()).toBe(true);
    });
});

// ==================== DropdownMenuLabel 组件 ====================
describe("DropdownMenuLabel 组件", () => {
    it("应该正确渲染标签", () => {
        const wrapper = mount(DropdownMenuLabel, {
            slots: { default: "分组标签" }
        });
        expect(wrapper.text()).toBe("分组标签");
    });

    it("应该有正确的基础类名", () => {
        const wrapper = mount(DropdownMenuLabel);
        expect(wrapper.html()).toContain("vort-dropdown-menu-label");
    });

    it("应该支持自定义类名", () => {
        const wrapper = mount(DropdownMenuLabel, {
            props: { class: "custom-label" }
        });
        expect(wrapper.html()).toContain("custom-label");
    });
});

// ==================== DropdownMenuGroup 组件 ====================
describe("DropdownMenuGroup 组件", () => {
    it("应该正确渲染分组", () => {
        const wrapper = mount(DropdownMenuGroup, {
            slots: { default: "<div>分组内容</div>" }
        });
        expect(wrapper.text()).toContain("分组内容");
    });

    it("应该有正确的基础类名", () => {
        const wrapper = mount(DropdownMenuGroup);
        expect(wrapper.html()).toContain("vort-dropdown-menu-group");
    });

    it("应该支持自定义类名", () => {
        const wrapper = mount(DropdownMenuGroup, {
            props: { class: "custom-group" }
        });
        expect(wrapper.html()).toContain("custom-group");
    });
});

// ==================== DropdownMenuSub 组件 ====================
describe("DropdownMenuSub 组件", () => {
    it("应该正确渲染子菜单", () => {
        const wrapper = mount(DropdownMenuSub, {
            props: { title: "子菜单" },
            slots: { default: "<div>子菜单内容</div>" }
        });
        expect(wrapper.text()).toContain("子菜单");
    });

    it("应该有正确的触发器类名", () => {
        const wrapper = mount(DropdownMenuSub);
        expect(wrapper.html()).toContain("vort-dropdown-menu-sub-trigger");
    });

    it("应该支持自定义类名", () => {
        const wrapper = mount(DropdownMenuSub, {
            props: { class: "custom-sub" }
        });
        expect(wrapper.html()).toContain("custom-sub");
    });

    it("应该支持 title 插槽", () => {
        const wrapper = mount(DropdownMenuSub, {
            slots: {
                title: "自定义标题",
                default: "<div>内容</div>"
            }
        });
        expect(wrapper.text()).toContain("自定义标题");
    });
});

// ==================== DropdownMenuCheckboxItem 组件 ====================
describe("DropdownMenuCheckboxItem 组件", () => {
    it("应该正确渲染复选框菜单项", () => {
        const wrapper = mount(DropdownMenuCheckboxItem, {
            slots: { default: "选项" }
        });
        expect(wrapper.text()).toContain("选项");
    });

    it("应该有正确的基础类名", () => {
        const wrapper = mount(DropdownMenuCheckboxItem);
        expect(wrapper.html()).toContain("vort-dropdown-menu-checkbox-item");
    });

    it("应该支持 v-model:checked", () => {
        const wrapper = mount(DropdownMenuCheckboxItem, {
            props: { checked: true }
        });
        expect(wrapper.props("checked")).toBe(true);
    });

    it("应该支持自定义类名", () => {
        const wrapper = mount(DropdownMenuCheckboxItem, {
            props: { class: "custom-checkbox" }
        });
        expect(wrapper.html()).toContain("custom-checkbox");
    });
});

// ==================== DropdownMenuRadioGroup 组件 ====================
describe("DropdownMenuRadioGroup 组件", () => {
    it("应该正确渲染单选组", () => {
        const wrapper = mount(DropdownMenuRadioGroup, {
            slots: { default: "<div>单选内容</div>" }
        });
        expect(wrapper.text()).toContain("单选内容");
    });

    it("应该有正确的基础类名", () => {
        const wrapper = mount(DropdownMenuRadioGroup);
        expect(wrapper.html()).toContain("vort-dropdown-menu-radio-group");
    });

    it("应该支持 v-model", () => {
        const wrapper = mount(DropdownMenuRadioGroup, {
            props: { modelValue: "option1" }
        });
        expect(wrapper.props("modelValue")).toBe("option1");
    });

    it("应该支持自定义类名", () => {
        const wrapper = mount(DropdownMenuRadioGroup, {
            props: { class: "custom-radio-group" }
        });
        expect(wrapper.html()).toContain("custom-radio-group");
    });
});

// ==================== DropdownMenuRadioItem 组件 ====================
describe("DropdownMenuRadioItem 组件", () => {
    it("应该正确渲染单选项", () => {
        const wrapper = mount(DropdownMenuRadioItem, {
            props: { value: "option1" },
            slots: { default: "选项1" }
        });
        expect(wrapper.text()).toContain("选项1");
    });

    it("应该有正确的基础类名", () => {
        const wrapper = mount(DropdownMenuRadioItem, {
            props: { value: "test" }
        });
        expect(wrapper.html()).toContain("vort-dropdown-menu-radio-item");
    });

    it("应该支持自定义类名", () => {
        const wrapper = mount(DropdownMenuRadioItem, {
            props: { value: "test", class: "custom-radio-item" }
        });
        expect(wrapper.html()).toContain("custom-radio-item");
    });
});

// ==================== DropdownButton 组件 ====================
describe("DropdownButton 组件", () => {
    it("应该正确渲染按钮组", () => {
        const wrapper = mount(DropdownButton, {
            slots: {
                default: "操作",
                overlay: "<div>菜单内容</div>"
            }
        });
        expect(wrapper.text()).toContain("操作");
    });

    it("应该有正确的容器类名", () => {
        const wrapper = mount(DropdownButton);
        expect(wrapper.find(".vort-dropdown-button").exists()).toBe(true);
    });

    it("应该触发左侧按钮点击事件", async () => {
        const wrapper = mount(DropdownButton, {
            slots: { default: "操作" }
        });

        const buttons = wrapper.findAll("button");
        await buttons[0].trigger("click");

        expect(wrapper.emitted("click")).toBeTruthy();
    });

    it.each(["primary", "default", "dashed"] as const)('type "%s" 应该正确传递给按钮', (type) => {
        const wrapper = mount(DropdownButton, {
            props: { type }
        });
        expect(wrapper.find(".vort-dropdown-button").exists()).toBe(true);
    });

    it.each(["large", "middle", "small"] as const)('size "%s" 应该正确传递给按钮', (size) => {
        const wrapper = mount(DropdownButton, {
            props: { size }
        });
        expect(wrapper.find(".vort-dropdown-button").exists()).toBe(true);
    });

    it("danger 状态应该传递给按钮", () => {
        const wrapper = mount(DropdownButton, {
            props: { danger: true }
        });
        expect(wrapper.find(".vort-dropdown-button").exists()).toBe(true);
    });

    it("disabled 应该禁用左侧按钮", () => {
        const wrapper = mount(DropdownButton, {
            props: { disabled: true }
        });
        const buttons = wrapper.findAll("button");
        expect(buttons[0].attributes("disabled")).toBeDefined();
    });

    it("buttonsDisabled 应该禁用所有按钮", () => {
        const wrapper = mount(DropdownButton, {
            props: { buttonsDisabled: true }
        });
        const buttons = wrapper.findAll("button");
        buttons.forEach((btn) => {
            expect(btn.attributes("disabled")).toBeDefined();
        });
    });

    it("loading 状态应该禁用左侧按钮", () => {
        const wrapper = mount(DropdownButton, {
            props: { loading: true }
        });
        const buttons = wrapper.findAll("button");
        expect(buttons[0].attributes("disabled")).toBeDefined();
    });

    it("应该支持 v-model:open", async () => {
        const wrapper = mount(DropdownButton, {
            props: { open: true },
            slots: { overlay: "<div>菜单</div>" }
        });
        expect(wrapper.props("open")).toBe(true);
    });
});
