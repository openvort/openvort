export { default as Tag } from "./Tag.vue";
export { default as CheckableTag } from "./CheckableTag.vue";
export { default as DraggableTags } from "./DraggableTags.vue";

// 类型导出
export type {
    // Tag 组件类型
    TagPresetStatusColor,
    TagPresetColor,
    TagColor,
    TagSize,
    TagProps,
    TagEmits,
    // CheckableTag 组件类型
    CheckableTagProps,
    CheckableTagEmits,
    // DraggableTags 组件类型
    TagItem,
    DraggableTagsProps,
    DraggableTagsEmits
} from "./types";
