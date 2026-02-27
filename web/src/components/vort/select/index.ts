// Select 组件导出
export { default as Select } from "./Select.vue";
export { default as SelectOption } from "./SelectOption.vue";

// 类型导出
export type { SelectSize, SelectStatus, SelectMode, SelectOption as SelectOptionType, SelectOptionContext, SelectProps, SelectEmits } from "./types";

// 以下为 shadcn-vue Select 原始子组件导出（用于高级自定义场景）
export { default as SelectContent } from "./SelectContent.vue";
export { default as SelectGroup } from "./SelectGroup.vue";
export { default as SelectItem } from "./SelectItem.vue";
export { default as SelectItemText } from "./SelectItemText.vue";
export { default as SelectLabel } from "./SelectLabel.vue";
export { default as SelectScrollDownButton } from "./SelectScrollDownButton.vue";
export { default as SelectScrollUpButton } from "./SelectScrollUpButton.vue";
export { default as SelectSeparator } from "./SelectSeparator.vue";
export { default as SelectTrigger } from "./SelectTrigger.vue";
export { default as SelectValue } from "./SelectValue.vue";
