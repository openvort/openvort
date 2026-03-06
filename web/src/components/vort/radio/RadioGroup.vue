<script setup lang="ts">
import { computed, provide, toRef, watch, ref, reactive } from "vue";
import type { RadioGroupProps, RadioOption, RadioOptionType } from "./types";

defineOptions({ name: "VortRadioGroup" });

/** Vort RadioGroup - 单选框组组件 */

const props = withDefaults(defineProps<RadioGroupProps>(), {
    disabled: false,
    size: "middle",
    buttonStyle: "outline"
});

const emit = defineEmits<{
    "update:modelValue": [value: string | number];
    change: [event: Event, value: string | number];
}>();

// ==================== RadioButton 注册机制 ====================
// 用于追踪子组件位置，解决 tooltip 等包装元素导致 CSS first/last 选择器失效的问题
// 同时用于自动检测是否使用了 vort-radio-button 子组件

// 已注册的 RadioButton uid 列表（按注册顺序）
const registeredButtons = reactive<number[]>([]);

// 计算实际的 optionType：
// 1. 用户显式设置 optionType 时，使用用户的值
// 2. 当有 RadioButton 子组件注册时（使用 vort-radio-button），默认为 "button"
// 3. 当 buttonStyle="solid" 时，默认为 "button"
// 4. 其他情况默认为 "default"
const actualOptionType = computed<RadioOptionType>(() => {
    if (props.optionType !== undefined) {
        return props.optionType;
    }
    // 当有 RadioButton 子组件注册时，自动切换为 button 模式
    if (registeredButtons.length > 0) {
        return "button";
    }
    return props.buttonStyle === "solid" ? "button" : "default";
});

// 内部值管理
const innerValue = ref<string | number | undefined>(props.modelValue ?? props.defaultValue);

// 监听 modelValue 变化
watch(
    () => props.modelValue,
    (newVal) => {
        if (newVal !== undefined) {
            innerValue.value = newVal;
        }
    }
);

// 注册 RadioButton
const registerButton = (uid: number) => {
    if (!registeredButtons.includes(uid)) {
        registeredButtons.push(uid);
    }
};

// 注销 RadioButton
const unregisterButton = (uid: number) => {
    const index = registeredButtons.indexOf(uid);
    if (index > -1) {
        registeredButtons.splice(index, 1);
    }
};

// 获取 RadioButton 的位置信息
const getButtonPosition = (uid: number) => {
    const index = registeredButtons.indexOf(uid);
    return {
        isFirst: index === 0,
        isLast: index === registeredButtons.length - 1
    };
};

// 提供给子组件的上下文
provide("radioGroupContext", {
    name: toRef(props, "name"),
    disabled: toRef(props, "disabled"),
    size: toRef(props, "size"),
    buttonStyle: toRef(props, "buttonStyle"),
    optionType: actualOptionType,
    value: innerValue,
    onChange: (value: string | number, event: Event) => {
        innerValue.value = value;
        emit("update:modelValue", value);
        emit("change", event, value);
    },
    // 注册机制
    registerButton,
    unregisterButton,
    getButtonPosition,
    // 响应式的按钮列表，用于触发位置重新计算
    registeredButtons
});

// 格式化 options
const normalizedOptions = computed(() => {
    if (!props.options) return [];
    return props.options.map((opt) => {
        if (typeof opt === "string" || typeof opt === "number") {
            return { label: String(opt), value: opt, disabled: false };
        }
        return opt;
    });
});

// 容器样式
const groupClasses = computed(() => {
    const classes = ["vort-radio-group"];
    // 计算 gap 样式
    // - buttonStyle="plain"（独立圆角按钮）：gap-2.5（10px）
    // - optionType="button"（outline/solid 边框合并）：gap-0
    // - 默认（普通 Radio 圆圈+文字）：gap-6（24px）
    if (props.buttonStyle === "plain") {
        // plain 风格：每个按钮独立圆角，需要间距
        classes.push("vort-radio-group-gap-plain");
    } else if (actualOptionType.value === "button") {
        // button 类型（outline/solid）：边框合并，无间距
        classes.push("vort-radio-group-gap-none");
    } else {
        classes.push("vort-radio-group-gap-default");
    }
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <div :class="groupClasses" role="radiogroup">
        <!-- 使用 options 配置 -->
        <template v-if="options && options.length > 0">
            <template v-if="actualOptionType === 'button'">
                <RadioButton v-for="opt in normalizedOptions" :key="opt.value" :value="opt.value" :disabled="opt.disabled">
                    {{ opt.label }}
                </RadioButton>
            </template>
            <template v-else>
                <Radio v-for="opt in normalizedOptions" :key="opt.value" :value="opt.value" :disabled="opt.disabled">
                    {{ opt.label }}
                </Radio>
            </template>
        </template>

        <!-- 使用 slot -->
        <slot v-else />
    </div>
</template>

<script lang="ts">
import Radio from "./Radio.vue";
import RadioButton from "./RadioButton.vue";

export default {
    components: {
        Radio,
        RadioButton
    }
};
</script>

<style scoped>
.vort-radio-group {
    display: inline-flex;
    flex-wrap: wrap;
}

.vort-radio-group-gap-default {
    gap: 24px;
}

.vort-radio-group-gap-plain {
    gap: 10px;
}

.vort-radio-group-gap-none {
    gap: 0;
}
</style>
